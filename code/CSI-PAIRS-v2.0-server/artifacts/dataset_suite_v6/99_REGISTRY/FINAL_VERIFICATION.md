# Final suite verification

时间：2026-08-09 17:38 CST  
命令：`./VERIFY_SUITE.sh`  
结果：`SUITE_VERIFICATION=PASS checks=20 mode=full`

## 已通过

- 12 个 catalog `COPIED` 目标路径全部存在，数据根均为真实目录而非顶层软链接；仅 3 项有源/目标复制审计，因此 `G-COPY=PARTIAL`。
- `external_wireless`：363,263 个普通文件、23,857,330,137 个普通文件字节；deep verifier 通过；133/133 SHA-256 通过；partial 文件为 0。
- external 真实性边界保持正确：`training_core_complete=true`、`all_original_sources_complete=false`。
- Qualcomm：190,590 个普通文件、13,435,727,571 bytes；两个 ZIP 与 11 个 HDF5 共 13/13 SHA-256 通过。
- 冻结规范、旧 candidate、fixtures/diagnostics：17/17 关键 SHA-256 通过。
- 早期失败 M4/visibility 快照：233/233 SHA-256 通过。
- 最新 path-ID collision M4 快照：247/247 SHA-256 通过。
- legacy 34-bank candidate 的缺陷可重复：16,124 pathless clean units，且同为 16,124 all-zero units；nonfinite 为 0。

## 磁盘

- 套件总计 554,820 个普通文件、48,272 个目录。
- 套件 `du -sk`：37,692,880 KiB，约 35.95 GiB 的目录视图。
- `$LOCAL_DATA_VOLUME`：926 GiB 总量、540 GiB 已用、349 GiB 可用、61%。
- 套件通过 APFS clone copy 建立，因此逻辑/分配视图不等于新增相同数量的独占物理块。

## 判定边界

```text
FORMAL_STATUS=POST_AUDIT_NO_GO
SCIENTIFIC_USE=FORBIDDEN
```

这次 `PASS` 证明已执行的目标路径、选定哈希、规模和登记失败状态检查一致；它不证明所有 12 项都完成源/目标独立复制审计，也不证明 RT qualification、paired intervention 资格、无泄漏、四臂结论或 external validity。科学缺口见套件根 `MISSING_ITEMS.md`。
