# Data availability and PR boundary

## Local complete snapshot

The audited local suite is represented without publishing a workstation path:

```text
$LOCAL_SUITE_ROOT
```

Final local directory view: 554,820 regular files, 48,272 directories, and 37,692,880 KiB (about 35.95 GiB). The data volume had 349 GiB available after the copy. APFS clone-copy semantics provide independent paths/inodes while allowing unchanged files to share physical blocks. The committed copy audit verifies source/target identity for 3 entries; the remaining catalog targets are existence records, so `G-COPY=PARTIAL`.

The two largest registered roots are:

| Root | Regular files | Regular-file bytes | Verification |
| --- | ---: | ---: | --- |
| `02_EXTERNAL_WIRELESS/external_wireless` | 363,263 | 23,857,330,137 | deep verifier + 133/133 SHA |
| `03_INDEPENDENT_ENGINE_QUALCOMM/qualcomm_wireless_indoor` | 190,590 | 13,435,727,571 | 13/13 ZIP/HDF5 SHA |

Exact paths, sizes, roles, source-completeness state, and failure snapshots are in `DATASET_CATALOG.json` and `99_REGISTRY/COPY_AUDIT.json`.

## Why the payload is not in this PR

This repository has no Git LFS configuration or local Git LFS runtime. The data includes individual 2-5 GiB archives/HDF5 files, which exceed GitHub's ordinary 100 MiB per-file Git limit, and the total payload is about 36 GiB. More importantly, the Qualcomm source directory lacks a local dataset-license and redistribution-terms snapshot. Uploading those bytes to a public PR would be technically invalid and could violate redistribution terms.

Therefore this PR intentionally contains only:

- frozen specifications and construction requirements;
- catalogs, role assignments, missing-item gates, and provenance gaps;
- upstream/local checksum manifests;
- final verification summaries and the reusable verifier;
- minimal M4 failure logs and shard/asset manifests.

It does not claim that raw data was uploaded to GitHub.

## Reproduce local verification

```bash
cd code/CSI-PAIRS-v2.0-server/artifacts/dataset_suite_v6
CSI_PAIRS_SUITE_ROOT="$LOCAL_SUITE_ROOT" \
  ./VERIFY_SUITE.sh
```

The `CSI_PAIRS_SUITE_ROOT` override lets this PR copy of the script verify the local data without duplicating it into the repository checkout.

## Requirements before any public data release

1. Resolve and archive dataset-level license/redistribution terms for every payload, especially Qualcomm Wi3R/WiPTR.
2. Choose an artifact host designed for multi-gigabyte research data and record immutable object hashes/versions.
3. Preserve original-source versus public-substitute labels for IRT2HighRes and WWM.
4. Publish a signed/root manifest that maps hosted objects to `DATASET_CATALOG.json` entries.
5. Do not label the release as formal scientific data until qualification and scientific gates pass.
