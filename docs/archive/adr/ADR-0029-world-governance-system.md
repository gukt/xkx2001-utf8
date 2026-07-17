# ADR-0029：WorldGovernanceSystem 代表性元素 + fail-closed 边界

- 状态：草案（阶段 2 Wave 2 前置，2.6 任务卡 ADR）
- 日期：2026-07-12
- 阶段：阶段 2 Wave 2（2.6 WorldGovernanceSystem）
- 关联：[04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 2（M2-6）+ §六不做清单（276 文件后置 M3）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 5（themed 治理）+ dissent 10（平台特性范围过载）+ 专家 5 承重论断 2（themed 治理平台级 fail-closed）+ Q2 收敛（themed 治理是异构 System）/ [09](../xkx-arch/09-灵魂系统盘点.md)（阴间 15 文件 + 法院四线交织盘点）/ [15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.6 + §四 Wave 2 范围控制 + §五 ADR 表 + §七 dissent 映射 / [ADR-0014](ADR-0014-daemon-responsibility-redesign.md)（themed 治理归属 + SECURITY_D valid_cmd fail-closed）/ [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)（存档崩溃安全）/ [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) EffectComp / [ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md) ConditionTickResult / [ADR-0025](ADR-0025-query-index-layer.md)（格式模板）/ [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) SECURITY_D valid_cmd / [spec/layer_f_death.py](../../engine/src/xkx/spec/layer_f_death.py) die/make_corpse/death_penalty/killer_reward 规格 / [runtime/capability.py](../../engine/src/xkx/runtime/capability.py) PermissionService / [runtime/conditions.py](../../engine/src/xkx/runtime/conditions.py) ConditionSystem

## 背景

[15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.6 任务卡：实现 1-2 个代表性治理元素（阴间 / 法院），对照 [09 灵魂系统盘点](../xkx-arch/09-灵魂系统盘点.md)。平台级 fail-closed Python，不落入 UGC 可编辑规则层。验收：阴间还阳路径可跑 + 法院通缉/执法/服刑闭环；平台级 fail-closed（不可被 UGC 规则覆盖）。范围控制：276 文件武林大会 / vote / intermud 推迟 M3 后（[04](../xkx-arch/04-迁移路径与避坑清单.md) §六）。

**现有资产（阶段 1 已产出，2.6 在此基础上构建治理层）**：

- [conditions.py](../../engine/src/xkx/runtime/conditions.py) ConditionSystem + ConditionHandler.on_tick 组合返回值（`ConditionTickResult`，ADR-0018）。Effect 作为独立实体（EffectComp attach 到 effect 实体，`target_id` 指向被作用实体）。**具体 condition 类型未填充**（T1 只定框架，2.2/2.6 按需补）。
- [capability.py](../../engine/src/xkx/runtime/capability.py) PermissionService（HS256 + 内存吊销集合，fail-closed）。`valid_cmd` 语义已映射为段 2 权限校验中间件（ADR-0020 决策 3），`exclude` 优先于 `authorized`。
- [spec/layer_f_death.py](../../engine/src/xkx/spec/layer_f_death.py) 完整提取 die()/unconcious()/revive()/reincarnate()/make_corpse()/death_penalty()/killer_reward() 规格（10 函数，含副作用顺序）。**阴间世界流程（黑白无常/还阳路径）标注为"后置到阶段 1"（文件头注释第 22 行），本 ADR 补全此缺口**。
- [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) SECURITY_D valid_cmd 规格（fail-closed + exclude 优先）+ CHAR_D break_relation（华山派师徒解除，die 触发）。
- [storage.py](../../engine/src/xkx/runtime/storage.py) StorageSystem（原子写 + offload + dirty-flag，ADR-0022）。新组件须可序列化 + 崩溃恢复。
- [ecs.py](../../engine/src/xkx/runtime/ecs.py) 13 组件（含 Marks/EffectComp）。Marks.flags 是 set[str]，可存通缉标记/阴间位置标记。
- [engine.py](../../engine/src/xkx/runtime/engine.py) System 注册 + 统一 tick 循环 + TickProfiler。

**dissent 5 的承重张力**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 5 承重论断 2 + §五第 5 条）：

> themed 治理（天雷/阴间/vote/法院）必须是非 UGC 可编辑的平台级 fail-closed Python，不能落入规则引擎或 UGC 可触的规则层。

[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §三 Q2 收敛进一步明确：themed 治理是**异构 System**（非统一规则引擎），"反作弊迭代慢"是 fail-closed 的正确取舍。本 ADR 落地裁决：**GovernanceSystem 是平台级 Python System，治理逻辑（通缉触发/量刑分级/阴间剧情/gate.c 物品销毁）硬编码在 Python，不通过层 1 DSL 或 UGC CPK 暴露**；UGC 只能"触发"治理（如 PK 行为触发通缉），不能"修改"治理规则。

**dissent 10 的承重张力**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 10 条）：

> 平台特性并行范围过载：4 层 DSL/Agent/6 维评估/CPK/ThemeRegistry/沙箱/审核/创作者经济远超"单机 1000+100 验证"，已显式排到引擎+核心循环验证之后。

本 ADR 落地裁决：**5 灵魂系统只含 1-2 代表性元素**（阴间死亡轮回 + 法院 PK 通缉），276 文件武林大会 / vote / intermud 后置 M3（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.6 范围控制 + [04](../xkx-arch/04-迁移路径与避坑清单.md) §六）。选择理由见 §决策 1。

**Wave 2 范围控制**（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §四说明）：2.6 的阴间路径依赖 2.2 死亡轮回（die -> 阴间衔接），法院依赖 2.4 Combat（PK 触发通缉）。Wave 2 先做**不依赖部分**（平台级 fail-closed 框架 + 阴间剧情骨架 + 法院通缉 condition 框架），2.2/2.4 完成后衔接完整阴间还阳 + 法院通缉/执法/服刑闭环。本 ADR 明确 Wave 2 范围 vs 后续衔接（§决策 6）。

**dissent 5 的 call_out 归属延伸**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 5 条，[15](../xkx-arch/15-阶段2-子系统实施计划.md) §七映射到 2.4）：

> call_out 归属未交叉验证：DSL 专家独家把 call_out（694 文件/3109 处）归 ActionScheduler，其他专家未确认。需实现时明确与 ConditionSystem/EventBus 边界。

阴间剧情的 call_out（黑白无常 5 段延时对话，`call_out("death_stage", 30, ob, 0)` + 5 秒间隔）是典型延时副作用。本 ADR 落地裁决：**阴间剧情 call_out 翻译为 EffectComp（可序列化/可中断/可崩溃恢复，ADR-0017/0022）**，由 GovernanceSystem 拥有；与 ConditionSystem 边界明确（§决策 4）。

**CLAUDE.md 不变量**：

- themed 治理（天雷/阴间/vote/法院）是平台级 fail-closed Python，不落入 UGC 可编辑规则层。
- 三层粒度 Theme > Module Pack > UGC CPK（治理是平台级，非题材包/UGC）。
- tick=1s + compute<100ms（治理 System tick 开销评估，见 §决策 7）。
- Command 仅覆盖外部意图（治理触发不经 Command，是 System tick 派生或 combat 副作用）。
- JSON 存档崩溃安全（阴间进度/通缉状态崩溃不丢失，ADR-0022）。

## 决策

### 1. 代表性元素选择（阴间死亡轮回 + 法院 PK 通缉）

从 [09](../xkx-arch/09-灵魂系统盘点.md) 五灵魂系统（阴间/法院/武林大会/vote/intermud）中选 **2 个代表性元素**：

| 代表性元素 | 选择理由 | 与核心循环关系 |
|---|---|---|
| **阴间死亡轮回** | die() 是 heart_beat 核心循环的死亡分支（[spec/layer_f](_die_spec)），阴间是 die -> reincarnate 之间的必经状态机；gate.c 物品销毁是关键副作用（不可遗漏）；黑白无常剧情是 call_out 翻译为 Effect 的典型场景 | 最紧：die 触发阴间入口（2.2 衔接） |
| **法院 PK 通缉** | killer_reward() 是 die() 副作用链的一环（[spec/layer_f](_killer_reward_spec)），PKS 计数 + killer condition 施加是 combat 副作用；condition 框架已就绪（ConditionSystem）；执法 NPC 检测 condition -> 自动攻击是 NPC AI 平台层 | 紧：PK 触发通缉（2.4 衔接） |

**砍掉项后置 M3**（[04](../xkx-arch/04-迁移路径与避坑清单.md) §六 + [15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.6 范围控制）：

| 砍掉项 | 后置时机 | 理由 |
|---|---|---|
| 武林大会（d/bwdh/ 297 文件） | M3 后 | 高度自包含赛事系统，不参与核心战斗循环日常运行；control.c 53KB 需拆分为 TeamRegistry/MatchScheduler/ScoreBoard 等多组件（[09](../xkx-arch/09-灵魂系统盘点.md) §三注意事项 4）；exec 代理机制需 Python 等价设计（注意事项 1） |
| vote 投票（cmds/std/vote/ + condition） | M3 后 | 玩家自治治理基础设施，UGC 开放前必须就位但非核心循环；依赖 condition 系统 + channeld，2.6 不强制 |
| intermud（adm/daemons/network/ 24 服务） | 砍掉/无限期后置 | 违反收缩约束第 1/3 条（不考虑分布式架构/分布式网关），[09](../xkx-arch/09-灵魂系统盘点.md) §六建议砍掉 |
| 完整 courthouse 反机器人审判 | 后置（M3 后视需求） | 与 PK 法院同名但不同系统，是巫师工具/平台安全机制（[09](../xkx-arch/09-灵魂系统盘点.md) §五注意事项 5） |

> 选择阴间 + 法院的核心理由：两者与核心循环关系最紧（die 副作用链 + PK combat 副作用），且规格已提取（layer_f_death.py 完整覆盖 die/killer_reward/death_penalty）。武林大会/vote/intermud 与核心循环关系弱或违反收缩约束，后置 M3 符合 dissent 10 范围控制。

### 2. GovernanceSystem 平台级 fail-closed 边界

**核心决策**：GovernanceSystem 是平台级 Python System，治理逻辑硬编码，不落入 UGC 可编辑规则层。

**三层边界**（对齐 CLAUDE.md 三层粒度 Theme > Module Pack > UGC CPK）：

| 层级 | 内容 | 2.6 归属 |
|---|---|---|
| **平台级（Python System）** | GovernanceSystem 治理逻辑：阴间状态机 + gate.c 物品销毁 + 黑白无常剧情 + 通缉施加 + 量刑分级 + 执法检测 | **本 ADR 范围**，硬编码 Python，不可被 UGC 编辑 |
| **题材包（Module Pack）** | 武侠题材下的门派/武学数据（2.7 切割），非治理逻辑 | 2.7，非本 ADR |
| **UGC CPK** | 玩家创作内容（房间描述/NPC 对话 flavor text），不可触治理规则 | M3 后，非本 ADR |

**与层 1 DSL 的边界**（对齐 [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §三 Q2 收敛"themed 治理是异构 System"）：

- 层 1 DSL（condition -> action）是 UGC 触发层（如 valid_leave 触发器，[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 3 承重论断 3 "533 valid_leave 证明层 1 是正确抽象层"）。
- **治理触发不经层 1 DSL**：PK 通缉由 combatd.killer_reward() 副作用直接施加（[spec/layer_f](_killer_reward_spec) side_effect order=3 `apply_condition("killer", 100)`），非层 1 规则触发。
- **治理规则不可被层 1 DSL 覆盖**：通缉时长（100 tick）、量刑分级（PKS>99 => 500 tick 等）、gate.c 物品销毁、黑白无常剧情段数（5 段）均为 Python 硬编码常量，层 1 DSL 无接口修改。
- UGC 只能"触发"治理（如玩家 PK 行为触发通缉），不能"修改"治理规则（如不能缩短通缉时长、不能跳过 gate.c 物品销毁）。

**fail-closed 语义**（对齐 [ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 决策 1 SECURITY_D valid_cmd fail-closed + [runtime/capability.py](../../engine/src/xkx/runtime/capability.py) PermissionService fail-closed）：

- 通缉 condition 施加是确定性副作用（killer_reward 无 random，[spec/layer_f](_killer_reward_spec) invariant "no random() in killer_reward()"），combat 副作用链不可跳过。
- 执法 NPC 检测通缉 condition 后自动追杀（call_out("kill_ob", 1, target)），是平台级强制行为，玩家无法绕过。
- gate.c 物品销毁（destruct 所有非 character 物品）是死亡副作用，玩家无法保留物品（阴间不携带阳间物品）。
- 阴间还阳路径有两条（主路径黑白无常剧情 + 隐藏路径 inn1 ask 回家），均调 reincarnate()，**无第三条"跳过阴间"路径**（fail-closed：必须经过阴间状态机）。

**与 PermissionService 的边界**：

- PermissionService 管命令权限（valid_cmd，玩家能执行什么命令）。
- GovernanceSystem 管治理状态（通缉/阴间/监狱），是命令权限之上的平台级强制层。
- pker > 240 禁止 kill/feed/wei/throw 对玩家：是命令层 precondition（[09](../xkx-arch/09-灵魂系统盘点.md) §五注意事项 6），由 PermissionService 或命令 precondition 实现，**非 GovernanceSystem 治理逻辑**（边界明确）。

### 3. 阴间死亡轮回（die -> 阴间 -> 黑白无常剧情 -> 还阳）

对照 [09](../xkx-arch/09-灵魂系统盘点.md) §二盘点 + [spec/layer_f_death.py](_die_spec) 规格。

**完整路径**（对照 LPC `d/death/gate.c` + `d/death/npc/wgargoyle.c` + `feature/damage.c:die/reincarnate`）：

```
die() [层 F 规格，2.2 实现]
  ├─ [no_death 房间] -> unconcious() + return（不进入阴间）
  ├─ clear_condition() + delete("poisoner")
  ├─ COMBAT_D->announce(ob, "dead")
  ├─ COMBAT_D->death_penalty(ob)        经验/技能/金钱惩罚
  ├─ COMBAT_D->killer_reward(killer, ob) PKS+1, killer condition 施加
  ├─ CHAR_D->make_corpse(ob, killer)    尸体生成 + 物品转移（留在死亡地点）
  ├─ 玩家分支:
  │    ├─ qi/jing/eff_qi/eff_jing/jingli = 1
  │    ├─ save()                         防止回档复活
  │    ├─ ghost = 1                      鬼魂标志
  │    ├─ move(DEATH_ROOM) ─────────> /d/death/gate.c [阴间入口]
  │    ├─ MARRY_D->break_marriage()
  │    └─ CHAR_D->break_relation()       华山派解除师徒
  └─ NPC 分支: destruct(this_object())

gate.c init() [2.6 GovernanceSystem 实现]
  ├─ 销毁鬼魂所有 inventory 物品（destruct 非 character 物品，关键副作用）
  ├─ clear_condition()
  └─ 白无常 NPC init() -> EffectComp(death_stage, stage=0, next_tick=current+30)

death_stage() [5 段对话，每段间隔 5 秒，EffectComp 驱动]
  ├─ stage 0-4: 白无常对话剧情（death_msg[stage]）
  └─ stage 4: reincarnate() + DROP_CMD 丢弃所有物品 + move(REVIVE_ROOM)

还阳 (reincarnate) [层 F 规格，2.2 实现]
  ├─ ghost=0; qi/jing/eff_qi/eff_jing/jingli/neili 恢复到 max
  └─ DROP_CMD->do_drop() 丢弃所有物品（主路径）+ move(REVIVE_ROOM)

隐藏路径（跳过黑白无常剧情）
  inn1.c do_stuff() -> reincarnate() + move("/d/city/wumiao") [不丢弃物品]
```

**gate.c 物品销毁是关键副作用**（[09](../xkx-arch/09-灵魂系统盘点.md) §二注意事项 3）：

- 玩家进入鬼门关时所有非 character 物品被 `destruct`（销毁，不是掉落）。
- 与 make_corpse 的物品转移是两个独立步骤：**先转移物品到尸体（留在死亡地点），再将鬼魂（已无物品）传送到鬼门关**。
- gate.c init() 再 `destruct` 鬼魂携带的剩余物品（防御性，正常路径鬼魂已无物品）。
- Python 实现必须保留此副作用顺序：die() 中 make_corpse 先转移物品 -> ghost move 到 DEATH_ROOM -> gate.c init() 销毁剩余物品。

**两条还阳路径统一入口**（[09](../xkx-arch/09-灵魂系统盘点.md) §二注意事项 2）：

- 主路径：黑白无常 5 段剧情结束 -> reincarnate() + DROP_CMD 丢弃物品 + move(REVIVE_ROOM)。
- 隐藏路径：inn1 ask `<自己id>` about 回家 -> reincarnate() + move("/d/city/wumiao")（**不丢弃物品**，因鬼魂已无物品）。
- Python 实现统一还阳入口 `reincarnate()`（层 F 规格），但位置移动 + 物品处理由 GovernanceSystem 按路径区分。

**start_death 是 LPC 空调用**（[09](../xkx-arch/09-灵魂系统盘点.md) §二注意事项 1）：LPC `DEATH_ROOM->start_death(this_object())` 在 gate.c 中未定义（FluffOS 对不存在方法返回 0）。Python 实现通过 room enter 事件触发 NPC 剧情链（EffectComp），不需要 start_death 方法。

**death_count 反刷安全机制**（[09](../xkx-arch/09-灵魂系统盘点.md) §二注意事项 5 + [spec/layer_h](_enter_world_spec) invariant）：

- death_count > 200 且 combat_exp < 50000 的玩家登录时强制移入地狱/死刑室（/d/death/block 或 /d/death/hell）。
- 是平台级 fail-closed 反刷死亡机制，GovernanceSystem 在登录/还阳时检查。

### 4. 黑白无常剧情 call_out -> EffectComp 翻译

对照 [09](../xkx-arch/09-灵魂系统盘点.md) §二 + LPC `d/death/npc/wgargoyle.c` 源码。

**LPC 原始机制**（wgargoyle.c init + death_stage）：

```c
// wgargoyle.c init()
call_out("death_stage", 30, previous_object(), 0);

// death_stage(ob, stage)
tell_object(ob, death_msg[stage]);
if (++stage < sizeof(death_msg)) {
    call_out("death_stage", 5, ob, stage);  // 5 段，每段 5 秒
    return;
} else
    ob->reincarnate();  // stage 4 还阳
```

**翻译为 EffectComp**（ADR-0017 Effect 一等公民组件 + ADR-0022 崩溃恢复）：

- `EffectComp(effect_id="death_stage", kind="governance_dialog", target_id=<鬼魂eid>, source_id=<白无常NPCeid>, detail="wgargoyle", duration=<剩余段数>, tick_interval=5, next_tick=<触发tick>, flags=0)`。
- duration 语义：剧情段数（5 段，stage 0-4），每 tick_interval（5 秒）触发一段，duration 递减到 0 时还阳。
- tick_interval=5 对齐 LPC `call_out("death_stage", 5, ob, stage)` 的 5 秒间隔；首延 30 秒用 `next_tick = current_tick + 30` 实现。
- EffectComp 作为独立 effect 实体（ADR-0017 §2），target_id 指向鬼魂实体。

**与 ConditionSystem 的边界**（dissent 5 call_out 归属，[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 5 条）：

- ConditionSystem 是通用 condition 衰减引擎（killer/pker/jail 等 condition 衰减，[runtime/conditions.py](../../engine/src/xkx/runtime/conditions.py)）。
- **GovernanceSystem 拥有阴间剧情 EffectComp**：death_stage 是治理剧情（非通用 condition），由 GovernanceSystem 注册 ConditionHandler 子类型处理，不混入通用 ConditionSystem 的 on_tick。
- 边界明确：通用 condition（killer 100 tick 衰减）走 ConditionSystem；治理剧情（death_stage 5 段对话）走 GovernanceSystem 自有的 EffectComp handler。
- 两者都复用 EffectComp 组件（ADR-0017）+ ConditionTickResult 模式（ADR-0018），但 handler 分离。

**崩溃恢复**（ADR-0022 §6）：

- death_stage EffectComp 随鬼魂实体序列化（`duration`/`next_tick`/`tick_interval` 完整恢复）。
- 冷重启后按 `next_tick <= current_tick` 判断是否触发（ADR-0022 §6 next_tick 对齐：若 `next_tick < current_tick`，顺延一个周期，不补执行）。
- 崩溃期间剧情暂停（duration 不衰减），等价于"崩溃期间阴间时间冻结"。

**黑白无常差异**（对照 wgargoyle.c vs bgargoyle.c 源码）：

- 白无常（wgargoyle.c）：鬼门关入口，5 段对话 + 还阳。
- 黑无常（bgargoyle.c）：酆都城门，逻辑同白无常，额外检查 `is_ghost()`：活人闯入直接传送回 /d/city/wumiao（`ob->move("/d/city/wumiao")`）。
- Python 实现统一为 GovernanceSystem 的 death_stage handler，按 NPC 类型（detail 字段区分 wgargoyle/bgargoyle）分支处理。

### 5. 法院 PK 通缉（killer condition + 执法 NPC + 监狱服刑）

对照 [09](../xkx-arch/09-灵魂系统盘点.md) §五盘点 + [spec/layer_f_death.py](_killer_reward_spec) 规格 + LPC 源码（killer.c/pker.c/city_jail.c/xunbu.c/kexiu.c）。

**四区域通缉 condition**（对照 [09](../xkx-arch/09-灵魂系统盘点.md) §五通缉 condition 文件表）：

| condition | 覆盖区域 | 通缉时长 | LPC 源文件 |
|---|---|---|---|
| killer | 扬州/通用 | 100 tick | kungfu/condition/killer.c |
| xakiller | 西夏 | 100 tick | kungfu/condition/xakiller.c |
| dlkiller | 大理 | 100 tick | kungfu/condition/dlkiller.c |
| bjkiller | 北京（无 condition 文件） | 100 tick | 仅 apply_condition 施加 |
| pker | 红名/PK 冷却 | 累积 +120 tick | kungfu/condition/pker.c |

**统一为"通缉令"概念**（[09](../xkx-arch/09-灵魂系统盘点.md) §五注意事项 3）：

- LPC 硬编码四种区域通缉（killer/xakiller/dlkiller/bjkiller），且 bjkiller 无 condition 文件（依赖 condition 框容错加载）。
- Python 实现统一为 `WantedCondition(effect_id, region, duration)` 概念，按区域绑定执法者，而非硬编码四种类型。
- 区域字段（region: "city"|"xa"|"dl"|"bj"）绑定对应执法 NPC（巡捕/西夏侍卫/大理捕快/北京侍卫）。

**通缉施加路径**（[spec/layer_f](_killer_reward_spec) side_effect order=3 + [09] §五触发条件）：

1. **PK 杀人在城市区域**：killer_reward() 检测 `strsrch(file_name(env), "/d/city/") >= 0`，施加 killer condition 100 tick。
2. **攻击执法 NPC**：巡捕/捕头 accept_kill() 施加 killer condition 100 tick；北京侍卫 accept_kill/accept_fight() 施加 bjkiller condition 100 tick。
3. **攻击城市 NPC**：大量城市 NPC 的 accept_kill() 施加 killer condition 100 tick。
4. **大理/西夏区域犯罪**：大理 NPC 施加 dlkiller，西夏同理。
5. **PK 红名累积**：killer_reward() 中 PvP 且有 pking 标记时施加 pker condition +120 tick。

**执法 NPC 行为**（对照 LPC xunbu.c/bgargoyle.c 源码 + [09] §五）：

- 巡捕/捕头/侍卫 init() 检测 `query_condition("killer") > 0`，`call_out("kill_ob", 1, this_player())` 自动攻击。
- pursuer 标记使 NPC 跨房间追踪（follow_me，[09] §五关键函数 `follow_me`）。
- 巡捕限定在 /d/city/ 区域活动，离开时自动 go_home() 回城（对照 xunbu.c go_home）。
- **执法 NPC 行为是 NPC AI 平台层**（[09] §五注意事项 4），非 GovernanceSystem 直接管理：GovernanceSystem 施加通缉 condition，NPC AI 层（层 G）检测 condition 后触发追杀。

**审判收监**（对照 LPC kexiu.c do_proceed 源码 + [09] §五）：

- 提督李克秀 do_proceed() 按 PKS 分级量刑（硬编码 if-else，[09] §五注意事项 2）：
  - PKS > 99 => city_jail 500 tick
  - PKS > 74 => city_jail 300 tick
  - PKS > 49 => city_jail 200 tick
  - 已有 city_jail > 4 => city_jail 600 tick（累犯加重）
- 穿琵琶骨（`set("embedded", 1)`）、清空 inventory、转移经验给逮捕者、10 金赏金、全服通报。
- 受贿销案：`accept_object()` 收钱后将 killer condition 设为 0（金额 >= combat_exp/10）。
- 自我投案：PKS>19 且低效率的玩家找李克秀"工作"时直接被抓，city_jail 50 tick。

**监狱服刑 condition**（对照 LPC city_jail.c 源码 + [09] §五监狱 condition 文件表）：

| 监狱 condition | 监狱位置 | 刑期 |
|---|---|---|
| city_jail | 扬州衙门 /d/city/yamen | 50-600 tick |
| dali_jail | 大理 /d/dali/taihejie5 | 65 tick |
| bonze_jail | 少林 /d/shaolin/guangchang1 | 60 tick |

- 监狱 condition 到期时 move 出监狱房间（city_jail.c: `me->move("/d/city/yamen")`）+ 设置 startroom。
- 是 ConditionSystem 通用 condition 衰减（非 GovernanceSystem 自有 handler），到期触发 move 副作用。

**PKS 称号**（[09] §五 + [spec/layer_h_daemons.py] rankd 规格，后置 2.5）：

- PKS > 100 且 PKS > MKS 时称号变"土匪头"/"土匪婆"（rankd.c 80-82, 190-191）。
- 属 TitleSystem（2.5），非本 ADR 范围，但通缉状态查询接口须为 2.5 预留。

### 6. Wave 2 范围 vs 后续衔接

对照 [15](../xkx-arch/15-阶段2-子系统实施计划.md) §四 Wave 2 范围控制说明。

**Wave 2 做（不依赖 2.2/2.4 部分）**：

| 组件 | Wave 2 范围 | 依赖 |
|---|---|---|
| GovernanceSystem 平台级框架 | System 注册 + tick 驱动 + fail-closed 边界 + 与层 1 DSL/UGC CPK 隔离 | 无（2.1 Query 已就绪） |
| 阴间剧情骨架 | gate.c 物品销毁 + 黑白无常 death_stage EffectComp handler + 两条还阳路径骨架 | 无（EffectComp 已就绪，ADR-0017） |
| 法院通缉 condition 框架 | WantedCondition 类型注册 + killer/pker/city_jail condition 衰减（ConditionSystem 扩展） | ConditionSystem 已就绪（ADR-0018） |
| 通缉状态可序列化 | WantedCondition + 阴间进度 EffectComp 随实体序列化（ADR-0022） | StorageSystem 已就绪 |

**Wave 2 不做（待 2.2/2.4 衔接）**：

| 组件 | 衔接时机 | 依赖 |
|---|---|---|
| 完整阴间还阳闭环（die -> 阴间 -> 还阳） | 2.2 死亡轮回完成后 | 2.2 die()/reincarnate()/make_corpse() 实现 |
| 完整法院通缉/执法/服刑闭环（PK -> 通缉 -> 追杀 -> 收监） | 2.4 Combat 完成后 | 2.4 kill_ob()/killer_reward() combat 副作用链 |
| 执法 NPC AI（巡捕检测 condition -> kill_ob） | 2.4 Combat + 层 G NPC AI | 2.4 combat 启动 + NPC AI 平台层 |
| 审判收监完整流程（李克秀 do_proceed） | 2.4 Combat 后 | 2.4 combat + NPC交互 |

**衔接协议**：

- Wave 2 产出 GovernanceSystem 接口 + 阴间/法院 condition 类型注册，**接口稳定**（2.2/2.4 实现时不动 GovernanceSystem 框架）。
- 2.2 实现 die() 时，在副作用链中调用 `governance.enter_underworld(eid)`（阴间入口）+ `governance.apply_wanted(killer_eid, region)`（通缉施加）。
- 2.4 实现 killer_reward() 时，调用 `governance.apply_wanted(killer_eid, region)` 衔接法院通缉。
- 执法 NPC AI 在 2.4/层 G 实现时，调用 `governance.query_wanted(eid)` 检测通缉状态。

### 7. 治理 System tick 开销评估

对照 CLAUDE.md 不变量 tick=1s + compute<100ms（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §七性能优化备选）。

**GovernanceSystem tick 开销**：

- 阴间剧情 EffectComp：只处理 `next_tick <= tick` 的 EffectComp（非均匀 tick，ADR-0018 §3），1000 实体中阴间鬼魂数量极少（< 10），O(阴间实体数) 查询。
- 通缉 condition 衰减：复用 ConditionSystem on_tick（killer/pker/jail 等 condition 衰减），O(通缉实体数) 查询。
- 执法 NPC 检测：NPC AI 层（层 G）init() 事件驱动，非 tick 驱动（NPC 进入房间时检测，非每 tick 遍历）。

**开销评估**：

- GovernanceSystem tick 开销 << CombatSystem（T10 实测 CombatSystem 占 92%，tick p99 12.6ms）。
- 阴间鬼魂 + 通缉实体数量 << 1000（死亡是低频事件，通缉是 PK 副作用），O(n) 查询 n < 50。
- 不预建索引（对齐 ADR-0025 §3 线性扫描策略），tick profiler 实测瓶颈后再优化。

### 8. 通缉状态 + 阴间进度可序列化（ADR-0022 衔接）

对照 ADR-0022 §6 Effect 序列化与崩溃恢复。

**通缉状态序列化**：

- WantedCondition 作为 EffectComp 独立 effect 实体（target_id 指向被通缉实体），随实体序列化。
- `duration`/`next_tick`/`tick_interval` 完整恢复，冷重启后 ConditionSystem 下一 tick 按 `next_tick <= current_tick` 判断触发。
- 通缉状态崩溃不丢失：玩家崩溃前通缉 100 tick，重启后仍 100 tick（减去崩溃期间未触发的 tick，ADR-0022 §6 "崩溃期间 Effect 时间冻结"）。

**阴间进度序列化**：

- death_stage EffectComp 随鬼魂实体序列化（`duration` = 剩余剧情段数，`next_tick` = 下一段对话触发 tick）。
- 鬼魂标志（ghost=1）+ 阴间位置（Position.room_id = DEATH_ROOM）随玩家实体序列化。
- 冷重启后：鬼魂玩家仍在阴间，death_stage EffectComp 从存档时进度继续（崩溃期间剧情暂停，ADR-0022 §6）。
- **登录检查**（[spec/layer_h](_enter_world_spec) invariant "起始房间选择优先级：ghost -> DEATH_ROOM"）：玩家登录时检查 ghost 标志，ghost=1 则 startroom = DEATH_ROOM（断线重连回到阴间）。

**Marks 组件复用**：

- Marks.flags（set[str]）可存通缉相关标记（vendetta/pking/pktime 等 dbase key，ADR-0025 §5 后置 key 激活策略）。
- 2.6 激活后置 key：`vendetta` / `vendetta_mark` / `pking` / `pktime`（[ADR-0025](ADR-0025-query-index-layer.md) §5 表格）。

## 代码结构

### 新建 `engine/src/xkx/runtime/governance.py`

```python
# GovernanceSystem 平台级 fail-closed Python System
class GovernanceSystem(System):
    """世界观治理系统（平台级 fail-closed，ADR-0029）。

    治理逻辑硬编码，不落入 UGC 可编辑规则层。
    """

    name = "GovernanceSystem"

    def update(self, world: World, tick: int) -> None: ...

# 阴间死亡轮回
def enter_underworld(world: World, eid: int) -> None:
    """die() 触发阴间入口：ghost=1 + move(DEATH_ROOM) + gate.c 物品销毁 +
    启动 death_stage EffectComp（白无常 5 段剧情）。"""

def death_stage_handler(world: World, eff: EffectComp, tick: int) -> ConditionTickResult:
    """黑白无常剧情 EffectComp handler（GovernanceSystem 自有，非通用 ConditionSystem）。
    5 段对话，每段 5 秒，stage 4 还阳。"""

def reincarnate_at(world: World, eid: int, revive_room: str, drop_items: bool) -> None:
    """还阳：reincarnate()（层 F）+ 位置移动 + 物品处理（主路径丢弃/隐藏路径不丢弃）。"""

# 法院 PK 通缉
def apply_wanted(world: World, eid: int, region: str, duration: int = 100) -> None:
    """施加通缉 condition（killer/xakiller/dlkiller/bjkiller 统一为 WantedCondition）。"""

def query_wanted(world: World, eid: int) -> str | None:
    """查询通缉状态（返回 region 或 None，执法 NPC AI 用）。"""

def proceed_sentencing(world: World, eid: int, arrester_eid: int) -> int:
    """审判收监：按 PKS 分级量刑（PKS>99=>500/74=>300/49=>200）+ 穿琵琶骨 +
    经验转移 + 赏金。返回刑期 tick 数。"""

def bribe_clear_wanted(world: World, eid: int, amount: int) -> bool:
    """受贿销案：金额 >= combat_exp/10 时清除 killer condition。"""
```

### 扩展 `engine/src/xkx/runtime/conditions.py`

- 注册治理 condition 类型：`WantedCondition`（killer/xakiller/dlkiller/bjkiller 统一）+ `JailCondition`（city_jail/dali_jail/bonze_jail 统一）。
- ConditionHandler 扩展：支持 GovernanceSystem 注册的 death_stage handler（非通用 condition 衰减，是治理剧情）。

### 测试 `engine/tests/test_governance.py`

- **平台级 fail-closed 边界**：UGC 规则层不可修改通缉时长/量刑分级/gate.c 物品销毁（断言治理常量不可被层 1 DSL 覆盖）。
- **阴间死亡轮回**：die -> gate.c 物品销毁 -> 黑白无常 5 段剧情 -> 还阳路径（主路径 + 隐藏路径）。
- **gate.c 物品销毁副作用顺序**：make_corpse 先转移物品 -> ghost move -> gate.c init() 销毁剩余物品。
- **death_stage EffectComp**：5 段对话时序 + 崩溃恢复（duration/next_tick 恢复 + 崩溃期间剧情暂停）。
- **法院通缉**：PK 在城市区域 -> killer condition 100 tick + pker 红名累积 +120 tick。
- **审判收监**：PKS 分级量刑（99/74/49 阈值）+ 穿琵琶骨 + 经验转移。
- **受贿销案**：金额 >= combat_exp/10 清除 killer condition。
- **可序列化**：WantedCondition + death_stage EffectComp 序列化往返一致性 + 冷重启恢复。
- **hypothesis 属性测试**：通缉时长衰减属性 + 量刑分级单调性（PKS 越高刑期越长）。
- **test_theme_neutrality 硬门禁**：GovernanceSystem 源码无武侠语义（通缉/阴间/监狱是通用治理概念，非武侠烙印）。

## 简化台账（与 LPC 阴间/法院的差异）

| # | LPC 语义 | greenfield 实现 | 后置时机 | 关联 |
|---|---|---|---|---|
| 1 | 武林大会（d/bwdh/ 297 文件） | 不实现 | M3 后 | [09](../xkx-arch/09-灵魂系统盘点.md) §三 / [04](../xkx-arch/04-迁移路径与避坑清单.md) §六 |
| 2 | vote 投票（cmds/std/vote/） | 不实现 | M3 后 | [09](../xkx-arch/09-灵魂系统盘点.md) §四 |
| 3 | intermud（adm/daemons/network/ 24 服务） | 不实现 | 砍掉/无限期后置 | [09](../xkx-arch/09-灵魂系统盘点.md) §六（违反收缩约束） |
| 4 | courthouse 反机器人审判（d/wizard/courthouse.c） | 不实现 | M3 后视需求 | [09](../xkx-arch/09-灵魂系统盘点.md) §五注意事项 5 |
| 5 | 尸体四阶段腐烂（新鲜->腐烂->骸骨->骨灰） | 不实现 | 后置（2.2/2.6 后） | [09](../xkx-arch/09-灵魂系统盘点.md) §二注意事项 7 / [spec/layer_f](_make_corpse_spec) notes |
| 6 | 四区域通缉硬编码（killer/xakiller/dlkiller/bjkiller） | 统一为 WantedCondition + region 字段 | 本 ADR 实现 | [09](../xkx-arch/09-灵魂系统盘点.md) §五注意事项 3 |
| 7 | wgargoyle1.c fightdie 分支（noloseroom） | 不实现（LPC 未完成特性） | 砍掉 | [09](../xkx-arch/09-灵魂系统盘点.md) §二注意事项 6 |
| 8 | exec 代理战斗体（fighter.c dummy） | 不实现（武林大会专属） | M3 后（随武林大会） | [09](../xkx-arch/09-灵魂系统盘点.md) §三注意事项 1 |
| 9 | 完整阴间还阳闭环（die -> 阴间 -> 还阳） | Wave 2 只做骨架，2.2 衔接完整闭环 | 2.2 完成后 | [15](../xkx-arch/15-阶段2-子系统实施计划.md) §四 |
| 10 | 完整法院通缉/执法/服刑闭环 | Wave 2 只做 condition 框架，2.4 衔接完整闭环 | 2.4 完成后 | [15](../xkx-arch/15-阶段2-子系统实施计划.md) §四 |
| 11 | 执法 NPC AI（巡捕检测 condition -> kill_ob） | 不实现（层 G NPC AI 范畴） | 2.4 + 层 G | [09](../xkx-arch/09-灵魂系统盘点.md) §五注意事项 4 |
| 12 | PKS 称号（"土匪头"/"土匪婆"） | 不实现（TitleSystem 范畴） | 2.5 | [09](../xkx-arch/09-灵魂系统盘点.md) §五 / rankd.c |
| 13 | pker > 240 命令层门禁（kill/feed/wei/throw） | 不实现（命令 precondition 范畴） | 2.4 命令层 | [09](../xkx-arch/09-灵魂系统盘点.md) §五注意事项 6 |
| 14 | 赌场系统（gamble_room.c） | 不实现（随武林大会） | M3 后 | [09](../xkx-arch/09-灵魂系统盘点.md) §三注意事项 6 |
| 15 | start_death 方法（LPC 空调用） | 不实现（room enter 事件触发） | 砍掉 | [09](../xkx-arch/09-灵魂系统盘点.md) §二注意事项 1 |

> 简化台账与 [ADR-0002](ADR-0002-resolve-attack-extraction.md) / [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) / [ADR-0025](ADR-0025-query-index-layer.md) §简化台账模式一致。砍掉项 = greenfield 不实现（LPC 特有机制或后置阶段）；后置项 = 对应子系统/阶段实现时补。

## 验收标准（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.6）

- [ ] 代表性元素选择：阴间死亡轮回 + 法院 PK 通缉（2 个），276 文件武林大会/vote/intermud 后置 M3（简化台账 1-3）
- [ ] GovernanceSystem 平台级 fail-closed：治理逻辑硬编码 Python，不通过层 1 DSL/UGC CPK 暴露（UGC 不可修改通缉时长/量刑分级/gate.c 物品销毁）
- [ ] 阴间路径骨架：die -> gate.c 物品销毁 -> 黑白无常 5 段剧情 EffectComp -> 还阳（主路径 + 隐藏路径）
- [ ] gate.c 物品销毁副作用顺序正确：make_corpse 先转移物品 -> ghost move -> gate.c init() 销毁剩余物品
- [ ] death_stage EffectComp 崩溃恢复：duration/next_tick 恢复 + 崩溃期间剧情暂停
- [ ] 法院通缉 condition 框架：WantedCondition（killer/xakiller/dlkiller/bjkiller 统一）+ pker 红名累积 + 监狱 condition
- [ ] 审判收监：PKS 分级量刑（99/74/49 阈值）+ 穿琵琶骨 + 经验转移
- [ ] 通缉状态 + 阴间进度可序列化：WantedCondition + death_stage EffectComp 序列化往返一致性 + 冷重启恢复
- [ ] Wave 2 范围控制：只做不依赖 2.2/2.4 部分（框架 + 骨架），完整闭环待 2.2/2.4 衔接
- [ ] tick 开销评估：GovernanceSystem tick 开销 << CombatSystem（不破 tick p99 100ms）
- [ ] hypothesis 属性测试：通缉时长衰减 + 量刑分级单调性
- [ ] 现有 1101 tests 不回归
- [ ] ruff 全过（行长 100，中文按字符数计）
- [ ] test_theme_neutrality 硬门禁持续通过（GovernanceSystem 无武侠烙印）

## 关联 dissent

| dissent | 本 ADR 应对 |
|---|---|
| **5（themed 治理）** | GovernanceSystem 平台级 fail-closed Python，治理逻辑硬编码，不落入层 1 DSL/UGC CPK 可编辑规则层（§决策 2）；UGC 只能触发治理不能修改规则 |
| **10（平台特性范围过载）** | 5 灵魂系统只含 2 代表性元素（阴间 + 法院），276 文件武林大会/vote/intermud 后置 M3（§决策 1 + 简化台账 1-3） |
| **5 延伸（call_out 归属）** | 阴间剧情 call_out（黑白无常 5 段延时对话）翻译为 EffectComp，GovernanceSystem 自有 death_stage handler，与 ConditionSystem 边界明确（§决策 4） |

## 不做（范围边界）

- **不实现 276 文件武林大会**：后置 M3（[04](../xkx-arch/04-迁移路径与避坑清单.md) §六），exec 代理战斗体/赌场/比武招亲随武林大会后置。
- **不实现 vote 投票**：后置 M3（玩家自治治理基础设施，UGC 开放前必须就位但非核心循环）。
- **不实现 intermud**：砍掉/无限期后置（违反收缩约束第 1/3 条，不考虑分布式架构/分布式网关）。
- **不实现完整 courthouse 反机器人审判**：后置 M3 后视需求（与 PK 法院同名但不同系统，是巫师工具/平台安全机制）。
- **不实现尸体四阶段腐烂**：后置（2.2/2.6 后，[spec/layer_f](_make_corpse_spec) notes 标注后置）。
- **不实现完整阴间还阳闭环**：Wave 2 只做骨架（gate.c 物品销毁 + death_stage EffectComp + 还阳路径骨架），die()/reincarnate()/make_corpse() 由 2.2 实现，2.6 衔接。
- **不实现完整法院通缉/执法/服刑闭环**：Wave 2 只做 condition 框架（WantedCondition + 监狱 condition），killer_reward() combat 副作用链由 2.4 实现，执法 NPC AI 由层 G 实现，2.6 衔接。
- **不实现执法 NPC AI**：层 G NPC AI 范畴（巡捕检测 condition -> kill_ob），2.4 + 层 G 实现。
- **不实现 PKS 称号**：TitleSystem 范畴（2.5），本 ADR 只预留通缉状态查询接口。
- **不实现 pker > 240 命令层门禁**：命令 precondition 范畴（kill/feed/wei/throw 命令），2.4 命令层实现。
- **不修改 LPC 源**（只读规格）。
- **不实现治理规则可配置化**：治理常量（通缉时长 100 tick / 量刑分级 PKS 阈值 / 黑白无常 5 段）硬编码 Python，不暴露配置接口（fail-closed，对齐 [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §三 Q2 收敛"反作弊迭代慢是 fail-closed 的正确取舍"）。

## 开放问题（需 lead 裁决）

1. **GovernanceSystem 与 ConditionSystem 的 handler 注册机制**：本 ADR 决策 death_stage 由 GovernanceSystem 自有 handler 处理（非通用 ConditionSystem on_tick），但两者都复用 EffectComp + ConditionTickResult 模式。具体 handler 注册机制（GovernanceSystem 注册子 handler 到 ConditionSystem？还是 GovernanceSystem 独立遍历 EffectComp？）需 2.6 实现 agent 在编码时定，本 ADR 只定边界（治理剧情 vs 通用 condition）。倾向：GovernanceSystem 独立遍历 `effect_id="death_stage"` 的 EffectComp（按 effect_id 过滤），不混入 ConditionSystem 通用 on_tick。

2. **法院通缉 condition 衰减由 ConditionSystem 还是 GovernanceSystem 拥有**：killer/pker/city_jail 等 condition 衰减是通用 condition 语义（每 tick duration-1），自然归属 ConditionSystem；但通缉施加/清除/量刑是治理逻辑，归属 GovernanceSystem。边界：ConditionSystem 管衰减（duration-1 + 到期移除），GovernanceSystem 管施加/清除/量刑（apply_wanted/proceed_sentencing/bribe_clear_wanted）。此边界本 ADR 已定，但实现时须确认 ConditionSystem 的 on_tick 不触发治理副作用（如 city_jail 到期 move 出监狱是 condition 副作用还是 GovernanceSystem 副作用？）。倾向：city_jail 到期 move 是 condition 到期副作用，由 ConditionSystem 触发（condition daemon 的 update_condition 返回 0 时触发，对齐 LPC city_jail.c update_condition 语义）。

3. **阴间位置（DEATH_ROOM/REVIVE_ROOM）是硬编码房间路径还是配置化**：LPC 硬编码 `/d/death/gate.c`（DEATH_ROOM）+ REVIVE_ROOM 宏。greenfield 房间系统尚未实现（层 D 世界，后置），2.6 Wave 2 阴间骨架如何在不依赖完整房间系统的情况下定义阴间位置？倾向：用 room_id 字符串常量（如 `"death/gate"`），房间系统实现后映射到实际房间实体，2.6 不依赖房间系统完整实现。

*最后更新：2026-07-12*
