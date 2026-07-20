# 21 - 标志位 no_take / no_drop（C4）

**What to build:** 物品可声明 `no_take`（拿不起，如固定家具）与 `no_drop`（丢不掉；支持字符串自定义提示，如"这是任务物品，不能丢弃"）。提示为声明式字符串字段，非闭包。

**Blocked by:** 19 - 标志位在 `transfer` reject 路径上生效。

**Status:** ready-for-agent

- [ ] `no_take` 物品 take 失败并有提示
- [ ] `no_drop` 物品 drop 失败；自定义提示字符串出现在消息中
- [ ] 标志位经 YAML 声明式配置
- [ ] 无标志位物品行为不变
- [ ] 现有测试全绿（不回归）
