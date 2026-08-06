from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from .formal_evidence import evidence_context
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_json
from .formal_statistics import (
    holm_adjust,
    interval_decision,
    paired_cluster_interval,
    paired_sign_flip_test,
)


SHUFFLED_SYSTEMS = (
    "matched_model",
    "shuffled_model",
    "constant",
    "csi_only",
    "map_only",
    "scene_id_only",
    "edit_status_xor",
    "variant_id_matcher",
)
PAIR_LABELS = ("positive", "negative")
RETENTION_CONDITIONS = ("correct", "map_swap", "map_removed")


def run_shuffled_pair_control(config, dataset, manifest_path, output_root):
    from .formal_data_verification import require_verified_roles_from_root

    require_verified_roles_from_root(
        output_root,
        config,
        dataset,
        ("source_probe_train", "source_probe_selection", "source_final_unseen_bank", "target"),
    )
    output_dir = Path(output_root) / "controls" / "shuffled_pair"
    result, manifest, source_hash = _run_adapter(
        config,
        dataset,
        manifest_path,
        output_dir,
        "csi-pairs-v6-shuffled-pair-adapter-v2",
        "results.json",
    )
    required = {
        "schema_version", "dataset_sha256", "config_sha256", "fixture",
        "per_unit_results_path", "per_unit_results_sha256",
        "pair_registry_sha256", "checkpoint_index_sha256", "adapter_source_sha256",
    }
    if not isinstance(result, dict) or set(result) != required:
        raise RuntimeError("shuffled-pair result fields must be exact")
    if result["schema_version"] != "csi-pairs-v6-shuffled-pair-results-v2":
        raise RuntimeError("shuffled-pair result schema mismatch")
    evidence = _validate_result_evidence(config, dataset, result)
    if result["adapter_source_sha256"] != source_hash:
        raise RuntimeError("shuffled-pair result is not bound to the authenticated adapter source")
    shortcut_binding = _validate_evaluation_shortcut_binding(
        config, dataset, output_root, evidence
    )
    checkpoints = _verify_checkpoint_index_binding(config, dataset, output_root, result)
    registry = _read_active_pair_registry(output_root, result, evidence, dataset)
    rows = _read_bound_rows(output_dir, result, "per_unit_results", _shuffled_columns())
    _validate_shuffled_rows(rows, registry, checkpoints, dataset)
    assessment = _shuffled_assessment(config, rows, registry)
    passed = assessment["passed"]
    gate = {
        "schema_version": "csi-pairs-v6-shuffled-pair-gate-v2",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        **evidence,
        "claim": "C4",
        **assessment,
        "pairing_permutation_seed": manifest["control_seed"],
        "checkpoint_hashes_verified": True,
        "per_unit_rows_verified": True,
        "adapter_source_sha256": source_hash,
        **shortcut_binding,
        "input_manifest_path": "adapter_manifest.json",
        "input_manifest_sha256": sha256_file(output_dir / "adapter_manifest.json"),
    }
    write_json(output_dir / "gate.json", gate)
    _write_manifest(output_dir, evidence)
    return gate


def run_retention_audit(config, dataset, manifest_path, output_root):
    from .formal_data_verification import require_verified_roles_from_root

    require_verified_roles_from_root(
        output_root,
        config,
        dataset,
        ("source_final_unseen_bank", "target"),
    )
    output_dir = Path(output_root) / "evaluation" / "retention"
    result, _, source_hash = _run_adapter(
        config,
        dataset,
        manifest_path,
        output_dir,
        "csi-pairs-v6-retention-adapter-v2",
        "results.json",
    )
    required = {
        "schema_version", "dataset_sha256", "config_sha256", "fixture",
        "per_unit_results_path", "per_unit_results_sha256",
        "pair_registry_sha256", "checkpoint_index_sha256", "adapter_source_sha256",
    }
    if not isinstance(result, dict) or set(result) != required:
        raise RuntimeError("retention result fields must be exact")
    if result["schema_version"] != "csi-pairs-v6-retention-results-v2":
        raise RuntimeError("retention result schema mismatch")
    evidence = _validate_result_evidence(config, dataset, result)
    if result["adapter_source_sha256"] != source_hash:
        raise RuntimeError("retention result is not bound to the authenticated adapter source")
    checkpoints = _verify_checkpoint_index_binding(config, dataset, output_root, result)
    registry = _read_active_pair_registry(output_root, result, evidence, dataset)
    rows = _read_bound_rows(output_dir, result, "per_unit_results", _retention_columns())
    _validate_retention_rows(rows, registry, checkpoints)
    assessment = _retention_assessment(config, rows, registry)
    passed = assessment["passed"]
    gate = {
        "schema_version": "csi-pairs-v6-retention-gate-v2",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        **evidence,
        "claim": "C6",
        **assessment,
        "checkpoint_hashes_verified": True,
        "per_unit_rows_verified": True,
        "downstream_f_only_verified": True,
        "disposable_heads_absent_verified": True,
        "adapter_source_sha256": source_hash,
        "input_manifest_path": "adapter_manifest.json",
        "input_manifest_sha256": sha256_file(output_dir / "adapter_manifest.json"),
    }
    write_json(output_dir / "gate.json", gate)
    _write_manifest(output_dir, evidence)
    return gate


def _run_adapter(config, dataset, manifest_path, output_dir, schema, result_name):
    manifest_path = Path(manifest_path).resolve()
    manifest = read_strict_json(manifest_path)
    required = {
        "schema_version", "command", "implementation_revision", "control_seed",
        "adapter_source_path", "adapter_source_sha256",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("claim-control manifest fields must be exact")
    if manifest["schema_version"] != schema:
        raise ValueError("claim-control manifest schema mismatch")
    if not isinstance(manifest["command"], list) or not manifest["command"]:
        raise ValueError("claim-control command must be nonempty argv")
    if not isinstance(manifest["implementation_revision"], str) or not manifest["implementation_revision"]:
        raise ValueError("claim-control implementation revision must be nonempty")
    if type(manifest["control_seed"]) is not int or manifest["control_seed"] < 0:
        raise ValueError("claim-control seed must be nonnegative integer")
    source = (manifest_path.parent / manifest["adapter_source_path"]).resolve()
    if manifest_path.parent not in source.parents or not source.is_file():
        raise ValueError("claim-control adapter source is missing or escapes the manifest directory")
    source_hash = sha256_file(source)
    if source_hash != manifest["adapter_source_sha256"]:
        raise ValueError("claim-control adapter source hash mismatch")
    if manifest["implementation_revision"] != source_hash:
        raise ValueError(
            "claim-control implementation revision must equal the authenticated source hash"
        )
    if manifest["command"][:2] != ["{python}", "{adapter_source}"]:
        raise ValueError(
            "claim-control command must execute the authenticated adapter source directly"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    source_copy = output_dir / f"adapter_source{source.suffix or '.bin'}"
    shutil.copyfile(source, source_copy)
    bound_manifest = dict(manifest)
    bound_manifest["adapter_source_path"] = source_copy.name
    write_json(output_dir / "adapter_manifest.json", bound_manifest)
    command = [
        value.format(
            dataset=str(dataset.source_path), output=str(output_dir), python=sys.executable,
            adapter_source=str(source), run_root=str(Path(output_dir).parents[1]),
        )
        for value in manifest["command"]
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    (output_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    path = output_dir / result_name
    if completed.returncode != 0 or not path.is_file():
        raise RuntimeError("claim-control adapter failed")
    return read_strict_json(path), manifest, source_hash


def _validate_result_evidence(config, dataset, result):
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    for key in ("dataset_sha256", "config_sha256", "fixture"):
        if result[key] != evidence[key]:
            raise RuntimeError(f"claim-control result {key} mismatch")
    return evidence


def _verify_checkpoint_index_binding(config, dataset, output_root, result):
    path = Path(output_root) / "factorial" / "checkpoint_index.json"
    if not path.is_file() or result["checkpoint_index_sha256"] != sha256_file(path):
        raise RuntimeError("claim-control result does not bind the executed checkpoint index")
    index = read_strict_json(path)
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    if index.get("schema_version") != "csi-pairs-formal-checkpoint-index-v2.1-v6":
        raise RuntimeError("claim-control checkpoint index schema mismatch")
    for key in ("dataset_sha256", "config_sha256", "fixture"):
        if index.get(key) != evidence[key]:
            raise RuntimeError(f"claim-control checkpoint index {key} mismatch")
    root = path.parent.resolve()
    full_by_seed = {}
    for row in index.get("checkpoints", []):
        checkpoint_path = (root / row["path"]).resolve()
        if root not in checkpoint_path.parents or not checkpoint_path.is_file():
            raise RuntimeError("claim-control checkpoint index contains a missing checkpoint")
        digest = sha256_file(checkpoint_path)
        if digest != row["sha256"]:
            raise RuntimeError("claim-control checkpoint index contains a mismatched checkpoint")
        if row.get("arm") != "full":
            continue
        payload = _validate_formal_checkpoint(checkpoint_path, row, evidence)
        seed = int(payload["seed"])
        if seed in full_by_seed:
            raise RuntimeError("claim-control checkpoint index duplicates a full-arm seed")
        full_by_seed[seed] = digest
    if not full_by_seed:
        raise RuntimeError("claim-control checkpoint index has no authenticated full-arm checkpoint")
    return full_by_seed


def _validate_formal_checkpoint(path, row, evidence):
    try:
        import torch
        from .formal_model import CSIPairsFormalModel

        payload = torch.load(path, map_location="cpu", weights_only=False)
    except Exception as error:
        raise RuntimeError("claim-control checkpoint is unreadable") from error
    required = {
        "schema_version", "arm", "seed", "model_spec", "normalization",
        "teacher_checkpoint_sha256", "checkpoint_rule", "state_dict",
        "dataset_sha256", "config_sha256", "fixture", "artifact_label", "scientific_use",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise RuntimeError("claim-control checkpoint fields are not the frozen F/P contract")
    if (
        payload["schema_version"] != "csi-pairs-formal-checkpoint-v2.1-v6"
        or payload["arm"] != "full"
        or int(payload["seed"]) != int(row["seed"])
        or payload["checkpoint_rule"] != "fixed_final_step_no_target_selection"
    ):
        raise RuntimeError("claim-control checkpoint identity mismatch")
    for key in ("dataset_sha256", "config_sha256", "fixture"):
        if payload[key] != evidence[key]:
            raise RuntimeError(f"claim-control checkpoint {key} mismatch")
    try:
        model = CSIPairsFormalModel(**payload["model_spec"])
        model.load_state_dict(payload["state_dict"], strict=True)
    except Exception as error:
        raise RuntimeError("claim-control checkpoint state is not the frozen formal model") from error
    if set(payload["state_dict"]) != set(model.state_dict()):
        raise RuntimeError("claim-control checkpoint contains disposable or missing heads")
    return payload


def _read_active_pair_registry(output_root, result, evidence, dataset):
    from .formal_factorial import _canonical_bank_digest

    path = Path(output_root) / "evaluation" / "compatibility_pair_effects.csv"
    if not path.is_file() or result["pair_registry_sha256"] != sha256_file(path):
        raise RuntimeError("claim-control result does not bind the evaluation pair registry")
    _require_stage_artifact(path)
    with path.open(newline="", encoding="utf-8") as handle:
        raw = list(csv.DictReader(handle))
    rows = [row for row in raw if row.get("arm") == "full" and row.get("route") == "active"]
    if not rows:
        raise RuntimeError("claim-control pair registry has no full-arm active rows")
    required = {
        "seed", "pair_id", "scene_index", "bank_id", "base_map_cluster_id",
        "canonical_base_map_digest", "canonical_bank_digest", "source_world",
        "target_world", "position_index", "route", "arm", "dataset_sha256",
        "config_sha256",
    }
    if any(not required.issubset(row) for row in rows):
        raise RuntimeError("claim-control pair registry lacks canonical hierarchy fields")
    registry = {}
    for row in rows:
        for key in ("dataset_sha256", "config_sha256"):
            if row.get(key) != str(evidence[key]):
                raise RuntimeError(f"claim-control pair registry {key} mismatch")
        key = (int(row["seed"]), row["pair_id"])
        if key in registry:
            raise RuntimeError("claim-control pair registry duplicates a seed/pair")
        scene = int(row["scene_index"])
        if scene < 0 or scene >= int(dataset.scene_count):
            raise RuntimeError("claim-control pair registry has an invalid scene index")
        expected_foundation = str(dataset.canonical_base_map_digest(scene))
        expected_bank = str(_canonical_bank_digest(dataset, scene))
        if (
            row["canonical_base_map_digest"] != expected_foundation
            or row["canonical_bank_digest"] != expected_bank
        ):
            raise RuntimeError(
                "claim-control pair registry canonical hierarchy differs from outer recomputation"
            )
        normalized = dict(row)
        for field in (
            "seed", "scene_index", "source_world", "target_world", "position_index"
        ):
            normalized[field] = int(row[field])
        registry[key] = normalized
    _require_unique_canonical_units(registry)
    if len({row["canonical_base_map_digest"] for row in registry.values()}) < 2:
        raise RuntimeError("claim-control pair registry has fewer than two independent clusters")
    return registry


def _validate_evaluation_shortcut_binding(config, dataset, output_root, evidence):
    from .formal_evidence import require_stage_manifested_gate

    evaluation_dir = Path(output_root) / "evaluation"
    gate_path = evaluation_dir / "gate.json"
    rows_path = evaluation_dir / "alignment_shortcut_baselines.csv"
    if not gate_path.is_file() or not rows_path.is_file():
        raise RuntimeError("shuffled-pair control requires the evaluation shortcut audit")
    gate = read_strict_json(gate_path)
    require_stage_manifested_gate(
        gate_path,
        gate,
        config,
        dataset,
        schema_version="csi-pairs-v6-evaluation-gate-v2",
    )
    audit = gate.get("alignment_shortcut_audit")
    required_baselines = set(SHUFFLED_SYSTEMS[2:])
    if (
        not isinstance(audit, dict)
        or audit.get("passed") is not True
        or audit.get("complete") is not True
        or set(audit.get("required_baselines", [])) != required_baselines
    ):
        raise RuntimeError("evaluation alignment shortcut audit is incomplete or failed")
    with rows_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or {row.get("baseline") for row in rows} != required_baselines:
        raise RuntimeError("evaluation shortcut rows do not cover the frozen baseline set")
    _require_stage_artifact(rows_path)
    for row in rows:
        for key in ("dataset_sha256", "config_sha256"):
            if row.get(key) != str(evidence[key]):
                raise RuntimeError(f"evaluation shortcut row {key} mismatch")
        if not np.isfinite(float(row["auroc"])):
            raise RuntimeError("evaluation shortcut AUROC must be finite")
    return {
        "evaluation_alignment_shortcut_audit_verified": True,
        "evaluation_gate_sha256": sha256_file(gate_path),
        "alignment_shortcut_rows_sha256": sha256_file(rows_path),
    }


def _require_stage_artifact(path):
    path = Path(path)
    manifest_path = path.parent / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"stage artifact has no manifest: {path}")
    manifest = read_strict_json(manifest_path)
    files = manifest.get("files") if isinstance(manifest, dict) else None
    matches = [
        row for row in files
        if isinstance(row, dict) and row.get("path") == path.name
    ] if isinstance(files, list) else []
    if len(matches) != 1 or matches[0].get("sha256") != sha256_file(path):
        raise RuntimeError(f"stage artifact is absent from or mismatched with its manifest: {path}")


def _read_bound_rows(output_dir, result, prefix, required_columns):
    path = (Path(output_dir) / result[f"{prefix}_path"]).resolve()
    if Path(output_dir).resolve() not in path.parents or not path.is_file():
        raise RuntimeError(f"claim-control {prefix} is missing or escapes adapter output")
    if sha256_file(path) != result[f"{prefix}_sha256"]:
        raise RuntimeError(f"claim-control {prefix} hash mismatch")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or any(set(row) != required_columns for row in rows):
        raise RuntimeError(f"claim-control {prefix} columns must be exact")
    return rows


def _shuffled_columns():
    return {"seed", "pair_id", "system", "pair_label", "alignment_score", "checkpoint_sha256", "action_sha256"}


def _retention_columns():
    return {"seed", "pair_id", "condition", "cgs_score", "response_score", "checkpoint_sha256", "representation_scope"}


def _validate_shuffled_rows(rows, registry, checkpoints, dataset):
    expected = {
        (seed, pair_id, system, label)
        for seed, pair_id in registry
        for system in SHUFFLED_SYSTEMS
        for label in PAIR_LABELS
    }
    seen = set()
    for row in rows:
        key = (int(row["seed"]), row["pair_id"])
        expanded = (*key, row["system"], row["pair_label"])
        if expanded in seen:
            raise RuntimeError("shuffled-pair rows duplicate a pair/system/label")
        seen.add(expanded)
        if key not in registry or row["system"] not in SHUFFLED_SYSTEMS or row["pair_label"] not in PAIR_LABELS:
            raise RuntimeError("shuffled-pair rows do not match the frozen pair registry")
        value = float(row["alignment_score"])
        if not np.isfinite(value):
            raise RuntimeError("shuffled-pair alignment scores must be finite")
        if row["checkpoint_sha256"] != checkpoints.get(key[0]):
            raise RuntimeError("shuffled-pair row is not bound to its full-arm seed checkpoint")
        expected_action = _registry_action_sha256(dataset, registry[key])
        if row["action_sha256"] != expected_action:
            raise RuntimeError("shuffled-pair row action digest differs from outer recomputation")
    if seen != expected:
        raise RuntimeError("shuffled-pair rows do not cover the complete active pair registry")


def _validate_retention_rows(rows, registry, checkpoints):
    expected = {
        (seed, pair_id, condition)
        for seed, pair_id in registry
        for condition in RETENTION_CONDITIONS
    }
    seen = set()
    for row in rows:
        key = (int(row["seed"]), row["pair_id"])
        expanded = (*key, row["condition"])
        if expanded in seen:
            raise RuntimeError("retention rows duplicate a pair/condition")
        seen.add(expanded)
        if key not in registry or row["condition"] not in RETENTION_CONDITIONS:
            raise RuntimeError("retention rows do not match the frozen pair registry")
        if row["representation_scope"] != "formal_model.retained_representation":
            raise RuntimeError("retention rows do not evaluate the downstream retained F representation")
        if row["checkpoint_sha256"] != checkpoints.get(key[0]):
            raise RuntimeError("retention row is not bound to its full-arm seed checkpoint")
        for field in ("cgs_score", "response_score"):
            if not np.isfinite(float(row[field])):
                raise RuntimeError("retention scores must be finite")
    if seen != expected:
        raise RuntimeError("retention rows do not cover the complete active pair registry")


def _registry_action_sha256(dataset, row):
    scene = int(row["scene_index"])
    source = int(row["source_world"])
    target = int(row["target_world"])
    matches = [
        edge for edge in dataset.directed_edges(scene)
        if edge.source_world == source and edge.target_world == target
    ]
    if len(matches) != 1:
        raise RuntimeError("claim-control pair does not identify one directed action")
    edge = matches[0]
    payload = {
        "scene_index": scene,
        "source_world": source,
        "target_world": target,
        "bit_index": int(edge.bit_index),
        "primitive_id": int(edge.primitive_id),
        "direction": int(edge.direction),
        "position_index": int(row["position_index"]),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _shuffled_assessment(config, rows, registry):
    _require_unique_canonical_units(registry)
    lookup = {
        (int(row["seed"]), row["pair_id"], row["system"], row["pair_label"]): float(row["alignment_score"])
        for row in rows
    }
    keys = sorted(registry)
    unit_gains = {
        system: {
            key:
            lookup[(*key, system, "positive")] - lookup[(*key, system, "negative")]
            for key in keys
        }
        for system in SHUFFLED_SYSTEMS
    }
    clusters = None
    gains = {}
    for system in SHUFFLED_SYSTEMS:
        system_clusters, system_values = _canonical_cluster_macro(
            registry, unit_gains[system]
        )
        if clusters is None:
            clusters = system_clusters
        elif not np.array_equal(clusters, system_clusters):
            raise RuntimeError("shuffled-pair systems do not share canonical support")
        gains[system] = system_values
    if clusters is None:
        raise RuntimeError("shuffled-pair assessment has no canonical support")
    resamples = int(config["evaluation"]["bootstrap_resamples"])
    matched_interval = paired_cluster_interval(
        clusters,
        gains["matched_model"],
        np.zeros_like(gains["matched_model"]),
        resamples,
        86201,
    )
    retained_interval = paired_cluster_interval(
        clusters,
        gains["shuffled_model"],
        np.zeros_like(gains["shuffled_model"]),
        resamples,
        86202,
    )
    shortcut_intervals = {
        system: {
            **paired_cluster_interval(
                clusters, gains["matched_model"], gains[system], resamples, 86210 + index
            ),
            "p_value_two_sided": paired_sign_flip_test(
                clusters, gains["matched_model"], gains[system], 86240 + index
            )["p_value_two_sided"],
        }
        for index, system in enumerate(SHUFFLED_SYSTEMS[2:])
    }
    for system, adjusted in zip(
        SHUFFLED_SYSTEMS[2:],
        holm_adjust([
            shortcut_intervals[system]["p_value_two_sided"]
            for system in SHUFFLED_SYSTEMS[2:]
        ]),
    ):
        shortcut_intervals[system]["holm_adjusted_p"] = float(adjusted)
    gain = float(matched_interval["paired_mean_difference"])
    shuffled = float(retained_interval["paired_mean_difference"])
    maximum_fraction = float(config["evaluation"]["shuffled_gain_fraction_max"])
    suppression_interval = paired_cluster_interval(
        clusters,
        maximum_fraction * gains["matched_model"],
        gains["shuffled_model"],
        resamples,
        86203,
    )
    alpha = float(config["evaluation"]["familywise_alpha"])
    shortcut_passed = all(
        interval_decision(value, threshold=0.0, relation="superiority")
        and value["holm_adjusted_p"] < alpha
        for value in shortcut_intervals.values()
    )
    passed = bool(
        interval_decision(matched_interval, threshold=0.0, relation="superiority")
        and interval_decision(suppression_interval, threshold=0.0, relation="superiority")
        and shortcut_passed
    )
    return {
        "base_map_cluster_count": int(np.unique(clusters).size),
        "alignment_gain": gain,
        "alignment_gain_interval": matched_interval,
        "shuffled_alignment_gain": shuffled,
        "shuffled_alignment_gain_interval": retained_interval,
        "shuffled_suppression_interval": suppression_interval,
        "maximum_retained_fraction": maximum_fraction,
        "shortcut_superiority_intervals": shortcut_intervals,
        "shortcut_familywise_method": "Holm",
        "shortcut_familywise_alpha": alpha,
        "shortcut_baselines_passed": shortcut_passed,
        "passed": passed,
    }


def _retention_assessment(config, rows, registry):
    _require_unique_canonical_units(registry)
    lookup = {
        (int(row["seed"]), row["pair_id"], row["condition"]): row
        for row in rows
    }
    keys = sorted(registry)
    metric_conditions = {
        "cgs_map_swap_effect": ("cgs_score", "map_swap"),
        "cgs_map_removal_effect": ("cgs_score", "map_removed"),
        "response_map_swap_effect": ("response_score", "map_swap"),
    }
    resamples = int(config["evaluation"]["bootstrap_resamples"])
    intervals = {}
    for index, (name, (metric, condition)) in enumerate(metric_conditions.items()):
        unit_effects = {
            key: float(lookup[(*key, "correct")][metric])
            - float(lookup[(*key, condition)][metric])
            for key in keys
        }
        clusters, effects = _canonical_cluster_macro(registry, unit_effects)
        intervals[name] = paired_cluster_interval(
            clusters, effects, np.zeros_like(effects), resamples, 86301 + index
        )
    minimum = float(config["evaluation"]["retention_minimum_effect"])
    effects = {name: float(value["paired_mean_difference"]) for name, value in intervals.items()}
    passed = all(
        interval_decision(value, threshold=minimum, relation="superiority")
        for value in intervals.values()
    )
    return {
        "base_map_cluster_count": int(np.unique(clusters).size),
        **effects,
        "effect_intervals": intervals,
        "minimum_effect": minimum,
        "passed": bool(passed),
    }


def _require_unique_canonical_units(registry):
    seen = {}
    for key, row in registry.items():
        unit = (
            int(row["seed"]),
            str(row["canonical_base_map_digest"]),
            str(row["canonical_bank_digest"]),
            int(row["source_world"]),
            int(row["target_world"]),
            int(row["position_index"]),
        )
        if unit in seen:
            raise RuntimeError(
                "claim-control pair registry duplicates a canonical evaluation unit"
            )
        seen[unit] = key


def _canonical_cluster_macro(registry, unit_values):
    if set(unit_values) != set(registry):
        raise RuntimeError("claim-control statistic does not cover the canonical registry")
    _require_unique_canonical_units(registry)
    bank_seed_values = {}
    for key, row in registry.items():
        value = float(unit_values[key])
        if not np.isfinite(value):
            raise RuntimeError("claim-control canonical unit statistic must be finite")
        cell = (
            str(row["canonical_base_map_digest"]),
            str(row["canonical_bank_digest"]),
            int(row["seed"]),
        )
        bank_seed_values.setdefault(cell, []).append(value)

    bank_values = {}
    for (cluster, bank, _), values in bank_seed_values.items():
        bank_values.setdefault((cluster, bank), []).append(float(np.mean(values)))
    cluster_values = {}
    for (cluster, _), seed_values in bank_values.items():
        cluster_values.setdefault(cluster, []).append(float(np.mean(seed_values)))
    clusters = np.asarray(sorted(cluster_values))
    if clusters.size < 2:
        raise RuntimeError("claim-control statistic has fewer than two canonical clusters")
    values = np.asarray(
        [np.mean(cluster_values[cluster]) for cluster in clusters],
        dtype=np.float64,
    )
    return clusters, values


def _write_manifest(output_dir, evidence):
    write_json(
        output_dir / "manifest.json",
        {
            "schema_version": "csi-pairs-formal-stage-manifest-v2.1-v6",
            **evidence,
            "files": artifact_manifest(output_dir, evidence=evidence),
        },
    )
