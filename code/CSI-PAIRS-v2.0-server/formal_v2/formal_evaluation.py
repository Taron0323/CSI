from __future__ import annotations

from pathlib import Path

import numpy as np

from .formal_dataset import FormalDataset
from .formal_evidence import (
    FACTORIAL_SCHEMA,
    bind_rows,
    complete_gate_vector,
    evidence_context,
    require_manifested_formal_qualification,
    require_stage_manifested_gate,
)
from .formal_factorial import (
    _normalized_action,
    _normalized_map,
    _normalized_radio,
    _training_normalization,
)
from .formal_features import multichannel_spatial_features
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_csv, write_json
from .formal_metrics import binary_auroc, spearman_correlation
from .formal_model import CSIPairsFormalModel, endpoint_per_sample, torch
from .formal_probes import (
    fit_action_response_probe,
    fit_select_compatibility_probe,
    predict_binary_probe,
    predict_response_probe,
)
from .formal_protocol import patchify_csi, typed_signed_edit, zero_typed_edit
from .formal_routing import ROUTE_NAMES, fit_route_normalization, route_dataset
from .formal_statistics import (
    holm_adjust,
    interval_decision,
    paired_cluster_interval,
    paired_sign_flip_test,
)
from .formal_teacher import load_teacher_bundle


def run_formal_evaluation(
    config: dict,
    dataset: FormalDataset,
    output_root: str | Path,
    qualification_gate: dict,
    factorial_gate: dict,
) -> dict:
    from .formal_data_verification import require_verified_roles_from_root

    require_verified_roles_from_root(
        output_root,
        config,
        dataset,
        (
            "source_encoder_train",
            "source_probe_train",
            "source_probe_selection",
            "source_final_unseen_bank",
            "target",
        ),
    )
    qualification_gate = require_manifested_formal_qualification(
        qualification_gate,
        config,
        dataset,
        allow_nonscientific_fixture=True,
    )
    root = Path(output_root)
    _validate_factorial_gate(config, dataset, factorial_gate, root / "factorial" / "gate.json")
    output_dir = root / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    teacher = load_teacher_bundle(qualification_gate["teacher_checkpoint"], config)
    route_normalization = fit_route_normalization(dataset, teacher)
    normalization = _training_normalization(
        dataset,
        dataset.indices_for_role("source_encoder_train"),
        route_normalization,
        teacher.patch_spec,
    )
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    checkpoint_index = read_strict_json(root / "factorial" / "checkpoint_index.json")
    checkpoint_rows = _validate_checkpoint_index(
        checkpoint_index, config, dataset, qualification_gate
    )
    cgs_rows = []
    response_rows = []
    probe_contract_rows = []
    response_probe_contract_rows = []
    route_rows = []
    effect_bin_rows = []
    compatibility_effect_rows = []
    response_effect_rows = []
    for checkpoint_row in checkpoint_rows:
        seed = int(checkpoint_row["seed"])
        arm = str(checkpoint_row["arm"])
        model = _load_model(
            root / "factorial",
            checkpoint_row,
            qualification_gate,
            config,
            dataset,
        )
        probe_train = _compatibility_dataset(
            model,
            dataset,
            teacher,
            config,
            normalization,
            dataset.indices_for_role("source_probe_train"),
        )
        probe_selection = _compatibility_dataset(
            model,
            dataset,
            teacher,
            config,
            normalization,
            dataset.indices_for_role("source_probe_selection"),
        )
        probe, selection_record = fit_select_compatibility_probe(
            probe_train["features"],
            probe_train["labels"],
            probe_selection["features"],
            probe_selection["labels"],
            config,
            seed=seed + 31001,
        )
        probe_contract_rows.append({"seed": seed, "arm": arm, **selection_record})
        evaluation_scenes = np.concatenate(
            (
                dataset.indices_for_role("source_final_unseen_bank"),
                dataset.indices_for_role("target"),
            )
        )
        evaluated = _compatibility_dataset(
            model,
            dataset,
            teacher,
            config,
            normalization,
            evaluation_scenes,
            active_only=False,
        )
        probabilities = predict_binary_probe(probe, evaluated["features"])
        compatibility_effect_rows.extend(
            _compatibility_effect_rows(seed, arm, evaluated, probabilities)
        )
        for bank in sorted(set(evaluated["bank_ids"].tolist())):
            bank_mask = evaluated["bank_ids"] == bank
            mask = bank_mask & (evaluated["routes"] == "active")
            if not np.any(mask):
                raise RuntimeError(f"evaluation bank {bank!r} has no active CGS quartet")
            cgs_rows.append(
                {
                    "seed": seed,
                    "arm": arm,
                    "bank_id": bank,
                    "base_map_cluster_id": str(
                        dataset.base_map_cluster_ids[int(evaluated["scene_indices"][mask][0])]
                    ),
                    "city_id": str(evaluated["city_ids"][mask][0]),
                    "route": "active",
                    "probe_family": selection_record["selected_family"],
                    "cgs_auroc": binary_auroc(evaluated["labels"][mask], probabilities[mask]),
                    "native_energy_auroc": binary_auroc(
                        evaluated["labels"][mask], evaluated["native_scores"][mask]
                    ),
                    "native_training_bank_auroc": binary_auroc(
                        evaluated["labels"][mask], evaluated["native_training_scores"][mask]
                    ),
                    "native_probe_spearman": spearman_correlation(
                        evaluated["native_scores"][mask], probabilities[mask]
                    ),
                    "n": int(np.sum(mask)),
                }
            )
            effect_bin_rows.extend(
                _active_effect_bin_rows(
                    seed,
                    arm,
                    bank,
                    str(evaluated["city_ids"][mask][0]),
                    probabilities[mask],
                    evaluated["labels"][mask],
                    evaluated["pair_ids"][mask],
                    evaluated["physical_distances"][mask],
                )
            )
            for route in ROUTE_NAMES.tolist():
                route_mask = bank_mask & (evaluated["routes"] == route)
                if not np.any(route_mask):
                    route_rows.append(
                        {
                            "seed": seed,
                            "arm": arm,
                            "bank_id": bank,
                            "base_map_cluster_id": str(
                                dataset.base_map_cluster_ids[
                                    int(evaluated["scene_indices"][bank_mask][0])
                                ]
                            ),
                            "city_id": str(evaluated["city_ids"][bank_mask][0]),
                            "route": route,
                            "condition_status": "MISSING",
                            "pair_count": 0,
                            "matched_minus_alternative_mean": None,
                            "matched_minus_alternative_median": None,
                            "absolute_difference_p90": None,
                            "overclassification_rate": None,
                        }
                    )
                    continue
                differences = _paired_score_differences(
                    probabilities[route_mask],
                    evaluated["labels"][route_mask],
                    evaluated["pair_ids"][route_mask],
                )
                margin = float(config["evaluation"]["null_score_equivalence_margin"])
                route_rows.append(
                    {
                        "seed": seed,
                        "arm": arm,
                        "bank_id": bank,
                        "base_map_cluster_id": str(
                            dataset.base_map_cluster_ids[
                                int(evaluated["scene_indices"][route_mask][0])
                            ]
                        ),
                        "city_id": str(evaluated["city_ids"][route_mask][0]),
                        "route": route,
                        "condition_status": "ASSESSED",
                        "pair_count": int(differences.size),
                        "matched_minus_alternative_mean": float(np.mean(differences)),
                        "matched_minus_alternative_median": float(np.median(differences)),
                        "absolute_difference_p90": float(np.percentile(np.abs(differences), 90)),
                        "overclassification_rate": (
                            float(np.mean(np.abs(differences) > margin)) if route == "null" else None
                        ),
                    }
                )

        response_train = _response_probe_dataset(
            model,
            dataset,
            teacher,
            config,
            normalization,
            dataset.indices_for_role("source_probe_train"),
            active_only=False,
        )
        response_probe = fit_action_response_probe(
            response_train["features"],
            response_train["targets"],
            config,
            seed=seed + 32001,
        )
        response_probe_contract_rows.append(
            {
                "seed": seed,
                "arm": arm,
                "probe": "main_masked_state_map_action_query",
                "steps": int(config["evaluation"]["probe_steps"]),
                "hidden_dim": int(config["evaluation"]["probe_hidden_dim"]),
            }
        )
        variant_probes = {}
        for offset, name in enumerate(
            ("without_map", "edit_only", "csi_only", "oracle_x"), start=1
        ):
            variant_probes[name] = fit_action_response_probe(
                response_train[f"{name}_features"],
                response_train["targets"],
                config,
                seed=seed + 32001 + offset,
            )
            response_probe_contract_rows.append(
                {
                    "seed": seed,
                    "arm": arm,
                    "probe": name,
                    "steps": int(config["evaluation"]["probe_steps"]),
                    "hidden_dim": int(config["evaluation"]["probe_hidden_dim"]),
                }
            )
        response_eval = _response_probe_dataset(
            model,
            dataset,
            teacher,
            config,
            normalization,
            evaluation_scenes,
            active_only=False,
        )
        probe_prediction = predict_response_probe(response_probe, response_eval["features"])
        action_swap_prediction = predict_response_probe(
            response_probe, response_eval["action_swap_features"]
        )
        no_action_prediction = predict_response_probe(
            response_probe, response_eval["no_action_features"]
        )
        variant_predictions = {
            name: predict_response_probe(
                probe, response_eval[f"{name}_features"]
            )
            for name, probe in variant_probes.items()
        }
        response_effect_rows.extend(
            _response_effect_rows(
                seed,
                arm,
                response_eval,
                probe_prediction,
                action_swap_prediction,
                no_action_prediction,
            )
        )
        for bank in sorted(set(response_eval["bank_ids"].tolist())):
            mask = (response_eval["bank_ids"] == bank) & (response_eval["routes"] == "active")
            if not np.any(mask):
                raise RuntimeError(f"evaluation bank {bank!r} has no active response patches")
            numerator = np.sum((probe_prediction[mask] - response_eval["targets"][mask]) ** 2)
            denominator = max(float(np.sum(response_eval["targets"][mask] ** 2)), 1e-12)
            copy_numerator = np.sum(
                (response_eval["source_targets"][mask] - response_eval["targets"][mask]) ** 2
            )
            swap_numerator = np.sum(
                (action_swap_prediction[mask] - response_eval["targets"][mask]) ** 2
            )
            variant_nmse = {
                f"probe_{name}_active_patch_nmse": float(
                    np.sum(
                        (prediction[mask] - response_eval["targets"][mask]) ** 2
                    )
                    / denominator
                )
                for name, prediction in variant_predictions.items()
            }
            native = _native_mask_cover_metrics(
                model,
                dataset,
                teacher,
                config,
                normalization,
                evaluation_scenes,
                bank,
            )
            response_rows.append(
                {
                    "seed": seed,
                    "arm": arm,
                    "bank_id": bank,
                    "base_map_cluster_id": str(
                        dataset.base_map_cluster_ids[
                            int(response_eval["scene_indices"][mask][0])
                        ]
                    ),
                    "city_id": str(response_eval["city_ids"][mask][0]),
                    "unified_response_probe_active_patch_nmse": float(numerator / denominator),
                    "probe_copy_active_patch_nmse": float(copy_numerator / denominator),
                    "probe_action_swap_active_patch_nmse": float(swap_numerator / denominator),
                    **variant_nmse,
                    **native,
                    "n_active_patches": int(np.sum(mask)),
                }
            )
    write_csv(output_dir / "compatibility_probe_contract.csv", bind_rows(probe_contract_rows, evidence))
    write_csv(
        output_dir / "response_probe_contract.csv",
        bind_rows(response_probe_contract_rows, evidence),
    )
    write_csv(output_dir / "cgs_per_bank.csv", bind_rows(cgs_rows, evidence))
    write_csv(output_dir / "compatibility_route_distributions.csv", bind_rows(route_rows, evidence))
    write_csv(output_dir / "cgs_active_effect_bins.csv", bind_rows(effect_bin_rows, evidence))
    write_csv(
        output_dir / "compatibility_pair_effects.csv",
        bind_rows(compatibility_effect_rows, evidence),
    )
    write_csv(
        output_dir / "response_pair_effects.csv",
        bind_rows(response_effect_rows, evidence),
    )
    write_csv(output_dir / "response_per_bank.csv", bind_rows(response_rows, evidence))
    gate = _evaluation_gate(
        config,
        dataset,
        cgs_rows,
        route_rows,
        effect_bin_rows,
        response_rows,
        factorial_gate,
        evidence,
    )
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


def _validate_factorial_gate(config, dataset, gate, gate_path):
    expected = evidence_context(config, dataset, str(gate.get("scientific_use", "")))
    if gate.get("schema_version") != FACTORIAL_SCHEMA:
        raise RuntimeError("evaluation requires a V6 factorial gate")
    for key in ("dataset_sha256", "config_sha256", "fixture"):
        if gate.get(key) != expected[key]:
            raise RuntimeError(f"factorial gate {key} mismatch")
    require_stage_manifested_gate(
        gate_path,
        gate,
        config,
        dataset,
        schema_version=FACTORIAL_SCHEMA,
    )


def _load_model(factorial_root, checkpoint_row, qualification_gate, config, dataset):
    root = Path(factorial_root).resolve()
    path = (root / checkpoint_row["path"]).resolve()
    if root not in path.parents:
        raise RuntimeError("checkpoint index path escapes the factorial directory")
    if sha256_file(path) != checkpoint_row["sha256"]:
        raise RuntimeError("factorial checkpoint hash mismatch")
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if payload.get("schema_version") != "csi-pairs-formal-checkpoint-v2.1-v6":
        raise RuntimeError("checkpoint schema is not V6-compatible")
    expected = evidence_context(config, dataset, str(payload.get("scientific_use", "")))
    for key in ("dataset_sha256", "config_sha256", "fixture"):
        if payload.get(key) != expected[key]:
            raise RuntimeError(f"factorial checkpoint {key} mismatch")
    if payload.get("teacher_checkpoint_sha256") != qualification_gate["teacher_checkpoint_sha256"]:
        raise RuntimeError("factorial checkpoint uses a different frozen teacher")
    if payload.get("seed") != int(checkpoint_row["seed"]) or payload.get("arm") != checkpoint_row["arm"]:
        raise RuntimeError("factorial checkpoint seed/arm identity mismatch")
    model = CSIPairsFormalModel(**payload["model_spec"])
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model


def _validate_checkpoint_index(index, config, dataset, qualification_gate):
    if not isinstance(index, dict) or index.get("schema_version") != "csi-pairs-formal-checkpoint-index-v2.1-v6":
        raise RuntimeError("checkpoint index schema mismatch")
    expected = evidence_context(config, dataset, str(index.get("scientific_use", "")))
    for key in ("dataset_sha256", "config_sha256", "fixture"):
        if index.get(key) != expected[key]:
            raise RuntimeError(f"checkpoint index {key} mismatch")
    rows = index.get("checkpoints")
    expected_cells = {(int(seed), arm) for seed in config["seeds"] for arm in config["factorial"]["arms"]}
    actual_cells = (
        {(int(row["seed"]), str(row["arm"])) for row in rows}
        if isinstance(rows, list)
        else set()
    )
    if actual_cells != expected_cells or len(rows) != len(expected_cells):
        raise RuntimeError("checkpoint index must contain every seed/arm exactly once")
    for row in rows:
        if row.get("teacher_checkpoint_sha256") != qualification_gate["teacher_checkpoint_sha256"]:
            raise RuntimeError("checkpoint index teacher hash mismatch")
    return rows


def _compatibility_dataset(
    model, dataset, teacher, config, normalization, scenes, active_only=True
):
    route_norm = fit_route_normalization(dataset, teacher)
    routed = route_dataset(dataset, teacher, config, scenes, normalization=route_norm)
    features = []
    labels = []
    native_scores = []
    native_training_scores = []
    bank_ids = []
    city_ids = []
    base_map_cluster_ids = []
    routes = []
    pair_ids = []
    physical_distances = []
    scene_indices = []
    edge_sources = []
    edge_targets = []
    positions = []
    csi_worlds = []
    zero = zero_typed_edit((1,), dataset.maps.shape[-1], int(dataset.metadata["assets"]["material_category_count"]))
    zero_tensor = torch.as_tensor(_normalized_action(normalization, zero), dtype=torch.float32)
    for scene_value in scenes:
        scene = int(scene_value)
        for edge in dataset.directed_edges(scene):
            if edge.source_world >= edge.target_world:
                continue
            for position in _eligible_evaluation_positions(dataset, scene):
                key = (scene, edge.source_world, edge.target_world, position)
                route_code = routed.alignment_route[key]
                if active_only and route_code != 2:
                    continue
                for csi_world, matched_map, alternative_map in (
                    (edge.source_world, edge.source_world, edge.target_world),
                    (edge.target_world, edge.target_world, edge.source_world),
                ):
                    for supplied_world, label in ((matched_map, 1), (alternative_map, 0)):
                        patches = _normalized_scene_patches(
                            dataset, normalization, teacher.patch_spec, scene, csi_world, position
                        )
                        maps = _normalized_map(normalization, dataset.maps[scene, supplied_world])[None, ...]
                        radio = _normalized_radio(
                            normalization, dataset.radio_config[scene], dataset.bs_pose[scene]
                        )[None, ...]
                        with torch.no_grad():
                            patch_tensor = torch.as_tensor(patches[None, ...], dtype=torch.float32)
                            map_tensor = torch.as_tensor(maps, dtype=torch.float32)
                            radio_tensor = torch.as_tensor(radio, dtype=torch.float32)
                            representation, training_score = _masked_alignment_state_and_score(
                                model,
                                patch_tensor,
                                map_tensor,
                                radio_tensor,
                                zero_tensor,
                                tuple(
                                    entry
                                    for entry in teacher.mask_bank
                                    if entry.mode == "random_75"
                                ),
                                routed.teacher_latent[scene][csi_world, position],
                                patches,
                                normalization,
                            )
                            _, audit_score = _masked_alignment_state_and_score(
                                model,
                                patch_tensor,
                                map_tensor,
                                radio_tensor,
                                zero_tensor,
                                tuple(
                                    entry
                                    for entry in teacher.audit_mask_bank
                                    if entry.mode == "random_75"
                                ),
                                routed.teacher_latent[scene][csi_world, position],
                                patches,
                                normalization,
                            )
                        features.append(representation)
                        labels.append(label)
                        native_scores.append(audit_score)
                        native_training_scores.append(training_score)
                        bank_ids.append(str(dataset.bank_ids[scene]))
                        city_ids.append(str(dataset.city_ids[scene]))
                        base_map_cluster_ids.append(str(dataset.base_map_cluster_ids[scene]))
                        routes.append(str(ROUTE_NAMES[route_code]))
                        pair_ids.append(
                            f"{dataset.bank_ids[scene]}:{edge.source_world}:{edge.target_world}:"
                            f"{position}:{csi_world}"
                        )
                        physical_distances.append(routed.alignment_distances[key][0])
                        scene_indices.append(scene)
                        edge_sources.append(edge.source_world)
                        edge_targets.append(edge.target_world)
                        positions.append(position)
                        csi_worlds.append(csi_world)
    if not features:
        raise RuntimeError("compatibility probe dataset has no active quartets")
    return {
        "features": np.asarray(features, dtype=np.float64),
        "labels": np.asarray(labels, dtype=np.int64),
        "native_scores": np.asarray(native_scores, dtype=np.float64),
        "native_training_scores": np.asarray(native_training_scores, dtype=np.float64),
        "bank_ids": np.asarray(bank_ids),
        "city_ids": np.asarray(city_ids),
        "base_map_cluster_ids": np.asarray(base_map_cluster_ids),
        "routes": np.asarray(routes),
        "pair_ids": np.asarray(pair_ids),
        "physical_distances": np.asarray(physical_distances, dtype=np.float64),
        "scene_indices": np.asarray(scene_indices, dtype=np.int64),
        "edge_sources": np.asarray(edge_sources, dtype=np.int64),
        "edge_targets": np.asarray(edge_targets, dtype=np.int64),
        "positions": np.asarray(positions, dtype=np.int64),
        "csi_worlds": np.asarray(csi_worlds, dtype=np.int64),
    }


def _masked_alignment_state_and_score(
    model,
    patch_tensor,
    map_tensor,
    radio_tensor,
    zero_tensor,
    mask_bank,
    latent_targets,
    physical_targets,
    normalization,
):
    representations = []
    errors = []
    for entry in mask_bank:
        visible = patch_tensor.clone()
        visible[:, entry.mask] = 0.0
        masks = torch.as_tensor(entry.mask[None, :], dtype=torch.bool)
        state = model.state(visible, map_tensor, radio_tensor, masks)
        query = torch.as_tensor([entry.query], dtype=torch.long)
        prediction_z, prediction_y = model.predict(state, zero_tensor, query)
        target_z = (
            latent_targets[entry.query] - normalization.latent_mean
        ) / normalization.latent_scale
        errors.append(
            endpoint_per_sample(
                prediction_z,
                prediction_y,
                torch.as_tensor(target_z[None, :], dtype=torch.float32),
                torch.as_tensor(physical_targets[entry.query][None, :], dtype=torch.float32),
                1.0,
            )[0]
        )
        representations.append(state[0].mean(dim=0))
    if {int(entry.query) for entry in mask_bank} != set(range(patch_tensor.shape[1])):
        raise RuntimeError("alignment mask bank must cover every query exactly once")
    return (
        torch.mean(torch.stack(representations), dim=0).cpu().numpy(),
        -float(torch.mean(torch.stack(errors)).cpu()),
    )


def _eligible_evaluation_positions(dataset, scene):
    if str(dataset.scene_roles[scene]) == "target":
        selected = np.flatnonzero(dataset.position_roles[scene] == "query")
        if selected.size == 0:
            raise RuntimeError("target evaluation has no query positions after support exclusion")
        return selected.astype(np.int64)
    return np.arange(dataset.position_count, dtype=np.int64)


def _paired_score_differences(scores, labels, pair_ids):
    values = np.asarray(scores, dtype=np.float64)
    targets = np.asarray(labels, dtype=np.int64)
    identifiers = np.asarray(pair_ids).astype(str)
    differences = []
    for pair_id in np.unique(identifiers):
        mask = identifiers == pair_id
        if int(np.sum(mask)) != 2 or set(targets[mask].tolist()) != {0, 1}:
            raise RuntimeError("compatibility pair must contain one matched and one alternative score")
        differences.append(float(values[mask & (targets == 1)][0] - values[mask & (targets == 0)][0]))
    if not differences:
        raise RuntimeError("compatibility route has no complete paired scores")
    return np.asarray(differences, dtype=np.float64)


def _active_effect_bin_rows(seed, arm, bank, city, scores, labels, pair_ids, distances):
    identifiers = np.asarray(pair_ids).astype(str)
    pair_order = np.unique(identifiers)
    if pair_order.size < 4:
        raise RuntimeError("active CGS effect-bin report requires at least four paired units per bank")
    pair_distance = np.asarray(
        [float(np.mean(np.asarray(distances)[identifiers == pair])) for pair in pair_order]
    )
    ranked = np.argsort(np.argsort(pair_distance, kind="stable"), kind="stable")
    bins = np.minimum(3, (4 * ranked) // pair_order.size)
    rows = []
    for bin_index, label in enumerate(("low", "medium_low", "medium_high", "high")):
        selected_pairs = pair_order[bins == bin_index]
        selected = np.isin(identifiers, selected_pairs)
        if not np.any(selected):
            raise RuntimeError("active CGS effect bin is empty")
        rows.append(
            {
                "seed": int(seed),
                "arm": str(arm),
                "bank_id": str(bank),
                "city_id": str(city),
                "effect_bin": label,
                "pair_count": int(selected_pairs.size),
                "physical_distance_min": float(np.min(np.asarray(distances)[selected])),
                "physical_distance_max": float(np.max(np.asarray(distances)[selected])),
                "cgs_auroc": binary_auroc(np.asarray(labels)[selected], np.asarray(scores)[selected]),
            }
        )
    return rows


def _compatibility_effect_rows(seed, arm, evaluated, probabilities):
    rows = []
    pair_ids = evaluated["pair_ids"]
    for pair_id in np.unique(pair_ids):
        mask = pair_ids == pair_id
        difference = _paired_score_differences(
            probabilities[mask], evaluated["labels"][mask], pair_ids[mask]
        )[0]
        first = int(np.flatnonzero(mask)[0])
        rows.append(
            {
                "seed": int(seed),
                "arm": str(arm),
                "pair_id": str(pair_id),
                "scene_index": int(evaluated["scene_indices"][first]),
                "bank_id": str(evaluated["bank_ids"][first]),
                "base_map_cluster_id": str(
                    evaluated.get("base_map_cluster_ids", evaluated["bank_ids"])[first]
                ),
                "city_id": str(evaluated["city_ids"][first]),
                "source_world": int(evaluated["csi_worlds"][first]),
                "target_world": int(
                    evaluated["edge_targets"][first]
                    if evaluated["csi_worlds"][first] == evaluated["edge_sources"][first]
                    else evaluated["edge_sources"][first]
                ),
                "position_index": int(evaluated["positions"][first]),
                "route": str(evaluated["routes"][first]),
                "physical_distance": float(evaluated["physical_distances"][first]),
                "matched_minus_alternative": float(difference),
            }
        )
    return rows


def _response_probe_dataset(model, dataset, teacher, config, normalization, scenes, active_only):
    route_norm = fit_route_normalization(dataset, teacher)
    routed = route_dataset(dataset, teacher, config, scenes, normalization=route_norm)
    features = []
    action_swap_features = []
    no_action_features = []
    without_map_features = []
    edit_only_features = []
    csi_only_features = []
    oracle_x_features = []
    targets = []
    bank_ids = []
    city_ids = []
    source_targets = []
    routes = []
    pair_ids = []
    scene_indices = []
    source_worlds = []
    target_worlds = []
    positions = []
    queries = []
    cluster_ids = []
    material_categories = int(dataset.metadata["assets"]["material_category_count"])
    world_lookup = {tuple(row): index for index, row in enumerate(dataset.world_bits.tolist())}
    for scene_value in scenes:
        scene = int(scene_value)
        for edge in dataset.directed_edges(scene):
            action = typed_signed_edit(
                dataset.maps[scene, edge.source_world],
                dataset.maps[scene, edge.target_world],
                dataset.map_channel_names,
                material_categories,
            )
            action_features = multichannel_spatial_features(
                _normalized_action(normalization, action)
            )
            other_bit = (edge.bit_index + 1) % dataset.bit_count
            swap_bits = dataset.world_bits[edge.source_world].copy()
            swap_bits[other_bit] = 1 - swap_bits[other_bit]
            swap_world = world_lookup[tuple(int(value) for value in swap_bits)]
            swap_action = typed_signed_edit(
                dataset.maps[scene, edge.source_world],
                dataset.maps[scene, swap_world],
                dataset.map_channel_names,
                material_categories,
            )
            swap_action_features = multichannel_spatial_features(
                _normalized_action(normalization, swap_action)
            )
            no_action_vector = np.zeros_like(action_features)
            for position in _eligible_evaluation_positions(dataset, scene):
                source_patches = _normalized_scene_patches(
                    dataset,
                    normalization,
                    teacher.patch_spec,
                    scene,
                    edge.source_world,
                    int(position),
                )
                maps = _normalized_map(
                    normalization, dataset.maps[scene, edge.source_world]
                )[None, ...]
                radio = _normalized_radio(
                    normalization, dataset.radio_config[scene], dataset.bs_pose[scene]
                )[None, ...]
                for query in range(teacher.patch_spec.patch_count):
                    key = (scene, edge.source_world, edge.target_world, position, query)
                    if active_only and routed.response_route[key] != 2:
                        continue
                    query_onehot = np.zeros(teacher.patch_spec.patch_count)
                    query_onehot[query] = 1.0
                    entry = next(item for item in teacher.mask_bank if item.query == query)
                    visible = source_patches.copy()
                    visible[entry.mask] = 0.0
                    with torch.no_grad():
                        state = model.state(
                            torch.as_tensor(visible[None, ...], dtype=torch.float32),
                            torch.as_tensor(maps, dtype=torch.float32),
                            torch.as_tensor(radio, dtype=torch.float32),
                            torch.as_tensor(entry.mask[None, :], dtype=torch.bool),
                        )[0, query].numpy()
                        no_map_state = model.state(
                            torch.as_tensor(visible[None, ...], dtype=torch.float32),
                            torch.zeros_like(torch.as_tensor(maps, dtype=torch.float32)),
                            torch.as_tensor(radio, dtype=torch.float32),
                            torch.as_tensor(entry.mask[None, :], dtype=torch.bool),
                        )[0, query].numpy()
                    features.append(np.concatenate((state, action_features, query_onehot)))
                    action_swap_features.append(
                        np.concatenate((state, swap_action_features, query_onehot))
                    )
                    no_action_features.append(
                        np.concatenate((state, no_action_vector, query_onehot))
                    )
                    without_map_features.append(
                        np.concatenate((no_map_state, action_features, query_onehot))
                    )
                    edit_only_features.append(
                        np.concatenate((np.zeros_like(state), action_features, query_onehot))
                    )
                    csi_only_features.append(
                        np.concatenate((no_map_state, no_action_vector, query_onehot))
                    )
                    oracle_state = np.zeros_like(state)
                    oracle_state[:2] = (
                        dataset.positions[scene, position] - normalization.position_mean
                    ) / normalization.position_scale
                    oracle_x_features.append(
                        np.concatenate((oracle_state, action_features, query_onehot))
                    )
                    targets.append(
                        _normalized_scene_patches(
                            dataset,
                            normalization,
                            teacher.patch_spec,
                            scene,
                            edge.target_world,
                            position,
                        )[query]
                    )
                    source_targets.append(
                        _normalized_scene_patches(
                            dataset,
                            normalization,
                            teacher.patch_spec,
                            scene,
                            edge.source_world,
                            position,
                        )[query]
                    )
                    bank_ids.append(str(dataset.bank_ids[scene]))
                    city_ids.append(str(dataset.city_ids[scene]))
                    routes.append(str(ROUTE_NAMES[routed.response_route[key]]))
                    pair_ids.append(
                        f"{dataset.bank_ids[scene]}:{edge.source_world}:{edge.target_world}:{position}:{query}"
                    )
                    scene_indices.append(scene)
                    source_worlds.append(edge.source_world)
                    target_worlds.append(edge.target_world)
                    positions.append(position)
                    queries.append(query)
                    cluster_ids.append(str(dataset.base_map_cluster_ids[scene]))
    if not features:
        raise RuntimeError("response probe dataset has no eligible patches")
    return {
        "features": np.asarray(features),
        "action_swap_features": np.asarray(action_swap_features),
        "no_action_features": np.asarray(no_action_features),
        "without_map_features": np.asarray(without_map_features),
        "edit_only_features": np.asarray(edit_only_features),
        "csi_only_features": np.asarray(csi_only_features),
        "oracle_x_features": np.asarray(oracle_x_features),
        "targets": np.asarray(targets),
        "bank_ids": np.asarray(bank_ids),
        "city_ids": np.asarray(city_ids),
        "source_targets": np.asarray(source_targets),
        "routes": np.asarray(routes),
        "pair_ids": np.asarray(pair_ids),
        "scene_indices": np.asarray(scene_indices, dtype=np.int64),
        "source_worlds": np.asarray(source_worlds, dtype=np.int64),
        "target_worlds": np.asarray(target_worlds, dtype=np.int64),
        "positions": np.asarray(positions, dtype=np.int64),
        "queries": np.asarray(queries, dtype=np.int64),
        "base_map_cluster_ids": np.asarray(cluster_ids),
        "input_contract": "masked_F_query_state_plus_typed_action_plus_query; target patch is supervision-only",
    }


def _response_effect_rows(
    seed, arm, evaluated, prediction, action_swap_prediction, no_action_prediction
):
    rows = []
    for pair_id in np.unique(evaluated["pair_ids"]):
        mask = evaluated["pair_ids"] == pair_id
        prediction_error = float(np.mean((prediction[mask] - evaluated["targets"][mask]) ** 2))
        copy_error = float(
            np.mean((evaluated["source_targets"][mask] - evaluated["targets"][mask]) ** 2)
        )
        action_swap_error = float(
            np.mean((action_swap_prediction[mask] - evaluated["targets"][mask]) ** 2)
        )
        no_action_error = float(
            np.mean((no_action_prediction[mask] - evaluated["targets"][mask]) ** 2)
        )
        first = int(np.flatnonzero(mask)[0])
        rows.append(
            {
                "seed": int(seed),
                "arm": str(arm),
                "pair_id": str(pair_id),
                "scene_index": int(evaluated["scene_indices"][first]),
                "bank_id": str(evaluated["bank_ids"][first]),
                "base_map_cluster_id": str(evaluated["base_map_cluster_ids"][first]),
                "city_id": str(evaluated["city_ids"][first]),
                "source_world": int(evaluated["source_worlds"][first]),
                "target_world": int(evaluated["target_worlds"][first]),
                "position_index": int(evaluated["positions"][first]),
                "query_index": int(evaluated["queries"][first]),
                "route": str(evaluated["routes"][first]),
                "prediction_mse": prediction_error,
                "copy_mse": copy_error,
                "action_swap_mse": action_swap_error,
                "no_action_mse": no_action_error,
                "response_advantage": copy_error - prediction_error,
                "response_advantage_vs_action_swap": action_swap_error - prediction_error,
                "response_advantage_vs_no_action": no_action_error - prediction_error,
            }
        )
    return rows


def _native_mask_cover_metrics(model, dataset, teacher, config, normalization, scenes, bank_id):
    scene_matches = [int(scene) for scene in scenes if str(dataset.bank_ids[int(scene)]) == bank_id]
    if len(scene_matches) != 1:
        raise RuntimeError("native response bank join is not unique")
    scene = scene_matches[0]
    route_norm = fit_route_normalization(dataset, teacher)
    routed = route_dataset(dataset, teacher, config, np.asarray([scene]), normalization=route_norm)
    material_categories = int(dataset.metadata["assets"]["material_category_count"])
    predictions = []
    latent_predictions = []
    no_action_predictions = []
    latent_no_action_predictions = []
    action_swap_predictions = []
    latent_action_swap_predictions = []
    sources = []
    latent_sources = []
    targets = []
    latent_targets = []
    direction_cosines = []
    magnitude_errors = []
    null_delta_norms = []
    latent_null_delta_norms = []
    audit_entries = [
        entry for entry in teacher.audit_mask_bank if entry.mode == "random_75"
    ]
    world_lookup = {tuple(row): index for index, row in enumerate(dataset.world_bits.tolist())}
    for edge in dataset.directed_edges(scene):
        action = typed_signed_edit(
            dataset.maps[scene, edge.source_world],
            dataset.maps[scene, edge.target_world],
            dataset.map_channel_names,
            material_categories,
        )
        action_tensor = torch.as_tensor(
            _normalized_action(normalization, action[None, ...]), dtype=torch.float32
        )
        other_bit = (edge.bit_index + 1) % dataset.bit_count
        swap_bits = dataset.world_bits[edge.source_world].copy()
        swap_bits[other_bit] = 1 - swap_bits[other_bit]
        swap_world = world_lookup[tuple(int(value) for value in swap_bits)]
        swap_action = typed_signed_edit(
            dataset.maps[scene, edge.source_world],
            dataset.maps[scene, swap_world],
            dataset.map_channel_names,
            material_categories,
        )
        swap_action_tensor = torch.as_tensor(
            _normalized_action(normalization, swap_action[None, ...]), dtype=torch.float32
        )
        zero_action_tensor = torch.zeros_like(action_tensor)
        for position in _eligible_evaluation_positions(dataset, scene):
            akey = (scene, edge.source_world, edge.target_world, position)
            if routed.alignment_route[akey] != 2:
                continue
            source = _normalized_scene_patches(
                dataset, normalization, teacher.patch_spec, scene, edge.source_world, position
            )
            target = _normalized_scene_patches(
                dataset, normalization, teacher.patch_spec, scene, edge.target_world, position
            )
            predicted = np.zeros_like(target)
            predicted_latent = np.zeros(
                (teacher.patch_spec.patch_count, normalization.latent_mean.size),
                dtype=np.float64,
            )
            predicted_no_action = np.zeros_like(target)
            predicted_latent_no_action = np.zeros_like(predicted_latent)
            predicted_action_swap = np.zeros_like(target)
            predicted_latent_action_swap = np.zeros_like(predicted_latent)
            for query in range(teacher.patch_spec.patch_count):
                entry = next(item for item in audit_entries if item.query == query)
                visible = source.copy()
                visible[entry.mask] = 0.0
                maps = _normalized_map(normalization, dataset.maps[scene, edge.source_world])[None, ...]
                radio = _normalized_radio(
                    normalization, dataset.radio_config[scene], dataset.bs_pose[scene]
                )[None, ...]
                with torch.no_grad():
                    state = model.state(
                        torch.as_tensor(visible[None, ...], dtype=torch.float32),
                        torch.as_tensor(maps, dtype=torch.float32),
                        torch.as_tensor(radio, dtype=torch.float32),
                        torch.as_tensor(entry.mask[None, :], dtype=torch.bool),
                    )
                    latent_value, value = model.predict(
                        state, action_tensor, torch.as_tensor([query], dtype=torch.long)
                    )
                    latent_no_action, no_action_value = model.predict(
                        state, zero_action_tensor, torch.as_tensor([query], dtype=torch.long)
                    )
                    latent_swap, swap_value = model.predict(
                        state, swap_action_tensor, torch.as_tensor([query], dtype=torch.long)
                    )
                predicted[query] = value[0].numpy()
                predicted_latent[query] = latent_value[0].numpy()
                predicted_no_action[query] = no_action_value[0].numpy()
                predicted_latent_no_action[query] = latent_no_action[0].numpy()
                predicted_action_swap[query] = swap_value[0].numpy()
                predicted_latent_action_swap[query] = latent_swap[0].numpy()
                rkey = (scene, edge.source_world, edge.target_world, int(position), query)
                if routed.response_route[rkey] == 0:
                    null_delta_norms.append(
                        float(np.sqrt(np.mean((predicted[query] - source[query]) ** 2)))
                    )
                    source_latent_query = (
                        routed.teacher_latent[scene][edge.source_world, position, query]
                        - normalization.latent_mean
                    ) / normalization.latent_scale
                    latent_null_delta_norms.append(
                        float(
                            np.sqrt(
                                np.mean(
                                    (predicted_latent[query] - source_latent_query) ** 2
                                )
                            )
                        )
                    )
            predictions.append(predicted)
            latent_predictions.append(predicted_latent)
            no_action_predictions.append(predicted_no_action)
            latent_no_action_predictions.append(predicted_latent_no_action)
            action_swap_predictions.append(predicted_action_swap)
            latent_action_swap_predictions.append(predicted_latent_action_swap)
            sources.append(source)
            latent_source = (
                routed.teacher_latent[scene][edge.source_world, position]
                - normalization.latent_mean
            ) / normalization.latent_scale
            latent_target = (
                routed.teacher_latent[scene][edge.target_world, position]
                - normalization.latent_mean
            ) / normalization.latent_scale
            latent_sources.append(latent_source)
            targets.append(target)
            latent_targets.append(latent_target)
            true_delta = (target - source).reshape(-1)
            predicted_delta = (predicted - source).reshape(-1)
            denominator = float(np.linalg.norm(true_delta) * np.linalg.norm(predicted_delta))
            direction_cosines.append(
                float(np.dot(true_delta, predicted_delta) / denominator) if denominator > 1e-12 else 0.0
            )
            magnitude_errors.append(
                float(
                    abs(np.linalg.norm(predicted_delta) - np.linalg.norm(true_delta))
                    / max(float(np.linalg.norm(true_delta)), 1e-12)
                )
            )
    if not predictions:
        raise RuntimeError("native response audit has no alignment-active transition")
    prediction = np.asarray(predictions)
    latent_prediction = np.asarray(latent_predictions)
    no_action_prediction = np.asarray(no_action_predictions)
    latent_no_action_prediction = np.asarray(latent_no_action_predictions)
    action_swap_prediction = np.asarray(action_swap_predictions)
    latent_action_swap_prediction = np.asarray(latent_action_swap_predictions)
    source = np.asarray(sources)
    latent_source = np.asarray(latent_sources)
    target = np.asarray(targets)
    latent_target = np.asarray(latent_targets)
    target_energy = max(float(np.sum(target**2)), 1e-12)
    latent_target_energy = max(float(np.sum(latent_target**2)), 1e-12)
    null_threshold = float(config["qualification"]["response_physical_null_rms_max"])
    return {
        "native_target_free_full_channel_nmse": float(
            np.sum((prediction - target) ** 2) / target_energy
        ),
        "native_copy_full_channel_nmse": float(np.sum((source - target) ** 2) / target_energy),
        "native_no_action_full_channel_nmse": float(
            np.sum((no_action_prediction - target) ** 2) / target_energy
        ),
        "native_action_swap_full_channel_nmse": float(
            np.sum((action_swap_prediction - target) ** 2) / target_energy
        ),
        "native_latent_nmse": float(
            np.sum((latent_prediction - latent_target) ** 2) / latent_target_energy
        ),
        "native_latent_copy_nmse": float(
            np.sum((latent_source - latent_target) ** 2) / latent_target_energy
        ),
        "native_latent_no_action_nmse": float(
            np.sum((latent_no_action_prediction - latent_target) ** 2)
            / latent_target_energy
        ),
        "native_latent_action_swap_nmse": float(
            np.sum((latent_action_swap_prediction - latent_target) ** 2)
            / latent_target_energy
        ),
        "native_delta_direction_cosine": float(np.mean(direction_cosines)),
        "native_delta_relative_magnitude_error": float(np.mean(magnitude_errors)),
        "native_null_patch_count": len(null_delta_norms),
        "native_null_delta_rms_mean": (
            float(np.mean(null_delta_norms)) if null_delta_norms else None
        ),
        "native_null_violation_rate": (
            float(np.mean(np.asarray(null_delta_norms) > null_threshold))
            if null_delta_norms
            else None
        ),
        "native_latent_null_delta_rms_mean": (
            float(np.mean(latent_null_delta_norms)) if latent_null_delta_norms else None
        ),
        "native_latent_null_violation_rate": (
            float(
                np.mean(
                    np.asarray(latent_null_delta_norms)
                    > float(config["qualification"]["response_latent_null_rms_max"])
                )
            )
            if latent_null_delta_norms
            else None
        ),
        "native_mask_bank": "B_audit_hold",
        "native_input_contract": "masked source F-state plus supplied map/c/action/query; target CSI supervision-only",
    }


def _normalized_scene_patches(dataset, normalization, spec, scene, world, position):
    raw = patchify_csi(dataset.csi[scene, world, position], spec)
    return (raw - normalization.patch_mean) / normalization.patch_scale


def _evaluation_gate(
    config, dataset, cgs_rows, route_rows, effect_bin_rows, response_rows, factorial_gate, evidence
):
    def arm_metric(rows, arm, key):
        values = [row[key] for row in rows if row["arm"] == arm and row[key] is not None]
        return float(np.mean(values)) if values else float("nan")

    null_safety = _null_safety_by_arm(config, route_rows)
    null_safe = all(null_safety[arm]["passed"] for arm in ("alignment", "full"))
    response_null_safe = all(
        row.get("native_null_violation_rate") is not None
        and row.get("native_latent_null_violation_rate") is not None
        and row["native_null_violation_rate"]
        <= float(config["evaluation"]["response_null_violation_rate_max"])
        and row["native_latent_null_violation_rate"]
        <= float(config["evaluation"]["response_null_violation_rate_max"])
        for row in response_rows
        if row["arm"] in {"response", "full"}
    )
    resamples = int(config["evaluation"]["bootstrap_resamples"])
    alignment_superiority = _paired_arm_comparison(
        cgs_rows,
        "cgs_auroc",
        "alignment",
        "endpoint",
        higher_is_better=True,
        resamples=resamples,
        seed=81101,
    )
    response_superiority = _paired_arm_comparison(
        response_rows,
        "native_target_free_full_channel_nmse",
        "response",
        "endpoint",
        higher_is_better=False,
        resamples=resamples,
        seed=81102,
    )
    response_copy = _within_arm_advantage_interval(
        response_rows,
        "response",
        "native_copy_full_channel_nmse",
        "native_target_free_full_channel_nmse",
        resamples,
        81103,
    )
    response_swap = _within_arm_advantage_interval(
        response_rows,
        "response",
        "native_action_swap_full_channel_nmse",
        "native_target_free_full_channel_nmse",
        resamples,
        81104,
    )
    response_no_action = _within_arm_advantage_interval(
        response_rows,
        "response",
        "native_no_action_full_channel_nmse",
        "native_target_free_full_channel_nmse",
        resamples,
        81106,
    )
    latent_copy = _within_arm_advantage_interval(
        response_rows,
        "response",
        "native_latent_copy_nmse",
        "native_latent_nmse",
        resamples,
        81107,
    )
    latent_no_action = _within_arm_advantage_interval(
        response_rows,
        "response",
        "native_latent_no_action_nmse",
        "native_latent_nmse",
        resamples,
        81108,
    )
    latent_swap = _within_arm_advantage_interval(
        response_rows,
        "response",
        "native_latent_action_swap_nmse",
        "native_latent_nmse",
        resamples,
        81109,
    )
    shortcut_intervals = {
        name: _within_arm_advantage_interval(
            response_rows,
            "response",
            f"probe_{name}_active_patch_nmse",
            "unified_response_probe_active_patch_nmse",
            resamples,
            81120 + offset,
        )
        for offset, name in enumerate(("without_map", "edit_only", "csi_only"))
    }
    direction = _within_arm_level_interval(
        response_rows, "response", "native_delta_direction_cosine", resamples, 81105
    )
    family = [
        alignment_superiority,
        response_superiority,
        response_copy,
        response_no_action,
        response_swap,
        latent_copy,
        latent_no_action,
        latent_swap,
        *shortcut_intervals.values(),
        direction,
    ]
    adjusted = holm_adjust([float(row["p_value_two_sided"]) for row in family])
    for row, value in zip(family, adjusted):
        row["holm_adjusted_p"] = float(value)
    alpha = float(config["evaluation"]["familywise_alpha"])
    effect_bins_complete = _effect_bins_complete(cgs_rows, effect_bin_rows)
    gray_complete = all(
        any(
            row["arm"] == arm
            and row["route"] == "gray"
            and row["condition_status"] == "ASSESSED"
            for row in route_rows
        )
        for arm in ("endpoint", "alignment", "response", "full")
    )
    correlation_complete = all(
        arm_metric(cgs_rows, arm, "native_probe_spearman")
        >= float(config["evaluation"]["minimum_native_probe_correlation"])
        for arm in ("alignment", "full")
    )
    g3_subgates = {
        "1_alignment_active_cgs_superiority_ci": "PASS"
        if interval_decision(
            alignment_superiority,
            threshold=float(config["evaluation"]["minimum_alignment_superiority"]),
            relation="superiority",
        )
        and alignment_superiority["holm_adjusted_p"] < alpha
        else "FAIL",
        "2_response_active_native_superiority_ci": "PASS"
        if interval_decision(
            response_superiority,
            threshold=float(config["evaluation"]["minimum_response_superiority"]),
            relation="superiority",
        )
        and response_superiority["holm_adjusted_p"] < alpha
        else "FAIL",
        "3_response_physical_and_latent_baselines_ci": "PASS"
        if interval_decision(
            response_copy,
            threshold=float(config["evaluation"]["minimum_response_superiority"]),
            relation="superiority",
        )
        and interval_decision(
            response_swap,
            threshold=float(config["evaluation"]["minimum_response_superiority"]),
            relation="superiority",
        )
        and interval_decision(
            response_no_action,
            threshold=float(config["evaluation"]["minimum_response_superiority"]),
            relation="superiority",
        )
        and all(
            interval_decision(
                value,
                threshold=float(config["evaluation"]["minimum_response_superiority"]),
                relation="superiority",
            )
            for value in (latent_copy, latent_no_action, latent_swap)
        )
        and all(
            interval_decision(
                value,
                threshold=float(config["evaluation"]["minimum_response_superiority"]),
                relation="superiority",
            )
            and value["holm_adjusted_p"] < alpha
            for value in shortcut_intervals.values()
        )
        and response_copy["holm_adjusted_p"] < alpha
        and response_no_action["holm_adjusted_p"] < alpha
        and response_swap["holm_adjusted_p"] < alpha
        and all(
            value["holm_adjusted_p"] < alpha
            for value in (latent_copy, latent_no_action, latent_swap)
        )
        and all(
            np.isfinite(row["probe_oracle_x_active_patch_nmse"])
            for row in response_rows
            if row["arm"] == "response"
        )
        else "FAIL",
        "4_response_direction_and_magnitude": "PASS"
        if float(direction["ci95_low"]) > 0
        and direction["holm_adjusted_p"] < alpha
        and all(
            np.isfinite(row["native_delta_relative_magnitude_error"])
            for row in response_rows
            if row["arm"] == "response"
        )
        else "FAIL",
        "5_four_active_effect_bins": "PASS" if effect_bins_complete else "FAIL",
        "6_gray_distributions_reported": "PASS" if gray_complete else "FAIL",
        "7_null_equivalence_and_overclassification": "PASS"
        if null_safe and response_null_safe
        else "FAIL",
        "8_native_probe_correlation": "PASS" if correlation_complete else "FAIL",
    }
    g3_pass = all(value == "PASS" for value in g3_subgates.values())
    g4 = dict(factorial_gate["g4_subgates"])
    full_cgs = _paired_arm_comparison(
        cgs_rows, "cgs_auroc", "full", "alignment", True, resamples, 81201
    )
    full_response = _paired_arm_comparison(
        response_rows,
        "native_target_free_full_channel_nmse",
        "full",
        "response",
        False,
        resamples,
        81202,
    )
    g4["2_cgs_noninferior_to_alignment"] = "PASS" if interval_decision(
        full_cgs,
        threshold=abs(float(config["evaluation"]["minimum_cgs_noninferiority"])),
        relation="noninferiority",
    ) else "FAIL"
    g4["3_native_response_noninferior_to_response"] = "PASS" if interval_decision(
        full_response,
        threshold=abs(float(config["evaluation"]["minimum_response_noninferiority"])),
        relation="noninferiority",
    ) else "FAIL"
    g4_status = "PASS" if all(value == "PASS" for value in g4.values()) else (
        "FAIL" if any(value == "FAIL" for value in g4.values()) else "NOT_ASSESSED"
    )
    vector = complete_gate_vector(
        {
            "G1": "PASS",
            "G2": "PASS",
            "G3": "PASS" if g3_pass else "FAIL",
            "G4": g4_status,
            "G5": factorial_gate.get("gate_vector", {}).get("G5", "NOT_ASSESSED"),
        }
    )
    return {
        "schema_version": "csi-pairs-v6-evaluation-gate-v2",
        "status": "PASS" if g3_pass else "FAIL",
        "passed": bool(g3_pass),
        "scientific_claim_status": "SOFTWARE_ONLY" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM",
        **evidence,
        "gate_vector": vector,
        "g3_subgates": g3_subgates,
        "g3_intervals": {
            "alignment_superiority": alignment_superiority,
            "response_superiority": response_superiority,
            "response_vs_copy": response_copy,
            "response_vs_no_action": response_no_action,
            "response_vs_action_swap": response_swap,
            "latent_vs_copy": latent_copy,
            "latent_vs_no_action": latent_no_action,
            "latent_vs_action_swap": latent_swap,
            "shortcut_probe_intervals": shortcut_intervals,
            "response_direction": direction,
        },
        "c3_evidence_complete": g3_pass,
        "c5_evidence_complete": g3_pass,
        "g4_subgates": g4,
        "g4_intervals": {"full_cgs": full_cgs, "full_response": full_response},
        "null_compatibility_safety": null_safety,
        "claim_boundary": "G4 remains NOT_ASSESSED until equal-FLOP and both matched-concat controls are present.",
    }


def _paired_arm_comparison(
    rows, metric, first_arm, second_arm, higher_is_better, resamples, seed
):
    grouped = {}
    for row in rows:
        if row["arm"] not in {first_arm, second_arm} or row.get(metric) is None:
            continue
        key = (str(row["base_map_cluster_id"]), int(row["seed"]))
        grouped.setdefault((key, row["arm"]), []).append(float(row[metric]))
    cells = sorted(
        key for key in {item[0] for item in grouped}
        if (key, first_arm) in grouped and (key, second_arm) in grouped
    )
    if not cells:
        raise RuntimeError(f"paired comparison has no complete cells for {metric}")
    first = np.asarray([np.mean(grouped[(key, first_arm)]) for key in cells])
    second = np.asarray([np.mean(grouped[(key, second_arm)]) for key in cells])
    advantage = first - second if higher_is_better else second - first
    clusters = np.asarray([key[0] for key in cells])
    result = paired_cluster_interval(clusters, advantage, np.zeros_like(advantage), resamples, seed)
    test = paired_sign_flip_test(clusters, advantage, np.zeros_like(advantage), seed + 1)
    return {**result, "p_value_two_sided": test["p_value_two_sided"]}


def _within_arm_advantage_interval(
    rows, arm, baseline_metric, method_metric, resamples, seed
):
    selected = [row for row in rows if row["arm"] == arm]
    clusters = np.asarray([row["base_map_cluster_id"] for row in selected])
    baseline = np.asarray([row[baseline_metric] for row in selected], dtype=np.float64)
    method = np.asarray([row[method_metric] for row in selected], dtype=np.float64)
    result = paired_cluster_interval(clusters, baseline, method, resamples, seed)
    test = paired_sign_flip_test(clusters, baseline, method, seed + 1)
    return {**result, "p_value_two_sided": test["p_value_two_sided"]}


def _within_arm_level_interval(rows, arm, metric, resamples, seed):
    selected = [row for row in rows if row["arm"] == arm and row.get(metric) is not None]
    clusters = np.asarray([row["base_map_cluster_id"] for row in selected])
    values = np.asarray([row[metric] for row in selected], dtype=np.float64)
    zeros = np.zeros_like(values)
    result = paired_cluster_interval(clusters, values, zeros, resamples, seed)
    test = paired_sign_flip_test(clusters, values, zeros, seed + 1)
    return {**result, "p_value_two_sided": test["p_value_two_sided"]}


def _effect_bins_complete(cgs_rows, effect_bin_rows):
    expected = {
        (int(row["seed"]), str(row["arm"]), str(row["bank_id"]))
        for row in cgs_rows
    }
    bins = ("low", "medium_low", "medium_high", "high")
    return bool(expected) and all(
        {
            row["effect_bin"]
            for row in effect_bin_rows
            if (int(row["seed"]), str(row["arm"]), str(row["bank_id"])) == key
        }
        == set(bins)
        for key in expected
    )


def _null_safety_by_arm(config, route_rows):
    margin = float(config["evaluation"]["null_score_equivalence_margin"])
    maximum_rate = float(config["evaluation"]["null_overclassification_rate_max"])
    resamples = int(config["qualification"]["bootstrap_resamples"])
    result = {}
    for arm_index, arm in enumerate(("endpoint", "alignment", "response", "full")):
        rows = [
            row
            for row in route_rows
            if row["route"] == "null"
            and row["arm"] == arm
            and row.get("condition_status") == "ASSESSED"
        ]
        if len({row["base_map_cluster_id"] for row in rows}) < 2:
            result[arm] = {
                "base_map_cluster_count": len(
                    {row["base_map_cluster_id"] for row in rows}
                ),
                "passed": False,
                "reason": "fewer than two assessed independent null clusters",
            }
            continue
        bank_values = {}
        bank_rates = {}
        for row in rows:
            cluster = row["base_map_cluster_id"]
            bank_values.setdefault(cluster, []).append(row["matched_minus_alternative_mean"])
            bank_rates.setdefault(cluster, []).append(row["overclassification_rate"])
        banks = sorted(bank_values)
        values = np.asarray([np.mean(bank_values[bank]) for bank in banks], dtype=np.float64)
        rates = np.asarray([np.mean(bank_rates[bank]) for bank in banks], dtype=np.float64)
        rng = np.random.default_rng(91001 + arm_index)
        samples = np.empty(resamples, dtype=np.float64)
        for index in range(resamples):
            selected = rng.integers(0, len(banks), size=len(banks))
            samples[index] = float(np.mean(values[selected]))
        low = float(np.percentile(samples, 2.5))
        high = float(np.percentile(samples, 97.5))
        rate = float(np.mean(rates))
        result[arm] = {
            "base_map_cluster_count": len(banks),
            "mean_score_difference": float(np.mean(values)),
            "ci95_low": low,
            "ci95_high": high,
            "equivalence_margin": margin,
            "overclassification_rate": rate,
            "overclassification_rate_max": maximum_rate,
            "passed": bool(low >= -margin and high <= margin and rate <= maximum_rate),
        }
    return result
