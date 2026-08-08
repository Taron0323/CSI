#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${CSI_PAIRS_BOOTSTRAP_PYTHON:-python3}"
ENVIRONMENT_PATH="${1:?usage: setup_formal_v2.sh UNUSED_ENVIRONMENT_PATH}"

if [[ -e "${ENVIRONMENT_PATH}" ]]; then
  echo "refusing to overwrite environment path: ${ENVIRONMENT_PATH}" >&2
  exit 2
fi

PYTHON_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "${PYTHON_VERSION}" != "3.12" ]]; then
  echo "Python 3.12 is required; ${PYTHON_BIN} reports ${PYTHON_VERSION}" >&2
  exit 3
fi

"${PYTHON_BIN}" - <<'PY'
import platform
import sys

system = platform.system()
machine = platform.machine()
if system == "Darwin" and machine == "arm64":
    version = platform.mac_ver()[0]
    if not version or int(version.split(".", 1)[0]) < 14:
        raise SystemExit(f"macOS 14 or newer is required; observed {version or 'unknown'}")
elif system == "Linux" and machine == "x86_64":
    libc, version = platform.libc_ver()
    parts = tuple(int(part) for part in version.split(".")[:2]) if version else ()
    if libc != "glibc" or parts < (2, 28):
        raise SystemExit(f"glibc 2.28 or newer is required; observed {libc} {version}")
else:
    raise SystemExit(
        "supported setup targets are macOS 14+ arm64 and glibc 2.28+ Linux x86_64; "
        f"observed {system} {machine}"
    )
print(f"validated setup target: {system} {machine}")
PY

"${PYTHON_BIN}" -m venv "${ENVIRONMENT_PATH}"
PIP_CERT_ARGS=()
if [[ -n "${CSI_PAIRS_PIP_CERT:-}" ]]; then
  if [[ ! -f "${CSI_PAIRS_PIP_CERT}" ]]; then
    echo "CSI_PAIRS_PIP_CERT is not a regular certificate file: ${CSI_PAIRS_PIP_CERT}" >&2
    exit 4
  fi
  PIP_CERT_ARGS=(--cert "${CSI_PAIRS_PIP_CERT}")
elif [[ "$(uname -s)" == "Darwin" && -f /etc/ssl/cert.pem ]]; then
  PIP_CERT_ARGS=(--cert /etc/ssl/cert.pem)
fi
"${ENVIRONMENT_PATH}/bin/python" -m pip install \
  "${PIP_CERT_ARGS[@]}" \
  --require-hashes \
  --only-binary=:all: \
  --report "${ENVIRONMENT_PATH}/csi-pairs-install-report.json" \
  --requirement "${PROJECT_ROOT}/formal_v2/requirements-lock.txt"
chmod 0444 "${ENVIRONMENT_PATH}/csi-pairs-install-report.json"
"${ENVIRONMENT_PATH}/bin/python" -m pip check
"${ENVIRONMENT_PATH}/bin/python" -c 'import numpy, torch; print("numpy", numpy.__version__, "torch", torch.__version__)'
