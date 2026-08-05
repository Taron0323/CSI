from __future__ import annotations

import csv
import subprocess
from pathlib import Path

import numpy as np

from .formal_evidence import (
    bind_rows,
    complete_gate_vector,
    evidence_context,
    require_stage_manifested_gate,
)
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_csv, write_json
from .formal_statistics import interval_decision, paired_cluster_interval


CONTROL_IDS = (
    "equal_flop_alignment",
    "equal_flop_response",
    "parameter_matched_concat",
    "flop_matched_concat",
    "generous_2x_concat",
)


def run_resource_controls(config, dataset, manifest_path, output_root):
    from .formal_data_verification import require_verified_roles_from_root

    require_verified_roles_from_root(
        output_root,
        config,
        dataset,
        ("source_encoder_train", "source_method_selection", "target"),
    )
    manifest = read_strict_json(manifest_path)
    _validate_manifest(manifest)
    root = Path(output_root)
    output_dir = root / "controls"
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    main_rows = _read_localization(root / "factorial" / "localization_per_bank.csv", evidence)
    full_utility = _utility(main_rows, "full", config["localization"]["primary_budgets"])
    main_resource = _main_resource(root / "factorial" / "training_summary.csv")
    result_rows = []
    resource_rows = []
    utilities = {}
    for adapter in manifest["controls"]:
        control_id = adapter["control_id"]
        target = output_dir / control_id
        target.mkdir(parents=True, exist_ok=True)
        command = [
            value.format(dataset=str(dataset.source_path), output=str(target), root=str(root))
            for value in adapter["command"]
        ]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        (target / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (target / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(f"resource control {control_id} failed with code {completed.returncode}")
        rows = _read_localization(target / "localization_per_bank.csv", evidence)
        if {row["arm"] for row in rows} != {control_id}:
            raise RuntimeError(f"resource control {control_id} emitted an incorrect arm name")
        resource = read_strict_json(target / "resource.json")
        _validate_resource(control_id, resource, evidence, target)
        if _localization_cells(rows) != _localization_cells(main_rows):
            raise RuntimeError(f"resource control {control_id} changes the frozen J estimand cells")
        utilities[control_id] = _utility(rows, control_id, config["localization"]["primary_budgets"])
        result_rows.extend(rows)
        resource_rows.append(resource)
    write_csv(output_dir / "localization_per_bank.csv", bind_rows(result_rows, evidence))
    write_csv(output_dir / "resource_summary.csv", bind_rows(resource_rows, evidence))
    tolerance = float(config["evaluation"]["resource_match_relative_tolerance"])
    matches = _resource_matches(main_resource, resource_rows, tolerance)
    equal_intervals = {
        name: _control_superiority_interval(
            main_rows,
            rows=[row for row in result_rows if row["arm"] == name],
            resamples=int(config["evaluation"]["bootstrap_resamples"]),
            seed=84000 + index,
        )
        for index, name in enumerate(CONTROL_IDS[:2])
    }
    concat_intervals = {
        name: _control_superiority_interval(
            main_rows,
            rows=[row for row in result_rows if row["arm"] == name],
            resamples=int(config["evaluation"]["bootstrap_resamples"]),
            seed=84100 + index,
        )
        for index, name in enumerate(CONTROL_IDS[2:])
    }
    gate6 = bool(
        matches["equal_flop_alignment"]
        and matches["equal_flop_response"]
        and all(
            interval_decision(
                value,
                threshold=float(config["evaluation"]["minimum_equal_flop_superiority"]),
                relation="superiority",
            )
            for value in equal_intervals.values()
        )
    )
    gate7 = bool(
        all(matches[name] for name in CONTROL_IDS[2:])
        and all(
            interval_decision(
                value,
                threshold=float(config["evaluation"]["minimum_concat_superiority"]),
                relation="superiority",
            )
            for value in concat_intervals.values()
        )
    )
    evaluation_gate = read_strict_json(root / "evaluation" / "gate.json")
    require_stage_manifested_gate(
        root / "evaluation" / "gate.json",
        evaluation_gate,
        config,
        dataset,
        schema_version="csi-pairs-v6-evaluation-gate-v2",
    )
    subgates = dict(evaluation_gate["g4_subgates"])
    subgates["6_equal_flop_single_branch_superiority"] = "PASS" if gate6 else "FAIL"
    subgates["7_parameter_and_flop_matched_concat_superiority"] = "PASS" if gate7 else "FAIL"
    g4 = "PASS" if all(value == "PASS" for value in subgates.values()) else "FAIL"
    gate = {
        "schema_version": "csi-pairs-v6-resource-control-gate-v2",
        "status": "PASS" if g4 == "PASS" else "FAIL",
        "passed": g4 == "PASS",
        **evidence,
        "gate_vector": complete_gate_vector({"G4": g4}),
        "g4_subgates": subgates,
        "main_full_utility": full_utility,
        "control_utilities": utilities,
        "resource_matches": matches,
        "equal_flop_superiority_intervals": equal_intervals,
        "concat_superiority_intervals": concat_intervals,
        "relative_tolerance": tolerance,
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


def _validate_manifest(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "controls"}:
        raise ValueError("resource-control manifest fields must be exact")
    if manifest["schema_version"] != "csi-pairs-v6-resource-controls-v1":
        raise ValueError("resource-control manifest schema mismatch")
    controls = manifest["controls"]
    if not isinstance(controls, list) or {item.get("control_id") for item in controls} != set(CONTROL_IDS):
        raise ValueError("resource-control manifest must contain the exact five V6 controls")
    for item in controls:
        if set(item) != {"control_id", "command"} or not isinstance(item["command"], list) or not item["command"]:
            raise ValueError("resource-control adapter fields must be exact")


def _read_localization(path, evidence):
    if not path.is_file():
        raise RuntimeError(f"missing localization control artifact: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "arm", "city_id", "bank_id", "base_map_cluster_id", "seed", "budget", "draw",
        "utility_neg_log_median", "dataset_sha256", "config_sha256", "fixture",
    }
    if not rows or any(not required.issubset(row) for row in rows):
        raise RuntimeError("localization control rows are missing V6 estimand fields")
    for row in rows:
        if row["dataset_sha256"] != str(evidence["dataset_sha256"]):
            raise RuntimeError("localization control dataset hash mismatch")
        if row["config_sha256"] != str(evidence["config_sha256"]):
            raise RuntimeError("localization control config hash mismatch")
        expected_fixture = "True" if evidence["fixture"] else "False"
        if row["fixture"] != expected_fixture:
            raise RuntimeError("localization control fixture status mismatch")
        row["seed"] = int(row["seed"])
        row["budget"] = int(row["budget"])
        row["draw"] = int(row["draw"])
        row["utility_neg_log_median"] = float(row["utility_neg_log_median"])
        for key in ("artifact_label", "dataset_sha256", "config_sha256", "fixture", "scientific_use"):
            row.pop(key, None)
    return rows


def _utility(rows, arm, budgets):
    selected = [row for row in rows if row["arm"] == arm and row["budget"] in set(map(int, budgets))]
    cities = sorted({row["city_id"] for row in selected})
    if not cities:
        raise RuntimeError(f"control {arm} has no primary-budget rows")
    city_values = []
    for city in cities:
        budget_values = []
        for budget in map(int, budgets):
            bank_values = []
            banks = sorted({row["base_map_cluster_id"] for row in selected if row["city_id"] == city and row["budget"] == budget})
            if not banks:
                raise RuntimeError(f"control {arm} is missing city={city}, k={budget}")
            for bank in banks:
                values = [row["utility_neg_log_median"] for row in selected if row["city_id"] == city and row["budget"] == budget and row["base_map_cluster_id"] == bank]
                bank_values.append(float(np.mean(values)))
            budget_values.append(float(np.mean(bank_values)))
        city_values.append(float(np.mean(budget_values)))
    return float(np.mean(city_values))


def _main_resource(path):
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["arm"] == "full"]
    if not rows or any(row["measured_flops_per_step"] in {"", "None"} for row in rows):
        raise RuntimeError("full arm lacks measured FLOPs required by resource controls")
    return {
        "training_flops": float(np.mean([float(row["measured_flops_per_step"]) * int(row["steps"]) for row in rows])),
        "parameters": float(np.mean([float(row["parameters"]) for row in rows])),
    }


def _validate_resource(control_id, resource, evidence, control_root):
    required = {"schema_version", "control_id", "dataset_sha256", "config_sha256", "fixture", "training_flops", "inference_flops", "parameters", "wall_seconds", "checkpoint_path", "checkpoint_sha256", "profiler_trace_path", "profiler_trace_sha256", "training_log_path", "training_log_sha256"}
    if not isinstance(resource, dict) or set(resource) != required:
        raise RuntimeError(f"{control_id} resource fields must be exact")
    if resource["schema_version"] != "csi-pairs-v6-resource-record-v1" or resource["control_id"] != control_id:
        raise RuntimeError(f"{control_id} resource identity mismatch")
    for key in ("dataset_sha256", "config_sha256"):
        if resource[key] != evidence[key]:
            raise RuntimeError(f"{control_id} resource {key} mismatch")
    if resource["fixture"] is not evidence["fixture"]:
        raise RuntimeError(f"{control_id} resource fixture mismatch")
    for key in ("training_flops", "inference_flops", "parameters", "wall_seconds"):
        if not np.isfinite(resource[key]) or float(resource[key]) <= 0:
            raise RuntimeError(f"{control_id} resource {key} must be positive and measured")
    for prefix in ("checkpoint", "profiler_trace", "training_log"):
        path = (Path(control_root) / str(resource[f"{prefix}_path"])).resolve()
        if Path(control_root).resolve() not in path.parents or not path.is_file():
            raise RuntimeError(f"{control_id} {prefix} artifact is missing or escapes its output")
        if sha256_file(path) != resource[f"{prefix}_sha256"]:
            raise RuntimeError(f"{control_id} {prefix} hash mismatch")
    checkpoint_path = Path(control_root) / resource["checkpoint_path"]
    try:
        import torch

        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    except Exception as error:
        raise RuntimeError(f"{control_id} checkpoint is not a readable training checkpoint") from error
    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("schema_version") != "csi-pairs-v6-control-checkpoint-v1"
        or checkpoint.get("control_id") != control_id
        or not isinstance(checkpoint.get("state_dict"), dict)
    ):
        raise RuntimeError(f"{control_id} checkpoint contract mismatch")
    parameter_count = sum(
        int(value.numel())
        for value in checkpoint["state_dict"].values()
        if hasattr(value, "numel")
    )
    if parameter_count != int(resource["parameters"]):
        raise RuntimeError(f"{control_id} parameter count is not measured from checkpoint")
    profiler = read_strict_json(Path(control_root) / resource["profiler_trace_path"])
    expected_profiler = {
        "schema_version",
        "profiler",
        "measured_training_flops",
        "measured_inference_flops",
        "profiled_step_count",
    }
    if not isinstance(profiler, dict) or set(profiler) != expected_profiler:
        raise RuntimeError(f"{control_id} profiler trace fields must be exact")
    if profiler["schema_version"] != "csi-pairs-v6-profiler-summary-v1":
        raise RuntimeError(f"{control_id} profiler schema mismatch")
    if not isinstance(profiler["profiler"], str) or not profiler["profiler"].strip():
        raise RuntimeError(f"{control_id} profiler identity is missing")
    if int(profiler["profiled_step_count"]) < 1:
        raise RuntimeError(f"{control_id} profiler did not observe a training step")
    if not np.isclose(float(profiler["measured_training_flops"]), float(resource["training_flops"])):
        raise RuntimeError(f"{control_id} training FLOPs disagree with profiler")
    if not np.isclose(float(profiler["measured_inference_flops"]), float(resource["inference_flops"])):
        raise RuntimeError(f"{control_id} inference FLOPs disagree with profiler")
    training = read_strict_json(Path(control_root) / resource["training_log_path"])
    expected_training = {
        "schema_version",
        "control_id",
        "optimizer_steps",
        "fixed_final_checkpoint",
        "target_selection_used",
        "checkpoint_sha256",
    }
    if not isinstance(training, dict) or set(training) != expected_training:
        raise RuntimeError(f"{control_id} training log fields must be exact")
    if (
        training["schema_version"] != "csi-pairs-v6-control-training-log-v1"
        or training["control_id"] != control_id
        or int(training["optimizer_steps"]) < 1
        or training["fixed_final_checkpoint"] is not True
        or training["target_selection_used"] is not False
        or training["checkpoint_sha256"] != resource["checkpoint_sha256"]
    ):
        raise RuntimeError(f"{control_id} training log contract failed")


def _localization_cells(rows):
    return {
        (
            row["city_id"],
            row["base_map_cluster_id"],
            int(row["seed"]),
            int(row["budget"]),
            int(row["draw"]),
        )
        for row in rows
    }


def _control_superiority_interval(main_rows, rows, resamples, seed):
    grouped = {}
    for label, source in (("full", [row for row in main_rows if row["arm"] == "full"]), ("control", rows)):
        for row in source:
            key = (
                row["city_id"],
                row["base_map_cluster_id"],
                int(row["seed"]),
                int(row["budget"]),
                int(row["draw"]),
            )
            grouped.setdefault((label, key), []).append(float(row["utility_neg_log_median"]))
    cells = sorted(
        key for key in {item[1] for item in grouped} if ("full", key) in grouped and ("control", key) in grouped
    )
    clusters = np.asarray([key[1] for key in cells])
    full = np.asarray([np.mean(grouped[("full", key)]) for key in cells])
    control = np.asarray([np.mean(grouped[("control", key)]) for key in cells])
    return paired_cluster_interval(clusters, full, control, resamples, seed)


def _resource_matches(main, rows, tolerance):
    lookup = {row["control_id"]: row for row in rows}
    matches = {}
    for control_id in CONTROL_IDS:
        row = lookup[control_id]
        if control_id == "parameter_matched_concat":
            ratio = float(row["parameters"]) / main["parameters"]
            matches[control_id] = abs(ratio - 1.0) <= tolerance
        elif control_id == "generous_2x_concat":
            flop_ratio = float(row["training_flops"]) / main["training_flops"]
            parameter_ratio = float(row["parameters"]) / main["parameters"]
            matches[control_id] = 1.0 <= flop_ratio <= 2.0 + tolerance and 1.0 <= parameter_ratio <= 2.0 + tolerance
        else:
            ratio = float(row["training_flops"]) / main["training_flops"]
            matches[control_id] = abs(ratio - 1.0) <= tolerance
    return matches
