# CSI-PAIRS V6 Goal ledger

Last updated: 2026-08-08 (Asia/Shanghai)

## Immutable context

- Repository: `yiweinanzi/CSI`
- `BASE_SHA`: `eef3040c13264829cda1f4398009f691b52038ae`
- Branch: `codex/fix-formal-experiment-readiness`
- Draft PR: `https://github.com/yiweinanzi/CSI/pull/3`
- Starting PR head: `1f5c5fafa0fd76cf1a243f18fcb234c3418a08a6`
- `AUDITED_CODE_SHA`: `7560120ca588c2cce76507116d58ed98c49895bf`
- Last code-bearing remote PR head replayed cleanly: `b2d22e56cf5ff4b2ab5ce1d9bc1a2e50035df01b`

## Authority inputs

| Input | SHA-256 | Read state |
|---|---|---|
| Frozen V6 zero-background reader | `e6d19a65325b688b75472d9814dc9bae26b1d36e08db68cefedc1918696a635b` | complete |
| Frozen V6 complete research plan | `75f7e4e4ce82834216f9a8bf76fcd0785377c6de38aae62cabf4d1e88170dd4a` | complete |
| Integrated Goal prompt | `79b759141bd31a75fbefc80365ef5e6467e6cfedfa58457fa78b4ddebb4bb132` | complete |

The GitHub checkout is the only implementation source. Historical local implementations were not
copied or used to restore code.

## Current phase

`Clean remote re-review complete; external/author blocker handoff`

## Closed code findings

All independently reproduced code-level P0/P1 findings are repaired at `AUDITED_CODE_SHA`:

- unsafe/duplicate adapter IDs and resource FAIL returning success;
- stale Boolean approval, approval replay and missing late-input preflight;
- missing main and external-runtime enforcement;
- cross-bank support leakage and per-role city undercoverage;
- pooled-city Response/C1 masking and incomplete control families;
- dynamic target-city cluster minimum;
- action-displacement identity bug;
- incomplete stage inventory authentication and cross-run C8 gate splicing;
- missing G8 and C1 runtime re-probes;
- nonredistributable PDFs in Git/deliveries and anonymous provenance leakage;
- nondeterministic bundles and missing CI.
- anonymous supplement retaining an internal audit test whose private contract was excluded.
- bundle verification propagating the fixture qualification's expected nonzero exit instead of
  authenticating it as a successful outer software check;
- pull-request CI treating the generic `GitHub <noreply@github.com>` merge committer as a project
  identity and false-positive scanning ordinary GitHub URLs.
- hosted Linux CPU execution legitimately taking longer than the tests' former 120-second nested
  integration bounds; the bounds are now 300 seconds without skipping work or weakening assertions.

The last hypothesis-driven sweep found one additional P1: the main runtime could record but not
reject an internally consistent unlocked environment. The unified evidence context now requires
CPython 3.12, every exact pinned version and a nonempty installed-distribution RECORD digest. The
new version/missing-package/RECORD mutations pass.

The first remote-head replay found the two delivery findings above. The dry-run wrapper now
requires exact exit `1` and reauthenticates the complete `DRY_RUN_FAIL_NOT_EVIDENCE`,
`passed=false`, fixture/FORBIDDEN state before it returns `0`. The anonymity scan ignores only the
two generic GitHub automation tokens while continuing to reject real authors, committers, emails,
repository owners, project SHAs, and personal paths. Both repairs have regression tests.

The second remote-head replay completed every assertion but GitHub Actions reported two
`TimeoutExpired` errors: the extracted anonymous public suite and the complete fixture dry-run took
longer than 120 seconds on the hosted Linux CPU. Their subprocess bounds are now 300 seconds. The
targeted tests pass locally in 63.532 and 51.993 seconds, and the unchanged complete 258-test suite
passes after the repair.

## Latest local verification

| Check | Result |
|---|---|
| Full unittest discovery | `258/258 PASS`, 122.409 s after the hosted-runner timeout repair |
| Compilation, Ruff `E9,F`, `pip check` | PASS |
| CLI help | `25/25 PASS` (top level plus 24 subcommands) |
| Formal/smoke strict config | V2.3 V6 PASS |
| Shell syntax | 9/9 PASS |
| Wi-GATr vendor hash | PASS |
| ICLR preflight on clean paper build | zero findings |
| PDF render | 10/10 pages inspected; no overlap, clipping or identity metadata |
| Remote main drift | none after fetch; `origin/main` remains `BASE_SHA` |
| Hosted Linux CPU CI | `test-and-package` PASS at `b2d22e56cf5ff4b2ab5ce1d9bc1a2e50035df01b` ([run 31223556644](https://github.com/yiweinanzi/CSI/actions/runs/31223556644)) |
| Anonymous exported-suite regression | PASS after fresh build/extraction; internal audit tooling absent |
| Pull-request merge-ref anonymity regression | PASS against the actual PR merge-ref committer identity |
| Deterministic server delivery | SHA-256 `4a3134d577f390f93d1b4eac665e0f343c3e8ca60790fb978bf3f8717c768dd5`; two byte-identical builds |
| Deterministic anonymous delivery | SHA-256 `3bf2be70ae0fe776d3e28821a4cc21b8dcd4a0895249ed704a95915758fd0d50`; two byte-identical builds |
| Fresh server package | 174 inventory entries; 258 tests pass with one expected source-only skip; outer verifier authenticates the expected fixture failure and returns `0` without claim promotion |
| Fresh anonymous package | 155 inventory entries; 247 tests pass; pre/post tree and ZIP anonymity scans pass |
| Reproducible paper PDF | two builds and tracked PDF share SHA-256 `35117a4a30261f7d9c04cdeedcf4edb0634722354509dc9b92da2f3d5acf2f3e` |
| Final ICLR/PDF check | clean-build preflight has zero findings; 10/10 rendered pages and anonymous metadata pass |

## Atomic trace state

- Public rows: 2,772.
- `PARTIAL/PROXY`: 2,719.
- `MISSING`: 38, all formal result cells requiring external execution.
- `CONFLICT`: 15, all mapped to the shared-reference gauge decision.
- Separate route-estimand conflict: `SC-ROUTE-002`.

The conservative matrix does not equate a section-level function/test with clause-level `EXACT`.
This prevents false completeness and leaves `GOAL_COMPLETE` blocked.

## External and author boundaries

- `SC-GAUGE-001` and `SC-ROUTE-002` require author decisions.
- No complete qualified formal dataset, independent RT calibration or shared-reference evidence.
- No second genuine C1-eligible model.
- No authenticated external-engine/controlled-real paired evidence.
- No Linux CUDA capacity or authorized formal compute budget.
- Four registered papers must be fetched locally and cannot be redistributed.
- No non-fixture scientific result exists; `SCIENTIFIC_EVIDENCE=NOT_ASSESSED`.

## Next single action

The authors must freeze `SC-GAUGE-001` and then `SC-ROUTE-002` in the V6 protocol. After both
decisions are reflected in config, code, tests and paper, obtain the non-fixture data/RT/model/license
and CUDA inputs listed above and run `prepare-full-run`. Until then, only the bounded smoke and
non-scientific pilot operations in `artifacts/formal_experiment_blockers.md` are authorized.
