# 26 - NPC 生成/重生地基（D2）

**What to build:** 场景 npcs 段支持 `count` / `respawn` / `startroom`；挂低频 Spawn/Reset 扫描到 tick。对应 LPC「唯一召回 / 多实例补齐」。M1 NPC 不死不触发重生，机制地基先埋；`Behavior` 形状为未来可变状态进存档留好。

**Blocked by:** 25 - 重生扫描与行为驱动同属 tick 侧 NPC 基础设施。

**Status:** ready-for-agent

- [ ] YAML npcs 支持 `count` / `respawn` / `startroom`（或与 `in_room` 关系明确）
- [ ] 加载时按 `count` 生成对应实例数
- [ ] 低频 Spawn/Reset 扫描挂 tick（M1 可空转或只补齐缺失实例）
- [ ] 现有单实例静态 NPC 加载行为不破
- [ ] 现有测试全绿（不回归）
