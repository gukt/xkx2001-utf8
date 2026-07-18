Type: chore
Status: resolved

## Question

M1 落地前，如何处置 `engine/` 下约 45k 行旧实现？新代码放到哪里？

## Answer

作为 **M1 第 0 步**（本票）执行完毕：

1. git tag `archive/engine-pre-m1-rewrite` 冻结旧树。
2. 从工作区移除 `engine/src`、`engine/tests`、`engine/scenes`、`engine/tools`。
3. 保留路径名 `engine/`，放入最小可导入包 + 冒烟测试；`prototypes/ecs_ugc` 保留。
4. 决策落 [ADR-0002](../../../docs/adr/0002-engine-workspace-greenfield-reset.md)。

否决：`engine_v2`、整棵进 `docs/archive/`、新旧混放渐进清理。

## 完成判据

- [x] tag 存在且指向清空前的 commit
- [x] 工作区无旧生产代码
- [x] `just test` / `just lint` 在最小骨架上通过
- [x] CLAUDE / PROGRESS / M1 spec 已指向本决策
