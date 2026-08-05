# CSI-PAIRS 当前代码位置图

## 1. 审查入口

| 用途 | 绝对路径 | 说明 |
|---|---|---|
| 冻结论文规范 | `/root/autodl-tmp/CSI/Idea1-CSI-PAIRS-冻结版-零基础阅读稿-v6_VSCode兼容版.md` | 科学与协议行为的最高依据 |
| Review 提示词 | `/root/autodl-tmp/CSI/CODE_REVIEW_PROMPT.md` | 针对当前 V2.1 实现的双向审计指令 |
| 当前代码根目录 | `/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server` | 唯一默认执行与 review 对象 |
| 当前 Python 包 | `/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/formal_v2` | V2.1/V6 可执行实现 |
| 当前配置 | `/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/formal_v2/configs/formal_v2.json` | 正式 schema 与冻结阈值 |
| 数据合同 | `/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/formal_v2/DATA_CONTRACT.md` | NPZ 字段、权限和验证边界 |
| 当前测试 | `/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/formal_v2/tests/test_formal_v2.py` | 61 个 schema/语义/变异测试 |
| 当前论文草稿 | `/root/autodl-tmp/CSI/code/CSI-PAIRS-v2.0-server/paper_v2/main.tex` | 必须反向核对 V6，不是更高规范 |
| 历史代码 | `/root/autodl-tmp/CSI/archive/CSI-PAIRS-anonymous-supplement-v1.26` | 只用于追溯，不得替当前代码补缺 |

目录名仍保留 `CSI-PAIRS-v2.0-server`，包内 schema 和 README 已是 V2.1/V6。为保持
`SHA256SUMS`、ZIP 和脚本路径可复现，当前源码不重命名、不移动。

## 2. 当前运行模块

```text
code/CSI-PAIRS-v2.0-server/
├── README.md
├── CSI-PAIRS-startup-package-v2.0.md
├── SHA256SUMS
├── formal_v2/
│   ├── formal_cli.py                 # 所有 CLI 入口与 all 编排
│   ├── formal_config.py              # 严格配置 schema
│   ├── formal_io.py                  # strict JSON、CSV、SHA、manifest
│   ├── formal_evidence.py            # evidence context、G0-G8/C1-C13 状态
│   ├── formal_dataset.py             # NPZ loader、world bank、roles、数据约束
│   ├── formal_data_verification.py   # 独立再生验证 adapter
│   ├── formal_protocol.py            # patch/mask/query/typed signed edit
│   ├── formal_teacher.py             # Stage-0 teacher 与 readout
│   ├── formal_routing.py             # Alignment/Response route
│   ├── formal_model.py               # 共享 F/P 与 loss 原语
│   ├── formal_factorial.py           # pilot、四臂训练、定位、J 与初步 gate
│   ├── formal_localization.py        # 异方差位置头与 few-shot adaptation
│   ├── formal_statistics.py          # J、bootstrap、Holm、区间判定
│   ├── formal_probes.py              # compatibility/response probes
│   ├── formal_evaluation.py          # CGS、response、G3/G4 部分子门
│   ├── formal_risk.py                # q_comp、p_fail、support、G6
│   ├── formal_path.py                # A_path、matching、G7
│   ├── formal_wrong_map.py           # 本地六条件诊断，不是 C1 外部证据
│   ├── formal_external.py            # 至少两个外部模型六条件 adapter
│   ├── external_adapters/             # Wi-GATr 官方 snapshot、独立环境、六条件适配
│   ├── formal_controls.py            # equal-FLOP/concat 资源控制 adapter
│   ├── formal_scene_id.py            # C2 scene-ID adapter
│   ├── formal_claim_controls.py      # shuffled-pair 与 retention adapter
│   ├── formal_rt_calibration.py      # C11 独立 RT 校准 adapter
│   ├── formal_external_validity.py   # G8 第二引擎/真实干预 adapter
│   ├── formal_literature.py          # G0 文献与资源 manifest
│   ├── formal_claims.py              # claim/gate 汇总
│   ├── formal_baselines.py           # 本地 ridge 基础工具
│   ├── formal_features.py            # 资格探针/诊断特征
│   ├── formal_metrics.py             # AUROC/NLL/Brier/ECE/AURC 等
│   ├── formal_fixture.py             # 永久 FORBIDDEN 的软件 fixture
│   ├── configs/
│   ├── data/                         # 只有 README；没有正式数据
│   ├── scripts/
│   └── tests/
├── paper_v2/                         # LaTeX 草稿
├── artifacts/                        # 合同和验证说明，不是实验结果
├── output/pdf/                       # 草稿 PDF，不是科学证据
└── paper/official_style/             # ICLR 样式文件
```

## 3. CLI 可达性

核心内生阶段：`inspect-data`、`qualify`、`run-wrong-map`、`run-factorial`、
`run-evaluation`、`run-risk`、`run-path`、`assemble-claims`。

需要外部 manifest/命令的阶段：`verify-data`、`run-external-baselines`、
`run-resource-controls`、`run-scene-id-audit`、`run-external-validity`、
`run-literature-resources`、`run-rt-calibration`、`run-shuffled-pair-control`、
`run-retention-audit`。

`all` 当前编排：

```text
verify-data -> qualify -> run-wrong-map -> run-factorial
            -> run-evaluation -> risk-feature-adapter -> run-risk
            -> run-path -> external-baselines -> resource-controls
            -> scene-ID -> external-validity -> literature/resources
            -> RT-calibration -> shuffled-pair -> retention
            -> assemble-claims
```

所有独立 adapter 都是 `all` 的必需输入；缺失、schema 错误、hash 不一致或
`NOT_ASSESSED` 会在当前阶段阻断，不会进入 claim assembly 的 `SUPPORTED`。

## 4. 历史与原始包

```text
/root/autodl-tmp/CSI/archive/CSI-PAIRS-anonymous-supplement-v1.26/
└── experiments/                      # 冻结 V1 历史实现

/root/autodl-tmp/CSI/CSI-PAIRS-v2.0-server.zip
/root/autodl-tmp/CSI/CSI-PAIRS-anonymous-supplement-v1.26.zip
```

ZIP 是原始传输包；`code/` 和 `archive/` 是当前阅读/测试位置。Review 不应递归审查
`archive/`、PDF、LaTeX 样式、`__pycache__` 或 `.ruff_cache`，除非在追踪版本/产物污染。

## 5. 当前可验证边界

- `sha256sum --check SHA256SUMS`：当前 117 个登记文件全部通过。
- `python3 -m unittest discover -s formal_v2/tests -v`：当前 61 个测试通过。
- `python3 -m py_compile formal_v2/*.py formal_v2/tests/test_formal_v2.py`：通过。
- 正式数据、licensed scene asset、外部模型 checkpoint、第二 RT/真实干预结果均不存在。
- `formal_v2/data/` 只有合同说明；fixture 永远是 `scientific_use=FORBIDDEN`。
- 上述通过项证明包完整性与部分软件属性，不证明 V6 协议已一一实现，更不证明任何科学 claim。
