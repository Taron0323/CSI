from __future__ import annotations

import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

from formal_v2.formal_claims import CLAIM_DEPENDENCIES, assemble_claim_evidence
from formal_v2.formal_cli import build_parser
from formal_v2.formal_controls import CONTROL_IDS, _validate_manifest as validate_control_manifest
from formal_v2.formal_config import load_formal_config, validate_formal_config
from formal_v2.formal_data_verification import (
    BLOCKING_ROLES,
    SCHEMA as DATA_GATE_SCHEMA,
    require_data_verification,
    require_verified_roles,
)
from formal_v2.formal_dataset import FormalDataset, FormalDatasetError, SOURCE_ROLES
from formal_v2.formal_evidence import (
    CLAIM_IDS,
    GATE_IDS,
    QUALIFICATION_SCHEMA,
    complete_gate_vector,
    evidence_context,
    require_formal_qualification,
    require_stage_manifested_gate,
)
from formal_v2.formal_factorial import city_support_candidates, eligible_query_indices
from formal_v2.formal_evaluation import _eligible_evaluation_positions, _paired_score_differences
from formal_v2.formal_external_validity import _validate_manifest as validate_external_validity_manifest
from formal_v2.formal_external import (
    _validate_manifest as validate_external_manifest,
    _validate_execution_manifest as validate_external_execution_manifest,
    _validate_six_condition_rows,
)
from formal_v2.external_adapters.controlled_map_adapter import (
    _batch as controlled_batch,
    _build_model as build_controlled_model,
    _fit_data_normalizer,
    _loss as controlled_loss,
    load_controlled_map_config,
)
from formal_v2.external_adapters.representation_models import build_representation_model
from formal_v2.external_adapters.wigatr_adapter import (
    _verify_vendor_tree,
    inverse_localize_power,
)
from formal_v2.external_adapters.wigatr_protocol import (
    SIX_CONDITIONS,
    build_six_condition_units,
    condition_map,
    geometry_destroyed_map,
    grid_to_triangular_mesh,
    load_wigatr_config,
    relative_total_power_db,
)
from formal_v2.formal_fixture import write_nonscientific_fixture
from formal_v2.formal_io import (
    StrictJsonError,
    artifact_manifest,
    parse_strict_json,
    sha256_file,
    write_csv,
    write_json,
)
from formal_v2.formal_model import CSIPairsFormalModel, required_mean
from formal_v2.formal_path import _noop_path_threshold, localization_path_incidence, path_incidence
from formal_v2.formal_protocol import (
    PatchSpec,
    delay_angle_power,
    frozen_mask_query_bank,
    patchify_csi,
    typed_signed_edit,
    unpatchify_csi,
)
from formal_v2.formal_representation_baselines import (
    _fit_normalizer as fit_representation_normalizer,
    _make_batch as make_representation_batch,
    load_representation_config,
)
from formal_v2.formal_resources import validate_resource_registry
from formal_v2.formal_qualification import qualification_blocking_scenes
from formal_v2.formal_risk import (
    TemperatureCalibration,
    _coverage_error_monotonic,
    fit_constrained_risk_calibrator,
    frozen_map_proposals,
    randomized_candidate_labels,
)
from formal_v2.formal_routing import route_code
from formal_v2.formal_scene_id import _validate_manifest as validate_scene_id_manifest
from formal_v2.formal_statistics import (
    exact_factorial_utilities,
    hierarchical_factorial_interval,
    holm_adjust,
)
from formal_v2.formal_teacher import CSIMaskedTeacher


ROOT = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = ROOT / "formal_v2" / "configs" / "formal_v2_smoke.json"


class ConfigTests(unittest.TestCase):
    def test_config_is_v6_and_has_complete_sections(self):
        config = load_formal_config(SMOKE_CONFIG)
        self.assertEqual(config["schema_version"], "csi-pairs-formal-config-v2.1-v6")
        self.assertEqual(len(config["seeds"]), 3)
        self.assertEqual(config["factorial"]["arms"], ["endpoint", "alignment", "response", "full"])
        self.assertEqual(set(("teacher", "evaluation", "risk", "path")).difference(config), set())
        self.assertIn("external_validity", config)
        self.assertIn("literature", config)

    def test_rejects_two_seeds(self):
        config = load_formal_config(SMOKE_CONFIG)
        config["seeds"] = [1, 2]
        with self.assertRaisesRegex(ValueError, "at least three"):
            validate_formal_config(config)

    def test_rejects_nonfactorial_order(self):
        config = load_formal_config(SMOKE_CONFIG)
        config["factorial"]["arms"] = ["full", "endpoint", "alignment", "response"]
        with self.assertRaisesRegex(ValueError, "exactly"):
            validate_formal_config(config)

    def test_rejects_teacher_state_initialization_mismatch(self):
        config = load_formal_config(SMOKE_CONFIG)
        config["teacher"]["latent_dim"] += 1
        with self.assertRaisesRegex(ValueError, "shared CSI initialization"):
            validate_formal_config(config)

    def test_rejects_non_v6_teacher_mask_fraction(self):
        config = load_formal_config(SMOKE_CONFIG)
        config["teacher"]["mask_fraction"] = 0.25
        with self.assertRaisesRegex(ValueError, "teacher.mask_fraction"):
            validate_formal_config(config)

    def test_rejects_disabling_clean_physical_targets(self):
        config = load_formal_config(SMOKE_CONFIG)
        config["data"]["require_clean_csi"] = False
        with self.assertRaisesRegex(ValueError, "requires data.require_clean_csi=true"):
            validate_formal_config(config)


class StrictJsonTests(unittest.TestCase):
    def test_duplicate_key_rejected(self):
        with self.assertRaisesRegex(StrictJsonError, "duplicate object key"):
            parse_strict_json('{"x":1,"x":2}')

    def test_nan_and_infinity_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value), self.assertRaises(StrictJsonError):
                parse_strict_json('{"x":' + value + "}")


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = write_nonscientific_fixture(self.root / "fixture.npz")
        self.dataset = FormalDataset.load(self.fixture)

    def tearDown(self):
        self.temporary.cleanup()

    def test_fixture_is_permanently_forbidden(self):
        report = self.dataset.contract_report()
        self.assertTrue(report["fixture"])
        self.assertEqual(report["scientific_use"], "FORBIDDEN")

    def test_exact_seven_source_roles_are_present(self):
        self.assertEqual(len(SOURCE_ROLES), 7)
        self.assertEqual(set(self.dataset.scene_roles).intersection(SOURCE_ROLES), set(SOURCE_ROLES))

    def test_maps_radio_and_coordinates_are_typed(self):
        self.assertEqual(self.dataset.maps.ndim, 5)
        self.assertTrue({"occupancy", "height", "material"}.issubset(self.dataset.map_channel_names))
        self.assertGreater(self.dataset.radio_config.shape[1], 0)
        self.assertEqual(self.dataset.metadata["representation"]["coordinate_system"], "bs_centered_right_handed_meters")

    def test_hypercube_edges_are_bidirectional_hamming_one(self):
        edges = list(self.dataset.directed_edges(0))
        pairs = {(edge.source_world, edge.target_world) for edge in edges}
        for edge in edges:
            self.assertIn((edge.target_world, edge.source_world), pairs)
            self.assertEqual(
                int(np.sum(self.dataset.world_bits[edge.source_world] != self.dataset.world_bits[edge.target_world])),
                1,
            )

    def test_qualification_blocking_allowlist_excludes_all_other_roles(self):
        blocking = qualification_blocking_scenes(self.dataset)
        roles = set(self.dataset.scene_roles[np.concatenate(tuple(blocking.values()))])
        self.assertEqual(roles, {"source_encoder_train", "source_method_selection"})
        self.assertNotIn("target", roles)
        self.assertNotIn("external_validation", roles)

    def test_city_level_support_pool_spans_banks_without_multiplying_k(self):
        candidates = city_support_candidates(self.dataset, "target-a")
        self.assertGreaterEqual(len({scene for scene, _ in candidates}), 2)
        selected = candidates[:2]
        self.assertEqual(len(selected), 2)
        self.assertEqual(len({self.dataset.position_ids[scene, position] for scene, position in selected}), 2)

    def test_support_sibling_ids_are_removed_from_every_query_bank(self):
        scene = int(self.dataset.indices_for_role("target")[0])
        query = int(np.flatnonzero(self.dataset.position_roles[scene] == "query")[0])
        support_ids = {str(self.dataset.position_ids[scene, query])}
        remaining = eligible_query_indices(self.dataset, scene, support_ids)
        self.assertNotIn(query, remaining.tolist())

    def test_target_metric_iterator_excludes_support_pool(self):
        for scene_value in self.dataset.indices_for_role("target"):
            scene = int(scene_value)
            selected = _eligible_evaluation_positions(self.dataset, scene)
            self.assertTrue(np.all(self.dataset.position_roles[scene, selected] == "query"))
            support = set(
                np.flatnonzero(self.dataset.position_roles[scene] == "support_pool").tolist()
            )
            self.assertTrue(set(selected.tolist()).isdisjoint(support))

    def test_embedded_metadata_duplicate_is_rejected(self):
        arrays = _archive_arrays(self.fixture)
        raw = str(arrays["metadata_json"].item())
        needle = '"dataset_id":"NONSCIENTIFIC-CODE-FIXTURE"'
        arrays["metadata_json"] = np.asarray(
            raw.replace(needle, '"dataset_id":"first","dataset_id":"NONSCIENTIFIC-CODE-FIXTURE"')
        )
        malformed = self.root / "duplicate.npz"
        np.savez_compressed(malformed, **arrays)
        with self.assertRaisesRegex(FormalDatasetError, "strict JSON"):
            FormalDataset.load(malformed)

    def test_unexpected_npz_array_is_rejected(self):
        arrays = _archive_arrays(self.fixture)
        arrays["undeclared_side_channel"] = np.asarray([1])
        malformed = self.root / "unexpected.npz"
        np.savez_compressed(malformed, **arrays)
        with self.assertRaisesRegex(FormalDatasetError, "array fields must be exact"):
            FormalDataset.load(malformed)

    def test_copied_sibling_noise_is_rejected(self):
        arrays = _archive_arrays(self.fixture)
        clean = arrays["csi_clean"]
        residual = arrays["csi_repeat"] - clean[:, :, :, None, :]
        residual[:, 1] = residual[:, 0]
        arrays["csi_repeat"] = clean[:, :, :, None, :] + residual
        malformed = self.root / "copied_noise.npz"
        np.savez_compressed(malformed, **arrays)
        with self.assertRaisesRegex(FormalDatasetError, "noise realization"):
            FormalDataset.load(malformed)

    def test_canonical_digest_mismatch_is_rejected(self):
        arrays = _archive_arrays(self.fixture)
        arrays["maps"] = arrays["maps"].copy()
        arrays["maps"][0, 0, 0, 1, 1] += 1
        malformed = self.root / "map_digest.npz"
        np.savez_compressed(malformed, **arrays)
        with self.assertRaisesRegex(FormalDatasetError, "canonical map digest"):
            FormalDataset.load(malformed)

    def test_base_map_cluster_cannot_cross_roles(self):
        arrays = _archive_arrays(self.fixture)
        arrays["base_map_cluster_ids"] = arrays["base_map_cluster_ids"].copy()
        arrays["base_map_cluster_ids"][1] = arrays["base_map_cluster_ids"][0]
        malformed = self.root / "cluster_leak.npz"
        np.savez_compressed(malformed, **arrays)
        with self.assertRaisesRegex(FormalDatasetError, "cross scene roles"):
            FormalDataset.load(malformed)

    def test_common_free_space_failure_is_rejected(self):
        arrays = _archive_arrays(self.fixture)
        arrays["free_space"] = arrays["free_space"].copy()
        arrays["free_space"][0, 1, 2] = False
        malformed = self.root / "occupied.npz"
        np.savez_compressed(malformed, **arrays)
        with self.assertRaisesRegex(FormalDatasetError, "free in every sibling"):
            FormalDataset.load(malformed)


class ProtocolTests(unittest.TestCase):
    def test_patch_roundtrip(self):
        spec = PatchSpec(antennas=2, subcarriers=4, patch_complex_size=1)
        csi = np.arange(32, dtype=float).reshape(2, 16)
        np.testing.assert_array_equal(unpatchify_csi(patchify_csi(csi, spec), spec), csi)

    def test_patchify_uses_two_dimensional_antenna_subcarrier_tiles(self):
        spec = PatchSpec(
            antennas=2,
            subcarriers=4,
            patch_complex_size=4,
            patch_antenna_size=2,
            patch_subcarrier_size=2,
        )
        real = np.arange(8, dtype=float)
        csi = np.concatenate((real, 100 + real))
        patches = patchify_csi(csi, spec)
        np.testing.assert_array_equal(patches[0, 0::2], [0, 1, 4, 5])
        np.testing.assert_array_equal(patches[1, 0::2], [2, 3, 6, 7])
        np.testing.assert_array_equal(unpatchify_csi(patches, spec), csi)

    def test_delay_angle_power_is_invariant_to_shared_phase_rotation(self):
        spec = PatchSpec(2, 4, 1)
        values = np.arange(1, 9) + 1j * np.arange(9, 17)
        first = np.concatenate((values.real, values.imag))
        rotated = values * np.exp(1j * 0.73)
        second = np.concatenate((rotated.real, rotated.imag))
        np.testing.assert_allclose(
            delay_angle_power(first, spec),
            delay_angle_power(second, spec),
            rtol=1e-12,
            atol=1e-12,
        )

    def test_mask_bank_has_three_modes_query_hidden_and_full_coverage(self):
        spec = PatchSpec(2, 4, 1)
        bank = frozen_mask_query_bank(spec, 7)
        self.assertEqual({entry.mode for entry in bank}, {"random_75", "antenna_block_50", "subcarrier_block_50"})
        self.assertTrue(all(entry.mask[entry.query] for entry in bank))
        for mode in {entry.mode for entry in bank}:
            self.assertEqual({entry.query for entry in bank if entry.mode == mode}, set(range(spec.patch_count)))

    def test_typed_action_has_inverse_direction_and_categorical_from_to(self):
        source = np.zeros((3, 4, 4))
        target = source.copy()
        source[0, 1, 1] = 1
        source[1, 1, 1] = 2
        source[2, 1, 1] = 1
        target[1, 1, 1] = 5
        target[2, 1, 1] = 3
        names = np.asarray(["occupancy", "height", "material"])
        forward = typed_signed_edit(source, target, names, 4)
        reverse = typed_signed_edit(target, source, names, 4)
        self.assertGreater(forward[2, 1, 1], 0)
        self.assertGreater(reverse[3, 1, 1], 0)
        self.assertEqual(forward[4 + 1, 1, 1], 1)
        self.assertEqual(forward[4 + 4 + 3, 1, 1], 1)

    def test_model_api_has_no_target_route_or_position_input_and_dual_outputs(self):
        signature = inspect.signature(CSIPairsFormalModel.state)
        self.assertEqual(list(signature.parameters), ["self", "visible_patches", "maps", "radio", "masks"])
        model = CSIPairsFormalModel(
            patch_count=8,
            patch_dim=2,
            map_channels=3,
            action_channels=12,
            radio_dim=4,
            latent_dim=12,
            state_dim=12,
            map_dim=8,
            hidden_dim=24,
            attention_heads=3,
        )
        state = model.state(
            torch.zeros(2, 8, 2), torch.zeros(2, 3, 8, 8), torch.zeros(2, 4), torch.ones(2, 8, dtype=torch.bool)
        )
        latent, physical = model.predict(state, torch.zeros(2, 12, 8, 8), torch.tensor([0, 7]))
        self.assertEqual(tuple(latent.shape), (2, 12))
        self.assertEqual(tuple(physical.shape), (2, 2))

    def test_model_has_no_batchnorm_and_batch_samples_are_isolated(self):
        model = CSIPairsFormalModel(
            patch_count=4,
            patch_dim=4,
            map_channels=3,
            action_channels=12,
            radio_dim=4,
            latent_dim=8,
            state_dim=8,
            map_dim=8,
            hidden_dim=16,
            attention_heads=2,
        ).eval()
        self.assertFalse(
            any(isinstance(module, torch.nn.modules.batchnorm._BatchNorm) for module in model.modules())
        )
        patches = torch.randn(2, 4, 4)
        maps = torch.randn(2, 3, 8, 8)
        radio = torch.randn(2, 4)
        masks = torch.zeros(2, 4, dtype=torch.bool)
        with torch.no_grad():
            first = model.state(patches, maps, radio, masks)[0].clone()
            patches[1] = torch.randn_like(patches[1]) * 100
            maps[1] = torch.randn_like(maps[1]) * 100
            radio[1] = torch.randn_like(radio[1]) * 100
            repeated = model.state(patches, maps, radio, masks)[0]
        torch.testing.assert_close(first, repeated, rtol=0.0, atol=0.0)

    def test_f_inherits_complete_teacher_encoder_and_uses_context_pose(self):
        teacher = CSIMaskedTeacher(2, 2, 2, 8, 2, 2, 1)
        model = CSIPairsFormalModel(
            patch_count=4,
            patch_rows=2,
            patch_columns=2,
            patch_dim=2,
            map_channels=3,
            action_channels=12,
            radio_dim=11,
            latent_dim=8,
            state_dim=8,
            map_dim=8,
            hidden_dim=16,
            attention_heads=2,
            csi_encoder_layers=2,
        ).eval()
        model.initialize_csi_from_teacher(teacher)
        for name, value in teacher.encoder.state_dict().items():
            torch.testing.assert_close(value, model.csi_encoder.state_dict()[name])
        patches = torch.zeros(1, 4, 2)
        maps = torch.zeros(1, 3, 8, 8)
        masks = torch.zeros(1, 4, dtype=torch.bool)
        first = model.state(patches, maps, torch.zeros(1, 11), masks)
        changed_pose = torch.zeros(1, 11)
        changed_pose[0, -1] = 1.0
        second = model.state(patches, maps, changed_pose, masks)
        self.assertFalse(torch.equal(first, second))

    def test_route_thresholds_are_direction_independent(self):
        forward = route_code(0.2, 0.3, 0.05, 0.1, 0.05, 0.1)
        reverse = route_code(abs(-0.2), abs(-0.3), 0.05, 0.1, 0.05, 0.1)
        self.assertEqual(forward, reverse)

    def test_paired_score_difference_requires_one_match_and_one_alternative(self):
        difference = _paired_score_differences(
            np.asarray([0.8, 0.2]), np.asarray([1, 0]), np.asarray(["pair", "pair"])
        )
        np.testing.assert_allclose(difference, [0.6])
        with self.assertRaisesRegex(RuntimeError, "one matched"):
            _paired_score_differences(
                np.asarray([0.8, 0.7]), np.asarray([1, 1]), np.asarray(["pair", "pair"])
            )

    def test_q_comp_random_order_and_candidate_swap_complement(self):
        labels = randomized_candidate_labels(100, 1234)
        np.testing.assert_array_equal(labels, randomized_candidate_labels(100, 1234))
        self.assertEqual(set(labels.tolist()), {0, 1})
        calibration = TemperatureCalibration(2.5)
        probability = calibration.predict(np.asarray([-2.0, 0.0, 3.0]))
        swapped = calibration.predict(np.asarray([2.0, -0.0, -3.0]))
        np.testing.assert_allclose(probability + swapped, np.ones(3), atol=1e-12)

    def test_empty_conditional_mean_fails(self):
        with self.assertRaisesRegex(RuntimeError, "empty conditional mean"):
            required_mean(torch.empty(0), "active")


class StatisticsTests(unittest.TestCase):
    def test_exact_j_equal_weights_city_k_bank_seed_draw(self):
        rows = _factorial_rows()
        report = exact_factorial_utilities(rows, [0, 8])
        self.assertAlmostEqual(report["utilities"]["endpoint"], 0.0)
        self.assertAlmostEqual(report["interaction"], 0.25)

    def test_hierarchical_bootstrap_declares_all_layers(self):
        report = hierarchical_factorial_interval(_factorial_rows(), [0, 8], 20, 3)
        self.assertEqual(
            report["resampling_layers"],
            ["base_map_cluster_within_fixed_city", "training_seed", "k_positive_label_draw"],
        )

    def test_holm_adjustment_is_monotone_in_sorted_order(self):
        adjusted = holm_adjust([0.01, 0.04, 0.03])
        self.assertTrue(all(0 <= value <= 1 for value in adjusted))
        self.assertGreaterEqual(adjusted[0], 0.01)

    def test_splitting_identical_bank_rows_inside_one_cluster_does_not_reweight_j(self):
        rows = _factorial_rows()
        original = exact_factorial_utilities(rows, [0, 8])
        duplicated = rows + [
            {**row, "bank_id": row["bank_id"] + "-duplicate"}
            for row in rows
            if row["city_id"] == "a" and row["base_map_cluster_id"] == "a1"
        ]
        repeated = exact_factorial_utilities(duplicated, [0, 8])
        self.assertEqual(original["utilities"], repeated["utilities"])
        self.assertEqual(original["interaction"], repeated["interaction"])


class EvidenceAndPathTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path = write_nonscientific_fixture(self.root / "fixture.npz")
        self.dataset = FormalDataset.load(self.path)
        self.config = load_formal_config(SMOKE_CONFIG)

    def tearDown(self):
        self.temporary.cleanup()

    def test_gate_and_claim_identifiers_are_fixed(self):
        self.assertEqual(GATE_IDS, tuple(f"G{i}" for i in range(9)))
        self.assertEqual(CLAIM_IDS, tuple(f"C{i}" for i in range(1, 14)))
        self.assertEqual(set(CLAIM_DEPENDENCIES), set(CLAIM_IDS))
        self.assertEqual(set(complete_gate_vector()), set(GATE_IDS))

    def test_not_assessed_from_later_stage_cannot_erase_upstream_gate(self):
        (self.root / "qualification").mkdir()
        (self.root / "evaluation").mkdir()
        (self.root / "controls").mkdir()
        context = evidence_context(self.config, self.dataset, "FORBIDDEN")
        checkpoint = self.root / "qualification" / "teacher.pt"
        checkpoint.write_bytes(b"teacher")
        write_json(
            self.root / "qualification" / "gate.json",
            {
                "schema_version": QUALIFICATION_SCHEMA,
                "status": "DRY_RUN_PASS_NOT_EVIDENCE",
                "passed": True,
                **context,
                "upstream_gates": complete_gate_vector({"G1": "PASS", "G2": "PASS"}),
                "teacher_checkpoint": str(checkpoint),
                "teacher_checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            },
        )
        write_json(
            self.root / "qualification" / "manifest.json",
            {
                "schema_version": "csi-pairs-formal-stage-manifest-v2.1-v6",
                **context,
                "files": artifact_manifest(self.root / "qualification", evidence=context),
            },
        )
        write_json(
            self.root / "evaluation" / "gate.json",
            {
                **context,
                "gate_vector": complete_gate_vector({"G1": "PASS", "G2": "PASS", "G3": "PASS"}),
            },
        )
        write_json(
            self.root / "controls" / "gate.json",
            {**context, "gate_vector": complete_gate_vector({"G4": "PASS"})},
        )
        result = assemble_claim_evidence(self.config, self.dataset, self.root)
        self.assertEqual(result["gate_vector"]["G1"], "PASS")
        self.assertEqual(result["gate_vector"]["G2"], "PASS")
        self.assertEqual(result["gate_vector"]["G3"], "BLOCKED")
        self.assertEqual(result["gate_vector"]["G4"], "BLOCKED")
        self.assertIn("G3", result["evidence_errors"])
        self.assertIn("G4", result["evidence_errors"])

    def test_evidence_context_propagates_fixture_forbidden(self):
        evidence = evidence_context(self.config, self.dataset, "FORMAL_EXPERIMENT_ALLOWED")
        self.assertTrue(evidence["fixture"])
        self.assertEqual(evidence["scientific_use"], "FORBIDDEN")
        self.assertEqual(len(evidence["dataset_sha256"]), 64)
        self.assertEqual(len(evidence["config_sha256"]), 64)

    def test_candidate_or_forbidden_nonfixture_cannot_start_factorial(self):
        arrays = _archive_arrays(self.path)
        metadata = parse_strict_json(str(arrays["metadata_json"].item()))
        metadata["fixture"] = False
        metadata["scientific_use"] = "CANDIDATE"
        arrays["metadata_json"] = np.asarray(json.dumps(metadata, sort_keys=True, separators=(",", ":")))
        candidate_path = self.root / "candidate.npz"
        np.savez_compressed(candidate_path, **arrays)
        candidate = FormalDataset.load(candidate_path)
        context = evidence_context(self.config, candidate, "FORBIDDEN")
        gate = {
            "schema_version": QUALIFICATION_SCHEMA,
            "passed": True,
            **context,
            "upstream_gates": complete_gate_vector({"G1": "PASS", "G2": "PASS"}),
            "teacher_checkpoint": "/not/read/by-this-check",
            "teacher_checkpoint_sha256": "0" * 64,
        }
        with self.assertRaisesRegex(RuntimeError, "FORMAL_EXPERIMENT_ALLOWED"):
            require_formal_qualification(gate, self.config, candidate, allow_nonscientific_fixture=False)

    def test_path_incidence_and_local_aggregation_are_bounded(self):
        edge = next(self.dataset.directed_edges(0))
        value = path_incidence(
            self.dataset, 0, edge.source_world, edge.target_world, 0, edge.bit_index
        )
        local = localization_path_incidence(self.dataset, 0, edge.source_world, 0)
        self.assertGreaterEqual(value, 0)
        self.assertLessEqual(value, 1)
        self.assertGreaterEqual(local, 0)
        self.assertLessEqual(local, 1)

    def test_noop_path_threshold_comes_from_registered_retrace(self):
        self.assertEqual(_noop_path_threshold(self.config, self.dataset, 0.99), 0.0)

    def test_frozen_map_proposal_is_deterministic_and_uses_typed_actions(self):
        scene = int(self.dataset.indices_for_role("source_calibration_fit")[0])
        world = int(self.dataset.natural_world_index[scene])
        first_maps, first_actions = frozen_map_proposals(
            self.dataset.maps[scene, world],
            self.dataset.radio_config[scene],
            self.dataset.map_channel_names,
            int(self.dataset.metadata["assets"]["material_category_count"]),
            self.config,
        )
        second_maps, second_actions = frozen_map_proposals(
            self.dataset.maps[scene, world],
            self.dataset.radio_config[scene],
            self.dataset.map_channel_names,
            int(self.dataset.metadata["assets"]["material_category_count"]),
            self.config,
        )
        np.testing.assert_array_equal(first_maps, second_maps)
        np.testing.assert_array_equal(first_actions, second_actions)
        self.assertEqual(first_actions.shape[1], 4 + 2 * 4)

    def test_risk_support_threshold_is_frozen_from_selection(self):
        fit_d = np.asarray([-2.0, -1.0, 0.0, 1.0, 2.0, 3.0])
        fit_u = np.asarray([0.0, 0.2, 0.1, 0.4, 0.3, 0.7])
        labels = np.asarray([0, 0, 0, 1, 1, 1])
        selection_d = np.asarray([-5.0, -4.0, 4.0, 5.0])
        selection_u = np.asarray([-2.0, -1.0, 1.0, 2.0])
        calibrator = fit_constrained_risk_calibrator(
            fit_d,
            fit_u,
            labels,
            (selection_d, selection_u, np.asarray([0, 0, 1, 1])),
            self.config,
        )
        transformed = np.clip(
            calibrator.standardization.transform(
                np.column_stack((selection_d, selection_u))
            ),
            -5.0,
            5.0,
        )
        expected = np.quantile(
            calibrator.support.squared_distance(transformed),
            1.0 - float(self.config["risk"]["support_alpha"]),
        )
        self.assertAlmostEqual(calibrator.support.threshold, expected)

    def test_coverage_monotonicity_checks_median_and_p90(self):
        retained = {
            "0.9": {"median_error": 3.0, "p90_error": 6.0},
            "0.75": {"median_error": 2.0, "p90_error": 5.0},
            "0.5": {"median_error": 1.0, "p90_error": 4.0},
        }
        self.assertTrue(_coverage_error_monotonic(retained, 0.0))
        retained["0.5"]["p90_error"] = 5.5
        self.assertFalse(_coverage_error_monotonic(retained, 0.0))

    def test_target_verification_failure_is_explicitly_nonblocking(self):
        context = evidence_context(self.config, self.dataset, "FORBIDDEN")
        gate = {
            "schema_version": DATA_GATE_SCHEMA,
            "passed": True,
            "blocking_passed": True,
            **context,
            "blocking_roles": list(BLOCKING_ROLES),
            "target_and_other_roles_are_nonblocking": True,
            "nonblocking_scene_failures": ["target-scene"],
            "role_status": {
                **{role: "PASS" for role in SOURCE_ROLES},
                "target": "FAIL",
                "external_validation": "PASS",
            },
        }
        self.assertIs(require_data_verification(gate, self.config, self.dataset), gate)
        with self.assertRaisesRegex(RuntimeError, "target"):
            require_verified_roles(gate, self.config, self.dataset, ("target",))

    def test_teacher_checkpoint_hash_is_authenticated(self):
        checkpoint = self.root / "teacher.pt"
        checkpoint.write_bytes(b"frozen-teacher")
        context = evidence_context(self.config, self.dataset, "FORBIDDEN")
        gate = {
            "schema_version": QUALIFICATION_SCHEMA,
            "passed": True,
            **context,
            "upstream_gates": complete_gate_vector({"G1": "PASS", "G2": "PASS"}),
            "teacher_checkpoint": str(checkpoint),
            "teacher_checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        }
        require_formal_qualification(
            gate, self.config, self.dataset, allow_nonscientific_fixture=True
        )
        checkpoint.write_bytes(b"tampered")
        with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
            require_formal_qualification(
                gate, self.config, self.dataset, allow_nonscientific_fixture=True
            )

    def test_manifested_gate_rejects_payload_or_file_mutation(self):
        stage = self.root / "authenticated-stage"
        stage.mkdir()
        context = evidence_context(self.config, self.dataset, "FORBIDDEN")
        gate = {"schema_version": "test-gate-v1", "passed": True, **context}
        write_json(stage / "gate.json", gate)
        write_json(
            stage / "manifest.json",
            {
                "schema_version": "csi-pairs-formal-stage-manifest-v2.1-v6",
                **context,
                "files": artifact_manifest(stage, evidence=context),
            },
        )
        require_stage_manifested_gate(
            stage / "gate.json",
            gate,
            self.config,
            self.dataset,
            schema_version="test-gate-v1",
        )
        mutated = {**gate, "passed": False}
        with self.assertRaisesRegex(RuntimeError, "differs"):
            require_stage_manifested_gate(
                stage / "gate.json",
                mutated,
                self.config,
                self.dataset,
                schema_version="test-gate-v1",
            )
        write_json(stage / "gate.json", mutated)
        with self.assertRaisesRegex(RuntimeError, "mismatched"):
            require_stage_manifested_gate(
                stage / "gate.json",
                mutated,
                self.config,
                self.dataset,
                schema_version="test-gate-v1",
            )

    def test_control_and_scene_id_manifests_are_fail_closed(self):
        controls = {
            "schema_version": "csi-pairs-v6-resource-controls-v1",
            "controls": [{"control_id": name, "command": ["true"]} for name in CONTROL_IDS],
        }
        validate_control_manifest(controls)
        controls["controls"] = controls["controls"][:-1]
        with self.assertRaisesRegex(ValueError, "exact five"):
            validate_control_manifest(controls)
        validate_scene_id_manifest(
            {
                "schema_version": "csi-pairs-v6-scene-id-adapters-v1",
                "adapters": [
                    {"adapter_id": "m", "model_name": "model", "command": ["true"]}
                ],
            }
        )
        validate_external_validity_manifest(
            {
                "schema_version": "csi-pairs-v6-external-validity-adapter-v1",
                "evidence_type": "independent_rt_engine",
                "source_revision": "revision",
                "license_id": "license",
                "command": ["true"],
            }
        )

    def test_cli_exposes_all_fail_closed_stages(self):
        help_text = build_parser().format_help()
        for command in (
            "run-evaluation",
            "run-risk",
            "run-path",
            "run-external-baselines",
            "verify-data",
            "run-resource-controls",
            "run-scene-id-audit",
            "run-external-validity",
            "run-literature-resources",
            "run-rt-calibration",
            "run-shuffled-pair-control",
            "run-retention-audit",
            "assemble-claims",
        ):
            self.assertIn(command, help_text)


class WiGATrAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path = self.root / "fixture.npz"
        write_nonscientific_fixture(self.path)
        self.dataset = FormalDataset.load(self.path)

    def tearDown(self):
        self.temporary.cleanup()

    def test_paper_dose_config_and_vendor_snapshot_are_frozen(self):
        config = load_wigatr_config(
            ROOT / "formal_v2/configs/wigatr_official_v1.json"
        )
        self.assertEqual(config["model"]["num_blocks"], 32)
        self.assertEqual(config["model"]["hidden_mv_channels"], 16)
        self.assertEqual(config["model"]["hidden_s_channels"], 32)
        self.assertEqual(config["model"]["num_heads"], 8)
        self.assertEqual(config["training"]["steps"], 200000)
        vendor = ROOT / "formal_v2/external_adapters/vendor/Wi-GATr"
        _verify_vendor_tree(vendor)
        self.assertTrue((vendor / "LICENSE").is_file())

    def test_relative_total_power_is_invariant_to_common_phase(self):
        real = np.asarray([1.2, -0.4, 0.7, 2.1])
        imaginary = np.asarray([-0.3, 0.8, 1.1, -0.6])
        angle = 0.71
        rotated_real = real * np.cos(angle) - imaginary * np.sin(angle)
        rotated_imaginary = real * np.sin(angle) + imaginary * np.cos(angle)
        original = relative_total_power_db(
            np.concatenate((real, imaginary)), 1e-12
        )
        rotated = relative_total_power_db(
            np.concatenate((rotated_real, rotated_imaginary)), 1e-12
        )
        self.assertAlmostEqual(float(original), float(rotated), places=12)

    def test_2p5d_mesh_has_top_exposed_sides_and_materials(self):
        maps = np.zeros((3, 3, 3), dtype=np.float64)
        maps[0, 1, 1] = 1.0
        maps[1, 1, 1] = 2.0
        maps[2, 1, 1] = 3.0
        mesh, materials = grid_to_triangular_mesh(
            maps,
            ("occupancy", "height", "material"),
            resolution_m=0.5,
            origin_xy_m=(-0.75, -0.75),
            occupancy_threshold=0.5,
            minimum_height_m=0.001,
        )
        self.assertEqual(mesh.shape, (10, 3, 3))
        self.assertTrue(np.all(materials == 3))
        self.assertAlmostEqual(float(mesh[..., 2].min()), 0.0)
        self.assertAlmostEqual(float(mesh[..., 2].max()), 2.0)
        empty_mesh, empty_materials = grid_to_triangular_mesh(
            np.zeros_like(maps),
            ("occupancy", "height", "material"),
            resolution_m=0.5,
            origin_xy_m=(-0.75, -0.75),
            occupancy_threshold=0.5,
            minimum_height_m=0.001,
        )
        self.assertEqual(empty_mesh.shape, (0, 3, 3))
        self.assertEqual(empty_materials.shape, (0,))

    def test_geometry_destroyed_preserves_joint_cell_statistics(self):
        maps = np.arange(3 * 4 * 4, dtype=np.float64).reshape(3, 4, 4)
        first = geometry_destroyed_map(maps, "fixed-unit")
        second = geometry_destroyed_map(maps, "fixed-unit")
        self.assertTrue(np.array_equal(first, second))
        self.assertFalse(np.array_equal(first, maps))
        original_cells = sorted(map(tuple, maps.reshape(3, -1).T.tolist()))
        destroyed_cells = sorted(map(tuple, first.reshape(3, -1).T.tolist()))
        self.assertEqual(original_cells, destroyed_cells)

    def test_common_unit_registry_excludes_target_support(self):
        routes = {}
        scenes = np.concatenate(
            (
                self.dataset.indices_for_role("source_final_unseen_bank"),
                self.dataset.indices_for_role("target"),
            )
        )
        for scene_value in scenes:
            scene = int(scene_value)
            for edge in self.dataset.directed_edges(scene):
                for position in range(self.dataset.position_count):
                    routes[(scene, edge.source_world, edge.target_world, position)] = (
                        2 if edge.bit_index == 0 else 0
                    )
        units = build_six_condition_units(
            self.dataset, SimpleNamespace(alignment_route=routes)
        )
        self.assertGreater(len(units), 0)
        for unit in units:
            if str(self.dataset.scene_roles[unit.scene]) == "target":
                self.assertEqual(
                    str(self.dataset.position_roles[unit.scene, unit.position]),
                    "query",
                )
        unit = units[0]
        maps = [condition_map(self.dataset, unit, name) for name in SIX_CONDITIONS]
        self.assertEqual(len(maps), 6)
        self.assertTrue(np.array_equal(maps[-1], np.zeros_like(maps[-1])))

    def test_external_rows_must_cover_the_frozen_registry(self):
        scene = int(self.dataset.indices_for_role("target")[0])
        position = int(np.flatnonzero(self.dataset.position_roles[scene] == "query")[0])
        unit_id = "registered-unit"
        rows = [
            {
                "unit_id": unit_id,
                "model_name": "Wi-GATr",
                "condition": condition,
                "city_id": str(self.dataset.city_ids[scene]),
                "bank_id": str(self.dataset.bank_ids[scene]),
                "position_id": str(self.dataset.position_ids[scene, position]),
                "localization_error_m": "1.0",
                "csi_context_sha256": "a" * 64,
                "query_count": "1",
            }
            for condition in SIX_CONDITIONS
        ]
        _validate_six_condition_rows(
            {"model_name": "Wi-GATr"},
            rows,
            self.dataset,
            expected_unit_ids={unit_id},
            expected_unit_contract={
                unit_id: SimpleNamespace(
                    scene=scene,
                    position=position,
                    csi_context_sha256="a" * 64,
                )
            },
        )
        with self.assertRaisesRegex(ValueError, "common unit registry"):
            _validate_six_condition_rows(
                {"model_name": "Wi-GATr"},
                rows,
                self.dataset,
                expected_unit_ids={unit_id, "missing-unit"},
            )
        rows[0]["csi_context_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "frozen csi_context_sha256"):
            _validate_six_condition_rows(
                {"model_name": "Wi-GATr"},
                rows,
                self.dataset,
                expected_unit_ids={unit_id},
                expected_unit_contract={
                    unit_id: SimpleNamespace(
                        scene=scene,
                        position=position,
                        csi_context_sha256="a" * 64,
                    )
                },
            )
        rows[0]["csi_context_sha256"] = "a" * 64
        support = int(
            np.flatnonzero(self.dataset.position_roles[scene] == "support_pool")[0]
        )
        rows[0]["position_id"] = str(self.dataset.position_ids[scene, support])
        with self.assertRaisesRegex(ValueError, "support_pool"):
            _validate_six_condition_rows(
                {"model_name": "Wi-GATr"}, rows, self.dataset
            )

    def test_execution_manifest_binds_config_training_checkpoint_and_results(self):
        output = self.root / "adapter"
        output.mkdir()
        config_path = output / "adapter_config.json"
        training_path = output / "training_record.json"
        checkpoint_path = output / "checkpoint.pt"
        result_path = output / "six_condition_results.csv"
        write_json(config_path, {"schema_version": "adapter-config"})
        write_json(
            training_path,
            {
                "train_role": "source_encoder_train",
                "selection_role": "source_method_selection",
                "target_roles_read": [],
            },
        )
        checkpoint_path.write_bytes(b"checkpoint")
        write_csv(result_path, [{"result": 1}])
        command = ["python", "adapter.py"]
        adapter = {
            "adapter_id": "wigatr",
            "model_name": "Wi-GATr",
            "implementation_status": "official-code-adaptation",
            "source_revision": "revision",
            "command": command,
        }
        execution = {
            "schema_version": "csi-pairs-v6-external-execution-v2",
            "adapter_id": "wigatr",
            "model_name": "Wi-GATr",
            "implementation_status": "official-code-adaptation",
            "source_revision": "revision",
            "dataset_sha256": sha256_file(self.path),
            "adapter_config_path": config_path.name,
            "adapter_config_sha256": sha256_file(config_path),
            "training_record_path": training_path.name,
            "training_record_sha256": sha256_file(training_path),
            "checkpoint_path": checkpoint_path.name,
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "command_sha256": hashlib.sha256(
                json.dumps(command, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "results_sha256": sha256_file(result_path),
        }
        write_json(output / "execution_manifest.json", execution)
        validate_external_execution_manifest(
            adapter, output, result_path, self.dataset
        )
        training = json.loads(training_path.read_text())
        training["target_roles_read"] = ["target"]
        write_json(training_path, training)
        execution["training_record_sha256"] = sha256_file(training_path)
        write_json(output / "execution_manifest.json", execution)
        with self.assertRaisesRegex(RuntimeError, "source-only"):
            validate_external_execution_manifest(
                adapter, output, result_path, self.dataset
            )

    def test_inverse_localizer_api_has_no_true_position_argument(self):
        parameters = inspect.signature(inverse_localize_power).parameters
        self.assertNotIn("true_position", parameters)

    def test_inverse_localizer_optimizes_only_from_public_bounds_and_power(self):
        class ToyBatch:
            @classmethod
            def from_data_list(cls, _values):
                return cls()

            def to(self, _device):
                return self

        class ToyPowerModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.anchor = torch.nn.Parameter(torch.zeros(()))

            def forward(self, _batch, overrides):
                receiver = overrides["rx"]
                value = receiver[0] + 0.5 * receiver[1] + 0.0 * self.anchor
                return value.reshape(1, 1)

        runtime = {
            "torch": torch,
            "Batch": ToyBatch,
            "tokenize_scene": lambda *_args, **_kwargs: object(),
        }
        config = load_wigatr_config(
            ROOT / "formal_v2/configs/wigatr_official_v1.json"
        )
        config["inverse"]["steps"] = 80
        config["inverse"]["restarts"] = 3
        prediction = inverse_localize_power(
            runtime,
            ToyPowerModel(),
            self.dataset,
            self.dataset.maps[0, 0],
            self.dataset.bs_pose[0, :3],
            observed_power=1.25,
            bounds=((-4.0, 4.0), (-4.0, 4.0)),
            config=config,
            num_materials=int(
                self.dataset.metadata["assets"]["material_category_count"]
            ),
            restart_salt="test-without-target-position",
        )
        self.assertTrue(np.all(np.isfinite(prediction)))
        self.assertTrue(np.all(prediction >= -4.0))
        self.assertTrue(np.all(prediction <= 4.0))
        self.assertLess(
            abs(float(prediction[0] + 0.5 * prediction[1]) - 1.25), 0.05
        )


class WaibuIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "fixture.npz"
        write_nonscientific_fixture(self.path)
        self.dataset = FormalDataset.load(self.path)

    def tearDown(self):
        self.temporary.cleanup()

    def test_every_waibu_resource_is_hash_authenticated(self):
        registry = parse_strict_json(
            (ROOT / "formal_v2/configs/waibu_resources_v1.json").read_text()
        )
        rows = validate_resource_registry(registry, ROOT / "waibu")
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["status"] == "PASS" for row in rows))
        registry["resources"][0]["sha256"] = "0" * 64
        changed = validate_resource_registry(registry, ROOT / "waibu")
        self.assertEqual(changed[0]["status"], "FAIL")

    def test_representation_registry_preserves_paper_labels_and_roles(self):
        config = load_representation_config(
            ROOT / "formal_v2/configs/representation_baselines_v1.json"
        )
        self.assertEqual(
            [row["model_name"] for row in config["models"]],
            ["CSI-MAE", "CSI-CLIP", "CSI-CLIP++", "ContraWiMAE", "WWM"],
        )
        self.assertEqual(config["source_roles"]["pretrain"], "source_encoder_train")
        self.assertEqual(config["source_roles"]["selection"], "source_method_selection")

    def test_csi_mae_controlled_model_runs_masked_backward(self):
        config = load_representation_config(
            ROOT / "formal_v2/configs/representation_baselines_smoke_v1.json"
        )["models"][0]
        spec = PatchSpec.from_metadata(self.dataset.metadata)
        model = build_representation_model(
            "CSI-MAE",
            spec,
            self.dataset.maps.shape[2],
            self.dataset.radio_config.shape[1] + 9,
            config,
        )
        scene = int(self.dataset.indices_for_role("source_encoder_train")[0])
        normalizer = fit_representation_normalizer(
            self.dataset, self.dataset.indices_for_role("source_encoder_train")
        )
        batch = make_representation_batch(
            self.dataset,
            [(scene, 0, 0), (scene, 1, 1)],
            normalizer,
            torch.device("cpu"),
        )
        loss = model.pretraining_loss(batch, config["mask_fraction"])
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertEqual(model.encode(batch).shape, (2, config["dim"]))

    def test_all_controlled_map_models_have_real_gradients(self):
        scene = int(self.dataset.indices_for_role("source_encoder_train")[0])
        normalizer = _fit_data_normalizer(self.dataset)
        files = (
            "controlled_map_smoke_v1.json",
            "wiser_controlled_v1.json",
            "rfir_controlled_v1.json",
        )
        for file_name in files:
            config = load_controlled_map_config(ROOT / "formal_v2/configs" / file_name)
            config["model"].update(
                {
                    "hidden_dim": 16,
                    "scene_dim": 16,
                    "heads": 4,
                    "layers": 1,
                    "grid_size": 4,
                    "corridor_tokens": 4,
                    "tap_count": 2,
                    "maximum_primitives": 16,
                }
            )
            model, _ = build_controlled_model(config, self.dataset)
            batch = controlled_batch(
                self.dataset,
                [(scene, 0, 0), (scene, 1, 1)],
                normalizer,
                torch.device("cpu"),
                config["method"],
            )
            loss = controlled_loss(model, config["method"], batch)
            loss.backward()
            gradients = [parameter.grad for parameter in model.parameters() if parameter.requires_grad]
            self.assertTrue(torch.isfinite(loss), config["method"])
            self.assertTrue(any(value is not None and torch.any(value != 0) for value in gradients), config["method"])
            if config["method"] in {"wiser", "rfir"}:
                with torch.no_grad():
                    first = model(
                        batch["maps"], batch["tx"], batch["context"], batch["receiver"],
                        batch["origin"], batch["resolution"],
                    )
                    second = model(
                        batch["maps"], batch["tx"], batch["context"] + 1.0, batch["receiver"],
                        batch["origin"], batch["resolution"],
                    )
                first_tensor = first[1] if isinstance(first, tuple) else first
                second_tensor = second[1] if isinstance(second, tuple) else second
                self.assertFalse(torch.equal(first_tensor, second_tensor), config["method"])

    def test_complete_map_manifest_has_four_distinct_c1_models(self):
        manifest = parse_strict_json(
            (ROOT / "formal_v2/external_adapters/all_map_adapters_v1.json").read_text()
        )
        validate_external_manifest(manifest)
        self.assertEqual(
            {row["model_name"] for row in manifest["adapters"]},
            {"SigMap", "Wi-GATr", "WiSER", "RFIR"},
        )

    def test_cli_exposes_resource_and_representation_stages(self):
        parser = build_parser()
        help_text = parser.format_help()
        self.assertIn("verify-waibu-resources", help_text)
        self.assertIn("run-representation-baselines", help_text)


def _archive_arrays(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {name: np.asarray(archive[name]).copy() for name in archive.files}


def _factorial_rows():
    rows = []
    # City A has three banks, city B one; k=8 has two draws. Equal macro layers must ignore both imbalances.
    for arm in ("endpoint", "alignment", "response", "full"):
        for city, banks in (("a", ("a1", "a2", "a3")), ("b", ("b1",))):
            for bank in banks:
                for seed in (1, 2):
                    rows.append(_row(arm, city, bank, seed, 0, 0, 0.0))
                    for draw in (0, 1):
                        full_value = 1.0 if city == "a" else 0.0
                        value = full_value if arm == "full" else 0.0
                        rows.append(_row(arm, city, bank, seed, 8, draw, value))
    return rows


def _row(arm, city, bank, seed, budget, draw, utility):
    return {
        "arm": arm,
        "city_id": city,
        "bank_id": bank,
        "base_map_cluster_id": bank,
        "seed": seed,
        "budget": budget,
        "draw": draw,
        "utility_neg_log_median": utility,
    }


if __name__ == "__main__":
    unittest.main()
