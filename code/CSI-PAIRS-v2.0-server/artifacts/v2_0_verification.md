# CSI-PAIRS V2.1 code verification record

Date: 2026-08-05 UTC

Engineering status: `CODE_COMPILES_AND_PURE_SEMANTIC_TESTS_PASS`

Scientific status: `NO_GO_EVIDENCE_NOT_RUN`

This record supersedes the previous V2.0 dry-run report. Archived V1/V1.26 fixture outputs and numbers are traceability material only; they do not prove that the current `formal_v2` implementation executes correctly and cannot support a V6 claim.

## Checks actually run

| Check | Command | Result |
|---|---|---|
| Static compilation | `python3 -m py_compile formal_v2/*.py formal_v2/external_adapters/*.py formal_v2/tests/test_formal_v2.py` | PASS |
| Static lint | `ruff check formal_v2 --exclude formal_v2/external_adapters/vendor` | PASS |
| Pure schema/semantic tests | `python3 -m unittest discover -s formal_v2/tests -v` | 61/61 PASS |
| Vendored Wi-GATr integrity | `sha256sum --check VENDOR_SHA256SUMS` from the vendored snapshot root | 45/45 PASS |
| Fixture independent regeneration | `formal_cli verify-data` with `fixture_verifier.json` | PASS, `scientific_use=FORBIDDEN` |
| Fixture qualification | `formal_cli qualify` before the smoke-only batch reduction | expected FAIL on branch coverage, geometry-matched wrong-action coverage, and B_audit_hold reconstruction; the final batch-4 retry was SIGKILLed by the 2 GiB cgroup after writing Stage-0, so it is not recorded as a second gate result |
| Current-tree test-only four-arm execution | factorial with an authenticated temporary fixture gate and smoke batch 4 | 12 checkpoints completed; 13 state + 15 predictor calls/step; 95,289,024 dispatch-counted FLOPs/step for the common branch plan; G5 FAIL; all artifacts fixture/FORBIDDEN |
| Current-tree unified evaluation attempt | evaluation from the 12 fixture checkpoints | NOT COMPLETED: the 2 GiB verification cgroup sent SIGKILL before any evaluation artifact was emitted; this is not recorded as an evaluation PASS or FAIL |
| Claim mutation check | `formal_cli assemble-claims` | `INCOMPLETE_FAIL_CLOSED`; no C1-C13 support |
| Reproducible paper build | `paper_v2/build_reproducible.sh` | PASS, 10-page placeholder draft |
| Server bundle build and extraction | `build_server_bundle.sh`, followed by package-root SHA and unit checks | PASS; 117/117 package files authenticated and 61/61 extracted tests PASS |

The tests cover strict JSON, the seven-role permission ledger, downstream per-role regeneration blocking, target query-only denominators, typed maps/actions, 2D patch tiling, complete teacher-encoder initialization, BS-pose sensitivity, model input allowlist and batch isolation, dual outputs, empty conditional failure, city-level k, base-map-cluster macro utility, hierarchical bootstrap layers, gate/claim authentication, checkpoint hashes, q_comp order/complement, selection-frozen risk support, coverage monotonicity, path/no-op primitives, fail-closed control manifests, Wi-GATr power/mesh conversion, target-free inverse input, common six-condition units, and external execution-manifest mutation.

The test-only four-arm run is not qualification bypass evidence. It used `/tmp`, retained `fixture=true` and `scientific_use=FORBIDDEN`, and exists only to exercise code after the real fixture qualification correctly stopped. Endpoint/Alignment/Response/Full used identical branch plans and measured forward counts; disabled A/R terms had zero weighted gradient while their raw gradients remained nonzero. The first arm used PyTorch's dispatch FLOP counter and later isomorphic arm plans explicitly reused that measured FLOP value while independently measuring their forward-call counts.

An earlier pre-final test-only revision reached evaluation and path and failed G3/G5/G7, but those outputs are not claimed as current-tree verification. The current-tree evaluation retry was resource-blocked as stated above. No result from either run is scientific evidence.

## Explicitly not run

- independent RT regeneration;
- non-fixture Stage-0 teacher training or qualification;
- wrong-map models;
- non-fixture four-arm training or localization;
- non-fixture compatibility/response probes;
- q_comp or p_fail fitting;
- path mechanism analysis;
- equal-FLOP/concat controls;
- formal Wi-GATr 200k-step training/evaluation, a second map-conditioned external model, scene-ID, shuffled-pair, retention, resource-control, RT-calibration, literature-resource, or external-validity adapters;
- any non-fixture result-producing experiment.

Therefore no G0-G8 gate and no C1-C13 claim is promoted by this record. `NOT_ASSESSED` remains distinct from PASS.

## Remaining external inputs

Formal execution still requires a qualified non-fixture dataset, an independent renderer adapter and version/license binding, RT calibration evidence, installation and execution of the pinned Wi-GATr environment, a second actually executed map-conditioned model, resource-control implementations, and a second engine or controlled intervention for G8. The inherited No-X/null failures and the four named warnings remain binding until untouched non-fixture evidence replaces them through the registered gates.
