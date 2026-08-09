from __future__ import annotations

from collections import Counter
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


SERVER_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = SERVER_ROOT / "artifacts" / "m4_formal_candidate_v2"
EVIDENCE_PATH = EVIDENCE_ROOT / "candidate_evidence.json"
VERIFIER_PATH = EVIDENCE_ROOT / "verify_candidate_evidence.py"


class M4CandidateEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    def test_repository_evidence_verifier_passes(self):
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, str(VERIFIER_PATH)],
            cwd=SERVER_ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("PASS mode=static", completed.stdout)
        self.assertIn("scenes=34 shards=14", completed.stdout)

    def test_critical_hashes_and_readiness_boundary_are_frozen(self):
        self.assertEqual(
            self.evidence["candidate"]["dataset"]["sha256"],
            "e5ec3d32bbb7c639f2fd6e6dcc23bc4bb6085cc76830a700e5b7103b17a37847",
        )
        self.assertEqual(
            self.evidence["verification"]["gate"]["sha256"],
            "ac790e2ffacca784cba22bc31bc9798049bb219f3f88cfeb3cd0c69fce7c86a8",
        )
        self.assertEqual(
            self.evidence["scientific_use"],
            "CANDIDATE_NOT_CLAIM",
        )
        self.assertEqual(
            self.evidence["readiness"],
            {
                "M4_DATA_PRODUCTION_READY": "YES",
                "FORMAL_CANDIDATE_READY": "YES",
                "FORMAL_INPUT_READY": "CANDIDATE_ONLY",
                "FORMAL_TRAINING_READY": "NO",
                "LAUNCH_READY": "BLOCKED",
                "SCIENTIFIC_EVIDENCE": "NOT_ASSESSED",
            },
        )
        self.assertEqual(
            set(self.evidence["closed_issue_ids"]),
            {
                "DATA-VISIBILITY-001",
                "DATA-REGEN-001",
                "PATH-ID-001",
                "INPUT-DATA-001",
            },
        )
        self.assertEqual(
            len(self.evidence["verification"]["regenerated_array_keys"]),
            15,
        )

    def test_scene_and_shard_inventories_are_complete(self):
        with (EVIDENCE_ROOT / "scene_inventory.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            scenes = list(csv.DictReader(handle))
        with (EVIDENCE_ROOT / "shard_inventory.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            shards = list(csv.DictReader(handle))

        self.assertEqual([int(row["scene_index"]) for row in scenes], list(range(34)))
        self.assertEqual(len({row["base_map_cluster_id"] for row in scenes}), 34)
        self.assertTrue(all(row["verification_status"] == "PASS" for row in scenes))
        self.assertEqual(
            dict(Counter(row["role"] for row in scenes)),
            self.evidence["candidate"]["role_counts"],
        )
        self.assertEqual([int(row["shard_index"]) for row in shards], list(range(14)))
        coverage = [
            scene_index
            for row in shards
            for scene_index in range(
                int(row["scene_start_inclusive"]),
                int(row["scene_end_exclusive"]),
            )
        ]
        self.assertEqual(coverage, list(range(34)))
        self.assertTrue(all(row["status"] == "PASS" for row in shards))

    def test_large_binaries_and_local_identity_are_absent(self):
        self.assertFalse(list(EVIDENCE_ROOT.rglob("*.npz")))
        markers = (
            "/" + "Users" + "/",
            "futa" + "oran",
            "wx" + "id_",
            "Taron" + "0323",
        )
        for path in EVIDENCE_ROOT.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for marker in markers:
                with self.subTest(path=path.name, marker=marker):
                    self.assertNotIn(marker, text)

    def test_delivery_boundaries_include_internal_evidence_only(self):
        server_builder = (
            SERVER_ROOT / "formal_v2" / "scripts" / "build_server_bundle.sh"
        ).read_text(encoding="utf-8")
        anonymous_builder = (
            SERVER_ROOT / "formal_v2" / "scripts" / "build_anonymous_supplement.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("artifacts/m4_formal_candidate_v2", server_builder)
        self.assertIn("test_m4_candidate_evidence.py", anonymous_builder)


if __name__ == "__main__":
    unittest.main()
