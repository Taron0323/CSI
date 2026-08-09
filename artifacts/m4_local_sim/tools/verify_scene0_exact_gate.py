#!/usr/bin/env python3
"""Independently gate the two fresh scene-0 LLVM outputs at exact equality."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np


SCIENTIFIC_USE = "DIAGNOSTIC_NOT_FORMAL_EVIDENCE"
RENDER_FIELDS = {
    "anchor_bits",
    "bs_pose",
    "csi_clean",
    "csi_repeat",
    "free_space",
    "maps",
    "natural_world_index",
    "noop_maps",
    "noop_path_ids",
    "noop_path_power",
    "noop_path_surface_ids",
    "path_ids",
    "path_power",
    "path_surface_ids",
    "phase_reference_ids",
    "phase_reference_source_sha256",
    "phase_reference_values",
    "positions",
    "primitive_ids",
    "primitive_surface_ids",
    "radio_config",
    "repeat_seeds",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def verify(left: Path, right: Path, comparison_path: Path) -> dict:
    comparison = _read_json(comparison_path)
    arrays_report = comparison.get("arrays")
    if not isinstance(arrays_report, dict) or set(arrays_report) != RENDER_FIELDS:
        raise ValueError("comparator did not cover the exact registered render field set")
    comparator_exact = {
        name: row.get("exact") is True for name, row in arrays_report.items()
    }
    with np.load(left, allow_pickle=False) as archive:
        left_arrays = {name: np.asarray(archive[name]) for name in archive.files}
    with np.load(right, allow_pickle=False) as archive:
        right_arrays = {name: np.asarray(archive[name]) for name in archive.files}
    expected_npz_fields = RENDER_FIELDS | {"scene_indices"}
    if set(left_arrays) != expected_npz_fields or set(right_arrays) != expected_npz_fields:
        raise ValueError("fresh output NPZ field set differs from the registered renderer")
    independent_exact = {
        name: bool(np.array_equal(left_arrays[name], right_arrays[name]))
        for name in sorted(expected_npz_fields)
    }
    left_hash = _sha256(left)
    right_hash = _sha256(right)
    left_manifest_path = left.with_suffix(".manifest.json")
    right_manifest_path = right.with_suffix(".manifest.json")
    left_manifest = _read_json(left_manifest_path)
    right_manifest = _read_json(right_manifest_path)
    manifest_checks = {
        "simulation_classification": all(
            manifest.get("simulation_not_measurement") is True
            and manifest.get("scientific_use") == SCIENTIFIC_USE
            for manifest in (left_manifest, right_manifest)
        ),
        "llvm_backend": all(
            manifest.get("backend") == "llvm" for manifest in (left_manifest, right_manifest)
        ),
        "llvm_variant": all(
            manifest.get("mitsuba_variant") == "llvm_ad_mono_polarized"
            for manifest in (left_manifest, right_manifest)
        ),
        "drjit_single_thread": all(
            manifest.get("drjit_thread_count") == 1
            for manifest in (left_manifest, right_manifest)
        ),
        "scene_identity": all(
            manifest.get("scene_index") == 0
            and manifest.get("scene_id") == "osm-sionna-source-chicago-bank-00"
            for manifest in (left_manifest, right_manifest)
        ),
        "manifest_output_hashes": (
            left_manifest.get("output_sha256") == left_hash
            and right_manifest.get("output_sha256") == right_hash
        ),
    }
    path_valid = (left_arrays["path_ids"] >= 0) & (left_arrays["path_power"] > 0)
    nonempty_rt = (
        left.stat().st_size > 0
        and right.stat().st_size > 0
        and int(np.count_nonzero(path_valid)) > 0
        and int(np.count_nonzero(left_arrays["csi_clean"])) > 0
    )
    checks = {
        "two_fresh_process_manifests": all(manifest_checks.values()),
        "comparator_status_pass": comparison.get("status") == "PASS",
        "comparator_all_required_fields_exact": all(comparator_exact.values()),
        "independent_all_npz_fields_exact": all(independent_exact.values()),
        "output_sha_identical": left_hash == right_hash,
        "nonempty_rt_output": nonempty_rt,
    }
    return {
        "schema_version": "csi-pairs-m4-scene0-exact-gate-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "simulation_not_measurement": True,
        "scientific_use": SCIENTIFIC_USE,
        "formal_data_ready": "NO",
        "formal_status": "POST_AUDIT_NO_GO",
        "formal_scientific_use": "FORBIDDEN",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scene_index": 0,
        "scene_id": "osm-sionna-source-chicago-bank-00",
        "rtol": 0,
        "atol": 0,
        "checks": checks,
        "comparator": {
            "path": str(comparison_path.resolve()),
            "sha256": _sha256(comparison_path),
            "exact_fields": sum(comparator_exact.values()),
            "total_fields": len(comparator_exact),
            "fields": comparator_exact,
        },
        "independent_npz_comparison": {
            "exact_fields": sum(independent_exact.values()),
            "total_fields": len(independent_exact),
            "fields": independent_exact,
        },
        "output_a": {
            "path": str(left.resolve()),
            "bytes": left.stat().st_size,
            "sha256": left_hash,
            "manifest_path": str(left_manifest_path.resolve()),
            "duration_seconds": left_manifest.get("duration_seconds"),
        },
        "output_b": {
            "path": str(right.resolve()),
            "bytes": right.stat().st_size,
            "sha256": right_hash,
            "manifest_path": str(right_manifest_path.resolve()),
            "duration_seconds": right_manifest.get("duration_seconds"),
        },
        "runtime_manifest_checks": manifest_checks,
        "nonempty_rt": {
            "valid_path_slots": int(np.count_nonzero(path_valid)),
            "nonzero_clean_csi_scalars": int(np.count_nonzero(left_arrays["csi_clean"])),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--process-a", type=Path, required=True)
    parser.add_argument("--process-b", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to overwrite {output}")
    report = verify(
        args.process_a.resolve(), args.process_b.resolve(), args.comparison.resolve()
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="ascii") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"output": str(output), "status": report["status"]}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
