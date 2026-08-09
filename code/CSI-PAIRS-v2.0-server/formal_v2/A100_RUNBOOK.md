# CSI-PAIRS Linux A100 launch runbook

This runbook prepares the current V2.1 code and the frozen raw OpenStreetMap
inputs on a separate Linux host with two A100 GPUs. It does not classify an
unrendered candidate, a fixture, or a failed gate as scientific evidence.

## Required transfer layout

Transfer the verified server bundle and the portable candidate bundle produced
by `export-data-verification`:

```text
CSI-PAIRS-v2.1-server/
CSI-PAIRS-A100-verified-candidate-v2/
  README.md
  SHA256SUMS
  dataset.npz
  regenerated.npz
  per_scene.csv
  data_contract.json
  verification_receipt.json
  precomputed_verifier.json
  formal_precomputed_regeneration_verifier.py
```

Keep the separate raw-input bundle outside Git only when the A100 host must
render a new candidate instead of replaying the Mac-verified bytes:

```text
CSI-PAIRS-A100-input-v2/
  README.md
  SHA256SUMS
  raw_osm/
    external-denver.json
    external-miami.json
    source-austin.json
    source-chicago.json
    target-boston.json
    target-seattle.json
```

Do not transfer or train on the old
`sionna_osm_candidate_20260809T005000Z/dataset.npz`. Its clean data contain
pathless/all-zero units and its CUDA-rendered banks failed exact independent
regeneration. Only the six frozen raw OSM JSON files are reusable.

## 1. Verify the host and transferred bytes

Run from the extracted server root:

```bash
set -euo pipefail
test "$(uname -s)" = Linux
test "$(uname -m)" = x86_64
nvidia-smi -L
nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader
df -h "$PWD"
sha256sum --check SHA256SUMS
(
  cd /absolute/path/CSI-PAIRS-A100-verified-candidate-v2
  sha256sum --check SHA256SUMS
)
```

The formal core requires CPython 3.12, glibc 2.28 or newer, two visible A100s,
and enough free disk for both isolated environments, 34 render banks, the
merged dataset, an independent regeneration copy, checkpoints, and results.
Do not put placeholder zero values into the reviewed compute plan.

The data renderer uses deterministic single-thread LLVM workers. Install
`uv`, `unzip`, and a discoverable LLVM shared library before Sionna setup. The
two A100s are used by model training, not by the frozen LLVM data renderer.

## 2. Install the reviewed runtime

```bash
formal_v2/scripts/setup_formal_v2.sh "$PWD/.venv"
```

The command selects the Linux CUDA 12.1 lock and installs PyTorch
`2.5.1+cu121`. This core runtime is sufficient to replay the portable
zero-tolerance verification and start the later model gates. Install the
separate Sionna/Dr.Jit runtime only when rendering or independently
regenerating the candidate on this Linux host:

```bash
formal_v2/external_adapters/setup_sionna.sh
```

Do not activate a CUDA 13 compatibility preload or reuse a Conda environment.
`setup_sionna.sh` accepts libLLVM only when its exact SHA-256 is already listed
for Linux x86_64 in `formal_v2/configs/sionna_llvm_approved_v1.json`. The
repository currently contains only the reviewed Darwin arm64 entry, so A100
setup must remain blocked until the destination library bytes and provenance
are reviewed and committed. Do not add a hash discovered during the same run.

Verify the core GPU runtime:

```bash
PYTHONDONTWRITEBYTECODE=1 "$PWD/.venv/bin/python" -B - <<'PY'
import torch
assert torch.__version__ == "2.5.1+cu121", torch.__version__
assert torch.cuda.is_available()
assert torch.cuda.device_count() == 2, torch.cuda.device_count()
print(torch.__version__, torch.version.cuda)
for index in range(2):
    properties = torch.cuda.get_device_properties(index)
    print(index, properties.name, properties.total_memory)
PY
```

## 3. Replay the Mac-verified candidate on the A100 host

Use new output paths and run both checks from the extracted server root:

```bash
CANDIDATE_BUNDLE=/absolute/path/CSI-PAIRS-A100-verified-candidate-v2
(
  cd "$CANDIDATE_BUNDLE"
  sha256sum --check SHA256SUMS
)

PYTHONDONTWRITEBYTECODE=1 "$PWD/.venv/bin/python" -B -m formal_v2.formal_cli inspect-data \
  --config "$PWD/formal_v2/configs/formal_v2.json" \
  --dataset "$CANDIDATE_BUNDLE/dataset.npz" \
  --output "$PWD/runs/sionna-osm-v2-inspect-001"

PYTHONDONTWRITEBYTECODE=1 "$PWD/.venv/bin/python" -B -m formal_v2.formal_cli verify-data \
  --config "$PWD/formal_v2/configs/formal_v2.json" \
  --dataset "$CANDIDATE_BUNDLE/dataset.npz" \
  --output "$PWD/runs/sionna-osm-v2-verify-001" \
  --verifier-manifest "$CANDIDATE_BUNDLE/precomputed_verifier.json"
```

Continue only when inspection passes, `verification_mode` is
`precomputed_independent_regeneration`, all 34 rows and all nine role groups
pass, and both tolerances are zero. This replay rechecks the complete candidate
against the independently regenerated archive. It is candidate-data evidence,
not an independent RT engine, G8 result, or paper claim.

## 4. Optional: generate a new V2 candidate from the raw cache

Choose a new output root. The command refuses to overwrite it:

```bash
RAW_OSM=/absolute/path/CSI-PAIRS-A100-input-v2/raw_osm
CANDIDATE_ROOT="$PWD/formal_inputs/sionna-osm-v2-001"
formal_v2/scripts/generate_sionna_osm_formal_candidate.sh \
  "$CANDIDATE_ROOT" "$RAW_OSM"
```

This prepares new V2 assets, runs eight independent LLVM render shards over
the 34 frozen banks, and writes `dataset.npz` beside `assets/`. Preserve that
adjacency: the independent verifier reconstructs the immutable assets from
`dirname(dataset.npz)/assets`.

Watch progress without changing the run:

```bash
tail -F "$CANDIDATE_ROOT"/logs/render-*.log
```

Any missing RT path, all-zero clean CSI unit, receiver-map collision, failed
shard, or runtime drift aborts generation. Do not delete the check or rename a
failed candidate into a formal dataset.

## 5. Inspect and independently regenerate all banks

Use two unused output roots:

```bash
PYTHONDONTWRITEBYTECODE=1 "$PWD/.venv/bin/python" -B -m formal_v2.formal_cli inspect-data \
  --config "$PWD/formal_v2/configs/formal_v2.json" \
  --dataset "$CANDIDATE_ROOT/dataset.npz" \
  --output "$PWD/runs/sionna-osm-v2-inspect-001"

PYTHONDONTWRITEBYTECODE=1 "$PWD/.venv/bin/python" -B -m formal_v2.formal_cli verify-data \
  --config "$PWD/formal_v2/configs/formal_v2.json" \
  --dataset "$CANDIDATE_ROOT/dataset.npz" \
  --output "$PWD/runs/sionna-osm-v2-verify-001" \
  --verifier-manifest "$PWD/formal_v2/configs/sionna_osm_verifier_v2.json"
```

Continue only when the inspection succeeds, every value in
`data_verification/gate.json` under `role_status` is `PASS`, and no one of the
34 scene banks failed at `rtol=0` and `atol=0`. A partial
source-role pass is useful for diagnosis but is not a complete formal input.
Do not edit the archive metadata after verification. The authenticated
`CANDIDATE` earns `FORMAL_EXPERIMENT_ALLOWED` only if G1 and G2 subsequently
pass; a failed gate or fixture remains forbidden.

## 6. Prepare the formal gate chain

Before training, provide real reviewed inputs for:

- independent RT fit, validation, and reference partitions;
- Wi-GATr and PMNet non-fixture adapter execution;
- a G8 engine or controlled intervention independent of the primary Sionna
  renderer;
- literature/resource licenses and a positive authorized compute plan.

The shipped Sionna G8 adapter cannot close G8 for a Sionna-generated primary
dataset. Reusing the same engine would only support simulator-consistent
wording and is rejected before training.

For a genuinely different RT engine, the precomputed archive contract may be
used only for diagnostic interchange and outer-statistics validation. It can
never authorize formal training or satisfy G8; formal execution requires an
authenticated executable adapter or controlled real intervention. The
diagnostic external-validity manifest has
schema `csi-pairs-v6-external-validity-archive-v1` and binds these files:

```json
{
  "schema_version": "csi-pairs-v6-external-validity-archive-v1",
  "evidence_type": "independent_rt_engine",
  "engine_family": "wireless-insite",
  "source_revision": "REPLACE_WITH_EXACT_ENGINE_REVISION",
  "license_id": "REPLACE_WITH_REVIEWED_LICENSE_ID",
  "external_csi_path": "external_csi.npz",
  "external_csi_sha256": "REPLACE_WITH_SHA256",
  "engine_config_path": "engine-config.json",
  "engine_config_sha256": "REPLACE_WITH_SHA256",
  "rt_scene_manifest_path": "rt_scene_manifest.json",
  "rt_scene_manifest_sha256": "REPLACE_WITH_SHA256"
}
```

`external_csi.npz` has exactly `scene_ids`, `position_ids`, and
`external_csi`; its axes must match all registered `external_validation`
scenes, sibling worlds, positions, and CSI channels. The scene manifest uses
schema `csi-pairs-v6-independent-rt-scene-manifest-v1`, covers every external
scene/world exactly once, binds each world to its canonical map and distinct
source asset, and repeats the exact engine family, revision, license, dataset
SHA, and engine-config SHA. Diagnostic execution loads and validates all three
files and recomputes every direction, effect, cluster interval, and
null-equivalence decision in first-party code, while recording
`DIAGNOSTIC_NOT_CLAIM`. Formal preflight rejects this archive schema.

Set both devices for every formal command:

```bash
export CSI_PAIRS_DEVICES=cuda:0,cuda:1
export CUDA_VISIBLE_DEVICES=0,1
```

Then follow the two-phase `prepare-full-run` and `all` commands in the root
`README.md`. Preparation runs G0, independent RT, independent data verification,
G1, and G2 before it emits a human-approval request. `all` starts the four-arm
training only after that exact request is reviewed and approved.

Stop on any nonzero exit, failed regeneration role, RT partition overlap,
Response/no-x/null-safety failure, runtime mismatch, or resource preflight
failure. Before those gates pass, `SCIENTIFIC_EVIDENCE=NOT_ASSESSED` and
`FORMAL_GO=NO-GO` remain the only valid status.
