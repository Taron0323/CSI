from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from .formal_evidence import evidence_context
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_csv, write_json


STATISTICS = ("path_loss", "delay_spread", "angular_spread", "visible_path_count")
STATISTIC_COLUMNS = ("unit_id", *STATISTICS)


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
    validation_inputs_path = _bound_input(
        manifest["validation_inputs_path"],
        manifest["validation_inputs_sha256"],
        manifest_file.parent,
        "validation inputs",
    )
    validation_reference_path = _bound_input(
        manifest["validation_reference_path"],
        manifest["validation_reference_sha256"],
        manifest_file.parent,
        "validation reference",
    )
    adapter_source_path = _bound_input(
        manifest["adapter_source_path"],
        manifest["adapter_source_sha256"],
        manifest_file.parent,
        "adapter source",
    )
    data_paths = {fit_dataset_path, validation_inputs_path, validation_reference_path}
    if len(data_paths) != 3:
        raise RuntimeError("RT calibration fit, validation inputs, and validation reference must be independent files")
    protocol = read_strict_json(protocol_path)
    _validate_protocol(protocol)
    reference_rows = _read_statistics_csv(validation_reference_path, "validation reference")
    if len(reference_rows) < int(protocol["minimum_validation_units"]):
        raise RuntimeError("RT calibration validation reference has too few units")

    output_dir = Path(output_root) / "qualification" / "rt_calibration"
    output_dir.mkdir(parents=True, exist_ok=True)
    bound_manifest = output_dir / "adapter_manifest.json"
    write_json(
        bound_manifest,
        {
            **manifest,
            "protocol_path": str(protocol_path),
            "fit_dataset_path": str(fit_dataset_path),
            "validation_inputs_path": str(validation_inputs_path),
            "validation_reference_path": str(validation_reference_path),
            "adapter_source_path": str(adapter_source_path),
        },
    )
    command = [
        value.format(
            dataset=str(dataset.source_path),
            output=str(output_dir),
            python=sys.executable,
            fit_dataset=str(fit_dataset_path),
            validation_inputs=str(validation_inputs_path),
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
    result_path = output_dir / "adapter_result.json"
    if completed.returncode != 0 or not result_path.is_file():
        raise RuntimeError("RT calibration adapter failed")
    result_record = read_strict_json(result_path)
    required_result = {
        "schema_version",
        "fit_dataset_sha256",
        "validation_inputs_sha256",
        "fitted_parameters_path",
        "fitted_parameters_sha256",
        "simulated_statistics_path",
        "simulated_statistics_sha256",
    }
    if not isinstance(result_record, dict) or set(result_record) != required_result:
        raise RuntimeError("RT calibration adapter-result fields must be exact")
    if result_record["schema_version"] != "csi-pairs-v6-rt-calibration-adapter-result-v3":
        raise RuntimeError("RT calibration adapter-result schema mismatch")
    for key in ("fit_dataset_sha256", "validation_inputs_sha256"):
        if result_record[key] != manifest[key]:
            raise RuntimeError(f"RT calibration result {key} mismatch")
    fitted_path = _bound_output_file(
        output_dir,
        result_record["fitted_parameters_path"],
        result_record["fitted_parameters_sha256"],
        "fitted parameters",
    )
    simulated_path = _bound_output_file(
        output_dir,
        result_record["simulated_statistics_path"],
        result_record["simulated_statistics_sha256"],
        "simulated statistics",
    )
    simulated_rows = _read_statistics_csv(simulated_path, "simulated statistics")
    validated_rows, assessments = _join_and_assess(
        reference_rows,
        simulated_rows,
        protocol["absolute_tolerances"],
    )
    validated_path = output_dir / "validated_statistics.csv"
    write_csv(validated_path, validated_rows)
    passed = all(value["passed"] for value in assessments.values())
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    gate = {
        "schema_version": "csi-pairs-v6-rt-calibration-gate-v3",
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
        "validation_inputs_sha256": manifest["validation_inputs_sha256"],
        "validation_reference_sha256": manifest["validation_reference_sha256"],
        "fitted_parameters_sha256": sha256_file(fitted_path),
        "simulated_statistics_path": simulated_path.name,
        "simulated_statistics_sha256": sha256_file(simulated_path),
        "validated_statistics_path": validated_path.name,
        "validated_statistics_sha256": sha256_file(validated_path),
        "validation_unit_count": len(validated_rows),
        "aggregation": "mean_per_unit",
        "fit_validation_are_independent": True,
        "statistics": assessments,
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
    required = {
        "schema_version",
        "protocol_path",
        "protocol_sha256",
        "fit_dataset_path",
        "fit_dataset_sha256",
        "validation_inputs_path",
        "validation_inputs_sha256",
        "validation_reference_path",
        "validation_reference_sha256",
        "adapter_source_path",
        "adapter_source_sha256",
        "command",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("RT calibration manifest fields must be exact")
    if manifest["schema_version"] != "csi-pairs-v6-rt-calibration-adapter-v3":
        raise ValueError("RT calibration manifest schema mismatch")
    digest_keys = (
        "protocol_sha256",
        "fit_dataset_sha256",
        "validation_inputs_sha256",
        "validation_reference_sha256",
        "adapter_source_sha256",
    )
    for key in digest_keys:
        value = manifest[key]
        if not _lower_sha256(value):
            raise ValueError(f"RT calibration {key} must be lowercase SHA-256")
    if len({manifest[key] for key in digest_keys[1:4]}) != 3:
        raise ValueError("RT calibration fit, validation inputs, and validation reference must be independent")
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
                "{validation_inputs}",
                "{protocol}",
                "{output}",
            )
        )
        or any("validation_reference" in value for value in command)
    ):
        raise ValueError(
            "RT calibration command must directly execute the authenticated adapter, bind fit, "
            "validation inputs, protocol, and output exactly once, and exclude validation references"
        )
    for key in (
        "protocol_path",
        "fit_dataset_path",
        "validation_inputs_path",
        "validation_reference_path",
        "adapter_source_path",
    ):
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise ValueError(f"RT calibration {key} must be nonempty")


def _read_statistics_csv(path, label):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != STATISTIC_COLUMNS:
            raise RuntimeError(f"RT calibration {label} columns must be exact")
        source_rows = list(reader)
    if not source_rows:
        raise RuntimeError(f"RT calibration {label} is empty")
    rows = {}
    for source in source_rows:
        unit_id = source["unit_id"]
        if not unit_id or unit_id.strip() != unit_id or unit_id in rows:
            raise RuntimeError(f"RT calibration {label} unit IDs must be nonempty and unique")
        parsed = {"unit_id": unit_id}
        for statistic in STATISTICS:
            try:
                value = float(source[statistic])
            except (TypeError, ValueError) as error:
                raise RuntimeError(f"RT calibration {label} contains a nonnumeric statistic") from error
            if not np.isfinite(value):
                raise RuntimeError(f"RT calibration {label} statistics must be finite")
            if statistic != "path_loss" and value < 0:
                raise RuntimeError(f"RT calibration {label} contains a negative physical statistic")
            if statistic == "visible_path_count" and not value.is_integer():
                raise RuntimeError(f"RT calibration {label} visible path counts must be integers")
            parsed[statistic] = value
        rows[unit_id] = parsed
    return rows


def _join_and_assess(reference_rows, simulated_rows, tolerances):
    if set(reference_rows) != set(simulated_rows):
        missing = sorted(set(reference_rows).difference(simulated_rows))
        unexpected = sorted(set(simulated_rows).difference(reference_rows))
        raise RuntimeError(
            "RT calibration simulated units differ from the frozen validation reference: "
            f"missing={missing[:5]}, unexpected={unexpected[:5]}"
        )
    validated = []
    for unit_id in sorted(reference_rows):
        validated.append(
            {
                "unit_id": unit_id,
                **{
                    f"reference_{statistic}": reference_rows[unit_id][statistic]
                    for statistic in STATISTICS
                },
                **{
                    f"simulated_{statistic}": simulated_rows[unit_id][statistic]
                    for statistic in STATISTICS
                },
            }
        )
    assessments = {}
    for statistic in STATISTICS:
        reference = float(np.mean([row[f"reference_{statistic}"] for row in validated]))
        simulated = float(np.mean([row[f"simulated_{statistic}"] for row in validated]))
        tolerance = float(tolerances[statistic])
        difference = abs(simulated - reference)
        assessments[statistic] = {
            "reference": reference,
            "simulated": simulated,
            "absolute_difference": difference,
            "absolute_tolerance": tolerance,
            "passed": difference <= tolerance,
        }
    return validated, assessments


def _bound_input(path_value, digest, manifest_root, label):
    path = Path(path_value)
    if not path.is_absolute():
        path = Path(manifest_root) / path
    if path.is_symlink():
        raise RuntimeError(f"RT calibration {label} must be a regular file")
    path = path.resolve()
    if not path.is_file() or sha256_file(path) != digest:
        raise RuntimeError(f"RT calibration {label} is missing or hash-mismatched")
    return path


def _bound_output_file(output_dir, relative, digest, label):
    if not isinstance(relative, str) or Path(relative).name != relative or not _lower_sha256(digest):
        raise RuntimeError(f"RT calibration {label} reference is invalid")
    candidate = Path(output_dir) / relative
    if candidate.is_symlink():
        raise RuntimeError(f"RT calibration {label} must be a regular file")
    path = candidate.resolve()
    if path.parent != Path(output_dir).resolve() or not path.is_file():
        raise RuntimeError(f"RT calibration {label} is missing or escapes the stage output")
    if sha256_file(path) != digest:
        raise RuntimeError(f"RT calibration {label} hash mismatch")
    return path


def _adapter_environment(project_root):
    root = str(Path(project_root).resolve())
    existing = os.environ.get("PYTHONPATH", "")
    return {
        **os.environ,
        "PYTHONPATH": root if not existing else root + os.pathsep + existing,
    }


def _validate_protocol(protocol):
    required = {
        "schema_version",
        "frozen_utc",
        "absolute_tolerances",
        "exclusion_rules",
        "minimum_validation_units",
        "aggregation",
    }
    if not isinstance(protocol, dict) or set(protocol) != required:
        raise ValueError("RT calibration protocol fields must be exact")
    if protocol["schema_version"] != "csi-pairs-v6-rt-calibration-protocol-v2":
        raise ValueError("RT calibration protocol schema mismatch")
    if not isinstance(protocol["frozen_utc"], str) or not protocol["frozen_utc"].endswith("Z"):
        raise ValueError("RT calibration protocol requires a frozen UTC timestamp")
    tolerances = protocol["absolute_tolerances"]
    if not isinstance(tolerances, dict) or set(tolerances) != set(STATISTICS):
        raise ValueError("RT calibration protocol must freeze all four tolerances")
    if any(not np.isfinite(value) or float(value) < 0 for value in tolerances.values()):
        raise ValueError("RT calibration tolerances must be finite and nonnegative")
    if not isinstance(protocol["exclusion_rules"], list):
        raise ValueError("RT calibration exclusion rules must be frozen")
    if type(protocol["minimum_validation_units"]) is not int or protocol["minimum_validation_units"] < 2:
        raise ValueError("RT calibration requires at least two validation units")
    if protocol["aggregation"] != "mean_per_unit":
        raise ValueError("RT calibration aggregation must be mean_per_unit")


def _lower_sha256(value):
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )
