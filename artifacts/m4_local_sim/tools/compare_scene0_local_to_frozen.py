#!/usr/bin/env python3
"""Compare one local LLVM scene row with the frozen handoff candidate row."""

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


def _load(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {name: np.asarray(archive[name]) for name in archive.files}


def _row_from_local(
    arrays: dict[str, np.ndarray], scene_index: int
) -> dict[str, np.ndarray]:
    if "scene_indices" not in arrays:
        raise ValueError("local shard does not contain scene_indices")
    matches = np.flatnonzero(arrays["scene_indices"] == scene_index)
    if matches.size != 1:
        raise ValueError(f"local scene index {scene_index} is not unique")
    missing = sorted(RENDER_FIELDS - arrays.keys())
    if missing:
        raise ValueError(f"local shard is missing registered fields: {missing}")
    row = int(matches[0])
    return {name: np.asarray(arrays[name][row]) for name in sorted(RENDER_FIELDS)}


def _row_from_frozen(
    arrays: dict[str, np.ndarray], scene_id: str
) -> tuple[int, dict[str, np.ndarray]]:
    if "scene_ids" not in arrays:
        raise ValueError("frozen candidate does not contain scene_ids")
    matches = np.flatnonzero(np.asarray(arrays["scene_ids"]).astype(str) == scene_id)
    if matches.size != 1:
        raise ValueError(f"frozen scene id {scene_id!r} is not unique")
    missing = sorted(RENDER_FIELDS - arrays.keys())
    if missing:
        raise ValueError(f"frozen candidate is missing registered fields: {missing}")
    row = int(matches[0])
    return row, {
        name: np.asarray(arrays[name][row]) for name in sorted(RENDER_FIELDS)
    }


def _field_record(local: np.ndarray, frozen: np.ndarray) -> dict:
    if local.shape != frozen.shape:
        return {
            "exact": False,
            "local_shape": list(local.shape),
            "frozen_shape": list(frozen.shape),
            "local_dtype": str(local.dtype),
            "frozen_dtype": str(frozen.dtype),
            "different_elements": None,
        }
    exact_mask = np.equal(local, frozen)
    record = {
        "exact": bool(np.array_equal(local, frozen)),
        "local_shape": list(local.shape),
        "frozen_shape": list(frozen.shape),
        "local_dtype": str(local.dtype),
        "frozen_dtype": str(frozen.dtype),
        "different_elements": int(exact_mask.size - np.count_nonzero(exact_mask)),
    }
    if np.issubdtype(local.dtype, np.number) and np.issubdtype(
        frozen.dtype, np.number
    ):
        difference = np.abs(local - frozen)
        record["max_absolute_difference"] = (
            float(np.max(difference)) if difference.size else 0.0
        )
    return record


def compare(
    local_path: Path,
    frozen_path: Path,
    scene_index: int,
    scene_id: str,
) -> dict:
    local_arrays = _load(local_path)
    frozen_arrays = _load(frozen_path)
    local = _row_from_local(local_arrays, scene_index)
    frozen_row, frozen = _row_from_frozen(frozen_arrays, scene_id)
    fields = {
        name: _field_record(local[name], frozen[name])
        for name in sorted(RENDER_FIELDS)
    }
    exact_count = sum(record["exact"] for record in fields.values())
    return {
        "schema_version": "csi-pairs-m4-local-vs-frozen-scene-comparison-v1",
        "status": "EXACT" if exact_count == len(fields) else "NOT_EXACT",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "simulation_not_measurement": True,
        "scientific_use": SCIENTIFIC_USE,
        "formal_data_ready": "NO",
        "formal_status": "POST_AUDIT_NO_GO",
        "formal_scientific_use": "FORBIDDEN",
        "scope": "LOCAL_MACOS_LLVM_ROW_VS_FROZEN_HANDOFF_CANDIDATE_ROW",
        "comparison_method": "np.array_equal",
        "rtol": 0,
        "atol": 0,
        "scene_index": scene_index,
        "scene_id": scene_id,
        "frozen_row_index": frozen_row,
        "local": {
            "path": str(local_path.resolve()),
            "sha256": _sha256(local_path),
        },
        "frozen": {
            "path": str(frozen_path.resolve()),
            "sha256": _sha256(frozen_path),
        },
        "exact_fields": exact_count,
        "total_fields": len(fields),
        "different_fields": [
            name for name, record in fields.items() if not record["exact"]
        ],
        "fields": fields,
        "interpretation": (
            "NOT_EXACT is retained diagnostic evidence. Local LLVM A-vs-B "
            "repeatability does not imply exact reproduction of the frozen "
            "handoff candidate or cross-backend equivalence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--scene-index", type=int, required=True)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to overwrite {output}")
    report = compare(
        args.local.resolve(),
        args.frozen.resolve(),
        args.scene_index,
        args.scene_id,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="ascii") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(
        json.dumps(
            {
                "exact_fields": report["exact_fields"],
                "output": str(output),
                "status": report["status"],
                "total_fields": report["total_fields"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
