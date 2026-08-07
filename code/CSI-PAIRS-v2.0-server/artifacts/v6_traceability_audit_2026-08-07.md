# CSI-PAIRS V6 bidirectional traceability audit

Date: 2026-08-07 (Asia/Shanghai)

Audited baseline: `origin/main` at `2e30621c4d44f57345adfe822992c778126443e1`.
The GitHub checkout is the only code baseline. The two frozen V6 research documents are
protocol authorities only; no implementation was copied from an older local tree.

## Status semantics

- `EXACT`: the repository contains a reachable implementation, a precise source location,
  regression coverage, and software execution evidence for the protocol property.
- `PARTIAL/PROXY`: a fail-closed contract exists, but an external implementation, input, or
  scientific execution is still absent.
- `MISSING`: neither an implementation nor an admissible external interface is present.
- `CONFLICT`: the two frozen V6 sources require an author decision that changes the estimand or
  information budget.

`EXACT` below is a software-protocol verdict. It never means that an empirical claim is true.
Fixture and smoke results remain permanently inadmissible as scientific evidence.

## Five-layer verdict

| Layer | Verdict | Evidence and boundary |
|---|---|---|
| `PACKAGE_INTEGRITY` | `PASS` | Repository SHA inventory is regenerated and verified after the change; no private path, secret, cache, or run output is included. |
| `SOFTWARE_EXECUTION` | `PASS` | 180 unit tests, Python compilation, shell syntax, CLI help, resource hashes, and the non-scientific verifier/qualification smoke complete. |
| `V6_PROTOCOL_FIDELITY` | `PASS_WITH_EXTERNAL_CONTRACTS` | All code-resolvable P0/P1 findings in this audit are closed. External controls and evidence remain fail-closed interfaces. |
| `FORMAL_EXPERIMENT_READINESS` | `CODE_READY_FOR_FORMAL_INPUT` | The runner can start formal qualification when admissible inputs exist, but the complete reviewer-grade `all` run is externally blocked. |
| `SCIENTIFIC_EVIDENCE` | `NOT_ASSESSED` | No qualified non-fixture Stage-0, four-arm, target-city, calibration, or external-validity result has been run. |

## Paper-to-code traceability

| Requirement ID | Frozen V6 source | Expected behavior | Reachable implementation | Test or execution evidence | Status and impact |
|---|---|---|---|---|---|
| V6-S0 | Section 0 | Joint Alignment/Response thesis with explicit non-causal and non-global-confidence boundaries | `formal_claims.py`, `artifacts/v2_0_claim_evidence_contract.json`, `paper_v2/main.tex` | claim dependency mutation tests | `EXACT`; all claims remain blocked without results |
| V6-S1 | Section 1 | Begin from wrong-map diagnostics; scene ID is a conditional mechanism hypothesis | `formal_wrong_map.py`, `formal_scene_id.py`, `formal_external.py` | wrong-map, scene-ID, and six-condition mutation tests | `EXACT` for protocol; evidence not run |
| V6-S2 | Section 2 | Canonical world banks, common positions, Hamming-1 pairs, typed edits, unique roles, clean/repeat CSI, provenance | `formal_dataset.py`, `formal_protocol.py`, `formal_data_verification.py` | dataset, verifier-authentication, support-exclusion tests | `EXACT` |
| V6-S3 | Section 3 | CSI-only asymmetric 2D MAE; per-sample random 75% masks; frozen teacher/readout; full-channel and patch routes; same-unit noise floors | `formal_teacher.py`, `formal_routing.py`, `formal_qualification.py` | mask resampling, checkpoint, route direction, native noise-floor tests; fixture qualification | `EXACT`; fixed in this branch |
| V6-S4 | Section 4 | Shared F/P, complete teacher initialization, endpoint/Alignment/Response losses, dead zones, bank-route macro objectives, matched dose | `formal_model.py`, `formal_factorial.py` | model allowlist, pose sensitivity, branch plan, gradient/FLOP tests | `EXACT` |
| V6-S5 | Section 5 | CGS and native metrics are separate; `q_comp` and `p_fail` are separately fitted and scoped | `formal_evaluation.py`, `formal_risk.py` | response/compatibility, proposal, calibration, common-support and monotonicity tests | `EXACT` |
| V6-S6 | Section 6 | Theory states limited identification results and does not pre-claim synergy | `paper_v2/main.tex`, `formal_claims.py` | claim fail-closed tests | `PARTIAL/PROXY`; final proofs and wording require paper review after evidence |
| V6-S7 | Section 7 | Strict 2x2 arms differ only by Alignment/Response switches; common plans and seven synergy gates | `formal_factorial.py`, `formal_statistics.py`, `formal_claims.py` | factorial mutation, synchronized-bootstrap, resource-control tests | `EXACT` |
| V6-S8 | Section 8 | RQ1-RQ5 use registered estimands and untouched target units | `formal_cli.py` complete chain plus evaluation/risk stages | CLI reachability and downstream authentication tests | `EXACT` for execution; all RQs scientifically unassessed |
| V6-S9 | Section 9 | Registered path incidence, no-op epsilon, balanced matching, bank-level inference | `formal_path.py` | path provenance, matching, duplicate, zero-path tests | `EXACT` |
| V6-S10 | Section 10 | Leakage audit, shuffled-pair control, and retention audit | `formal_claim_controls.py`, `formal_evidence.py` | source-binding, row-completeness, claim dependency tests | `PARTIAL/PROXY`; reviewed external control implementations/manifests are absent |
| V6-S11 | Section 11 | Internal factorial baselines plus faithful, resource-matched external models | `formal_external.py`, `formal_representation_baselines.py`, `external_adapters/` | model gradients, registry, C1 eligibility and six-condition tests | `PARTIAL/PROXY`; only one external map model is currently C1-eligible |
| V6-S12 | Section 12 | City/bank/foundation/seed/draw hierarchy, paired bootstrap, Holm, superiority, noninferiority, equivalence | `formal_statistics.py`, `formal_evaluation.py`, `formal_risk.py` | hierarchy, duplicate invariance, simultaneous-bound and Holm tests | `EXACT` |
| V6-S13 | Section 13 | Main figures and tables show only formal results with traceable denominators | `paper_v2/main.tex` explicit placeholders | PDF/page inspection | `MISSING` by design until formal evidence exists; placeholders must remain |
| V6-S14 | Section 14 | C1-C13 advance only through authenticated dependencies | `formal_claims.py`, `artifacts/v2_0_claim_evidence_contract.json` | weak-artifact and copied-manifest mutation tests | `EXACT`; current claims are `BLOCKED` |
| V6-S15 | Section 15 | G0-G8 fail closed and preserve `NOT_ASSESSED` | `formal_evidence.py`, all stage gates, `formal_cli.py` | gate-vector and fixture propagation tests | `EXACT`; reviewer-grade run is externally blocked |

## RQ traceability

| ID | Registered question and discriminator | Main code/evidence path | Software status | Scientific status |
|---|---|---|---|---|
| RQ1 | Counterfactual map use under the six-condition paired wrong-map audit | `formal_wrong_map.py`, `formal_external.py`, `formal_scene_id.py` | `PARTIAL/PROXY` because a second faithful external model is absent | `NOT_ASSESSED` |
| RQ2 | Restricted relative compatibility from Alignment, including shortcut controls | `formal_factorial.py`, `formal_evaluation.py`, `formal_claim_controls.py` | `PARTIAL/PROXY` because shuffled-pair execution is external | `NOT_ASSESSED` |
| RQ3 | Target-free response direction and magnitude against RT rerendered targets | `formal_factorial.py`, `formal_evaluation.py` | `EXACT` | `NOT_ASSESSED` |
| RQ4 | Strict unseen-city localization at k=0 and city-level k=8 | `formal_localization.py`, `formal_evaluation.py`, `formal_statistics.py` | `EXACT` | `NOT_ASSESSED` |
| RQ5 | Paired compatibility to calibrated localization risk on common support | `formal_risk.py` | `EXACT` | `NOT_ASSESSED` |

## Gate traceability

| Gate | Required decision | Implementation and tests | Status |
|---|---|---|---|
| G0 | Current literature/resource provenance and novelty overlap | `formal_literature.py`; local-content and contradiction tests | `PARTIAL/PROXY`; authenticated literature execution input is absent |
| G1 | Verified world banks, repeat quality, per-bank route coverage, and all four same-unit route noise floors | `formal_data_verification.py`, `formal_qualification.py`; verifier, coverage, and native noise-floor tests | `EXACT`; no formal bank has passed |
| G2 | Frozen teacher/readout, no-X/oracle/action controls, null safety, shortcut audit | `formal_teacher.py`, `formal_qualification.py` | `EXACT`; no formal teacher has passed |
| G3 | Each single branch performs its registered job | `formal_factorial.py`, `formal_evaluation.py`, `formal_claims.py` | `EXACT`; not run formally |
| G4 | Full arm passes all seven synchronized synergy/resource subgates | `formal_statistics.py`, `formal_controls.py`, `formal_claims.py` | `PARTIAL/PROXY`; resource-control executions are external |
| G5 | Two-city localization and no reversal beyond tolerance | `formal_evaluation.py`, `formal_statistics.py` | `EXACT`; not run formally |
| G6 | Separate `q_comp`/`p_fail`, common support, calibration, AURC and coverage | `formal_risk.py` | `EXACT`; not run formally |
| G7 | Registered path provenance, matched mechanism strata, zero-path equivalence | `formal_path.py` | `EXACT`; not run formally |
| G8 | Independent engine or real intervention with direction and null-equivalence intervals | `formal_external_validity.py`, Sionna adapter/export | `PARTIAL/PROXY`; licensed scenes and independent rerender results are absent |

## Claim traceability

| Claim | Required evidence dependency | Enforcement location | Software status | Current claim state |
|---|---|---|---|---|
| C1 | At least two faithful external map models and complete six-condition paired rows | `formal_external.py`, `formal_claims.py` | `PARTIAL/PROXY` | `BLOCKED` |
| C2 | Held-out scene-ID mechanism with exact four-condition joins | `formal_scene_id.py`, `formal_claims.py` | `PARTIAL/PROXY` external execution | `BLOCKED` |
| C3 | Single-branch target-free metrics, active/null controls, unseen banks/cities | evaluation plus G3 dependency | `EXACT` | `BLOCKED` |
| C4 | Alignment gain plus shortcut and shuffled-pair discriminator | evaluation, `formal_claim_controls.py` | `PARTIAL/PROXY` external control | `BLOCKED` |
| C5 | Target-free response under all mask families and simple controls | evaluation response probes | `EXACT` | `BLOCKED` |
| C6 | Map/action retention and F-only downstream audit | evaluation, retention control | `PARTIAL/PROXY` external control | `BLOCKED` |
| C7 | Every G4 synergy gate and G5 city result | factorial/statistics/claims | `PARTIAL/PROXY` resource controls external | `BLOCKED` |
| C8 | Two target cities at strict k=0 and city-level k=8 | localization/statistics | `EXACT` | `BLOCKED` |
| C9 | All four risk-gate families | risk/claims | `EXACT` | `BLOCKED` |
| C10 | Path mechanism and zero-path equivalence | path/claims | `EXACT` | `BLOCKED` |
| C11 | Independent RT calibration with all registered validation statistics | `formal_rt_calibration.py` | `PARTIAL/PROXY` external fit/validation execution | `BLOCKED` |
| C12 | Independent RT engine or controlled real intervention | `formal_external_validity.py` | `PARTIAL/PROXY` external evidence | `BLOCKED` |
| C13 | Current, auditable literature search and overlap decision | `formal_literature.py` | `PARTIAL/PROXY` external literature input | `BLOCKED` |

### C7 seven subgates

| ID | Frozen decision | Code/test | Status |
|---|---|---|---|
| C7.1 | Full J exceeds Alignment-only and Response-only | synchronized factorial family | `EXACT` |
| C7.2 | Full CGS is noninferior to Alignment-only | evaluation/claims noninferiority bound | `EXACT` |
| C7.3 | Full native response is noninferior to Response-only | response bound and common units | `EXACT` |
| C7.4 | Interaction lower bound exceeds zero and the practical threshold | hierarchical synchronized bootstrap | `EXACT` |
| C7.5 | No target city reverses beyond tolerance at k=0 or k=8 | per-city reversal gate | `EXACT` |
| C7.6 | Full exceeds both equal-FLOP single branches | dispatch FLOP/resource controls | `PARTIAL/PROXY`; external runs absent |
| C7.7 | Full exceeds parameter- and FLOP-matched independent concat | authenticated architecture/operator controls | `PARTIAL/PROXY`; external runs absent |

### C9 four risk gates

| ID | Frozen decision | Code/test | Status |
|---|---|---|---|
| C9.1 | Frozen map-only proposals, strict k=0, common four-arm denominator | first-party proposal replay and common-unit checks | `EXACT` |
| C9.2 | ECE, Brier, NLL and reliability intervals pass | seed/foundation/bank macro calibration | `EXACT` |
| C9.3 | Common-support coverage and Full out-of-support noninferiority pass | fit/selection split and support detector | `EXACT` |
| C9.4 | Joint AURC beats random and u-only; 90/75/50 errors are monotone | tied-score invariant AURC and monotonicity tests | `EXACT` |

## Code-to-paper reverse matrix

| Code surface | Frozen authority | Information/estimand audit | Status |
|---|---|---|---|
| NPZ arrays and metadata | V6 Sections 2, 9, 12 | Exact keys, role ledger, licenses, clean/repeat CSI, paths, support/query split; unknown fields rejected | `EXACT` |
| Stage-0 teacher inputs | V6 3.1 | CSI only; target/map/position/action substitution cannot enter | `EXACT` |
| Stage-0 masks | V6 3.1 | Independent per-sample, without replacement, exact 75%, resampled each step; checkpoint-bound | `EXACT` |
| Route normalization | V6 3.2, 4.4 | Fitted only on `source_encoder_train`; alignment and response retain separate physical granularity | `EXACT` |
| Route low thresholds | V6 3.2 | Each source-method-selection bank must cover pairwise independent-repeat noise in the identical norm | `EXACT` |
| F input schema | V6 4.1 | Masked source CSI, source map, radio and BS pose only; no route, ID, target CSI or true receiver position | `EXACT` |
| P input/output schema | V6 4.4 | State, typed signed edit and query; predicts both latent and physical patch targets | `EXACT` |
| Endpoint loss | V6 4.2 | Same in all arms and bank-macro weighted | `EXACT` |
| Alignment loss | V6 4.3 | Complete B_align mean before hinge; active quartet and null dead zone; gray excluded | `EXACT` |
| Response loss | V6 4.4 | All-route target regression; active deltas and null dead zones use independent latent/physical weights | `EXACT` |
| Pilot scales/margins | V6 4.3-4.5 | Source-method-selection only; one shared initialization/batch plan; final checkpoints cannot retune | `EXACT` |
| Four-arm resource accounting | V6 7 | Real forward calls, parameter updates, gradients, dispatch FLOPs and timing; no proxy execution of disabled branches | `EXACT` |
| Evaluation/probes | V6 5, 8 | Frozen F, target-free masked inputs, common budgets and support-sibling exclusion | `EXACT` |
| Statistics | V6 7, 12 | City, canonical foundation, bank, seed and draw hierarchy; synchronized contrasts and Holm | `EXACT` |
| Risk outputs | V6 5.3-5.4 | `q_comp` and `p_fail` remain distinct; target route is never an online input | `EXACT` |
| External adapters | V6 10-11, G8 | Hash-bound code/config/checkpoint/unit rows; style controls cannot self-promote | `PARTIAL/PROXY` until external implementations/results exist |
| Gate and claim outputs | V6 14-15 | Missing, fixture, `NOT_ASSESSED`, hash mismatch and incomplete dependencies never auto-PASS | `EXACT` |
| CLI output policy | V6 reproducibility/evidence integrity | Every evidence-producing stage atomically reserves its registered output under an exclusive run-root operation lock; fixture writers normalize `.npz` before exclusive creation | `EXACT` |

## CLI and orchestration audit

| Command | Output or role | Implementation class | Fresh-output rule |
|---|---|---|---|
| `make-fixture` | permanently non-scientific NPZ | endogenous | exact file must be absent |
| `verify-waibu-resources` | `waibu_resources/` | endogenous byte authentication | `exist_ok=False` |
| `export-sionna-scenes` | hashed external scene tree | endogenous exporter | root `exist_ok=False` |
| `inspect-data` | `data_contract.json` | endogenous | registered path absent |
| `verify-data` | `data_verification/` | external verifier contract plus endogenous comparison | registered path absent |
| `qualify` | `qualification/` | endogenous | registered path absent |
| `run-wrong-map` | `wrong_map/` | endogenous | registered path absent |
| `run-factorial` | `factorial/` | endogenous | registered path absent |
| `run-evaluation` | `evaluation/` | endogenous | registered path absent |
| `run-risk` | `risk/` | endogenous first-party replay | registered path absent |
| `run-path` | `path/` | endogenous | registered path absent |
| `run-external-baselines` | `external_baselines/` | authenticated adapter contracts | registered path absent |
| `run-representation-baselines` | `representation_baselines/` | endogenous controlled implementations | registered path absent |
| `run-resource-controls` | `controls/` | authenticated external control contracts | registered path absent |
| `run-scene-id-audit` | `scene_id/` | authenticated external contract | registered path absent |
| `run-external-validity` | `external_validity/` | authenticated independent-engine contract | registered path absent |
| `run-literature-resources` | `literature_resources/` | authenticated external input contract | registered path absent |
| `run-rt-calibration` | `qualification/rt_calibration/` | authenticated fit/validation contract | registered path absent |
| `run-shuffled-pair-control` | `controls/shuffled_pair/` | authenticated external control contract | registered path absent |
| `run-retention-audit` | `evaluation/retention/` | authenticated external control contract | registered path absent |
| `assemble-claims` | `claims/` | endogenous dependency assembly | registered path absent |
| `all` | complete chain above | orchestrator | unused root, except one non-symlink `inputs/` directory |

`all` calls resource verification, data verification, qualification, wrong-map, factorial,
evaluation, risk, path, external map baselines, representation baselines, resource controls,
scene-ID, external validity, literature resources, RT calibration, shuffled-pair, retention, and
claim assembly. No required stage is silently skipped.

## Directed hypothesis recheck

| Audit hypothesis | Current verdict | Evidence |
|---|---|---|
| Teacher is only a simplified full-visible Transformer | `REFUTED` | asymmetric masked 2D MAE and held-out mask audit |
| F copies only the teacher embedding | `REFUTED` | embedding, mask token, 2D positions and complete encoder state copied/tested |
| BS pose is declared but unused | `REFUTED` | concatenated context and pose-sensitivity mutation test |
| Branch siblings use different source/mask/query units | `REFUTED` | immutable shared branch plan and repeated-source-query tests |
| Alignment trains per-view hinge instead of full B_align mean | `REFUTED` | complete branch bundle aggregation before hinge |
| Support siblings contaminate target metrics | `REFUTED` | city support selection and every target metric iterator exclude them |
| G3/G4/G6/G7 accept weak aggregate artifacts | `REFUTED` | row-level identity, manifest reauthentication and mutation tests |
| Repeated banks or clusters multiply statistical weight | `REFUTED` | canonical foundation/bank and duplicate-invariance tests |
| Claims can advance before dependencies | `REFUTED` | C1-C13 dependency assembly is fail closed |
| `all` omits required evidence stages | `REFUTED` | enumerated reachable call chain above |
| Stage-0 reuses a small fixed mask bank | `CONFIRMED_AND_FIXED` | independent exact-cardinality sampler plus per-step integration test |
| Route null thresholds lack same-unit noise-floor proof | `CONFIRMED_AND_FIXED` | `route_noise_floor.csv` and G1 four-metric coverage requirement |
| Single-stage commands can overwrite evidence | `CONFIRMED_AND_FIXED` | atomic output reservation, exclusive run-root operation locks, normalized fixture paths, and sequential/concurrent overwrite mutation tests |

## External blockers

The code must not substitute fixtures or self-reported JSON for the following:

- a qualified non-fixture RT dataset with the exact V6 NPZ schema and asset licenses;
- an independently authenticated regeneration command and RT calibration fit/validation inputs;
- enough independent source banks, target banks in two cities, and external-validation banks;
- reviewed shuffled-pair, retention, scene-ID and five resource-control implementations/manifests;
- a second C1-eligible faithful external map model and its formal checkpoint/results;
- licensed Sionna/second-engine scene assets and completed G8 paired rerender rows;
- NVIDIA CUDA and an approved compute budget for formal Wi-GATr and full training.

Until those inputs pass their registered gates, the only defensible handoff state is
`CODE_READY_FOR_FORMAL_INPUT`, not `FORMAL_EXPERIMENT_READY` and not scientific PASS.
