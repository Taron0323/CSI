# CSI-PAIRS V2.1 V6 paper draft

This directory is independent of the frozen V1.26 paper. `main.tex` preserves the evidence-gated manuscript and includes protocol-only figures for the six-condition audit, model information flow, and fail-closed G0--G8 sequence. Planned result-table cells are explicitly marked `PLANNED`; no formal result panel is instantiated before authenticated non-fixture evidence exists. It states all five frozen research questions and uses the current G0--G8 meanings.

The protocol figures specify:

1. the external two-model, six-condition paired audit;
2. the shared CSI/map encoder and endpoint/Alignment/Response paths;
3. immutable source/target/external splits and gate exits;
4. No-X/null, strict four-arm, two-city localization, and interaction result schemas.

Do not populate a planned result cell with fixture output or an expected value. A formal value must trace to a non-fixture per-sample row, frozen config hash, checkpoint hash, independent bank count, training seeds, label draws where applicable, interval, and pass threshold.

Build into an unused directory:

```bash
CSI_PAIRS_LATEXMK=/path/to/latexmk paper_v2/build_reproducible.sh /unused/build-directory
```

The current build has eight pages before references and ten pages including references and the protocol appendix. The ICLR initial-submission main text remains within the nine-page limit; final page allocation must be rechecked after authenticated result tables and figures are generated.
