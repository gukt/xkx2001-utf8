# 红队性能风险挑战：战斗与效果生命周期簇

> 角色：性能与可扩展性专家（红队）。对 Phase 1 产出（尤其 `03-engine-insights/performance-review.md` 与 `06-engine-critique/engine-comparison.md`）的性能结论进行对抗性质疑。
> 证据要求：每条质疑引用被质疑文件与段落 + 一手源码证据（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名）。
> 约束参照：CLAUDE.md 架构不变量第 1 条「单机 1000 在线 + 100 并发」。

---

## 0. 挑战总览

`performance-review.md` 的结论方向大体正确（识别了 `entities_in_room` 全量扫描、Effect 引擎缺失、`set_heart_beat` 节能缺失三个核心问题），但存在 **7 处系统性低估或遗漏**，使其在「1000 在线 + 100 并发」约束下的风险评估偏乐观。本文件逐条质疑并给出修正后的量级估计。

**质疑汇总**：

| # | 被质疑结论 | 质疑要点 | 修正后量级 |
|---|-----------|---------|-----------|
| 1 | 「50 对交战方每 tick 100 次 resolve_one_strike」 | 忽略 NPC 围攻 + 双向各一次 = 每对 2 次非 1 次；且 1000 在线时 NPC 参战使交战对数远超 50 | 100-200 对，200-400 次 resolve_one_strike |
| 2 | 「300,000 次 Position 实体扫描」 | 低估 Position 实体总数（LPC 6414 房间 + 1401 NPC），且 `_broadcast_round` 每对交战方调 `entities_in_room` 4 次非 2 次（双向各出手 + 各扫一次） | 60-120 万次扫描 |
| 3 | 「engine 无 Effect 引擎，无法评估开销」 | 放弃评估过于轻率；LPC 模式可推算补齐后的真实成本 | 每 Effect tick 数千次 handler 调用 + 递归伤害 + 广播 |
| 4 | 「死亡流程已去除同步存盘 IO」 | 忽略 `_spawn_loot_item` 的 9-spec CAPABILITIES 遍历 + `_grant_kill_exp` 的 `select_move` 全技能扫描；密集死亡时累积 | AE 死亡峰值时每 NPC 死亡 9N + M 次遍历 |
| 5 | 「`set_heart_beat` 节能是关键」 | 只指出缺失但未分析 ECS 架构下补齐的难度与代价；`AIController.tick_interval` 仍全量遍历 | 节能层本身有 O(N) 遍历开销 |
| 6 | 「tick 是命令驱动」 | 只分析了 2/6 个 ON_TICK 订阅者；遗漏 `_on_ai_tick` 全量 NPC 遍历 + nature/ferry/room_hooks | 6 个订阅者叠加每 tick 开销被低估 3 倍 |
| 7 | （未提及）GC 压力 | `entities_with` 每次创建新 set 对象，6 个订阅者 × 多次调用 = 海量临时对象 | 每 tick 数十个临时 set 对象 |

---

## 1. 质疑：战斗 tick 并发开销被低估——交战对数与 resolve_one_strike 次数

### 被质疑结论

`performance-review.md` §1.4 与 §2.2：
- §1.4：「1000 在线时若 30% 同时战斗（300 场），每 heart_beat interval 触发 300+ 次 do_attack。」
- §2.2：「50 对交战方每 tick 50 * 2 = 100 次 `resolve_one_strike`。」

### 质疑

**（a）交战对数估计偏低。** `performance-review.md` §2.2 用「50 对交战方」（100 并发 / 2），但 LPC 战斗并非只有玩家对玩家。`inherit/char/char.c:135-139` 的 `chat()` 对所有 NPC 每 tick 调用，`feature/attack.c:229-258 init()` 的 `auto_fight` 让 aggressive NPC 主动开战（`combatd.c:846-962` 四种类型）。MVP 场景清单（CLAUDE.md 架构不变量 7）含「野外遇敌」「门派」「组队围攻」，意味着大量 NPC-玩家战斗同时存在。

LPC 源码体量：`d/` 下 6414 个房间文件 + `d/*/npc/` 下 1401 个 NPC 文件（`find d -name "*.c" -path "*/npc/*" | wc -l`）。即使只有 10% NPC 同时与玩家交战，也有 140 场 NPC-玩家战斗 + 玩家间战斗，远超 50 对。

**修正估计**：1000 在线 + 100 并发时，同时交战对数应为 **100-200 对**（含 NPC 参战），而非 50 对。

**（b）`resolve_one_strike` 调用次数翻倍被算对了一半。** `performance-review.md` §2.2 说「每对双方各出手一次」即 50 * 2 = 100 次。验证 `_on_combat_tick`（`combat_system.py:248-273`）：

```python
resolve_one_strike(world, entity, opponent, rng=combat.rng)      # :271
if world.has_component(entity, Engaged) and world.has_component(opponent, Engaged):
    resolve_one_strike(world, opponent, entity, rng=combat.rng)  # :273
```

确实是双向各一次。但 `performance-review.md` §2.3 在估算 `_broadcast_round` 开销时只算「attacker 和 defender 各扫一次 = 2 次 `entities_in_room`」，忽略了 **每次 `resolve_one_strike` 内部都调 `_broadcast_round`**（`combat_system.py:164`）。所以每对交战方每 tick 的 `entities_in_room` 调用次数 = 2 次 `resolve_one_strike` × 2 次 `entities_in_room`（attacker + defender 各扫）= **4 次**，而非 2 次。

**修正估计**：100-200 对交战方 × 4 次 `entities_in_room` = **400-800 次** `entities_in_room` 调用/每 tick（非 performance-review 的 100 次）。

**（c）LPC heart_beat 每 tick 的实际工作量被简化。** `performance-review.md` §1.1 列出了 `char.c:60-169` 的 8 个步骤，但性能分析时只关注了 `attack()` + `update_condition()`。实际每 living 每 tick 还执行：
- `char.c:70-81`：频道刷屏检测 + `load_object` 惰性加载 NPC（aqingsao）——**含跨对象 `load_object` 开销**。
- `char.c:84-97`：neili/jingli/jing 三属性 clamp——每个属性一次 `query` + `set`。
- `char.c:118-121`：`is_busy()` 判定 + 可能的 `continue_action()`。
- `char.c:124-130`：wimpy 逃跑检定——`query("env/wimpy")` + 比例计算 + 可能的 `GO_CMD->do_flee`。
- `char.c:135-139`：NPC `chat()`——含 `exert_function` 内功自动恢复（`npc.c:100-107` 三次资源比例计算）+ `random_move` 可能的房间解析。
- `char.c:149`：`heal_up()`——每 tick 调用，含 water/food 递减 + 四属性恢复计算 + `eff_*` 缓慢自愈。

即每 living 每 tick 的真实工作量是 **~10 个操作序列**，而非「attack + update_condition」两项。1000 在线 + N 个活跃 NPC 时，单次 heart_beat 的总操作次数 = (1000 + N_active_npc) × ~10。

### 来源

- 被质疑：`performance-review.md` §1.4（行 70「300+ 次 do_attack」）、§2.2（行 126「50 * 2 = 100 次」）、§2.3（行 155「50 * 2 * 3000 = 300,000 次」）。
- LPC 证据：`inherit/char/char.c:60-169` heart_beat 全量步骤；`feature/attack.c:229-258 init()` auto_fight；`adm/daemons/combatd.c:846-962` 四种 auto_fight；`inherit/char/npc.c:100-107` NPC 内功自动恢复。
- engine 证据：`combat_system.py:271-273` 双向 `resolve_one_strike`；`combat_system.py:164` `_broadcast_round` 在 `resolve_one_strike` 内部调用。

---

## 2. 质疑：全员战斗广播——entities_in_room 全量扫描量级被低估

### 被质疑结论

`performance-review.md` §2.3：

> 「假设 1000 在线玩家 + 2000 NPC = 3000 个 Position 实体。每次 `_broadcast_round` 扫描 3000 个实体（实际 attacker 和 defender 各扫一次 = 6000 次），每次 `require_component` 是一次 dict 查找。50 对同时交战时，每 tick 50 * 2 * 3000 = 300,000 次 Position 实体扫描 + room 比对。」

### 质疑

**（a）Position 实体总数被低估。** `performance-review.md` 假设 3000 个 Position 实体（1000 玩家 + 2000 NPC）。但：
- LPC 源码有 1401 个 NPC 文件（`find d -name "*.c" -path "*/npc/*" | wc -l`），6414 个房间。一个活跃的 MUD 世界，NPC 会随 spawn/despawn 动态存在。
- `world.py:225` docstring 明确「玩家与 NPC 都用 `Position` 表达'在房间里'（物品不挂，被 Container 持有）」——物品不占 Position，但所有活跃 NPC 都占。
- MVP 场景含「少林寺」（门派）+ 「扬州」（城镇丰富子集）+ 野外区域，这些场景的 NPC 密度不低。保守估计活跃 NPC 数 3000-5000。

**修正的 Position 实体总数**：1000 玩家 + 3000-5000 NPC = **4000-6000 个 Position 实体**。

**（b）每对交战方的 `entities_in_room` 调用次数翻倍。** 见质疑 1(b)。`performance-review.md` 算 2 次/对，实际是 4 次/对（2 次 `resolve_one_strike` × 2 次扫描）。

**（c）`entities_in_room` 的内部开销被简化为「room 比对」。** 验证 `world.py:217-232`：

```python
def entities_in_room(self, room, *, exclude=None):
    for entity in self.entities_with(Position):     # :227 -- 先创建一个 set 拷贝
        if entity == exclude: continue
        if self.require_component(entity, Position).room != room:  # :230 -- 逐个 dict 查找
            continue
        yield entity
```

`entities_with(Position)`（`world.py:210-215`）的实现：
```python
matching_sets = [set(self._components.get(t, {})) for t in component_types]  # :214
return iter(set.intersection(*matching_sets))                                # :215
```

即每次 `entities_in_room` 调用：
1. 创建一个新 set 对象（O(N) 拷贝全部 Position 实体 id）
2. 迭代该 set，每个实体做一次 `require_component(Position).room != room` dict 查找 + 字符串/对象比较

单组件查询时 `set.intersection` 实际是对单 set 的拷贝（无交集计算），但仍创建新 set 对象。

**修正后的量级**：
- 4000-6000 个 Position 实体
- 100-200 对交战方 × 4 次 `entities_in_room` = 400-800 次调用
- 每次扫描 4000-6000 实体
- 总扫描次数 = 400-800 × 4000-6000 = **160 万 - 480 万次 Position 实体扫描 + room 比对/每 tick**

这比 `performance-review.md` 的 30 万次高出 **5-16 倍**。

**（d）LPC 的 `message_vision` 并非「零成本」。** `performance-review.md` §2.3 称「LPC 的 `message_vision` 只遍历 `all_inventory(environment())`（单个房间的物品列表，通常几十个对象）」。但 `receive_message`（`feature/message.c:11-54`）对每个接收者执行：block_msg 判定（`:41`）、blind condition 随机丢弃（`:44`）、语言转换（`:46-47`）、输入态缓冲（`:49-53`）。即每条消息 × 每个接收者都有固定处理开销，LPC 的局部广播在密集战斗时也有可观的 per-recipient 成本。

### 来源

- 被质疑：`performance-review.md` §2.3（行 143-157）。
- engine 证据：`world.py:210-215` `entities_with`（set 创建）；`world.py:217-232` `entities_in_room`（全量扫描 + `require_component`）；`combat_system.py:164` `_broadcast_round` 在 `resolve_one_strike` 内；`combat_system.py:291-299` `_broadcast_round` 调 `entities_in_room` 两次（attacker + defender）。
- LPC 证据：`feature/message.c:11-54` `receive_message` per-recipient 处理链。

---

## 3. 质疑：Effect 遍历峰值开销——「无法评估」过于轻率

### 被质疑结论

`performance-review.md` §2.4：

> 「engine 的 `conditions.py` 是通用布尔条件表达式求值器……**完全不是 LPC `condition.c` 的时效性 Effect 引擎**……性能维度评估：**无法评估 Effect 遍历开销，因为 engine 根本未实现 Effect 引擎**。这不是性能隐患而是功能缺失。」

§3.3：

> 「1000 在线时若平均每人挂 3 个 condition，每 Effect tick 遍历 3000 个 condition daemon 调用，每个含伤害结算与广播。」

### 质疑

**（a）放弃推算是不合理的。** `abstraction-options.md` §3 方向 C 已明确 Effect 引擎的形状（薄调度器 + 题材包 EffectHandler），且 ADR-0004 已拍板归属引擎。既然 Effect 引擎**必定要建**，红队的职责正是**前瞻性预警其建成后的性能风险**，而非以「未实现」为由跳过。

**（b）Effect tick 的真实开销远超「3000 次 daemon 调用」。** 验证 LPC `feature/condition.c:21-69 update_condition` 的调用链：

每个 condition daemon 的 `update_condition(me, info)` 内部执行（以 `bt_poison.c:7-42` 为例）：
1. `eff_jing` 三档分级播报（`:11-26`，3 次 `message`/`tell_object` 广播）
2. `receive_wound("jing", damage/2, ...)`（`:33`）——内部调 `damage.c:39-66`：`set_temp` + `set("eff_jing", ...)` + `set_heart_beat(1)` + 可能触发数值修改
3. `receive_damage("jingli", damage/2, ...)`（`:34`）——同上开销
4. `apply_condition("bt_poison", duration-1)`（`:36`）——mapping 写入
5. `query_skill("poison")` 技能查询（`:36`）——跨对象 `call_other`

即**单个 Effect daemon 单次 tick 的真实开销 ≈ 2 次伤害结算 + 3 次广播 + 1 次 skill 查询 + 1 次 mapping 写入**，远非「一次 daemon 调用」。

`performance-review.md` §3.3 估算「3000 个 condition daemon 调用」，但每个调用实际展开为 **~7 个子操作**。真实开销 = 3000 × 7 = **~21,000 个子操作/每 Effect tick**。

**（c）Effect tick 频率缺失是延迟问题而非性能豁免。** `performance-review.md` §1.3 正确指出 LPC 用 `tick = 5 + random(10)`（`char.c:141-142`）稀释 Effect 频率。但 `abstraction-options.md` §8 未决问题 2 明确：「engine 是否复用 tick 节流还是每 tick 全量遍历 Effect？」

如果 engine 选择**每 tick 全量遍历**（无节流），Effect 遍历频率将比 LPC 高 6-15 倍。1000 在线 × 平均 3 Effect × 每 tick 遍历 = 3000 次 handler 调用/每 tick，且每次含 ~7 个子操作 = **~21,000 子操作/每 tick**。如果 tick 间隔 = 2 秒（LPC 标准），这 21,000 个操作必须在 2 秒内完成，CPU 占用显著。

**（d）Effect 的递归伤害触发链被忽略。** `bt_poison.c:33` 调 `receive_wound` -> `damage.c:39-66` -> `set_heart_beat(1)` + 数值修改。`hanbing_damage.c:23-24` 同理。这意味着**每个 Effect tick 可能触发新的伤害事件**，进而触发死亡判定（`char.c:100-115`）-> `unconcious()`/`die()` -> 死亡流程开销（见质疑 4）。Effect tick 不是独立的开销域，它与战斗 tick、死亡流程**形成递归触发链**。

engine 若实现 Effect 引擎，`EffectHandler.update` 调 `apply_damage` -> `apply_combat_result` -> 可能触发 `handle_vitals_depleted` -> 死亡流程。单次 Effect tick 可能级联触发多个死亡流程。

### 来源

- 被质疑：`performance-review.md` §2.4（行 159-168「无法评估」）、§3.3（行 238-244「3000 个 condition daemon 调用」）。
- LPC 证据：`feature/condition.c:21-69 update_condition`；`kungfu/condition/bt_poison.c:33-34` 递归 `receive_wound`/`receive_damage`；`kungfu/condition/hanbing_damage.c:23-24`；`feature/damage.c:39-66 receive_wound` 含 `set_heart_beat(1)`；`inherit/char/char.c:141-144` tick 节流。
- 设计输入：`abstraction-options.md` §3 方向 C（EffectEngine 薄调度器 + EffectHandler）、§8 未决问题 2（节流策略未定）。

---

## 4. 质疑：死亡流程峰值开销——被简化的掉落与经验结算

### 被质疑结论

`performance-review.md` §2.5：

> 「engine 死亡流程已去除 LPC 的同步存盘 IO（`die()` 内 `save()`），性能优于 LPC；但 `_spawn_loot_item` 的 CAPABILITIES 遍历在密集死亡时有累积开销。」

### 质疑

**（a）`_spawn_loot_item` 的 CAPABILITIES 遍历开销被轻描淡写。** 验证 `death_flow.py:373-395`：

```python
def _spawn_loot_item(world, template_key, room):
    from openmud.capabilities import CAPABILITIES
    raw = world.item_templates.get(template_key)
    ...
    item = world.create_entity()                     # :380 -- 创建实体
    world.add_component(item, Identity(...))         # :382
    world.add_component(item, Description(...))      # :384-386
    for spec in CAPABILITIES:                        # :389 -- 遍历全部 9 个 spec
        component = spec.from_yaml(raw, ...)         # :390 -- 每 spec 一次 YAML 解析
        if component is not None:
            world.add_component(item, component)      # :392
    floor = world.require_component(room, Container) # :394
    floor.items.add(item)                            # :395
```

验证 `capabilities.py:393-453`：`CAPABILITIES` 列表含 **9 个 `CapabilitySpec`**（Stackable/Valuable/Equippable/Consumable/LiquidContainer/ItemFlags/ItemContainer/Weight/ItemTags）。每件掉落物 = 9 次 `from_yaml` 调用 + 最多 9 次 `add_component`。

**死亡峰值估计**：门派战/AOE 场景下，假设 20 个 NPC 同时死亡，每个掉 3 件物品 = 60 件物品 × 9 spec = **540 次 `from_yaml` + `add_component` 调用**，全部在同一个 tick 内同步执行。`from_yaml` 每个 spec 内部还做 YAML dict 查询 + 组件构造，非零成本。

**（b）`_grant_kill_exp` 的 `select_move` 全技能扫描被完全忽略。** 验证 `death_flow.py:398-408`：

```python
def _grant_kill_exp(world, killer_id, amount):
    ...
    move = select_move(world, killer_id)  # combat_system.py:198-224
```

`select_move`（`combat_system.py:198-224`）遍历 `SkillLevels.levels` dict 的**全部已学技能**，对每个技能遍历其**全部招式**（`SkillData.moves`）查最高 force。即每个 NPC 死亡都触发一次** killer 的全技能 × 全招式扫描**。

如果一个 killer 学了 10 个技能，每技能 5 个招式 = 50 次招式比较。20 个 NPC 同时被同一 killer 击杀 = **1000 次招式比较**，在同一 tick 内。`performance-review.md` 完全未提及此开销。

**（c）LPC 死亡的同步存盘 IO 被 engine 的周期存盘「替代」而非「去除」。** `performance-review.md` §2.5 称「engine 当前无同步存盘 IO（存档走 `save_fn` 周期触发，`tick.py:84-85`）」。验证 `tick.py:73-85`：

```python
def advance(self):
    self._tick += 1
    if self._world is not None:
        self._world.events.dispatch(ON_TICK, ...)    # :83 -- 先分发 tick
    if self._tick % self._interval == 0:             # :84 -- 每 10 tick 存档
        self._save()
```

`DEFAULT_SAVE_INTERVAL = 10`（`tick.py:39`）。即每 10 个 tick 触发一次全量存档。如果 tick 是时间驱动（2 秒/tick），则每 20 秒一次全量存档。1000 在线玩家的存档大小不可忽视——`world.py:234 all_entities()` 遍历全部实体序列化。密集死亡场景下，10 个 tick 内可能积累大量状态变更，存档时一次性序列化全部实体 + 组件，这是**延迟的 IO 峰值**，只是被分摊到周期边界而非即时触发。

LPC 的 `die()` 内 `save()`（`damage.c:245`）是**单玩家存档**（只存死者），而 engine 的周期存档是**全量存档**（存所有实体）。两者粒度不同，engine 的周期存档在 1000 在线时的单次开销可能**大于** LPC 的单玩家 `save()`。

### 来源

- 被质疑：`performance-review.md` §2.5（行 171-191）。
- engine 证据：`death_flow.py:373-395 _spawn_loot_item`（9 spec 遍历）；`death_flow.py:398-408 _grant_kill_exp` 调 `select_move`；`combat_system.py:198-224 select_move`（全技能×全招式扫描）；`capabilities.py:393-453 CAPABILITIES`（9 个 spec）；`tick.py:39,84 DEFAULT_SAVE_INTERVAL=10` + `world.py:234 all_entities()` 全量序列化。
- LPC 证据：`damage.c:245 save()` 单玩家存档。

---

## 5. 质疑：set_heart_beat 节能机制——ECS 架构下补齐的难度与代价

### 被质疑结论

`performance-review.md` §2.6：

> 「engine 没有 LPC `set_heart_beat(0)` 的按需启停 tick 机制……LPC 的 `set_heart_beat` 机制让空闲 NPC/玩家完全退出 tick 循环（`char.c:157`），1000 在线时只有活跃的 living 消耗 CPU。engine 若改为时间驱动 tick，将面临全量实体每 tick 都被遍历的开销，缺少按需启停的节能层。」

结论 §4.1：

> 「LPC 的 `set_heart_beat` 节能机制是 1000 在线可行的关键。engine 无等效机制，改时间驱动 tick 时需补齐。」

### 质疑

**（a）`performance-review.md` 指出了缺失但未分析补齐的代价。** 在 ECS 架构下实现「按需启停」有两条路径，各有显著代价：

**路径 1：维护「活跃实体集合」**——只有战斗/挂 Effect/昏迷的实体进 tick 队列。
- 代价：每次 `Engaged`/`Unconscious`/Effect 组件增删时都要同步更新活跃集合。`combat_system.py:93-114 try_engage` + `clear_engagement` + `death_flow.py` 的 `Unconscious` 挂载/移除 + 未来的 `apply_effect`/`clear_effect` 都要 hook 进活跃集合维护。这是一**全局一致性约束**，任何遗漏 tick 管理的组件增删都会导致实体「卡在活跃集合」或「漏 tick」。
- 验证：engine 已有的 `AIController.tick_interval`（`ai.py:171-173`）是「每 tick 遍历全部 AIController 但按 interval 跳过」，**不是**「只遍历活跃 NPC」。即 engine 现有的唯一节能先例仍是 O(N) 全量遍历 + 条件跳过，并非真正的「退出 tick 循环」。

**路径 2：每 tick 全量遍历 + per-entity 跳过标志**——即 `AIController.tick_interval` 模式推广到战斗/Effect/昏迷。
- 代价：仍是 O(N) 遍历全部实体，只是每个实体多一次 flag 检查。1000 玩家 + 5000 NPC = 6000 实体 × 每 tick 检查 = 6000 次 flag 检查。这比 LPC 的「空闲 living 完全退出 heart_beat」差一个数量级——LPC 空闲 living 的 heart_beat 直接不执行，零开销；engine 路径 2 仍需遍历 + 检查。

**（b）LPC 的 `set_heart_beat(0)` 本身有隐含的一致性风险。** `char.c:149-157` 的关闭条件是 `!is_fighting() && !interactive() && (cnd_flag & CND_NO_HEAL_UP || !heal_up())`。但 `receive_damage`（`damage.c:34`）和 `receive_wound`（`damage.c:63`）都调 `set_heart_beat(1)` 强制重开——**即任何外部伤害都能唤醒已关闭的 heart_beat**。这意味着 `set_heart_beat(0)` 并非可靠的「完全退出」，而是「随时可能被伤害事件唤醒」的脆弱状态。LPC 靠 `set_heart_beat(1)` 在所有伤害入口的显式调用来维持一致性，engine 若模仿，需在所有 `apply_damage` 路径上同样显式标记活跃——这是**跨模块的隐式契约**，违反 ECS 的显式组件模型。

**（c）`performance-review.md` 的结论「set_heart_beat 节能是 1000 在线可行的关键」暗示补齐即可解决，但未量化补齐后的残余开销。** 即使实现路径 1（活跃集合），活跃集合在 100 并发战斗场景下仍含 100-200 个交战实体 + 挂 Effect 的实体（可能 500+）+ 昏迷实体。活跃集合本身可能有 700-1000 个实体，每 tick 全部遍历。这不是「只有活跃的消耗 CPU」的零开销，而是「活跃集合的 O(M) 遍历」（M << N 但 M 仍可观）。

### 来源

- 被质疑：`performance-review.md` §2.6（行 193-200）、§4.1（行 250）。
- engine 证据：`ai.py:160-173 _on_ai_tick`（全量遍历 AIController + interval 跳过，非退出）；`combat_system.py:248-273 _on_combat_tick`（全量遍历 Engaged，无跳过）；`death_flow.py:417-429 _on_unconscious_tick`（全量遍历 Unconscious，无跳过）；`components.py:362-371 AIController.tick_interval`（唯一的 interval 跳过先例）。
- LPC 证据：`inherit/char/char.c:149-157 set_heart_beat(0)` 关闭条件；`feature/damage.c:34,63 set_heart_beat(1)` 强制重开；`feature/attack.c:44 fight_ob` 调 `set_heart_beat(1)`。

---

## 6. 质疑：ON_TICK 多订阅者叠加开销被忽略

### 被质疑结论

`performance-review.md` §2 只分析了 `_on_combat_tick`（§2.2）和 `_on_unconscious_tick`（§2.6 提及）两个 ON_TICK 订阅者。

### 质疑

**`performance-review.md` 遗漏了 4 个 ON_TICK 订阅者的开销。** 验证 `runtime.py:33-38` 的 attach 序列 + grep 全引擎 `register(ON_TICK`：

```
runtime.py:33  attach_nature(world, ...)        -> nature.py:443-444  register(ON_TICK, _on_tick_nature)
runtime.py:34  attach_ai_system(world)           -> ai.py:152-153      register(ON_TICK, _on_ai_tick)
runtime.py:35  attach_ferries(world)             -> ferry.py:47-48     register(ON_TICK, _on_ferry_tick)
runtime.py:36  attach_combat_system(world)       -> combat_system.py:85-86 register(ON_TICK, _on_combat_tick)
runtime.py:38  attach_unconscious_recovery(world)-> death_flow.py:413-414 register(ON_TICK, _on_unconscious_tick)
room_hooks.py:701                                  register(ON_TICK, _on_tick)
```

**共 6 个 ON_TICK 订阅者**，每 tick 全部执行。`performance-review.md` 只分析了 2 个。

**遗漏的开销**：

**（a）`_on_ai_tick`（`ai.py:160-182`）——最严重的遗漏。** 每 tick：
1. `entities_with(AIController)`——创建一个新 set（`world.py:214`），含全部 NPC 的 entity id。5000 NPC = 5000 元素 set 拷贝。
2. 遍历全部 NPC，每个做 `tick % interval` 跳过检查（`ai.py:171-173`）。
3. 未跳过的 NPC：`get_component(Behaviors)` + `_condition_context(world, room_id)` 构造（`ai.py:180`）+ 遍历 `behaviors.entries` 逐个 `_tick_behavior`。

即使 `tick_interval` 跳过 90% 的 NPC，**`entities_with(AIController)` 的 set 创建仍是每 tick 全量**（5000 元素）。6 个 ON_TICK 订阅者中，`_on_ai_tick` 的 set 创建开销最大（NPC 数 >> 交战实体数 >> 昏迷实体数）。

**（b）`_on_tick_nature`（`nature.py:452-457`）**——推进 NatureState（时辰/天气）。单次开销小（无实体遍历），但每 tick 执行。

**（c）`_on_ferry_tick`（`ferry.py`）**——渡船状态推进。开销小但每 tick 执行。

**（d）`room_hooks.py:701 _on_tick`**——房间 hook tick。未读实现细节，但每 tick 执行。

**修正后的每 tick 总开销**：

| 订阅者 | 每 tick 核心开销 | 量级 |
|--------|-----------------|------|
| `_on_combat_tick` | `entities_with(Engaged)` set + 遍历交战对 + `resolve_one_strike` × 2 × N 对 | 100-200 对 × ~13 get_component + broadcast |
| `_on_unconscious_tick` | `entities_with(Unconscious)` set + 遍历昏迷实体 | 昏迷实体数（小） |
| **`_on_ai_tick`** | **`entities_with(AIController)` set（5000 元素） + 全量遍历 + interval 跳过** | **5000 元素 set 创建 + 5000 次跳过检查** |
| `_on_tick_nature` | NatureState 推进 | 小 |
| `_on_ferry_tick` | 渡船状态 | 小 |
| `room_hooks._on_tick` | 房间 hook | 未量化 |

**`_on_ai_tick` 的 5000 元素 set 创建 + 全量遍历**是 `performance-review.md` 完全未提及的最大单 tick 开销之一。它与 `_on_combat_tick` 的交战对遍历叠加，使每 tick 的 `entities_with` 调用从 2 次（combat + unconscious）变为 **至少 4 次**（+ AIController + Position in broadcast），每次创建不同的 set 对象。

### 来源

- 被质疑：`performance-review.md` §2（行 98-211，只分析 combat + unconscious）。
- engine 证据：`runtime.py:33-38` 6 个 attach 调用；`ai.py:160-182 _on_ai_tick`（`entities_with(AIController)` 全量遍历）；`nature.py:452-457`；`ferry.py:47-48`；`room_hooks.py:701`；`combat_system.py:85-86`；`death_flow.py:413-414`。

---

## 7. 质疑：GC 压力与临时对象开销——完全未分析

### 被质疑结论

`performance-review.md` 未提及 GC 压力。

### 质疑

**`entities_with` 的 set 创建是 GC 压力的主要来源，`performance-review.md` 完全未分析。**

验证 `world.py:210-215`：
```python
def entities_with(self, *component_types):
    matching_sets = [set(self._components.get(t, {})) for t in component_types]  # :214
    return iter(set.intersection(*matching_sets))                                # :215
```

每次调用 `entities_with(T)` 创建 **1 个新 set 对象**（单组件时是 `set(dict.keys())` 拷贝）。多组件查询创建多个 set + 交集结果 set。

**每 tick 的 `entities_with` 调用次数**（保守估计）：

| 调用方 | 调用次数/tick | set 大小 |
|--------|-------------|---------|
| `_on_combat_tick` `entities_with(Engaged)` | 1 | 100-200（交战实体） |
| `_on_combat_tick` 内 `_broadcast_round` `entities_with(Position)` | 400-800 次 | 4000-6000（全部 Position） |
| `_on_unconscious_tick` `entities_with(Unconscious)` | 1 | 小 |
| `_on_ai_tick` `entities_with(AIController)` | 1 | 3000-5000（全部 NPC） |
| `_on_ai_tick` 内 `_condition_context` 可能的查询 | 未量化 | - |

**保守估计每 tick 创建 400-800 + 2 = ~400-800 个临时 set 对象**（主要是 `_broadcast_round` 的 `entities_in_room` -> `entities_with(Position)`）。每个 set 含 4000-6000 个元素 = **400-800 × 4000-6000 = 160 万 - 480 万元素的临时拷贝/每 tick**。

Python 的 GC 对大量短生命周期对象有代际回收开销。CPython 的分代 GC 默认每 700 次分配触发一次第 0 代回收（`gc.get_threshold()` 默认 `(700, 10, 10)`）。每 tick 创建 400-800 个 set 对象，每个 set 内部又是 dict + 列表，实际分配次数远超 700，**每 tick 可能触发多次 GC 回收**。在 2 秒 tick 间隔下，GC 回收的 CPU 占用不可忽略。

LPC 的 MudOS 是 C 实现，`all_inventory(environment())` 返回的是对象指针数组，无堆分配（无 GC 压力）。engine 的 Python ECS 架构在这一点上有**结构性劣势**。

### 来源

- 被质疑：`performance-review.md` 全文（未提及 GC）。
- engine 证据：`world.py:214 set(self._components.get(t, {}))` 每次 `entities_with` 创建新 set；`combat_system.py:297 entities_in_room` 被 `_broadcast_round` 调 400-800 次/tick；`ai.py:169 entities_with(AIController)` 全量 set。

---

## 8. 修正后的 1000 在线 + 100 并发性能风险矩阵

| 风险点 | `performance-review.md` 估计 | 红队修正估计 | 倍数 | 来源 |
|--------|------------------------------|-------------|------|------|
| 交战对数 | 50 对 | 100-200 对（含 NPC 参战） | 2-4× | 质疑 1(a) |
| `resolve_one_strike` 次/tick | 100 | 200-400 | 2-4× | 质疑 1(b) |
| `entities_in_room` 调用/tick | 100（50×2） | 400-800（100-200×4） | 4-8× | 质疑 1(b)+2(b) |
| Position 实体总数 | 3000 | 4000-6000 | 1.3-2× | 质疑 2(a) |
| Position 扫描次/tick | 30 万 | 160 万-480 万 | 5-16× | 质疑 2(c) |
| Effect tick 子操作 | 3000 daemon 调用 | ~21,000 子操作（含递归伤害+广播） | 7× | 质疑 3(b) |
| ON_TICK 订阅者 | 2 个分析 | 6 个（含 `_on_ai_tick` 5000 NPC 遍历） | 3× | 质疑 6 |
| 临时 set 对象/tick | 未分析 | 400-800 个（含 160-480 万元素拷贝） | 新增 | 质疑 7 |
| 死亡峰值开销 | 仅 CAPABILITIES 遍历 | + `select_move` 全技能扫描 + 周期全量存档 | 新增 | 质疑 4 |

---

## 9. 结论

1. **`performance-review.md` 的核心结论方向正确但量级系统性偏低 3-16 倍**。最严重的低估是 `_broadcast_round` 的 `entities_in_room` 扫描次数（少算 4-8 倍）与 Position 实体总数（少算 1.3-2 倍），叠加后真实扫描量级是 160-480 万次/tick 而非 30 万次。

2. **最被低估的单项开销是 `_on_ai_tick` 的全量 NPC 遍历**（`ai.py:160-182`）。`performance-review.md` 完全未分析此 ON_TICK 订阅者。5000 NPC 的 `entities_with(AIController)` set 创建 + 全量遍历是每 tick 的固定开销，与战斗强度无关——即使无人战斗，AI tick 仍每 tick 扫描全部 NPC。

3. **Effect 引擎补齐后的性能风险被「无法评估」一笔带过**。LPC 的 Effect 递归触发伤害 + 广播模式（`bt_poison.c:33-34`）意味着每个 Effect tick 的真实开销是 mapping 遍历的 ~7 倍。若 engine 不复用 LPC 的 tick 节流（`char.c:141-142` 每 5-15 tick 才 update），Effect 遍历频率将比 LPC 高 6-15 倍。

4. **`set_heart_beat` 节能机制在 ECS 下补齐的代价被低估**。engine 现有的唯一节能先例 `AIController.tick_interval` 仍是 O(N) 全量遍历 + 条件跳过，非 LPC 的「完全退出 tick 循环」。真正的活跃集合维护是跨模块隐式契约，与 ECS 显式组件模型冲突。

5. **GC 压力是 engine Python ECS 架构的结构性劣势，`performance-review.md` 完全未分析**。每 tick 400-800 个临时 set 对象 × 4000-6000 元素拷贝 = 160-480 万元素的短生命周期对象，在 CPython 分代 GC 下每 tick 可能触发多次回收。LPC 的 C 实现 `all_inventory` 无此开销。
