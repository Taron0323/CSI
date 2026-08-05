#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENDOR_ROOT="${PROJECT_ROOT}/formal_v2/external_adapters/vendor/Wi-GATr"
ENV_DIR="${1:?usage: setup_wigatr.sh UNUSED_ENV_DIRECTORY}"
PYTHON310="${CSI_PAIRS_PYTHON310:-/usr/bin/python3.10}"

if [[ -e "${ENV_DIR}" ]]; then
  echo "refusing to overwrite Wi-GATr environment" >&2
  exit 2
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to install the locked official Wi-GATr environment" >&2
  exit 3
fi
if [[ ! -x "${PYTHON310}" ]]; then
  echo "Python 3.10 is required by the official Wi-GATr snapshot" >&2
  exit 4
fi

uv venv --python "${PYTHON310}" "${ENV_DIR}"
UV_PROJECT_ENVIRONMENT="${ENV_DIR}" uv sync \
  --project "${VENDOR_ROOT}" \
  --locked \
  --no-dev

"${ENV_DIR}/bin/python" -c "import gatr, torch_geometric, wigatr; print('Wi-GATr environment ready')"
