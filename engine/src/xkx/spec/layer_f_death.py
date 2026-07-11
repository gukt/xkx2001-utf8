"""层 F：死亡轮回 -- LPC 规格提取（ADR-0010）。

覆盖范围：
- ``feature/damage.c`` -- die() / unconcious() / revive() / reincarnate() / heal_up()
- ``adm/daemons/combatd.c`` -- death_penalty() / killer_reward() / announce()
- ``adm/daemons/chard.c`` -- make_corpse() / break_relation()
- ``inherit/char/char.c`` -- heart_beat() 中的死亡触发条件

核心契约要点：
1. **die 与 unconcious 的触发条件区别**：
   - heart_beat 中 eff_qi<0 或 eff_jing<0 -> 直接 die()（致命伤死亡）
   - heart_beat 中 qi<0 或 jing<0 或 jingli<0 ->
     若 living(this_object()) -> unconcious()（首次昏迷）
     若已昏迷（disable_type == " <昏迷不醒>"）-> die()（昏迷中再次触发=死亡）
   - 即：qi/jing 降到 0 以下先昏迷，昏迷中再受创则死亡。eff_qi/eff_jing 降到 0 以下直接死亡。
2. **death_penalty 无随机性**：经验/技能/属性扣减全部为确定性公式（无 random() 调用）。
3. **make_corpse 的物品转移完整性**：死者所有 inventory 物品转移到尸体（含装备重穿尝试）。
4. **reincarnate 的状态恢复**：qi/jing/jingli/neili 恢复到 max 值，ghost 标志清除。

不做（边界）：
- 阴间世界流程（黑白无常/还阳路径，后置到阶段 1）
- 尸体四阶段腐烂（后置）
- PvP 通缉机制细节（后置）
- combat 上游（do_attack 属层 E，仅提取 do_attack 触发 die 的调用点在副作用里）
- setup_char 完整规格（属层 H，仅引用 make_corpse 相关部分）
- receive_damage / receive_wound / receive_heal / receive_curing（属层 E）
- skill_death_penalty 内部逻辑（属层 H: F_SKILL，仅在 death_penalty 副作用中引用）
"""

from __future__ import annotations

from enum import StrEnum

from xkx.spec.base import (
    FunctionSignature,
    FunctionSpec,
    Invariant,
    LayerSpec,
    LPCParam,
    Postcondition,
    Precondition,
    RandomSpec,
    SideEffect,
    SideEffectType,
)

# ---------------------------------------------------------------------------
# 层 F 特定模型
# ---------------------------------------------------------------------------


class DeathState(StrEnum):
    """角色死亡状态（从 heart_beat 触发逻辑提取）。"""

    ALIVE = "alive"
    """正常存活状态。"""

    UNCONSCIOUS = "unconscious"
    """昏迷：qi/jing/jingli < 0 且 living() 时触发，disable_player(' <昏迷不醒>')。"""

    DYING = "dying"
    """濒死：eff_qi 或 eff_jing < 0 时直接触发 die()。"""

    DEAD = "dead"
    """已死亡：die() 完成后玩家 ghost=1，NPC 被 destruct。"""

    GHOST = "ghost"
    """鬼魂：玩家死亡后移到 DEATH_ROOM，reincarnate() 后恢复。"""


# ---------------------------------------------------------------------------
# heart_beat 死亡触发条件（inherit/char/char.c:60-169）
# ---------------------------------------------------------------------------

_heart_beat_death_trigger = FunctionSpec(
    signature=FunctionSignature(
        name="heart_beat",
        params=[],
        return_type="void",
        lpc_file="inherit/char/char.c",
        line_range=(60, 169),
    ),
    preconditions=[
        Precondition(
            description="对象已 setup()，heart_beat 已启动",
            lpc_expr="set_heart_beat(1) in setup()",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="eff_qi<0 或 eff_jing<0 时调用 die()（致命伤直接死亡，不经过昏迷）",
            state_change="remove_all_enemy(); die(); return",
            kind="effect",
        ),
        Postcondition(
            description="qi<0 或 jing<0 或 jingli<0 时：living() 则 unconcious()；已昏迷则 die()",
            state_change="remove_all_enemy(); living(this_object()) ? unconcious() : die()",
            kind="effect",
        ),
        Postcondition(
            description="非死亡/昏迷时执行 attack() / heal_up() / update_condition() 等常规 tick 逻辑",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="死亡判定优先级：eff_qi/eff_jing < 0（直接 die）> qi/jing/jingli < 0（先 unconcious 再 die）",
            lpc_expr=(
                "if(eff_qi<0||eff_jing<0) die(); "
                "else if(qi<0||jing<0||jingli<0) "
                "living(this_object())?unconcious():die()"
            ),
            scope="function",
        ),
        Invariant(
            description="昏迷中再受创（qi/jing 再次 <0 且 !living）升级为 die()",
            lpc_expr='disable_type == " <昏迷不醒>" => die()',
            scope="function",
        ),
        Invariant(
            description="wimpy 自动逃跑：qi/jing/jingli 百分比 <= wimpy_ratio 时触发 GO_CMD->do_flee",
            lpc_expr="qi*100/max_qi <= wimpy_ratio || jing*100/max_jing <= wimpy_ratio || ...",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="清零 cmd_count / channel_msg_cnt（每 tick 重置）",
            lpc_call="clear_cmd_count(); set_temp('channel_msg_cnt', 0)",
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="neili/jingli/jing 上限钳位（不超过 max*2）",
            lpc_call="if(my['neili']>my['max_neili']*2) my['neili']=my['max_neili']*2",
            target="this_object",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="致命伤判定：eff_qi<0 或 eff_jing<0 -> remove_all_enemy() + die() + return",
            lpc_call="if(eff_qi<0||eff_jing<0) { remove_all_enemy(); die(); return; }",
            target="this_object",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="昏迷/死亡判定：qi<0||jing<0||jingli<0 -> remove_all_enemy()；living()?unconcious():die()",
            lpc_call="if(qi<0||jing<0||jingli<0) { remove_all_enemy(); living()?unconcious():die(); return; }",
            target="this_object",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="busy 状态 -> continue_action() + return",
            lpc_call="if(is_busy()) { continue_action(); return; }",
            target="this_object",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="wimpy 判定：qi/jing/jingli 百分比 <= wimpy_ratio -> GO_CMD->do_flee",
            lpc_call="if(wimpy_ratio>0 && qi*100/max_qi<=wimpy_ratio) GO_CMD->do_flee(this_object())",
            target="this_object",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.EXTERNAL,
            description="attack() 执行战斗回合（委托 COMBAT_D->fight，属层 E）",
            lpc_call="attack()",
            target="this_object",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.CALL_OUT,
            description="非均匀 tick：tick 递减到 0 时执行 update_condition() + heal_up()，重置 tick=5+random(10)",
            lpc_call="if(tick--) return; tick=5+random(10); update_condition(); heal_up()",
            target="this_object",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.STATE_MUTATION,
            description="空闲心跳关闭：非战斗+非交互+heal_up 无更新+环境无交互对象 -> set_heart_beat(0)",
            lpc_call="if(!is_fighting()&&!interactive()&&!heal_up()) set_heart_beat(0)",
            target="this_object",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(10)",
            probability_model="tick = 5 + random(10)，即 5-14 tick 的非均匀周期",
            semantic="非均匀 tick 间隔（heart_beat 周期内子 tick 计数）",
            seed_inputs=[],
            determinism_note="非战斗随机性，不影响 combat-only 确定性范围。",
        ),
    ],
    notes=(
        "heart_beat 是死亡/昏迷的唯一触发入口。触发条件分两级："
        "(1) eff_qi/eff_jing < 0 -> 直接 die()（致命伤）；"
        "(2) qi/jing/jingli < 0 -> 首次 living() 则 unconcious()，"
        "已昏迷（disable_type==' <昏迷不醒>'）则 die()。"
        "这意味着玩家不会因为 qi 降到 0 而直接死亡，先昏迷，昏迷中再受创才死。"
        "但 eff_qi/eff_jing（有效上限）降到 0 以下是直接死亡。"
    ),
)


# ---------------------------------------------------------------------------
# unconcious()（feature/damage.c:105-135）
# ---------------------------------------------------------------------------

_unconcious = FunctionSpec(
    signature=FunctionSignature(
        name="unconcious",
        params=[],
        return_type="void",
        lpc_file="feature/damage.c",
        line_range=(105, 135),
    ),
    preconditions=[
        Precondition(
            description="对象必须处于 living 状态（!living 则直接 return）",
            lpc_expr="living(this_object())",
            kind="require",
        ),
        Precondition(
            description="巫师且设置了 env/immortal 则不昏迷",
            lpc_expr='wizardp(this_object()) && query("env/immortal")',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="清零 qi/jing/jingli 到 0，设置 block_msg/all 遮罩",
            state_change="set('jing',0); set('qi',0); set('jingli',0); set_temp('block_msg/all',1)",
            kind="effect",
        ),
        Postcondition(
            description="disable_player(' <昏迷不醒>') 使对象进入昏迷状态",
            state_change='disable_player(" <昏迷不醒>")',
            kind="effect",
        ),
        Postcondition(
            description="安排随机延迟后自动 revive：call_out('revive', random(100-con)+30)",
            state_change="call_out('revive', random(100-con)+30)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="昏迷后 living() 返回 0（disable_player 生效）",
            lpc_expr="!living(this_object()) after unconcious()",
            scope="function",
        ),
        Invariant(
            description="昏迷期间所有消息被 block_msg/all 遮罩屏蔽",
            scope="function",
        ),
        Invariant(
            description="昏迷后 heart_beat 中再次触发 qi<0 -> 升级为 die()",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="若有 last_damage_from，调用 COMBAT_D->winner_reward(defeater, this_object())",
            lpc_call="COMBAT_D->winner_reward(defeater, this_object())",
            target="defeater",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="记录 last_fainted_from（userp defeater 时设置临时标记）",
            lpc_call='set_temp("last_fainted_from", defeater->query("id"))',
            target="this_object",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="remove_all_enemy() 清除所有敌人（脱离战斗）",
            lpc_call="this_object()->remove_all_enemy()",
            target="this_object",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="interrupt_me() 中断所有进行中的动作（打坐/吐纳/静坐等）",
            lpc_call="this_object()->interrupt_me()",
            target="this_object",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="dismiss_team() 解散队伍",
            lpc_call="this_object()->dismiss_team()",
            target="this_object",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="向昏迷者输出 '你的眼前一黑，接著什么也不知道了....'（HIR 红色系统消息）",
            lpc_call='message("system", HIR "\\n你的眼前一黑，接著什么也不知道了....\\n\\n" NOR, this_object())',
            target="this_object",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="disable_player(' <昏迷不醒>') 禁用命令输入",
            lpc_call='this_object()->disable_player(" <昏迷不醒>")',
            target="this_object",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="set('jing',0); set('qi',0); set('jingli',0) 清零三项属性",
            lpc_call='set("jing",0); set("qi",0); set("jingli",0)',
            target="this_object",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.STATE_MUTATION,
            description="set_temp('block_msg/all',1) 屏蔽所有消息接收",
            lpc_call='set_temp("block_msg/all", 1)',
            target="this_object",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="COMBAT_D->announce(this_object(), 'unconcious') 向房间输出昏迷消息",
            lpc_call='COMBAT_D->announce(this_object(), "unconcious")',
            target="room",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.CALL_OUT,
            description="call_out('revive', random(100-con)+30) 安排 30~129 秒后自动苏醒",
            lpc_call="call_out('revive', random(100 - query('con')) + 30)",
            target="this_object",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(100 - query('con')) + 30",
            probability_model="昏迷持续时间 = 30 + random(100-con)，con 越高恢复越快（30~129 秒）",
            semantic="昏迷自动苏醒延迟，体质 con 影响恢复速度",
            seed_inputs=["con"],
            determinism_note="非战斗随机性，不影响 combat-only 确定性范围。",
        ),
    ],
    notes=(
        "unconcious 与 die 的核心区别：unconcious 后对象仍存在，安排 revive 自动恢复；"
        "die 后玩家变为 ghost 移到 DEATH_ROOM，NPC 被 destruct。"
        "unconcious 的触发条件是 qi/jing/jingli < 0 且 living()。"
        "若 !living()（已昏迷），heart_beat 会调用 die() 而非 unconcious()。"
    ),
)


# ---------------------------------------------------------------------------
# revive()（feature/damage.c:137-150）
# ---------------------------------------------------------------------------

_revive = FunctionSpec(
    signature=FunctionSignature(
        name="revive",
        params=[
            LPCParam(name="quiet", lpc_type="int", description="quiet=1 安静苏醒（不输出消息、不 announce）；quiet=0（默认）输出苏醒消息"),
        ],
        return_type="void",
        lpc_file="feature/damage.c",
        line_range=(137, 150),
        is_varargs=True,
    ),
    preconditions=[
        Precondition(
            description="对象当前处于昏迷状态（有 pending revive call_out）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="remove_call_out('revive') 取消待执行的苏醒定时器",
            state_change="remove_call_out('revive')",
            kind="effect",
        ),
        Postcondition(
            description="若 environment 是 character（被人背着），逐层 move 到非 character 环境",
            state_change="this_object()->move(environment(environment()))",
            kind="effect",
        ),
        Postcondition(
            description="enable_player() 恢复命令输入能力",
            state_change="enable_player()",
            kind="effect",
        ),
        Postcondition(
            description="quiet=0 时输出苏醒消息 + announce；quiet=1 仅清除 block_msg",
            state_change="set_temp('block_msg/all', 0)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="revive 后 living() 返回 1（enable_player 生效）",
            lpc_expr="living(this_object()) after revive()",
            scope="function",
        ),
        Invariant(
            description="revive 后 block_msg/all 被清除（消息接收恢复）",
            scope="function",
        ),
        Invariant(
            description="revive 不恢复 qi/jing/jingli（它们在 unconcious 中被设为 0，需 heal_up 逐渐恢复）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.CALL_OUT,
            description="remove_call_out('revive') 取消苏醒定时器",
            lpc_call="remove_call_out('revive')",
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="若 environment()->is_character() 则逐层 move 到非 character 环境",
            lpc_call="while(environment()->is_character()) this_object()->move(environment(environment()))",
            target="this_object",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="enable_player() 恢复命令输入",
            lpc_call="this_object()->enable_player()",
            target="this_object",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="quiet=0 时输出 '慢慢地你终于又有了知觉....'（HIY 黄色系统消息）",
            lpc_call='message("system", HIY "\\n慢慢地你终于又有了知觉....\\n\\n" NOR, this_object())',
            target="this_object",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="quiet=0 时 COMBAT_D->announce(this_object(), 'revive') 向房间输出苏醒消息",
            lpc_call='COMBAT_D->announce(this_object(), "revive")',
            target="room",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="set_temp('block_msg/all', 0) 恢复消息接收",
            lpc_call='set_temp("block_msg/all", 0)',
            target="this_object",
        ),
    ],
    notes=(
        "revive 由 unconcious 的 call_out 定时触发，或由 die() 中 !living() 时强制调用 revive(1)。"
        "die() 中的 revive(1) 是为了处理 '已昏迷再受创死亡' 的场景：先安静苏醒再执行死亡流程。"
    ),
)


# ---------------------------------------------------------------------------
# die()（feature/damage.c:152-253）
# ---------------------------------------------------------------------------

_die = FunctionSpec(
    signature=FunctionSignature(
        name="die",
        params=[],
        return_type="void",
        lpc_file="feature/damage.c",
        line_range=(152, 253),
    ),
    preconditions=[
        Precondition(
            description="对象有 environment（environment(this_object()) 非 null）",
            lpc_expr="environment(this_object())",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="no_death 房间中玩家死亡转为 unconcious（不真正死亡）",
            state_change='if(env->query("no_death") && userp) unconcious(); remove_call_out("revive"); return',
            kind="effect",
        ),
        Postcondition(
            description="若 !living 则先 revive(1) 安静苏醒（处理昏迷中死亡场景）",
            state_change="if(!living(this_object())) revive(1)",
            kind="effect",
        ),
        Postcondition(
            description="巫师且 env/immortal 则不死亡",
            state_change='if(wizardp && query("env/immortal")) return',
            kind="guard",
        ),
        Postcondition(
            description="玩家死亡后：qi/jing/eff_qi/eff_jing 设为 1，jingli 设为 1",
            state_change='set("jing",1); set("eff_jing",1); set("qi",1); set("eff_qi",1); set("jingli",1)',
            kind="effect",
        ),
        Postcondition(
            description="玩家死亡后 ghost=1，move 到 DEATH_ROOM（/d/death/gate.c）",
            state_change="ghost=1; this_object()->move(DEATH_ROOM); DEATH_ROOM->start_death(this_object())",
            kind="effect",
        ),
        Postcondition(
            description="NPC 死亡后被 destruct(this_object())",
            state_change="destruct(this_object())",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="die 后 no_death 房间的玩家不会真正死亡，转为 unconcious",
            lpc_expr='env->query("no_death") && userp(this_object()) => unconcious()',
            scope="function",
        ),
        Invariant(
            description="玩家死亡后 ghost=1（is_ghost() 返回 1），直到 reincarnate() 清除",
            lpc_expr="ghost=1 after die()",
            scope="class",
        ),
        Invariant(
            description="die 中先 clear_condition 清除所有状态（毒/特殊状态等）",
            lpc_expr="this_object()->clear_condition()",
            scope="function",
        ),
        Invariant(
            description="玩家死亡后存档（save()），防止回档复活",
            lpc_expr="this_object()->save()",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="no_death 房间玩家判定：转 unconcious + remove_call_out('revive') + return",
            lpc_call='if(env->query("no_death") && userp) { unconcious(); remove_call_out("revive"); return; }',
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="若 !living 则 revive(1) 安静苏醒（昏迷中死亡场景）",
            lpc_call="if(!living(this_object())) revive(1)",
            target="this_object",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="巫师 immortal 检查：wizardp && env/immortal 则 return",
            lpc_call='if(wizardp(this_object()) && query("env/immortal")) return',
            target="this_object",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="clear_condition() 清除所有状态（毒/特殊状态等）",
            lpc_call="this_object()->clear_condition()",
            target="this_object",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="delete('poisoner') 清除投毒者标记",
            lpc_call='this_object()->delete("poisoner")',
            target="this_object",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="COMBAT_D->announce(this_object(), 'dead') 向房间输出死亡消息",
            lpc_call='COMBAT_D->announce(this_object(), "dead")',
            target="room",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.EXTERNAL,
            description="玩家且非 no_death 房间：COMBAT_D->death_penalty(this_object()) 执行死亡惩罚",
            lpc_call='if(userp && !env->query("no_death")) COMBAT_D->death_penalty(this_object())',
            target="this_object",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.EXTERNAL,
            description="若有 killer 对象：set_temp('my_killer', killer->id) + COMBAT_D->killer_reward(killer, victim)",
            lpc_call='set_temp("my_killer", killer->query("id")); COMBAT_D->killer_reward(killer, this_object())',
            target="killer",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="无 killer 对象但为玩家：通过阿庆嫂 NPC 发谣言频道消息（被杀/莫名其妙死了）",
            lpc_call='CHANNEL_D->do_channel(rum_ob, "rumor", sprintf(...))',
            target="channel",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.EXTERNAL,
            description="玩家死亡日志：log_file('PKILL_DATA'/'PLAYER_DEATH') 记录死因和击杀者",
            lpc_call='log_file("PLAYER_DEATH", sprintf(...))',
            target="log",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="CHAR_D->make_corpse(this_object(), killer) 生成尸体并 move 到当前房间",
            lpc_call='corpse = CHAR_D->make_corpse(this_object(), killer); corpse->move(environment())',
            target="corpse",
        ),
        SideEffect(
            order=12,
            kind=SideEffectType.STATE_MUTATION,
            description="remove_all_killer() 清除所有追杀关系 + 房间内对象 remove_killer(this_object())",
            lpc_call="this_object()->remove_all_killer(); all_inventory(env)->remove_killer(this_object())",
            target="this_object",
        ),
        SideEffect(
            order=13,
            kind=SideEffectType.STATE_MUTATION,
            description="玩家：interrupt_me()（若 busy）+ 设 qi/jing/eff_qi/eff_jing/jingli = 1",
            lpc_call='set("jing",1); set("eff_jing",1); set("qi",1); set("eff_qi",1); set("jingli",1)',
            target="this_object",
        ),
        SideEffect(
            order=14,
            kind=SideEffectType.STATE_MUTATION,
            description="no_death 房间玩家：eff_jing/eff_qi 恢复到 max 值 + return（不进入阴间）",
            lpc_call='if(env->query("no_death")) { set("eff_jing",query("max_jing")); set("eff_qi",query("max_qi")); return; }',
            target="this_object",
        ),
        SideEffect(
            order=15,
            kind=SideEffectType.STATE_MUTATION,
            description="玩家：dismiss_team() 解散队伍",
            lpc_call="this_object()->dismiss_team()",
            target="this_object",
        ),
        SideEffect(
            order=16,
            kind=SideEffectType.PERSISTENCE,
            description="玩家：save() 存档（防止回档复活）",
            lpc_call="this_object()->save()",
            target="this_object",
        ),
        SideEffect(
            order=17,
            kind=SideEffectType.STATE_MUTATION,
            description="玩家：ghost=1 设置鬼魂标志",
            lpc_call="ghost = 1",
            target="this_object",
        ),
        SideEffect(
            order=18,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="玩家：move(DEATH_ROOM) 移到阴间入口（/d/death/gate.c）",
            lpc_call="this_object()->move(DEATH_ROOM)",
            target="this_object",
        ),
        SideEffect(
            order=19,
            kind=SideEffectType.EXTERNAL,
            description="玩家：DEATH_ROOM->start_death(this_object()) 启动阴间流程",
            lpc_call="DEATH_ROOM->start_death(this_object())",
            target="this_object",
        ),
        SideEffect(
            order=20,
            kind=SideEffectType.EXTERNAL,
            description="玩家：MARRY_D->break_marriage(this_object()) 解除婚姻",
            lpc_call="MARRY_D->break_marriage(this_object())",
            target="this_object",
        ),
        SideEffect(
            order=21,
            kind=SideEffectType.EXTERNAL,
            description="玩家：风清扬弟子 CHAR_D->break_relation(this_object()) 解除师徒关系",
            lpc_call='if(family/master_id=="feng qingyang") CHAR_D->break_relation(this_object())',
            target="this_object",
        ),
        SideEffect(
            order=22,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="NPC：destruct(this_object()) 销毁对象",
            lpc_call="destruct(this_object())",
            target="this_object",
        ),
    ],
    notes=(
        "die() 是死亡主流程，核心分支：no_death 房间玩家转 unconcious、玩家死亡进阴间、NPC 死亡被 destruct。"
        "die 中的 revive(1) 处理 '昏迷中再受创死亡' 场景：先安静苏醒再执行死亡流程。"
        "玩家死亡后 qi/jing 等设为 1（非 0），因为 0 会在下一 tick heart_beat 中再次触发 unconcious/die。"
        "DEATH_ROOM='/d/death/gate.c'，阴间流程（黑白无常/还阳）后置到阶段 1。"
    ),
)


# ---------------------------------------------------------------------------
# reincarnate()（feature/damage.c:255-264）
# ---------------------------------------------------------------------------

_reincarnate = FunctionSpec(
    signature=FunctionSignature(
        name="reincarnate",
        params=[],
        return_type="void",
        lpc_file="feature/damage.c",
        line_range=(255, 264),
    ),
    preconditions=[
        Precondition(
            description="对象当前为 ghost 状态（is_ghost() 返回 1）",
            lpc_expr="ghost == 1",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="ghost 标志清除为 0",
            state_change="ghost = 0",
            kind="effect",
        ),
        Postcondition(
            description="qi/jing/eff_qi/eff_jing 恢复到 max 值",
            state_change='set("jing",query("max_jing")); set("qi",query("max_qi")); set("eff_jing",query("max_jing")); set("eff_qi",query("max_qi"))',
            kind="effect",
        ),
        Postcondition(
            description="jingli/neili 恢复到 max 值",
            state_change='set("jingli",query("max_jingli")); set("neili",query("max_neili"))',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="reincarnate 后 is_ghost() 返回 0",
            lpc_expr="ghost == 0 after reincarnate()",
            scope="class",
        ),
        Invariant(
            description="reincarnate 后所有核心属性恢复到 max（完整恢复，非渐进）",
            lpc_expr="qi==max_qi && jing==max_jing && eff_qi==max_qi && eff_jing==max_jing && jingli==max_jingli && neili==max_neili",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="ghost = 0 清除鬼魂标志",
            lpc_call="ghost = 0",
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="set('jing', max_jing); set('qi', max_qi) 恢复精/气",
            lpc_call='set("jing", query("max_jing")); set("qi", query("max_qi"))',
            target="this_object",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="set('eff_jing', max_jing); set('eff_qi', max_qi) 恢复有效精/气上限",
            lpc_call='set("eff_jing", query("max_jing")); set("eff_qi", query("max_qi"))',
            target="this_object",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="set('jingli', max_jingli); set('neili', max_neili) 恢复精力/内力",
            lpc_call='set("jingli", query("max_jingli")); set("neili", query("max_neili"))',
            target="this_object",
        ),
    ],
    notes=(
        "reincarnate 是玩家从阴间还阳后的状态恢复接口。"
        "与 revive（昏迷苏醒）不同：revive 不恢复属性（需 heal_up 渐进恢复），"
        "reincarnate 将所有属性恢复到 max（完整恢复）。"
        "reincarnate 不处理位置移动（还阳流程由 DEATH_ROOM 控制，后置到阶段 1）。"
    ),
)


# ---------------------------------------------------------------------------
# death_penalty()（adm/daemons/combatd.c:987-1025）
# ---------------------------------------------------------------------------

_death_penalty = FunctionSpec(
    signature=FunctionSignature(
        name="death_penalty",
        params=[
            LPCParam(name="victim", lpc_type="object", description="死亡的玩家对象"),
        ],
        return_type="void",
        lpc_file="adm/daemons/combatd.c",
        line_range=(987, 1025),
    ),
    preconditions=[
        Precondition(
            description="victim 必须是 user（!userp 则直接 return）",
            lpc_expr="userp(victim)",
            kind="require",
        ),
        Precondition(
            description="victim 不是巫师（wizardp 则直接 return）",
            lpc_expr="!wizardp(victim)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="clear_condition() 清除所有状态",
            state_change="victim->clear_condition()",
            kind="effect",
        ),
        Postcondition(
            description="death_times 递增（当 combat_exp >= 10000*death_times 时）",
            state_change='victim->add("death_times", 1) (条件性)',
            kind="effect",
        ),
        Postcondition(
            description="shen 扣减 1/20：add('shen', -shen/20)",
            state_change='victim->add("shen", -(int)victim->query("shen") / 20)',
            kind="effect",
        ),
        Postcondition(
            description="behavior_exp 扣减 1/20",
            state_change='victim->add("behavior_exp", -(int)victim->query("behavior_exp") / 20)',
            kind="effect",
        ),
        Postcondition(
            description="combat_exp 扣减：amount=combat_exp/100（上限 5000），>50 扣 amount，<=50 且 >20 扣 20",
            state_change="victim->add('combat_exp', -amount) where amount=min(combat_exp/100, 5000)",
            kind="effect",
        ),
        Postcondition(
            description="combat_exp 扣减 >50 时 potential 扣减 1/2",
            state_change='victim->add("potential", -(int)victim->query("potential") / 2)',
            kind="effect",
        ),
        Postcondition(
            description="balance 扣减：超出 10000 的部分扣减 1/2",
            state_change='victim->add("balance", -amount/2) where amount=balance-10000',
            kind="effect",
        ),
        Postcondition(
            description="death_count 递增 1",
            state_change='victim->add("death_count", 1)',
            kind="effect",
        ),
        Postcondition(
            description="删除 vendetta 和 rob_victim/initiator 临时标记",
            state_change='victim->delete("vendetta"); victim->delete_temp("rob_victim"); victim->delete_temp("initiator")',
            kind="effect",
        ),
        Postcondition(
            description="thief 标记减半",
            state_change='victim->set("thief", thief/2)',
            kind="effect",
        ),
        Postcondition(
            description="skill_death_penalty() 扣减所有技能等级",
            state_change="victim->skill_death_penalty()",
            kind="effect",
        ),
        Postcondition(
            description="save() 存档",
            state_change="victim->save()",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="death_penalty 无 random() 调用，所有扣减为确定性公式",
            lpc_expr="no random() in death_penalty()",
            scope="function",
        ),
        Invariant(
            description="combat_exp 扣减有上限保护：amount 上限 5000，下限 20（当 combat_exp>20 时）",
            lpc_expr="amount = min(combat_exp/100, 5000); if(amount>50) ... else if(combat_exp>20) amount=20",
            scope="function",
        ),
        Invariant(
            description="death_times 仅在 combat_exp >= 10000*death_times 时递增（防止低经验刷死亡次数）",
            lpc_expr='combat_exp >= 10000 * death_times => death_times++',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="clear_condition() 清除所有状态条件",
            lpc_call="victim->clear_condition()",
            target="victim",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="death_times 递增（条件性：combat_exp >= 10000*death_times）",
            lpc_call='if(combat_exp >= 10000*death_times) victim->add("death_times", 1)',
            target="victim",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="shen 扣减 1/20（正神值减少）",
            lpc_call='victim->add("shen", -(int)victim->query("shen") / 20)',
            target="victim.shen",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="behavior_exp 扣减 1/20",
            lpc_call='victim->add("behavior_exp", -(int)victim->query("behavior_exp") / 20)',
            target="victim.behavior_exp",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="combat_exp 扣减：amount=combat_exp/100（上限 5000），amount>50 扣 amount",
            lpc_call='amount=min(combat_exp/100,5000); if(amount>50) victim->add("combat_exp", -amount)',
            target="victim.combat_exp",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="combat_exp 扣减 >50 时 potential 扣减 1/2",
            lpc_call='if(amount>50) victim->add("potential", -(int)victim->query("potential") / 2)',
            target="victim.potential",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="combat_exp<=50 且 >20 时扣减 20 点 combat_exp",
            lpc_call='else if(combat_exp>20) victim->add("combat_exp", -20)',
            target="victim.combat_exp",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="balance 扣减：超出 10000 的部分扣减 1/2",
            lpc_call='amount=balance-10000; if(amount>0) victim->add("balance", -amount/2)',
            target="victim.balance",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.STATE_MUTATION,
            description="death_count 递增",
            lpc_call='victim->add("death_count", 1)',
            target="victim.death_count",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.STATE_MUTATION,
            description="删除 vendetta / rob_victim / initiator 标记",
            lpc_call='victim->delete("vendetta"); victim->delete_temp("rob_victim"); victim->delete_temp("initiator")',
            target="victim",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.STATE_MUTATION,
            description="thief 标记减半",
            lpc_call='if(victim->query("thief")) victim->set("thief", thief/2)',
            target="victim.thief",
        ),
        SideEffect(
            order=12,
            kind=SideEffectType.EXTERNAL,
            description="skill_death_penalty() 扣减所有技能等级（委托 F_SKILL，属层 H）",
            lpc_call="victim->skill_death_penalty()",
            target="victim.skills",
        ),
        SideEffect(
            order=13,
            kind=SideEffectType.PERSISTENCE,
            description="save() 存档",
            lpc_call="victim->save()",
            target="victim",
        ),
    ],
    notes=(
        "death_penalty 完全确定性，无 random() 调用。"
        "combat_exp 扣减公式：amount = min(combat_exp/100, 5000)，"
        "amount>50 扣 amount 且 potential 扣 1/2，amount<=50 且 combat_exp>20 扣 20。"
        "skill_death_penalty 的内部逻辑属层 H（F_SKILL），此处仅引用为副作用。"
    ),
)


# ---------------------------------------------------------------------------
# killer_reward()（adm/daemons/combatd.c:1027-1096）
# ---------------------------------------------------------------------------

_killer_reward = FunctionSpec(
    signature=FunctionSignature(
        name="killer_reward",
        params=[
            LPCParam(name="killer", lpc_type="object", description="击杀者对象"),
            LPCParam(name="victim", lpc_type="object", description="被杀者对象"),
        ],
        return_type="void",
        lpc_file="adm/daemons/combatd.c",
        line_range=(1027, 1096),
    ),
    preconditions=[
        Precondition(
            description="victim 的 environment 不在 no_death 房间（no_death 房间不执行奖励）",
            lpc_expr='!environment(victim)->query("no_death")',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="调用 killer->killed_enemy(victim) 触发击杀回调",
            state_change="killer->killed_enemy(victim)",
            kind="effect",
        ),
        Postcondition(
            description="victim 为玩家时 killer PKS+1，记录 pktime",
            state_change='killer->add("PKS", 1); killer->set("pktime", mud_age)',
            kind="effect",
        ),
        Postcondition(
            description="在 /d/city/ 下 PK 玩家施加 killer condition（通缉 100 tick）",
            state_change='killer->apply_condition("killer", 100)',
            kind="effect",
        ),
        Postcondition(
            description="victim 为 NPC 且人类时 killer MKS+1",
            state_change='killer->add("MKS", 1)',
            kind="effect",
        ),
        Postcondition(
            description="击杀非盟主玩家：killer shen 扣减 victim.shen/10（条件性）",
            state_change='killer->add("shen", -(int)victim->query("shen") / 10)',
            kind="effect",
        ),
        Postcondition(
            description="behavior_exp 扣减 victim.behavior_exp/10",
            state_change='killer->add("behavior_exp", -(int)victim->query("behavior_exp") / 10)',
            kind="effect",
        ),
        Postcondition(
            description="PvP 且已有 pking 标记：施加 pker condition +120 tick",
            state_change='killer->apply_condition("pker", killer->query_condition("pker") + 120)',
            kind="effect",
        ),
        Postcondition(
            description="victim 有 vendetta_mark 时 killer 仇杀计数+1",
            state_change='killer->add("vendetta/" + vmark, 1)',
            kind="effect",
        ),
        Postcondition(
            description="发谣言频道消息：victim 被 killer 杀死（按种族选择动词：咬/踩/啄/杀）",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="killer_reward 无 random() 调用，所有奖励为确定性公式",
            lpc_expr="no random() in killer_reward()",
            scope="function",
        ),
        Invariant(
            description="free_rider 机制：击杀盟主（mengzhu）不获得奖励/惩罚",
            lpc_expr='victim->query("id") == winner => killer->set_temp("free_rider", 1)',
            scope="function",
        ),
        Invariant(
            description="盟主被杀时 free_rider 标记清除 my_killer，不触发后续奖励逻辑",
            lpc_expr='if(killer->query_temp("free_rider")) victim->delete_temp("my_killer")',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="killer->killed_enemy(victim) 触发击杀回调（apply 函数）",
            lpc_call="killer->killed_enemy(victim)",
            target="killer",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="victim 为玩家时：killer PKS+1 + 记录 pktime",
            lpc_call='killer->add("PKS", 1); killer->set("pktime", killer->query("mud_age"))',
            target="killer",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="在 /d/city/ 下 PK 玩家：apply_condition('killer', 100) 通缉状态",
            lpc_call='if(strsrch(file_name(env), "/d/city/")>=0) killer->apply_condition("killer", 100)',
            target="killer",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="发谣言频道：victim 被 killer <mode> 死了（mode 按种族：咬/踩/啄/杀）",
            lpc_call='CHANNEL_D->do_channel(this_object(), "rumor", sprintf(...))',
            target="channel",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="victim 为 NPC 人类时：killer MKS+1",
            lpc_call='killer->add("MKS", 1)',
            target="killer",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.EXTERNAL,
            description="查找/加载泰山封禅台，判断 victim 是否为盟主",
            lpc_call='room = find_object("/d/taishan/fengchan"); winner = room->query("winner")',
            target="room",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="非 free_rider 且 killer 经验在 victim 的 1/4~1 倍之间：killer shen 扣减 victim.shen/10",
            lpc_call='if(!free_rider && killer_exp<victim_exp && killer_exp>victim_exp/4) killer->add("shen", -victim->query("shen")/10)',
            target="killer.shen",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="killer behavior_exp 扣减 victim.behavior_exp/10",
            lpc_call='killer->add("behavior_exp", -(int)victim->query("behavior_exp") / 10)',
            target="killer.behavior_exp",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.STATE_MUTATION,
            description="free_rider 清除：victim->delete_temp('my_killer') + killer->delete_temp('free_rider')",
            lpc_call='if(free_rider) { victim->delete_temp("my_killer"); killer->delete_temp("free_rider"); }',
            target="killer",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.STATE_MUTATION,
            description="PvP 且已有 pking 标记：apply_condition('pker', current+120) 红名状态",
            lpc_call='if(userp(killer)&&userp(victim)&&killer->query_temp("pking/"+victim->id)) killer->apply_condition("pker", killer->query_condition("pker")+120)',
            target="killer",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.STATE_MUTATION,
            description="victim 有 vendetta_mark 时 killer 仇杀计数+1",
            lpc_call='if(vmark=victim->query("vendetta_mark")) killer->add("vendetta/"+vmark, 1)',
            target="killer",
        ),
    ],
    notes=(
        "killer_reward 完全确定性，无 random() 调用。"
        "free_rider 机制防止从击杀盟主中获益。"
        "城市内 PK 施加 killer 通缉状态（100 tick），由 PvP 追杀系统处理（细节后置）。"
        "pker condition 是红名累积机制，已有 pker 状态再 PK 时叠加 120 tick。"
    ),
)


# ---------------------------------------------------------------------------
# make_corpse()（adm/daemons/chard.c:116-171）
# ---------------------------------------------------------------------------

_make_corpse = FunctionSpec(
    signature=FunctionSignature(
        name="make_corpse",
        params=[
            LPCParam(name="victim", lpc_type="object", description="死者对象"),
            LPCParam(name="killer", lpc_type="object", description="击杀者对象（可为 0）"),
        ],
        return_type="object",
        is_varargs=True,
        lpc_file="adm/daemons/chard.c",
        line_range=(116, 171),
    ),
    preconditions=[
        Precondition(
            description="victim 是有效对象",
            lpc_expr="objectp(victim)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="成功时返回 corpse 对象（已 move 到 environment(victim) 并含死者物品）",
            return_value="object（尸体对象）或 0（victim 是 ghost 时）",
            kind="ensure",
        ),
        Postcondition(
            description="ghost 死者不生成尸体：物品直接掉落到 environment(victim)，返回 0",
            state_change="inv->move(environment(victim)); return 0",
            kind="effect",
        ),
        Postcondition(
            description="尸体名称设为 '<死者名>的尸体'，long 追加死亡描述",
            state_change='corpse->set_name(victim->name(1)+"的尸体", ({"corpse"}))',
            kind="effect",
        ),
        Postcondition(
            description="尸体继承死者的 age/gender/combat_exp/weight/max_encumbrance",
            state_change="corpse->set('age'/'gender'/'combat_exp'/weight/max_encumbrance from victim)",
            kind="effect",
        ),
        Postcondition(
            description="非巫师死者的所有 inventory 物品转移到尸体（含装备重穿尝试）",
            state_change="all_inventory(victim)->move(corpse)",
            kind="effect",
        ),
        Postcondition(
            description="装备物品转移后尝试在尸体上 wear()，失败则 move 到环境",
            state_change="if(equipped=='worn') inv[i]->move(corpse); if(!inv[i]->wear()) inv[i]->move(environment(victim))",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="物品转移完整性：非巫师死者 transfer 后 all_inventory(victim) 为空",
            lpc_expr="all_inventory(victim) == ({}) after make_corpse() (non-wizard)",
            scope="function",
        ),
        Invariant(
            description="巫师死者不转移物品（防止非法物品残留）",
            lpc_expr="wizardp(victim) => items stay in victim",
            scope="function",
        ),
        Invariant(
            description="尸体 max_encumbrance 继承自死者，可承载死者全部物品",
            lpc_expr="corpse->query_max_encumbrance() == victim->query_max_encumbrance()",
            scope="function",
        ),
        Invariant(
            description="corpse 的 my_killer 记录死者 temp 中的 my_killer（由 die 设置）",
            lpc_expr='corpse->query("my_killer") == victim->query_temp("my_killer")',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="ghost 判定：victim->is_ghost() 时物品直接掉落到环境，返回 0",
            lpc_call="if(victim->is_ghost()) { inv->move(environment(victim)); return 0; }",
            target="victim_inventory",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="new(CORPSE_OB) 创建尸体对象（/clone/misc/corpse）",
            lpc_call="corpse = new(CORPSE_OB)",
            target="corpse",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="set_name 设置尸体名称为 '<死者名>的尸体'",
            lpc_call='corpse->set_name(victim->name(1) + "的尸体", ({"corpse"}))',
            target="corpse",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="set('long', ...) 设置尸体描述（死者 long + 死亡追加文本）",
            lpc_call='corpse->set("long", victim->long() + "然而，" + gender_pronoun(...) + "已经死了...")',
            target="corpse",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="复制死者属性到尸体：age/gender/victim_name/combat_exp",
            lpc_call='corpse->set("age", ...); corpse->set("gender", ...); corpse->set("victim_name", ...); corpse->set("combat_exp", ...)',
            target="corpse",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="设置尸体重量和最大负重（继承自死者）",
            lpc_call="corpse->set_weight(victim->query_weight()); corpse->set_max_encumbrance(victim->query_max_encumbrance())",
            target="corpse",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="set('my_killer', victim->query_temp('my_killer')) 记录击杀者",
            lpc_call='corpse->set("my_killer", victim->query_temp("my_killer"))',
            target="corpse",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.EXTERNAL,
            description="查找泰山封禅台盟主，判断 was_userp 标记（玩家尸体标记）",
            lpc_call='room = find_object("/d/taishan/fengchan"); if(userp(victim) && victim->id != winner) corpse->set("was_userp", 1)',
            target="corpse",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="corpse->move(environment(victim)) 将尸体移到死者所在房间",
            lpc_call="corpse->move(environment(victim))",
            target="corpse",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="非巫师：all_inventory(victim)->owner_is_killed(killer) 通知物品所有者已死亡",
            lpc_call='if(!wizardp(victim)) { inv = all_inventory(victim); inv->owner_is_killed(killer); }',
            target="victim_inventory",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="逐个转移物品：装备物品 move 到尸体后尝试 wear()，失败则 move 到环境；非装备物品直接 move 到尸体",
            lpc_call='if(equipped=="worn") { inv[i]->move(corpse); if(!inv[i]->wear()) inv[i]->move(environment(victim)); } else inv[i]->move(corpse)',
            target="victim_inventory",
        ),
    ],
    notes=(
        "make_corpse 的物品转移是核心不变量：非巫师死者转移后 inventory 为空。"
        "装备物品（equipped=='worn'）转移到尸体后尝试 wear()，失败则掉落到环境。"
        "ghost 死者不生成尸体，物品直接掉落到环境（防止 ghost 携带物品消失）。"
        "was_userp 标记区分玩家尸体和 NPC 尸体（盟主除外），影响后续拾取/搜索行为。"
        "owner_is_killed 是物品的 apply 回调（如邮箱/roommaker 会自毁）。"
    ),
)


# ---------------------------------------------------------------------------
# announce()（adm/daemons/combatd.c:966-980）
# ---------------------------------------------------------------------------

_announce = FunctionSpec(
    signature=FunctionSignature(
        name="announce",
        params=[
            LPCParam(name="ob", lpc_type="object", description="事件主体对象"),
            LPCParam(name="event", lpc_type="string", description="事件类型：'dead'/'unconcious'/'revive'"),
        ],
        return_type="void",
        lpc_file="adm/daemons/combatd.c",
        line_range=(966, 980),
    ),
    preconditions=[
        Precondition(
            description="event 必须是 'dead'、'unconcious' 或 'revive' 之一",
            lpc_expr='event in ("dead", "unconcious", "revive")',
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="向 ob 所在房间输出对应的 message_vision 消息",
            state_change="message_vision(ob->query(event+'_message'), ob)",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="announce 仅输出消息，不修改任何状态（纯消息输出）",
            scope="function",
        ),
        Invariant(
            description="消息模板由种族设置（race/*.c 中 set dead_message/unconcious_message/revive_message）",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="根据 event 类型输出 ob->query(event+'_message') 到房间",
            lpc_call='message_vision(ob->query(event + "_message"), ob)',
            target="room",
        ),
    ],
    notes=(
        "announce 是死亡/昏迷/苏醒事件的房间消息广播。"
        "消息模板由种族 daemon 设置（如 human: '倒在地上，挣扎了几下就死了'）。"
        "这是纯消息输出函数，不涉及任何状态变更。"
    ),
)


# ---------------------------------------------------------------------------
# heal_up()（feature/damage.c:270-331）-- 死亡轮回相关部分
# ---------------------------------------------------------------------------

_heal_up = FunctionSpec(
    signature=FunctionSignature(
        name="heal_up",
        params=[],
        return_type="int",
        lpc_file="feature/damage.c",
        line_range=(270, 331),
    ),
    preconditions=[
        Precondition(
            description="对象的 dbase 已初始化（query_entire_dbase() 返回有效 mapping）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 update_flag（>0 表示有属性更新，0 表示无变化）",
            return_value="int（更新标志位）",
            kind="observable",
        ),
        Postcondition(
            description="water/food 每 tick 递减 1",
            state_change="my['water'] -= 1; my['food'] -= 1",
            kind="effect",
        ),
        Postcondition(
            description="water 或 food < 1 时玩家不恢复属性（饥饿/脱水停止恢复）",
            state_change="if(water<1||food<1) return update_flag (for userp)",
            kind="effect",
        ),
        Postcondition(
            description="jing 恢复：战斗中 con/9+max_jingli/30，非战斗 con/3+max_jingli/10，上限 eff_jing",
            state_change="my['jing'] += fighting ? con/9+max_jingli/30 : con/3+max_jingli/10",
            kind="effect",
        ),
        Postcondition(
            description="qi 恢复：战斗中 con/9+max_neili/30，非战斗 con/3+max_neili/10，上限 eff_qi",
            state_change="my['qi'] += fighting ? con/9+max_neili/30 : con/3+max_neili/10",
            kind="effect",
        ),
        Postcondition(
            description="eff_jing/eff_qi 缓慢恢复（每 tick +1，上限 max）",
            state_change="if(jing>=eff_jing && eff_jing<max_jing) eff_jing++",
            kind="effect",
        ),
        Postcondition(
            description="jingli 恢复：战斗中 (str+dex)/12，非战斗 (str+dex)/4，上限 max_jingli*2",
            state_change="my['jingli'] += fighting ? (str+dex)/12 : (str+dex)/4",
            kind="effect",
        ),
        Postcondition(
            description="neili 恢复：战斗中 force_skill/6，非战斗 force_skill/2，上限 max_neili",
            state_change="my['neili'] += fighting ? force_skill/6 : force_skill/2",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="heal_up 恢复速率受战斗状态影响：战斗中恢复速率约为非战斗的 1/3",
            lpc_expr="heal_rate(fighting) ≈ heal_rate(!fighting) / 3",
            scope="function",
        ),
        Invariant(
            description="jing 不超过 eff_jing，eff_jing 不超过 max_jing（qi 同理）",
            lpc_expr="jing <= eff_jing <= max_jing; qi <= eff_qi <= max_qi",
            scope="class",
        ),
        Invariant(
            description="jingli 可超过 max_jingli（上限 max*2），neili 不超过 max_neili",
            lpc_expr="jingli <= max_jingli*2; neili <= max_neili",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="water/food 递减 1",
            lpc_call="my['water'] -= 1; my['food'] -= 1",
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="jing 恢复（战斗慢/非战斗快），上限 eff_jing",
            lpc_call="my['jing'] += fighting ? con/9+max_jingli/30 : con/3+max_jingli/10",
            target="this_object.jing",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="eff_jing 缓慢恢复（+1，上限 max_jing）",
            lpc_call="if(eff_jing<max_jing) eff_jing++",
            target="this_object.eff_jing",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="qi 恢复（战斗慢/非战斗快），上限 eff_qi",
            lpc_call="my['qi'] += fighting ? con/9+max_neili/30 : con/3+max_neili/10",
            target="this_object.qi",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="eff_qi 缓慢恢复（+1，上限 max_qi）",
            lpc_call="if(eff_qi<max_qi) eff_qi++",
            target="this_object.eff_qi",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="jingli 恢复（战斗慢/非战斗快），上限 max_jingli*2",
            lpc_call="my['jingli'] += fighting ? (str+dex)/12 : (str+dex)/4",
            target="this_object.jingli",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="neili 恢复（战斗慢/非战斗快），上限 max_neili",
            lpc_call="my['neili'] += fighting ? force_skill/6 : force_skill/2",
            target="this_object.neili",
        ),
    ],
    notes=(
        "heal_up 是恢复系统的核心，由 heart_beat 在非均匀 tick 中调用。"
        "与死亡轮回的关系：heal_up 渐进恢复 qi/jing，但 reincarnate 是完整恢复到 max。"
        "heal_up 受战斗状态影响（战斗中恢复速率约 1/3），water/food 耗尽时停止恢复。"
        "heal_up 无 random() 调用，完全确定性。"
    ),
)


# ---------------------------------------------------------------------------
# 层 F 规格集合
# ---------------------------------------------------------------------------

LAYER_SPEC = LayerSpec(
    layer_id="F",
    layer_name="死亡轮回",
    lpc_files=[
        "feature/damage.c",
        "adm/daemons/combatd.c",
        "adm/daemons/chard.c",
        "inherit/char/char.c",
    ],
    function_specs=[
        _heart_beat_death_trigger,
        _unconcious,
        _revive,
        _die,
        _reincarnate,
        _death_penalty,
        _killer_reward,
        _make_corpse,
        _announce,
        _heal_up,
    ],
    cross_layer_refs=[
        "receive_damage / receive_wound (层 E: combat) -- 伤害来源，触发 qi/jing 降低",
        "do_attack (层 E: combat) -- 战斗回合，通过 receive_damage 间接触发死亡",
        "remove_all_enemy / remove_all_killer (层 E: combat) -- die/unconcious 中清除战斗关系",
        "interrupt_me (层 B: F_ACTION) -- unconcious 中中断进行中的动作",
        "dismiss_team (层 B: F_TEAM) -- die/unconcious 中解散队伍",
        "disable_player / enable_player (层 C: command) -- 昏迷/苏醒的命令输入控制",
        "move (层 B: F_MOVE) -- corpse move 到房间、玩家 move 到 DEATH_ROOM",
        "save (层 B: F_SAVE) -- die / death_penalty 中存档",
        "destruct (层 A: driver) -- NPC 死亡后销毁",
        "new (层 A: driver) -- make_corpse 中 clone 尸体对象",
        "all_inventory / environment (层 A: driver) -- make_corpse 中物品转移",
        "set / query / set_temp / delete_temp (层 B: F_DBASE) -- 状态读写",
        "clear_condition (层 B: F_CONDITION) -- die / death_penalty 中清除状态",
        "skill_death_penalty (层 H: F_SKILL) -- death_penalty 中技能扣减",
        "setup_char (层 H: CHAR_D) -- 角色初始化（reincarnate 依赖 max 值由 setup_char 设置）",
        "COMBAT_D->winner_reward (层 E: combat) -- unconcious 中胜者奖励",
        "COMBAT_D->fight (层 E: combat) -- heart_beat 中战斗回合",
        "GO_CMD->do_flee (层 D: world) -- heart_beat 中 wimpy 自动逃跑",
        "message / message_vision (层 B: F_MESSAGE) -- 消息输出",
        "CHANNEL_D->do_channel (层 G: communication) -- 死亡谣言频道",
        "MARRY_D->break_marriage (层 H) -- 死亡解除婚姻",
        "CHAR_D->break_relation (层 H) -- 死亡解除师徒关系",
        "DEATH_ROOM->start_death (阶段 1 后置) -- 阴间流程入口",
        "log_file (层 A: driver) -- 死亡日志",
        "call_out / remove_call_out (层 A: driver) -- revive 定时器",
    ],
    notes=(
        "层 F 覆盖死亡轮回全流程：heart_beat 触发 -> unconcious/die -> death_penalty/killer_reward -> "
        "make_corpse -> reincarnate/revive。"
        "die 与 unconcious 的触发条件区别是本层最关键契约："
        "eff_qi/eff_jing<0 -> 直接 die；qi/jing/jingli<0 -> 首次 unconcious，昏迷中再触发 -> die。"
        "death_penalty 和 killer_reward 均无 random() 调用，完全确定性。"
        "make_corpse 的物品转移完整性是核心不变量：非巫师死者转移后 inventory 为空。"
        "阴间世界流程（黑白无常/还阳路径）后置到阶段 1。"
        "尸体四阶段腐烂后置。PvP 通缉机制细节后置。"
    ),
)
