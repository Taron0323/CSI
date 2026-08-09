#!/usr/bin/env python3
"""Render one diagnostic Sionna bank under an explicitly recorded backend."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import uuid

import numpy as np

from formal_v2 import sionna_osm_candidate as candidate
from formal_v2 import render_sionna_bank_backend_diagnostic as audited_renderer


def main() -> int:
    parser = argparse.ArgumentParser()
    asset_input = parser.add_mutually_exclusive_group(required=True)
    asset_input.add_argument("--asset-root", type=Path)
    asset_input.add_argument("--diagnostic-asset-root", type=Path)
    parser.add_argument("--scene-index", type=int, required=True)
    parser.add_argument("--backend", choices=("llvm",), required=True)
    parser.add_argument("--drjit-threads", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(".manifest.json").exists():
        raise FileExistsError(f"refusing to overwrite diagnostic output {args.output}")
    llvm_path = audited_renderer._prepare_backend(args, [__file__, *sys.argv[1:]])
    import mitsuba as mi

    mi.set_variant("llvm_ad_mono_polarized")
    import drjit as dr

    if args.drjit_threads is not None:
        if args.drjit_threads < 1:
            raise ValueError("--drjit-threads requires a positive count")
        dr.set_thread_count(args.drjit_threads)
    import sionna.rt  # noqa: F401

    if args.diagnostic_asset_root is not None:
        from formal_v2.sionna_scene0_diagnostic_assets import (
            load_diagnostic_asset_manifest,
        )

        root, manifest, config = load_diagnostic_asset_manifest(
            args.diagnostic_asset_root
        )
        asset_input_kind = "diagnostic_asset_manifest"
        asset_manifest_path = root / "diagnostic_asset_manifest.json"
    else:
        root, manifest, config = candidate.load_asset_manifest(args.asset_root)
        asset_input_kind = "formal_asset_manifest"
        asset_manifest_path = root / "asset_manifest.json"
    if not 0 <= args.scene_index < len(manifest["banks"]):
        raise ValueError("scene index is out of range")
    bank_row = manifest["banks"][args.scene_index]
    bank = candidate._read_json(root / str(bank_row["bank_record_path"]))
    run_id = uuid.uuid4().hex
    started_utc = datetime.now(timezone.utc)
    started = time.monotonic()
    rendered = candidate.render_bank(bank, root, config, args.scene_index)
    duration = time.monotonic() - started
    ended_utc = datetime.now(timezone.utc)
    arrays = {
        "scene_indices": np.asarray((args.scene_index,), dtype=np.int64),
        **{name: np.asarray(value)[None, ...] for name, value in rendered.items()},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    candidate._write_npz_exclusive(args.output, arrays)
    tool_path = Path(__file__).resolve()
    payload = {
        "schema_version": "csi-pairs-sionna-bank-backend-diagnostic-v2",
        "status": "DIAGNOSTIC_NOT_FORMAL_EVIDENCE",
        "simulation_not_measurement": True,
        "scientific_use": "DIAGNOSTIC_NOT_FORMAL_EVIDENCE",
        "run_id": run_id,
        "started_utc": started_utc.isoformat(),
        "ended_utc": ended_utc.isoformat(),
        "backend": args.backend,
        "mitsuba_variant": mi.variant(),
        "drjit_thread_count": int(dr.thread_count()),
        "scene_index": args.scene_index,
        "scene_id": bank_row["scene_id"],
        "duration_seconds": duration,
        "asset_root": str(root),
        "asset_input_kind": asset_input_kind,
        "asset_manifest_path": str(asset_manifest_path),
        "asset_manifest_sha256": candidate.sha256_file(asset_manifest_path),
        "output_path": str(args.output.resolve()),
        "output_bytes": args.output.stat().st_size,
        "output_sha256": candidate.sha256_file(args.output),
        "runtime": audited_renderer._llvm_runtime_record(llvm_path, mi, dr),
        "generator_path": str(Path(candidate.__file__).resolve()),
        "generator_sha256": candidate.sha256_file(Path(candidate.__file__).resolve()),
        "tool_path": str(tool_path),
        "tool_sha256": candidate.sha256_file(tool_path),
    }
    candidate._write_json_exclusive(args.output.with_suffix(".manifest.json"), payload)
    print(json.dumps({"output": str(args.output.resolve()), "status": payload["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
