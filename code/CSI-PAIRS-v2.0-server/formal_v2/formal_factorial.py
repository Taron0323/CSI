from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .formal_config import ARMS, public_formal_config
from .formal_dataset import FormalDataset
from .formal_evidence import (
    FACTORIAL_SCHEMA,
    bind_rows,
    complete_gate_vector,
    evidence_context,
    require_manifested_formal_qualification,
)
from .formal_io import artifact_manifest, sha256_file, write_csv, write_json
from .formal_localization import (
    adapt_position_head,
    fit_source_position_head,
    predict_position_distribution,
)
from .formal_model import (
    CSIPairsFormalModel,
    LossWeights,
    alignment_active_quartet_loss,
    alignment_null_quartet_loss,
    endpoint_per_sample,
    require_torch,
    squared_rms_error,
    torch,
)
from .formal_protocol import PatchSpec, patchify_csi, typed_signed_edit, zero_typed_edit
from .formal_routing import RouteNormalization, RoutedEdges, fit_route_normalization, route_dataset
from .formal_statistics import (
    bank_only_factorial_interval,
    exact_factorial_utilities,
    hierarchical_factorial_interval,
    holm_adjust,
    interval_decision,
    leave_one_factorial_sensitivity,
    paired_cluster_interval,
    paired_sign_flip_test,
)
from .formal_teacher import TeacherBundle, load_teacher_bundle


ARM_FACTORS = {
    "endpoint": (0.0, 0.0),
    "alignment": (1.0, 0.0),
    "response": (0.0, 1.0),
    "full": (1.0, 1.0),
}


@dataclass(frozen=True)
class TrainingNormalization:
    patch_mean: np.ndarray
    patch_scale: np.ndarray
    latent_mean: np.ndarray
    latent_scale: np.ndarray
    map_scale: np.ndarray
    radio_mean: np.ndarray
    radio_scale: np.ndarray
    action_scale: np.ndarray
    position_mean: np.ndarray
    position_scale: np.ndarray


@dataclass
class TrainingCorpus:
    dataset: FormalDataset
    scenes: tuple[int, ...]
    routed: RoutedEdges
    teacher: TeacherBundle
    normalization: TrainingNormalization
    material_categories: int
    alignment_bank: tuple
    alignment_audit_bank: tuple
    endpoint: dict[int, list[tuple[int, int]]]
    natural_endpoint: dict[int, list[tuple[int, int]]]
    alignment_active: dict[int, list[tuple[int, int, int]]]
    alignment_null: dict[int, list[tuple[int, int, int]]]
    response_all: dict[int, list[tuple[int, int, int, int]]]
    response_active: dict[int, list[tuple[int, int, int, int]]]
    response_null: dict[int, list[tuple[int, int, int, int]]]
    response_bundles: dict[int, list[tuple[int, tuple[int, ...], int, int]]]
    response_active_bundles: dict[int, list[tuple[int, tuple[int, ...], int, int]]]
    response_null_bundles: dict[int, list[tuple[int, tuple[int, ...], int, int]]]


@dataclass(frozen=True)
class StepPlan:
    endpoint: tuple
    natural_endpoint: tuple
    alignment_active: tuple
    alignment_null: tuple
    response_all: tuple
    response_active: tuple
    response_null: tuple
    endpoint_masks: tuple[int, ...]
    natural_masks: tuple[int, ...]
    response_all_masks: tuple[int, ...]
    response_active_masks: tuple[int, ...]
    response_null_masks: tuple[int, ...]
    response_bundle_count: int


def run_formal_factorial(
    config: dict,
    dataset: FormalDataset,
    output_root: str | Path,
    qualification_gate: dict,
    allow_nonscientific_fixture: bool = False,
) -> dict:
    require_torch()
    from .formal_data_verification import require_verified_roles_from_root

    require_verified_roles_from_root(
        output_root,
        config,
        dataset,
        ("source_encoder_train", "source_method_selection", "target"),
    )
    require_manifested_formal_qualification(
        qualification_gate,
        config,
        dataset,
        allow_nonscientific_fixture=allow_nonscientific_fixture,
    )
    teacher_path = Path(str(qualification_gate["teacher_checkpoint"]))
    if sha256_file(teacher_path) != qualification_gate["teacher_checkpoint_sha256"]:
        raise RuntimeError("teacher checkpoint hash does not match the qualification gate")
    teacher = load_teacher_bundle(teacher_path, config)
    output_dir = Path(output_root) / "factorial"
    output_dir.mkdir(parents=True, exist_ok=True)

    train_scenes = dataset.indices_for_role("source_encoder_train")
    selection_scenes = dataset.indices_for_role("source_method_selection")
    route_normalization = fit_route_normalization(dataset, teacher)
    normalization = _training_normalization(dataset, train_scenes, route_normalization, teacher.patch_spec)
    write_json(output_dir / "normalization.json", _normalization_record(normalization))
    train_corpus = _build_corpus(dataset, train_scenes, teacher, config, route_normalization, normalization)
    selection_corpus = _build_corpus(
        dataset, selection_scenes, teacher, config, route_normalization, normalization
    )
    pilot = _pilot_scales(
        config, train_corpus, selection_corpus, int(config["seeds"][0]) + 6001
    )
    write_json(
        output_dir / "frozen_pilot.json",
        {
            "schema_version": "csi-pairs-v6-frozen-pilot-v1",
            "source_roles": ["source_encoder_train", "source_method_selection"],
            "role_permissions": {
                "source_encoder_train": "endpoint-only pilot optimization",
                "source_method_selection": "no-op kappa and loss-scale selection only",
            },
            **pilot,
        },
    )

    models: dict[tuple[int, str], object] = {}
    training_rows = []
    checkpoint_rows = []
    provisional_use = "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    evidence = evidence_context(config, dataset, provisional_use)
    reference_flops = None
    for seed in config["seeds"]:
        for arm in ARMS:
            model, row = _train_arm(
                config,
                train_corpus,
                int(seed),
                arm,
                pilot,
                reference_flops=reference_flops,
            )
            if reference_flops is None:
                reference_flops = row["measured_flops_per_step"]
            checkpoint = output_dir / "checkpoints" / f"seed_{seed}" / f"{arm}.pt"
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            torch.save(
                {
                    "schema_version": "csi-pairs-formal-checkpoint-v2.1-v6",
                    "arm": arm,
                    "seed": int(seed),
                    "model_spec": _model_spec(config, train_corpus),
                    "normalization": _normalization_record(normalization),
                    "teacher_checkpoint_sha256": qualification_gate["teacher_checkpoint_sha256"],
                    "checkpoint_rule": "fixed_final_step_no_target_selection",
                    "state_dict": model.state_dict(),
                    **evidence,
                },
                checkpoint,
            )
            row.update(
                {
                    "checkpoint": str(checkpoint.relative_to(output_dir)),
                    "checkpoint_sha256": sha256_file(checkpoint),
                    "alignment_scale": pilot["alignment_scale"],
                    "response_scale": pilot["response_scale"],
                    "alignment_null_tolerance": pilot["alignment_null_tolerance"],
                }
            )
            training_rows.append(row)
            checkpoint_rows.append(
                {
                    "seed": int(seed),
                    "arm": arm,
                    "path": str(checkpoint.relative_to(output_dir)),
                    "sha256": sha256_file(checkpoint),
                    "parameters": row["parameters"],
                    "measured_flops_per_step": row["measured_flops_per_step"],
                    "teacher_checkpoint_sha256": qualification_gate["teacher_checkpoint_sha256"],
                }
            )
            models[(int(seed), arm)] = model
    write_csv(output_dir / "training_summary.csv", bind_rows(training_rows, evidence))
    write_json(
        output_dir / "checkpoint_index.json",
        {
            "schema_version": "csi-pairs-formal-checkpoint-index-v2.1-v6",
            **evidence,
            "checkpoints": bind_rows(checkpoint_rows, evidence),
        },
    )

    bank_rows, sample_rows = _run_localization(config, dataset, models, normalization, teacher.patch_spec)
    write_csv(output_dir / "localization_per_sample.csv", bind_rows(sample_rows, evidence))
    write_csv(output_dir / "localization_per_bank.csv", bind_rows(bank_rows, evidence))
    summary_rows = _localization_summary(bank_rows)
    write_csv(output_dir / "localization_summary.csv", bind_rows(summary_rows, evidence))
    statistics = _factorial_statistics(config, bank_rows)
    write_json(output_dir / "factorial_statistics.json", {**statistics, **evidence})
    gate = _preliminary_factorial_gate(config, dataset, bank_rows, statistics, evidence)
    write_json(output_dir / "gate.json", gate)
    write_json(
        output_dir / "manifest.json",
        {
            "schema_version": "csi-pairs-formal-stage-manifest-v2.1-v6",
            **evidence,
            "files": artifact_manifest(output_dir, evidence=evidence),
        },
    )
    return gate


def _training_normalization(
    dataset: FormalDataset,
    scenes: np.ndarray,
    route_normalization: RouteNormalization,
    spec: PatchSpec,
) -> TrainingNormalization:
    patch_mean = patchify_csi(route_normalization.channel_mean, spec)
    patch_scale = patchify_csi(route_normalization.channel_scale, spec)
    maps = dataset.maps[scenes]
    map_scale = np.max(np.abs(maps), axis=(0, 1, 3, 4))
    map_scale[map_scale < 1e-9] = 1.0
    radio = np.concatenate((dataset.radio_config[scenes], dataset.bs_pose[scenes]), axis=1)
    radio_mean = radio.mean(axis=0)
    radio_scale = radio.std(axis=0)
    radio_scale[radio_scale < 1e-9] = 1.0
    material_categories = int(dataset.metadata["assets"]["material_category_count"])
    occupancy_index = list(dataset.map_channel_names).index("occupancy")
    height_index = list(dataset.map_channel_names).index("height")
    action_scale = np.ones(4 + 2 * material_categories, dtype=np.float64)
    action_scale[:2] = map_scale[occupancy_index]
    action_scale[2:4] = map_scale[height_index]
    position_values = dataset.positions[scenes].reshape(-1, 2)
    position_mean = position_values.mean(axis=0)
    position_scale = position_values.std(axis=0)
    position_scale[position_scale < 1e-9] = 1.0
    return TrainingNormalization(
        patch_mean=patch_mean,
        patch_scale=patch_scale,
        latent_mean=route_normalization.latent_mean,
        latent_scale=route_normalization.latent_scale,
        map_scale=map_scale,
        radio_mean=radio_mean,
        radio_scale=radio_scale,
        action_scale=action_scale,
        position_mean=position_mean,
        position_scale=position_scale,
    )


def _normalization_record(normalization: TrainingNormalization) -> dict:
    return {
        "source_roles": ["source_encoder_train"],
        "patch_mean": normalization.patch_mean.tolist(),
        "patch_scale": normalization.patch_scale.tolist(),
        "latent_mean": normalization.latent_mean.tolist(),
        "latent_scale": normalization.latent_scale.tolist(),
        "map_scale": normalization.map_scale.tolist(),
        "radio_mean": normalization.radio_mean.tolist(),
        "radio_scale": normalization.radio_scale.tolist(),
        "action_scale": normalization.action_scale.tolist(),
        "position_mean": normalization.position_mean.tolist(),
        "position_scale": normalization.position_scale.tolist(),
    }


def _build_corpus(dataset, scenes, teacher, config, route_normalization, normalization):
    routed = route_dataset(dataset, teacher, config, scenes, normalization=route_normalization)
    scene_tuple = tuple(int(value) for value in scenes)
    endpoint = {}
    natural_endpoint = {}
    alignment_active = {}
    alignment_null = {}
    response_all = {}
    response_active = {}
    response_null = {}
    response_bundles = {}
    response_active_bundles = {}
    response_null_bundles = {}
    for scene in scene_tuple:
        endpoint[scene] = [
            (world, position)
            for world in range(dataset.world_count)
            for position in range(dataset.position_count)
        ]
        natural = int(dataset.natural_world_index[scene])
        natural_endpoint[scene] = [(natural, position) for position in range(dataset.position_count)]
        alignment_active[scene] = []
        alignment_null[scene] = []
        response_all[scene] = []
        response_active[scene] = []
        response_null[scene] = []
        response_bundles[scene] = []
        response_active_bundles[scene] = []
        response_null_bundles[scene] = []
        for edge in dataset.directed_edges(scene):
            for position in range(dataset.position_count):
                if edge.source_world < edge.target_world:
                    route = routed.alignment_route[(scene, edge.source_world, edge.target_world, position)]
                    target = alignment_active if route == 2 else alignment_null if route == 0 else None
                    if target is not None:
                        target[scene].append((edge.source_world, edge.target_world, position))
                for query in range(teacher.patch_spec.patch_count):
                    unit = (edge.source_world, edge.target_world, position, query)
                    response_all[scene].append(unit)
                    route = routed.response_route[(scene, *unit)]
                    if route == 2:
                        response_active[scene].append(unit)
                    elif route == 0:
                        response_null[scene].append(unit)
        targets_by_source = {
            source: tuple(
                sorted(
                    edge.target_world
                    for edge in dataset.directed_edges(scene)
                    if edge.source_world == source
                )
            )
            for source in range(dataset.world_count)
        }
        for source, targets in targets_by_source.items():
            if len(targets) < 2:
                raise RuntimeError("V6 branch bundle requires at least two actions per source state")
            actions = [
                typed_signed_edit(
                    dataset.maps[scene, source],
                    dataset.maps[scene, target],
                    dataset.map_channel_names,
                    int(dataset.metadata["assets"]["material_category_count"]),
                )
                for target in targets
            ]
            if len({np.asarray(action).tobytes() for action in actions}) < 2:
                raise RuntimeError("branch bundle targets are not action-distinguishable")
            for position in range(dataset.position_count):
                for query in range(teacher.patch_spec.patch_count):
                    bundle = (source, targets, position, query)
                    routes = {
                        routed.response_route[(scene, source, target, position, query)]
                        for target in targets
                    }
                    response_bundles[scene].append(bundle)
                    if 2 in routes:
                        response_active_bundles[scene].append(bundle)
                    if 0 in routes:
                        response_null_bundles[scene].append(bundle)
    for name, table in (
        ("endpoint", endpoint),
        ("natural endpoint", natural_endpoint),
        ("alignment active", alignment_active),
        ("alignment null", alignment_null),
        ("response all", response_all),
        ("response active", response_active),
        ("response null", response_null),
    ):
        if not any(table.values()):
            raise RuntimeError(f"no eligible banks for {name}")
    alignment_bank = tuple(entry for entry in teacher.mask_bank if entry.mode == "random_75")
    expected_queries = int(config["factorial"]["alignment_bank_queries"])
    if len(alignment_bank) != expected_queries:
        raise RuntimeError(
            f"frozen B_align must cover every patch exactly once; config={expected_queries}, actual={len(alignment_bank)}"
        )
    return TrainingCorpus(
        dataset=dataset,
        scenes=scene_tuple,
        routed=routed,
        teacher=teacher,
        normalization=normalization,
        material_categories=int(dataset.metadata["assets"]["material_category_count"]),
        alignment_bank=alignment_bank,
        alignment_audit_bank=tuple(
            entry for entry in teacher.audit_mask_bank if entry.mode == "random_75"
        ),
        endpoint=endpoint,
        natural_endpoint=natural_endpoint,
        alignment_active=alignment_active,
        alignment_null=alignment_null,
        response_all=response_all,
        response_active=response_active,
        response_null=response_null,
        response_bundles=response_bundles,
        response_active_bundles=response_active_bundles,
        response_null_bundles=response_null_bundles,
    )


def _make_plan(corpus: TrainingCorpus, batch_size: int, seed: int, step: int) -> StepPlan:
    rng = np.random.default_rng(int(seed) * 1000003 + int(step))
    endpoint = _macro_sample(corpus.endpoint, rng, batch_size, corpus.dataset)
    natural = _macro_sample(corpus.natural_endpoint, rng, batch_size, corpus.dataset)
    alignment_active = _macro_sample(corpus.alignment_active, rng, batch_size, corpus.dataset)
    alignment_null = _macro_sample(corpus.alignment_null, rng, batch_size, corpus.dataset)
    active_bundle_count = max(1, int(batch_size) // 2)
    null_bundle_count = max(1, int(batch_size) - active_bundle_count)
    bundles = _macro_sample(
        corpus.response_active_bundles, rng, active_bundle_count, corpus.dataset
    )
    bundles += _macro_sample(
        corpus.response_null_bundles, rng, null_bundle_count, corpus.dataset
    )
    response_all = []
    for scene, source, targets, position, query in bundles:
        response_all.extend(
            (scene, source, target, position, query) for target in targets
        )
    response_active = [
        unit
        for unit in response_all
        if corpus.routed.response_route[tuple(unit)] == 2
    ]
    response_null = [
        unit
        for unit in response_all
        if corpus.routed.response_route[tuple(unit)] == 0
    ]
    if not response_active or not response_null:
        raise RuntimeError("branch-bundle batch lacks an active or null conditional unit")
    return StepPlan(
        endpoint=tuple(endpoint),
        natural_endpoint=tuple(natural),
        alignment_active=tuple(alignment_active),
        alignment_null=tuple(alignment_null),
        response_all=tuple(response_all),
        response_active=tuple(response_active),
        response_null=tuple(response_null),
        endpoint_masks=tuple(int(rng.integers(0, len(corpus.teacher.mask_bank))) for _ in endpoint),
        natural_masks=tuple(int(rng.integers(0, len(corpus.teacher.mask_bank))) for _ in natural),
        response_all_masks=tuple(_mask_index_for_query(corpus, unit[-1], rng) for unit in response_all),
        response_active_masks=tuple(_mask_index_for_query(corpus, unit[-1], rng) for unit in response_active),
        response_null_masks=tuple(_mask_index_for_query(corpus, unit[-1], rng) for unit in response_null),
        response_bundle_count=len(bundles),
    )


def _macro_sample(table, rng, count, dataset):
    eligible = [scene for scene, values in table.items() if values]
    if not eligible:
        raise RuntimeError("empty eligible-bank conditional sampler")
    by_cluster = {}
    for scene in eligible:
        by_cluster.setdefault(str(dataset.base_map_cluster_ids[scene]), []).append(scene)
    clusters = sorted(by_cluster)
    output = []
    for _ in range(int(count)):
        cluster = clusters[int(rng.integers(0, len(clusters)))]
        scenes = by_cluster[cluster]
        scene = scenes[int(rng.integers(0, len(scenes)))]
        values = table[scene]
        value = values[int(rng.integers(0, len(values)))]
        output.append((scene, *value))
    return output


def _mask_index_for_query(corpus, query, rng):
    candidates = [
        index for index, entry in enumerate(corpus.teacher.mask_bank) if int(entry.query) == int(query)
    ]
    return candidates[int(rng.integers(0, len(candidates)))]


def _new_model(config: dict, corpus: TrainingCorpus, seed: int):
    torch.manual_seed(int(seed))
    spec = _model_spec(config, corpus)
    model = CSIPairsFormalModel(**spec)
    model.initialize_csi_from_teacher(corpus.teacher.teacher)
    return model


def _model_spec(config, corpus):
    dataset = corpus.dataset
    spec = corpus.teacher.patch_spec
    return {
        "patch_count": spec.patch_count,
        "patch_rows": spec.patch_rows,
        "patch_columns": spec.patch_columns,
        "patch_dim": spec.patch_dim,
        "map_channels": int(dataset.maps.shape[2]),
        "action_channels": 4 + 2 * corpus.material_categories,
        "radio_dim": int(dataset.radio_config.shape[1] + dataset.bs_pose.shape[1]),
        "latent_dim": int(config["teacher"]["latent_dim"]),
        "state_dim": int(config["model"]["state_dim"]),
        "map_dim": int(config["model"]["map_dim"]),
        "hidden_dim": int(config["model"]["hidden_dim"]),
        "attention_heads": int(config["model"]["attention_heads"]),
        "csi_encoder_layers": int(config["teacher"]["encoder_layers"]),
    }


def _pilot_scales(config, train_corpus, selection_corpus, seed):
    model = _new_model(config, train_corpus, seed)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["model"]["learning_rate"]),
        weight_decay=float(config["model"]["weight_decay"]),
    )
    for step in range(int(config["factorial"]["pilot_steps"])):
        plan = _make_plan(train_corpus, int(config["factorial"]["batch_size"]), seed, step)
        endpoint_batch = _identity_batch(
            train_corpus,
            plan.endpoint,
            [train_corpus.teacher.mask_bank[index] for index in plan.endpoint_masks],
        )
        natural_batch = _identity_batch(
            train_corpus,
            plan.natural_endpoint,
            [train_corpus.teacher.mask_bank[index] for index in plan.natural_masks],
        )
        physical_weight = float(config["factorial"]["endpoint_physical_weight"])
        loss = _endpoint_loss(model, endpoint_batch, physical_weight)
        loss = loss + float(config["factorial"]["natural_endpoint_weight"]) * _endpoint_loss(
            model, natural_batch, physical_weight
        )
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
    kappa = _estimate_noop_kappa(
        model,
        selection_corpus,
        float(config["qualification"]["alignment_noop_quantile"]),
    )
    alignment_values = []
    response_values = []
    weights = _loss_weights(config, 1.0, 1.0, 1.0, 1.0, kappa)
    model.eval()
    for step in range(int(config["factorial"]["pilot_steps"])):
        plan = _make_plan(
            selection_corpus,
            int(config["factorial"]["batch_size"]),
            seed + 1,
            step,
        )
        with torch.no_grad():
            components = _loss_components(model, selection_corpus, plan, weights)
        alignment_values.append(float(components["alignment"]))
        response_values.append(float(components["response"]))
    return {
        "pilot_seed": int(seed),
        "pilot_steps": int(config["factorial"]["pilot_steps"]),
        "pilot_contract": "endpoint-only source-encoder-train fit; source-method-selection no-op kappa and frozen scale sequence",
        "alignment_scale": max(float(np.mean(alignment_values)), 1e-6),
        "response_scale": max(float(np.mean(response_values)), 1e-6),
        "alignment_null_tolerance": float(kappa),
        "checkpoint_reused_for_final_training": False,
    }


def _estimate_noop_kappa(model, corpus, quantile):
    units = []
    for scene, values in corpus.endpoint.items():
        for world, position in values:
            units.append((scene, world, position))
    gaps = _noop_score_gaps(model, corpus, units)
    if not gaps:
        raise RuntimeError("canonical no-op pilot has no units")
    return float(np.quantile(np.asarray(gaps), float(quantile)))


def _noop_score_gaps(model, corpus, units):
    gaps = []
    for unit in units:
        scene, world, position = unit
        scores = []
        for supplied in (
            corpus.dataset.maps[scene, world],
            corpus.dataset.noop_maps[scene, world],
        ):
            errors = []
            for entry in corpus.alignment_bank:
                batch = _identity_batch(corpus, [(scene, world, position)], [entry], supplied_maps=[supplied])
                state = model.state(batch["visible"], batch["maps"], batch["radio"], batch["masks"])
                prediction_z, prediction_y = model.predict(state, batch["zero_action"], batch["query"])
                errors.append(
                    endpoint_per_sample(
                        prediction_z,
                        prediction_y,
                        batch["target_z"],
                        batch["target_y"],
                        1.0,
                    )[0]
                )
            scores.append(-torch.mean(torch.stack(errors)))
        gaps.append(float(torch.abs(scores[0] - scores[1]).detach()))
    return gaps


def _train_arm(config, corpus, seed, arm, pilot, *, reference_flops=None):
    model = _new_model(config, corpus, seed)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["model"]["learning_rate"]),
        weight_decay=float(config["model"]["weight_decay"]),
    )
    alignment_factor, response_factor = ARM_FACTORS[arm]
    weights = _loss_weights(
        config,
        alignment_factor,
        response_factor,
        float(pilot["alignment_scale"]),
        float(pilot["response_scale"]),
        float(pilot["alignment_null_tolerance"]),
    )
    alignment_gradient_norms = []
    response_gradient_norms = []
    raw_alignment_gradient_norms = []
    raw_response_gradient_norms = []
    last = None
    started = time.perf_counter()
    execution = None
    for step in range(int(config["factorial"]["steps"])):
        plan = _make_plan(corpus, int(config["factorial"]["batch_size"]), seed, step)
        if step == 0:
            execution = _measure_execution(
                model,
                corpus,
                plan,
                weights,
                reference_flops=reference_flops,
            )
        components = _loss_components(model, corpus, plan, weights)
        if step in {0, int(config["factorial"]["steps"]) - 1}:
            retained = _retained_parameters(model)
            raw_alignment_gradient_norms.append(_gradient_norm(components["alignment"], retained))
            raw_response_gradient_norms.append(_gradient_norm(components["response"], retained))
            alignment_gradient_norms.append(
                _gradient_norm(
                    float(weights.alignment)
                    * components["alignment"]
                    / max(float(weights.alignment_scale), 1e-12),
                    retained,
                )
            )
            response_gradient_norms.append(
                _gradient_norm(
                    float(weights.response)
                    * components["response"]
                    / max(float(weights.response_scale), 1e-12),
                    retained,
                )
            )
        optimizer.zero_grad(set_to_none=True)
        components["total"].backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()
        last = components
    elapsed = time.perf_counter() - started
    if last is None:
        raise RuntimeError("training schedule must contain at least one step")
    if execution is None:
        raise RuntimeError("training execution measurement was not performed")
    row = {
        "seed": int(seed),
        "arm": arm,
        "steps": int(config["factorial"]["steps"]),
        "batch_size": int(config["factorial"]["batch_size"]),
        "parameters": int(sum(parameter.numel() for parameter in model.parameters())),
        "elapsed_seconds": elapsed,
        "state_calls_per_step": execution["state_calls"],
        "predict_calls_per_step": execution["predict_calls"],
        "forward_calls_per_step": execution["state_calls"] + execution["predict_calls"],
        "total_forward_calls": (execution["state_calls"] + execution["predict_calls"])
        * int(config["factorial"]["steps"]),
        "measured_flops_per_step": execution["flops"],
        "flop_measurement_status": execution["flop_measurement_status"],
        "compute_contract": "all arms execute the identical branch bundle; disabled losses have zero weighted gradient but retain raw compute",
        "alignment_gradient_norm_mean": float(np.mean(alignment_gradient_norms)),
        "response_gradient_norm_mean": float(np.mean(response_gradient_norms)),
        "raw_alignment_gradient_norm_mean": float(np.mean(raw_alignment_gradient_norms)),
        "raw_response_gradient_norm_mean": float(np.mean(raw_response_gradient_norms)),
        "checkpoint_rule": "fixed_final_step_no_target_selection",
        "batch_plan_contract": "identical bank/edge/direction/mask/query sequence for all arms at a seed",
    }
    for name, value in last.items():
        row[f"final_{name}_loss"] = float(value.detach())
    return model, row


def _loss_weights(config, alignment_factor, response_factor, alignment_scale, response_scale, kappa):
    f = config["factorial"]
    q = config["qualification"]
    return LossWeights(
        endpoint_physical=float(f["endpoint_physical_weight"]),
        natural_endpoint=float(f["natural_endpoint_weight"]),
        alignment=alignment_factor * float(f["alignment_weight"]),
        alignment_null=float(f["alignment_null_weight"]),
        response=response_factor * float(f["response_weight"]),
        response_physical=float(f["response_physical_weight"]),
        response_delta=float(f["response_delta_weight"]),
        response_delta_physical=float(f["response_delta_physical_weight"]),
        response_null=float(f["response_null_weight"]),
        response_null_physical=float(f["response_null_physical_weight"]),
        active_margin=float(f["active_margin"]),
        effect_margin_scale=float(f["effect_margin_scale"]),
        effect_margin_cap=float(f["effect_margin_cap"]),
        alignment_primary_margin=str(f["alignment_primary_margin"]),
        alignment_null_tolerance=float(kappa),
        response_latent_null_tolerance=float(q["response_latent_null_rms_max"]),
        response_physical_null_tolerance=float(q["response_physical_null_rms_max"]),
        alignment_scale=float(alignment_scale),
        response_scale=float(response_scale),
    )


def _loss_components(model, corpus, plan, weights):
    endpoint_batch = _identity_batch(
        corpus, plan.endpoint, [corpus.teacher.mask_bank[index] for index in plan.endpoint_masks]
    )
    natural_batch = _identity_batch(
        corpus,
        plan.natural_endpoint,
        [corpus.teacher.mask_bank[index] for index in plan.natural_masks],
    )
    endpoint = _endpoint_loss(model, endpoint_batch, weights.endpoint_physical)
    natural = _endpoint_loss(model, natural_batch, weights.endpoint_physical)
    endpoint_total = endpoint + float(weights.natural_endpoint) * natural

    active_scores = _alignment_scores(model, corpus, plan.alignment_active, weights.endpoint_physical)
    null_scores = _alignment_scores(model, corpus, plan.alignment_null, weights.endpoint_physical)
    active_effect = torch.as_tensor(
        [
            corpus.routed.alignment_distances[(scene, source, target, position)][0]
            for scene, source, target, position in plan.alignment_active
        ],
        dtype=torch.float32,
    )
    phi = torch.clamp(
        active_effect / max(float(weights.effect_margin_scale), 1e-12),
        min=0.0,
        max=float(weights.effect_margin_cap),
    )
    alignment_active_effect_aware = torch.mean(
        alignment_active_quartet_loss(
            *active_scores, margin=float(weights.active_margin) * phi
        )
    )
    alignment_active_fixed = torch.mean(
        alignment_active_quartet_loss(
            *active_scores, margin=float(weights.active_margin)
        )
    )
    alignment_active = (
        alignment_active_fixed
        if weights.alignment_primary_margin == "fixed"
        else alignment_active_effect_aware
    )
    alignment_null = torch.mean(
        alignment_null_quartet_loss(
            *null_scores, tolerance=float(weights.alignment_null_tolerance)
        )
    )
    alignment = alignment_active + float(weights.alignment_null) * alignment_null

    target_batch = _response_batch(
        corpus,
        plan.response_all,
        [corpus.teacher.mask_bank[index] for index in plan.response_all_masks],
    )
    active_batch = _response_batch(
        corpus,
        plan.response_active,
        [corpus.teacher.mask_bank[index] for index in plan.response_active_masks],
    )
    null_batch = _response_batch(
        corpus,
        plan.response_null,
        [corpus.teacher.mask_bank[index] for index in plan.response_null_masks],
    )
    response_target, response_physical = _response_target_loss(model, target_batch)
    response_active = _response_active_loss(model, active_batch, weights)
    response_null = _response_null_loss(model, null_batch, weights)
    response = (
        response_target
        + float(weights.response_physical) * response_physical
        + float(weights.response_delta) * response_active
        + float(weights.response_null) * response_null
    )
    total = (
        endpoint_total
        + float(weights.alignment) * alignment / max(float(weights.alignment_scale), 1e-12)
        + float(weights.response) * response / max(float(weights.response_scale), 1e-12)
    )
    return {
        "total": total,
        "endpoint": endpoint_total,
        "endpoint_world": endpoint,
        "endpoint_natural": natural,
        "alignment": alignment,
        "alignment_active": alignment_active,
        "alignment_active_fixed": alignment_active_fixed,
        "alignment_active_effect_aware": alignment_active_effect_aware,
        "alignment_null": alignment_null,
        "response": response,
        "response_target": response_target,
        "response_physical": response_physical,
        "response_active": response_active,
        "response_null": response_null,
    }


def _endpoint_loss(model, batch, physical_weight):
    state = model.state(batch["visible"], batch["maps"], batch["radio"], batch["masks"])
    prediction_z, prediction_y = model.predict(state, batch["zero_action"], batch["query"])
    return torch.mean(
        endpoint_per_sample(
            prediction_z,
            prediction_y,
            batch["target_z"],
            batch["target_y"],
            physical_weight,
        )
    )


def _alignment_scores(model, corpus, units, physical_weight):
    expanded = []
    entries = []
    for unit in units:
        for entry in corpus.alignment_bank:
            expanded.append(unit)
            entries.append(entry)
    left = [(scene, source, position) for scene, source, target, position in expanded]
    right = [(scene, target, position) for scene, source, target, position in expanded]
    map_u = [corpus.dataset.maps[scene, source] for scene, source, target, position in expanded]
    map_v = [corpus.dataset.maps[scene, target] for scene, source, target, position in expanded]
    batches = (
        _identity_batch(corpus, left, entries, supplied_maps=map_u),
        _identity_batch(corpus, left, entries, supplied_maps=map_v),
        _identity_batch(corpus, right, entries, supplied_maps=map_v),
        _identity_batch(corpus, right, entries, supplied_maps=map_u),
    )
    scores = []
    for batch in batches:
        state = model.state(batch["visible"], batch["maps"], batch["radio"], batch["masks"])
        prediction_z, prediction_y = model.predict(state, batch["zero_action"], batch["query"])
        error = endpoint_per_sample(
            prediction_z,
            prediction_y,
            batch["target_z"],
            batch["target_y"],
            physical_weight,
        )
        scores.append(-error.reshape(len(units), len(corpus.alignment_bank)).mean(dim=1))
    return tuple(scores)


def _response_target_loss(model, batch):
    state = model.state(batch["visible"], batch["maps"], batch["radio"], batch["masks"])
    prediction_z, prediction_y = model.predict(state, batch["action"], batch["query"])
    return (
        torch.mean(squared_rms_error(prediction_z, batch["target_z"])),
        torch.mean(squared_rms_error(prediction_y, batch["target_y"])),
    )


def _response_active_loss(model, batch, weights):
    state = model.state(batch["visible"], batch["maps"], batch["radio"], batch["masks"])
    identity_z, identity_y = model.predict(state, batch["zero_action"], batch["query"])
    prediction_z, prediction_y = model.predict(state, batch["action"], batch["query"])
    return torch.mean(
        squared_rms_error(prediction_z - identity_z, batch["target_z"] - batch["source_z"])
        + float(weights.response_delta_physical)
        * squared_rms_error(prediction_y - identity_y, batch["target_y"] - batch["source_y"])
    )


def _response_null_loss(model, batch, weights):
    state = model.state(batch["visible"], batch["maps"], batch["radio"], batch["masks"])
    identity_z, identity_y = model.predict(state, batch["zero_action"], batch["query"])
    prediction_z, prediction_y = model.predict(state, batch["action"], batch["query"])
    latent_norm = torch.sqrt(torch.mean((prediction_z - identity_z) ** 2, dim=1) + 1e-12)
    physical_norm = torch.sqrt(torch.mean((prediction_y - identity_y) ** 2, dim=1) + 1e-12)
    return torch.mean(
        torch.relu(latent_norm - float(weights.response_latent_null_tolerance)) ** 2
        + float(weights.response_null_physical)
        * torch.relu(physical_norm - float(weights.response_physical_null_tolerance)) ** 2
    )


def _identity_batch(corpus, units, entries, supplied_maps=None):
    dataset = corpus.dataset
    norm = corpus.normalization
    visible = []
    maps = []
    radio = []
    masks = []
    query = []
    target_z = []
    target_y = []
    map_size = dataset.maps.shape[-1]
    for index, ((scene, world, position), entry) in enumerate(zip(units, entries)):
        patches = _normalized_patches(corpus, scene, world, position)
        visible_patches = patches.copy()
        visible_patches[entry.mask] = 0.0
        visible.append(visible_patches)
        supplied = supplied_maps[index] if supplied_maps is not None else dataset.maps[scene, world]
        maps.append(_normalized_map(norm, supplied))
        radio.append(_normalized_radio(norm, dataset.radio_config[scene], dataset.bs_pose[scene]))
        masks.append(entry.mask)
        query.append(entry.query)
        target_z.append(_normalized_latent(corpus, scene, world, position, entry.query))
        target_y.append(patches[entry.query])
    zero = zero_typed_edit((len(units),), map_size, corpus.material_categories)
    return {
        "visible": torch.as_tensor(np.asarray(visible), dtype=torch.float32),
        "maps": torch.as_tensor(np.asarray(maps), dtype=torch.float32),
        "radio": torch.as_tensor(np.asarray(radio), dtype=torch.float32),
        "masks": torch.as_tensor(np.asarray(masks), dtype=torch.bool),
        "query": torch.as_tensor(np.asarray(query), dtype=torch.long),
        "target_z": torch.as_tensor(np.asarray(target_z), dtype=torch.float32),
        "target_y": torch.as_tensor(np.asarray(target_y), dtype=torch.float32),
        "zero_action": torch.as_tensor(_normalized_action(norm, zero), dtype=torch.float32),
    }


def _response_batch(corpus, units, entries):
    dataset = corpus.dataset
    base_units = [(scene, source, position) for scene, source, target, position, query in units]
    identity = _identity_batch(corpus, base_units, entries)
    actions = []
    source_z = []
    source_y = []
    target_z = []
    target_y = []
    for scene, source, target, position, query in units:
        action = typed_signed_edit(
            dataset.maps[scene, source],
            dataset.maps[scene, target],
            dataset.map_channel_names,
            corpus.material_categories,
        )
        actions.append(action)
        source_z.append(_normalized_latent(corpus, scene, source, position, query))
        target_z.append(_normalized_latent(corpus, scene, target, position, query))
        source_y.append(_normalized_patches(corpus, scene, source, position)[query])
        target_y.append(_normalized_patches(corpus, scene, target, position)[query])
    identity.update(
        {
            "action": torch.as_tensor(
                _normalized_action(corpus.normalization, np.asarray(actions)), dtype=torch.float32
            ),
            "source_z": torch.as_tensor(np.asarray(source_z), dtype=torch.float32),
            "source_y": torch.as_tensor(np.asarray(source_y), dtype=torch.float32),
            "target_z": torch.as_tensor(np.asarray(target_z), dtype=torch.float32),
            "target_y": torch.as_tensor(np.asarray(target_y), dtype=torch.float32),
        }
    )
    return identity


def _normalized_patches(corpus, scene, world, position):
    raw = corpus.routed.physical_patches[scene][world, position]
    return (raw - corpus.normalization.patch_mean) / corpus.normalization.patch_scale


def _normalized_latent(corpus, scene, world, position, query):
    raw = corpus.routed.teacher_latent[scene][world, position, query]
    return (raw - corpus.normalization.latent_mean) / corpus.normalization.latent_scale


def _normalized_map(norm, maps):
    return np.asarray(maps, dtype=np.float64) / norm.map_scale[:, None, None]


def _normalized_radio(norm, radio, bs_pose=None):
    context = np.asarray(radio, dtype=np.float64)
    if bs_pose is not None:
        context = np.concatenate((context, np.asarray(bs_pose, dtype=np.float64)), axis=-1)
    if context.shape[-1] != norm.radio_mean.shape[-1]:
        raise ValueError("complete c must include radio_config and bs_pose")
    return (context - norm.radio_mean) / norm.radio_scale


def _normalized_action(norm, action):
    return np.asarray(action, dtype=np.float64) / norm.action_scale.reshape(
        *((1,) * (np.asarray(action).ndim - 3)), -1, 1, 1
    )


def _retained_parameters(model):
    prefixes = ("csi_", "map_encoder", "map_projection", "radio_encoder", "fusion", "state_norm")
    return [parameter for name, parameter in model.named_parameters() if name.startswith(prefixes)]


def _gradient_norm(loss, parameters):
    gradients = torch.autograd.grad(loss, parameters, retain_graph=True, allow_unused=True)
    squared = [torch.sum(gradient.detach() ** 2) for gradient in gradients if gradient is not None]
    return float(torch.sqrt(torch.sum(torch.stack(squared))).item()) if squared else 0.0


def _measure_execution(model, corpus, plan, weights, *, reference_flops=None):
    counts = {"state_calls": 0, "predict_calls": 0}
    state_hook = model.fusion.register_forward_hook(
        lambda _module, _inputs, _output: counts.__setitem__(
            "state_calls", counts["state_calls"] + 1
        )
    )
    predict_hook = model.predictor.register_forward_hook(
        lambda _module, _inputs, _output: counts.__setitem__(
            "predict_calls", counts["predict_calls"] + 1
        )
    )
    try:
        if reference_flops is None:
            from torch.utils.flop_counter import FlopCounterMode

            with FlopCounterMode(display=False) as counter:
                with torch.no_grad():
                    _loss_components(model, corpus, plan, weights)
            value = int(counter.get_total_flops())
            counts["flops"] = value if value > 0 else None
            counts["flop_measurement_status"] = (
                "TORCH_DISPATCH_COUNTER" if value > 0 else "NOT_ASSESSED"
            )
        else:
            with torch.no_grad():
                _loss_components(model, corpus, plan, weights)
            counts["flops"] = int(reference_flops)
            counts["flop_measurement_status"] = "REUSED_IDENTICAL_BRANCH_PLAN_MEASUREMENT"
    except Exception:
        counts["state_calls"] = 0
        counts["predict_calls"] = 0
        with torch.no_grad():
            _loss_components(model, corpus, plan, weights)
        counts["flops"] = None
        counts["flop_measurement_status"] = "NOT_ASSESSED"
    finally:
        state_hook.remove()
        predict_hook.remove()
    return counts


def _run_localization(config, dataset, models, normalization, patch_spec):
    bank_rows = []
    sample_rows = []
    source_scenes = [int(value) for value in dataset.indices_for_role("source_encoder_train")]
    target_scenes = [int(value) for value in dataset.indices_for_role("target")]
    target_cities = sorted(set(dataset.city_ids[target_scenes].tolist()))
    for seed in config["seeds"]:
        city_orders = {}
        for city in target_cities:
            candidates = city_support_candidates(dataset, city)
            for draw in range(int(config["localization"]["label_draws"])):
                rng = np.random.default_rng(int(seed) * 100003 + _stable_city_seed(city) + draw)
                city_orders[(city, draw)] = [candidates[index] for index in rng.permutation(len(candidates))]
        for arm in ARMS:
            model = models[(int(seed), arm)]
            scene_representations = _natural_representations(
                model, dataset, source_scenes + target_scenes, normalization, patch_spec
            )
            source_x = np.vstack([scene_representations[scene] for scene in source_scenes])
            source_y = np.vstack([dataset.positions[scene] for scene in source_scenes])
            source_head = fit_source_position_head(
                source_x, source_y, config, seed=int(seed) + 17003
            )
            for city in target_cities:
                city_scenes = [scene for scene in target_scenes if str(dataset.city_ids[scene]) == city]
                for draw in range(int(config["localization"]["label_draws"])):
                    order = city_orders[(city, draw)]
                    for budget in config["localization"]["label_budgets"]:
                        if int(budget) == 0 and draw > 0:
                            continue
                        if int(budget) > len(order):
                            raise ValueError(
                                f"target city {city} has {len(order)} support positions, fewer than k={budget}"
                            )
                        selected = order[: int(budget)]
                        support_ids = [str(dataset.position_ids[scene, position]) for scene, position in selected]
                        if len(support_ids) != len(set(support_ids)):
                            raise RuntimeError("city-level support draw contains duplicate receiver positions")
                        support_x = (
                            np.vstack([scene_representations[scene][position] for scene, position in selected])
                            if selected
                            else np.empty((0, source_x.shape[1]))
                        )
                        support_y = (
                            np.vstack([dataset.positions[scene, position] for scene, position in selected])
                            if selected
                            else np.empty((0, 2))
                        )
                        head = adapt_position_head(source_head, support_x, support_y, config)
                        for scene in city_scenes:
                            query_indices = eligible_query_indices(dataset, scene, set(support_ids))
                            prediction, variance, uncertainty = predict_position_distribution(
                                head,
                                scene_representations[scene][query_indices],
                                sigma_min=float(config["localization"]["sigma_min"]),
                            )
                            errors = np.sqrt(
                                np.sum((prediction - dataset.positions[scene, query_indices]) ** 2, axis=1)
                            )
                            for local_index, position in enumerate(query_indices):
                                sample_rows.append(
                                    {
                                        "seed": int(seed),
                                        "arm": arm,
                                        "city_id": city,
                                        "bank_id": str(dataset.bank_ids[scene]),
                                        "base_map_cluster_id": str(dataset.base_map_cluster_ids[scene]),
                                        "budget": int(budget),
                                        "draw": 0 if int(budget) == 0 else draw,
                                        "position_id": str(dataset.position_ids[scene, position]),
                                        "prediction_x": float(prediction[local_index, 0]),
                                        "prediction_y": float(prediction[local_index, 1]),
                                        "variance_x": float(variance[local_index, 0]),
                                        "variance_y": float(variance[local_index, 1]),
                                        "u_g": float(uncertainty[local_index]),
                                        "true_x": float(dataset.positions[scene, position, 0]),
                                        "true_y": float(dataset.positions[scene, position, 1]),
                                        "error_m": float(errors[local_index]),
                                        "failure": bool(
                                            errors[local_index]
                                            > float(config["localization"]["failure_threshold_m"])
                                        ),
                                    }
                                )
                            median = float(np.median(errors))
                            bank_rows.append(
                                {
                                    "seed": int(seed),
                                    "arm": arm,
                                    "city_id": city,
                                    "bank_id": str(dataset.bank_ids[scene]),
                                    "base_map_cluster_id": str(dataset.base_map_cluster_ids[scene]),
                                    "budget": int(budget),
                                    "draw": 0 if int(budget) == 0 else draw,
                                    "city_support_unique_positions": len(selected),
                                    "support_position_ids": ";".join(support_ids),
                                    "query_unique_positions": int(query_indices.size),
                                    "median_error_m": median,
                                    "p90_error_m": float(np.percentile(errors, 90)),
                                    "utility_neg_log_median": float(-math.log(max(median, 1e-12))),
                                }
                            )
    return bank_rows, sample_rows


def _natural_representations(model, dataset, scenes, normalization, patch_spec):
    model.eval()
    outputs = {}
    with torch.no_grad():
        for scene in scenes:
            world = int(dataset.natural_world_index[scene])
            raw = patchify_csi(dataset.csi[scene, world], patch_spec)
            patches = (raw - normalization.patch_mean) / normalization.patch_scale
            maps = np.repeat(dataset.maps[scene, world][None, :, :, :], dataset.position_count, axis=0)
            maps = maps / normalization.map_scale[None, :, None, None]
            context = np.concatenate((dataset.radio_config[scene], dataset.bs_pose[scene]))
            radio = np.repeat(context[None, :], dataset.position_count, axis=0)
            radio = (radio - normalization.radio_mean) / normalization.radio_scale
            representation = model.retained_representation(
                torch.as_tensor(patches, dtype=torch.float32),
                torch.as_tensor(maps, dtype=torch.float32),
                torch.as_tensor(radio, dtype=torch.float32),
            )
            outputs[scene] = representation.numpy().astype(np.float64)
    return outputs


def _localization_summary(rows):
    summary = []
    keys = sorted({(row["arm"], row["city_id"], row["budget"]) for row in rows})
    for arm, city, budget in keys:
        selected = [
            row for row in rows
            if (row["arm"], row["city_id"], row["budget"]) == (arm, city, budget)
        ]
        summary.append(
            {
                "arm": arm,
                "city_id": city,
                "budget": budget,
                "independent_base_map_clusters": len({row["base_map_cluster_id"] for row in selected}),
                "training_seeds": len({row["seed"] for row in selected}),
                "label_draws": len({row["draw"] for row in selected}),
                "mean_bank_median_error_m": float(np.mean([row["median_error_m"] for row in selected])),
                "mean_utility_neg_log_median": float(
                    np.mean([row["utility_neg_log_median"] for row in selected])
                ),
                "mean_bank_p90_error_m": float(np.mean([row["p90_error_m"] for row in selected])),
            }
        )
    return summary


def _factorial_statistics(config, rows):
    primary = list(config["localization"]["primary_budgets"])
    exact = exact_factorial_utilities(rows, primary)
    hierarchical = hierarchical_factorial_interval(
        rows,
        primary,
        int(config["factorial"]["bootstrap_resamples"]),
        int(config["seeds"][0]) + 700001,
    )
    bank_only = bank_only_factorial_interval(
        rows,
        primary,
        int(config["factorial"]["bootstrap_resamples"]),
        int(config["seeds"][0]) + 700002,
    )
    sensitivity = leave_one_factorial_sensitivity(rows, primary)
    return {
        "schema_version": "csi-pairs-v6-factorial-statistics-v1",
        "estimand": "equal city x k x base-map-cluster x seed x positive-budget-draw macro utility",
        "exact": exact,
        "hierarchical_bootstrap": hierarchical,
        "bank_only_bootstrap": bank_only,
        "sensitivity": sensitivity,
    }


def _preliminary_factorial_gate(config, dataset, rows, statistics, evidence):
    hierarchical = statistics["hierarchical_bootstrap"]
    minimum_interaction = float(config["factorial"]["minimum_interaction_effect"])
    primary = set(int(value) for value in config["localization"]["primary_budgets"])
    city_checks = []
    maximum_regression = 0.0
    for city in sorted({row["city_id"] for row in rows}):
        for budget in sorted(primary):
            for baseline in ("alignment", "response"):
                interval = _city_budget_arm_interval(
                    rows,
                    city,
                    budget,
                    baseline,
                    int(config["evaluation"]["bootstrap_resamples"]),
                    730000 + len(city_checks),
                )
                difference = float(interval["paired_mean_difference"])
                maximum_regression = max(maximum_regression, max(0.0, -difference))
                city_checks.append(
                    {
                        "city_id": city,
                        "budget": budget,
                        "baseline": baseline,
                        "difference": difference,
                        **interval,
                    }
                )
    subgates = {
        "1_full_beats_both_single_branches": "PASS"
        if hierarchical["full_vs_alignment"]["ci95_low"] > 0
        and hierarchical["full_vs_response"]["ci95_low"] > 0
        else "FAIL",
        "2_cgs_noninferior_to_alignment": "NOT_ASSESSED",
        "3_native_response_noninferior_to_response": "NOT_ASSESSED",
        "4_hierarchical_interaction_ci_exceeds_minimum": "PASS"
        if hierarchical["interaction"]["ci95_low"] > minimum_interaction
        else "FAIL",
        "5_no_city_k_reverse_regression": "PASS"
        if all(
            row["ci95_low"]
            >= -float(config["localization"]["maximum_city_regression"])
            for row in city_checks
        )
        else "FAIL",
        "6_equal_flop_single_branch_superiority": "NOT_ASSESSED",
        "7_parameter_and_flop_matched_concat_superiority": "NOT_ASSESSED",
    }
    localization_checks = []
    for city in sorted({row["city_id"] for row in rows}):
        for budget in sorted(primary):
            interval = _city_budget_arm_interval(
                rows,
                city,
                budget,
                "endpoint",
                int(config["evaluation"]["bootstrap_resamples"]),
                735000 + len(localization_checks),
            )
            localization_checks.append(
                {
                    "city_id": city,
                    "budget": budget,
                    "baseline": "endpoint",
                    "difference": float(interval["paired_mean_difference"]),
                    **interval,
                }
            )
    p_values = [row["p_value_two_sided"] for row in localization_checks]
    adjusted = holm_adjust(p_values)
    for row, value in zip(localization_checks, adjusted):
        row["holm_adjusted_p"] = value
    alpha = float(config["evaluation"]["familywise_alpha"])
    for row in localization_checks:
        row["passed"] = bool(
            interval_decision(
                row,
                threshold=float(config["localization"]["minimum_city_improvement"]),
                relation="superiority",
            )
            and float(row["holm_adjusted_p"]) < alpha
        )
    target_cities = sorted({row["city_id"] for row in localization_checks})
    primary_complete = set(primary) == {0, 8}
    g5_subgates = {
        "1_two_target_cities_and_independent_clusters": "PASS"
        if len(target_cities) >= 2
        and all(
            len(
                {
                    row["base_map_cluster_id"]
                    for row in rows
                    if row["city_id"] == city
                }
            )
            >= 2
            for city in target_cities
        )
        else "FAIL",
        "2_strict_primary_k0_k8_complete": "PASS" if primary_complete else "FAIL",
        "3_every_city_k0_full_vs_endpoint_ci_holm": "PASS"
        if all(row["passed"] for row in localization_checks if row["budget"] == 0)
        else "FAIL",
        "4_every_city_k8_full_vs_endpoint_ci_holm": "PASS"
        if primary_complete
        and all(row["passed"] for row in localization_checks if row["budget"] == 8)
        else "FAIL",
    }
    g5_passed = all(value == "PASS" for value in g5_subgates.values())
    gate_vector = complete_gate_vector(
        {
            "G1": "PASS",
            "G2": "PASS",
            "G4": "NOT_ASSESSED",
            "G5": "PASS" if g5_passed else "FAIL",
        }
    )
    return {
        "schema_version": FACTORIAL_SCHEMA,
        "status": "PASS" if g5_passed else "FAIL",
        "passed": bool(g5_passed),
        **evidence,
        "gate_vector": gate_vector,
        "g4_subgates": subgates,
        "g5_subgates": g5_subgates,
        "city_budget_checks": city_checks,
        "localization_city_budget_checks": localization_checks,
        "claim_boundary": "G4 cannot PASS until all seven subgates are PASS; NOT_ASSESSED is never PASS.",
        "config": public_formal_config(config),
    }


def _city_budget_arm_interval(rows, city, budget, baseline, resamples, seed):
    grouped = {}
    for row in rows:
        if str(row["city_id"]) != str(city) or int(row["budget"]) != int(budget):
            continue
        if row["arm"] not in {"full", baseline}:
            continue
        key = (
            str(row["base_map_cluster_id"]),
            int(row["seed"]),
            int(row["draw"]),
        )
        grouped.setdefault((key, str(row["arm"])), []).append(
            float(row["utility_neg_log_median"])
        )
    cells = sorted(
        key
        for key in {item[0] for item in grouped}
        if (key, "full") in grouped and (key, baseline) in grouped
    )
    clusters = np.asarray([key[0] for key in cells])
    full = np.asarray([np.mean(grouped[(key, "full")]) for key in cells])
    other = np.asarray([np.mean(grouped[(key, baseline)]) for key in cells])
    interval = paired_cluster_interval(clusters, full, other, resamples, seed)
    test = paired_sign_flip_test(clusters, full, other, seed + 1)
    return {**interval, "p_value_two_sided": test["p_value_two_sided"]}


def _stable_city_seed(city):
    import hashlib

    return int.from_bytes(hashlib.sha256(str(city).encode("utf-8")).digest()[:4], "little")


def city_support_candidates(dataset: FormalDataset, city: str) -> list[tuple[int, int]]:
    by_position = {}
    for scene in (int(value) for value in dataset.indices_for_role("target")):
        if str(dataset.city_ids[scene]) != str(city):
            continue
        for position in np.flatnonzero(dataset.position_roles[scene] == "support_pool"):
            identifier = str(dataset.position_ids[scene, position])
            by_position.setdefault(identifier, (scene, int(position)))
    return [by_position[identifier] for identifier in sorted(by_position)]


def eligible_query_indices(dataset: FormalDataset, scene: int, support_ids: set[str]) -> np.ndarray:
    candidates = np.flatnonzero(dataset.position_roles[scene] == "query")
    selected = np.asarray(
        [position for position in candidates if str(dataset.position_ids[scene, position]) not in support_ids],
        dtype=np.int64,
    )
    if selected.size == 0:
        raise RuntimeError("support sibling exclusion leaves no target query positions")
    return selected
