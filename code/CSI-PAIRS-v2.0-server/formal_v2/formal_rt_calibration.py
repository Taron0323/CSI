from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

from .formal_evidence import evidence_context
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_json


STATISTICS = ("path_loss", "delay_spread", "angular_spread", "visible_path_count")


def run_rt_calibration_gate(config, dataset, manifest_path, output_root):
    manifest = read_strict_json(manifest_path)
    _validate_manifest(manifest)
    protocol_path = Path(manifest["protocol_path"])
    if sha256_file(protocol_path) != manifest["protocol_sha256"]:
        raise RuntimeError("RT calibration protocol hash mismatch")
    protocol = read_strict_json(protocol_path)
    _validate_protocol(protocol)
    output_dir = Path(output_root) / "qualification" / "rt_calibration"
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        value.format(dataset=str(dataset.source_path), output=str(output_dir), python=sys.executable)
        for value in manifest["command"]
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    (output_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    result_path = output_dir / "statistics.json"
    if completed.returncode != 0 or not result_path.is_file():
        raise RuntimeError("RT calibration adapter failed")
    results = read_strict_json(result_path)
    if not isinstance(results, dict) or set(results) != set(STATISTICS):
        raise RuntimeError("RT calibration must emit exactly four statistics")
    assessments = {}
    for statistic in STATISTICS:
        result = results[statistic]
        if not isinstance(result, dict) or set(result) != {"reference", "simulated"}:
            raise RuntimeError(f"RT calibration {statistic} result fields must be exact")
        reference = float(result["reference"])
        simulated = float(result["simulated"])
        tolerance = float(protocol["absolute_tolerances"][statistic])
        if not np.isfinite(reference) or not np.isfinite(simulated):
            raise RuntimeError("RT calibration statistics must be finite")
        difference = abs(simulated - reference)
        assessments[statistic] = {
            "reference": reference,
            "simulated": simulated,
            "absolute_difference": difference,
            "absolute_tolerance": tolerance,
            "passed": difference <= tolerance,
        }
    passed = all(value["passed"] for value in assessments.values())
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    gate = {
        "schema_version": "csi-pairs-v6-rt-calibration-gate-v1",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        **evidence,
        "claim": "C11",
        "protocol_sha256": manifest["protocol_sha256"],
        "fit_dataset_sha256": manifest["fit_dataset_sha256"],
        "validation_dataset_sha256": manifest["validation_dataset_sha256"],
        "fit_validation_are_independent": True,
        "statistics": assessments,
    }
    gate_path = output_dir / "gate.json"
    write_json(gate_path, gate)
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
    required = {
        "schema_version", "protocol_path", "protocol_sha256", "fit_dataset_sha256",
        "validation_dataset_sha256", "command",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("RT calibration manifest fields must be exact")
    if manifest["schema_version"] != "csi-pairs-v6-rt-calibration-adapter-v1":
        raise ValueError("RT calibration manifest schema mismatch")
    for key in ("protocol_sha256", "fit_dataset_sha256", "validation_dataset_sha256"):
        value = manifest[key]
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"RT calibration {key} must be lowercase SHA-256")
    if manifest["fit_dataset_sha256"] == manifest["validation_dataset_sha256"]:
        raise ValueError("RT calibration fit and validation datasets must be independent")
    if not isinstance(manifest["command"], list) or not manifest["command"]:
        raise ValueError("RT calibration command must be nonempty argv")


def _validate_protocol(protocol):
    if not isinstance(protocol, dict) or set(protocol) != {
        "schema_version", "frozen_utc", "absolute_tolerances", "exclusion_rules"
    }:
        raise ValueError("RT calibration protocol fields must be exact")
    if protocol["schema_version"] != "csi-pairs-v6-rt-calibration-protocol-v1":
        raise ValueError("RT calibration protocol schema mismatch")
    tolerances = protocol["absolute_tolerances"]
    if not isinstance(tolerances, dict) or set(tolerances) != set(STATISTICS):
        raise ValueError("RT calibration protocol must freeze all four tolerances")
    if any(not np.isfinite(value) or float(value) < 0 for value in tolerances.values()):
        raise ValueError("RT calibration tolerances must be finite and nonnegative")
    if not isinstance(protocol["exclusion_rules"], list):
        raise ValueError("RT calibration exclusion rules must be frozen")
