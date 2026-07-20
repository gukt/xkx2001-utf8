# 23 - look 物品增强（C6）

**What to build:** `look <物品>`（或等价 examine）展示 long 描述；若是容器展示内容；若有堆叠/价值/重量展示数值。玩家能了解物品详情（房间 look 地面仍可只列名）。

**Blocked by:** 18 - 需要能力组件字段供展示。

**Status:** ready-for-agent

- [ ] `look <物品>` 返回 long 描述
- [ ] 容器物品展示内容列表
- [ ] Stackable/Valuable/重量等有数值时出现在消息中
- [ ] 找不到物品时有明确提示
- [ ] 现有无参 `look`（房间）行为不回归
- [ ] 现有测试全绿（不回归）
