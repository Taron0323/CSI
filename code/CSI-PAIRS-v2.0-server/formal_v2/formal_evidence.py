from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from .formal_config import public_formal_config
from .formal_dataset import FormalDataset
from .formal_io import sha256_file


QUALIFICATION_SCHEMA = "csi-pairs-formal-qualification-gate-v2.1-v6"
FACTORIAL_SCHEMA = "csi-pairs-formal-factorial-gate-v2.1-v6"
GATE_IDS = tuple(f"G{index}" for index in range(9))
CLAIM_IDS = tuple(f"C{index}" for index in range(1, 14))
ASSESSMENT_STATES = {"PASS", "FAIL", "BLOCKED", "NOT_ASSESSED"}


def config_sha256(config: dict) -> str:
    payload = json.dumps(
        public_formal_config(config),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def evidence_context(config: dict, dataset: FormalDataset, scientific_use: str) -> dict[str, object]:
    ceiling = "FORBIDDEN" if dataset.is_fixture else scientific_use
    return {
        "artifact_label": config["artifact_label"],
        "dataset_sha256": sha256_file(dataset.source_path),
        "config_sha256": config_sha256(config),
        "fixture": dataset.is_fixture,
        "scientific_use": ceiling,
    }


def bind_rows(rows: Iterable[dict], evidence: dict[str, object]) -> list[dict]:
    output = []
    for source in rows:
        row = dict(source)
        for key, value in evidence.items():
            if key in row and row[key] != value:
                raise ValueError(f"row attempts to override evidence field {key!r}")
            row[key] = value
        output.append(row)
    return output


def require_formal_qualification(
    gate: object,
    config: dict,
    dataset: FormalDataset,
    *,
    allow_nonscientific_fixture: bool,
) -> dict:
    if not isinstance(gate, dict):
        raise RuntimeError("qualification gate must be an object")
    required = {
        "schema_version",
        "passed",
        "scientific_use",
        "fixture",
        "dataset_sha256",
        "config_sha256",
        "upstream_gates",
        "teacher_checkpoint",
        "teacher_checkpoint_sha256",
    }
    missing = required.difference(gate)
    if missing:
        raise RuntimeError(f"qualification gate is missing authenticated fields: {sorted(missing)}")
    if gate["schema_version"] != QUALIFICATION_SCHEMA:
        raise RuntimeError("qualification gate schema is not V6-compatible")
    expected = evidence_context(config, dataset, str(gate["scientific_use"]))
    for key in ("dataset_sha256", "config_sha256", "fixture"):
        if gate[key] != expected[key]:
            raise RuntimeError(f"qualification gate {key} does not match the current run")
    if not bool(gate["passed"]):
        raise RuntimeError("formal factorial is blocked because the upstream qualification gate failed")
    if dataset.is_fixture:
        if not allow_nonscientific_fixture:
            raise RuntimeError("fixture training requires explicit software-test permission")
        if gate["scientific_use"] != "FORBIDDEN":
            raise RuntimeError("fixture qualification gate must remain FORBIDDEN")
    elif gate["scientific_use"] != "FORMAL_EXPERIMENT_ALLOWED":
        raise RuntimeError("factorial requires scientific_use=FORMAL_EXPERIMENT_ALLOWED")
    for gate_id, status in gate["upstream_gates"].items():
        if status not in ASSESSMENT_STATES:
            raise RuntimeError(f"invalid upstream assessment state for {gate_id}")
        if gate_id in {"G1", "G2"} and status != "PASS":
            raise RuntimeError(f"required upstream gate {gate_id} is not PASS")
    teacher_checkpoint = Path(str(gate["teacher_checkpoint"]))
    if not teacher_checkpoint.is_file():
        raise RuntimeError("qualification teacher checkpoint is missing")
    if sha256_file(teacher_checkpoint) != gate["teacher_checkpoint_sha256"]:
        raise RuntimeError("qualification teacher checkpoint hash mismatch")
    return gate


def complete_gate_vector(overrides: dict[str, str] | None = None) -> dict[str, str]:
    result = {gate_id: "NOT_ASSESSED" for gate_id in GATE_IDS}
    if overrides:
        for gate_id, status in overrides.items():
            if gate_id not in result:
                raise ValueError(f"unknown V6 gate: {gate_id}")
            if status not in ASSESSMENT_STATES:
                raise ValueError(f"invalid gate status: {status}")
            result[gate_id] = status
    return result


def blocked_claim_vector() -> dict[str, str]:
    return {claim_id: "BLOCKED" for claim_id in CLAIM_IDS}


def require_stage_manifested_gate(
    path: str | Path,
    payload: object,
    config: dict,
    dataset: FormalDataset,
    *,
    schema_version: str,
) -> dict:
    """Authenticate a gate against its stage manifest and current evidence context."""
    from .formal_io import read_strict_json

    gate_path = Path(path)
    if not isinstance(payload, dict) or payload.get("schema_version") != schema_version:
        raise RuntimeError(f"gate schema mismatch for {gate_path}")
    if not gate_path.is_file():
        raise RuntimeError(f"gate file is missing: {gate_path}")
    on_disk = read_strict_json(gate_path)
    if on_disk != payload:
        raise RuntimeError(f"supplied gate payload differs from its manifested file: {gate_path}")
    expected = evidence_context(config, dataset, str(payload.get("scientific_use", "")))
    for key in ("dataset_sha256", "config_sha256", "fixture"):
        if payload.get(key) != expected[key]:
            raise RuntimeError(f"gate {key} mismatch for {gate_path}")
    manifest_path = gate_path.parent / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"gate has no stage manifest: {gate_path}")
    manifest = read_strict_json(manifest_path)
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != "csi-pairs-formal-stage-manifest-v2.1-v6"
    ):
        raise RuntimeError(f"stage manifest schema mismatch: {manifest_path}")
    for key in ("dataset_sha256", "config_sha256", "fixture"):
        if manifest.get(key) != expected[key]:
            raise RuntimeError(f"stage manifest {key} mismatch: {manifest_path}")
    entries = manifest.get("files")
    relative = gate_path.name
    matches = [
        row
        for row in entries
        if isinstance(row, dict) and row.get("path") == relative
    ] if isinstance(entries, list) else []
    if len(matches) != 1 or matches[0].get("sha256") != sha256_file(gate_path):
        raise RuntimeError(f"gate is absent from or mismatched with its stage manifest: {gate_path}")
    return payload


def require_manifested_formal_qualification(
    gate: object,
    config: dict,
    dataset: FormalDataset,
    *,
    allow_nonscientific_fixture: bool,
) -> dict:
    """Validate qualification semantics and authenticate its complete stage output."""
    validated = require_formal_qualification(
        gate,
        config,
        dataset,
        allow_nonscientific_fixture=allow_nonscientific_fixture,
    )
    teacher_parent = Path(str(validated["teacher_checkpoint"])).parent
    stage_dir = teacher_parent.parent if teacher_parent.name == "checkpoints" else teacher_parent
    gate_path = stage_dir / "gate.json"
    return require_stage_manifested_gate(
        gate_path,
        validated,
        config,
        dataset,
        schema_version=QUALIFICATION_SCHEMA,
    )
