# CSI-PAIRS Dataset Suite V6

快照日期：2026-08-09  
权威研究口径：`00_FROZEN_SPECS/` 中的 v6 文档  
当前科学状态：`POST_AUDIT_NO_GO`  
当前科学使用权限：`scientific_use=FORBIDDEN`

## 这是什么

这是一个按 CSI-PAIRS v6 科学角色整理的独立数据套件。它把现有数据复制到同一棵目录下，保存来源、角色、规模和哈希，并把“已经下载”“结构可读”“满足数据资格”“足以支持论文结论”四件事严格分开。

本目录的存在不表示 CSI-PAIRS 正式数据已经完成。当前可以确认的是：静态来源已复制；外部无线核心子集可以复验；部分 fixture 通过软件结构检查。当前不能确认的是：完整 formal 主数据、RT 资格、第二引擎同世界复追踪和论文主张是否成立。

## 目录

```text
CSI_PAIRS_DATASET_SUITE_V6/
├── 00_FROZEN_SPECS/                  冻结 v6 方案与数据合同副本
├── 01_FORMAL_MAIN_CANDIDATES/        可能接近 formal 结构的数据，但仍需逐项资格审计
├── 02_EXTERNAL_WIRELESS/             DeepMIMO、UrbanMIMOMap、RadioMapSeer、WWM 元数据/替代数据
├── 03_INDEPENDENT_ENGINE_QUALCOMM/    Qualcomm Wi3R/WiPTR，Remcom Wireless InSite 来源
├── 04_FIXTURES_SOFTWARE_ONLY/         仅供 loader、schema、训练链和复现测试
├── 05_INCOMPLETE_AND_FAILED_RUNS/     中间 candidate、单 scene diagnostic 和失败/未完成运行
├── 99_REGISTRY/                       哈希、复制审计和机器可读验证记录
├── DATASET_BLUEPRINT_V6.md            正式数据的完整构造蓝图
├── DATASET_CATALOG.json               每个本地数据实体的机器可读角色和状态
├── ROLE_ASSIGNMENTS.csv               允许用途与禁止用途
├── MISSING_ITEMS.md                    缺失项与 Go/No-Go
└── VERIFY_SUITE.sh                     套件内复验入口
```

## 当前已纳入的数据

| 目录 | 内容 | 当前可用性 | 不能据此声称什么 |
| --- | --- | --- | --- |
| `02_EXTERNAL_WIRELESS/external_wireless` | 363,263 个普通文件；DeepMIMO、UrbanMIMOMap map 0、RadioMapSeer 系列、WWM 元数据和 DeepSense 替代 | 外部基线、适配器开发、预先声明的外部域实验 | 不能当作 v6 sibling-world paired intervention 主数据 |
| `03_INDEPENDENT_ENGINE_QUALCOMM/qualcomm_wireless_indoor` | 190,590 个普通文件；Wi3R/WiPTR ZIP、HDF5、室内几何 | 独立引擎基线候选；许可补齐后可做预声明外部实验 | 不能把普通 layout/OOD split 写成同一 Tx/Rx 的单编辑配对；不能自动关闭第二引擎 gate |
| `01_FORMAL_MAIN_CANDIDATES/legacy_sionna_osm_34bank_POST_AUDIT_NO_GO` | 34 banks、4 worlds、256 positions、3 repeats | 结构与缺陷诊断 | 16,124/34,816 clean units 无路径且全零，禁止用于论文结果 |
| `04_FIXTURES_SOFTWARE_ONLY/*` | synthetic、dual-A100 Sionna fixture、smoke fixture | 软件测试、schema 测试、dry-run | 即使 contract `PASS` 也不是科学证据 |
| `05_INCOMPLETE_AND_FAILED_RUNS/*` | 较早 candidate 和单 scene diagnostics | 回归与故障分析 | 不是完整数据集，不得进入结果表 |

最新 M4 formal 生成已终止并失败：scene 12 出现 stable Sionna path identifier collision，只有 7/8 个完整 shard、没有 merge 产物。整个运行已快照到 `05_INCOMPLETE_AND_FAILED_RUNS/failed_m4_formal_20260809T080951Z_path_id_collision`，不得进入 formal main。未来新运行只有在所有 shard、merge、manifest/hash 和数据质量检查均通过后才能进入 candidate 区；生成成功也仍须经过 `DATASET_BLUEPRINT_V6.md` 和 `MISSING_ITEMS.md` 中的资格门。

## 你特别指出的 `external_wireless`

该目录已整体复制，而不是只复制几个 ZIP：

- DeepMIMO：`asu_campus_3p5`、完整 `i1_2p5.zip`、解压场景、官方代码和本地环境；
- UrbanMIMOMap：官方仓库快照和 map 0 的 120/120 个 NPZ；
- RadioMapSeer：主包、Loc、ToA、RadioMap3DSeer 公开替代和 RadioUNet；
- WWM：公开元数据；受限原始文件未取得；本地实际数据是 DeepSense Scenario 8+33 替代，共 8,024 个样本。

必须保留两条真实性边界：

1. `RadioMap3DSeer.zip` 不是付费的原始 `IRT2HighRes.zip`。
2. DeepSense Scenario 8+33 不是原始 WWM train/test/field/point-cloud/checkpoint 数据。

套件副本内的 `verify_core_subset.py --deep` 和 `SHA256SUMS` 可复验公开核心；其正确结论应同时为：

```text
training_core_complete=true
all_original_sources_complete=false
```

## 副本语义

静态数据使用 macOS APFS clone copy (`cp -cRp`) 建立。目标是独立路径和独立 inode，不是软链接；删除源路径不会删除此副本。APFS 可以在未修改时共享底层数据块，因此 Finder/`du` 的逻辑大小不等于立即新增的物理占用。套件根目录和每个数据根都必须保持为真实目录。

`external_wireless/DeepMIMO/.venv/bin` 内保留了源数据已有的 3 个 Python 环境符号链接，其中 `python3.12` 指向本机 Python Framework。这些是环境内部链接，不是数据根链接；跨机器复现时应重建环境，不应把该绝对链接当作可移植运行时。

## 使用规则

1. 先从 `DATASET_CATALOG.json` 和 `ROLE_ASSIGNMENTS.csv` 查用途，不按文件名猜用途。
2. headline Stage-0 teacher 只能读取注册账本中的 `source-encoder-train` CSI；不得静默混入 external 数据。
3. fixture、diagnostic、failed run、旧 pathless candidate 永远不能填论文结果表。
4. 外部数据若用于论文，必须单列适配、许可、split、泄漏检查和超参数选择来源。
5. Qualcomm 若要关闭第二引擎 gate，必须对同一批已注册 sibling worlds、相同 Tx/Rx 和相同物理配置重新追踪；现有 Wi3R/WiPTR 本身不满足这一条件。
6. 任何 schema `PASS` 都只代表结构通过；后续还要通过 RT qualification、route、teacher/readout、No-X、shortcut、retention、shuffled-pair、四臂和 external-validity gates。

## 验证

在套件根运行：

```bash
./VERIFY_SUITE.sh
```

2026-08-09 的最终完整验证为 `SUITE_VERIFICATION=PASS checks=20 mode=full`。它检查目录类型、机器可读 catalog、精确文件数/字节数、external 133 项 SHA-256、external 深度 ZIP/NPZ 校验、Qualcomm 关键 ZIP/HDF5 哈希、失败运行快照、关键 candidate/fixture 哈希和残留部分下载文件。验证通过只证明套件副本与登记状态一致，不会把 `POST_AUDIT_NO_GO` 改为 scientific Go。短报告见 `99_REGISTRY/FINAL_VERIFICATION.md`。
