# CSI-PAIRS v6 dataset suite audit

This directory is the reviewable control plane for the local CSI-PAIRS v6 dataset suite audited on 2026-08-09. It records the required construction, current local inventory, allowed roles, missing items, checksums, final verification, and failed M4 evidence without promoting engineering artifacts to scientific evidence.

```text
FORMAL_STATUS=POST_AUDIT_NO_GO
SCIENTIFIC_USE=FORBIDDEN
```

## Outcome

- The local suite exists at `/Users/futaoran/Desktop/ICLR2027/CSI_PAIRS_DATASET_SUITE_V6`.
- All 12 registered data entities were copied to independent APFS paths; top-level dataset roots are not symlinks.
- The full verifier passed 20 checks.
- `external_wireless` passed deep structure/CRC checks and 133/133 SHA-256 entries.
- Qualcomm Wi3R/WiPTR passed 13/13 locally generated ZIP/HDF5 SHA-256 entries.
- The legacy 34-bank candidate remains quarantined: 16,124/34,816 clean units are pathless and all-zero.
- The newest M4 run failed on scene 12 with `stable Sionna path identifier collision`; only 7/8 shards were sealed and no merged dataset exists.

## Start here

| File | Purpose |
| --- | --- |
| `DATASET_BLUEPRINT_V6.md` | Exact city -> bank -> hypercube -> common-position -> repeat/path construction contract |
| `DATASET_CATALOG.json` | Machine-readable source paths, copied paths, sizes, roles, statuses, and failure facts |
| `ROLE_ASSIGNMENTS.csv` | Allowed and forbidden use for every registered data entity |
| `MISSING_ITEMS.md` | P0 gaps and current Go/No-Go table |
| `99_REGISTRY/FINAL_VERIFICATION.md` | Short final verification report |
| `DATA_AVAILABILITY.md` | Why the 35.95 GiB data payload is local-only and how to verify it |
| `failure_evidence/` | Minimal logs/manifests proving the three observed M4 failure modes |

`LOCAL_SUITE_README.md` is the README stored at the root of the complete local suite. `00_FROZEN_SPECS/` contains immutable copies of the two v6 research documents and the formal data contract used for this audit.

## Verify the local suite

From this checked-out artifact directory:

```bash
CSI_PAIRS_SUITE_ROOT=/Users/futaoran/Desktop/ICLR2027/CSI_PAIRS_DATASET_SUITE_V6 \
  ./VERIFY_SUITE.sh
```

Use `--quick` to skip external's 133 large-file hashes and Qualcomm's 13 large-file hashes while retaining inventory, metadata, failure-snapshot, critical-artifact, and non-deep external checks.

Expected final lines:

```text
SUITE_VERIFICATION=PASS checks=20 mode=full
FORMAL_STATUS=POST_AUDIT_NO_GO
SCIENTIFIC_USE=FORBIDDEN
```

The engineering `PASS` means that the local snapshot matches the registered bytes and failure states. It does not establish RT qualification, paired-intervention validity, leakage resistance, factorial results, or external validity.

To verify this PR's metadata package without the local data payload:

```bash
./VERIFY_PR_METADATA.sh
```

This checks every committed audit file against `99_REGISTRY/PR_METADATA_SHA256SUMS`, validates the JSON/CSV status boundary, and rejects raw dataset payload extensions or files above GitHub's ordinary per-file limit.

## External dataset truth boundary

The complete local `datasets/external_wireless` copy is included in the catalog and verification. Its correct state is simultaneously:

```text
training_core_complete=true
all_original_sources_complete=false
```

The public RadioMap3DSeer archive is not the paid `IRT2HighRes.zip`. DeepSense Scenarios 8 and 33 are not the restricted WWM train/test/field/point-cloud/checkpoint artifacts. The metadata-only copies under `external_wireless_metadata/` preserve these distinctions.

## Formal dataset truth boundary

DeepMIMO, UrbanMIMOMap, RadioMapSeer, DeepSense, and Qualcomm cannot be mechanically concatenated into a CSI-PAIRS formal dataset. They do not share the registered bank, complete sibling-world hypercube, common Tx/Rx, signed edit, clean/repeat, phase-reference, primitive-surface, and path-surface semantics required by the frozen v6 design.

The next formal run must fix the stable path-ID collision, produce all 8 shards and a strict 34-bank merge, pass whole-dataset pathless/all-zero/nonfinite checks, and then pass the RT/data/scientific gates in `MISSING_ITEMS.md`. Until then all headline claims remain untested propositions.
