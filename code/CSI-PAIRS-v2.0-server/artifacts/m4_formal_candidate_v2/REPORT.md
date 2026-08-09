# CSI-PAIRS M4 34-bank candidate report

Date: 2026-08-09

## Outcome

The M4 data-production phase completed a non-fixture 34-bank, six-city,
four-world paired dataset and a separate same-host/same-engine regeneration.
All 34 banks and all nine role groups passed the registered verifier with
<code>rtol=0</code> and <code>atol=0</code>. No target or other nonblocking
scene failed.

The authoritative candidate and gate digests are:

| Artifact | SHA-256 | Bytes |
|---|---|---:|
| Candidate <code>dataset.npz</code> | <code>e5ec3d32bbb7c639f2fd6e6dcc23bc4bb6085cc76830a700e5b7103b17a37847</code> | 28,449,796 |
| Generation manifest | <code>ce6ce3a048c8091dd77068c18e0fef5d9585c5d7b9e0c3e3dce2af5d26ee865b</code> | 5,065 |
| Asset manifest | <code>0b1a379b0ddd5170376515fe582795a1a84e5eb948c033909b2ba259a5267fe7</code> | 79,209 |
| Verification gate | <code>ac790e2ffacca784cba22bc31bc9798049bb219f3f88cfeb3cd0c69fce7c86a8</code> | 7,295 |
| Regenerated NPZ | <code>64ed7292b4d2ae2e6da0f65349d189c6eb70a1bf43750fbc11685fad4a47429d</code> | 28,106,727 |
| Per-scene verification | <code>972ed8e5a49547515941d83eb6c619e7e5244e111685ecd894ffc0c1c1042697</code> | 29,158 |

The original and regenerated NPZ container digests differ because the
regeneration archive contains only the 15 registered re-rendered/recomputed
physical arrays. The other 20 identity, position, configuration, and metadata
arrays are not duplicated there. The registered verifier and this package's
deep checker compare all 15 regenerated arrays with their candidate
counterparts at zero tolerance.

## Production inventory

- 34 scene banks and 34 independent base-map cluster IDs.
- Six cities: two source, two target, and two external-validation cities.
- Four worlds per bank, 256 registered positions per bank, three observation
  repeats, and 16 real-valued CSI channels.
- 34,816 clean scene/world/position units.
- 14 render shards with contiguous, non-overlapping coverage of scene indices
  0 through 33.
- 22,232.107 aggregate shard-seconds and 28,399,625 aggregate shard bytes.

Role counts are two banks for each of the seven source roles, 16 target banks,
and four external-validation banks. The detailed assignments and immutable
asset identities are in <code>scene_inventory.csv</code>.

## Runtime

Each shard recorded Python 3.12.13, Sionna 2.0.1, Sionna RT 1.2.1, Mitsuba
3.7.1, Dr.Jit 1.2.0, the <code>llvm_ad_mono_polarized</code> variant, and one
Dr.Jit thread. The loaded LLVM library digest was
<code>26273678e919e90006fe2f5fc6e020cfc11a428103494d4dad6fa211b5d50451</code>.

The generator source digest was
<code>d149fe687a8b063ff3dab8dd75bd38d4de764657e1f7e6d3698162b6bb3a0157</code>
at main-ancestor commit
<code>3fb3133f959f953091f911a5a256ca65d5b3f850</code>. Later main changes harden
runtime-library approval but do not rewrite this historical generator-bound
evidence.

## Data checks

Independent inspection of the untouched candidate reported:

| Check | Count |
|---|---:|
| Pathless clean units | 0 |
| Pathless no-op units | 0 |
| All-zero clean units | 0 |
| Non-finite clean values | 0 |
| Units with duplicate path IDs | 0 |
| Target support/query ID intersection | 0 |
| Target support/query coordinate intersection | 0 |

The latest-main inspection contract passed and is bound by
<code>c0c0644ff546efee9583846ce1120cdd0e80c96ff01dfe8fc210612ed55fc3a3</code>.
Its run manifest is bound by
<code>7e2d948989ec130316e9521a27f7ea840cc950a48d4db40ebfc8da55186f206c</code>.

## What this closes

This evidence closes <code>DATA-VISIBILITY-001</code>,
<code>DATA-REGEN-001</code>, <code>PATH-ID-001</code>, and
<code>INPUT-DATA-001</code>. It establishes that the replacement candidate is
visible, complete, path-identity-safe, repository-auditable, and internally
reproducible under the recorded Sionna/LLVM environment.

## What remains blocked

This package does not close independent RT calibration, controlled
measurement/G8, asset and checkpoint release review, destination-host A100
preflight, PMNet/Wi-GATr formal runs, four-arm training, or result
qualification. Therefore:

<code>FORMAL_INPUT_READY=CANDIDATE_ONLY</code>,
<code>FORMAL_TRAINING_READY=NO</code>,
<code>LAUNCH_READY=BLOCKED</code>, and
<code>SCIENTIFIC_EVIDENCE=NOT_ASSESSED</code>.

The candidate remains <code>scientific_use=CANDIDATE_NOT_CLAIM</code>. A
same-host, same-engine regeneration does not establish physical validity or
independent external validity.
