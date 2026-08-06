# CSI-PAIRS V2.1 V6 server bundle

Status: engineering `READY_FOR_DATA`; scientific `POST_AUDIT_NO_GO` until non-fixture gates pass.

This bundle is self-contained for the V2.1 runtime. It does not require the frozen V1 `experiments/` tree. It includes the formal code, tests, configs, data contract, paper source, official LaTeX style files, draft PDF, claim contract, verification report, supplied external papers, and authenticated official source archives. It intentionally contains no formal dataset, external model checkpoint, licensed scene asset, or claimed result. The top-level directory and three audit-listed artifact filenames retain `v2.0`/`v2_0` only as compatibility paths; their contents, schemas, runtime version, and generated bundle root are V2.1.

## 1. Server requirements

- Linux with Python 3.12 and `venv` support;
- enough disk space for PyTorch and your formal data;
- CUDA is optional for the non-scientific dry run and recommended for formal training;
- `sha256sum` for bundle verification.

## 2. Verify and install

From the extracted `CSI-PAIRS-v2.1-server` directory:

```bash
sha256sum --check SHA256SUMS
formal_v2/scripts/setup_formal_v2.sh "$PWD/.venv"
```

The setup script refuses to overwrite an existing environment directory.

## 3. Run code-only verification

Use a new output path:

```bash
"$PWD/.venv/bin/python" -m py_compile formal_v2/*.py formal_v2/tests/test_formal_v2.py
"$PWD/.venv/bin/python" -m unittest discover -s formal_v2/tests -v
```

Expected software outcome:

- all pure schema and semantic tests pass;
- no teacher, qualification, four-arm, localization, RT, or external-model experiment is run;
- no scientific gate changes state.

## 3.1 External papers, baselines, and Sionna facilities

Authenticate all ten supplied resources before any external experiment:

```bash
"$PWD/.venv/bin/python" -m formal_v2.formal_cli verify-waibu-resources \
  --registry "$PWD/formal_v2/configs/waibu_resources_v1.json" \
  --waibu-root "$PWD/waibu" \
  --output "$PWD/runs/resource-auth-001"
```

The core environment runs CSI-MAE, CSI-CLIP, CSI-CLIP++, ContraWiMAE, WWM, SigMap, WiSER, and RFIR
controlled implementations. WWM and RFIR retain explicit inspired/style-controlled labels; WiSER is
a paper-spec controlled adaptation over CSI-PAIRS-derived sparse scene tokens.
Wi-GATr retains its separate Python 3.10
environment:

```bash
formal_v2/external_adapters/setup_wigatr.sh
```

Sionna RT and the official large-radio-map tools use a separate Python 3.12 environment because of
their Mitsuba/Dr.Jit/Open3D stack:

```bash
formal_v2/external_adapters/setup_sionna.sh
"$PWD/formal_v2/external_adapters/.runtime-sionna/venv/bin/python" \
  -m formal_v2.sionna_facility \
  --runtime-root "$PWD/formal_v2/external_adapters/.runtime-sionna" verify
```

The top-level Sionna source package is installed without its independent PHY/PyTorch CUDA
dependency set because this G8 facility calls only `sionna.rt`.

Use `formal_v2/external_adapters/all_map_adapters_v1.json` for C1 and
`formal_v2/configs/representation_baselines_v1.json` for the representation comparison. Read
`formal_v2/WAIBU_INTEGRATION.md` for the exact mapping. Code, authenticated paper bytes, smoke
execution, and an installed simulator still do not constitute C1/G8 evidence.

Use `formal_cli export-sionna-scenes` to generate the hashed PLY/XML/assets manifest for every
`external_validation` sibling world before running the shipped
`formal_v2/configs/sionna_external_validity_adapter_v1.json` G8 adapter.

## 4. Inspect formal data

Do not start training first. Validate the NPZ against the frozen contract:

```bash
"$PWD/.venv/bin/python" -m formal_v2.formal_cli inspect-data \
  --config "$PWD/formal_v2/configs/formal_v2.json" \
  --dataset /absolute/path/csi_pairs_formal_v2_1_v6.npz \
  --output "$PWD/runs/data-inspection-001"
```

Review the generated `data_contract.json`, the engine/config hash, license records, phase/gauge convention, scene roles, support/query isolation, repeats, natural anchors, and primitive permutations.

## 5. Verify physical regeneration before qualification

```bash
"$PWD/.venv/bin/python" -m formal_v2.formal_cli verify-data \
  --config "$PWD/formal_v2/configs/formal_v2.json" \
  --dataset /absolute/path/csi_pairs_formal_v2_1_v6.npz \
  --verifier-manifest /absolute/path/independent_rt_verifier.json \
  --output "$PWD/runs/formal-001"

"$PWD/.venv/bin/python" -m formal_v2.formal_cli qualify \
  --config "$PWD/formal_v2/configs/formal_v2.json" \
  --dataset /absolute/path/csi_pairs_formal_v2_1_v6.npz \
  --data-verification-gate "$PWD/runs/formal-001/data_verification/gate.json" \
  --output "$PWD/runs/formal-001"
```

Only a non-fixture `qualification/gate.json` with `passed=true` permits the four-arm experiment. After approval, run the complete chain into another unused directory:

```bash
CSI_PAIRS_PYTHON="$PWD/.venv/bin/python" \
CSI_PAIRS_FORMAL_DATASET=/absolute/path/csi_pairs_formal_v2_1_v6.npz \
CSI_PAIRS_FORMAL_OUTPUT="$PWD/runs/formal-all-001" \
CSI_PAIRS_VERIFIER_MANIFEST=/absolute/path/independent_rt_verifier.json \
CSI_PAIRS_RISK_FEATURE_MANIFEST=/absolute/path/risk_feature_adapter.json \
CSI_PAIRS_EXTERNAL_ADAPTER_MANIFEST=/absolute/path/external_adapters.json \
CSI_PAIRS_RESOURCE_CONTROL_MANIFEST=/absolute/path/resource_controls.json \
CSI_PAIRS_SCENE_ID_MANIFEST=/absolute/path/scene_id.json \
CSI_PAIRS_EXTERNAL_VALIDITY_MANIFEST=/absolute/path/external_validity.json \
CSI_PAIRS_LITERATURE_RESOURCE_MANIFEST=/absolute/path/literature.json \
CSI_PAIRS_RT_CALIBRATION_MANIFEST=/absolute/path/rt_calibration.json \
CSI_PAIRS_SHUFFLED_PAIR_MANIFEST=/absolute/path/shuffled_pair.json \
CSI_PAIRS_RETENTION_MANIFEST=/absolute/path/retention.json \
  formal_v2/scripts/run_formal_v2.sh
```

Never reuse an output directory. Never replace paper placeholders with fixture output. The inherited No-X failures and four warning names remain binding until new untouched non-fixture banks pass the registered gates.
