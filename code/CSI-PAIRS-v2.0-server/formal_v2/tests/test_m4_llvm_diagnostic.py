from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from formal_v2 import render_sionna_bank_backend_diagnostic as diagnostic


class M4LLVMBackendDiagnosticTests(unittest.TestCase):
    def test_llvm_path_requires_fixed_llvm_inputs_without_cuda(self):
        args = argparse.Namespace(
            backend="llvm", drjit_threads=1
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

    def test_cuda_backend_is_not_exposed_as_an_authenticated_diagnostic(self):
        args = argparse.Namespace(backend="cuda", drjit_threads=None)
        with self.assertRaisesRegex(ValueError, "only the LLVM backend"):
            diagnostic._prepare_backend(args, ["diagnostic.py"])


if __name__ == "__main__":
    unittest.main()
