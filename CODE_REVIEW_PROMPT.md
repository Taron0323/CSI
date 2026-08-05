# CSI-PAIRS V6 论文-框架-项目-代码一一对应审查提示词

下面代码块可直接交给具备整个工作区读取权限的代码审查模型。它针对当前
`formal_v2` V2.1 实现编写，不沿用旧版 V1.26 或早期 V2.0 的缺口假设。

```text
你是一名严格的机器学习系统、实验方法学、统计学和科研软件审稿人。请对
CSI-PAIRS 做一次“冻结论文规范 -> 项目框架 -> 可达代码 -> 测试 -> 证据产物”的
双向一一对应审计。目标不是评价代码风格，而是确定当前项目是否逐条、同语义地实现
冻结 V6 研究方案，以及当前自动 gate 是否足以支撑它声称绑定的论文结论。

工作区：/root/autodl-tmp/CSI

【唯一最高规范】
/root/autodl-tmp/CSI/Idea1-CSI-PAIRS-冻结版-零基础阅读稿-v6_VSCode兼容版.md

【当前可执行实现，默认审查范围】
/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/formal_v2

【项目框架和论文草稿，必须做一致性复核】
/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/README.md
/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/CSI-PAIRS-startup-package-v2.0.md
/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/formal_v2/README.md
/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/formal_v2/DATA_CONTRACT.md
/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/formal_v2/configs/formal_v2.json
/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/paper_v2/main.tex
/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/artifacts/v2_0_claim_evidence_contract.json
/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/SHA256SUMS

【历史代码，只用于追溯，禁止替当前实现补缺】
/root/autodl-tmp/CSI/archive/CSI-PAIRS-anonymous-supplement-v1.26/experiments

权威顺序固定为：冻结 V6 方案 > 当前可达代码的实际行为 > 配置与测试 > README、
启动包、paper_v2 和 claim contract 的自述。V1 中存在但 V2.1 未调用的功能仍判当前实现
缺失。模块、schema、注释、测试名或文档写着 V6/implemented/PASS，不是实现正确的证据。

不要使用 GSD。不要修改仓库。允许只读检查，并可在临时目录运行测试、CLI dry run、
最小复现和变异测试。fixture 永远只能证明软件路径可执行，不能支持科学 claim。

一、强制审查方法

1. 完整阅读 V6，不要只读目录或摘要。把所有“必须、只能、禁止、至少、主指标、唯一、
   冻结、等权、非劣、等效、资格门”拆成原子 Requirement ID。至少覆盖 0-15 节、
   C1-C13、C7 七道子门、C9 风险门、G0-G8。
2. 枚举 formal_cli.py 的所有子命令，分别追踪到数据读取、模型、loss、评测、统计、gate、
   claim assembly 和写出的 artifact。区分：
   - 内生实现：仓库直接计算结果；
   - adapter contract：仓库只运行外部命令并验证结果格式；
   - schema-only：只有字段/manifest，没有算法实现；
   - unreachable：模块存在但标准工作流不可达。
3. 对每条原子要求给且只给一种状态：
   - EXACT：定义、输入权限、采样、量纲、聚合、统计和输出均与 V6 相同；
   - PARTIAL/PROXY：有近似实现或 adapter 合同，但不足以承载原结论；
   - MISSING：当前代码或可执行工作流不存在；
   - CONFLICT：行为改变论文 estimand、信息预算、训练剂量、数据权限或结论语义。
4. EXACT 必须同时给出 V6 章节/公式、代码文件+符号+精确行号、可达入口、测试和运行证据。
   只有 schema test、函数存在或 README 自述时，最多是 PARTIAL，不得判完全验证。
5. 做两遍审计：先 paper-to-code 查漏项；再 code-to-paper 检查每个输入、配置项、损失、
   阈值、输出和自动 PASS 是否有 V6 依据。任何新增信息、删减门槛或替换统计量都要报告。
6. 明确分开四个层次：
   - package integrity（文件哈希是否一致）；
   - software execution（能否运行、测试是否通过）；
   - protocol fidelity（是否实现 V6 的同一个实验）；
   - scientific evidence（是否已有非 fixture、独立数据支持 claim）。
7. 不允许用“fail-closed”掩盖实现缺失。fail-closed 是正确的安全属性，但 schema/adapter
   存在不等于 P0 实验已经实现；同样，不得把缺数据误报成算法 bug。

二、必须逐项核对的论文-代码表面

A. 数据、world bank 与权限账本
- 七个互斥 source role 是否在 loader、所有调用者和产物中真正执行各自权限；target、
  external_validation 是否不会参与 teacher、阈值、归一化、选模和校准。
- scene tile/world bank/base_map_cluster 谁是最高 split 与统计单位。重复基础地图能否被当成
  多个 bank 重复计权；城市、bank 和 cluster 的“独立”计数是否真实。
- 完整超立方、Hamming-1 双向边、随机 bit-to-primitive、随机 natural anchor、canonical
  rerender、共同自由位置、节点均衡和边对称是否被验证，而非只由 metadata 声明。
- 每项编辑是否对所有固定位置完整交叉生成；active/gray/null 是否在采样后判定；d=2 时的
  geometry-matched wrong-action coverage 和 active branching coverage 是否存在。
- clean CSI、独立 repeat noise、pair-consistent phase gauge、radio/BS pose、材质类别、路径 ID、
  引擎/资产/许可/哈希是否可独立再生验证。
- target support/query 是否按位置整组隔离；support 的 sibling worlds、边、mask/query 是否从
  localization、CGS、response、risk、path 和 interaction 的全部分母删除。
- k 是否是每个 target city 的唯一位置数，每位置一条观测；k=8/32/128 draw 是否嵌套且四臂共享。

B. Stage 0 teacher、route 与物理量纲
- teacher 是否真是 CSI-only、75% patch mask、天线×子载波二维 patch/位置编码、不对称 MAE
  encoder/decoder；训练后 eval+freeze，target 对 M/x/action 替换 bitwise 不变。
- F 的 CSI 初始化是否真共享 teacher 的 CSI encoder，而不只是拷贝输入线性层或位置参数。
- readout 是否只审计 latent，不进入物理 loss；teacher reconstruction/readout 是否在独立的
  source-method-selection 上资格，而非复用训练误差。
- Alignment 是否用完整复数 CSI + delay-angle power，Response 是否逐 patch；两者是否各自使用
  与 dead-zone 同量纲的独立阈值和 practical-effect floor。
- route 是否方向不变、绝不进入模型输入；route coverage 是否按 raw bank/edge/position/patch
  报告；空条件是否 fail，而不是返回 0。

C. F/P、动作和信息隔离
- F 是否实际读取 V_m(H_u)、多通道 G(M_u)、完整 c（特别是 bs_pose/config）和 m；P 是否读取
  同一 state、zero/signed action、q，并分别输出 latent 与 physical patch。
- 地图中的 occupancy/height/material/BS 信息、固定范围/token/padding 是否符合 V6；是否存在
  receiver-centered crop、真实 x、ID、route、path/effect 或 target-derived 输入。
- signed edit 是否区分 add/remove、height +/-、material from/to；材质不得做普通数值差。
- branch bundle 是否复用同一 H/source map/c/m/q/增强并覆盖同一 source 的至少两个可区分目标；
  Alignment/Response/active/null 分层采样是否仍保持论文要求的联合结构。
- target H_v 是否只在监督侧；下游定位是否只读 F，完全不调用 P/action/teacher/readout/route。
- 检查 batch 污染、BN/attention 泄漏、target bitwise test、输入 allowlist 和 checkpoint hash 绑定。

D. 三类 loss 与四臂剂量
- L_B：同世界正确图、zero action、latent+physical、bank-macro、自然分支四臂等量。
- L_A：先对完整冻结 B_align 求平均 score，再做 active 双向 quartet hinge；effect-aware margin
  phi 与固定-margin 主结果是否都实现；B_audit_hold 是否独立；gray=0；null kappa_s 是否来自
  endpoint pilot + canonical no-op；active/null 分别按 eligible-bank macro 聚合。
- L_R：所有 directed edge 回归 latent+physical target；active 额外 delta_z+delta_y；null 使用
  两空间 dead-zone；各子项是否有论文规定的独立权重并做 route-stratified bank macro。
- c_A/c_R 是否来自同一共享初始化和冻结短 pilot 序列的均值，只算一次；pilot checkpoint 不复用。
- 四臂是否仅改变 A/R 开关，共享 teacher、初始化、数据、branch、mask、batch、增强、步数、
  checkpoint、位置头和目标信息预算；lambda_A/lambda_R 在单分支与 full 中相同。
- 实际 forward/FLOPs/梯度/耗时是否测量而非硬编码；关闭 loss 后仍计算整条分支时，应准确说明
  它改变了论文“原始计算差异”和 equal-FLOP 控制的含义。

E. 评测、定位与统计
- native alignment score 是否严格复用训练定义的 masked B_align，并用独立 B_audit_hold；不能在
  评测时改成 full-visible CSI 或另一种 error。
- compatibility probe 是否 frozen F、linear+2-layer MLP、统一预算；active CGS AUROC、四个 effect
  档、gray 分布、null 过判/等效、native-probe 相关性和捷径基线是否齐全。
- response probe 是否读取同一 masked F state+action+q；native mask-cover 是否 target-free 覆盖全
  CSI，以 alignment-active transition 的 scene-macro full-channel physical NMSE 为唯一主指标；
  SGCS、方向、幅度、TransitionSkill、gray/null 与 copy/no-action/action-swap/w-o-map/edit-only/
  CSI-only/oracle-x 是否齐全。
- strict k=0 是否无 target 统计、无标签 CSI、reference/fingerprint 库、梯度和目标超参；坐标与
  BS pose 是否同一右手米制系统；位置头是否异方差 Gaussian NLL + Huber 且四臂同预算。
- J_a 是否严格等权 city × {0,8} × base-map-cluster/bank × seed × positive-k draw；重复 cluster
  不得被当成独立 bank。多层 paired bootstrap、bank-only CI、leave-one seed/draw 是否正确。
- 优越/非劣/等效是否基于预注册 CI 或检验，而不是简单比较总体均值；Holm/同步区间是否真正
  在 gate 调用，而不只是定义了函数和单元测试。

F. 风险、路径、外部对照和 claim gate
- q_comp：active paired only、候选顺序随机、无截距温度、swap complement、source-only fit，
  q_comp 与 p_fail 的指标和适用范围分开。
- p_fail：proposal 只读 supplied map+公开 c；d_used、u_g、median/MAD、受符号约束 L2 logistic、
  fit/selection 分离；support 阈值是否按 V6 从 calibration-selection 冻结；四臂 common support。
- G6 必须实际检查 C9 四项风险门：校准及置信区间、共同范围和 out-of-support 非劣、AURC
  胜 random 与 u-only、90/75/50% 覆盖误差单调；同时报告 d-only/u-only/joint。不能只检查
  common coverage 与 beta 符号就 PASS。
- A_path 是否按 persistent path/surface 正确算，epsilon 来自 no-op；A_path,loc 只聚合当前状态
  相邻编辑；zero/low/medium/high 的匹配是否控制 edit magnitude、BS/UE distance、LoS 等预注册
  协变量；零路径等效和 bank-level 推断是否落实。
- 至少两个 map-conditioned 外部模型是否实际跑六条件；所有论文基线的 executed/unavailable/
  controlled 命名是否准确。local ridge diagnostic 不得支撑 C1。
- equal-FLOP 两单分支、parameter-matched concat、FLOP-matched concat、2x generous concat 是否
  有真实训练实现、checkpoint、资源测量和同一 J estimand，不能只接收自报 CSV/JSON 就视为证据。
- C1-C13 的依赖必须覆盖论文第 14 节列出的全部证据；G0-G8 的 PASS 条件必须与第 15 节一致。
  检查一个较弱 gate 是否会让多个较强 claim 自动 SUPPORTED。
- `all` 实际执行哪些阶段，跳过哪些独立 adapter/gate；“模块可单独运行”和“完整工作流已执行”
  必须分开。缺失/NOT_ASSESSED 不能晋级，但 fail-closed 也不能被写成 feature complete。

三、基于当前代码初读得到的定向验证假设

以下只是待证伪假设，不是预设结论。逐项用调用链、行号、最小复现或反证回答：

1. formal_teacher.py 是单层 Transformer + 线性 decoder 和一维 learned position，patchify 只是
   展平后连续切块，可能不等价于 V6 的二维 CSI-MAE patch 与不对称 MAE。
2. initialize_csi_from_teacher 似乎只复制 patch embedding/position，没有复制 teacher encoder；
   “四臂共享 CSI encoder 初始化”可能只有部分成立。
3. bs_pose 在 dataset 中被验证，但 _identity_batch/_natural_representations 似乎只把 radio_config
   送入 F，需确认完整 c 是否实际进入模型。
4. _make_plan 分别抽 endpoint、alignment active/null、response all/active/null，未见显式 branch
   bundle 或同源多动作覆盖；需检查是否改变 V6 联合采样语义。
5. L_A 似乎只有固定 active_margin，未见 effect-aware phi 或独立 B_audit_hold；L_R 似乎把 latent
   与 physical delta/null 固定等权，缺少论文中的 lambda_Delta_y/lambda_0y。
6. 四臂均无条件执行 alignment/response 前向后再把 factor 乘 0，且 forward_calls_per_step=12
   是常量；需核实真实调用数、FLOPs 和 equal-FLOP 叙事。
7. _compatibility_dataset 使用全 false mask 和 retained_representation，并对 full-visible CSI 计算
   native energy，可能与训练时 masked B_align score 冲突，也可能让 query 答案直接可见。
8. target evaluation_scenes 中的 compatibility/response 循环遍历全部 position，可能把
   support_pool 位置放入 CGS/response，违反 support sibling 从所有最终指标删除的规则。
9. response probe 似乎基于 full-H retained representation，而非相同 masked source state；需要
   检查其信息预算和论文 5.2 的定义。
10. G3 只比较 alignment CGS 与 response native NMSE 的均值，未明显检查 response 胜 copy、
    action-swap、方向/幅度、latent/readout 和统计非劣；C3/C5 又只依赖 G3，可能过早晋级。
11. G4 的原生非劣与 G5 似乎使用点估计；holm_adjust 已定义但未见 gate 调用。需核对论文要求
    的配对 CI、最小实际效应与多重比较控制。
12. 统计函数主要以 bank_id 聚合，而 dataset 允许同一 base_map_cluster 下有多个 bank；这可能
    把重复基础地图当独立证据，并让 minimum bank count 高估独立样本数。
13. risk support threshold 似乎从 calibration-fit 距离分位数得到，而论文要求在
    source-calibration-selection 冻结；risk feature archive 也需验证是否绑定具体 checkpoint、
    probe、proposal 和真实 dataset unit，而不只是 dataset/config hash。
14. G6 当前 PASS 条件看起来只检查 common-support coverage 与 beta 符号，未执行 C9 的完整
    校准/AURC/coverage 闭环；risk_metrics 也未见 d-only、u-only、random-rejection 比较和 CI。
15. G7 的 `_exact_path_match` 似乎按排序后截取每档相同数量，balance 只检查 city/bit 类别，
    可能不等价于论文要求的距离、编辑幅度、LoS 等匹配。
16. claim dependency 表可能让 C3/C5/C8/C9 由过弱的单一 G gate 自动 SUPPORTED；必须逐条把
    第 14 节“至少需要哪些证据”与实际依赖图对照。
17. `all` 只运行 verify/qualify/wrong-map/factorial/evaluation/path/claims，似乎不运行 risk、
    resource controls、external baselines、scene-ID、RT calibration、G0/G8、shuffled/retention；
    检查 README 的“完整链”措辞与实际 orchestration 是否一致。
18. 目录和 CLI 仍混用 V2.0/V2.1 命名。检查 README、schema、paper_v2、bundle 文件名与当前
    行为是否存在版本漂移或会导致运行错包。

不要默认以上假设成立；被代码或实验推翻时明确写“已推翻”并给证据。

四、最低动态验证

先运行并原样记录结论（不要把 PASS 外推为科学正确）：

cd /root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server
sha256sum --check SHA256SUMS
python3 -m py_compile formal_v2/*.py formal_v2/tests/test_formal_v2.py
python3 -m unittest discover -s formal_v2/tests -v
python3 -m formal_v2.formal_cli --help

随后在临时目录做最小定向测试，至少覆盖：
- 替换 target/support/external 数据是否影响 teacher、route normalization、资格门或 checkpoint；
- bs_pose 改变时 F 输出是否改变，M/x/action 改变时 teacher target 是否严格不变；
- native compatibility 的 query 是否被 mask，训练 B_align 与评测 score 是否同定义；
- target support_pool 是否进入 CGS/response/risk/path 分母；
- 同一 base_map_cluster 拆成多个 bank 是否改变 J、CI 和独立 bank 计数；
- 关闭 A/R 时真实 forward、FLOPs、梯度和参数更新；四臂 batch/mask/query 是否逐项一致；
- G3/G4/G6/G7 和 claim assembly 的 adversarial artifact：只满足弱条件时能否错误 PASS；
- risk fit/selection role、common support、u-only/random baseline、coverage monotonicity；
- fixture/NOT_ASSESSED/哈希不匹配是否在所有下游层永久 fail-closed。

现有测试通过只说明被覆盖的软件属性。请列出没有端到端测试的关键公式和 gate，不得按测试名
推断测试体已经验证整条语义。

五、输出格式

先输出 Findings，按 P0/P1/P2 排序，不要先写总结。每条 finding 必须包含：
- 严重度和短标题；
- V6 章节/公式/claim/gate；
- 当前文件、符号、精确行号和可达入口；
- 实际可观察行为及最小复现；
- EXACT/PARTIAL/MISSING/CONFLICT；
- 对 estimand、泄漏、公平性、统计或 claim 的影响；
- 最小修复方向和应新增的具体测试。

随后依次给出：
1. Paper-to-Code Traceability Matrix：Requirement ID | V6 source | Expected behavior |
   Runtime path | Code evidence | Test/evidence | Status | Gap/impact | Required change。
2. Code-to-Paper Reverse Matrix：所有没有论文依据、改变信息预算或更改统计量的代码行为。
3. Reachability & Orchestration Matrix：每个 CLI stage、输入、输出、上游 gate、是否被 all 调用、
   internal/adapter/schema-only 状态。
4. Claim Safety Table：C1-C13 的完整依赖、当前 supported/software-only/blocked/invalid 状态，
   以及当前允许使用的最强论文措辞。
5. Gate Audit：G0-G8 及 C7 七子门、C9 四子门逐项说明真实 PASS 条件是否充分。
6. Test Coverage Gaps：现有测试实际覆盖与未覆盖内容，区分 schema、unit semantic、integration、
   statistical mutation 和 end-to-end evidence test。
7. Prioritized Remediation Plan：按依赖顺序先修改变实验定义/泄漏/统计推断的问题，再补评测、
   adapter 与工程质量；不要直接修改代码。
8. Final Verdict：分别给 Package integrity、Software execution、V6 protocol fidelity、
   Scientific claim readiness；禁止用一个总 PASS/FAIL 混写。

即使某类没有发现问题，也写“未发现”并说明剩余测试风险。所有结论必须能由文件、行号、
测试或命令输出复核，拒绝“看起来合理”“README 说已实现”和只按同名函数判断。
```
