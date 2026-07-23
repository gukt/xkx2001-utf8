---
Status: ready-for-agent
---

# 04 — A5 `block_exits` 拒走文案（`deny_message`）

**What to build:** `block_exits` 某方向可声明可选 `deny_message`，挡路 NPC 在场时用该自定义文案代替固定的「{名}挡住了{方向}方向的去路。」；未声明 `deny_message` 的既有场景行为不变（回退默认文案）。

对应 spec：`.scratch/polishing/spec.md` §A5（User Stories 16–17；Implementation Decisions「A5」）。

**Blocked by:** None — 可立即开始。

- [ ] `components.py`：`BlockExits.by_direction` 值从裸模板键字符串升级为 `BlockEntry`（含 `npc_template: str` + `deny_message: str | None`）。
- [ ] `scene_loader.py`：`block_exits: { <dir>: { npc: <key>, deny_message?: <str> } }` 解析（`npc` 必填，`deny_message` 可选）；纯字符串写法（旧形状：`<dir>: <npc模板键>`）保留兼容，等价于 `deny_message: null`。
- [ ] `commands.py::_cmd_go` 挡向分支：有 `deny_message` 用之；否则回退现有默认文案。
- [ ] 契约新增字段：`rooms.*.block_exits.<dir>.deny_message`（可选字符串）——`docs/creator-contract-v0.md` 同步补写。
- [ ] `test_doors.py`/`test_story_doors.py`（或同目录新文件）新增 `deny_message` 用例：自定义文案生效、未声明回退默认文案、旧字符串写法仍加载成功。
- [ ] `just test` 全绿。
