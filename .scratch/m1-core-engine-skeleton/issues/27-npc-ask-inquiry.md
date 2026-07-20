# 27 - ask 对话命令 + inquiry 映射（D3）

**What to build:** `ask <npc> about <topic>`：同房间 NPC 候选 + topic 自由 token；NPC 按预设 inquiry 映射返回字符串响应（钩子可选，默认声明式）。原子交易节点推 M2。NPC 交互最低门槛。

**Blocked by:** None - 可立即开始（仅需现有静态展示型 NPC）。

**Status:** resolved（2026-07-20 re-pass：handler 占位 + ask 候选收窄）

- [x] `ask <npc> about <topic>` 可解析并执行
- [x] 命中 inquiry 映射时返回对应字符串
- [x] 未知 topic / 找不到 NPC 有明确提示
- [x] inquiry 经 YAML 声明（或 extension_data / 组件字段）
- [x] 经 `execute_line` 端到端可验证
- [x] 现有测试全绿（不回归）

## Comments

### 2026-07-20 re-pass

- 复核既有 ask/inquiry 路径（解析 + 执行 + YAML + 存档）；AC 全绿。
- 补 `Inquiry.handler: str | None` 声明式占位（同 `Equippable.apply_hook`），YAML/存档透传，M1 不执行、不接 RestrictedPython。
- ask 候选收窄：同房间实体须挂 `Inquiry` 或 `NpcSpawnMeta`，不再匹配裸 `Position`。
- 测试：`TestAskInquiry` 7 + save/restore inquiry 相关 2；`tests/test_npc_extension.py` 22 passed。
