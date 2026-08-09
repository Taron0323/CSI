from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from formal_v2 import sionna_osm_candidate as candidate
from formal_v2.sionna_scene0_diagnostic_assets import (
    _byte_comparison,
    _read_ascii_triangle_ply,
)


class Scene0DiagnosticAssetTests(unittest.TestCase):
    def test_ascii_triangle_ply_is_fully_readable(self) -> None:
        triangles = np.asarray(
            (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),),
            dtype=np.float32,
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "triangle.ply"
            candidate._write_triangle_ply(path, triangles)
            report = _read_ascii_triangle_ply(path)
        self.assertEqual(report["vertex_count"], 3)
        self.assertEqual(report["face_count"], 1)
        self.assertTrue(report["all_values_finite"])
        self.assertTrue(report["all_faces_triangular"])

    def test_ascii_triangle_ply_rejects_out_of_range_face(self) -> None:
        malformed = """ply
format ascii 1.0
element vertex 3
property float x
property float y
property float z
element face 1
property list uchar int vertex_indices
end_header
0 0 0
1 0 0
0 1 0
3 0 1 3
"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.ply"
            path.write_text(malformed, encoding="ascii")
            with self.assertRaisesRegex(ValueError, "invalid vertex indices"):
                _read_ascii_triangle_ply(path)

    def test_byte_comparison_reports_identity_and_first_difference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left = root / "left"
            right = root / "right"
            left.write_bytes(b"abcdef")
            right.write_bytes(b"abcdef")
            identical = _byte_comparison(left, right)
            self.assertTrue(identical["byte_identical"])
            self.assertIsNone(identical["first_differing_byte_offset"])
            right.write_bytes(b"abcXefg")
            different = _byte_comparison(left, right)
            self.assertFalse(different["byte_identical"])
            self.assertEqual(different["first_differing_byte_offset"], 3)
            self.assertEqual(different["differing_byte_count_with_size_delta"], 2)


if __name__ == "__main__":
    unittest.main()
