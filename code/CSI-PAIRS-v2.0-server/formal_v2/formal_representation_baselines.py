from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import torch

from .external_adapters.representation_models import BaselineBatch, WWMJEPA, build_representation_model
from .formal_data_verification import require_verified_roles_from_root
from .formal_evidence import bind_rows, evidence_context
from .formal_io import artifact_manifest, read_strict_json, sha256_file, write_csv, write_json
from .formal_localization import adapt_position_head, fit_source_position_head, predict_position_distribution
from .formal_protocol import PatchSpec
from .formal_resources import validate_resource_registry


CONFIG_SCHEMA = "csi-pairs-v6-representation-baselines-v1"
MODEL_NAMES = {"CSI-MAE", "CSI-CLIP", "CSI-CLIP++", "ContraWiMAE", "WWM"}
IMPLEMENTATION_STATUSES = {
    "paper-spec-controlled-implementation",
    "style-controlled-implementation",
}


def run_representation_baselines(config, dataset, adapter_config_path, output_root):
    required_roles = (
        "source_encoder_train",
        "source_method_selection",
        "source_probe_train",
        "source_probe_selection",
        "source_final_unseen_bank",
        "target",
    )
    require_verified_roles_from_root(output_root, config, dataset, required_roles)
    adapter_config_path = Path(adapter_config_path).resolve()
    adapter = load_representation_config(adapter_config_path)
    if not dataset.is_fixture and adapter["profile"] != "formal-paper-dose":
        raise RuntimeError("scientific representation execution requires the formal-paper-dose profile")
    project_root = Path(__file__).resolve().parents[1]
    resource_registry_path = Path(__file__).resolve().parent / "configs" / "waibu_resources_v1.json"
    resource_rows = validate_resource_registry(
        read_strict_json(resource_registry_path), project_root / "waibu"
    )
    resources = {row["resource_id"]: row for row in resource_rows}
    output_dir = Path(output_root) / "representation_baselines"
    output_dir.mkdir(parents=True, exist_ok=False)
    evidence = evidence_context(
        config, dataset, "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
    )
    spec = PatchSpec.from_metadata(dataset.metadata)
    normalizer = _fit_normalizer(dataset, dataset.indices_for_role("source_encoder_train"))
    support_draws = _target_support_draws(config, adapter, dataset)
    status_rows = []
    metric_rows = []
    per_query_rows = []
    for model_index, model_config in enumerate(adapter["models"]):
        model_name = model_config["model_name"]
        resource = resources.get(model_config["resource_id"])
        if resource is None or resource["status"] != "PASS":
            raise RuntimeError(f"representation baseline resource is not authenticated: {model_name}")
        allowed_labels = {resource["allowed_name"]}
        if model_name == "CSI-CLIP++":
            allowed_labels.add("CSI-CLIP++-style controlled implementation")
        if model_config["paper_label"] not in allowed_labels:
            raise RuntimeError(f"representation baseline label exceeds its authenticated provenance: {model_name}")
        model_output = output_dir / _slug(model_name)
        model_output.mkdir(parents=True, exist_ok=False)
        torch.manual_seed(int(adapter["seed"]) + model_index)
        model = build_representation_model(
            model_name,
            spec,
            dataset.maps.shape[2],
            dataset.radio_config.shape[1] + dataset.bs_pose.shape[1] + 2,
            model_config,
        )
        checkpoint, training_record = _train_model(
            model,
            model_name,
            model_config,
            dataset,
            normalizer,
            model_output,
            seed=int(adapter["seed"]) + model_index,
        )
        write_json(model_output / "training_record.json", training_record)
        rows, queries, probe_record = _evaluate_localization(
            model,
            model_name,
            model_config,
            adapter,
            config,
            dataset,
            normalizer,
            support_draws,
            seed=int(adapter["seed"]) + model_index,
        )
        write_json(model_output / "probe_record.json", probe_record)
        write_csv(model_output / "localization_metrics.csv", bind_rows(rows, evidence))
        write_csv(model_output / "localization_per_query.csv", bind_rows(queries, evidence))
        metric_rows.extend(rows)
        per_query_rows.extend(queries)
        status_rows.append(
            {
                "model_name": model_name,
                "paper_label": model_config["paper_label"],
                "implementation_status": model_config["implementation_status"],
                "resource_id": model_config["resource_id"],
                "resource_sha256": resource["sha256"],
                "checkpoint_path": str(checkpoint.relative_to(output_dir)),
                "checkpoint_sha256": sha256_file(checkpoint),
                "status": "PASS",
            }
        )
    write_csv(output_dir / "model_status.csv", bind_rows(status_rows, evidence))
    write_csv(output_dir / "localization_metrics.csv", bind_rows(metric_rows, evidence))
    write_csv(output_dir / "localization_per_query.csv", bind_rows(per_query_rows, evidence))
    passed = len(status_rows) == len(adapter["models"]) and all(row["status"] == "PASS" for row in status_rows)
    gate = {
        "schema_version": "csi-pairs-v6-representation-baseline-gate-v1",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        **evidence,
        "profile": adapter["profile"],
        "adapter_config_sha256": sha256_file(adapter_config_path),
        "resource_registry_sha256": sha256_file(resource_registry_path),
        "executed_model_count": len(status_rows),
        "executed_models": [row["model_name"] for row in status_rows],
        "c1_eligible_model_count": 0,
        "claim_scope": "representation/localization comparison only; these rows cannot satisfy C1",
    }
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


def load_representation_config(path: str | Path) -> dict:
    payload = read_strict_json(path)
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "profile",
        "seed",
        "source_roles",
        "probe",
        "models",
    }:
        raise ValueError("representation baseline config fields must be exact")
    if payload["schema_version"] != CONFIG_SCHEMA:
        raise ValueError("representation baseline config schema mismatch")
    if payload["profile"] not in {"formal-paper-dose", "software-smoke-only"}:
        raise ValueError("representation baseline profile is invalid")
    if payload["source_roles"] != {
        "pretrain": "source_encoder_train",
        "selection": "source_method_selection",
        "probe_train": "source_probe_train",
        "probe_selection": "source_probe_selection",
        "evaluation": ["source_final_unseen_bank", "target"],
    }:
        raise ValueError("representation baseline role ledger is not frozen V6")
    _positive_integer(payload["seed"], "seed")
    if set(payload["probe"]) != {"head_steps", "learning_rate", "hidden_dim", "label_draws"}:
        raise ValueError("representation probe config fields must be exact")
    for key in ("head_steps", "hidden_dim", "label_draws"):
        _positive_integer(payload["probe"][key], f"probe.{key}")
    _positive_number(payload["probe"]["learning_rate"], "probe.learning_rate")
    models = payload["models"]
    if not isinstance(models, list) or not models:
        raise ValueError("representation models must be a nonempty list")
    expected_fields = {
        "model_name",
        "paper_label",
        "implementation_status",
        "resource_id",
        "epochs",
        "batch_size",
        "learning_rate",
        "weight_decay",
        "warmup_epochs",
        "mask_fraction",
        "dim",
        "heads",
        "encoder_layers",
        "decoder_layers",
        "resnet_width",
        "resnet_depth",
        "ema",
        "reconstruction_weight",
        "minimum_snr_db",
        "maximum_snr_db",
    }
    names = []
    for row in models:
        if not isinstance(row, dict) or set(row) != expected_fields:
            raise ValueError("representation model config fields must be exact")
        if row["model_name"] not in MODEL_NAMES or row["model_name"] in names:
            raise ValueError("representation model name is invalid or duplicated")
        names.append(row["model_name"])
        if row["implementation_status"] not in IMPLEMENTATION_STATUSES:
            raise ValueError("representation implementation status is invalid")
        for key in ("epochs", "batch_size", "dim", "heads", "encoder_layers", "decoder_layers", "resnet_width", "resnet_depth"):
            _positive_integer(row[key], f"{row['model_name']}.{key}")
        for key in ("learning_rate", "ema", "reconstruction_weight"):
            _positive_number(row[key], f"{row['model_name']}.{key}")
        if not isinstance(row["mask_fraction"], (int, float)) or isinstance(row["mask_fraction"], bool):
            raise ValueError("mask fraction must be numeric")
        if row["weight_decay"] < 0 or row["warmup_epochs"] < 0:
            raise ValueError("weight decay and warmup epochs must be nonnegative")
        if row["dim"] % row["heads"]:
            raise ValueError("representation dimension must be divisible by attention heads")
        if not 0.0 <= row["mask_fraction"] < 1.0 or not 0.0 < row["ema"] < 1.0:
            raise ValueError("mask fraction or EMA is out of range")
        if not 0.0 < row["reconstruction_weight"] < 1.0:
            raise ValueError("reconstruction weight must lie strictly between zero and one")
        if row["minimum_snr_db"] >= row["maximum_snr_db"]:
            raise ValueError("ContraWiMAE SNR range is empty")
    return payload


def _train_model(model, model_name, model_config, dataset, normalizer, output, *, seed):
    train_units = _world_position_units(dataset, "source_encoder_train")
    selection_units = _world_position_units(dataset, "source_method_selection")
    if not train_units or not selection_units:
        raise RuntimeError("representation pretraining roles are empty")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(model_config["learning_rate"]),
        weight_decay=float(model_config["weight_decay"]),
    )
    batch_size = int(model_config["batch_size"])
    steps_per_epoch = max(1, math.ceil(len(train_units) / batch_size))
    total_steps = int(model_config["epochs"]) * steps_per_epoch
    warmup_steps = int(model_config["warmup_epochs"]) * steps_per_epoch

    def factor(step):
        if warmup_steps and step < warmup_steps:
            return max((step + 1) / warmup_steps, 1e-6)
        progress = (step - warmup_steps) / max(total_steps - warmup_steps, 1)
        return 0.5 * (1.0 + math.cos(math.pi * min(max(progress, 0.0), 1.0)))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, factor)
    rng = np.random.default_rng(int(seed))
    best_state = None
    best_loss = float("inf")
    best_epoch = 0
    training_loss = float("nan")
    for epoch in range(1, int(model_config["epochs"]) + 1):
        order = rng.permutation(len(train_units))
        model.train()
        for start in range(0, len(order), batch_size):
            chosen = [train_units[int(index)] for index in order[start : start + batch_size]]
            batch = _make_batch(dataset, chosen, normalizer, device)
            loss = model.pretraining_loss(batch, float(model_config["mask_fraction"]))
            if not torch.isfinite(loss):
                raise RuntimeError(f"{model_name} produced nonfinite pretraining loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
            optimizer.step()
            if isinstance(model, WWMJEPA):
                model.update_target()
            scheduler.step()
            training_loss = float(loss.detach().cpu())
        selection_loss = _mean_pretraining_loss(
            model, dataset, selection_units, normalizer, device, model_config
        )
        if selection_loss < best_loss:
            best_loss = selection_loss
            best_epoch = epoch
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    if best_state is None:
        raise RuntimeError(f"{model_name} source-method-selection produced no checkpoint")
    model.load_state_dict(best_state)
    model.to(device).eval()
    checkpoint = output / "source_selected.pt"
    torch.save(
        {
            "schema_version": "csi-pairs-v6-representation-checkpoint-v1",
            "model_name": model_name,
            "paper_label": model_config["paper_label"],
            "implementation_status": model_config["implementation_status"],
            "dataset_sha256": sha256_file(dataset.source_path),
            "train_role": "source_encoder_train",
            "selection_role": "source_method_selection",
            "target_roles_read": [],
            "selected_epoch": best_epoch,
            "selection_loss": best_loss,
            "normalizer": {key: value.tolist() for key, value in normalizer.items()},
            "model_config": model_config,
            "state_dict": best_state,
        },
        checkpoint,
    )
    return checkpoint, {
        "schema_version": "csi-pairs-v6-representation-training-record-v1",
        "model_name": model_name,
        "device": str(device),
        "epochs": int(model_config["epochs"]),
        "batch_size": batch_size,
        "optimizer": "AdamW",
        "scheduler": "linear-warmup-cosine",
        "last_training_loss": training_loss,
        "selected_epoch": best_epoch,
        "selection_loss": best_loss,
        "train_role": "source_encoder_train",
        "selection_role": "source_method_selection",
        "probe_roles_read": [],
        "target_roles_read": [],
    }


def _evaluate_localization(model, model_name, model_config, adapter, formal_config, dataset, normalizer, support_draws, *, seed):
    source_units = _natural_position_units(dataset, "source_probe_train", query_only=False)
    source_selection_units = _natural_position_units(dataset, "source_probe_selection", query_only=False)
    source_rep, source_position, _ = _represent(model, dataset, source_units, normalizer)
    selection_rep, selection_position, _ = _represent(model, dataset, source_selection_units, normalizer)
    head_config = {
        "model": {"hidden_dim": int(adapter["probe"]["hidden_dim"]) * 2},
        "localization": {
            "head_steps": int(adapter["probe"]["head_steps"]),
            "learning_rate": float(adapter["probe"]["learning_rate"]),
            "sigma_min": float(formal_config["localization"]["sigma_min"]),
        },
    }
    source_head = fit_source_position_head(source_rep, source_position, head_config, seed=int(seed))
    selection_mean, _, _ = predict_position_distribution(
        source_head, selection_rep, sigma_min=float(formal_config["localization"]["sigma_min"])
    )
    selection_error = np.linalg.norm(selection_mean - selection_position, axis=1)
    query_rows = []
    metric_rows = []
    source_final = _natural_position_units(dataset, "source_final_unseen_bank", query_only=False)
    _append_evaluation(
        model,
        source_head,
        model_name,
        model_config,
        dataset,
        normalizer,
        source_final,
        budget=0,
        draw=0,
        rows=query_rows,
    )
    target_units = _natural_position_units(dataset, "target", query_only=True)
    target_cities = sorted({str(dataset.city_ids[scene]) for scene, _, _ in target_units})
    budgets = [int(value) for value in formal_config["localization"]["label_budgets"]]
    for city in target_cities:
        city_queries = [unit for unit in target_units if str(dataset.city_ids[unit[0]]) == city]
        for draw, ordered_support in support_draws[city].items():
            for budget in budgets:
                selected = ordered_support[:budget]
                if len(selected) < budget:
                    if adapter["profile"] == "formal-paper-dose":
                        raise RuntimeError(f"target city {city} lacks {budget} unique support positions")
                    continue
                if budget:
                    support_rep, support_position, _ = _represent(model, dataset, selected, normalizer)
                    head = adapt_position_head(source_head, support_rep, support_position, head_config)
                else:
                    head = source_head
                _append_evaluation(
                    model,
                    head,
                    model_name,
                    model_config,
                    dataset,
                    normalizer,
                    city_queries,
                    budget=budget,
                    draw=draw,
                    rows=query_rows,
                )
    grouped = {}
    for row in query_rows:
        key = (row["model_name"], row["split_role"], row["city_id"], row["budget"], row["draw"])
        grouped.setdefault(key, []).append(float(row["localization_error_m"]))
    for key, values in sorted(grouped.items()):
        model_key, role, city, budget, draw = key
        metric_rows.append(
            {
                "model_name": model_key,
                "paper_label": model_config["paper_label"],
                "implementation_status": model_config["implementation_status"],
                "split_role": role,
                "city_id": city,
                "budget": budget,
                "draw": draw,
                "query_count": len(values),
                "median_error_m": float(np.median(values)),
                "p90_error_m": float(np.quantile(values, 0.9)),
            }
        )
    return metric_rows, query_rows, {
        "schema_version": "csi-pairs-v6-representation-probe-record-v1",
        "probe_train_role": "source_probe_train",
        "probe_selection_role": "source_probe_selection",
        "target_support_role": "support_pool",
        "target_evaluation_role": "query",
        "source_probe_selection_median_error_m": float(np.median(selection_error)),
        "head_steps": int(adapter["probe"]["head_steps"]),
        "label_draws": int(adapter["probe"]["label_draws"]),
        "target_normalization_statistics_used": False,
    }


def _append_evaluation(model, head, model_name, model_config, dataset, normalizer, units, *, budget, draw, rows):
    if not units:
        return
    representations, positions, selected_units = _represent(model, dataset, units, normalizer)
    means, variances, uncertainty = predict_position_distribution(head, representations)
    for index, (scene, world, position) in enumerate(selected_units):
        rows.append(
            {
                "model_name": model_name,
                "paper_label": model_config["paper_label"],
                "implementation_status": model_config["implementation_status"],
                "split_role": str(dataset.scene_roles[scene]),
                "city_id": str(dataset.city_ids[scene]),
                "independent_unit_id": dataset.independent_unit_id(scene),
                "bank_id": str(dataset.bank_ids[scene]),
                "position_id": str(dataset.position_ids[scene, position]),
                "world": int(world),
                "budget": int(budget),
                "draw": int(draw),
                "localization_error_m": float(np.linalg.norm(means[index] - positions[index])),
                "predicted_x_m": float(means[index, 0]),
                "predicted_y_m": float(means[index, 1]),
                "variance_x_m2": float(variances[index, 0]),
                "variance_y_m2": float(variances[index, 1]),
                "uncertainty": float(uncertainty[index]),
            }
        )


def _represent(model, dataset, units, normalizer, batch_size=256):
    device = next(model.parameters()).device
    model.eval()
    values = []
    with torch.no_grad():
        for start in range(0, len(units), batch_size):
            batch_units = units[start : start + batch_size]
            batch = _make_batch(dataset, batch_units, normalizer, device)
            values.append(model.encode(batch).detach().cpu().numpy())
    representations = np.concatenate(values, axis=0)
    positions = np.asarray([dataset.positions[scene, position] for scene, _, position in units], dtype=np.float32)
    return representations, positions, units


def _mean_pretraining_loss(model, dataset, units, normalizer, device, model_config):
    model.eval()
    values = []
    batch_size = int(model_config["batch_size"])
    with torch.no_grad():
        for start in range(0, len(units), batch_size):
            batch = _make_batch(dataset, units[start : start + batch_size], normalizer, device)
            loss = model.pretraining_loss(batch, float(model_config["mask_fraction"]))
            values.append(float(loss.detach().cpu()))
    return float(np.mean(values))


def _fit_normalizer(dataset, scenes):
    csi = dataset.csi_clean[np.asarray(scenes, dtype=np.int64)]
    maps = dataset.maps[np.asarray(scenes, dtype=np.int64)]
    positions = dataset.positions[np.asarray(scenes, dtype=np.int64)]
    radio = dataset.radio_config[np.asarray(scenes, dtype=np.int64)]
    bs_pose = dataset.bs_pose[np.asarray(scenes, dtype=np.int64)]
    return {
        "csi_mean": np.mean(csi, axis=(0, 1, 2)),
        "csi_std": np.maximum(np.std(csi, axis=(0, 1, 2)), 1e-6),
        "map_mean": np.mean(maps, axis=(0, 1, 3, 4)),
        "map_std": np.maximum(np.std(maps, axis=(0, 1, 3, 4)), 1e-6),
        "position_mean": np.mean(positions, axis=(0, 1)),
        "position_std": np.maximum(np.std(positions, axis=(0, 1)), 1e-6),
        "radio_mean": np.mean(radio, axis=0),
        "radio_std": np.maximum(np.std(radio, axis=0), 1e-6),
        "bs_mean": np.mean(bs_pose, axis=0),
        "bs_std": np.maximum(np.std(bs_pose, axis=0), 1e-6),
    }


def _make_batch(dataset, units, normalizer, device):
    csi = np.asarray([dataset.csi_clean[scene, world, position] for scene, world, position in units])
    maps = np.asarray([dataset.maps[scene, world] for scene, world, _ in units])
    radio = np.asarray([dataset.radio_config[scene] for scene, _, _ in units])
    bs_pose = np.asarray([dataset.bs_pose[scene] for scene, _, _ in units])
    positions = np.asarray([dataset.positions[scene, position] for scene, _, position in units])
    csi = (csi - normalizer["csi_mean"]) / normalizer["csi_std"]
    maps = (maps - normalizer["map_mean"][None, :, None, None]) / normalizer["map_std"][None, :, None, None]
    radio = (radio - normalizer["radio_mean"]) / normalizer["radio_std"]
    bs_pose = (bs_pose - normalizer["bs_mean"]) / normalizer["bs_std"]
    positions = (positions - normalizer["position_mean"]) / normalizer["position_std"]
    return BaselineBatch(
        csi=torch.as_tensor(csi, dtype=torch.float32, device=device),
        maps=torch.as_tensor(maps, dtype=torch.float32, device=device),
        radio=torch.as_tensor(radio, dtype=torch.float32, device=device),
        bs_pose=torch.as_tensor(bs_pose, dtype=torch.float32, device=device),
        position=torch.as_tensor(positions, dtype=torch.float32, device=device),
    )


def _world_position_units(dataset, role):
    return [
        (int(scene), world, position)
        for scene in dataset.indices_for_role(role)
        for world in range(dataset.world_count)
        for position in range(dataset.position_count)
    ]


def _natural_position_units(dataset, role, *, query_only):
    output = []
    for scene_value in dataset.indices_for_role(role):
        scene = int(scene_value)
        world = int(dataset.natural_world_index[scene])
        for position in range(dataset.position_count):
            if query_only and str(dataset.position_roles[scene, position]) != "query":
                continue
            output.append((scene, world, position))
    return output


def _target_support_draws(config, adapter, dataset):
    support_by_city = {}
    for scene_value in dataset.indices_for_role("target"):
        scene = int(scene_value)
        city = str(dataset.city_ids[scene])
        world = int(dataset.natural_world_index[scene])
        for position in np.flatnonzero(dataset.position_roles[scene] == "support_pool"):
            key = str(dataset.position_ids[scene, position])
            support_by_city.setdefault(city, {})
            if key in support_by_city[city]:
                previous = support_by_city[city][key]
                if not np.array_equal(dataset.positions[previous[0], previous[2]], dataset.positions[scene, position]):
                    raise RuntimeError("one target position_id maps to different coordinates within a city")
                continue
            support_by_city[city][key] = (scene, world, int(position))
    output = {}
    for city, keyed in support_by_city.items():
        ordered_keys = sorted(keyed)
        output[city] = {}
        for draw in range(int(adapter["probe"]["label_draws"])):
            seed = int(adapter["seed"]) + draw + int.from_bytes(city.encode("utf-8"), "little") % 1000003
            order = np.random.default_rng(seed).permutation(len(ordered_keys))
            output[city][draw] = [keyed[ordered_keys[int(index)]] for index in order]
    return output


def _positive_integer(value, name):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _positive_number(value, name):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not np.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")


def _slug(value):
    return str(value).lower().replace("+", "plus").replace("-", "_")
