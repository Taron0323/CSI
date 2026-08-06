# CSI-PAIRS V6 论文-框架-项目-代码一一对应审查提示词

下面代码块可直接交给具备整个工作区读取权限的代码审查模型。它针对当前
`main@874e82c` 的 `formal_v2` V2.1 实现编写，不沿用旧版 V1.26、早期 V2.0，
也不沿用 V2.1 首次发布后已经修复的缺口假设。

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

【历史传输包，只用于追溯，禁止替当前实现补缺】
/root/autodl-tmp/CSI/CSI-PAIRS-anonymous-supplement-v1.26.zip

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
8. “代码彻底完成”的判定必须同时满足：算法真实存在、标准 CLI 可达、输入权限正确、正式剂量
   配置存在、产物绑定 checkpoint/config/data、统计量与 V6 同义、gate 真实消费该结果、至少有
   语义/变异/集成测试。缺任一项均不得写 feature complete。
9. 审查当前工作树，不以本提示词中的初读假设代替证据。先记录 HEAD、dirty state、Python/
   PyTorch/CUDA/外部环境；若 HEAD 已变化，重新从调用链生成疑点，不机械复述本提示词。
10. 不得抽样阅读 first-party 实现：逐个覆盖 formal_v2 下的 Python、正式 config、shell runner、
    DATA_CONTRACT/README、paper_v2 和 artifacts 合同。vendor 代码只需审查被 adapter 实际调用的
    边界；基线 fidelity 必须直接对照 waibu 中的论文/PDF、官方 snapshot 和适配代码，不能只引用
    WAIBU_INTEGRATION.md 的自述。不得找到若干 P0 后提前停止，所有矩阵必须填完。

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

G. 方法对比、消融与负对照的代码完整性
- 建立“实验名 -> V6 优先级(P0/P1) -> 训练实现 -> 正式配置/剂量 -> checkpoint -> 评测 -> 统计 ->
  gate/表格 -> 测试”的完整矩阵。禁止把一个能 forward/backward 的小模型当成完整比较实验。
- P0 内部比较必须包括 Endpoint/Alignment-only/Response-only/Full 严格四臂，以及 copy、
  no-action、geometry-matched action-swap、without-source-map、edit/map-only、CSI-only、oracle-x、
  shuffled-pair、retention/F-only 审计。
- Alignment/CGS 捷径对照必须逐项核对 constant、CSI-only、map-only、scene-ID-only、edit-status
  XOR、variant-ID matcher；不能拿 Response 的 without-map/edit-only probe 代替 Alignment 捷径审计。
- 计算与机械拼接对照必须包括 equal-FLOP Alignment、equal-FLOP Response、parameter-matched
  concat、FLOP-matched concat 和 2x generous concat。2x generous 是报告上界，核对 V6 是否要求
  Full 必须胜它才能过 C7，不能擅自收紧或放松 gate。
- 外部六条件至少两个真正 map-conditioned 模型；逐个核实 correct/paired-active/paired-null/
  wrong-city/geometry-destroyed/empty 实际收到不同且正确的地图张量，而不是只验证六个 condition
  字符串。核实 Wi-GATr、WiSER、SigMap、RFIR 的实现标签、原论文信息预算、训练目标与适配差异。
- 表征/定位比较逐个核实 CSI-MAE、CSI-CLIP、CSI-CLIP++、ContraWiMAE、WWM-inspired：不是只看
  类名和配置，要核对原论文关键结构、预处理、loss、优化剂量、seed、选模、统一位置头、k-shot
  draws、目标 query 隔离、资源量与统计不确定性；无法忠实实现时必须降级命名。
- 逐项盘点 V6 明确列出的 P1/附录实验：旧版 per-position world-bank 泄漏对照、all-non-diagonal
  ranking、单独训练的 full-H no-x、不同 tokenizer、convex-mixture/梯度匹配、两项 stop-gradient、
  I(x)、LoS/NLoS、自然图域偏移、第二引擎/真实干预。P1 缺失应准确标为计划项，不得伪装成 P0
  bug；但 README/paper 若声称“完整实现”覆盖它们，则报告文档冲突。
- 检查消融是否改变了不该改变的数据、模型容量、源标签、目标信息、训练步数或选模次数；每个
  对照必须共享可配对的独立 unit/cell，输出可直接进入预注册 estimand，而不是不可比的总体均值。

三、基于当前代码初读得到的定向验证假设

以下只是待证伪假设，不是预设结论。逐项用调用链、行号、最小复现或反证回答：

1. `frozen_mask_query_bank` 把 75%/50% 写死，而 config validator 对 teacher mask 只限制范围，
   `model.mask_fraction` 也可能没有控制实际 mask。检查修改配置后运行语义是否静默不变，以及
   正式冻结值是否有精确校验。
2. `_make_plan` 已构造多动作 response bundle，但同一 bundle 中各 target 的 mask index 被分别
   随机抽取；同一 unit 在 target/all、active-delta、null 项中也可能再次抽不同 mask。验证这是否
   违反 V6 要求的同一 H/map/c/m/q/增强，仅改变 action 与 target。
3. 四臂当前似乎都计算完整 Endpoint+Alignment+Response 分支，再用 0 factor 关闭梯度。这会令
   raw forward/FLOPs 人为相等，与 V6“分支带来原始计算差异，再做 equal-FLOP 控制”的 estimand
   可能冲突；同时核实复用第一臂 FLOP 数是否仍算各臂实测。
4. `formal_external.py` 的 C1 gate 看起来只要求 Wi-GATr 与 WiSER 成功输出六条件，并未检验两者
   是否真的呈现 C1 所需的 active 不敏感/null 安全现象、paired cluster CI 或 practical effect。
   构造六条件数值完全相同的合法结果，测试 C1 是否仍会错误 SUPPORTED。
5. 外部六条件 row 绑定 unit/context，但未明显绑定每个 condition 实际使用的 map/action digest。
   检查 adapter 把同一张 map 用六次是否仍可通过 outer gate。
6. Compatibility 主路径构造了对称四元组，但未见 constant/CSI-only/map-only/scene-ID-only/
   edit-status-XOR/variant-ID matcher 的完整结果进入 G3/C3/C4；`shortcut_baselines_passed` 可能只由
   shuffled-pair 外部 adapter 自报一个布尔值。
7. C3 与 C5 都由同一个 G3 总布尔量晋级。验证某一 claim 的专属证据缺失、但另一分支很强时，
   是否可能一起晋级；再逐项核对 C4/C6/C8-C10 的 dependency 是否覆盖 V6 第 14 节全部证据。
8. `predict_components()['u_only']` 似乎复用 joint calibrator 的 intercept/beta_u，而非独立拟合、
   独立选择 L2 的 u-only 风险基线；`d_only` 同理。检查 G6 的 joint-vs-u-only AURC 是否公平。
9. G6 的 AURC 优越判断和 90/75/50 单调性主要是点估计；核对“所有预登记点胜 random/u-only”
   是否需要 base-map-cluster 配对区间/多重控制，以及当前 reliability CI 是否真覆盖每个要求。
10. risk-feature adapter 能提交数值和 proposal-contract JSON，但 outer code 未明显重放 proposal、
    复算 d_used/u_g/failure，也未绑定 adapter source/manifest hash。检查伪造但 schema 合法的 archive
    是否可以过 G6。
11. resource-control adapter 虽绑定 checkpoint/log/profiler，但 outer code 未明显验证 checkpoint
    架构真是两独立 encoder、训练 loss 真是指定单分支/concat，也可能接受自报 FLOPs。做语义
    substitution test，而不只做缺字段测试。
12. G4 子门 7 当前似乎把 `generous_2x_concat` 也纳入“Full 必须显著胜过”的 all()；V6 C7 只明确
    要求胜 parameter-matched 与 FLOP-matched，而 2x 是宽松上界报告。核对这是错误收紧还是有依据。
13. G4 的两项 Full-vs-single 非劣和两项 Full-vs-single J 优越区间未明显做 Holm 或同步 bootstrap；
    核对 V6 第 12.4 节同层多重比较要求。
14. `formal_evaluation.py` 已有 full-channel NMSE、latent、direction cosine、magnitude 与多种负对照，
    但未见 SGCS、TransitionSkill、path-loss/delay-spread/angular-spread 变化误差与方向正确率。区分
    P0 必需、次要必报和 P1，不能用近似指标顶替同名指标。
15. G7 的 path provenance 子门似乎无条件 PASS；未见 Q% path truncation convergence 的可执行
    资格检查。`A_path,loc` 被写出但似乎没有进入机制统计/gate，需和 V6 第 9、14、15 节逐条对照。
16. representation-baseline stage 每个方法似乎只训练一个 seed，PASS 只表示五个模型执行完成，
    且该 stage 不在 claim assembly 依赖图中。检查它能否支撑论文方法比较表、方差/CI和“完整链”。
17. WiSER/SigMap/RFIR 是不同强度的 controlled implementation。逐项对照本地论文资源验证关键
    架构与训练语义，尤其不能因有真实梯度和大剂量 config 就自动视为论文级基线。
18. `paper_v2/main.tex` 的正文公式主要只写 physical Endpoint/Response，弱化或省略冻结 V6 的
    latent+physical 双目标；实验问题只列四项，RQ5 风险链和若干 C/G gate 也可能不完整。做全文
    双向公式/术语/claim 对照，而非只检查摘要。
19. `all` 现已调用风险、表征基线、外部基线、资源控制、scene-ID、G8、G0、RT calibration、
    shuffled/retention 和 claims；但仓库没有正式 dataset/外部输入，dry-run 脚本只走 verify+qualify，
    当前 85 个测试也没有执行完整 `all`。检查“complete evidence chain/READY_FOR_DATA”措辞边界。
20. `CODEBASE_MAP.md` 仍可能写 61 个测试并引用不存在的解压 archive，目录/zip/README 又混用
    V2.0/V2.1/V2.2 schema 名。检查所有启动命令、文件计数、版本标签与当前行为的漂移。

不要默认以上假设成立；被代码或实验推翻时明确写“已推翻”并给证据。

四、最低动态验证

先运行并原样记录结论（不要把 PASS 外推为科学正确）：

cd /root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server
sha256sum --check SHA256SUMS
python3 -m py_compile formal_v2/*.py formal_v2/tests/test_formal_v2.py
python3 -m unittest discover -s formal_v2/tests -v
python3 -m formal_v2.formal_cli --help

再在临时目录运行 `formal_v2/scripts/run_formal_v2_dry_run.sh`，明确它实际只覆盖到哪一阶段；
在临时副本编译 `paper_v2/main.tex` 并报告引用、公式、占位符和构建问题。不要污染当前工作树。

当前 `main@874e82c` 的已知基线是 SHA 登记文件全通过、py_compile 通过、85 tests 通过；审查者
必须自己重跑。若结果不同，记录当前 HEAD/环境和差异，不得沿用 85 这个数字。

随后在临时目录做最小定向测试，至少覆盖：
- 替换 target/support/external 数据是否影响 teacher、route normalization、资格门或 checkpoint；
- bs_pose 改变时 F 输出是否改变，M/x/action 改变时 teacher target 是否严格不变；
- native compatibility 的 query 是否被 mask，训练 B_align 与评测 score 是否同定义；
- target support_pool 是否进入 CGS/response/risk/path 分母；
- 同一 base_map_cluster 拆成多个 bank 是否改变 J、CI 和独立 bank 计数；
- 关闭 A/R 时真实 forward、FLOPs、梯度和参数更新；四臂 batch/mask/query 是否逐项一致；
- 同一个 response branch bundle 的所有 target、target/delta/null 子项是否逐字节复用 mask/query；
- G3/G4/G6/G7 和 claim assembly 的 adversarial artifact：只满足弱条件时能否错误 PASS；
- C1 六条件结果全相等、六次复用同一地图时是否会错误 PASS；
- risk fit/selection role、proposal 重放、独立 d-only/u-only、common support、random baseline、
  coverage monotonicity与 cluster-level inference；
- resource-control 用错误架构 checkpoint/伪造 profiler，representation baseline 只跑单 seed时，
  gate 和 claim 是否仍会把“执行完成”写成“比较充分”；
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
4. Comparison & Ablation Completeness Matrix：所有 P0/P1 方法、基线、负对照和消融的训练代码、
   正式剂量、seed、checkpoint、统一评测、统计、gate、可达性和准确命名；明确缺哪些代码。
5. Claim Safety Table：C1-C13 的完整依赖、当前 supported/software-only/blocked/invalid 状态，
   以及当前允许使用的最强论文措辞。
6. Gate Audit：G0-G8 及 C7 七子门、C9 四子门逐项说明真实 PASS 条件是否充分。
7. Test Coverage Gaps：现有测试实际覆盖与未覆盖内容，区分 schema、unit semantic、integration、
   statistical mutation 和 end-to-end evidence test。
8. Prioritized Remediation Plan：按依赖顺序先修改变实验定义/泄漏/统计推断的问题，再补评测、
   adapter 与工程质量；不要直接修改代码。
9. Final Verdict：分别给 Package integrity、Software execution、V6 protocol fidelity、
   Scientific claim readiness；禁止用一个总 PASS/FAIL 混写。

即使某类没有发现问题，也写“未发现”并说明剩余测试风险。所有结论必须能由文件、行号、
测试或命令输出复核，拒绝“看起来合理”“README 说已实现”和只按同名函数判断。
```
