# M4 single-bank backend gate (2026-08-09)

```text
simulation_not_measurement=true
scientific_use=DIAGNOSTIC_NOT_FORMAL_EVIDENCE
M4_SINGLE_BANK_GATE=PASS
M4_LOCAL_READY=YES
M4_BACKEND_CONTRACT_REVALIDATION=PASS
FORMAL_DATA_READY=NO
```

## Scope

Scene 0 was rendered twice from the post-merge repair worktree against the
current V2 asset manifest (`10ebbbf...a969b`, 34 banks) on native Darwin arm64.
The fixed runtime used Python 3.12.13, Sionna 2.0.1, Sionna RT 1.2.1, Mitsuba
3.7.1, Dr.Jit 1.2.0, LLVM 18.1.8 (`26273678...0451`),
`llvm_ad_mono_polarized`, and one Dr.Jit thread. The assets and generator
remained read-only. Only scene 0 was rendered; no 34-bank generation, A100
connection, or training was started.

The diagnostic renderer had SHA-256 `8834acad...1a37`. Both process manifests
bound the absolute asset-manifest path and its full `10ebbbf...a969b` digest,
in addition to the generator, renderer, runtime, and output hashes.

Process A (`PID=17451`, parent `17449`, `run_id=ab052d...eba8`) took
429.1010855420027 seconds. Process B (`PID=20327`, parent `20325`,
`run_id=f3e642...ca2a`) took 395.75950987497345 seconds and started
60.882647 seconds after process A ended.
The parent and Python process IDs, run IDs, and output paths were all distinct.
Each output was 827,540 bytes and had the same SHA-256:

```text
caff866902f96126876948bfc73b9af45ac416c530704d32e107a63f5c8c5392
```

## Exact replay result

All 23 NPZ fields had identical field names, shapes, dtypes, finite status, and
values under `rtol=0`, `atol=0`, and `equal_nan=false`. This includes clean and
repeated CSI, active and null path IDs/power/surfaces, maps, intervention
identity, phase references, positions, repeat seeds, and scene identity. The
maximum absolute clean-CSI difference was 0.0; the complete NPZ SHA-256 and ZIP
metadata/payload were also identical. The frozen repository replay comparator
independently passed all 22 scene-row fields and all 6,984 active plus 6,984
null path records. The independent exact gate accepted all fresh-process,
asset, generator, renderer, runtime, comparison-input, and output bindings.

Stable path signature inputs were captured without changing the generator or
output ordering. Each process produced 13,968 valid active/null path slots and
1,746 unique canonical IDs. Digest collisions, signature-to-ID ambiguity,
ID-to-signature ambiguity, same-context conflicts, and cross-process ID drift
were all zero. The 667 material/power variants are expected because the frozen
identity is geometry-based and intentionally excludes material state and power.

## Visibility boundary

All 1,024 scene-0 world-position units in this V2 diagnostic had visible clean
CSI in both processes. This one-scene observation is not a full-candidate
visibility qualification and cannot be extrapolated to all 34 banks.

For historical clarity, the existing full visibility audit below applies only
to the prior V1 candidate; it is not evidence about the V2 assets used above:

- overall no-path: 16,124 / 34,816 (46.31204044117647%)
- target no-path: 8,312 / 16,384 (50.732421875%)
- Boston no-path: 4,692 / 8,192 (57.275390625%)
- all four worlds no-path: 4,031 / 8,704 scene-position units
- worst bank: `osm-sionna-target-boston-bank-05`, 880 / 1,024 (85.9375%)
- active/null visibility changes: 0
- maximum stored paths used: 31 / 64; units at the storage cap: 0

The visibility audit being executable is an engineering PASS, not a scientific
quality PASS. The prior V1 candidate remains forbidden as formal paper evidence,
and this scene-0 diagnostic does not qualify or promote the V2 assets. A frozen
visibility quality protocol and acceptance threshold are still required.

## Targeted checks

```text
test_asset_manifest_record_binds_digest_to_absolute_path ... ok
test_cuda_path_preserves_visibility_and_runtime_bootstrap_checks ... ok
test_cuda_renderer_dispatch_does_not_fall_back_to_formal_llvm_config ... ok
test_llvm_path_requires_fixed_llvm_inputs_without_cuda ... ok
test_repository_replay_cli_has_frozen_dependency ... ok

Ran 5 tests
OK
```

The LLVM branch requires the fixed package versions, an absolute regular
`DRJIT_LIBLLVM_PATH`, the LLVM Mitsuba variant, and exactly one Dr.Jit thread.
The approved Darwin arm64 registry retains both exact audited libraries: LLVM
18.1.8 (`26273678...451`) for this scene-0 replay and LLVM 22.1.8
(`e514c689...a88`) for the later M4 diagnostic runtime. The CUDA branch retains
the frozen Linux `CUDA_VISIBLE_DEVICES`, CUDA driver preload, OptiX library,
LLVM-18, runtime Python, and re-exec checks. The macOS gate does not claim that
the Linux CUDA/OptiX branch was dynamically executed on this machine.

The CUDA diagnostic temporarily owns renderer selection while it invokes the
formal generator, so an LLVM value in the formal generator config cannot switch
the requested CUDA run back to `llvm_ad_mono_polarized`. The formal generator
itself remains unchanged.

Fresh real-runtime probes loaded both approved libraries, reported LLVM
18.1.8 and 22.1.8 respectively, selected `llvm_ad_mono_polarized`, and held the
Dr.Jit thread count at one. The missing frozen dependency for
`compare_sionna_shard_replay.py` was restored byte-for-byte as
`compare_sionna_regeneration.py` (`9d46304e...7be`); the replay CLI now imports
successfully under `python -P` with only its repository tool directory on
`PYTHONPATH`. Fresh manifests now emit both `asset_manifest_path` and
`asset_manifest_sha256`; the independent gate fails closed if the bound asset
bytes change or the path is absent.
