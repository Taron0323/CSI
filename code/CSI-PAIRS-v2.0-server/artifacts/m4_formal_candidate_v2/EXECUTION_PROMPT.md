# Reusable M4 formal-data execution prompt

Use the following prompt with a coding agent that has terminal access to a
clean CSI-PAIRS worktree and the approved local Sionna runtime.

## Prompt

You are executing the CSI-PAIRS V2.1 V6 paired-world formal-candidate data
pipeline on an Apple Silicon M4 Pro. Work fail-closed and preserve the boundary
between engineering evidence and scientific evidence.

Objective:

1. Validate the frozen Python/Sionna/Mitsuba/Dr.Jit/LLVM runtime and record the
   exact executable, package versions, Mitsuba variant, Dr.Jit thread count,
   LLVM path digest, repository commit, source-tree digest, config digest, and
   requirements-lock digest.
2. Build the six-city OSM-derived asset bank from a frozen raw OSM cache. Do not
   silently refetch or substitute a city. Require all 34 unique bank IDs, all 34
   unique base-map cluster IDs, all registered role counts, complete
   attribution, and per-file SHA-256 records.
3. Run protocol and one-bank LLVM diagnostics before the full render. Stop on a
   runtime mismatch, pathless unit, all-zero clean CSI unit, non-finite value,
   duplicate complete path identity, power-loss merge, receiver-count
   mismatch, support/query overlap, or scene-role mismatch.
4. Render all 34 banks as explicit shards. Every shard must use
   <code>llvm_ad_mono_polarized</code> and
   <code>drjit_thread_count=1</code>. Give every shard a manifest containing
   its inclusive start, exclusive end, NPZ hash, byte size, duration, asset
   manifest hash, generator hash, engine revision, and runtime record. Require
   exact non-overlapping coverage of scene indices 0 through 33 before merge.
5. Merge only authenticated shards into a new <code>dataset.npz</code>. Never
   overwrite a prior output. Keep dataset metadata at
   <code>scientific_use=CANDIDATE</code> and
   <code>simulation_not_measurement=true</code>.
6. From the intended repository head, run <code>inspect-data</code> into a
   fresh output and confirm 34 scenes, six cities, four worlds, 256 positions,
   three repeats, 16 channels, 34 independent clusters, the exact role counts,
   and disjoint target support/query IDs and coordinates.
7. Run <code>verify-data</code> in a second fresh output using the registered
   verifier manifest. Require all 34 per-scene rows and all nine role groups to
   pass at <code>rtol=0</code>, <code>atol=0</code>, with
   <code>engine_config_match=true</code> and no nonblocking scene failures.
8. Independently hash every candidate, shard, manifest, inspection, and
   verification artifact. Re-open the candidate and recompute pathless,
   no-op-pathless, all-zero, non-finite, duplicate-path-ID, and target split
   intersection counts.
9. Produce a repository-safe evidence package containing full hashes, sizes,
   scene and shard inventories, runtime facts, and verification outcomes. Do
   not commit NPZ files or unsanitized manifests with local absolute paths.
10. End with these exact readiness fields unless later external gates have
    actually passed:

    <code>M4_DATA_PRODUCTION_READY=REPORTED</code>

    <code>EVIDENCE_REGISTRY_READY=YES</code>

    <code>FORMAL_CANDIDATE_READY=BLOCKED_UNAPPROVED_RUNTIME</code>

    <code>FORMAL_INPUT_READY=BLOCKED</code>

    <code>FORMAL_TRAINING_READY=NO</code>

    <code>LAUNCH_READY=BLOCKED</code>

    <code>SCIENTIFIC_EVIDENCE=NOT_ASSESSED</code>

    <code>scientific_use=CANDIDATE_NOT_CLAIM</code>

Required stop conditions:

- Do not relax a registered gate or tolerance.
- Do not convert a fixture, failed run, partial role pass, or prose handoff into
  formal evidence.
- Do not promote a candidate whose LLVM digest is absent from the approved
  platform registry, even when same-host regeneration is exact.
- Do not call same-engine regeneration independent RT evidence.
- Do not start teacher, Wi-GATr, PMNet, four-arm, or formal model training on
  the M4.
- Do not claim physical validity, external validity, model efficacy, or paper
  results from data-generation success.

Use the shipped
<code>formal_v2/scripts/generate_sionna_osm_formal_candidate.sh</code>,
<code>formal_v2.formal_cli inspect-data</code>, and
<code>formal_v2.formal_cli verify-data</code> entrypoints where their frozen
contracts apply. For a strict one-process render, set
<code>CSI_PAIRS_RENDER_WORKERS=1</code>; when sharding, independently preserve
the one-thread runtime record in every shard and authenticate the final
coverage before merge.

Final report requirements:

- Exact candidate, generation-manifest, asset-manifest, inspection-contract,
  verification-gate, per-scene, and regenerated-NPZ hashes and sizes.
- Exact generator, config, verifier, source-tree, requirements-lock, runtime,
  and LLVM hashes.
- All 34 scene rows, all shard intervals, role/city counts, and zero-valued
  data-quality counters.
- A plain statement that same-host/same-engine regeneration proves
  determinism and internal consistency only.
- The unresolved independent RT, license, A100 preflight, model, training, and
  scientific-qualification blockers.
