from __future__ import annotations

from pathlib import Path

from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_csv, write_json


RESOURCE_SCHEMA = "csi-pairs-v6-waibu-resources-v1"
REQUIRED_FILES = {
    "2406.14995v2.pdf",
    "2502.11965v2.pdf",
    "2505.09160v2.pdf",
    "2601.03789v1.pdf",
    "2603.25216v1.pdf",
    "2604.07086v1.pdf",
    "2606.04770v1.pdf",
    "Wi-GATr-main.zip",
    "sionna-main.zip",
    "sionna-large-radio-maps-main.zip",
}
IMPLEMENTATION_STATUSES = {
    "official-code-adaptation",
    "paper-spec-controlled-implementation",
    "style-controlled-implementation",
}


def verify_waibu_resources(registry_path: str | Path, waibu_root: str | Path, output_root: str | Path) -> dict:
    registry_file = Path(registry_path).resolve()
    resource_root = Path(waibu_root).resolve()
    output_dir = Path(output_root).resolve() / "waibu_resources"
    output_dir.mkdir(parents=True, exist_ok=False)
    payload = read_strict_json(registry_file)
    rows = validate_resource_registry(payload, resource_root)
    write_csv(output_dir / "resource_inventory.csv", rows)
    passed = all(row["status"] == "PASS" for row in rows)
    gate = {
        "schema_version": "csi-pairs-v6-waibu-resource-gate-v1",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "registry_path": str(registry_file),
        "registry_sha256": sha256_file(registry_file),
        "waibu_root": str(resource_root),
        "resource_count": len(rows),
        "verified_count": sum(row["status"] == "PASS" for row in rows),
        "rule": "A resource hash authenticates local bytes only; it does not authenticate scientific results.",
    }
    write_json(output_dir / "gate.json", gate)
    write_json(
        output_dir / "manifest.json",
        {
            "schema_version": "csi-pairs-waibu-resource-stage-manifest-v1",
            "files": artifact_manifest(output_dir),
        },
    )
    return gate


def validate_resource_registry(payload: dict, waibu_root: str | Path) -> list[dict]:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "resources"}:
        raise ValueError("waibu resource registry fields must be exact")
    if payload["schema_version"] != RESOURCE_SCHEMA:
        raise ValueError("waibu resource registry schema mismatch")
    resources = payload["resources"]
    if not isinstance(resources, list):
        raise ValueError("waibu resources must be a list")
    expected_fields = {
        "file",
        "sha256",
        "resource_id",
        "title",
        "kind",
        "integration_role",
        "implementation_status",
        "allowed_name",
    }
    names = [row.get("file") for row in resources if isinstance(row, dict)]
    if len(names) != len(set(names)) or set(names) != REQUIRED_FILES:
        raise ValueError("waibu registry must contain each frozen resource exactly once")
    root = Path(waibu_root).resolve()
    actual_files = {path.name for path in root.iterdir() if path.is_file()}
    if actual_files != REQUIRED_FILES:
        raise ValueError(
            f"waibu directory contents changed: missing={sorted(REQUIRED_FILES - actual_files)}, "
            f"unexpected={sorted(actual_files - REQUIRED_FILES)}"
        )
    output = []
    for row in resources:
        if set(row) != expected_fields:
            raise ValueError("waibu resource fields must be exact")
        if row["kind"] not in {"paper", "official-source-archive"}:
            raise ValueError("waibu resource kind is invalid")
        if row["implementation_status"] not in IMPLEMENTATION_STATUSES:
            raise ValueError("waibu implementation status is invalid")
        if not all(isinstance(row[key], str) and row[key].strip() for key in expected_fields):
            raise ValueError("waibu resource string fields must be nonempty")
        path = (root / row["file"]).resolve()
        if path.parent != root or not path.is_file():
            raise ValueError("waibu resource path escapes its frozen directory")
        actual_sha256 = sha256_file(path)
        output.append(
            {
                **row,
                "actual_sha256": actual_sha256,
                "status": "PASS" if actual_sha256 == row["sha256"] else "FAIL",
            }
        )
    return output
