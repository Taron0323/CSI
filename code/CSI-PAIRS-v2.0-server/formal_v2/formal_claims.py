from __future__ import annotations

from pathlib import Path

from .formal_evidence import (
    CLAIM_IDS,
    GATE_IDS,
    blocked_claim_vector,
    evidence_context,
    require_stage_manifested_gate,
)
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_json


CLAIM_DEPENDENCIES = {
    "C1": ("external_baselines",),
    "C2": ("scene_id_mechanism",),
    "C3": ("G1_G2", "G3"),
    "C4": ("G1_G2", "G3", "shuffled_pair"),
    "C5": ("G1_G2", "G3"),
    "C6": ("G1_G2", "G3", "retention"),
    "C7": ("G1_G2", "G3", "G4", "G5"),
    "C8": ("G1_G2", "G5"),
    "C9": ("G1_G2", "G3", "G6"),
    "C10": ("G1_G2", "G3", "G7"),
    "C11": ("rt_calibration",),
    "C12": ("G8",),
    "C13": ("G0",),
}


STAGE_SPECS = {
    "G0": ("literature_resources/gate.json", "csi-pairs-v6-literature-resource-gate-v1"),
    "G1_G2": ("qualification/gate.json", "csi-pairs-formal-qualification-gate-v2.1-v6"),
    "G3": ("evaluation/gate.json", "csi-pairs-v6-evaluation-gate-v2"),
    "G4": ("controls/gate.json", "csi-pairs-v6-resource-control-gate-v2"),
    "G5": ("factorial/gate.json", "csi-pairs-formal-factorial-gate-v2.1-v6"),
    "G6": ("risk/gate.json", "csi-pairs-v6-risk-gate-v2"),
    "G7": ("path/gate.json", "csi-pairs-v6-path-gate-v3"),
    "G8": ("external_validity/gate.json", "csi-pairs-v6-external-validity-gate-v1"),
    "external_baselines": (
        "external_baselines/gate.json",
        "csi-pairs-v6-external-baseline-gate-v2",
    ),
    "scene_id_mechanism": ("scene_id/gate.json", "csi-pairs-v6-scene-id-gate-v1"),
    "shuffled_pair": (
        "controls/shuffled_pair/gate.json",
        "csi-pairs-v6-shuffled-pair-gate-v2",
    ),
    "retention": (
        "evaluation/retention/gate.json",
        "csi-pairs-v6-retention-gate-v2",
    ),
    "rt_calibration": (
        "qualification/rt_calibration/gate.json",
        "csi-pairs-v6-rt-calibration-gate-v1",
    ),
}


def assemble_claim_evidence(config, dataset, output_root):
    root = Path(output_root)
    output_dir = root / "claims"
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    assessments = {}
    errors = {}
    for name, (relative, schema) in STAGE_SPECS.items():
        status, error = _assess_stage(root / relative, schema, name, config, dataset)
        assessments[name] = status
        if error is not None:
            errors[name] = error

    gates = {gate_id: "NOT_ASSESSED" for gate_id in GATE_IDS}
    gates["G0"] = _gate_state(assessments["G0"])
    qualification = assessments["G1_G2"]
    if qualification == "PASS":
        gates["G1"] = "PASS"
        gates["G2"] = "PASS"
    elif qualification in {"FAIL", "INVALID"}:
        gates["G1"] = "FAIL"
        gates["G2"] = "FAIL"
    for gate_id in ("G3", "G4", "G5", "G6", "G7", "G8"):
        gates[gate_id] = _gate_state(assessments[gate_id])

    claims = blocked_claim_vector()
    for claim_id in CLAIM_IDS:
        statuses = [
            assessments[value] if value in assessments else "NOT_ASSESSED"
            for value in CLAIM_DEPENDENCIES[claim_id]
        ]
        if any(value in {"FAIL", "INVALID"} for value in statuses):
            claims[claim_id] = "INVALID"
        elif all(value == "PASS" for value in statuses):
            claims[claim_id] = "SOFTWARE_ONLY" if dataset.is_fixture else "SUPPORTED"
        else:
            claims[claim_id] = "BLOCKED"

    all_required_assessed = all(value in {"PASS", "FAIL"} for value in gates.values())
    result = {
        "schema_version": "csi-pairs-v6-claim-evidence-v2",
        "status": "COMPLETE" if all_required_assessed and not errors else "INCOMPLETE_FAIL_CLOSED",
        **evidence,
        "gate_vector": gates,
        "claim_vector": claims,
        "stage_assessments": assessments,
        "evidence_errors": errors,
        "claim_dependencies": {key: list(value) for key, value in CLAIM_DEPENDENCIES.items()},
        "rule": (
            "Only exact-schema, stage-manifested, semantically complete evidence can become PASS. "
            "Missing, malformed, BLOCKED, or NOT_ASSESSED evidence cannot support a claim."
        ),
    }
    write_json(output_dir / "claim_evidence.json", result)
    write_json(
        output_dir / "manifest.json",
        {
            "schema_version": "csi-pairs-formal-stage-manifest-v2.1-v6",
            **evidence,
            "files": artifact_manifest(output_dir, evidence=evidence),
        },
    )
    return result


def _assess_stage(path, schema, name, config, dataset):
    if not path.is_file():
        return "NOT_ASSESSED", None
    try:
        payload = read_strict_json(path)
        require_stage_manifested_gate(
            path,
            payload,
            config,
            dataset,
            schema_version=schema,
        )
        if name == "external_baselines":
            _validate_external_manifest_binding(path, payload)
        return _semantic_status(name, payload), None
    except Exception as error:
        return "INVALID", f"{type(error).__name__}: {error}"


def _semantic_status(name, payload):
    if name == "G1_G2":
        vector = payload.get("upstream_gates")
        if not isinstance(vector, dict):
            raise RuntimeError("qualification gate lacks upstream_gates")
        return "PASS" if vector.get("G1") == vector.get("G2") == "PASS" and payload.get("passed") is True else "FAIL"
    if name == "G3":
        if not _require_pass_subgates(payload, "g3_subgates", 8):
            return "FAIL"
        if payload.get("c3_evidence_complete") is not True or payload.get("c5_evidence_complete") is not True:
            return "FAIL"
    elif name == "G4":
        if not _require_pass_subgates(payload, "g4_subgates", 7):
            return "FAIL"
    elif name == "G5":
        if not _require_pass_subgates(payload, "g5_subgates", 4):
            return "FAIL"
    elif name == "G6":
        if not _require_pass_subgates(payload, "c9_subgates", 4):
            return "FAIL"
    elif name == "G7":
        if not _require_pass_subgates(payload, "g7_subgates", 5):
            return "FAIL"
    elif name == "external_baselines":
        eligible = payload.get("c1_eligible_models")
        if (
            not isinstance(eligible, list)
            or len(eligible) != len(set(eligible))
            or int(payload.get("c1_eligible_model_count", 0)) != len(eligible)
            or set(eligible) != {"Wi-GATr", "WiSER"}
            or not _lower_sha256(payload.get("adapter_manifest_sha256"))
            or payload.get("adapter_manifest_path") != "adapter_manifest.json"
        ):
            return "FAIL"
    elif name in {"shuffled_pair", "retention"}:
        if not payload.get("checkpoint_hashes_verified"):
            return "FAIL"
    if payload.get("passed") is True and payload.get("status") == "PASS":
        return "PASS"
    if payload.get("passed") is False or payload.get("status") in {"FAIL", "BLOCKED"}:
        return "FAIL"
    raise RuntimeError(f"stage {name} has no unambiguous PASS/FAIL result")


def _require_pass_subgates(payload, field, count):
    values = payload.get(field)
    if not isinstance(values, dict) or len(values) != int(count):
        raise RuntimeError(f"{field} must contain exactly {count} entries")
    if any(value not in {"PASS", "FAIL"} for value in values.values()):
        raise RuntimeError(f"{field} contains an unassessed state")
    if any(value != "PASS" for value in values.values()):
        return False
    return True


def _lower_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_external_manifest_binding(gate_path, payload):
    from .formal_external import _validate_manifest

    manifest_path = gate_path.parent / str(payload.get("adapter_manifest_path", ""))
    if not manifest_path.is_file():
        raise RuntimeError("external-baseline gate has no bound adapter manifest")
    if sha256_file(manifest_path) != payload.get("adapter_manifest_sha256"):
        raise RuntimeError("external-baseline adapter manifest hash mismatch")
    stage_manifest_path = gate_path.parent / "manifest.json"
    stage_manifest = read_strict_json(stage_manifest_path)
    entries = stage_manifest.get("files") if isinstance(stage_manifest, dict) else None
    matches = [
        row
        for row in entries
        if isinstance(row, dict) and row.get("path") == manifest_path.name
    ] if isinstance(entries, list) else []
    if len(matches) != 1 or matches[0].get("sha256") != payload.get("adapter_manifest_sha256"):
        raise RuntimeError("external adapter manifest is absent from or mismatched with the stage manifest")
    _validate_manifest(read_strict_json(manifest_path))


def _gate_state(status):
    if status == "PASS":
        return "PASS"
    if status in {"FAIL", "INVALID"}:
        return "FAIL" if status == "FAIL" else "BLOCKED"
    return "NOT_ASSESSED"
