# Formal experiment blockers

Date: 2026-08-08 (Asia/Shanghai)

`PROTOCOL_READY=PASS`. `FORMAL_INPUT_READY=BLOCKED`, `LAUNCH_READY=BLOCKED`, and
`SCIENTIFIC_EVIDENCE=NOT_ASSESSED` remain mandatory until every P0 row below closes.

| ID | Severity/type | Missing decision or input | Acceptance check | Consequence |
|---|---|---|---|---|
| `INPUT-DATA-001` | P0 `EXTERNAL_DATA_REQUIRED` | Complete non-fixture V2.1 NPZ with seven source roles, two target cities, external role, independent repeats, clean CSI, immutable assets and per-city cluster minimums. | `inspect-data` and independent `verify-data` pass on untouched bytes. | G1-G8 cannot run. |
| `INPUT-RT-001` | P0 `EXTERNAL_DATA_REQUIRED` | Independent regeneration and RT calibration fit/validation manifests, shared reference evidence and raw rows. | `run-rt-calibration` plus G1 four-statistic/noise-floor checks pass. | C11 and qualification remain blocked. |
| `MODEL-C1-001` | P0 `LICENSE_OR_ACCESS_REQUIRED` | A second genuine C1-eligible map-conditioned model, checkpoint, source revision, license and executable six-condition adapter. | External-baseline V3 gate passes in every city for two distinct models. | C1 remains blocked. |
| `INPUT-G8-001` | P0 `EXTERNAL_DATA_REQUIRED` | Licensed independent-engine scenes or controlled real paired intervention with registered active/null units. | G8 V4 gate re-probes the runtime and passes cluster intervals. | C12 and external-validity wording remain blocked. |
| `RESOURCE-001` | P0 `LICENSE_OR_ACCESS_REQUIRED` | Four nonredistributable papers must be fetched locally from registered URLs; all selected assets/checkpoints need permission records. | `fetch_waibu_resources` then `verify-waibu-resources`; compute-plan license acknowledgements match. | G0/full preflight remains blocked. |
| `COMPUTE-001` | P0 `COMPUTE_REQUIRED` | Linux CUDA host, required Wi-GATr/Sionna runtimes, disk estimate, wall-time and authorized GPU-hour budget. | Formal compute-plan preflight passes actual GPU memory, driver, disk and budget checks. | Formal training is not authorized. |
| `RESULTS-001` | P0 `EXTERNAL_DATA_REQUIRED` | Authenticated non-fixture Response qualification, four-arm, two-city, controls and external runs. | Same-run gate chain and claim assembly pass; per-unit rows populate planned cells. | Scientific claims and submission-ready result panels remain absent. |

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
