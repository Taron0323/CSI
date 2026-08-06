from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from .formal_evidence import bind_rows, evidence_context
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_csv, write_json
from .formal_wrong_map import CONDITIONS
from .formal_resources import validate_resource_registry


ALLOWED_IMPLEMENTATION_STATUS = {
    "official-code-adaptation",
    "paper-spec-controlled-implementation",
    "style-controlled-implementation",
}
REQUIRED_BASELINE_NAMES = {
    "CSI-MAE",
    "CSI-CLIP",
    "CSI-CLIP++",
    "ContraWiMAE",
    "WWM",
    "SigMap",
    "Wi-GATr",
    "WiSER",
    "CSI-only",
    "oracle-x",
    "RFIR",
}
BASELINE_STATUSES = {"executed", "not_executed", "not_applicable", "oracle_only"}
C1_ELIGIBLE_IDENTITIES = {
    "Wi-GATr": "official-code-adaptation",
    "WiSER": "paper-spec-controlled-implementation",
}


def run_external_baselines(config, dataset, manifest_path, output_root):
    from .formal_data_verification import require_verified_roles_from_root

    project_root = Path(__file__).resolve().parents[1]
    resource_registry_path = Path(__file__).resolve().parent / "configs/waibu_resources_v1.json"
    validate_resource_registry(
        read_strict_json(resource_registry_path), project_root / "waibu"
    )
    require_verified_roles_from_root(
        output_root,
        config,
        dataset,
        ("source_final_unseen_bank", "target"),
    )
    manifest = read_strict_json(manifest_path)
    _validate_manifest(manifest)
    output_dir = Path(output_root) / "external_baselines"
    output_dir.mkdir(parents=True, exist_ok=True)
    adapter_manifest_copy = output_dir / "adapter_manifest.json"
    write_json(adapter_manifest_copy, manifest)
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    expected_units = _expected_six_condition_units(
        config, dataset, output_root
    )
    expected_unit_ids = {unit.unit_id for unit in expected_units}
    unit_rows = []
    for unit in expected_units:
        unit_rows.append(
            {
                "unit_id": unit.unit_id,
                "city_id": str(dataset.city_ids[unit.scene]),
                "bank_id": str(dataset.bank_ids[unit.scene]),
                "position_id": str(dataset.position_ids[unit.scene, unit.position]),
                "source_world": unit.source_world,
                "active_world": unit.active_world,
                "null_world": unit.null_world,
                "wrong_city_bank_id": str(dataset.bank_ids[unit.wrong_city_scene]),
                "csi_context_sha256": unit.csi_context_sha256,
                "query_count": 1,
            }
        )
    write_csv(
        output_dir / "external_unit_registry.csv",
        bind_rows(unit_rows, evidence),
    )
    status_rows = []
    all_rows = []
    for adapter in manifest["adapters"]:
        adapter_output = output_dir / "adapters" / adapter["adapter_id"]
        adapter_output.mkdir(parents=True, exist_ok=True)
        command_digest = hashlib.sha256(
            json.dumps(
                adapter["command"], separators=(",", ":"), ensure_ascii=True
            ).encode("utf-8")
        ).hexdigest()
        command = [
            value.format(
                dataset=str(dataset.source_path),
                output=str(adapter_output),
                run_root=str(Path(output_root).resolve()),
                project_root=str(Path(__file__).resolve().parents[1]),
                adapter_command_sha256=command_digest,
                adapter_id=adapter["adapter_id"],
                model_name=adapter["model_name"],
                source_revision=adapter["source_revision"],
            )
            for value in adapter["command"]
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                cwd=Path(__file__).resolve().parents[1],
            )
        except OSError as error:
            completed = subprocess.CompletedProcess(command, 127, "", f"{type(error).__name__}: {error}")
        (adapter_output / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (adapter_output / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        result_path = adapter_output / "six_condition_results.csv"
        if completed.returncode != 0 or not result_path.is_file():
            status_rows.append(
                {
                    "adapter_id": adapter["adapter_id"],
                    "model_name": adapter["model_name"],
                    "implementation_status": adapter["implementation_status"],
                    "c1_eligible": adapter["c1_eligible"],
                    "status": "FAIL",
                    "return_code": completed.returncode,
                }
            )
            continue
        with result_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        _validate_six_condition_rows(
            adapter,
            rows,
            dataset,
            expected_unit_ids=expected_unit_ids,
            expected_unit_contract={unit.unit_id: unit for unit in expected_units},
        )
        _validate_execution_manifest(
            adapter, adapter_output, result_path, dataset
        )
        all_rows.extend(rows)
        status_rows.append(
            {
                "adapter_id": adapter["adapter_id"],
                "model_name": adapter["model_name"],
                "implementation_status": adapter["implementation_status"],
                "c1_eligible": adapter["c1_eligible"],
                "status": "PASS",
                "return_code": completed.returncode,
            }
        )
    write_csv(output_dir / "adapter_status.csv", bind_rows(status_rows, evidence))
    resolved_registry = []
    passed_adapter_ids = {
        row["adapter_id"] for row in status_rows if row["status"] == "PASS"
    }
    for row in manifest["literature_registry"]:
        resolved = dict(row)
        if resolved["status"] == "executed" and resolved["adapter_id"] not in passed_adapter_ids:
            resolved["status"] = "not_executed"
            resolved["reason"] = resolved["reason"] + " Adapter execution did not authenticate in this run."
            resolved["adapter_id"] = ""
        resolved_registry.append(resolved)
    write_csv(output_dir / "literature_baseline_registry.csv", bind_rows(resolved_registry, evidence))
    write_csv(output_dir / "six_condition_results.csv", bind_rows(all_rows, evidence))
    passed_models = {
        row["model_name"] for row in status_rows if row["status"] == "PASS"
    }
    c1_eligible_models = {
        row["model_name"]
        for row in status_rows
        if row["status"] == "PASS" and row["c1_eligible"] is True
    }
    passed = len(c1_eligible_models) >= 2
    gate = {
        "schema_version": "csi-pairs-v6-external-baseline-gate-v2",
        "status": "PASS" if passed else "BLOCKED",
        "passed": passed,
        **evidence,
        "gate_scope": "C1 six-condition domain evidence",
        "passing_map_conditioned_models": len(passed_models),
        "unique_passing_model_count": len(passed_models),
        "unique_passing_models": sorted(passed_models),
        "c1_eligible_model_count": len(c1_eligible_models),
        "c1_eligible_models": sorted(c1_eligible_models),
        "adapter_manifest_sha256": sha256_file(adapter_manifest_copy),
        "adapter_manifest_path": adapter_manifest_copy.name,
        "resource_registry_sha256": sha256_file(resource_registry_path),
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


def _validate_manifest(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "adapters", "literature_registry"}:
        raise ValueError("external adapter manifest fields must be exact")
    if manifest["schema_version"] != "csi-pairs-v6-external-adapters-v2":
        raise ValueError("external adapter manifest schema mismatch")
    adapters = manifest["adapters"]
    if not isinstance(adapters, list) or len(adapters) < 2:
        raise ValueError("at least two external map-conditioned adapters are required")
    seen = set()
    eligible_models = set()
    for adapter in adapters:
        required = {
            "adapter_id",
            "model_name",
            "implementation_status",
            "license_id",
            "citation_key",
            "source_revision",
            "map_conditioned",
            "c1_eligible",
            "command",
        }
        if not isinstance(adapter, dict) or set(adapter) != required:
            raise ValueError("external adapter fields must be exact")
        if adapter["adapter_id"] in seen:
            raise ValueError("external adapter IDs must be unique")
        seen.add(adapter["adapter_id"])
        if adapter["implementation_status"] not in ALLOWED_IMPLEMENTATION_STATUS:
            raise ValueError("external adapter implementation status is inaccurate or unsupported")
        if adapter["map_conditioned"] is not True:
            raise ValueError("C1 adapters must actually be map-conditioned")
        if not isinstance(adapter["c1_eligible"], bool):
            raise ValueError("external adapter c1_eligible must be boolean")
        if adapter["c1_eligible"] and adapter["implementation_status"] == "style-controlled-implementation":
            raise ValueError("style-controlled adapters cannot support C1")
        if adapter["c1_eligible"]:
            expected_status = C1_ELIGIBLE_IDENTITIES.get(adapter["model_name"])
            if expected_status != adapter["implementation_status"]:
                raise ValueError("C1-eligible adapter identity or implementation status is not frozen")
            eligible_models.add(adapter["model_name"])
        if not isinstance(adapter["command"], list) or not adapter["command"]:
            raise ValueError("external adapter command must be a nonempty argv list")
        if not all(isinstance(adapter[key], str) and adapter[key].strip() for key in ("citation_key", "source_revision", "license_id")):
            raise ValueError("external adapter provenance fields must be nonempty")
    if eligible_models != set(C1_ELIGIBLE_IDENTITIES):
        raise ValueError("external manifest must contain both frozen C1-eligible identities")
    registry = manifest["literature_registry"]
    if not isinstance(registry, list) or {row.get("baseline_name") for row in registry} != REQUIRED_BASELINE_NAMES:
        raise ValueError("literature registry must contain every frozen V6 baseline name")
    for row in registry:
        if set(row) != {"baseline_name", "status", "adapter_id", "reason"}:
            raise ValueError("literature baseline registry fields must be exact")
        if row["status"] not in BASELINE_STATUSES:
            raise ValueError("literature baseline registry has an invalid status")
        if row["status"] == "executed" and row["adapter_id"] not in seen:
            raise ValueError("executed literature baseline must reference an adapter")
        if row["status"] != "executed" and row["adapter_id"] != "":
            raise ValueError("unexecuted literature baseline may not claim an adapter")


def _validate_six_condition_rows(
    adapter,
    rows,
    dataset,
    *,
    expected_unit_ids=None,
    expected_unit_contract=None,
):
    if not rows:
        raise ValueError("external adapter emitted no result rows")
    by_unit = {}
    required_columns = {
        "unit_id",
        "model_name",
        "condition",
        "city_id",
        "bank_id",
        "position_id",
        "localization_error_m",
        "csi_context_sha256",
        "query_count",
    }
    for row in rows:
        if set(row) != required_columns:
            raise ValueError("external result columns must be exact")
        if row.get("model_name") != adapter["model_name"]:
            raise ValueError("external result model name does not match its manifest")
        if not row.get("unit_id") or not row.get("bank_id") or not row.get("position_id"):
            raise ValueError("external result unit keys must be nonempty")
        scene_matches = [
            index for index, value in enumerate(dataset.bank_ids.tolist()) if str(value) == row["bank_id"]
        ]
        if len(scene_matches) != 1:
            raise ValueError("external result bank_id is not unique in the current dataset")
        scene = scene_matches[0]
        if row["city_id"] != str(dataset.city_ids[scene]):
            raise ValueError("external result city_id does not match its bank")
        if row["position_id"] not in set(dataset.position_ids[scene].tolist()):
            raise ValueError("external result position_id is absent from its bank")
        position = int(np.flatnonzero(dataset.position_ids[scene] == row["position_id"])[0])
        if str(dataset.scene_roles[scene]) == "target" and str(dataset.position_roles[scene, position]) != "query":
            raise ValueError("external baseline includes target support_pool in its denominator")
        try:
            value = float(row["localization_error_m"])
        except ValueError as error:
            raise ValueError("external localization error must be numeric") from error
        if value < 0:
            raise ValueError("external localization error must be nonnegative")
        by_unit.setdefault(row.get("unit_id"), set()).add(row.get("condition"))
    required = set(CONDITIONS)
    if any(conditions != required for conditions in by_unit.values()):
        raise ValueError("every external unit must contain exactly the six frozen conditions")
    if expected_unit_ids is not None and set(by_unit) != set(expected_unit_ids):
        missing = sorted(set(expected_unit_ids).difference(by_unit))
        unexpected = sorted(set(by_unit).difference(expected_unit_ids))
        raise ValueError(
            "external adapter does not cover the frozen common unit registry: "
            f"missing={missing[:5]}, unexpected={unexpected[:5]}"
        )
    if expected_unit_contract is not None:
        for unit_id, unit in expected_unit_contract.items():
            selected = [row for row in rows if row["unit_id"] == unit_id]
            expected = {
                "city_id": str(dataset.city_ids[unit.scene]),
                "bank_id": str(dataset.bank_ids[unit.scene]),
                "position_id": str(dataset.position_ids[unit.scene, unit.position]),
                "csi_context_sha256": unit.csi_context_sha256,
                "query_count": "1",
            }
            for key, value in expected.items():
                if any(str(row[key]) != value for row in selected):
                    raise ValueError(
                        f"external unit {unit_id!r} changes frozen {key}"
                    )
    for unit_id in by_unit:
        selected = [row for row in rows if row["unit_id"] == unit_id]
        if len({row["csi_context_sha256"] for row in selected}) != 1:
            raise ValueError("six-condition unit changes the frozen CSI/radio context")
        if len({row["query_count"] for row in selected}) != 1:
            raise ValueError("six-condition unit changes the evaluation denominator")
        digest = selected[0]["csi_context_sha256"]
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("external CSI context digest must be lowercase SHA-256")
        if int(selected[0]["query_count"]) <= 0:
            raise ValueError("external query_count must be positive")


def _validate_execution_manifest(adapter, output_dir, result_path, dataset):
    path = output_dir / "execution_manifest.json"
    if not path.is_file():
        raise RuntimeError("external adapter omitted execution_manifest.json")
    payload = read_strict_json(path)
    required = {
        "schema_version",
        "adapter_id",
        "model_name",
        "implementation_status",
        "source_revision",
        "dataset_sha256",
        "adapter_config_path",
        "adapter_config_sha256",
        "training_record_path",
        "training_record_sha256",
        "checkpoint_path",
        "checkpoint_sha256",
        "command_sha256",
        "results_sha256",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise RuntimeError("external execution manifest fields must be exact")
    if payload["schema_version"] != "csi-pairs-v6-external-execution-v2":
        raise RuntimeError("external execution manifest schema mismatch")
    for key in (
        "adapter_id",
        "model_name",
        "implementation_status",
        "source_revision",
    ):
        if payload[key] != adapter[key]:
            raise RuntimeError(f"external execution {key} mismatch")
    if payload["dataset_sha256"] != sha256_file(dataset.source_path):
        raise RuntimeError("external execution dataset hash mismatch")
    command_digest = hashlib.sha256(
        json.dumps(adapter["command"], separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    if payload["command_sha256"] != command_digest:
        raise RuntimeError("external execution command hash mismatch")
    for prefix in ("adapter_config", "training_record", "checkpoint"):
        artifact = (output_dir / payload[f"{prefix}_path"]).resolve()
        if output_dir.resolve() not in artifact.parents or not artifact.is_file():
            raise RuntimeError(f"external {prefix} is missing or escapes adapter output")
        if sha256_file(artifact) != payload[f"{prefix}_sha256"]:
            raise RuntimeError(f"external {prefix} hash mismatch")
    adapter_config = read_strict_json(output_dir / payload["adapter_config_path"])
    if not dataset.is_fixture and adapter_config.get("profile") != "formal-paper-dose":
        raise RuntimeError("scientific external adapter did not use its formal-paper-dose profile")
    training_record = read_strict_json(output_dir / payload["training_record_path"])
    if (
        training_record.get("train_role") != "source_encoder_train"
        or training_record.get("selection_role") != "source_method_selection"
        or training_record.get("target_roles_read") != []
    ):
        raise RuntimeError("external training record violates the source-only role ledger")
    if sha256_file(result_path) != payload["results_sha256"]:
        raise RuntimeError("external result hash mismatch")


def _expected_six_condition_units(config, dataset, output_root):
    from .external_adapters.wigatr_protocol import build_six_condition_units
    from .formal_evidence import require_manifested_formal_qualification
    from .formal_routing import fit_route_normalization, route_dataset
    from .formal_teacher import load_teacher_bundle

    qualification = read_strict_json(
        Path(output_root) / "qualification" / "gate.json"
    )
    qualification = require_manifested_formal_qualification(
        qualification,
        config,
        dataset,
        allow_nonscientific_fixture=True,
    )
    teacher = load_teacher_bundle(qualification["teacher_checkpoint"], config)
    normalization = fit_route_normalization(dataset, teacher)
    scenes = np.concatenate(
        (
            dataset.indices_for_role("source_final_unseen_bank"),
            dataset.indices_for_role("target"),
        )
    )
    routed = route_dataset(
        dataset, teacher, config, scenes, normalization=normalization
    )
    return build_six_condition_units(dataset, routed)
