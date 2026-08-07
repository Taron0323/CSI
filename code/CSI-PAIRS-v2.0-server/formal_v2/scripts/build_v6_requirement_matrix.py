from __future__ import annotations

import argparse
import csv
import hashlib
import os
from pathlib import Path
import re
import tempfile


SOURCE_SPECS = {
    "reader": {
        "sha256": "e6d19a65325b688b75472d9814dc9bae26b1d36e08db68cefedc1918696a635b",
        "prefix": "ZR",
    },
    "plan": {
        "sha256": "75f7e4e4ce82834216f9a8bf76fcd0785377c6de38aae62cabf4d1e88170dd4a",
        "prefix": "CP",
    },
}

NORMATIVE_TERMS = re.compile(
    "|".join(
        (
            "必须", "只能", "不得", "禁止", "至少", "唯一", "冻结", "等权",
            "非劣", "等效", "主指标", "资格门", "通过", "失败", "停止", "信息预算",
            "不能", "不允许", "应当", "需要", "固定", "共享", "排除", "不参与",
            "只用", "定义", "默认", "阈值", "条件", "分别", "保持", "严格",
        )
    )
)
FORMULA_MARKERS = re.compile(
    r"(?:\\begin\{|\\operatorname|\\mathbb|\\Delta|\\epsilon|\\tau|<=|>=|≤|≥|:=|=)"
)
TOP_SECTION = re.compile(r"^##\s+(\d+)(?:\.|\s)")
HEADING = re.compile(r"^#{2,6}\s+")
SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？；;])\s*")


SECTION_MAP = {
    0: {
        "expected": "Claims remain within the registered relative, non-causal evidence boundary.",
        "entry": "assemble-claims",
        "code": (("formal_v2/formal_claims.py", "def assemble_claim_evidence"),),
        "config": (("artifacts/v2_0_claim_evidence_contract.json", '"claims"'),),
        "tests": (("formal_v2/tests/test_formal_v2.py", "def test_gate_and_claim_identifiers_are_fixed"),),
        "paper": "paper_v2/main.tex",
    },
    1: {
        "expected": "The six-condition wrong-map and scene-ID audits remain paired and fail closed.",
        "entry": "run-wrong-map; run-external-baselines; run-scene-id-audit",
        "code": (
            ("formal_v2/formal_wrong_map.py", "def run_formal_wrong_map"),
            ("formal_v2/formal_external.py", "def run_external_baselines"),
            ("formal_v2/formal_scene_id.py", "def run_scene_id_audit"),
        ),
        "config": (("formal_v2/external_adapters/all_map_adapters_v1.json", '"adapters"'),),
        "tests": (("formal_v2/tests/test_evidence_integrity.py", "def test_six_equal_conditions_cannot_pass_c1"),),
        "paper": "paper_v2/main.tex",
    },
    2: {
        "expected": "World banks, typed edits, positions, roles, support/query exclusion, and provenance satisfy the frozen data contract.",
        "entry": "inspect-data; verify-data",
        "code": (("formal_v2/formal_dataset.py", "class FormalDataset"),),
        "config": (("formal_v2/configs/formal_v2.json", '"data"'),),
        "tests": (("formal_v2/tests/test_formal_v2.py", "class DatasetTests"),),
        "paper": "paper_v2/main.tex",
    },
    3: {
        "expected": "CSI-only frozen targets, physical-only primary routes, independent teacher strata, masks, and pair-consistent gauge are enforced.",
        "entry": "qualify",
        "code": (
            ("formal_v2/formal_teacher.py", "def train_teacher_bundle"),
            ("formal_v2/formal_routing.py", "def route_dataset"),
            ("formal_v2/formal_qualification.py", "def run_formal_qualification"),
        ),
        "config": (("formal_v2/configs/formal_v2.json", '"qualification"'),),
        "tests": (("formal_v2/tests/test_data_protocol_integrity.py", "class QualificationCoverageTests"),),
        "paper": "paper_v2/main.tex",
    },
    4: {
        "expected": "The shared F/P architecture, endpoint, Alignment, Response, dead zones, dose, and retained-module rules match V6.",
        "entry": "run-factorial",
        "code": (
            ("formal_v2/formal_model.py", "class CSIPairsFormalModel"),
            ("formal_v2/formal_factorial.py", "def run_formal_factorial"),
        ),
        "config": (("formal_v2/configs/formal_v2.json", '"factorial"'),),
        "tests": (("formal_v2/tests/test_factorial_integrity.py", "class ArmExecutionMutationTests"),),
        "paper": "paper_v2/main.tex",
    },
    5: {
        "expected": "CGS, native metrics, q_comp, p_fail, support, and calibration remain separate and use registered units.",
        "entry": "run-evaluation; run-risk",
        "code": (
            ("formal_v2/formal_evaluation.py", "def run_formal_evaluation"),
            ("formal_v2/formal_risk.py", "def run_risk_contract"),
        ),
        "config": (("formal_v2/configs/formal_v2.json", '"evaluation"'),),
        "tests": (("formal_v2/tests/test_risk_path_evaluation_integrity.py", "class RiskPathEvaluationIntegrityTests"),),
        "paper": "paper_v2/main.tex",
    },
    6: {
        "expected": "Theory states only the registered identification and supervision limits and does not pre-claim synergy.",
        "entry": "paper protocol and claim gate",
        "code": (("formal_v2/formal_claims.py", "CLAIM_DEPENDENCIES"),),
        "config": (("artifacts/v2_0_claim_evidence_contract.json", '"rule"'),),
        "tests": (("formal_v2/tests/test_formal_v2.py", "def test_claim_semantics_recheck_g0_c2_c11_and_g8_evidence"),),
        "paper": "paper_v2/main.tex",
    },
    7: {
        "expected": "The strict 2x2 factorial changes only Alignment/Response switches and earns all synchronized G4 subgates.",
        "entry": "run-factorial; run-evaluation; run-resource-controls",
        "code": (
            ("formal_v2/formal_config.py", "ARMS ="),
            ("formal_v2/formal_statistics.py", "def hierarchical_factorial_interval"),
            ("formal_v2/formal_controls.py", "def run_resource_controls"),
        ),
        "config": (("formal_v2/configs/formal_v2.json", '"arms"'),),
        "tests": (("formal_v2/tests/test_factorial_integrity.py", "class FactorialStatisticsMutationTests"),),
        "paper": "paper_v2/main.tex",
    },
    8: {
        "expected": "RQ1-RQ5 execute only through their registered estimands and untouched evaluation units.",
        "entry": "prepare-full-run; all",
        "code": (("formal_v2/formal_cli.py", "def _run_authorized_full_chain"),),
        "config": (("formal_v2/configs/formal_v2.json", '"schema_version"'),),
        "tests": (("formal_v2/tests/test_run_approval.py", "def test_authorized_chain_order_and_failure_short_circuit"),),
        "paper": "paper_v2/main.tex",
    },
    9: {
        "expected": "Path incidence, no-op tolerance, matched strata, and bank-level inference use authenticated retraces.",
        "entry": "run-path",
        "code": (("formal_v2/formal_path.py", "def run_path_audit"),),
        "config": (("formal_v2/configs/formal_v2.json", '"path"'),),
        "tests": (("formal_v2/tests/test_risk_path_evaluation_integrity.py", "def test_path_gate_cannot_pass_without_provenance"),),
        "paper": "paper_v2/main.tex",
    },
    10: {
        "expected": "Shortcut, shuffled-pair, leakage, and retention controls are independently trained and hash bound.",
        "entry": "run-shuffled-pair-control; run-retention-audit",
        "code": (("formal_v2/formal_claim_controls.py", "def run_shuffled_pair_control"),),
        "config": (("formal_v2/external_adapters/shuffled_pair_control_v3.json", '"schema_version"'),),
        "tests": (("formal_v2/tests/test_evidence_integrity.py", "def test_shuffled_control_cannot_reuse_matched_checkpoint"),),
        "paper": "paper_v2/main.tex",
    },
    11: {
        "expected": "Internal and external baselines retain accurate implementation labels, common units, and resource accounting.",
        "entry": "run-external-baselines; run-representation-baselines",
        "code": (
            ("formal_v2/formal_external.py", "def run_external_baselines"),
            ("formal_v2/formal_representation_baselines.py", "def run_representation_baselines"),
        ),
        "config": (("formal_v2/external_adapters/all_map_adapters_v1.json", '"implementation_status"'),),
        "tests": (("formal_v2/tests/test_evidence_integrity.py", "def test_fewer_than_two_faithful_c1_models_is_blocked_not_supported"),),
        "paper": "paper_v2/main.tex",
    },
    12: {
        "expected": "City, foundation, bank, seed, and draw hierarchy plus Holm and interval decisions use the frozen independent units.",
        "entry": "run-evaluation; run-risk; run-path",
        "code": (("formal_v2/formal_statistics.py", "def exact_factorial_utilities"),),
        "config": (("formal_v2/configs/formal_v2.json", '"bootstrap_resamples"'),),
        "tests": (("formal_v2/tests/test_formal_v2.py", "class StatisticsTests"),),
        "paper": "paper_v2/main.tex",
    },
    13: {
        "expected": "Every main result cell must be populated only by authenticated non-fixture rows with denominators and intervals.",
        "entry": "paper build after formal evidence",
        "code": (("paper_v2/main.tex", r"\planned"),),
        "config": (("artifacts/v2_0_claim_evidence_contract.json", '"current_scientific_status"'),),
        "tests": (("paper_v2/build_reproducible.sh", "latexmk"),),
        "paper": "paper_v2/main.tex",
    },
    14: {
        "expected": "C1-C13 promote only through complete authenticated dependencies and otherwise remain BLOCKED.",
        "entry": "assemble-claims",
        "code": (("formal_v2/formal_claims.py", "CLAIM_DEPENDENCIES"),),
        "config": (("artifacts/v2_0_claim_evidence_contract.json", '"claims"'),),
        "tests": (("formal_v2/tests/test_formal_v2.py", "def test_gate_and_claim_identifiers_are_fixed"),),
        "paper": "paper_v2/main.tex",
    },
    15: {
        "expected": "G0-G8 run in the frozen order, stop on failure, and preserve PASS/FAIL/BLOCKED/NOT_ASSESSED distinctions.",
        "entry": "prepare-full-run; create-run-approval; all",
        "code": (
            ("formal_v2/formal_cli.py", "def _prepare_full_run"),
            ("formal_v2/formal_run_approval.py", "def authenticate_prepared_run"),
        ),
        "config": (("formal_v2/configs/formal_v2.json", '"schema_version"'),),
        "tests": (("formal_v2/tests/test_run_approval.py", "def test_authorized_chain_order_and_failure_short_circuit"),),
        "paper": "paper_v2/main.tex",
    },
}


FIELDNAMES = (
    "requirement_id",
    "source_document",
    "source_document_sha256",
    "source_line",
    "clause_index",
    "source_clause_sha256",
    "original_norm",
    "normative_signal",
    "section",
    "section_heading",
    "verifiable_expectation",
    "runtime_entry",
    "code_locations",
    "config_or_schema_locations",
    "regression_test_locations",
    "dynamic_evidence",
    "paper_location",
    "status",
    "blocking_type",
    "repair_or_boundary",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def locate(project_root: Path, items: tuple[tuple[str, str], ...]) -> str:
    locations = []
    for relative, anchor in items:
        path = project_root / relative
        lines = path.read_text(encoding="utf-8").splitlines()
        matches = [index for index, line in enumerate(lines, start=1) if anchor in line]
        if not matches:
            raise RuntimeError(f"traceability anchor not found: {relative}:{anchor}")
        locations.append(f"{relative}:{matches[0]}")
    return "; ".join(locations)


def clauses_for_line(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped or stripped in {"---", "```", "\\[", "\\]"}:
        return []
    if stripped.startswith("```"):
        return []
    if stripped.startswith("|"):
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        return [
            cell
            for cell in cells
            if cell and re.fullmatch(r"[-: ]+", cell) is None
        ]
    stripped = HEADING.sub("", stripped)
    stripped = re.sub(r"^(?:[-*+]\s+|\d+[.)]\s+)", "", stripped)
    return [part for part in SENTENCE_BOUNDARY.split(stripped) if part.strip()]


def normative_signal(clause: str, raw_line: str) -> str:
    terms = sorted(set(NORMATIVE_TERMS.findall(clause)))
    if terms:
        return "TERM:" + ",".join(terms)
    if FORMULA_MARKERS.search(clause):
        return "FORMULA_OR_CONDITION"
    if HEADING.match(raw_line.strip()):
        return "HEADING_INCLUDED_FOR_COMPLETENESS"
    return "CONTEXT_INCLUDED_FOR_COMPLETENESS"


def section_status(source_name: str, line_number: int, section: int) -> tuple[str, str, str]:
    if (source_name == "reader" and 328 <= line_number <= 330) or (
        source_name == "plan" and line_number == 287
    ):
        return (
            "CONFLICT",
            "AUTHOR_DECISION_REQUIRED",
            "Keep the frozen world-independent shared reference; the later Goal's source-derived transform changes the estimand and cannot be selected silently.",
        )
    if section == 13:
        return (
            "MISSING",
            "EXTERNAL_DATA_REQUIRED",
            "Formal result cells remain absent until authenticated non-fixture execution.",
        )
    if section in {1, 6, 8, 11, 14, 15}:
        return (
            "PARTIAL/PROXY",
            "EXTERNAL_DATA_REQUIRED",
            "A section-level executable contract is mapped; clause-level dynamic or external evidence remains incomplete.",
        )
    return (
        "PARTIAL/PROXY",
        "CODE_REQUIRED",
        "The current anchor is section-level and cannot establish atomic EXACT status; add a clause-specific implementation, configuration, regression, and dynamic-evidence mapping.",
    )


def build_rows(source_name: str, source: Path, project_root: Path, include_text: bool) -> list[dict[str, str]]:
    spec = SOURCE_SPECS[source_name]
    digest = sha256_file(source)
    if digest != spec["sha256"]:
        raise RuntimeError(
            f"{source_name} SHA-256 changed: expected {spec['sha256']}, observed {digest}"
        )
    rows = []
    section = None
    heading = ""
    for line_number, raw_line in enumerate(
        source.read_text(encoding="utf-8").splitlines(), start=1
    ):
        top = TOP_SECTION.match(raw_line)
        if top is not None:
            section = int(top.group(1))
        if section not in SECTION_MAP:
            continue
        if HEADING.match(raw_line.strip()):
            heading = HEADING.sub("", raw_line.strip())
        mapping = SECTION_MAP[section]
        for clause_index, clause in enumerate(clauses_for_line(raw_line), start=1):
            clause = clause.strip()
            status, blocker, repair = section_status(source_name, line_number, section)
            clause_digest = hashlib.sha256(clause.encode("utf-8")).hexdigest()
            rows.append(
                {
                    "requirement_id": f"{spec['prefix']}-L{line_number:04d}-C{clause_index:02d}",
                    "source_document": source_name,
                    "source_document_sha256": digest,
                    "source_line": str(line_number),
                    "clause_index": str(clause_index),
                    "source_clause_sha256": clause_digest,
                    "original_norm": clause if include_text else "[OMITTED_FROM_PUBLIC_REPOSITORY]",
                    "normative_signal": normative_signal(clause, raw_line),
                    "section": str(section),
                    "section_heading": (
                        heading if include_text else "[OMITTED_FROM_PUBLIC_REPOSITORY]"
                    ),
                    "verifiable_expectation": mapping["expected"],
                    "runtime_entry": mapping["entry"],
                    "code_locations": locate(project_root, mapping["code"]),
                    "config_or_schema_locations": locate(project_root, mapping["config"]),
                    "regression_test_locations": locate(project_root, mapping["tests"]),
                    "dynamic_evidence": "full unittest, CLI, schema, package, and clean-extraction validation record; non-fixture evidence remains separate",
                    "paper_location": mapping["paper"],
                    "status": status,
                    "blocking_type": blocker,
                    "repair_or_boundary": repair,
                }
            )
    return rows


def _stage_matrix(path: Path, rows: list[dict[str, str]]) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            descriptor = -1
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def write_matrix_pair(
    public_path: Path,
    public_rows: list[dict[str, str]],
    private_path: Path,
    private_rows: list[dict[str, str]],
) -> None:
    outputs = (public_path, private_path)
    if public_path.resolve(strict=False) == private_path.resolve(strict=False):
        raise ValueError("public and private requirement matrices must use different paths")
    for path in outputs:
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"refusing to overwrite requirement matrix: {path}")
    for parent in {path.parent for path in outputs}:
        parent.mkdir(parents=True, exist_ok=True)

    staged: list[tuple[Path, Path]] = []
    created: list[Path] = []
    try:
        staged = [
            (_stage_matrix(public_path, public_rows), public_path),
            (_stage_matrix(private_path, private_rows), private_path),
        ]
        for temporary_path, output_path in staged:
            os.link(temporary_path, output_path)
            created.append(output_path)
    except Exception:
        for output_path in reversed(created):
            output_path.unlink(missing_ok=True)
        raise
    finally:
        for temporary_path, _ in staged:
            temporary_path.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build privacy-safe public and private V6 atomic traceability matrices"
    )
    parser.add_argument("--reader", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--public-output", required=True)
    parser.add_argument("--private-output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(args.project_root).resolve()
    sources = {
        "reader": Path(args.reader).resolve(),
        "plan": Path(args.plan).resolve(),
    }
    public_rows = []
    private_rows = []
    for source_name, source in sources.items():
        public_rows.extend(build_rows(source_name, source, project_root, False))
        private_rows.extend(build_rows(source_name, source, project_root, True))
    if not public_rows or len(public_rows) != len(private_rows):
        raise RuntimeError("V6 requirement extraction produced an invalid row count")
    write_matrix_pair(
        Path(args.public_output),
        public_rows,
        Path(args.private_output),
        private_rows,
    )
    print(f"requirements={len(public_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
