#!/bin/zsh
set -euo pipefail

suite_root=${CSI_PAIRS_SUITE_ROOT:-${0:A:h}}
suite_root=${suite_root:A}
mode=full

if (( $# > 1 )); then
  print -u2 'usage: ./VERIFY_SUITE.sh [--quick]'
  exit 2
fi
if (( $# == 1 )); then
  if [[ $1 != '--quick' ]]; then
    print -u2 'usage: ./VERIFY_SUITE.sh [--quick]'
    exit 2
  fi
  mode=quick
fi

tmp_root=$(mktemp -d "${TMPDIR:-/tmp}/csi-pairs-suite-verify.XXXXXX")
trap 'rm -rf -- "$tmp_root"' EXIT INT TERM

checks=0

pass() {
  checks=$((checks + 1))
  printf 'PASS  %s\n' "$1"
}

die() {
  printf 'FAIL  %s\n' "$1" >&2
  exit 1
}

assert_eq() {
  local label=$1
  local actual=$2
  local expected=$3
  [[ $actual == $expected ]] || die "$label: expected=$expected actual=$actual"
  pass "$label=$actual"
}

require_file() {
  [[ -f $1 ]] || die "missing file: $1"
}

require_real_dir() {
  [[ -d $1 ]] || die "missing directory: $1"
  [[ ! -L $1 ]] || die "dataset root must not be a symlink: $1"
}

inventory() {
  local label=$1
  local data_root=$2
  local expected_files=$3
  local expected_dirs=$4
  local expected_links=$5
  local expected_bytes=$6
  local files dirs links bytes

  files=$(find "$data_root" -type f | wc -l | tr -d ' ')
  dirs=$(find "$data_root" -type d | wc -l | tr -d ' ')
  links=$(find "$data_root" -type l | wc -l | tr -d ' ')
  bytes=$(find "$data_root" -type f -exec stat -f '%z' {} + | awk '{sum += $1} END {printf "%.0f", sum}')

  assert_eq "$label regular files" "$files" "$expected_files"
  assert_eq "$label directories" "$dirs" "$expected_dirs"
  assert_eq "$label symlinks" "$links" "$expected_links"
  assert_eq "$label regular-file bytes" "$bytes" "$expected_bytes"
}

external_root="$suite_root/02_EXTERNAL_WIRELESS/external_wireless"
qualcomm_root="$suite_root/03_INDEPENDENT_ENGINE_QUALCOMM/qualcomm_wireless_indoor"
legacy_root="$suite_root/01_FORMAL_MAIN_CANDIDATES/legacy_sionna_osm_34bank_POST_AUDIT_NO_GO"

for required_dir in \
  "$suite_root/00_FROZEN_SPECS" \
  "$suite_root/01_FORMAL_MAIN_CANDIDATES" \
  "$suite_root/02_EXTERNAL_WIRELESS" \
  "$external_root" \
  "$suite_root/03_INDEPENDENT_ENGINE_QUALCOMM" \
  "$qualcomm_root" \
  "$suite_root/04_FIXTURES_SOFTWARE_ONLY" \
  "$suite_root/05_INCOMPLETE_AND_FAILED_RUNS" \
  "$suite_root/99_REGISTRY"
do
  require_real_dir "$required_dir"
done
pass 'all suite and dataset roots are real directories'

for required_file in \
  "$suite_root/README.md" \
  "$suite_root/DATASET_BLUEPRINT_V6.md" \
  "$suite_root/DATASET_CATALOG.json" \
  "$suite_root/ROLE_ASSIGNMENTS.csv" \
  "$suite_root/MISSING_ITEMS.md" \
  "$suite_root/99_REGISTRY/COPY_AUDIT.json" \
  "$suite_root/99_REGISTRY/CRITICAL_SHA256SUMS" \
  "$suite_root/99_REGISTRY/FAILED_RUN_SHA256SUMS" \
  "$suite_root/99_REGISTRY/FINAL_VERIFICATION.json" \
  "$suite_root/99_REGISTRY/FINAL_VERIFICATION.md" \
  "$suite_root/99_REGISTRY/M4_FAILED_RUN_SHA256SUMS" \
  "$suite_root/99_REGISTRY/QUALCOMM_SHA256SUMS"
do
  require_file "$required_file"
done
pass 'required documentation and registry files exist'

jq -e '
  .schema_version == "csi-pairs-dataset-suite-catalog-v1" and
  .suite_status.formal_status == "POST_AUDIT_NO_GO" and
  .suite_status.scientific_use == "FORBIDDEN" and
  ([.datasets[] | select(.copy_status == "COPIED")] | length) >= 12
' "$suite_root/DATASET_CATALOG.json" >/dev/null || die 'DATASET_CATALOG.json invariant failure'
jq -e '.schema_version == "csi-pairs-suite-copy-audit-v1"' \
  "$suite_root/99_REGISTRY/COPY_AUDIT.json" >/dev/null || die 'COPY_AUDIT.json invariant failure'
pass 'machine-readable catalog and copy audit are valid'

while IFS= read -r relative_path; do
  [[ -e "$suite_root/$relative_path" ]] || die "catalog COPIED path is absent: $relative_path"
done < <(jq -r '.datasets[] | select(.copy_status == "COPIED") | .suite_path' "$suite_root/DATASET_CATALOG.json")
pass 'all catalog entries marked COPIED exist'

inventory external_wireless "$external_root" 363263 1005 3 23857330137
inventory qualcomm_wireless_indoor "$qualcomm_root" 190590 46945 0 13435727571

partial_count=$(find "$external_root" -type f \( \
  -name '*.part' -o -name '*.partial' -o -name '*.crdownload' \
\) | wc -l | tr -d ' ')
assert_eq 'external partial-download files' "$partial_count" 0

(
  cd "$suite_root"
  shasum -a 256 -c 99_REGISTRY/CRITICAL_SHA256SUMS >/dev/null
)
pass '17 frozen-spec/candidate/fixture critical SHA-256 entries'

(
  cd "$suite_root"
  shasum -a 256 -c 99_REGISTRY/FAILED_RUN_SHA256SUMS >/dev/null
)
pass 'failed-run snapshot 233/233 SHA-256 entries'

(
  cd "$suite_root"
  shasum -a 256 -c 99_REGISTRY/M4_FAILED_RUN_SHA256SUMS >/dev/null
)
pass 'latest failed M4 snapshot 247/247 SHA-256 entries'

external_args=(--json)
if [[ $mode == full ]]; then
  external_args+=(--deep)
fi
(
  cd "$external_root"
  python3 verify_core_subset.py "${external_args[@]}" > "$tmp_root/external-verification.json"
)
jq -e '
  .training_core_complete == true and
  .all_original_sources_complete == false and
  .all_sources_complete == false and
  .public_substitutions_used == true and
  .under_hard_limit == true and
  .total_apparent_bytes == 23857786425 and
  .checks.UrbanMIMOMap.npz_count == 120 and
  .checks.RadioMapSeer.items["IRT2HighRes.zip"] == "missing" and
  .checks.WWM.original_source_acquired == false
' "$tmp_root/external-verification.json" >/dev/null || die 'external verifier truth-boundary failure'
pass "external verifier ($mode): core complete, original sources explicitly incomplete"

if [[ $mode == full ]]; then
  (
    cd "$external_root"
    shasum -a 256 -c SHA256SUMS >/dev/null
  )
  pass 'external 133/133 SHA-256 entries'

  (
    cd "$suite_root"
    shasum -a 256 -c 99_REGISTRY/QUALCOMM_SHA256SUMS >/dev/null
  )
  pass 'Qualcomm 13/13 ZIP/HDF5 SHA-256 entries'
else
  printf 'SKIP  external 133-entry and Qualcomm 13-entry large-file hashes (--quick)\n'
fi

legacy_python="$external_root/DeepMIMO/.venv/bin/python"
[[ -x $legacy_python ]] || die "numpy-capable audit runtime missing: $legacy_python"
LEGACY_NPZ="$legacy_root/dataset.npz" "$legacy_python" - <<'PY'
import os
import numpy as np

with np.load(os.environ["LEGACY_NPZ"], allow_pickle=False) as data:
    clean = data["csi_clean"]
    path_ids = data["path_ids"]
    assert clean.shape == (34, 4, 256, 16), clean.shape
    assert data["csi_repeat"].shape == (34, 4, 256, 3, 16)
    assert int(np.all(clean == 0, axis=-1).sum()) == 16124
    assert int(np.all(path_ids < 0, axis=-1).sum()) == 16124
    assert int((~np.isfinite(clean).all(axis=-1)).sum()) == 0
PY
pass 'legacy 34-bank candidate remains quarantined with exactly 16124 pathless/all-zero units'

printf '\nSUITE_VERIFICATION=PASS checks=%d mode=%s\n' "$checks" "$mode"
printf 'FORMAL_STATUS=POST_AUDIT_NO_GO\n'
printf 'SCIENTIFIC_USE=FORBIDDEN\n'
printf 'NOTE=Engineering verification does not establish scientific validity.\n'
