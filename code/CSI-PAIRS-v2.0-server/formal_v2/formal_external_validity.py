from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import numpy as np

from .formal_evidence import bind_rows, evidence_context
from .formal_io import artifact_manifest, read_strict_json, write_csv, write_json


def run_external_validity(config, dataset, manifest_path, output_root):
    from .formal_data_verification import require_verified_roles_from_root

    require_verified_roles_from_root(
        output_root, config, dataset, ("external_validation",)
    )
    manifest = read_strict_json(manifest_path)
    _validate_manifest(manifest)
    output_dir = Path(output_root) / "external_validity"
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    command = [
        value.format(dataset=str(dataset.source_path), output=str(output_dir), python=sys.executable)
        for value in manifest["command"]
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    (output_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    result_path = output_dir / "paired_effects.csv"
    if completed.returncode != 0 or not result_path.is_file():
        raise RuntimeError("external-validity adapter failed")
    with result_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    _validate_rows(rows, evidence, dataset)
    for row in rows:
        scenes = np.flatnonzero(dataset.bank_ids == row["bank_id"])
        if scenes.size != 1:
            raise RuntimeError("external-validity bank join is not unique")
        row["base_map_cluster_id"] = str(dataset.base_map_cluster_ids[int(scenes[0])])
    active = [row for row in rows if row["route"] == "active"]
    null = [row for row in rows if row["route"] == "null"]
    if len({row["base_map_cluster_id"] for row in active}) < 2 or len({row["base_map_cluster_id"] for row in null}) < 2:
        raise RuntimeError("G8 requires at least two independent base-map clusters in active and null strata")
    agreement = float(
        np.mean([int(row["primary_direction"]) == int(row["external_direction"]) for row in active])
    )
    equivalence = _paired_bank_equivalence(
        null,
        float(config["external_validity"]["null_equivalence_margin"]),
        int(config["external_validity"]["bootstrap_resamples"]),
    )
    passed = bool(
        agreement >= float(config["external_validity"]["minimum_active_direction_agreement"])
        and equivalence["passed"]
    )
    clean_rows = [
        {
            key: value
            for key, value in row.items()
            if key not in {"dataset_sha256", "config_sha256", "fixture"}
        }
        for row in rows
    ]
    write_csv(output_dir / "validated_paired_effects.csv", bind_rows(clean_rows, evidence))
    gate = {
        "schema_version": "csi-pairs-v6-external-validity-gate-v1",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        **evidence,
        "gate": "G8",
        "evidence_type": manifest["evidence_type"],
        "source_revision": manifest["source_revision"],
        "license_id": manifest["license_id"],
        "active_direction_agreement": agreement,
        "minimum_active_direction_agreement": float(
            config["external_validity"]["minimum_active_direction_agreement"]
        ),
        "null_equivalence": equivalence,
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
    required = {"schema_version", "evidence_type", "source_revision", "license_id", "command"}
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("external-validity manifest fields must be exact")
    if manifest["schema_version"] != "csi-pairs-v6-external-validity-adapter-v1":
        raise ValueError("external-validity manifest schema mismatch")
    if manifest["evidence_type"] not in {"independent_rt_engine", "controlled_real_intervention"}:
        raise ValueError("external-validity evidence type is unsupported")
    if not isinstance(manifest["command"], list) or not manifest["command"]:
        raise ValueError("external-validity command must be nonempty argv")
    for key in ("source_revision", "license_id"):
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise ValueError(f"external-validity {key} must be nonempty")


def _validate_rows(rows, evidence, dataset):
    required = {
        "unit_id", "bank_id", "route", "primary_direction", "external_direction",
        "primary_effect", "external_effect", "context_sha256", "dataset_sha256",
        "config_sha256", "fixture",
    }
    if not rows or any(set(row) != required for row in rows):
        raise RuntimeError("external-validity row fields must be exact")
    for row in rows:
        if row["route"] not in {"active", "null"}:
            raise RuntimeError("external-validity rows may only use active/null frozen routes")
        if int(row["primary_direction"]) not in {-1, 1} or int(row["external_direction"]) not in {-1, 1}:
            raise RuntimeError("external-validity directions must be signed")
        if not np.isfinite(float(row["primary_effect"])) or not np.isfinite(float(row["external_effect"])):
            raise RuntimeError("external-validity effects must be finite")
        for key in ("dataset_sha256", "config_sha256"):
            if row[key] != str(evidence[key]):
                raise RuntimeError(f"external-validity {key} mismatch")
        if row["fixture"] != ("True" if evidence["fixture"] else "False"):
            raise RuntimeError("external-validity fixture mismatch")
        scenes = np.flatnonzero(dataset.bank_ids == row["bank_id"])
        if scenes.size != 1 or str(dataset.scene_roles[int(scenes[0])]) != "external_validation":
            raise RuntimeError("external-validity row must use an external_validation bank")
        digest = row["context_sha256"]
        if len(digest) != 64 or any(value not in "0123456789abcdef" for value in digest):
            raise RuntimeError("external-validity context hash is invalid")


def _paired_bank_equivalence(rows, margin, resamples):
    banks = sorted({row["base_map_cluster_id"] for row in rows})
    differences = np.asarray(
        [
            np.mean(
                [float(row["external_effect"]) - float(row["primary_effect"]) for row in rows if row["base_map_cluster_id"] == bank]
            )
            for bank in banks
        ]
    )
    rng = np.random.default_rng(180001)
    samples = np.asarray(
        [np.mean(differences[rng.integers(0, len(banks), size=len(banks))]) for _ in range(resamples)]
    )
    low, high = float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))
    return {
        "base_map_cluster_count": len(banks),
        "mean_difference": float(np.mean(differences)),
        "ci95_low": low,
        "ci95_high": high,
        "margin": margin,
        "passed": bool(low >= -margin and high <= margin),
    }
