# `waibu/` integration reachability audit

Date: 2026-08-06 UTC

Scope: every regular file directly under `waibu/`, its authenticated provenance, executable consumer,
CLI reachability, dynamic software evidence, and scientific evidence boundary.

Method note: the `experiment-audit` skill requests an independent cross-model reviewer. That reviewer
backend was unavailable in this session. This report is therefore a direct local audit using file hashes,
paper text extraction, call-chain inspection, dependency probes, fixture mutation, real forward/backward
execution, and Sionna RT tracing. It is not an independent cross-model review.

## Verdict

- Resource authentication: **PASS, 10/10 files**.
- Resource-to-code reachability: **PASS, 10/10 files have an explicit consumer or provenance role**.
- Executable software integration: **PASS with declared boundaries**. Five representation models,
  three controlled map models, Wi-GATr's official environment/adapter, and Sionna RT/LRM facilities are
  reachable. Wi-GATr formal forward requires CUDA and was not run on this CPU-only host.
- Faithful upstream reproduction: **not claimed for paper-only methods**. WWM and RFIR are explicitly
  style/inspired controls; CSI-MAE, CSI-CLIP, ContraWiMAE, and WiSER are paper-spec controlled
  implementations; Wi-GATr is an official-code adaptation over CSI-PAIRS data.
- Formal comparison evidence: **NOT RUN**. No paper-dose non-fixture training or G8 effect experiment
  exists, so no G0-G8 gate or C1-C13 claim is promoted.

## Per-resource matrix

| Resource | Authenticated role | Runtime consumer | Dynamic evidence | Classification |
|---|---|---|---|---|
| `2406.14995v2.pdf` | Wi-GATr paper specification | `wigatr_official_v1.json`, `wigatr_adapter.py` | title checked; official model instantiated; CPU forward correctly rejected because frozen xFormers requires CUDA | provenance + official-code adaptation; formal run pending |
| `2502.11965v2.pdf` | CSI-CLIP specification | `representation_baselines_v1.json`, `CSIClip`, `CSIClipPlus` | both models completed finite forward/backward; all-five CLI fixture stage emitted checkpoints | paper-spec/style controlled, not official source |
| `2505.09160v2.pdf` | ContraWiMAE specification | `ContraWiMAE`, source-only WiMAE warm start | warm-start test plus finite joint backward and all-five CLI fixture stage | paper-spec controlled |
| `2601.03789v1.pdf` | CSI-MAE specification | `CSIMAE` | independent 75% masks, fixed 2D positions, asymmetric decoder, finite backward, CLI checkpoint | paper-spec controlled |
| `2603.25216v1.pdf` | wireless world-model specification | `WWMJEPA` | finite JEPA backward, EMA target path, CLI checkpoint | WWM-inspired; 2.5D maps replace original 3D point clouds |
| `2604.07086v1.pdf` | RFIR specification | `RFIRForward`, `rfir_controlled_v1.json` | finite gradients through visibility, anisotropic primitives, and alpha transmittance | RFIR-inspired; no visual 3DGS reconstruction stage |
| `2606.04770v1.pdf` | WiSER specification | `WiSERForward`, `wiser_controlled_v1.json` | finite radiomap/CIR gradients, learned queries, Hungarian matching, staged task schedule | paper-spec controlled; CSI-PAIRS 2.5D tokens replace ScanNet++ sparse voxels |
| `Wi-GATr-main.zip` | official source at `6daa5bd...` | vendored snapshot, isolated Python 3.10 adapter | ZIP commit and 45-file vendor hash PASS; imports PASS; CUDA prerequisite is explicit | official-code adaptation; 200k-step run pending |
| `sionna-main.zip` | official Sionna source at `04ddb931...` | setup, scene exporter, G8 adapter | Sionna 2.0.1 / RT 1.2.1, dependency check, scene load and CFR trace PASS | official-source RT facility |
| `sionna-large-radio-maps-main.zip` | official LRM source at `1ba19ae...` | setup and `sionna_facility.py` tiling/scene/radio-map commands | all three official script CLIs start; source import and output schema audit reachable | official facility; optional infrastructure, not the default G8 trace algorithm |

## Reachability

`formal_cli all` authenticates `waibu/`, then calls the external six-condition adapters, all five
representation baselines, and external validity before claim assembly. Standalone commands are also
available:

- `verify-waibu-resources`
- `run-external-baselines`
- `run-representation-baselines`
- `export-sionna-scenes`
- `run-external-validity`

The external-baseline runner authenticates the resource registry before launching adapters, generates
one common six-condition unit registry, validates every result row and execution manifest, and permits
only Wi-GATr plus WiSER to count toward C1. Style-controlled SigMap/RFIR results cannot satisfy C1.

## Dynamic checks performed

- `verify-waibu-resources`: 10/10 PASS.
- Wi-GATr: official ZIP/vendored bytes match; locked Python 3.10 environment imports; formal execution
  reports `formal_execution_ready=False` on this host because CUDA is unavailable.
- All five representation models: finite loss, `(2, 8)` representation, nonzero gradients.
- All-five downscaled CLI fixture stage: 5/5 PASS, five source-selected checkpoints, permanently
  `scientific_use=FORBIDDEN`.
- SigMap, WiSER, RFIR: real differentiable losses and nonzero parameter gradients.
- Sionna: package dependency check PASS; exact source/RT/Torch/h5py versions authenticated; official LRM
  script help paths execute; exported four-world fixture scene traced to four finite `(16, 16)` CFR arrays.
- Unit suite: 77/77 PASS.
- Clean extracted server bundle: 147/147 package hashes and 77/77 tests after this report is included.

## Defects found and corrected during this audit

1. The G8 adapter requested Torch CFR output despite the RT-only environment. It now requests NumPy CFR.
2. The G8 adapter still needs CPU PyTorch to replay the frozen teacher route. Setup now pins
   `torch==2.9.1+cpu` while excluding CUDA wheels.
3. NumPy scalar receiver coordinates failed the Mitsuba boundary. Tx/Rx points are now finite Python
   float triples.
4. Sionna's declared `h5py` dependency was absent. Setup pins `h5py==3.15.1` and runs `uv pip check`.
5. Sionna scene manifests accepted an arbitrary nonempty revision. Exact revisions, RT version, and both
   source archive hashes are now mandatory.
6. Wi-GATr attempted an unsupported CPU fallback. It now fails before training with an explicit CUDA
   prerequisite.
7. Runtime-generated Wi-GATr `*.egg-info` could enter the release bundle. Bundle construction now removes it.
8. Only a subset of representation models had gradient tests. All five are now exercised in one regression.

## Remaining blockers

- A qualified non-fixture V6 dataset is not present.
- This host exposes no NVIDIA CUDA device, so the official Wi-GATr paper-dose run cannot execute here.
- Wi-GATr 200k-step and WiSER 100k-step training, common six-condition evaluation, and resource controls
  have not run.
- Licensed independent external-validation scenes and a completed non-fixture Sionna G8 retrace are absent.
- Paper-only methods cannot be upgraded to `official reproduction` without released source and original
  data modalities. Their weaker labels are intentional and enforced.

Consequently, `waibu/` is genuinely connected at the software and provenance layers, but it is not a
completed comparison experiment. Treating resource authentication, fixture execution, or environment
installation as scientific evidence remains forbidden.
