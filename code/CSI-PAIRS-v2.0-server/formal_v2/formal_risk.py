from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .formal_evidence import (
    bind_rows,
    evidence_context,
    require_manifested_formal_qualification,
)
from .formal_io import artifact_manifest, parse_strict_json, sha256_file, write_csv, write_json
from .formal_metrics import (
    binary_nll,
    brier_score,
    expected_calibration_error,
    risk_coverage,
    spearman_correlation,
)
from .formal_protocol import typed_signed_edit
from .formal_routing import ROUTE_NAMES
from .formal_statistics import holm_adjust


class FirstPartyRiskFeatures(dict):
    """Marker type emitted only by the reviewed replay path."""


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



@dataclass(frozen=True)
class ScalarRiskCalibration:
    intercept: float
    coefficient: float
    median: float
    scale: float
    l2: float
    direction: str

    def predict(self, values: np.ndarray) -> np.ndarray:
        standardized = np.clip(
            (np.asarray(values, dtype=np.float64) - self.median) / self.scale,
            -5.0,
            5.0,
        )
        return _sigmoid(self.intercept + self.coefficient * standardized)


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


def fit_scalar_risk_calibrator(
    values: np.ndarray,
    labels: np.ndarray,
    selection: tuple[np.ndarray, np.ndarray],
    config: dict,
    *,
    direction: str,
) -> ScalarRiskCalibration:
    """Fit and select a restricted one-feature control independently."""
    if direction not in {"nonpositive", "nonnegative"}:
        raise ValueError("scalar risk coefficient direction is invalid")
    raw = np.asarray(values, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    selection_values, selection_y = selection
    median = float(np.median(raw))
    scale = float(
        1.4826 * np.median(np.abs(raw - median)) + float(config["risk"]["epsilon"])
    )
    x = np.clip((raw - median) / scale, -5.0, 5.0)
    selection_x = np.clip(
        (np.asarray(selection_values, dtype=np.float64) - median) / scale,
        -5.0,
        5.0,
    )
    candidates = []
    for l2 in config["risk"]["l2_grid"]:
        beta = np.zeros(2, dtype=np.float64)
        for _ in range(int(config["risk"]["logistic_steps"])):
            probability = _sigmoid(beta[0] + beta[1] * x)
            gradient = np.asarray(
                [
                    np.mean(probability - y),
                    np.mean((probability - y) * x) + float(l2) * beta[1],
                ]
            )
            beta -= float(config["risk"]["learning_rate"]) * gradient
            beta[1] = min(beta[1], 0.0) if direction == "nonpositive" else max(beta[1], 0.0)
        probability = _sigmoid(beta[0] + beta[1] * selection_x)
        candidates.append(
            (binary_nll(np.asarray(selection_y), probability), float(l2), beta.copy())
        )
    _, selected_l2, selected_beta = min(candidates, key=lambda item: (item[0], item[1]))
    return ScalarRiskCalibration(
        intercept=float(selected_beta[0]),
        coefficient=float(selected_beta[1]),
        median=median,
        scale=scale,
        l2=selected_l2,
        direction=direction,
    )


def risk_metrics(labels, probabilities, errors, inside_support, cluster_ids=None):
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
    ranking = (
        _bank_macro_risk_coverage(error, p, cluster_ids)
        if cluster_ids is not None
        else risk_coverage(error, p)
    )
    probability_metrics.update(ranking)
    probability_metrics["risk_error_spearman"] = spearman_correlation(p, error)
    return probability_metrics


def _bank_macro_risk_coverage(errors, risk_scores, cluster_ids):
    error = np.asarray(errors, dtype=np.float64)
    risk = np.asarray(risk_scores, dtype=np.float64)
    clusters = np.asarray(cluster_ids).astype(str)
    if error.shape != risk.shape or error.shape != clusters.shape:
        raise ValueError("bank-macro risk inputs must be aligned")
    rows = []
    for cluster in np.unique(clusters):
        selected = clusters == cluster
        if int(np.sum(selected)) < 2:
            raise RuntimeError(f"risk cluster {cluster!r} has fewer than two observations")
        rows.append(risk_coverage(error[selected], risk[selected]))
    retained = {}
    for coverage in ("0.9", "0.75", "0.5"):
        retained[coverage] = {
            key: float(np.mean([row["retained"][coverage][key] for row in rows]))
            for key in ("median_error", "p90_error", "effective_coverage")
        }
    return {
        "aurc": float(np.mean([row["aurc"] for row in rows])),
        "retained": retained,
        "base_map_cluster_count": len(rows),
    }


def _cluster_mean_interval(values, clusters, resamples, seed):
    values = np.asarray(values, dtype=np.float64)
    clusters = np.asarray(clusters).astype(str)
    unique = np.unique(clusters)
    if unique.size < 2:
        raise RuntimeError("cluster interval requires at least two base-map clusters")
    per_cluster = np.asarray([np.mean(values[clusters == cluster]) for cluster in unique])
    rng = np.random.default_rng(int(seed))
    samples = np.empty(int(resamples), dtype=np.float64)
    for index in range(int(resamples)):
        samples[index] = float(
            np.mean(per_cluster[rng.integers(0, unique.size, size=unique.size)])
        )
    return {
        "estimate": float(np.mean(per_cluster)),
        "ci95_low": float(np.percentile(samples, 2.5)),
        "ci95_high": float(np.percentile(samples, 97.5)),
        "base_map_cluster_count": int(unique.size),
    }


def _cluster_ranking_contrast(
    errors, first_scores, second_scores, clusters, resamples, seed, null_threshold=0.0
):
    error = np.asarray(errors, dtype=np.float64)
    first = np.asarray(first_scores, dtype=np.float64)
    second = np.asarray(second_scores, dtype=np.float64)
    cluster = np.asarray(clusters).astype(str)
    unique = np.unique(cluster)
    if unique.size < 2:
        raise RuntimeError("AURC contrast requires at least two base-map clusters")
    improvements = []
    for value in unique:
        selected = cluster == value
        if int(np.sum(selected)) < 2:
            raise RuntimeError(f"risk cluster {value!r} has fewer than two observations")
        first_aurc = risk_coverage(error[selected], first[selected])["aurc"]
        second_aurc = risk_coverage(error[selected], second[selected])["aurc"]
        improvements.append(float(second_aurc - first_aurc))
    interval = _cluster_mean_interval(
        np.asarray(improvements), unique, resamples, seed
    )
    centered = np.asarray(improvements) - float(null_threshold)
    signs = np.random.default_rng(int(seed) + 1).choice(
        (-1.0, 1.0), size=(max(int(resamples), 1000), len(improvements))
    )
    null = np.mean(signs * centered[None, :], axis=1)
    observed = abs(float(np.mean(centered)))
    interval["p_value_two_sided"] = float((1 + np.sum(np.abs(null) >= observed)) / (len(null) + 1))
    return interval


def _cluster_value_contrast(
    first, second, clusters, resamples, seed, null_threshold=0.0
):
    first = np.asarray(first, dtype=np.float64)
    second = np.asarray(second, dtype=np.float64)
    cluster = np.asarray(clusters).astype(str)
    unique = np.unique(cluster)
    differences = np.asarray(
        [np.mean(first[cluster == value] - second[cluster == value]) for value in unique]
    )
    interval = _cluster_mean_interval(differences, unique, resamples, seed)
    centered = differences - float(null_threshold)
    signs = np.random.default_rng(int(seed) + 1).choice(
        (-1.0, 1.0), size=(max(int(resamples), 1000), len(differences))
    )
    null = np.mean(signs * centered[None, :], axis=1)
    observed = abs(float(np.mean(centered)))
    interval["p_value_two_sided"] = float(
        (1 + np.sum(np.abs(null) >= observed)) / (len(null) + 1)
    )
    return interval


def _cluster_monotonic_margin(
    errors, scores, clusters, resamples, seed, null_threshold=0.0
):
    error = np.asarray(errors, dtype=np.float64)
    risk = np.asarray(scores, dtype=np.float64)
    cluster = np.asarray(clusters).astype(str)
    unique = np.unique(cluster)
    margins = []
    for value in unique:
        selected = cluster == value
        curve = risk_coverage(error[selected], risk[selected])["retained"]
        medians = [curve[key]["median_error"] for key in ("0.9", "0.75", "0.5")]
        p90s = [curve[key]["p90_error"] for key in ("0.9", "0.75", "0.5")]
        margins.append(
            min(
                medians[0] - medians[1],
                medians[1] - medians[2],
                p90s[0] - p90s[1],
                p90s[1] - p90s[2],
            )
        )
    interval = _cluster_mean_interval(np.asarray(margins), unique, resamples, seed)
    centered = np.asarray(margins) - float(null_threshold)
    signs = np.random.default_rng(int(seed) + 1).choice(
        (-1.0, 1.0), size=(max(int(resamples), 1000), len(margins))
    )
    null = np.mean(signs * centered[None, :], axis=1)
    observed = abs(float(np.mean(centered)))
    interval["p_value_two_sided"] = float(
        (1 + np.sum(np.abs(null) >= observed)) / (len(null) + 1)
    )
    return interval


def run_risk_contract(
    config: dict,
    dataset,
    output_root: str | Path,
    arm_inputs: dict[str, dict[str, np.ndarray]],
) -> dict:
    """Fit source-only calibrators from prepared immutable features and audit target k=0."""
    if not isinstance(arm_inputs, FirstPartyRiskFeatures):
        raise RuntimeError(
            "risk contracts only accept features produced by first-party checkpoint replay"
        )
    if set(arm_inputs) != {"endpoint", "alignment", "response", "full"}:
        raise RuntimeError("risk replay must contain exactly the four frozen arms")
    reference = arm_inputs["endpoint"]
    for arm, data in arm_inputs.items():
        for field in (
            "fit_unit_id",
            "selection_unit_id",
            "target_unit_id",
            "target_base_map_cluster_id",
            "target_city_id",
            "target_position_role",
            "q_target_unit_id",
            "q_fit_unit_id",
        ):
            if not np.array_equal(np.asarray(data[field]), np.asarray(reference[field])):
                raise RuntimeError(f"four-arm common risk denominator mismatch: {arm}/{field}")
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
        d_only = fit_scalar_risk_calibrator(
            data["fit_d"],
            data["fit_y"],
            (data["selection_d"], data["selection_y"]),
            config,
            direction="nonpositive",
        )
        u_only = fit_scalar_risk_calibrator(
            data["fit_u"],
            data["fit_y"],
            (data["selection_u"], data["selection_y"]),
            config,
            direction="nonnegative",
        )
        probabilities, inside = calibrator.predict(data["target_d"], data["target_u"])
        inside_by_arm[arm] = inside
        components = {
            "d_only": d_only.predict(data["target_d"]),
            "u_only": u_only.predict(data["target_u"]),
            "joint": probabilities,
        }
        if not np.allclose(probabilities, components["joint"]):
            raise RuntimeError("joint risk probability implementation mismatch")
        component_predictions[arm] = components
        rows.append(
            {
                "arm": arm,
                "beta_d": calibrator.beta_d,
                "beta_u": calibrator.beta_u,
                "l2": calibrator.l2,
                "d_only_intercept": d_only.intercept,
                "d_only_beta": d_only.coefficient,
                "d_only_l2": d_only.l2,
                "u_only_intercept": u_only.intercept,
                "u_only_beta": u_only.coefficient,
                "u_only_l2": u_only.l2,
                "individual_support_coverage": float(np.mean(inside)),
            }
        )
    common = np.logical_and.reduce([inside_by_arm[arm] for arm in sorted(inside_by_arm)])
    metrics = []
    ranking_checks = []
    for arm, data in arm_inputs.items():
        for model_name, probabilities in component_predictions[arm].items():
            result = risk_metrics(
                data["target_y"],
                probabilities,
                data["target_error"],
                common,
                data["target_base_map_cluster_id"],
            )
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
            clusters = np.asarray(data["target_base_map_cluster_id"]).astype(str)[selected]
            random_scores = np.zeros_like(joint)
            joint_metrics = _bank_macro_risk_coverage(error, joint, clusters)
            u_metrics = _bank_macro_risk_coverage(error, u_only, clusters)
            random_metrics = _bank_macro_risk_coverage(error, random_scores, clusters)
            comparison_seed = 93000 + city_index + 101 * len(ranking_checks)
            joint_vs_u = _cluster_ranking_contrast(
                error,
                joint,
                u_only,
                clusters,
                int(config["risk"]["bootstrap_resamples"]),
                comparison_seed,
                float(config["risk"]["aurc_minimum_improvement"]),
            )
            joint_vs_random = _cluster_ranking_contrast(
                error,
                joint,
                random_scores,
                clusters,
                int(config["risk"]["bootstrap_resamples"]),
                comparison_seed + 1,
                float(config["risk"]["aurc_minimum_improvement"]),
            )
            monotonic = _cluster_monotonic_margin(
                error,
                joint,
                clusters,
                int(config["risk"]["bootstrap_resamples"]),
                comparison_seed + 2,
                -float(config["risk"]["coverage_monotonic_tolerance"]),
            )
            ranking_checks.append(
                {
                    "arm": arm,
                    "city_id": city,
                    "joint_aurc": joint_metrics["aurc"],
                    "u_only_aurc": u_metrics["aurc"],
                    "random_rejection_aurc": random_metrics["aurc"],
                    "joint_vs_u_only": joint_vs_u,
                    "joint_vs_random": joint_vs_random,
                    "coverage_monotonic_margin": monotonic,
                    "retained": joint_metrics["retained"],
                }
            )
    ranking_family = [
        interval
        for row in ranking_checks
        for interval in (
            row["joint_vs_u_only"],
            row["joint_vs_random"],
            row["coverage_monotonic_margin"],
        )
    ]
    adjusted = holm_adjust([row["p_value_two_sided"] for row in ranking_family])
    for interval, value in zip(ranking_family, adjusted):
        interval["holm_adjusted_p"] = float(value)
    alpha = float(config["evaluation"]["familywise_alpha"])
    for row in ranking_checks:
        row["joint_beats_u_only"] = bool(
            row["joint_vs_u_only"]["ci95_low"]
            > float(config["risk"]["aurc_minimum_improvement"])
            and row["joint_vs_u_only"]["holm_adjusted_p"] < alpha
        )
        row["joint_beats_random"] = bool(
            row["joint_vs_random"]["ci95_low"]
            > float(config["risk"]["aurc_minimum_improvement"])
            and row["joint_vs_random"]["holm_adjusted_p"] < alpha
        )
        row["coverage_error_monotonic"] = bool(
            row["coverage_monotonic_margin"]["ci95_low"]
            >= -float(config["risk"]["coverage_monotonic_tolerance"])
            and row["coverage_monotonic_margin"]["holm_adjusted_p"] < alpha
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
    reference_clusters = np.asarray(
        arm_inputs["endpoint"]["target_base_map_cluster_id"]
    ).astype(str)
    common_support_interval = _cluster_mean_interval(
        common.astype(np.float64),
        reference_clusters,
        int(config["risk"]["bootstrap_resamples"]),
        94000,
    )
    outside_intervals = {
        arm: _cluster_mean_interval(
            (~inside).astype(np.float64),
            reference_clusters,
            int(config["risk"]["bootstrap_resamples"]),
            94010 + index,
        )
        for index, (arm, inside) in enumerate(sorted(inside_by_arm.items()))
    }
    outside = {arm: interval["estimate"] for arm, interval in outside_intervals.items()}
    support_contrasts = {
        arm: _cluster_value_contrast(
            (~inside_by_arm[arm]).astype(np.float64),
            (~inside_by_arm["full"]).astype(np.float64),
            reference_clusters,
            int(config["risk"]["bootstrap_resamples"]),
            94100 + index,
            -float(config["risk"]["outside_support_noninferiority_max"]),
        )
        for index, arm in enumerate(("alignment", "response"))
    }
    support_adjusted = holm_adjust(
        [value["p_value_two_sided"] for value in support_contrasts.values()]
    )
    for value, adjusted_p in zip(support_contrasts.values(), support_adjusted):
        value["holm_adjusted_p"] = float(adjusted_p)
    support_pass = bool(
        common_support_interval["ci95_low"]
        >= float(config["risk"]["common_support_minimum"])
        and all(
            value["ci95_low"]
            >= -float(config["risk"]["outside_support_noninferiority_max"])
            and value["holm_adjusted_p"] < alpha
            for value in support_contrasts.values()
        )
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
        and all(
            row["beta_d"] < 0
            and row["beta_u"] > 0
            and row["d_only_beta"] < 0
            and row["u_only_beta"] > 0
            for row in rows
        )
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
        "common_support_coverage": common_support_interval["estimate"],
        "common_support_interval": common_support_interval,
        "outside_support_fraction": outside,
        "outside_support_intervals": outside_intervals,
        "outside_support_noninferiority": support_contrasts,
        "c9_subgates": c9_subgates,
        "q_comp_scope": "active paired candidates only; no null/gray/wrong-city probability claim",
        "scope": "frozen k=0 paired-proposal audit only",
        "feature_generation": "first-party checkpoint/data/proposal replay",
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
    source_sha256 = sha256_file(Path(__file__).resolve())
    if manifest["implementation_revision"] != source_sha256:
        raise RuntimeError(
            "risk features must bind the reviewed first-party formal_risk.py revision"
        )
    if manifest["proposal_library_revision"] != "csi-pairs-v6-map-proposal-v1":
        raise RuntimeError("risk proposal library revision is not frozen V6")
    write_json(
        output_dir / "replay_manifest.json",
        {
            "schema_version": "csi-pairs-v6-risk-first-party-replay-v1",
            "implementation_source_sha256": source_sha256,
            "proposal_library_revision": manifest["proposal_library_revision"],
            "external_command_ignored": True,
            "reason": "risk features are recomputed from authenticated checkpoints and data",
        },
    )
    return build_first_party_risk_features(config, dataset, output_root)


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


def build_first_party_risk_features(config, dataset, output_root):
    """Recompute immutable risk features from the reviewed model and dataset code."""
    from .formal_evaluation import (
        _load_model,
        _masked_alignment_state_and_score,
        _normalized_scene_patches,
        _validate_checkpoint_index,
    )
    from .formal_factorial import (
        _natural_representations,
        _normalized_action,
        _normalized_map,
        _normalized_radio,
        _training_normalization,
    )
    from .formal_io import read_strict_json
    from .formal_localization import fit_source_position_head, predict_position_distribution
    from .formal_protocol import patchify_csi, zero_typed_edit
    from .formal_routing import ROUTE_NAMES, fit_route_normalization, route_dataset
    from .formal_teacher import load_teacher_bundle

    root = Path(output_root)
    qualification = read_strict_json(root / "qualification" / "gate.json")
    qualification = require_manifested_formal_qualification(
        qualification,
        config,
        dataset,
        allow_nonscientific_fixture=True,
    )
    teacher = load_teacher_bundle(qualification["teacher_checkpoint"], config)
    route_normalization = fit_route_normalization(dataset, teacher)
    normalization = _training_normalization(
        dataset,
        dataset.indices_for_role("source_encoder_train"),
        route_normalization,
        teacher.patch_spec,
    )
    checkpoint_index = read_strict_json(root / "factorial" / "checkpoint_index.json")
    checkpoint_rows = _validate_checkpoint_index(
        checkpoint_index, config, dataset, qualification
    )
    role_examples = {}
    routed_by_role = {}
    for role in ("source_calibration_fit", "source_calibration_selection", "target"):
        scenes = dataset.indices_for_role(role)
        routed = route_dataset(
            dataset, teacher, config, scenes, normalization=route_normalization
        )
        routed_by_role[role] = routed
        role_examples[role] = _risk_audit_examples(dataset, routed, config, role)

    replayed = {}
    order_seed = int(config["risk"]["proposal_seed"]) + 701
    for checkpoint_row in checkpoint_rows:
        arm = str(checkpoint_row["arm"])
        seed = int(checkpoint_row["seed"])
        model = _load_model(
            root / "factorial", checkpoint_row, qualification, config, dataset
        )
        source_scenes = [
            int(value) for value in dataset.indices_for_role("source_encoder_train")
        ]
        source_representations = _natural_representations(
            model, dataset, source_scenes, normalization, teacher.patch_spec
        )
        source_x = np.vstack(
            [source_representations[scene] for scene in source_scenes]
        )
        source_y = np.vstack([dataset.positions[scene] for scene in source_scenes])
        head = fit_source_position_head(source_x, source_y, config, seed=seed + 17003)
        arm_data = {}
        for prefix, role in (
            ("fit", "source_calibration_fit"),
            ("selection", "source_calibration_selection"),
            ("target", "target"),
        ):
            values = _replay_risk_examples(
                model,
                head,
                dataset,
                teacher,
                config,
                normalization,
                routed_by_role[role],
                role_examples[role],
                arm,
                seed,
                _masked_alignment_state_and_score,
                _normalized_scene_patches,
                _normalized_map,
                _normalized_radio,
                _normalized_action,
                zero_typed_edit,
                patchify_csi,
                predict_position_distribution,
            )
            arm_data[f"{prefix}_d"] = values["d"]
            arm_data[f"{prefix}_u"] = values["u"]
            arm_data[f"{prefix}_y"] = values["y"]
            arm_data[f"{prefix}_unit_id"] = values["unit_id"]
            arm_data[f"{prefix}_role"] = np.asarray([role] * len(values["y"]))
            if prefix == "target":
                arm_data["target_error"] = values["error"]
                arm_data["target_budget"] = np.zeros(len(values["y"]), dtype=np.int64)
                arm_data["target_base_map_cluster_id"] = values["cluster"]
                arm_data["target_city_id"] = values["city"]
                arm_data["target_position_role"] = np.asarray(
                    ["query"] * len(values["y"])
                )
            active = values["condition"] == "active"
            if prefix in {"fit", "target"}:
                labels = randomized_candidate_labels(
                    int(np.sum(active)), order_seed + (0 if prefix == "fit" else 1)
                )
                margin = values["paired_margin"][active]
                q_prefix = "q_fit" if prefix == "fit" else "q_target"
                arm_data[f"{q_prefix}_d"] = np.where(labels == 1, margin, -margin)
                arm_data[f"{q_prefix}_y"] = labels
                arm_data[f"{q_prefix}_unit_id"] = np.asarray(
                    [f"q:{value}" for value in values["unit_id"][active]]
                )
                arm_data[f"{q_prefix}_role"] = np.asarray(
                    [role] * len(labels)
                )
        replayed.setdefault(arm, []).append(arm_data)
    output = FirstPartyRiskFeatures({
        arm: {
            field: np.concatenate([row[field] for row in rows], axis=0)
            for field in rows[0]
        }
        for arm, rows in replayed.items()
    })
    expected_arms = {"endpoint", "alignment", "response", "full"}
    if set(output) != expected_arms:
        raise RuntimeError("first-party risk replay did not cover the four frozen arms")
    return output


def _risk_audit_examples(dataset, routed, config, role):
    groups = {name: [] for name in ("correct", "active", "gray", "null")}
    for scene_value in dataset.indices_for_role(role):
        scene = int(scene_value)
        positions = range(dataset.position_count)
        if role == "target":
            positions = np.flatnonzero(dataset.position_roles[scene] == "query").tolist()
        for world in range(dataset.world_count):
            for position in positions:
                groups["correct"].append((scene, world, world, int(position), "correct"))
        for edge in dataset.directed_edges(scene):
            for position in positions:
                key = (scene, edge.source_world, edge.target_world, int(position))
                condition = str(ROUTE_NAMES[routed.alignment_route[key]])
                if condition in groups:
                    groups[condition].append(
                        (
                            scene,
                            edge.source_world,
                            edge.target_world,
                            int(position),
                            condition,
                        )
                    )
    proportions = config["risk"]["audit_mixture"]
    if set(proportions) != set(groups) or not np.isclose(sum(proportions.values()), 1.0):
        raise RuntimeError("risk audit mixture is not a complete probability vector")
    if any(not groups[name] for name in groups):
        raise RuntimeError(f"risk role {role} lacks one or more frozen audit conditions")
    total = min(len(groups[name]) / float(proportions[name]) for name in groups)
    selected = []
    for name in sorted(groups):
        count = max(2, int(np.floor(total * float(proportions[name]))))
        if count > len(groups[name]):
            raise RuntimeError(f"risk role {role} cannot realize its frozen {name} mixture")
        selected.extend(sorted(groups[name])[:count])
    return sorted(selected, key=lambda row: (row[0], row[3], row[1], row[2], row[4]))


def _replay_risk_examples(
    model,
    head,
    dataset,
    teacher,
    config,
    normalization,
    routed,
    examples,
    arm,
    seed,
    masked_score,
    normalized_patches,
    normalized_map,
    normalized_radio,
    normalized_action,
    zero_edit,
    patchify,
    predict_position,
):
    import torch

    representations = []
    d_values = []
    margins = []
    identifiers = []
    conditions = []
    clusters = []
    cities = []
    zero = zero_edit(
        (1,),
        dataset.maps.shape[-1],
        int(dataset.metadata["assets"]["material_category_count"]),
    )
    zero_tensor = torch.as_tensor(
        normalized_action(normalization, zero), dtype=torch.float32
    )
    mask_bank = tuple(entry for entry in teacher.mask_bank if entry.mode == "random_75")
    for scene, observed_world, supplied_world, position, condition in examples:
        raw = patchify(dataset.csi[scene, observed_world, position], teacher.patch_spec)
        patches = (raw - normalization.patch_mean) / normalization.patch_scale
        map_value = normalized_map(normalization, dataset.maps[scene, supplied_world])
        radio_value = normalized_radio(
            normalization, dataset.radio_config[scene], dataset.bs_pose[scene]
        )
        with torch.no_grad():
            representation = model.retained_representation(
                torch.as_tensor(patches[None], dtype=torch.float32),
                torch.as_tensor(map_value[None], dtype=torch.float32),
                torch.as_tensor(radio_value[None], dtype=torch.float32),
            )[0]
        representations.append(representation.detach().cpu().numpy())

        physical = normalized_patches(
            dataset,
            normalization,
            teacher.patch_spec,
            scene,
            observed_world,
            position,
        )
        latent = routed.teacher_latent[scene][observed_world, position]

        def energy(map_array):
            with torch.no_grad():
                _, value = masked_score(
                    model,
                    torch.as_tensor(patches[None], dtype=torch.float32),
                    torch.as_tensor(
                        normalized_map(normalization, map_array)[None],
                        dtype=torch.float32,
                    ),
                    torch.as_tensor(radio_value[None], dtype=torch.float32),
                    zero_tensor,
                    mask_bank,
                    latent,
                    physical,
                    normalization,
                )
            return float(value)

        used_energy = energy(dataset.maps[scene, supplied_world])
        proposal_maps, _ = frozen_map_proposals(
            dataset.maps[scene, supplied_world],
            dataset.radio_config[scene],
            dataset.map_channel_names,
            int(dataset.metadata["assets"]["material_category_count"]),
            config,
        )
        candidate_energies = np.asarray([energy(value) for value in proposal_maps])
        d_values.append(float(np.min(candidate_energies - used_energy)))
        matched_energy = energy(dataset.maps[scene, observed_world])
        margins.append(float(used_energy - matched_energy))
        identifiers.append(
            f"risk:{seed}:{scene}:{observed_world}:{supplied_world}:{position}:{condition}"
        )
        conditions.append(condition)
        clusters.append(str(dataset.base_map_cluster_ids[scene]))
        cities.append(str(dataset.city_ids[scene]))
    representation = np.asarray(representations, dtype=np.float64)
    prediction, _, uncertainty = predict_position(
        head,
        representation,
        sigma_min=float(config["localization"]["sigma_min"]),
    )
    truth = np.asarray(
        [dataset.positions[scene, position] for scene, _, _, position, _ in examples],
        dtype=np.float64,
    )
    error = np.linalg.norm(prediction - truth, axis=1)
    return {
        "d": np.asarray(d_values, dtype=np.float64),
        "u": np.asarray(uncertainty, dtype=np.float64),
        "y": (error > float(config["localization"]["failure_threshold_m"])).astype(np.int64),
        "error": error,
        "unit_id": np.asarray(identifiers),
        "condition": np.asarray(conditions),
        "paired_margin": np.asarray(margins, dtype=np.float64),
        "cluster": np.asarray(clusters),
        "city": np.asarray(cities),
    }


def load_risk_feature_archive(
    path: str | Path, config, dataset, output_root: str | Path
) -> dict[str, dict[str, np.ndarray]]:
    raise RuntimeError(
        "external risk feature archives are not admissible evidence; use first-party "
        "build_first_party_risk_features so proposals, model outputs, and labels are replayed"
    )
    # Kept below as a reader for forensic compatibility with legacy v3 artifacts.
    # It is deliberately unreachable from scientific execution.
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
