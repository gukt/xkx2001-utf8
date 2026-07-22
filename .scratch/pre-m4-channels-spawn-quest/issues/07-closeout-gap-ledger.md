---
Status: resolved
---

# 07 — 收口：GAP 台账 + CONTEXT/PROGRESS 回写

**What to build:** 本 effort（票 `01`–`06`）全部落地后，做一次收口：把 GAP 台账（`docs/gap-ledger.md`）里"多人频道 / 物品 respawn / 任务"相关条目从"未实现/降级建议"改写为"已支持"（措辞保持克制，不宣称完整多人网游、不宣称通用任务引擎——仍是严格切片交付）；核对 `CONTEXT.md` 里 Channel、房间 objects 放置、Quest 三个词条的描述与最终实现是否一致，若实现细节（如字段名、命令名）与词条描述有出入，直接回写词条本身（不新开决策票，spec 已明确允许此类收敛，若发现偏差过大到需要重新拍板，停下来做一次短 grill 说明再继续）；`PROGRESS.md` 的 Done/Next Up 按本 effort 完成状态更新；确认 Pre-M4 引擎房间保真 effort 的既有文档未被本效重开放置模型讨论（US30，纯核对，不需要改房间保真仓库内容）。

对应 spec：[.scratch/pre-m4-channels-spawn-quest/spec.md](../spec.md) US29、US30。

**Blocked by:** 04、05、06（GAP 台账改判前提是三条能力都已落地）。

- [x] `docs/gap-ledger.md`：更新"多人频道/物品 respawn/任务"对应条目为已支持，措辞不越界（不写"完整多人网游"/"通用任务引擎"）。
- [x] `CONTEXT.md`：核对并（如需）回写 Channel / 房间 objects 放置 / Quest 三条词条，使其与票 `01`–`06` 最终实现一致（字段名、命令名、语义边界）。
- [x] `PROGRESS.md`：Done 增补本 effort 收尾条目（滑动窗口只留最近 5 条，超出的移入 `.scratch/progress-archive.md`）；Next Up 移除本 effort、按当时状态决定是否推进房间保真或评估 M4。
- [x] 核对 [.scratch/pre-m4-engine-room-fidelity/](../../pre-m4-engine-room-fidelity/) 现有文档未把放置模型当未决项重开（US30，只读核对，不修改对方文档，除非发现对方文档已过期需要提醒——如有则在本票 Comments 里记录而非直接改对方文件）。
- [x] 不新增 ADR（ADR-0008/0010 结论不变）；若发现需要修订，先短 grill 再动手，不静默改判。

## Comments

2026-07-22 收口落地：GAP 台账改判「多人频道」「物品/NPC 槽位补刷」（新增行）与「脚本化任务」行内声明式 Quest 已支持；CONTEXT Channel / objects / Quest 与实现对齐（命令与字段细节留在 GAP/契约，词条保持「是什么」），effort 词条标为已关闭；PROGRESS Next Up 推进到房间保真 grill，明确不自动开 M4。US30 核对：房间保真 [README](../../pre-m4-engine-room-fidelity/README.md) 与 [session-notes](../../pre-m4-engine-room-fidelity/session-notes-2026-07-21.md) 均写明放置已迁出且不得重开——**未**当未决项。提醒（不改对方文件）：对方 README「状态」仍写「等频道/spawn/任务关完后再 grill」，兄弟批现已关，对方 grill 开工时可顺手改成「可开 grill」。

Review fix：按 CONTEXT-FORMAT 收紧 Channel / Quest / objects 词条（去掉命令面堆砌）。
