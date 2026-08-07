from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from functools import lru_cache
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
EVIDENCE_AUTH_KEYS = (
    "artifact_label",
    "dataset_sha256",
    "config_sha256",
    "fixture",
    "source_tree_sha256",
    "requirements_lock_sha256",
    "runtime_provenance_sha256",
    "runtime_provenance",
)


def config_sha256(config: dict) -> str:
    payload = json.dumps(
        public_formal_config(config),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def configure_reproducible_runtime() -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    try:
        import torch
    except ImportError:
        runtime_provenance.cache_clear()
        return
    torch.use_deterministic_algorithms(True)
    torch.set_float32_matmul_precision("highest")
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.allow_tf32 = False
    if hasattr(torch.backends, "cuda") and hasattr(torch.backends.cuda, "matmul"):
        torch.backends.cuda.matmul.allow_tf32 = False
    runtime_provenance.cache_clear()


@lru_cache(maxsize=1)
def runtime_provenance() -> dict[str, object]:
    requirements = Path(__file__).resolve().parent / "requirements-lock.txt"
    distributions = {}
    if requirements.is_file():
        for line in requirements.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#") or "==" not in line:
                continue
            name = line.split("==", 1)[0]
            try:
                distribution = importlib.metadata.distribution(name)
                record = distribution.read_text("RECORD")
                distributions[name] = {
                    "version": distribution.version,
                    "record_sha256": (
                        hashlib.sha256(record.encode("utf-8")).hexdigest()
                        if record is not None
                        else None
                    ),
                }
            except importlib.metadata.PackageNotFoundError:
                distributions[name] = {"version": None, "record_sha256": None}
    torch_record = {
        "version": None,
        "cuda_version": None,
        "cuda_available": False,
        "gpu_names": [],
        "deterministic_algorithms": False,
        "cudnn_benchmark": None,
        "cudnn_deterministic": None,
        "cudnn_allow_tf32": None,
        "cuda_matmul_allow_tf32": None,
    }
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        torch_record.update(
            {
                "version": str(torch.__version__),
                "cuda_version": str(torch.version.cuda) if torch.version.cuda else None,
                "cuda_available": cuda_available,
                "gpu_names": (
                    [
                        str(torch.cuda.get_device_name(index))
                        for index in range(torch.cuda.device_count())
                    ]
                    if cuda_available
                    else []
                ),
                "deterministic_algorithms": bool(
                    torch.are_deterministic_algorithms_enabled()
                ),
                "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
                "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
                "cudnn_allow_tf32": bool(torch.backends.cudnn.allow_tf32),
                "cuda_matmul_allow_tf32": bool(
                    torch.backends.cuda.matmul.allow_tf32
                ),
            }
        )
    except ImportError:
        pass
    return {
        "schema_version": "csi-pairs-runtime-provenance-v1",
        "source_tree_sha256": _source_tree_sha256(),
        "requirements_lock_sha256": (
            sha256_file(requirements) if requirements.is_file() else None
        ),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable_name": Path(sys.executable).name,
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "platform_machine": platform.machine(),
        "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
        "torch": torch_record,
        "installed_distributions": distributions,
    }


def _source_tree_sha256() -> str:
    root = Path(__file__).resolve().parent
    included_suffixes = {
        ".py", ".json", ".sh", ".txt", ".toml", ".lock", ".yaml", ".yml"
    }
    digest = hashlib.sha256()
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in included_suffixes
        and not any(
            part.startswith(".venv-") or part.startswith(".runtime-")
            for part in path.relative_to(root).parts
        )
        and "__pycache__" not in path.parts
    )
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def evidence_context(config: dict, dataset: FormalDataset, scientific_use: str) -> dict[str, object]:
    ceiling = "FORBIDDEN" if dataset.is_fixture else scientific_use
    runtime = runtime_provenance()
    runtime_payload = json.dumps(
        runtime,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return {
        "artifact_label": config["artifact_label"],
        "dataset_sha256": sha256_file(dataset.source_path),
        "config_sha256": config_sha256(config),
        "fixture": dataset.is_fixture,
        "scientific_use": ceiling,
        "source_tree_sha256": runtime["source_tree_sha256"],
        "requirements_lock_sha256": runtime["requirements_lock_sha256"],
        "runtime_provenance_sha256": hashlib.sha256(runtime_payload).hexdigest(),
        "runtime_provenance": runtime,
    }


def bind_rows(rows: Iterable[dict], evidence: dict[str, object]) -> list[dict]:
    output = []
    for source in rows:
        row = dict(source)
        for key, value in evidence.items():
            if isinstance(value, (dict, list)):
                continue
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
        "artifact_label",
        "source_tree_sha256",
        "requirements_lock_sha256",
        "runtime_provenance_sha256",
        "runtime_provenance",
    }
    missing = required.difference(gate)
    if missing:
        raise RuntimeError(f"qualification gate is missing authenticated fields: {sorted(missing)}")
    if gate["schema_version"] != QUALIFICATION_SCHEMA:
        raise RuntimeError("qualification gate schema is not V6-compatible")
    expected = evidence_context(config, dataset, str(gate["scientific_use"]))
    for key in EVIDENCE_AUTH_KEYS:
        if gate[key] != expected[key]:
            raise RuntimeError(f"qualification gate {key} does not match the current run")
    software_fixture_execution = bool(
        dataset.is_fixture
        and allow_nonscientific_fixture
        and gate["scientific_use"] == "FORBIDDEN"
    )
    if not bool(gate["passed"]) and not software_fixture_execution:
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
        if (
            gate_id in {"G1", "G2"}
            and status != "PASS"
            and not software_fixture_execution
        ):
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
    for key in EVIDENCE_AUTH_KEYS:
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
    for key in EVIDENCE_AUTH_KEYS:
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
