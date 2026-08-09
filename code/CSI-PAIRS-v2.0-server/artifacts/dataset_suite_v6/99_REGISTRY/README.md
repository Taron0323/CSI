# Registry

- `COPY_AUDIT.json`：3 项源/目标规模、inode 与 clone-copy 语义；其余 catalog 项仅验证目标路径，因此 `G-COPY=PARTIAL`。
- `CRITICAL_SHA256SUMS`：冻结规范、旧 candidate、fixtures 和 diagnostics 的关键哈希。
- `FAILED_RUN_SHA256SUMS`：失败 M4 run 与 visibility diagnostic 的 233 项文件哈希。
- `FINAL_VERIFICATION.json` / `.md`：最终 full verifier 的机器可读与人读摘要。
- `M4_FAILED_RUN_SHA256SUMS`：最新 scene-12 path-ID collision run 的 247 项文件哈希。
- `QUALCOMM_SHA256SUMS`：本套件对两个 ZIP 和 11 个 HDF5 计算的本地哈希。

Qualcomm 哈希是 local snapshot checksums，不是上游发布者签名或官方 checksum。external 的上游/下载哈希继续保存在 `02_EXTERNAL_WIRELESS/external_wireless/SHA256SUMS`。

`VERIFY_SUITE.sh` 完整模式会重新计算上述哈希并运行 external deep verifier。`--quick` 仍检查结构、精确文件数/字节数、失败快照哈希、关键小文件哈希和 external 非深度结构，但跳过 13 GB Qualcomm 与 external 133 项大文件哈希。
