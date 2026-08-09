from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from formal_v2 import render_sionna_bank_backend_diagnostic as diagnostic


class M4LLVMBackendDiagnosticTests(unittest.TestCase):
    def test_asset_manifest_record_binds_digest_to_absolute_path(self):
        payload = b'{"schema_version":"asset-test"}\n'
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "asset_manifest.json"
            manifest.write_bytes(payload)
            record = diagnostic._asset_manifest_record(Path(temporary))
        self.assertEqual(record["asset_manifest_path"], str(manifest.resolve()))
        self.assertEqual(
            record["asset_manifest_sha256"], hashlib.sha256(payload).hexdigest()
        )

    def test_llvm_path_requires_fixed_llvm_inputs_without_cuda(self):
        registry = diagnostic.candidate._read_json(
            Path(diagnostic.__file__).resolve().parent
            / "configs/sionna_llvm_approved_v1.json"
        )
        registered = {
            (row["sha256"], row["provenance"]) for row in registry["libraries"]
        }
        self.assertIn(
            (
                "26273678e919e90006fe2f5fc6e020cfc11a428103494d4dad6fa211b5d50451",
                "M4 LLVM 18.1.8 Homebrew arm64 scene-0 two-process exact replay audited on 2026-08-09",
            ),
            registered,
        )
        self.assertIn(
            (
                "e514c689a4469887f30396826cec7559ad6ddc1d9db1a0b243790bee7725ca88",
                "M4 LLVM 22.1.8 diagnostic runtime audited on 2026-08-09",
            ),
            registered,
        )
        args = argparse.Namespace(
            backend="llvm", drjit_threads=1, physical_gpu_index=None
        )
        with tempfile.TemporaryDirectory() as temporary:
            llvm_path = Path(temporary) / "libLLVM.dylib"
            llvm_path.touch()
            environment = {"DRJIT_LIBLLVM_PATH": str(llvm_path)}
            with (
                patch.dict(os.environ, environment, clear=True),
                patch.object(
                    diagnostic, "_runtime_versions",
                    return_value=diagnostic._expected_runtime_versions(),
                ),
                patch(
                    "formal_v2.sionna_runtime_lock.approved_library_record",
                    return_value={"libllvm_path": str(llvm_path.resolve())},
                ),
                patch.object(
                    diagnostic.candidate,
                    "ensure_sionna_runtime",
                    side_effect=AssertionError("LLVM must not bootstrap CUDA"),
                ),
            ):
                self.assertEqual(
                    diagnostic._prepare_backend(args, ["diagnostic.py"]),
                    llvm_path.resolve(),
                )

    def test_cuda_path_preserves_visibility_and_runtime_bootstrap_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            python = project / diagnostic.CUDA_RUNTIME_RELATIVE / "bin/python"
            optix = project / diagnostic.CUDA_OPTIX_RELATIVE
            driver = project / "libcuda.so.1"
            llvm = project / "libLLVM-18.so"
            for path in (python, optix / "libnvoptix.so.1", driver, llvm):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            current = {
                "LD_PRELOAD": "/existing/preload.so",
                "LD_LIBRARY_PATH": "/existing/lib",
                "PYTHONPATH": "/existing/python",
            }
            resolved_python, environment = diagnostic._cuda_bootstrap_environment(
                project,
                current,
                cuda_driver=driver,
                libllvm=llvm,
            )
            self.assertEqual(resolved_python, python.resolve())
            self.assertEqual(
                environment["LD_PRELOAD"], f"{driver}:/existing/preload.so"
            )
            self.assertEqual(
                environment["LD_LIBRARY_PATH"], f"{optix.resolve()}:/existing/lib"
            )
            self.assertEqual(environment["DRJIT_LIBLLVM_PATH"], str(llvm))
            self.assertEqual(
                environment["PYTHONPATH"], f"{project.resolve()}:/existing/python"
            )

        args = argparse.Namespace(
            backend="cuda", drjit_threads=None, physical_gpu_index=2
        )
        with (
            patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": "2"}, clear=True),
            patch.object(diagnostic, "_ensure_cuda_runtime") as ensure,
            patch.object(
                diagnostic,
                "_runtime_versions",
                return_value=diagnostic._expected_runtime_versions(),
            ),
        ):
            self.assertIsNone(diagnostic._prepare_backend(args, ["diagnostic.py"]))
            ensure.assert_called_once_with(["diagnostic.py"])
        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": "1"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "CUDA_VISIBLE_DEVICES=2"):
                diagnostic._prepare_backend(args, ["diagnostic.py"])

    def test_cuda_renderer_dispatch_does_not_fall_back_to_formal_llvm_config(self):
        calls = []
        fake_mitsuba = SimpleNamespace(
            set_variant=lambda variant: calls.append(variant),
            variant=lambda: calls[-1],
        )
        original = diagnostic.candidate._configure_renderer
        with (
            patch.dict(sys.modules, {"mitsuba": fake_mitsuba}),
            diagnostic._diagnostic_renderer_configuration("cuda"),
        ):
            self.assertIs(
                diagnostic.candidate._configure_renderer,
                diagnostic._configure_cuda_renderer,
            )
            diagnostic.candidate._configure_renderer(
                {"renderer": {"mitsuba_variant": "llvm_ad_mono_polarized"}}
            )
        self.assertIs(diagnostic.candidate._configure_renderer, original)
        self.assertEqual(calls, ["cuda_ad_mono_polarized"])

        with diagnostic._diagnostic_renderer_configuration("llvm"):
            self.assertIs(diagnostic.candidate._configure_renderer, original)


if __name__ == "__main__":
    unittest.main()
