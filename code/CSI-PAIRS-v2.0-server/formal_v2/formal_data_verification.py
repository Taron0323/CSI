from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Iterable

import numpy as np

from .formal_dataset import _canonical_foundation_sha256
from .formal_evidence import bind_rows, evidence_context
from .formal_io import (
    artifact_manifest,
    parse_strict_json,
    read_strict_json,
    write_csv,
    write_json,
)


SCHEMA = "csi-pairs-v6-data-verification-gate-v1"
BLOCKING_ROLES = ("source_encoder_train", "source_method_selection")
REGENERATED_FIELDS = {
    "maps",
    "csi_clean",
    "csi_repeat",
    "free_space",
    "phase_reference_ids",
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
    from .formal_io import read_strict_json

    manifest = read_strict_json(manifest_path)
    _validate_manifest(manifest, dataset)
    output_dir = Path(output_root) / "data_verification"
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        value.format(dataset=str(dataset.source_path), output=str(output_dir), python=sys.executable)
        for value in manifest["command"]
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    (output_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"independent data verifier failed with code {completed.returncode}")
    regenerated_path = output_dir / "regenerated.npz"
    if not regenerated_path.is_file():
        raise RuntimeError("independent data verifier did not emit regenerated.npz")
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
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
            "pair_consistent_phase_reference",
            "path_and_noop_retrace",
            "engine_config_and_license_binding",
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


def require_data_verification(gate, config, dataset):
    if not isinstance(gate, dict) or gate.get("schema_version") != SCHEMA:
        raise RuntimeError("qualification requires a V6 independent data-verification gate")
    expected = evidence_context(config, dataset, str(gate.get("scientific_use", "")))
    for key in ("dataset_sha256", "config_sha256", "fixture"):
        if gate.get(key) != expected[key]:
            raise RuntimeError(f"data-verification gate {key} mismatch")
    if gate.get("blocking_roles") != list(BLOCKING_ROLES):
        raise RuntimeError("data-verification gate uses the wrong blocking roles")
    if gate.get("target_and_other_roles_are_nonblocking") is not True:
        raise RuntimeError("data-verification gate lets target data control qualification")
    if gate.get("blocking_passed") is not True or gate.get("passed") is not True:
        raise RuntimeError("independent data-verification blocking partition failed")
    require_verified_roles(gate, config, dataset, BLOCKING_ROLES)
    return gate


def require_verified_roles(
    gate: object,
    config: dict,
    dataset,
    roles: Iterable[str],
) -> dict:
    """Require regeneration PASS for every role a downstream stage will read."""
    if not isinstance(gate, dict) or gate.get("schema_version") != SCHEMA:
        raise RuntimeError("stage requires a V6 independent data-verification gate")
    expected = evidence_context(config, dataset, str(gate.get("scientific_use", "")))
    for key in ("dataset_sha256", "config_sha256", "fixture"):
        if gate.get(key) != expected[key]:
            raise RuntimeError(f"data-verification gate {key} mismatch")
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
    return require_verified_roles(read_strict_json(path), config, dataset, roles)


def _validate_manifest(manifest, dataset):
    required = {
        "schema_version",
        "command",
        "engine_source_revision",
        "engine_license_id",
        "asset_license_ids",
        "rtol",
        "atol",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("data verifier manifest fields must be exact")
    if manifest["schema_version"] != "csi-pairs-v6-data-verifier-v1":
        raise ValueError("data verifier manifest schema mismatch")
    if not isinstance(manifest["command"], list) or not manifest["command"]:
        raise ValueError("data verifier command must be a nonempty argv list")
    if manifest["engine_source_revision"] != dataset.metadata["engine"]["source_revision"]:
        raise ValueError("data verifier engine revision does not match the dataset")
    if manifest["engine_license_id"] != dataset.metadata["engine"]["license_id"]:
        raise ValueError("data verifier engine license does not match the dataset")
    if sorted(manifest["asset_license_ids"]) != sorted(dataset.metadata["assets"]["license_ids"]):
        raise ValueError("data verifier asset licenses do not match the dataset")
    for name in ("rtol", "atol"):
        if not np.isfinite(manifest[name]) or float(manifest[name]) < 0:
            raise ValueError(f"data verifier {name} must be finite and nonnegative")


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
