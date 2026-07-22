---
Status: ready-for-agent
---

# 05 — 日间店铺 day_shop + 打铁铺

**What to build:** 房间可写 `day_shop: true`；加载期编成依赖 `is_night` 的拒入 `entry_guard`（复用既有进房系统，不平行第二套）。同房若再手写会与夜间语义冲突的 `entry_guard`，加载失败。官方打铁铺（或指定日间店）夜间不可入、白天可进。

对应 spec：US24–US26；Testing S2/S3。冲突策略见 [to-tickets-notes.md](../to-tickets-notes.md) 决策 2。

**Blocked by:** None — 可立即开始（技术上可与 Wave 1 并行；建议仍按 Wave 2 控 session 体量）。

- [ ] 一等布尔字段 `day_shop`；加载期编译为夜间拒入的 `entry_guard`（谓词复用 `is_night`）。
- [ ] 同房同时存在 `day_shop` 与手写 `entry_guard` → **加载失败**（明确错误，不静默覆盖）。
- [ ] 官方 `m2_mvp_scene` 的打铁铺挂 `day_shop`；白天可进、夜间拒入（可测 Nature 相位或等价观测）。
- [ ] 契约/已知字段对本字段做加法（最终措辞可与票 `07` 对齐）。
- [ ] 测试（S2）：字段消费；冲突加载失败；编译后夜间拒入语义可观测。测试（S3）：打铁铺日/夜路径。
- [ ] 本票为**非硬门闩**：若实现中撞上未预见的进房模型大洞，可止损并在 Comments + PROGRESS Blocked 记录，不堵硬门闩收口。
- [ ] `just test` 全绿。

## Comments
