#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_INPUT="${1:?usage: build_anonymous_supplement.sh UNUSED_OUTPUT_ZIP}"
OUTPUT_PARENT="$(cd "$(dirname "${OUTPUT_INPUT}")" && pwd)"
OUTPUT_ZIP="${OUTPUT_PARENT}/$(basename "${OUTPUT_INPUT}")"

if [[ -e "${OUTPUT_ZIP}" || -e "${OUTPUT_ZIP}.sha256" ]]; then
  echo "refusing to overwrite anonymous supplement output" >&2
  exit 2
fi
if ! command -v zip >/dev/null 2>&1; then
  echo "zip is required to build the anonymous supplement" >&2
  exit 3
fi

STAGING_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/csi-pairs-anonymous.XXXXXX")"
BUNDLE_ROOT="${STAGING_ROOT}/CSI-PAIRS-anonymous-supplement"
trap 'rm -rf "${STAGING_ROOT}"' EXIT

mkdir -p "${BUNDLE_ROOT}/paper/official_style"
(
  cd "${PROJECT_ROOT}"
  tar \
    --exclude='formal_v2/external_adapters/.venv-wigatr' \
    --exclude='formal_v2/external_adapters/.runtime-sionna' \
    --exclude='formal_v2/scripts/build_server_bundle.sh' \
    --exclude='formal_v2/scripts/build_anonymous_supplement.sh' \
    -cf - formal_v2
) | (
  cd "${BUNDLE_ROOT}"
  tar -xf -
)
cp -R "${PROJECT_ROOT}/paper_v2" "${BUNDLE_ROOT}/"
cp -R "${PROJECT_ROOT}/paper/official_style/iclr2027" "${BUNDLE_ROOT}/paper/official_style/"
cp -p "${PROJECT_ROOT}/formal_v2/ANONYMOUS_SUPPLEMENT.md" "${BUNDLE_ROOT}/README.md"

find "${BUNDLE_ROOT}" -type d -name __pycache__ -prune -exec rm -rf {} +
find "${BUNDLE_ROOT}" -type d -name '*.egg-info' -prune -exec rm -rf {} +
find "${BUNDLE_ROOT}" -type f \( -name '*.pyc' -o -name '.DS_Store' \) -delete

python3 - "${BUNDLE_ROOT}" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
forbidden = (
    "yiweinanzi",
    "Taron0323",
    "Immune-SkillNet",
    "researcher@immune-skillnet.ai",
    "origin/main",
    "/Users/futaoran",
)
violations = []
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".zip", ".pt", ".npz"}:
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for token in forbidden:
        if token.lower() in text.lower():
            violations.append(f"{path.relative_to(root)}: {token}")
if violations:
    raise SystemExit("anonymous supplement identity scan failed: " + "; ".join(violations[:10]))
PY

cd "${BUNDLE_ROOT}"
find . -type f ! -name SHA256SUMS -print | LC_ALL=C sort | while IFS= read -r path; do
  shasum -a 256 "${path}"
done > SHA256SUMS
find "${BUNDLE_ROOT}" -type d -exec chmod 0755 {} +
find "${BUNDLE_ROOT}" -type f -exec chmod 0644 {} +
find "${BUNDLE_ROOT}" -type f -name '*.sh' -exec chmod 0755 {} +
find "${BUNDLE_ROOT}" -exec touch -t 198001010000.00 {} +

cd "${STAGING_ROOT}"
TZ=UTC find CSI-PAIRS-anonymous-supplement -type f -print | LC_ALL=C sort | TZ=UTC zip -X -q "${OUTPUT_ZIP}" -@
cd "${OUTPUT_PARENT}"
shasum -a 256 "$(basename "${OUTPUT_ZIP}")" > "${OUTPUT_ZIP}.sha256"

echo "${OUTPUT_ZIP}"
