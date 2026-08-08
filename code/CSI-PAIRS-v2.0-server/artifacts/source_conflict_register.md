# CSI-PAIRS V6 source conflict register

Date: 2026-08-08 (Asia/Shanghai)

Authority hashes:

- unique frozen V6 reader: `5866888fac736bcb812ebe3630b38095ad4989979a9fdf68cabcdbfe286f737e`
- integrated Goal prompt: `79b759141bd31a75fbefc80365ef5e6467e6cfedfa58457fa78b4ddebb4bb132`

The optional private matrix retains clause text. The tracked matrix records source line, document
hash, and clause hash without duplicating the authority prose into every row.

## Decisions that remain open

| ID | Sources | Conflict and estimand impact | Conservative implementation | Required author decision | Gate consequence |
|---|---|---|---|---|---|
| `SC-GAUGE-001` | reader lines 328-330; plan line 287; Goal lines 214-232 | Frozen V6 requires a world-independent shared RT clock/phase reference, with a phase-invariant fallback when that reference is unavailable. The Goal instead asks for a transform estimated from observable source CSI and applied to both siblings. A sample-derived complex reference changes the response target and may break direction symmetry; it is not an implementation detail. | The loader accepts only `shared_complex_reference`, requires one `phase_reference_id` per scene-position across siblings, rejects per-world fitting, and rejects the unimplemented fallback. No formal data is accepted without independent RT/reference evidence. | Choose exactly one registered P0 target: `(A)` world-independent shared RT complex reference; `(B)` a fully specified source-derived transform and inverse with anchor/fallback rules; or `(C)` a named phase-invariant representation. Freeze the choice before qualification. | `PAPER_PROTOCOL_GO=NO-GO`; `FORMAL_INPUT_READY=BLOCKED`; `LAUNCH_READY=BLOCKED`. |
| `SC-ROUTE-002` | reader lines 671-675 and 1044; plan lines 648-650 and 983-985; Goal lines 203-212 | Frozen V6 defines native mask-cover as complete-channel NMSE on full-channel `r^A=active` transitions, but defines the unified retained-state probe on query-level `r^{R,q}=active` patches. The Goal says raw-CSI Response primary inclusion must always be query-level. Replacing the native transition filter changes the registered G3/G4 response estimand. | Code preserves the two frozen estimands: native mask-cover uses physical-only `r^A`; patch training and the unified probe use physical-only `r^R`. Teacher sensitivity is an independent stratum and never selects either primary set. The paper now states the distinction. | Confirm whether the Goal intentionally replaces the frozen native full-channel estimand. If yes, define how active patches are assembled into a complete-channel score and its denominator before code changes. | `PAPER_PROTOCOL_GO=NO-GO`; `FORMAL_GO=NO-GO` until frozen. |

## Explicit amendment already applied

| ID | Sources | Resolution | Evidence |
|---|---|---|---|
| `SC-ROUTE-001` | frozen V6 joint physical/teacher active wording; Goal lines 203-212 | The later Goal explicitly removes teacher-dependent primary selection. Alignment uses full-channel physical distance, Response patch routing uses query-level physical distance, and teacher sensitivity is an independent audit/auxiliary stratum. | `formal_v2/formal_routing.py::PRIMARY_ROUTE_CONTRACT`; target-replacement and teacher-latent-replacement regression tests. |

No external input, fixture, or prose change can close `SC-GAUGE-001` or `SC-ROUTE-002`. They
require a protocol decision because each option changes the quantity being estimated.
