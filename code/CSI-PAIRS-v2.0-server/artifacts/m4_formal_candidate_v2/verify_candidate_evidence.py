#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import csv
from decimal import Decimal
import gc
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


EVIDENCE_ROOT = Path(__file__).resolve().parent
SERVER_ROOT = EVIDENCE_ROOT.parents[1]
EVIDENCE_PATH = EVIDENCE_ROOT / "candidate_evidence.json"
SCENE_PATH = EVIDENCE_ROOT / "scene_inventory.csv"
SHARD_PATH = EVIDENCE_ROOT / "shard_inventory.csv"
CHECKSUM_PATH = EVIDENCE_ROOT / "SHA256SUMS"
APPROVED_LLVM_PATH = SERVER_ROOT / "formal_v2/configs/sionna_llvm_approved_v1.json"

REQUIRED_FILES = {
    "EXECUTION_PROMPT.md",
    "README.md",
    "REPORT.md",
    "SHA256SUMS",
    "candidate_evidence.json",
    "scene_inventory.csv",
    "shard_inventory.csv",
    "verify_candidate_evidence.py",
}
EXPECTED_READINESS = {
    "M4_DATA_PRODUCTION_READY": "REPORTED",
    "EVIDENCE_REGISTRY_READY": "YES",
    "FORMAL_CANDIDATE_READY": "BLOCKED_NOT_PREAPPROVED_AT_GENERATION",
    "FORMAL_INPUT_READY": "BLOCKED",
    "FORMAL_TRAINING_READY": "NO",
    "LAUNCH_READY": "BLOCKED",
    "SCIENTIFIC_EVIDENCE": "NOT_ASSESSED",
}
EXPECTED_CONDITIONAL_ISSUES = {
    "DATA-VISIBILITY-001",
    "DATA-REGEN-001",
    "PATH-ID-001",
    "INPUT-DATA-001",
}
SCENE_FIELDS = [
    "scene_index",
    "scene_id",
    "bank_id",
    "city_id",
    "role",
    "bank_index_within_city",
    "base_map_cluster_id",
    "canonical_base_map_sha256",
    "scene_xml_sha256",
    "bank_record_sha256",
    "verification_status",
]
SHARD_FIELDS = [
    "shard_index",
    "scene_start_inclusive",
    "scene_end_exclusive",
    "scene_count",
    "npz_sha256",
    "npz_bytes",
    "manifest_sha256",
    "manifest_bytes",
    "duration_seconds",
    "status",
]
PER_SCENE_BOOLEAN_FIELDS = [
    "maps_match",
    "canonical_foundation_identity_match",
    "csi_clean_match",
    "csi_repeat_match",
    "observation_noise_seed_binding_match",
    "free_space_match",
    "phase_reference_ids_match",
    "phase_reference_values_match",
    "phase_reference_source_sha256_match",
    "noop_maps_match",
    "path_ids_match",
    "path_power_match",
    "path_surface_ids_match",
    "noop_path_ids_match",
    "noop_path_power_match",
    "noop_path_surface_ids_match",
    "passed",
]
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
CHECKSUM_LINE_PATTERN = re.compile(r"([0-9a-f]{64})  (\./[^\n]+)")
EMAIL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
FORBIDDEN_IDENTITY_MARKERS = (
    "/" + "Users" + "/",
    "\\" + "Users" + "\\",
    "futa" + "oran",
    "wx" + "id_",
    "Taron" + "0323",
)


class EvidenceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise EvidenceError(f"non-finite JSON value is forbidden: {value}")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=strict_object,
        parse_constant=reject_constant,
    )
    require(isinstance(value, dict), f"{path.name} must contain a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_sha256(value: object, label: str) -> str:
    require(
        isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None,
        f"{label} must be a lowercase SHA-256",
    )
    return value


def read_csv(path: Path, expected_fields: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == expected_fields, f"{path.name} header mismatch")
        rows = list(reader)
    require(all(None not in row for row in rows), f"{path.name} has extra columns")
    return rows


def verify_repository_checksums() -> None:
    require(CHECKSUM_PATH.is_file() and not CHECKSUM_PATH.is_symlink(), "missing SHA256SUMS")
    listed: dict[str, str] = {}
    for line in CHECKSUM_PATH.read_text(encoding="utf-8").splitlines():
        match = CHECKSUM_LINE_PATTERN.fullmatch(line)
        require(match is not None, f"invalid SHA256SUMS line: {line!r}")
        digest, listed_path = match.groups()
        relative = listed_path[2:]
        require(relative not in listed, f"duplicate SHA256SUMS path: {relative}")
        require(".." not in Path(relative).parts, f"unsafe SHA256SUMS path: {relative}")
        listed[relative] = digest

    actual: dict[str, Path] = {}
    for path in EVIDENCE_ROOT.rglob("*"):
        require(not path.is_symlink(), f"evidence tree contains symlink: {path.name}")
        if path.is_file() and path != CHECKSUM_PATH:
            actual[path.relative_to(EVIDENCE_ROOT).as_posix()] = path
    require(set(listed) == set(actual), "SHA256SUMS inventory does not match evidence files")
    for relative, path in actual.items():
        require(sha256_file(path) == listed[relative], f"checksum mismatch: {relative}")


def verify_privacy_and_binary_policy() -> None:
    actual_names = {
        path.relative_to(EVIDENCE_ROOT).as_posix()
        for path in EVIDENCE_ROOT.rglob("*")
        if path.is_file()
    }
    require(REQUIRED_FILES <= actual_names, "required evidence files are missing")
    require(not list(EVIDENCE_ROOT.rglob("*.npz")), "NPZ binaries must not enter Git evidence")
    for path in EVIDENCE_ROOT.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_IDENTITY_MARKERS:
            require(marker not in text, f"local identity marker found in {path.name}")
        require(EMAIL_PATTERN.search(text) is None, f"email address found in {path.name}")


def verify_scene_inventory(
    evidence: dict[str, Any],
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    rows = read_csv(SCENE_PATH, SCENE_FIELDS)
    require(len(rows) == 34, "scene_inventory.csv must contain 34 banks")
    indices = [int(row["scene_index"]) for row in rows]
    require(indices == list(range(34)), "scene indices must be exactly 0..33")
    require(len({row["scene_id"] for row in rows}) == 34, "scene IDs must be unique")
    require(len({row["bank_id"] for row in rows}) == 34, "bank IDs must be unique")
    require(
        len({row["base_map_cluster_id"] for row in rows}) == 34,
        "base-map cluster IDs must be unique",
    )
    require(
        all(row["scene_id"] == row["bank_id"] for row in rows),
        "scene and bank IDs must be identical for this candidate",
    )
    require(
        all(row["verification_status"] == "PASS" for row in rows),
        "all scene rows must be verified PASS",
    )
    for row in rows:
        for field in (
            "canonical_base_map_sha256",
            "scene_xml_sha256",
            "bank_record_sha256",
        ):
            require_sha256(row[field], f"scene {row['scene_index']} {field}")

    role_counts = dict(Counter(row["role"] for row in rows))
    city_counts = dict(Counter(row["city_id"] for row in rows))
    require(role_counts == evidence["candidate"]["role_counts"], "scene role counts mismatch")
    require(city_counts == evidence["candidate"]["city_counts"], "scene city counts mismatch")
    by_scene_id = {row["scene_id"]: row for row in rows}
    return rows, by_scene_id


def verify_shard_inventory(
    evidence: dict[str, Any],
) -> list[dict[str, str]]:
    rows = read_csv(SHARD_PATH, SHARD_FIELDS)
    require(len(rows) == 14, "shard_inventory.csv must contain 14 shards")
    indices = [int(row["shard_index"]) for row in rows]
    require(indices == list(range(14)), "shard indices must be exactly 0..13")

    coverage: list[int] = []
    total_bytes = 0
    total_duration = Decimal("0")
    for row in rows:
        start = int(row["scene_start_inclusive"])
        end = int(row["scene_end_exclusive"])
        count = int(row["scene_count"])
        require(end > start and end - start == count, "invalid shard scene interval")
        coverage.extend(range(start, end))
        total_bytes += int(row["npz_bytes"])
        total_duration += Decimal(row["duration_seconds"])
        require_sha256(row["npz_sha256"], f"shard {row['shard_index']} NPZ")
        require_sha256(row["manifest_sha256"], f"shard {row['shard_index']} manifest")
        require(int(row["manifest_bytes"]) > 0, "shard manifest must be nonempty")
        require(row["status"] == "PASS", "all shards must be PASS")

    expected = evidence["candidate"]["shards"]
    require(coverage == list(range(34)), "shards must cover scene indices 0..33 exactly once")
    require(total_bytes == expected["total_npz_bytes"], "total shard bytes mismatch")
    require(
        total_duration == Decimal(str(expected["total_duration_seconds"])),
        "total shard duration mismatch",
    )
    return rows


def verify_runtime_trust(evidence: dict[str, Any]) -> None:
    runtime = evidence["candidate"]["runtime"]
    require(
        runtime["approved_registry_path"]
        == "formal_v2/configs/sionna_llvm_approved_v1.json",
        "approved LLVM registry path mismatch",
    )
    registry = load_json(APPROVED_LLVM_PATH)
    require(
        registry.get("schema_version") == "csi-pairs-sionna-approved-libllvm-v1"
        and isinstance(registry.get("libraries"), list),
        "approved LLVM registry schema mismatch",
    )
    matches = [
        row
        for row in registry["libraries"]
        if isinstance(row, dict)
        and row.get("platform_system") == runtime["platform_system"]
        and row.get("platform_machine") == runtime["platform_machine"]
        and row.get("sha256") == runtime["libllvm_sha256"]
    ]
    registered = len(matches) == 1
    require(
        registered and runtime["approved_registry_match"] is True,
        "candidate LLVM registry-match declaration is stale",
    )
    require(
        runtime.get("preapproved_at_generation") is False
        and runtime["formal_runtime_status"]
        == "BLOCKED_NOT_PREAPPROVED_AT_GENERATION",
        "this evidence package must remain blocked because its bound generation source predates runtime approval enforcement",
    )


def verify_static() -> tuple[dict[str, Any], list[dict[str, str]], dict[str, dict[str, str]], list[dict[str, str]]]:
    verify_privacy_and_binary_policy()
    evidence = load_json(EVIDENCE_PATH)
    require(
        evidence["schema_version"] == "csi-pairs-m4-formal-candidate-evidence-v1",
        "unexpected evidence schema",
    )
    require(
        evidence["status"] == "STATIC_REGISTRY_PASS",
        "evidence status must describe static registry verification only",
    )
    require(
        evidence["scientific_use"] == "CANDIDATE_NOT_CLAIM",
        "scientific boundary must remain CANDIDATE_NOT_CLAIM",
    )
    require(evidence["readiness"] == EXPECTED_READINESS, "readiness boundary mismatch")
    require(
        evidence["closed_issue_ids"] == [],
        "unapproved-runtime evidence must not close formal issues",
    )
    require(
        set(evidence["conditional_issue_ids"]) == EXPECTED_CONDITIONAL_ISSUES,
        "conditional issue scope mismatch",
    )
    require(
        evidence["candidate"]["shape"]
        == {
            "scene_banks": 34,
            "cities": 6,
            "worlds_per_bank": 4,
            "positions_per_bank": 256,
            "repeats": 3,
            "channels": 16,
            "clean_units": 34816,
            "base_map_clusters": 34,
        },
        "candidate shape summary mismatch",
    )
    require(
        all(value == 0 for value in evidence["candidate"]["data_checks"].values()),
        "candidate data checks must all be zero",
    )
    require(
        evidence["repository_policy"]["npz_files_included"] is False,
        "NPZ repository policy must remain false",
    )
    require(
        evidence["repository_policy"]["original_manifests_included"] is False,
        "unsanitized original manifests must remain omitted",
    )
    regenerated_keys = evidence["verification"]["regenerated_array_keys"]
    require(
        len(regenerated_keys) == 15 and len(set(regenerated_keys)) == 15,
        "registered regenerated-array inventory mismatch",
    )
    verify_runtime_trust(evidence)

    for section_name, records in (
        (
            "candidate",
            [
                evidence["candidate"]["dataset"],
                evidence["candidate"]["generation_manifest"],
                evidence["candidate"]["asset_manifest"],
            ],
        ),
        (
            "inspection",
            [
                evidence["inspection"]["data_contract"],
                evidence["inspection"]["run_manifest"],
            ],
        ),
        (
            "verification",
            [
                evidence["verification"]["gate"],
                evidence["verification"]["regenerated_dataset"],
                evidence["verification"]["per_scene_inventory"],
                evidence["verification"]["verifier_manifest"],
                evidence["verification"]["stage_manifest"],
                evidence["verification"]["run_manifest"],
            ],
        ),
    ):
        for record in records:
            require_sha256(record["sha256"], f"{section_name} {record['label']}")
            require(record["bytes"] > 0, f"{section_name} artifact must be nonempty")
            require(
                record["included_in_repository"] is False,
                f"unsanitized {section_name} artifact must remain external",
            )

    scenes, by_scene_id = verify_scene_inventory(evidence)
    shards = verify_shard_inventory(evidence)
    verify_repository_checksums()
    return evidence, scenes, by_scene_id, shards


def verify_file_record(path: Path, record: dict[str, Any], label: str) -> None:
    require(path.is_file() and not path.is_symlink(), f"missing regular {label}: {path}")
    require(path.stat().st_size == record["bytes"], f"{label} byte size mismatch")
    require(sha256_file(path) == record["sha256"], f"{label} SHA-256 mismatch")


def verify_generation(
    candidate_root: Path,
    evidence: dict[str, Any],
    shard_rows: list[dict[str, str]],
) -> None:
    candidate = evidence["candidate"]
    dataset_path = candidate_root / "dataset.npz"
    generation_path = candidate_root / "dataset.generation.json"
    asset_path = candidate_root / "assets" / "asset_manifest.json"
    verify_file_record(dataset_path, candidate["dataset"], "candidate dataset")
    verify_file_record(generation_path, candidate["generation_manifest"], "generation manifest")
    verify_file_record(asset_path, candidate["asset_manifest"], "asset manifest")

    generation = load_json(generation_path)
    require(generation["status"] == "PASS", "generation manifest is not PASS")
    require(generation["fixture"] is False, "generation manifest must be non-fixture")
    require(
        generation["scientific_use"] == "CANDIDATE",
        "generated dataset must remain CANDIDATE",
    )
    require(generation["simulation_not_measurement"] is True, "simulation flag mismatch")
    require(generation["output_sha256"] == candidate["dataset"]["sha256"], "output hash mismatch")
    require(generation["output_bytes"] == candidate["dataset"]["bytes"], "output size mismatch")
    require(
        generation["asset_manifest_sha256"] == candidate["asset_manifest"]["sha256"],
        "generation asset-manifest hash mismatch",
    )
    require(
        generation["generator_sha256"] == candidate["generator"]["source_sha256"],
        "generator source hash mismatch",
    )
    require(
        generation["engine_config_sha256"] == candidate["engine"]["config_sha256"],
        "generation engine-config hash mismatch",
    )
    generated_shards = {
        int(row["render_shard_index"]): row for row in generation["shards"]
    }
    require(set(generated_shards) == set(range(14)), "generation shard set mismatch")

    runtime_expected = candidate["runtime"]
    for row in shard_rows:
        index = int(row["shard_index"])
        manifest_path = candidate_root / "shards" / f"shard-{index}.manifest.json"
        npz_path = candidate_root / "shards" / f"shard-{index}.npz"
        verify_file_record(
            manifest_path,
            {
                "sha256": row["manifest_sha256"],
                "bytes": int(row["manifest_bytes"]),
            },
            f"shard {index} manifest",
        )
        verify_file_record(
            npz_path,
            {"sha256": row["npz_sha256"], "bytes": int(row["npz_bytes"])},
            f"shard {index} NPZ",
        )
        manifest = load_json(manifest_path)
        require(manifest["status"] == "PASS", f"shard {index} is not PASS")
        require(manifest["fixture"] is False, f"shard {index} must be non-fixture")
        require(manifest["scientific_use"] == "CANDIDATE", "shard scientific use mismatch")
        require(manifest["simulation_not_measurement"] is True, "shard simulation flag mismatch")
        for field in (
            "render_shard_index",
            "scene_start_inclusive",
            "scene_end_exclusive",
            "scene_count",
            "output_sha256",
            "output_bytes",
        ):
            inventory_field = {
                "render_shard_index": "shard_index",
                "output_sha256": "npz_sha256",
                "output_bytes": "npz_bytes",
            }.get(field, field)
            expected_value: object = row[inventory_field]
            if field not in {"output_sha256"}:
                expected_value = int(expected_value)
            require(manifest[field] == expected_value, f"shard {index} {field} mismatch")
        require(
            Decimal(str(manifest["duration_seconds"])) == Decimal(row["duration_seconds"]),
            f"shard {index} duration mismatch",
        )
        require(
            manifest["generator_sha256"] == candidate["generator"]["source_sha256"],
            "shard generator hash mismatch",
        )
        require(
            manifest["asset_manifest_sha256"] == candidate["asset_manifest"]["sha256"],
            "shard asset-manifest hash mismatch",
        )
        runtime = manifest["runtime"]
        for field in (
            "python",
            "sionna",
            "sionna_rt",
            "mitsuba",
            "drjit",
            "mitsuba_variant",
            "drjit_thread_count",
        ):
            require(runtime[field] == runtime_expected[field], f"shard runtime {field} mismatch")
        require(
            runtime["drjit_libllvm_sha256"] == runtime_expected["libllvm_sha256"],
            "shard LLVM hash mismatch",
        )
        generated = generated_shards[index]
        require(generated["sha256"] == row["npz_sha256"], "merged shard hash mismatch")
        require(
            Decimal(str(generated["duration_seconds"])) == Decimal(row["duration_seconds"]),
            "merged shard duration mismatch",
        )


def verify_assets(
    candidate_root: Path,
    evidence: dict[str, Any],
    scene_rows: list[dict[str, str]],
) -> None:
    asset_root = candidate_root / "assets"
    asset = load_json(asset_root / "asset_manifest.json")
    require(asset["status"] == "PASS", "asset manifest is not PASS")
    require(
        asset["schema_version"] == evidence["candidate"]["asset_manifest"]["schema_version"],
        "asset schema mismatch",
    )
    require(
        asset["config_sha256"] == evidence["candidate"]["asset_manifest"]["asset_config_sha256"],
        "asset config hash mismatch",
    )
    require(
        asset["source_config_sha256"]
        == evidence["candidate"]["asset_manifest"]["source_config_sha256"],
        "asset source-config hash mismatch",
    )
    require(
        {row["license_id"] for row in asset["licenses"]} == {"ODbL-1.0", "Apache-2.0"},
        "asset licenses mismatch",
    )
    require(
        {row["city_id"] for row in asset["raw_sources"]}
        == set(evidence["candidate"]["city_counts"]),
        "raw OSM city set mismatch",
    )
    require(
        len(asset["raw_sources"]) == 6
        and len({row["path"] for row in asset["raw_sources"]}) == 6,
        "raw OSM inventory must contain one distinct file per city",
    )
    expected_files = {"asset_manifest.json"}
    for field, digest_field in (
        ("config_path", "config_sha256"),
        ("attribution_path", "attribution_sha256"),
    ):
        relative = Path(str(asset[field]))
        require(
            not relative.is_absolute() and ".." not in relative.parts,
            f"unsafe asset {field}",
        )
        verify_file_record(
            asset_root / relative,
            {
                "sha256": require_sha256(asset[digest_field], f"asset {digest_field}"),
                "bytes": (asset_root / relative).stat().st_size,
            },
            f"asset {field}",
        )
        expected_files.add(relative.as_posix())
    for source in asset["raw_sources"]:
        relative = Path(str(source["path"]))
        require(
            not relative.is_absolute() and ".." not in relative.parts,
            "unsafe raw OSM path",
        )
        verify_file_record(
            asset_root / relative,
            {"sha256": source["sha256"], "bytes": source["bytes"]},
            f"raw OSM source {source['city_id']}",
        )
        expected_files.add(relative.as_posix())
    banks = sorted(asset["banks"], key=lambda row: row["scene_index"])
    require(len(banks) == len(scene_rows), "asset bank count mismatch")
    for bank, expected in zip(banks, scene_rows, strict=True):
        for key in (
            "scene_id",
            "bank_id",
            "city_id",
            "role",
            "base_map_cluster_id",
            "scene_xml_sha256",
            "bank_record_sha256",
        ):
            require(str(bank[key]) == expected[key], f"asset bank {key} mismatch")
        require(
            bank["scene_index"] == int(expected["scene_index"]),
            "asset scene index mismatch",
        )
        require(
            bank["bank_index_within_city"] == int(expected["bank_index_within_city"]),
            "asset bank-within-city index mismatch",
        )
        prefix = Path("banks") / expected["scene_id"]
        expected_bank_files = {
            (prefix / "bank.json").as_posix(),
            (prefix / "scene.xml").as_posix(),
            (prefix / "mesh/background.ply").as_posix(),
            (prefix / "mesh/ground.ply").as_posix(),
            (prefix / "mesh/primitive-0.ply").as_posix(),
            (prefix / "mesh/primitive-1.ply").as_posix(),
        }
        file_rows = bank.get("files")
        require(isinstance(file_rows, list), "asset bank files must be a list")
        listed = [str(row.get("path")) for row in file_rows if isinstance(row, dict)]
        require(
            len(listed) == 6 and len(set(listed)) == 6 and set(listed) == expected_bank_files,
            f"asset bank file inventory mismatch: {expected['scene_id']}",
        )
        require(
            bank["bank_record_path"] == (prefix / "bank.json").as_posix()
            and bank["scene_xml_path"] == (prefix / "scene.xml").as_posix(),
            f"asset bank primary paths mismatch: {expected['scene_id']}",
        )
        for file_row in file_rows:
            relative = Path(file_row["path"])
            require(".." not in relative.parts, "unsafe asset bank path")
            verify_file_record(
                asset_root / relative,
                {"sha256": file_row["sha256"], "bytes": file_row["bytes"]},
                f"asset bank file {relative}",
            )
            expected_files.add(relative.as_posix())
        require(
            bank["bank_record_sha256"]
            == next(row["sha256"] for row in file_rows if row["path"] == bank["bank_record_path"])
            and bank["scene_xml_sha256"]
            == next(row["sha256"] for row in file_rows if row["path"] == bank["scene_xml_path"]),
            f"asset bank primary hashes mismatch: {expected['scene_id']}",
        )
    actual_files = set()
    for path in asset_root.rglob("*"):
        require(not path.is_symlink(), f"asset tree contains symlink: {path}")
        if path.is_file():
            actual_files.add(path.relative_to(asset_root).as_posix())
    require(actual_files == expected_files, "asset tree file inventory is not exact")


def verify_inspection(
    inspection_root: Path,
    evidence: dict[str, Any],
    scene_rows: list[dict[str, str]],
) -> None:
    inspection = evidence["inspection"]
    contract_path = inspection_root / "data_contract.json"
    manifest_path = inspection_root / "manifest.json"
    verify_file_record(contract_path, inspection["data_contract"], "inspection data contract")
    verify_file_record(manifest_path, inspection["run_manifest"], "inspection manifest")
    contract = load_json(contract_path)
    require(contract["status"] == "PASS", "inspection status is not PASS")
    require(contract["fixture"] is False, "inspection must be non-fixture")
    require(contract["scientific_use"] == "CANDIDATE", "inspection scientific use mismatch")
    require(
        contract["dataset_sha256"] == evidence["candidate"]["dataset"]["sha256"],
        "inspection dataset hash mismatch",
    )
    require(
        contract["shape"]
        == {
            "bits": 2,
            "channels": 16,
            "map_channels": 3,
            "map_size": 256,
            "positions": 256,
            "radio_features": 4,
            "repeats": 3,
            "scenes": 34,
            "worlds": 4,
        },
        "inspection shape mismatch",
    )
    require(
        contract["scene_role_counts"] == evidence["candidate"]["role_counts"],
        "inspection role counts mismatch",
    )
    require(
        contract["independent_cluster_role_counts"] == evidence["candidate"]["role_counts"],
        "inspection independent role counts mismatch",
    )
    require(
        contract["base_map_clusters"] == 34
        and contract["canonical_base_map_digest_count"] == 34,
        "inspection cluster count mismatch",
    )
    expected_digests = {
        row["bank_id"]: row["canonical_base_map_sha256"] for row in scene_rows
    }
    require(
        contract["canonical_base_map_digests_by_bank"] == expected_digests,
        "inspection canonical-map digests mismatch",
    )
    require(
        contract["engine"]["config_sha256"] == evidence["candidate"]["engine"]["config_sha256"],
        "inspection engine-config hash mismatch",
    )


def verify_per_scene(
    path: Path,
    evidence: dict[str, Any],
    scene_by_id: dict[str, dict[str, str]],
) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == 34, "verification per_scene.csv must contain 34 scenes")
    require({row["scene_id"] for row in rows} == set(scene_by_id), "verified scene set mismatch")
    for row in rows:
        expected = scene_by_id[row["scene_id"]]
        require(row["bank_id"] == expected["bank_id"], "verified bank ID mismatch")
        require(row["base_map_cluster_id"] == expected["base_map_cluster_id"], "verified cluster mismatch")
        require(row["role"] == expected["role"], "verified role mismatch")
        require(
            row["canonical_base_map_digest"] == expected["canonical_base_map_sha256"],
            "verified canonical-map digest mismatch",
        )
        require(
            row["regenerated_canonical_base_map_digest"]
            == expected["canonical_base_map_sha256"],
            "regenerated canonical-map digest mismatch",
        )
        require(
            all(row[field] == "True" for field in PER_SCENE_BOOLEAN_FIELDS),
            f"scene verification failed: {row['scene_id']}",
        )
        require(
            row["dataset_sha256"] == evidence["candidate"]["dataset"]["sha256"],
            "per-scene dataset hash mismatch",
        )
        require(
            row["scientific_use"] == "CANDIDATE_NOT_CLAIM",
            "per-scene scientific boundary mismatch",
        )


def verify_npz_equivalence(
    original_path: Path,
    regenerated_path: Path,
    expected_keys: list[str],
) -> int:
    try:
        import numpy as np
    except ImportError as exc:
        raise EvidenceError("deep verification requires numpy") from exc

    with (
        np.load(original_path, allow_pickle=False) as original,
        np.load(regenerated_path, allow_pickle=False) as regenerated,
    ):
        require(
            set(regenerated.files) == set(expected_keys),
            "regenerated NPZ key set mismatch",
        )
        require(
            set(regenerated.files) <= set(original.files),
            "regenerated NPZ contains an unknown key",
        )
        for key in expected_keys:
            left = original[key]
            right = regenerated[key]
            require(left.shape == right.shape, f"regenerated {key} shape mismatch")
            require(left.dtype == right.dtype, f"regenerated {key} dtype mismatch")
            require(np.array_equal(left, right), f"regenerated {key} differs at zero tolerance")
            del left, right
            gc.collect()
        return len(expected_keys)


def count_duplicate_id_units(values: Any) -> int:
    import numpy as np

    duplicate_units = 0
    for row in values.reshape(-1, values.shape[-1]):
        valid = row[row >= 0]
        if valid.size != np.unique(valid).size:
            duplicate_units += 1
    return duplicate_units


def verify_dataset_metrics(dataset_path: Path, evidence: dict[str, Any]) -> None:
    try:
        import numpy as np
    except ImportError as exc:
        raise EvidenceError("deep verification requires numpy") from exc

    with np.load(dataset_path, allow_pickle=False) as dataset:
        expected_shape = evidence["candidate"]["shape"]
        require(dataset["csi_clean"].shape == (34, 4, 256, 16), "csi_clean shape mismatch")
        require(dataset["csi_repeat"].shape == (34, 4, 256, 3, 16), "csi_repeat shape mismatch")
        require(dataset["path_ids"].shape == (34, 4, 256, 64), "path_ids shape mismatch")
        require(dataset["noop_path_ids"].shape == (34, 4, 256, 64), "noop_path_ids shape mismatch")
        require(dataset["positions"].shape == (34, 256, 2), "positions shape mismatch")

        clean = dataset["csi_clean"]
        path_ids = dataset["path_ids"]
        noop_path_ids = dataset["noop_path_ids"]
        checks = {
            "pathless_clean_units": int(np.count_nonzero(~np.any(path_ids >= 0, axis=-1))),
            "pathless_noop_units": int(
                np.count_nonzero(~np.any(noop_path_ids >= 0, axis=-1))
            ),
            "all_zero_clean_units": int(np.count_nonzero(np.all(clean == 0, axis=-1))),
            "nonfinite_clean_values": int(np.count_nonzero(~np.isfinite(clean))),
            "duplicate_path_id_units": count_duplicate_id_units(path_ids),
        }

        target_indices = np.flatnonzero(dataset["scene_roles"] == "target")
        support_ids: set[str] = set()
        query_ids: set[str] = set()
        support_coordinates: set[tuple[float, float]] = set()
        query_coordinates: set[tuple[float, float]] = set()
        for scene_index in target_indices.tolist():
            roles = dataset["position_roles"][scene_index]
            support_mask = roles == "support_pool"
            query_mask = roles == "query"
            support_ids.update(dataset["position_ids"][scene_index][support_mask].tolist())
            query_ids.update(dataset["position_ids"][scene_index][query_mask].tolist())
            support_coordinates.update(
                tuple(row.tolist()) for row in dataset["positions"][scene_index][support_mask]
            )
            query_coordinates.update(
                tuple(row.tolist()) for row in dataset["positions"][scene_index][query_mask]
            )
        checks["target_support_query_id_intersection"] = len(support_ids & query_ids)
        checks["target_support_query_coordinate_intersection"] = len(
            support_coordinates & query_coordinates
        )
        require(checks == evidence["candidate"]["data_checks"], "deep data checks mismatch")
        require(int(np.prod(clean.shape[:-1])) == expected_shape["clean_units"], "clean-unit count mismatch")
        require(np.all(dataset["free_space"]), "candidate contains non-free registered units")
        require(
            len(set(dataset["base_map_cluster_ids"].tolist()))
            == expected_shape["base_map_clusters"],
            "dataset cluster count mismatch",
        )
        require(
            dict(Counter(dataset["city_ids"].tolist()))
            == evidence["candidate"]["city_counts"],
            "dataset city counts mismatch",
        )
        require(
            dict(Counter(dataset["scene_roles"].tolist()))
            == evidence["candidate"]["role_counts"],
            "dataset role counts mismatch",
        )
        metadata = json.loads(str(dataset["metadata_json"]))
        require(metadata["fixture"] is False, "dataset metadata must be non-fixture")
        require(metadata["scientific_use"] == "CANDIDATE", "dataset metadata boundary mismatch")
        require(
            metadata["engine"]["config_sha256"] == evidence["candidate"]["engine"]["config_sha256"],
            "dataset engine-config hash mismatch",
        )


def verify_verification(
    verification_root: Path,
    evidence: dict[str, Any],
    scene_by_id: dict[str, dict[str, str]],
    candidate_root: Path,
) -> int:
    verification = evidence["verification"]
    data_root = verification_root / "data_verification"
    artifact_paths = {
        "gate": data_root / "gate.json",
        "regenerated_dataset": data_root / "regenerated.npz",
        "per_scene_inventory": data_root / "per_scene.csv",
        "verifier_manifest": data_root / "verifier_manifest.json",
        "stage_manifest": data_root / "manifest.json",
        "run_manifest": verification_root / "manifest.json",
    }
    for key, path in artifact_paths.items():
        verify_file_record(path, verification[key], f"verification {key}")

    gate = load_json(artifact_paths["gate"])
    require(gate["status"] == "PASS" and gate["passed"] is True, "verification gate failed")
    require(gate["blocking_passed"] is True, "blocking roles did not pass")
    require(gate["fixture"] is False, "verification gate must be non-fixture")
    require(gate["scientific_use"] == "CANDIDATE_NOT_CLAIM", "gate boundary mismatch")
    require(gate["dataset_sha256"] == evidence["candidate"]["dataset"]["sha256"], "gate dataset hash mismatch")
    require(gate["rtol"] == 0.0 and gate["atol"] == 0.0, "gate tolerance is not zero")
    require(gate["engine_config_match"] is True, "gate engine config mismatch")
    require(gate["nonblocking_scene_failures"] == [], "gate has scene failures")
    require(gate["role_status"] == verification["role_status"], "gate role status mismatch")
    for field in (
        "formal_config_sha256",
        "requirements_lock_sha256",
        "source_tree_sha256",
        "runtime_provenance_sha256",
    ):
        gate_field = "config_sha256" if field == "formal_config_sha256" else field
        require(gate[gate_field] == verification[field], f"gate {gate_field} mismatch")
    require(
        gate["verifier_source_sha256"] == verification["verifier_source"]["sha256"],
        "gate verifier-source hash mismatch",
    )
    require(
        gate["verifier_manifest_sha256"] == verification["verifier_manifest"]["sha256"],
        "gate verifier-manifest hash mismatch",
    )
    require(
        gate["verified_properties"] == verification["verified_properties"],
        "gate verified-properties mismatch",
    )

    verifier_manifest = load_json(artifact_paths["verifier_manifest"])
    require(
        verifier_manifest["verifier_source_sha256"]
        == verification["verifier_source"]["sha256"],
        "verifier manifest source hash mismatch",
    )
    require(
        verifier_manifest["engine_source_revision"]
        == evidence["candidate"]["engine"]["source_revision"],
        "verifier engine revision mismatch",
    )
    require(
        verifier_manifest["rtol"] == 0.0 and verifier_manifest["atol"] == 0.0,
        "verifier manifest tolerance mismatch",
    )
    verify_per_scene(artifact_paths["per_scene_inventory"], evidence, scene_by_id)
    arrays = verify_npz_equivalence(
        candidate_root / "dataset.npz",
        artifact_paths["regenerated_dataset"],
        verification["regenerated_array_keys"],
    )
    return arrays


def verify_deep(
    candidate_root: Path,
    inspection_root: Path,
    verification_root: Path,
    evidence: dict[str, Any],
    scene_rows: list[dict[str, str]],
    scene_by_id: dict[str, dict[str, str]],
    shard_rows: list[dict[str, str]],
) -> int:
    for path, label in (
        (candidate_root, "candidate root"),
        (inspection_root, "inspection root"),
        (verification_root, "verification root"),
    ):
        require(path.is_dir() and not path.is_symlink(), f"missing regular {label}: {path}")
    verify_generation(candidate_root, evidence, shard_rows)
    verify_assets(candidate_root, evidence, scene_rows)
    verify_inspection(inspection_root, evidence, scene_rows)
    verify_dataset_metrics(candidate_root / "dataset.npz", evidence)
    return verify_verification(
        verification_root,
        evidence,
        scene_by_id,
        candidate_root,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the repository evidence and optional original M4 artifacts."
    )
    parser.add_argument(
        "--candidate-root",
        type=Path,
        help="Root containing dataset.npz, dataset.generation.json, assets, and shards.",
    )
    parser.add_argument(
        "--inspection-root",
        type=Path,
        help="Root containing latest-main data_contract.json and manifest.json.",
    )
    parser.add_argument(
        "--verification-root",
        type=Path,
        help="Root containing the independent data_verification directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    deep_paths = (args.candidate_root, args.inspection_root, args.verification_root)
    try:
        evidence, scenes, scene_by_id, shards = verify_static()
        if any(path is not None for path in deep_paths):
            require(all(path is not None for path in deep_paths), "all deep roots are required together")
            array_count = verify_deep(
                args.candidate_root,
                args.inspection_root,
                args.verification_root,
                evidence,
                scenes,
                scene_by_id,
                shards,
            )
            print(
                "PASS mode=deep "
                f"dataset_sha256={evidence['candidate']['dataset']['sha256']} "
                f"scenes={len(scenes)} shards={len(shards)} npz_arrays={array_count} "
                "formal_candidate=BLOCKED_NOT_PREAPPROVED_AT_GENERATION"
            )
        else:
            print(
                "PASS mode=static "
                f"dataset_sha256={evidence['candidate']['dataset']['sha256']} "
                f"scenes={len(scenes)} shards={len(shards)} "
                "external_artifacts=NOT_VERIFIED "
                "formal_candidate=BLOCKED_NOT_PREAPPROVED_AT_GENERATION"
            )
    except (EvidenceError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
