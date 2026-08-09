#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export VECLIB_MAXIMUM_THREADS="${VECLIB_MAXIMUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${CSI_PAIRS_SIONNA_PYTHON:-${PROJECT_ROOT}/formal_v2/external_adapters/.runtime-sionna/venv/bin/python}"
OUTPUT_ROOT_INPUT="${1:?usage: generate_sionna_osm_formal_candidate.sh OUTPUT_ROOT [RAW_OSM_CACHE]}"
OUTPUT_PARENT="$(cd "$(dirname "${OUTPUT_ROOT_INPUT}")" && pwd)"
OUTPUT_ROOT="${OUTPUT_PARENT}/$(basename "${OUTPUT_ROOT_INPUT}")"
RAW_CACHE="${2:-}"
CONFIG="${PROJECT_ROOT}/formal_v2/configs/sionna_osm_formal_candidate_v2.json"
RENDER_WORKERS="${CSI_PAIRS_RENDER_WORKERS:-8}"

if [[ ! "${RENDER_WORKERS}" =~ ^[0-9]+$ ]] || (( RENDER_WORKERS < 1 || RENDER_WORKERS > 34 )); then
  echo "CSI_PAIRS_RENDER_WORKERS must be an integer from 1 through 34" >&2
  exit 4
fi

if [[ -e "${OUTPUT_ROOT}" ]]; then
  echo "refusing to overwrite Sionna candidate root: ${OUTPUT_ROOT}" >&2
  exit 2
fi
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Sionna Python is unavailable; run formal_v2/external_adapters/setup_sionna.sh first" >&2
  exit 3
fi

mkdir -p "${OUTPUT_ROOT}/logs" "${OUTPUT_ROOT}/shards"
ASSET_ARGS=(
  -m formal_v2.sionna_osm_candidate prepare-assets
  --config "${CONFIG}"
  --output "${OUTPUT_ROOT}/assets"
)
if [[ -n "${RAW_CACHE}" ]]; then
  if [[ ! -d "${RAW_CACHE}" ]]; then
    echo "raw OSM cache is not a directory: ${RAW_CACHE}" >&2
    exit 5
  fi
  ASSET_ARGS+=(--raw-cache "${RAW_CACHE}")
fi

cd "${PROJECT_ROOT}"
"${PYTHON_BIN}" -B "${ASSET_ARGS[@]}" \
  >"${OUTPUT_ROOT}/logs/prepare-assets.log" 2>&1

RANGES=()
scene_start=0
base_count=$((34 / RENDER_WORKERS))
extra_count=$((34 % RENDER_WORKERS))
for ((shard_index = 0; shard_index < RENDER_WORKERS; shard_index++)); do
  scene_count="${base_count}"
  if (( shard_index < extra_count )); then
    scene_count=$((scene_count + 1))
  fi
  scene_end=$((scene_start + scene_count))
  RANGES+=("${scene_start} ${scene_end}")
  scene_start="${scene_end}"
done
PIDS=()
SHARDS=()
for shard_index in "${!RANGES[@]}"; do
  read -r scene_start scene_end <<<"${RANGES[${shard_index}]}"
  shard="${OUTPUT_ROOT}/shards/shard-${shard_index}.npz"
  SHARDS+=("${shard}")
  "${PYTHON_BIN}" -B -m formal_v2.sionna_osm_candidate render-shard \
    --asset-root "${OUTPUT_ROOT}/assets" \
    --output "${shard}" \
    --scene-start "${scene_start}" \
    --scene-end "${scene_end}" \
    --shard-index "${shard_index}" \
    >"${OUTPUT_ROOT}/logs/render-${shard_index}.log" 2>&1 &
  PIDS+=("$!")
done

failed=0
for index in "${!PIDS[@]}"; do
  if ! wait "${PIDS[${index}]}"; then
    echo "Sionna render shard ${index} failed; see ${OUTPUT_ROOT}/logs/render-${index}.log" >&2
    failed=1
  fi
done
if [[ "${failed}" -ne 0 ]]; then
  exit 6
fi

MERGE_ARGS=(
  -m formal_v2.sionna_osm_candidate merge
  --config "${CONFIG}"
  --asset-root "${OUTPUT_ROOT}/assets"
  --output "${OUTPUT_ROOT}/dataset.npz"
)
for shard in "${SHARDS[@]}"; do
  MERGE_ARGS+=(--shard "${shard}")
done
"${PYTHON_BIN}" -B "${MERGE_ARGS[@]}" \
  >"${OUTPUT_ROOT}/logs/merge.log" 2>&1

printf 'candidate=%s\n' "${OUTPUT_ROOT}/dataset.npz"
printf 'render_workers=%s\n' "${RENDER_WORKERS}"
printf 'next=run inspect-data, then zero-tolerance verify-data before qualification\n'
