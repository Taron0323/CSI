#!/usr/bin/env python3
"""Run a fixed-seed, strict one-factor Sionna visibility diagnostic."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np

from formal_v2 import sionna_osm_candidate as candidate


CONFIG_SCHEMA = "csi-pairs-sionna-visibility-one-factor-config-v1"
REPORT_SCHEMA = "csi-pairs-sionna-visibility-one-factor-report-v1"
SCIENTIFIC_USE = "DIAGNOSTIC_NOT_FORMAL_EVIDENCE"
FACTOR_NAMES = (
    "receiver_effective_radius_m",
    "bs_xy_offset_m",
    "bs_height_m",
    "max_depth",
    "specular_reflection",
    "refraction",
    "diffraction",
    "stored_path_capacity",
)
ROOT_FIELDS = {
    "schema_version",
    "simulation_not_measurement",
    "scientific_use",
    "scene_index",
    "backend",
    "drjit_threads",
    "solver_seed",
    "receiver_sampling",
    "fixed_solver_settings",
    "baseline",
    "variants",
}
FIXED_SOLVER_SETTINGS = {
    "los": True,
    "diffuse_reflection": False,
    "edge_diffraction": False,
    "synthetic_array": True,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode("ascii"))
    digest.update(json.dumps(array.shape, separators=(",", ":")).encode("ascii"))
    digest.update(array.tobytes())
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=candidate._reject_json_constant)


def _exact_fields(value: Any, expected: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ValueError(f"{label} fields must be exact: expected={sorted(expected)}, actual={actual}")
    return value


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, list) or isinstance(right, list):
        return isinstance(left, list) and isinstance(right, list) and left == right
    return type(left) is type(right) and left == right


def load_diagnostic_config(path: str | Path) -> dict:
    config_path = Path(path).resolve()
    config = _exact_fields(_read_json(config_path), ROOT_FIELDS, "diagnostic config")
    if config["schema_version"] != CONFIG_SCHEMA:
        raise ValueError("diagnostic config schema mismatch")
    if config["simulation_not_measurement"] is not True:
        raise ValueError("diagnostic config must state simulation_not_measurement=true")
    if config["scientific_use"] != SCIENTIFIC_USE:
        raise ValueError(f"diagnostic config scientific_use must be {SCIENTIFIC_USE}")
    if type(config["scene_index"]) is not int or config["scene_index"] != 27:
        raise ValueError("this bounded diagnostic is registered only for scene_index=27")
    if (
        config["backend"] != "llvm"
        or type(config["drjit_threads"]) is not int
        or config["drjit_threads"] != 1
    ):
        raise ValueError("this local diagnostic requires LLVM with one Dr.Jit thread")
    if type(config["solver_seed"]) is not int or config["solver_seed"] < 0:
        raise ValueError("solver_seed must be a nonnegative integer")
    sampling = _exact_fields(
        config["receiver_sampling"], {"method", "position_count"}, "receiver_sampling"
    )
    if (
        sampling.get("method") != "frozen_candidate_grid_with_optional_radial_filter"
        or type(sampling.get("position_count")) is not int
        or sampling["position_count"] != 256
    ):
        raise ValueError("receiver_sampling protocol differs from the registered diagnostic")
    fixed = _exact_fields(
        config["fixed_solver_settings"], set(FIXED_SOLVER_SETTINGS), "fixed_solver_settings"
    )
    if any(fixed[name] is not expected for name, expected in FIXED_SOLVER_SETTINGS.items()):
        raise ValueError("fixed_solver_settings differ from the registered diagnostic")
    baseline = _exact_fields(config["baseline"], set(FACTOR_NAMES), "baseline")
    if baseline["receiver_effective_radius_m"] is not None:
        raise ValueError("baseline must use the frozen candidate receiver positions")
    _validate_xy(baseline["bs_xy_offset_m"], "baseline bs_xy_offset_m")
    if baseline["bs_xy_offset_m"] != [0.0, 0.0]:
        raise ValueError("baseline BS XY offset must be the frozen [0, 0]")
    _validate_positive_float(baseline["bs_height_m"], "baseline bs_height_m")
    _validate_positive_int(baseline["max_depth"], "baseline max_depth")
    _validate_bool(baseline["specular_reflection"], "baseline specular_reflection")
    _validate_bool(baseline["refraction"], "baseline refraction")
    _validate_bool(baseline["diffraction"], "baseline diffraction")
    _validate_positive_int(baseline["stored_path_capacity"], "baseline stored_path_capacity")
    variants = config["variants"]
    if not isinstance(variants, list) or len(variants) != len(FACTOR_NAMES):
        raise ValueError("variants must contain exactly one entry for every registered factor")
    seen_names: set[str] = set()
    seen_factors: set[str] = set()
    for index, variant in enumerate(variants):
        row = _exact_fields(variant, {"name", "single_change"}, f"variants[{index}]")
        name = row["name"]
        if not isinstance(name, str) or not name or name in seen_names:
            raise ValueError("variant names must be unique nonempty strings")
        seen_names.add(name)
        change = _exact_fields(
            row["single_change"], {"factor", "from", "to"}, f"variants[{index}].single_change"
        )
        factor = change["factor"]
        if factor not in FACTOR_NAMES or factor in seen_factors:
            raise ValueError("each registered factor must appear in exactly one variant")
        seen_factors.add(factor)
        if not _same_value(change["from"], baseline[factor]):
            raise ValueError(f"variant {name} does not bind from to the baseline value")
        if _same_value(change["to"], baseline[factor]):
            raise ValueError(f"variant {name} does not change factor {factor}")
        _validate_factor_value(factor, change["to"])
    if seen_factors != set(FACTOR_NAMES):
        raise ValueError("variant factor coverage is incomplete")
    return config


def _validate_bool(value: Any, label: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"{label} must be boolean")


def _validate_positive_int(value: Any, label: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")


def _validate_positive_float(value: Any, label: str) -> None:
    if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive finite number")


def _validate_xy(value: Any, label: str) -> None:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must contain exactly two coordinates")
    for coordinate in value:
        if type(coordinate) not in (int, float) or isinstance(coordinate, bool) or not math.isfinite(coordinate):
            raise ValueError(f"{label} coordinates must be finite numbers")


def _validate_factor_value(factor: str, value: Any) -> None:
    if factor == "receiver_effective_radius_m":
        _validate_positive_float(value, factor)
    elif factor == "bs_xy_offset_m":
        _validate_xy(value, factor)
    elif factor == "bs_height_m":
        _validate_positive_float(value, factor)
    elif factor in ("max_depth", "stored_path_capacity"):
        _validate_positive_int(value, factor)
    elif factor in ("specular_reflection", "refraction", "diffraction"):
        _validate_bool(value, factor)
    else:
        raise ValueError(f"unknown diagnostic factor: {factor}")


def condition_rows(config: dict) -> list[dict]:
    baseline = dict(config["baseline"])
    rows = [{"name": "baseline_registered", "single_change": None, "factors": baseline}]
    for variant in config["variants"]:
        change = variant["single_change"]
        factors = dict(baseline)
        factors[change["factor"]] = change["to"]
        changed = [name for name in FACTOR_NAMES if not _same_value(factors[name], baseline[name])]
        if changed != [change["factor"]]:
            raise RuntimeError(f"variant {variant['name']} is not a strict one-factor change")
        rows.append(
            {
                "name": variant["name"],
                "single_change": dict(change),
                "factors": factors,
            }
        )
    return rows


def _load_asset_bundle(asset_root: Path) -> tuple[Path, dict, dict, dict, Path, Path]:
    root = asset_root.resolve()
    formal_path = root / "asset_manifest.json"
    diagnostic_path = root / "diagnostic_asset_manifest.json"
    available = [path for path in (formal_path, diagnostic_path) if path.is_file()]
    if len(available) != 1:
        raise ValueError("asset root must contain exactly one formal or diagnostic asset manifest")
    manifest_path = available[0]
    if manifest_path == formal_path:
        root, manifest, frozen_config = candidate.load_asset_manifest(root)
        source_kind = "formal_asset_manifest_read_only"
    else:
        from formal_v2.sionna_scene0_diagnostic_assets import (
            load_diagnostic_asset_manifest,
        )

        root, manifest, frozen_config = load_diagnostic_asset_manifest(root)
        source_kind = "single_bank_diagnostic_asset_manifest"
    banks = manifest.get("banks")
    if not isinstance(banks, list) or not banks:
        raise ValueError("asset manifest contains no bank records")
    return root, manifest, frozen_config, {"kind": source_kind}, manifest_path, available[0]


def _validate_transmitter_clearance(bank: dict, factors: dict) -> float:
    from shapely.geometry import Point, Polygon

    offset = factors["bs_xy_offset_m"]
    point = Point(float(offset[0]), float(offset[1]))
    polygons = [Polygon(row["local_exterior_xy_m"]) for row in bank["buildings"]]
    clearance = min(float(polygon.distance(point)) for polygon in polygons)
    if clearance < 4.0:
        raise ValueError(
            f"diagnostic BS XY {offset} has only {clearance:.6f} m building clearance; "
            "the frozen four-meter clearance rule still applies"
        )
    return clearance


def _select_bank(root: Path, manifest: dict, scene_index: int) -> tuple[dict, dict, Path, Path]:
    matches = [row for row in manifest["banks"] if row.get("scene_index") == scene_index]
    if len(matches) != 1:
        raise ValueError("requested scene_index is absent or duplicated in the asset manifest")
    row = matches[0]
    required = {"scene_index", "scene_id", "city_id", "bank_record_path", "scene_xml_path"}
    if not isinstance(row, dict) or not required.issubset(row):
        raise ValueError("asset bank row is missing required identity or path fields")
    bank_path = root / str(row["bank_record_path"])
    scene_path = root / str(row["scene_xml_path"])
    for label, path in (("bank record", bank_path), ("scene XML", scene_path)):
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError(f"{label} is missing or escapes the asset root")
    if row.get("bank_record_sha256") is not None and _sha256(bank_path) != row["bank_record_sha256"]:
        raise ValueError("bank record hash mismatch")
    if row.get("scene_xml_sha256") is not None and _sha256(scene_path) != row["scene_xml_sha256"]:
        raise ValueError("scene XML hash mismatch")
    bank = candidate._read_json(bank_path)
    if bank.get("scene_id") != row["scene_id"]:
        raise ValueError("bank record scene identity mismatch")
    return row, bank, bank_path, scene_path


def _receiver_positions_with_radius(
    bank: dict, frozen_config: dict, scene_index: int, radius_m: float | None
) -> np.ndarray:
    if radius_m is None:
        return candidate._receiver_positions(bank, frozen_config, scene_index)
    from shapely.geometry import Point, Polygon

    count = int(frozen_config["positions_per_bank"])
    polygons = [Polygon(row["local_exterior_xy_m"]) for row in bank["buildings"]]
    primitive_ids = [int(value) for value in bank["primitive_osm_ids"]]
    by_id = {
        int(row["osm_id"]): Polygon(row["local_exterior_xy_m"])
        for row in bank["buildings"]
    }
    primitives = [by_id[value] for value in primitive_ids]
    offset_x = ((scene_index % 17) - 8) * 0.013
    offset_y = (((scene_index * 7) % 19) - 9) * 0.011
    values = np.linspace(-116.0, 116.0, 31)
    candidates = []
    for y in values + offset_y:
        for x in values + offset_x:
            point = Point(float(x), float(y))
            if float(point.distance(Point(0.0, 0.0))) > radius_m:
                continue
            if all(float(polygon.distance(point)) >= 2.0 for polygon in polygons):
                candidates.append((float(x), float(y)))
    if len(candidates) < count:
        raise RuntimeError(
            f"effective radius {radius_m:g} m leaves only {len(candidates)} receiver-clear "
            f"grid points; {count} are required"
        )
    remaining = list(range(len(candidates)))
    selected: list[int] = []
    for primitive in primitives:
        ranked = sorted(
            remaining,
            key=lambda index: (
                primitive.distance(Point(*candidates[index])),
                candidates[index][0],
                candidates[index][1],
            ),
        )
        take = ranked[: min(64, count - len(selected))]
        selected.extend(take)
        used = set(take)
        remaining = [index for index in remaining if index not in used]
    rng = np.random.default_rng(int(frozen_config["seed"]) + scene_index * 1009)
    remainder = np.asarray(remaining, dtype=np.int64)
    rng.shuffle(remainder)
    selected.extend(int(value) for value in remainder[: count - len(selected)])
    output = np.asarray([candidates[index] for index in selected], dtype=np.float64)
    order = np.arange(count)
    rng.shuffle(order)
    output = output[order]
    if output.shape != (count, 2) or np.any(np.linalg.norm(output, axis=1) > radius_m):
        raise RuntimeError("receiver effective-radius sampling invariant failed")
    return output


def _path_counts(paths: Any, position_count: int) -> np.ndarray:
    valid = np.asarray(paths.valid)
    if valid.ndim != 3 or valid.shape[:2] != (position_count, 1):
        raise RuntimeError(f"unexpected Sionna valid-path shape: {valid.shape}")
    return np.count_nonzero(valid[:, 0], axis=-1).astype(np.int64, copy=False)


def _distribution(counts: np.ndarray) -> dict:
    values, frequencies = np.unique(counts, return_counts=True)
    return {
        "histogram": [
            {"path_count": int(value), "positions": int(frequency)}
            for value, frequency in zip(values, frequencies)
        ],
        "min": int(np.min(counts)),
        "median": float(np.median(counts)),
        "p90": float(np.quantile(counts, 0.9)),
        "max": int(np.max(counts)),
        "mean": float(np.mean(counts)),
    }


def _condition_metrics(raw_counts: np.ndarray, capacity: int) -> dict:
    started = time.monotonic()
    stored_counts = np.minimum(raw_counts, capacity)
    raw_total = int(np.sum(raw_counts))
    retained_total = int(np.sum(stored_counts))
    visible = raw_counts > 0
    no_path_positions = int(np.count_nonzero(~visible))
    truncated_positions = int(np.count_nonzero(raw_counts > capacity))
    capacity_reached = int(np.count_nonzero(raw_counts >= capacity))
    return {
        "positions": int(raw_counts.size),
        "visible_positions": int(np.count_nonzero(visible)),
        "no_path_positions": no_path_positions,
        "no_path_rate": float(no_path_positions / raw_counts.size),
        "path_count_distribution": {
            "raw_solver_paths": _distribution(raw_counts),
            "stored_after_capacity_projection": _distribution(stored_counts),
        },
        "stored_path_capacity": capacity,
        "capacity_diagnostics": {
            "classification": "STORAGE_PROJECTION_ONLY_NOT_PHYSICAL_VISIBILITY",
            "raw_path_total": raw_total,
            "retained_path_total": retained_total,
            "truncated_path_total": raw_total - retained_total,
            "truncated_positions": truncated_positions,
            "truncated_position_rate": float(truncated_positions / raw_counts.size),
            "capacity_reached_positions": capacity_reached,
            "capacity_reached_rate": float(capacity_reached / raw_counts.size),
            "saturated_positions": capacity_reached,
            "saturation_rate": float(capacity_reached / raw_counts.size),
            "saturation_definition": "raw_solver_path_count_greater_than_or_equal_to_capacity",
            "capacity_exceeded_positions": truncated_positions,
            "capacity_exceeded_rate": float(truncated_positions / raw_counts.size),
            "physical_visibility_changed_by_storage_projection": False,
        },
        "metric_projection_seconds": time.monotonic() - started,
    }


def _build_and_trace(
    root: Path,
    bank_row: dict,
    bank: dict,
    frozen_config: dict,
    scene_index: int,
    factors: dict,
    fixed: dict,
    solver_seed: int,
) -> tuple[np.ndarray, np.ndarray, dict]:
    from sionna.rt import (
        ITURadioMaterial,
        PathSolver,
        PlanarArray,
        Receiver,
        Transmitter,
        load_scene,
    )

    started = time.monotonic()
    radio = frozen_config["radio"]
    transmitter_clearance = _validate_transmitter_clearance(bank, factors)
    positions = _receiver_positions_with_radius(
        bank, frozen_config, scene_index, factors["receiver_effective_radius_m"]
    )
    scene = load_scene(root / str(bank_row["scene_xml_path"]))
    if set(scene.objects) != set(candidate.STABLE_SURFACE_IDS):
        raise RuntimeError("diagnostic scene object catalog differs from the frozen candidate")
    for material_type in ("glass", "metal"):
        name = f"itu_{material_type}"
        if name not in scene.radio_materials:
            scene.add(
                ITURadioMaterial(
                    name=name,
                    itu_type=material_type,
                    thickness=candidate.SIONNA_MATERIAL_THICKNESS_M,
                )
            )
    scene.frequency = float(radio["carrier_frequency_hz"])
    scene.bandwidth = float(radio["subcarrier_spacing_hz"]) * int(radio["subcarriers"])
    scene.tx_array = PlanarArray(
        num_rows=1,
        num_cols=int(radio["tx_antennas"]),
        vertical_spacing=0.5,
        horizontal_spacing=0.5,
        pattern="iso",
        polarization="V",
    )
    scene.rx_array = PlanarArray(
        num_rows=1,
        num_cols=1,
        vertical_spacing=0.5,
        horizontal_spacing=0.5,
        pattern="iso",
        polarization="V",
    )
    offset = factors["bs_xy_offset_m"]
    scene.add(
        Transmitter(
            "tx",
            position=[float(offset[0]), float(offset[1]), float(factors["bs_height_m"])],
        )
    )
    for position_index, xy in enumerate(positions):
        scene.add(
            Receiver(
                f"rx-{position_index}",
                position=[float(xy[0]), float(xy[1]), float(radio["receiver_z_m"])],
            )
        )
    worlds = np.asarray(frozen_config["world_bits"], dtype=np.int64)
    natural_world = int(candidate._natural_world_index(scene_index, worlds))
    candidate._set_world_materials(
        scene,
        candidate._physical_states(
            worlds[natural_world], candidate._primitive_mapping(scene_index)
        ),
    )
    setup_seconds = time.monotonic() - started
    solver_started = time.monotonic()
    paths = PathSolver()(
        scene,
        max_depth=int(factors["max_depth"]),
        los=bool(fixed["los"]),
        specular_reflection=bool(factors["specular_reflection"]),
        diffuse_reflection=bool(fixed["diffuse_reflection"]),
        refraction=bool(factors["refraction"]),
        diffraction=bool(factors["diffraction"]),
        edge_diffraction=bool(fixed["edge_diffraction"]),
        synthetic_array=bool(fixed["synthetic_array"]),
        seed=solver_seed,
    )
    solver_seconds = time.monotonic() - solver_started
    counts = _path_counts(paths, positions.shape[0])
    return counts, positions, {
        "scene_setup_seconds": setup_seconds,
        "solver_seconds": solver_seconds,
        "total_seconds": time.monotonic() - started,
        "solver_invoked": True,
        "transmitter_building_clearance_m": transmitter_clearance,
    }


def _validate_against_frozen(config: dict, frozen_config: dict) -> None:
    radio = frozen_config["radio"]
    baseline = config["baseline"]
    expected_seed = (
        int(frozen_config["seed"])
        + int(config["scene_index"]) * 1000
        + int(
            candidate._natural_world_index(
                int(config["scene_index"]), np.asarray(frozen_config["world_bits"], dtype=np.int64)
            )
        )
    )
    if config["solver_seed"] != expected_seed:
        raise ValueError("diagnostic solver_seed differs from the frozen natural-world seed")
    expected = {
        "receiver_effective_radius_m": None,
        "bs_xy_offset_m": [0.0, 0.0],
        "bs_height_m": float(radio["transmitter_z_m"]),
        "max_depth": int(radio["max_depth"]),
        "specular_reflection": True,
        "refraction": False,
        "diffraction": False,
        "stored_path_capacity": int(radio["max_stored_paths"]),
    }
    if baseline != expected:
        raise ValueError("diagnostic baseline differs from the frozen propagation protocol")
    if int(config["receiver_sampling"]["position_count"]) != int(
        frozen_config["positions_per_bank"]
    ):
        raise ValueError("diagnostic receiver count differs from the frozen candidate")


def diagnose(asset_root: Path, config_path: Path) -> dict:
    config = load_diagnostic_config(config_path)
    root, manifest, frozen_config, asset_source, manifest_path, _ = _load_asset_bundle(asset_root)
    scene_index = int(config["scene_index"])
    bank_row, bank, bank_path, scene_path = _select_bank(root, manifest, scene_index)
    _validate_against_frozen(config, frozen_config)
    rows = condition_rows(config)
    baseline_counts: np.ndarray | None = None
    baseline_visible: np.ndarray | None = None
    baseline_positions_hash: str | None = None
    results = []
    for row in rows:
        change = row["single_change"]
        factor = None if change is None else str(change["factor"])
        if factor == "stored_path_capacity":
            if baseline_counts is None or baseline_visible is None or baseline_positions_hash is None:
                raise RuntimeError("capacity projection requires the completed baseline trace")
            projection_started = time.monotonic()
            raw_counts = baseline_counts.copy()
            positions_hash = baseline_positions_hash
            timing = {
                "scene_setup_seconds": 0.0,
                "solver_seconds": 0.0,
                "total_seconds": time.monotonic() - projection_started,
                "solver_invoked": False,
                "transmitter_building_clearance_m": _validate_transmitter_clearance(
                    bank, row["factors"]
                ),
            }
            trace_source = "baseline_raw_path_counts_reused_exactly"
        else:
            raw_counts, positions, timing = _build_and_trace(
                root,
                bank_row,
                bank,
                frozen_config,
                scene_index,
                row["factors"],
                config["fixed_solver_settings"],
                int(config["solver_seed"]),
            )
            positions_hash = _array_sha256(positions)
            trace_source = "independent_solver_invocation_same_registered_seed"
        visible = raw_counts > 0
        metrics = _condition_metrics(raw_counts, int(row["factors"]["stored_path_capacity"]))
        timing["trace_total_seconds"] = timing.pop("total_seconds")
        timing["metric_projection_seconds"] = metrics["metric_projection_seconds"]
        timing["total_seconds"] = (
            timing["trace_total_seconds"] + timing["metric_projection_seconds"]
        )
        if baseline_counts is None:
            baseline_counts = raw_counts.copy()
            baseline_visible = visible.copy()
            baseline_positions_hash = positions_hash
        assert baseline_visible is not None
        if factor != "receiver_effective_radius_m" and positions_hash != baseline_positions_hash:
            raise RuntimeError(f"condition {row['name']} changed receiver positions unexpectedly")
        positions_changed = positions_hash != baseline_positions_hash
        if factor == "receiver_effective_radius_m":
            newly_visible = None
            lost_visible = None
        else:
            newly_visible = int(np.count_nonzero(visible & (~baseline_visible)))
            lost_visible = int(np.count_nonzero((~visible) & baseline_visible))
        result = {
            "name": row["name"],
            "single_change": change,
            "factors": row["factors"],
            "solver_seed": int(config["solver_seed"]),
            "trace_source": trace_source,
            "receiver_positions_sha256": positions_hash,
            "receiver_set_relation_to_baseline": (
                "CHANGED_BY_REGISTERED_RECEIVER_SAMPLING_FACTOR"
                if positions_changed
                else "EXACT_SHA256_MATCH"
            ),
            "visible_positions": metrics["visible_positions"],
            "no_path_positions": metrics["no_path_positions"],
            "no_path_rate": metrics["no_path_rate"],
            "path_count_distribution": metrics["path_count_distribution"],
            "capacity_diagnostics": metrics["capacity_diagnostics"],
            "runtime": timing,
            "newly_visible_vs_baseline": newly_visible,
            "lost_visibility_vs_baseline": lost_visible,
        }
        if factor == "receiver_effective_radius_m":
            result["visibility_interpretation"] = (
                "AGGREGATE_ONLY; receiver positions changed, so positionwise newly-visible "
                "and lost-visibility counts are not comparable"
            )
        elif factor == "stored_path_capacity":
            if newly_visible or lost_visible or not np.array_equal(raw_counts, baseline_counts):
                raise RuntimeError("storage-only capacity projection altered physical visibility")
            result["visibility_interpretation"] = (
                "NOT_APPLICABLE_STORAGE_ONLY; raw physical trace is the baseline trace"
            )
        else:
            result["visibility_interpretation"] = (
                "SIMULATION_DIAGNOSTIC_COMPARISON_NOT_FORMAL_SCIENTIFIC_EVIDENCE"
            )
        results.append(result)
        print(
            json.dumps(
                {
                    "condition": row["name"],
                    "visible_positions": result["visible_positions"],
                    "no_path_rate": result["no_path_rate"],
                    "runtime_seconds": result["runtime"]["total_seconds"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
    return {
        "schema_version": REPORT_SCHEMA,
        "status": "DIAGNOSTIC_COMPLETE",
        "simulation_not_measurement": True,
        "scientific_use": SCIENTIFIC_USE,
        "formal_data_ready": "NO",
        "formal_status": "POST_AUDIT_NO_GO",
        "formal_scientific_use": "FORBIDDEN",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "backend": config["backend"],
        "drjit_threads": int(config["drjit_threads"]),
        "same_solver_seed_for_all_physical_conditions": int(config["solver_seed"]),
        "runtime": candidate._sionna_runtime_record(backend=str(config["backend"])),
        "asset_source": asset_source,
        "asset_root": str(root),
        "asset_manifest_path": str(manifest_path),
        "asset_manifest_sha256": _sha256(manifest_path),
        "bank_record_path": str(bank_path),
        "bank_record_sha256": _sha256(bank_path),
        "scene_xml_path": str(scene_path),
        "scene_xml_sha256": _sha256(scene_path),
        "scene_index": scene_index,
        "scene_id": bank_row["scene_id"],
        "city_id": bank_row["city_id"],
        "diagnostic_config_path": str(config_path.resolve()),
        "diagnostic_config_sha256": _sha256(config_path.resolve()),
        "tool_path": str(Path(__file__).resolve()),
        "tool_sha256": _sha256(Path(__file__).resolve()),
        "conditions": results,
    }


def _local_sim_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "CSI_M4_LOCAL_SIM":
            return parent
    raise RuntimeError("diagnostic tool is not running from CSI_M4_LOCAL_SIM")


def _checked_output(path: Path) -> Path:
    output = path.resolve()
    local_root = _local_sim_root()
    if not output.is_relative_to(local_root):
        raise ValueError(f"diagnostic output must remain under {local_root}")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to overwrite diagnostic output {output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = load_diagnostic_config(args.config)
    output = _checked_output(args.output)
    candidate.ensure_sionna_runtime(
        [__file__, *sys.argv[1:]], backend=str(config["backend"])
    )
    import mitsuba as mi

    mi.set_variant(f"{config['backend']}_ad_mono_polarized")
    import drjit as dr

    dr.set_thread_count(int(config["drjit_threads"]))
    report = diagnose(args.asset_root, args.config)
    output.parent.mkdir(parents=True, exist_ok=True)
    candidate._write_json_exclusive(output, report)
    print(json.dumps({"output": str(output), "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
