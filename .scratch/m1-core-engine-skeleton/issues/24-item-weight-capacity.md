# 24 - 重量与容量上限最小版（C7）

**What to build:** 物品有 weight（或复用 Stackable.base_weight）；容器有 `max_capacity`；超重或超容量放入被拒绝并提示。角色负重公式推迟 M2，本票只做单容器超限拒绝。

**Blocked by:** 22 - 嵌套容器 put 是超限拒绝的主要路径；19 - transfer reject。

**Status:** resolved

- [x] 容器可配置 `max_capacity`（及/或重量上限）
- [x] 超容量 / 超重 `put`/`transfer` 失败并给提示
- [x] 未超限时放入成功
- [x] 角色负重惩罚不做（Out of Scope）
- [x] 经 `execute_line` 可观察
- [x] 现有测试全绿（不回归）
