from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .formal_config import load_formal_config, resolve_dataset_path
from .formal_dataset import FormalDataset, SOURCE_ROLES
from .formal_fixture import write_nonscientific_fixture
from .formal_io import artifact_manifest, read_strict_json, write_json


DEFAULT_SHUFFLED_PAIR_MANIFEST = str(
    Path(__file__).resolve().parent
    / "external_adapters"
    / "shuffled_pair_control_v3.json"
)
DEFAULT_RETENTION_MANIFEST = str(
    Path(__file__).resolve().parent / "external_adapters" / "retention_control_v3.json"
)
DEFAULT_SCENE_ID_MANIFEST = "builtin:sigmap-scene-id-v1"
DEFAULT_RESOURCE_CONTROL_MANIFEST = str(
    Path(__file__).resolve().parent
    / "external_adapters"
    / "resource_controls_v3.json"
)


COMMAND_OUTPUT_PATHS = {
    "inspect-data": "data_contract.json",
    "verify-data": "data_verification",
    "qualify": "qualification",
    "run-wrong-map": "wrong_map",
    "run-factorial": "factorial",
    "run-evaluation": "evaluation",
    "run-risk": "risk",
    "run-path": "path",
    "run-external-baselines": "external_baselines",
    "run-representation-baselines": "representation_baselines",
    "run-resource-controls": "controls",
    "run-scene-id-audit": "scene_id",
    "run-external-validity": "external_validity",
    "run-literature-resources": "literature_resources",
    "run-rt-calibration": "qualification/rt_calibration",
    "run-shuffled-pair-control": "controls/shuffled_pair",
    "run-retention-audit": "evaluation/retention",
    "assemble-claims": "claims",
}
FILE_OUTPUT_COMMANDS = frozenset({"inspect-data"})
SELF_RESERVING_DIRECTORY_COMMANDS = frozenset({"run-representation-baselines"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CSI-PAIRS V2.1 V6 evidence-gated formal experiment runner"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    fixture = subparsers.add_parser("make-fixture", help="create a permanently non-scientific code fixture")
    fixture.add_argument("--output", required=True)
    fixture.add_argument("--seed", type=int, default=20270805)
    fixture.add_argument(
        "--source-banks-per-role",
        type=int,
        default=1,
        help="non-scientific fixture banks per source role; use 2 to exercise cross-source-city controls",
    )
    resources = subparsers.add_parser("verify-waibu-resources")
    resources.add_argument("--registry", required=True)
    resources.add_argument("--waibu-root", required=True)
    resources.add_argument("--output", required=True)
    sionna_export = subparsers.add_parser("export-sionna-scenes")
    sionna_export.add_argument("--dataset", required=True)
    sionna_export.add_argument("--output", required=True)
    sionna_export.add_argument("--license-id", required=True)
    sionna_export.add_argument("--carrier-frequency-hz", type=float, required=True)
    sionna_export.add_argument("--subcarrier-spacing-hz", type=float, required=True)
    sionna_export.add_argument("--receiver-z-m", type=float, default=1.5)
    sionna_export.add_argument("--max-depth", type=int, default=5)
    sionna_export.add_argument("--refraction", action="store_true")

    for command in (
        "inspect-data",
        "verify-data",
        "qualify",
        "run-wrong-map",
        "run-factorial",
        "run-evaluation",
        "run-risk",
        "run-path",
        "run-external-baselines",
        "run-representation-baselines",
        "run-resource-controls",
        "run-scene-id-audit",
        "run-external-validity",
        "run-literature-resources",
        "run-rt-calibration",
        "run-shuffled-pair-control",
        "run-retention-audit",
        "assemble-claims",
        "all",
    ):
        child = subparsers.add_parser(command)
        child.add_argument("--config", required=True)
        child.add_argument("--output", required=True)
        child.add_argument("--dataset", help="optional dataset override; does not mutate the config")
        if command in {"run-factorial", "all"}:
            child.add_argument(
                "--allow-nonscientific-fixture",
                action="store_true",
                help="exercise downstream code on a fixture; outputs remain scientific_use=FORBIDDEN",
            )
        if command == "run-factorial":
            child.add_argument("--qualification-gate", help="defaults to OUTPUT/qualification/gate.json")
        if command == "qualify":
            child.add_argument("--data-verification-gate", help="defaults to OUTPUT/data_verification/gate.json")
        if command == "verify-data":
            child.add_argument("--verifier-manifest", required=True)
        if command == "all":
            child.add_argument("--verifier-manifest", required=True)
            child.add_argument(
                "--risk-feature-manifest",
                help="deprecated; all replays risk features in first-party code",
            )
            child.add_argument("--adapter-manifest", required=True)
            child.add_argument(
                "--control-manifest", default=DEFAULT_RESOURCE_CONTROL_MANIFEST
            )
            child.add_argument(
                "--scene-id-manifest", default=DEFAULT_SCENE_ID_MANIFEST
            )
            child.add_argument("--external-validity-manifest", required=True)
            child.add_argument("--literature-resource-manifest", required=True)
            child.add_argument("--rt-calibration-manifest", required=True)
            child.add_argument(
                "--shuffled-pair-manifest", default=DEFAULT_SHUFFLED_PAIR_MANIFEST
            )
            child.add_argument(
                "--retention-manifest", default=DEFAULT_RETENTION_MANIFEST
            )
            child.add_argument(
                "--representation-baseline-config",
                default=str(Path(__file__).resolve().parent / "configs" / "representation_baselines_v1.json"),
            )
        if command == "run-wrong-map":
            child.add_argument("--qualification-gate", help="defaults to OUTPUT/qualification/gate.json")
        if command == "run-evaluation":
            child.add_argument("--qualification-gate", help="defaults to OUTPUT/qualification/gate.json")
            child.add_argument("--factorial-gate", help="defaults to OUTPUT/factorial/gate.json")
        if command == "run-risk":
            child.add_argument(
                "--risk-features",
                help="deprecated; risk features are replayed first-party from OUTPUT artifacts",
            )
        if command == "run-external-baselines":
            child.add_argument("--adapter-manifest", required=True)
        if command == "run-representation-baselines":
            child.add_argument("--representation-baseline-config", required=True)
        if command == "run-resource-controls":
            child.add_argument(
                "--control-manifest", default=DEFAULT_RESOURCE_CONTROL_MANIFEST
            )
        if command == "run-scene-id-audit":
            child.add_argument(
                "--scene-id-manifest", default=DEFAULT_SCENE_ID_MANIFEST
            )
        if command == "run-external-validity":
            child.add_argument("--external-validity-manifest", required=True)
        if command == "run-literature-resources":
            child.add_argument("--literature-resource-manifest", required=True)
        if command == "run-rt-calibration":
            child.add_argument("--rt-calibration-manifest", required=True)
        if command == "run-shuffled-pair-control":
            child.add_argument(
                "--claim-control-manifest", default=DEFAULT_SHUFFLED_PAIR_MANIFEST
            )
        if command == "run-retention-audit":
            child.add_argument(
                "--claim-control-manifest", default=DEFAULT_RETENTION_MANIFEST
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_lock: Path | None = None
    try:
        if args.command == "make-fixture":
            source_banks_per_role = int(args.source_banks_per_role)
            scene_count = len(SOURCE_ROLES) * source_banks_per_role + 4
            path = write_nonscientific_fixture(
                args.output,
                seed=int(args.seed),
                scene_count=scene_count,
                source_banks_per_role=source_banks_per_role,
            )
            print(json.dumps({"status": "success", "fixture": str(path.resolve()), "scientific_use": "FORBIDDEN"}))
            return 0
        if args.command == "verify-waibu-resources":
            from .formal_resources import verify_waibu_resources

            output = Path(args.output).resolve()
            output_lock = _acquire_output_lock(output)
            result = verify_waibu_resources(args.registry, args.waibu_root, output)
            print(json.dumps({"status": result["status"], "output": str(output)}, sort_keys=True))
            return 0
        if args.command == "export-sionna-scenes":
            from .sionna_scene_export import export_sionna_scenes

            output = Path(args.output).resolve()
            output_lock = _acquire_output_lock(_sionna_export_lock_root(output))
            manifest = export_sionna_scenes(
                args.dataset,
                output,
                license_id=args.license_id,
                carrier_frequency_hz=args.carrier_frequency_hz,
                subcarrier_spacing_hz=args.subcarrier_spacing_hz,
                receiver_z_m=args.receiver_z_m,
                max_depth=args.max_depth,
                refraction=bool(args.refraction),
            )
            print(json.dumps({"status": "PASS", "manifest": str(manifest)}, sort_keys=True))
            return 0
        config = load_formal_config(args.config)
        dataset_path = Path(args.dataset).resolve() if args.dataset else resolve_dataset_path(config)
        dataset = FormalDataset.load(
            dataset_path,
            require_clean_csi=bool(config["data"]["require_clean_csi"]),
        )
        dataset.validate(
            require_clean_csi=bool(config["data"]["require_clean_csi"]),
            minimum_repeats=int(config["data"]["minimum_repeats"]),
            minimum_target_cities=int(config["data"]["minimum_target_cities"]),
            minimum_source_cities=int(config["data"]["minimum_source_cities"]),
            minimum_banks_per_target_city=int(config["data"]["minimum_banks_per_target_city"]),
            minimum_banks_per_source_role=int(config["data"]["minimum_banks_per_source_role"]),
        )
        output = Path(args.output).resolve()
        output_lock = _acquire_output_lock(output)
        if args.command == "all":
            _reserve_full_run_output(output)
        else:
            _reserve_command_output(args.command, output)
            output.mkdir(parents=True, exist_ok=True)
        if args.command == "inspect-data":
            target = output / "data_contract.json"
            report = dataset.contract_report()
            write_json(target, report)
            result = report
        elif args.command == "qualify":
            from .formal_qualification import run_formal_qualification

            verification_path = Path(args.data_verification_gate) if args.data_verification_gate else output / "data_verification" / "gate.json"
            result = run_formal_qualification(
                config,
                dataset,
                output,
                read_strict_json(verification_path),
                data_verification_gate_path=verification_path,
            )
        elif args.command == "verify-data":
            from .formal_data_verification import run_data_verification

            result = run_data_verification(config, dataset, args.verifier_manifest, output)
        elif args.command == "run-wrong-map":
            from .formal_wrong_map import run_formal_wrong_map

            gate_path = Path(args.qualification_gate) if args.qualification_gate else output / "qualification" / "gate.json"
            result = run_formal_wrong_map(config, dataset, output, read_strict_json(gate_path))
        elif args.command == "run-factorial":
            gate_path = Path(args.qualification_gate) if args.qualification_gate else output / "qualification" / "gate.json"
            gate = read_strict_json(gate_path)
            from .formal_factorial import run_formal_factorial

            result = run_formal_factorial(
                config,
                dataset,
                output,
                gate,
                allow_nonscientific_fixture=bool(args.allow_nonscientific_fixture),
            )
        elif args.command == "run-evaluation":
            qualification_path = Path(args.qualification_gate) if args.qualification_gate else output / "qualification" / "gate.json"
            factorial_path = Path(args.factorial_gate) if args.factorial_gate else output / "factorial" / "gate.json"
            from .formal_evaluation import run_formal_evaluation

            result = run_formal_evaluation(
                config,
                dataset,
                output,
                read_strict_json(qualification_path),
                read_strict_json(factorial_path),
            )
        elif args.command == "run-risk":
            from .formal_risk import run_risk_contract

            result = run_risk_contract(config, dataset, output)
        elif args.command == "run-path":
            from .formal_path import run_path_audit

            result = run_path_audit(config, dataset, output / "factorial", output)
        elif args.command == "run-external-baselines":
            from .formal_external import run_external_baselines

            result = run_external_baselines(config, dataset, args.adapter_manifest, output)
        elif args.command == "run-representation-baselines":
            from .formal_representation_baselines import run_representation_baselines

            result = run_representation_baselines(
                config, dataset, args.representation_baseline_config, output
            )
        elif args.command == "run-resource-controls":
            from .formal_controls import run_resource_controls

            result = run_resource_controls(config, dataset, args.control_manifest, output)
        elif args.command == "run-scene-id-audit":
            from .formal_scene_id import run_scene_id_audit

            result = run_scene_id_audit(config, dataset, args.scene_id_manifest, output)
        elif args.command == "run-external-validity":
            from .formal_external_validity import run_external_validity

            result = run_external_validity(
                config, dataset, args.external_validity_manifest, output
            )
        elif args.command == "run-literature-resources":
            from .formal_literature import run_literature_resource_gate

            result = run_literature_resource_gate(
                config, dataset, args.literature_resource_manifest, output
            )
        elif args.command == "run-rt-calibration":
            from .formal_rt_calibration import run_rt_calibration_gate

            result = run_rt_calibration_gate(
                config, dataset, args.rt_calibration_manifest, output
            )
        elif args.command == "run-shuffled-pair-control":
            from .formal_claim_controls import run_shuffled_pair_control

            result = run_shuffled_pair_control(
                config, dataset, args.claim_control_manifest, output
            )
        elif args.command == "run-retention-audit":
            from .formal_claim_controls import run_retention_audit

            result = run_retention_audit(
                config, dataset, args.claim_control_manifest, output
            )
        elif args.command == "assemble-claims":
            from .formal_claims import assemble_claim_evidence

            result = assemble_claim_evidence(config, dataset, output)
        else:
            from .formal_resources import verify_waibu_resources

            verify_waibu_resources(
                Path(__file__).resolve().parent / "configs" / "waibu_resources_v1.json",
                Path(__file__).resolve().parents[1] / "waibu",
                output,
            )
            from .formal_data_verification import run_data_verification

            verification = run_data_verification(config, dataset, args.verifier_manifest, output)
            from .formal_qualification import run_formal_qualification

            qualification = run_formal_qualification(
                config,
                dataset,
                output,
                verification,
                data_verification_gate_path=output / "data_verification" / "gate.json",
            )
            from .formal_wrong_map import run_formal_wrong_map

            run_formal_wrong_map(config, dataset, output, qualification)
            from .formal_factorial import run_formal_factorial

            result = run_formal_factorial(
                config,
                dataset,
                output,
                qualification,
                allow_nonscientific_fixture=bool(args.allow_nonscientific_fixture),
            )
            from .formal_evaluation import run_formal_evaluation

            run_formal_evaluation(config, dataset, output, qualification, result)
            from .formal_risk import run_risk_contract

            run_risk_contract(config, dataset, output)
            from .formal_path import run_path_audit

            run_path_audit(config, dataset, output / "factorial", output)
            from .formal_external import run_external_baselines

            run_external_baselines(config, dataset, args.adapter_manifest, output)
            from .formal_representation_baselines import run_representation_baselines

            run_representation_baselines(
                config, dataset, args.representation_baseline_config, output
            )
            from .formal_controls import run_resource_controls

            run_resource_controls(config, dataset, args.control_manifest, output)
            from .formal_scene_id import run_scene_id_audit

            run_scene_id_audit(config, dataset, args.scene_id_manifest, output)
            from .formal_external_validity import run_external_validity

            run_external_validity(
                config, dataset, args.external_validity_manifest, output
            )
            from .formal_literature import run_literature_resource_gate

            run_literature_resource_gate(
                config, dataset, args.literature_resource_manifest, output
            )
            from .formal_rt_calibration import run_rt_calibration_gate

            run_rt_calibration_gate(
                config, dataset, args.rt_calibration_manifest, output
            )
            from .formal_claim_controls import (
                run_retention_audit,
                run_shuffled_pair_control,
            )

            run_shuffled_pair_control(
                config, dataset, args.shuffled_pair_manifest, output
            )
            run_retention_audit(config, dataset, args.retention_manifest, output)
            from .formal_claims import assemble_claim_evidence

            result = assemble_claim_evidence(config, dataset, output)
        from .formal_evidence import evidence_context

        root_scientific_use = "FORBIDDEN" if dataset.is_fixture else "CANDIDATE_NOT_CLAIM"
        root_evidence = evidence_context(config, dataset, root_scientific_use)
        write_json(
            output / "manifest.json",
            {
                "schema_version": "csi-pairs-formal-root-manifest-v2.1-v6",
                **root_evidence,
                "files": artifact_manifest(output, evidence=root_evidence),
            },
        )
        print(json.dumps({"status": result.get("status", "success"), "output": str(output.resolve())}, sort_keys=True))
        return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        if output_lock is not None:
            output_lock.unlink(missing_ok=True)


def _acquire_output_lock(output_root: Path) -> Path:
    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output_root.parent / f".{output_root.name}.csi-pairs-operation.lock"
    try:
        lock_path.touch(exist_ok=False)
    except FileExistsError as error:
        raise FileExistsError(
            f"refusing concurrent V2 output use; operation lock exists: {lock_path}"
        ) from error
    return lock_path


def _sionna_export_lock_root(output: Path) -> Path:
    output = output.resolve()
    return output.parent if output.name == "inputs" else output


def _reserve_command_output(command: str, output_root: Path) -> Path | None:
    relative_path = COMMAND_OUTPUT_PATHS.get(command)
    if relative_path is None:
        return None
    target = output_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if command in SELF_RESERVING_DIRECTORY_COMMANDS:
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"refusing to overwrite V2 output: {target}")
        return target
    try:
        if command in FILE_OUTPUT_COMMANDS:
            target.touch(exist_ok=False)
        else:
            target.mkdir(exist_ok=False)
    except FileExistsError as error:
        raise FileExistsError(f"refusing to overwrite V2 output: {target}") from error
    return target


def _reserve_full_run_output(output_root: Path) -> None:
    try:
        output_root.mkdir(parents=True, exist_ok=False)
        return
    except FileExistsError:
        pass
    entries = list(output_root.iterdir()) if output_root.is_dir() else []
    if (
        len(entries) != 1
        or entries[0].name != "inputs"
        or not entries[0].is_dir()
        or entries[0].is_symlink()
    ):
        raise FileExistsError(
            "refusing to reuse V2 full-run output directory except for a single "
            f"pre-staged inputs directory: {output_root}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
