# CSI-PAIRS v6 当前缺失项与 Go/No-Go

审计日期：2026-08-09  
结论：数据资产已经很多，但 formal 主数据和科学证据链仍未闭合。项目保持 `POST_AUDIT_NO_GO`，`scientific_use=FORBIDDEN`。

## 1. 一眼结论

| 层级 | 当前状态 | 判定 |
| --- | --- | --- |
| 静态数据复制 | 12 个 catalog 目标路径存在；仅 external、Qualcomm、latest failed M4 有源/目标复制审计 | `PARTIAL` |
| external 公开核心 | 四类公开核心可复验；133 项 SHA；无 partial | `PASS_WITH_SUBSTITUTIONS` |
| 所有 original external 来源 | 缺原始 IRT2HighRes 和原始 WWM 文件 | `NO` |
| Qualcomm 本地副本完整性 | 关键 ZIP/HDF5 已生成 SHA；源/目标规模一致 | `PASS` |
| Qualcomm 许可/provenance | 本地没有数据许可、来源 manifest、下载记录 | `NO_GO` |
| legacy 34-bank candidate | 结构存在，但 16,124/34,816 clean units 无路径且全零 | `NO_GO` |
| 新 M4 formal candidate | receiver protocol 与 scene-00 replay 已过，但 scene 12 path-ID collision；仅 7/8 shards、无 merge | `FAILED` |
| RT 与数据资格 | 没有完成冻结的 calibration/qualification 全链 | `NO_GO` |
| 论文科学证据 | teacher/readout、No-X、route、四臂、retention、external validity 均未形成正式结果 | `NO_GO` |

## 2. `external_wireless` 还缺什么

### 明确缺少的 original artifacts

- `RadioMapSeer/IRT2HighRes.zip`：IEEE DataPort 付费/订阅项，未取得。
- 原始 WWM train dataset。
- 原始 WWM test dataset。
- 原始 WWM field dataset。
- 原始 WWM beam-prediction dataset。
- 原始 WWM 3D point clouds。
- 原始 WWM checkpoints。

本地 `WWM/zenodo_community_records_metadata.json` 是公开元数据，不是数据文件。`RadioMap3DSeer.zip` 是公开 3D 几何替代，不是 `IRT2HighRes.zip`。DeepSense Scenario 8+33 是公开多模态替代，不是 WWM。

### 即使补齐 original artifacts，仍不自动满足 v6

- DeepMIMO 的两个 scenario 不是同一 bank 上的单编辑 sibling worlds。
- UrbanMIMOMap 当前只有一个完整 map，独立环境数为 1。
- RadioMapSeer 的 missing/removed building maps 没有自动提供 CSI-PAIRS 所需的共同 Tx/Rx、完整超立方体、clean/repeats、signed action 和 path-surface 证据。
- DeepSense 两个场景的硬件/传感器差异会混杂地点泛化。
- 四个来源之间没有天然样本级配对关系，不能机械拼接成 paired intervention。
- 任何 external 数据进入论文前仍需冻结许可证、版本、adapter、split、normalization 和调参权限。

## 3. Qualcomm Wi3R/WiPTR 还缺什么

### 本地记录缺口

- 数据 archive 的上游官方 SHA 或签名；当前只有本套件生成的本地 SHA。
- 下载 URL、下载日期、版本/commit、下载命令和原始响应记录。
- 数据集级 README 与字段词典。
- 数据许可证和再分发条款快照。
- Wi3R/WiPTR 与相关代码仓库许可证之间的明确边界。

代码许可证不能自动替代数据许可证。在补齐许可前，这一目录不得公开再分发，也不得被当作正式 paper artifact 发布。

### v6 语义缺口

- 没有同一 foundation 的 `d>=2` 完整 sibling-world hypercube。
- 没有为每条 paired edge 固定共同 Tx/Rx 的证据。
- 没有至少 3 次独立 observation repeats 与统一 phase reference。
- 没有 ID-free signed edit/action grid。
- 没有 primitive-surface IDs 与 path-surface interaction 映射。
- 没有 CSI-PAIRS 七块 source 权限账本、target support/query 和 unseen-city 账本。
- WiPTR 的 5 个拆墙 OOD layouts 与普通 validation 的 Tx/Rx 坐标无重合，不能直接当同位置 paired intervention。

### 若要作为“第二引擎”关闭 external-validity gate

必须将正式 CSI-PAIRS 注册的 foundation、world bits 和 edits 导入 Remcom Wireless InSite，在同一 Tx/Rx、载频、阵列和输出定义下重追踪，并报告跨引擎的 path loss、delay/angular spread、visible path count、route agreement 和模型结论稳定性。现有 Wi3R/WiPTR 只能作为独立引擎数据域基线候选。

## 4. formal 主数据的 P0 缺口

### P0-A：完整且合格的主 candidate

最新运行：

```text
$LOCAL_M4_ROOT/runs/m4-formal-20260809T080951Z
```

该运行已于 2026-08-09 终止。已通过的前置检查只有：

- receiver protocol：34/34 banks，每 bank 256 个 deterministic shared positions；
- scene-00 两次独立生成：23/23 fields byte-exact；
- scene-00：1,024 clean units 中 pathless=0、all-zero=0、nonfinite=0。

最终失败状态：日志在报错前完成 32/34 banks，但只有 7/8 个 shard 封口，实际完整 shard 覆盖 30 banks；worker-2 的 scene 10/11 因 scene 12 报错而没有形成 shard。scene 12 `osm-sionna-source-chicago-bank-06` 在 `_extract_paths` 触发 `stable Sionna path identifier collision`，没有 merge 产物。因此仍缺 8 个 shard 全部成功、严格 merge、完整 34-bank manifest/hash、全体 34,816 clean units 的 pathless/all-zero/nonfinite 审计、contract 检查和 fresh-output qualification。该失败 run 已完整快照并隔离，不能作为 candidate 使用。

另一运行 `CSI_M4_PAPER_OUTPUTS/sionna-osm-m4-v2-20260809T082513Z` 已出现硬失败：`source-chicago-bank-05` 只有 199 个 deterministic LOS candidates，低于 256。追加 visibility diagnostic 又发现 `target-boston-bank-01` 有 8 个 pathless/all-zero units，scene-10 没有产出。两套失败证据已快照到 `05_INCOMPLETE_AND_FAILED_RUNS` 并登记 233 项 SHA，不能与成功 shard 混合。

### P0-B：冻结 RT qualification protocol

需要在训练和看 arm 结果前冻结：

- path loss 分布与独立参考；
- RMS delay spread；
- angular spread；
- visible path count；
- path/surface matching 稳定性；
- phase/gauge 规则与 no-op noise floor；
- clean/repeat 独立性；
- engine/runtime/assets/config 复现与 hash。

### P0-C：CSI 可辨识性

当前候选只保存 `2 Tx antennas x 4 subcarriers`，即 Re/Im 展开后的 16 个通道。这个观测是否足够保留材料/几何编辑影响仍是待验证命题。必须做频率/阵列/子载波消融和 frozen teacher/readout retention 检查；不足时应扩充观测配置，而不是把低 coverage 写成方法失败。

### P0-D：edit 与 route 覆盖

- `d=2` 必须证明每个 source 有至少两个 target-sensitive branches。
- 必须有 physical-active、teacher-sensitive active、physical-null/teacher-null agreement 和 gray coverage。
- 必须有同族同量级 wrong-action 与 geometry-matched wrong-action。
- 若 `d=2` 无法稳定提供这些 coverage，则升级 `d>=3`。
- active gate、dead-zone 和 matching tolerance 只能从允许的 source 数据块冻结。

### P0-E：独立 bank 数与 power analysis

当前 34-bank profile 中，每个 source permission role 只有两个 banks，即 Austin/Chicago 各一个。这对 bank-level uncertainty 和 interaction CI 可能不足。必须在读正式结果前做 bank-level power/sensitivity 分析，并预注册最小有效 bank 数、bootstrap 层级和 downgrade rule。position/repeat/seed 不能替代独立 bank。

## 5. 正式科学证据仍全部缺失

以下都必须使用资格通过后的 fresh-output formal 数据重新运行，fixture/dry-run 不计：

- frozen CSI-only Stage-0 teacher 与独立 physical readout；
- teacher 的 target bitwise test 和输入 allowlist；
- route coverage、active/null/gray、teacher/physical agreement；
- No-X：移除 CSI、保持 map/action 后不应解决任务；
- no-action、copy-source、no-change、action-swap、wrong-action；
- shuffled pairing 和 variant/world-ID shortcut baselines；
- retention：监督信号必须保留在最终 `F(H,M)`，不能只留在将被丢弃的 head；
- 严格 `2x2` 四臂：baseline、alignment-only、response-only、full；
- equal-step/equal-FLOP/gradient-norm 与 mechanical-concatenation controls；
- unseen-position/edit/bank/city 与 target `k=0/8/32/128`；
- bank-macro 指标、多层配对 bootstrap 和预注册 interaction gate；
- 第二引擎同 worlds 重追踪或真实受控干预。

在这些证据完成前，“paired supervision 改善跨城定位”“alignment 与 response 有协同”“模型学习到几何机制”只能写作待验证命题。

## 6. Go/No-Go 总门

| Gate | 通过条件 | 当前 |
| --- | --- | --- |
| G-COPY | 所有登记静态源均有独立副本，源/目标规模一致，关键哈希通过 | `PARTIAL`；12 个 catalog 目标路径存在，但仅 3 项有源/目标复制审计 |
| G-EXTERNAL-FILES | external deep verify + 133 SHA | `PASS`；但 originals 不全 |
| G-LICENSE | 每个论文使用数据有明确许可证与再分发边界 | `NO_GO` |
| G-FORMAL-COMPLETE | 全部 shard/merge/hash/contract/quality 通过 | `PENDING` |
| G-RT-QUAL | 冻结物理资格协议通过 | `NO_GO` |
| G-ROUTE | active/null/gray 与 teacher/physical coverage 通过 | `NO_GO` |
| G-LEAKAGE | No-X、target allowlist、shortcut、shuffled-pair 通过 | `NO_GO` |
| G-FACTORIAL | 四臂、公平算力、机械拼接、interaction gate 通过 | `NO_GO` |
| G-EXTERNAL-VALIDITY | 同注册 worlds 的第二引擎或真实干预通过 | `NO_GO` |

当前最终判定：**工程数据套件可用，论文科学数据尚不可用。**
