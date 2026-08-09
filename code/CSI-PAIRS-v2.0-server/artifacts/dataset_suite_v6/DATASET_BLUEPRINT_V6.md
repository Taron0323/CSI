# CSI-PAIRS v6 数据集整体构造蓝图

本文把两份冻结 v6 文档转成数据层面的实施合同。若本文与 `00_FROZEN_SPECS/` 冲突，以冻结文档为准。

## 1. 最小逻辑单位

正式数据不是一堆互不相关的 CSI/地图样本。其层级必须是：

```text
city
└── bank/tile                         独立统计单位
    ├── canonical foundation          冻结底图与共同物理配置
    ├── d primitive edits             d >= 2，兼容、可逆、模型可见
    ├── K = 2^d sibling worlds        完整超立方体，K >= 4
    │   └── same receiver set X_b     所有 worlds 共同可用
    │       ├── clean CSI
    │       ├── >= 3 observation repeats
    │       └── paths/surfaces/evidence
    └── Hamming-1 directed edges      alignment/response 的 paired transitions
```

统计推断的最高层独立单位是 `bank/tile`。world、receiver position、edge direction、observation repeat 和训练 seed 都不能虚增场景样本量。共用同一 base map 的多个 bank 必须留在同一 split/cluster，并做去重或 inverse-degree weighting。

## 2. 每个 bank 怎样生成

### 2.1 先冻结 foundation 与 edit 语义

每个 bank 先冻结：城市、tile 边界、base map digest、BS pose、Tx/Rx array、载频、带宽/子载波、材料表、RT 配置、随机种子策略、许可证和 provenance。随后选择 `d >= 2` 个 primitive edits。

每个 edit 必须同时满足：

- 物理可实施、可逆，两个状态都有明确语义；
- edit 之间兼容，所有 `2^d` 个组合都能 canonical render；
- 能在模型输入地图中被观察到，而不是只改 simulator 内部参数；
- 有 ID-free signed action 表示，不能暴露 world/edit/scene ID；
- 能定位到 primitive surface IDs，支持路径机制分析；
- 包含 active/null 与困难错动作覆盖，而不只是“改了就一定大变化”。

bit 编码要在 bank 内随机置换。每个 world 都从冻结 foundation 和完整状态说明独立 canonical render，不能按 edit 顺序增量修改同一个文件，否则操作顺序会泄漏标签。

### 2.2 完整生成超立方体

对 `d` 个 edits 生成 `K=2^d` 个完整 sibling worlds。训练配对只使用 Hamming distance 为 1 的边；两个方向必须边对称、节点均衡采样。不得只生成自然图与若干单独编辑图形成星形结构，也不得把不同 scene 的相似地图硬拼成 paired worlds。

默认 `d=2` 时有 4 个 worlds、4 条无向 Hamming-1 边、8 条有向 transitions。若同族同量级 wrong-action、geometry-matched wrong-action 或 target-sensitive branching coverage 不足，必须升级到 `d>=3`，而不是放宽证据标准。

### 2.3 先求共同自由空间，再冻结 receiver positions

必须先生成全部 worlds 的 occupancy/free-space，计算：

```text
X_b = intersection_u FreeSpace(M_b,u)
```

然后只从 `X_b` 采样并冻结 receiver positions。所有 worlds、edits、repeats、paired directions 使用完全相同的 Tx/Rx 坐标和索引。不能逐 world 独立采样后用最近邻“配对”。

接收位置应在生成前通过 deterministic receiver protocol 检查唯一性、共同可行性和预注册的 LoS/NLoS/空间覆盖要求。位置不足是数据门失败，不应在生成后删除困难 world 来补齐。

### 2.4 完整交叉追踪

冻结 `X_b` 后，对所有 `bank x world x position` 完整追踪：

- `csi_clean`：clean RT channel；
- `csi_repeat`：至少 3 个独立 observation noise/hardware repeats；
- `repeat_seeds` 与 `phase_reference_ids`；
- maps/no-op maps、occupancy、height、material、free-space；
- receiver positions、BS pose/config、carrier/array/subcarrier metadata；
- path IDs、path power、delay/angle/interaction order；
- path surface IDs 与 primitive surface IDs；
- natural world index、anchor bits、signed edit/action grid；
- source/target permission、city/bank/base-map cluster 和 provenance digest。

clean CSI 用于 route、teacher target、alignment/response target 和主科学比较；repeat 只用于噪声稳健性、no-op floor 和校准检查。repeat 不能冒充新的 clean physical scene。

## 3. 数据规模怎样计数

令 bank 数为 `B`、world 数为 `K`、每 bank receiver positions 为 `N`、observation repeats 为 `R`：

```text
clean units       = B * K * N
repeat units      = B * K * N * R
undirected edges  = B * d * 2^(d-1) * N
directed edges    = B * d * 2^d * N
```

当前 34-bank、`d=2`、`K=4`、`N=256`、`R=3` 的候选 profile 应有 34,816 个 clean units 和 104,448 个 repeats。但论文统计的 `n` 仍是独立 banks，不是 34,816 或 104,448。

规模验收不能只看 shape。还必须报告：每 bank 非零/有路径 coverage、active/null/gray route coverage、每类 edit 和 wrong-action coverage、每城市独立 bank 数、target unique-position support 容量，以及每个 gate 的有效分母。

## 4. 城市、bank 与权限账本

headline unseen-city 至少需要两个 source cities、两个 target cities，每城多个独立 banks。外部验证最好再使用不同数据/引擎或受控实测，但不能与主 split 共享 foundation、位置、teacher 统计或调参信息。

source 必须按最高层 bank 整体放入七块互斥权限账本：

| 权限 | 唯一允许用途 |
| --- | --- |
| `source-encoder-train` | Stage-0 CSI-only teacher/readout、四臂 `F/P`、源域位置头、训练归一化常数 |
| `source-method-selection` | 冻结方法选择、route/readout/noise floor 等预注册 pilot |
| `source-probe-train` | 统一 frozen probe 训练 |
| `source-probe-selection` | probe 超参数与 checkpoint 选择 |
| `source-calibration-fit` | calibrator 拟合 |
| `source-calibration-selection` | calibrator 选择；选中后冻结，不回灌重拟合 |
| `source-final-unseen-bank` | 一次性 source 外部审计与统计检验 |

同一 bank 的 sibling worlds、positions、edges、directions、masks 和 queries 必须整体跟随 bank，不能跨权限表。headline teacher 只能读取 `source-encoder-train` CSI。DeepMIMO、RadioMapSeer、Qualcomm 或其他 external 数据不得静默混入 teacher；若做共同 warm-start，必须作为四臂共同、单列的预注册消融。

## 5. target support/query

target 城市整体不参与 source 方法选择、teacher、route threshold、normalization、probe 或 calibrator 选择。目标适配必须按唯一 receiver position 划分 support/query，而不是按 observation 行随机切分。

一个 support position 一旦被选中，其所有 sibling worlds、edges、directions、repeats 和派生样本必须整组从 query 排除。`k=8/32/128` 使用读取结果前冻结的嵌套 unique-position draws；四臂共享同一 draw 和同一 target data budget。

## 6. 四类 generalization split

必须分别构造和报告：

- `unseen-position`：同 bank，位置完全留出；
- `unseen-edit`：编辑语义/组合留出，避免 edit-ID 记忆；
- `unseen-bank`：foundation/tile 整体留出；
- `unseen-city`：整座城市的 tile、world、位置、CSI 和统计量全部留出，作为 headline。

逐位置随机切分只能回答同 scene 插值，不能替代 unseen-bank/city。外部无线数据也必须按 scenario/city/sequence 分组，不能逐行随机切分造成空间或时间泄漏。

## 7. 数据资格不是 schema 检查

推荐把资格分成四层，任何下层通过都不能自动抬升上层：

| 层 | 需要证明 | 当前可由什么检查 |
| --- | --- | --- |
| 文件完整 | 文件存在、字节数、SHA/CRC、无 partial | `VERIFY_SUITE.sh`、来源 manifest |
| 工程结构 | schema、dtype、shape、permissions、replay | strict loader/contract tests |
| 数据资格 | RT calibration、相位/重复、visibility、route coverage、无泄漏 | 冻结 qualification protocol |
| 科学证据 | teacher/readout、No-X、retention、null、shortcut、四臂、外部有效性 | fresh-output 正式实验链 |

RT qualification 必须在训练前冻结，并用独立物理读出检查 path loss、delay spread、angular spread、visible path count、path matching 和 phase/gauge 规则。当前 2 Tx antennas x 4 subcarriers 是否足够保留编辑效应是待验证命题，不能因为 schema 是 16 个 Re/Im 通道就视为充分。

## 8. external 数据应放在哪里

### `external_wireless`

允许用途：外部强基线、数据适配器开发、按 scenario/city 分组的域外实验、四臂共同的预注册 warm-start 消融。禁止用途：直接填充 formal sibling-world 数据、headline teacher、route threshold/normalization 偷看、把公开替代写成原始 WWM/IRT2。

### Qualcomm Wi3R/WiPTR

它提供不同 RT 引擎生成的路径增益、相位、ToA、AoD/AoA 和室内几何，适合作为 independent-engine baseline candidate。但现有 layouts 没有合法的 CSI-PAIRS 完整 hypercube、同 Tx/Rx 单编辑 siblings、至少 3 次独立 observation repeats、primitive-surface/path-surface 映射或 v6 权限账本。

要让 Qualcomm 关闭第二引擎 gate，需要把已经注册的 CSI-PAIRS foundation/world edits 导入第二引擎，在完全相同的 Tx/Rx、载频、阵列和 world 语义下重新追踪，并保存 engine-specific provenance。仅比较 Sionna 城市与 Qualcomm 随机室内 layouts 属于跨数据域比较，不是同干预外部有效性。

## 9. 数据冻结与发布顺序

1. 冻结研究规范、许可证、来源 URL/版本、RT runtime/assets/config。
2. 冻结 city/bank/foundation/edit registry 和权限账本。
3. 生成所有 sibling worlds，求共同 free-space，冻结 receiver positions。
4. 完整交叉追踪 clean CSI、repeats、paths 和 map/action evidence。
5. 生成 authenticated manifest、每文件 hash、运行时和随机种子记录。
6. 在不训练模型的 fresh output 上运行 structural + RT qualification。
7. 资格失败时冻结失败报告并重新生成新 dataset ID；不得原地修补正式数据。
8. 资格通过后才训练 Stage-0 teacher/readout，并冻结 checkpoint/hash。
9. 依次执行 route、No-X、null、shortcut、retention、shuffled-pair、四臂、机械拼接和 external validity。
10. 只有全部预注册 gate 通过，才能解除 `scientific_use=FORBIDDEN` 并形成论文 release。

## 10. 当前结论

现有数据覆盖了三类有价值的资产：大规模外部无线数据、独立引擎室内 RT 数据、以及接近 v6 schema 的 Sionna/fixture 数据。但三类资产不能机械拼接成 formal 主数据，因为它们没有共同的 bank/world/edit/Tx/Rx/phase/path semantics。

因此，当前最重要的缺口不是“再找一些普通 CSI 文件”，而是生成并资格化一套完整、同位置、完整超立方体、可追踪表面、权限隔离的 formal sibling-world 主数据；随后再用第二引擎或真实受控干预对同一注册 worlds 做外部验证。当前所有主结论仍是待验证命题。

