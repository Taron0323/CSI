#!/usr/bin/env python3
"""Summarize structural CSI/path consistency without assigning scientific validity."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np


SCIENTIFIC_USE = "DIAGNOSTIC_NOT_FORMAL_EVIDENCE"
STABLE_SURFACE_IDS = {-1, 100, 101, 102, 103}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _group(role: str) -> str:
    if role.startswith("source_"):
        return "source"
    if role == "target":
        return "target"
    if role == "external_validation":
        return "external"
    return f"unknown:{role}"


def _pairwise_intersections(values: dict[str, set[str]]) -> dict[str, int]:
    names = sorted(values)
    return {
        f"{left}__{right}": len(values[left] & values[right])
        for index, left in enumerate(names)
        for right in names[index + 1 :]
    }


def _path_report(ids: np.ndarray, power: np.ndarray, surfaces: np.ndarray) -> dict:
    id_present = ids >= 0
    power_present = power > 0
    valid = id_present & power_present
    counts = np.count_nonzero(valid, axis=-1)
    invalid_slot_surface_values = int(
        np.count_nonzero((~id_present)[..., None] & (surfaces >= 0))
    )
    invalid_surface_values = int(
        np.count_nonzero(~np.isin(surfaces, tuple(sorted(STABLE_SURFACE_IDS))))
    )
    return {
        "id_power_presence_mismatch": int(np.count_nonzero(id_present != power_present)),
        "invalid_slot_nonnegative_surface_values": invalid_slot_surface_values,
        "surface_values_outside_registered_catalog": invalid_surface_values,
        "path_count_min": int(counts.min()),
        "path_count_median": float(np.median(counts)),
        "path_count_p90": float(np.quantile(counts, 0.9)),
        "path_count_max": int(counts.max()),
        "positions_at_capacity_64": int(np.count_nonzero(counts == 64)),
        "positions_exceeding_capacity_64": int(np.count_nonzero(counts > 64)),
        "visible_mask": valid.any(axis=-1),
    }


def audit(dataset: Path) -> dict:
    with np.load(dataset, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}

    required = {
        "csi_clean",
        "csi_repeat",
        "path_ids",
        "path_power",
        "path_surface_ids",
        "noop_path_ids",
        "noop_path_power",
        "noop_path_surface_ids",
        "phase_reference_ids",
        "phase_reference_values",
        "phase_reference_source_sha256",
        "repeat_seeds",
        "scene_ids",
        "city_ids",
        "scene_roles",
        "bank_ids",
        "base_map_cluster_ids",
        "position_ids",
        "position_roles",
        "positions",
        "world_bits",
        "maps",
        "noop_maps",
        "primitive_surface_ids",
        "metadata_json",
        "engine_config_json",
    }
    missing = sorted(required - set(arrays))
    if missing:
        raise ValueError(f"candidate is missing required arrays: {missing}")

    clean = arrays["csi_clean"]
    repeated = arrays["csi_repeat"]
    paths = _path_report(
        arrays["path_ids"], arrays["path_power"], arrays["path_surface_ids"]
    )
    noop_paths = _path_report(
        arrays["noop_path_ids"],
        arrays["noop_path_power"],
        arrays["noop_path_surface_ids"],
    )
    visible = paths.pop("visible_mask")
    noop_visible = noop_paths.pop("visible_mask")
    zero_csi = np.all(np.abs(clean) == 0, axis=-1)

    roles = arrays["scene_roles"].astype(str)
    groups = np.asarray([_group(value) for value in roles])
    split_intersections = {}
    for field in ("scene_ids", "city_ids", "bank_ids", "base_map_cluster_ids"):
        values = arrays[field].astype(str)
        grouped = {
            group: set(values[groups == group].tolist()) for group in sorted(set(groups))
        }
        split_intersections[field] = _pairwise_intersections(grouped)

    target_isolation = {}
    cities = arrays["city_ids"].astype(str)
    position_roles = arrays["position_roles"].astype(str)
    position_ids = arrays["position_ids"].astype(str)
    positions = arrays["positions"]
    for city in sorted(set(cities[groups == "target"])):
        scene_mask = (groups == "target") & (cities == city)
        support_ids = set(position_ids[scene_mask][position_roles[scene_mask] == "support_pool"])
        query_ids = set(position_ids[scene_mask][position_roles[scene_mask] == "query"])
        support_coordinates = {
            tuple(row.tolist())
            for row in positions[scene_mask][position_roles[scene_mask] == "support_pool"]
        }
        query_coordinates = {
            tuple(row.tolist())
            for row in positions[scene_mask][position_roles[scene_mask] == "query"]
        }
        target_isolation[city] = {
            "support_query_id_overlap": len(support_ids & query_ids),
            "support_query_coordinate_overlap": len(
                support_coordinates & query_coordinates
            ),
            "unique_support_ids": len(support_ids),
            "unique_query_ids": len(query_ids),
        }

    phase_values = arrays["phase_reference_values"]
    phase_ids = arrays["phase_reference_ids"].astype(str)
    phase_sources = arrays["phase_reference_source_sha256"].astype(str)
    repeat_seeds = arrays["repeat_seeds"]
    metadata = json.loads(str(arrays["metadata_json"].item()))
    engine_config = json.loads(str(arrays["engine_config_json"].item()))
    finite_arrays = {
        name: bool(np.isfinite(value).all())
        for name, value in arrays.items()
        if np.issubdtype(value.dtype, np.number)
    }
    expected_world_bits = np.asarray(((0, 0), (0, 1), (1, 0), (1, 1)), dtype=np.int64)

    checks = {
        "all_numeric_arrays_finite": all(finite_arrays.values()),
        "shape_34_scenes": clean.shape[0] == 34,
        "shape_4_worlds": clean.shape[1] == 4,
        "shape_256_positions": clean.shape[2] == 256,
        "shape_3_repeats": repeated.shape[3] == 3,
        "world_bits_exact": bool(np.array_equal(arrays["world_bits"], expected_world_bits)),
        "no_path_exactly_equals_zero_csi": bool(np.array_equal(~visible, zero_csi)),
        "path_slots_aligned": paths["id_power_presence_mismatch"] == 0,
        "noop_path_slots_aligned": noop_paths["id_power_presence_mismatch"] == 0,
        "path_surfaces_registered": paths["surface_values_outside_registered_catalog"] == 0,
        "noop_path_surfaces_registered": noop_paths["surface_values_outside_registered_catalog"] == 0,
        "unused_path_surfaces_are_negative": paths[
            "invalid_slot_nonnegative_surface_values"
        ]
        == 0,
        "unused_noop_path_surfaces_are_negative": noop_paths[
            "invalid_slot_nonnegative_surface_values"
        ]
        == 0,
        "path_capacity_not_reached": paths["positions_at_capacity_64"] == 0,
        "noop_path_capacity_not_reached": noop_paths["positions_at_capacity_64"] == 0,
        "phase_reference_has_no_world_or_repeat_axis": phase_values.shape == (34, 256),
        "phase_reference_nonzero": bool(np.all(np.abs(phase_values) > 0)),
        "phase_reference_ids_complete": bool(np.all(phase_ids != "")),
        "phase_reference_source_hashes_complete": bool(
            np.all(np.char.str_len(phase_sources) == 64)
        ),
        "repeat_seeds_globally_unique": np.unique(repeat_seeds).size == repeat_seeds.size,
        "repeat_seeds_three_unique_per_clean_unit": bool(
            np.all(np.apply_along_axis(lambda row: np.unique(row).size, -1, repeat_seeds) == 3)
        ),
        "split_identity_intersections_zero": all(
            count == 0
            for field in split_intersections.values()
            for count in field.values()
        ),
        "target_support_query_intersections_zero": all(
            row["support_query_id_overlap"] == 0
            and row["support_query_coordinate_overlap"] == 0
            for row in target_isolation.values()
        ),
        "registered_active_and_noop_path_arrays_present": True,
        "registered_active_and_noop_map_arrays_present": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema_version": "csi-pairs-m4-final-candidate-diagnostic-audit-v1",
        "status": status,
        "simulation_not_measurement": True,
        "scientific_use": SCIENTIFIC_USE,
        "formal_data_ready": "NO",
        "formal_status": "POST_AUDIT_NO_GO",
        "formal_scientific_use": "FORBIDDEN",
        "dataset": str(dataset.resolve()),
        "dataset_bytes": dataset.stat().st_size,
        "dataset_sha256": _sha256(dataset),
        "npz_field_count": len(arrays),
        "shapes": {
            "csi_clean": list(clean.shape),
            "csi_repeat": list(repeated.shape),
            "paths": list(arrays["path_ids"].shape),
            "path_surfaces": list(arrays["path_surface_ids"].shape),
            "phase_reference_values": list(phase_values.shape),
            "repeat_seeds": list(repeat_seeds.shape),
        },
        "counts": {
            "scene_roles": dict(sorted(Counter(roles.tolist()).items())),
            "cities": dict(sorted(Counter(cities.tolist()).items())),
            "unique_scenes": len(set(arrays["scene_ids"].astype(str))),
            "unique_banks": len(set(arrays["bank_ids"].astype(str))),
            "unique_base_map_clusters": len(
                set(arrays["base_map_cluster_ids"].astype(str))
            ),
            "clean_units": int(np.prod(clean.shape[:-1])),
            "repeat_observations": int(np.prod(repeated.shape[:-1])),
        },
        "checks": checks,
        "finite_numeric_arrays": finite_arrays,
        "path_alignment": {
            "active": paths,
            "noop": noop_paths,
            "no_path_units": int(np.count_nonzero(~visible)),
            "zero_csi_units": int(np.count_nonzero(zero_csi)),
            "no_path_but_nonzero_csi": int(np.count_nonzero((~visible) & (~zero_csi))),
            "visible_but_zero_csi": int(np.count_nonzero(visible & zero_csi)),
            "active_noop_visibility_different_units": int(
                np.count_nonzero(visible != noop_visible)
            ),
            "registered_surface_catalog": sorted(STABLE_SURFACE_IDS),
            "primitive_surface_ids": sorted(
                set(int(value) for value in arrays["primitive_surface_ids"].flat)
            ),
        },
        "phase_reference": {
            "shared_across_worlds_and_repeats_by_shape": list(phase_values.shape),
            "magnitude_min": float(np.abs(phase_values).min()),
            "magnitude_max": float(np.abs(phase_values).max()),
            "empty_id_count": int(np.count_nonzero(phase_ids == "")),
            "invalid_source_hash_length_count": int(
                np.count_nonzero(np.char.str_len(phase_sources) != 64)
            ),
        },
        "repeats": {
            "repeat_count": int(repeated.shape[3]),
            "seed_count": int(repeat_seeds.size),
            "unique_seed_count": int(np.unique(repeat_seeds).size),
            "csi_repeat_all_finite": finite_arrays["csi_repeat"],
        },
        "split_identity_intersections": split_intersections,
        "target_support_query_isolation": target_isolation,
        "metadata_scientific_use": metadata.get("scientific_use"),
        "engine": metadata.get("engine"),
        "assets": metadata.get("assets"),
        "engine_config": engine_config,
        "interpretation": (
            "PASS is structural and diagnostic only; it does not override candidate status, "
            "visibility quality failures, exact-regeneration gates, or formal scientific gates."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to overwrite {output}")
    report = audit(args.dataset.resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="ascii") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"output": str(output), "status": report["status"]}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
