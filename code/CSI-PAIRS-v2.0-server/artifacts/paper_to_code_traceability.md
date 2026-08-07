# Paper-to-code traceability

Date: 2026-08-08 (Asia/Shanghai)

Audited code: `4074e98fe3c1d1ddccee79672f312b9111185992`

## Atomic source ledger

The authoritative row-level index is
`artifacts/v6_atomic_requirement_matrix_2026-08-08.csv`. It contains 2,772 rows and binds each
row to the immutable source-document hash, source line, clause hash, executable entry, code,
configuration, regression anchor, evidence boundary, and paper location. Source prose is omitted
from the public repository; the private companion remains outside Git.

| Atomic status | Rows | Meaning |
|---|---:|---|
| `PARTIAL/PROXY` | 2,719 | A section-level implementation/test anchor exists, but the row does not meet the matrix's clause-specific `EXACT` standard or still lacks formal dynamic evidence. |
| `MISSING` | 38 | Authenticated non-fixture result cells do not exist. This is an external-data/execution boundary, not permission to use fixture values. |
| `CONFLICT` | 15 | The shared-reference gauge clauses require an author protocol decision. |

The matrix deliberately does not promote a clause to `EXACT` from a same-section function or test.
The 1,875 `CODE_REQUIRED` partial rows are therefore an atomic trace-granularity backlog. They are
not counted as closed scientific evidence and prevent `GOAL_COMPLETE`, even though the independent
P0/P1 runtime review found no remaining reproducible code defect at the audited commit.

## Decision-critical mappings

| Protocol surface | Runtime entry | Code and configuration | Regression/adversarial evidence | Paper location | Current state |
|---|---|---|---|---|---|
| Seven source roles and per-role city coverage | `inspect-data`, `verify-data` | `formal_v2/formal_dataset.py`; `formal_v2/configs/formal_v2.json` | `test_data_protocol_integrity.py`; role-by-role city-collapse mutations | Sec. 3.2; App. B | Software exact; formal rows absent |
| Target support/query isolation across banks and siblings | data load, factorial, evaluation | `formal_dataset.py`, `formal_factorial.py`, `formal_evaluation.py` | cross-bank position-ID and sibling contamination mutations | Sec. 6.1; App. B | Software exact; formal rows absent |
| Physical primary routes and independent teacher strata | `qualify`, `run-evaluation` | `formal_routing.py`; config `qualification` | target/teacher replacement, empty-route, unit and coverage tests | Sec. 3.3, Eq. 4 | Software exact under `SC-ROUTE-002` boundary |
| Pair-consistent gauge | data load, `qualify` | `formal_dataset.py`; `DATA_CONTRACT.md` | per-world reference and target-derived reference rejection | Sec. 4.1 | Conservative shared-reference implementation; author decision blocked |
| CSI-only teacher, exact 75% masks, frozen targets | `qualify` | `formal_teacher.py`, `formal_qualification.py` | per-sample/per-step mask and target-replacement mutations | Secs. 3.3, 4.1 | Software exact; formal qualification absent |
| No-position information allowlist | `qualify`, `run-factorial` | `formal_model.py`, `formal_factorial.py` | receiver-position, target, route, ID, crop and batch-leak tests | Fig. 2; App. B | Software exact |
| Strict Endpoint/A/R/Full factorial | `run-factorial` | `formal_config.py`, `formal_factorial.py` | initialization, branch-plan, gradient, FLOP and checkpoint parity tests | Sec. 4.5; Table 1 | Software exact; experiment not run |
| Response stop/go gate | `prepare-full-run` | `formal_qualification.py`, `formal_run_approval.py` | oracle/no-x, copy, no-action, exact action-swap, null and replay mutations | Sec. 7; Table 2 | Executable; input and author conflicts block launch |
| Dynamic per-city base-map-cluster minimum | data load, factorial | `formal_dataset.py`; config `minimum_independent_base_map_clusters_per_target_city` | split/duplicate cluster and single-city failure mutations | Sec. 6.1 | Software exact; formal banks absent |
| Scene-clustered intervals, Holm, sign flip | evaluation, risk, path | `formal_statistics.py`, `formal_evaluation.py`, `formal_risk.py`, `formal_path.py` | exact/Monte Carlo p-value, tie-order, duplicate and pooled-mask tests | Sec. 6.4 | Software exact; results absent |
| Two-phase approval and stopping budget | `prepare-full-run`, `create-run-approval`, `all` | `formal_cli.py`, `formal_run_approval.py` | nonce, expiry, root relocation, mutation, replay, GPU/disk/license and short-circuit tests | Fig. 3; Sec. 7 | Software exact |
| Main and external runtime identity | every evidence stage | `formal_evidence.py`, `formal_external_runtime.py` | locked version/RECORD, interpreter, CUDA/driver and profile-collision mutations | Reproducibility statement | Software exact; formal CUDA runtimes absent |
| C8 G3/G4/G5 chain | `assemble-claims` | `formal_claims.py` | cross-run qualification/factorial/evaluation/control gate splicing | App. D | Software exact; gates not assessed |
| C1 two-model six-condition audit | `run-external-baselines` | `formal_external.py`; adapter registry | unsafe IDs, per-city pooled masking, unit/hash and runtime substitution tests | Fig. 1; Sec. 6.2 | One eligible model only; blocked |
| G8 independent external validity | `run-external-validity` | `formal_external_validity.py`; Sionna adapter | raw-CSI outer recompute, runtime reprobe and stage inventory mutations | Sec. 7; App. D | External scenes/runtime/compute blocked |
| Claim promotion | `assemble-claims` | `formal_claims.py`; claim contract | stale schema, missing gate, weak manifest, fixture and cross-run mutations | App. D | C1-C13 blocked |
| Anonymous delivery | build anonymous supplement | `anonymous_release.py`; anonymous build script | identity, Git SHA, path, symlink, duplicate and binary-token scans | Reproducibility statement | Mechanical package passes; submission science not ready |

## Frozen conflicts

`SC-GAUGE-001` and `SC-ROUTE-002` are defined in `artifacts/source_conflict_register.md`.
Neither is an implementation detail. The current code preserves the more conservative frozen
estimands and fails closed where the required external reference is absent.
