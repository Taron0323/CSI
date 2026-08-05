# CSI-PAIRS V2.1 V6 paper draft

This directory is independent of the frozen V1.26 paper. `main.tex` preserves the evidence-gated manuscript and adds four visible `DRAFT PLACEHOLDER / NOT A RESULT` figures plus `NOT RUN` result-table cells.

The placeholders specify:

1. the external two-model, six-condition paired audit;
2. the shared CSI/map encoder and endpoint/Alignment/Response paths;
3. immutable source/target/external splits and gate exits;
4. No-X/null, strict four-arm, two-city localization, and interaction results.

Do not replace a placeholder with fixture output or an expected curve. A formal value must trace to a non-fixture per-sample row, frozen config hash, checkpoint hash, independent bank count, training seeds, label draws where applicable, interval, and pass threshold.

Build into an unused directory:

```bash
CSI_PAIRS_LATEXMK=/path/to/latexmk paper_v2/build_reproducible.sh /unused/build-directory
```

The current build has seven pages before references and ten pages including references and the protocol appendix. The ICLR initial-submission main text remains within the nine-page limit; final page allocation must be rechecked after real figures replace placeholders.
