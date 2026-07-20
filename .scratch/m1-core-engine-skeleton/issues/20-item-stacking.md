# 20 - 物品堆叠合并与拆分（C3）

**What to build:** `Stackable` 物品 `transfer` 到容器时，目标已有同规范堆则合并 amount；`take <物品> <数量>` 可从一堆拆出指定数量。物品栏不被同名堆刷屏。

**Blocked by:** 19 - 堆叠逻辑挂在 `transfer` 路径上。

**Status:** resolved

- [x] 同规范 Stackable 放入同一容器时自动合并 amount
- [x] `take <物品> <数量>` 可拆分（剩余留源容器，拆出部分进目标）
- [x] 非 Stackable 物品不合并
- [x] 数量非法（0 / 超堆）被拒绝并给提示
- [x] 经 `execute_line` 断言合并/拆分后的可观察状态
- [x] 现有测试全绿（不回归）
