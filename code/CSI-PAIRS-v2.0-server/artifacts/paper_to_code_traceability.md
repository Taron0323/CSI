# Paper-to-code traceability

Date: 2026-08-08 (Asia/Shanghai)

Audited code: `2c0969a7b67086de83471f40f7e65d328bf1ded4`

## Atomic source ledger

The authoritative row-level index is
`artifacts/v6_atomic_requirement_matrix_2026-08-08.csv`. It contains 2,124 rows derived from the
workspace's single declared V6 authority and binds each row to the immutable source-document hash,
source line, clause hash, executable entry, code,
configuration, regression anchor, evidence boundary, and paper location. Matrix cells redact the
duplicated clause text; the authoritative reader itself remains tracked at the repository root.

| Atomic status | Rows | Meaning |
|---|---:|---|
| `EXACT` | 837 | The normative clause has an explicit semantic family, reachable code/config/test anchors, and a replayable software check. This is not a scientific-result verdict. |
| `PARTIAL/PROXY` | 1,268 | 1,080 rows are retained non-normative context; 137 require external data/execution and 51 require licensed or access-controlled inputs. |
| `MISSING` | 19 | Authenticated non-fixture result cells do not exist. This is an external-data/execution boundary, not permission to use fixture values. |
| `CONFLICT` | 0 | The A + R1 author decision closes the former gauge and route conflicts. |

The matrix has no section-level fallback. Markdown table data cells are normative without keyword
guessing, and source CI rebuilds and compares the complete public matrix. Each normative row is bound to a semantic evidence family
and its exact clause hash; a new or unknown normative subsection aborts generation. Formal result
rows remain `MISSING`, the author-frozen gauge clauses are `EXACT`, and RQ/claim-gate mentions of
`q_comp` or `p_fail` retain their external-evidence family. There is no remaining `CODE_REQUIRED`
trace row, but no `EXACT` software row is counted as a completed scientific result.

## Decision-critical mappings

| Protocol surface | Runtime entry | Code and configuration | Regression/adversarial evidence | Paper location | Current state |
|---|---|---|---|---|---|
| Seven source roles and per-role city coverage | `inspect-data`, `verify-data` | `formal_v2/formal_dataset.py`; `formal_v2/configs/formal_v2.json` | `test_data_protocol_integrity.py`; role-by-role city-collapse mutations | Sec. 3.2; App. B | Software exact; formal rows absent |
| Target support/query isolation across banks and siblings | data load, factorial, evaluation | `formal_dataset.py`, `formal_factorial.py`, `formal_evaluation.py` | cross-bank position-ID and sibling contamination mutations | Sec. 6.1; App. B | Software exact; formal rows absent |
| Physical primary routes and independent teacher strata | `qualify`, `run-evaluation` | `formal_routing.py`; config `qualification` | target/teacher replacement, empty-route, unit and coverage tests | Sec. 3.3, Eq. 4 | Software exact; R1 dual estimands frozen |
| Pair-consistent gauge | data load, `qualify` | `formal_dataset.py`; `DATA_CONTRACT.md` | per-world reference and target-derived reference rejection | Sec. 4.1 | Software exact; A shared-reference target frozen; formal rows absent |
| CSI-only teacher, exact 75% masks, frozen targets | `qualify` | `formal_teacher.py`, `formal_qualification.py` | per-sample/per-step mask and target-replacement mutations | Secs. 3.3, 4.1 | Software exact; formal qualification absent |
| No-position information allowlist | `qualify`, `run-factorial` | `formal_model.py`, `formal_factorial.py` | receiver-position, target, route, ID, crop and batch-leak tests | Fig. 2; App. B | Software exact |
| Strict Endpoint/A/R/Full factorial | `run-factorial` | `formal_config.py`, `formal_factorial.py` | initialization, branch-plan, gradient, FLOP and checkpoint parity tests | Sec. 4.5; Table 1 | Software exact; experiment not run |
| Response stop/go gate | `prepare-full-run` | `formal_qualification.py`, `formal_run_approval.py` | oracle/no-x, copy, no-action, exact action-swap, null and replay mutations | Sec. 7; Table 2 | Executable; external inputs block launch |
| Dynamic per-city base-map-cluster minimum | data load, factorial | `formal_dataset.py`; config `minimum_independent_base_map_clusters_per_target_city` | split/duplicate cluster and single-city failure mutations | Sec. 6.1 | Software exact; formal banks absent |
| Scene-clustered intervals, Holm, sign flip | evaluation, risk, path | `formal_statistics.py`, `formal_evaluation.py`, `formal_risk.py`, `formal_path.py` | exact/Monte Carlo p-value, tie-order, duplicate and pooled-mask tests | Sec. 6.4 | Software exact; results absent |
| Two-phase approval and stopping budget | `prepare-full-run`, `create-run-approval`, `all` | `formal_cli.py`, `formal_run_approval.py` | nonce, expiry, root relocation, mutation, replay, GPU/disk/license and short-circuit tests | Fig. 3; Sec. 7 | Software exact |
| Main and external runtime identity | every evidence stage | `formal_evidence.py`, `formal_external_runtime.py` | locked version/RECORD, interpreter, CUDA/driver and profile-collision mutations | Reproducibility statement | Software exact; formal CUDA runtimes absent |
| C8 G3/G4/G5 chain | `assemble-claims` | `formal_claims.py` | cross-run qualification/factorial/evaluation/control gate splicing | App. D | Software exact; gates not assessed |
| C1 two-model six-condition audit | `run-external-baselines` | `formal_external.py`; adapter registry | unsafe IDs, per-city pooled masking, unit/hash and runtime substitution tests | Fig. 1; Sec. 6.2 | One eligible model only; blocked |
| G8 independent external validity | `run-external-validity` | `formal_external_validity.py`; Sionna adapter | raw-CSI outer recompute, runtime reprobe and stage inventory mutations | Sec. 7; App. D | External scenes/runtime/compute blocked |
| Claim promotion | `assemble-claims` | `formal_claims.py`; claim contract | stale schema, missing gate, weak manifest, fixture and cross-run mutations | App. D | C1-C13 blocked |
| Anonymous delivery | build anonymous supplement | `anonymous_release.py`; anonymous build script | identity, Git SHA, path, symlink, duplicate and binary-token scans | Reproducibility statement | Mechanical package passes; submission science not ready |

## Frozen protocol decisions

`SC-GAUGE-001=A` and `SC-ROUTE-002=R1` are recorded in
`artifacts/source_conflict_register.md`. The code, configuration, data contract, tests and paper
already implement those choices and fail closed where required external reference evidence is
absent.
