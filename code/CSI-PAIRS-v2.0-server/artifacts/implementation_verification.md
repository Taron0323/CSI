# Current implementation verification

Date: 2026-08-08 (Asia/Shanghai)

- `BASE_SHA`: `eef3040c13264829cda1f4398009f691b52038ae`
- `AUDITED_CODE_SHA`: `4074e98fe3c1d1ddccee79672f312b9111185992`
- Branch: `codex/fix-formal-experiment-readiness`
- Draft PR: `https://github.com/yiweinanzi/CSI/pull/3`
- Environment: CPython 3.12.10, locked packages, macOS arm64, CPU-only

## Code verification at audited SHA

| Check | Result |
|---|---|
| Full unittest discovery | `258/258 PASS` in 123.402 s |
| Python compilation | PASS for core, adapters and tests |
| Ruff `E9,F` | PASS |
| Dependency health | `pip check` PASS |
| CLI help | `25/25 PASS` (top level plus 24 subcommands) |
| Strict config load | formal and smoke both `csi-pairs-formal-config-v2.3-v6` |
| Shell syntax | 9 scripts PASS |
| Wi-GATr vendor inventory | PASS |
| `git diff --check` | PASS |

Expected `error:` lines in the unittest log are failure-injection assertions. They do not denote
failed tests.

## Repairs covered by this record

- per-role source-city and global support/query isolation;
- dynamic per-city base-map-cluster qualification;
- physical-only primary routing and independent teacher strata;
- per-city Response, null and C1 decisions;
- exact action displacement and complete Holm families;
- safe, unique adapter identifiers and fail-closed resource exits;
- two-phase nonce/hash-bound human approval and full static compute preflight;
- main, Wi-GATr and Sionna runtime provenance, exact versions and RECORD authentication;
- complete stage inventories and same-run qualification/factorial/evaluation/control bindings;
- C8 G3/G4/G5 chain authentication and runtime re-probes;
- nonredistributable-resource exclusion and deterministic anonymous/internal deliveries;
- anonymous identity/Git/path scanner and CPU CI.
- anonymous export omits internal requirement-matrix tooling and proves the exported public test
  suite runs to completion after fresh extraction.
- bundle verification accepts only the fully authenticated expected fixture failure and never
  reclassifies it as a scientific PASS;
- pull-request merge-ref anonymity scanning ignores only GitHub's generic automation identity while
  retaining project author, committer, email, repository, SHA and personal-path checks.

## Final local delivery checks

| Check | Result |
|---|---|
| Server bundle reproducibility | Two byte-identical builds; SHA-256 `e8c0713dfe04fb03a93c4d64588fe8269ba5e3809e4ee7e5d6f8d35ea9cde94f` |
| Anonymous bundle reproducibility | Two byte-identical builds; SHA-256 `3b4959ef147baab62997ad0225eed0b7c705e362e827c209ac054ad0ea300839` |
| Bundle sidecars | All four generated sidecars verify |
| Fresh server extraction | Exact 174-entry inventory; 258 tests pass with one expected source-only Git-history test skipped |
| Fresh anonymous extraction | Exact 155-entry inventory; 247 tests pass; pre/post-test tree and ZIP anonymity scans pass |
| Anonymous exclusions | No internal matrix builder, internal audit test, audit artifacts, PDF, `.DS_Store`, bytecode or identity/path finding |
| Extracted server dry run | Outer verifier PASS after authenticating inner exit `1`, `passed=false`, `DRY_RUN_FAIL_NOT_EVIDENCE`, and fixture `scientific_use=FORBIDDEN` |
| Reproducible paper | Two byte-identical builds and tracked PDF share SHA-256 `35117a4a30261f7d9c04cdeedcf4edb0634722354509dc9b92da2f3d5acf2f3e` |
| ICLR preflight | Zero findings on the clean build directory containing the official style and build log |
| PDF visual/metadata review | 10/10 pages rendered; main text ends on page 8, references and appendix start on page 9; no clipping, overlap, identity metadata or author-bearing link |

The appendix's `PLANNED` cells are registered result-schema sentinels, not populated values or
claimed results. The startup guide, paper README and atomic matrix prohibit replacing them with
fixture, smoke, unit-test or expected values.

## Readiness verdict before remote-head replay

| Layer | Verdict | Boundary |
|---|---|---|
| `PACKAGE_INTEGRITY` | `PASS` | Deterministic local builds, sidecars and fresh extractions pass. |
| `SOFTWARE_READY` | `PASS` | No open reproduced code-level P0/P1 remains in the audited environment. |
| `V6_PROTOCOL_FIDELITY` | `BLOCKED` | `SC-GAUGE-001` and `SC-ROUTE-002` require author decisions. |
| `PAPER_PROTOCOL_READY` | `BLOCKED` | The paper is mechanically valid, but the two protocol conflicts prevent a scientific protocol GO. |
| `FORMAL_INPUT_READY` | `BLOCKED` | Formal data, RT/reference evidence, a second C1 model, licenses and authorized CUDA compute are absent. |
| `LAUNCH_READY` | `BLOCKED` | Software readiness alone cannot authorize formal execution. |
| `ANONYMOUS_RELEASE_READY` | `PASS` | Mechanical anonymous packaging passes; no scientific evidence is implied. |
| `SCIENTIFIC_EVIDENCE` | `NOT_ASSESSED` | No authenticated non-fixture result exists and no formal training was run. |

`SMOKE_GO=GO`, `PILOT_GO=CONDITIONAL-GO`, `FORMAL_GO=NO-GO`, and
`PAPER_PROTOCOL_GO=NO-GO`. Remote PR-head clean-clone verification remains mandatory after push.
