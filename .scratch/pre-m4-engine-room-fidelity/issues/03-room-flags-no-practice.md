---
Status: resolved
---

# 03 — 房间旗标 + 藏书阁禁练

**What to build:** 任意房间可声明 `no_fight` / `no_steal` / `no_sleep_room`；`no_fight` 对已有命令面生效（拦 `attack`/`kill` 并给清晰提示）。尚无对应命令的旗标可声明并校验，但不假装已禁偷/睡。另：可声明同房禁 `practice`（「读书还是练功」类提示），供藏书阁及同构房使用——本票交付通用拦截能力，官方藏书阁挂载留给票 `04`。

对应 spec：US13–US16；Testing S1/S2。

**Blocked by:** None — 可立即开始。

- [x] 房间布尔字段 `no_fight` / `no_steal` / `no_sleep_room` 加载期消费并进已知字段集。
- [x] `no_fight` 房间执行 `attack`/`kill` 被拒绝，状态不变，提示清晰。
- [x] `no_steal` / `no_sleep_room`：可声明 + 校验；无对应命令面时行为 inert（不为成真而补 steal/睡眠子系统）。
- [x] 同房禁 `practice`：以「本房启用藏书阅读」的同房规则或等价一等声明落地（见 [to-tickets-notes.md](../to-tickets-notes.md) 决策 3）；文案对齐「读书/练功」意图即可，不要求 LPC 字面。
- [x] 测试：`no_fight` 拦攻击；禁练房拦 `practice`；inert 旗标可加载；不破坏现有战斗/练功基线。
- [x] `just test` 全绿。

## Comments

实现摘要（供 07 回写契约 / 票 04 挂载）：

- **旗标字段**：`no_fight` / `no_steal` / `no_sleep_room`（布尔）→ 组件 `RoomFlags`；全假不挂。
- **禁练挂载**：`library: true` 或 `library: {…}` → 组件 `LibraryRoom`（「本房启用藏书阅读」）；`_cmd_practice` 入口若当前房有 `LibraryRoom` 则拒：`这里是读书的地方，还是别练功了。` 票 04 可把 `library` 映射扩展为书档配置，仍挂本组件。
- **no_fight 提示**：`这里不能动手打架。`（`attack`/`kill`）。
- **inert**：`no_steal` / `no_sleep_room` 仅加载+校验+存档，无命令面副作用。
- **契约**：`rooms.*` 已知字段已加上述四名。
