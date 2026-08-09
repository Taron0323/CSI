# Incomplete and failed runs

本目录全部为隔离数据。它们只允许用于回归、故障定位和历史对照，不得进入 formal merge、teacher、模型选择、论文训练或结果表。

## 已隔离内容

- `legacy_sionna_osm_candidate_005000Z`：较早的 34-bank candidate。
- `diagnostic_scene_00_004000Z`：单 scene diagnostic。
- `dense_diagnostic_scene_22_004500Z`：单 scene dense diagnostic。
- `failed_m4_paper_v2_20260809T082513Z`：正式生成前失败的 paper-v2 run 快照。
- `failed_visibility_diagnostic_20260809T0852Z`：针对失败 run 的追加 visibility 诊断。
- `failed_m4_formal_20260809T080951Z_path_id_collision`：通过 receiver/pilot 前检、但在 scene 12 因 stable path-ID collision 终止的新 M4 run。

## 已确认失败

```text
bank osm-sionna-source-chicago-bank-05 has only 199 deterministic LOS candidates
```

追加诊断还确认：

```text
bank osm-sionna-target-boston-bank-01 violates zero-pathless protocol:
pathless=8, all_zero=8
```

scene-10 diagnostic 只有空日志且没有 NPZ 产出，因此也属于 incomplete，不能解释为通过。

最新 M4 run 的日志在失败前记录 32/34 banks，但只有 7/8 个 shard 封口，完整 shard 只覆盖 30 banks；worker-2 在 scene 12 `osm-sionna-source-chicago-bank-06` 触发：

```text
RuntimeError: stable Sionna path identifier collision
```

没有 merged dataset。该 run 的 247 个文件哈希见套件根 `99_REGISTRY/M4_FAILED_RUN_SHA256SUMS`。

早期失败 run 与 visibility 诊断共 233 个文件，哈希见套件根 `99_REGISTRY/FAILED_RUN_SHA256SUMS`。
