#!/usr/bin/env bash
set -euo pipefail

artifact_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${artifact_root}"

python3 - <<'PY'
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path.cwd()
MANIFEST = ROOT / "99_REGISTRY/PR_METADATA_SHA256SUMS"
PAYLOAD_SUFFIXES = {
    ".zip", ".h5", ".hdf5", ".npz", ".npy", ".pt", ".pth", ".ckpt"
}
MAX_FILE_BYTES = 100 * 1024 * 1024
PRIVATE_PATTERNS = {
    "private Unix home path": re.compile(rb"/(?:Users|home|root)/"),
    "private macOS data path": re.compile(
        b"/" + b"System" + b"/" + b"Volumes" + b"/" + b"Data" + rb"(?:/|\b)"
    ),
    "hardware UUID": re.compile(
        rb"GPU-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        rb"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    ),
    "personal hostname": re.compile(
        rb"[A-Za-z0-9_-]*(?:MacBook|Mac)[A-Za-z0-9_.-]*\.local"
    ),
    "known private account name": re.compile(
        b"(?:" + b"futa" + b"oran|" + b"xun" + b"lian)", re.IGNORECASE
    ),
}


def fail(message: str) -> None:
    raise SystemExit(f"PR_METADATA_VERIFICATION=FAIL {message}")


def strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=lambda value: fail(f"non-finite JSON value in {path}: {value}"),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail(f"invalid JSON {path.relative_to(ROOT)}: {error}")
    if not isinstance(value, dict):
        fail(f"JSON root must be an object: {path.relative_to(ROOT)}")
    return value


if not MANIFEST.is_file():
    fail("missing 99_REGISTRY/PR_METADATA_SHA256SUMS")

manifest_paths: list[str] = []
for line_number, line in enumerate(MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
    match = re.fullmatch(r"([0-9a-f]{64})  (\./[^\r\n]+)", line)
    if match is None:
        fail(f"malformed checksum entry at line {line_number}")
    expected, encoded_path = match.groups()
    relative = encoded_path[2:]
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or relative == "99_REGISTRY/PR_METADATA_SHA256SUMS":
        fail(f"unsafe checksum path at line {line_number}: {encoded_path}")
    if relative in manifest_paths:
        fail(f"duplicate checksum path: {encoded_path}")
    target = ROOT / path
    if not target.is_file():
        fail(f"missing manifested file: {encoded_path}")
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual != expected:
        fail(f"checksum mismatch: {encoded_path}")
    manifest_paths.append(relative)

actual_paths = sorted(
    path.relative_to(ROOT).as_posix()
    for path in ROOT.rglob("*")
    if path.is_file() and path != MANIFEST
)
if sorted(manifest_paths) != actual_paths:
    missing = sorted(set(actual_paths) - set(manifest_paths))
    extra = sorted(set(manifest_paths) - set(actual_paths))
    fail(f"checksum coverage mismatch missing={missing} extra={extra}")

catalog = load_json(ROOT / "DATASET_CATALOG.json")
suite_status = catalog.get("suite_status")
verification = catalog.get("final_verification")
datasets = catalog.get("datasets")
if not isinstance(suite_status, dict) or not isinstance(verification, dict):
    fail("catalog status objects are missing")
if (
    catalog.get("schema_version") != "csi-pairs-dataset-suite-catalog-v1"
    or suite_status.get("engineering_copy_status") != "PARTIAL_SOURCE_TARGET_AUDIT"
    or suite_status.get("formal_status") != "POST_AUDIT_NO_GO"
    or suite_status.get("scientific_use") != "FORBIDDEN"
    or verification.get("result") != "PASS"
    or verification.get("copy_gate") != "PARTIAL"
    or verification.get("formal_status_after_verification") != "POST_AUDIT_NO_GO"
    or verification.get("scientific_use_after_verification") != "FORBIDDEN"
):
    fail("catalog readiness boundary changed")
if not isinstance(datasets, list) or len(datasets) != 12:
    fail("catalog must contain exactly 12 datasets")

catalog_pairs: set[tuple[str, str]] = set()
for row in datasets:
    if not isinstance(row, dict):
        fail("catalog dataset row must be an object")
    dataset_id = row.get("dataset_id")
    suite_path = row.get("suite_path")
    source_path = row.get("source_path")
    if not all(isinstance(value, str) and value for value in (dataset_id, suite_path)):
        fail("catalog dataset ID/path must be nonempty strings")
    if not isinstance(source_path, str) or not source_path.startswith("$LOCAL_"):
        fail(f"catalog source_path must be a portable placeholder: {dataset_id}")
    if row.get("copy_status") != "COPIED":
        fail(f"catalog copy_status changed: {dataset_id}")
    pair = (dataset_id, suite_path)
    if pair in catalog_pairs:
        fail(f"duplicate catalog dataset mapping: {pair}")
    catalog_pairs.add(pair)

with (ROOT / "ROLE_ASSIGNMENTS.csv").open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    required_columns = {
        "dataset_id", "suite_path", "allowed_roles", "forbidden_roles",
        "headline_teacher_policy", "scientific_status", "reason",
    }
    if set(reader.fieldnames or ()) != required_columns:
        fail("ROLE_ASSIGNMENTS.csv columns changed")
    role_rows = list(reader)
if len(role_rows) != 12:
    fail("ROLE_ASSIGNMENTS.csv must contain exactly 12 rows")
role_pairs = {(row["dataset_id"], row["suite_path"]) for row in role_rows}
if len(role_pairs) != 12 or role_pairs != catalog_pairs:
    fail("catalog and role assignment ID/path mappings do not match exactly")
if any(row["headline_teacher_policy"] != "NEVER" for row in role_rows):
    fail("headline teacher policy must remain NEVER for every registered suite entity")

final_verification = load_json(ROOT / "99_REGISTRY/FINAL_VERIFICATION.json")
verified = final_verification.get("verified")
if (
    final_verification.get("result") != "PASS"
    or final_verification.get("copy_gate") != "PARTIAL"
    or final_verification.get("formal_status") != "POST_AUDIT_NO_GO"
    or final_verification.get("scientific_use") != "FORBIDDEN"
    or not isinstance(verified, dict)
    or verified.get("catalog_copied_entries_exist") != 12
    or verified.get("source_target_copy_audited_entries") != 3
):
    fail("final verification boundary changed")

project_root = ROOT.parent.parent
frozen_contract = ROOT / "00_FROZEN_SPECS/FORMAL_V2_DATA_CONTRACT.md"
executable_contract = project_root / "formal_v2/DATA_CONTRACT.md"
if frozen_contract.read_bytes() != executable_contract.read_bytes():
    fail("frozen data contract differs from the executable data contract")

for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    relative = path.relative_to(ROOT)
    if path.suffix.lower() in PAYLOAD_SUFFIXES:
        fail(f"raw dataset/model payload is not allowed: {relative}")
    if path.stat().st_size > MAX_FILE_BYTES:
        fail(f"file exceeds 100 MiB: {relative}")
    content = path.read_bytes()
    for label, pattern in PRIVATE_PATTERNS.items():
        if pattern.search(content):
            fail(f"{label} found in {relative}")

print(f"PR_METADATA_VERIFICATION=PASS files={len(actual_paths)}")
print("COPY_GATE=PARTIAL source_target_audited=3 catalog_targets=12")
print("FORMAL_STATUS=POST_AUDIT_NO_GO")
print("SCIENTIFIC_USE=FORBIDDEN")
PY
