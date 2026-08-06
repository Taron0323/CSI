# CSI-PAIRS 论文启动包 V2.1（V6 协议修订）

> 兼容性说明：文件名保留 `v2.0` 是为了不破坏冻结审计路径；本文、运行时 schema 和打包根均为 V2.1。

> 日期：2026-08-06（Asia/Shanghai）
> 版本性质：正式实验执行版，不是新增科学结果  
> 当前状态：`CODE_IMPLEMENTED_NOT_EXPERIMENTALLY_VERIFIED`  
> 当前科学结论：继续继承 V1.1/V1.26 的 `POST_AUDIT_NO_GO` 与 `scientific_use=FORBIDDEN`，直到非 fixture 数据逐门通过  
> 工程基线：V1.26；科学设计约束：V1.1 的 No-X/null/shortcut 失败与 Idea V6

## 0. 一页结论

V2.1 按冻结 V6 实现数据再生成门、资格门、patch F/P、严格四臂、两城市定位、统一评测、风险、路径、资源控制和证据汇编代码。当前没有运行正式实验，代码存在不等于 gate 通过。

本版解决了 V1.x 最重要的五个阻塞：

1. 新增 qualified RT/实测数据入口，强制引擎版本、配置哈希、许可、材质、坐标、相位规范、clean target 和重复测量。
2. 每个 bank 随机化 natural anchor 与 bit-to-primitive mapping；No-X 仍读取真实 source map、radio、patch mask/query 和 typed signed edit，不再用零图代理。
3. 正式训练前先验收 repeat noise、physical/teacher 双空间 route、teacher reconstruction、oracle-x、No-X、action-swap、null safety 与 variant-ID。
4. Endpoint/Alignment/Response/Full 使用同一 PyTorch 架构、初始化、batch、mask、步数和完整前向合同；四臂参数量和前向分支一致。
5. 定位只读取共享 state；目标 support/query 按唯一 receiver position 隔离，最高独立统计单位为 base-map-cluster，并对 seed、draw、cluster 做配对汇总。

V2.1 的 dry run 只能证明软件执行。fixture 在元数据、gate 和报告中永久标记 `FORBIDDEN`，其任何数字都不得进入论文。

## 1. 本版交付物

| 交付 | 文件 | 状态 |
|---|---|---|
| 正式数据合同与独立再生成门 | `formal_v2/DATA_CONTRACT.md`、`formal_v2/formal_dataset.py`、`formal_v2/formal_data_verification.py` | 代码已实现；未运行正式 verifier |
| 冻结正式配置 | `formal_v2/configs/formal_v2.json` | 完成；读正式数据前再由负责人签字冻结 |
| 非科学小配置 | `formal_v2/configs/formal_v2_smoke.json`、`formal_v2/formal_fixture.py` | 完成；只测代码 |
| 六条件 wrong-map | `formal_v2/formal_wrong_map.py` | 代码已实现；必须复用资格门冻结 teacher；ridge 不冒充外部 baseline |
| Stage-0 与 Response 资格 | `formal_v2/formal_qualification.py`、`formal_v2/formal_teacher.py` | 代码已实现；未运行 |
| patch F/P 与严格四臂 | `formal_v2/formal_model.py`、`formal_v2/formal_factorial.py` | 代码已实现；未运行 |
| 两城市定位与统计 | `formal_v2/formal_factorial.py`、`formal_v2/formal_statistics.py` | 代码已实现；city-level k 和 V6 多层估计量 |
| CGS/Response/q_comp/p_fail/path | `formal_v2/formal_evaluation.py`、`formal_v2/formal_risk.py`、`formal_v2/formal_path.py` | 代码已实现；未运行 |
| 资源、scene-ID、外部模型控制 | `formal_v2/formal_controls.py`、`formal_v2/formal_scene_id.py`、`formal_v2/formal_external.py` | runner 已实现；scene-ID 按 base-map cluster 做 CI 并绑定实现/checkpoint；Wi-GATr 官方适配与 WiSER paper-spec controlled adapter 是两项 C1 合格身份，但均未跑正式训练 |
| 外部论文与 Sionna 设施 | `formal_v2/WAIBU_INTEGRATION.md`、`formal_v2/sionna_scene_export.py`、`formal_v2/sionna_facility.py` | 10 项资源哈希登记、表征/地图基线、formal world 到 PLY/XML 的 exporter 和 G8 adapter 已实现；G8 active/null 均按 cluster CI 判门；无正式结果 |
| 命令入口 | `formal_v2/formal_cli.py` | 完成；上游失败会阻断四臂 |
| V2 自包含工具 | `formal_v2/formal_io.py`、`formal_v2/formal_baselines.py` | 完成；不再导入冻结 V1 `experiments` 代码 |
| 依赖与脚本 | `formal_v2/requirements-lock.txt`、`formal_v2/scripts/setup_formal_v2.sh`、`formal_v2/scripts/run_formal_v2.sh` | 完成 |
| 服务器打包/自检 | `formal_v2/scripts/build_server_bundle.sh`、`formal_v2/scripts/verify_server_bundle.sh`、`README.md` | 完成 |
| V2 论文源稿 | `paper_v2/main.tex` | 完成；V1.26 论文未改动 |
| Claim-Evidence | `artifacts/v2_0_claim_evidence_contract.json` | 完成；所有科学 claim 仍 blocked |
| V2 测试 | `formal_v2/tests/test_formal_v2.py` | 完成 |
| 最终验证报告 | `artifacts/v2_0_verification.md` | 完成；汇总测试、dry run、PDF 和 V1 冻结锚点 |

## 2. 继承且不得删除的失败事实

- V1.1 scene 3 的 82/82、scene 4 的 84/84 No-X null units 超过 0.018 tolerance，两处均为 100%。
- `map_feature_hurts`、`variant_id_signal`、`oracle_x_not_helpful`、`beam_readout_insensitive_to_copy` 四个 warning 必须在 V2 输出继续出现；未评估不能写 PASS。
- 在新的非 fixture gate 通过前，禁止 `first`、`outperform`、`calibrated`、`label-efficient`、`synergy`、`method efficacy`、`localization improvement` 和 `real causal grounding`。
- V2 的 relative-edit 修复是新假设，不是既有失败已经被修好。只有 untouched selection banks 能决定它是否有效。

## 3. 正式 gate 顺序

| Gate | 输入 | 通过标准 | 失败退出 |
|---|---|---|---|
| G0 文献与资源 | 投稿前检索和资源记录 | 可核查、未过期、许可完整 | 删除首创性表述 |
| G1 RT/repeat/route | clean CSI 与独立 repeats | 每个 bank repeat threshold 通过，双空间 active/null 数量达标 | 修 RT、gauge 或资产；不能放宽 held-out 阈值 |
| G2 teacher 与 No-X | source-train teacher、method-selection | teacher/readout、No-X、null、shortcut 全通过 | 停止四臂 |
| G3 单分支 | 冻结 probe 与 target-free response | Alignment/Response 分别成立且 null 安全 | 删除失败分支结论 |
| G4 联合价值 | 四臂及五个资源/concat 控制 | 七个子门全部 PASS | 不写 synergy；NOT_ASSESSED 不是 PASS |
| G5 两城市 | target support/query，k=0/8 主检验 | 两城市不反向退化；median/P90 与 bank CI 同报 | 删除跨城/label-efficiency/improvement claim |
| G6 风险 | source calibration 与 target k=0 common support | q_comp/p_fail、符号、校准、AURC 全通过 | 删除 calibrated risk |
| G7 路径机制 | persistent paths 与 no-op retrace | 四档、平衡、趋势和零路径等效通过 | 删除机制解释 |
| G8 外部有效性 | 第二引擎或受控实测 banks | active 方向和 null 稳定性独立通过 | 只写 simulator-defined/consistent |

独立数据再生成门、G1 和 G2 是四臂硬前置。CLI 会认证 dataset/config/teacher 哈希；`--allow-nonscientific-fixture` 只允许软件链路，不会改变 `scientific_use=FORBIDDEN`。

## 4. 数据负责人现在要准备什么

1. 七个互斥 source role 都必须有独立 banks：encoder-train、method-selection、probe-train、probe-selection、calibration-fit、calibration-selection、final-unseen-bank。
2. 至少两个 target cities；每城建议至少 4 个独立 banks。每 bank 至少 128 个 support-pool positions，另有完全不重叠的 query positions。
3. 每个 bank 的完整 `2^d` canonical worlds、共同 receiver positions、双向 Hamming-1 edges、每 bank 独立 primitive permutation 与 natural anchor。
4. 至少 3 个独立 observation repeats；确定性 RT 另存 clean target。重复噪声不能在 paired worlds 间复制。
5. 引擎 name/version/config 文件及 SHA-256，地图/材质许可，BS/坐标定义，CSI 单位、real/imag 布局和 pair-consistent phase/gauge 规则。
6. 第二引擎或受控实测数据若可用，必须作为实际 `external_validation` banks 放入 archive；只有 metadata 声明会被拒绝。

数组和 metadata 的精确字段见 `formal_v2/DATA_CONTRACT.md`。

## 5. 两个实验怎样运行

### 实验一：六条件 wrong-map

内置 `controlled-relative-map-ridge-diagnostic` 只负责验证六条件、相同 CSI、相同 denominator 和配对评分链路：

1. correct；
2. paired active alternative；
3. paired null alternative；
4. wrong city；
5. geometry destroyed；
6. empty。

它会输出 `wrong_map/per_sample_results.csv` 与 `summary.csv`。正式 C1 仍要求把同一条件合同接到至少两个准确命名、许可明确的外部 map-conditioned models；内置 ridge 的结果不得写成领域现象。

### 实验二：Response 资格

source-encoder-train 只拟合 CSI-only masked teacher、冻结 readout、归一化和资格 probes；source-method-selection 决定：

- raw physical target 是否可学；
- oracle-x 是否胜 copy；
- No-X 是否逐 bank 胜 copy、no-action、fixed-checkpoint action-swap；
- null predicted delta 是否留在 0.018 dead zone；
- randomized variant ID 是否仍有异常信号；
- absolute source-map 是否再次伤害泛化。

输出在 `qualification/`。最重要的是 `gate.json`、`response_gate.csv`、`null_safety.csv` 和 `shortcut_audit.json`。

## 6. 四臂实现边界

`formal_v2/formal_model.py` 实现继承完整二维 CSI teacher encoder 的 F、多通道地图 encoder、radio+BS-pose token、cross-attention fusion、typed signed-edit encoder、query embedding，以及 latent/physical 双输出。下游定位只读取保留的 F state；teacher、predictor、edit encoder、route 和 readout 都不进入定位输入。

四臂复用同一 teacher、初始化、StepPlan、bank/edge/direction/mask/query 顺序和 checkpoint 规则，arm 只改变 loss factor。代码记录 forward、FLOPs、梯度范数和 wall time；资源差异必须由 equal-FLOP 与三类 concat 控制实际验证。

这是正式可执行 baseline architecture，不代表最终最优 backbone。若换成 CSI-MAE/Transformer，必须保持同输入 allowlist、四臂同结构、同 forward 预算和 checkpoint 规则，并重新跑全部测试。

## 7. 启动命令

### 7.1 建环境

```bash
formal_v2/scripts/setup_formal_v2.sh /unused/path/csi-pairs-v2-env
```

如本机 Python 的 CA 证书异常，先修复证书，不要把 `--trusted-host` 写入长期实验脚本。

### 7.2 先做代码检查（不运行实验）

```bash
python3 -m py_compile formal_v2/*.py formal_v2/tests/test_formal_v2.py
python3 -m unittest discover -s formal_v2/tests -v
```

这只证明静态导入和已覆盖语义测试通过，不证明资格、四臂或科学 gate。

### 7.3 检查正式数据

```bash
/unused/path/csi-pairs-v2-env/bin/python -m formal_v2.formal_cli inspect-data \
  --config formal_v2/configs/formal_v2.json \
  --dataset /path/to/csi_pairs_formal_v2_1_v6.npz \
  --output /unused/path/data-inspection
```

### 7.4 独立再生成后运行正式资格门

```bash
/unused/path/csi-pairs-v2-env/bin/python -m formal_v2.formal_cli verify-data \
  --config formal_v2/configs/formal_v2.json \
  --dataset /path/to/csi_pairs_formal_v2_1_v6.npz \
  --verifier-manifest /path/to/independent_rt_verifier.json \
  --output /unused/path/formal-run

/unused/path/csi-pairs-v2-env/bin/python -m formal_v2.formal_cli qualify \
  --config formal_v2/configs/formal_v2.json \
  --dataset /path/to/csi_pairs_formal_v2_1_v6.npz \
  --data-verification-gate /unused/path/formal-run/data_verification/gate.json \
  --output /unused/path/formal-run
```

先人工签字检查 `qualification/gate.json`。只有非 fixture `passed=true` 才运行全链：

```bash
CSI_PAIRS_PYTHON=/unused/path/csi-pairs-v2-env/bin/python \
CSI_PAIRS_FORMAL_DATASET=/path/to/csi_pairs_formal_v2_1_v6.npz \
CSI_PAIRS_FORMAL_OUTPUT=/unused/path/formal-run-all \
CSI_PAIRS_VERIFIER_MANIFEST=/path/to/independent_rt_verifier.json \
CSI_PAIRS_RISK_FEATURE_MANIFEST=/path/to/risk_feature_adapter.json \
CSI_PAIRS_EXTERNAL_ADAPTER_MANIFEST=/path/to/external_adapters.json \
CSI_PAIRS_RESOURCE_CONTROL_MANIFEST=/path/to/resource_controls.json \
CSI_PAIRS_SCENE_ID_MANIFEST=/path/to/scene_id.json \
CSI_PAIRS_EXTERNAL_VALIDITY_MANIFEST=/path/to/external_validity.json \
CSI_PAIRS_LITERATURE_RESOURCE_MANIFEST=/path/to/literature.json \
CSI_PAIRS_RT_CALIBRATION_MANIFEST=/path/to/rt_calibration.json \
CSI_PAIRS_SHUFFLED_PAIR_MANIFEST=/path/to/shuffled_pair.json \
CSI_PAIRS_RETENTION_MANIFEST=/path/to/retention.json \
  formal_v2/scripts/run_formal_v2.sh
```

每次正式 run 使用新的输出目录；脚本拒绝覆盖 stage 目录。

## 8. 论文 V2 图表占位符应该写什么

`paper_v2/main.tex` 已加入四个可见的 `DRAFT PLACEHOLDER / NOT A RESULT`：

| 图/表 | 应填内容 | 允许替换的条件 |
|---|---|---|
| Figure 1 paired audit | 至少两个外部模型的六条件；active/null 分开；paired bank CI | C1 数据与模型合同完成 |
| Figure 2 architecture | CSI/map -> shared F；endpoint/A/R；teacher audit；oracle-x 独立；下游丢弃辅助头 | 方法代码冻结后可画，不需要结果 |
| Figure 3 split/gate flow | source 四角色、target support/query、external；G0-G8 失败出口与删除 claim | 数据协议冻结后可画 |
| Figure 4 formal panel | A wrong-map；B No-X 三基线；C null；D 两城四臂；E interaction CI | 对应 gate 的非 fixture CSV 生成并复核 |
| Table 3 | Endpoint/A/R/Full 的 active CGS、null gap、Response NMSE、FLOPs | G3/G4 通过或如实报告失败 |
| Table 4 | 两城 k=0/8/32/128 median/P90；risk 仅 frozen k=0 | G5；risk 另需 calibration gate |

每个最终 caption 必须写：输入/对照、独立 scene banks 数、训练 seeds、label draws、误差区间、单位和冻结门槛。表中的 `NOT RUN` 不能用 fixture 数字替换。

## 9. 论文状态和写作动作

- V2 论文是独立目录 `paper_v2/`；`paper/main.tex` 与 V1.26 PDF 未改动。
- 当前摘要仍写 No-Go，不得把 `READY_FOR_DATA` 改成 method ready/effective。
- G2 失败：论文转向数据/readout qualification，不再写 Response 方法。
- oracle 通过而 No-X 失败：删除 deterministic Response headline，转概率 response 或 paired compatibility。
- G4 interaction 失败但 Full 胜两单支：最多写 complementary，不写 synergy。
- Full 未胜两单支：取消 CSI-PAIRS Full headline，围绕更强单分支或 audit 重新定题。
- G8 未通过：结论止于 simulator-defined/consistent。

## 10. 目前仍需外部资源

以下内容不能由代码生成，也没有在工作区被发现：

1. qualified RT engine 与真实版本化配置；
2. 许可明确的场景、地图、材质与 BS 坐标；
3. 第二引擎或受控实测 paired CSI；
4. 足够多的独立 source banks 和两个 target cities；
5. 至少两个可运行外部 map-conditioned models；
6. 正式 GPU 预算与训练时长。

因此 V2.1 的准确裁决是：**工程上可以开始接数据和跑资格实验；科学上仍是 No-Go，不能直接启动论文主结果写作。**
