# CSI-PAIRS V6 Goal ledger

Last updated: 2026-08-08 (Asia/Shanghai)

## Immutable context

- Repository: `yiweinanzi/CSI`
- `BASE_SHA`: `bf5764afb52cc5c29fd41f230b66f9d869dfb8cb`
- Branch: `codex/freeze-a-r1-protocols`
- Previous repair PR: `https://github.com/yiweinanzi/CSI/pull/4` (merged)
- Initial repair commit: `6fbfea3da3fbb6d95603914c473ca950ab4c2407`
- Last exact-head CI SHA: `853a369447618a11c3384342ab38f8f53734dcb0`

## Authority inputs

| Input | SHA-256 | Read state |
|---|---|---|
| Unique frozen V6 reader | `5866888fac736bcb812ebe3630b38095ad4989979a9fdf68cabcdbfe286f737e` | complete |
| Integrated Goal prompt (superseded) | `79b759141bd31a75fbefc80365ef5e6467e6cfedfa58457fa78b4ddebb4bb132` | complete |
| Active Goal continuation prompt | `7ddb84cdb605428409b0f38b7d8d58f1d6f169b8c4a0aa7cd20024fbe638173c` | complete |

The GitHub checkout is the only implementation source. Historical local implementations were not
copied or used to restore code.

## Current phase

`Author-frozen protocol decisions and external-input handoff`

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
- GitHub-hosted runners deprecating the Node 20 runtime used by floating legacy action majors; the
  workflow now pins the current official Node 24 checkout/setup-python release commits.
- version-only dependencies and self-reported runtime provenance; installation now accepts only the
  reviewed macOS arm64 or Linux x86_64 wheel hashes, and evidence reauthenticates the pip receipt,
  installed RECORD files, interpreter/platform floor, source tree, and deterministic Torch state.
- section-level atomic trace fallbacks; all normative clauses now resolve through an explicit
  semantic evidence family plus their exact clause SHA, while unknown subsections, formal-result
rows and external-input boundaries remain fail closed. Author decision A + R1 is now frozen.

The last supply-chain sweep found that the main runtime could record but not reject an internally
consistent unlocked environment. The unified evidence context now requires CPython 3.12, an exact
supported platform, a hash-locked wheel receipt, exact versions, per-distribution RECORD digests,
installed-file hash/size agreement, and deterministic Torch/CUBLAS settings. Wheel, receipt,
version, missing-package, RECORD, installed-file, platform, and determinism mutations pass.

The first remote-head replay found the two delivery findings above. The dry-run wrapper now
requires exact exit `1` and reauthenticates the complete `DRY_RUN_FAIL_NOT_EVIDENCE`,
`passed=false`, fixture/FORBIDDEN state before it returns `0`. The anonymity scan ignores only the
two generic GitHub automation tokens while continuing to reject real authors, committers, emails,
repository owners, project SHAs, and personal paths. Both repairs have regression tests.

The second remote-head replay completed every assertion but GitHub Actions reported two
`TimeoutExpired` errors: the extracted anonymous public suite and the complete fixture dry-run took
longer than 120 seconds on the hosted Linux CPU. Their subprocess bounds are now 300 seconds. The
targeted tests pass locally in 63.532 and 51.993 seconds, and the then-current complete 258-test
suite passes after the repair.

## Latest local verification

| Check | Result |
|---|---|
| Full unittest discovery | `293/293 PASS`, 453.520 s at exact head `853a369` |
| Compilation, Ruff 0.16.2 `E9,F`, `pip check` | PASS; Ruff is isolated from the formal runtime lock |
| CLI help | `25/25 PASS` (top level plus 24 subcommands) |
| Formal/smoke strict config | V2.3 V6 PASS |
| Shell syntax | 8/8 PASS |
| Wi-GATr vendor hash | PASS |
| ICLR preflight on clean paper build | zero findings |
| PDF render | 10/10 pages inspected; no overlap, clipping or identity metadata |
| Remote main drift | branch created directly from `origin/main` at `BASE_SHA` |
| Hosted Linux CPU CI | `test-and-package` PASS at exact head `853a369` ([run 31254239881](https://github.com/yiweinanzi/CSI/actions/runs/31254239881)); 293 tests pass in 1255.989 s |
| CI action supply chain | official `checkout@v7.0.1` and `setup-python@v7.0.0` commits pinned; both use Node 24 |
| Anonymous exported-suite regression | PASS after fresh build/extraction; internal audit tooling absent |
| Pull-request merge-ref anonymity regression | PASS against the actual PR merge-ref committer identity |
| Deterministic server delivery | Two byte-identical builds and both sidecars pass in exact-head CI; the temporary digest is not retained by the workflow log |
| Deterministic anonymous delivery | Two byte-identical builds and both sidecars pass in exact-head CI; the temporary digest is not retained by the workflow log |
| Fresh server package | Extracted server verification passes in exact-head CI, including authenticated fixture failure without claim promotion |
| Fresh anonymous package | Extracted anonymous full-suite replay and anonymity scans pass in exact-head CI |
| Reproducible paper PDF | two builds and tracked PDF share SHA-256 `35117a4a30261f7d9c04cdeedcf4edb0634722354509dc9b92da2f3d5acf2f3e` |
| Final ICLR/PDF check | clean-build preflight has zero findings; 10/10 rendered pages and anonymous metadata pass |

## Atomic trace state

- Public rows: 2,124, all derived from the unique frozen V6 reader.
- `EXACT`: 837 software-protocol clauses with explicit semantic-family evidence.
- `PARTIAL/PROXY`: 1,268: 1,080 non-normative context rows, 161 external-data rows, and
  27 license/access rows.
- `MISSING`: 19, all formal result cells requiring external execution.
- `CONFLICT`: 0 after the A + R1 author decision.

The registry has no section-level fallback: every normative row binds a semantic family and exact
clause SHA, and unknown normative subsections fail generation. RQ and claim-gate clauses mentioning
`q_comp` or `p_fail` retain their external-evidence boundary rather than being promoted by a keyword.
`GOAL_COMPLETE` remains blocked by the external conditions below, not a code trace backlog.

## External boundaries

- No complete qualified formal dataset, independent RT calibration or shared-reference evidence.
- Both genuine C1-eligible adapters are shipped, but neither has authenticated non-fixture checkpoint/results in this delivery.
- No authenticated external-engine/controlled-real paired evidence.
- No Linux CUDA capacity or authorized formal compute budget.
- Four registered papers must be fetched locally and cannot be redistributed.
- No non-fixture scientific result exists; `SCIENTIFIC_EVIDENCE=NOT_ASSESSED`.

## Next single action

Regenerate the requirement matrix and repository SHA inventory, run the affected audit tests, and
require exact-head CI. Formal execution remains unauthorized until every external input in
`artifacts/formal_experiment_blockers.md` is closed.
