from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from formal_v2.formal_runtime_integrity import (
    canonical_manifest_bytes,
    reviewed_wheel_manifest,
    validate_installed_wheel_closure,
)


def _record_hash(payload: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()


class RuntimeIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.prefix = self.root / "venv"
        self.site = self.prefix / "lib" / "site-packages"
        self.wheelhouse = self.prefix / "csi-pairs-reviewed-wheels"
        self.site.mkdir(parents=True)
        self.wheelhouse.mkdir()
        self.members = {
            "example/__init__.py": b"VALUE = 1\n",
            "example-1.0.dist-info/METADATA": b"Metadata-Version: 2.1\nName: example\nVersion: 1.0\n\n",
            "example-1.0.dist-info/WHEEL": (
                b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
            ),
        }
        rows = [
            [name, f"sha256={_record_hash(payload)}", str(len(payload))]
            for name, payload in self.members.items()
        ]
        rows.append(["example-1.0.dist-info/RECORD", "", ""])
        stream = io.StringIO()
        csv.writer(stream, lineterminator="\n").writerows(rows)
        self.record = stream.getvalue().encode()
        self.members["example-1.0.dist-info/RECORD"] = self.record
        self.wheel = self.wheelhouse / "example-1.0-py3-none-any.whl"
        with zipfile.ZipFile(self.wheel, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in self.members.items():
                archive.writestr(name, payload)
        self.expected = {
            "example": {
                "version": "1.0",
                "hashes": (hashlib.sha256(self.wheel.read_bytes()).hexdigest(),),
            }
        }
        for name, payload in self.members.items():
            destination = self.site / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        dist_info = self.site / "example-1.0.dist-info"
        (dist_info / "INSTALLER").write_bytes(b"pip\n")
        (dist_info / "REQUESTED").write_bytes(b"")
        self.manifest_path = self.prefix / "csi-pairs-reviewed-wheel-manifest.json"
        manifest = reviewed_wheel_manifest(self.wheelhouse, self.expected, "a" * 64)
        self.manifest_path.write_bytes(canonical_manifest_bytes(manifest))

    def tearDown(self):
        self.temporary.cleanup()

    def validate(self, names=("example",)):
        return validate_installed_wheel_closure(
            self.prefix,
            self.wheelhouse,
            self.manifest_path,
            self.expected,
            "a" * 64,
            site_roots={"purelib": self.site, "platlib": self.site},
            observed_distribution_names=names,
        )

    def test_reviewed_wheel_closure_accepts_exact_install(self):
        result = self.validate()
        self.assertEqual(set(result["record_digests"]), {"example"})

    def test_nested_vendored_dist_info_is_not_mistaken_for_wheel_metadata(self):
        nested = {
            "example/_vendor/helper-2.0.dist-info/METADATA": (
                b"Metadata-Version: 2.1\nName: helper\nVersion: 2.0\n\n"
            ),
            "example/_vendor/helper-2.0.dist-info/WHEEL": (
                b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
            ),
            "example/_vendor/helper-2.0.dist-info/RECORD": b"vendored metadata\n",
        }
        self.members.update(nested)
        rows = [
            [name, f"sha256={_record_hash(payload)}", str(len(payload))]
            for name, payload in self.members.items()
            if name != "example-1.0.dist-info/RECORD"
        ]
        rows.append(["example-1.0.dist-info/RECORD", "", ""])
        stream = io.StringIO()
        csv.writer(stream, lineterminator="\n").writerows(rows)
        self.members["example-1.0.dist-info/RECORD"] = stream.getvalue().encode()
        with zipfile.ZipFile(self.wheel, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in self.members.items():
                archive.writestr(name, payload)
        for name, payload in nested.items():
            destination = self.site / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        (self.site / "example-1.0.dist-info" / "RECORD").write_bytes(
            self.members["example-1.0.dist-info/RECORD"]
        )
        self.expected["example"]["hashes"] = (
            hashlib.sha256(self.wheel.read_bytes()).hexdigest(),
        )
        manifest = reviewed_wheel_manifest(self.wheelhouse, self.expected, "a" * 64)
        self.manifest_path.write_bytes(canonical_manifest_bytes(manifest))

        result = self.validate()
        self.assertEqual(set(result["record_digests"]), {"example"})

    def test_wheel_data_files_are_bound_outside_site_packages(self):
        archive_name = "example-1.0.data/data/share/example.txt"
        payload = b"wheel-owned data\n"
        self.members[archive_name] = payload
        rows = [
            [name, f"sha256={_record_hash(content)}", str(len(content))]
            for name, content in self.members.items()
            if name != "example-1.0.dist-info/RECORD"
        ]
        rows.append(["example-1.0.dist-info/RECORD", "", ""])
        stream = io.StringIO()
        csv.writer(stream, lineterminator="\n").writerows(rows)
        self.members["example-1.0.dist-info/RECORD"] = stream.getvalue().encode()
        with zipfile.ZipFile(self.wheel, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in self.members.items():
                archive.writestr(name, content)
        installed_data = self.prefix / "share" / "example.txt"
        installed_data.parent.mkdir()
        installed_data.write_bytes(payload)
        (self.site / "example-1.0.dist-info" / "RECORD").write_bytes(
            self.members["example-1.0.dist-info/RECORD"]
        )
        self.expected["example"]["hashes"] = (
            hashlib.sha256(self.wheel.read_bytes()).hexdigest(),
        )
        manifest = reviewed_wheel_manifest(self.wheelhouse, self.expected, "a" * 64)
        self.manifest_path.write_bytes(canonical_manifest_bytes(manifest))

        self.validate()
        installed_data.write_bytes(b"mutated\n")
        with self.assertRaisesRegex(RuntimeError, "differs from reviewed wheel"):
            self.validate()

    def test_rewritten_record_cannot_hide_installed_file_mutation(self):
        module = self.site / "example" / "__init__.py"
        module.write_bytes(b"VALUE = 9\n")
        record = self.site / "example-1.0.dist-info" / "RECORD"
        record.write_text(
            record.read_text().replace(_record_hash(b"VALUE = 1\n"), _record_hash(module.read_bytes())),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(RuntimeError, "differs from reviewed wheel"):
            self.validate()

    def test_extra_distribution_and_unregistered_files_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "distribution closure mismatch"):
            self.validate(("example", "rogue"))
        for relative in ("example/rogue.py", "rogue.pth", "sitecustomize.py"):
            with self.subTest(relative=relative):
                path = self.site / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("raise RuntimeError('unreviewed')\n", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "closure mismatch|startup hook"):
                    self.validate()
                path.unlink()

    def test_unhashed_bytecode_is_rejected(self):
        pyc = self.site / "example" / "__pycache__" / "__init__.cpython-312.pyc"
        pyc.parent.mkdir()
        pyc.write_bytes(b"malicious-bytecode")
        with self.assertRaisesRegex(RuntimeError, "forbidden bytecode"):
            self.validate()

    def test_forged_report_or_manifest_cannot_replace_locked_wheel(self):
        fake_report = self.prefix / "csi-pairs-install-report.json"
        fake_report.write_text(json.dumps({"claimed_wheel": self.expected["example"]["hashes"][0]}))
        self.wheel.write_bytes(self.wheel.read_bytes() + b"forged")
        with self.assertRaisesRegex(RuntimeError, "does not identify one locked package"):
            self.validate()

    def test_each_validation_rescans_install_tree(self):
        self.validate()
        (self.site / "example" / "__init__.py").write_bytes(b"VALUE = 2\n")
        with self.assertRaisesRegex(RuntimeError, "differs from reviewed wheel"):
            self.validate()

    def test_setup_retains_wheels_and_forbids_generated_bytecode(self):
        setup = (Path(__file__).resolve().parents[1] / "scripts" / "setup_formal_v2.sh").read_text()
        self.assertIn("pip download", setup)
        self.assertIn("--no-index", setup)
        self.assertIn("--no-compile", setup)
        self.assertIn("pip uninstall --yes pip", setup)
        self.assertIn("-name '*.pyc'", setup)


if __name__ == "__main__":
    unittest.main()
