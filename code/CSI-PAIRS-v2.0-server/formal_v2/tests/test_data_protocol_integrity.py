from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from formal_v2.formal_config import load_formal_config, validate_formal_config
from formal_v2.formal_dataset import FormalDataset, FormalDatasetError
from formal_v2.formal_fixture import write_nonscientific_fixture
from formal_v2.formal_protocol import (
    PatchSpec,
    frozen_mask_query_bank,
    typed_signed_edit,
)
from formal_v2.formal_qualification import (
    _action_geometry_profile,
    _response_gate_rows,
    _route_coverage_passed,
    _select_wrong_action,
    _wrong_action_distance,
)


ROOT = Path(__file__).resolve().parents[1]
SMOKE_CONFIG = ROOT / "configs" / "formal_v2_smoke.json"


def _archive_arrays(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {name: np.asarray(archive[name]) for name in archive.files}


class DatasetIdentityAndNoiseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path = write_nonscientific_fixture(self.root / "fixture.npz")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_canonical_foundation_digest_is_content_based_and_stable(self) -> None:
        first = FormalDataset.load(self.path)
        second = FormalDataset.load(self.path)
        np.testing.assert_array_equal(
            first.canonical_base_map_digests,
            second.canonical_base_map_digests,
        )
        self.assertEqual(first.canonical_base_map_digests.shape, (first.scene_count,))
        self.assertTrue(all(len(value) == 64 for value in first.canonical_base_map_digests))

    def test_formal_profile_rejects_foundation_content_spoofed_across_splits(self) -> None:
        dataset = FormalDataset.load(self.path)
        dataset.metadata["fixture"] = False
        dataset.metadata["scientific_use"] = "CANDIDATE"
        with self.assertRaisesRegex(FormalDatasetError, "canonical foundation content"):
            dataset.validate()

    def test_one_copied_observation_residual_is_rejected(self) -> None:
        arrays = _archive_arrays(self.path)
        clean = arrays["csi_clean"]
        residual = arrays["csi_repeat"] - clean[:, :, :, None, :]
        residual[0, 1, 2, 1] = residual[0, 0, 2, 1]
        arrays["csi_repeat"] = clean[:, :, :, None, :] + residual
        malformed = self.root / "one-copied-observation.npz"
        np.savez_compressed(malformed, **arrays)
        with self.assertRaisesRegex(FormalDatasetError, "sibling observations"):
            FormalDataset.load(malformed)

    def test_scaled_copy_of_one_observation_residual_is_rejected(self) -> None:
        arrays = _archive_arrays(self.path)
        clean = arrays["csi_clean"]
        residual = arrays["csi_repeat"] - clean[:, :, :, None, :]
        residual[0, 1, 2, 1] = 1.01 * residual[0, 0, 2, 1]
        arrays["csi_repeat"] = clean[:, :, :, None, :] + residual
        malformed = self.root / "scaled-copied-observation.npz"
        np.savez_compressed(malformed, **arrays)
        with self.assertRaisesRegex(FormalDatasetError, "near-perfectly correlate"):
            FormalDataset.load(malformed)

    def test_noise_binding_digest_changes_for_one_observation(self) -> None:
        dataset = FormalDataset.load(self.path)
        repeated = dataset.csi_repeat[0].copy()
        repeated[1, 2, 1, 0] += 1e-6
        self.assertNotEqual(
            dataset.observation_noise_binding_digest(0),
            dataset.observation_noise_binding_digest(0, repeated),
        )

    def test_phase_invariant_gauge_is_fail_closed_for_raw_complex_profile(self) -> None:
        arrays = _archive_arrays(self.path)
        metadata = json.loads(str(arrays["metadata_json"].item()))
        metadata["representation"]["phase_gauge_rule"] = "phase_invariant_delay_angle_power"
        arrays["metadata_json"] = np.asarray(
            json.dumps(metadata, sort_keys=True, separators=(",", ":"))
        )
        malformed = self.root / "unsupported-gauge.npz"
        np.savez_compressed(malformed, **arrays)
        with self.assertRaisesRegex(FormalDatasetError, "phase-invariant targets are not implemented"):
            FormalDataset.load(malformed)


class FrozenMaskContractTests(unittest.TestCase):
    def test_teacher_and_model_mask_configuration_cannot_be_silently_ignored(self) -> None:
        teacher = load_formal_config(SMOKE_CONFIG)
        teacher["teacher"]["mask_fraction"] = 0.6
        with self.assertRaisesRegex(ValueError, "teacher.mask_fraction"):
            validate_formal_config(teacher)
        model = load_formal_config(SMOKE_CONFIG)
        model["model"]["mask_fraction"] = 0.1
        with self.assertRaisesRegex(ValueError, "model.mask_fraction"):
            validate_formal_config(model)

    def test_block_masks_are_complete_half_axis_blocks(self) -> None:
        spec = PatchSpec(4, 4, 1, 1, 1)
        bank = frozen_mask_query_bank(spec, 17)
        for entry in bank:
            grid = entry.mask.reshape(spec.patch_rows, spec.patch_columns)
            if entry.mode == "antenna_block_50":
                selected = np.flatnonzero(np.all(grid, axis=1))
                self.assertEqual(selected.size, 2)
                self.assertTrue(np.all(np.logical_or(np.all(grid, axis=1), ~np.any(grid, axis=1))))
                self.assertTrue(np.all(np.diff(selected) == 1))
            if entry.mode == "subcarrier_block_50":
                selected = np.flatnonzero(np.all(grid, axis=0))
                self.assertEqual(selected.size, 2)
                self.assertTrue(np.all(np.logical_or(np.all(grid, axis=0), ~np.any(grid, axis=0))))
                self.assertTrue(np.all(np.diff(selected) == 1))
            self.assertTrue(entry.mask[entry.query])


class QualificationCoverageTests(unittest.TestCase):
    def test_per_bank_train_route_coverage_requires_all_four_denominators(self) -> None:
        qualification = {
            "minimum_active_units_per_bank": 2,
            "minimum_null_units_per_bank": 2,
        }
        row = {
            "alignment_active_units": 2,
            "alignment_null_units": 2,
            "response_patch_active_units": 2,
            "response_patch_null_units": 2,
        }
        self.assertTrue(_route_coverage_passed(row, qualification))
        row["response_patch_null_units"] = 1
        self.assertFalse(_route_coverage_passed(row, qualification))

    def test_wrong_action_matching_distinguishes_exact_fallback_and_failed(self) -> None:
        reference = np.zeros((12, 6, 6), dtype=np.float64)
        reference[2, 1:3, 1:3] = 1.0
        exact = np.zeros_like(reference)
        exact[2, 3:5, 3:5] = 1.0
        fallback = np.zeros_like(reference)
        fallback[2, 3:6, 3:5] = 1.0
        failed = np.zeros_like(reference)
        failed[0, 3:5, 3:5] = 1.0
        self.assertEqual(_wrong_action_distance(reference, exact)[:2], (0, 0))
        self.assertEqual(_wrong_action_distance(reference, fallback)[:2], (0, 1))
        self.assertEqual(_wrong_action_distance(reference, failed)[0], 1)
        self.assertNotEqual(
            _action_geometry_profile(reference)["family"],
            _action_geometry_profile(failed)["family"],
        )

    def test_material_from_to_planes_are_part_of_wrong_action_semantics(self) -> None:
        reference = np.zeros((10, 4, 4), dtype=np.float64)
        candidate = np.zeros_like(reference)
        reference[4, 1:3, 1:3] = 1.0
        reference[8, 1:3, 1:3] = 1.0
        candidate[5, 1:3, 1:3] = 1.0
        candidate[9, 1:3, 1:3] = 1.0
        self.assertEqual(reference.shape[0], 4 + 2 * 3)
        self.assertEqual(_wrong_action_distance(reference, candidate)[0], 1)
        self.assertNotEqual(
            _action_geometry_profile(reference)["family"],
            _action_geometry_profile(candidate)["family"],
        )

    def test_wrong_action_selection_is_receiver_position_specific(self) -> None:
        world_bits = (
            (np.arange(8, dtype=np.int64)[:, None] >> np.arange(3)) & 1
        )
        maps = np.zeros((1, 8, 3, 5, 5), dtype=np.float64)
        primitive_cells = ((1, 1), (1, 3), (3, 1))
        for world, bits in enumerate(world_bits):
            for bit, (row, column) in enumerate(primitive_cells):
                maps[0, world, 0, row, column] = float(bits[bit])
        dataset = SimpleNamespace(
            world_bits=world_bits,
            bit_count=3,
            maps=maps,
            map_channel_names=np.asarray(["occupancy", "height", "material"]),
            metadata={
                "representation": {
                    "map_origin_xy_m": [0.0, 0.0],
                    "map_resolution_m": 1.0,
                }
            },
        )
        correct = typed_signed_edit(
            maps[0, 0],
            maps[0, 1],
            dataset.map_channel_names,
            1,
        )
        _, first_status, first_world = _select_wrong_action(
            dataset,
            0,
            0,
            0,
            correct,
            1,
            receiver_position=np.asarray([2.5, 0.5, 0.0]),
        )
        _, second_status, second_world = _select_wrong_action(
            dataset,
            0,
            0,
            0,
            correct,
            1,
            receiver_position=np.asarray([0.5, 2.5, 0.0]),
        )
        self.assertEqual((first_status, first_world), ("exact", 2))
        self.assertEqual((second_status, second_world), ("exact", 4))
        self.assertNotEqual(first_world, second_world)
        self.assertEqual(
            _select_wrong_action(dataset, 0, 0, 0, correct, 1)[1],
            "fallback",
        )

    def test_failed_wrong_actions_cannot_enter_the_swap_comparison_denominator(self) -> None:
        dataset = SimpleNamespace(
            scene_ids=np.asarray(["scene"]),
            bank_ids=np.asarray(["bank"]),
        )
        records = [
            {"scene": 0, "route": 2, "wrong_action_match_status": "failed"},
            {"scene": 0, "route": 0, "wrong_action_match_status": "failed"},
        ]
        target = np.asarray([[1.0], [0.0]])
        predictions = {
            "no_x": np.asarray([[1.0], [0.0]]),
            "copy": np.zeros((2, 1)),
            "no_action": np.zeros((2, 1)),
            "action_swap": np.zeros((2, 1)),
            "oracle_x": np.asarray([[1.0], [0.0]]),
        }
        _, _, gates = _response_gate_rows(
            dataset,
            records,
            target,
            predictions,
            {
                "response_physical_null_rms_max": 0.1,
                "no_x_min_relative_improvement": 0.0,
                "oracle_min_relative_improvement": 0.0,
                "null_violation_rate_max": 0.0,
            },
        )
        self.assertIsNone(gates[0]["relative_improvement_vs_action_swap"])
        self.assertEqual(gates[0]["action_swap_exact_common_denominator"], 0)
        self.assertFalse(gates[0]["passed"])


if __name__ == "__main__":
    unittest.main()
