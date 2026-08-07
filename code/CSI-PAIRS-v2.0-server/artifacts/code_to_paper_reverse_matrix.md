# Code-to-paper reverse matrix

Date: 2026-08-08 (Asia/Shanghai)

Audited code: `7560120ca588c2cce76507116d58ed98c49895bf`

Every public CLI entry is listed below. `FORBIDDEN` means that an output cannot enter a paper claim;
`CANDIDATE` means it must still pass its registered scientific gate and claim assembly.

| CLI entry | Registered semantic role | Principal output | Paper/protocol basis | Evidence ceiling before formal execution |
|---|---|---|---|---|
| `make-fixture` | Generate a schema-complete software fixture | NPZ fixture | Reproducibility only | `FORBIDDEN` |
| `inspect-data` | Validate and report the data contract | data-contract JSON | Sec. 3; App. B | Inspection, not evidence |
| `verify-waibu-resources` | Authenticate all local external inputs | resource gate/manifest | G0; reproducibility | Byte identity only |
| `export-sionna-scenes` | Export registered worlds for independent RT | scene manifest and assets | G8 | `CANDIDATE` after license and hash checks |
| `create-run-approval` | Materialize explicit human attestation | external approval JSON | Sec. 7 launch rule | Authorization only |
| `verify-data` | Run independent regeneration verifier | data-verification gate | G1 prerequisite | `CANDIDATE` |
| `qualify` | Train/audit teacher and run G1/G2 Response gate | qualification gate | Secs. 3.3, 4, 7 | Fixture `FORBIDDEN`; formal gate required |
| `run-wrong-map` | Native six-condition diagnostic | per-unit rows and gate | Fig. 1; Sec. 6.2 | Diagnostic, not C1 by itself |
| `run-factorial` | Execute Endpoint/A/R/Full with shared plan | checkpoints and factorial gate | Sec. 4.5; Table 1 | `CANDIDATE` after G1/G2 |
| `run-evaluation` | Evaluate native skills and two-city localization | evaluation gate | Sec. 6.4; Tables 3-4 | `CANDIDATE` |
| `run-risk` | Fit/evaluate paired-proposal risk | G6 gate | RQ5; Sec. 6.4 | `CANDIDATE` |
| `run-path` | Audit registered path mechanism | G7 gate | mechanism boundary | `CANDIDATE` |
| `run-external-baselines` | Run common-unit map-conditioned adapters | C1 gate | RQ1; Fig. 1 | Blocked until two eligible models pass |
| `run-representation-baselines` | Run source-only representation baselines | baseline records | Related work/control suite | Comparison only |
| `run-resource-controls` | Run five equal-resource/concat controls | control gate | G4; Table 1 | `CANDIDATE` |
| `run-scene-id-audit` | Test scene/variant identity shortcut | C2 gate | Secs. 3.2, 6.3 | `CANDIDATE` |
| `run-external-validity` | Retrace registered external scenes | G8 gate | Sec. 7 | Blocked until independent input/runtime exists |
| `run-literature-resources` | Authenticate literature/resource review | G0 gate | G0 | Human review still required for C13 |
| `run-rt-calibration` | Validate independent RT calibration | C11 gate | G1/G8 boundary | Blocked until fit/validation inputs exist |
| `run-shuffled-pair-control` | Train and evaluate shuffled-pair control | C4 dependency | Table 1 | `CANDIDATE` |
| `run-retention-audit` | Test retained-state dependence | C6 dependency | Fig. 2; App. D | `CANDIDATE` |
| `assemble-claims` | Reauthenticate all gates and promote C1-C13 | claim matrix | App. D | Fail closed |
| `prepare-full-run` | Preflight all late inputs; run G0/RT/G1/G2; stop | approval request | Fig. 3; Sec. 7 | No late-stage authorization |
| `all` | Resume the exact approved root and run remaining stages | root manifest | Fig. 3; Sec. 7 | Requires bound, unexpired, single-use approval |

## Public contracts

| Surface | Frozen contract | Compatibility result |
|---|---|---|
| Config | `csi-pairs-formal-config-v2.3-v6` | Older V2.2 formal configs are rejected rather than guessed. |
| Dataset | `csi-pairs-formal-dataset-v2.1-v6` | Existing fields retain meaning; validation is stricter. |
| Qualification | `csi-pairs-formal-qualification-gate-v3-v6` | Adds physical-only route identity and authenticated prerequisites. |
| Factorial | `csi-pairs-formal-factorial-gate-v2.1-v6` | Binds the exact qualification gate. |
| Evaluation | `csi-pairs-v6-evaluation-gate-v3` | Binds qualification and factorial gates and per-city decisions. |
| Controls | V3 resource-control gate | Binds factorial and evaluation gates. |
| External map models | external-baseline gate V3 | Requires per-city C1 success and exact runtime evidence. |
| External validity | G8 gate V4 | Requires exact Sionna runtime reprobe and raw-CSI recomputation. |
| Root artifact | formal root manifest V2.1 | Authenticates a complete, non-symlinked stage inventory. |

The reverse matrix found no reachable command that can promote fixture output, skip a registered
stage, or bypass the two-phase approval at the audited commit. This statement is limited to the
tested environment and does not assert that formal inputs or scientific gates pass.
