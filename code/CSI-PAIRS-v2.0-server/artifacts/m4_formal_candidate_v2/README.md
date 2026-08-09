# M4 formal candidate evidence

This directory registers hash commitments for a reported 34-bank CSI-PAIRS
V2.1 V6 Sionna/OSM paired-world run on Apple Silicon on 2026-08-09. The candidate
dataset itself and its isolated regeneration are external binary inputs. They
are bound here by complete SHA-256 digests, byte sizes, a 34-row scene
inventory, a 14-row shard inventory, and a verifier that can inspect the
original local artifacts.

The evidence boundary is:

| Field | Value |
|---|---|
| <code>M4_DATA_PRODUCTION_READY</code> | <code>REPORTED</code> |
| <code>EVIDENCE_REGISTRY_READY</code> | <code>YES</code> |
| <code>FORMAL_CANDIDATE_READY</code> | <code>BLOCKED_UNAPPROVED_RUNTIME</code> |
| <code>FORMAL_INPUT_READY</code> | <code>BLOCKED</code> |
| <code>FORMAL_TRAINING_READY</code> | <code>NO</code> |
| <code>LAUNCH_READY</code> | <code>BLOCKED</code> |
| <code>SCIENTIFIC_EVIDENCE</code> | <code>NOT_ASSESSED</code> |
| <code>scientific_use</code> | <code>CANDIDATE_NOT_CLAIM</code> |

## Contents

| File | Purpose |
|---|---|
| <code>candidate_evidence.json</code> | Canonical machine-readable hashes, dimensions, runtime, results, and readiness boundary. |
| <code>scene_inventory.csv</code> | All 34 scene banks, cities, roles, cluster identities, asset hashes, and verification status. |
| <code>shard_inventory.csv</code> | All 14 render shards with exact scene coverage, NPZ/manifest hashes, sizes, and durations. |
| <code>REPORT.md</code> | Human-readable production and verification report. |
| <code>EXECUTION_PROMPT.md</code> | Reusable fail-closed prompt for local generation and evidence collection. |
| <code>verify_candidate_evidence.py</code> | Standard-library static verification plus optional NumPy-backed deep verification. |
| <code>SHA256SUMS</code> | Complete checksum inventory for this directory, excluding itself. |

## Verify repository evidence

From the server root:

~~~bash
PYTHONDONTWRITEBYTECODE=1 python3 \
  artifacts/m4_formal_candidate_v2/verify_candidate_evidence.py
~~~

Static mode verifies the local evidence checksums, privacy boundary, binary
omission policy, blocked readiness status, all 34 declared scene rows, all 14
declared shard rows, and inventory self-consistency. It does not open or
authenticate any omitted artifact and prints
<code>external_artifacts=NOT_VERIFIED</code> explicitly.

## Verify the original artifacts

Use the frozen Python environment that supplies NumPy:

~~~bash
PYTHONDONTWRITEBYTECODE=1 /path/to/frozen/python \
  artifacts/m4_formal_candidate_v2/verify_candidate_evidence.py \
  --candidate-root /absolute/path/to/candidate-root \
  --inspection-root /absolute/path/to/latest-main-inspection-root \
  --verification-root /absolute/path/to/isolated-verification-root
~~~

Deep mode additionally authenticates every omitted file and all shard
manifests, recomputes the visibility/path-ID/split checks from the candidate,
checks every per-scene gate field, and compares all 15 registered regenerated
physical arrays with their original NPZ counterparts at zero tolerance. The
remaining 20 identity, position, configuration, and metadata arrays are not
duplicated in the verifier's regeneration archive.

Even a successful deep check remains blocked from formal use: the recorded
libLLVM SHA-256 is absent from
<code>formal_v2/configs/sionna_llvm_approved_v1.json</code>. The runtime must be
reviewed and registered, or the data regenerated under an approved runtime.

## Binary and privacy policy

Neither 27 MiB NPZ is in ordinary Git history. Git LFS was not part of this
delivery, and the dataset remains an external formal input. Original
generation, asset, inspection, and verification manifests are also omitted
because they contain host-local absolute paths. Their untouched hashes and byte
sizes are retained in <code>candidate_evidence.json</code>.

Same-host, same-engine isolated regeneration establishes determinism and
internal consistency only. It is not independent RT evidence, a controlled
measurement, a license clearance, a training result, or a scientific claim.
