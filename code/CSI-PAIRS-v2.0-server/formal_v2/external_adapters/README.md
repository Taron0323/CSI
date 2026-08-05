# External Baseline Adapters

These adapters implement the frozen V6 Section 1.1 six-condition audit. An adapter is
scientific evidence only after its source, command, checkpoint, result file, dataset, config,
and stage manifest hashes all authenticate and at least two distinct map-conditioned models pass.

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
formal_v2/external_adapters/setup_wigatr.sh /absolute/path/wigatr-env
```

The setup is intentionally separate from the core V2.1 environment. If the pinned dependencies
cannot be installed, the adapter fails and remains `not_executed`; no substitute model is used.

### Formal execution

1. Copy `wigatr_adapter_entry.json` into the `adapters` array of the formal external-adapter
   manifest and replace only `/absolute/path/to/wigatr-env/bin/python`.
2. Mark the Wi-GATr literature-registry row `executed` and bind it to
   `wigatr-official-csi-pairs-v1`.
3. Add at least one other actually executable map-conditioned adapter. The external gate rejects a
   one-model manifest by design.
4. Run `formal_cli all` or `formal_cli run-external-baselines` after data verification,
   qualification, factorial training, and evaluation have produced their authenticated artifacts.

Fixture runs remain `scientific_use=FORBIDDEN`, even if the adapter exits successfully.
