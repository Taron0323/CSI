# M4 local LLVM diagnostic node

This directory records the bounded macOS M4 Pro engineering validation for the
CSI-PAIRS Sionna path. The implementation adds an explicit LLVM bootstrap,
single-bank diagnostic asset construction, strict A/B comparison tools, and
visibility/data diagnostics while retaining the existing Linux CUDA bootstrap
as the default path.

The checked-in report is an audit record, not a portable data bundle. The two
rendered NPZ files, the 34-bank handoff dataset, the isolated Python runtimes,
and the LLVM runtime are deliberately excluded from Git because they are
machine-local or large external evidence. Their paths and SHA-256 values remain
bound in `M4_LOCAL_SIM_REPORT.md`.

The status boundary is mandatory:

```text
M4_LOCAL_READY=YES
FORMAL_DATA_READY=NO
FORMAL_STATUS=POST_AUDIT_NO_GO
SCIENTIFIC_USE=DIAGNOSTIC_NOT_FORMAL_EVIDENCE
FORMAL_SCIENTIFIC_USE=FORBIDDEN
```

The local A/B LLVM runs were exact at `rtol=0` and `atol=0`, but the local row
was only `12/22` exact against the frozen handoff candidate. This proves local
repeatability only; it does not prove Linux CUDA equivalence, full 34-bank
regeneration, propagation calibration, or scientific validity.

Focused tests from the repository root:

```bash
cd code/CSI-PAIRS-v2.0-server
python -m unittest \
  formal_v2.tests.test_m4_local_sionna_backend \
  formal_v2.tests.test_sionna_scene0_diagnostic_assets \
  formal_v2.tests.test_sionna_visibility_one_factor_diagnostic
```
