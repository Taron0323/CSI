from __future__ import annotations

import csv
import subprocess
from pathlib import Path

import numpy as np

from .formal_evidence import bind_rows, evidence_context
from .formal_io import artifact_manifest, read_strict_json, write_csv, write_json
from .formal_metrics import spearman_correlation


CONDITIONS = ("map", "scene_id", "map_swap", "id_swap")


def run_scene_id_audit(config, dataset, manifest_path, output_root):
    from .formal_data_verification import require_verified_roles_from_root

    require_verified_roles_from_root(
        output_root, config, dataset, ("source_final_unseen_bank",)
    )
    manifest = read_strict_json(manifest_path)
    _validate_manifest(manifest)
    output_dir = Path(output_root) / "scene_id"
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    all_rows = []
    model_rows = []
    for adapter in manifest["adapters"]:
        target = output_dir / "adapters" / adapter["adapter_id"]
        target.mkdir(parents=True, exist_ok=True)
        command = [
            value.format(dataset=str(dataset.source_path), output=str(target))
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
        model_rows.append(_model_assessment(config, adapter, rows))
    passed = bool(model_rows and all(row["passed"] for row in model_rows))
    write_csv(output_dir / "per_unit.csv", bind_rows(all_rows, evidence))
    write_csv(output_dir / "per_model.csv", bind_rows(model_rows, evidence))
    gate = {
        "schema_version": "csi-pairs-v6-scene-id-gate-v1",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        **evidence,
        "claim": "C2",
        "models_assessed": len(model_rows),
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
    if manifest["schema_version"] != "csi-pairs-v6-scene-id-adapters-v1":
        raise ValueError("scene-ID manifest schema mismatch")
    if not isinstance(manifest["adapters"], list) or not manifest["adapters"]:
        raise ValueError("scene-ID audit requires at least one map-conditioned model adapter")
    for adapter in manifest["adapters"]:
        if set(adapter) != {"adapter_id", "model_name", "command"}:
            raise ValueError("scene-ID adapter fields must be exact")
        if not isinstance(adapter["command"], list) or not adapter["command"]:
            raise ValueError("scene-ID adapter command must be a nonempty argv list")


def _validate_rows(adapter, rows, dataset, evidence):
    required = {
        "unit_id", "model_name", "condition", "bank_id", "position_id",
        "localization_error_m", "response_score", "source_role",
        "dataset_sha256", "config_sha256",
    }
    if not rows or any(set(row) != required for row in rows):
        raise RuntimeError("scene-ID result columns must be exact")
    by_unit = {}
    allowed_banks = set(dataset.bank_ids[dataset.indices_for_role("source_final_unseen_bank")].tolist())
    for row in rows:
        if row["model_name"] != adapter["model_name"]:
            raise RuntimeError("scene-ID result model name mismatch")
        if row["source_role"] != "source_final_unseen_bank" or row["bank_id"] not in allowed_banks:
            raise RuntimeError("scene-ID audit may only use held-out source banks")
        if row["dataset_sha256"] != str(evidence["dataset_sha256"]) or row["config_sha256"] != str(evidence["config_sha256"]):
            raise RuntimeError("scene-ID result evidence hash mismatch")
        if not np.isfinite(float(row["localization_error_m"])) or not np.isfinite(float(row["response_score"])):
            raise RuntimeError("scene-ID metrics must be finite")
        by_unit.setdefault(row["unit_id"], set()).add(row["condition"])
        for key in ("dataset_sha256", "config_sha256"):
            row.pop(key)
    if any(value != set(CONDITIONS) for value in by_unit.values()):
        raise RuntimeError("each scene-ID unit must contain the exact four conditions")


def _model_assessment(config, adapter, rows):
    units = sorted({row["unit_id"] for row in rows})
    lookup = {(row["unit_id"], row["condition"]): row for row in rows}
    map_error = float(np.mean([float(lookup[(unit, "map")]["localization_error_m"]) for unit in units]))
    id_error = float(np.mean([float(lookup[(unit, "scene_id")]["localization_error_m"]) for unit in units]))
    map_swap = np.asarray([float(lookup[(unit, "map_swap")]["response_score"]) for unit in units])
    id_swap = np.asarray([float(lookup[(unit, "id_swap")]["response_score"]) for unit in units])
    correlation = spearman_correlation(map_swap, id_swap)
    passed = bool(
        id_error - map_error <= float(config["evaluation"]["scene_id_error_noninferiority_m"])
        and correlation >= float(config["evaluation"]["scene_id_swap_correlation_min"])
    )
    return {
        "adapter_id": adapter["adapter_id"],
        "model_name": adapter["model_name"],
        "unit_count": len(units),
        "map_mean_error_m": map_error,
        "scene_id_mean_error_m": id_error,
        "scene_id_minus_map_error_m": id_error - map_error,
        "map_swap_id_swap_spearman": correlation,
        "passed": passed,
    }
