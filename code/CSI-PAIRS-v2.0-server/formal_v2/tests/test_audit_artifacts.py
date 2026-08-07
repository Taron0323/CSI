from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from formal_v2.scripts import build_v6_requirement_matrix as matrix


class AtomicRequirementMatrixTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.rows = [{field: field for field in matrix.FIELDNAMES}]

    def tearDown(self):
        self.temporary.cleanup()

    def test_existing_private_target_leaves_public_target_absent(self):
        public = self.root / "public.csv"
        private = self.root / "private.csv"
        private.write_text("preserve\n", encoding="utf-8")

        with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
            matrix.write_matrix_pair(public, self.rows, private, self.rows)

        self.assertFalse(public.exists())
        self.assertEqual(private.read_text(encoding="utf-8"), "preserve\n")

    def test_second_publish_failure_rolls_back_first_target(self):
        public = self.root / "public.csv"
        private = self.root / "private.csv"
        real_link = os.link
        calls = 0

        def fail_second_link(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected second-output failure")
            return real_link(source, destination)

        with patch.object(matrix.os, "link", side_effect=fail_second_link):
            with self.assertRaisesRegex(OSError, "injected second-output failure"):
                matrix.write_matrix_pair(public, self.rows, private, self.rows)

        self.assertFalse(public.exists())
        self.assertFalse(private.exists())
        self.assertEqual(list(self.root.glob(".*.tmp")), [])

    def test_output_paths_must_be_distinct(self):
        output = self.root / "matrix.csv"
        with self.assertRaisesRegex(ValueError, "different paths"):
            matrix.write_matrix_pair(output, self.rows, output, self.rows)
        self.assertFalse(output.exists())

    def test_section_level_anchor_cannot_be_promoted_to_atomic_exact(self):
        status, blocker, explanation = matrix.section_status("reader", 44, 0)
        self.assertEqual(status, "PARTIAL/PROXY")
        self.assertEqual(blocker, "CODE_REQUIRED")
        self.assertIn("section-level", explanation)

    def test_public_rows_redact_clause_and_heading_source_text(self):
        source = self.root / "reader.md"
        source.write_text("## 0. Private heading\n必须保留私有条款。\n", encoding="utf-8")
        source_spec = {
            "sha256": matrix.sha256_file(source),
            "prefix": "TEST",
        }
        with patch.dict(matrix.SOURCE_SPECS, {"reader": source_spec}):
            public_rows = matrix.build_rows("reader", source, matrix.Path.cwd(), False)
            private_rows = matrix.build_rows("reader", source, matrix.Path.cwd(), True)

        self.assertTrue(public_rows)
        self.assertEqual(
            {row["original_norm"] for row in public_rows},
            {"[OMITTED_FROM_PUBLIC_REPOSITORY]"},
        )
        self.assertEqual(
            {row["section_heading"] for row in public_rows},
            {"[OMITTED_FROM_PUBLIC_REPOSITORY]"},
        )
        self.assertTrue(any("私有条款" in row["original_norm"] for row in private_rows))
        self.assertEqual(
            {row["section_heading"] for row in private_rows},
            {"0. Private heading"},
        )


if __name__ == "__main__":
    unittest.main()
