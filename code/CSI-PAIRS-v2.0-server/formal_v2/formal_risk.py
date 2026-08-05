from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

import numpy as np

from .formal_evidence import bind_rows, evidence_context
from .formal_io import artifact_manifest, parse_strict_json, sha256_file, write_csv, write_json
from .formal_metrics import (
    binary_nll,
    brier_score,
    expected_calibration_error,
    risk_coverage,
    spearman_correlation,
)
from .formal_protocol import typed_signed_edit


@dataclass(frozen=True)
class TemperatureCalibration:
    temperature: float

    def predict(self, score_difference: np.ndarray) -> np.ndarray:
        values = np.asarray(score_difference, dtype=np.float64) / float(self.temperature)
        return _sigmoid(values)


@dataclass(frozen=True)
class RobustStandardization:
    median: np.ndarray
    scale: np.ndarray

    def transform(self, values: np.ndarray) -> np.ndarray:
        return (np.asarray(values, dtype=np.float64) - self.median) / self.scale


@dataclass(frozen=True)
class SupportModel:
    center: np.ndarray
    covariance: np.ndarray
    threshold: float

    def squared_distance(self, values: np.ndarray) -> np.ndarray:
        delta = np.asarray(values, dtype=np.float64) - self.center
        inverse = np.linalg.inv(self.covariance)
        return np.einsum("bi,ij,bj->b", delta, inverse, delta)


@dataclass(frozen=True)
class ConstrainedRiskCalibration:
    intercept: float
    beta_d: float
    beta_u: float
    standardization: RobustStandardization
    support: SupportModel
    l2: float

    def predict(self, d_used: np.ndarray, uncertainty: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        raw = np.column_stack((d_used, uncertainty))
        standardized = np.clip(self.standardization.transform(raw), -5.0, 5.0)
        logits = self.intercept + self.beta_d * standardized[:, 0] + self.beta_u * standardized[:, 1]
        inside = self.support.squared_distance(standardized) <= self.support.threshold
        return _sigmoid(logits), inside

    def predict_components(
        self, d_used: np.ndarray, uncertainty: np.ndarray
    ) -> dict[str, np.ndarray]:
        raw = np.column_stack((d_used, uncertainty))
        standardized = np.clip(self.standardization.transform(raw), -5.0, 5.0)
        return {
            "d_only": _sigmoid(self.intercept + self.beta_d * standardized[:, 0]),
            "u_only": _sigmoid(self.intercept + self.beta_u * standardized[:, 1]),
            "joint": _sigmoid(
                self.intercept
                + self.beta_d * standardized[:, 0]
                + self.beta_u * standardized[:, 1]
            ),
        }


def frozen_map_proposals(
    supplied_map: np.ndarray,
    public_radio_config: np.ndarray,
    map_channel_names: np.ndarray,
    material_categories: int,
    config: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a frozen candidate set without CSI, route, identity, position, or outcome inputs."""
    world_map = np.asarray(supplied_map, dtype=np.float64)
    radio = np.asarray(public_radio_config, dtype=np.float64)
    names = [str(value) for value in np.asarray(map_channel_names).tolist()]
    if world_map.ndim != 3 or not np.all(np.isfinite(world_map)) or not np.all(np.isfinite(radio)):
        raise ValueError("map proposal inputs must be finite typed map and public radio arrays")
    for required in ("occupancy", "height", "material"):
        if required not in names:
            raise ValueError(f"map proposal requires {required!r} channel")
    occupancy_index = names.index("occupancy")
    height_index = names.index("height")
    material_index = names.index("material")
    seed_material = np.ascontiguousarray(world_map).tobytes() + np.ascontiguousarray(radio).tobytes()
    import hashlib

    digest_seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "little")
    rng = np.random.default_rng(digest_seed ^ int(config["risk"]["proposal_seed"]))
    cells = [(row, column) for row in range(world_map.shape[1]) for column in range(world_map.shape[2])]
    order = rng.permutation(len(cells))
    height_step = float(config["risk"]["proposal_height_step"])
    candidates = []
    for cell_index in order:
        row, column = cells[int(cell_index)]
        occupied = world_map[occupancy_index, row, column] >= 0.5
        operations = ("remove", "height_down", "height_up", "material") if occupied else ("add",)
        for operation in operations:
            candidate = world_map.copy()
            if operation == "remove":
                candidate[occupancy_index, row, column] = 0.0
                candidate[height_index, row, column] = 0.0
                candidate[material_index, row, column] = 0.0
            elif operation == "add":
                candidate[occupancy_index, row, column] = 1.0
                positive = world_map[height_index][world_map[height_index] > 0]
                candidate[height_index, row, column] = float(np.median(positive)) if positive.size else height_step
                materials = world_map[material_index][world_map[occupancy_index] >= 0.5].astype(np.int64)
                candidate[material_index, row, column] = int(np.bincount(materials, minlength=material_categories).argmax()) if materials.size else 1
            elif operation == "height_down":
                candidate[height_index, row, column] = max(0.0, candidate[height_index, row, column] - height_step)
            elif operation == "height_up":
                candidate[height_index, row, column] += height_step
            else:
                current = int(round(candidate[material_index, row, column]))
                candidate[material_index, row, column] = (current + 1) % int(material_categories)
            if not np.array_equal(candidate, world_map):
                candidates.append(candidate)
            if len(candidates) >= int(config["risk"]["proposal_count"]):
                break
        if len(candidates) >= int(config["risk"]["proposal_count"]):
            break
    if not candidates:
        raise RuntimeError("frozen map proposal library produced no legal candidates")
    maps = np.asarray(candidates)
    actions = np.asarray(
        [typed_signed_edit(world_map, candidate, map_channel_names, material_categories) for candidate in maps]
    )
    return maps, actions


def fit_temperature_no_intercept(
    score_difference: np.ndarray,
    labels: np.ndarray,
    config: dict,
) -> TemperatureCalibration:
    d = np.asarray(score_difference, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    log_temperature = 0.0
    learning_rate = float(config["risk"]["learning_rate"])
    for _ in range(int(config["risk"]["temperature_steps"])):
        temperature = np.exp(log_temperature)
        probability = _sigmoid(d / temperature)
        gradient = np.mean((probability - y) * (-d / temperature))
        log_temperature -= learning_rate * gradient
        log_temperature = float(np.clip(log_temperature, -8.0, 8.0))
    return TemperatureCalibration(float(np.exp(log_temperature)))


def fit_constrained_risk_calibrator(
    d_used: np.ndarray,
    uncertainty: np.ndarray,
    labels: np.ndarray,
    selection: tuple[np.ndarray, np.ndarray, np.ndarray],
    config: dict,
) -> ConstrainedRiskCalibration:
    raw = np.column_stack((d_used, uncertainty)).astype(np.float64)
    y = np.asarray(labels, dtype=np.float64)
    median = np.median(raw, axis=0)
    mad = np.median(np.abs(raw - median), axis=0)
    scale = 1.4826 * mad + float(config["risk"]["epsilon"])
    standardization = RobustStandardization(median=median, scale=scale)
    x = np.clip(standardization.transform(raw), -5.0, 5.0)
    selection_d, selection_u, selection_y = selection
    selection_x = np.clip(
        standardization.transform(np.column_stack((selection_d, selection_u))), -5.0, 5.0
    )
    candidates = []
    for l2 in config["risk"]["l2_grid"]:
        beta = np.zeros(3, dtype=np.float64)
        for _ in range(int(config["risk"]["logistic_steps"])):
            probability = _sigmoid(beta[0] + x @ beta[1:])
            gradient = np.asarray(
                [
                    np.mean(probability - y),
                    np.mean((probability - y) * x[:, 0]) + float(l2) * beta[1],
                    np.mean((probability - y) * x[:, 1]) + float(l2) * beta[2],
                ]
            )
            beta -= float(config["risk"]["learning_rate"]) * gradient
            beta[1] = min(beta[1], 0.0)
            beta[2] = max(beta[2], 0.0)
        selection_probability = _sigmoid(beta[0] + selection_x @ beta[1:])
        candidates.append((binary_nll(selection_y, selection_probability), float(l2), beta.copy()))
    _, selected_l2, selected_beta = min(candidates, key=lambda item: (item[0], item[1]))
    covariance = np.cov(x, rowvar=False) + float(config["risk"]["epsilon"]) * np.eye(2)
    center = np.mean(x, axis=0)
    inverse = np.linalg.inv(covariance)
    selection_delta = selection_x - center
    selection_distances = np.einsum(
        "bi,ij,bj->b", selection_delta, inverse, selection_delta
    )
    support = SupportModel(
        center=center,
        covariance=covariance,
        threshold=float(
            np.quantile(
                selection_distances, 1.0 - float(config["risk"]["support_alpha"])
            )
        ),
    )
    return ConstrainedRiskCalibration(
        intercept=float(selected_beta[0]),
        beta_d=float(selected_beta[1]),
        beta_u=float(selected_beta[2]),
        standardization=standardization,
        support=support,
        l2=selected_l2,
    )


def risk_metrics(labels, probabilities, errors, inside_support):
    y = np.asarray(labels, dtype=np.int64)
    p = np.asarray(probabilities, dtype=np.float64)
    error = np.asarray(errors, dtype=np.float64)
    inside = np.asarray(inside_support, dtype=np.bool_)
    if not np.any(inside):
        raise RuntimeError("risk calibration has empty common support")
    probability_metrics = {
        "ece": expected_calibration_error(y[inside], p[inside]),
        "brier": brier_score(y[inside], p[inside]),
        "nll": binary_nll(y[inside], p[inside]),
        "support_coverage": float(np.mean(inside)),
    }
    ranking = risk_coverage(error, p)
    probability_metrics.update(ranking)
    probability_metrics["risk_error_spearman"] = spearman_correlation(p, error)
    return probability_metrics


def run_risk_contract(
    config: dict,
    dataset,
    output_root: str | Path,
    arm_inputs: dict[str, dict[str, np.ndarray]],
) -> dict:
    """Fit source-only calibrators from prepared immutable features and audit target k=0."""
    from .formal_data_verification import require_verified_roles_from_root

    require_verified_roles_from_root(
        output_root,
        config,
        dataset,
        ("source_calibration_fit", "source_calibration_selection", "target"),
    )
    output_dir = Path(output_root) / "risk"
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    rows = []
    q_rows = []
    inside_by_arm = {}
    component_predictions = {}
    for arm, data in arm_inputs.items():
        temperature = fit_temperature_no_intercept(data["q_fit_d"], data["q_fit_y"], config)
        q_probability = temperature.predict(data["q_target_d"])
        q_rows.append(
            {
                "arm": arm,
                "route": "active_paired_only",
                "temperature": temperature.temperature,
                "ece": expected_calibration_error(data["q_target_y"], q_probability),
                "brier": brier_score(data["q_target_y"], q_probability),
                "nll": binary_nll(data["q_target_y"], q_probability),
                "candidate_order_randomized": True,
                "probability_semantics": "first_candidate_is_generating_map",
            }
        )
        calibrator = fit_constrained_risk_calibrator(
            data["fit_d"],
            data["fit_u"],
            data["fit_y"],
            (data["selection_d"], data["selection_u"], data["selection_y"]),
            config,
        )
        probabilities, inside = calibrator.predict(data["target_d"], data["target_u"])
        inside_by_arm[arm] = inside
        components = calibrator.predict_components(data["target_d"], data["target_u"])
        if not np.allclose(probabilities, components["joint"]):
            raise RuntimeError("joint risk probability implementation mismatch")
        component_predictions[arm] = components
        rows.append(
            {
                "arm": arm,
                "beta_d": calibrator.beta_d,
                "beta_u": calibrator.beta_u,
                "l2": calibrator.l2,
                "individual_support_coverage": float(np.mean(inside)),
            }
        )
    common = np.logical_and.reduce([inside_by_arm[arm] for arm in sorted(inside_by_arm)])
    metrics = []
    ranking_checks = []
    for arm, data in arm_inputs.items():
        for model_name, probabilities in component_predictions[arm].items():
            result = risk_metrics(data["target_y"], probabilities, data["target_error"], common)
            calibration_ci = _calibration_confidence_intervals(
                data["target_y"],
                probabilities,
                common,
                data["target_base_map_cluster_id"],
                int(config["risk"]["bootstrap_resamples"]),
                92000 + len(metrics),
            )
            metrics.append({"arm": arm, "risk_model": model_name, **result, **calibration_ci})
        cities = sorted(set(np.asarray(data["target_city_id"]).astype(str).tolist()))
        for city_index, city in enumerate(cities):
            selected = np.asarray(data["target_city_id"]).astype(str) == city
            error = np.asarray(data["target_error"], dtype=np.float64)[selected]
            joint = component_predictions[arm]["joint"][selected]
            u_only = component_predictions[arm]["u_only"][selected]
            joint_metrics = risk_coverage(error, joint)
            u_metrics = risk_coverage(error, u_only)
            random_aurc = _random_rejection_aurc(
                error,
                int(config["risk"]["bootstrap_resamples"]),
                93000 + city_index + 101 * len(ranking_checks),
            )
            ranking_checks.append(
                {
                    "arm": arm,
                    "city_id": city,
                    "joint_aurc": joint_metrics["aurc"],
                    "u_only_aurc": u_metrics["aurc"],
                    "random_rejection_aurc": random_aurc,
                    "joint_beats_u_only": joint_metrics["aurc"]
                    < u_metrics["aurc"] - float(config["risk"]["aurc_minimum_improvement"]),
                    "joint_beats_random": joint_metrics["aurc"]
                    < random_aurc - float(config["risk"]["aurc_minimum_improvement"]),
                    "coverage_error_monotonic": _coverage_error_monotonic(
                        joint_metrics["retained"],
                        float(config["risk"]["coverage_monotonic_tolerance"]),
                    ),
                    "retained": joint_metrics["retained"],
                }
            )
    write_csv(output_dir / "calibrators.csv", bind_rows(rows, evidence))
    write_csv(output_dir / "q_comp.csv", bind_rows(q_rows, evidence))
    write_csv(output_dir / "metrics.csv", bind_rows(metrics, evidence))
    write_json(
        output_dir / "ranking_checks.json",
        {"checks": ranking_checks, **evidence},
    )
    joint_metrics = [row for row in metrics if row["risk_model"] == "joint"]
    calibration_pass = all(
        row["ece_ci95_high"] <= float(config["risk"]["calibration_ece_max"])
        and row["brier_ci95_high"] <= float(config["risk"]["calibration_brier_max"])
        and row["nll_ci95_high"] <= float(config["risk"]["calibration_nll_max"])
        for row in joint_metrics
    )
    outside = {arm: 1.0 - float(np.mean(inside)) for arm, inside in inside_by_arm.items()}
    support_pass = bool(
        float(np.mean(common)) >= float(config["risk"]["common_support_minimum"])
        and outside["full"]
        <= outside["alignment"] + float(config["risk"]["outside_support_noninferiority_max"])
        and outside["full"]
        <= outside["response"] + float(config["risk"]["outside_support_noninferiority_max"])
    )
    ranking_pass = all(
        row["joint_beats_u_only"]
        and row["joint_beats_random"]
        and row["coverage_error_monotonic"]
        for row in ranking_checks
    )
    candidate_pass = bool(
        set(arm_inputs) == {"endpoint", "alignment", "response", "full"}
        and all(np.all(np.asarray(data["target_budget"]) == 0) for data in arm_inputs.values())
        and all(row["beta_d"] <= 0 and row["beta_u"] >= 0 for row in rows)
    )
    c9_subgates = {
        "1_frozen_candidates_k0_common_denominator": "PASS" if candidate_pass else "FAIL",
        "2_calibration_metrics_and_reliability_ci": "PASS" if calibration_pass else "FAIL",
        "3_common_support_and_full_oos_noninferiority": "PASS" if support_pass else "FAIL",
        "4_aurc_baselines_and_coverage_monotonicity": "PASS" if ranking_pass else "FAIL",
    }
    passed = all(value == "PASS" for value in c9_subgates.values())
    gate = {
        "schema_version": "csi-pairs-v6-risk-gate-v2",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        **evidence,
        "gate": "G6",
        "common_support_coverage": float(np.mean(common)),
        "outside_support_fraction": outside,
        "c9_subgates": c9_subgates,
        "q_comp_scope": "active paired candidates only; no null/gray/wrong-city probability claim",
        "scope": "frozen k=0 paired-proposal audit only",
    }
    write_json(output_dir / "gate.json", gate)
    write_json(
        output_dir / "manifest.json",
        {
            "schema_version": "csi-pairs-formal-stage-manifest-v2.1-v6",
            **evidence,
            "files": artifact_manifest(output_dir, evidence=evidence),
        },
    )
    return gate


def run_risk_feature_adapter(manifest_path, config, dataset, output_root):
    from .formal_io import read_strict_json

    manifest = read_strict_json(manifest_path)
    required = {
        "schema_version",
        "command",
        "implementation_revision",
        "proposal_library_revision",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("risk-feature adapter manifest fields must be exact")
    if manifest["schema_version"] != "csi-pairs-v6-risk-feature-adapter-v1":
        raise ValueError("risk-feature adapter manifest schema mismatch")
    if not isinstance(manifest["command"], list) or not manifest["command"]:
        raise ValueError("risk-feature adapter command must be nonempty argv")
    for key in ("implementation_revision", "proposal_library_revision"):
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise ValueError(f"risk-feature adapter {key} must be nonempty")
    output_dir = Path(output_root) / "risk_feature_adapter"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / "risk_features_v3.npz"
    command = [
        value.format(
            dataset=str(dataset.source_path),
            root=str(Path(output_root).resolve()),
            output=str(archive_path),
            python=sys.executable,
        )
        for value in manifest["command"]
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    (output_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0 or not archive_path.is_file():
        raise RuntimeError("risk-feature adapter failed")
    return load_risk_feature_archive(archive_path, config, dataset, output_root)


def _calibration_confidence_intervals(
    labels, probabilities, inside, cluster_ids, resamples, seed
):
    y = np.asarray(labels, dtype=np.int64)
    p = np.asarray(probabilities, dtype=np.float64)
    support = np.asarray(inside, dtype=np.bool_)
    clusters = np.asarray(cluster_ids).astype(str)
    unique = np.unique(clusters[support])
    if unique.size < 2:
        raise RuntimeError("calibration confidence interval requires two base-map clusters")
    rng = np.random.default_rng(int(seed))
    samples = {name: np.empty(int(resamples)) for name in ("ece", "brier", "nll")}
    for index in range(int(resamples)):
        selected_clusters = unique[rng.integers(0, unique.size, size=unique.size)]
        indices = np.concatenate([np.flatnonzero(support & (clusters == value)) for value in selected_clusters])
        samples["ece"][index] = expected_calibration_error(y[indices], p[indices])
        samples["brier"][index] = brier_score(y[indices], p[indices])
        samples["nll"][index] = binary_nll(y[indices], p[indices])
    return {
        f"{name}_ci95_low": float(np.percentile(values, 2.5))
        for name, values in samples.items()
    } | {
        f"{name}_ci95_high": float(np.percentile(values, 97.5))
        for name, values in samples.items()
    }


def _random_rejection_aurc(errors, resamples, seed):
    values = np.asarray(errors, dtype=np.float64)
    rng = np.random.default_rng(int(seed))
    aurc = [
        risk_coverage(values, rng.random(values.size))["aurc"]
        for _ in range(int(resamples))
    ]
    return float(np.mean(aurc))


def _coverage_error_monotonic(retained, tolerance):
    order = ("0.9", "0.75", "0.5")
    for metric in ("median_error", "p90_error"):
        values = [float(retained[coverage][metric]) for coverage in order]
        if any(values[index + 1] > values[index] + tolerance for index in range(2)):
            return False
    return True


def load_risk_feature_archive(
    path: str | Path, config, dataset, output_root: str | Path
) -> dict[str, dict[str, np.ndarray]]:
    required_suffixes = {
        "fit_d",
        "fit_u",
        "fit_y",
        "selection_d",
        "selection_u",
        "selection_y",
        "target_d",
        "target_u",
        "target_y",
        "target_error",
        "q_fit_d",
        "q_fit_y",
        "q_target_d",
        "q_target_y",
        "fit_unit_id",
        "fit_role",
        "selection_unit_id",
        "selection_role",
        "target_unit_id",
        "target_role",
        "target_budget",
        "target_base_map_cluster_id",
        "target_city_id",
        "target_position_role",
        "q_fit_unit_id",
        "q_fit_role",
        "q_target_unit_id",
        "q_target_role",
    }
    arms = ("endpoint", "alignment", "response", "full")
    with np.load(Path(path), allow_pickle=False) as archive:
        expected = {f"{arm}__{suffix}" for arm in arms for suffix in required_suffixes}
        expected.update(
            {
                "schema_version",
                "dataset_sha256",
                "config_sha256",
                "candidate_order_seed",
                "q_comp_route_contract",
                "proposal_contract_json",
                "checkpoint_index_sha256",
                "evaluation_manifest_sha256",
                "mixture_contract_json",
            }
        )
        if set(archive.files) != expected:
            raise ValueError(
                f"risk feature archive fields must be exact; missing={sorted(expected-set(archive.files))}, "
                f"unexpected={sorted(set(archive.files)-expected)}"
            )
        if str(np.asarray(archive["schema_version"]).item()) != "csi-pairs-v6-risk-features-v3":
            raise ValueError("risk feature archive schema mismatch")
        evidence = evidence_context(config, dataset, "CANDIDATE_NOT_CLAIM")
        if str(np.asarray(archive["dataset_sha256"]).item()) != evidence["dataset_sha256"]:
            raise ValueError("risk feature dataset hash mismatch")
        if str(np.asarray(archive["config_sha256"]).item()) != evidence["config_sha256"]:
            raise ValueError("risk feature config hash mismatch")
        root = Path(output_root)
        bindings = (
            ("checkpoint_index_sha256", root / "factorial" / "checkpoint_index.json"),
            ("evaluation_manifest_sha256", root / "evaluation" / "manifest.json"),
        )
        for field, bound_path in bindings:
            if not bound_path.is_file() or str(np.asarray(archive[field]).item()) != sha256_file(bound_path):
                raise ValueError(f"risk feature {field} does not bind the executed model/probe")
        if str(np.asarray(archive["q_comp_route_contract"]).item()) != "active_paired_only":
            raise ValueError("q_comp may only be calibrated on active paired candidates")
        proposal_contract = parse_strict_json(str(np.asarray(archive["proposal_contract_json"]).item()))
        _validate_proposal_contract(proposal_contract)
        mixture_contract = parse_strict_json(str(np.asarray(archive["mixture_contract_json"]).item()))
        if mixture_contract != {
            "schema_version": "csi-pairs-v6-risk-mixture-v1",
            "frozen_role": "source_method_selection",
            "proportions": config["risk"]["audit_mixture"],
        }:
            raise ValueError("risk feature archive uses the wrong frozen audit mixture")
        order_seed = int(np.asarray(archive["candidate_order_seed"]).item())
        output = {
            arm: {suffix: np.asarray(archive[f"{arm}__{suffix}"]) for suffix in required_suffixes}
            for arm in arms
        }
        for arm in arms:
            data = output[arm]
            _validate_binary_vector(data["q_fit_y"], "q_fit_y")
            _validate_binary_vector(data["q_target_y"], "q_target_y")
            expected_fit = randomized_candidate_labels(
                len(data["q_fit_y"]), order_seed
            )
            expected_target = randomized_candidate_labels(
                len(data["q_target_y"]), order_seed + 1
            )
            if not np.array_equal(data["q_fit_y"].astype(np.int64), expected_fit):
                raise ValueError(f"{arm} q_comp fit candidate order does not match the registered seed")
            if not np.array_equal(data["q_target_y"].astype(np.int64), expected_target):
                raise ValueError(f"{arm} q_comp target candidate order does not match the registered seed")
            _validate_arm_shapes(arm, data)
            _validate_split_identity(arm, data, dataset)
        reference = output[arms[0]]
        for arm in arms[1:]:
            for field in ("target_unit_id", "q_target_unit_id"):
                if not np.array_equal(output[arm][field].astype(str), reference[field].astype(str)):
                    raise ValueError(f"four-arm common support mismatch in {field}")
        return output


def randomized_candidate_labels(count: int, seed: int) -> np.ndarray:
    if count < 2:
        raise ValueError("q_comp requires at least two active paired examples")
    labels = np.random.default_rng(int(seed)).integers(0, 2, size=int(count), dtype=np.int64)
    if np.all(labels == labels[0]):
        raise ValueError("registered q_comp randomization produced a degenerate candidate order")
    return labels


def _validate_binary_vector(values: np.ndarray, name: str) -> None:
    array = np.asarray(values)
    if array.ndim != 1 or not np.all(np.isin(array, (0, 1))):
        raise ValueError(f"{name} must be a one-dimensional binary vector")


def _validate_arm_shapes(arm: str, data: dict[str, np.ndarray]) -> None:
    groups = (
        ("fit_d", "fit_u", "fit_y"),
        ("selection_d", "selection_u", "selection_y"),
        ("target_d", "target_u", "target_y", "target_error"),
        ("q_fit_d", "q_fit_y"),
        ("q_target_d", "q_target_y"),
    )
    for group in groups:
        lengths = {len(np.asarray(data[name])) for name in group}
        if len(lengths) != 1 or next(iter(lengths)) < 2:
            raise ValueError(f"{arm} risk feature lengths disagree for {group}")
        for name in group:
            values = np.asarray(data[name])
            if values.ndim != 1 or not np.all(np.isfinite(values)):
                raise ValueError(f"{arm} {name} must be a finite one-dimensional vector")


def _validate_split_identity(arm: str, data: dict[str, np.ndarray], dataset) -> None:
    contracts = (
        ("fit", "source_calibration_fit", "fit_y"),
        ("selection", "source_calibration_selection", "selection_y"),
        ("target", "target", "target_y"),
        ("q_fit", "source_calibration_fit", "q_fit_y"),
        ("q_target", "target", "q_target_y"),
    )
    for prefix, expected_role, length_field in contracts:
        identifiers = np.asarray(data[f"{prefix}_unit_id"]).astype(str)
        roles = np.asarray(data[f"{prefix}_role"]).astype(str)
        expected_length = len(np.asarray(data[length_field]))
        if identifiers.shape != (expected_length,) or roles.shape != (expected_length,):
            raise ValueError(f"{arm} {prefix} identity/role lengths do not match features")
        if np.any(identifiers == "") or len(set(identifiers.tolist())) != expected_length:
            raise ValueError(f"{arm} {prefix} unit IDs must be nonempty and unique")
        if set(roles.tolist()) != {expected_role}:
            raise ValueError(f"{arm} {prefix} uses the wrong permission role")
    budget = np.asarray(data["target_budget"])
    if budget.shape != np.asarray(data["target_y"]).shape or not np.all(budget == 0):
        raise ValueError(f"{arm} p_fail target audit must be strict k=0")
    target_length = len(np.asarray(data["target_y"]))
    for field in ("target_base_map_cluster_id", "target_city_id", "target_position_role"):
        values = np.asarray(data[field]).astype(str)
        if values.shape != (target_length,) or np.any(values == ""):
            raise ValueError(f"{arm} {field} must bind every target risk unit")
    if set(np.asarray(data["target_position_role"]).astype(str).tolist()) != {"query"}:
        raise ValueError(f"{arm} target support_pool leaked into risk denominator")
    allowed_clusters = set(
        str(value)
        for value in dataset.base_map_cluster_ids[dataset.indices_for_role("target")]
    )
    if not set(np.asarray(data["target_base_map_cluster_id"]).astype(str)).issubset(allowed_clusters):
        raise ValueError(f"{arm} risk archive has a non-target base-map cluster")


def _validate_proposal_contract(contract: object) -> None:
    expected = {
        "schema_version": "csi-pairs-v6-map-proposal-v1",
        "frozen_before_target": True,
        "k": 0,
        "input_allowlist": [
            "supplied_map",
            "public_radio_config",
            "registered_edit_library",
            "registered_seed",
        ],
        "forbidden_inputs": [
            "target_csi",
            "route",
            "effect_bin",
            "generating_side",
            "bank_id",
            "world_id",
            "receiver_position",
            "localization_result",
        ],
    }
    if contract != expected:
        raise ValueError("p_fail proposal contract is not the exact frozen map-only V6 contract")


def _sigmoid(values):
    values = np.asarray(values, dtype=np.float64)
    output = np.empty_like(values)
    positive = values >= 0
    output[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exponential = np.exp(values[~positive])
    output[~positive] = exponential / (1.0 + exponential)
    return output
