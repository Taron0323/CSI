# Collaborator-code invariant ledger

Baseline: `eef3040c13264829cda1f4398009f691b52038ae` (`yiweinanzi/CSI:main` at task start)

Branch: `codex/fix-formal-experiment-readiness`

## Preserved boundaries

| Invariant | Required boundary | Current repair effect | Verdict |
|---|---|---|---|
| Module ownership | Dataset, teacher, routing, F/P model, factorial training, evaluation, risk, path, external controls, and claims remain separate | Repairs extend the existing modules and CLI; no replacement framework or second implementation was introduced | Preserved |
| Dependency direction | Core data/model code must not depend on adapter implementations | Adapters and runtime probes depend on `formal_v2`; core modules do not import Wi-GATr or Sionna adapters | Preserved |
| Public CLI | Existing stage names retain their scientific meaning; new authorization must not bypass a stage | `prepare-full-run`, external approval, and `all` make the prior stop point explicit; the Boolean approval flag has no authority | Fail-closed extension |
| Dataset schema | World banks, roles, support/query isolation, CSI layout, actions, provenance, and output paths retain their meanings | Validation is stricter for per-role city coverage, canonical clusters, phase reference identity, and cross-bank support exclusion | Compatible validation hardening |
| Checkpoint schema | Teacher/factorial/control checkpoints bind source, config, seed, plan, and runtime | Existing payload roles remain; stale or weak payloads are rejected | Compatible authentication hardening |
| F/P information budget | No-position F/P cannot receive receiver position, target CSI, route, target statistics, or IDs | Input allowlists and mutation tests are unchanged or stricter; oracle-x remains a separate diagnostic path | Preserved |
| Teacher role | Teacher is CSI-only, frozen, and auxiliary to the physical target | Teacher sensitivity no longer selects primary raw-CSI routes; target replacement cannot change source-only artifacts | V6 Goal amendment, no model-input expansion |
| Route semantics | Direction-invariant physical routes select losses/evaluation; route is never a model input | Alignment and patch Response routes are physical-only; native full-channel versus unified patch estimands remain separately registered pending `SC-ROUTE-002` | Preserved with declared author decision |
| Four-arm design | Endpoint/A/R/Full share initialization, data, branch plan, masks, steps, downstream head, and information budget | Approval and evidence changes do not alter arm architecture or loss switches | Preserved |
| Statistical unit | Scene bank/base-map foundation is the highest independent data unit; seeds/draws propagate uncertainty without inflating n | City-specific gates, canonical duplicate resistance, Holm family, and synchronized bootstrap are stricter | Preserved and hardened |
| Claim promotion | Fixture, smoke, self-report, stale hash, missing dependency, and `NOT_ASSESSED` cannot promote G0-G8 or C1-C13 | C8 now reauthenticates G3/G4/G5; all downstream gates bind current inputs and runtime | Preserved and hardened |
| External code | Vendored/official bytes are not silently edited; controlled implementations are labeled accurately | Runtime and source hashes are recorded independently; nonredistributable papers are removed from release tracking | Preserved |
| Artifact ownership | Existing evidence cannot be overwritten, mixed across runs, or certified after partial failure | Atomic stage reservations, run-root locks, nonce-bound approval, and paired matrix publication reject reuse/races | Preserved and hardened |

## Principle-level change assessment

No collaborator model architecture, loss estimand, data role, information allowlist, or public
artifact meaning was silently replaced. Physical-only primary routing is the explicit later Goal
amendment. The two unresolved changes that would alter an estimand are not implemented and are
recorded in `artifacts/source_conflict_register.md`.
