from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from formal_v2.formal_claims import _semantic_status
from formal_v2.formal_controls import (
    G4_CONCAT_CONTROL_IDS,
    REPORT_ONLY_CONTROL_IDS,
    _validate_manifest as validate_resource_manifest,
    _validate_resource,
)
from formal_v2.formal_external import (
    _c1_model_assessment,
    _validate_manifest as validate_external_manifest,
    _validate_six_condition_rows,
)
from formal_v2.formal_io import sha256_file, write_json
from formal_v2.external_adapters.wigatr_protocol import SIX_CONDITIONS as CONDITIONS


ROOT = Path(__file__).resolve().parents[2]


class EvidenceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.dataset = SimpleNamespace(
            bank_ids=np.asarray(["bank-a", "bank-b"]),
            city_ids=np.asarray(["city-a", "city-b"]),
            position_ids=np.asarray([["p0"], ["p1"]]),
            scene_roles=np.asarray(["source_final_unseen_bank", "target"]),
            position_roles=np.asarray([["query"], ["query"]]),
            base_map_cluster_ids=np.asarray(["cluster-a", "cluster-b"]),
        )
        self.units = {
            "u-a": SimpleNamespace(scene=0, position=0, csi_context_sha256="a" * 64),
            "u-b": SimpleNamespace(scene=1, position=0, csi_context_sha256="b" * 64),
        }
        self.contract = {
            (unit_id, condition): {
                "base_map_cluster_id": str(
                    self.dataset.base_map_cluster_ids[unit.scene]
                ),
                "map_sha256": f"{index + 1:064x}",
                "action_sha256": f"{index + 101:064x}",
            }
            for unit_id, unit in self.units.items()
            for index, condition in enumerate(CONDITIONS)
        }

    def _rows(self, value="7.0"):
        rows = []
        for unit_id, unit in self.units.items():
            for condition in CONDITIONS:
                contract = self.contract[(unit_id, condition)]
                rows.append(
                    {
                        "unit_id": unit_id,
                        "model_name": "honest-model",
                        "condition": condition,
                        "city_id": str(self.dataset.city_ids[unit.scene]),
                        "bank_id": str(self.dataset.bank_ids[unit.scene]),
                        "position_id": str(self.dataset.position_ids[unit.scene, unit.position]),
                        "localization_error_m": value,
                        "csi_context_sha256": unit.csi_context_sha256,
                        "base_map_cluster_id": contract["base_map_cluster_id"],
                        "map_sha256": contract["map_sha256"],
                        "action_sha256": contract["action_sha256"],
                        "query_count": "1",
                    }
                )
        return rows

    def test_shipped_wiser_is_style_control_and_c1_stays_underidentified(self):
        manifest = json.loads(
            (ROOT / "formal_v2/external_adapters/all_map_adapters_v1.json").read_text()
        )
        validate_external_manifest(manifest)
        wiser = next(row for row in manifest["adapters"] if row["model_name"] == "WiSER")
        self.assertEqual(wiser["implementation_status"], "style-controlled-implementation")
        self.assertFalse(wiser["c1_eligible"])
        self.assertEqual(
            [row["model_name"] for row in manifest["adapters"] if row["c1_eligible"]],
            ["Wi-GATr"],
        )

    def test_six_equal_conditions_cannot_pass_c1(self):
        rows = self._rows()
        _validate_six_condition_rows(
            {"model_name": "honest-model"},
            rows,
            self.dataset,
            expected_unit_ids=set(self.units),
            expected_unit_contract=self.units,
            expected_condition_contract=self.contract,
        )
        assessment = _c1_model_assessment(
            {
                "evaluation": {
                    "bootstrap_resamples": 100,
                    "null_score_equivalence_margin": 0.05,
                    "null_overclassification_rate_max": 0.05,
                    "c1_active_error_minimum_m": 0.05,
                    "c1_null_error_equivalence_margin_m": 0.05,
                }
            },
            {"adapter_id": "a", "model_name": "honest-model", "c1_eligible": True},
            rows,
            self.dataset,
            expected_unit_contract=self.units,
        )
        self.assertFalse(assessment["active_effect_passed"])
        self.assertFalse(assessment["passed"])

    def test_same_map_or_action_reuse_is_rejected_by_outer_contract(self):
        rows = self._rows()
        active = next(row for row in rows if row["condition"] == "paired_active_alternative")
        active["map_sha256"] = next(row for row in rows if row["condition"] == "correct")["map_sha256"]
        with self.assertRaisesRegex(ValueError, "outer recomputation"):
            _validate_six_condition_rows(
                {"model_name": "honest-model"},
                rows,
                self.dataset,
                expected_unit_ids=set(self.units),
                expected_unit_contract=self.units,
                expected_condition_contract=self.contract,
            )

    def test_aggregate_only_claim_controls_cannot_support_claims(self):
        legacy = {
            "status": "PASS",
            "passed": True,
            "checkpoint_hashes_verified": True,
            "alignment_gain": 1.0,
            "shuffled_alignment_gain": 0.0,
            "shortcut_baselines_passed": True,
        }
        self.assertEqual(_semantic_status("shuffled_pair", legacy), "FAIL")
        self.assertEqual(_semantic_status("retention", legacy), "FAIL")

    def test_fewer_than_two_faithful_c1_models_is_blocked_not_supported(self):
        payload = {
            "status": "BLOCKED",
            "passed": False,
            "c1_eligible_model_count": 0,
            "c1_eligible_models": [],
            "c1_required_eligible_model_count": 2,
            "model_assessments": [],
            "condition_input_contract": "outer-recomputed-map-and-action-sha256-v1",
            "condition_registry_path": "external_condition_registry.csv",
            "condition_registry_sha256": "c" * 64,
            "adapter_manifest_path": "adapter_manifest.json",
            "adapter_manifest_sha256": "a" * 64,
        }
        self.assertEqual(_semantic_status("external_baselines", payload), "BLOCKED")

    def test_g4_excludes_generous_control_from_required_subgate(self):
        self.assertEqual(
            G4_CONCAT_CONTROL_IDS,
            ("parameter_matched_concat", "flop_matched_concat"),
        )
        self.assertEqual(REPORT_ONLY_CONTROL_IDS, ("generous_2x_concat",))

    def test_legacy_resource_manifest_without_source_and_replay_is_rejected(self):
        legacy = {
            "schema_version": "csi-pairs-v6-resource-controls-v1",
            "controls": [
                {"control_id": name, "command": ["true"]}
                for name in (
                    "equal_flop_alignment", "equal_flop_response",
                    "parameter_matched_concat", "flop_matched_concat", "generous_2x_concat",
                )
            ],
        }
        with self.assertRaisesRegex(ValueError, "schema mismatch|fields must be exact"):
            validate_resource_manifest(legacy)

    def test_single_tensor_checkpoint_cannot_authenticate_as_control_architecture(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint = root / "checkpoint.pt"
            torch.save(
                {
                    "schema_version": "csi-pairs-v6-control-checkpoint-v2",
                    "control_id": "equal_flop_alignment",
                    "architecture_family": "single_branch_alignment",
                    "architecture_spec_sha256": "c" * 64,
                    "adapter_source_sha256": "d" * 64,
                    "dataset_sha256": "a" * 64,
                    "config_sha256": "b" * 64,
                    "fixture": False,
                    "state_dict": {"totally_wrong.single_tensor": torch.zeros(3)},
                },
                checkpoint,
            )
            profiler = root / "profiler.json"
            training = root / "training.json"
            write_json(profiler, {})
            write_json(training, {})
            resource = {
                "schema_version": "csi-pairs-v6-resource-record-v2",
                "control_id": "equal_flop_alignment",
                "dataset_sha256": "a" * 64,
                "config_sha256": "b" * 64,
                "fixture": False,
                "training_flops": 1.0,
                "inference_flops": 1.0,
                "parameters": 3,
                "wall_seconds": 1.0,
                "checkpoint_path": checkpoint.name,
                "checkpoint_sha256": sha256_file(checkpoint),
                "profiler_trace_path": profiler.name,
                "profiler_trace_sha256": sha256_file(profiler),
                "training_log_path": training.name,
                "training_log_sha256": sha256_file(training),
                "architecture_spec_sha256": "c" * 64,
                "adapter_source_sha256": "d" * 64,
            }
            architecture = {
                "architecture_family": "single_branch_alignment",
                "state_keys": ["encoder.weight", "encoder.bias", "head.weight", "head.bias"],
                "objective_terms": ["endpoint", "alignment"],
            }
            with self.assertRaisesRegex(RuntimeError, "architecture/state-key"):
                _validate_resource(
                    "equal_flop_alignment",
                    resource,
                    {"dataset_sha256": "a" * 64, "config_sha256": "b" * 64, "fixture": False},
                    root,
                    architecture=architecture,
                    architecture_sha256="c" * 64,
                    adapter_source_sha256="d" * 64,
                )


if __name__ == "__main__":
    unittest.main()
