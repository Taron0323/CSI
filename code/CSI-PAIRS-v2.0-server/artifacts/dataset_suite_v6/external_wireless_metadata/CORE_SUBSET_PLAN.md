# 60 GB 外部无线数据核心子集计划

更新日期：2026-08-09

完成标准是四类数据各有可实际读取、具有代表性的核心内容，且 `external_wireless/` 整个目录的表观大小严格小于 `60,000,000,000` bytes。原始来源受限或付费时，改用无需登录、公开可下载且任务最相近的数据；替代数据必须单独标记，不能冒充原始文件。

## 选择原则

- 优先保留 CSI/无线功率、位置、几何、ToA 和独立环境验证能力，避免下载大量同地点重复场景。
- 原始 ZIP 必须核对官方字节数、完整 ZIP CRC 和 SHA-256；NPZ 必须可由 NumPy/ZIP 读取。
- 登录页、公开元数据、代码仓库和未完成的 `.part` 文件不计为数据集完成。
- 工程下载成功不构成 CSI-PAIRS 的科学有效性证据。

## 核心目标

| 来源 | 核心子集 | 选择理由 | 原始来源状态 | 公开替代状态 |
| --- | --- | --- | --- | --- |
| DeepMIMO | `asu_campus_3p5` + `i1_2p5` | 室外校园与室内场景，覆盖基本域差异 | 已取得并校验 | 不适用 |
| UrbanMIMOMap | `resu_npz_map_0` 的 120 个 NPZ | 保留一张完整地图的全部 Tx/Rx 配置 | 已取得并校验 | 不适用 |
| RadioMapSeer | 主包、Loc、ToA、3D | 覆盖 pathloss、定位、ToA 与 3D 几何 | `IRT2HighRes.zip` 需 IEEE 付费，未取得 | `RadioMap3DSeer.zip` 已取得并校验 |
| WWM | 原计划为 `test_gen_city.zip` + 3D Point Clouds | 原始 WWM 可用于其论文设定的城市生成与几何建模 | Zenodo Restricted，未取得 | DeepSense 6G Scenario 8 + 33，共 `6,073,581,606` bytes |

## WWM 替代选择

- Scenario 8：McAllister Ave，4,043 个样本，RGB、GPS、64 维 60 GHz 接收功率和 2D LiDAR，`910,993,649` bytes。
- Scenario 33：College Ave，3,981 个样本，RGB、GPS、64 维 60 GHz 接收功率、3D LiDAR 和 FMCW 雷达，`5,162,587,957` bytes。
- 两包来自不同地点，合计 8,024 个多模态样本；共同模态可用于跨地点训练/验证，Scenario 33 单独提供 3D 点云与雷达。
- Scenario 31、32、34 不纳入核心子集。31/32 的异常慢分片已停止并删除，避免为同类模态额外占用约 17.44 GB。

该选择小于用户给出的 10 GB 替代预算，同时保留至少一个 3D LiDAR 场景和两个地点。它适合多模态波束预测、感知辅助无线学习和适配器开发，但不等价于 WWM 的训练/测试数据、3D 城市点云或检查点。

## 复验与完成语义

```bash
cd /Users/futaoran/Desktop/ICLR2027/datasets/external_wireless
python3 verify_core_subset.py --deep
shasum -a 256 -c SHA256SUMS
```

验证器分别报告：

- `training_core_complete`：每类数据的原始核心或明确公开替代至少有一个完成。
- `all_original_sources_complete`：只在原始 WWM 和 IRT2 等指定文件也实际取得时才为真。
- `under_hard_limit`：整个目录是否小于 `60,000,000,000` bytes。

因此，公开替代全部通过后可以称为“60 GB 内训练核心子集完成”，但不能称为“原始 WWM/IRT2 全部下载完成”。

最终结果（2026-08-09）：`training_core_complete=true`，目录表观大小 `23,857,786,425/60,000,000,000` bytes，133/133 个 SHA-256 条目和全部深度 CRC 检查通过，无 `.part` 残留。
