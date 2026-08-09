# Formal experiment blockers

Date: 2026-08-09 (Asia/Shanghai)

`PROTOCOL_READY=PASS`, `M4_DATA_PRODUCTION_READY=PASS`,
`EVIDENCE_REGISTRY_READY=YES`, and `FORMAL_CANDIDATE_READY=PASS_CANDIDATE_NOT_CLAIM`.
`FORMAL_INPUT_READY=BLOCKED`, `FORMAL_TRAINING_READY=NO`,
`LAUNCH_READY=BLOCKED`, and `SCIENTIFIC_EVIDENCE=NOT_ASSESSED`
remain mandatory until every open P0 row below closes.

| ID | Severity/type | Missing decision or input | Acceptance check | Consequence |
|---|---|---|---|---|
| `INPUT-RT-001` | P0 `EXTERNAL_DATA_REQUIRED` | Independent RT calibration fit/validation/reference manifests, shared reference evidence and raw rows. Reported candidate-data regeneration does not substitute for the separate calibration partitions. | `run-rt-calibration` plus G1 four-statistic/noise-floor checks pass. | C11 and qualification remain blocked. |
| `MODEL-C1-001` | P0 `COMPUTE_REQUIRED` | The shipped, licensed PMNet adapter is the second C1-eligible model, but its formal non-fixture checkpoint and authenticated six-condition execution are not yet available. | External-baseline V3 gate passes in every city for both shipped C1-eligible models, Wi-GATr and PMNet. | C1 remains blocked until both formal executions pass. |
| `INPUT-G8-001` | P0 `EXTERNAL_DATA_REQUIRED` | Licensed independent-engine scenes or controlled real paired intervention with registered active/null units. The shipped Sionna G8 adapter is deliberately rejected when the primary data also declare Sionna. | G8 V4 gate re-probes an actually independent runtime and passes cluster intervals. | C12 and external-validity wording remain blocked; same-Sionna evidence cannot close it. |
| `RESOURCE-001` | P0 `LICENSE_OR_ACCESS_REQUIRED` | Four nonredistributable papers must be fetched locally from registered URLs; all selected assets/checkpoints need permission records. | `fetch_waibu_resources` then `verify-waibu-resources`; compute-plan license acknowledgements match. | G0/full preflight remains blocked. |
| `COMPUTE-001` | P0 `COMPUTE_REQUIRED` | A prior handoff verified 2 x A100-SXM4-40GB with PyTorch 2.5.1+cu121, but the final branch must be installed on the destination host and supplied a reviewed disk, wall-time and GPU-hour budget. | Follow `formal_v2/A100_RUNBOOK.md`; formal compute-plan preflight passes actual GPU memory, driver, disk and budget checks. | Formal training is not authorized until destination-host preflight passes. |
| `RESULTS-001` | P0 `EXTERNAL_DATA_REQUIRED` | Authenticated non-fixture Response qualification, four-arm, two-city, controls and external runs. | Same-run gate chain and claim assembly pass; per-unit rows populate planned cells. | Scientific claims and submission-ready result panels remain absent. |

## Registered Conditional Data Findings

| ID | Registered at | Evidence and boundary |
|---|---|---|
| `INPUT-DATA-001-HISTORICAL` | Earlier M4 candidate-evidence delivery | `artifacts/m4_formal_candidate_v2/` records hashes and sizes for candidate `e5ec3d32...7847`. Static mode reports `external_artifacts=NOT_VERIFIED`; that historical record does not close current candidate readiness. |

## Closed candidate-data evidence

| ID | Closed at | Evidence and boundary |
|---|---|---|
| `INPUT-DATA-001` | latest main plus approved LLVM 22.1.8 | `artifacts/m4_llvm22_candidate_v1/candidate_evidence.json` binds candidate `e8903430...d2e`, 34/34 live zero-tolerance regeneration, all nine role groups and a relocated portable replay. This closes candidate-data ingestion only; G1/G2, independent RT, C1, G8 and A100 resource approval remain blocked. |

## Closed author protocol decisions

| ID | Decision | Existing implementation evidence |
|---|---|---|
| `SC-GAUGE-001` | `A`: freeze `shared_complex_reference` for the formal study. | `formal_dataset.py`, `DATA_CONTRACT.md`, the phase-gauge regression tests and `paper_v2/main.tex` already agree. |
| `SC-ROUTE-002` | `R1`: native full-channel Response remains on `r^A`; the unified patch probe remains on `r^{R,q}`. | `formal_routing.py`, qualification/evaluation tests, formal config and `paper_v2/main.tex` already agree. |

## Closed code-controlled blockers

| ID | Closed at | Evidence |
|---|---|---|
| `TRACE-001` | current delivery head | All 2,124 rows rebuild from the unique authority SHA `5866888f...`; table requirements are normative without keyword guessing, and source CI compares every regenerated row with the tracked artifact. |
| `LOCK-001` | `6b0ccdcfb4f03909ed377151ff906d9f0c162adf` | The CPython 3.12 lock contains complete reviewed wheel hashes for macOS 14+ arm64 and glibc 2.28+ Linux x86_64. Setup retains those exact wheels, installs offline without bytecode, and removes pip after its integrity check. Every evidence context walks the complete site-packages tree and compares it with the authenticated wheel-member union; unchanged inode/size/mode/mtime/ctime fingerprints may reuse a process-local digest, while any ordinary mutation forces a byte rehash. Mutable pip reports or installed RECORD files cannot replace the wheel trust root; extra distributions, files, startup hooks, symlinks, or bytecode fail closed. |

## Permitted work before closure

- `SMOKE_GO=GO`: CPU fixture, static checks, packaging and paper compilation only.
- `PILOT_GO=CONDITIONAL-GO`: disposable fixture/qualification diagnostics, no GPU, at most
  30 minutes wall time and 5 GiB output per run. Stop on any nonzero exit, manifest mismatch,
  route-coverage failure or null-safety failure. Every artifact remains `scientific_use=FORBIDDEN`.
- `FORMAL_GO=NO-GO`: do not start formal Stage-0, Wi-GATr training, four-arm training, two-city
  evaluation or G8 until every required external preflight row closes.
