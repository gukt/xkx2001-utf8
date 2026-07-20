# 35 - NPC ask/say 文案统一（NPC #8 Divergent Change）

**Smell:** `commands._cmd_ask`（683/685）用"说道："，`room_say`（718）/`_cmd_say`（720）用"说："。同域概念（NPC 说话）两种文案。

**Fix:** 评估统一为"说："（简洁）或"说道："（口语）。注意测试断言（`test_ask`/`test_say` 可能含"说"/"说道"），改文案要同步测试。语义微差（ask 响应 vs 广播）可保留，判断后定。

**From:** BCD re-pass code-review NPC 批 Standards #8（commit bab2f44f）。

**Status:** ready-for-agent

- [ ] 文案统一或明确语义区分理由
- [ ] just gate 全绿
