# CSI-PAIRS 完整研究方案（v6.0）

## Paired Alignment and Intervention-Response Supervision

版本：v6.0  
日期：2026-08-04  
目标：ICLR 2027  
方法名：**CSI-PAIRS（Paired Alignment and Intervention-Response Supervision）**

> 文档性质：这是一份实验前研究方案，不是结果总结。除明确引用的已有论文结果外，文中的“预期”“应当”和“若成立”都不能写成已经得到的结论。投稿时，每一条结果性表述都必须通过第 14 节的 Claim-Evidence Gate。

---

## 0. 最终决策摘要

### 0.1 一句话问题

地图条件无线模型即使在正确配对的 CSI 和地图上取得较好预测或定位结果，也可能只把地图当作粗粒度场景提示，而没有学会局部几何改变后，当前信道究竟应当保持不变还是发生怎样的变化。

### 0.2 一句话方法

CSI-PAIRS 在同一条可审计的场景干预边上同时施加两级监督：**paired alignment** 判断两个场景状态中哪一个相对更能解释当前 CSI，**intervention-response** 则根据 RT 重追踪 target 监督变化方向与幅度；下游定位不调用 intervention predictor，只保留二者共同更新的地图条件 state encoder。

### 0.3 论文的中心命题

> Correctly matched training can leave map-conditioned CSI models insensitive to local geometry. CSI-PAIRS uses reusable scene-level paired interventions to supervise both relative map-CSI alignment and signed target response, and tests whether their shared representation improves calibrated unseen-city localization beyond either supervision alone.

中文限定版：

> 正确配对训练仍可能让地图条件 CSI 模型对局部几何不敏感。CSI-PAIRS 利用可跨位置复用的场景级配对干预，同时学习相对地图-CSI 对齐和带方向的 RT target response，并以联合监督在跨城定位与 paired-context 风险校准上胜过任一单分支作为核心可证伪检验。

### 0.4 这不是把 V4.1 和 V5 并排放在一起

两条监督必须作用在**同一条干预边、同一个物理单元和同一个最终保留的编码器**上：

```text
alignment：当前 CSI 更支持边的哪一侧？
response：沿这条边发生编辑后，CSI 应向哪里移动、移动多少？
```

alignment 只给出序关系，无法规定错误分支应靠近哪个真实目标；response 给出方向与幅度，却不自动保证最终表征能辨认当前地图是否与 CSI 对齐。二者约束不同，但“约束不同”本身不等于“存在协同”。最终必须通过严格四臂、交互效应和机械拼接对照来赚取这一结论。

### 0.5 V4.1 与 V5 的取舍

| 内容 | v6 决策 | 原因 |
|---|---|---|
| 错图现象 | 保留为论文开场 | 它直接暴露正确配对训练与局部几何响应之间的缺口 |
| CGS 与统一探针 | 保留，但限定在 active paired-edit 支撑上 | 不再把任意错图解释为绝对物理不相容 |
| 显式 compatibility | 保留为相对 alignment | 只比较同一物理单元、同一 active edge 的两侧 |
| 每个位置单独生成 K 个世界 | 删除 | 独一无二的地图变体可能泄露位置 ID |
| scene-level world bank | 采用 | 同一地图和编辑跨大量位置复用，切断 map-only 到位置的查表路径 |
| 所有非对角配对做 ranking | 删除 | 不同地图可能在别处产生相似 CSI，gray/null 也不应被强行推开 |
| RT 重追踪 target-response | 升为核心分支 | 直接约束 simulator-consistent 目标、方向与幅度 |
| 风险校准 | 保留并收紧支持范围 | `q_comp` 与 `p_fail` 分开，均只在源域拟合并冻结迁移 |
| 跨城市 zero/few-shot 定位 | 保留为最终价值检验 | 方法不能只在自造的 compatibility 或 response 任务上自证成功 |
| path-incidence 与 LoS/NLoS | 保留 | 检查收益是否出现在编辑确实作用于传播路径的位置 |
| I(x) 可辨识性分析 | 降为 P1 | 它有价值，但不应与四臂主证据争夺 P0 资源 |

### 0.6 必须守住的 claim 边界

- 不把 `(H_i, M_j)` 称为全局绝对负样本、物理不可能组合或错误世界；正文统一称 **paired active alternative**。
- 不把 scene-level hypercube 称为 i.i.d. “可交换世界”。准确名称是**节点均衡、边对称的场景级世界库**。
- `q_comp` 只表示指定 paired-intervention 支撑内的相对 compatibility，不是任意地图在全空间上的正确概率。
- 任意错误城市地图属于 stress test。除非校准集明确包含该扰动族，否则不能给它套用概率语义。
- 没有真实受控干预或独立引擎证据时，只写 `simulator-consistent`，不写真实世界因果理解。
- 不把 ranking、Transformer、MAE、JEPA、对比学习或多任务加权当作算法新颖性。
- 不称 world model，不声称学会 rollout 或通用信道仿真器。
- 若最终保留的 `F` 未通过 map-retention 审计，只能说一次性 response/alignment head 学会了任务，不能说下游表征获得 geometry grounding。
- 若 full 未同时胜过两个单分支，删除联合方法优越性；若交互效应不过门，只能写“统一的 paired multi-task supervision”，不能写 synergy。

---

## 1. 论文叙事：从错图现象到可证伪的联合监督

### 1.1 开场现象仍按 V4.1 展开

现有 map-conditioned 模型通常只在正确地图上训练和测试。正确配对上的性能不能回答一个更尖锐的问题：模型是否会随着局部几何改变而作出相应变化，还是只使用了地图中的城市风格、场景类别或粗粒度 LoS 先验。

对至少两个可运行的 map-conditioned 模型，统一评测以下输入：

| 条件 | 地图输入 | 作用 |
|---|---|---|
| A correct | 生成当前 CSI 的地图 | 常规基准 |
| B paired-active alternative | 同一位置、配置和外生变量下，经物理量与 frozen teacher 双重确认生效的相邻世界 | 检查局部反事实响应 |
| C paired-null alternative | 地图有编辑，但当前信道与 teacher target 均落在 noise floor 内 | 检查模型是否见编辑就误报 |
| D wrong-city map | 另一城市地图，经 BS-centric 米制坐标协议对齐 | 压力测试，不自动赋予 calibrated compatibility 语义 |
| E geometry-destroyed | 保留低阶统计但破坏空间结构 | 区分几何与粗统计 |
| F empty map | 全零或冻结均值提示 | 检查模型是否至少使用了某种地图条件信息 |

如果 B 与 A 几乎无差，而 F 明显退化，能支持的有限结论是“模型使用了地图提供的粗条件，但缺乏对局部、确实生效编辑的反事实敏感性”。仅凭这一现象不能断言地图就是 scene ID。

### 1.2 scene-ID 仍是条件性机制假说

“地图被当作场景身份证”必须由两个源城域内实验共同支持：

1. 在严格留出位置上，scene-ID prompt 能否追平正确 map prompt；
2. 把地图替换为城市 `b` 与把 prompt 替换为 `ID_b` 时，输出或表征的偏移方向是否一致。

目标城 `k=0` 不允许学习新的 scene embedding，只能使用训练前冻结的 `UNK` 或源城 embedding 均值。若替换响应不一致，论文只保留“局部几何不敏感”，删除 scene-ID 机制解释。

### 1.3 从现象到方法的逻辑链

```text
正确配对表现好
    不代表
局部几何被反事实地使用
        ↓
active/null 错图 reveal + CGS 诊断
        ↓
alignment 指定干预边的相对一致侧
        +
response 指定 RT 重追踪变化的方向与幅度
        ↓
只保留共享 state encoder F
        ↓
四臂检验跨城定位、风险校准和路径机制
```

论文仍沿用 V4.1 的 `phenomenon → metric → method → result → analysis` 主结构。V5 不单列成第二套方法，而是补上 V4.1 缺失的 response 监督。

### 1.4 在介绍方法前先钉死指标

CGS 的问题先于模型定义：在同一隐藏接收状态与同一条确认生效的 paired edit 上，冻结表征后用统一固定预算 probe，能否分辨 generating side 与 paired active alternative。active quartet 进入 AUROC，gray 只描述，null 只检查是否过判。这个定义对 endpoint、alignment-only、response-only、full 和外部 map-conditioned baselines 一视同仁。

`q_comp` 是 active edge 内的离线相对概率，`p_fail` 是给定冻结 comparison/proposal set 后的定位失败概率。二者分别校准，且都只在 source calibration data 上拟合。第 5 节给出完整公式，但本节先固定语义，避免方法训练什么，指标就跟着改成什么。

---

## 2. CGS 所需的 paired unit 与场景级世界库

### 2.1 模拟器内的配对物理单元

对独立场景 tile `b`、世界状态 `u`、用户位置 `x`、无线配置 `c` 和共享物理外生变量 `ξ_phys`，先定义无观测噪声的 RT 输出：

\[
H^*_{b, u}(x)=\mathcal R(M_{b, u}, x, c,\xi_{\mathrm{phys}}).
\]

其中 `c` 包含 BS 位姿、载频、阵列与天线配置，`ξ_phys` 包含除地图编辑外必须固定的传播条件。对一条 `u↔v` 干预边，`x,c,ξ_phys` 完全相同，只切换一个明确记录的地图 primitive edit。因此 `H_u^*(x)` 与 `H_v^*(x)` 是这个 simulator-defined 物理单元下的配对结果。

若研究接收机噪声或测量扰动，第 `r` 次观测另写为：

\[
H_{b, u}^{(r)}(x)=\mathcal O\big(H^*_{b, u}(x),\eta_{b, u}^{(r)}\big),
\]

其中 `η_{b,u}^{(r)}` 是 world-specific observation noise。paired worlds 共享 `ξ_phys`，但 `η_u` 与 `η_v` 必须独立抽样，不能复制同一段观测噪声来制造虚假的 response 可预测性。P0 主结果使用 clean RT target `H^*`，把 intervention effect 与测量噪声分开；独立噪声下的重复测量作为稳健性实验，并用于估计 no-edit/identity noise floor。真实测量没有 clean target 时，改用预注册的多 replicate 均值和不确定性区间，不得把单次噪声差当作地图 effect。

除专门的噪声稳健性实验外，下文简写 `H_u:=H_u^*`；所有 route、teacher target、alignment score 和 response target 默认都由 clean RT pair 计算。

批量生成数据前保留 V4.1 的 RT 资格门：材质、散射、天线和噪声参数只在独立校准集拟合，随后冻结；在不参与拟合、世界编辑和最终测试的验证集上，预注册检查 path loss、delay spread、angular spread 与可见路径数。未通过时仍可做 simulator-defined 方法研究，但全文不得称 calibrated simulator。

### 2.2 一个场景 tile 对应一个可复用 world bank

对每个独立场景 tile 选择 `d≥2` 个彼此兼容且可逆的 primitive edits，生成：

\[
\mathcal W_b=\{M_{b, u}:u\in\{0,1\}^{d}\},
\qquad K=2^d\ge4.
\]

每个 bit 对应两个预注册、物理上可行的状态。bit 编码在每个 bank 内随机置换，所有节点都由完整状态说明 canonical render，不能按编辑顺序逐步修改文件，否则渲染痕迹和操作顺序会成为 provenance。训练只使用 Hamming distance 为 1 的边：

\[
\mathcal E_b=\{\{u, v\}:\lVert u-v\rVert_1=1\}.
\]

同一个 `M_{b, u}` 必须服务 tile 内大量位置 `x∈X_b`。先确定 bank 和共同位置集，再对所有节点、边和位置完整交叉生成，不能为某个 action 另挑更容易产生 effect 的位置。

自然原图 `M_b^{nat}` 进入四臂共同的 endpoint/natural 分支，但不作为 alignment 中唯一、带 privileged pristine 身份的锚点。若确需让自然原图成为 bank 节点，必须通过 randomized-anchor 和 edit-status XOR 单元测试；任何能稳定识别“原图/编辑图”并用两模态 XOR 解出标签的构造都不能进入 headline alignment。

这个构造不是 V4.1 意义下的 i.i.d. exchangeable variants。v6 依赖的是：

- bank 节点在 source 使用中均衡；
- 每条无向边的两个方向等频；
- active alignment 四元组在边内精确匹配 H 与 M 边际；
- 同一 bank 跨位置复用，使地图纹理不能唯一标识位置。

P0 原则上每个独立 tile 只生成一个 hypercube。若多个 bank 共用完全相同的 base map，它们必须留在同一 split 和统计 cluster 中，并对重复 base node 去重或使用 inverse-degree 权重，不能把它们当作独立场景扩充样本量。

`d=2` 只在两个 primitive 预先设计为同编辑族、同量级，且 geometry-matched wrong-action candidate coverage 通过资格门时用于 headline。否则在大规模 RT 前升级为 `d≥3`，不能等看完目标城市结果后再放宽 action-swap 匹配标准。

### 2.3 共同位置集与采样顺序

所有世界共享：

\[
X_b=\bigcap_{u}\operatorname{FreeSpace}(M_{b, u}).
\]

新增建筑不能覆盖任何公共 UE 位置。推荐采样顺序为：

1. 均匀采独立 scene tile / bank；
2. 均匀采无向 edge；
3. 从该 bank 固定的 `X_b` 均匀采 `x`；
4. 固定 `c,ξ_phys` 形成完整物理单元；
5. alignment 同时构造两侧，response 对两个方向等频采样。

active/gray/null 在采样完成后路由。不得按位置筛选 effectful action，否则 `P(x|action)` 会重新泄露位置。

每个 source unit 在训练中组成 branch bundle：完全复用同一 `H_u`、source map、`c`、input mask、output query 和数值增强，只改变 action 与 target neighbor。每个 source 至少有两个 Hamming-1 分支，每个分支以正概率被采到。结构上有两个分支不代表 target 一定可分，必须报告 target-sensitive active branching coverage。若同一 source 永远只配一个 target，模型可以忽略 action，动作信息价值实验不成立。

### 2.4 编辑与模型可观测性

P0 仅使用地图表示能观察、RT 能双向重追踪的编辑：

| 编辑族 | 例子 | 约束 |
|---|---|---|
| occupancy | 加入或移除建筑、大型临时结构 | 不覆盖共同位置集 |
| height | 建筑升高或降低 | 高度落在预注册物理范围 |
| material | 混凝土、玻璃、金属类别切换 | 材质电磁参数在 RT 资格门后冻结 |
| compound state | world 同时含两个 primitive 状态 | 每条训练边仍只 toggle 一个 primitive |

窗口、细面片等无法被主模型分辨的编辑不进入 P0。不能让模型输入看不见编辑，却让 loss 强迫模型作出响应。

### 2.5 地图与 action 表示

source map 使用 BS-centric 固定范围、固定分辨率的多通道网格，至少包含 occupancy、height、material 和 BS pose/config。`G(M)` 只表示确定性栅格化与 token 顺序，trainable map encoder 属于 `F_θ`。

动作分支只接收与 source map 对齐的 ID-free signed edit grid：

\[
e_{uv}=E_\phi(\Delta_{uv}).
\]

`Δ_uv` 逐格记录 add/remove、高度变化以及 material from/to，不对类别 ID 做数值相减。它不能包含 world ID、edit ID、文件名、生成序号、`x`、path-incidence、effect bucket、`δ_phys` 或 target CSI 派生量，也不能重复输入完整 target map。

地图范围、token 数量、顺序和 padding 不能依赖 UE 位置。用户中心裁图、按真实用户连线选择 map token、轨迹输入和 receiver ID 均禁止进入主模型。

### 2.6 四类严格 split

四个问题分开评测：

| 测试轴 | 分组规则 | 回答什么 |
|---|---|---|
| unseen-position | 同一位置的所有 sibling worlds、edges、masks 同进一侧；test-position CSI 不进 Stage 0 或归一化 | 是否泛化到同 bank 新位置 |
| unseen-edit/operator | 整个 primitive family/instance 及其专属 worlds、CSI 从 Stage 0 起留出 | 是否学到可迁移编辑规律 |
| unseen-scene-bank | 整个 tile、base map、bank、全部位置和 CSI 从 Stage 0 起留出 | 是否摆脱具体 world/bank 指纹 |
| unseen-city | 整座城市的 tile、bank、位置、CSI 和统计量全部留出 | headline 跨城泛化 |

headline 至少使用两个源训练城市和两个彼此独立的目标城市，每个城市都需要多个独立 scene tiles。训练 seed 不是城市或场景 replicate，不能代替独立数据单位。

`d≥3` 下只留出某个已见 primitive 在新 bit context 中的 edge，可作为单独的 compositional operator 诊断；因为节点可能经其他 edges 出现在训练，它不能冒充独立数据泛化。任何 split 的 siblings 都不能被随机拆散。

### 2.7 唯一的数据权限账本

全文不再混用 `outer-train`、`source pilot`、`source validation` 和 `model-selection` 而不说明归属。除独立 RT 资格门数据外，source scene banks 按最高层 tile cluster 一次性划入下列互斥数据块：

| 数据块 | 唯一允许用途 | 明确禁止 |
|---|---|---|
| `source-encoder-train` | 训练 Stage-0 teacher/readout、四臂 `F/P`、源域位置头；计算训练归一化常数 | probe、calibrator 或阈值选模 |
| `source-method-selection` | 所有 source pilot/validation/model-selection：冻结 route practical/noise floors、margin/`φ`、loss 权重、mask/query bank、architecture、qualification gate 和 checkpoint rule | 更新最终 encoder、训练统一 probe 或拟合 calibrator |
| `source-probe-train` | 在冻结表示上拟合统一 compatibility/response probes | probe 选型、校准器拟合 |
| `source-probe-selection` | 只选择 probe family、正则和 checkpoint | 训练 calibrator 或报告 final 指标 |
| `source-calibration-fit` | 拟合 `T_A`、风险校准器、feature standardization 与 support estimator | 选择 probe 或查看 target 结果 |
| `source-calibration-selection` | 只选择预声明的 calibration regularization/family，并冻结 support quantile | 回流训练 encoder/probe，或充当 calibration final test |
| `source-final-unseen-bank` | 一次性 source 外部审计与统计检验 | 任何训练、阈值、选模或校准 |

这里的 “source pilot 后冻结” 一律指只读取 `source-method-selection`；“source train/outer-train” 一律落实为 `source-encoder-train`。校准候选只在 `source-calibration-fit` 拟合，在 `source-calibration-selection` 选择，选中参数随后冻结，不再用 selection 数据回灌重拟合。所有 sibling worlds、positions、edges、directions、masks 和 queries 跟随最高层 tile 一起移动，不能跨表中数据块。

目标城市另按 receiver position 划分 adaptation-support 与 frozen query。`k` 固定指 **k 个唯一 receiver positions**；每个 support position 只使用一条预注册 correct/natural CSI-map observation 做 headline adaptation，不能借该位置的 K 个 sibling worlds 把 `k=8` 扩成 `8K` 个有标签样本。support position 的全部 sibling worlds、edges、masks 和 queries 整组从最终定位、风险、CGS 与 interaction 统计中排除。使用 target siblings 增广只能单列为 privileged diagnostic，并同时报告 unique labels 与有标签 example 总数。`k=0` 没有 adaptation-support；任何 `k>0` 的 query position 均不得出现在梯度更新、早停、归一化或超参数选择中。

---

## 3. 双空间 effect routing

### 3.1 frozen CSI-only teacher

先只用 `source-encoder-train` CSI 训练 `T_CSI`，采用 CSI-MAE 式 Re/Im 双通道、antenna×subcarrier patch、二维位置编码、75% random mask 和非对称 MAE encoder-decoder。teacher 训练完成后冻结，四个受控方法共享同一 teacher 和同一 CSI encoder 初始化。

对完整、未遮挡的 `H_k`，target 定义为 frozen teacher 在 eval mode 下输出的 pre-decoder patch token，经 `source-encoder-train` 统计做固定归一化：

\[
z_k^q=\operatorname{stopgrad}(T_{\mathrm{CSI}}(H_k)_q).
\]

teacher 的函数签名中没有地图、位置、动作或轨迹。实现必须有单元测试：保持 `H` 不变，只替换 `M, x, a` 的引用时，target 在规定数值精度内不变。

另用 `source-encoder-train` CSI 训练逐 patch readout `D_CSI`，随后冻结：

\[
y_k^q=\Psi_q(H_k),
\qquad
\widetilde y_k^q=D_{\mathrm{CSI}}(z_k^q).
\]

`Ψ` 默认是用 source 常数归一化的 Re/Im patch。所有 delta target 必须采用 **pair-consistent phase gauge**：确定性 RT 使用与 world 无关的共同时钟/相位参考；不允许对 `H_u,H_v` 分别做独立最优相位旋转，因为那会把预处理差异写进 response 方向。若实测链路无法提供共同相位参考，P0 physical target 与 metric 改用相位不变的幅度、协方差或 delay-angle power 表示，并把选择规则在 source-method-selection 上冻结。`D_CSI` 只审计 frozen latent 是否保留物理可读性，不参与 response 的训练 target。若把 `D_CSI(\hat z)` 直接放进 physical loss，readout 自身的近似误差可能与 latent target 冲突。v6 因此让 predictor 独立输出 physical patch，并把 frozen readout 结果单列为审计指标。若 readout 不能在 source-method-selection 上可靠还原 patch，就不能用 latent target 支持“物理响应”表述，应回退到固定 raw/physical target。

### 3.2 alignment 与 response 使用不同粒度的 route

alignment 是 full-channel pair-level 任务。定义：

`Φ(H)` 是实验前冻结的 full-channel 物理表征，P0 使用 source 常数归一化的复 CSI 与 delay-angle power summary；`d_phys` 是其 normalized RMS distance。`d_z` 是 frozen teacher token 的 normalized RMS distance。具体归一化常数只能来自 `source-encoder-train`，并在所有四臂和 split 中固定。

\[
\delta^{A}_{uv}=d_{\mathrm{phys}}(\Phi(H_u),\Phi(H_v)),
\qquad
\gamma^{A}_{uv}=d_z(T_{\mathrm{CSI}}(H_u),T_{\mathrm{CSI}}(H_v)).
\]

response 是 patch-level 任务，对 query `q` 定义：

\[
\delta^{q}_{uv}=d_{\mathrm{phys}}(\Phi_q(H_u),\Phi_q(H_v)),
\qquad
\gamma^{q}_{uv}=d_z(z_u^q, z_v^q).
\]

response route 默认令 `Φ_q=Ψ_q`，并让 `d_phys`、`d_z` 分别使用后续 dead-zone 相同的 physical norm 与 latent RMS norm。这样 route threshold 和 null tolerance 处于同一量纲。

定义同一形式的 route 函数：

\[
\operatorname{Route}(\delta,\gamma;\epsilon_0,\epsilon_1,\tau_0,\tau_1)
=\begin{cases}
\mathrm{null}, & \delta\le\epsilon_0\ \land\ \gamma\le\tau_0,\\
\mathrm{active}, & \delta\ge\epsilon_1\ \land\ \gamma\ge\tau_1,\\
\mathrm{gray}, & \text{otherwise}.
\end{cases}
\]

但两条路线使用各自冻结的阈值与单位：

\[
0\le\epsilon_0^A<\epsilon_1^A,
\quad 0\le\tau_0^A<\tau_1^A,
\qquad
0\le\epsilon_0^R<\epsilon_1^R,
\quad 0\le\tau_0^R<\tau_1^R.
\]

\[
r^A_{uv}
=\operatorname{Route}(\delta^A_{uv},\gamma^A_{uv};
\epsilon_0^A,\epsilon_1^A,\tau_0^A,\tau_1^A),
\]

\[
r^{R, q}_{uv}
=\operatorname{Route}(\delta^q_{uv},\gamma^q_{uv};
\epsilon_0^R,\epsilon_1^R,\tau_0^R,\tau_1^R).
\]

两组 `ε0,τ0` 来自无编辑重复仿真或重复测量的 noise floor，两组 `ε1,τ1` 来自 `source-method-selection` 上预注册的 practical-effect floor。所有阈值在查看目标城市结果前冻结。不能用 full-channel alignment threshold 直接路由单个 response patch。

route 必须满足三点：

- 对 edge 方向对称，即 `r^A_uv=r^A_vu` 且 `r^{R, q}_uv=r^{R, q}_vu`；
- 只用于 loss routing、采样审计和评测分层，不进入模型输入；
- 每个 split 报 active/gray/null 的原始数量、比例和 scene-level coverage，不得只保留 active 后宣称覆盖率为 100%。

另报 physical-active→teacher-sensitive coverage 与 physical-null→teacher-null agreement。若二者过低，说明 teacher target 与物理任务错位，不能让 latent 指标替代真实物理差异。

### 3.3 为什么 gray 与 null 不能做强 ranking

active 表示物理空间和 teacher target 都确认这条编辑对当前单元产生可分辨影响，因此只在 active 上要求 source-generating map 的分数相对更高。

gray 表示两个空间没有同时给出明确结论。它仍有 RT 重追踪得到的 `H_v`，因此可以做 target regression，但不能被强行规定为“必须不同”或“必须相同”。

null 表示差异落在双空间 noise floor 内。它不应被当成负样本，也不能要求预测变化严格为零，因为真实 `z_u` 与 `z_v` 仍可能有阈值内小差异。v6 对 null 使用 dead-zone penalty，只惩罚超过容许半径的虚假差异。

### 3.4 input mask 与 output query 隔离

`m` 是 source CSI 中被遮住的 patch 集合，`V_m(H_u)` 是 predictor 唯一可见的 source CSI。`q` 是要预测的 target patch，常规训练与 target-free 评测强制 `q∈m`。同一 quartet 和 branch bundle 逐样本复用完全相同的 `(m, q)`，不能让正确/alternative 或不同 action 使用不同 mask。

Stage 1 的 source mask bank 预注册包含 Random-75%、Antenna-block-50% 和 Subcarrier-block-50%。后两项是本方案为下游外推加入的扩展，不能误写为 CSI-MAE 原论文的预训练设置。评测 mask/query bank 在训练前冻结并覆盖全部 patch。

`full-H no-x` 只作可预测性上界：另行训练 `m=∅` 的受控模型，不能把 masked 训练后的模型直接换成 full-H 输入，再把分布外结果当成 identifiability 证据。任何情况下，target-world `H_v` 都不能进入 source predictor；它只进入 frozen target、physical label、effect route 和最终评分。

---

## 4. CSI-PAIRS 方法

### 4.1 共享且最终保留的 state encoder

对 source world `u` 和输入 mask `m`：

\[
C_u^m=F_\theta\big(V_m(H_u),G(M_u),c, m\big).
\]

`F_θ` 由 CSI encoder、map encoder 和轻量 cross-attention fusion 构成。alignment 与 response 都必须把梯度传回同一个 `F_θ`。用于下游定位时，action encoder、predictor、teacher 和审计 readout 均不向位置头提供信息，只保留：

\[
r=F_\theta(H, M, c),
\qquad
\hat x=g(r).
\]

位置头 `g` 只使用源城市位置标签训练。目标城市 `k=0` 时整网冻结，`k>0` 时所有方法使用相同标签数、更新参数集合和步数。

为报告 intrinsic compatibility 和 native response，可在独立诊断路径保留冻结的 `P_ψ/T_CSI/D_CSI`，但它们的输出不得进入 `g`。这样下游增益只能来自共享 `F_θ`，而不是测试时调用额外的反事实 predictor。

### 4.2 共同 endpoint 目标

下文 `ρ_z` 是按 latent 维度平均的 normalized MSE，`ρ_y` 是按 physical patch 维度平均、采用第 3.1 节 pair-consistent gauge 或相位不变规则的 normalized MSE。二者的归一化常数只由 `source-encoder-train` 冻结，并与 route/dead-zone 使用的 norm 保持一致。

本文中的 **endpoint** 只指四臂共同的 same-world matched/identity prediction，不指下游监督定位 loss，也不在不同表中改变含义。predictor 从同一个 state 同时输出 latent 与 physical patch：

\[
(\hat z_{u\to u}^{m, q},\hat y_{u\to u}^{m, q})
=P_\psi(C_u^m,0, q),
\]

\[
\ell_B^{u, m, q}
=\rho_z(\hat z_{u\to u}^{m, q}, z_u^q)
+\lambda_{By}\rho_y(\hat y_{u\to u}^{m, q}, y_u^q).
\]

数据集级 endpoint 目标为：

\[
\mathcal L_B
=\mathbb E_{\substack{
b\sim\mathrm{Unif}(\mathcal B),\ u\sim\mathrm{Unif}(\mathcal W_b),\ x\sim\mathrm{Unif}(X_b),\\
(m, q)\sim\mathrm{Unif}(\mathcal B_{\mathrm{mask/query}})
}}
\left[\ell_B^{u, m, q}\right].
\]

采样顺序必须先均匀 bank，再均匀 node、position 和 mask/query，避免节点多或位置多的 bank 获得更高权重。它把相同 K-world 数据中的每个 `(H_u, M_u)` 当作独立正确配对使用，但看不到 edge route、signed action 或跨世界 target。自然原图以预注册固定混合权重进入四臂完全相同的 endpoint stratum，不改变上式的 bank-macro 原则。若实现还保留共享的 CSI-MAE reconstruction 项，它必须等量出现在四臂中，并计入 `L_B`。

### 4.3 Paired alignment

alignment 不另接一个互不相关的标量分类头。它直接使用**零动作下候选地图解释当前 CSI 的预测误差**作为能量。对训练前冻结、覆盖 full channel 的小型 mask/query bank `B_align`，定义：

\[
\begin{aligned}
\ell_0(H, M; m, q)=&\ \rho_z\big(
P_\psi^z(F_\theta(V_m(H),G(M),c, m),0, q),T_{\mathrm{CSI}}(H)_q
\big)\\
&+\lambda_{sy}\rho_y\big(
P_\psi^y(F_\theta(V_m(H),G(M),c, m),0, q),\Psi_q(H)
\big),
\end{aligned}
\]

\[
s_{\theta,\psi}(H, M, c)
=-\frac{1}{|\mathcal B_{\mathrm{align}}|}
\sum_{(m, q)\in\mathcal B_{\mathrm{align}}}\ell_0(H, M; m, q).
\]

每次 alignment update 都对 quartet 的四个 candidate pairs 使用同一 `B_align` 和同一组数值增强，并先求完整 bank 平均，再进入 hinge。不能用单个随机 `q` 的 hinge 冒充“平均 score 的 hinge”，因为两者期望一般不相等。native alignment 的主结果沿用同一个 score 定义；另用不参与训练的 `B_audit^hold` 报 mask/query 稳健性。这样 alignment 与 response 不只是共用 backbone，而是共用同一个“零动作/非零动作”预测机制。

对固定 `(b,x,c,ξ_phys)` 的 active 无向 edge `{u,v}`，定义单 edge 的对称相对 ranking：

\[
\begin{aligned}
\ell_{\mathrm{rank}}^{uv}
=&
[m_{uv}-s(H_u, M_u)+s(H_u, M_v)]_+\\
&+[m_{uv}-s(H_v, M_v)+s(H_v, M_u)]_+,
\end{aligned}
\]

其中：

\[
m_{uv}=m_0\,\phi(\delta^{A}_{uv})
\]

且 `φ` 单调、截断上界在 `source-method-selection` 冻结。主结果同时报告 fixed-margin 版本；`m_uv` 只能称 effect-aware margin，因为 score 尺度不是物理单位，不能再写“物理标定 margin”。这里的监督语义只是“在这条确认生效的 paired edge 内，哪一侧相对更能解释当前 CSI”，不表示另一侧在未知位置上绝对不可能产生相似信道。

null edge 不做 ranking。为抑制“看见地图编辑就制造不相容”的行为，可使用带容差的分数等同性：

\[
\ell_{\mathrm{dz}}(a;\kappa)=[\max(|a|-\kappa,0)]^2,
\]

`κ_s` 不能从任一最终 arm 反推。先按固定 endpoint schedule 在 `source-encoder-train` 训练一个四臂共享、只用于定标的 endpoint-pilot checkpoint；随后以 eval mode、同一 `B_align`、同一 score normalization，在 `source-method-selection` 的 canonical no-op pairs 上计算 predictive-energy absolute gap。no-op pair 固定为同一 `H`、同一语义地图经 empty-edit canonical rerender 后的两侧；噪声稳健性版本使用独立 observation replicates。`κ_s` 取这些 gap 的预注册 `(1-α_s)` quantile，`α_s` 在读取该数据块前固定。四臂共用同一个 `κ_s`，最终 checkpoint 和 target 数据都不能改变它。另用预先 route 为 physical-null 的 edges 检查该容差是否覆盖 noise floor；未覆盖时修复 gauge/noise model 或判数据门失败，不能看完 arm 结果后放宽 `κ_s`。

\[
\begin{aligned}
\ell_{\mathrm{nullA}}^{uv}
=&
\ell_{\mathrm{dz}}(s(H_u, M_u)-s(H_u, M_v);\kappa_s)\\
&+\ell_{\mathrm{dz}}(s(H_v, M_v)-s(H_v, M_u);\kappa_s).
\end{aligned}
\]

alignment 分支按 route 条件分别归一化：

令 `B_A^active` 与 `B_A^null` 分别表示通过预注册 scene-level coverage gate、至少含相应 route 的 source training banks。则：

\[
\begin{aligned}
\mathcal L_A
=&\ \mathbb E_{b\sim\mathrm{Unif}(\mathcal B_A^{\mathrm{active}})}
\mathbb E_{\{u, v\}, x\mid b,\,r^A_{uv}=\mathrm{active}}
\left[\ell_{\mathrm{rank}}^{uv}\right]\\
&+\lambda_{nA}
\mathbb E_{b\sim\mathrm{Unif}(\mathcal B_A^{\mathrm{null}})}
\mathbb E_{\{u, v\}, x\mid b,\,r^A_{uv}=\mathrm{null}}
\left[\ell_{\mathrm{nullA}}^{uv}\right].
\end{aligned}
\]

两个 route 都先对 eligible banks 等权，再在 bank 内均匀采符合 route 的无向 edge-position units。这样 bank 大小和 active/null prevalence 不会暗中改变 `λ_nA`。gray 对 alignment 的 loss 为零，不进入上述两个条件均值。

### 4.4 Intervention-response supervision

动作支路从相同 `C_u^m` 和同一个 predictor 出发：

\[
(\hat z_{u\to v}^{m, q},\hat y_{u\to v}^{m, q})
=P_\psi(C_u^m, e_{uv}, q).
\]

真实与预测变化量为：

\[
\Delta z_{uv}^q=z_v^q-z_u^q,
\qquad
\widehat{\Delta z}_{uv}^{m, q}=\hat z_{u\to v}^{m, q}-\hat z_{u\to u}^{m, q}.
\]

物理 patch 同理定义 `Δy_uv^q=y_v^q-y_u^q` 和 `widehat{Δy}_uv^{m, q}=hat y_{u→v}^{m, q}-hat y_{u→u}^{m, q}`。

所有 directed edges，包括 active、gray 和 null，都回归 RT 重追踪 target：

\[
\ell_{\mathrm{target}}^{uv, m, q}=\rho_z(\hat z_{u\to v}^{m, q}, z_v^q),
\]

\[
\ell_{\mathrm{phys}}^{uv, m, q}=\rho_y(\hat y_{u\to v}^{m, q}, y_v^q).
\]

active 额外约束变化方向与幅度：

\[
\ell_{\Delta}^{uv, m, q}
=
\rho_z(\widehat{\Delta z}_{uv}^{m, q},\Delta z_{uv}^q)
+\lambda_{\Delta y}\rho_y(\widehat{\Delta y}_{uv}^{m, q},\Delta y_{uv}^q)
.
\]

null 使用 dead-zone，而不是与 target regression 冲突的严格零约束：

\[
\ell_{\mathrm{nullR}}^{uv, m, q}
=
\left[\max\left(\lVert\widehat{\Delta z}_{uv}^{m, q}\rVert_{\mathrm{rms}}-\kappa_z,0\right)\right]^2
+\lambda_{0y}\left[\max\left(\lVert\widehat{\Delta y}_{uv}^{m, q}\rVert_{\mathrm{phys}}-\kappa_y,0\right)\right]^2
.
\]

`κ_z,κ_y` 分别由 identity/no-edit latent 与 physical replicate 的 source noise floor 冻结。默认取 `κ_z=τ0^R`、`κ_y=ε0^R`，并做单元测试保证：只要 `r^{R,q}_{uv}=null`，RT `Δz_uv/Δy_uv` 就位于两个 dead zones 内。若 route 使用复合 `Φ`，必须把 `κ` 调到覆盖 source-null RT 差值的预注册上界；否则精确 target 仍可能同时受到 null penalty，loss 定义不合格。gray 只有 RT target 与 physical patch regression，不承担强 delta 或零变化假设。

令 `→E_b` 表示把每条无向 edge 的两个方向各放一次后的 directed edge set，`B_R^active/B_R^null` 表示通过相应 patch-route coverage gate 的 banks。response 分支定义为：

\[
\begin{aligned}
\mathcal L_R
=&\ \mathbb E_{b\sim\mathrm{Unif}(\mathcal B)}
\mathbb E_{u\to v, x, m, q\mid b}
\left[\ell_{\mathrm{target}}^{uv, m, q}
+\lambda_{\mathrm{phys}}\ell_{\mathrm{phys}}^{uv, m, q}\right]\\
&+\lambda_{\Delta}
\mathbb E_{b\sim\mathrm{Unif}(\mathcal B_R^{\mathrm{active}})}
\mathbb E_{u\to v, x, m, q\mid b,\,r^{R, q}_{uv}=\mathrm{active}}
\left[\ell_{\Delta}^{uv, m, q}\right]\\
&+\lambda_{nR}
\mathbb E_{b\sim\mathrm{Unif}(\mathcal B_R^{\mathrm{null}})}
\mathbb E_{u\to v, x, m, q\mid b,\,r^{R, q}_{uv}=\mathrm{null}}
\left[\ell_{\mathrm{nullR}}^{uv, m, q}\right].
\end{aligned}
\]

所有期望先对 eligible banks 等权，再在 bank 内均匀采 directed edge、position 和 mask/query。第一项不按 route 条件化，因此 active、gray、null 都学习 RT target；后两项分别在 active/null 内归一化，gray 不承担强 delta 或零变化约束。因为 directed sampler 已经等频包含 `u→v` 与 `v→u`，公式中不再额外加一遍 symmetric term。

若某个训练 split 缺少足够的 active 或 null scene-bank coverage，数据资格门直接失败；空的条件均值不得在实现中静默写成 0。每个条件均值的有效 bank、edge、position 和 patch 数必须随实验报告。

### 4.5 联合目标、factor 剂量与资源核算

在共享初始化上，用 `source-method-selection` 的固定短 pilot batch sequence `P` 运行临时模型。令 `\widehat L_A^{(t)},\widehat L_R^{(t)}` 是第 `t` 个 batch 对第 4.3/4.4 节 scene-bank-macro 目标的无偏分层估计，定义：

\[
c_A=\max\left(\operatorname{mean}_{t\in\mathcal P}\widehat{\mathcal L}_A^{(t)},\varepsilon\right),
\qquad
c_R=\max\left(\operatorname{mean}_{t\in\mathcal P}\widehat{\mathcal L}_R^{(t)},\varepsilon\right),
\]

\[
\widetilde{\mathcal L}_A=\mathcal L_A/c_A,
\qquad
\widetilde{\mathcal L}_R=\mathcal L_R/c_R.
\]

这个临时 pilot checkpoint 不进入最终训练或评测。batch sequence `P`、共享初始化和 numerical floor `ε` 在四臂间相同，`c_A,c_R` 一次计算后冻结，不按 arm 重估。随后固定 `λ_A,λ_R`。同一个 factor 在单分支和 full 中必须保持完全相同的权重：

\[
\begin{aligned}
\mathcal L_{00}&=\mathcal L_B,\\
\mathcal L_{10}&=\mathcal L_B+\lambda_A\widetilde{\mathcal L}_A,\\
\mathcal L_{01}&=\mathcal L_B+\lambda_R\widetilde{\mathcal L}_R,\\
\mathcal L_{11}&=\mathcal L_B+\lambda_A\widetilde{\mathcal L}_A
+\lambda_R\widetilde{\mathcal L}_R.
\end{aligned}
\]

`00/10/01/11` 分别对应 endpoint、alignment-only、response-only 和 full。若 full 才改变某一 factor 的权重，后续 difference-in-differences 就不再是标准 `2×2` interaction。所有 loss 权重只能用 `source-method-selection` 选择。需要报告各分支对 `F` 的梯度范数、训练 FLOPs 和有效更新次数；若 full 的训练 FLOPs 超过单分支预注册容差，增加相同 FLOPs 的单分支训练控制。固定总辅助梯度预算的 convex-mixture 版本只作稳健性实验，不进入主交互检验。

### 4.6 方法新颖性到底在哪里

可守的新颖性不是某个 loss 公式，而是完整的 paired supervision protocol：

1. 同一场景 world bank 跨位置复用，避免地图变体成为位置 ID；
2. 同一 `(x,c,ξ_phys)` 的 edge 两侧由冻结 RT 重追踪，监督对象逐样本可审计；
3. 只有物理与 teacher 双重确认的 active edge 进入相对 alignment；
4. gray/null 不被硬标为负样本，null 还显式约束不过度反应；
5. response 直接靠近 RT target-world `H_v` 导出的 target，而不是只把另一支推远；
6. 两条监督共同更新并最终只保留同一个 state encoder；
7. 四臂、交互效应、机械拼接对照和跨城下游共同决定方法 claim 是否成立。

---

## 5. CGS、relative compatibility 与风险校准

### 5.1 CGS v6 的操作定义

在留出的 active edges 上，对每个固定物理单元构造：

```text
matched side:           (H_u, M_u), (H_v, M_v)
paired active alternative: (H_u, M_v), (H_v, M_u)
```

每条 edge 的 H 边际和 M 边际逐边相同。包括 CSI-PAIRS 在内的所有模型都冻结 `F`，使用相同数据、相同线性和两层 MLP 探针、相同参数量、训练步数和 source-only 选模预算。CGS 仍定义为 **fixed-budget compatibility decodability**，主数值为 active matched-versus-alternative AUROC，并按 `δ_phys` 四桶分别报告。

这个指标测的是固定探针预算下的可解码性，不是表征的固有信息量。gray 不进入 AUROC，只报告 score gap 分布。null 不当负类，单独报告：

- matched/alternative 绝对 score gap；
- 超过 source noise tolerance 的 false-incompatibility rate；
- 与 identity/no-edit noise floor 的等效检验，而不是用“不显著”冒充“等于零”。

无地图 CSI-only 模型只作为协议 negative control，不与 map-conditioned 模型并列暗示它“没有学到地图”。

当可公平运行的 map-conditioned 模型不少于 3 个时，保留 V4.1 的跨模型散点：横轴为所有模型同协议的 active CGS，纵轴为 unseen-city median error。该图只展示二者是否具有一致趋势，不把少量模型上的相关性写成因果关系。CSI-only negative control 使用不同 marker 单列。

### 5.2 intrinsic energy 与统一探针分表报告

四臂都共享 zero-action predictor，因此都能按第 4.3 节计算 native `s_{θ,ψ}`；区别在于只有 alignment-only/full 用 `L_A` 显式优化过其 active 排序。四臂的 intrinsic active AUROC、校准误差和 reliability curve 单独成表，不进入跨模型统一探针主图。另报 intrinsic predictive energy 与统一 probe 排序的 Spearman、AUROC 差值，检查 native readout 是否与保留表征一致。

response-only 和 full 的 native response predictor 同样另表报告。native response 的唯一主指标预注册为：full-channel active transitions 上，target-free mask-cover 得到的完整 CSI scene-macro NMSE。null hallucination 是独立 safety gate，SGCS、delta cosine/magnitude 和 PL/DS/AS 变化均为 secondary。

跨四臂比较 representation 时，再训练一个固定预算 action-conditioned response probe：输入 frozen `F(H_u, M_u)`、同一 signed edit grid 和 query，固定预测 physical target patch `y_v^q`。统一 probe 的唯一主指标是 `r^{R, q}=active` 上的 scene-macro physical-patch NMSE，不允许在看到结果后改选 `Δz`。这样可以区分“信息留在 `F`”与“只有将被丢弃的任务头会做题”。

### 5.3 `q_comp` 是成对条件概率，不是全局地图真伪概率

对随机排列的 active candidate maps `(M_a, M_b)`，定义 pairwise margin：

\[
d_{\mathrm{comp}}=s(H, M_a)-s(H, M_b).
\]

在独立 `source-calibration-fit` 上拟合：

\[
q_{\mathrm{comp}}
=\sigma\left(\frac{d_{\mathrm{comp}}}{T_A}\right),
\qquad T_A>0,
\]

其中 temperature `T_A` 只用 `source-calibration-fit` active edges 按 NLL 拟合，随后冻结。这个无截距、反对称形式强制 `q(d)+q(-d)=1`，避免交换候选顺序后得到两个互不相容的概率。其语义是“在这条 active paired-intervention edge 的两个候选中，第一张地图是生成侧的概率”。candidate 顺序随机。

对 null edge，理想输出接近 `0.5`，但不在 null 上重新拟合 calibrator。对 arbitrary wrong-city、geometry-destroyed 或 empty map，除非 source calibration 预先纳入相同 corruption family，否则只报告 raw score 和 stress-test 行为，不报告具有概率含义的 `q_comp`。

`r^A=active` 的资格依赖 paired counterfactual `H_v` 与 `T(H_v)`，在线只有当前 `H` 和两张候选地图时无法自行判断是否落在该 support。因此 `q_comp` 是 **offline paired-audit probability**，不是能自知适用范围的在线置信度。`p_fail` 在预注册的 correct/active/gray/null 混合上直接校准失败标签，不要求测试时观察 route label，但仍需要冻结的 paired proposal set，并受 source feature support 限制。

### 5.4 `p_fail` 与 `q_comp` 必须分开

定位头统一为 heteroscedastic regression head，输出位置均值 `μ` 和 raw scale `v`，并用正值参数化：

\[
\Sigma=\operatorname{diag}\left(
\left(\operatorname{softplus}(v)+\sigma_{\min}\right)^2
\right).
\]

所有方法使用相同 `σ_min`、Gaussian NLL 与 Huber point loss 在源域位置标签上训练。定义：

\[
u_g=\log\det\Sigma.
\]

失败事件为：

\[
Y_{\mathrm{fail}}=\mathbf 1[\lVert\hat x-x\rVert_2>\tau_{\mathrm{loc}}],
\]

其中 `τ_loc` 在 source 域预注册。风险校准器为：

对每个 supplied map，在 RT 和模型输出生成前，由确定性的 map-side proposal rule 构造大小相同的 paired comparison set `P(M_used)`。它只能读取 `M_used`、公开 radio configuration 和预注册 edit library/seed；不得读取 target-world CSI、active/gray/null route、effect bucket、true generating side、bank/world ID、receiver label 或定位结果。proposal 应由 canonical edit operator 直接作用于 supplied map，而不是看完 RT effect 后从邻居中挑最强的一条。无合法 edit 时使用预注册 fallback 并单报 coverage，不能缩小分母。只有一个合法 paired map 时集合大小为 1；有多个 candidates 时固定使用 worst-case margin：

\[
d_{\mathrm{used}}
=\min_{M'\in\mathcal P(M_{\mathrm{used}})}
\left[s(H, M_{\mathrm{used}})-s(H, M')\right].
\]

\[
p_{\mathrm{fail}}
=\operatorname{Cal}_{\mathrm{risk}}\big(
d_{\mathrm{used}}, u_g(H, M_{\mathrm{used}})
\big).
\]

headline `Cal_risk` 固定为带 L2 正则的 logistic calibration。标准化也写死为 median/MAD：

\[
\widetilde d=\frac{d-\operatorname{median}_{\mathrm{fit}}(d)}
{1.4826\operatorname{MAD}_{\mathrm{fit}}(d)+\epsilon_s},
\qquad
\widetilde u=\frac{u-\operatorname{median}_{\mathrm{fit}}(u)}
{1.4826\operatorname{MAD}_{\mathrm{fit}}(u)+\epsilon_s},
\]

其中统计量只来自 `source-calibration-fit`，`ε_s` 在 `source-method-selection` 冻结。随后拟合：

\[
\operatorname{Cal}_{\mathrm{risk}}(d, u)
=\sigma\left(\beta_0+\beta_d\widetilde d+\beta_u\widetilde u\right).
\]

主 calibrator 加入方向约束 `β_d≤0,β_u≥0`：supplied map 的相对 compatibility 越高，风险不能反而升高；定位 covariance 越大，风险不能反而降低。约束模型若不能胜过 `u_g-only` 或系数压到无信息边界，则“compatibility 转化为 risk”的 claim gate 失败。正则强度只从预声明网格中选择：候选均在 `source-calibration-fit` 拟合，只用 `source-calibration-selection` 的 NLL 决定，选中参数随后冻结。含 `\widetilde d\widetilde u` interaction 的版本只作预声明 sensitivity，不与主 family 事后择优。

correct/active/gray/null 的采样 prevalence 先在 `source-method-selection` 冻结；因此 `p_fail` 的概率语义只对应这个预注册 paired-audit mixture，gray/null 可以提供真实失败标签，但仍不获得 ranking 标签。若要外推到自然部署 prevalence，必须预先给出部署先验并做 label-shift/reweighting；没有该信息时只报告排序和 coverage 行为，不声称部署概率已校准。

`q_comp` 的 candidate 顺序可以随机，因为它预测哪一侧是 generating map；`p_fail` 不允许沿用这个随机符号。对每个定位输入，`M_used` 必须是实际送入位置头的 supplied map，proposal 数量、生成规则与 `min` 聚合在 source/target 间完全相同，`u_g` 也必须由 `(H,M_used)` 的定位输出计算。目标城市上 calibrator 完全冻结。主比较分两层：

- **公平表征比较**：四臂都使用统一 frozen compatibility probe 的 margin 和相同 `u_g`；
- **native 诊断比较**：四臂都报 intrinsic `s_{θ,ψ}` 产生的 `q_comp` 与 `p_fail`，并明确 A/full 才直接优化过 alignment。

报告 `d_used-only`、`u_g-only` 和 joint 三臂，以及 localization ECE、Brier、NLL、Spearman、risk-coverage、AURC 和 90%/75%/50% coverage 下的 median/P90。

feature-support 也使用固定算法。令 `v=\operatorname{clip}((\widetilde d,\widetilde u),-5,5)`，在 `source-calibration-fit` 上计算 empirical location `\mu_v` 和 covariance `\Sigma_v`；median/MAD 与固定 winsorization 提供稳健性。定义 regularized Mahalanobis distance：

\[
D_{\mathrm{support}}^2(v)
=(v-\mu_v)^\top(\Sigma_v+\epsilon_I I)^{-1}(v-\mu_v).
\]

阈值取 `source-calibration-selection` 上的预注册 `(1-α_support)` quantile；`α_support` 和 `ε_I` 在 `source-method-selection` 后冻结。所有 target points 都输出 inside/outside 标记并报告 outside 比例；outside points 只报告 raw score 与 error，不把 `p_fail` 当作已校准概率。

不同 arm 的 source support 可能不同，不能让 full 通过把困难样本判为 outside 来获得更低 ECE。四臂 headline calibration 比较固定在共同分母：

\[
\mathcal S_{\mathrm{common}}
=\bigcap_{a\in\{00,10,01,11\}}
\{i:D_{\mathrm{support},a}^2(v_i)\le t_{\mathrm{support},a}\}.
\]

共同 support coverage 必须超过预注册 floor，且 full 的 outside rate 对两个单分支达到非劣界，之后才比较 `S_common` 上的 ECE/Brier/NLL 与 reliability CI。每个 arm 自己的 inside-support 校准只作补充；全体 query points 仍报告 raw-score ranking/AURC 和误差，不赋予 support 外概率语义。

headline risk audit 只报告未做目标更新的 `k=0` checkpoint。若要报告 `k=8/32/128`，必须在 source 城市预先复现完全相同的 k-shot adaptation protocol，并为每个 `k` 和更新规则单独拟合、选择、冻结 calibrator；目标 support labels 不能参与校准。否则 k-shot 只报告定位误差，不报告 ECE/AURC 概率 claim。

当前概率 claim 明确需要 paired candidate context。只有单张待检地图、没有预注册 comparison/proposal bank 的部署场景，不在本论文的 calibrated risk claim 内。可在附录研究固定 edit-proposal bank，但不能把它偷偷写成已解决的单地图风险检测。

---

## 6. 可以严格写出的理论结果与边界

### 6.1 命题 1：same-world matched support 不识别 intervention response

令 matched predictor 输入为 `(H, M, a)`，常规正确配对训练只观察 `a=0`。若两个 predictor 在 matched support 上几乎处处相同，则它们具有相同 matched risk，但在 `a≠0` 的 intervention support 上可以任意不同。

因此，正确配对的 endpoint/masked prediction 不能单独规定地图编辑后的 target。这个命题只说明监督支撑的缺口，不说明所有 `(H_i, M_j)` 都不可能，也不把 wrong-map reveal 当成全局不相容证明。

### 6.2 命题 2：edge-symmetric active 四元组的边际匹配

对任意固定 `(b,x,c,ξ_phys)` 和任意 active 无向 edge `{u,v}`，matched multiset 为：

\[
\{(H_u, M_u),(H_v, M_v)\},
\]

paired-alternative multiset 为：

\[
\{(H_u, M_v),(H_v, M_u)\}.
\]

二者的 H 边际均为 `{H_u, H_v}`，M 边际均为 `{M_u, M_v}`。只要 active gate 对方向对称、两侧等权进入，物理/teacher gating 不破坏这一逐边等式。因此任何只使用 `φ(H)` 或只使用 `ψ(M)` 的单模态统计量都不能区分 matched 与 alternative 标签。

该命题不排除 joint world-ID matching。后者必须靠 scene-level reuse、unseen-bank/unseen-city 和显式 variant-ID baseline 经验排除。

### 6.3 命题 3：零 active ranking loss 的有限含义

若某 active edge 上 `m_uv>0` 且双向 ranking loss 为零，则：

\[
s(H_u, M_u)\ge s(H_u, M_v)+m_{uv},
\]

\[
s(H_v, M_v)\ge s(H_v, M_u)+m_{uv}.
\]

constant、CSI-only、map-only 和同 tile scene-ID-only 打分无法同时满足这两个不等式。这个结果证明 score 必须利用 pairwise joint coupling，但仍只在 active paired support 内成立，不能推出全球位置空间中的绝对 compatibility。

### 6.4 引理：target regression 比 ranking 多规定了什么

若 active pair 上 identity 的 latent `L_B=0`、`L_target=0`，且距离函数为零当且仅当两输入相等，则：

\[
\hat z_{u\to u}=z_u,
\qquad
\hat z_{u\to v}=z_v,
\qquad
\widehat{\Delta z}_{uv}=\Delta z_{uv}.
\]

因此 `L_Δ` 不是新的识别来源，而是有限优化下对方向与幅度的直接强化。ranking 只要求另一侧分数足够低，不包含靠近 RT target 的向量约束。这是 loss 语义，不包装成新的深理论贡献。

### 6.5 动作信息价值

令 `S=(V_m(H_u),G(M_u),c, m, q)`，`A=Δ_uv` 是模型输入前的 raw signed edit grid，`Z=z_v^q`。branch bundle 保证同一 `S` 下多个 raw action 具有正概率支持。在平方损失下：

\[
R_{\mathrm{noA}}^*-R_A^*
=\mathbb E\left[
\operatorname{tr}\operatorname{Cov}(\mathbb E[Z\mid S, A]\mid S)
\right]\ge0.
\]

只有当 target conditional mean 随 action 在正测度集合上改变时，差值才严格大于零。模型实际读取 `e_uv=E_φ(A)`，learned action encoder 可能塌缩并丢失上述信息，因此命题不能把 `E_φ` 的成功当作前提。full vs no-action、action-embedding effective rank 和 fixed-checkpoint action swap 必须从实验上验证信息确实被使用。物理 CSI 有差异还不够，frozen teacher 也必须保留该差异。该结果是 Bayes-risk 的信息论陈述，不保证有限网络一定达到最优。

### 6.6 理论不声称协同，协同必须由四臂赚取

alignment 的序关系不能唯一确定 response 向量；response head 能命中 target 也不自动保证 compatibility 留在 `F`。这说明两项监督不相互包含，但不能证明联合训练一定更好。是否互补、相加或相互干扰，必须由第 7 节的 2×2 实验、交互效应和参数/FLOPs 匹配的机械拼接对照决定。

### 6.7 source CSI 的信息价值与 no-x 边界

令 `B=(G(M_u),Δ_uv, c, m, q)` 包含 map/edit-only 方法可合法读取的全部信息，`C=V_m(H_u)`，`Y=Δz_{uv}^q`。平方损失下：

\[
R_B^*-R_{B, C}^*
=\mathbb E\left[
\operatorname{tr}\operatorname{Cov}(\mathbb E[Y\mid B, C]\mid B)
\right]\ge0.
\]

同一 world/action 跨大量位置复用，使这一信息差可被 full 与 edit/map-only 的对照检验。它不保证有限网络达到 Bayes optimum，也不保证 source CSI 完全消除位置歧义。真实 UE 位置 `x` 只能进入 RT、配对索引、effect 标注、下游标签和 oracle 诊断，不能作为主预训练模型输入。

---

## 7. 严格四臂：CSI-PAIRS 的决定性实验

### 7.1 四臂不是四个不同工程配置

四臂固定为一个 `2×2` 因子实验：是否加入 alignment，是否加入 response。

| Arm | 共同 endpoint `L_B` | alignment `L_A` | response `L_R` | 下游保留 |
|---|---:|---:|---:|---|
| **Endpoint** | ✓ |  |  | 同一 `F_θ` |
| **Alignment-only** | ✓ | ✓ |  | 同一 `F_θ` |
| **Response-only** | ✓ |  | ✓ | 同一 `F_θ` |
| **CSI-PAIRS full** | ✓ | ✓ | ✓ | 同一 `F_θ` |

名称在全文固定。`Endpoint` 就是第 4.2 节的 same-world identity/matched prediction，不再有时指 SigMap 定位 loss、有时指 MAE。

### 7.2 必须完全匹配的条件

四臂共享：

- 同一 Stage-0 teacher、physical target 定义和 CSI 初始化；
- 同一 scene-level banks、自然原图、raw `NK` 条信道和共同位置集；
- 同一 edge、方向、mask、query、数值增强与 batch 顺序；
- 同一地图 tokenizer、state encoder 宽度、融合模块和 predictor 容量；
- 同一训练步数、unique source units、batch 顺序、source-only 选模集与调参次数；
- 同一源域定位标签、位置头、优化器和 `k>0` 更新参数集合；
- 同一 target-city 信息预算。

所有臂都实例化同规格模块，只通过 loss factor 是否为零区分。`λ_A` 在 alignment-only/full 中相同，`λ_R` 在 response-only/full 中相同。没有使用 action 的臂不能额外扩宽 backbone 补偿，使用两个辅助目标的 full 也不能获得更多目标城市调参机会。

由于 alignment 需要 crossed-map forward，response 需要 action forward，原始 FLOPs 不可能字面相同。主结果必须报告训练 FLOPs、source forward 数和 wall-clock；若超过预注册容差，给单分支增加等 FLOPs 训练控制。主四臂不通过改变 `λ_A/λ_R` 匹配总梯度，因为那会改变 factor 剂量；另用等步数、等 FLOPs 和 gradient-norm 稳健性实验检查“只是更新更多”的解释。

### 7.3 预注册主结果与交互效应

把越小越好的定位误差变成越大越好的 scene-bank utility。对 arm `a`、目标城市 `c`、标签预算 `k`、独立 bank `b`、配对训练 seed `s` 和配对 label draw `d`，只在冻结的 target-query receiver positions 上，使用预注册 supplied correct/natural map 计算该 bank 内位置误差的 median；adaptation-support positions 及其所有 siblings 均已按第 2.7 节排除。定义无量纲 log error：

\[
\bar\ell_{a, c, k, b}
=\operatorname{mean}_{s, d}
\log\left(
\frac{\operatorname{MedianError}^{\mathrm{query, correct}}_{a, c, k, b, s, d}}
{1\ \mathrm{m}}
\right),
\]

其中 `k=0` 没有 label draw。主效用固定为：

\[
J_a
=-\frac{1}{2|\mathcal C_{\mathrm{tgt}}|}
\sum_{c\in\mathcal C_{\mathrm{tgt}}}
\sum_{k\in\{0,8\}}
\frac{1}{|\mathcal B_c|}
\sum_{b\in\mathcal B_c}\bar\ell_{a, c, k, b}.
\]

`k=8/32/128` 使用查看目标结果前冻结的多个嵌套 unique-position label draws，即每个 draw 的 8 个 receiver positions 是其 32、128 position 集合的子集；每个 position 只提供一条 correct/natural observation，四臂共享完全相同的 draw。draw 数量在 `source-method-selection` 后冻结。常规 pooled city median 仍在主表报告，但不用于 `Δ_int`，避免在 city median 与 bank-macro 之间事后选择。

记四臂效用为 `J_00, J_10, J_01, J_11`，交互量为：

\[
\Delta_{\mathrm{int}}
=J_{11}-J_{10}-J_{01}+J_{00}.
\]

interaction 的主置信区间使用配对多层 bootstrap：目标城市作为固定报告层，在每个城市内重采样独立 banks；训练 seed 索引在全体 banks 上成对重采样，`k=8` label-draw 索引在对应城市内成对重采样；同一次抽样的 bank、seed、draw 在四臂间完全共享。bank 仍是最高层数据推断单位，seed/draw 只传播算法和 support-choice 不确定性，不能增加 scene 样本量。另报只重采 bank、对 seed/draw 条件化的 cluster CI，以及 leave-one-seed/draw sensitivity；主 gate 使用预注册的多层 CI。能够写“在预注册 log bank-median utility 上存在正交互”必须同时满足：

1. full 在 `J_a` 上分别胜过 alignment-only 和 response-only；
2. full 在 active CGS 上对 alignment-only 达到预注册非劣界；
3. full 在预注册的 active full-channel target-free CSI NMSE 上对 response-only 达到非劣界；
4. `Δ_int` 的配对多层 scene-bank bootstrap 置信区间下界高于 0，并超过预注册最小实际效应；
5. 两个目标城市的 `k=0/8` 均不出现超过容许界的反向退化；
6. full 在 `J_a` 上分别达到对 equal-FLOP alignment-only 与 equal-FLOP response-only 的预注册实际优越界，排除“只是更多 forward/updates”；
7. full 胜过第 7.4 节参数/FLOPs 匹配的机械拼接对照。

full 同时胜两个单分支只是必要条件，不足以单独证明 synergy。`Δ_int` 只是在预注册 `-log bank-median error` 尺度上的交互，不能无条件外推为所有指标上的一般协同。若前三项成立但 `Δ_int≤0`，只能写“两类监督互补并可统一训练”；若 full 未胜两个单分支，CSI-PAIRS 不能作为 headline 方法。

### 7.4 机械拼接对照

训练两个互不共享梯度的独立 encoder：一个只做 alignment，一个只做 response。下游先拼接两种表示，再通过预声明、可训练的线性 bottleneck 投到与 full 相同的表示维度；bottleneck 只使用四臂共同的源域定位标签，与位置头一起训练，其参数量、训练数据和 FLOPs 全部计入资源匹配。这里的“预声明”指架构在看结果前固定，不是冻结随机投影，后者可能主动丢掉单分支信息而使对照失真。不能想当然地使用“半宽”，因为 Transformer 参数近似随宽度平方变化。应先用实际实现 profile 反解宽度/深度；若一个配置无法同时匹配参数与 FLOPs，就分别报告 parameter-matched 和 FLOP-matched 两个独立拼接对照，并公开误差比例。

资源匹配拼接回答的是同总资源下的表示效率，不能单独排除“每个任务在 full 中拥有更大有效容量”。因此另报两个全宽单分支表示不降维 concat 的 `2× compute` generous upper control，并为其使用匹配输入维度的位置头、如实计入额外参数与 FLOPs。full 若以约一半资源匹配它，支持共享编码效率；full 若还能胜它，才是更强的非机械证据。P1 再做两项 gradient-stop 诊断：

- response loss 在 `F` 前 stop-gradient；
- alignment loss 在 `F` 前 stop-gradient。

如果某分支停止更新共享 `F` 后，对应跨能力与下游增益消失，才支持两类监督确实通过 shared representation 发生作用。

### 7.5 分支本职指标与跨能力指标

| 目标 | native 指标 | 四臂统一 frozen probe |
|---|---|---|
| Alignment | 四臂的 predictive energy active AUROC、`q_comp` 校准；A/full 直接受 `L_A` 监督 | 四臂相同 probe 架构/步数的 CGS、null over-discrimination |
| Response | R/full 的 target-free NMSE/SGCS、delta 方向与幅度 | 四臂相同 probe 架构/步数的 action-conditioned response decodability |
| Localization | 无额外任务头，只用 `F` | 同位置头、同标签预算 |
| Risk | 四臂都报 native energy；A/full 直接受 `L_A` 监督 | 四臂统一 probe margin + 同一 `u_g` |

full 的合理目标不是在每个 native 数字上都显著超过专门单分支，而是在各分支本职指标上非劣，同时在另一分支的跨能力和最终跨城定位上获得增益。

---

## 8. P0 实验问题

### RQ1：现有模型是否反事实一致地使用地图

按第 1.1 节六条件协议至少评测两个 map-conditioned 模型。外部代码或数据不可得时，允许使用 paper-spec controlled implementation，但必须准确命名，不能写 faithful reproduction。

主读数是定位 median/P90。只有本来具有同构 masked predictor 的模型才另报 prediction error，不为表面统一而临时给纯定位模型加一个新 head。必须区分 active 和 null：

- active alternative 与 correct 几乎无差、empty 明显退化，支持“使用粗地图条件但缺乏局部响应”；
- null alternative 不应导致大幅退化，若模型反而强烈响应，说明它对编辑痕迹过敏；
- wrong-city 只作压力测试，不代替 active paired evidence。

训练后用同一六条件做一张 before/after behavior-recovery panel：active margin 是否恢复、null 是否不过判、paired-context `p_fail` 是否随真实失败上升、correct-map 跨城定位是否改善。wrong-city、geometry-destroyed 和 empty 若未进入 source-risk calibration family，只报 raw score，不画 calibrated probability。错图后误差上升本身不是优点；没有可靠 compatibility/risk 读数的模型不能称为 graceful degradation。

### RQ2：alignment 是否学到受限但可靠的 relative compatibility

四臂统一 CGS 主表报告：

- active AUROC，按 `δ_phys` 四桶；
- unseen-position、unseen-edit、unseen-bank 与 unseen-city；
- null score gap 与 false-incompatibility rate；
- gray score gap 分布，不给 gray 硬贴分类标签；
- constant、CSI-only、map-only、scene-ID-only、edit-status XOR 和 variant-ID matcher；
- 四臂 native predictive energy 与统一 probe 的一致性。

alignment-only 必须在留出 bank/city 的 active CGS 上胜 endpoint，同时 null 过判不高于预注册容差。只在训练 bank 高、留出 bank 回落的结果说明模型记住了 world fingerprint，不构成 compatibility 学习。

P1 加入“V4.1 旧式所有非对角都 ranking”的对照，直接测它是否提高 active AUROC 却同时制造 null/gray 误报。该对照的作用是证明 v6 的 effect routing 不是文字上的保守化，而是修复可测的错误监督。

### RQ3：response 是否预测 RT 重追踪后的方向与幅度

冻结一组 target-free `(m, q)` mask-cover bank，使每个 target patch 至少被查询一次。每次只输入 `V_m(H_u)`、source map 和 signed edit，预测 target patch；重叠 patch 按预注册规则平均并拼成完整 `hat H_v`。真实 `H_v` 只能在组装完成后评分，不能在 mask-cover 过程中提供任何 patch 或 token。

native response 的唯一主指标是：在 full-channel `r^A=active` transitions 上，target-free mask-cover 组装完整 `hat H_v` 后计算的 scene-macro CSI NMSE。null safety gate 单独检验 hallucination 是否落在 replicate noise-floor 等效界内。

secondary 指标包括：

- SGCS；
- path loss、delay spread、angular spread 变化误差与方向正确率；
- active delta cosine 与 magnitude ratio；
- gray target absolute error，不作强 delta 结论。

辅助 latent 指标可报告 TransitionSkill：

\[
\operatorname{TransitionSkill}
=1-
\frac{\sum_{(u, v)\in S_+}d(\hat z_{u\to v}, z_v)}
{\sum_{(u, v)\in S_+}d(z_u, z_v)},
\]

其中 `d(a,b)=ρ_z(a,b)` 使用第 4.2 节冻结的 latent normalization，`S_+` 只含 `r^A=active` 且 teacher-sensitive 的完整 transition units。先在每个独立 bank 内计算 numerator、copy denominator 与 ratio，再做 scene macro；denominator 或 coverage 不足记 `N/A`，不能事后加小常数。

必须包含的 response 对照：

| 对照 | 回答什么 |
|---|---|
| CSI persistence/copy | 不预测变化是否已经很强 |
| no-action | branching 下 action 是否提供信息 |
| fixed-checkpoint geometry-matched action swap | 同一个训练好模型是否真的读取了正确 action |
| w/o source map | response 是否需要 source geometry |
| edit/map-only | 是否只记平均编辑响应 |
| CSI-only | 是否只靠 source CSI 外推 |
| oracle-x | 无显式位置条件下的可预测上界，单列信息预算 |

test-time action swap 固定同一 source unit、mask、query 和 checkpoint，只把 `e_uv` 换成同 source、同编辑族和同量级的错误 `e_uw`。必须报告 exact/fallback/failed candidate coverage；所有方法在完全相同 qualified support 上比较，不能使用不同分母。

### RQ4：联合监督是否改善严格 unseen-city 定位

至少两个完整留出城市，目标标签数：

\[
k\in\{0,8,32,128\}.
\]

每个城市分别报告 median、P90、3 个以上训练 seeds 的算法方差和 scene-bank bootstrap 区间，再给 macro average。`k=0/8` 是主检验，`k=32/128` 展示 label-efficiency 曲线。域内正确自然图精度同时报告，检查 paired training 是否牺牲常规性能。

这里 `k` 是唯一 receiver-position 标签数，不是 CSI-map example 数。few-shot support 每个位置只提供一条预注册 correct/natural observation；support/query 按第 2.7 节整组隔离，任何 support position 及其 sibling worlds 都不进入 median、P90、risk 或 interaction 分母。

所有城市统一使用已知 BS 位姿建立右手米制局部坐标：原点为 reference BS，x 轴取阵列 boresight 水平投影，z 轴为重力方向。地图、BS token 和位置输出使用同一刚体坐标。目标城市禁止用位置标签、包围盒、均值方差或测试结果拟合归一化。

严格 `k=0` **single-map localization** 只允许 supplied target map、BS 位姿和单条待定位 CSI，不允许目标无标签 CSI 更新、target fingerprint/reference 库、目标统计量、目标校准、梯度更新或超参数选择。需要目标参考库的方法单列为 transductive/retrieval setting。第 5.4 节的 paired-proposal risk audit 是额外信息设置，不能与这个单图定位协议混写。

headline 表先放严格四臂，再放外部强基线。最终判断以 full 是否胜两个单分支及第 7.3 节交互量为准，不能拿 full 对一个较弱外部 baseline 的胜利替代受控内部比较。

### RQ5：paired context 下 compatibility 能否转化为可靠的定位风险

RQ5 是 **paired-proposal risk audit**：除 single-map localization 的信息外，额外允许第 5.4 节预先冻结、只由 map-side rule 生成的 `P(M_used)`。这个额外 proposal 信息预算必须单列，不能暗示严格单图部署可直接计算 `p_fail`。对四臂先使用统一 probe margin 完成公平比较，再为四臂全部报告 native predictive energy，并标明只有 A/full 直接优化过 alignment。所有 calibration 都严格使用第 2.7 节的 `source-calibration-fit/selection`，并在目标城市完全冻结；headline ECE/Brier/NLL/AURC 仅对应 `k=0` checkpoint。

风险闭环至少满足：

1. paired-active alternative 输入使 `p_fail` 上升；
2. correct 与 null 条件不产生系统性虚假高风险；
3. 四臂共同 support coverage 过门，full outside rate 对两个单分支非劣；
4. 共同 support 上的 ECE/Brier/NLL 与 reliability CI 通过预注册校准门；
5. 全体 query points 上，joint raw risk ranking 的 AURC 优于随机拒绝和 `u_g-only`；
6. coverage 从 90% 降到 75%、50% 时，保留样本的 median/P90 单调下降；
7. 每臂 target outside-support 比例和全体点 raw error 必须报告；
8. `q_comp` 的 ECE/Brier/NLL 与定位风险的 ECE/Brier/NLL 分表，禁止互相替代。

---

## 9. 路径机制与可辨识性分析

### 9.1 Path-incidence 是机制分层，不是独立因果识别

对每个 `(x,u,v)`，令 `P_u,P_v` 为两个世界保留的 RT paths，`P_p^u/P_p^v` 为接收功率。优先使用 RT 提供的 persistent path ID 与 ordered surface-interaction IDs 做一一对应；若引擎没有 persistent ID，则在 `source-method-selection` 上冻结 delay、AoA、AoD 与 interaction-order 容差，用确定性 bipartite matching 建立一一对应，未匹配路径分别记为 disappeared/new。定义 `I_{uv}^u(p)=1` 当且仅当 path `p` 与编辑表面交互，或它在另一世界无匹配；`I_{uv}^v` 同理。随后计算：

\[
A_{\mathrm{path}}(x, u, v)
=\frac{
\sum_{p\in\mathcal P_u}P_p^u I_{uv}^u(p)
+\sum_{p\in\mathcal P_v}P_p^v I_{uv}^v(p)
}{
\sum_{p\in\mathcal P_u}P_p^u
+\sum_{p\in\mathcal P_v}P_p^v
}\in[0,1].
\]

每个 path 的功率在其 world 内只计一次；matched path 若与编辑表面交互，两侧功率各计一次，正好对应分母中的两个 world，不属于重复计数。matching tolerance、tie-break 与 path-ID 规则在查看 target/model 结果前冻结，不能为了得到更漂亮的 `A_path` 分层事后调整。

RT 只保留累计功率达到预注册 `Q%` 的主路径；`Q` 由 `source-method-selection` 上的路径截断收敛曲线冻结，使继续提高累计功率时 `A_path` 的变化低于预注册容差。`A_path≤ε_path` 的 zero 组由 no-edit/identity numerical replicates 的 `(1-α_path)` quantile 决定，`α_path` 在读取该数据块前固定。它只用于评测分层，不进入模型、action、route 或采样优先级。

地图侧编辑幅度只由 edit grid 决定：

\[
\delta_{\mathrm{map}}
=w_o\frac{A_{\mathrm{occupancy\ change}}}{A_{\mathrm{tile}}}
+w_h\frac{\operatorname{RMS}(\Delta h)}{h_{\mathrm{ref}}}
+w_m\frac{A_{\mathrm{material\ change}}}{A_{\mathrm{tile}}}.
\]

`w_o,w_h,w_m,h_ref` 只用 `source-method-selection` 的 map-side scale 冻结，不读取 CSI、route、path 或模型结果。

匹配 active/zero 或 low/high 组时控制 edit family、面积/高度/材质规模、编辑到 BS/UE 的距离、scene、LoS/NLoS 和地图侧幅度 `δ_map`，报告 SMD、overlap 与有效样本量。不能匹配作为编辑作用中介的 `δ_phys` 后再声称 path-incidence 有效应。

可守的预测签名是：

- alignment score gap 随 `A_path` 增长；
- full/response 相对 no-action 和 action-swap 的 response error 优势随 `A_path` 增长；
- zero 组的预测变化不超过 noise-floor 容差；
- full 相对两个单分支的收益主要出现在 geometry-relevant strata。

这叫 **mechanism-consistent effect heterogeneity**，不写成“path-incidence 独立识别了因果效应”。

### 9.2 定位分析必须预先聚合多条 edit

`A_path(x, u, v)` 是 transition 属性，不能把与当前 source world 无关的整张 hypercube 边都平均到同一定位样本。若定位样本使用 bank state `u`，只聚合它的 incident edges：

\[
A_{\mathrm{path}}^{\mathrm{loc}}(x, u)
=\frac{1}{|\mathcal N_b(u)|}
\sum_{v\in\mathcal N_b(u)}A_{\mathrm{path}}(x, u, v).
\]

其中 `N_b(u)={v:{u, v}∈E_b}`。若 headline 定位输入是独立自然图 `M_b^nat`，则在生成 RT 前另行冻结一个 direct-edit proposal set `N_b^nat`，只平均从该自然状态直接出发的 edits。该 proposal set 对所有方法相同，不按模型结果或 target effect 选择。

不得事后挑最大 `A_path` 或只保留对 full 最有利的 edit。按 `A_path^loc` 的 zero/low/medium/high 桶报告 full 相对 endpoint、alignment-only、response-only 的定位差值。这一分析保留 V4.1 的“收益应出现在路径相关区域”主线，同时避免把无关 transition 属性随意贴到定位样本上。

### 9.3 LoS/NLoS 与 I(x)

LoS/NLoS 是 P0 辅助轴。NLoS 通常更依赖反射和绕射几何，但 LoS 不等于地图无用，NLoS 也不等于地图必需。应在相同 `A_path` 桶内比较，而不是用 LoS/NLoS 代替 path-incidence。

几何可辨识性 `I(x)` 保留为 P1：从 mesh 与 BS 位姿计算量化路径签名碰撞，检查高 `A_path` 样本中，收益是否集中在物理上可辨识的位置。若 `I(x)` 未通过预注册相关性与碰撞审计，删除“可辨识区域”子句，不影响 P0 的路径机制结果。

---

## 10. Shortcut、泄漏与负对照

### 10.1 必做审计表

| 风险 | 设计防线 | 必做测试 |
|---|---|---|
| per-location map 泄露位置 | scene-level bank 跨全部 `x` 复用 | 旧 per-location bank 与新 bank 的 map-only/position probe 对比 |
| 用户中心裁图泄漏 | 固定 BS-centric 网格 | token 数、顺序、padding 对 `x` 的独立性单元测试 |
| privileged pristine / edit XOR | randomized anchor、canonical render、自然图分支隔离 | edit-status XOR baseline |
| world/edit ID 记忆 | unseen-bank/edit/city 整体留出 | variant-ID matcher 训练侧可高，留出侧必须回落 |
| 单模态捷径 | active edge 四元组边际匹配 | constant、CSI-only、map-only、scene-ID-only |
| action 携带结果 | ID-free signed grid | 扫描序列化字段；edit-only baseline |
| target map/位置泄漏 | teacher 只读 CSI，主模型无 `x` | target bitwise test、allowlist 审计 |
| `H_v` 污染 predictor | target 只作监督 | 替换 batch 其他元素后 source 输出不变；禁止跨支路 BN/attention |
| effect route 泄漏 | route 不进输入 | 模型输入 schema 与保存 tensor 审计 |
| 目标城泄漏 | outer city 从 Stage 0 起留出 | normalization、threshold、checkpoint、calibration、gradient 清单 |
| 人工编辑域偏移 | 四臂等量看自然原图 | 自然正确图域内误差与 feature shift |
| 仿真噪声被当 effect | pair 共享 `ξ_phys`、两侧 `η` 独立；另做 replicate | no-edit/identity noise-floor 审计 |

### 10.2 打断物理配对关系的负对照

保留 V4.1 的证据链 A，但同时覆盖两个分支。在相同 edit family、effect bucket、scene 和数据量内，打乱：

- alignment 的 H-map edge coupling；
- response 的 action-target coupling。

保持单模态边际、loss 形式、训练步数和 effect 分布不变。若 shuffled-pair 仍在真实留出 edits 上得到同等 CGS、response 或跨城增益，说明收益不来自物理配对关系，方法 claim 失败。

test-time action swap 与 shuffled training 不能互相替代。前者检验一个训练好的模型是否使用正确 action，后者检验训练增益是否依赖真实 pairing。

### 10.3 retention 审计

训练后只对 frozen `F` 做：

- `w/o source map`；
- correct source map 与 paired-active alternative map swap；
- fixed-budget compatibility probe；
- fixed-budget action-conditioned response probe；
- source map gradient/attention 只作辅助可视化，不作决定性证据。

只有 native head 好、frozen `F` probe 不好时，结论必须降级为“disposable head 学会了任务”。

---

## 11. Baseline 与最近工作的准确位置

### 11.1 headline 内部基线优先

最重要的 baseline 就是严格四臂，因为它们共享数据、骨干、teacher、训练步数、mask/query、source-only 选择预算和下游头；原生 FLOPs 如实报告，并补 equal-FLOP 单分支控制。外部方法数量不能弥补四臂控制不严。

### 11.2 强外部基线

| Baseline | 本文角色 | 命名要求 |
|---|---|---|
| CSI-MAE | CSI-only masked signal prior 与 Stage-0 起点 | `official-code adaptation`，在本 split 重训，不冒充原文数字复现 |
| CSI-CLIP / CSI-CLIP++ | CSI-CIR consistency 强对照 | 有官方实现才按官方名；ViT 版本写 `CSI-CLIP++-style controlled implementation` |
| ContraWiMAE | reconstruction + contrastive 混合预训练 | 使用公开管线并重做严格 split；无权重时不写 official checkpoint |
| WWM | same-world matched predictive learning 的最邻近思想基线 | 资源不足时写 `WWM-inspired same-world matched prediction`，不写 faithful WWM |
| SigMap | map-conditioned localization 与 wrong-map reveal | 写 paper-spec controlled implementation；目标侧微调预算重新统一 |
| CSI-only map-free | 协议 negative control | 不把无地图模型的低 CGS 解释为 grounding 失败 |
| Wi-GATr-inspired oracle-x | 已知 receiver position 的信息上界 | 单列 privileged-x，不冒充严格 no-x baseline |
| RFIR official-code adaptation | 场景修改与无线前向建模邻近对照 | 只在共同物理 readout 和目标侧信息预算明确时比较 |

CSI-MAE、CSI-CLIP/++ 和 WWM 提供的是强 CFM 起点，但都不能替代 scene-level paired intervention。CSI/CIR 是同一信道的确定性变换视图，不是两个独立物理世界；same-world masked prediction 也没有规定地图变化后的 response。

### 11.3 related work 的差异轴

最近的差异轴只保留三条：WWM、CSI-MAE 与 CSI-CLIP/++ 都在同一世界或同一信道视图上学习，CSI-PAIRS 的监督跨越 RT 重追踪的场景状态；SigMap 已经使用地图做定位，但没有 active/null paired intervention；Wi-GATr、WiSER 与 RFIR 研究带位置或场景输入的无线前向建模，本文 headline 不输入 receiver position，检验的是最终保留的 map-conditioned representation。ranking 是成熟工具，不作为贡献。

截止投稿前必须重跑邻近工作检索。任何 “first” 表述都需要独立证据；默认写 `we study` 和 `we introduce`。

---

## 12. 统计与审计协议

- 所有 source/target 数据权限严格服从第 2.7 节的唯一 split ledger；不得再临时创造名为 pilot、validation 或 calibration 的重叠子集。probe 不得读取 calibration banks，calibrator 不得复用 probe-selection，final unseen-bank/city 只评测。
- 四臂使用相同 probe 架构、样本数、训练步数、选择次数和 calibration family。risk calibration 的 correct/active/gray/null 抽样比例在 `source-method-selection` 后冻结，它定义 paired-audit mixture 的 estimand；没有部署 prevalence/reweighting 时不外推为自然部署概率。
- headline 方法至少 3 个训练 seeds，使用配对初始化、数据顺序和 mask bank；seed 只表示算法方差。
- 独立统计单位是最高层 scene tile/world bank，不是 position、edge、方向、mask、patch 或 pair。
- 同一 bank 的 sibling worlds、全部位置、边、正反方向和增强始终留在同一 cluster。
- 先在每个 bank 计算 AUROC、NMSE numerator/denominator、AURC 和定位汇总，再做 scene-macro average。
- 两个目标城市逐城报告，不能据此声称对“所有城市总体”有统计显著性。
- primary interaction 使用 scene-bank cluster bootstrap；同时报告 effect size、置信区间和预注册最小实际效应。
- null/zero-path 采用相对 replicate noise floor 的等效检验，不能用 `p>0.05` 解释为“等于零”。
- active threshold、mask/query bank、primary outcome、non-inferiority margin、action-swap coverage、teacher agreement、oracle gap、null hallucination 上限和所有排除标准，只用 `source-method-selection` 冻结并存档。
- `source-calibration-fit/selection` 与 `source-method-selection` 严格分离。目标城市不得重新拟合温度、logistic calibrator、support threshold 或风险阈值。
- 报告 target samples 落在 source calibration feature support 外的比例，避免 ECE 被平均数掩盖。
- 所有跨城配置生成信息预算审计清单，逐项记录地图、BS 位姿、无标签 CSI、reference 库、位置标签、归一化与更新权限。

主 claim 使用分层 gatekeeping，顺序在看 target 结果前固定：

1. alignment 与 response 单分支各自先胜 endpoint/copy；
2. full 在 alignment/response native primary 上通过单侧非劣检验；
3. full 分别胜两个单分支的 `J_a`；
4. 检验 preregistered log-utility interaction；
5. 最后检查两个城市与 `k=0/8` 无超过容许界的反向退化。

同一层含多个 superiority/non-inferiority 对比时使用 Holm 或预注册的 simultaneous cluster-bootstrap interval 控制 family-wise error。上游 gate 未过，下游 `p` 值只作探索性报告。

---

## 13. 主文图表

主文优先保留六个图表：

1. **Figure 1：错图现象与 CGS。** correct、active alternative、null、wrong-city、destroyed、empty；至少两个模型；active CGS 与 null over-discrimination 并列。
2. **Figure 2：CSI-PAIRS 方法图。** scene-level hypercube 跨位置复用，同一 edge 的 alignment quartet、branch bundle、signed edit、CSI-only target 和 shared `F/P`。
3. **Table 1：四臂的 alignment/response 能力。** 统一 CGS、统一 response probe、native response、null safety、interaction 前置指标。
4. **Table 2：两个未见城市的定位与风险。** single-map localization 对 `k=0/8/32/128` 报 median/P90；paired-proposal risk 只对 `k=0` 报 AURC/ECE/Brier。只有预先完成 source episodic calibrator 时，k-shot risk 才另列附表。
5. **Figure 3：2×2 交互与机械拼接。** `Δ_int`、parameter/FLOP-matched 独立拼接、full-width 2× compute 上界。
6. **Figure 4：路径机制。** `A_path` 分层下 score gap、response advantage、null hallucination 与预注册 `A_path^loc` 定位差值。

附录放：完整 shortcut suite、per-location bank 泄漏对照、old-all-off-diagonal ranking、全部 active/gray/null 桶、tokenizer 变体、gradient-stop、`I(x)×LoS/NLoS`、更多 baselines、自然图域偏移和外部干预。

---

## 14. Claim-Evidence Gate

规则：目标 claim 不会因为排期自动成立。任何证据未完成或结果为负，Abstract、Introduction 和贡献列表必须同步删除或降级，不能留给 rebuttal 补救。

| # | 目标 claim | 必须完成的证据 | 未达成时的提交写法 |
|---|---|---|---|
| C1 | 现有 map-conditioned 模型缺乏局部反事实几何响应 | 至少两个模型的 active/null wrong-map reveal | 只在具体模型上报告，不作领域断言 |
| C2 | scene-ID 是一种机制解释 | 源城留出位置准确率追平 + 地图/ID 替换响应一致 | 删除 scene-ID 解释，只写局部不敏感 |
| C3 | CGS 测到 active paired compatibility | 四臂统一 probe、逐 edge 边际审计、null 不过判、unseen-bank/city | 限定为具体数据上的 probe task，不称统一 grounding 指标 |
| C4 | alignment 依赖 joint physical pairing | A 胜 endpoint，单模态/ID 捷径失败，shuffled-pair 负对照失败 | 删除 alignment 方法 claim |
| C5 | response 预测 RT 重追踪后的方向与幅度 | target-free mask-cover、physical/latent 指标、copy/no-action/action-swap、teacher/readout 资格 | 只写 latent prediction，或删除 response claim |
| C6 | 几何与 response 信息留在最终 `F` | w/o-map、map-swap、统一 frozen probes、下游只读 `F` | 只称 disposable head 学到任务 |
| C7 | 两项监督不是机械拼接或额外计算 | full 胜原始及 equal-FLOP 两个单臂、Pareto 非劣、`Δ_int>0`、胜参数/FLOPs 匹配拼接 | 无交互只写 complementary；未胜控制则取消 CSI-PAIRS headline |
| C8 | 改善 zero/few-shot unseen-city localization | 两个目标城市，严格信息预算，`k=0/8` 达预注册实际改善 | 删除定位与 label-efficient claim |
| C9 | 给定冻结 comparison/proposal set 时，`k=0` paired-audit mixture 上能预测定位何时失败 | 四臂共同 support 分母的 ECE/Brier/NLL 与 reliability CI 过门，common coverage 足够且 full outside-rate 非劣；全体点 AURC 胜 random/`u_g-only`、coverage 单调 | 删除 calibrated-risk/graceful-degradation，不以 `q_comp` 顶替 |
| C10 | 收益具有传播路径机制签名 | `A_path` 分层、匹配审计、zero 等效检验、定位聚合预注册 | 只报平均结果，不作机制解释 |
| C11 | 数据来自 calibrated RT | 独立校准/验证四项统计过资格门 | 只称 simulator-defined，不称 calibrated |
| C12 | 超出单一模拟器 | 小型真实受控干预或独立 RT 引擎 | 全文限定 simulator-consistent |
| C13 | 方法具有首创性 | 截止投稿日的邻近工作更新检索 | 删除 first，使用有限差异轴 |

---

## 15. Go/No-Go 与风险树

### 15.1 分阶段闸门

| Gate | Go 标准 | No-Go 处理 |
|---|---|---|
| G0 文献与资源 | 无直接重合工作；RT/map/真实或第二引擎路径明确 | 收缩新颖性或暂停立项 |
| G1 world-bank 资格 | canonical render、共同 `X_b`、无 per-location/edit-status 泄漏、RT 资格状态明确 | 修数据，不启动主训练 |
| G2 teacher/no-x | effect agreement、physical readout 过门；masked no-x 胜 copy/no-action/action-swap | 换 raw physical target 或转 compatibility 诊断 |
| G3 单分支成立 | A 胜 endpoint 的 active CGS 且 null 不过判；R 胜 endpoint/copy 的 response | 对应分支不能进入 full claim |
| G4 full 联合价值 | Pareto 非劣、胜原始及 equal-FLOP 两单臂、交互过门、胜机械拼接 | 降为 complementary 或选择更强单分支 |
| G5 跨城 | 两目标城市 `k=0/8` 达最小实际改善 | 删除 label-efficient localization |
| G6 paired-context 风险 | `k=0`、四臂共同 support、冻结 proposal 下 calibration/AURC/coverage 三项闭环 | 删除“知道何时失败” |
| G7 路径机制 | score/response 优势随 `A_path`，zero 组等效安全 | 删除机制解释 |
| G8 外部有效性 | 真实小干预或第二引擎方向/null 一致 | 限定 simulator-consistent |

### 15.2 主要风险与 Plan B

| 风险 | 触发信号 | 处理 |
|---|---|---|
| wrong-map 现象不普遍 | 只在一个或零个模型成立 | 现象降级，重心移到 paired metric 和方法 |
| teacher 对物理 effect 不敏感 | 双空间 agreement 低 | 换 fixed raw/physical target，不用 latent 粉饰 |
| no-x 无法预测 response | oracle-x 强，no-x 接近 copy | 不偷加 `x`；转概率 response 或 compatibility 主线 |
| alignment 只学 world ID | train 高、unseen-bank/city 回落 | 增加独立 tiles、随机 anchor、重做 bank/split |
| response 只靠 action+CSI | w/o-map 不掉、map-swap 无效 | 收缩 grounding claim，改 source fusion 或停止 full |
| null 幻觉严重 | null error 超 noise tolerance | 提高 null coverage、dead-zone 权重，检查 edit artifacts |
| full 干扰单分支 | native 指标明显退化 | 梯度归一化、分阶段 schedule；仍失败则选单主线 |
| full 仅为加法 | 胜单臂但 `Δ_int≤0` | 写 complementary multi-task，不写 synergy |
| full 不胜机械拼接 | resource-matched concat 持平或更好 | 承认共享训练无额外价值，不能强推 PAIRS |
| CGS 涨但定位不涨 | G5 失败 | 不以 proxy 替代下游，检查 retention/位置头后决定转诊断论文 |
| 风险校准跨城漂移 | support 外比例高、AURC 不升 | 删除风险 claim，研究 domain-robust calibration |
| 自然图性能退化 | 域内或目标 correct-map 明显下降 | 调整共同 natural branch 比例，四臂重训 |
| 工期过载 | W5 前 P0 不齐 | 转更晚会期，不带缺失证据投稿 |

---

## 16. 执行时间线

| 周 | 工作 | 硬交付 |
|---|---|---|
| W1 | 更新文献检索；跑至少两个模型的错图 reveal；锁定地图网格、编辑族、坐标和目标侧预算；RT 资格门 | 现象结果、数据规范、claim 边界 |
| W2 | 两到三个独立 tile 的小 bank；canonical render、共同位置与泄漏 probes；轻量 teacher/readout；no-x/oracle-x kill test | G1/G2 preliminary 决策，不通过不扩数据 |
| W3 | 批量 scene-level world-bank RT；训练并冻结最终 teacher；重跑 effect agreement | 可审计 manifest、最终 route/threshold |
| W4 | 严格四臂在 source/unseen-bank 训练；单分支、shortcut、action-swap 与 pairing-break | G3、response/CGS 主表初版 |
| W5 | 两个目标城市 `k=0/8/32/128`；交互与机械拼接 | G4/G5 分流决定 |
| W6 | 统一 probes、`q_comp/p_fail`、risk-coverage、path-incidence 与 retention | 风险表、机制图、G6/G7 |
| W7 | 外部强 baseline；小型真实干预或第二引擎；补 P1 中最高价值项 | 外部有效性与 related-work 对照 |
| W8 | 主文图表、复现实验配置、逐条 claim gate 对账、内部红队 | 可提交版本 |

项目至少拆成三个并行工作包：RT/world-bank、四臂与 baseline、统一 probe/统计审计。W2 的 preliminary gate 只决定是否扩大数据；正式 G2-G7 必须使用最终 teacher、bank 和 checkpoint 重跑。

---

## 17. Abstract 骨架与贡献列表

### 17.1 工作标题

方法名已冻结，论文标题暂不冻结。当前最贴合 V4.1 叙事的工作标题为：

> **Do Map-Conditioned Wireless Models Use Geometry Counterfactually? CSI-PAIRS: Paired Alignment and Intervention-Response Supervision**

若错图现象未在至少两个模型上成立，改用方法导向标题，删除领域级问句。

### 17.2 Abstract 骨架

> Map-conditioned wireless models are trained on matched signal-scene pairs, but matched performance does not establish counterfactual sensitivity to local geometry. We audit this gap with paired active and null map interventions, then introduce CSI-PAIRS on reusable scene-level world banks. For the same receiver state and radio configuration, one shared predictor scores zero-action map-CSI alignment and predicts the RT re-traced target under an ID-free signed edit. Only physically and teacher-confirmed active edges receive relative alignment; gray and null edges are not treated as strong negatives. A strict `2×2` design compares endpoint, alignment-only, response-only, and full supervision using the same data, backbone, teacher, and downstream head. We evaluate fixed-budget compatibility, target-free channel response, paired-context localization risk, and zero/few-shot localization in two unseen cities. [Only if earned: Full supervision outperforms both single branches and yields a positive interaction on the preregistered log-error utility.] [Without external audit: Conclusions are limited to simulator-consistent paired interventions.]

### 17.3 目标贡献列表

实验完成前只使用“提出、建立、检验”，不把预期结果写成事实：

1. **诊断与度量**：建立区分 active、gray、null 的 wrong-map/CGS 协议，检验正确配对训练是否真正产生局部几何响应。
2. **数据与方法**：提出跨位置复用、节点均衡且边对称的 scene-level paired-intervention bank，以及作用于同一 state/predictor 的 alignment 与 target-response 联合监督。
3. **受控证据**：用同数据、同骨干、同 teacher、同训练步数和 source-only 选择预算的四臂，并补 equal-FLOP 单分支控制，结合交互效应、机械拼接、shortcut、target-free response 和 retention 审计，检验两类监督是否产生共享表征价值。
4. **下游与校准**：在无目标信息泄漏的 BS-centric 协议下，检验两个未见城市的 zero/few-shot 定位、relative compatibility 和给定冻结 comparison/proposal set 的 source-frozen localization risk。

---

## 18. 主要局限

1. paired worlds 主要来自 RT。没有外部干预证据时，结论只在 simulator-consistent 范围成立。
2. 主模型不输入 receiver position，source CSI 无法消除的碰撞会形成不可约条件方差。
3. 2.5D occupancy/height/material 网格无法表示所有细粒度三维结构和动态物体。
4. frozen teacher 可能丢失某些 simulator-defined physical effect，因此必须公开双空间 agreement 与 raw physical 指标。
5. scene-level edits 只覆盖预注册变化族，不能代表城市中所有地图陈旧与传播变化。
6. `q_comp` 是 active paired candidate 内的相对概率；`p_fail` 的概率语义也受 source calibration support 和 paired context 限制。
7. 两个目标城市足以做严格留出验证，但不足以支持“对所有城市普遍成立”的总体推断。
8. full 的训练开销高于普通 same-world endpoint，不能写 training-cheap；它追求的是减少位置标签需求，而不是减少总计算。
9. 定位是本文唯一 headline 下游，不能自动外推到波束、感知、资源调度或整个 RAN 控制闭环。

---

## Appendix A. v6 合并决策记录（内部，不进入论文正文）

| 原问题 | v6 修复 | 不修复的直接后果 |
|---|---|---|
| V4.1 每个位置拥有独立 K 张地图 | scene-level bank 跨全部位置复用 | 地图纹理可成为位置 ID，定位提升无法归因于几何 |
| V5 hypercube 被误称 exchangeable | 改为 node-balanced、bidirectional、edge-symmetric | 理论假设与实际采样不一致，边际证明站不住 |
| hypercube 有唯一 pristine 节点 | randomized anchor、canonical render、自然图分支隔离 | edit-status XOR 可以无须理解物理就解标签 |
| 所有 `(H_i, M_j)` 被视为绝对负样本 | 仅 active fixed-unit edge 做相对 alignment | channel collision、gray/null 会被错误监督 |
| V4.1 ranking 只把另一支推远 | response 回归 RT `z_v/y_v` 与 delta | 模型可以任意方向推开，无法声称预测了反事实变化 |
| V5 null target 与严格零 delta 冲突 | latent/physical dead-zone | 小于阈值但非零的真实变化收到互相矛盾的梯度 |
| alignment 与 response 可能是两个外挂 head | score 直接来自同一 predictor 的 zero-action error | “共享 backbone”停留在结构图上，机械拼接质疑无法回答 |
| latent physical loss 受 frozen readout 误差牵制 | predictor 独立输出 physical patch，readout 只审计 | `D(z_v)≠y_v` 时 latent 与 physical target 互相冲突 |
| full 只与 endpoint 比 | 严格四臂、Pareto 非劣、交互效应 | 无法知道提升来自哪一支，也无法证明联合有价值 |
| full 胜单臂就称协同 | 增加 `Δ_int` 与 resource-matched 独立拼接 | 加法效果会被误写成 synergy，容易被审稿人击穿 |
| CGS 被解释为全局地图真伪 | active paired support、null 单列 | AUROC 被过度解释为任意位置上的物理可能性 |
| `q_comp` 与定位 uncertainty 混用 | relative `q_comp` 与 `p_fail` 双校准 | “会判配对”被偷换成“知道定位会失败” |
| path-incidence 直接贴到定位样本 | 只聚合当前 state 的 incident edges；自然图用冻结 direct-edit set | 平均无关边或事后挑最大 effect 会制造机制曲线 |
| native head 自己考自己的任务 | 四臂统一 compatibility/response probes | 无法证明信息留在最终下游表征 |
| active/null loss 用全局样本均值 | route 内先做等权 scene-bank macro | route prevalence 会暗中改变 loss 剂量，城市间不可比 |
| paired worlds 复制同一观测噪声 | 只共享 `ξ_phys`，两侧 `η` 独立；clean RT 为主 | 模型可预测被人工共享的噪声，response 指标虚高 |
| source pilot/validation/calibration 边界含混 | 七块互斥 source 权限账本 | teacher、probe、calibrator 与阈值可能循环泄漏 |
| `k` 未说明位置还是 example | k 个 unique positions、每点一条 observation、support/query 整组隔离 | `k=8` 可膨胀为 `8K`，support 还会直接进入 test |
| 风险校准器与 proposal 未锁死 | map-side proposal、单调 logistic、support detector、k=0 主风险 | 使用 RT/route 挑 proposal 或微调后复用 calibrator 会产生伪校准 |
| 独立拼接使用冻结投影 | 预声明可训练 bottleneck 并计入参数/FLOPs，另报不降维 2× control | 随机投影可能主动损失信息，使 mechanical baseline 不公平 |

最终最重要的一句话固定为：

> **Alignment identifies the better-explaining side of a verified intervention edge; response supervision identifies its displacement. CSI-PAIRS trains both through the same zero-action/intervention predictor and retains only their shared state encoder for downstream localization.**

这句话保住了 V4.1 的错图、CGS、compatibility、风险校准和跨城定位主叙事，同时让 V5 的 scene-level bank 与 RT target-response 成为方法闭环中不可替代的一半。
