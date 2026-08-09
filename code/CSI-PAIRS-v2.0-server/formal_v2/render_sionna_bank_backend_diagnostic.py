#!/usr/bin/env python3
"""Render one Sionna bank under an explicitly audited CUDA or LLVM backend."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time
import uuid

import numpy as np

from formal_v2 import sionna_osm_candidate as candidate


CUDA_RUNTIME_RELATIVE = Path("formal_v2/external_adapters/.runtime-sionna/venv")
CUDA_OPTIX_RELATIVE = Path(
    "formal_v2/external_adapters/.runtime-sionna/driver-libs/root/usr/lib/x86_64-linux-gnu"
)
CUDA_DRIVER = Path("/usr/lib/x86_64-linux-gnu/libcuda.so.1")
CUDA_LIBLLVM = Path("/lib/x86_64-linux-gnu/libLLVM-18.so")


def _runtime_versions() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "sionna": importlib.metadata.version("sionna"),
        "sionna_rt": importlib.metadata.version("sionna-rt"),
        "mitsuba": importlib.metadata.version("mitsuba"),
        "drjit": importlib.metadata.version("drjit"),
    }


def _expected_runtime_versions() -> dict[str, str]:
    return {
        "python": candidate.SIONNA_PYTHON_VERSION,
        "sionna": candidate.SIONNA_VERSION,
        "sionna_rt": candidate.SIONNA_RT_VERSION,
        "mitsuba": candidate.MITSUBA_VERSION,
        "drjit": candidate.DRJIT_VERSION,
    }


def _cuda_bootstrap_environment(
    project_root: str | Path,
    current: dict[str, str] | None = None,
    *,
    cuda_driver: str | Path = CUDA_DRIVER,
    libllvm: str | Path = CUDA_LIBLLVM,
) -> tuple[Path, dict[str, str]]:
    """Reproduce the frozen Linux CUDA/OptiX bootstrap without touching LLVM mode."""
    root = Path(project_root).resolve()
    python = root / CUDA_RUNTIME_RELATIVE / "bin" / "python"
    optix = root / CUDA_OPTIX_RELATIVE
    driver_path = Path(cuda_driver)
    llvm_path = Path(libllvm)
    required = {
        "Sionna runtime Python": python,
        "NVIDIA CUDA driver": driver_path,
        "Dr.Jit LLVM library": llvm_path,
        "OptiX driver directory": optix,
        "OptiX library": optix / "libnvoptix.so.1",
    }
    missing = [label for label, path in required.items() if not path.exists()]
    if missing:
        raise RuntimeError("Sionna CUDA prerequisites are missing: " + ", ".join(missing))

    environment = dict(os.environ if current is None else current)
    preload = [value for value in environment.get("LD_PRELOAD", "").split(":") if value]
    driver = str(driver_path)
    environment["LD_PRELOAD"] = ":".join(
        [driver, *[value for value in preload if value != driver]]
    )
    library_path = [
        value for value in environment.get("LD_LIBRARY_PATH", "").split(":") if value
    ]
    optix_text = str(optix)
    environment["LD_LIBRARY_PATH"] = ":".join(
        [optix_text, *[value for value in library_path if value != optix_text]]
    )
    environment["DRJIT_LIBLLVM_PATH"] = str(llvm_path)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    project_text = str(root)
    python_path = [
        value for value in environment.get("PYTHONPATH", "").split(os.pathsep) if value
    ]
    environment["PYTHONPATH"] = os.pathsep.join(
        [project_text, *[value for value in python_path if value != project_text]]
    )
    return python, environment


def _ensure_cuda_runtime(reexec_arguments: list[str]) -> None:
    project_root = Path(candidate.__file__).resolve().parents[1]
    python, environment = _cuda_bootstrap_environment(project_root)
    runtime_prefix = python.parent.parent.resolve()
    preload_entries = os.environ.get("LD_PRELOAD", "").split(":")
    library_entries = os.environ.get("LD_LIBRARY_PATH", "").split(":")
    python_entries = os.environ.get("PYTHONPATH", "").split(os.pathsep)
    correct_python = Path(sys.prefix).resolve() == runtime_prefix
    driver_preloaded = str(CUDA_DRIVER) in preload_entries
    llvm_configured = os.environ.get("DRJIT_LIBLLVM_PATH") == str(CUDA_LIBLLVM)
    optix_configured = str(project_root / CUDA_OPTIX_RELATIVE) in library_entries
    project_importable = str(project_root) in python_entries
    if (
        correct_python
        and driver_preloaded
        and llvm_configured
        and optix_configured
        and project_importable
    ):
        return
    if os.environ.get("CSI_PAIRS_SIONNA_BOOTSTRAPPED") == "1":
        raise RuntimeError(
            "Sionna runtime bootstrap did not activate the fixed Python and CUDA driver"
        )
    environment["CSI_PAIRS_SIONNA_BOOTSTRAPPED"] = "1"
    os.execve(str(python), [str(python), *reexec_arguments], environment)


def _prepare_backend(args: argparse.Namespace, reexec_arguments: list[str]) -> Path | None:
    physical_gpu_index = getattr(args, "physical_gpu_index", None)
    if args.backend == "cuda":
        visible = os.environ.get("CUDA_VISIBLE_DEVICES")
        if physical_gpu_index is None or visible != str(physical_gpu_index):
            raise RuntimeError(
                f"expected CUDA_VISIBLE_DEVICES={physical_gpu_index}, got {visible!r}"
            )
        _ensure_cuda_runtime(reexec_arguments)
        if _runtime_versions() != _expected_runtime_versions():
            raise RuntimeError(
                "CUDA diagnostic runtime versions differ from the frozen Sionna runtime"
            )
        return None
    if args.backend != "llvm":
        raise ValueError(f"unsupported diagnostic backend: {args.backend!r}")
    if physical_gpu_index is not None:
        raise ValueError("--physical-gpu-index is forbidden for the LLVM backend")
    if args.drjit_threads != 1:
        raise ValueError("the LLVM diagnostic requires --drjit-threads=1")
    if _runtime_versions() != _expected_runtime_versions():
        raise RuntimeError(
            "LLVM diagnostic runtime versions differ from the frozen Sionna runtime"
        )
    llvm_value = os.environ.get("DRJIT_LIBLLVM_PATH")
    if not llvm_value:
        raise RuntimeError("DRJIT_LIBLLVM_PATH is required for the LLVM backend")
    llvm_path = Path(llvm_value)
    if not llvm_path.is_absolute() or llvm_path.is_symlink() or not llvm_path.is_file():
        raise RuntimeError("DRJIT_LIBLLVM_PATH must name an absolute regular non-symlink file")
    if not Path(sys.executable).is_file():
        raise RuntimeError("the active fixed Python executable is not a regular file")
    from formal_v2.sionna_runtime_lock import approved_library_record

    approved = approved_library_record(Path(candidate.__file__).resolve().parents[1], llvm_path)
    return Path(approved["libllvm_path"])


def _configure_cuda_renderer(_config: dict) -> None:
    import mitsuba as mi

    expected_variant = "cuda_ad_mono_polarized"
    mi.set_variant(expected_variant)
    if mi.variant() != expected_variant:
        raise RuntimeError("Sionna diagnostic did not activate the CUDA backend")


@contextmanager
def _diagnostic_renderer_configuration(backend: str) -> Iterator[None]:
    if backend == "llvm":
        yield
        return
    if backend != "cuda":
        raise ValueError(f"unsupported diagnostic backend: {backend!r}")
    original = candidate._configure_renderer
    candidate._configure_renderer = _configure_cuda_renderer
    try:
        yield
    finally:
        candidate._configure_renderer = original


def _canonical_path_record(
    surface_ids: np.ndarray,
    delay_s: float,
    interaction_vertices_m: np.ndarray,
    extra: tuple[object, ...],
) -> bytes:
    if hasattr(candidate, "_stable_path_record"):
        return candidate._stable_path_record(
            surface_ids, delay_s, interaction_vertices_m, *extra
        )
    if extra:
        raise RuntimeError("unexpected extra stable path identity fields")
    vertices = np.asarray(interaction_vertices_m, dtype=np.float64)
    quantized_vertices = np.rint(
        vertices / candidate.PATH_VERTEX_QUANTIZATION_M
    ).astype("<i8")
    record = np.concatenate(
        (
            np.asarray(surface_ids, dtype="<i8"),
            np.asarray((int(round(delay_s * 1e12)),), dtype="<i8"),
            quantized_vertices.reshape(-1),
        )
    )
    return record.tobytes()


class _StablePathRecorder:
    def __init__(self) -> None:
        self._original = candidate._stable_path_id
        self._records: Counter[tuple[int, str]] = Counter()

    def __enter__(self) -> "_StablePathRecorder":
        def recorded(
            surface_ids: np.ndarray,
            delay_s: float,
            interaction_vertices_m: np.ndarray,
            *extra: object,
        ) -> int:
            path_id = self._original(
                surface_ids, delay_s, interaction_vertices_m, *extra
            )
            record = _canonical_path_record(
                surface_ids, delay_s, interaction_vertices_m, extra
            )
            expected_id = int.from_bytes(hashlib.sha256(record).digest()[:8], "big") & (
                (1 << 63) - 1
            )
            if path_id != expected_id:
                raise RuntimeError("stable path ID differs from its frozen canonical record")
            self._records[(path_id, record.hex())] += 1
            return path_id

        candidate._stable_path_id = recorded
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        candidate._stable_path_id = self._original

    def payload(self) -> dict[str, object]:
        records = [
            {
                "path_id": path_id,
                "canonical_record_hex": record_hex,
                "canonical_record_sha256": hashlib.sha256(
                    bytes.fromhex(record_hex)
                ).hexdigest(),
                "occurrences": count,
            }
            for (path_id, record_hex), count in sorted(self._records.items())
        ]
        return {
            "schema_version": "csi-pairs-stable-path-signature-capture-v1",
            "simulation_not_measurement": True,
            "scientific_use": "DIAGNOSTIC_NOT_FORMAL_EVIDENCE",
            "canonical_definition_source": str(Path(candidate.__file__).resolve()),
            "canonical_definition_sha256": candidate.sha256_file(
                Path(candidate.__file__).resolve()
            ),
            "unique_id_record_pairs": len(records),
            "total_calls": int(sum(self._records.values())),
            "records": records,
        }


def _llvm_runtime_record(llvm_path: Path, mi, dr) -> dict[str, object]:
    return {
        **_runtime_versions(),
        "backend": "llvm",
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "python_executable": str(Path(sys.executable).resolve()),
        "mitsuba_variant": mi.variant(),
        "drjit_thread_count": int(dr.thread_count()),
        "drjit_libllvm_path": str(llvm_path),
        "drjit_libllvm_sha256": candidate.sha256_file(llvm_path),
        "python_dont_write_bytecode": bool(sys.dont_write_bytecode),
    }


def _cuda_runtime_record(mi, dr) -> dict[str, object]:
    project_root = Path(candidate.__file__).resolve().parents[1]
    optix_library = project_root / CUDA_OPTIX_RELATIVE / "libnvoptix.so.1"
    return {
        **_runtime_versions(),
        "backend": "cuda",
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "python_executable": str(Path(sys.executable).resolve()),
        "mitsuba_variant": mi.variant(),
        "drjit_thread_count": int(dr.thread_count()),
        "cuda_driver_preload": str(CUDA_DRIVER),
        "cuda_driver_sha256": candidate.sha256_file(CUDA_DRIVER),
        "drjit_libllvm_path": str(CUDA_LIBLLVM),
        "drjit_libllvm_sha256": candidate.sha256_file(CUDA_LIBLLVM),
        "optix_library_path": str(optix_library),
        "optix_library_sha256": candidate.sha256_file(optix_library),
        "python_dont_write_bytecode": bool(sys.dont_write_bytecode),
    }


def _asset_manifest_record(root: Path) -> dict[str, str]:
    manifest = (root / "asset_manifest.json").resolve()
    return {
        "asset_manifest_path": str(manifest),
        "asset_manifest_sha256": candidate.sha256_file(manifest),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--scene-index", type=int, required=True)
    parser.add_argument("--backend", choices=("cuda", "llvm"), required=True)
    parser.add_argument("--drjit-threads", type=int)
    parser.add_argument("--physical-gpu-index", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.output.with_suffix(".manifest.json")
    signatures_path = args.output.with_suffix(".path_signatures.json")
    if args.output.exists() or manifest_path.exists() or signatures_path.exists():
        raise FileExistsError(f"refusing to overwrite diagnostic output {args.output}")

    llvm_path = _prepare_backend(args, [__file__, *sys.argv[1:]])
    import mitsuba as mi

    mi.set_variant(f"{args.backend}_ad_mono_polarized")
    import drjit as dr

    if args.drjit_threads is not None:
        if args.backend != "llvm" or args.drjit_threads < 1:
            raise ValueError("--drjit-threads requires LLVM and a positive count")
        dr.set_thread_count(args.drjit_threads)
    import sionna.rt  # noqa: F401

    root, manifest, config = candidate.load_asset_manifest(args.asset_root)
    if not 0 <= args.scene_index < len(manifest["banks"]):
        raise ValueError("scene index is out of range")
    bank_row = manifest["banks"][args.scene_index]
    bank = candidate._read_json(root / str(bank_row["bank_record_path"]))
    started_utc = datetime.now(timezone.utc)
    started = time.monotonic()
    with _diagnostic_renderer_configuration(args.backend), _StablePathRecorder() as recorder:
        rendered = candidate.render_bank(bank, root, config, args.scene_index)
    duration = time.monotonic() - started
    ended_utc = datetime.now(timezone.utc)
    arrays = {
        "scene_indices": np.asarray((args.scene_index,), dtype=np.int64),
        **{name: np.asarray(value)[None, ...] for name, value in rendered.items()},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    candidate._write_npz_exclusive(args.output, arrays)
    candidate._write_json_exclusive(signatures_path, recorder.payload())
    tool_path = Path(__file__).resolve()
    runtime = (
        _llvm_runtime_record(llvm_path, mi, dr)
        if args.backend == "llvm"
        else _cuda_runtime_record(mi, dr)
    )
    payload = {
        "schema_version": "csi-pairs-sionna-bank-backend-diagnostic-v2",
        "status": "DIAGNOSTIC_NOT_FORMAL_EVIDENCE",
        "scientific_use": "DIAGNOSTIC_NOT_FORMAL_EVIDENCE",
        "simulation_not_measurement": True,
        "fixture": False,
        "run_id": uuid.uuid4().hex,
        "process_id": os.getpid(),
        "parent_process_id": os.getppid(),
        "started_utc": started_utc.isoformat(),
        "ended_utc": ended_utc.isoformat(),
        "duration_seconds": duration,
        "backend": args.backend,
        "mitsuba_variant": mi.variant(),
        "drjit_thread_count": int(dr.thread_count()),
        "scene_index": args.scene_index,
        "scene_id": bank_row["scene_id"],
        "asset_root": str(root),
        **_asset_manifest_record(root),
        "output_path": str(args.output.resolve()),
        "output_bytes": args.output.stat().st_size,
        "output_sha256": candidate.sha256_file(args.output),
        "path_signatures_path": str(signatures_path.resolve()),
        "path_signatures_sha256": candidate.sha256_file(signatures_path),
        "runtime": runtime,
        "generator_path": str(Path(candidate.__file__).resolve()),
        "generator_sha256": candidate.sha256_file(Path(candidate.__file__).resolve()),
        "tool_path": str(tool_path),
        "tool_sha256": candidate.sha256_file(tool_path),
        "argv": [str(Path(sys.executable)), *sys.argv],
    }
    if args.backend == "cuda":
        payload["cuda_visible_devices"] = os.environ.get("CUDA_VISIBLE_DEVICES")
        payload["physical_gpu_index"] = args.physical_gpu_index
    candidate._write_json_exclusive(manifest_path, payload)
    print(json.dumps({"output": str(args.output.resolve()), "status": payload["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
