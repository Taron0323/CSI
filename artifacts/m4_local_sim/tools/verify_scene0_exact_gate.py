#!/usr/bin/env python3
"""Independently gate the two fresh scene-0 LLVM outputs at exact equality."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

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
EXPECTED_NPZ_FIELDS = RENDER_FIELDS | {"scene_indices"}
EXPECTED_RUNTIME = {
    "python": "3.12.13",
    "sionna": "2.0.1",
    "sionna_rt": "1.2.1",
    "mitsuba": "3.7.1",
    "drjit": "1.2.0",
    "backend": "llvm",
    "platform_system": "Darwin",
    "platform_machine": "arm64",
    "mitsuba_variant": "llvm_ad_mono_polarized",
    "drjit_thread_count": 1,
    "python_dont_write_bytecode": True,
}
RUNTIME_FIELDS = set(EXPECTED_RUNTIME) | {
    "python_executable",
    "drjit_libllvm_path",
    "drjit_libllvm_sha256",
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


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _bound_file_matches(path_value: object, digest: object) -> bool:
    if not isinstance(path_value, str) or not _is_sha256(digest):
        return False
    path = Path(path_value)
    return (
        path.is_absolute()
        and not path.is_symlink()
        and path.is_file()
        and _sha256(path) == digest
    )


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _runtime_is_frozen(runtime: object) -> bool:
    if not isinstance(runtime, dict) or set(runtime) != RUNTIME_FIELDS:
        return False
    if any(runtime.get(key) != expected for key, expected in EXPECTED_RUNTIME.items()):
        return False
    python = Path(str(runtime.get("python_executable", "")))
    llvm = Path(str(runtime.get("drjit_libllvm_path", "")))
    return (
        python.is_absolute()
        and python.is_file()
        and llvm.is_absolute()
        and _bound_file_matches(
            runtime.get("drjit_libllvm_path"),
            runtime.get("drjit_libllvm_sha256"),
        )
    )


def _comparison_input_matches(record: object, path: Path, digest: str) -> bool:
    return (
        isinstance(record, dict)
        and record.get("path") == str(path.resolve())
        and record.get("bytes") == path.stat().st_size
        and record.get("sha256") == digest
    )


def verify(left: Path, right: Path, comparison_path: Path) -> dict:
    left = left.resolve()
    right = right.resolve()
    comparison_path = comparison_path.resolve()
    if left == right:
        raise ValueError("process A and process B must be distinct output paths")
    left_manifest_path = left.with_suffix(".manifest.json").resolve()
    right_manifest_path = right.with_suffix(".manifest.json").resolve()
    if left_manifest_path == right_manifest_path:
        raise ValueError("process A and process B must have distinct manifests")
    comparison = _read_json(comparison_path)
    arrays_report = comparison.get("arrays")
    if not isinstance(arrays_report, dict) or set(arrays_report) != EXPECTED_NPZ_FIELDS:
        raise ValueError("comparator did not cover the exact registered render field set")
    comparator_exact = {
        name: row.get("exact") is True for name, row in arrays_report.items()
    }
    with np.load(left, allow_pickle=False) as archive:
        left_arrays = {name: np.asarray(archive[name]) for name in archive.files}
    with np.load(right, allow_pickle=False) as archive:
        right_arrays = {name: np.asarray(archive[name]) for name in archive.files}
    if set(left_arrays) != EXPECTED_NPZ_FIELDS or set(right_arrays) != EXPECTED_NPZ_FIELDS:
        raise ValueError("fresh output NPZ field set differs from the registered renderer")
    independent_exact = {
        name: bool(np.array_equal(left_arrays[name], right_arrays[name]))
        for name in sorted(EXPECTED_NPZ_FIELDS)
    }
    all_finite = all(
        not np.issubdtype(arrays[name].dtype, np.number)
        or bool(np.isfinite(arrays[name]).all())
        for arrays in (left_arrays, right_arrays)
        for name in EXPECTED_NPZ_FIELDS
    )
    left_hash = _sha256(left)
    right_hash = _sha256(right)
    left_manifest = _read_json(left_manifest_path)
    right_manifest = _read_json(right_manifest_path)
    left_started = _timestamp(left_manifest.get("started_utc"), "process A started_utc")
    left_ended = _timestamp(left_manifest.get("ended_utc"), "process A ended_utc")
    right_started = _timestamp(right_manifest.get("started_utc"), "process B started_utc")
    right_ended = _timestamp(right_manifest.get("ended_utc"), "process B ended_utc")
    valid_windows = left_started < left_ended and right_started < right_ended
    nonoverlapping_windows = left_ended <= right_started or right_ended <= left_started
    runtimes = (left_manifest.get("runtime"), right_manifest.get("runtime"))
    manifest_checks = {
        "manifest_schema": all(
            manifest.get("schema_version") == "csi-pairs-sionna-bank-backend-diagnostic-v2"
            for manifest in (left_manifest, right_manifest)
        ),
        "simulation_classification": all(
            manifest.get("simulation_not_measurement") is True
            and manifest.get("scientific_use") == SCIENTIFIC_USE
            and manifest.get("status") == SCIENTIFIC_USE
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
        "manifest_output_paths": (
            left_manifest.get("output_path") == str(left)
            and right_manifest.get("output_path") == str(right)
        ),
        "manifest_output_sizes": (
            left_manifest.get("output_bytes") == left.stat().st_size
            and right_manifest.get("output_bytes") == right.stat().st_size
        ),
        "distinct_run_ids": (
            isinstance(left_manifest.get("run_id"), str)
            and re.fullmatch(r"[0-9a-f]{32}", left_manifest["run_id"]) is not None
            and isinstance(right_manifest.get("run_id"), str)
            and re.fullmatch(r"[0-9a-f]{32}", right_manifest["run_id"]) is not None
            and left_manifest["run_id"] != right_manifest["run_id"]
        ),
        "valid_nonoverlapping_process_windows": valid_windows and nonoverlapping_windows,
        "frozen_runtime": all(_runtime_is_frozen(runtime) for runtime in runtimes),
        "same_runtime": runtimes[0] == runtimes[1],
        "same_asset_manifest": (
            _is_sha256(left_manifest.get("asset_manifest_sha256"))
            and left_manifest.get("asset_manifest_sha256")
            == right_manifest.get("asset_manifest_sha256")
            and all(
                _bound_file_matches(
                    manifest.get("asset_manifest_path"),
                    manifest.get("asset_manifest_sha256"),
                )
                for manifest in (left_manifest, right_manifest)
            )
        ),
        "same_generator_and_tool": all(
            _is_sha256(left_manifest.get(field))
            and left_manifest.get(field) == right_manifest.get(field)
            and all(
                _bound_file_matches(
                    manifest.get(field.removesuffix("_sha256") + "_path"),
                    manifest.get(field),
                )
                for manifest in (left_manifest, right_manifest)
            )
            for field in ("generator_sha256", "tool_sha256")
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
        "comparator_inputs_bound": (
            _comparison_input_matches(comparison.get("process_a"), left, left_hash)
            and _comparison_input_matches(comparison.get("process_b"), right, right_hash)
        ),
        "comparator_all_required_fields_exact": all(comparator_exact.values()),
        "independent_all_npz_fields_exact": all(independent_exact.values()),
        "all_numeric_fields_finite": all_finite,
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
            "run_id": left_manifest.get("run_id"),
            "started_utc": left_manifest.get("started_utc"),
            "ended_utc": left_manifest.get("ended_utc"),
            "duration_seconds": left_manifest.get("duration_seconds"),
        },
        "output_b": {
            "path": str(right.resolve()),
            "bytes": right.stat().st_size,
            "sha256": right_hash,
            "manifest_path": str(right_manifest_path.resolve()),
            "run_id": right_manifest.get("run_id"),
            "started_utc": right_manifest.get("started_utc"),
            "ended_utc": right_manifest.get("ended_utc"),
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
