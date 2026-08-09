# CSI-PAIRS V2.0 formal data contract

Status: execution contract. Passing this schema is necessary but not sufficient scientific qualification.

## Container

Use one compressed NumPy archive (`.npz`) with `allow_pickle=False`. The formal runner reads no implicit filenames or neighboring metadata. The archive SHA-256 is recorded in `qualification/data_contract.json`.

## Required arrays

| Array | Shape | Meaning |
|---|---|---|
| `csi_repeat` | `[scene, world, position, repeat, channel]` | Independent repeat observations; channel layout is real values followed by imaginary values. |
| `csi_clean` | `[scene, world, position, channel]` | Clean deterministic target. It is mandatory when `require_clean_csi=true`. |
| `maps` | `[scene, world, row, column]` | Complete canonical rendering of every world, not edit-history deltas. |
| `positions` | `[scene, position, 2]` | Receiver coordinates used only for labels, pairing, and oracle diagnostics. |
| `world_bits` | `[world, bit]` | One complete binary hypercube shared as a logical index. |
| `primitive_ids` | `[scene, bit]` | A per-bank permutation mapping logical bits to physical primitives. |
| `anchor_bits` | `[scene, bit]` | Per-bank randomized natural-world state. |
| `natural_world_index` | `[scene]` | Row of `world_bits` equal to each bank's `anchor_bits`. |
| `scene_ids`, `city_ids`, `bank_ids` | `[scene]` | Fixed-width string identifiers; scene and bank IDs are globally unique. |
| `scene_roles` | `[scene]` | Immutable bank-level split role. |
| `position_roles` | `[scene, position]` | `standard` for source banks; disjoint `support_pool`/`query` for target banks. |
| `metadata_json` | scalar string | Exact provenance object described below. |

Allowed scene roles are `source_encoder_train`, `source_method_selection`, `source_calibration_fit`, `source_calibration_selection`, `target`, and `external_validation`. Every sibling world and every repeat inherits the scene-bank role. Target support positions and all of their sibling worlds are excluded from query evaluation.

## Required metadata

`metadata_json` has exact top-level keys: `schema_version`, `dataset_id`, `dataset_version`, `scientific_use`, `fixture`, `engine`, `representation`, `assets`, `generation`, and `external_reference`.

- `schema_version` must be `csi-pairs-formal-dataset-v2.0`.
- `engine` records `name`, `version`, a lowercase 64-character `config_sha256`, and `deterministic`.
- `representation` freezes CSI layout/units, phase gauge, coordinates, position/map units, and the clean-target definition. Independent per-world phase optimization is rejected.
- `assets` records nonempty license IDs, provenance, material library, and redistribution permission.
- `external_reference.available=true` is accepted only when the archive contains actual `external_validation` banks. The converse is also enforced.
- Generated test fixtures must set `fixture=true` and `scientific_use=FORBIDDEN` permanently.

## Non-negotiable invariants

1. Every bank contains the complete hypercube and all Hamming-1 directions.
2. At least two source banks use different bit-to-primitive permutations and different natural anchors.
3. Source split roles and target cities are independent scene banks, not renamed position slices.
4. CSI, maps, positions, and clean targets are finite; real/imag channel count is even.
5. Repeats are measured/generated independently. Copying one noise realization across worlds invalidates the response experiment.
6. Phase/gauge preprocessing is pair-consistent. If a common phase reference is unavailable, the dataset must freeze a phase-invariant physical representation before selection data are read.
7. `QUALIFIED` is not trusted from metadata alone. The executable repeat, route, oracle/readout, No-X, null, shortcut, and external gates still decide use.

## Build sequence

Create and hash the engine configuration first, render canonical worlds, populate the archive, then run:

```bash
python -m formal_v2.formal_cli inspect-data \
  --config formal_v2/configs/formal_v2.json \
  --output /unused/output
```

Do not alter thresholds after inspecting `source_method_selection`, `target`, or `external_validation` outputs. A failed gate requires a new preregistered protocol and new untouched banks, not an in-place threshold edit.
