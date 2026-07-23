---
Status: resolved
---

# 04 — A5 `block_exits` 拒走文案（`deny_message`）

**What to build:** `block_exits` 某方向可声明可选 `deny_message`，挡路 NPC 在场时用该自定义文案代替固定的「{名}挡住了{方向}方向的去路。」；未声明 `deny_message` 的既有场景行为不变（回退默认文案）。

对应 spec：`.scratch/polishing/spec.md` §A5（User Stories 16–17；Implementation Decisions「A5」）。

**Blocked by:** None — 可立即开始。

- [x] `components.py`：`BlockExits.by_direction` 值从裸模板键字符串升级为 `BlockEntry`（含 `npc_template: str` + `deny_message: str | None`）。
- [x] `scene_loader.py`：`block_exits: { <dir>: { npc: <key>, deny_message?: <str> } }` 解析（`npc` 必填，`deny_message` 可选）；纯字符串写法（旧形状：`<dir>: <npc模板键>`）保留兼容，等价于 `deny_message: null`。
- [x] `commands.py::_cmd_go` 挡向分支：有 `deny_message` 用之；否则回退现有默认文案。
- [x] 契约新增字段：`rooms.*.block_exits.<dir>.deny_message`（可选字符串）——`docs/creator-contract-v0.md` 同步补写。
- [x] `test_doors.py`/`test_story_doors.py`（或同目录新文件）新增 `deny_message` 用例：自定义文案生效、未声明回退默认文案、旧字符串写法仍加载成功。
- [x] `just test` 全绿。

## Comments

**落地（2026-07-23）**

- **字段形状**：`BlockEntry(npc_template: str, deny_message: str | None = None)`；`BlockExits.by_direction: dict[str, BlockEntry]`。
- **YAML**：推荐 `{npc, deny_message?}`；纯字符串 `<dir>: <模板键>` → `deny_message=None`。
- **命令**：非空 `deny_message` 时原样返回；`None`/空串回退默认「{名}挡住了{方向}方向的去路。」。
- **存档**：新格式 `{npc_template, deny_message}`；旧存档字符串值仍可反序列化。
- **契约**：`docs/creator-contract-v0.md` 剧情挡向段已补 `deny_message` 与字符串简写说明。
