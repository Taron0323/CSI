# 外部无线数据集下载记录

下载日期：2026-08-09  
根目录：`datasets/external_wireless/`

本目录将原始压缩包、解压数据、代码快照和访问受限数据的元数据分开保存。这里的“完整”只表示对应公开下载项已完整取得并通过文件级校验，不代表数据已满足 CSI-PAIRS 的科学有效性门槛。

当前下载范围已收敛为四类代表性核心数据，整个目录硬上限为 `60,000,000,000` bytes。遇到登录、Restricted 或付费来源时，改用无需登录且任务最接近的公开替代；原始来源状态与替代状态分别记录。精确选择和完成语义见 `CORE_SUBSET_PLAN.md`，机器复验使用 `verify_core_subset.py`。

## 状态总览

| 数据集 | 当前状态 | 已取得内容 | 尚未取得内容 |
| --- | --- | --- | --- |
| DeepMIMO | 核心子集完成 | `asu_campus_3p5` 与 `i1_2p5` 原始 ZIP、解压场景、官方仓库和独立 Python 环境 | 无 |
| UrbanMIMOMap | 核心子集完成 | 完整官方代码/样例快照，以及 map 0 的全部 120 个本地有效 `.npz` 文件 | 无 |
| RadioMapSeer | 公开核心完成 | 主包、Loc、ToA、`RadioMap3DSeer.zip` 和 RadioUNet | 原始 `IRT2HighRes.zip` 需付费，未取得；3D 包是公开替代 |
| WWM | 公开替代核心完成 | Zenodo 元数据；DeepSense Scenario 8 + 33 多模态实测数据 | 原始 WWM 文件 Restricted，未取得；DeepSense 不是原始 WWM |

## 1. DeepMIMO

来源：

- 官网：<https://www.deepmimo.net/>
- 文档：<https://deepmimo.github.io/DeepMIMO/>
- GitHub：<https://github.com/DeepMIMO/DeepMIMO>

本地内容：

- `DeepMIMO/deepmimo_scenarios/asu_campus_3p5_downloaded.zip`：官方场景原始包，30,558,838 bytes
- `DeepMIMO/deepmimo_scenarios/asu_campus_3p5/`：解压后的完整场景
- `DeepMIMO/repository/`：官方 Git 仓库，提交 `8f616f58d643adcb4fc9aa021017486668a4a7fd`
- `DeepMIMO/.venv/`：独立环境，安装 `deepmimo==4.0.3`
- `DeepMIMO/download_all_scenarios.py`：逐场景申请官方地址、断点下载、ZIP CRC 和 SHA-256 校验的下载器
- `DeepMIMO/all_scenario_zips/i1_2p5.zip`：完整室内场景，2,445,139,772 bytes；1,413 个 ZIP 成员全部通过 CRC，SHA-256 为 `186a775040f6bc45ddae8097b555454df5620ae17d76a2274facd9f583c2d29e`

已实际加载场景，验证结果为 131,931 个接收位置，`power.shape == (131931, 10)`，`rx_pos.shape == (131931, 3)`。

复验命令：

```bash
(
cd datasets/external_wireless/DeepMIMO
.venv/bin/python - <<'PY'
import deepmimo as dm

dataset = dm.load('asu_campus_3p5')
print(dataset.power.shape)
print(dataset.rx_pos.shape)
PY
)
```

## 2. UrbanMIMOMap

来源：

- GitHub：<https://github.com/UNIC-Lab/UrbanMIMOMap>
- 论文：<https://arxiv.org/abs/2509.06270>
- 完整数据下载入口位于官方仓库 README（百度网盘；OneDrive 提供部分地图）

本地内容：

- `UrbanMIMOMap/repository-main.zip`：官方源码 ZIP
- `UrbanMIMOMap/repository_snapshot/UrbanMIMOMap-main/`：解压快照，对应官方提交 `d614b3b0153ab0f29bc26fb2f47cc0cdfe3757a4c`
- `UrbanMIMOMap/channelMatrix/resu_npz_map_0/`：从官方仓库列出的公开 OneDrive 分享逐文件取得的完整 map 0，共 120 个 `.npz` 文件

仓库快照包含代码和 6 个官方样例 `.npz`。OneDrive 的匿名共享页显示完整 `resu_npz_map_0` 为 120 项、2.45 GB；该分享不提供匿名文件夹整包下载，因此通过页面公开的逐文件下载入口取得全部 120 项。未使用浏览器凭据、账号令牌或访问控制绕过。

当前核心选择只保留一个完整地图的全部 Tx/Rx 配置，不下载约 350 张地图的完整集合，以满足 60 GB 硬上限。`resu_npz_map_0` 的文件名集合已精确核对为 `0_0_{0,60,120}.npz` 到 `0_39_{0,60,120}.npz`，无缺失或多余文件。

已逐个打开全部 120 个下载文件：每项只包含 `coords`、`matrices`，形状分别为 `(262144, 3)` 和 `(262144, 4, 4)`；`bad_npz=[]`。全部 120 项均已写入 `SHA256SUMS`。

抽检命令：

```bash
datasets/external_wireless/DeepMIMO/.venv/bin/python - <<'PY'
import numpy as np

path = 'datasets/external_wireless/UrbanMIMOMap/channelMatrix/resu_npz_map_0/0_0_0.npz'
with np.load(path) as item:
    print(item.files)
    print(item['coords'].shape)
    print(item['matrices'].shape)
PY
```

## 3. RadioMapSeer

来源：

- 官方页面：<https://radiomapseer.github.io/>
- IEEE DataPort：<https://ieee-dataport.org/documents/dataset-pathloss-and-toa-radio-maps-localization-application>

本地内容：

- `RadioMapSeer/RadioMapSeer.zip`：官方公开主数据原始包，3,259,544,919 bytes
- `RadioMapSeer/RadioLocSeer.zip`：作者 LocUNet 页面公开镜像，921,324,526 bytes，63,575 个 ZIP 成员
- `RadioMapSeer/RadioToASeer.zip`：作者 LocUNet 页面公开镜像，2,996,448,454 bytes，1 个 ZIP 成员
- `RadioMapSeer/RadioMap3DSeer.zip`：RadioFlow 项目引用的公开 Google Drive 镜像，1,535,957,450 bytes；完整 ZIP CRC 已通过
- `RadioMapSeer/data/`：完整解压数据，约 3.9 GB
- `RadioMapSeer/RadioUNet-master.zip`：官方 RadioUNet 源码 ZIP
- `RadioMapSeer/RadioUNet_repository/`：解压后的代码快照，对应提交 `36ab70663443af615c37051ce97da14d04925c7a`

主 ZIP 已通过 CRC 检查。解压结果包含 355,408 个文件：`antenna/` 701 个、`gain/` 227,124 个、`png/` 91,831 个、`polygon/` 35,751 个；`Dataset.csv` 共 702 行。

`RadioLocSeer` 和 `RadioToASeer` 已通过作者项目页的公开 Google Drive 镜像取得；`RadioMap3DSeer` 已通过 RadioFlow 项目公开列出的 Google Drive 镜像取得。三者均已核对实际字节数、完整 ZIP CRC 和 SHA-256。IEEE DataPort 账号登录后，`IRT2HighRes.zip` 仍显示 `SUBSCRIBE TO ACCESS DATASET FILES`；该付费项已按用户要求跳过，不会绕过访问控制。

CRC 复验：

```bash
unzip -t datasets/external_wireless/RadioMapSeer/RadioMapSeer.zip
unzip -t datasets/external_wireless/RadioMapSeer/RadioUNet-master.zip
```

## 4. Wireless World Model (WWM)

来源：

- Zenodo 社区：<https://zenodo.org/communities/wwm/>
- 3D 点云记录：<https://zenodo.org/records/18919467>

`WWM/zenodo_community_records_metadata.json` 保存了社区当前 6 条记录的公开元数据：

- `18781953`：Wireless World Model - Test Dataset
- `18783399`：Wireless World Model - Field Dataset
- `18785355`：Wireless World Model - Train Dataset
- `18797221`：Wireless World Model - Beam Prediction Dataset
- `18919467`：Wireless World Model - 3D Point Clouds
- `18889383`：Wireless World Models - Checkpoints

这些记录的描述页和元数据公开，但文件全部标记为 Restricted，匿名 API 不返回文件列表。2026-08-09 已通过 ORCID 完成 Zenodo 登录，账号仍未获得共享权限。按“遇到账号/受限来源就换公开类似数据”的策略，不再继续尝试 WWM 登录或访问控制。

公开替代保存在 `WWM/alternatives/DeepSense6G/`：

- `official_scenarios_metadata.json`：DeepSense 官方场景元数据快照
- `substitution_manifest.json`：原始 WWM 状态、替代选择、精确大小、CRC、SHA-256 和等价性边界
- `scenario8.zip`：McAllister Ave，4,043 个样本，RGB、GPS、64 维 60 GHz 接收功率和 2D LiDAR，910,993,649 bytes
- `scenario33.zip`：College Ave，3,981 个样本，RGB、GPS、64 维 60 GHz 接收功率、3D LiDAR 和 FMCW 雷达，5,162,587,957 bytes

两包合计 8,024 个多模态样本和 6,073,581,606 bytes，小于 10 GB 选择预算，并保留两个地点和至少一个 3D 点云场景。它们适合多模态波束预测和感知辅助无线学习，但不是 WWM 的 `test_gen_city.zip`、3D 城市点云、训练 CSI 或检查点。

## 完整性校验

`SHA256SUMS` 覆盖原始下载文件。请在本目录执行：

```bash
cd datasets/external_wireless
shasum -a 256 -c SHA256SUMS
python3 verify_core_subset.py --deep
```

2026-08-09 最终复验：`SHA256SUMS` 的 133/133 项通过；深度 ZIP/NPZ CRC 通过；`training_core_complete=true`、`all_original_sources_complete=false`、`under_hard_limit=true`；目录表观大小为 `23,857,786,425` bytes，未发现 `.part` 文件。

验证器同时输出 `training_core_complete`、`all_original_sources_complete` 和 `under_hard_limit`，避免把公开替代误写成原始来源完成。解压目录未逐文件写入 SHA-256 清单；DeepMIMO 使用实际加载验证，RadioMapSeer 和 DeepSense 使用原始 ZIP CRC，UrbanMIMOMap 的 120 个 `.npz` 均执行结构检查并逐文件写入 SHA-256 清单。

## 科学使用边界

下载成功、压缩包完整和代码可加载属于工程就绪检查，不构成数据适配、无泄漏、独立物理读出、场景独立性或论文结论的科学证据。用于 CSI-PAIRS 正式实验前，仍需按项目的数据合同、许可记录、资格门槛和正式验证流程处理；不要把工程完整性写成科学有效性结论。
