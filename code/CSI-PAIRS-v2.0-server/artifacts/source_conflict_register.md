# CSI-PAIRS V6 source conflict register

Date: 2026-08-08 (Asia/Shanghai)

Authority hashes:

- unique frozen V6 reader: `5866888fac736bcb812ebe3630b38095ad4989979a9fdf68cabcdbfe286f737e`
- integrated Goal prompt: `79b759141bd31a75fbefc80365ef5e6467e6cfedfa58457fa78b4ddebb4bb132`

The optional private matrix retains clause text. The tracked matrix records source line, document
hash, and clause hash without duplicating the authority prose into every row.

## Frozen author decisions

| ID | Sources | Author decision | Frozen protocol | Evidence and gate effect |
|---|---|---|---|---|
| `SC-GAUGE-001` | reader lines 328-330; plan line 287; Goal lines 214-232 | `A`, confirmed 2026-08-08: use a world-independent shared RT complex reference. | The loader accepts only `shared_complex_reference`, requires one `phase_reference_id` per scene-position across siblings, and rejects per-world fitting or an unregistered phase-invariant target. | Code, data contract, tests and paper already implement A. `PROTOCOL_READY=PASS`; independent RT/reference evidence remains an external input requirement. |
| `SC-ROUTE-002` | reader lines 671-675 and 1044; plan lines 648-650 and 983-985; Goal lines 203-212 | `R1`, confirmed 2026-08-08: retain two explicit Response estimands. | Native target-free mask-cover uses full-channel physical-only `r^A`; the unified retained-state probe uses query-level physical-only `r^{R,q}`. Teacher sensitivity remains an independent stratum. | Code, configuration, tests and paper already implement R1. The author-decision blocker is closed without changing training or evaluation semantics. |

## Explicit amendment already applied

| ID | Sources | Resolution | Evidence |
|---|---|---|---|
| `SC-ROUTE-001` | frozen V6 joint physical/teacher active wording; Goal lines 203-212 | The later Goal explicitly removes teacher-dependent primary selection. Alignment uses full-channel physical distance, Response patch routing uses query-level physical distance, and teacher sensitivity is an independent audit/auxiliary stratum. | `formal_v2/formal_routing.py::PRIMARY_ROUTE_CONTRACT`; target-replacement and teacher-latent-replacement regression tests. |

No protocol conflict remains open. The A + R1 confirmation closes only the author-decision
blockers; formal data, independent RT evidence, external models, licenses and compute remain
separate launch requirements.
