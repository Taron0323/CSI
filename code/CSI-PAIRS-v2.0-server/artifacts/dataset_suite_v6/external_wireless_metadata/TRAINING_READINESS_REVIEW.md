# 外部无线数据训练就绪审查

审查日期：2026-08-09

## 结论

这批数据足够训练和比较一批有意义的工程基线，也足够开发 CSI、位置、无线地图和多模态传感器的数据适配器；但不够复现原始 WWM，也不够直接支撑 CSI-PAIRS 的论文级科学结论。

| 目标 | 结论 | 主要原因 |
| --- | --- | --- |
| RadioUNet/LocUNet 类 pathloss、ToA 或定位基线 | YES | RadioMapSeer、RadioLocSeer、RadioToASeer 和 RadioMap3DSeer 已取得 |
| DeepMIMO 信道/位置/pathloss 基线 | YES | 室外 `asu_campus_3p5` 与室内 `i1_2p5` 均已取得 |
| UrbanMIMOMap 单地图 MIMO 预测或表征学习 | YES | map 0 的 120/120 个 NPZ 可读，共 31,457,280 个逻辑样本行 |
| DeepSense 多模态波束预测/传感器融合 | YES, BASELINE SCALE | Scenario 8 + 33 共 8,024 个样本，含两个地点、64 维无线功率、GPS/RGB 和 LiDAR |
| 3D LiDAR/雷达辅助无线学习 | YES, PILOT SCALE | Scenario 33 有 3,981 个对齐样本，适合小模型、微调和消融，不适合声称大规模预训练 |
| 跨地点泛化实验 | CONDITIONAL | 可按 McAllister/College 切分共同模态；硬件代际和 2D/3D LiDAR 差异会形成混杂因素 |
| 原始 WWM 复现或 Wireless World Model 预训练 | NO | 缺少原始 WWM 城市点云、train/test CSI、检查点和论文定义的数据管线 |
| CSI-PAIRS 正式阶乘训练与论文证据 | NO | 缺少成对干预、独立重复、共享相位参考、路径/材质映射和足够独立城市 |

## 已取得数据与可做任务

- DeepMIMO：`asu_campus_3p5` 和 `i1_2p5`，可做合成信道、位置、功率与室内/室外域差异实验。
- UrbanMIMOMap：map 0 的全部 120 个配置，可做单地图内 MIMO 表征或预测；独立环境数仍为 1。
- RadioMapSeer：主包、Loc、ToA 和 3D 几何包，可做 radio-map、定位、ToA 与几何条件基线。付费 `IRT2HighRes.zip` 未取得，`RadioMap3DSeer.zip` 是替代而非同一文件。
- DeepSense Scenario 8：4,043 个 McAllister Ave 样本，提供 RGB、GPS、64 维功率和 2D LiDAR。
- DeepSense Scenario 33：3,981 个 College Ave 样本，提供 RGB、GPS、64 维功率、3D LiDAR 和 FMCW 雷达。

## 推荐切分

- DeepSense 主实验只使用两场景共有的 RGB、GPS 和 64 维功率时，可用 Scenario 8 训练、Scenario 33 外部测试，再反向复验。不要把传感器硬件变化误归因为纯地点泛化。
- 3D LiDAR/雷达实验只能在 Scenario 33 内按 `seq_index` 分组切分，不能逐行随机切分；否则同一采集序列会泄漏到训练和测试。
- RadioMapSeer 按 city map 切分；DeepMIMO 按 scenario 切分；UrbanMIMOMap 当前只能做 map-0 内按 Tx/配置分组的训练/验证。
- 四个来源没有天然的样本级配对关系，不能通过机械拼接补造 CSI-PAIRS 所需的成对干预语义。

## 科学使用边界

`CSI-PAIRS-v2.1-server/formal_v2/DATA_CONTRACT.md` 还要求 `csi_repeat`、`csi_clean`、`maps`、`noop_maps`、`occupancy`、`height`、`material`、`free_space`、`repeat_seeds`、`phase_reference_ids`、`path_ids`、`path_power`、`path_surface_ids` 和 `primitive_surface_ids`，并要求多个源/目标城市、每城多个 bank 和至少 3 次重复。

当前公开核心子集不满足这些形式语义。因此 CSI-PAIRS 的模型有效性、跨城市泛化和几何扎根仍是待验证命题；项目科学状态保持 `POST_AUDIT_NO_GO` 与 `scientific_use=FORBIDDEN`。ZIP CRC、SHA-256 和可加载性只证明工程完整性，不证明无泄漏、校准有效或论文主张成立。

## 最终复验

- `verify_core_subset.py --deep`：四类训练核心均为 `COMPLETE`，`training_core_complete=true`。
- 原始 WWM 和付费 IRT2 未取得，因此 `all_original_sources_complete=false`；DeepSense 和 RadioMap3DSeer 的公开替代均完成。
- `SHA256SUMS`：133/133 项通过。
- 目录表观大小：`23,857,786,425/60,000,000,000` bytes。
- `.part` 残留：0。
