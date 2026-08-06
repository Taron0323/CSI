from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from .formal_evidence import evidence_context
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_json


STATISTICS = ("path_loss", "delay_spread", "angular_spread", "visible_path_count")


def run_rt_calibration_gate(config, dataset, manifest_path, output_root):
    manifest_file = Path(manifest_path).resolve()
    manifest = read_strict_json(manifest_file)
    _validate_manifest(manifest)
    protocol_path = _bound_input(
        manifest["protocol_path"], manifest["protocol_sha256"], manifest_file.parent, "protocol"
    )
    fit_dataset_path = _bound_input(
        manifest["fit_dataset_path"], manifest["fit_dataset_sha256"], manifest_file.parent, "fit dataset"
    )
    validation_dataset_path = _bound_input(
        manifest["validation_dataset_path"],
        manifest["validation_dataset_sha256"],
        manifest_file.parent,
        "validation dataset",
    )
    adapter_source_path = _bound_input(
        manifest["adapter_source_path"],
        manifest["adapter_source_sha256"],
        manifest_file.parent,
        "adapter source",
    )
    if fit_dataset_path == validation_dataset_path:
        raise RuntimeError("RT calibration fit and validation paths must be independent")
    protocol = read_strict_json(protocol_path)
    _validate_protocol(protocol)
    output_dir = Path(output_root) / "qualification" / "rt_calibration"
    output_dir.mkdir(parents=True, exist_ok=True)
    bound_manifest = output_dir / "adapter_manifest.json"
    write_json(
        bound_manifest,
        {
            **manifest,
            "protocol_path": str(protocol_path),
            "fit_dataset_path": str(fit_dataset_path),
            "validation_dataset_path": str(validation_dataset_path),
            "adapter_source_path": str(adapter_source_path),
        },
    )
    command = [
        value.format(
            dataset=str(dataset.source_path),
            output=str(output_dir),
            python=sys.executable,
            fit_dataset=str(fit_dataset_path),
            validation_dataset=str(validation_dataset_path),
            protocol=str(protocol_path),
            adapter_source=str(adapter_source_path),
        )
        for value in manifest["command"]
    ]
    project_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        cwd=project_root,
        env=_adapter_environment(project_root),
    )
    (output_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    result_path = output_dir / "statistics.json"
    if completed.returncode != 0 or not result_path.is_file():
        raise RuntimeError("RT calibration adapter failed")
    result_record = read_strict_json(result_path)
    required_result = {
        "schema_version", "fit_dataset_sha256", "validation_dataset_sha256",
        "fitted_parameters_path", "fitted_parameters_sha256", "statistics",
    }
    if not isinstance(result_record, dict) or set(result_record) != required_result:
        raise RuntimeError("RT calibration result fields must be exact")
    if result_record["schema_version"] != "csi-pairs-v6-rt-calibration-statistics-v2":
        raise RuntimeError("RT calibration result schema mismatch")
    for key in ("fit_dataset_sha256", "validation_dataset_sha256"):
        if result_record[key] != manifest[key]:
            raise RuntimeError(f"RT calibration result {key} mismatch")
    fitted_path = (output_dir / str(result_record["fitted_parameters_path"])).resolve()
    if output_dir.resolve() not in fitted_path.parents or not fitted_path.is_file():
        raise RuntimeError("RT fitted parameters are missing or escape the stage output")
    if sha256_file(fitted_path) != result_record["fitted_parameters_sha256"]:
        raise RuntimeError("RT fitted-parameter hash mismatch")
    results = result_record["statistics"]
    if not isinstance(results, dict) or set(results) != set(STATISTICS):
        raise RuntimeError("RT calibration must emit exactly four statistics")
    assessments = {}
    for statistic in STATISTICS:
        statistic_result = results[statistic]
        if not isinstance(statistic_result, dict) or set(statistic_result) != {"reference", "simulated"}:
            raise RuntimeError(f"RT calibration {statistic} result fields must be exact")
        reference = float(statistic_result["reference"])
        simulated = float(statistic_result["simulated"])
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
        "schema_version": "csi-pairs-v6-rt-calibration-gate-v2",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        **evidence,
        "claim": "C11",
        "protocol_sha256": manifest["protocol_sha256"],
        "adapter_source_path": str(adapter_source_path),
        "adapter_source_sha256": manifest["adapter_source_sha256"],
        "input_manifest_path": bound_manifest.name,
        "input_manifest_sha256": sha256_file(bound_manifest),
        "fit_dataset_sha256": manifest["fit_dataset_sha256"],
        "validation_dataset_sha256": manifest["validation_dataset_sha256"],
        "fitted_parameters_sha256": result_record["fitted_parameters_sha256"],
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
        "schema_version", "protocol_path", "protocol_sha256", "fit_dataset_path",
        "fit_dataset_sha256", "validation_dataset_path", "validation_dataset_sha256",
        "adapter_source_path", "adapter_source_sha256", "command",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("RT calibration manifest fields must be exact")
    if manifest["schema_version"] != "csi-pairs-v6-rt-calibration-adapter-v2":
        raise ValueError("RT calibration manifest schema mismatch")
    for key in (
        "protocol_sha256", "fit_dataset_sha256", "validation_dataset_sha256",
        "adapter_source_sha256",
    ):
        value = manifest[key]
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"RT calibration {key} must be lowercase SHA-256")
    if manifest["fit_dataset_sha256"] == manifest["validation_dataset_sha256"]:
        raise ValueError("RT calibration fit and validation datasets must be independent")
    if not isinstance(manifest["command"], list) or not manifest["command"]:
        raise ValueError("RT calibration command must be nonempty argv")
    command = manifest["command"]
    if (
        Path(manifest["adapter_source_path"]).suffix != ".py"
        or command[:2] != ["{python}", "{adapter_source}"]
        or any(
            command.count(placeholder) != 1
            for placeholder in (
                "{fit_dataset}",
                "{validation_dataset}",
                "{protocol}",
                "{output}",
            )
        )
    ):
        raise ValueError(
            "RT calibration command must directly execute the authenticated adapter "
            "and bind fit, validation, protocol, and output exactly once"
        )
    for key in ("protocol_path", "fit_dataset_path", "validation_dataset_path", "adapter_source_path"):
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise ValueError(f"RT calibration {key} must be nonempty")


def _bound_input(path_value, digest, manifest_root, label):
    path = Path(path_value)
    if not path.is_absolute():
        path = Path(manifest_root) / path
    path = path.resolve()
    if not path.is_file() or sha256_file(path) != digest:
        raise RuntimeError(f"RT calibration {label} is missing or hash-mismatched")
    return path


def _adapter_environment(project_root):
    root = str(Path(project_root).resolve())
    existing = os.environ.get("PYTHONPATH", "")
    return {
        **os.environ,
        "PYTHONPATH": root if not existing else root + os.pathsep + existing,
    }


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
