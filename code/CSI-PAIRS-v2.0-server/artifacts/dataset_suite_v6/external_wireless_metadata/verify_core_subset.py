#!/usr/bin/env python3
"""Audit the selected wireless core datasets and the 60 GB hard limit."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HARD_LIMIT_BYTES = 60_000_000_000


def tree_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def zip_ok(
    path: Path, deep: bool, expected_size: int | None = None
) -> tuple[bool, str]:
    if not path.is_file():
        return False, "missing"
    actual_size = path.stat().st_size
    if expected_size is not None and actual_size != expected_size:
        return False, f"size mismatch: {actual_size:,} != {expected_size:,} bytes"
    try:
        with zipfile.ZipFile(path) as archive:
            if deep:
                bad_member = archive.testzip()
                if bad_member:
                    return False, f"CRC failure: {bad_member}"
            elif not archive.namelist():
                return False, "empty ZIP"
    except zipfile.BadZipFile:
        return False, "invalid ZIP"
    return True, f"{actual_size:,} bytes"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--deep",
        action="store_true",
        help="read every compressed member to verify CRC (can take several minutes)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    total = tree_size(ROOT)
    checks: dict[str, dict[str, object]] = {}

    deepmimo_targets = [
        ROOT / "DeepMIMO/deepmimo_scenarios/asu_campus_3p5_downloaded.zip",
        ROOT / "DeepMIMO/all_scenario_zips/i1_2p5.zip",
    ]
    deepmimo_expected_sizes = [30_558_838, 2_445_139_772]
    deepmimo_results = [
        zip_ok(path, args.deep, expected_size)
        for path, expected_size in zip(
            deepmimo_targets, deepmimo_expected_sizes, strict=True
        )
    ]
    deepmimo_complete = all(ok for ok, _ in deepmimo_results)
    checks["DeepMIMO"] = {
        "complete": deepmimo_complete,
        "core_complete": deepmimo_complete,
        "original_source_acquired": deepmimo_complete,
        "public_substitute_complete": None,
        "items": {
            path.name: detail
            for path, (_, detail) in zip(deepmimo_targets, deepmimo_results, strict=True)
        },
    }

    urban_dir = ROOT / "UrbanMIMOMap/channelMatrix/resu_npz_map_0"
    urban_files = sorted(urban_dir.glob("*.npz"))
    urban_expected = {
        f"0_{receiver}_{angle}.npz"
        for receiver in range(40)
        for angle in (0, 60, 120)
    }
    urban_actual = {path.name for path in urban_files}
    urban_bad: list[str] = []
    for path in urban_files:
        try:
            with zipfile.ZipFile(path) as archive:
                if args.deep and archive.testzip():
                    urban_bad.append(path.name)
                elif not {"coords.npy", "matrices.npy"}.issubset(archive.namelist()):
                    urban_bad.append(path.name)
        except zipfile.BadZipFile:
            urban_bad.append(path.name)
    urban_complete = urban_actual == urban_expected and not urban_bad
    checks["UrbanMIMOMap"] = {
        "complete": urban_complete,
        "core_complete": urban_complete,
        "original_source_acquired": urban_complete,
        "public_substitute_complete": None,
        "npz_count": len(urban_files),
        "missing_npz": sorted(urban_expected - urban_actual),
        "unexpected_npz": sorted(urban_actual - urban_expected),
        "bad_npz": urban_bad,
    }

    radio_public_targets = [
        ROOT / "RadioMapSeer/RadioMapSeer.zip",
        ROOT / "RadioMapSeer/RadioLocSeer.zip",
        ROOT / "RadioMapSeer/RadioToASeer.zip",
        ROOT / "RadioMapSeer/RadioMap3DSeer.zip",
    ]
    radio_public_results = [zip_ok(path, args.deep) for path in radio_public_targets]
    irt2_path = ROOT / "RadioMapSeer/IRT2HighRes.zip"
    irt2_result = zip_ok(irt2_path, args.deep)
    radio_items = {
        path.name: detail
        for path, (_, detail) in zip(
            radio_public_targets, radio_public_results, strict=True
        )
    }
    radio_items[irt2_path.name] = irt2_result[1]
    radio_base_complete = all(ok for ok, _ in radio_public_results[:3])
    radio_3d_complete = radio_public_results[3][0]
    radio_core_complete = radio_base_complete and (
        irt2_result[0] or radio_3d_complete
    )
    checks["RadioMapSeer"] = {
        "complete": radio_core_complete,
        "core_complete": radio_core_complete,
        "original_source_acquired": irt2_result[0],
        "public_substitute_complete": radio_3d_complete,
        "items": radio_items,
        "note": (
            "RadioMap3DSeer is the public geometric substitute for paid "
            "IRT2HighRes; it is not the IRT2 archive."
        ),
    }

    wwm_core = ROOT / "WWM/core"
    test_candidates = list(wwm_core.glob("*test_gen_city*.zip"))
    point_candidates = [
        path
        for path in wwm_core.glob("*.zip")
        if "point" in path.name.lower() or "3d" in path.name.lower()
    ]
    test_results = [zip_ok(path, args.deep) for path in test_candidates]
    point_results = [zip_ok(path, args.deep) for path in point_candidates]
    wwm_original_complete = any(ok for ok, _ in test_results) and any(
        ok for ok, _ in point_results
    )
    deepsense_targets = [
        ROOT / "WWM/alternatives/DeepSense6G/scenario8.zip",
        ROOT / "WWM/alternatives/DeepSense6G/scenario33.zip",
    ]
    deepsense_expected_sizes = [910_993_649, 5_162_587_957]
    deepsense_results = [
        zip_ok(path, args.deep, expected_size)
        for path, expected_size in zip(
            deepsense_targets, deepsense_expected_sizes, strict=True
        )
    ]
    deepsense_complete = all(ok for ok, _ in deepsense_results)
    checks["WWM"] = {
        "complete": wwm_original_complete or deepsense_complete,
        "core_complete": wwm_original_complete or deepsense_complete,
        "original_source_acquired": wwm_original_complete,
        "public_substitute_complete": deepsense_complete,
        "test_gen_city_candidates": [path.name for path in test_candidates],
        "point_cloud_candidates": [path.name for path in point_candidates],
        "substitute_items": {
            path.name: detail
            for path, (_, detail) in zip(
                deepsense_targets, deepsense_results, strict=True
            )
        },
        "note": (
            "Restricted WWM metadata is not data. DeepSense Scenarios 8 and "
            "33 are a public multimodal substitute, not original WWM files."
        ),
    }

    training_core_complete = all(
        bool(result["core_complete"]) for result in checks.values()
    )
    all_original_sources_complete = all(
        bool(result["original_source_acquired"]) for result in checks.values()
    )
    report = {
        "root": str(ROOT),
        "total_apparent_bytes": total,
        "hard_limit_bytes": HARD_LIMIT_BYTES,
        "under_hard_limit": total < HARD_LIMIT_BYTES,
        "training_core_complete": training_core_complete,
        "all_original_sources_complete": all_original_sources_complete,
        "all_sources_complete": all_original_sources_complete,
        "public_substitutions_used": not all_original_sources_complete,
        "checks": checks,
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Directory: {total:,}/{HARD_LIMIT_BYTES:,} bytes")
        for name, result in checks.items():
            state = "COMPLETE" if result["core_complete"] else "INCOMPLETE"
            print(f"{name}: {state}")
            for key, value in result.items():
                if key not in {"complete", "core_complete"}:
                    print(f"  {key}: {value}")
    return 0 if report["under_hard_limit"] and training_core_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
