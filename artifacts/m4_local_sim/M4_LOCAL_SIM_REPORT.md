# CSI-PAIRS M4 Pro 本地 LLVM 仿真节点报告

- 报告创建时间（UTC）：`2026-08-09T08:47:51Z`
- 最后更新时间（UTC）：`2026-08-09T09:28:37Z`
- 主执行：`GPT-5.6 Sol / Max / Local`
- 工作根：`/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM`
- 只读交接源：`/Users/futaoran/Desktop/ICLR2027/CSI_HANDOFF_20260809T032602Z`
- 权威本轮输出：`/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/outputs/20260809T074722Z`

## 0. 最终门控

```text
M4_ENV_READY=PASS
PINNED_RUNTIME=PASS
HANDOFF_INTEGRITY=PASS
UPSTREAM_GIT_CLEAN=PASS
ASSET_BUILD_SINGLE_BANK=PASS
LLVM_SINGLE_BANK_RENDER_A=PASS
LLVM_SINGLE_BANK_RENDER_B=PASS
SINGLE_BANK_EXACT_REGEN=PASS
LOCAL_LLVM_TWO_PROCESS_REPEATABILITY=PASS
FROZEN_HANDOFF_CANDIDATE_EXACT_REPRODUCTION=FAIL
VISIBILITY_AUDIT=PASS
VISIBILITY_QUALITY=NOT_QUALIFIED
DATA_CONTRACT_AUDIT=PASS
LINUX_CUDA_PATH_PRESERVED=PASS
FOCUSED_TESTS=PASS_13_OF_13
M4_LOCAL_READY=YES
FORMAL_DATA_READY=NO
FORMAL_STATUS=POST_AUDIT_NO_GO
SCIENTIFIC_USE=DIAGNOSTIC_NOT_FORMAL_EVIDENCE
FORMAL_SCIENTIFIC_USE=FORBIDDEN
simulation_not_measurement=true
ULTRA_READ_ONLY_REVIEW=PASS_WITH_NONBLOCKING_FINDINGS
ULTRA_REVIEW_BLOCKERS=0
M4_LOCAL_READY_CAN_STAND=YES
```

`M4_LOCAL_READY=YES` 只表示这台 M4 Pro 已具备以下工程能力：项目内固定 LLVM 环境可工作；可以构建一个诊断 bank 的资产；可以在两个新的本机 LLVM 运行中生成非空 RT 输出并得到逐字段完全一致的结果；可以执行可见性与数据结构审计。

它不表示数据已经通过正式科学门控，也不表示本机 LLVM 输出精确复现冻结 handoff 候选。正式状态仍是 `FORMAL_DATA_READY=NO`、`POST_AUDIT_NO_GO` 和 `FORBIDDEN`。

## 1. 范围与证据边界

本轮完成的是本地 CPU/LLVM 诊断节点，不是论文实验完成证明。所有新环境、修改副本、日志、sidecar 和本轮输出均位于 `CSI_M4_LOCAL_SIM`。原始 handoff 未修改，上游 Git checkout 未修改。

以下 `PASS` 仅代表对应工程检查完成：

- `SINGLE_BANK_EXACT_REGEN=PASS` 的严格定义是本机 macOS LLVM process A 与 process B 之间的 exact repeatability。
- `VISIBILITY_AUDIT=PASS` 表示审计程序和内部一致性检查完成，不表示已有冻结协议下的可见性质量资格判定。
- `DATA_CONTRACT_AUDIT=PASS` 表示结构/契约检查完成，不表示数据可用于正式训练或论文结论。

禁止把这些结果表述为测量数据、跨后端等价、全 34 bank exact regeneration、传播模型已校准或科学结论已验证。

## 2. 机器与固定运行时

机器预检：

| 项目 | 实测值 |
|---|---:|
| macOS | `26.5.1` |
| Kernel | `Darwin 25.5.0` |
| 架构 | `arm64` |
| CPU | `Apple M4 Pro` |
| 物理/逻辑 CPU | `14 / 14` |
| 内存 | `51,539,607,552 bytes`，约 `48 GiB` |
| Command Line Tools | `/Library/Developer/CommandLineTools` |

RT 固定运行时：

| 组件 | 版本/值 |
|---|---|
| Python | `3.12.13` |
| Sionna | `2.0.1` |
| Sionna RT | `1.2.1` |
| Mitsuba | `3.7.1` |
| Dr.Jit | `1.2.0` |
| PyProj | `3.7.2` |
| Shapely | `2.1.2` |
| Mitsuba variant | `llvm_ad_mono_polarized` |
| Dr.Jit threads | `1` |
| Dr.Jit LLVM | `22.1.8` |

运行时路径：

```text
RT_VENV=/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/runtime/venv
FORMAL_VENV=/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/runtime/formal_venv
LLVM=/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/runtime/llvm/22.1.8/lib/libLLVM.dylib
LLVM_SHA256=e514c689a4469887f30396826cec7559ad6ddc1d9db1a0b243790bee7725ca88
```

本机没有 Homebrew。LLVM 使用官方 Homebrew `llvm 22.1.8 arm64_tahoe` bottle，在项目目录内解包、重定位并 ad-hoc 签名；原始 bottle 的大小与发布 digest 均匹配。`otool`、`codesign --verify`、真实 Dr.Jit LLVM JIT 数值求值和 Sionna RT import 均通过。完整偏差记录见：

`/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/logs/llvm_install_source_and_deviation.log`

## 3. 来源、handoff 与工作副本

上游 Git：

```text
REMOTE=https://github.com/yiweinanzi/CSI.git
BRANCH=main
HEAD=11595f168f9fcf36dc178aaee927b348d7c6402a
ORIGIN_MAIN=11595f168f9fcf36dc178aaee927b348d7c6402a
AHEAD_BEHIND=+0/-0
TRACKED_CHANGES=0
STAGED_CHANGES=0
NONIGNORED_UNTRACKED=0
```

只读 handoff 完整性：

```text
HANDOFF_ROOT_SHA256SUMS=1439/1439_PASS
ARCHIVE_COPIED_FILES=181/181_PASS
ARCHIVE_MAPPED_BACK_TO_HANDOFF=181/181_PASS
EXTRA_HANDOFF_SYMLINKS=0
```

handoff 根共有 1440 个普通文件；根 `SHA256SUMS` 覆盖另外 1439 个文件，唯一未自我覆盖的是 `SHA256SUMS` 本身。archive 中的两个目录与 handoff 递归一致，两个 Sionna ZIP 逐字节一致。

未修改的首次运行被保留为真实失败证据。原实现即使请求 LLVM，仍先要求仓库内置 Python venv、Linux CUDA driver、LLVM-18、OptiX 和 Linux `.so`，因此在 macOS 上于 bootstrap 阶段失败。没有把该失败改写为 PASS。

工作副本相对 181 文件 archive copied scope：

```text
MODIFIED_FILES=5
NEW_FILES=5
DELETED_FILES=0
PERMISSION_CHANGES=0
__pycache__=0
.pyc=0
.pyo=0
```

macOS 修改保持窄范围：LLVM 分支只要求当前固定 Python 与真实 `libLLVM.dylib`；默认 CUDA 分支继续要求原 Linux runtime、CUDA driver preload、OptiX、Linux library path 和 LLVM-18。独立探针证明默认 CUDA bootstrap 的 Python 路径与完整 environment 字典和 archive 版本逐项一致：

```text
LINUX_CUDA_PATH_PRESERVED=PASS
environment_exact_equal=true
```

`setup_formal_v2.sh` 只修复 Bash 3.2 在 `set -u` 下展开空数组的问题。第一次 12 MB 左右的失败 venv 被保留，没有伪装为成功环境：

`/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/runtime/formal_venv.failed-bash32-empty-array-20260809T0750Z`

## 4. 单 bank 资产构建

权威资产目录：

`/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/outputs/20260809T074722Z/assets`

结果：

```text
ASSET_BUILD_SINGLE_BANK=PASS
SCENE_INDEX=0
SCENE_ID=osm-sionna-source-chicago-bank-00
RECEIVER_POSITIONS=256
UNIQUE_RECEIVER_POSITIONS=256
BUILD_WALL_SECONDS=0.60
VERIFY_WALL_SECONDS=0.09
DIAGNOSTIC_MANIFEST_SHA256=ad809b2437483684dc22ebcd65b005d296f694d302d2827575d4d0258a09808e
FORMAL_ASSET_MANIFEST_PRESENT=NO
```

独立 loader 验证了 manifest、XML、四个 PLY、材料、BS/receiver clearance 和文件哈希。`bank.json`、四个 PLY、`scene.xml` 共 `6/6` 与冻结 scene 0 参考逐字节一致。资产明确使用 `diagnostic_asset_manifest.json`，未生成会被误认成正式资产的 `asset_manifest.json`。

## 5. 单 bank LLVM A/B 仿真与零容差

| 运行 | 外部 wall time | renderer time | 文件大小 | NPZ SHA-256 |
|---|---:|---:|---:|---|
| A | `458.42 s` | `457.583272667 s` | `687,072 bytes` | `a26cbefef92bd881573ba2078dcdb9decdd2107f5e26e3d139dd4cf5f65dea22` |
| B | `462.70 s` | `461.783055625 s` | `687,072 bytes` | `a26cbefef92bd881573ba2078dcdb9decdd2107f5e26e3d139dd4cf5f65dea22` |

独立进程证据：

```text
A_WINDOW=2026-08-09T08:00:38Z..2026-08-09T08:08:16Z
B_WINDOW=2026-08-09T08:09:40Z..2026-08-09T08:17:23Z
WINDOWS_NONOVERLAPPING=PASS
OUTPUT_PATHS_DISTINCT=PASS
MANIFEST_PATHS_DISTINCT=PASS
RUNNER_REFUSES_PREEXISTING_OUTPUT=PASS
```

A 与 B 绑定同一个资产 manifest、generator、renderer、scene、LLVM runtime、Mitsuba variant 和单线程设置。完整补强 sidecar：

`/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/outputs/20260809T074722Z/scene_00_fresh_process_audit.json`

零容差的实际含义：

```text
COMPARATOR_FIELDS_EXACT=22/22
INDEPENDENT_NPZ_FIELDS_EXACT=23/23
COMPARISON_METHOD=np.array_equal
RTOL=0
ATOL=0
WHOLE_FILE_SHA256_IDENTICAL=PASS
NONFINITE_NUMERIC_FIELDS_A=0
NONFINITE_NUMERIC_FIELDS_B=0
VALID_PATH_SLOTS=3584
NONZERO_CLEAN_CSI_SCALARS=9664
```

因此本机 A/B exact 不是放宽容差后的近似相等。比较器第一次因 `python -P` 不自动加入工具目录而出现 `ModuleNotFoundError`；失败日志保留。仅显式加入工具目录 `PYTHONPATH` 后重跑，未修改 comparator、字段集合或容差。

必须保留的反例：本机 A 与冻结 handoff candidate 的 scene 0 对应字段只有 `12/22` exact。以下 10 个字段不同：

```text
csi_clean
csi_repeat
noop_path_ids
noop_path_power
noop_path_surface_ids
path_ids
path_power
path_surface_ids
phase_reference_source_sha256
phase_reference_values
```

完整逐字段 comparator 已保留，不再只依赖汇总 sidecar：

`/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/outputs/20260809T074722Z/scene_00_local_vs_frozen.comparison.json`

```text
STATUS=NOT_EXACT
EXACT_FIELDS=12/22
COMPARISON_METHOD=np.array_equal
RTOL=0
ATOL=0
COMPARISON_SHA256=98e98571323eb56880ea711aedb562fe635c660d189ae865db45d8919e6124ce
```

所以：

```text
LOCAL_LLVM_TWO_PROCESS_REPEATABILITY=PASS
FROZEN_HANDOFF_CANDIDATE_EXACT_REPRODUCTION=FAIL
```

本轮结果不能覆盖 handoff 已记录的全 34 bank exact-regeneration scientific gate failure，也不能证明 macOS LLVM 与 Linux CUDA 跨后端逐字段等价。

## 6. 可见性审计

分类后的完整审计：

`/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/outputs/20260809T074722Z/rt_visibility_audit.json`

关键统计：

| 范围 | no-path | 比率 |
|---|---:|---:|
| 全部 | `16,124 / 34,816` | `46.312040%` |
| target | `8,312 / 16,384` | `50.732422%` |
| target Boston | `4,692 / 8,192` | `57.275391%` |
| 最差 bank，四个 worlds | `880 / 1,024` | `85.937500%` |
| 最差 bank，唯一位置 mask | `220 / 256` | `85.937500%` |

最差 bank 是 `osm-sionna-target-boston-bank-05`，scene index `27`。no-path 与全零 CSI 双向精确对应：`no_path_but_nonzero_csi=0`、`visible_but_zero_csi=0`。最大存储路径数为 `31`，正式容量 `64` 未饱和。

四个 worlds 的 visibility mask 完全相同，只说明 active/no-op 的可见/不可见分类相同；不能写成路径内容相同。审计明确显示 active/no-op 的 path IDs、power、surface arrays 并非逐字节相等。

因此：

```text
VISIBILITY_AUDIT=PASS
VISIBILITY_QUALITY=NOT_QUALIFIED
SCIENTIFIC_GATE=NOT_ASSIGNED_REQUIRES_FROZEN_PROTOCOL
```

## 7. 严格单因素诊断

报告：

`/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/outputs/20260809T074722Z/visibility_one_factor_scene27.json`

所有物理条件固定同一个 seed `2026107904`，LLVM 单线程；除 registered factor 外保持一致。

| 条件 | 可见位置 | no-path | 相对 baseline | runtime |
|---|---:|---:|---|---:|
| baseline | `36/256` | `220/256` | baseline | `49.60 s` |
| receiver radius `112 m` | `42/256` | `214/256` | 位置集合改变，只能总体比较 | `48.32 s` |
| BS south `10 m` | `30/256` | `226/256` | `+5/-11` 可见位置 | `50.43 s` |
| BS height `35 m` | `32/256` | `224/256` | `+0/-4` | `40.88 s` |
| max depth `6` | `49/256` | `207/256` | `+13/-0` | `76.66 s` |
| reflection off | `15/256` | `241/256` | `+0/-21` | `3.14 s` |
| refraction on | `131/256` | `125/256` | `+95/-0` | `54.81 s` |
| diffraction on | `36/256` | `220/256` | 本条件未观察到变化 | `57.19 s` |
| capacity `16` | `36/256` | `220/256` | storage projection only | `<0.001 s` |

capacity `16` 没有重新调用 PathSolver，复用 baseline 原始路径计数：`solver_invoked=false`。它截断 `31` 条存储路径；`6` 个位置真正超过容量，`7` 个位置达到容量；物理可见性没有改变。

最多三个待人工冻结候选：

1. `refraction_on`：单 bank 效果最大，但依赖材料介电参数与厚度校准；必须做跨 bank、第二引擎或测量验证，当前不可直接采用。
2. `max_depth_6`：增加高阶反射，单次成本约为 baseline 的 `1.55x`，但该 bank 仍有 `80.86%` no-path。
3. `receiver radius 112 m`：只改变接收点采样分布，不能称为传播改善；冻结它会改变任务覆盖范围。

这些都是 `待验证命题`，不是已验证传播结论。

## 8. 数据检查与失败残留

权威候选：

```text
DATASET=/Users/futaoran/Desktop/ICLR2027/CSI_HANDOFF_20260809T032602Z/project/generated_datasets/csi_pairs_v2_1_v6_sionna_osm_candidate_20260809T091000Z_final_candidate/dataset.npz
DATASET_BYTES=22399401
DATASET_SHA256=6534777ee33d6cc2f4b964b60e7a6fcd5f8bb14fd9b4714e19cb300c9a9bd5fc
```

只有以下完整 retry 目录是成功的原生 `inspect-data` 证据：

`/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/outputs/20260809T074722Z/formal_inspect_data_retry1`

它的 stdout 状态为 `PASS`，wall time `25.69 s`，并同时生成 `data_contract.json` 与 `manifest.json`。分类 sidecar：

`/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/outputs/20260809T074722Z/formal_inspect_data_retry1_classification.json`

首次目录 `formal_inspect_data/` 不是成功证据。首次命令因 `main runtime hashed installer report is missing` 失败，但在失败前留下了内部 `status=PASS` 的孤立 `data_contract.json`。该 partial 文件必须与失败 stderr 一起解释，禁止单独引用为成功运行。

补充结构审计：

```text
NPZ_FIELDS=35
BANKS=34
CITIES=6
WORLDS=4
POSITIONS_PER_BANK=256
REPEATS=3
REPEAT_OBSERVATIONS=104448
UNIQUE_REPEAT_SEEDS=104448
SPLIT_IDENTITY_INTERSECTIONS=0
TARGET_SUPPORT_QUERY_INTERSECTIONS=0
PATH_SLOT_ALIGNMENT=PASS
SURFACE_CATALOG_ALIGNMENT=PASS
PHASE_REFERENCE_STRUCTURE=PASS
DATASET_SHA256_MANIFESTS_CONSISTENT=PASS
SHA256SUMS_DATASETS=471/471_PASS
```

原生 contract 的 `scientific_use=CANDIDATE` 和 manifest 的 `CANDIDATE_NOT_CLAIM` 是上游原生字段；本轮最终解释以 classified sidecar 和本报告为准。原生 metadata 中 `engine.deterministic=true` 只能视为候选声明，不能替代实测 exact gate。`external_reference.available=true` 与同一对象的 `PENDING-INDEPENDENT-ENGINE-EVIDENCE`/`independent-engine-rerender-required-not-yet-supplied` 相冲突；独立外部证据实际未提供。

## 9. 最终测试

最终聚焦集合：

```text
BACKEND_TESTS=2/2_PASS
ASSET_TESTS=3/3_PASS
VISIBILITY_CONFIG_TESTS=8/8_PASS
TOTAL=13/13_PASS
FAILURES=0
ERRORS=0
WARNINGS=0
```

两套执行均通过：

- 固定 `formal_venv` Python + 外部 pytest runner：`13/13`，过程 wall `5.11 s`。
- 纯固定 `formal_venv` 标准库 unittest：`13/13`，过程 wall `2.09 s`。

最终 unittest 记录：

`/Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM/logs/final_focused_unittest_13.log`

测试后 working、archive、原 handoff 中均无 `__pycache__`、`.pyc` 或 `.pyo`。

### 9.1 最终当前状态复核

`2026-08-09T09:28:37Z` 的只读复核没有重跑 RT，也没有修改 handoff 或已有 NPZ。复核结果：

```text
PINNED_RUNTIME_LIVE_PROBE=PASS
DRJIT_LLVM_VERSION=22.1.8
FORMAL_ASSET_LOADER=PASS_34_BANKS_34_SCENES_34_CLUSTERS_204_FILES
UPSTREAM_AFTER_FETCH=11595f168f9fcf36dc178aaee927b348d7c6402a_AHEAD_0_BEHIND_0_CLEAN
HANDOFF_SHA256=1439/1439_PASS
ARCHIVE_COPIED_FILES_SHA256=181/181_PASS
DATASET_SHA256SUMS=471/471_PASS
DELIVERY_SHA256SUMS=44/44_PASS
LOCAL_EXACT_GATE_RECOMPUTED=PASS_22/22_COMPARATOR_23/23_NPZ
LOCAL_A_VS_FROZEN_RECOMPUTED=NOT_EXACT_12/22
NONFINITE_NUMERIC_FIELDS_A=0
NONFINITE_NUMERIC_FIELDS_B=0
ACTIVE_M4_GATE_PROCESSES=0
```

运行时 probe 直接调用 `dr.detail.llvm_version()`，得到 `(22, 1, 8)`；34-bank probe 从目标 `CSI-PAIRS-v2.0-server` 工作目录以 `python -P -B` 和显式 `PYTHONPATH` 加载，避免工作区顶层同名 `formal_v2` 包遮蔽。两次更早的失败 probe 分别来自不存在的 `drjit.llvm_version()` 和错误导入根，只是 probe 构造错误，不是运行时或资产失败。

## 10. 实测耗时与容量估计

| 阶段 | 实测 wall time |
|---|---:|
| 资产构建 | `0.60 s` |
| 资产独立验证 | `0.09 s` |
| LLVM bank A | `458.42 s` |
| LLVM bank B | `462.70 s` |
| comparator 成功重跑 | `0.13 s` |
| independent exact gate | `0.07 s` |
| scene 27 单因素诊断 | `382.09 s` |
| formal inspect-data retry1 | `25.69 s` |
| final candidate structural audit | `0.43 s` |
| final focused unittest | `2.09 s` |

上述核心成功命令合计约 `1,331.62 s = 22 m 11.62 s`。它不含环境下载、LLVM 重定位、协议调试、失败证据保留、人工审阅和日志整理。

从成功 preflight 时间 `2026-08-09T07:25:18Z` 到分类/最终测试证据记录 `2026-08-09T08:45:49Z`，本轮端到端工程闭环约 `1 h 20 m 31 s`。这比纯仿真时间长，主要差异来自 runtime 建设、macOS 兼容修复、Bash 3.2 修复和证据审计。

仅按 scene 0 两次平均 `460.56 s/bank` 线性外推，34 bank 单进程单遍约 `4 h 21 m`，两遍约 `8 h 42 m`。这是粗略工程估计，不是承诺；bank 复杂度、并行资源竞争和完整生成步骤会改变实际时间。

报告前容量快照：

```text
CSI_M4_LOCAL_SIM_APPARENT_SIZE=5.3G
RUNTIME_APPARENT_SIZE=5.0G
AUTHORITATIVE_OUTPUT_APPARENT_SIZE=3.9M
DATA_VOLUME_AVAILABLE=349Gi
```

`runs/` 下另有并发启动的完整候选任务，未纳入本报告 gate 和 checksum 集合，也未被本轮停止或修改。`2026-08-09T09:28:37Z` 快照中，本报告 A/B gate 进程数为 `0`，`CSI_M4_LOCAL_SIM/runs/m4-formal-*` 对应 Python `render-shard` 进程数也为 `0`；其他 worktree 和 `CSI_M4_PAPER_OUTPUTS` 中共有 `16` 个外部 Python `render-shard` 进程，属于并行用户任务，本轮没有启动、停止或修改它们。当前 `runs/` 目录约 `33M`。

## 11. 修改文件与哈希

相对 archive 修改的 5 个文件：

```text
7b988c1fbd0579f57e992b67f753021f6d2e79641efc787ddb671e698c637127  artifacts/formal_readiness/tools/audit_rt_visibility.py
0aea80e00c1a010602a3b727496c71864c68ea4c822c6e1d2c248997b078fed3  artifacts/formal_readiness/tools/render_sionna_bank_backend_diagnostic.py
141a77b6d736f5b87f39682df59b11c9b6c8560c14563b08e0774a30df593668  code/CSI-PAIRS-v2.0-server/formal_v2/scripts/setup_formal_v2.sh
ea7386313c3e5b4c8fcf5a4621cbade72b5a95e307b363eff41f9368803f39d9  code/CSI-PAIRS-v2.0-server/formal_v2/sionna_osm_candidate.py
e51ae61b296af0cd6c422a1cecb822bf67ffef02122351dd1a8b80d988128402  code/CSI-PAIRS-v2.0-server/formal_v2/tests/test_pre_run_regressions.py
```

新增的 5 个工作副本文件：

```text
a52892f873c8bc54005f79250676cd602065a6af4993228c778050047a5d10c4  artifacts/formal_readiness/configs/sionna_visibility_one_factor_v1.json
dd907d1387a632219802cd872f7075ccfa8219142b32f89abda991fbedf6abe6  artifacts/formal_readiness/tools/diagnose_sionna_visibility_one_factor.py
af42e36fdfff9725591d03899db12e5a831cd5a3185c4eb598395140c230759c  code/CSI-PAIRS-v2.0-server/formal_v2/sionna_scene0_diagnostic_assets.py
a22be7c725edd06ae4fb4a3cb289083c2ff72b4fa3cd438d48bf23a862733bc4  code/CSI-PAIRS-v2.0-server/formal_v2/tests/test_sionna_scene0_diagnostic_assets.py
6679637517a8117b40f1a70a93a038eed9f6c0ae19e2ed597df72d2bc0efe9a0  code/CSI-PAIRS-v2.0-server/formal_v2/tests/test_sionna_visibility_one_factor_diagnostic.py
```

## 12. Go / No-Go 决策

本机工程节点：`GO`。

```text
M4_LOCAL_READY=YES
```

正式训练与论文证据：`NO-GO`。

```text
FORMAL_DATA_READY=NO
FORMAL_STATUS=POST_AUDIT_NO_GO
SCIENTIFIC_USE=DIAGNOSTIC_NOT_FORMAL_EVIDENCE
FORMAL_SCIENTIFIC_USE=FORBIDDEN
```

阻断正式使用的核心原因：

1. 候选的整体 no-path 比率为 `46.31%`，target 为 `50.73%`；机器审计仍是 `NOT_ASSIGNED_REQUIRES_FROZEN_PROTOCOL`，因此可见性质量尚未取得资格，正式使用维持保守 No-Go。
2. 本机 LLVM A/B exact 不等于冻结候选 exact；全 34 bank 正式 exact-regeneration gate 仍未通过。
3. 独立第二引擎或受控测量证据尚未提供。
4. refraction/material thickness 等传播设置尚未跨 bank 校准与人工冻结。
5. 原生 metadata 的 deterministic/external-reference 字段不能替代独立实测证据。

在人工冻结传播协议并重新生成、通过全量 exact regeneration、可见性质量资格门控和独立外部验证之前，不得把这批诊断输出用于正式训练结论或论文 claim。

## 13. Ultra 只读复审

仅在本报告已经支持 `M4_LOCAL_READY=YES` 后，才启动了一次 `GPT-5.6 Sol / Ultra` 只读复审。Ultra 未编辑或生成文件，只检查：

1. macOS 修改是否破坏 Linux CUDA 默认路径；
2. A/B 零容差证据是否可信且未越界解释；
3. 可见性结论是否与产物一致。

复审结论：

```text
ULTRA_READ_ONLY_REVIEW=PASS_WITH_NONBLOCKING_FINDINGS
ULTRA_REVIEW_BLOCKERS=0
M4_LOCAL_READY_CAN_STAND=YES
```

Ultra 的三个非阻断发现及 Max 处理：

1. 可见性机器状态是 `NOT_ASSIGNED_REQUIRES_FROZEN_PROTOCOL`，原报告的硬 FAIL 状态过强。Max 已改为 `VISIBILITY_QUALITY=NOT_QUALIFIED`；正式 No-Go 不变。
2. 原 `verify_scene0_exact_gate.py` 的 standalone `two_fresh_process_manifests` 名称比脚本自身覆盖更强，且脚本本身不检查 finite。最终 exact 决策继续要求 core exact gate 与 `scene_00_fresh_process_audit.json` 联合成立；后者绑定不同路径、非重叠时间窗、共同输入和 finite 检查。该残余是 standalone gate 的命名/覆盖边界，不影响当前联合证据。
3. 原 `12/22` local-vs-frozen 只在 sidecar 汇总。Max 已新增完整、分类后的逐字段 comparator `scene_00_local_vs_frozen.comparison.json` 并绑定其哈希。

Ultra 同时确认 Linux CUDA 默认环境构造未改变，但该证据仍是 macOS 上的合成 Linux prerequisite/static equivalence probe，不等同于真实 Linux CUDA/OptiX 动态加载或 GPU 执行测试。

## 14. 下一步

```text
NEXT_ACTION=HUMAN_FREEZE_VISIBILITY_PROTOCOL
```

当前最短且安全的科学下一步不是直接宣称数据可训练，而是人工审阅并冻结 refraction、max-depth 或采样范围方案。冻结前保持：

```text
FORMAL_DATA_READY=NO
FORMAL_STATUS=POST_AUDIT_NO_GO
SCIENTIFIC_USE=DIAGNOSTIC_NOT_FORMAL_EVIDENCE
FORMAL_SCIENTIFIC_USE=FORBIDDEN
```

本轮交付文件的最短完整性复核命令：

```bash
cd /Users/futaoran/Desktop/ICLR2027/CSI_M4_LOCAL_SIM
shasum -a 256 -c M4_LOCAL_SIM_SHA256SUMS
```
