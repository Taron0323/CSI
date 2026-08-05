#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${CSI_PAIRS_PYTHON:-python3}"
OUTPUT="${1:?usage: run_formal_v2_dry_run.sh UNUSED_OUTPUT_DIRECTORY}"
FIXTURE="${OUTPUT}.fixture.npz"

cd "${PROJECT_ROOT}"
"${PYTHON_BIN}" -m formal_v2.formal_cli make-fixture --output "${FIXTURE}"
"${PYTHON_BIN}" -m formal_v2.formal_cli verify-data \
  --config "${PROJECT_ROOT}/formal_v2/configs/formal_v2_smoke.json" \
  --dataset "${FIXTURE}" \
  --output "${OUTPUT}" \
  --verifier-manifest "${PROJECT_ROOT}/formal_v2/configs/fixture_verifier.json"
"${PYTHON_BIN}" -m formal_v2.formal_cli qualify \
  --config "${PROJECT_ROOT}/formal_v2/configs/formal_v2_smoke.json" \
  --dataset "${FIXTURE}" \
  --output "${OUTPUT}"
