# 战斗与效果生命周期簇 - 性能与可扩展性评估

> 角色：性能与可扩展性专家。基于一手 LPC 源码（唯一真相源）与 engine 已建模块（批判对照对象），评估战斗/Effect/死亡三系统在「单机 1000 在线 + 100 并发」约束（CLAUDE.md 架构不变量第 1 条）下的性能特征与隐患。每条结论标注来源文件路径 + 函数/对象名或 engine 模块 + 行号/类名。

---

## 1. LPC 侧性能特征（基准画像）

### 1.1 heart_beat 驱动全量 living 的 tick 密度

LPC 采用固定时间间隔的 heart_beat 机制驱动所有 living 对象。每个角色在 `setup()` 时即 `set_heart_beat(1)` 开启心跳（`inherit/char/char.c:53`），此后每过一个 heart_beat interval（MudOS 配置的固定秒数，通常 2 秒）执行一次 `heart_beat()`（`inherit/char/char.c:60`）。

`heart_beat()` 每个 tick 对每个 living 依次执行（`inherit/char/char.c:60-169`）：

1. **命令计数清理 + 频道刷屏检测**（`:70-81`）：仅 `userp` 时执行，含 `load_object` 惰性加载 NPC（aqingsao）。
2. **数值钳制**（`:84-97`）：neili/jingli/jing 上限修正。
3. **死亡判定**（`:100-104`）：`eff_qi < 0 || eff_jing < 0` -> `remove_all_enemy()` + `die()`。
4. **昏迷/二次死亡判定**（`:108-115`）：`qi < 0 || jing < 0 || jingli < 0` -> `remove_all_enemy()` + `unconcious()`/`die()`。
5. **忙碌处理或战斗**（`:118-133`）：`is_busy()` 时 `continue_action()`；否则 wimpy 逃跑判定 + `attack()`。
6. **NPC 闲聊**（`:135-139`）：`!userp` 时 `chat()`，可能 `destruct(this_object())`。
7. **tick 计数器**（`:141-142`）：`tick--` 到 0 时重置为 `5 + random(10)`，执行 `update_condition()` + `heal_up()` + 空闲判定。
8. **年龄/空闲超时**（`:165-168`）：仅 interactive 玩家。

关键密度估算：**1000 在线玩家 + 大量 NPC**，每 heart_beat interval 全量遍历。步骤 1-6 对每个 living 都跑，其中 `attack()`（`feature/attack.c:208-224`）每 heart_beat 调一次 `clean_up_enemy()`（遍历 enemy 列表，`feature/attack.c:64-75`）+ `select_opponent()`（`feature/attack.c:79-88`，`random(MAX_OPPONENT=4)` 选 1 个）+ `COMBAT_D->fight()`。即每个参战 living 每 interval 触发一次完整战斗结算。

### 1.2 set_heart_beat 启停机制（节能设计）

LPC 有按需启停 heart_beat 的节能机制，是控制 tick 密度的关键：

- **伤害触发开启**：`receive_damage()`（`feature/damage.c:34`）和 `receive_wound()`（`feature/damage.c:63`）均调用 `set_heart_beat(1)` 强制开启心跳。`fight_ob()`（`feature/attack.c:44`）也调 `set_heart_beat(1)`。
- **和平时关闭**：`heart_beat()` 末尾（`inherit/char/char.c:149-157`），当 `!is_fighting() && !interactive()` 且房间内无 interactive 对象时，`set_heart_beat(0)` 关闭心跳，停止 tick。
- **条件驱动保持**：`update_condition()` 返回 `CND_CONTINUE` 标志（`feature/condition.c:62-64`）时，`heart_beat` 会继续保持开启（`inherit/char/char.c:149` 的 `cnd_flag & CND_NO_HEAL_UP` 判定）。

这意味着：空闲 NPC（无战斗、无 condition、房间无人）的心跳被关闭，不消耗 CPU。只有受伤/战斗/挂 condition 的 living 才持续跑 heart_beat。这是 LPC 在数千 living 下仍可运行的关键节能设计。

### 1.3 Effect 遍历开销（condition.c update_condition）

`update_condition()`（`feature/condition.c:21-69`）遍历 `conditions` mapping：

- 对每个 condition 调 `find_object(CONDITION_D(cnd[i]))`（`:36`）查找对应 daemon 对象；未加载时 `catch(call_other(CONDITION_D(cnd[i]), "???"))`（`:38`）触发加载。
- 加载成功后 `call_other(cnd_d, "update_condition", this_object(), conditions[cnd[i]])`（`:62`）执行 Effect 逻辑。
- daemon 返回值不含 `CND_CONTINUE` 时 `map_delete` 移除该 condition（`:63`）。

**源码注释显式警告性能风险**（`feature/condition.c:15-19`）：

> "This function is called by heart_beat to update 'continously active' conditions. These conditions will be saved as well. Because such type of conditions costs heart beat evaluation time, don't make player got too much this kind of conditions or you might got lots of 'Too long evaluation' error message in the log file."

Effect 遍历的频率被 tick 计数器稀释：`update_condition()` 不是每 heart_beat 调用，而是每 `5 + random(10)` 次 heart_beat 调一次（`inherit/char/char.c:141-142` 的 `tick` 计数器）。即在 ~5-14 个 heart_beat interval 后才遍历一次 conditions。这降低了单次遍历的频率密度，但代价是 Effect 触发有最高约 14 个 interval 的延迟。

Effect daemon 数量：`kungfu/condition/` 目录下约 70 个 condition 文件（含 `bt_poison.c`/`chilian_poison.c`/`hanbing_damage.c`/`drunk.c`/`blind.c`/`embedded.c`/`*_jail` 等）。每个是独立 daemon 文件，首次 `call_other` 触发 `load_object` 带来的编译/加载开销，后续调用走已加载对象。单个 condition daemon 的 `update_condition` 实现开销差异大：`bt_poison.c`（42 行）含 2 次 `receive_wound`/`receive_damage`（触发 `set_heart_beat(1)` + 数值修改）+ 多次 `message`/`tell_object` 广播；`hanbing_damage.c`（31 行）类似含 `receive_damage`/`receive_wound`。**每个 Effect tick 内部会递归触发伤害与广播**，实际开销远超一次 mapping 遍历。

### 1.4 战斗 daemon 单次结算开销（s_combatd.c do_attack）

`do_attack()`（`adm/daemons/s_combatd.c:294-679`）是单次攻击结算核心，开销极重：

1. **选技能 + reset_action**（`:316-339`）：`me->reset_action()`（`feature/attack.c:143-171`）内部可能 `call_other(SKILL_D(skill), "query_action", me, ob)` 跨对象调用 skill daemon。
2. **skill_power 三次方运算**（`:359`/`:366` 调 `skill_power`，定义 `:212-245`）：`power = (level*level*level) / 3`（`:237`），再乘 combat_exp / 30 * str/dex / 100 * jingli_bonus。每个 AP/DP/PP 各算一次，共三次三次方运算。
3. **多层 hit_ob 钩子调用**（命中分支 `:471-515`）：
   - force skill `SKILL_D(force_skill)->hit_ob()`（`:473`）
   - martial skill `SKILL_D(martial_skill)->hit_ob()`（`:501`）
   - weapon `weapon->hit_ob()` 或 `me->hit_ob()`（`:508-515`）
   - 每个都是 `call_other` 跨对象调用，可能返回 string/int/mapping 多态结果。
4. **damage 公式多层叠加**（`:451-538`）：base damage + action["damage"] bonus + skill bonus + damage_bonus(str) + force bonus + martial bonus + jiajin bonus + combat_exp defense_factor 循环递减（`:542-545` 的 while 循环）。
5. **message_vision 广播**（`:635`）：向房间内所有对象广播战斗文案（`replace_string` 替换 $N/$n/$l/$w 后调 `receive_message`，`feature/message.c:11-54`）。
6. **report_status**（`:647` 调 `:198-208`）：再两次 `message_vision` 广播状态。
7. **post_action + riposte**（`:661-678`）：`post_action` 钩子执行；riposte 分支可能**递归调用 `do_attack`**（`:673`/`:676`），最坏情况单次 fight 触发 2-3 次 do_attack。

`fight()`（`adm/daemons/s_combatd.c:686-743`）在 `heart_beat` -> `attack()` -> `COMBAT_D->fight()` 路径上调用 `do_attack`，且双手互博（pixie-jian/双手 prepare）可能**二次调用 `do_attack`**（`:700-714`/`:721-735`）。

单次完整战斗结算的开销量级：3 次三次方运算 + 3-5 次跨对象 call_other + 多次 message_vision 广播 + 可能递归。1000 在线时若 30% 同时战斗（300 场），每 heart_beat interval 触发 300+ 次 do_attack。

### 1.5 全员战斗广播开销

战斗消息分发的开销分两层：

- **战斗结算层**：`do_attack` 内 `message_vision(result, me, victim)`（`s_combatd.c:635`）+ `report_status`（`:647`）向房间内所有对象广播。`message_vision` 实现（simul_efun）遍历 `environment(me)` 的 `all_inventory`，对每个 interactive 对象调 `receive_message`（`feature/message.c:11-54`）。`receive_message` 内含 block_msg 判定（`:41`）、blind condition 随机丢弃（`:44`）、语言转换（`:46-47`）、输入态缓冲（`:49-53`）。
- **Effect 层**：condition daemon 内部的 `message("vision", ..., environment(me), ({me}))`（如 `bt_poison.c:11,16,21,26`）和 `tell_object(me, ...)`（如 `bt_poison.c:15,20,25`）也产生广播。多个 condition 同时 active 时，每个 condition daemon tick 都产生若干条广播。

多场战斗同时进行时，同一房间内的玩家会收到所有战斗的广播消息（即使未参与），导致消息量随房间内战斗场数线性增长。

### 1.6 死亡流程开销

`die()`（`feature/damage.c:152-253`）在死亡峰值时的开销：

1. `clear_condition()`（`:184`）：清空全部 conditions mapping（`feature/condition.c:105-108`）。
2. `COMBAT_D->announce(this_object(), "dead")`（`:187`）：`message_vision` 广播死亡文案（`s_combatd.c:854-867`）。
3. `COMBAT_D->death_penalty(this_object())`（`:190`，定义 `s_combatd.c:874-907`）：含 `victim->clear_condition()` + 多项数值扣减（combat_exp/potential/balance/shen/behavior_exp）+ **`victim->save()`**（`:905`）同步存盘 IO + `skill_death_penalty()`。
4. `COMBAT_D->killer_reward(killer, this_object())`（`:194`，定义 `s_combatd.c:910-972`）：含 `killer->killed_enemy()` + `CHANNEL_D->do_channel` 全服谣言广播 + `apply_condition("pker"/"killer", ...)` 挂 condition + `find_object`/`load_object` 惰性加载（`:943` 泰山封禅台）。
5. `log_file("PKILL_DATA"/"PLAYER_DEATH", ...)`（`:211-223`）：多次文件 IO 写死亡日志。
6. `CHAR_D->make_corpse()` + `corpse->move(environment())`（`:227-228`）：创建尸体对象 + 移动。
7. `this_object()->save()`（`:245`）：第二次同步存盘。
8. `this_object()->move(DEATH_ROOM)` + `DEATH_ROOM->start_death(this_object())`（`:247-248`）：移入地府 + 启动地府流程。

**死亡峰值风险**：大规模团战（如门派战）时多个玩家同时死亡，每个死亡流程含 2 次 `save()` 同步存盘 IO + 多次 `log_file` 文件 IO + 全服 `CHANNEL_D` 广播。IO 是阻塞操作，密集死亡时存盘队列与日志写入可能成为瓶颈。`unconcious()`（`feature/damage.c:105-135`）含 `call_out("revive", random(100 - query("con")) + 30)`（`:134`）注册延迟回调，苏醒时间随机化，昏迷态的 living 仍持续跑 heart_beat（因 condition/heal 驱动）。

---

## 2. engine 侧性能隐患（批判对照）

### 2.1 tick 驱动方式根本差异（最大架构风险）

engine 的 tick 驱动方式与 LPC 的固定时间间隔 heart_beat **根本不同**：

- `engine/src/openmud/tick.py:73-85`：`TickLoop.advance()` 由 CLI 每条命令推进 1 tick（docstring 明确："CLI 每条命令推进 1 tick，即约每 10 条命令存一次"）。
- `engine/src/openmud/tick.py:80-83`：`advance` 内 `self._tick += 1` 后分发 `ON_TICK` 事件给订阅者。
- 战斗 tick（`combat_system.py` 的 `_on_combat_tick`）挂在 `ON_TICK` 上（`combat_system.py:85-86`），只有 `advance()` 被调用时才触发。

**这意味着战斗回合只在有玩家输入命令时推进**。空闲时（无命令输入）完全不跑 tick，战斗不推进，Effect 不衰减，昏迷不苏醒。这与 LPC 的实时自动回合制（每 2 秒双方自动出手）完全不同。

性能影响：当前架构下**不存在"1000 在线时每 N 秒全量 tick"的开销**，因为 tick 由命令驱动而非时间驱动。但这是架构能力缺失而非性能优势——100 并发场景下若需实时战斗（LPC 式自动回合），必须改为时间驱动 tick，届时将面临与 LPC 相同的全量遍历开销，且 engine 缺少 LPC 的 `set_heart_beat` 节能机制（见 §2.6）。

### 2.2 _on_combat_tick 遍历与单次结算开销

`_on_combat_tick`（`engine/src/openmud/combat_system.py:248-273`）每 tick 执行：

1. `entities_with(Engaged)`（`:254`）查询所有交战实体。底层实现（`engine/src/openmud/world.py:210-215`）是 `set.intersection`：把每个查询的组件类型的 `dict[eid, component]` keys 取出转 set 再求交集。单组件查询等价于遍历该类型全部实体。
2. 对每对交战方去重（`frozenset` pair，`:266-269`），双方各出手一次 `resolve_one_strike`（`:271-273`）。
3. `resolve_one_strike`（`combat_system.py:134-165`）内部：
   - `run_vetoable(world, ON_BEFORE_COMBAT_ROUND, ctx)`（`:143`）：遍历所有 `ON_BEFORE_COMBAT_ROUND` handler（`events.py:127-141`）。
   - `build_combat_context`（`:149`/`:168-195`）：5 次 `get_component`（attacker Vitals/attrs + defender Vitals/attrs + `select_move`）。
   - `resolve_attack`（`:153`）：七步结算（`combat.py:132-216`），含 PowerModel 四次调用 + `_roll_opposed` 两次 + hit_ob/hit_by/post_action 钩子。
   - `apply_combat_result`（`:154`/`:227-245`）：写 Vitals + 可能触发 `handle_vitals_depleted`。
   - `events.dispatch(ON_COMBAT_ROUND, ...)`（`:155-163`）：遍历所有 `ON_COMBAT_ROUND` handler。
   - `_broadcast_round`（`:164`）：消息广播（见 §2.3）。

单对交战方单 tick 的 `get_component` 调用次数：build_context 5 次 + apply 1 次 + broadcast 3 次（attacker Identity + defender Vitals + defender Identity）+ pair 去重时的 `has_component` 检查 4 次 = 约 13+ 次 dict 查找。`get_component`（`world.py:181-185`）是 `dict.get` 嵌套两次（`_components.get(type, {}).get(entity)`），单次 O(1) 但在 100 并发（50 对交战方）时每 tick 约 650+ 次 dict 查找，尚在可接受范围。

### 2.3 _broadcast_round 的 entities_in_room 全量扫描（关键瓶颈）

`_broadcast_round`（`engine/src/openmud/combat_system.py:276-301`）的消息分发实现：

```python
for entity in (attacker, defender):           # :291
    if world.has_component(entity, PlayerSession):
        recipients.add(entity)
    pos = world.get_component(entity, Position)   # :294
    if pos is None: continue
    for other in world.entities_in_room(pos.room): # :297
        if world.has_component(other, PlayerSession):
            recipients.add(other)
```

`entities_in_room`（`world.py:217-232`）的实现：

```python
for entity in self.entities_with(Position):      # :227 — 遍历所有 Position 实体
    if entity == exclude: continue
    if self.require_component(entity, Position).room != room:  # :230 — 逐个比对 room
        continue
    yield entity
```

**这是 O(N) 全量扫描，没有 room -> entities 的反向索引**。`entities_with(Position)`（`world.py:210-215`）返回所有挂 Position 组件的实体（所有玩家 + 所有 NPC），再逐个 `require_component(Position).room != room` 过滤。

性能影响：假设 1000 在线玩家 + 2000 NPC = 3000 个 Position 实体。每次 `_broadcast_round` 扫描 3000 个实体（实际 attacker 和 defender 各扫一次 = 6000 次），每次 `require_component` 是一次 dict 查找。50 对同时交战时，每 tick 50 * 2 * 3000 = **300,000 次 Position 实体扫描 + room 比对**。这是当前 engine 最严重的性能隐患。

对比 LPC：`message_vision` 只遍历 `environment(me)->all_inventory()`（单个房间的物品列表，通常几十个对象），不遍历全局所有 living。LPC 用「对象 -> 所在房间 -> 房间内对象」的对象引用链实现了局部广播，无需全局扫描。

### 2.4 Effect 引擎缺失（无法评估 Effect 遍历开销）

engine 的 `conditions.py`（257 行）是**通用布尔条件表达式求值器**（`Predicate`/`Equals`/`Gte`/`And`/`Or`/`Not` 节点 + `evaluate` 纯函数），**完全不是 LPC `condition.c` 的时效性 Effect 引擎**。它没有：

- `conditions` mapping（无 Effect 存储结构）
- `update_condition()` 等效物（无 Effect 遍历/tick 衰减/触发机制）
- `apply_condition()` / `clear_condition()` 等效物（无 Effect 挂载/移除接口）
- `CONDITION_D` 外部 daemon 调用机制（无 Effect 内容层的调用约定）

性能维度评估：**无法评估 Effect 遍历开销，因为 engine 根本未实现 Effect 引擎**。这不是性能隐患而是功能缺失。若未来按 LPC 模式实现 Effect 引擎，需特别注意 LPC 注释的警告（`feature/condition.c:15-19`）：每个 condition daemon 的 `update_condition` 内部会递归触发 `receive_damage`/`receive_wound`（如 `bt_poison.c:33-34`、`hanbing_damage.c:23-24`），进而触发 `set_heart_beat(1)` 和数值修改与广播，实际开销远超 mapping 遍历本身。

### 2.5 死亡流程开销

engine 的死亡流程（`engine/src/openmud/death_flow.py`）相比 LPC 大幅简化，但仍含若干开销点：

**玩家死亡** `_execute_player_death`（`death_flow.py:212-270`）：
- `run_vetoable(world, ON_BEFORE_DEATH, ctx)`（`:224`）：遍历 handler。
- `events.dispatch(ON_DEATH, ctx)`（`:239`）：遍历 handler。
- `_drop_inventory_to_room`（`:245`/`:283-288`）：遍历 `Container.items`，逐个 `transfer`。
- `_apply_currency_penalty`（`:248`/`:291-296`）：一次数值扣减。
- `_apply_skill_exp_penalty`（`:249`/`:299-305`）：遍历 `SkillLevels.levels` dict，逐个 `SkillProgress` 重建。
- `_resolve_revive_room`（`:256`/`:273-280`）：`room_ids` dict 查找 O(1)，fallback `next(iter(room_ids.values()))`。
- 重置 Vitals（`:260-264`）+ `events.dispatch(ON_REVIVE)`（`:266-269`）。

**NPC 死亡** `_handle_npc_death`（`death_flow.py:308-336`）：
- `_loot_for_npc`（`:322`/`:339-349`）：查 `spawners` dict + `entity_extension_data` + `parse_loot_table`。
- `_grant_loot`（`:325`/`:352-370`）：currency 加成 + 逐个 `_spawn_loot_item`。
- `_spawn_loot_item`（`:373-395`）：**每件掉落物 `create_entity` + 4 次 `add_component` + 遍历 `CAPABILITIES` 列表逐个 `from_yaml`**。CAPABILITIES 遍历是每个掉落物的固定开销。
- `_grant_kill_exp`（`:331`/`:398-408`）：`select_move`（遍历 `SkillLevels` 查最高 force 招式）+ 写经验。
- `world.destroy_entity(npc_id)`（`:334`）：销毁实体。

相比 LPC 的 `die()`，engine 省去了同步存盘 IO（`victim->save()`）、`log_file` 文件 IO、`CHANNEL_D` 全服广播、`make_corpse` 尸体对象创建、`move(DEATH_ROOM)` 地府流程。但 `_spawn_loot_item` 的 CAPABILITIES 遍历在大量 NPC 同时死亡（AOE/团战）时可能累积开销。`_grant_kill_exp` 内的 `select_move`（`combat_system.py:198-224`）遍历玩家全部已学技能的全部招式查最高 force，每次 NPC 死亡都跑一次。

### 2.6 无 set_heart_beat 等效节能机制

engine 没有 LPC `set_heart_beat(0)` 的按需启停 tick 机制：

- `ON_TICK` 的所有订阅者（`_on_combat_tick`、`_on_unconscious_recovery` 等）在**每次 `advance()` 时都执行**，不区分实体是否需要推进。
- `_on_combat_tick`（`combat_system.py:248-273`）每次都 `entities_with(Engaged)` 查询——即使无交战方，仍执行一次 `set.intersection`（空集快速返回，开销小但非零）。
- `_on_unconscious_tick`（`death_flow.py:417-429`）每次都 `entities_with(Unconscious)` 遍历——即使无昏迷实体，同上。

LPC 的 `set_heart_beat` 机制让空闲 NPC/玩家完全退出 tick 循环（`char.c:157`），1000 在线时只有活跃的 living 消耗 CPU。engine 若改为时间驱动 tick（支持实时战斗），将面临全量实体每 tick 都被遍历的开销，缺少按需启停的节能层。`AIController.tick_interval`（`components.py:362-371`）提供了 NPC 行为的 tick 间隔跳过，但战斗/Effect/昏迷 tick 无类似机制。

### 2.7 entities_with 的 set.intersection 开销

`entities_with`（`world.py:210-215`）对每个查询的组件类型执行 `set(self._components.get(t, {}))`——即把 dict 的 keys 视图转为新 set 对象，再 `set.intersection`。这意味着：

- 每次 `entities_with(Engaged)` 创建一个新 set（拷贝所有 Engaged 实体 id）。
- 每次 `entities_with(Unconscious)` 同理。
- 每次 `entities_with(Position)`（被 `entities_in_room` 调用）创建一个包含所有 Position 实体 id 的新 set。

单组件查询时 set 创建是 O(N) 拷贝。`_broadcast_round` 中 `entities_in_room` 调 `entities_with(Position)` 每次创建 3000 元素的 set 拷贝，50 对交战方每 tick 创建 100 个这样的 set（attacker + defender 各一），产生大量临时 set 对象的 GC 压力。多组件查询（如 `entities_with(Position, PlayerSession)`）则创建多个 set 再交集，开销更大。

---

## 3. 1000 在线 + 100 并发约束下的风险评估

### 3.1 当前命令驱动 tick 下的性能（单机单玩家 CLI 场景）

当前 engine 是单玩家 CLI 驱动（`tick.py` docstring），tick 频率 = 命令输入频率。此场景下：

- 战斗只在玩家敲命令时推进，NPC 不会主动出手（无 aggro AI 接入 tick）。
- Effect 不衰减（无 Effect 引擎）。
- 昏迷苏醒只在实际推进 tick 时发生。
- 性能压力极低：每 tick 最多 1 对交战方结算。

此架构无法支撑 1000 在线的多人实时场景。100 并发意味着 100 个玩家可能同时输入命令，但当前 `TickLoop` 是单线程顺序处理（`advance` 逐个推进），无并发 tick 调度。

### 3.2 若改为时间驱动 tick（支撑实时战斗）的瓶颈预测

若 engine 按 LPC 模式改为固定间隔时间驱动 tick 以支撑实时战斗，预测瓶颈排序：

1. **`entities_in_room` 全量扫描（§2.3）**：最严重。需引入 `room -> entities` 反向索引（如 `dict[EntityId, set[EntityId]]`，在 `Position` 组件增删时维护），将 O(全局 Position 数) 降为 O(房间内实体数)。LPC 的 `all_inventory(environment())` 天然是局部遍历，engine 需补齐这一层。
2. **`entities_with` 的 set 创建开销（§2.7）**：高频 tick 下大量临时 set。可改用 `dict.keys()` 视图（不拷贝）或维护反向索引避免全量扫描。
3. **`do_attack` 等效路径的单次开销（§2.2）**：50 对交战方每 tick 50 * 2 = 100 次 `resolve_one_strike`，每次含 ~13 次 `get_component` + vetoable 遍历 + dispatch 遍历 + broadcast 扫描。优化方向：减少 `get_component` 次数（build_context 可一次取齐）、broadcast 反向索引。
4. **无 `set_heart_beat` 节能（§2.6）**：1000 实体全量每 tick 遍历。需引入按需启停机制（如「活跃实体集合」，仅战斗/挂 Effect/昏迷的实体进 tick 队列）。
5. **死亡峰值 IO（§2.5）**：engine 当前无同步存盘 IO（存档走 `save_fn` 周期触发，`tick.py:84-85`），优于 LPC 的 `die()` 内 `save()`。但 `_spawn_loot_item` 的 CAPABILITIES 遍历在密集死亡时累积。

### 3.3 Effect 引擎实现时的性能预警

若未来按 LPC 模式实现 Effect 引擎，需警惕：

- LPC 注释已明确警告 condition 过多导致 "Too long evaluation"（`feature/condition.c:15-19`）。
- 每个 condition daemon 的 `update_condition` 内部递归触发伤害（`receive_damage`/`receive_wound`）与广播（`bt_poison.c:33-34`），单次 Effect tick 的实际开销是「mapping 遍历 × 每个 Effect 的伤害结算 + 广播」。
- LPC 用 tick 计数器稀释频率（每 5-14 heart_beat 才 update_condition，`char.c:141-142`），engine 若每 tick 都遍历 Effect 会比 LPC 更密集。
- 1000 在线时若平均每人挂 3 个 condition，每 Effect tick 遍历 3000 个 condition daemon 调用，每个含伤害结算与广播——需设计 Effect 批处理与频率稀释机制。

---

## 4. 结论摘要

1. **LPC 的 `set_heart_beat` 节能机制（`char.c:149-157`、`damage.c:34/63`）是 1000 在线可行的关键**：空闲 living 退出 tick，仅活跃 living 消耗 CPU。engine 无等效机制（§2.6），改时间驱动 tick 时需补齐。
2. **engine 的 `entities_in_room` 全量扫描（`world.py:217-232`，无 room 反向索引）是当前最严重性能隐患**：50 对交战方每 tick 产生 30 万次 Position 扫描（§2.3）。LPC 用 `all_inventory(environment())` 天然局部遍历。
3. **engine tick 是命令驱动非时间驱动（`tick.py:80-85`）**：当前无法支撑实时自动回合战斗，100 并发场景需改架构。这不是性能问题而是能力缺失。
4. **engine Effect 引擎完全缺失（`conditions.py` 是布尔求值器非时效引擎，§2.4）**：性能维度无法评估，但 LPC 的 Effect 递归触发伤害+广播模式（`bt_poison.c:33-34`）是实现时的性能预警。
5. **engine 死亡流程已去除 LPC 的同步存盘 IO（`die()` 内 `save()`）**，性能优于 LPC；但 `_spawn_loot_item` 的 CAPABILITIES 遍历（`death_flow.py:373-395`）在密集死亡时有累积开销。
