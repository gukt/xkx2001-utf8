# 35 - NPC ask/say 文案统一（NPC #8 Divergent Change）

**Smell:** `commands._cmd_ask`（683/685）用"说道："，`room_say`（718）/`_cmd_say`（720）用"说："。同域概念（NPC 说话）两种文案。

**Fix:** 评估统一为"说："（简洁）或"说道："（口语）。注意测试断言（`test_ask`/`test_say` 可能含"说"/"说道"），改文案要同步测试。语义微差（ask 响应 vs 广播）可保留，判断后定。

**From:** BCD re-pass code-review NPC 批 Standards #8（commit bab2f44f）。

**Status:** resolved

- [x] 文案统一或明确语义区分理由
- [x] just gate 全绿

**Resolved:** 2026-07-20，commit `7d603c51`。
经评估统一为「说：」：ask 响应的「说道：」改为与 say/room_say/Chatter 一致的「说：」。test_ask_uses_alias 断言改为「石像守卫说：」以同时验证别名解析与统一文案。29 绿。
