# V6 external-resource integration

This document maps every file under `waibu/` to executable V6 behavior. The authenticated registry
is `configs/waibu_resources_v1.json`. SHA-256 authentication proves local bytes, not paper fidelity
or scientific support.

| Resource | Project role | Executable implementation | Allowed evidence label |
|---|---|---|---|
| `2406.14995v2.pdf`, `Wi-GATr-main.zip` | map-conditioned forward baseline | official tokenizer/GATr plus CSI-PAIRS mesh and inverse localization | Wi-GATr official-code adaptation |
| `2502.11965v2.pdf` | CIR/CSI consistency baseline | ResNet-50 CSI/CIR encoders and symmetric contrastive loss; ViT style extension | CSI-CLIP-style / CSI-CLIP++-style controlled implementation |
| `2505.09160v2.pdf` | reconstruction+contrastive baseline | 2D asymmetric MAE, independent masked noisy views, SNR 5--40 dB, temperature 0.2 | ContraWiMAE paper-spec controlled implementation |
| `2601.03789v1.pdf` | masked CSI baseline and Stage-0 neighbor | 75% random 2D patches, asymmetric ViT encoder/decoder | CSI-MAE paper-spec controlled implementation |
| `2603.25216v1.pdf` | multimodal same-world baseline | CSI/map/context modality experts, online/EMA target JEPA, latent L1 | WWM-inspired same-world matched prediction |
| `2604.07086v1.pdf` | editable RF forward baseline | 2.5D Gaussian primitives, learned material reflection/roughness, direct+scattered RF-BSDF field | RFIR paper-spec controlled implementation |
| `2606.04770v1.pdf` | geometry-grounded multi-view baseline | sparse scene memory, Tx modulation, ray-corridor radiomap head, set-based CIR decoder | WiSER paper-spec controlled implementation |
| `sionna-main.zip` | PHY/RT engine | authenticated local Sionna 2.0.1 source plus official `sionna-rt` dependency | Sionna official source facility |
| `sionna-large-radio-maps-main.zip` | tiling, scene build, large radio maps | official scripts and strict output audit | Sionna large-radio-map official facility |

SigMap is required by frozen V6 but has no paper/source file in `waibu/`. Its implementation is
therefore named only `style-controlled-implementation`; it cannot be upgraded by documentation.

## Commands

Authenticate resources:

```bash
python3 -m formal_v2.formal_cli verify-waibu-resources \
  --registry formal_v2/configs/waibu_resources_v1.json \
  --waibu-root waibu \
  --output runs/waibu-auth-001
```

Run the five representation baselines after role-wise data verification:

```bash
python3 -m formal_v2.formal_cli run-representation-baselines \
  --config formal_v2/configs/formal_v2.json \
  --dataset /absolute/path/csi_pairs_formal_v2_1_v6.npz \
  --representation-baseline-config formal_v2/configs/representation_baselines_v1.json \
  --output /absolute/path/formal-run
```

Run the common C1 unit registry:

```bash
python3 -m formal_v2.formal_cli run-external-baselines \
  --config formal_v2/configs/formal_v2.json \
  --dataset /absolute/path/csi_pairs_formal_v2_1_v6.npz \
  --adapter-manifest formal_v2/external_adapters/all_map_adapters_v1.json \
  --output /absolute/path/formal-run
```

Install and inspect Sionna facilities:

```bash
formal_v2/external_adapters/setup_sionna.sh
formal_v2/external_adapters/.runtime-sionna/venv/bin/python \
  -m formal_v2.sionna_facility \
  --runtime-root formal_v2/external_adapters/.runtime-sionna verify
```

## Evidence boundary

- Representation-baseline PASS means source-only training, checkpoint selection, unified probe,
  and target query evaluation completed. It contributes comparison rows but never C1.
- External-baseline PASS requires at least two distinct map-conditioned model executions over the
  exact same internally generated unit IDs and six maps.
- G8 requires actual independent Sionna scene XML/assets, hashes, licenses, and retraced CFRs.
- Formal profile execution on real, independently regenerated data is required for scientific use.
- Fixture, smoke profile, unavailable dependency, missing asset, or hash mismatch remains permanently
  non-scientific/fail-closed downstream.
