# CSI-PAIRS V6 formal implementation (V2.1)

This directory implements the frozen V6 protocol contract. It intentionally rejects the earlier V2.0 single-channel/full-vector schema.

Implemented code surfaces:

- seven-way source permission ledger and city/bank/base-map-cluster validation;
- strict embedded JSON, independent data regeneration, engine/config/license binding, typed maps/radio/path/no-op data;
- CSI-only 2D asymmetric MAE Stage-0 teacher with exact per-sample 75% masks resampled every step,
  independent B_audit_hold, sampler-bound checkpoints, and frozen physical readout;
- patch-level mask/query banks, separate full-channel Alignment and patch Response routes;
- shared F/P with complete teacher-encoder initialization, map/radio/BS-pose fusion, typed signed actions, latent and physical patch outputs;
- bank/route-stratified Endpoint, Alignment quartet, and Response objectives;
- one frozen source-method-selection pilot and canonical no-op Alignment tolerance;
- strict four arms with common batch plans, measured resource fields, and fail-closed seven-part G4;
- city-level k, heteroscedastic localization, exact V6 J_a, multilevel and bank-only bootstrap, leave-one sensitivity;
- active CGS plus gray/null distributions, unified response probes, q_comp/p_fail calibration, path matching/equivalence, external/scene-ID/resource/claim controls, independent RT calibration and external-validity adapters, literature/resource G0, and C1-C13/G0-G8 assembly;
- authenticated `waibu/` resource inventory, five source-only representation baselines, four map-conditioned six-condition adapters (currently one C1-eligible), and Sionna RT/large-radio-map facilities.

Unavailable data, external models, independent RT calibration, or unrun controls produce `NOT_ASSESSED/BLOCKED`. Code presence is not scientific evidence.

CLI stages are visible with:

```bash
python3 -m formal_v2.formal_cli --help
```

`all` is the complete evidence-chain orchestrator. It authenticates every local `waibu/` resource and runs the five representation baselines in addition to the verifier, first-party risk replay, external-baseline, resource-control, scene-ID, external-validity, literature, RT-calibration, shuffled-pair, and retention stages. Missing inputs fail at argument parsing; no independent stage is silently skipped. Fixtures remain `FORBIDDEN` at every artifact layer. Code and tests do not constitute scientific evidence.
G1 also writes a per-bank `route_noise_floor.csv` and requires all four route null thresholds to
cover the registered quantile of independent repeat-pair noise in their native alignment/response
and physical/latent norms. Overall repeat NMSE cannot substitute for this test.

The full-run root must be new, except that a single pre-staged `inputs/` directory is allowed for
authenticated Sionna scenes and other immutable run inputs; any existing result/stage file is rejected.
Individual stage commands atomically reserve their registered output path and hold an exclusive
operation lock for the run root, so concurrent, interrupted, or completed evidence directories
cannot be silently mixed or overwritten. Fixture paths are normalized to `.npz` before exclusive
creation.

`external_adapters/all_map_adapters_v1.json` registers SigMap, Wi-GATr, WiSER, and RFIR for the
same internally generated six-condition unit registry. `configs/representation_baselines_v1.json`
registers CSI-MAE, CSI-CLIP, CSI-CLIP++, ContraWiMAE, and WWM-inspired same-world prediction for
the unified localization comparison. Signal-only representation rows can never count toward C1.
WiSER is a style-controlled 2D map/CSI diagnostic and not a faithful implementation of the paper;
RFIR remains style-controlled because the data contract lacks its multi-view RGB 3DGS geometry stage.
Only Wi-GATr is currently C1-eligible, so C1 remains `BLOCKED` until a second authenticated,
faithful official-code or paper-spec adapter is supplied. The shipped
`configs/sionna_external_validity_adapter_v2.json` is the standard G8 adapter manifest.
See `WAIBU_INTEGRATION.md` and `external_adapters/README.md` for provenance and execution limits.

The repository ships first-party shuffled-pair, retention, scene-ID, and five resource-control
adapters with authenticated default manifests. Shuffled Alignment and Response models are trained
independently from deranged pair registries; retention probes are source-only and bind the frozen
Full checkpoint; scene-ID reuses the source-trained SigMap checkpoint and evaluates unseen source
banks; resource controls emit one checkpoint, log, loss trace, profiler summary, and replay record
per seed. Aggregate or self-reported substitutes remain rejected. Formal results are still absent,
so the controls are executable protocol surfaces rather than scientific evidence.

External evidence contracts are fail-closed. Scene-ID adapters must bind their implementation source
and trained checkpoint, cover each held-out position with one exact four-condition unit, and pass
base-map-cluster bootstrap intervals rather than row-level point estimates. RT calibration manifests
bind separate fit data, validation inputs, and an independent per-unit validation-reference CSV.
The adapter cannot receive the reference path; it emits per-unit simulated statistics and the outer
runner joins and recomputes all four C11 assessments. G8 adapters emit raw independent-engine CSI in
an exact NPZ contract; direction and effect are recomputed outside the adapter before cluster-macro
confidence intervals are evaluated. G0 requires one raw API receipt for every frozen database/query
pair plus authenticated PDF records. A G0 PASS never automatically proves C13: non-fixture C13
remains `REVIEW_REQUIRED`. Each validated input manifest is copied into its stage output and
reauthenticated during claim assembly.

Every stage records and reauthenticates the formal source-tree digest, requirements-lock digest,
Python/platform identity, installed-distribution RECORD digests, Torch/CUDA/GPU identity, and
determinism settings. The CLI enables deterministic Torch algorithms, disables TF32 and cuDNN
benchmarking, and refuses to combine gates produced by a different recorded runtime.

`scripts/build_server_bundle.sh` creates a deterministic internal research-delivery ZIP. It contains
delivery provenance and all locally supplied resources, so it is not an anonymous submission
artifact. `scripts/build_anonymous_supplement.sh` creates the separate deterministic anonymous
package and excludes `waibu/`, internal Git provenance, and identity-bearing delivery audits.

C1 rows bind the exact supplied map and directed action by SHA-256; the outer runner recomputes both
from the frozen unit registry and makes cluster-macro active-effect/null-equivalence decisions.
Shuffled-pair and retention controls use complete per-pair rows bound to the evaluation registry,
adapter source, independently trained control checkpoints, and exact formal checkpoints; aggregate
self-reported effects are rejected. Resource controls require frozen architecture/state specs,
per-step loss traces, operator-level profiler events, complete seed coverage, and a source-bound
replay. The resource scope excludes the common localization head from both main and control totals,
but includes concat bottleneck parameters and its measured training/inference FLOPs.
`generous_2x_concat` is report-only, not G4 subgate 7.

Use `make-fixture --source-banks-per-role 2` only when a software smoke must exercise the
cross-source-city scene-ID path. The generated data and every derivative remain permanently
`scientific_use=FORBIDDEN`.
