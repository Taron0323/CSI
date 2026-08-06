# CSI-PAIRS V6 formal implementation (V2.1)

This directory implements the frozen V6 protocol contract. It intentionally rejects the earlier V2.0 single-channel/full-vector schema.

Implemented code surfaces:

- seven-way source permission ledger and city/bank/base-map-cluster validation;
- strict embedded JSON, independent data regeneration, engine/config/license binding, typed maps/radio/path/no-op data;
- CSI-only 2D asymmetric MAE Stage-0 teacher, independent B_audit_hold, and frozen physical readout;
- patch-level mask/query banks, separate full-channel Alignment and patch Response routes;
- shared F/P with complete teacher-encoder initialization, map/radio/BS-pose fusion, typed signed actions, latent and physical patch outputs;
- bank/route-stratified Endpoint, Alignment quartet, and Response objectives;
- one frozen source-method-selection pilot and canonical no-op Alignment tolerance;
- strict four arms with common batch plans, measured resource fields, and fail-closed seven-part G4;
- city-level k, heteroscedastic localization, exact V6 J_a, multilevel and bank-only bootstrap, leave-one sensitivity;
- active CGS plus gray/null distributions, unified response probes, q_comp/p_fail calibration, path matching/equivalence, external/scene-ID/resource/claim controls, independent RT calibration and external-validity adapters, literature/resource G0, and C1-C13/G0-G8 assembly;
- authenticated `waibu/` resource inventory, five source-only representation baselines, four map-conditioned C1 adapters, and Sionna RT/large-radio-map facilities.

Unavailable data, external models, independent RT calibration, or unrun controls produce `NOT_ASSESSED/BLOCKED`. Code presence is not scientific evidence.

CLI stages are visible with:

```bash
python3 -m formal_v2.formal_cli --help
```

`all` is the complete evidence chain. It authenticates every local `waibu/` resource and runs the five representation baselines in addition to the verifier, risk archive, external-baseline, resource-control, scene-ID, external-validity, literature, RT-calibration, shuffled-pair, and retention stages. Missing inputs fail at argument parsing; no independent stage is silently skipped. Fixtures remain `FORBIDDEN` at every artifact layer. Code and tests do not constitute scientific evidence.

`external_adapters/all_map_adapters_v1.json` registers SigMap, Wi-GATr, WiSER, and RFIR for the
same internally generated six-condition unit registry. `configs/representation_baselines_v1.json`
registers CSI-MAE, CSI-CLIP, CSI-CLIP++, ContraWiMAE, and WWM-inspired same-world prediction for
the unified localization comparison. Signal-only representation rows can never count toward C1.
See `WAIBU_INTEGRATION.md` and `external_adapters/README.md` for provenance and execution limits.
