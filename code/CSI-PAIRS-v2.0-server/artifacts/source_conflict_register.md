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
| `SC-GAUGE-001` | reader lines 352-354 and 518; plan line 287; Goal lines 214-232 | `A`, confirmed 2026-08-08: use a world-independent shared RT complex reference. | The dataset carries one complex reference value, stable ID and source SHA per scene-position with no world axis. The loader rejects malformed records; the authenticated independent verifier must regenerate the references and referenced CSI before qualification. | Code, data contract and tests implement A. `PROTOCOL_READY=PASS`; `FORMAL_INPUT_READY` remains blocked until independent RT/reference regeneration passes. |
| `SC-ROUTE-002` | reader lines 962, 966 and 1506-1508; plan lines 648-650 and 983-985; Goal lines 203-212 | `R1`, confirmed 2026-08-08: retain two explicit Response estimands. | Native target-free mask-cover uses full-channel physical-only `r^A`; the unified retained-state probe uses query-level physical-only `r^{R,q}`. Teacher sensitivity remains an independent stratum. | Dedicated regression tests exercise both asymmetric route combinations so the two selectors cannot be collapsed silently. |

## Explicit amendment already applied

| ID | Sources | Resolution | Evidence |
|---|---|---|---|
| `SC-ROUTE-001` | frozen V6 joint physical/teacher active wording; Goal lines 203-212 | The later Goal explicitly removes teacher-dependent primary selection. Alignment uses full-channel physical distance, Response patch routing uses query-level physical distance, and teacher sensitivity is an independent audit/auxiliary stratum. | `formal_v2/formal_routing.py::PRIMARY_ROUTE_CONTRACT`; target-replacement and teacher-latent-replacement regression tests. |

No protocol conflict remains open. The A + R1 confirmation closes only the author-decision
blockers; formal data, independent RT evidence, executed external checkpoints, licenses and
compute remain separate launch requirements.
