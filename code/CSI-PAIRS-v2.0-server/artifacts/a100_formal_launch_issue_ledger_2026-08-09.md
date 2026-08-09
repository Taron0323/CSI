# A100 formal-launch P0/P1 ledger

Date: 2026-08-09 (Asia/Shanghai)

Baseline: `origin/main@790053c44ac5cb3792ec87f72554bf2bb5ac42c4`

This ledger covers only issues that can block the first authenticated formal
gate chain or invalidate its evidence. It does not promote smoke, fixture,
diagnostic replay, or candidate artifacts to scientific evidence.

| ID | Severity | Reproduction/evidence | Impact | Minimal repair and acceptance | State |
|---|---|---|---|---|---|
| `HOTPATH-RESOURCE-001` | P1 code | `test_resource_localization_authentication_is_constant_in_result_rows` runs 1 and 10,000 result rows while asserting zero inner-loop file hashes and evidence-context calls. | Historical `O(rows * dataset/runtime)` cost made controls impractical. | Compute evidence once at the control boundary and pass immutable values into localization evaluation. | `CLOSED_ON_BASELINE` |
| `RT-INDEPENDENCE-001` | P0 science/code | Adversarial tests cover renamed IDs, copied bytes, payload/source mismatch, canonical key order, equal measurements from distinct units, and the same raw unit under another wrapper. | Fit/validation reuse could falsely support C11. | Bind authenticated source asset, batch, record, and raw-unit identity and reject identity overlap. | `CLOSED_ON_BASELINE` |
| `DATA-VISIBILITY-001` | P0 data/protocol | `artifacts/m4_llvm22_candidate_v1/candidate_evidence.json` records hashes and a reported 34-bank inventory, but the candidate NPZ and original manifests are external. | Static registry validation cannot authenticate omitted bytes or prove that the reported inspection ran. | Deep-verify every original external artifact, then run live verification on the destination from the approved runtime and current source. | `REGISTRY_INGESTED_EXTERNAL_DEEP_VERIFICATION_REQUIRED` |
| `DATA-REGEN-001` | P0 data/runtime | The registry reports a 34-bank LLVM 22.1.8 exact regeneration and commits its receipt digest, but not the regenerated NPZ, origin bundle, or runtime evidence. | Editable hash commitments and a precomputed replay cannot authenticate an omitted execution. | Authenticate the external originals and execute live independent regeneration with approved runtime/source binding. | `REGISTRY_INGESTED_EXTERNAL_DEEP_VERIFICATION_REQUIRED` |
| `DATA-REPLAY-REGISTRY-001` | P1 science/code | Portable replay verifies registered receipt fields and zero-tolerance array equality. | It establishes transferred-content integrity only; the same arrays can be supplied as both candidate and regeneration output. | Keep replay `DIAGNOSTIC_NOT_CLAIM`; only live independent regeneration may satisfy the formal data gate. | `CLOSED_IN_CODE_DIAGNOSTIC_ONLY` |
| `DATA-EXPORT-REGISTRATION-001` | P1 execution/code | Export previously required consumer registration before the new receipt could exist in a registry. | First portable export could not complete. | Export skips only prior registration while retaining receipt, dataset, archive, runtime, and zero-tolerance validation; consumer replay still requires exact registry membership. | `CLOSED_IN_CODE_AND_REGRESSION` |
| `DATA-METADATA-001` | P0 code/data | A failed or reported candidate could otherwise be mistaken for formal input. | Candidate metadata could bypass qualification. | The generator emits `scientific_use=CANDIDATE`; only authenticated live verification can promote role evidence. | `CLOSED_IN_CODE_OLD_DATA_QUARANTINED` |
| `PATH-ID-001` | P0 science/data | Scene 12, world 0, receiver 27 exposed an incomplete historical identity. | Rendering could stop before a complete candidate exists. | Coalesce identical complete records with power preserved, retain fatal digest collisions, and re-run the live candidate gate. | `CLOSED_IN_CODE_LIVE_CANDIDATE_REVIEW_PENDING` |
| `DATA-PROMOTION-001` | P0 code/protocol | Promotion requires authenticated live data verification followed by G1 and G2. | A diagnostic receipt must not enter factorial execution. | `require_data_verification` and role verification reject precomputed replay modes. | `CLOSED_IN_CODE_AND_REGRESSION` |
| `DATA-CLUSTER-001` | P0 science/data | Frozen OSM replay found overlapping Boston target extents. | Overlapping regions could be mislabeled as independent clusters. | Admit only disjoint 256 m scene extents while preserving frozen score order. | `CLOSED_IN_CODE_AND_FROZEN_OSM_REPLAY` |
| `SUITE-FINAL-001` | P1 code | Earlier heads passed their own test/package checks; this integration changes verifier semantics, manifests, and packaging. | Prior CI status does not certify this exact head. | Require local focused/full checks and hosted `test-and-package` on the pushed merge head. | `LOCAL_VERIFICATION_PENDING_EXACT_HEAD_GITHUB_CHECK_REQUIRED` |
| `M4-BACKEND-COMPAT-001` | P1 code/runtime | LLVM 18.1.8 and 22.1.8 digests are registered. The proposed CUDA diagnostic depended on unprovisioned, unhashed OptiX/driver paths and inherited injection-capable environment variables. | Such a CUDA run could appear authenticated without an authenticated runtime closure. | Preserve the audited LLVM diagnostic; expose CUDA only after setup provisions and hashes the complete CUDA/OptiX closure and sanitizes inherited loader paths. | `LLVM_CLOSED_CUDA_INTENTIONALLY_UNAVAILABLE` |
| `M4-EVIDENCE-BINDING-001` | P1 code/evidence | Fresh manifests now bind asset path/hash and run/process IDs; the repository comparator dependency is restored. The comparator previously based PASS only on `csi_clean`. | Drift in another required array could be ignored. | Compare every required array for presence, shape, dtype, finiteness, and exact equality; bind asset/generator/renderer/runtime/output bytes. | `CLOSED_IN_CODE_FRESH_LIVE_EVIDENCE_REQUIRED` |
| `GPU-SCHEDULER-001` | P1 code/runtime | Tests cover ordered 4 arms x 3 seeds scheduling and the 12-job fixture chain. | Destination peak memory remains unknown. | Run destination-host runtime and memory preflight. | `CODE_CLOSED_HOST_PREFLIGHT_PENDING` |
| `CUDA12-DELIVERY-001` | P1 packaging/runtime | A100 evidence records PyTorch 2.5.1+cu121, CUDA 12.1, and NCCL 2.21.5. | Main must reproduce the reviewed A100 runtime. | Use the platform-selected CUDA 12.1 hash lock and validate the runtime closure. | `CLOSED_IN_CODE_HOST_REINSTALL_PENDING` |
| `G8-INTERFACE-001` | P0 science/code | The shipped Sionna adapter is not independent when primary data also use Sionna. | Same-engine evidence cannot establish G8. | Keep archive interchange diagnostic-only and add an authenticated independent executable adapter or controlled intervention. | `CODE_FAIL_CLOSED_EXTERNAL_ADAPTER_REQUIRED` |
| `FORMAL-INPUT-001` | P0 external input | Candidate registries are present, but external candidate bytes and live verification are not repository-verifiable. Independent RT, model, license, G8, and A100 inputs are also absent. | The candidate cannot enter formal gates. | Deep-verify the external originals, run approved live regeneration, then satisfy every remaining input and host gate. | `BLOCKED_EXTERNAL_DEEP_VERIFICATION_AND_INPUTS_REQUIRED` |

## Current launch boundary

- `PACKAGE_INTEGRITY`: local integration verification pending; exact-head hosted check required.
- `SOFTWARE_READY`: `CONDITIONAL_ON_REQUIRED_EXACT_HEAD_CHECKS`.
- `PROTOCOL_READY`: `PASS` (`A + R1`).
- `M4_DATA_PRODUCTION_READY`: `REPORTED`.
- `EVIDENCE_REGISTRY_READY`: `YES`.
- `FORMAL_CANDIDATE_READY`: `EXTERNAL_DEEP_VERIFICATION_REQUIRED`.
- `FORMAL_INPUT_READY`: `BLOCKED`.
- `FORMAL_TRAINING_READY`: `NO`.
- `LAUNCH_READY`: `BLOCKED`.
- `SCIENTIFIC_EVIDENCE`: `NOT_ASSESSED`.
