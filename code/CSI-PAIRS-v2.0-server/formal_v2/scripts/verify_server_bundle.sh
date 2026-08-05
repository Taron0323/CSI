#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${CSI_PAIRS_PYTHON:-python3}"
OUTPUT="${1:?usage: verify_server_bundle.sh UNUSED_DRY_RUN_OUTPUT_DIRECTORY}"

cd "${PROJECT_ROOT}"
if [[ -f SHA256SUMS ]]; then
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum --check SHA256SUMS
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 --check SHA256SUMS
  else
    echo "sha256sum or shasum is required to verify the bundle" >&2
    exit 3
  fi
fi

"${PYTHON_BIN}" -m unittest discover -s formal_v2/tests -v
CSI_PAIRS_PYTHON="${PYTHON_BIN}" \
  formal_v2/scripts/run_formal_v2_dry_run.sh "${OUTPUT}"
