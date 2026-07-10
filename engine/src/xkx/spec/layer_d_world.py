"""层 D：世界构建 -- LPC 规格提取（ADR-0010）。

覆盖范围：
- ``inherit/room/room.c`` -- ROOM 基类：valid_leave / reset / make_inventory / 门机制
- ``cmds/std/go.c`` -- go 命令：main / do_flee
- ``feature/team.c`` -- follow_me 组队跟随

核心契约要点：
1. **valid_leave 基类契约**：返回 1=允许离开，0=拒绝（notify_fail 返回 0）。
   516 个 override 遵循可分类的固定模式（门检查 / 敌对 NPC / 门派限制 / 任务标记 /
   状态限制 / 环境触发 / 复合）。本层只提取基类契约 + 模式分类，不逐个提取 override。
2. **go main() 副作用交织顺序**：方向解析 -> 逃跑判定 -> valid_leave -> 旧房间消息 ->
   move -> 新房间消息 -> follow_me -> team 跟随。状态变更与消息输出不可分离。
3. **reset() 触发**：由 NATURE_D 定时驱动（或 driver heart_beat 调用），
   make_inventory 维护 NPC/物品数量与归位。
4. **门机制**：create_door 定义门（含跨房间同步），open_door/close_door 改状态，
   valid_leave 基类自动检查 DOOR_CLOSED 阻止离开。
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
# 层 D 特定模型
# ---------------------------------------------------------------------------


class DoorStatus(StrEnum):
    """门状态位掩码（LPC ``room.h`` 定义）。"""

    CLOSED = "1"  # DOOR_CLOSED = 1
    LOCKED = "2"  # DOOR_LOCKED = 2
    SMASHED = "4"  # DOOR_SMASHED = 4


class ValidLeaveOverridePattern(StrEnum):
    """valid_leave override 模式分类（基于 516 个 d/ 房间实证扫描）。

    每种模式描述一个 override 类别，Python 实现时以策略对象或规则引擎表达，
    而非逐个翻译 516 个 LPC 文件。
    """

    DOOR_CHECK = "door_check"
    """基类内置：门关闭时阻止离开（room.c:269-271）。"""

    HOSTILE_NPC = "hostile_npc"
    """敌对 NPC 拦路：present() 检查 NPC 存在且 living，拒绝离开并输出拦路消息。"""

    FACTION_GATE = "faction_gate"
    """门派守卫/身份检查：query("family/family_name") 匹配则放行，否则拒绝。"""

    QUEST_FLAG = "quest_flag"
    """任务状态标记：query_temp() 检查任务进行中状态，阻止离开（如挖矿/打铁/打麻将）。"""

    STATE_LIMIT = "state_limit"
    """玩家状态限制：query_temp() 检查 cannot_move / pigging_seat 等 immobilize 状态。"""

    ENVIRONMENT_TRIGGER = "environment_trigger"
    """环境触发：离开时触发副作用（如删除 rent_paid、触发 call_out 延迟事件）。"""

    COMPOSITE = "composite"
    """复合模式：组合两种以上检查（如门派 + NPC、任务 + NPC）。"""

    WIZARD_BYPASS = "wizard_bypass"
    """巫师豁免：wizardp(me) 跳过所有限制（调试通道，非游戏机制）。"""


# ---------------------------------------------------------------------------
# room.c 函数规格
# ---------------------------------------------------------------------------

_valid_leave = FunctionSpec(
    signature=FunctionSignature(
        name="valid_leave",
        params=[
            LPCParam(name="me", lpc_type="object", description="试图离开的玩家/NPC 对象"),
            LPCParam(name="dir", lpc_type="string", description="离开方向（如 north/up/out）"),
        ],
        return_type="int",
        lpc_file="inherit/room/room.c",
        line_range=(267, 275),
    ),
    preconditions=[
        Precondition(
            description="me 是有效对象且在当前房间内（environment(me) == this_object()）",
            lpc_expr="objectp(me) && environment(me) == this_object()",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 1 表示允许离开；返回 0（notify_fail）表示拒绝",
            return_value="1=允许, 0=拒绝",
            kind="ensure",
        ),
        Postcondition(
            description="拒绝时已通过 notify_fail 设置错误消息",
            state_change="notify_fail 消息已设置",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="门关闭时必须拒绝离开（基类契约，override 可叠加但不绕过）",
            lpc_expr="doors[dir] & DOOR_CLOSED => return 0",
            scope="class",
        ),
        Invariant(
            description="无门或门开启时基类返回 1，由 override 决定是否叠加限制",
            lpc_expr="!mapp(doors) || undefinedp(doors[dir]) || !(doors[dir][status] & DOOR_CLOSED) => return 1",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="门关闭时通过 notify_fail 输出 '你必须先把<门名>打开！'",
            lpc_call='notify_fail("你必须先把" + doors[dir]["name"] + "打开！\\n")',
            target="me",
        ),
    ],
    notes=(
        "基类契约是 dissent 4（规则冲突语义漂移）的核心。516 个 override 中 "
        "多数调用 ::valid_leave(me, dir) 委托基类门检查，再叠加自身逻辑。"
        "override 模式分类见 ValidLeaveOverridePattern 枚举。"
        "Python 实现应以策略链表达：基类门检查 -> override 规则链 -> 最终判定。"
    ),
)


_make_inventory = FunctionSpec(
    signature=FunctionSignature(
        name="make_inventory",
        params=[
            LPCParam(name="file", lpc_type="string", description="要克隆的对象文件路径"),
        ],
        return_type="object",
        lpc_file="inherit/room/room.c",
        line_range=(52, 74),
    ),
    preconditions=[
        Precondition(
            description="file 是有效的 LPC 对象文件路径",
            lpc_expr='stringp(file)',
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="成功时返回新克隆的对象，已 move 到 this_object() 并设置 startroom",
            return_value="object（成功）/ 0（失败）",
            state_change="新对象已 move 到当前房间，startroom 设为当前房间 base_name",
            kind="ensure",
        ),
        Postcondition(
            description="若为 /kungfu/class/ 下的 NPC 且已有多份克隆，先 clean_up 再重新克隆",
            state_change="重复 NPC 被 destruct 后重新 clone",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="克隆的 NPC/物品的 startroom 始终指向创建它的房间",
            lpc_expr='ob->query("startroom") == base_name(this_object())',
            scope="function",
        ),
        Invariant(
            description="living NPC 克隆后立即在房间内，environment(ob) == this_object()",
            lpc_expr="environment(ob) == this_object()",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="new(file) 克隆对象",
            lpc_call="new(file)",
            target="ob",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="若 /kungfu/class/ NPC 重复，npc_clean_up 清理所有克隆后重新 new",
            lpc_call="npc_clean_up(file); ob = new(file)",
            target="ob_list",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="ob->move(this_object()) 将对象移入当前房间",
            lpc_call="ob->move(this_object())",
            target="ob",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 startroom 为当前房间 base_name",
            lpc_call='ob->set("startroom", base_name(this_object()))',
            target="ob.startroom",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="若为 living NPC，向房间输出 '<NPC名>急急忙忙走了过来。'",
            lpc_call='tell_room(environment(ob), ob->query("name") + "急急忙忙走了过来。\\n")',
            target="room",
        ),
    ],
    notes="make_inventory 由 reset() 调用，维护房间内 NPC/物品的预期数量。",
)


_reset = FunctionSpec(
    signature=FunctionSignature(
        name="reset",
        params=[],
        return_type="void",
        lpc_file="inherit/room/room.c",
        line_range=(76, 155),
    ),
    preconditions=[
        Precondition(
            description="房间已初始化（setup() 已调用）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="query('objects') 中指定的每个对象文件在房间内存在预期数量",
            state_change="缺失的 NPC/物品被重新 clone；多余的杂项被 destruct",
            kind="ensure",
        ),
        Postcondition(
            description="temp('objects') 映射更新为当前存活对象列表",
            state_change='set_temp("objects", ob)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="is_character() 且 query('no_refresh') 的 NPC 不被 destruct",
            lpc_expr="inv[i]->is_character() || inv[i]->query('no_refresh') => skip destruct",
            scope="function",
        ),
        Invariant(
            description="query('objects') 列表中的对象不会被 destruct（仅补充缺失）",
            lpc_expr="member_array(base_name(inv[i]), list) != -1 => skip destruct",
            scope="function",
        ),
        Invariant(
            description="离开房间的 NPC 尝试 return_home，失败则递增 no_clean_up 计数",
            lpc_expr="!return_home(this_object()) => add('no_clean_up', 1)",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description='set("no_clean_up", 0) 重置清理计数',
            lpc_call='set("no_clean_up", 0)',
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="清理不在 objects 列表中的非角色非 no_refresh 杂项对象（destruct）",
            lpc_call="destruct(inv[i])",
            target="inv",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="对 query('objects') 中缺失的对象调用 make_inventory 补充",
            lpc_call="make_inventory(list[i])",
            target="ob",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="对离开房间的 NPC 调用 return_home 尝试召回",
            lpc_call="ob[list[i]]->return_home(this_object())",
            target="ob",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description='set_temp("objects", ob) 更新对象追踪映射',
            lpc_call='set_temp("objects", ob)',
            target="this_object",
        ),
    ],
    notes=(
        "reset 由 NATURE_D 定时驱动（LPC heart_beat 机制），不是玩家离开后触发。"
        "make_inventory 对数量 >1 的对象用数组追踪每个实例。"
    ),
)


_create_door = FunctionSpec(
    signature=FunctionSignature(
        name="create_door",
        params=[
            LPCParam(name="dir", lpc_type="string", description="门所在方向"),
            LPCParam(name="data", lpc_type="mixed", description="门数据（string 紧凑模式或 mapping 完整模式）"),
            LPCParam(name="other_side_dir", lpc_type="string", description="对面房间对应方向"),
            LPCParam(name="status", lpc_type="int", description="初始状态位掩码（DOOR_CLOSED 等）"),
        ],
        return_type="void",
        lpc_file="inherit/room/room.c",
        line_range=(227, 257),
        is_varargs=True,
    ),
    preconditions=[
        Precondition(
            description="dir 方向必须存在于 exits 映射中",
            lpc_expr='mapp(exits) && !undefinedp(exits[dir])',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="doors[dir] 被设置为门数据映射（含 name/id/other_side_dir/status）",
            state_change="doors[dir] = d",
            kind="ensure",
        ),
        Postcondition(
            description="item_desc[dir] 被设置为 look_door 闭包",
            state_change='set("item_desc/" + dir, (: look_door, dir :))',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="门必须关联一个 exit（无 exit 的方向不能创建门）",
            lpc_expr='mapp(exits) && !undefinedp(exits[dir])',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="紧凑模式下构造门数据映射（name/id/other_side_dir/status）",
            lpc_call='d = (["name": data, "id": ({dir, data, "door"}), ...])',
            target="d",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 item_desc 使 look 命令能查看门",
            lpc_call='set("item_desc/" + dir, (: look_door, dir :))',
            target="this_object",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="若对面房间已加载，调用 check_door 同步门状态",
            lpc_call="ob->check_door(other_side_dir, d)",
            target="other_room",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="doors 映射中注册门",
            lpc_call="doors[dir] = d",
            target="doors",
        ),
    ],
    notes="create_door 在房间 create() 中调用，定义门后 valid_leave 基类自动检查。",
)


_open_door = FunctionSpec(
    signature=FunctionSignature(
        name="open_door",
        params=[
            LPCParam(name="dir", lpc_type="string", description="门所在方向"),
            LPCParam(name="from_other_side", lpc_type="int", description="是否由对面房间调用（递归同步标记）"),
        ],
        return_type="int",
        lpc_file="inherit/room/room.c",
        line_range=(168, 191),
        is_varargs=True,
    ),
    preconditions=[
        Precondition(
            description="dir 方向存在门（doors[dir] 已定义）",
            lpc_expr='mapp(doors) && !undefinedp(doors[dir])',
            kind="guard",
        ),
        Precondition(
            description="门当前处于关闭状态",
            lpc_expr="doors[dir]['status'] & DOOR_CLOSED",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 1 表示开门成功；返回 0 表示失败（notify_fail）",
            return_value="1=成功, 0=失败",
            kind="ensure",
        ),
        Postcondition(
            description="门状态清除 DOOR_CLOSED 位",
            state_change="doors[dir]['status'] &= (!DOOR_CLOSED)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="门必须关联一个 exit",
            lpc_expr='mapp(exits) && !undefinedp(exits[dir])',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="from_other_side 时向本房间输出 '有人从另一边将<门名>打开了。'",
            lpc_call='message("vision", "有人从另一边将" + doors[dir]["name"] + "打开了。\\n", this_object())',
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="非 from_other_side 时，递归调用对面房间的 open_door(other_side_dir, 1) 同步",
            lpc_call="ob->open_door(doors[dir]['other_side_dir'], 1)",
            target="other_room",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="清除门的 DOOR_CLOSED 位",
            lpc_call='doors[dir]["status"] &= (!DOOR_CLOSED)',
            target="doors[dir].status",
        ),
    ],
    notes="开门是跨房间同步操作：先同步对面，再改本地状态。",
)


_close_door = FunctionSpec(
    signature=FunctionSignature(
        name="close_door",
        params=[
            LPCParam(name="dir", lpc_type="string", description="门所在方向"),
            LPCParam(name="from_other_side", lpc_type="int", description="是否由对面房间调用（递归同步标记）"),
        ],
        return_type="int",
        lpc_file="inherit/room/room.c",
        line_range=(193, 216),
        is_varargs=True,
    ),
    preconditions=[
        Precondition(
            description="dir 方向存在门",
            lpc_expr='mapp(doors) && !undefinedp(doors[dir])',
            kind="guard",
        ),
        Precondition(
            description="门当前未关闭",
            lpc_expr="!(doors[dir]['status'] & DOOR_CLOSED)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 1 表示关门成功；返回 0 表示失败",
            return_value="1=成功, 0=失败",
            kind="ensure",
        ),
        Postcondition(
            description="门状态设置 DOOR_CLOSED 位",
            state_change="doors[dir]['status'] |= DOOR_CLOSED",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="门必须关联一个 exit",
            lpc_expr='mapp(exits) && !undefinedp(exits[dir])',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="from_other_side 时向本房间输出 '有人从另一边将<门名>关上了。'",
            lpc_call='message("vision", "有人从另一边将" + doors[dir]["name"] + "关上了。\\n", this_object())',
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="非 from_other_side 时，递归调用对面房间 close_door(other_side_dir, 1) 同步",
            lpc_call="ob->close_door(doors[dir]['other_side_dir'], 1)",
            target="other_room",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="设置门的 DOOR_CLOSED 位",
            lpc_call='doors[dir]["status"] |= DOOR_CLOSED',
            target="doors[dir].status",
        ),
    ],
    notes="关门与开门对称：先同步对面，再改本地状态。",
)


# ---------------------------------------------------------------------------
# go.c 函数规格
# ---------------------------------------------------------------------------

_go_main = FunctionSpec(
    signature=FunctionSignature(
        name="main",
        params=[
            LPCParam(name="me", lpc_type="object", description="执行 go 命令的玩家/NPC"),
            LPCParam(name="arg", lpc_type="string", description="方向参数（如 north/up/out）"),
        ],
        return_type="int",
        lpc_file="cmds/std/go.c",
        line_range=(40, 264),
    ),
    preconditions=[
        Precondition(
            description="arg 非空（方向参数必须提供）",
            lpc_expr="arg",
            kind="input_constraint",
        ),
        Precondition(
            description="me 未超负荷",
            lpc_expr="!me->over_encumbranced()",
            kind="require",
        ),
        Precondition(
            description="me 不在 busy 状态",
            lpc_expr="!me->is_busy()",
            kind="require",
        ),
        Precondition(
            description="me 精力 >= max_jingli/10（非精疲力尽）",
            lpc_expr='me->query("jingli") >= me->query("max_jingli")/10',
            kind="require",
        ),
        Precondition(
            description="me 有当前环境（environment(me) 非 null）",
            lpc_expr="environment(me)",
            kind="require",
        ),
        Precondition(
            description="arg 是当前房间 exits 中的有效方向",
            lpc_expr='mapp(exit = env->query("exits")) && !undefinedp(exit[arg])',
            kind="require",
        ),
        Precondition(
            description="env->valid_leave(me, arg) 返回 1（基类 + override 均通过）",
            lpc_expr="env->valid_leave(me, arg)",
            kind="guard",
        ),
        Precondition(
            description="目标房间可加载（load_object(dest) 成功）",
            lpc_expr="obj = load_object(dest)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="成功时 me 已 move 到目标房间，返回 1",
            return_value="1=成功移动, 0=移动失败",
            state_change="me 在新房间 environment(me) == obj",
            kind="ensure",
        ),
        Postcondition(
            description="成功后 me 的所有敌人被清除（remove_all_enemy）",
            state_change="me->remove_all_enemy()",
            kind="effect",
        ),
        Postcondition(
            description="成功后旧房间内所有对象的 follow_me(me, arg) 被调用",
            state_change="team 成员跟随到新房间（或延迟 1 tick 跟随）",
            kind="effect",
        ),
        Postcondition(
            description="成功后 me->set_temp('pending', 0) 清除待定状态",
            state_change="me.pending = 0",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="move 原子性：从旧房间移除后必在新房间（me->move(obj) 成功或失败，无中间态）",
            lpc_expr="me->move(obj) ? environment(me)==obj : environment(me)==env",
            scope="system",
        ),
        Invariant(
            description="副作用交织顺序不可重排：valid_leave -> 旧房间消息 -> move -> 新房间消息 -> follow",
            lpc_expr="order(valid_leave) < order(mout_msg) < order(move) < order(min_msg) < order(follow_me)",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="战斗中逃跑判定：5 + random(dex) vs random(enemy_dex)，失败则 start_busy(1)",
            lpc_call="me->start_busy(1) (逃跑失败时)",
            target="me.busy",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="方向解析：arg -> default_dirs[arg] 中文名（如 north -> 北）",
            lpc_call="dir = default_dirs[arg]",
            target="dir",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="调用 env->valid_leave(me, arg) 执行离开校验（含门检查 + override 规则）",
            lpc_call="env->valid_leave(me, arg)",
            target="env",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="骑乘/坐骑/镖车/夜间商店等额外检查与状态变更",
            lpc_call="rided 检查 / day_shop 检查 / exit_blockers 检查",
            target="me",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="构造离开消息 mout（战斗=落荒而逃 / 室外=急步离开 / 室内=走了出去 / 骑乘=飞驰而去）",
            lpc_call='mout = "往" + dir + "落荒而逃了。\\n" (etc.)',
            target="env",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="向旧房间输出离开消息（不含 me 自身）",
            lpc_call='message("vision", me->name() + mout, env, ({me}))',
            target="env",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="扣除精力：人类步行 me->add('jingli', -env->cost*2)；骑乘 rided->add('jingli', -env->cost*2)",
            lpc_call='me->add("jingli", - env->query("cost")*2)',
            target="me.jingli",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="精力耗尽时 me->unconcious() 昏迷",
            lpc_call='me->unconcious() (when jingli <= 0)',
            target="me",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="me->move(obj) 将玩家移动到目标房间（原子操作）",
            lpc_call="me->move(obj)",
            target="me",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.STATE_MUTATION,
            description="me->remove_all_enemy() 清除所有敌人（脱离战斗）",
            lpc_call="me->remove_all_enemy()",
            target="me",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="向新房间输出到达消息 min（跌跌撞撞跑来 / 快步走来 / 走了过来 等）",
            lpc_call='message("vision", me->name() + min, environment(me), ({me}))',
            target="new_room",
        ),
        SideEffect(
            order=12,
            kind=SideEffectType.STATE_MUTATION,
            description="me->set_temp('pending', 0) 清除待定状态",
            lpc_call='me->set_temp("pending", 0)',
            target="me.pending",
        ),
        SideEffect(
            order=13,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="旧房间所有对象的 follow_me(me, arg) 被调用，触发组队/宠物跟随",
            lpc_call="all_inventory(env)->follow_me(me, arg)",
            target="env_inventory",
        ),
        SideEffect(
            order=14,
            kind=SideEffectType.STATE_MUTATION,
            description="清理骑乘/骑手关系（若不在同一房间则删除）和 exit_blocked 状态",
            lpc_call='me->delete("rided") / me->delete_temp("exit_blocked")',
            target="me",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random((int)me->query('dex'))",
            probability_model="逃跑概率 = P(5 + random(dex_me) > random(dex_enemy))",
            semantic="战斗中逃跑判定：5 + random(dex) vs random(enemy_dex)，失败则 busy",
            seed_inputs=["me.dex", "enemy.dex"],
        ),
        RandomSpec(
            lpc_call="random(5)",
            probability_model="1/5 概率骑乘额外消耗精力 2 点",
            semantic="骑乘移动时 20% 概率额外扣精力",
            seed_inputs=["me.rided"],
        ),
        RandomSpec(
            lpc_call="random(ob->query_dex()+5+random(5))",
            probability_model="exit_blocker 闪避判定",
            semantic="被挡路时轻功闪避判定：me.dex vs ob.dex+5+random(5)",
            seed_inputs=["me.dex", "ob.dex"],
        ),
    ],
    notes=(
        "go main() 的副作用交织顺序是本层最关键契约（CLAUDE.md 架构不变量："
        "do_attack 七步管线的文本与副作用交织不可分离，同理 go 的移动管线也遵循交织顺序）。"
        "valid_leave 可通过设置 me->set_temp('new_valid_dest', dest) 改写目的地（override 副作用）。"
        "day_shop 夜间关门检查依赖 NATURE_D->outdoor_room_event()（层 H 交叉引用）。"
    ),
)


_do_flee = FunctionSpec(
    signature=FunctionSignature(
        name="do_flee",
        params=[
            LPCParam(name="me", lpc_type="object", description="需要逃跑的对象"),
        ],
        return_type="void",
        lpc_file="cmds/std/go.c",
        line_range=(266, 277),
    ),
    preconditions=[
        Precondition(
            description="me 有当前环境（environment(me) 非 null）",
            lpc_expr="environment(me)",
            kind="require",
        ),
        Precondition(
            description="me 是 living 状态",
            lpc_expr="living(me)",
            kind="require",
        ),
        Precondition(
            description="当前房间有至少一个 exit",
            lpc_expr='mapp(exits) && sizeof(exits)',
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="随机选择一个方向调用 go main() 尝试逃跑",
            state_change="调用 main(me, directions[random(sizeof(directions))])",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="do_flee 本身不直接移动，委托 go main() 执行移动",
            lpc_expr="movement delegated to GO_CMD->main()",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="向 me 输出 '看来该找机会逃跑了...'",
            lpc_call='tell_object(me, "看来该找机会逃跑了...\\n")',
            target="me",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="随机选择方向并调用 main(me, dir) 执行 go 命令",
            lpc_call="main(me, directions[random(sizeof(directions))])",
            target="me",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(sizeof(directions))",
            probability_model="1/sizeof(exits) 均匀分布选择逃跑方向",
            semantic="随机选择一个出口方向逃跑",
            seed_inputs=["exits"],
        ),
    ],
    notes="do_flee 是 NPC AI 或战斗系统调用的逃跑入口，不是玩家直接命令。",
)


# ---------------------------------------------------------------------------
# team.c 函数规格
# ---------------------------------------------------------------------------

_follow_me = FunctionSpec(
    signature=FunctionSignature(
        name="follow_me",
        params=[
            LPCParam(name="ob", lpc_type="object", description="被跟随的领队对象"),
            LPCParam(name="dir", lpc_type="string", description="领队移动的方向"),
        ],
        return_type="int",
        lpc_file="feature/team.c",
        line_range=(37, 49),
    ),
    preconditions=[
        Precondition(
            description="this_object() 是 living 状态",
            lpc_expr="living(this_object())",
            kind="require",
        ),
        Precondition(
            description="ob 不是 this_object() 自身（不能跟随自己）",
            lpc_expr="ob != this_object()",
            kind="require",
        ),
        Precondition(
            description="ob 是 leader 或 this_object() 是 pursuer 且正在追杀 ob",
            lpc_expr='ob==leader || (query("pursuer") && this_object()->is_killing(ob->query("id")))',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="成功跟随返回 1，不跟随返回 0",
            return_value="1=跟随, 0=不跟随",
            kind="ensure",
        ),
        Postcondition(
            description="跟随方式：立即 follow_path 或延迟 1 tick call_out follow_path",
            state_change="调用 follow_path(dir) 或 call_out('follow_path', 1, dir)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="follow_path 委托 GO_CMD->main 执行移动，不直接 move",
            lpc_expr="follow_path => GO_CMD->main(this_object(), dir)",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="移动技能判定：random(ob->move_skill) vs this_object()->move_skill",
            lpc_call='random(ob->query_skill("move")) > this_object()->query_skill("move")',
            target="this_object",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="若领队移动技能更高，remove_call_out + call_out('follow_path', 1, dir) 延迟跟随",
            lpc_call='call_out("follow_path", 1, dir)',
            target="this_object",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="若自身移动技能 >= 领队，立即 follow_path(dir) 跟随",
            lpc_call="follow_path(dir)",
            target="this_object",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="follow_path 内部先 remove_all_enemy 再调用 GO_CMD->main",
            lpc_call="this_object()->remove_all_enemy(); GO_CMD->main(this_object(), dir)",
            target="this_object",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call='random(ob->query_skill("move"))',
            probability_model="P(跟随延迟) = P(random(leader_move) > follower_move)",
            semantic="移动技能判定：领队移动技能越高，跟随者越可能延迟 1 tick 才跟上",
            seed_inputs=["leader.move_skill", "follower.move_skill"],
        ),
    ],
    notes=(
        "follow_me 由 go main() 中的 all_inventory(env)->follow_me(me, arg) 触发。"
        "非 leader 的 team 成员和 pursuer 都通过此机制跟随。"
        "延迟跟随（call_out）是异步的，跟随者可能在 1 tick 后才到达。"
    ),
)


# ---------------------------------------------------------------------------
# 层 D 规格集合
# ---------------------------------------------------------------------------

LAYER_SPEC = LayerSpec(
    layer_id="D",
    layer_name="世界构建",
    lpc_files=[
        "inherit/room/room.c",
        "cmds/std/go.c",
        "feature/team.c",
    ],
    function_specs=[
        _valid_leave,
        _make_inventory,
        _reset,
        _create_door,
        _open_door,
        _close_door,
        _go_main,
        _do_flee,
        _follow_me,
    ],
    cross_layer_refs=[
        "move (层 B: F_MOVE)",  # go main 中 me->move(obj)
        "load_object (层 A: master/driver)",  # go main 中加载目标房间
        "notify_fail (层 C: command_hook)",  # valid_leave / go 中错误消息
        "message / tell_room / tell_object (层 B: F_MESSAGE)",  # 所有消息输出
        "remove_all_enemy (层 E: combat)",  # go main 移动后清除战斗
        "unconcious (层 F: 死亡轮回)",  # go main 精力耗尽昏迷
        "return_home (层 G: NPC AI)",  # reset 中 NPC 归位
        "NATURE_D->outdoor_room_event (层 H: 核心守护进程)",  # day_shop 夜间检查
        "SECURITY_D->valid_cmd (层 H)",  # command_hook 前置（go 命令入口）
        "COMBAT_D->eff_status_msg (层 E: combat)",  # exit_blocker 伤害状态消息
        "RANK_D->query_respect / query_rude (层 H)",  # valid_leave override 中的称谓
        "GO_CMD->main (层 D: go.c)",  # follow_path 调用 GO_CMD
    ],
    notes=(
        "层 D 覆盖 ROOM 基类契约 + go 命令 + 组队跟随。"
        "valid_leave 的 516 个 override 仅提取基类契约 + 8 种模式分类（ValidLeaveOverridePattern），"
        "不逐个提取（ADR-0010 §6 收敛原则）。"
        "门机制只提取 create_door/open_door/close_door 契约，门状态机完整运行时后置。"
        "ship/harbor/p9room 等特殊房间变体后置。"
    ),
)
