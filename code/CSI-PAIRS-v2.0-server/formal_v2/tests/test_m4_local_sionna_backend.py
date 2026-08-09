from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest

from formal_v2.sionna_osm_candidate import (
    SIONNA_OPTIX_RELATIVE,
    SIONNA_RUNTIME_RELATIVE,
    _sionna_bootstrap_environment,
)


class M4LocalSionnaBackendTests(unittest.TestCase):
    def test_cuda_bootstrap_preserves_linux_driver_and_optix_requirements(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            python_path = project / SIONNA_RUNTIME_RELATIVE / "bin/python"
            optix = project / SIONNA_OPTIX_RELATIVE
            driver = project / "libcuda.so.1"
            llvm = project / "libLLVM-18.so"
            python_path.parent.mkdir(parents=True)
            for path in (python_path, llvm):
                path.touch()

            with self.assertRaisesRegex(
                RuntimeError,
                "NVIDIA CUDA driver.*OptiX driver directory.*OptiX library",
            ):
                _sionna_bootstrap_environment(
                    project,
                    backend="cuda",
                    cuda_driver=driver,
                    libllvm=llvm,
                )

            optix.mkdir(parents=True)
            for path in (driver, optix / "libnvoptix.so.1"):
                path.touch()
            python, environment = _sionna_bootstrap_environment(
                project,
                {
                    "LD_PRELOAD": "/tmp/existing-preload.so",
                    "LD_LIBRARY_PATH": "/tmp/existing-library-path",
                    "PYTHONPATH": "/tmp/python",
                },
                backend="cuda",
                cuda_driver=driver,
                libllvm=llvm,
            )

        self.assertEqual(python, python_path)
        self.assertEqual(environment["LD_PRELOAD"].split(":")[0], str(driver))
        self.assertEqual(environment["LD_LIBRARY_PATH"].split(":")[0], str(optix))
        self.assertEqual(environment["DRJIT_LIBLLVM_PATH"], str(llvm))
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(environment["PYTHONPATH"].split(os.pathsep)[0], str(project))

    def test_llvm_bootstrap_uses_current_python_without_cuda_or_optix(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            llvm = project / "libLLVM.dylib"
            llvm.touch()
            python, environment = _sionna_bootstrap_environment(
                project,
                {
                    "LD_PRELOAD": "/tmp/unchanged-preload.so",
                    "LD_LIBRARY_PATH": "/tmp/unchanged-library-path",
                    "PYTHONPATH": "/tmp/python",
                },
                backend="llvm",
                libllvm=llvm,
            )

        self.assertEqual(python, Path(sys.executable))
        self.assertEqual(environment["DRJIT_LIBLLVM_PATH"], str(llvm.resolve()))
        self.assertEqual(environment["LD_PRELOAD"], "/tmp/unchanged-preload.so")
        self.assertEqual(
            environment["LD_LIBRARY_PATH"], "/tmp/unchanged-library-path"
        )
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(environment["PYTHONPATH"].split(os.pathsep)[0], str(project))


if __name__ == "__main__":
    unittest.main()
