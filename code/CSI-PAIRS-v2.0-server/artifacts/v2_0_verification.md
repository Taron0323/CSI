# CSI-PAIRS V2.1 code verification record

> Historical verification snapshot for an earlier commit. Test counts and bundle hashes below are
> not evidence for the current tree; use the current PR validation record.

Date: 2026-08-07 (Asia/Shanghai)

Engineering status: `CODE_READY_FOR_FORMAL_INPUT`

Scientific status: `NO_GO_EVIDENCE_NOT_RUN`

This record supersedes the previous V2.0 dry-run report. Archived V1/V1.26 fixture outputs and numbers are traceability material only; they do not prove that the current `formal_v2` implementation executes correctly and cannot support a V6 claim.

## 2026-08-08 current PR addendum

The current repair starts from `BASE_SHA`
`eef3040c13264829cda1f4398009f691b52038ae`; code and regression tests are fixed at
`AUDITED_CODE_SHA` `2c0969a7b67086de83471f40f7e65d328bf1ded4`. The source-tree suite passes
`271/271` tests under CPython 3.12.10. Compilation, Ruff `E9,F`, `pip check`, strict V2.3
formal/smoke configuration loading, 25 CLI help paths, shell syntax, and vendored hashes pass.

The anonymous-release regression now builds a fresh archive, excludes the private requirement-matrix
generator and its internal audit tests, extracts the archive, and executes every exported public test.
This closes the discovered failure in which the exported suite retained an audit test whose internal
claim contract was intentionally absent. The release remains separated from the provenance-bearing
internal server delivery.

Remote-head replay found two additional delivery defects and closed both before this audited SHA.
First, the bundle verifier inherited the fixture qualification's expected exit `1`; it now returns
success only after authenticating the complete `DRY_RUN_FAIL_NOT_EVIDENCE`, `passed=false`,
`fixture=true`, `scientific_use=FORBIDDEN` state. Second, pull-request merge refs use the generic
`GitHub <noreply@github.com>` committer; the anonymity scan now excludes only those two
non-identifying automation tokens while retaining real author/committer identities, repository
owners, project commit SHAs, and personal-path detection.

A subsequent GitHub Actions replay completed the code assertions but two nested integration
subprocesses exceeded their former 120-second limits on the hosted Linux CPU. Those bounded waits
are now 300 seconds without skipping tests or changing assertions. Both targeted regressions and
the then-current 258-test source suite passed locally. The current 271-test suite passes at the
audited SHA after adding the hashed-runtime and atomic-trace regressions.

The reproducible paper build has SHA-256
`35117a4a30261f7d9c04cdeedcf4edb0634722354509dc9b92da2f3d5acf2f3e`, contains 10 PDF
pages with references beginning on page 9 and appendices after references, and passes the ICLR
preflight with zero findings. All pages were visually inspected; no clipping, overlap, author/title
metadata, unembedded font, undefined citation/reference, duplicate label, or overfull box was found.

These are implementation and protocol checks, not experimental results. `PAPER_PROTOCOL_GO=NO-GO`,
`FORMAL_INPUT_READY=BLOCKED`, `LAUNCH_READY=BLOCKED`, `FORMAL_GO=NO-GO`, and
`SCIENTIFIC_EVIDENCE=NOT_ASSESSED` remain binding for the author-decision and external-input blockers
listed in `artifacts/formal_experiment_blockers.md`.

## 2026-08-07 readiness repair

The latest audit closed the following code-resolvable protocol/evidence-integrity gaps:

1. Stage-0 now resamples an independent exact-cardinality 75% mask for every sample and every
   optimization step. The sampler contract is checkpoint-bound as schema v2.3.
2. Formal patch grids must have a patch count divisible by four; 75% masking is never rounded.
3. G1 now checks four same-unit per-bank repeat-pair noise floors against the corresponding
   alignment/response and physical/latent null thresholds.
4. Every evidence-producing single-stage CLI command atomically reserves its registered output
   under an exclusive run-root operation lock. `make-fixture` normalizes `.npz` before exclusive
   creation, so suffix aliases and concurrent writers cannot overwrite an archive.
5. Shuffled-pair and retention controls now train and bind independent source-only checkpoints
   instead of accepting aggregate or reused-checkpoint claims.
6. The built-in SigMap scene-ID control binds source-only training provenance and compares actual
   two-dimensional output displacement directions on unseen source banks.
7. Five first-party resource controls provide complete per-seed checkpoints, training/loss logs,
   profiler events, replay, and symmetric accounting that retains concat bottleneck cost.
8. The fixture generator can opt into two banks per source role to exercise cross-source-city
   controls without changing the formal schema or scientific-use prohibition.

Follow-up checks on the current tree:

Locked audit environment: Python 3.12.10. The host-specific interpreter path is recorded in the
delivery PR, not embedded in runtime configuration or the release bundle.

| Check | Result |
|---|---|
| Full `unittest` discovery | 198/198 PASS |
| Python compilation and CLI help | PASS; top-level parser and all 22 subcommand help paths returned exit 0 |
| Formal/smoke config schema | PASS through strict `load_formal_config`; all shipped JSON also parsed strictly |
| Locked dependency health | `pip check` PASS |
| Shell syntax | PASS |
| Current locked lint | NOT AVAILABLE: `ruff` is not present or version-pinned in `formal_v2/requirements-lock.txt`; the historical 2026-08-06 ruff result below is not promoted to a current reproducible check |
| Secret/path/cache/large-file scan | PASS with declared assets: no credential or personal absolute path; ignored test bytecode removed; large tracked files are authenticated papers/source archives and the draft PDF |
| Repository and vendored SHA-256 inventories | PASS after regeneration |
| Fresh server ZIP and extraction | 166/166 package hashes PASS; ZIP structure PASS; extracted 199/199 tests PASS; extracted dry run PASS with `scientific_use=FORBIDDEN` |
| Non-scientific `make-fixture -> verify-data -> qualify` | verifier PASS; qualification `DRY_RUN_FAIL_NOT_EVIDENCE` on route coverage; native route noise-floor component PASS; `scientific_use=FORBIDDEN` |
| Non-scientific five-resource-control chain | all five adapters emitted three authenticated seeds, checkpoints, traces and replay; scientific gates retained fixture FAIL/FORBIDDEN boundaries |
| Non-scientific cross-source-city scene-ID chain | built-in SigMap adapter executed to its software gate; `fixture=true`, `scientific_use=FORBIDDEN`, and no claim promotion |
| Reproducible paper build and visual inspection | PASS; 7 main-text pages before statements/references, 10 PDF pages total, anonymous metadata, four explicit `NOT A RESULT` placeholders |
| ICLR 2027 Author/Reviewer/AI policy live recheck | PASS; Author Guidelines retain September 25, 2026 AOE and the reviewer FAQ still contains the stale September 16 sentence |

The complete traceability matrices and five-layer verdict are in
`artifacts/v6_traceability_audit_2026-08-07.md`.

## Historical checks retained from the 2026-08-06 audit

The counts in this section describe the immutable 2026-08-06 package snapshot. They are not the
current 198-test or final-package totals recorded above.

| Check | Command | Result |
|---|---|---|
| Static compilation | `python3 -m py_compile formal_v2/*.py formal_v2/external_adapters/*.py formal_v2/tests/test_formal_v2.py` | PASS |
| Static lint | `ruff check formal_v2 --exclude formal_v2/external_adapters/vendor` | PASS |
| Pure schema/semantic tests | the 85-test `formal_v2.tests.test_formal_v2` suite, executed in six class groups after evicting read-only Torch pages between groups to stay below the 2 GiB verification cgroup | 85/85 PASS; every group returned exit 0 |
| Supplied external-resource authentication | `formal_cli verify-waibu-resources` | 10/10 PASS; authenticates bytes only |
| Vendored Wi-GATr integrity | `sha256sum --check VENDOR_SHA256SUMS` from the vendored snapshot root | 45/45 PASS |
| Wi-GATr isolated runtime | Python 3.10 `uv.lock` offline sync, imports, and official-model CPU mutation | environment PASS: Torch 2.0.1+cu117, GATr 1.2.2, Wi-GATr 1.0.0; formal forward correctly requires CUDA because frozen xFormers has no compatible CPU kernel; CUDA unavailable on this host, no formal training |
| Fixture independent regeneration | `formal_cli verify-data` with `fixture_verifier.json` | PASS, `scientific_use=FORBIDDEN` |
| Fixture qualification | `formal_cli qualify` before the smoke-only batch reduction | expected FAIL on branch coverage, geometry-matched wrong-action coverage, and B_audit_hold reconstruction; the final batch-4 retry was SIGKILLed by the 2 GiB cgroup after writing Stage-0, so it is not recorded as a second gate result |
| Current-tree test-only four-arm execution | factorial with an authenticated temporary fixture gate and smoke batch 4 | 12 checkpoints completed; 13 state + 15 predictor calls/step; 95,289,024 dispatch-counted FLOPs/step for the common branch plan; G5 FAIL; all artifacts fixture/FORBIDDEN |
| Current-tree unified evaluation attempt | evaluation from the 12 fixture checkpoints | NOT COMPLETED: the 2 GiB verification cgroup sent SIGKILL before any evaluation artifact was emitted; this is not recorded as an evaluation PASS or FAIL |
| Claim mutation check | `formal_cli assemble-claims` | `INCOMPLETE_FAIL_CLOSED`; no C1-C13 support |
| External-evidence mutation checks | scene-ID duplicate cluster/unit, G8 duplicate rows, G0 content mutation, RT fit/validation/source binding, copied input-manifest mutation, and weak C2/C11/C12/C13 gate payloads | PASS: all mutations are rejected or remain FAIL/BLOCKED |
| Representation fixture integration | role verifier plus downscaled pretraining/selection/unified localization probe for all five registered models | PASS: 5/5 models and 5 checkpoints; `scientific_use=FORBIDDEN`, not paper dose |
| External-model semantic mutations | per-sample MAE masks, ContraWiMAE source-only warm-start, WiSER learned-query/Hungarian path, RFIR visibility, C1 eligibility | PASS; no style-controlled adapter can support C1 |
| Sionna RT/LRM runtime | authenticated source setup, dependency consistency, and `formal_v2.sionna_facility verify` | PASS: Sionna 2.0.1, RT 1.2.1, LRM revision `1ba19ae1...`, CPU Torch 2.9.1, h5py 3.15.1; CUDA dependencies excluded |
| Sionna scene export/CFR | material PLY/XML, asset licenses/hashes, complete external-world manifest, reverse schema validation, `load_scene`, and `PathSolver.cfr(out_type="numpy")` | PASS on generated fixture extension: four sibling worlds, each `(16 positions, 16 CSI channels)`, all finite; no G8 effect result |
| Reproducible paper build | `paper_v2/build_reproducible.sh` | PASS, 10-page placeholder draft |
| Server bundle build and extraction | `build_server_bundle.sh`, followed by clean extraction, package-root SHA, compilation, and unit checks | PASS: 147/147 SHA entries and 85/85 tests; runtime-generated `*.egg-info` is excluded |

The tests cover strict JSON, the seven-role permission ledger, downstream per-role regeneration blocking, target query-only denominators, typed maps/actions, 2D patch tiling, complete teacher-encoder initialization, BS-pose sensitivity, model input allowlist and batch isolation, dual outputs, empty conditional failure, city-level k, base-map-cluster macro utility, hierarchical bootstrap layers, gate/claim authentication, checkpoint hashes, q_comp order/complement, selection-frozen risk support, coverage monotonicity, path/no-op primitives, fail-closed control manifests, cluster-macro scene-ID and G8 confidence gates, exact scene-ID four-condition joins, RT fit/validation/source/fitted-parameter binding, G0 local-content and overlap-decision consistency, downstream copied-manifest reauthentication, weak-gate claim mutations, Wi-GATr power/mesh conversion, target-free inverse input, CUDA fail-fast, common six-condition units, external execution-manifest mutation, all-five representation gradients, fixed CSI-MAE positions/per-sample masks, ContraWiMAE warm-start, WiSER set matching, RFIR visibility, C1 model identity, authenticated Sionna scene export, NumPy CFR, and Mitsuba coordinate conversion.

The test-only four-arm run is not qualification bypass evidence. It used `/tmp`, retained `fixture=true` and `scientific_use=FORBIDDEN`, and exists only to exercise code after the real fixture qualification correctly stopped. Endpoint/Alignment/Response/Full used identical branch plans and measured forward counts; disabled A/R terms had zero weighted gradient while their raw gradients remained nonzero. The first arm used PyTorch's dispatch FLOP counter and later isomorphic arm plans explicitly reused that measured FLOP value while independently measuring their forward-call counts.

An earlier pre-final test-only revision reached evaluation and path and failed G3/G5/G7, but those outputs are not claimed as current-tree verification. The current-tree evaluation retry was resource-blocked as stated above. No result from either run is scientific evidence.

## Explicitly not run

- non-fixture independent RT regeneration;
- non-fixture Stage-0 teacher training or qualification;
- wrong-map models;
- non-fixture four-arm training or localization;
- non-fixture compatibility/response probes;
- q_comp or p_fail fitting;
- path mechanism analysis;
- non-fixture equal-FLOP/concat, scene-ID, shuffled-pair, retention, or resource-control executions;
- formal Wi-GATr 200k-step or controlled WiSER training/evaluation, RT-calibration, literature-resource, or external-validity effect adapters;
- any non-fixture result-producing experiment.

Therefore no G0-G8 gate and no C1-C13 claim is promoted by this record. `NOT_ASSESSED` remains distinct from PASS.

## Remaining external inputs

Formal execution still requires a qualified non-fixture dataset, independent regeneration and RT calibration evidence, actual Wi-GATr plus a second C1-eligible model's checkpoints/six-condition rows, non-fixture executions of the shipped controls, licensed external-validation scene assets, and a completed Sionna G8 retrace. The inherited No-X/null failures and the four named warnings remain binding until untouched non-fixture evidence replaces them through the registered gates.
