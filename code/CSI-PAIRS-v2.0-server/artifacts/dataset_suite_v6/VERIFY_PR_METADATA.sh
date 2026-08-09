#!/bin/zsh
set -euo pipefail

artifact_root=${0:A:h}
cd "$artifact_root"

manifest=99_REGISTRY/PR_METADATA_SHA256SUMS
[[ -f $manifest ]] || {
  print -u2 "missing metadata checksum manifest: $manifest"
  exit 1
}

shasum -a 256 -c "$manifest" >/dev/null

manifest_entries=$(wc -l < "$manifest" | tr -d ' ')
artifact_files=$(find . -type f ! -path "./$manifest" | wc -l | tr -d ' ')
[[ $manifest_entries == $artifact_files ]] || {
  print -u2 "metadata manifest coverage mismatch: entries=$manifest_entries files=$artifact_files"
  exit 1
}

jq -e '
  .suite_status.formal_status == "POST_AUDIT_NO_GO" and
  .suite_status.scientific_use == "FORBIDDEN" and
  .final_verification.result == "PASS" and
  .final_verification.formal_status_after_verification == "POST_AUDIT_NO_GO" and
  .final_verification.scientific_use_after_verification == "FORBIDDEN" and
  ([.datasets[] | select(.copy_status == "COPIED")] | length) == 12
' DATASET_CATALOG.json >/dev/null

python3 - <<'PY'
import csv

with open("ROLE_ASSIGNMENTS.csv", newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
assert len(rows) == 12, len(rows)
assert len({row["dataset_id"] for row in rows}) == 12
PY

payload_count=$(find . -type f \( \
  -name '*.zip' -o -name '*.h5' -o -name '*.hdf5' -o \
  -name '*.npz' -o -name '*.npy' -o -name '*.pt' -o \
  -name '*.pth' -o -name '*.ckpt' \
\) | wc -l | tr -d ' ')
[[ $payload_count == 0 ]] || {
  print -u2 "raw dataset/model payloads are not allowed in this metadata PR: count=$payload_count"
  exit 1
}

oversize_count=$(find . -type f -size +100M | wc -l | tr -d ' ')
[[ $oversize_count == 0 ]] || {
  print -u2 "files above 100 MiB are not allowed in this metadata PR: count=$oversize_count"
  exit 1
}

zsh -n VERIFY_SUITE.sh

printf 'PR_METADATA_VERIFICATION=PASS files=%s\n' "$artifact_files"
printf 'FORMAL_STATUS=POST_AUDIT_NO_GO\n'
printf 'SCIENTIFIC_USE=FORBIDDEN\n'

