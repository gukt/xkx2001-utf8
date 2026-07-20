# 09 - 领域事件点：移动 / 物品 / 门

**What to build:** 在移动/物品/门命令路径预留事件点（空挂调用,M1 默认放行）,为"门锈住打不开""任务物品不能丢""进房触发 NPC 反应"等规则留触发点。复用 07 的事件总线注册 handler。M1 不实现任何规则逻辑,只把调用点接上。

- **移动**:`on_before_enter_room`（可否决）/ `on_enter_room` / `on_leave_room` 挂 `_cmd_go` 前后;`on_traverse_blocked`（出口存在但被门挡住时）可选。
- **物品**:`on_get` / `on_drop`（均可否决）挂 `_cmd_take` / `_cmd_drop` 前后。
- **门**:`on_door_state_change` 挂门命令（`open`/`close`/`unlock` 改门状态处）。
- **空挂调用**,M1 默认放行,不改现有命令行为。
- **`on_nature_change` 不在此票**--推 B 块 Nature 落地时挂（块 A 阶段 Nature 未实现,无切换处可挂）。

**Blocked by:** 07 - 复用其事件总线注册领域事件 handler。

**Status:** resolved（2026-07-19 落地；288 测试全绿，`/code-review` 双轴过）

- [x] `_cmd_go` 前后挂 `on_before_enter_room`（可否决）/ `on_enter_room` / `on_leave_room`
- [x] `_cmd_take` / `_cmd_drop` 前后挂 `on_get` / `on_drop`（均可否决）
- [x] 门状态切换处挂 `on_door_state_change`
- [x] 注册测试 handler,触发 `go` / `take` / `drop` / 门命令,断言各 handler 被调用且收到正确参数
- [x] 注册 deny handler 拦截 `on_before_enter_room`,`go` 被否决
- [x] 不注册 handler 时现有命令行为不变
- [x] 现有测试全绿（不回归）
