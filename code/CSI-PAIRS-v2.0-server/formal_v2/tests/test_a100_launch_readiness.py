from __future__ import annotations

import math
import multiprocessing
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import torch

from formal_v2.formal_claims import _validate_stage_bound_input
from formal_v2.formal_metrics import (
    binary_auroc,
    binary_nll,
    brier_score,
    expected_calibration_error,
    spearman_correlation,
)
from formal_v2.formal_factorial import _run_training_jobs
from formal_v2.formal_external_validity import (
    _load_external_csi,
    _load_rt_scene_manifest,
    _stage_independent_source_assets,
    _validate_manifest as validate_external_validity_manifest,
    _verify_archive_inputs,
    require_claim_eligible_manifest,
    require_independent_primary_engine,
)
from formal_v2.formal_model import (
    _DeterministicAdaptiveAvgPool2d,
    portable_state_dict,
    resolve_execution_device,
    resolve_execution_devices,
)
from formal_v2.formal_qualification import _qualification_scientific_use
from formal_v2.sionna_osm_candidate import (
    PATH_ANGLE_QUANTIZATION_RAD,
    SIONNA_DRJIT_THREADS,
    SIONNA_MITSUBA_VARIANT,
    _extract_paths,
    _sionna_bootstrap_environment,
    _regeneration_executor,
    _select_nonoverlapping_bank_candidates,
    _stable_path_id,
    _validate_shard_runtime,
    load_config,
    sha256_file,
)


class MetricInputContractTests(unittest.TestCase):
    def test_binary_metrics_match_hand_calculations(self):
        labels = np.asarray([0, 1, 0, 1])
        probabilities = np.asarray([0.1, 0.9, 0.2, 0.8])
        self.assertEqual(binary_auroc(labels, probabilities), 1.0)
        expected_nll = -float(
            np.mean(
                labels * np.log(probabilities)
                + (1 - labels) * np.log(1 - probabilities)
            )
        )
        self.assertAlmostEqual(binary_nll(labels, probabilities), expected_nll)
        self.assertAlmostEqual(
            brier_score(labels, probabilities),
            float(np.mean((probabilities - labels) ** 2)),
        )
        self.assertAlmostEqual(
            expected_calibration_error(labels, probabilities, bins=2), 0.15
        )
        self.assertEqual(
            spearman_correlation(np.asarray([1, 2, 3]), np.asarray([3, 2, 1])),
            -1.0,
        )

    def test_metrics_reject_broadcast_nonfinite_and_invalid_values(self):
        labels = np.asarray([0, 1])
        probabilities = np.asarray([0.25, 0.75])
        for function in (binary_nll, brier_score, expected_calibration_error):
            with self.subTest(function=function.__name__, case="broadcast"):
                with self.assertRaises(ValueError):
                    function(labels[:, None], probabilities)
            with self.subTest(function=function.__name__, case="label"):
                with self.assertRaises(ValueError):
                    function(np.asarray([0, 2]), probabilities)
            with self.subTest(function=function.__name__, case="probability"):
                with self.assertRaises(ValueError):
                    function(labels, np.asarray([-0.1, 1.1]))
        with self.assertRaises(ValueError):
            binary_auroc(labels, np.asarray([0.1, math.inf]))
        with self.assertRaises(ValueError):
            spearman_correlation(np.asarray([1.0, math.nan]), np.asarray([1.0, 2.0]))


class ExecutionDeviceContractTests(unittest.TestCase):
    def test_deterministic_pool_matches_adaptive_average_reference(self):
        pool = _DeterministicAdaptiveAvgPool2d((4, 4))
        for shape in ((2, 3, 8, 8), (1, 2, 9, 11), (1, 1, 16, 12)):
            values = torch.arange(np.prod(shape), dtype=torch.float32).reshape(shape)
            values.requires_grad_(True)
            actual = pool(values)
            expected = torch.nn.functional.adaptive_avg_pool2d(values, (4, 4))
            self.assertTrue(torch.allclose(actual, expected, atol=1e-6, rtol=0.0))
            actual.sum().backward()
            self.assertTrue(torch.all(torch.isfinite(values.grad)))

    def test_fixture_defaults_to_cpu_and_formal_data_rejects_cpu(self):
        fixture = SimpleNamespace(is_fixture=True)
        formal = SimpleNamespace(is_fixture=False)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CSI_PAIRS_DEVICE", None)
            os.environ.pop("CSI_PAIRS_DEVICES", None)
            self.assertEqual(resolve_execution_device(fixture), torch.device("cpu"))
        with self.assertRaisesRegex(RuntimeError, "requires an NVIDIA CUDA device"):
            resolve_execution_device(formal, "cpu")

    def test_multi_gpu_inventory_is_explicit_unique_and_ordered(self):
        fixture = SimpleNamespace(is_fixture=True)
        with (
            patch.dict(os.environ, {"CSI_PAIRS_DEVICES": "cuda:0,cuda:1"}),
            patch("formal_v2.formal_model.torch.cuda.is_available", return_value=True),
            patch("formal_v2.formal_model.torch.cuda.device_count", return_value=2),
        ):
            self.assertEqual(
                resolve_execution_devices(fixture),
                (torch.device("cuda:0"), torch.device("cuda:1")),
            )
        with (
            patch.dict(os.environ, {"CSI_PAIRS_DEVICES": "cuda:0,cuda:0"}),
            patch("formal_v2.formal_model.torch.cuda.is_available", return_value=True),
            patch("formal_v2.formal_model.torch.cuda.device_count", return_value=2),
        ):
            with self.assertRaisesRegex(RuntimeError, "duplicate"):
                resolve_execution_devices(fixture)

    def test_checkpoint_state_is_an_independent_cpu_copy(self):
        module = torch.nn.Linear(3, 2)
        state = portable_state_dict(module)
        for name, value in module.state_dict().items():
            self.assertEqual(state[name].device.type, "cpu")
            self.assertNotEqual(state[name].data_ptr(), value.data_ptr())
            self.assertTrue(torch.equal(state[name], value))

    def test_two_device_scheduler_serializes_each_device_and_preserves_job_order(self):
        class Model:
            def __init__(self, job_index):
                self.job_index = job_index
                self.device = "cpu"

            def to(self, device):
                self.device = str(device)
                return self

        barrier = threading.Barrier(2)
        calls = {"cuda:0": [], "cuda:1": []}

        def train(
            _config,
            _corpus,
            seed,
            arm,
            _pilot,
            *,
            device,
            prepared_model,
            stop_event,
        ):
            self.assertEqual(prepared_model.device, device)
            self.assertFalse(stop_event.is_set())
            calls[device].append(prepared_model.job_index)
            barrier.wait(timeout=2.0)
            return prepared_model, {"seed": seed, "arm": arm, "execution_device": device}

        jobs = {"cuda:0": [], "cuda:1": []}
        expected = []
        for job_index in range(12):
            device = f"cuda:{job_index % 2}"
            seed = 100 + job_index // 4
            arm = ("endpoint", "alignment", "response", "full")[job_index % 4]
            model = Model(job_index)
            jobs[device].append((job_index, seed, arm, model))
            expected.append((seed, arm))
        with patch("formal_v2.formal_factorial._train_arm", side_effect=train):
            trained = _run_training_jobs({}, object(), {}, jobs)
        self.assertEqual(
            [(row[1]["seed"], row[1]["arm"]) for row in trained],
            expected,
        )
        self.assertEqual(calls["cuda:0"], [0, 2, 4, 6, 8, 10])
        self.assertEqual(calls["cuda:1"], [1, 3, 5, 7, 9, 11])
        self.assertTrue(all(model.device == "cpu" for model, _row in trained))


class SionnaFormalRendererContractTests(unittest.TestCase):
    def test_stable_path_identity_distinguishes_aoa_and_aod(self):
        surfaces = np.asarray([100, 102, -1], dtype=np.int64)
        vertices = np.asarray(
            [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [0.0, 0.0, 0.0]],
            dtype=np.float64,
        )
        reference = np.asarray([1.1, 2.2, 1.3, -2.4], dtype=np.float64)
        changed_aoa = reference.copy()
        changed_aoa[1] += 2.0 * PATH_ANGLE_QUANTIZATION_RAD
        changed_aod = reference.copy()
        changed_aod[3] += 2.0 * PATH_ANGLE_QUANTIZATION_RAD
        reference_id = _stable_path_id(surfaces, 1.25e-7, vertices, reference)
        self.assertNotEqual(
            reference_id,
            _stable_path_id(surfaces, 1.25e-7, vertices, changed_aoa),
        )
        self.assertNotEqual(
            reference_id,
            _stable_path_id(surfaces, 1.25e-7, vertices, changed_aod),
        )

    def test_numerical_duplicate_paths_are_merged_without_losing_power(self):
        invalid = np.iinfo(np.uint32).max
        objects = np.full((3, 1, 1, 2), invalid, dtype=np.uint32)
        objects[0, 0, 0] = 7
        vertices = np.zeros((3, 1, 1, 2, 3), dtype=np.float64)
        vertices[0, 0, 0, 0] = [1.0, 2.0, 3.0]
        vertices[0, 0, 0, 1] = [1.0 + 1e-6, 2.0, 3.0]
        angles = np.asarray([[[1.0, 1.0 + 1e-6]]], dtype=np.float64)
        paths = SimpleNamespace(
            valid=np.ones((1, 1, 2), dtype=np.bool_),
            tau=np.asarray([[[1.25e-7, 1.25e-7 + 1e-14]]]),
            objects=objects,
            vertices=vertices,
            phi_r=angles,
            theta_r=np.asarray([[[1.1, 1.1]]]),
            phi_t=np.asarray([[[-2.0, -2.0]]]),
            theta_t=np.asarray([[[1.2, 1.2]]]),
            a=(
                np.asarray([[[[[1.0, 2.0]]]]]),
                np.zeros((1, 1, 1, 1, 2), dtype=np.float64),
            ),
        )
        path_ids, path_power, path_surfaces = _extract_paths(
            paths,
            {7: 102},
            position_count=1,
            max_paths=4,
            max_depth=3,
        )
        self.assertEqual(np.count_nonzero(path_ids[0] >= 0), 1)
        self.assertEqual(path_power[0, path_ids[0] >= 0].tolist(), [5.0])
        self.assertEqual(path_surfaces[0, path_ids[0] >= 0][0].tolist(), [102, -1, -1])

    def test_verified_candidate_earns_formal_use_only_after_g1_and_g2(self):
        candidate = SimpleNamespace(
            is_fixture=False,
            metadata={"scientific_use": "CANDIDATE"},
        )
        self.assertEqual(_qualification_scientific_use(candidate, False), "FORBIDDEN")
        self.assertEqual(
            _qualification_scientific_use(candidate, True),
            "FORMAL_EXPERIMENT_ALLOWED",
        )
        candidate.metadata["scientific_use"] = "FORBIDDEN"
        self.assertEqual(_qualification_scientific_use(candidate, True), "FORBIDDEN")
        candidate.metadata["scientific_use"] = "CANDIDATE"
        candidate.is_fixture = True
        self.assertEqual(_qualification_scientific_use(candidate, True), "FORBIDDEN")

    def test_precomputed_independent_rt_archive_is_diagnostic_only(self):
        manifest = {
            "schema_version": "csi-pairs-v6-external-validity-archive-v1",
            "evidence_type": "independent_rt_engine",
            "engine_family": "wireless-insite",
            "source_revision": "wireless-insite@3.4.4",
            "license_id": "USER-SUPPLIED-LICENSE",
            "external_csi_path": "external_csi.npz",
            "external_csi_sha256": "a" * 64,
            "engine_config_path": "engine-config.json",
            "engine_config_sha256": "c" * 64,
            "rt_scene_manifest_path": "rt_scene_manifest.json",
            "rt_scene_manifest_sha256": "b" * 64,
        }
        validate_external_validity_manifest(manifest)
        with self.assertRaisesRegex(RuntimeError, "DIAGNOSTIC_NOT_CLAIM"):
            require_claim_eligible_manifest(manifest)
        dataset = SimpleNamespace(
            is_fixture=False,
            engine_config={
                "engine": {
                    "name": "NVIDIA Sionna RT PathSolver",
                    "sionna_revision": "04ddb9312116b408093b9d3ad363a3df355093a6",
                }
            },
        )
        require_independent_primary_engine(dataset, manifest)
        same_engine = dict(manifest)
        same_engine["source_revision"] = "sionna@different-revision"
        for alias in ("sionna", "Sionna RT", "NVIDIA-Sionna-RT", "sionna_rt"):
            with self.subTest(alias=alias):
                same_engine["engine_family"] = alias
                with self.assertRaisesRegex(RuntimeError, "not independent"):
                    require_independent_primary_engine(dataset, same_engine)

    def test_primary_plus_epsilon_archive_cannot_satisfy_formal_g8(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            primary = np.ones((1, 2, 1, 4), dtype=np.float64)
            dataset = SimpleNamespace(
                csi_clean=primary,
                scene_ids=np.asarray(["external-a"]),
                position_ids=np.asarray([["p-a"]]),
                position_count=1,
                world_count=2,
                channel_count=4,
                indices_for_role=lambda role: np.asarray([0], dtype=np.int64),
            )
            archive = root / "external_csi.npz"
            np.savez(
                archive,
                scene_ids=np.asarray(["external-a"]),
                position_ids=np.asarray([["p-a"]]),
                external_csi=primary + 1e-12,
            )
            self.assertEqual(_load_external_csi(archive, dataset).shape, primary.shape)
            manifest = {
                "schema_version": "csi-pairs-v6-external-validity-archive-v1",
                "evidence_type": "independent_rt_engine",
                "engine_family": "claimed-independent-engine",
                "source_revision": "claimed-revision",
                "license_id": "CLAIMED-LICENSE",
                "external_csi_path": archive.name,
                "external_csi_sha256": sha256_file(archive),
                "engine_config_path": "engine-config.bin",
                "engine_config_sha256": "c" * 64,
                "rt_scene_manifest_path": "scene.json",
                "rt_scene_manifest_sha256": "d" * 64,
            }
            with self.assertRaisesRegex(RuntimeError, "DIAGNOSTIC_NOT_CLAIM"):
                require_claim_eligible_manifest(manifest)

    def test_independent_rt_scene_manifest_binds_every_external_world(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset_path = root / "dataset.npz"
            dataset_path.write_bytes(b"formal-dataset")
            dataset = SimpleNamespace(
                source_path=dataset_path,
                scene_ids=np.asarray(["external-a", "external-b"]),
                world_count=2,
                position_count=1,
                channel_count=4,
                position_ids=np.asarray([["p-a"], ["p-b"]]),
                csi_clean=np.zeros((2, 2, 1, 4), dtype=np.float64),
                canonical_map_sha256=np.asarray(
                    [["1" * 64, "2" * 64], ["3" * 64, "4" * 64]]
                ),
                indices_for_role=lambda role: (
                    np.asarray([0, 1], dtype=np.int64)
                    if role == "external_validation"
                    else np.asarray([], dtype=np.int64)
                ),
            )
            adapter = {
                "schema_version": "csi-pairs-v6-external-validity-archive-v1",
                "evidence_type": "independent_rt_engine",
                "engine_family": "wireless-insite",
                "source_revision": "wireless-insite@3.4.4",
                "license_id": "USER-SUPPLIED-LICENSE",
                "external_csi_path": "external_csi.npz",
                "external_csi_sha256": "a" * 64,
                "engine_config_path": "engine-config.json",
                "engine_config_sha256": "e" * 64,
                "rt_scene_manifest_path": "rt_scene_manifest.json",
                "rt_scene_manifest_sha256": "b" * 64,
            }
            worlds = []
            for scene in range(2):
                for world in range(2):
                    asset = root / f"asset-{scene}-{world}.bin"
                    asset.write_bytes(f"independent-asset-{scene}-{world}".encode("ascii"))
                    worlds.append(
                        {
                            "scene_id": str(dataset.scene_ids[scene]),
                            "world": world,
                            "canonical_map_sha256": str(
                                dataset.canonical_map_sha256[scene, world]
                            ),
                            "source_asset_id": f"asset-{scene}-{world}",
                            "source_asset_path": asset.name,
                            "source_asset_sha256": sha256_file(asset),
                        }
                    )
            context = {
                "schema_version": "csi-pairs-v6-independent-rt-scene-manifest-v1",
                "dataset_sha256": sha256_file(dataset_path),
                "engine_family": "wireless-insite",
                "engine_name": "Wireless InSite",
                "engine_revision": "wireless-insite@3.4.4",
                "configuration_sha256": "e" * 64,
                "license_id": "USER-SUPPLIED-LICENSE",
                "worlds": worlds,
            }
            context_path = root / "context.json"
            from formal_v2.formal_io import write_json

            engine_config = root / "engine-config.json"
            engine_config.write_text('{"max_reflections":6}\n', encoding="ascii")
            context["configuration_sha256"] = sha256_file(engine_config)
            write_json(context_path, context)
            external_csi = root / "external_csi.npz"
            np.savez(
                external_csi,
                scene_ids=dataset.scene_ids,
                position_ids=dataset.position_ids,
                external_csi=np.ones((2, 2, 1, 4), dtype=np.float64),
            )
            adapter.update(
                {
                    "external_csi_path": external_csi.name,
                    "external_csi_sha256": sha256_file(external_csi),
                    "engine_config_path": engine_config.name,
                    "engine_config_sha256": sha256_file(engine_config),
                    "rt_scene_manifest_path": context_path.name,
                    "rt_scene_manifest_sha256": sha256_file(context_path),
                }
            )
            resolved = _verify_archive_inputs(adapter, root, dataset)
            self.assertEqual(
                resolved[:3],
                (external_csi.resolve(), context_path.resolve(), engine_config.resolve()),
            )
            self.assertEqual(
                _load_rt_scene_manifest(context_path, dataset, adapter),
                context,
            )
            self.assertEqual(
                resolved[4],
                tuple((root / row["source_asset_path"]).resolve() for row in worlds),
            )
            staged_root = root / "stage"
            staged_root.mkdir()
            staged_context = {
                **context,
                "worlds": [dict(row) for row in context["worlds"]],
            }
            _stage_independent_source_assets(
                staged_context, resolved[4], staged_root
            )
            for index, row in enumerate(staged_context["worlds"]):
                self.assertEqual(row["source_asset_path"], f"source_assets/{index:04d}.bin")
                self.assertEqual(
                    sha256_file(staged_root / row["source_asset_path"]),
                    row["source_asset_sha256"],
                )

            staged_csi = staged_root / "external_csi.npz"
            staged_config = staged_root / "external_engine_config.bin"
            staged_scene = staged_root / "rt_scene_manifest.json"
            staged_manifest = staged_root / "adapter_manifest.json"
            staged_csi.write_bytes(external_csi.read_bytes())
            staged_config.write_bytes(engine_config.read_bytes())
            write_json(staged_scene, staged_context)
            bound_adapter = {
                **adapter,
                "external_csi_path": str(staged_csi.resolve()),
                "external_csi_sha256": sha256_file(staged_csi),
                "engine_config_path": str(staged_config.resolve()),
                "engine_config_sha256": sha256_file(staged_config),
                "rt_scene_manifest_path": str(staged_scene.resolve()),
                "rt_scene_manifest_sha256": sha256_file(staged_scene),
            }
            write_json(staged_manifest, bound_adapter)
            files = [
                {
                    "path": path.relative_to(staged_root).as_posix(),
                    "sha256": sha256_file(path),
                }
                for path in sorted(staged_root.rglob("*"))
                if path.is_file()
            ]
            write_json(staged_root / "manifest.json", {"files": files})
            agreement = {
                "estimate": 1.0,
                "ci95_low": 1.0,
                "ci95_high": 1.0,
                "base_map_cluster_count": 2,
            }
            equivalence = {"passed": True}
            gate = {
                "input_manifest_path": staged_manifest.name,
                "input_manifest_sha256": sha256_file(staged_manifest),
                "execution_mode": "authenticated_precomputed_rt_archive",
                "rt_scene_manifest_path": staged_scene.name,
                "rt_scene_manifest_sha256": sha256_file(staged_scene),
                "external_csi_path": staged_csi.name,
                "external_csi_sha256": sha256_file(staged_csi),
                "external_engine_config_path": staged_config.name,
                "external_engine_config_sha256": sha256_file(staged_config),
                "active_direction_agreement": agreement["estimate"],
                "active_direction_agreement_ci95_low": agreement["ci95_low"],
                "active_direction_agreement_ci95_high": agreement["ci95_high"],
                "active_direction_cluster_count": agreement["base_map_cluster_count"],
                "null_equivalence": equivalence,
                "external_scene_count": 2,
                "adapter_source_path": None,
                "adapter_source_sha256": None,
                "external_runtime_provenance_path": None,
                "external_runtime_provenance_sha256": None,
                "external_runtime_environment_sha256": None,
                "external_runtime_provenance": None,
            }
            config = {
                "external_validity": {
                    "bootstrap_resamples": 100,
                    "null_equivalence_margin": 0.1,
                }
            }
            dataset.is_fixture = False
            dataset.engine_config = {
                "engine": {
                    "name": "NVIDIA Sionna RT PathSolver",
                    "sionna_revision": "04ddb9312116b408093b9d3ad363a3df355093a6",
                }
            }
            patches = (
                patch(
                    "formal_v2.formal_external_validity._expected_external_registry",
                    return_value={},
                ),
                patch(
                    "formal_v2.formal_external_validity._rows_from_external_csi",
                    return_value=[],
                ),
                patch(
                    "formal_v2.formal_external_validity._cluster_direction_interval",
                    return_value=agreement,
                ),
                patch(
                    "formal_v2.formal_external_validity._paired_bank_equivalence",
                    return_value=equivalence,
                ),
            )
            with patches[0], patches[1], patches[2], patches[3]:
                with self.assertRaisesRegex(RuntimeError, "DIAGNOSTIC_NOT_CLAIM"):
                    _validate_stage_bound_input(
                        staged_root / "gate.json", gate, config, "G8", dataset
                    )
            context["worlds"][1]["source_asset_id"] = context["worlds"][0][
                "source_asset_id"
            ]
            write_json(context_path, context)
            with self.assertRaisesRegex(ValueError, "distinct source assets"):
                _load_rt_scene_manifest(context_path, dataset, adapter)

    def test_precomputed_archive_rejects_legacy_sionna_scene_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "legacy-sionna-scene.json"
            path.write_text(
                '{"schema_version":"csi-pairs-v6-sionna-scene-manifest-v1"}\n',
                encoding="ascii",
            )
            archive = {
                "schema_version": "csi-pairs-v6-external-validity-archive-v1"
            }
            with patch(
                "formal_v2.external_adapters.sionna_external_validity.load_scene_manifest",
                return_value={"schema_version": "csi-pairs-v6-sionna-scene-manifest-v1"},
            ):
                with self.assertRaisesRegex(ValueError, "independent RT scene schema"):
                    _load_rt_scene_manifest(path, SimpleNamespace(), archive)

    def test_independent_rt_scene_manifest_authenticates_source_asset_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset_path = root / "dataset.npz"
            dataset_path.write_bytes(b"formal-dataset")
            dataset = SimpleNamespace(
                source_path=dataset_path,
                scene_ids=np.asarray(["external-a"]),
                world_count=2,
                canonical_map_sha256=np.asarray([["1" * 64, "2" * 64]]),
                indices_for_role=lambda role: np.asarray([0], dtype=np.int64),
            )
            archive = {
                "schema_version": "csi-pairs-v6-external-validity-archive-v1",
                "engine_family": "wireless-insite",
                "source_revision": "wireless-insite@3.4.4",
                "license_id": "USER-SUPPLIED-LICENSE",
            }
            assets = []
            worlds = []
            for world in range(2):
                asset = root / f"world-{world}.bin"
                asset.write_bytes(f"asset-{world}".encode("ascii"))
                assets.append(asset)
                worlds.append(
                    {
                        "scene_id": "external-a",
                        "world": world,
                        "canonical_map_sha256": str(
                            dataset.canonical_map_sha256[0, world]
                        ),
                        "source_asset_id": f"asset-{world}",
                        "source_asset_path": asset.name,
                        "source_asset_sha256": sha256_file(asset),
                    }
                )
            payload = {
                "schema_version": "csi-pairs-v6-independent-rt-scene-manifest-v1",
                "dataset_sha256": sha256_file(dataset_path),
                "engine_family": "wireless-insite",
                "engine_name": "Wireless InSite",
                "engine_revision": "wireless-insite@3.4.4",
                "configuration_sha256": "e" * 64,
                "license_id": "USER-SUPPLIED-LICENSE",
                "worlds": worlds,
            }
            path = root / "scene-manifest.json"
            from formal_v2.formal_io import write_json

            def validate(candidate):
                write_json(path, candidate)
                return _load_rt_scene_manifest(path, dataset, archive)

            self.assertEqual(validate(payload), payload)

            missing = {**payload, "worlds": [dict(row) for row in worlds]}
            missing["worlds"][0]["source_asset_path"] = "missing.bin"
            with self.assertRaisesRegex(RuntimeError, "missing or hash-mismatched"):
                validate(missing)

            fake_hash = {**payload, "worlds": [dict(row) for row in worlds]}
            fake_hash["worlds"][0]["source_asset_sha256"] = "f" * 64
            with self.assertRaisesRegex(RuntimeError, "missing or hash-mismatched"):
                validate(fake_hash)

            original = assets[0].read_bytes()
            assets[0].write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeError, "missing or hash-mismatched"):
                validate(payload)
            assets[0].write_bytes(original)

            symlink = root / "world-link.bin"
            symlink.symlink_to(assets[0])
            linked = {**payload, "worlds": [dict(row) for row in worlds]}
            linked["worlds"][0]["source_asset_path"] = symlink.name
            with self.assertRaisesRegex(RuntimeError, "regular file"):
                validate(linked)

            reused = {**payload, "worlds": [dict(row) for row in worlds]}
            reused["worlds"][1]["source_asset_path"] = assets[0].name
            reused["worlds"][1]["source_asset_sha256"] = sha256_file(assets[0])
            with self.assertRaisesRegex(ValueError, "distinct source assets"):
                validate(reused)

            copied_asset = root / "copied-under-new-name.bin"
            copied_asset.write_bytes(assets[0].read_bytes())
            copied = {**payload, "worlds": [dict(row) for row in worlds]}
            copied["worlds"][1]["source_asset_path"] = copied_asset.name
            copied["worlds"][1]["source_asset_sha256"] = sha256_file(copied_asset)
            with self.assertRaisesRegex(ValueError, "distinct source assets"):
                validate(copied)

    def test_generator_script_defaults_to_the_reviewed_sionna_runtime(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "scripts/generate_sionna_osm_formal_candidate.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("CSI_PAIRS_SIONNA_PYTHON", script)
        self.assertIn(".runtime-sionna/venv/bin/python", script)
        self.assertIn("setup_sionna.sh first", script)
        self.assertIn("CSI_PAIRS_RENDER_WORKERS", script)
        self.assertIn('RENDER_WORKERS:-8', script)
        self.assertIn('OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"', script)
        self.assertIn('VECLIB_MAXIMUM_THREADS="${VECLIB_MAXIMUM_THREADS:-1}"', script)

    def test_sionna_setup_has_native_macos_arm64_branch(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "external_adapters/setup_sionna.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('SYSTEM="$(uname -s)"', script)
        self.assertIn('if [[ "${SYSTEM}" == "Darwin" ]]', script)
        self.assertIn("CSI_PAIRS_BREW", script)
        self.assertIn("--prefix llvm@18", script)
        self.assertIn("requirements-sionna-runtime-darwin-arm64.txt", script)
        self.assertIn("requirements-sionna-runtime-linux-x86_64.txt", script)
        self.assertIn("--require-hashes", script)
        self.assertIn("sionna_runtime_lock", script)
        self.assertIn("llvm_ad_mono_polarized", script)
        self.assertIn("drjit.set_thread_count(1)", script)

    def test_a100_runbook_forbids_old_candidate_and_binds_two_devices(self):
        root = Path(__file__).resolve().parents[1]
        runbook = (root / "A100_RUNBOOK.md").read_text(encoding="utf-8")
        self.assertIn("old", runbook.lower())
        self.assertIn("pathless/all-zero", runbook)
        self.assertIn("CSI_PAIRS_DEVICES=cuda:0,cuda:1", runbook)
        self.assertIn("rtol=0", runbook)
        self.assertIn("atol=0", runbook)

    def test_sionna_primary_cannot_reuse_sionna_as_g8_independent_engine(self):
        dataset = SimpleNamespace(
            is_fixture=False,
            engine_config={
                "engine": {
                    "name": "NVIDIA Sionna RT PathSolver",
                    "sionna_revision": "04ddb9312116b408093b9d3ad363a3df355093a6",
                }
            },
        )
        manifest = {
            "schema_version": "csi-pairs-v6-external-validity-adapter-v3",
            "source_revision": "sionna@04ddb9312116b408093b9d3ad363a3df355093a6"
        }
        with self.assertRaisesRegex(RuntimeError, "not independent"):
            require_independent_primary_engine(dataset, manifest)

        dataset.engine_config["engine"] = {
            "name": "independent-commercial-ray-tracer",
            "source_revision": "other-revision",
        }
        require_independent_primary_engine(dataset, manifest)

    def test_regeneration_executor_uses_spawn_context(self):
        context = multiprocessing.get_context("spawn")
        executor = MagicMock()
        with (
            patch("formal_v2.sionna_osm_candidate.multiprocessing.get_context", return_value=context),
            patch("formal_v2.sionna_osm_candidate.ProcessPoolExecutor", return_value=executor) as factory,
        ):
            self.assertIs(_regeneration_executor(8), executor)
        factory.assert_called_once_with(max_workers=8, mp_context=context)

    def test_bank_selection_skips_higher_scoring_overlapping_extent(self):
        candidates = [
            (100.0, 10.0, 0.0, 0.0, []),
            (99.0, 10.0, 244.0, 0.0, []),
            (98.0, 10.0, 300.0, 0.0, []),
            (97.0, 10.0, 0.0, 300.0, []),
        ]
        selected = _select_nonoverlapping_bank_candidates(
            candidates,
            3,
            map_extent_m=256.0,
        )
        self.assertEqual(
            [(row[2], row[3]) for row in selected],
            [(0.0, 0.0), (300.0, 0.0), (0.0, 300.0)],
        )

    def test_checked_in_candidate_uses_single_thread_llvm(self):
        config_path = (
            Path(__file__).resolve().parents[1]
            / "configs"
            / "sionna_osm_formal_candidate_v2.json"
        )
        config = load_config(config_path)
        self.assertEqual(config["renderer"]["mitsuba_variant"], SIONNA_MITSUBA_VARIANT)
        self.assertEqual(config["renderer"]["drjit_threads"], SIONNA_DRJIT_THREADS)
        self.assertEqual(config["map"]["receiver_grid_spacing_m"], 1.5)

    def test_bootstrap_requires_only_python_and_llvm_for_renderer(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            python = project / "formal_v2/external_adapters/.runtime-sionna/venv/bin/python"
            llvm = project / "libLLVM-test.so"
            python.parent.mkdir(parents=True)
            python.touch()
            llvm.touch()
            approved = {"libllvm_path": str(llvm.resolve())}
            with patch(
                "formal_v2.sionna_runtime_lock.approved_library_record",
                return_value=approved,
            ):
                resolved_python, environment = _sionna_bootstrap_environment(
                    project,
                    {"PYTHONPATH": "/existing"},
                    libllvm=llvm,
                )
        self.assertEqual(resolved_python, python.resolve())
        self.assertEqual(environment["DRJIT_LIBLLVM_PATH"], str(llvm.resolve()))
        self.assertEqual(environment["MI_DEFAULT_VARIANT"], SIONNA_MITSUBA_VARIANT)
        self.assertNotIn("LD_PRELOAD", environment)

    def test_runtime_contract_rejects_cuda_variant(self):
        with tempfile.TemporaryDirectory() as temporary:
            llvm = Path(temporary) / "libLLVM-test.so"
            llvm.write_bytes(b"llvm")
            runtime = {
                "python": "3.12.13",
                "sionna": "2.0.1",
                "sionna_rt": "1.2.1",
                "mitsuba": "3.7.1",
                "drjit": "1.2.0",
                "mitsuba_variant": SIONNA_MITSUBA_VARIANT,
                "drjit_thread_count": 1,
                "sionna_revision": "04ddb9312116b408093b9d3ad363a3df355093a6",
                "drjit_libllvm_path": str(llvm),
                "drjit_libllvm_sha256": sha256_file(llvm),
            }
            approved = {"libllvm_sha256": sha256_file(llvm)}
            with patch(
                "formal_v2.sionna_runtime_lock.approved_library_record",
                return_value=approved,
            ):
                _validate_shard_runtime(runtime)
                runtime["mitsuba_variant"] = "cuda_ad_mono_polarized"
                with self.assertRaisesRegex(ValueError, "frozen Sionna runtime"):
                    _validate_shard_runtime(runtime)


if __name__ == "__main__":
    unittest.main()
