---
Status: resolved
---

# 01 — 房间钩子协议 + 注册表 + 窄 `ctx` 基础设施

**What to build:** 新增与 `SkillBehavior` 同信任级、同注册模式的可信房间钩子协议 + 全局注册表：房间 YAML 按 `hook_id`（+ 每房间参数）引用已注册的可信 Python 实现；场景加载完成后统一遍历所有声明了钩子引用的房间，把实现按房间 id 订阅到既有的进房/离房/心跳事件点上（不用的事件点不订阅）。新增一个只服务钩子实现的窄 `ctx` 外观对象，覆盖出口增/删/隐藏/揭示、一次性延时自查登记、房间广播/单玩家消息、房间级自由状态读写、受限实体位置变更（后者需实现为可被 `ctx` 与未来的 `SkillBehavior` 双方共享调用的独立方法本体，不只挂在 `ctx` 对象上——供票 `10` 柔丝索直调）。新增房间级自由状态组件（钩子自定义存什么，引擎不假设结构）。未注册的 `hook_id` 在加载 / `--validate` 时 fail-closed（不区分拼写错与未注册）；钩子异常 fail-fast 传播。内容包轨道（带 `manifest.yaml`）声明该字段一律加载失败，`--validate`/`--strict` 与非严格路径给出一致的失败判定——本票随字段一起落地，不留窗口期。用一个测试专用哑钩子（不进 `xingxiu_mechanics.yaml`）验证挂载全链路可用。

对应 spec：US1–9；Testing S0 + S2（挂载与 UGC 拒绝部分）。

**Blocked by:** None — 可立即开始。

- [x] 房间钩子协议：方法集合按「房间生命周期事件点」设计（进房/离房/心跳到期等），全部可选实现；未实现的方法在对应事件点视为不参与，不强制实现全部方法。
- [x] 全局注册表：按 `hook_id` 注册 Python 侧实现；查询未命中即视为未注册。
- [x] 房间 YAML 声明式引用字段：`hook_id`（+ 每房间参数映射）；仅官方单文件轨道（`pack_manifest is None`）允许；内容包轨道声明即失败——`--validate`/`--strict`/非严格加载路径判定一致，非仅警告。
- [x] 挂载逻辑：场景加载完成后遍历声明了钩子引用的房间，按需订阅到既有进房/离房/心跳事件点；未声明的房间不受影响。
- [x] 引用校验：`hook_id` 查不到时加载 / `--validate` 失败（fail-closed，不区分「拼写错」与「未注册」）。
- [x] 钩子异常按 fail-fast 传播（不静默吞掉）。
- [x] 窄 `ctx`：构造时绑定当前房间/当前触发实体；只读信息只到房间 id / 触发实体 id / 时段等既有只读快照字段，不透出其他实体私有组件。
- [x] `ctx` 方法：出口增/删/隐藏/揭示（封装既有 `Exits`/`HiddenExits` dict 操作，不新建平行出口系统）；一次性延时回调登记（落在房间级自由状态里，由钩子自己的心跳方法在到期时自查执行，不新建引擎级通用调度服务）；房间广播 / 单玩家消息；房间级自由状态读写；受限实体位置变更（复用既有「改位置 + 分发进出房间事件」路径，实现为独立可复用方法本体）。
- [x] 房间级自由状态组件：新增，钩子自定义存什么，引擎不假设结构；随存档 codec 同步覆盖（若引擎已有存档路径）。
- [x] 测试专用哑钩子 + S0 测试：直接构造 `ctx` + 调用哑钩子各生命周期方法，断言 `add_exit`/`remove_exit`/`schedule`/`message_room`/`move_entity`/房间状态读写副作用；未注册 `hook_id` 引用失败；钩子异常传播。
- [x] S2 测试：官方单文件轨道声明钩子引用加载成功并挂载生效（用哑钩子验证）；内容包轨道声明同字段加载/`--validate`/`--strict`失败。
- [x] `just test` 全绿。

## Comments

### 实现摘要（2026-07-22 Wave 1）

- **模块**：`engine/src/openmud/room_hooks.py`
- **协议**：`RoomHook`（可选 `on_enter` / `on_leave` / `on_tick`，均收 `RoomHookContext`）；注册表 `register_room_hook` / `get_room_hook` / `clear_room_hooks`
- **窄 ctx 方法名**：`add_exit` / `remove_exit` / `hide_exit` / `reveal_exit` / `schedule` / `clear_schedule` / `schedule_due` / `message_room` / `message_actor` / `get_state` / `set_state` / `move_entity`
- **只读快照字段**：`room_id` / `actor_id` / `params` / `tick` / `phase` / `is_day` / `is_night`
- **受限移动本体**：`relocate_entity(world, entity_id, to_room)`（`ctx.move_entity` 委托它；供票 10 SkillBehavior 直调）
- **组件**：`RoomHookBinding(hook_id, params)`（YAML 声明）；`RoomFreeState(data, schedules)`（钩子自由 KV + 延时戳）
- **YAML 字段形状**：
  ```yaml
  hooks:
    hook_id: <registered_id>
    params: { ... }   # 可选
  ```
- **UGC 拒绝**：`load_pack(..., pack_track=True)` 与旁路同级 `manifest.yaml` 检测；声明 `hooks` → `SceneLoadError`（与 validate 同路径）
- **挂载**：`wire_runtime` → `attach_room_hooks`；按实现方法按需订阅 `on_enter_room` / `on_leave_room` / `on_tick`
- **测试**：`engine/tests/test_room_hooks.py`（S0 + S2；测试内 `RecordingHook`，不进 `xingxiu_mechanics.yaml`）
- **code-review fix**（Wave 1）：注册表类型改为 `RoomHook`；`attach_room_hooks` 注册表缺钩子改 raise；补 CLI `--validate`/`--strict`、挂载路径异常传播、restore+`wire_runtime` 重挂测。
