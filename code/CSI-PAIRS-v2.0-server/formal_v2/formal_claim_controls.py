from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

from .formal_evidence import evidence_context
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_json


def run_shuffled_pair_control(config, dataset, manifest_path, output_root):
    from .formal_data_verification import require_verified_roles_from_root

    require_verified_roles_from_root(
        output_root,
        config,
        dataset,
        ("source_probe_train", "source_probe_selection", "source_final_unseen_bank", "target"),
    )
    result, manifest = _run_adapter(
        config,
        dataset,
        manifest_path,
        Path(output_root) / "controls" / "shuffled_pair",
        "csi-pairs-v6-shuffled-pair-adapter-v1",
        "results.json",
    )
    required = {
        "schema_version", "dataset_sha256", "config_sha256", "fixture",
        "alignment_gain", "shuffled_alignment_gain", "shortcut_baselines_passed",
        "checkpoint_index_sha256",
    }
    if not isinstance(result, dict) or set(result) != required:
        raise RuntimeError("shuffled-pair result fields must be exact")
    evidence = _validate_result_evidence(config, dataset, result)
    checkpoint_hashes_verified = _verify_checkpoint_index_binding(output_root, result)
    gain = float(result["alignment_gain"])
    shuffled = float(result["shuffled_alignment_gain"])
    if not np.isfinite(gain) or not np.isfinite(shuffled):
        raise RuntimeError("shuffled-pair gains must be finite")
    passed = bool(
        gain > 0
        and shuffled <= float(config["evaluation"]["shuffled_gain_fraction_max"]) * gain
        and result["shortcut_baselines_passed"] is True
    )
    gate = {
        "schema_version": "csi-pairs-v6-shuffled-pair-gate-v2",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        **evidence,
        "claim": "C4",
        "alignment_gain": gain,
        "shuffled_alignment_gain": shuffled,
        "maximum_retained_fraction": float(config["evaluation"]["shuffled_gain_fraction_max"]),
        "pairing_permutation_seed": manifest["control_seed"],
        "checkpoint_hashes_verified": checkpoint_hashes_verified,
    }
    gate_path = Path(output_root) / "controls" / "shuffled_pair" / "gate.json"
    write_json(gate_path, gate)
    _write_manifest(gate_path.parent, evidence)
    return gate


def run_retention_audit(config, dataset, manifest_path, output_root):
    from .formal_data_verification import require_verified_roles_from_root

    require_verified_roles_from_root(
        output_root,
        config,
        dataset,
        ("source_final_unseen_bank", "target"),
    )
    result, _ = _run_adapter(
        config,
        dataset,
        manifest_path,
        Path(output_root) / "evaluation" / "retention",
        "csi-pairs-v6-retention-adapter-v1",
        "results.json",
    )
    required = {
        "schema_version", "dataset_sha256", "config_sha256", "fixture",
        "cgs_map_swap_effect", "cgs_map_removal_effect", "response_map_swap_effect",
        "downstream_f_only", "disposable_heads_absent",
        "checkpoint_index_sha256",
    }
    if not isinstance(result, dict) or set(result) != required:
        raise RuntimeError("retention result fields must be exact")
    evidence = _validate_result_evidence(config, dataset, result)
    checkpoint_hashes_verified = _verify_checkpoint_index_binding(output_root, result)
    effects = {
        key: float(result[key])
        for key in ("cgs_map_swap_effect", "cgs_map_removal_effect", "response_map_swap_effect")
    }
    if not all(np.isfinite(value) for value in effects.values()):
        raise RuntimeError("retention effects must be finite")
    minimum = float(config["evaluation"]["retention_minimum_effect"])
    passed = bool(
        all(value >= minimum for value in effects.values())
        and result["downstream_f_only"] is True
        and result["disposable_heads_absent"] is True
    )
    gate = {
        "schema_version": "csi-pairs-v6-retention-gate-v2",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        **evidence,
        "claim": "C6",
        **effects,
        "minimum_effect": minimum,
        "downstream_f_only": result["downstream_f_only"],
        "disposable_heads_absent": result["disposable_heads_absent"],
        "checkpoint_hashes_verified": checkpoint_hashes_verified,
    }
    gate_path = Path(output_root) / "evaluation" / "retention" / "gate.json"
    write_json(gate_path, gate)
    _write_manifest(gate_path.parent, evidence)
    return gate


def _run_adapter(config, dataset, manifest_path, output_dir, schema, result_name):
    manifest = read_strict_json(manifest_path)
    required = {"schema_version", "command", "implementation_revision", "control_seed"}
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
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        value.format(dataset=str(dataset.source_path), output=str(output_dir), python=sys.executable)
        for value in manifest["command"]
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    (output_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    path = output_dir / result_name
    if completed.returncode != 0 or not path.is_file():
        raise RuntimeError("claim-control adapter failed")
    return read_strict_json(path), manifest


def _validate_result_evidence(config, dataset, result):
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    for key in ("dataset_sha256", "config_sha256", "fixture"):
        if result[key] != evidence[key]:
            raise RuntimeError(f"claim-control result {key} mismatch")
    return evidence


def _verify_checkpoint_index_binding(output_root, result):
    path = Path(output_root) / "factorial" / "checkpoint_index.json"
    if not path.is_file() or result["checkpoint_index_sha256"] != sha256_file(path):
        raise RuntimeError("claim-control result does not bind the executed checkpoint index")
    index = read_strict_json(path)
    root = path.parent.resolve()
    for row in index.get("checkpoints", []):
        checkpoint = (root / row["path"]).resolve()
        if root not in checkpoint.parents or not checkpoint.is_file() or sha256_file(checkpoint) != row["sha256"]:
            raise RuntimeError("claim-control checkpoint index contains a missing or mismatched checkpoint")
    return True


def _write_manifest(output_dir, evidence):
    write_json(
        output_dir / "manifest.json",
        {
            "schema_version": "csi-pairs-formal-stage-manifest-v2.1-v6",
            **evidence,
            "files": artifact_manifest(output_dir, evidence=evidence),
        },
    )
