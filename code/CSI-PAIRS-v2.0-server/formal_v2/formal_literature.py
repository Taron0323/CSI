from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .formal_evidence import evidence_context
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_json


def run_literature_resource_gate(config, dataset, manifest_path, output_root):
    path = Path(manifest_path).resolve()
    manifest = read_strict_json(path)
    _validate_manifest(config, manifest, path.parent)
    output_dir = Path(output_root) / "literature_resources"
    output_dir.mkdir(parents=True, exist_ok=True)
    bound_manifest = output_dir / "literature_manifest.json"
    bound_records = []
    for record in manifest["records"]:
        content = Path(record["content_path"])
        if not content.is_absolute():
            content = path.parent / content
        bound_records.append({**record, "content_path": str(content.resolve())})
    write_json(bound_manifest, {**manifest, "records": bound_records})
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    decision = manifest["decision"]
    passed = bool(
        decision["no_direct_overlap"]
        and decision["rt_path_ready"]
        and decision["map_path_ready"]
        and decision["external_validity_path_ready"]
    )
    gate = {
        "schema_version": "csi-pairs-v6-literature-resource-gate-v2",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        **evidence,
        "gate": "G0",
        "input_manifest_path": bound_manifest.name,
        "input_manifest_sha256": sha256_file(bound_manifest),
        "search_completed_utc": manifest["search_completed_utc"],
        "databases": manifest["databases"],
        "record_count": len(manifest["records"]),
        "resource_plan": manifest["resource_plan"],
        "decision": decision,
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


def _validate_manifest(config, manifest, manifest_root=None):
    required = {
        "schema_version", "search_completed_utc", "databases", "queries", "records",
        "resource_plan", "licenses_reviewed", "decision",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("literature/resource manifest fields must be exact")
    if manifest["schema_version"] != "csi-pairs-v6-literature-resource-manifest-v2":
        raise ValueError("literature/resource manifest schema mismatch")
    completed = _parse_utc(manifest["search_completed_utc"])
    age = (datetime.now(timezone.utc) - completed).total_seconds() / 86400.0
    if age < 0 or age > int(config["literature"]["maximum_search_age_days"]):
        raise ValueError("literature search is future-dated or stale")
    if set(manifest["databases"]) != set(config["literature"]["required_databases"]):
        raise ValueError("literature search did not cover the required databases")
    if not isinstance(manifest["queries"], list) or not manifest["queries"]:
        raise ValueError("literature search queries must be recorded")
    records = manifest["records"]
    record_fields = {
        "citation_key", "title", "doi_or_url", "verified_utc", "content_path", "content_sha256",
        "relation_to_claim", "implementation_status",
    }
    if not isinstance(records, list) or not records:
        raise ValueError("literature manifest requires verified records")
    if len({record.get("citation_key") for record in records}) != len(records):
        raise ValueError("literature citation keys must be unique")
    for record in records:
        if not isinstance(record, dict) or set(record) != record_fields:
            raise ValueError("literature record fields must be exact")
        if any(not isinstance(record[key], str) or not record[key].strip() for key in record_fields):
            raise ValueError("literature record values must be nonempty strings")
        digest = record["content_sha256"]
        if len(digest) != 64 or any(value not in "0123456789abcdef" for value in digest):
            raise ValueError("literature record content hash is invalid")
        _parse_utc(record["verified_utc"])
        if record["relation_to_claim"] not in {
            "direct_overlap", "adjacent_nonoverlap", "baseline", "facility"
        }:
            raise ValueError("literature relation_to_claim is not a frozen category")
        if record["implementation_status"] not in {
            "integrated", "adapter_ready", "paper_only", "unavailable"
        }:
            raise ValueError("literature implementation_status is not a frozen category")
        content = Path(record["content_path"])
        if not content.is_absolute():
            if manifest_root is None:
                raise ValueError("relative literature content requires a manifest root")
            content = Path(manifest_root) / content
        if not content.is_file() or sha256_file(content) != digest:
            raise ValueError("literature content is missing or hash-mismatched")
    resource = manifest["resource_plan"]
    resource_fields = {
        "gpu_hours", "storage_gb", "seed_count", "failure_policy", "adapter_owners",
    }
    if not isinstance(resource, dict) or set(resource) != resource_fields:
        raise ValueError("resource plan fields must be exact")
    if float(resource["gpu_hours"]) <= 0 or float(resource["storage_gb"]) <= 0:
        raise ValueError("resource plan compute/storage must be positive")
    if int(resource["seed_count"]) < 3:
        raise ValueError("resource plan must fund at least three seeds")
    if not resource["failure_policy"] or not resource["adapter_owners"]:
        raise ValueError("resource plan ownership/failure policy must be explicit")
    if manifest["licenses_reviewed"] is not True:
        raise ValueError("resource gate requires an explicit license review")
    decision = manifest["decision"]
    decision_fields = {
        "no_direct_overlap", "rt_path_ready", "map_path_ready",
        "external_validity_path_ready", "novelty_scope",
    }
    if not isinstance(decision, dict) or set(decision) != decision_fields:
        raise ValueError("literature/resource decision fields must be exact")
    for key in (
        "no_direct_overlap", "rt_path_ready", "map_path_ready",
        "external_validity_path_ready",
    ):
        if type(decision[key]) is not bool:
            raise ValueError(f"literature/resource decision {key} must be boolean")
    if not isinstance(decision["novelty_scope"], str) or not decision["novelty_scope"].strip():
        raise ValueError("literature novelty scope must be explicit")
    direct_overlap = any(record["relation_to_claim"] == "direct_overlap" for record in records)
    if decision["no_direct_overlap"] == direct_overlap:
        raise ValueError("literature direct-overlap decision contradicts its records")


def _parse_utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamps must use UTC Z format")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("invalid UTC timestamp") from error
