#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${CSI_PAIRS_BOOTSTRAP_PYTHON:-python3}"
ENVIRONMENT_PATH="${1:?usage: setup_formal_v2.sh UNUSED_ENVIRONMENT_PATH}"

if [[ -e "${ENVIRONMENT_PATH}" ]]; then
  echo "refusing to overwrite environment path: ${ENVIRONMENT_PATH}" >&2
  exit 2
fi

"${PYTHON_BIN}" -m venv "${ENVIRONMENT_PATH}"
"${ENVIRONMENT_PATH}/bin/python" -m pip install --requirement "${PROJECT_ROOT}/formal_v2/requirements-lock.txt"
"${ENVIRONMENT_PATH}/bin/python" -c 'import numpy, torch; print("numpy", numpy.__version__, "torch", torch.__version__)'
