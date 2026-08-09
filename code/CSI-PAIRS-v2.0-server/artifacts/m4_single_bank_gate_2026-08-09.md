# M4 single-bank LLVM gate (2026-08-09)

```text
simulation_not_measurement=true
scientific_use=DIAGNOSTIC_NOT_FORMAL_EVIDENCE
M4_SINGLE_BANK_GATE=PASS
M4_LOCAL_READY=YES
FORMAL_DATA_READY=NO
```

## Scope

Scene 0 of the frozen v1 Sionna OSM candidate was rendered twice on a native
Darwin arm64 process with Python 3.12.13, Sionna 2.0.1, Sionna RT 1.2.1,
Mitsuba 3.7.1, Dr.Jit 1.2.0, `llvm_ad_mono_polarized`, and one Dr.Jit thread.
The frozen handoff assets, generator, and candidate dataset remained read-only.
No 34-bank generation, A100 connection, or training was started.

The first render took 1016.7360200840048 seconds and the second took
696.7697717079427 seconds. They ran in separate Python processes, with process
B starting 51.446408 seconds after process A ended. Each output was 687,072
bytes and had the same SHA-256:

```text
a26cbefef92bd881573ba2078dcdb9decdd2107f5e26e3d139dd4cf5f65dea22
```

## Exact replay result

All 23 NPZ fields had identical field names, shapes, dtypes, finite status, and
values under `rtol=0`, `atol=0`, and `equal_nan=false`. This includes clean and
repeated CSI, active and null path IDs/power/surfaces, maps, intervention
identity, phase references, positions, repeat seeds, and scene identity. The
maximum absolute clean-CSI difference was 0.0. The repository's existing replay
comparator also passed independently.

The frozen v1 stable path signature inputs were captured without changing the
path generator or output ordering. Each process produced 7,168 valid path slots
and 896 unique canonical IDs. Digest collisions, one signature mapping to
multiple IDs, one ID mapping to multiple signatures, same-context conflicts,
and cross-process ID drift were all zero.

## Visibility result

The existing visibility audit completed against the frozen full candidate:

- overall no-path: 16,124 / 34,816 (46.31204044117647%)
- target no-path: 8,312 / 16,384 (50.732421875%)
- Boston no-path: 4,692 / 8,192 (57.275390625%)
- all four worlds no-path: 4,031 / 8,704 scene-position units
- worst bank: `osm-sionna-target-boston-bank-05`, 880 / 1,024 (85.9375%)
- active/null visibility changes: 0
- maximum stored paths used: 31 / 64; units at the storage cap: 0

The visibility audit being executable is an engineering PASS, not a scientific
quality PASS. The current candidate remains forbidden as formal paper evidence
until a visibility quality protocol and acceptance threshold are frozen and
qualified.

## Targeted checks

```text
test_llvm_path_requires_fixed_llvm_inputs_without_cuda ... ok
test_cuda_path_preserves_visibility_and_runtime_bootstrap_checks ... ok

Ran 2 tests
OK
```

The LLVM branch requires the fixed package versions, an absolute regular
`DRJIT_LIBLLVM_PATH`, the LLVM Mitsuba variant, and exactly one Dr.Jit thread.
The diagnostic CLI is LLVM-only. CUDA/OptiX execution is deliberately not
offered by this tool because it has no separately authenticated CUDA bootstrap.
