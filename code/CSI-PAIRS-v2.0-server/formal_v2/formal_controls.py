from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from .formal_evidence import (
    bind_rows,
    complete_gate_vector,
    evidence_context,
    require_stage_manifested_gate,
)
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_csv, write_json
from .formal_statistics import (
    holm_adjust,
    interval_decision,
    paired_cluster_interval,
    paired_sign_flip_test,
)


CONTROL_IDS = (
    "equal_flop_alignment",
    "equal_flop_response",
    "parameter_matched_concat",
    "flop_matched_concat",
    "generous_2x_concat",
)
G4_CONCAT_CONTROL_IDS = CONTROL_IDS[2:4]
REPORT_ONLY_CONTROL_IDS = ("generous_2x_concat",)

CONTROL_CONTRACTS = {
    "equal_flop_alignment": ("single_branch_alignment", {"endpoint", "alignment"}),
    "equal_flop_response": ("single_branch_response", {"endpoint", "response"}),
    "parameter_matched_concat": ("concat_parameter_matched", {"endpoint", "alignment", "response"}),
    "flop_matched_concat": ("concat_flop_matched", {"endpoint", "alignment", "response"}),
    "generous_2x_concat": ("concat_generous_2x", {"endpoint", "alignment", "response"}),
}


def run_resource_controls(config, dataset, manifest_path, output_root):
    from .formal_data_verification import require_verified_roles_from_root

    require_verified_roles_from_root(
        output_root,
        config,
        dataset,
        ("source_encoder_train", "source_method_selection", "target"),
    )
    manifest_path = Path(manifest_path).resolve()
    manifest = read_strict_json(manifest_path)
    _validate_manifest(manifest, manifest_path.parent)
    root = Path(output_root)
    output_dir = root / "controls"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_copy = output_dir / "resource_control_manifest.json"
    bound_input_dir = output_dir / "bound_inputs"
    bound_input_dir.mkdir(parents=True, exist_ok=True)
    bound_manifest = {"schema_version": manifest["schema_version"], "controls": []}
    for item in manifest["controls"]:
        bound = dict(item)
        for prefix in ("adapter_source", "architecture_spec"):
            source_path = (manifest_path.parent / item[f"{prefix}_path"]).resolve()
            suffix = source_path.suffix or ".bin"
            copied = bound_input_dir / f"{item['control_id']}_{prefix}{suffix}"
            shutil.copyfile(source_path, copied)
            bound[f"{prefix}_path"] = str(copied.relative_to(output_dir))
        bound_manifest["controls"].append(bound)
    write_json(manifest_copy, bound_manifest)
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
        source = (manifest_path.parent / adapter["adapter_source_path"]).resolve()
        architecture_path = (manifest_path.parent / adapter["architecture_spec_path"]).resolve()
        architecture = read_strict_json(architecture_path)
        _validate_architecture_spec(control_id, architecture)
        target = output_dir / control_id
        target.mkdir(parents=True, exist_ok=True)
        command = [
            value.format(
                dataset=str(dataset.source_path), output=str(target), root=str(root),
                adapter_source=str(source), architecture_spec=str(architecture_path),
                python=sys.executable,
            )
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
        _validate_resource(
            control_id,
            resource,
            evidence,
            target,
            architecture=architecture,
            architecture_sha256=adapter["architecture_spec_sha256"],
            adapter_source_sha256=adapter["adapter_source_sha256"],
        )
        _run_replay(
            adapter,
            dataset,
            root,
            target,
            resource,
            architecture_path,
            source,
            evidence,
        )
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
            superiority_margin=float(
                config["evaluation"]["minimum_equal_flop_superiority"]
            ),
        )
        for index, name in enumerate(CONTROL_IDS[:2])
    }
    concat_intervals = {
        name: _control_superiority_interval(
            main_rows,
            rows=[row for row in result_rows if row["arm"] == name],
            resamples=int(config["evaluation"]["bootstrap_resamples"]),
            seed=84100 + index,
            superiority_margin=float(
                config["evaluation"]["minimum_concat_superiority"]
            ),
        )
        for index, name in enumerate(CONTROL_IDS[2:])
    }
    control_family_names = list(CONTROL_IDS[:2]) + list(G4_CONCAT_CONTROL_IDS)
    control_family = {
        **{name: equal_intervals[name] for name in CONTROL_IDS[:2]},
        **{name: concat_intervals[name] for name in G4_CONCAT_CONTROL_IDS},
    }
    for name, adjusted in zip(
        control_family_names,
        holm_adjust([control_family[name]["p_value_two_sided"] for name in control_family_names]),
    ):
        control_family[name]["holm_adjusted_p"] = float(adjusted)
    alpha = float(config["evaluation"]["familywise_alpha"])
    gate6 = bool(
        matches["equal_flop_alignment"]
        and matches["equal_flop_response"]
        and all(
            interval_decision(
                value,
                threshold=float(config["evaluation"]["minimum_equal_flop_superiority"]),
                relation="superiority",
            )
            and value["holm_adjusted_p"] < alpha
            for value in equal_intervals.values()
        )
    )
    gate7 = bool(
        all(matches[name] for name in G4_CONCAT_CONTROL_IDS)
        and all(
            interval_decision(
                value,
                threshold=float(config["evaluation"]["minimum_concat_superiority"]),
                relation="superiority",
            )
            and value["holm_adjusted_p"] < alpha
            for name, value in concat_intervals.items()
            if name in G4_CONCAT_CONTROL_IDS
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
        "g4_control_comparison_family": {
            "method": "Holm",
            "familywise_alpha": alpha,
            "members": control_family_names,
            "note": "The generous 2x control is report-only and excluded from the confirmatory family.",
        },
        "generous_2x_report_only": {
            "resource_match": matches["generous_2x_concat"],
            "superiority_interval": concat_intervals["generous_2x_concat"],
            "included_in_g4_subgate_7": False,
        },
        "relative_tolerance": tolerance,
        "resource_integrity_verified": True,
        "input_manifest_path": manifest_copy.name,
        "input_manifest_sha256": sha256_file(manifest_copy),
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


def _validate_manifest(manifest, manifest_root=None):
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "controls"}:
        raise ValueError("resource-control manifest fields must be exact")
    if manifest["schema_version"] != "csi-pairs-v6-resource-controls-v2":
        raise ValueError("resource-control manifest schema mismatch")
    controls = manifest["controls"]
    if not isinstance(controls, list) or {item.get("control_id") for item in controls} != set(CONTROL_IDS):
        raise ValueError("resource-control manifest must contain the exact five V6 controls")
    for item in controls:
        required = {
            "control_id", "command", "replay_command",
            "adapter_source_path", "adapter_source_sha256",
            "architecture_spec_path", "architecture_spec_sha256",
        }
        if set(item) != required or not isinstance(item["command"], list) or not item["command"]:
            raise ValueError("resource-control adapter fields must be exact")
        if not isinstance(item["replay_command"], list) or not item["replay_command"]:
            raise ValueError("resource-control replay command must be nonempty")
        if item["command"][:2] != ["{python}", "{adapter_source}"]:
            raise ValueError(
                "resource-control command must execute the authenticated adapter source directly"
            )
        if item["replay_command"][:2] != ["{python}", "{adapter_source}"]:
            raise ValueError(
                "resource-control replay must execute the authenticated adapter source directly"
            )
        if "{architecture_spec}" not in item["command"] or "{architecture_spec}" not in item["replay_command"]:
            raise ValueError(
                "resource-control commands must consume the authenticated architecture spec"
            )
        for key in ("adapter_source_sha256", "architecture_spec_sha256"):
            if not _lower_sha256(item[key]):
                raise ValueError(f"resource-control {key} must be lowercase SHA-256")
        for key in ("adapter_source_path", "architecture_spec_path"):
            if not isinstance(item[key], str) or not item[key].strip():
                raise ValueError(f"resource-control {key} must be nonempty")
        if manifest_root is not None:
            for prefix in ("adapter_source", "architecture_spec"):
                path = (Path(manifest_root) / item[f"{prefix}_path"]).resolve()
                if Path(manifest_root).resolve() not in path.parents or not path.is_file():
                    raise ValueError(f"resource-control {prefix} is missing or escapes its manifest root")
                if sha256_file(path) != item[f"{prefix}_sha256"]:
                    raise ValueError(f"resource-control {prefix} hash mismatch")
            _validate_architecture_spec(
                item["control_id"],
                read_strict_json(Path(manifest_root) / item["architecture_spec_path"]),
            )


def _validate_architecture_spec(control_id, spec):
    required = {
        "schema_version", "control_id", "architecture_family", "state_keys",
        "objective_terms", "training_role", "selection_role", "evaluation_roles",
    }
    if not isinstance(spec, dict) or set(spec) != required:
        raise ValueError(f"{control_id} architecture spec fields must be exact")
    expected_family, expected_terms = CONTROL_CONTRACTS[control_id]
    if (
        spec["schema_version"] != "csi-pairs-v6-control-architecture-v1"
        or spec["control_id"] != control_id
        or spec["architecture_family"] != expected_family
    ):
        raise ValueError(f"{control_id} architecture identity is not frozen")
    keys = spec["state_keys"]
    if (
        not isinstance(keys, list) or len(keys) < 4
        or len(keys) != len(set(keys))
        or not all(isinstance(key, str) and key.strip() for key in keys)
    ):
        raise ValueError(f"{control_id} architecture state-key contract is invalid")
    if set(spec["objective_terms"]) != expected_terms:
        raise ValueError(f"{control_id} loss contract differs from the frozen control")
    if (
        spec["training_role"] != "source_encoder_train"
        or spec["selection_role"] != "source_method_selection"
        or spec["evaluation_roles"] != ["source_final_unseen_bank", "target_query"]
    ):
        raise ValueError(f"{control_id} role ledger differs from the frozen control")


def _read_localization(path, evidence):
    if not path.is_file():
        raise RuntimeError(f"missing localization control artifact: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "arm", "city_id", "bank_id", "base_map_cluster_id",
        "canonical_base_map_digest", "canonical_bank_digest",
        "seed", "budget", "draw",
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
            cluster_values = []
            clusters = sorted(
                {
                    row["canonical_base_map_digest"]
                    for row in selected
                    if row["city_id"] == city and row["budget"] == budget
                }
            )
            if not clusters:
                raise RuntimeError(f"control {arm} is missing city={city}, k={budget}")
            for cluster in clusters:
                by_bank = {}
                for row in selected:
                    if (
                        row["city_id"] == city
                        and row["budget"] == budget
                        and row["canonical_base_map_digest"] == cluster
                    ):
                        by_bank.setdefault(row["canonical_bank_digest"], []).append(
                            row["utility_neg_log_median"]
                        )
                cluster_values.append(
                    float(np.mean([np.mean(values) for values in by_bank.values()]))
                )
            budget_values.append(float(np.mean(cluster_values)))
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


def _validate_resource(
    control_id,
    resource,
    evidence,
    control_root,
    *,
    architecture,
    architecture_sha256,
    adapter_source_sha256,
):
    required = {
        "schema_version", "control_id", "dataset_sha256", "config_sha256", "fixture",
        "training_flops", "inference_flops", "parameters", "wall_seconds",
        "checkpoint_path", "checkpoint_sha256", "profiler_trace_path", "profiler_trace_sha256",
        "training_log_path", "training_log_sha256", "architecture_spec_sha256",
        "adapter_source_sha256",
    }
    if not isinstance(resource, dict) or set(resource) != required:
        raise RuntimeError(f"{control_id} resource fields must be exact")
    if resource["schema_version"] != "csi-pairs-v6-resource-record-v2" or resource["control_id"] != control_id:
        raise RuntimeError(f"{control_id} resource identity mismatch")
    for key in ("dataset_sha256", "config_sha256"):
        if resource[key] != evidence[key]:
            raise RuntimeError(f"{control_id} resource {key} mismatch")
    if resource["fixture"] is not evidence["fixture"]:
        raise RuntimeError(f"{control_id} resource fixture mismatch")
    if resource["architecture_spec_sha256"] != architecture_sha256:
        raise RuntimeError(f"{control_id} resource architecture-spec hash mismatch")
    if resource["adapter_source_sha256"] != adapter_source_sha256:
        raise RuntimeError(f"{control_id} resource adapter-source hash mismatch")
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
    checkpoint_fields = {
        "schema_version", "control_id", "architecture_family", "architecture_spec_sha256",
        "adapter_source_sha256", "dataset_sha256", "config_sha256", "fixture", "state_dict",
    }
    if not isinstance(checkpoint, dict) or set(checkpoint) != checkpoint_fields:
        raise RuntimeError(f"{control_id} checkpoint contract mismatch")
    if (
        checkpoint["schema_version"] != "csi-pairs-v6-control-checkpoint-v2"
        or checkpoint["control_id"] != control_id
        or checkpoint["architecture_family"] != architecture["architecture_family"]
        or checkpoint["architecture_spec_sha256"] != architecture_sha256
        or checkpoint["adapter_source_sha256"] != adapter_source_sha256
        or checkpoint["dataset_sha256"] != evidence["dataset_sha256"]
        or checkpoint["config_sha256"] != evidence["config_sha256"]
        or checkpoint["fixture"] is not evidence["fixture"]
        or not isinstance(checkpoint["state_dict"], dict)
        or set(checkpoint["state_dict"]) != set(architecture["state_keys"])
    ):
        raise RuntimeError(f"{control_id} checkpoint architecture/state-key contract mismatch")
    try:
        import torch
        if any(
            not isinstance(value, torch.Tensor)
            or value.numel() == 0
            or not bool(torch.isfinite(value).all())
            for value in checkpoint["state_dict"].values()
        ):
            raise RuntimeError(f"{control_id} checkpoint contains invalid parameter tensors")
    except ImportError as error:
        raise RuntimeError("resource controls require PyTorch checkpoint validation") from error
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
        "events",
        "measured_training_flops",
        "measured_inference_flops",
        "profiled_step_count",
    }
    if not isinstance(profiler, dict) or set(profiler) != expected_profiler:
        raise RuntimeError(f"{control_id} profiler trace fields must be exact")
    if profiler["schema_version"] != "csi-pairs-v6-profiler-summary-v2":
        raise RuntimeError(f"{control_id} profiler schema mismatch")
    if not isinstance(profiler["profiler"], str) or not profiler["profiler"].strip():
        raise RuntimeError(f"{control_id} profiler identity is missing")
    if int(profiler["profiled_step_count"]) < 1:
        raise RuntimeError(f"{control_id} profiler did not observe a training step")
    events = profiler["events"]
    if not isinstance(events, list) or len(events) < 2:
        raise RuntimeError(f"{control_id} profiler lacks operator-level events")
    totals = {"training": 0.0, "inference": 0.0}
    for event in events:
        if not isinstance(event, dict) or set(event) != {"name", "phase", "count", "flops"}:
            raise RuntimeError(f"{control_id} profiler event fields must be exact")
        if (
            not isinstance(event["name"], str) or not event["name"].strip()
            or event["phase"] not in totals
            or type(event["count"]) is not int or event["count"] < 1
            or not np.isfinite(event["flops"]) or float(event["flops"]) <= 0
        ):
            raise RuntimeError(f"{control_id} profiler event is invalid")
        totals[event["phase"]] += int(event["count"]) * float(event["flops"])
    if any(value <= 0 for value in totals.values()):
        raise RuntimeError(f"{control_id} profiler must measure training and inference")
    if not np.isclose(totals["training"], float(resource["training_flops"])):
        raise RuntimeError(f"{control_id} training FLOPs are not the sum of profiler events")
    if not np.isclose(totals["inference"], float(resource["inference_flops"])):
        raise RuntimeError(f"{control_id} inference FLOPs are not the sum of profiler events")
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
        "architecture_spec_sha256",
        "adapter_source_sha256",
        "loss_trace_path",
        "loss_trace_sha256",
    }
    if not isinstance(training, dict) or set(training) != expected_training:
        raise RuntimeError(f"{control_id} training log fields must be exact")
    if (
        training["schema_version"] != "csi-pairs-v6-control-training-log-v2"
        or training["control_id"] != control_id
        or int(training["optimizer_steps"]) < 1
        or training["fixed_final_checkpoint"] is not True
        or training["target_selection_used"] is not False
        or training["checkpoint_sha256"] != resource["checkpoint_sha256"]
        or training["architecture_spec_sha256"] != architecture_sha256
        or training["adapter_source_sha256"] != adapter_source_sha256
    ):
        raise RuntimeError(f"{control_id} training log contract failed")
    loss_path = (Path(control_root) / training["loss_trace_path"]).resolve()
    if (
        Path(control_root).resolve() not in loss_path.parents
        or not loss_path.is_file()
        or sha256_file(loss_path) != training["loss_trace_sha256"]
    ):
        raise RuntimeError(f"{control_id} training loss trace is missing or hash-mismatched")
    _validate_loss_trace(
        control_id,
        loss_path,
        int(training["optimizer_steps"]),
        set(architecture["objective_terms"]),
    )


def _validate_loss_trace(control_id, path, optimizer_steps, objective_terms):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    fields = {"step", "total_loss", "endpoint_loss", "alignment_loss", "response_loss", "gradient_norm"}
    if len(rows) != optimizer_steps or any(set(row) != fields for row in rows):
        raise RuntimeError(f"{control_id} loss trace does not cover every optimizer step")
    for index, row in enumerate(rows, start=1):
        if int(row["step"]) != index:
            raise RuntimeError(f"{control_id} loss trace steps are not contiguous")
        values = {key: float(row[key]) for key in fields.difference({"step"})}
        if not all(np.isfinite(value) and value >= 0 for value in values.values()):
            raise RuntimeError(f"{control_id} loss trace contains invalid values")
        for term in {"endpoint", "alignment", "response"}.difference(objective_terms):
            if values[f"{term}_loss"] != 0.0:
                raise RuntimeError(f"{control_id} optimized a loss outside its frozen objective")
        component_total = sum(
            values[f"{term}_loss"] for term in ("endpoint", "alignment", "response")
        )
        if not np.isclose(values["total_loss"], component_total):
            raise RuntimeError(f"{control_id} total loss does not replay from weighted components")
        if values["gradient_norm"] <= 0:
            raise RuntimeError(f"{control_id} loss trace has no measured gradient")


def _run_replay(
    adapter,
    dataset,
    root,
    target,
    resource,
    architecture_path,
    source,
    evidence,
):
    replay_path = target / "replay.json"
    command = [
        value.format(
            dataset=str(dataset.source_path), output=str(target), root=str(root),
            checkpoint=str((target / resource["checkpoint_path"]).resolve()),
            architecture_spec=str(architecture_path), adapter_source=str(source),
            replay_output=str(replay_path),
            python=sys.executable,
        )
        for value in adapter["replay_command"]
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    (target / "replay_stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (target / "replay_stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0 or not replay_path.is_file():
        raise RuntimeError(f"resource control {adapter['control_id']} replay failed")
    replay = read_strict_json(replay_path)
    required = {
        "schema_version", "control_id", "dataset_sha256", "config_sha256",
        "checkpoint_sha256", "architecture_spec_sha256", "adapter_source_sha256",
        "localization_per_bank_sha256", "training_log_sha256", "profiler_trace_sha256",
        "recomputed_parameters", "recomputed_training_flops", "recomputed_inference_flops",
    }
    if not isinstance(replay, dict) or set(replay) != required:
        raise RuntimeError(f"resource control {adapter['control_id']} replay fields must be exact")
    expected = {
        "schema_version": "csi-pairs-v6-resource-replay-v1",
        "control_id": adapter["control_id"],
        "dataset_sha256": evidence["dataset_sha256"],
        "config_sha256": evidence["config_sha256"],
        "checkpoint_sha256": resource["checkpoint_sha256"],
        "architecture_spec_sha256": adapter["architecture_spec_sha256"],
        "adapter_source_sha256": adapter["adapter_source_sha256"],
        "localization_per_bank_sha256": sha256_file(target / "localization_per_bank.csv"),
        "training_log_sha256": resource["training_log_sha256"],
        "profiler_trace_sha256": resource["profiler_trace_sha256"],
    }
    for key, value in expected.items():
        if replay[key] != value:
            raise RuntimeError(f"resource control {adapter['control_id']} replay {key} mismatch")
    numeric = {
        "recomputed_parameters": resource["parameters"],
        "recomputed_training_flops": resource["training_flops"],
        "recomputed_inference_flops": resource["inference_flops"],
    }
    if any(not np.isclose(float(replay[key]), float(value)) for key, value in numeric.items()):
        raise RuntimeError(f"resource control {adapter['control_id']} replay measurements disagree")


def _lower_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _localization_cells(rows):
    return {
        (
            row["city_id"],
            row["canonical_base_map_digest"],
            int(row["seed"]),
            int(row["budget"]),
            int(row["draw"]),
        )
        for row in rows
    }


def _control_superiority_interval(
    main_rows,
    rows,
    resamples,
    seed,
    superiority_margin,
):
    grouped = {}
    for label, source in (("full", [row for row in main_rows if row["arm"] == "full"]), ("control", rows)):
        for row in source:
            key = (
                row["city_id"],
                row["canonical_base_map_digest"],
                int(row["seed"]),
                int(row["budget"]),
                int(row["draw"]),
            )
            grouped.setdefault((label, key), {}).setdefault(
                row["canonical_bank_digest"], []
            ).append(float(row["utility_neg_log_median"]))
    cells = sorted(
        key for key in {item[1] for item in grouped} if ("full", key) in grouped and ("control", key) in grouped
    )
    clusters = np.asarray([key[1] for key in cells])
    full = np.asarray(
        [
            np.mean([np.mean(values) for values in grouped[("full", key)].values()])
            for key in cells
        ]
    )
    control = np.asarray(
        [
            np.mean(
                [np.mean(values) for values in grouped[("control", key)].values()]
            )
            for key in cells
        ]
    )
    interval = paired_cluster_interval(clusters, full, control, resamples, seed)
    margin = float(superiority_margin)
    if not np.isfinite(margin) or margin < 0.0:
        raise ValueError("control superiority margin must be finite and nonnegative")
    test = paired_sign_flip_test(clusters, full, control + margin, seed + 1)
    return {
        **interval,
        "superiority_margin": margin,
        "p_value_two_sided": test["p_value_two_sided"],
    }


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
