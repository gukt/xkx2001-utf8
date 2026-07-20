# 27 - ask 对话命令 + inquiry 映射（D3）

**What to build:** `ask <npc> about <topic>`：同房间 NPC 候选 + topic 自由 token；NPC 按预设 inquiry 映射返回字符串响应（钩子可选，默认声明式）。原子交易节点推 M2。NPC 交互最低门槛。

**Blocked by:** None - 可立即开始（仅需现有静态展示型 NPC）。

**Status:** resolved

- [x] `ask <npc> about <topic>` 可解析并执行
- [x] 命中 inquiry 映射时返回对应字符串
- [x] 未知 topic / 找不到 NPC 有明确提示
- [x] inquiry 经 YAML 声明（或 extension_data / 组件字段）
- [x] 经 `execute_line` 端到端可验证
- [x] 现有测试全绿（不回归）
