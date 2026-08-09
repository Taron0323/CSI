from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import numpy as np

from .formal_dataset import _canonical_foundation_sha256
from .formal_evidence import EVIDENCE_AUTH_KEYS, bind_rows, evidence_context
from .formal_io import (
    artifact_manifest,
    parse_strict_json,
    read_strict_json,
    sha256_file,
    write_csv,
    write_json,
)


SCHEMA = "csi-pairs-v6-data-verification-gate-v1"
LIVE_MANIFEST_SCHEMA = "csi-pairs-v6-data-verifier-v1"
PRECOMPUTED_MANIFEST_SCHEMA = "csi-pairs-v6-precomputed-data-verifier-v1"
BLOCKING_ROLES = ("source_encoder_train", "source_method_selection")
REGENERATED_FIELDS = {
    "maps",
    "csi_clean",
    "csi_repeat",
    "free_space",
    "phase_reference_ids",
    "phase_reference_values",
    "phase_reference_source_sha256",
    "engine_config_json",
    "noop_maps",
    "path_ids",
    "path_power",
    "path_surface_ids",
    "noop_path_ids",
    "noop_path_power",
    "noop_path_surface_ids",
}


def run_data_verification(config, dataset, manifest_path, output_root):
    manifest_file = _require_regular_file(manifest_path, "data verifier manifest")
    manifest = read_strict_json(manifest_file)
    _validate_manifest(manifest, dataset)
    verifier_source = _resolve_verifier_source(manifest, manifest_file.parent)
    receipt_path = None
    receipt = None
    if manifest["schema_version"] == PRECOMPUTED_MANIFEST_SCHEMA:
        receipt_path, receipt = _resolve_precomputed_receipt(
            manifest, manifest_file.parent, dataset
        )
    output_dir = Path(output_root) / "data_verification"
    output_dir.mkdir(parents=True, exist_ok=True)
    bound_manifest = output_dir / "verifier_manifest.json"
    write_json(
        bound_manifest,
        {
            **manifest,
            "verifier_source_path": str(verifier_source),
            **(
                {"verification_receipt_path": str(receipt_path)}
                if receipt_path is not None
                else {}
            ),
        },
    )
    command = [
        value.format(
            dataset=str(Path(dataset.source_path).resolve()),
            output=str(output_dir.resolve()),
            python=sys.executable,
            verifier_source=str(verifier_source),
            verification_receipt=str(receipt_path or ""),
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
        env=_verifier_environment(project_root),
    )
    (output_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"independent data verifier failed with code {completed.returncode}")
    _require_file_sha256(
        verifier_source,
        manifest["verifier_source_sha256"],
        "data verifier source",
    )
    regenerated_path = output_dir / "regenerated.npz"
    if regenerated_path.is_symlink() or not regenerated_path.is_file():
        raise RuntimeError("independent data verifier did not emit regenerated.npz")
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    if receipt is not None:
        receipt_keys = ["dataset_sha256", "config_sha256", "fixture"]
        if receipt["fixture"]:
            receipt_keys.append("source_tree_sha256")
        for key in receipt_keys:
            if receipt[key] != evidence[key]:
                raise RuntimeError(f"precomputed regeneration receipt {key} mismatch")
    with np.load(regenerated_path, allow_pickle=False) as archive:
        if set(archive.files) != REGENERATED_FIELDS:
            raise RuntimeError("regenerated data fields must be exact")
        engine = parse_strict_json(str(np.asarray(archive["engine_config_json"]).item()))
        global_engine_match = engine == dataset.engine_config
        rows = [
            _scene_comparison(
                dataset,
                archive,
                scene,
                float(manifest["rtol"]),
                float(manifest["atol"]),
            )
            for scene in range(dataset.scene_count)
        ]
    blocking = [row for row in rows if row["role"] in BLOCKING_ROLES]
    blocking_passed = bool(global_engine_match and blocking and all(row["passed"] for row in blocking))
    nonblocking_failures = [row["scene_id"] for row in rows if row["role"] not in BLOCKING_ROLES and not row["passed"]]
    role_status = {}
    for role in sorted(set(str(row["role"]) for row in rows)):
        selected = [row for row in rows if row["role"] == role]
        role_status[role] = (
            "PASS" if global_engine_match and selected and all(row["passed"] for row in selected)
            else "FAIL"
        )
    write_csv(output_dir / "per_scene.csv", bind_rows(rows, evidence))
    verification_mode = (
        "precomputed_independent_regeneration"
        if receipt is not None
        else "live_independent_regeneration"
    )
    gate = {
        "schema_version": SCHEMA,
        "status": "PASS" if blocking_passed else "FAIL",
        "passed": blocking_passed,
        "blocking_passed": blocking_passed,
        **evidence,
        "blocking_roles": list(BLOCKING_ROLES),
        "target_and_other_roles_are_nonblocking": True,
        "engine_config_match": global_engine_match,
        "engine_source_revision": manifest["engine_source_revision"],
        "engine_license_id": manifest["engine_license_id"],
        "asset_license_ids": manifest["asset_license_ids"],
        "verifier_manifest_path": str(bound_manifest.resolve()),
        "verifier_manifest_sha256": sha256_file(bound_manifest),
        "verifier_source_path": str(verifier_source),
        "verifier_source_sha256": manifest["verifier_source_sha256"],
        "verification_mode": verification_mode,
        **(
            {
                "verification_receipt_path": str(receipt_path),
                "verification_receipt_sha256": manifest["verification_receipt_sha256"],
                "verification_receipt": receipt,
            }
            if receipt is not None
            else {}
        ),
        "rtol": float(manifest["rtol"]),
        "atol": float(manifest["atol"]),
        "nonblocking_scene_failures": nonblocking_failures,
        "role_status": role_status,
        "verified_properties": [
            "canonical_rendering",
            "canonical_foundation_content_identity",
            "complete_cross_generation",
            "common_free_positions",
            "independent_repeat_noise_regeneration",
            "observation_seed_to_residual_binding",
            "world_independent_complex_phase_reference",
            "phase_reference_source_sha256",
            "path_and_noop_retrace",
            "engine_config_and_license_binding",
            verification_mode,
        ],
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


def require_data_verification(gate, config, dataset, gate_path=None):
    if not isinstance(gate, dict) or gate.get("schema_version") != SCHEMA:
        raise RuntimeError("qualification requires a V6 independent data-verification gate")
    expected = evidence_context(config, dataset, str(gate.get("scientific_use", "")))
    for key in EVIDENCE_AUTH_KEYS:
        if gate.get(key) != expected[key]:
            raise RuntimeError(f"data-verification gate {key} mismatch")
    if gate.get("blocking_roles") != list(BLOCKING_ROLES):
        raise RuntimeError("data-verification gate uses the wrong blocking roles")
    if gate.get("target_and_other_roles_are_nonblocking") is not True:
        raise RuntimeError("data-verification gate lets target data control qualification")
    if gate.get("blocking_passed") is not True or gate.get("passed") is not True:
        raise RuntimeError("independent data-verification blocking partition failed")
    _require_verifier_binding(gate, config, dataset, gate_path=gate_path)
    require_verified_roles(
        gate,
        config,
        dataset,
        BLOCKING_ROLES,
        gate_path=gate_path,
        _binding_checked=True,
    )
    return gate


def require_verified_roles(
    gate: object,
    config: dict,
    dataset,
    roles: Iterable[str],
    *,
    gate_path: str | Path | None = None,
    _binding_checked: bool = False,
) -> dict:
    """Require regeneration PASS for every role a downstream stage will read."""
    if not isinstance(gate, dict) or gate.get("schema_version") != SCHEMA:
        raise RuntimeError("stage requires a V6 independent data-verification gate")
    expected = evidence_context(config, dataset, str(gate.get("scientific_use", "")))
    for key in EVIDENCE_AUTH_KEYS:
        if gate.get(key) != expected[key]:
            raise RuntimeError(f"data-verification gate {key} mismatch")
    if not _binding_checked:
        _require_verifier_binding(gate, config, dataset, gate_path=gate_path)
    statuses = gate.get("role_status")
    if not isinstance(statuses, dict):
        raise RuntimeError("data-verification gate is missing per-role status")
    missing_or_failed = [role for role in roles if statuses.get(str(role)) != "PASS"]
    if missing_or_failed:
        raise RuntimeError(
            "data regeneration failed or was not assessed for roles: "
            + ", ".join(sorted(missing_or_failed))
        )
    return gate


def require_verified_roles_from_root(
    output_root: str | Path,
    config: dict,
    dataset,
    roles: Iterable[str],
) -> dict:
    path = Path(output_root) / "data_verification" / "gate.json"
    if not path.is_file():
        raise RuntimeError(f"missing data-verification gate: {path}")
    return require_verified_roles(
        read_strict_json(path),
        config,
        dataset,
        roles,
        gate_path=path,
    )


def export_precomputed_verification(config, dataset, verification_root, output_root):
    if dataset.is_fixture:
        raise RuntimeError("formal data-verification export rejects fixtures")
    stage = Path(verification_root).resolve() / "data_verification"
    gate_path = _require_regular_file(stage / "gate.json", "live data-verification gate")
    gate = read_strict_json(gate_path)
    require_data_verification(gate, config, dataset, gate_path=gate_path)
    if (
        gate.get("verification_mode") != "live_independent_regeneration"
        or gate.get("status") != "PASS"
        or gate.get("passed") is not True
        or gate.get("blocking_passed") is not True
        or gate.get("engine_config_match") is not True
        or gate.get("nonblocking_scene_failures") != []
        or not isinstance(gate.get("role_status"), dict)
        or not gate["role_status"]
        or any(value != "PASS" for value in gate["role_status"].values())
        or float(gate.get("rtol", -1.0)) != 0.0
        or float(gate.get("atol", -1.0)) != 0.0
        or dataset.scene_count != 34
    ):
        raise RuntimeError("only a complete 34-bank live zero-tolerance PASS can be exported")
    regenerated = _require_regular_file(
        stage / "regenerated.npz", "live independently regenerated archive"
    )
    per_scene = _require_regular_file(stage / "per_scene.csv", "live per-scene verification")
    stage_manifest = _require_regular_file(stage / "manifest.json", "live stage manifest")
    target = Path(output_root).expanduser()
    if target.exists() or target.is_symlink():
        raise FileExistsError(
            f"refusing to overwrite precomputed verification export: {target}"
        )
    target.mkdir(parents=True, exist_ok=False)
    target = target.resolve()

    dataset_target = target / "dataset.npz"
    regenerated_target = target / "regenerated.npz"
    per_scene_target = target / "per_scene.csv"
    verifier_source = Path(__file__).with_name("formal_precomputed_regeneration_verifier.py")
    verifier_target = target / verifier_source.name
    shutil.copyfile(dataset.source_path, dataset_target)
    shutil.copyfile(regenerated, regenerated_target)
    shutil.copyfile(per_scene, per_scene_target)
    shutil.copyfile(verifier_source, verifier_target)
    write_json(target / "data_contract.json", dataset.contract_report())

    evidence = evidence_context(config, dataset, "CANDIDATE_NOT_CLAIM")
    renderer_runtime = _renderer_runtime_receipt()
    receipt = {
        "schema_version": "csi-pairs-v6-precomputed-regeneration-receipt-v1",
        "status": "PASS",
        "fixture": False,
        "scientific_use": "CANDIDATE_NOT_CLAIM",
        "dataset_sha256": sha256_file(dataset_target),
        "dataset_bytes": dataset_target.stat().st_size,
        "config_sha256": evidence["config_sha256"],
        "source_tree_sha256": evidence["source_tree_sha256"],
        "origin_gate_sha256": sha256_file(gate_path),
        "origin_manifest_sha256": sha256_file(stage_manifest),
        "origin_per_scene_sha256": sha256_file(per_scene),
        "origin_verifier_source_sha256": gate["verifier_source_sha256"],
        "regenerated_path": regenerated_target.name,
        "regenerated_sha256": sha256_file(regenerated_target),
        "regenerated_bytes": regenerated_target.stat().st_size,
        "scene_count": dataset.scene_count,
        "role_status": gate["role_status"],
        "rtol": 0.0,
        "atol": 0.0,
        "engine_source_revision": gate["engine_source_revision"],
        "engine_license_id": gate["engine_license_id"],
        "asset_license_ids": gate["asset_license_ids"],
        "renderer_runtime": renderer_runtime,
    }
    receipt_path = target / "verification_receipt.json"
    write_json(receipt_path, receipt)
    verifier_manifest = {
        "schema_version": PRECOMPUTED_MANIFEST_SCHEMA,
        "command": [
            "{python}",
            "{verifier_source}",
            "--dataset",
            "{dataset}",
            "--output",
            "{output}",
            "--receipt",
            "{verification_receipt}",
        ],
        "verifier_source_path": verifier_target.name,
        "verifier_source_sha256": sha256_file(verifier_target),
        "verification_receipt_path": receipt_path.name,
        "verification_receipt_sha256": sha256_file(receipt_path),
        "engine_source_revision": gate["engine_source_revision"],
        "engine_license_id": gate["engine_license_id"],
        "asset_license_ids": gate["asset_license_ids"],
        "rtol": 0.0,
        "atol": 0.0,
    }
    write_json(target / "precomputed_verifier.json", verifier_manifest)
    (target / "README.md").write_text(
        "# CSI-PAIRS precomputed independent regeneration\n\n"
        "Verify `SHA256SUMS`, then pass `dataset.npz` and "
        "`precomputed_verifier.json` to the current CSI-PAIRS server. "
        "The target host recomputes every zero-tolerance scene comparison; "
        "these bytes are candidate input, not scientific results.\n",
        encoding="ascii",
    )
    _write_sha256sums(target)
    from .formal_precomputed_regeneration_verifier import validate_receipt

    validate_receipt(receipt_path, dataset_target, require_registration=False)
    return {
        "status": "PASS",
        "passed": True,
        "output": str(target),
        "dataset_sha256": receipt["dataset_sha256"],
        "regenerated_sha256": receipt["regenerated_sha256"],
        "verification_receipt_sha256": sha256_file(receipt_path),
        "scientific_use": "CANDIDATE_NOT_CLAIM",
    }


def _renderer_runtime_receipt() -> dict:
    from .formal_external_runtime import probe_external_runtime
    from .sionna_runtime_lock import require_runtime_record

    project = Path(__file__).resolve().parents[1]
    runtime_root = project / "formal_v2/external_adapters/.runtime-sionna"
    executable = runtime_root / "venv/bin/python"
    provenance = probe_external_runtime(
        executable,
        "sionna",
        project,
        require_execution_ready=False,
    )
    _llvm_path, llvm = require_runtime_record(project, runtime_root)
    critical = {}
    for name in ("drjit", "h5py", "mitsuba", "sionna", "sionna-rt", "torch"):
        record = provenance["installed_distributions"].get(name)
        if not isinstance(record, dict):
            raise RuntimeError(f"Sionna runtime lacks required distribution {name}")
        critical[name] = {
            "version": record["version"],
            "record_sha256": record["record_sha256"],
        }
    if provenance["lock_files"].get("sionna_approved_libllvm_registry") != llvm["registry_sha256"]:
        raise RuntimeError("Sionna runtime provenance does not bind the approved LLVM registry")
    return {
        "schema_version": "csi-pairs-sionna-renderer-runtime-receipt-v1",
        "profile": "sionna",
        "platform_system": provenance["platform_system"],
        "platform_machine": provenance["platform_machine"],
        "python_version": provenance["python_version"],
        "environment_sha256": provenance["environment_sha256"],
        "critical_distributions": critical,
        "lock_files": provenance["lock_files"],
        "libllvm_sha256": llvm["libllvm_sha256"],
        "libllvm_registry_sha256": llvm["registry_sha256"],
        "libllvm_approval_provenance": llvm["approval_provenance"],
    }


def _write_sha256sums(root: Path) -> None:
    files = sorted(
        path for path in root.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    )
    (root / "SHA256SUMS").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in files),
        encoding="ascii",
    )


def _validate_manifest(manifest, dataset):
    common = {
        "schema_version",
        "command",
        "verifier_source_path",
        "verifier_source_sha256",
        "engine_source_revision",
        "engine_license_id",
        "asset_license_ids",
        "rtol",
        "atol",
    }
    if not isinstance(manifest, dict):
        raise ValueError("data verifier manifest fields must be exact")
    schema = manifest.get("schema_version")
    required = (
        common
        if schema == LIVE_MANIFEST_SCHEMA
        else common | {"verification_receipt_path", "verification_receipt_sha256"}
        if schema == PRECOMPUTED_MANIFEST_SCHEMA
        else set()
    )
    if not required or set(manifest) != required:
        raise ValueError("data verifier manifest fields must be exact")
    if not isinstance(manifest["command"], list) or not manifest["command"]:
        raise ValueError("data verifier command must be a nonempty argv list")
    if not _command_executes_verifier_source(
        manifest["command"], precomputed=schema == PRECOMPUTED_MANIFEST_SCHEMA
    ):
        raise ValueError(
            "data verifier command must directly execute the authenticated source "
            "and bind dataset/output exactly once"
        )
    source_path = manifest["verifier_source_path"]
    if (
        not isinstance(source_path, str)
        or not source_path.strip()
        or Path(source_path).suffix != ".py"
        or not _lower_sha256(manifest["verifier_source_sha256"])
    ):
        raise ValueError("data verifier source path/hash is invalid")
    if manifest["engine_source_revision"] != dataset.metadata["engine"]["source_revision"]:
        raise ValueError("data verifier engine revision does not match the dataset")
    if manifest["engine_license_id"] != dataset.metadata["engine"]["license_id"]:
        raise ValueError("data verifier engine license does not match the dataset")
    if sorted(manifest["asset_license_ids"]) != sorted(dataset.metadata["assets"]["license_ids"]):
        raise ValueError("data verifier asset licenses do not match the dataset")
    for name in ("rtol", "atol"):
        if not np.isfinite(manifest[name]) or float(manifest[name]) < 0:
            raise ValueError(f"data verifier {name} must be finite and nonnegative")
    if schema == PRECOMPUTED_MANIFEST_SCHEMA:
        if (
            not isinstance(manifest["verification_receipt_path"], str)
            or not manifest["verification_receipt_path"].strip()
            or not _lower_sha256(manifest["verification_receipt_sha256"])
            or float(manifest["rtol"]) != 0.0
            or float(manifest["atol"]) != 0.0
        ):
            raise ValueError("precomputed data verifier receipt or tolerance is invalid")


def _command_executes_verifier_source(command, *, precomputed=False) -> bool:
    if not isinstance(command, list) or any(
        not isinstance(value, str) or not value for value in command
    ):
        return False
    placeholders = ["{python}", "{verifier_source}", "{dataset}", "{output}"]
    if precomputed:
        placeholders.append("{verification_receipt}")
    if command[:2] != ["{python}", "{verifier_source}"]:
        return False
    if any(command.count(value) != 1 for value in placeholders):
        return False
    if any(
        ("{" in value or "}" in value) and value not in placeholders
        for value in command
    ):
        return False
    valid = bool(
        _command_binds_option(command, "--dataset", "{dataset}")
        and _command_binds_option(command, "--output", "{output}")
    )
    if precomputed:
        valid = valid and _command_binds_option(
            command, "--receipt", "{verification_receipt}"
        )
    return valid


def _command_binds_option(command, option, placeholder) -> bool:
    indices = [index for index, value in enumerate(command) if value == option]
    return bool(
        len(indices) == 1
        and indices[0] + 1 < len(command)
        and command[indices[0] + 1] == placeholder
    )


def _resolve_verifier_source(manifest, manifest_root: Path) -> Path:
    source = Path(manifest["verifier_source_path"])
    candidate = source if source.is_absolute() else Path(manifest_root) / source
    resolved = _require_regular_file(candidate, "data verifier source")
    _require_file_sha256(
        resolved,
        manifest["verifier_source_sha256"],
        "data verifier source",
    )
    if manifest["schema_version"] == PRECOMPUTED_MANIFEST_SCHEMA:
        builtin = Path(__file__).with_name("formal_precomputed_regeneration_verifier.py")
        if manifest["verifier_source_sha256"] != sha256_file(builtin):
            raise RuntimeError("precomputed verifier source differs from the shipped adapter")
    return resolved


def _resolve_precomputed_receipt(manifest, manifest_root: Path, dataset):
    from .formal_precomputed_regeneration_verifier import validate_receipt

    source = Path(manifest["verification_receipt_path"])
    candidate = source if source.is_absolute() else manifest_root / source
    path = _require_regular_file(candidate, "precomputed regeneration receipt")
    _require_file_sha256(
        path,
        manifest["verification_receipt_sha256"],
        "precomputed regeneration receipt",
    )
    receipt, _regenerated = validate_receipt(path, dataset.source_path)
    for key in (
        "engine_source_revision",
        "engine_license_id",
        "asset_license_ids",
        "rtol",
        "atol",
    ):
        if receipt[key] != manifest[key]:
            raise RuntimeError(f"precomputed regeneration receipt {key} mismatch")
    return path, receipt


def _require_regular_file(path, label: str) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_symlink() or not candidate.is_file():
        raise RuntimeError(f"{label} must be a regular non-symlink file: {candidate}")
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise RuntimeError(f"{label} must be a regular file: {candidate}")
    return resolved


def _require_file_sha256(path, expected, label: str) -> None:
    if not _lower_sha256(expected) or sha256_file(path) != expected:
        raise RuntimeError(f"{label} hash mismatch")


def _lower_sha256(value) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_verifier_binding(gate, config, dataset, *, gate_path=None) -> None:
    required = {
        "verifier_manifest_path",
        "verifier_manifest_sha256",
        "verifier_source_path",
        "verifier_source_sha256",
        "engine_source_revision",
        "engine_license_id",
        "asset_license_ids",
        "rtol",
        "atol",
        "verification_mode",
    }
    missing = required.difference(gate)
    if missing:
        raise RuntimeError(
            "data-verification gate is missing authenticated verifier fields: "
            f"{sorted(missing)}"
        )
    manifest_path = _require_regular_file(
        gate["verifier_manifest_path"], "bound data verifier manifest"
    )
    _require_file_sha256(
        manifest_path,
        gate["verifier_manifest_sha256"],
        "bound data verifier manifest",
    )
    manifest = read_strict_json(manifest_path)
    _validate_manifest(manifest, dataset)
    source = _resolve_verifier_source(manifest, manifest_path.parent)
    gate_source = _require_regular_file(
        gate["verifier_source_path"], "data verifier source"
    )
    if source != gate_source:
        raise RuntimeError("data-verification gate verifier source path mismatch")
    _require_file_sha256(
        gate_source,
        gate["verifier_source_sha256"],
        "data verifier source",
    )
    if gate["verifier_source_sha256"] != manifest["verifier_source_sha256"]:
        raise RuntimeError("data-verification gate verifier source hash mismatch")
    for key in (
        "engine_source_revision",
        "engine_license_id",
        "asset_license_ids",
        "rtol",
        "atol",
    ):
        if gate[key] != manifest[key]:
            raise RuntimeError(f"data-verification gate {key} differs from verifier manifest")
    expected_mode = (
        "precomputed_independent_regeneration"
        if manifest["schema_version"] == PRECOMPUTED_MANIFEST_SCHEMA
        else "live_independent_regeneration"
    )
    if gate["verification_mode"] != expected_mode:
        raise RuntimeError("data-verification gate verification mode mismatch")
    if manifest["schema_version"] == PRECOMPUTED_MANIFEST_SCHEMA:
        receipt_path, receipt = _resolve_precomputed_receipt(
            manifest, manifest_path.parent, dataset
        )
        if (
            gate.get("verification_receipt_path") != str(receipt_path)
            or gate.get("verification_receipt_sha256")
            != manifest["verification_receipt_sha256"]
            or gate.get("verification_receipt") != receipt
        ):
            raise RuntimeError("data-verification gate precomputed receipt mismatch")
    if gate_path is not None:
        from .formal_evidence import require_stage_manifested_gate

        resolved_gate = _require_regular_file(gate_path, "data-verification gate")
        require_stage_manifested_gate(
            resolved_gate,
            gate,
            config,
            dataset,
            schema_version=SCHEMA,
        )
        expected_manifest = (resolved_gate.parent / "verifier_manifest.json").resolve()
        if manifest_path != expected_manifest:
            raise RuntimeError(
                "data-verification gate does not bind its colocated verifier manifest"
            )
        _require_stage_file(resolved_gate.parent, manifest_path)


def _require_stage_file(stage_dir: Path, path: Path) -> None:
    manifest_path = stage_dir / "manifest.json"
    manifest = read_strict_json(manifest_path)
    entries = manifest.get("files") if isinstance(manifest, dict) else None
    relative = str(path.relative_to(stage_dir))
    matches = [
        row
        for row in entries
        if isinstance(row, dict) and row.get("path") == relative
    ] if isinstance(entries, list) else []
    if len(matches) != 1 or matches[0].get("sha256") != sha256_file(path):
        raise RuntimeError(
            "bound data verifier manifest is absent from or mismatched with its stage manifest"
        )


def _verifier_environment(project_root: Path) -> dict[str, str]:
    root = str(project_root.resolve())
    existing = os.environ.get("PYTHONPATH", "")
    return {
        **os.environ,
        "PYTHONPATH": root if not existing else root + os.pathsep + existing,
    }


def _scene_comparison(dataset, archive, scene, rtol, atol):
    zero_world = int(np.flatnonzero(np.all(dataset.world_bits == 0, axis=1))[0])
    representation = dataset.metadata["representation"]
    regenerated_foundation_digest = _canonical_foundation_sha256(
        archive["maps"][scene, zero_world],
        dataset.map_channel_names,
        float(representation["map_resolution_m"]),
        representation["map_origin_xy_m"],
    )
    expected_foundation_digest = dataset.canonical_base_map_digest(scene)
    regenerated_noise_digest = dataset.observation_noise_binding_digest(
        scene, archive["csi_repeat"][scene]
    )
    expected_noise_digest = dataset.observation_noise_binding_digest(scene)
    checks = {
        "maps": _equal(dataset.maps[scene], archive["maps"][scene], rtol, atol),
        "canonical_foundation_identity": regenerated_foundation_digest
        == expected_foundation_digest,
        "csi_clean": _equal(dataset.csi_clean[scene], archive["csi_clean"][scene], rtol, atol),
        "csi_repeat": _equal(dataset.csi_repeat[scene], archive["csi_repeat"][scene], rtol, atol),
        "observation_noise_seed_binding": regenerated_noise_digest == expected_noise_digest,
        "free_space": np.array_equal(dataset.free_space[scene], archive["free_space"][scene]),
        "phase_reference_ids": np.array_equal(dataset.phase_reference_ids[scene], archive["phase_reference_ids"][scene]),
        "phase_reference_values": np.array_equal(
            dataset.phase_reference_values[scene],
            archive["phase_reference_values"][scene],
        ),
        "phase_reference_source_sha256": np.array_equal(
            dataset.phase_reference_source_sha256[scene],
            archive["phase_reference_source_sha256"][scene],
        ),
        "noop_maps": _equal(dataset.noop_maps[scene], archive["noop_maps"][scene], rtol, atol),
        "path_ids": np.array_equal(dataset.path_ids[scene], archive["path_ids"][scene]),
        "path_power": _equal(dataset.path_power[scene], archive["path_power"][scene], rtol, atol),
        "path_surface_ids": np.array_equal(dataset.path_surface_ids[scene], archive["path_surface_ids"][scene]),
        "noop_path_ids": np.array_equal(dataset.noop_path_ids[scene], archive["noop_path_ids"][scene]),
        "noop_path_power": _equal(dataset.noop_path_power[scene], archive["noop_path_power"][scene], rtol, atol),
        "noop_path_surface_ids": np.array_equal(dataset.noop_path_surface_ids[scene], archive["noop_path_surface_ids"][scene]),
    }
    return {
        "scene_id": str(dataset.scene_ids[scene]),
        "bank_id": str(dataset.bank_ids[scene]),
        "base_map_cluster_id": str(dataset.base_map_cluster_ids[scene]),
        "canonical_base_map_digest": expected_foundation_digest,
        "regenerated_canonical_base_map_digest": regenerated_foundation_digest,
        "observation_noise_binding_sha256": expected_noise_digest,
        "regenerated_observation_noise_binding_sha256": regenerated_noise_digest,
        "role": str(dataset.scene_roles[scene]),
        **{f"{name}_match": bool(value) for name, value in checks.items()},
        "passed": bool(all(checks.values())),
    }


def _equal(first, second, rtol, atol):
    left = np.asarray(first)
    right = np.asarray(second)
    return left.shape == right.shape and bool(np.allclose(left, right, rtol=rtol, atol=atol))
