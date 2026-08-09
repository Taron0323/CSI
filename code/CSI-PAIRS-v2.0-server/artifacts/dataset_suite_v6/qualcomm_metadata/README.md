# Qualcomm Wi3R/WiPTR local copy

数据副本位于 `qualcomm_wireless_indoor/`。这是从 `/Users/futaoran/Desktop/ICLR2027/datasets/qualcomm_wireless_indoor` 建立的 APFS clone copy，不是软链接。

## 本地内容

- `archives/Wi3R.zip` 与 `archives/WiPTR.zip`；
- Wi3R main、grid、三个 OOD split 的 HDF5 和几何/对象文件；
- WiPTR train/validation/test、grid 与 5-layout wall-removal OOD 数据；
- 总计 190,590 个普通文件、46,945 个目录、13,435,727,571 个普通文件字节；
- 两个 ZIP 和 11 个 HDF5 的本地 SHA-256 见 `../99_REGISTRY/QUALCOMM_SHA256SUMS`，实际路径为套件根的 `99_REGISTRY/QUALCOMM_SHA256SUMS`。

现有审计表明 Wi3R main 有 5,000 layouts、5,000,000 links、125,000,000 个存储 path rows；WiPTR 标准 split 有 10,000/1,000/1,000 train/validation/test layouts。路径字段包含 gain、phase、ToA 和 departure/arrival phi/theta；载频为 3.5 GHz；生成引擎为 Remcom Wireless InSite。

## 关键科学边界

这些数据来自和 Sionna 不同的 RT 引擎，但它们不是 CSI-PAIRS 注册 sibling worlds 的第二引擎复追踪。现有 layouts 没有共同 Tx/Rx 的完整 `d>=2` intervention hypercube、三次 observation repeats、signed action、primitive/path surface mapping 或 v6 权限账本。WiPTR 拆墙 OOD scenes 与普通 validation 的 Tx/Rx 坐标也不能直接配对。

因此当前只允许：独立引擎基线候选、adapter 开发和许可补齐后的预注册外部域实验。若要关闭 second-engine external-validity gate，必须对同一正式 CSI-PAIRS foundation/world/edit/Tx/Rx 重新追踪。

## Provenance/许可缺口

源目录没有本地数据集 README、下载/source manifest、上游 archive checksum、数据许可证或再分发条款快照。当前套件 SHA 只能证明本地副本内容稳定，不能证明上游身份或授权。相关代码仓库许可证不能自动替代数据许可证。许可补齐前不要公开再分发本目录，也不要把它写成 paper release 已清权数据。

