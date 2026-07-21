# 08 — 抽出 `messaging.py`，解开 `ai ↔ commands` 循环依赖

**What to build:** `room_say`（及其依赖的 `ON_HEAR_SAY`/`HearSayContext`/玩家判定辅助函数）搬到一个新的 `messaging.py` 模块，`ai.py` 的 Chatter 行为可以在模块顶部直接 `from mud_engine.messaging import room_say`，不用再在函数体内做一次延迟 import 来绕开循环依赖。这次搬家只是"移动 + 改 import"，不改变 `room_say` 的行为或签名。

对应 spec：[.scratch/m3-hardening/spec.md](../spec.md) B3-2（P1-3/M1）。

**Blocked by:** None — 可立即开始（与 04 号票 `wire_runtime` 都是纯结构性重构，互相独立，可并行）。

**Status:** ready-for-agent

- [ ] 新建 `engine/src/mud_engine/messaging.py`：迁入 `room_say`、`_is_player_entity`（可考虑改名去掉下划线前缀，因为将被 `ai.py` 跨模块使用）、`ON_HEAR_SAY`、`HearSayContext`（若这些常量/类型当前定义在 `commands.py` 别处，一并迁移到 `messaging.py`）。
- [ ] `commands.py` 的 `say` 命令改为 `from mud_engine.messaging import room_say`（模块顶部 import，不再是本地定义）。
- [ ] `ai.py` 第 174 行附近的延迟 import（`from mud_engine.commands import room_say`，在函数体内）改为模块顶部 `from mud_engine.messaging import room_say`，移除函数体内的延迟 import。
- [ ] 纯结构性搬家，不改变 `room_say` 行为；现有测试（若有直接 `from mud_engine.commands import room_say` 的测试用例）同步改 import 路径。
- [ ] `just test` 全绿，尤其 `test_commands.py`、涉及 AI Chatter 行为的测试。

## Comments
