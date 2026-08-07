# CSI-PAIRS V6 Goal ledger

Last updated: 2026-08-08 (Asia/Shanghai)

## Immutable context

- Repository: `yiweinanzi/CSI`
- `BASE_SHA`: `eef3040c13264829cda1f4398009f691b52038ae`
- Branch: `codex/fix-formal-experiment-readiness`
- Draft PR: `https://github.com/yiweinanzi/CSI/pull/3`
- Starting PR head: `1f5c5fafa0fd76cf1a243f18fcb234c3418a08a6`
- `AUDITED_CODE_SHA`: `4074e98fe3c1d1ddccee79672f312b9111185992`
- Current remote PR head: `742ec70b88ef48e3179aa6a23f7cba482c846a5b` (latest repairs not pushed yet)

## Authority inputs

| Input | SHA-256 | Read state |
|---|---|---|
| Frozen V6 zero-background reader | `e6d19a65325b688b75472d9814dc9bae26b1d36e08db68cefedc1918696a635b` | complete |
| Frozen V6 complete research plan | `75f7e4e4ce82834216f9a8bf76fcd0785377c6de38aae62cabf4d1e88170dd4a` | complete |
| Integrated Goal prompt | `79b759141bd31a75fbefc80365ef5e6467e6cfedfa58457fa78b4ddebb4bb132` | complete |

The GitHub checkout is the only implementation source. Historical local implementations were not
copied or used to restore code.

## Current phase

`Final manifests, push, and clean remote re-review`

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

The last hypothesis-driven sweep found one additional P1: the main runtime could record but not
reject an internally consistent unlocked environment. The unified evidence context now requires
CPython 3.12, every exact pinned version and a nonempty installed-distribution RECORD digest. The
new version/missing-package/RECORD mutations pass.

The first remote-head replay then found the two delivery findings above. The dry-run wrapper now
requires exact exit `1` and reauthenticates the complete `DRY_RUN_FAIL_NOT_EVIDENCE`,
`passed=false`, fixture/FORBIDDEN state before it returns `0`. The anonymity scan ignores only the
two generic GitHub automation tokens while continuing to reject real authors, committers, emails,
repository owners, project SHAs, and personal paths. Both repairs have regression tests.

## Latest local verification

| Check | Result |
|---|---|
| Full unittest discovery | `258/258 PASS`, 123.402 s |
| Compilation, Ruff `E9,F`, `pip check` | PASS |
| CLI help | `25/25 PASS` (top level plus 24 subcommands) |
| Formal/smoke strict config | V2.3 V6 PASS |
| Shell syntax | 9/9 PASS |
| Wi-GATr vendor hash | PASS |
| ICLR preflight on clean paper build | zero findings |
| PDF render | 10/10 pages inspected; no overlap, clipping or identity metadata |
| Remote main drift | none after fetch; `origin/main` remains `BASE_SHA` |
| Anonymous exported-suite regression | PASS after fresh build/extraction; internal audit tooling absent |
| Pull-request merge-ref anonymity regression | PASS against the actual PR merge-ref committer identity |
| Deterministic server delivery | SHA-256 `e8c0713dfe04fb03a93c4d64588fe8269ba5e3809e4ee7e5d6f8d35ea9cde94f`; two byte-identical builds |
| Deterministic anonymous delivery | SHA-256 `3b4959ef147baab62997ad0225eed0b7c705e362e827c209ac054ad0ea300839`; two byte-identical builds |
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

Regenerate and verify the repository root `SHA256SUMS`, commit the delivery metadata, fetch and
confirm `origin/main` has not drifted, then push normally to PR #3 and repeat all required checks
from a fresh clone of the remote PR head.
