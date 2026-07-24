# 红队：战斗与效果生命周期簇性能与可扩展性风险

> 角色：性能与可扩展性红队挑战者。基于 Phase 1 产出与一手源码复核，对「战斗/Effect/死亡」三系统在 1000 在线 / 100 并发约束下的性能风险提出质疑。每条结论标注来源（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名）。量化估计为数量级推断，非精确压测。

---

## 0. 风险总览

| 风险项 | 严重度 | 量化锚点 | 主要来源 |
|--------|--------|----------|----------|
| LPC 战斗 tick 全量 heart_beat 遍历 | 高 | 1000 在线 + NPC 时，每 2 s 需处理上千 living 的 `heart_beat`；30% 参战约触发 600+ `do_attack` / tick | `inherit/char/char.c:60-169` |
| Effect 遍历峰值开销 | 高 | 人均 3 condition 时，每 Effect tick 约 3000 次外部 daemon 调用；每个 daemon 可能再触发伤害与广播 | `feature/condition.c:21-69` |
| 全员战斗广播放大 | 高 | LPC 单房间广播 10-50 对象；engine 当前是 O(全局 Position 数) 扫描，50 场战斗 ≈ 30 万次扫描 / tick | `combatd.c:732` / `combat_system.py:297` |
| 死亡峰值 IO/对象创建 | 中高 | 单次 `die()` 含 2 次同步 `save()` + 多次 `log_file` + 全服 channel + `make_corpse`；50 人同时死亡即 100 次同步存档 | `damage.c:245` / `combatd.c:1023` |
| engine 命令驱动 tick 无法支撑实时战斗 | 高 | 当前 `TickLoop.advance()` 由 CLI 每条命令触发，空闲时世界不推进；这是能力缺失而非性能优势 | `tick.py:73-85` |
| engine `entities_in_room` 全量扫描 | 高 | `entities_with(Position)` 每次创建新 set 并全量遍历，无 room -> entities 反向索引 | `world.py:217-232` |
| engine 缺少 `set_heart_beat` 节能等效机制 | 中 | 改时间驱动后，所有实体每 tick 都会被扫描，无论是否活跃 | `combat_system.py:248-273` |
| engine Effect 引擎完全缺失 | 高 | `conditions.py` 是布尔求值器，无时效 Effect 引擎；无法评估/承载 30+ condition 遍历 | `conditions.py:1-22` |

---

## 1. LPC 侧基准画像

### 1.1 heart_beat 是单线程全量 living 遍历

`inherit/char/char.c:heart_beat()`（`char.c:60-169`）是每个 living 对象每 tick 的入口。`setup()` 时即 `set_heart_beat(1)`（`char.c:53`），驱动器按固定间隔（MudOS 通常 2 s）对每个 living 顺序调用一次。每个 tick 内依次执行：

- 玩家限流/频道刷屏检测（`:70-81`）
- `neili`/`jingli`/`jing` 钳制（`:84-97`）
- 死亡快道判定 `eff_qi<0 || eff_jing<0` -> `die()`（`:100-104`）
- 两段式昏迷/死亡判定 `qi<0 || jing<0 || jingli<0`（`:108-115`）
- `is_busy()` -> `continue_action()`，否则 wimpy 逃跑 + `attack()`（`:118-133`）
- NPC `chat()`（`:135-139`）
- `tick--` 归零时 `update_condition()` + `heal_up()` + 空闲关心跳（`:141-158`）

**质疑**：Phase 1 性能评估（`performance-review.md` §1.1）指出"1000 在线 + 大量 NPC 时每 interval 全量遍历"，但未显式指出该遍历是**单线程顺序执行**——MudOS driver 通常按对象数组顺序调用 heart_beat，无并行。1000 living 时，即使每次 `heart_beat` 仅 1 ms，单 tick 总耗时已达 1 s，远超 2 s 间隔的一半，CPU 利用率极易跑满。

### 1.2 set_heart_beat 启停机制的开销被过度乐观

LPC 通过 `set_heart_beat(1)`/`set_heart_beat(0)` 做按需启停：

- **开启点**：`feature/attack.c:fight_ob()`（`:44`）、`feature/damage.c:receive_damage()`（`:34`）、`receive_wound()`（`:63`）。任何战斗/受伤都会强制开启心跳。
- **关闭点**：`char.c:149-157` 在和平时检查 `!is_fighting() && !interactive(this_object())` 且房间内无 interactive 对象时，调用 `set_heart_beat(0)`。

**质疑**：

1. **启停本身是 driver 级对象数组操作**。MudOS 中 `set_heart_beat(1)` 会把对象加入全局 heart_beat 列表；高频受伤/脱战（如 AOE 法术、团战）会导致该列表频繁增删，带来 O(N) 列表维护开销。
2. **"和平时关闭"的条件苛刻**。只要角色仍挂着 condition（中毒/通缉/perform 锁），`update_condition()` 返回 `CND_CONTINUE` 就会让 `cnd_flag & CND_NO_HEAL_UP` 为真或因 `heal_up()` 有更新而保持心跳（`char.c:149`）。Phase 1 提到 `CND_NO_HEAL_UP` 全仓库无实现（`mechanisms.md` §3.2），但 `heal_up()` 在自然恢复时返回非零（`damage.c:270-331`），同样阻止关心跳。结果是：只要玩家在线且未掉线，基本不会退出 heart_beat 列表。
3. **1000 在线玩家不可能被关闭心跳**——因为 `!interactive(this_object())` 对在线玩家为假。因此 1000 在线玩家会**常驻** heart_beat 列表，LPC 的节能机制在在线玩家维度几乎无效。

**量化**：若 1000 在线玩家 + 500 活跃 NPC 常驻 heart_beat 列表，每 2 s 触发 1500 次 `heart_beat()`；按平均每个 `heart_beat` 0.5-2 ms 估算，单 tick 总耗时 0.75-3 s，已接近或超过 2 s 间隔。

---

## 2. 战斗 tick 并发风险

### 2.1 `attack()` 每 tick 触发一次完整战斗结算

`char.c:132` 在 `is_fighting()` 且非 busy 时调用 `feature/attack.c:attack()`（`:208-224`），其内部：

- `clean_up_enemy()` 遍历 `enemy` 列表（`:64-75`）
- `select_opponent()` 从 `random(MAX_OPPONENT=4)` 中选一（`:79-88`）
- 调 `COMBAT_D->fight(this_object(), opponent)`（`:220`）

`combatd.c:fight()`（`:787-845`）再根据状态走三分支，通常调用一次 `do_attack()`；若触发双手互博/辟邪剑法/双武，会**再调用一次 `do_attack()`**（`:806-833`）。

**质疑**：Phase 1 估算"30% 同时战斗（300 场）每 interval 触发 300+ 次 do_attack"（`performance-review.md` §1.4），但该估算**低估**了以下乘数：

- 每场 1v1 双方各有一次 `attack()` -> 基础 600 次 `fight()`/`do_attack()`
- 双手互博/辟邪/双武二次攻击按触发条件额外 +30-50%（`combatd.c:807` 条件 `sizeof(prepare)>1` 或 `pixie-jian` 等）
- `do_attack` 内部 `riposte` 可能**递归调用 `do_attack()`**（`combatd.c:766-779`）

**量化修正**：300 场 1v1 战斗中，双方各出手一次约 600 次 `do_attack`；假设 30% 触发二次攻击、5% 触发 riposte，则每 tick 约 **600 × 1.35 × 1.05 ≈ 850 次** `do_attack` 调用。

### 2.2 `do_attack` 单次开销极高

`combatd.c:do_attack()`（`:340-780`）单次结算包含：

- 3 次 `skill_power()` 调用（ap/dp/pp），内部含 `level^3/3` 三次方运算（`combatd.c:288-333`，`:317 power = level*level*level/3`）
- 多次 `call_other` 跨对象调用：`SKILL_D(force)->hit_ob`（`:541-562`）、`SKILL_D(martial)->hit_ob`（`:578-585`）、`weapon->hit_ob`/`me->hit_ob`（`:588-603`）、`armor->hit_by`（`:644-656`）、`dodge_skill->hit_by`（`:660-672`）
- `message_vision(result, me, victim)` 向房间内所有对象广播（`:732`）
- `report_status(victim, wounded)` 再播状态条（`:744-746`）
- `post_action` 钩子与 riposte 递归（`:762-779`）

**质疑**：Phase 1 已指出单次开销"3 次三次方 + 3-5 次 call_other + 多次广播"，但未强调**跨对象 call_other 在 MudOS 中是堆栈切换 + efun 调用**，比本地函数调用重 1-2 个数量级。高并发 tick 下，driver 的 call_other 开销会显著放大。

**量化**：保守按单次 `do_attack` 平均 0.5 ms（含 3 次 skill_power + 3 次 call_other + 广播），850 次/ tick × 0.5 ms = **425 ms/tick**。若玩家平均每秒操作 0.5 次命令，tick 间隔约 2 s，则战斗 tick 单独占用约 20% CPU。但在团战/世界 BOSS 等高密度场景（50+ 人同房间混战），单房间内广播对象剧增，单次 `do_attack` 可能升至 1-2 ms，战斗 tick 耗时可达 **850-1700 ms/tick**，接近或超过 tick 间隔。

### 2.3 engine 当前无实时战斗 tick 能力

`engine/src/openmud/tick.py:73-85` 的 `TickLoop.advance()` 明确由 CLI 每条命令推进 1 tick；`combat_system.py:_on_combat_tick` 挂在 `ON_TICK` 上（`:248-273`），只有命令输入时才触发。

**质疑**：Phase 1 将此描述为"当前不存在 1000 在线时每 N 秒全量 tick 开销"（`performance-review.md` §2.1/§3.1），但这**不是性能优势而是架构能力缺失**。1000 在线/100 并发场景必须改为时间驱动 tick，届时 engine 将面临与 LPC 相同的全量遍历问题，且当前 engine 没有 LPC 的 `set_heart_beat` 节能机制（见 §6）。

---

## 3. Effect 遍历峰值风险

### 3.1 `update_condition()` 是每 living 每 N tick 遍历所有 condition

`feature/condition.c:update_condition()`（`:21-69`）由 `char.c:144` 每 `tick = 5+random(10)` 次 heart_beat 调用一次。对每个 condition：

- `find_object(CONDITION_D(cnd[i]))` 查对象（`:36`）
- 未加载则 `catch(call_other(..., "???"))` 触发编译加载（`:38`）
- 调 `call_other(cnd_d, "update_condition", this_object(), conditions[cnd[i]])`（`:62`）
- 返回值不含 `CND_CONTINUE` 则 `map_delete` 移除（`:63`）

源码注释已明确警告性能风险（`condition.c:15-19`）："Because such type of conditions costs heart beat evaluation time, don't make player got too much this kind of conditions or you might got lots of 'Too long evaluation' error message in the log file."

**质疑**：Phase 1 提到 "1000 在线时若平均每人挂 3 个 condition，每 Effect tick 遍历 3000 个 condition daemon 调用"（`performance-review.md` §3.3），但该估算未计入：

- **condition daemon 内部会递归触发 `receive_damage`/`receive_wound`**，从而再次 `set_heart_beat(1)` 并触发数值修改与广播。例如 `bt_poison.c:33-34` 每 tick 调 `receive_wound("jing", ...)` + `receive_damage("jingli", ...)`；`hanbing_damage.c:23-24` 调 `receive_damage("qi", ...)` + `receive_wound("jing", ...)`。
- **每个 condition 可能触发多次 `message("vision", ...)` 广播**。例如 `bt_poison.c:11-28` 在三个 `eff_jing` 档位分别 `tell_object` + `message("vision", ...)`。
- **`apply_condition` 无去重**（`condition.c:79-85` 注释明确），同一 condition 可被重复叠加，导致单角色同一 condition 被调用多次——虽然通常只存一个 key，但 duration 累加时调用方逻辑分散（如 `skill.c:147`、`skill2.c:147`、`combatd.c:1089`），可能意外放大遍历次数。

**量化修正**：1000 在线，人均 3 condition，每 Effect tick 约 3000 次 daemon 调用。每个 daemon 内部平均 2 次 `receive_damage/wound` + 2 次 `message` 广播。Effect tick 频率约为 heart_beat 的 1/7.5（`5+random(10)` 平均 7.5），即每 15 s 一次（heart_beat 间隔 2 s）。单次 Effect tick 总操作量约 **3000 × (2 伤害 + 2 广播) = 12000 次副作用调用**，其中广播可能触及 10-50 对象/房间。若 30% 玩家处于热门区域（房间对象密集），广播放大可达 **3000 × 2 × 15 ≈ 90,000 条消息投递 / Effect tick**。

### 3.2 engine `_on_unconscious_tick` 密度被忽略

`engine/src/openmud/death_flow.py:_on_unconscious_tick`（`:417-429`）每 `ON_TICK` 遍历所有 `entities_with(Unconscious)`，对每个实体递减 `ticks_remaining`、恢复气血、发消息。

**质疑**：

1. 当前 engine 无通用 Effect 引擎，但 `_on_unconscious_tick` 是**唯一硬编码的时效 Effect 雏形**。若未来按 LPC 模式扩展为通用 Effect 引擎，所有 condition 都要按此模式每 tick 遍历，密度将远高于当前单一 Unconscious 组件。
2. 该遍历没有稀释机制（LPC 用 `5+random(10)` 稀释），每个 tick 都执行。
3. 与 `_on_combat_tick` 叠加：每 tick 既遍历 Engaged，又遍历 Unconscious；未来再加上通用 Effect 遍历，单次 `ON_TICK` 可能触发 3 次全量组件查询。

**量化**：1000 在线中若有 50 人昏迷，每 tick 需处理 50 次 Unconscious 更新；若未来人均 3 Effect，每 tick 需处理 3000 次 Effect 更新。当前 `_on_unconscious_tick` 虽轻量，但其模式是高密度 Effect 遍历的预演。

---

## 4. 全员战斗广播风险

### 4.1 LPC `message_vision` 已是房间级局部广播

LPC `do_attack` 通过 `message_vision(result, me, victim)`（`combatd.c:732`）和 `report_status()`（`:744-746`）向**单个房间**内所有对象广播。`message_vision` 由 simul_efun 实现，遍历 `environment(me)->all_inventory()`，通常 10-50 对象/房间。

**质疑**：Phase 1 §1.5 指出"同一房间内的玩家会收到所有战斗的广播消息，消息量随房间内战斗场数线性增长"，但未量化该放大。在热门区域（如扬州城中心、门派战、世界 BOSS 房），一个房间可能有 50+ 玩家 + NPC，同时发生 10+ 场战斗。每场战斗每 tick 产生 2-4 条 `message_vision`（攻击文案 + 状态条 + 可能的 winner_msg/riposte 文案），则单房间内每 tick 广播量可达 **10 场 × 3 条 × 50 对象 = 1500 条消息投递**。这会导致：

- 玩家客户端刷屏严重（block_msg 判定成本增加）
- driver 消息分发队列堆积
- `blind` condition 随机丢消息（`feature/message.c:44`）的随机判定进一步增加 CPU

### 4.2 engine `_broadcast_round` 是全局 O(N) 扫描，比 LPC 更差

`engine/src/openmud/combat_system.py:_broadcast_round`（`:276-301`）在找同房间玩家时：

```python
for entity in (attacker, defender):
    pos = world.get_component(entity, Position)
    if pos is None: continue
    for other in world.entities_in_room(pos.room):   # :297
        if world.has_component(other, PlayerSession):
            recipients.add(other)
```

`world.entities_in_room`（`engine/src/openmud/world.py:217-232`）的实现是：

```python
for entity in self.entities_with(Position):           # :227
    if entity == exclude: continue
    if self.require_component(entity, Position).room != room:  # :230
        continue
    yield entity
```

**质疑**：Phase 1 性能评估（`performance-review.md` §2.3）已指出这是 O(全局 Position 数) 全量扫描，无 room -> entities 反向索引。但该风险需要进一步强调：

1. `entities_with(Position)`（`world.py:210-215`）每次调用都把 dict keys 转成新 set，即 **O(N) 内存拷贝**。`_broadcast_round` 对 attacker 和 defender 各扫一次，50 场战斗每 tick 创建 100 个临时 set。
2. `require_component(entity, Position)` 每次是一次 dict 查找；若全局 3000 个 Position 实体，50 场战斗每 tick 执行 **50 × 2 × 3000 = 300,000 次 Position 查找 + room 比对**。
3. 与 LPC 相比，LPC 是"房间级局部遍历"，engine 是"全局遍历后过滤"，复杂度从 O(房间对象数) 升到 O(全局实体数)。

**量化**：

- LPC：50 场战斗，平均每房间 20 对象，每场 3 条广播 -> 50 × 3 × 20 = 3000 条消息投递 / tick，加少量状态条。
- engine（当前实现）：50 场战斗，全局 3000 Position 实体 -> 50 × 2 × 3000 = 300,000 次扫描操作；若每条广播最终发给 5 个玩家，实际消息投递 50 × 3 × 5 = 750 条，但**扫描开销占主导**。

---

## 5. 死亡流程峰值风险

### 5.1 LPC `die()` 是高 IO + 高对象创建流程

`feature/damage.c:die()`（`:152-253`）在玩家死亡时执行：

- `clear_condition()`（`:184`）
- `COMBAT_D->announce(this, "dead")` -> `message_vision` 广播（`:187`，对应 `combatd.c:966-980`）
- `COMBAT_D->death_penalty(this)`（`:190`）
  - 内部再次 `clear_condition()`（`combatd.c:995`）
  - 多项数值扣减
  - `victim->skill_death_penalty()`（`combatd.c:1022`）
  - `victim->save()` **同步存档**（`combatd.c:1023`）
- `COMBAT_D->killer_reward(killer, this)`（`:194`）
  - `CHANNEL_D->do_channel` 全服谣言广播（`combatd.c:1060-1061`）
  - `apply_condition("killer"/"pker", ...)` 挂 condition
  - `find_object("/d/taishan/fengchan")` 惰性加载（`combatd.c:1070-1071`）
- `log_file("PKILL_DATA"/"PLAYER_DEATH", ...)` 多次文件 IO（`damage.c:209-224`）
- `CHAR_D->make_corpse()` 创建尸体对象 + 移动（`damage.c:226-228`）
- `this_object()->save()` **第二次同步存档**（`damage.c:245`）
- `move(DEATH_ROOM)` 进入地府（`damage.c:247`）

**质疑**：Phase 1 §1.6 已列出死亡流程开销，但需强调 **IO 是阻塞操作**。MudOS 的 `save()` 和 `log_file()` 都是同步写磁盘。团战/门派战死亡峰值时，多个 `save()` 串行执行会导致后续 heart_beat 延迟，形成"死亡越多 -> 卡顿越重 -> 更容易死亡"的正反馈。

**量化**：

- 单次玩家死亡：2 次 `save()` + 2-3 次 `log_file()` + 1 次 `CHANNEL_D` 全服广播 + 1 次 `make_corpse` 对象创建。
- 若 `save()` 平均耗时 5 ms（玩家数据复杂时可能 10-20 ms），单次死亡仅存档就 10 ms。
- **50 人同时死亡**：100 次 `save()` × 5 ms = 500 ms 纯 IO 阻塞；加上 log 与 channel，可能达 **1-2 s 的单线程阻塞**，远超 2 s heart_beat 间隔的一半。
- `unconcious()` 也会注册 `call_out("revive", random(100-con)+30)`（`damage.c:134`），大规模昏迷时大量 call_out 排队，增加 driver 定时器开销。

### 5.2 engine 死亡流程虽未同步存档，但 `_spawn_loot_item` 有累积风险

`engine/src/openmud/death_flow.py:_execute_player_death`（`:212-270`）去掉了 LPC 的同步 `save()`，但 NPC 死亡路径 `_handle_npc_death`（`:308-336`）中：

- `_spawn_loot_item`（`:373-395`）为每件掉落物 `create_entity` + 4 次 `add_component` + 遍历 `CAPABILITIES` 列表逐个 `from_yaml`。
- `_grant_kill_exp`（`:398-408`）每次 NPC 死亡都调用 `select_move(world, killer_id)`，遍历该玩家全部已学技能的全部招式（`combat_system.py:198-224`，`:205-212` 内层循环）。

**质疑**：

1. 当前 engine 死亡流程看似比 LPC 轻，但 `_spawn_loot_item` 的 **CAPABILITIES 遍历是每个掉落物的固定开销**。在 AOE/团战中大量 NPC 同时死亡，掉落物创建可能成为瓶颈。
2. `_grant_kill_exp` 的 `select_move` 本应在战斗前调用一次，却在**每次 NPC 死亡时重复调用**，O(玩家技能数 × 每技能招式数) 的复杂度被反复执行。

**量化**：若一次 AOE 击杀 20 个 NPC，每个 NPC 掉落 2 件物品，则 `_spawn_loot_item` 执行 40 次，每次遍历 CAPABILITIES（假设 10 个能力）-> 400 次 `from_yaml` 调用。若每个玩家已学 5 个技能、每技能 10 招，`select_move` 每次死亡遍历 50 条招式，20 次死亡 = 1000 次招式比较。

---

## 6. engine 现有模块的性能反模式

### 6.1 `entities_with` 的 set 拷贝开销

`engine/src/openmud/world.py:210-215`：

```python
def entities_with(self, *component_types: type) -> Iterable[EntityId]:
    if not component_types:
        return iter(())
    matching_sets = [set(self._components.get(t, {})) for t in component_types]
    return iter(set.intersection(*matching_sets))
```

**质疑**：

1. 单组件查询时，`set(self._components.get(t, {}))` 会创建包含所有该类型实体 id 的新 set。`_broadcast_round` 每调用一次 `entities_in_room` 就触发一次该拷贝。
2. 多组件查询时，创建多个 set 再求交集，临时对象更多。
3. 高频 tick 下，大量临时 set 对象增加 GC 压力。

**量化**：全局 3000 Position 实体，50 场战斗每 tick 创建 100 个 3000 元素 set -> 约 300,000 个整数被拷贝到临时 set 中。Python int 约 28 字节，单次 tick 临时内存约 8.4 MB，GC 负担显著。

### 6.2 `entities_in_room` 缺少反向索引

见 §4.2。`world.py:217-232` 的 `entities_in_room` 没有维护 `room -> set[EntityId]` 反向索引，每次都要扫全局 Position 实体。

**建议**：在 `add_component(Position)` / `remove_component(Position)` 时维护 `dict[room, set[EntityId]]`，将复杂度降到 O(房间内实体数)。

### 6.3 无 `set_heart_beat` 等效节能机制

`engine/src/openmud/components.py:AIController`（`:362-371`）提供了 NPC 行为的 `tick_interval` 跳过机制，但：

- `_on_combat_tick`（`combat_system.py:248-273`）每次 `ON_TICK` 都执行 `entities_with(Engaged)`。
- `_on_unconscious_tick`（`death_flow.py:417-429`）每次 `ON_TICK` 都执行 `entities_with(Unconscious)`。
- 当前无通用 Effect tick，但未来若有，也会每 tick 全量遍历。

**质疑**：当 engine 改为时间驱动 tick 后，所有 tick handler 都会每 tick 全量扫描，无论当前是否有交战/昏迷/Effect 实体。LPC 通过 `set_heart_beat(0)` 让空闲 living 完全退出 tick 循环；engine 缺少等效机制，1000 在线时会浪费大量 CPU 在空查询上。

**量化**：即使 `entities_with(Engaged)` 空集时 `set.intersection` 快速返回，仍有创建空 set 和 dict lookup 的开销。1000 tick/s 时，单次空查询约 1-5 µs，累计 1-5 ms/s；若叠加 3-4 个空查询 handler，浪费 3-20 ms/s，看似不大，但在高密度 tick 下会累积。

### 6.4 `ON_TICK` 事件分发顺序与阻塞

`engine/src/openmud/tick.py:80-83`：

```python
self._tick += 1
if self._world is not None:
    self._world.tick = self._tick
    self._world.events.dispatch(ON_TICK, TickContext(...))
if self._tick % self._interval == 0:
    self._save()
```

**质疑**：

1. 所有 `ON_TICK` handler 是同步顺序执行的。`_on_combat_tick`、`_on_unconscious_tick`、未来的 Effect tick、AI tick、Nature tick 都在同一次 `dispatch` 中串行运行。若某个 handler 耗时过长，会阻塞后续 handler 与存档。
2. 存档 `self._save()` 在 `ON_TICK` 分发之后执行。若战斗/Effect 处理耗时过长，会导致存档延迟，崩溃恢复窗口扩大。

### 6.5 Effect 引擎完全缺失导致无法评估

`engine/src/openmud/conditions.py`（`:1-22`）文档自述是"门条件 / 物品使用限制 / NPC 行为条件三类动态规则的共同条件子语言地基"，其 `evaluate()`（`:170-176`）是纯布尔求值函数。**它不是 LPC `condition.c` 的时效性 Effect 引擎**。

**质疑**：

1. Phase 1 已明确"engine Effect 引擎完全缺失"（`engine-comparison.md` 模块 3，最严重负面遗漏）。红队进一步指出：因为缺失，**1000 在线时的 Effect 遍历峰值开销在当前 engine 中无法被任何测试或 profiling 捕捉到**——这是一个"看不见的风险"，会在补建 Effect 引擎时突然暴露。
2. 当前 `DemoPoisonStrikeBehavior`（`skills.py:87-102`）名含 Poison 却只做瞬时 `damage+5`，不施加持久毒。这种误导性占位会让团队低估 Effect 引擎缺失的影响。

---

## 7. 综合量化估计与风险排序

### 7.1 场景：1000 在线 / 30% 参战 / 人均 3 condition

假设 heart_beat / tick 间隔 2 s，全局约 3000 个 Position 实体（1000 玩家 + 2000 NPC）。

| 子系统 | LPC 量级 | engine（若改时间驱动）量级 | 风险等级 |
|--------|----------|---------------------------|----------|
| heart_beat 遍历 | 1500 living × 0.5-2 ms = 0.75-3 s / tick | 1500 entity × 各 handler = 1-4 s / tick | 高 |
| 战斗 do_attack | ~850 次 / tick × 0.5-2 ms = 425-1700 ms | ~100 对 × 2 次 = 200 次 `resolve_one_strike`；但广播扫描 300,000 次 | 高 |
| Effect 遍历 | 3000 daemon 调用 / 15 s；每个含伤害+广播 | 无引擎，未来若补建同 LPC | 高 |
| 战斗广播 | 10-50 对象/房间，热门区 1500 条投递/tick | 300,000 次扫描操作 + 实际投递 | 高 |
| 死亡峰值 | 50 人同时死 -> 1-2 s IO 阻塞 | 无同步 save，但掉落物创建 40-100 次/波 | 中高 |

### 7.2 最关键的三个性能瓶颈

1. **engine `entities_in_room` 全局扫描**：这是当前 engine 独有的、最严重的性能反模式。即使只有 50 场战斗，每 tick 也要扫描 30 万次 Position 组件。
2. **LPC/engine 改时间驱动后的全量 tick 遍历**：1000 在线时，heart_beat/tick 遍历是 O(在线数) 的不可扩展瓶颈；缺少 `set_heart_beat` 等效节能会让空闲玩家也消耗 CPU。
3. **Effect 引擎缺失/递归副作用**：LPC 的 condition daemon 每 tick 可能递归触发伤害与广播；engine 若未来补建，必须设计批处理与稀释机制，否则 3000 condition 调用/ tick 会压垮单线程。

---

## 8. 质疑清单（引用被质疑文件与段落）

| # | 质疑 | 被质疑文件/段落 | 证据 |
|---|------|----------------|------|
| 1 | Phase 1 对 LPC 在线玩家无法关闭心跳的分析不足 | `performance-review.md` §1.2 | `char.c:149-157` 要求 `!interactive(this_object())` 才关心跳；在线玩家永不满足 |
| 2 | Phase 1 估算的 `do_attack` 次数偏低 | `performance-review.md` §1.4 | `combatd.c:806-833` 双手互博/辟邪二次攻击；`:766-779` riposte 递归 |
| 3 | Phase 1 未量化 `message_vision` 在热门房间的放大 | `performance-review.md` §1.5 | `combatd.c:732` `message_vision` 扫 `all_inventory(environment())` |
| 4 | Phase 1 未强调 `update_condition` 递归触发伤害+广播 | `performance-review.md` §1.3 | `bt_poison.c:33-34`、`hanbing_damage.c:23-24` |
| 5 | Phase 1 对 engine 命令驱动 tick 的风险定性过轻 | `performance-review.md` §2.1/§3.1 | `tick.py:73-85` docstring 明确 CLI 命令驱动 |
| 6 | Phase 1 已指出但未充分强调 `entities_in_room` 是最严重隐患 | `performance-review.md` §2.3 | `combat_system.py:297`、`world.py:217-232` |
| 7 | `engine-comparison.md` 将 Effect 引擎缺失列为最严重遗漏，但未给出性能量级 | `engine-comparison.md` 模块 3 | `conditions.py:1-22` 布尔求值器 vs `condition.c:21-69` 时效引擎 |
| 8 | engine `_spawn_loot_item` 的 CAPABILITIES 遍历在死亡峰值时累积 | `performance-review.md` §2.5 | `death_flow.py:373-395` |
| 9 | engine `entities_with` 的 set 拷贝是隐藏 GC 压力 | `performance-review.md` §2.7 | `world.py:210-215` |

---

## 9. 结论与建议

1. **engine 必须优先修复 `entities_in_room` 全量扫描**：引入 room -> entities 反向索引，将广播复杂度从 O(全局 Position 数) 降到 O(房间内实体数)。这是支撑 100 并发战斗广播的最低要求。
2. **改时间驱动 tick 时必须引入等效 `set_heart_beat` 节能机制**：维护一个"活跃实体集合"，仅战斗/挂 Effect/昏迷/有 AI 行为的实体进入高频 tick；其余实体按更长间隔或事件驱动更新。
3. **Effect 引擎设计必须批处理 + 稀释**：参考 LPC 的 `5+random(10)` tick 稀释，但不要每 tick 遍历所有 condition；考虑按 condition 类型分组、按房间批处理、限制每 tick 最大 condition 处理数。
4. **死亡流程必须异步化 IO**：LPC 的 `save()`/`log_file()` 同步写磁盘在死亡峰值时阻塞严重；engine 应把存档/日志/全服广播移出同步死亡路径，或合并批量写入。
5. **建立性能基线测试**：在补建 Effect 引擎和改时间驱动 tick 后，必须针对 1000 在线/30% 参战/人均 3 condition 场景做 profiling，重点监控 `entities_with` 调用次数、`entities_in_room` 扫描次数、单 tick 总耗时、GC 频率。
