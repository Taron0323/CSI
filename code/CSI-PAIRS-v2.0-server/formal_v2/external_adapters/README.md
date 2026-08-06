# External Baseline Adapters

These adapters implement the frozen V6 Section 1.1 six-condition audit. An adapter is
scientific evidence only after its source, command, checkpoint, result file, dataset, config,
and stage manifest hashes all authenticate and at least two distinct map-conditioned models pass.

## Frozen adapter set

`all_map_adapters_v1.json` contains four distinct map-conditioned methods:

| Model | Implementation | Native training target | Six-condition localization |
|---|---|---|---|
| SigMap | V6 style-controlled map+CSI locator | source position | direct map-conditioned estimate |
| Wi-GATr | official-code adaptation | total received power | inverse coordinate optimization |
| WiSER | paper-spec controlled implementation | radiomap power + DETR-style CIR taps | frozen forward-model inverse search |
| RFIR | paper-spec controlled 2.5D RF-BSDF implementation | complex field + received power | frozen inverse-renderer search |

All four train on `source_encoder_train`, select on `source_method_selection`, and evaluate only
`source_final_unseen_bank` plus target `query` positions. Every adapter emits a source-only training
record, selected checkpoint, exact config, result rows, and hashes. Missing environments resolve to
`not_executed`; they do not abort into a false PASS.

WiSER and RFIR have no source archive in `waibu/`, so the code must never be called an official
implementation or faithful reproduction. SigMap has no supplied paper file and is deliberately
weaker-labelled `style-controlled-implementation`.

## Wi-GATr

`wigatr_adapter.py` adapts the official Wi-GATr implementation from Hehn et al. (ICLR 2025,
arXiv:2406.14995v2). Its evidence label is `official-code-adaptation`, not `faithful reproduction`:
the tokenizer and GATr architecture are official, while CSI-PAIRS supplies a deterministic 2.5D
grid-to-mesh conversion and a different source-domain dataset.

The retained paper semantics are:

- one token per triangular mesh face, with material one-hot scalars;
- Tx, Rx, and Tx-Rx link tokens;
- the official `kitchen_sink_z` geometric-algebra embedding;
- 32 GATr blocks, 16 hidden multivector channels, 32 hidden scalar channels, 8 heads, and
  multi-query attention;
- scalar total received-power regression with MSE, Adam at `1e-3`, batch 64, cosine decay,
  and the paper's 200,000-step WiPTR dose;
- frozen-model inverse localization by optimizing receiver coordinates against observed power.

CSI-PAIRS-specific deterministic adaptations are:

- occupied 2.5D cells are extruded to their height and triangulated; exposed sides and top faces
  retain the categorical material ID;
- real-then-imag CSI is reduced to
  `10 log10(mean(real^2 + imag^2))`; the affine scale is fitted on
  `source_encoder_train` only;
- training uses `source_encoder_train`; checkpoint selection uses
  `source_method_selection`; evaluation uses only `source_final_unseen_bank` and target query
  positions;
- target localization initializes from the public map extent, never from target coordinates,
  fingerprints, target normalization, support positions, or labels;
- each eligible observation has the same frozen CSI/radio context under `correct`,
  `paired_active_alternative`, `paired_null_alternative`, `wrong_city`,
  `geometry_destroyed`, and `empty` maps.

The adapter rejects varying carrier/antenna configurations because the paper's regression model
assumes one fixed wireless configuration. It reports localization error only. It does not add a CSI
prediction head and cannot support a full-channel response claim.

### Environment

The official snapshot requires Python 3.10 and git-pinned GATr/WiInSim dependencies:

```bash
formal_v2/external_adapters/setup_wigatr.sh
```

The setup is intentionally separate from the core V2.1 environment. If the pinned dependencies
cannot be installed, the adapter fails and remains `not_executed`; no substitute model is used.

### Formal execution

1. Run the complete `all_map_adapters_v1.json`; its Wi-GATr command points to the default environment.
2. Run `formal_cli all` or `formal_cli run-external-baselines` after data verification,
   qualification, factorial training, and evaluation have produced their authenticated artifacts.

Fixture runs remain `scientific_use=FORBIDDEN`, even if the adapter exits successfully.

## Representation baselines

The separate `formal_representation_baselines.py` stage runs CSI-MAE, CSI-CLIP, CSI-CLIP++,
ContraWiMAE, and WWM-inspired same-world matched prediction. These methods use a common source
probe and target label-draw budget, but preserve their distinct pretraining losses. They are not
inserted into the C1 adapter list because CSI/CIR consistency and same-world prediction are not
six-map interventions.

## Sionna

`setup_sionna.sh` authenticates and extracts both supplied official archives, installs Sionna RT
1.2.1 (the version frozen by the large-radio-map project), and installs the official tiling/scene/
radio-map scripts. `sionna_facility.py` exposes those operations and audits each `rm_*.npz` output.

`sionna_external_validity.py` is an internal G8 engine adapter. It requires every external-validation
sibling world to have a scene XML, canonical-map hash, asset manifest, per-asset hash, and license.
It retraces CFRs with `PathSolver` and emits paired active/null effects. A source archive alone cannot
pass G8; actual scene assets and a formal non-fixture run are mandatory.
