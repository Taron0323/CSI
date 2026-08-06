from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from formal_v2.formal_evaluation import _transition_metrics
from formal_v2.formal_metrics import risk_coverage
from formal_v2.formal_path import _mechanism_gate
from formal_v2.formal_protocol import PatchSpec, patchify_csi
from formal_v2.formal_risk import load_risk_feature_archive, run_risk_contract


class RiskPathEvaluationIntegrityTests(unittest.TestCase):
    def test_risk_coverage_is_invariant_to_tied_score_row_order(self):
        errors = np.asarray([9.0, 1.0, 7.0, 2.0, 5.0, 3.0, 8.0, 4.0])
        scores = np.zeros_like(errors)
        first = risk_coverage(errors, scores)
        second = risk_coverage(errors[::-1], scores)
        self.assertEqual(first, second)

    def test_external_risk_archive_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "first-party"):
                load_risk_feature_archive(
                    Path(directory) / "fabricated.npz", {}, object(), directory
                )

    def test_risk_contract_rejects_unmarked_self_reported_features(self):
        with self.assertRaisesRegex(RuntimeError, "first-party"):
            run_risk_contract({}, object(), ".", {})

    def test_path_gate_cannot_pass_without_provenance(self):
        config = {
            "path": {
                "minimum_trend_slope": 0.001,
                "equivalence_margin": 0.02,
                "balance_smd_max": 0.1,
                "bootstrap_resamples": 20,
                "minimum_effective_sample_size": 2,
                "covariate_overlap_minimum": 0.5,
            }
        }
        result = _mechanism_gate(
            config,
            [],
            [],
            [],
            0,
            [],
            {"passed": False, "registry_sha256": "0" * 64},
        )
        self.assertEqual(
            result["g7_subgates"]["1_registered_path_provenance_and_noop_epsilon"],
            "FAIL",
        )
        self.assertFalse(result["passed"])

    def test_perfect_response_has_complete_transition_metrics(self):
        spec = PatchSpec(
            antennas=2,
            subcarriers=2,
            patch_complex_size=2,
            patch_antenna_size=1,
            patch_subcarrier_size=2,
        )
        source_csi = np.asarray([[1.0, 0.5, 0.25, 0.75, 0.0, 0.1, 0.2, 0.3]])
        target_csi = np.asarray([[0.8, 0.3, 0.5, 0.9, 0.2, 0.2, 0.4, 0.1]])
        source = patchify_csi(source_csi, spec)
        target = patchify_csi(target_csi, spec)
        normalization = SimpleNamespace(
            patch_mean=np.zeros((spec.patch_count, spec.patch_dim)),
            patch_scale=np.ones((spec.patch_count, spec.patch_dim)),
        )
        result = _transition_metrics(target, source, target, normalization, spec)
        self.assertAlmostEqual(result["native_sgcs"], 1.0)
        self.assertAlmostEqual(result["native_transition_skill"], 1.0)
        for name in ("path_loss", "delay_spread", "angular_spread"):
            self.assertAlmostEqual(result[f"native_{name}_change_mae"], 0.0)
            self.assertAlmostEqual(result[f"native_{name}_direction_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
