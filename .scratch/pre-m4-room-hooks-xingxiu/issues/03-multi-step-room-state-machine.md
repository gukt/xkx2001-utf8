---
Status: resolved
---

# 03 — 机关 #3 多步房间状态机

**What to build:** 挂一个"多步顺序动作才能改变房间状态"的官方房间钩子（玉路刮锈拔斧推门灵感）：新增 2–3 个命令动词（如刮锈/拔斧/推门），钩子用房间自由状态记录当前完成到第几步；跳过前置步骤直接做后续步骤时被拒绝并有提示；按正确顺序走完全部步骤后房间状态确实改变（如新增/揭示出口）。在 `xingxiu_mechanics.yaml` 追加对应验收房间。

对应 spec：US17–20；Testing S0/S1。

**Blocked by:** `01`（房间自由状态组件 + 窄 `ctx`）。

- [x] 新增命令动词（数量按机关设计，2–3 个），仅在挂了对应钩子的房间生效；其余房间返回统一拒绝提示。
- [x] 钩子用 `ctx` 房间级自由状态记录多步进度（钩子自己定义存什么，引擎不假设结构）。
- [x] 跳步直接做最后一步被拒绝并有提示；按序完成后经 `ctx.add_exit`/揭示出口等方式改变房间状态。
- [x] `xingxiu_mechanics.yaml` 追加至少一条覆盖本机关的验收房间。
- [x] 测试（S0）：直调钩子各步骤方法，断言进度状态与跳步拒绝。测试（S1）：命令序列——跳步失败提示、按序完成后新出口可走。
- [x] `just test` 全绿。

## Comments

### 实现摘要（2026-07-22 Wave 3）

- **钩子**：`multi_step_gate`（`MultiStepGateHook`）
- **命令**：`scrape`/`pull`/`push`（别名 `刮锈`/`拔斧`/`推门`）；公共路径 `_invoke_room_hook_action`
- **params**：`direction` + `target`（完成后 `add_exit`）
- **自由状态**：`{"step": 0|1|2|3}`（0 未开始 → scrape→1 → pull→2 → push→3）
- **验收房**：`jade_gate` / `jade_chamber`（自 `dig_base` 西入）
- **测试**：`engine/tests/test_xingxiu_mechanics_03.py`
