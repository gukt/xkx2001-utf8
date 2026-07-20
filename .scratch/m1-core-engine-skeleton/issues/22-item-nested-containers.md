# 22 - 容器物品 put / take from（C5）

**What to build:** 物品可挂 `Container`（箱子/背包）；`put <物品> in <容器>` / `take <物品> from <容器>`。M1 容器始终可打开（不做 open/closed）。玩家能管理物品与发现隐藏内容。

**Blocked by:** 19 - 嵌套转移走统一 `transfer`。

**Status:** resolved

- [x] 场景 YAML 物品可声明为容器（挂 Container）
- [x] `put <物品> in <容器>` 将物品从玩家栏移入容器
- [x] `take <物品> from <容器>` 从容器取到玩家栏
- [x] 容器须在同房间或玩家栏内可达
- [x] 经 `execute_line` 端到端可验证
- [x] 现有测试全绿（不回归）
