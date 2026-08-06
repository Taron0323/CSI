from __future__ import annotations

import csv
import subprocess
from pathlib import Path

import numpy as np

from .formal_evidence import bind_rows, evidence_context
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_csv, write_json
from .formal_metrics import spearman_correlation
from .formal_statistics import paired_cluster_interval


CONDITIONS = ("map", "scene_id", "map_swap", "id_swap")


def run_scene_id_audit(config, dataset, manifest_path, output_root):
    from .formal_data_verification import require_verified_roles_from_root

    require_verified_roles_from_root(
        output_root, config, dataset, ("source_final_unseen_bank",)
    )
    manifest_file = Path(manifest_path).resolve()
    manifest = read_strict_json(manifest_file)
    _validate_manifest(manifest)
    output_dir = Path(output_root) / "scene_id"
    output_dir.mkdir(parents=True, exist_ok=True)
    verified = []
    bound_payload = {**manifest, "adapters": [dict(value) for value in manifest["adapters"]]}
    for adapter, bound_adapter in zip(manifest["adapters"], bound_payload["adapters"]):
        adapter_source, checkpoint = _verify_adapter_files(adapter, manifest_file.parent)
        bound_adapter["adapter_source_path"] = str(adapter_source)
        bound_adapter["model_checkpoint_path"] = str(checkpoint)
        verified.append((adapter, adapter_source, checkpoint))
    bound_manifest = output_dir / "adapter_manifest.json"
    write_json(bound_manifest, bound_payload)
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    all_rows = []
    model_rows = []
    for adapter, adapter_source, checkpoint in verified:
        target = output_dir / "adapters" / adapter["adapter_id"]
        target.mkdir(parents=True, exist_ok=True)
        command = [
            value.format(
                dataset=str(dataset.source_path),
                output=str(target),
                checkpoint=str(checkpoint),
                adapter_source=str(adapter_source),
            )
            for value in adapter["command"]
        ]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        (target / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (target / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        result = target / "scene_id_results.csv"
        if completed.returncode != 0 or not result.is_file():
            raise RuntimeError(f"scene-ID adapter {adapter['adapter_id']} failed")
        with result.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        _validate_rows(adapter, rows, dataset, evidence)
        all_rows.extend(rows)
        assessment = _model_assessment(config, adapter, rows)
        assessment["implementation_revision"] = adapter["implementation_revision"]
        assessment["adapter_source_sha256"] = adapter["adapter_source_sha256"]
        assessment["model_checkpoint_sha256"] = adapter["model_checkpoint_sha256"]
        model_rows.append(assessment)
    passed = bool(model_rows and all(row["passed"] for row in model_rows))
    write_csv(output_dir / "per_unit.csv", bind_rows(all_rows, evidence))
    write_csv(output_dir / "per_model.csv", bind_rows(model_rows, evidence))
    gate = {
        "schema_version": "csi-pairs-v6-scene-id-gate-v2",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        **evidence,
        "claim": "C2",
        "models_assessed": len(model_rows),
        "model_assessments": model_rows,
        "input_manifest_path": bound_manifest.name,
        "input_manifest_sha256": sha256_file(bound_manifest),
        "scope": "held-out source positions only",
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
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "adapters"}:
        raise ValueError("scene-ID manifest fields must be exact")
    if manifest["schema_version"] != "csi-pairs-v6-scene-id-adapters-v2":
        raise ValueError("scene-ID manifest schema mismatch")
    if not isinstance(manifest["adapters"], list) or not manifest["adapters"]:
        raise ValueError("scene-ID audit requires at least one map-conditioned model adapter")
    for adapter in manifest["adapters"]:
        if set(adapter) != {
            "adapter_id", "model_name", "implementation_revision", "adapter_source_path",
            "adapter_source_sha256", "model_checkpoint_path", "model_checkpoint_sha256", "command",
        }:
            raise ValueError("scene-ID adapter fields must be exact")
        if not isinstance(adapter["command"], list) or not adapter["command"]:
            raise ValueError("scene-ID adapter command must be a nonempty argv list")
        for key in ("adapter_id", "model_name", "implementation_revision", "adapter_source_path", "model_checkpoint_path"):
            if not isinstance(adapter[key], str) or not adapter[key].strip():
                raise ValueError(f"scene-ID adapter {key} must be nonempty")
        for key in ("adapter_source_sha256", "model_checkpoint_sha256"):
            digest = adapter[key]
            if not isinstance(digest, str) or len(digest) != 64 or any(value not in "0123456789abcdef" for value in digest):
                raise ValueError(f"scene-ID adapter {key} must be lowercase SHA-256")


def _verify_adapter_files(adapter, manifest_root):
    paths = []
    for prefix in ("adapter_source", "model_checkpoint"):
        path = Path(adapter[f"{prefix}_path"])
        if not path.is_absolute():
            path = Path(manifest_root) / path
        path = path.resolve()
        if not path.is_file() or sha256_file(path) != adapter[f"{prefix}_sha256"]:
            raise RuntimeError(f"scene-ID {prefix} is missing or hash-mismatched")
        paths.append(path)
    return tuple(paths)


def _validate_rows(adapter, rows, dataset, evidence):
    required = {
        "unit_id", "model_name", "condition", "bank_id", "position_id",
        "localization_error_m", "response_score", "source_role",
        "dataset_sha256", "config_sha256",
    }
    if not rows or any(set(row) != required for row in rows):
        raise RuntimeError("scene-ID result columns must be exact")
    by_unit = {}
    final_scenes = dataset.indices_for_role("source_final_unseen_bank")
    bank_to_scene = {str(dataset.bank_ids[int(scene)]): int(scene) for scene in final_scenes}
    if len(bank_to_scene) != len(final_scenes):
        raise RuntimeError("scene-ID held-out bank join is not unique")
    observed_pairs = set()
    for row in rows:
        if row["model_name"] != adapter["model_name"]:
            raise RuntimeError("scene-ID result model name mismatch")
        if row["source_role"] != "source_final_unseen_bank" or row["bank_id"] not in bank_to_scene:
            raise RuntimeError("scene-ID audit may only use held-out source banks")
        if row["dataset_sha256"] != str(evidence["dataset_sha256"]) or row["config_sha256"] != str(evidence["config_sha256"]):
            raise RuntimeError("scene-ID result evidence hash mismatch")
        if not np.isfinite(float(row["localization_error_m"])) or not np.isfinite(float(row["response_score"])):
            raise RuntimeError("scene-ID metrics must be finite")
        if row["condition"] not in CONDITIONS:
            raise RuntimeError("scene-ID result contains an unknown condition")
        scene = bank_to_scene[row["bank_id"]]
        positions = np.flatnonzero(dataset.position_ids[scene] == row["position_id"])
        if positions.size != 1 or str(dataset.position_roles[scene, int(positions[0])]) != "standard":
            raise RuntimeError("scene-ID result is not bound to one held-out standard position")
        pair = (row["unit_id"], row["condition"])
        if pair in observed_pairs:
            raise RuntimeError("scene-ID result duplicates a unit/condition cell")
        observed_pairs.add(pair)
        identity = (row["model_name"], row["bank_id"], row["position_id"])
        unit = by_unit.setdefault(row["unit_id"], {"conditions": set(), "identity": identity})
        if unit["identity"] != identity:
            raise RuntimeError("scene-ID four-condition unit changes bank or position")
        unit["conditions"].add(row["condition"])
        row["base_map_cluster_id"] = str(dataset.base_map_cluster_ids[scene])
        for key in ("dataset_sha256", "config_sha256"):
            row.pop(key)
    if any(value["conditions"] != set(CONDITIONS) for value in by_unit.values()):
        raise RuntimeError("each scene-ID unit must contain the exact four conditions")


def _model_assessment(config, adapter, rows):
    units = sorted({row["unit_id"] for row in rows})
    lookup = {(row["unit_id"], row["condition"]): row for row in rows}
    clusters = np.asarray([lookup[(unit, "map")]["base_map_cluster_id"] for unit in units])
    map_values = np.asarray([float(lookup[(unit, "map")]["localization_error_m"]) for unit in units])
    id_values = np.asarray([float(lookup[(unit, "scene_id")]["localization_error_m"]) for unit in units])
    resamples = int(config["evaluation"]["bootstrap_resamples"])
    noninferiority = paired_cluster_interval(
        clusters, id_values, map_values, resamples, 86001
    )
    swap = _cluster_spearman_interval(
        clusters,
        np.asarray([float(lookup[(unit, "map_swap")]["response_score"]) for unit in units]),
        np.asarray([float(lookup[(unit, "id_swap")]["response_score"]) for unit in units]),
        resamples,
        86002,
    )
    margin = float(config["evaluation"]["scene_id_error_noninferiority_m"])
    minimum_correlation = float(config["evaluation"]["scene_id_swap_correlation_min"])
    passed = bool(
        noninferiority["ci95_high"] <= margin
        and swap["ci95_low"] >= minimum_correlation
    )
    return {
        "adapter_id": adapter["adapter_id"],
        "model_name": adapter["model_name"],
        "unit_count": len(units),
        "base_map_cluster_count": int(noninferiority["cluster_count"]),
        "map_mean_error_m": _cluster_macro_mean(clusters, map_values),
        "scene_id_mean_error_m": _cluster_macro_mean(clusters, id_values),
        "scene_id_minus_map_error_m": noninferiority["paired_mean_difference"],
        "scene_id_minus_map_ci95_low": noninferiority["ci95_low"],
        "scene_id_minus_map_ci95_high": noninferiority["ci95_high"],
        "scene_id_error_noninferiority_margin_m": margin,
        "map_swap_id_swap_spearman": swap["estimate"],
        "map_swap_id_swap_spearman_ci95_low": swap["ci95_low"],
        "map_swap_id_swap_spearman_ci95_high": swap["ci95_high"],
        "minimum_swap_spearman": minimum_correlation,
        "passed": passed,
    }


def _cluster_macro_mean(clusters, values):
    identifiers = np.asarray(clusters).astype(str)
    array = np.asarray(values, dtype=np.float64)
    return float(np.mean([np.mean(array[identifiers == cluster]) for cluster in np.unique(identifiers)]))


def _cluster_spearman_interval(clusters, first, second, resamples, seed):
    identifiers = np.asarray(clusters).astype(str)
    unique = np.unique(identifiers)
    if unique.size < 2:
        raise RuntimeError("scene-ID inference requires at least two independent base-map clusters")
    first_macro = np.asarray([np.mean(first[identifiers == value]) for value in unique])
    second_macro = np.asarray([np.mean(second[identifiers == value]) for value in unique])
    estimate = spearman_correlation(first_macro, second_macro)
    if not np.isfinite(estimate):
        raise RuntimeError("scene-ID swap correlation is undefined")
    rng = np.random.default_rng(seed)
    samples = []
    maximum_attempts = max(int(resamples) * 50, 1000)
    for _ in range(maximum_attempts):
        selected = rng.integers(0, unique.size, size=unique.size)
        if np.unique(selected).size < 2:
            continue
        value = spearman_correlation(first_macro[selected], second_macro[selected])
        if np.isfinite(value):
            samples.append(float(value))
        if len(samples) == int(resamples):
            break
    if len(samples) != int(resamples):
        raise RuntimeError("scene-ID swap correlation bootstrap could not form valid resamples")
    return {
        "estimate": float(estimate),
        "ci95_low": float(np.percentile(samples, 2.5)),
        "ci95_high": float(np.percentile(samples, 97.5)),
    }
