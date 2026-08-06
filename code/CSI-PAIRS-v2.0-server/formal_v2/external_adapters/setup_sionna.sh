#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WAIBU_ROOT="${PROJECT_ROOT}/waibu"
RUNTIME_ROOT="${1:-${PROJECT_ROOT}/formal_v2/external_adapters/.runtime-sionna}"
ENV_DIR="${RUNTIME_ROOT}/venv"
SOURCE_DIR="${RUNTIME_ROOT}/src"

if [[ -e "${RUNTIME_ROOT}" ]]; then
  echo "refusing to overwrite Sionna runtime: ${RUNTIME_ROOT}" >&2
  exit 2
fi
command -v uv >/dev/null 2>&1 || { echo "uv is required" >&2; exit 3; }
command -v unzip >/dev/null 2>&1 || { echo "unzip is required" >&2; exit 4; }

(
  cd "${WAIBU_ROOT}"
  printf '%s  %s\n' \
    'fdbf89f307cc8933535af1587f00f1bcbd4b5edf7715275cd461bd4779f1fac7' 'sionna-main.zip' \
    '694ad17e7977e1c1adbdc8f93e6dcb1856e14cdf1b25f33da14c0e7aca80c33b' 'sionna-large-radio-maps-main.zip' \
    | sha256sum --check --strict
)

mkdir -p "${SOURCE_DIR}"
unzip -q "${WAIBU_ROOT}/sionna-main.zip" -d "${SOURCE_DIR}"
unzip -q "${WAIBU_ROOT}/sionna-large-radio-maps-main.zip" -d "${SOURCE_DIR}"
mkdir -p \
  "${RUNTIME_ROOT}/data/local/scenes" \
  "${RUNTIME_ROOT}/data/remote/scenes" \
  "${RUNTIME_ROOT}/data/remote/outputs" \
  "${RUNTIME_ROOT}/data/remote/transmitters"

# The GitHub source archive does not carry the sionna-rt git submodule. Both supplied
# projects declare the official wheel; large-radio-maps freezes it to 1.2.1.
uv venv --python 3.12 "${ENV_DIR}"
UV_PROJECT_ENVIRONMENT="${ENV_DIR}" uv sync \
  --project "${SOURCE_DIR}/sionna-large-radio-maps-main" \
  --no-dev
uv pip install --python "${ENV_DIR}/bin/python" "${SOURCE_DIR}/sionna-main"

PYTHONPATH="${SOURCE_DIR}/sionna-large-radio-maps-main" \
SLRM_DATA_DIR="${RUNTIME_ROOT}/data" \
"${ENV_DIR}/bin/python" - <<'PY'
import importlib.metadata
import sionna
import sionna.rt
import sionna_lrm
print("sionna", importlib.metadata.version("sionna"))
print("sionna-rt", importlib.metadata.version("sionna-rt"))
print("sionna-large-radio-maps", "source@1ba19ae1df1d26302fcfbaab14efc2347313da5d")
PY

printf 'Sionna runtime ready: %s\n' "${RUNTIME_ROOT}"
