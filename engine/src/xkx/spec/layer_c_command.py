"""层 C：命令系统规格（ADR-0010 九层之第三层）。

本层覆盖 LPC 命令分发管线，提取自以下 LPC 源文件：

- ``feature/command.c`` -- ``command_hook`` 四分支分发主循环 + ``enable/disable_player``
- ``feature/alias.c`` -- ``process_input`` 别名/历史/刷屏检测预处理
- ``adm/daemons/commandd.c`` -- ``find_command`` / ``rehash`` 命令路径查找
- ``adm/daemons/aliasd.c`` -- ``process_global_alias`` 全局方向别名
- ``include/command.h`` -- 命令路径常量 + 命令对象定义

关键不变量
==========

1. **命令分发优先级**：``process_input``（别名/历史/刷屏）先于 ``command_hook``
   四分支执行。``command_hook`` 内部四分支优先级为：
   (a) 无参方向快捷 -- ``arg==""`` 且当前房间有对应 exit 时，直接调 ``go``
   (b) ``find_command`` -- 在玩家命令路径中查找并执行
   (c) ``EMOTE_D->do_emote`` -- emote 处理
   (d) ``CHANNEL_D->do_channel`` -- 频道处理
   四分支短路求值，首个命中即返回，全部未命中返回 0。

2. **命令路径搜索顺序**：``find_command`` 从 path 尾部向头部逆序搜索
   （``while(i--)``），先搜到的优先。路径由 ``enable_player`` 按身份设定。

3. **每条命令过 SECURITY_D valid_cmd**：``find_command`` 找到命令文件后，
   调 ``SECURITY_D->valid_cmd(cmd, this_player(), "cmd_file")`` 校验，
   不通过则返回 0（命令视为不存在）。

4. **方向别名全局映射**：``aliasd.c`` 中 ``global_alias`` 定义了 n/s/e/w 等
   20+ 个方向简写到 ``go <direction>`` 的映射，在 ``process_global_alias`` 中处理。

5. **刷屏检测**：``process_input`` 维护 tick 内命令计数，
   超过 ``CMDS_PER_TICK``（20）开始扣气/精，超过 ``3*CMDS_PER_TICK``（60）
   触发天雷惩罚（50% 概率昏迷 + 强制 quit）。

边界（本层不做，后置）
======================

- 玩家自定义别名（``alias.c`` 的 ``set_alias`` / ``alias`` mapping 管理）
- emote 频道分支细节（emote/频道内部实现逻辑）
- 语言转换（BIG5->GB）
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

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

# ── 命令路径常量（提取自 command.h） ──────────────────────────────────

COMMAND_PATHS: dict[str, list[str]] = {
    "ADM_PATH": [
        "/cmds/adm/", "/cmds/arch/", "/cmds/wiz/",
        "/cmds/imm/", "/cmds/usr/", "/cmds/std/", "/cmds/skill/",
    ],
    "ARC_PATH": [
        "/cmds/arch/", "/cmds/wiz/", "/cmds/imm/",
        "/cmds/usr/", "/cmds/std/", "/cmds/skill/",
    ],
    "WIZ_PATH": [
        "/cmds/imm/", "/cmds/usr/", "/cmds/std/", "/cmds/skill/", "/cmds/wiz/",
    ],
    "APR_PATH": [
        "/cmds/imm/", "/cmds/usr/", "/cmds/std/", "/cmds/skill/", "/cmds/wiz/",
    ],
    "IMM_PATH": ["/cmds/imm/", "/cmds/usr/", "/cmds/std/", "/cmds/skill/"],
    "PLR_PATH": ["/cmds/std/", "/cmds/usr/", "/cmds/skill/"],
    "UNR_PATH": ["/cmds/usr/", "/cmds/std/"],
    "NPC_PATH": ["/cmds/std/", "/cmds/skill/"],
}

# ── 命令对象常量（提取自 command.h） ──────────────────────────────────

COMMAND_OBJECTS: dict[str, str] = {
    "DROP_CMD": "/cmds/std/drop",
    "GET_CMD": "/cmds/std/get",
    "GO_CMD": "/cmds/std/go",
    "KILL_CMD": "/cmds/std/kill",
    "TELL_CMD": "/cmds/std/tell",
    "UPTIME_CMD": "/cmds/usr/uptime",
    "WHO_CMD": "/cmds/usr/who",
    "MUDLIST_CMD": "/cmds/usr/mudlist",
}

# ── 全局方向别名映射（提取自 aliasd.c global_alias） ──────────────────
# 仅提取方向别名，非方向别名（l/i/tf/tt/tt*）单独列出。

DIRECTION_ALIASES: dict[str, str] = {
    "n": "go north",
    "e": "go east",
    "w": "go west",
    "s": "go south",
    "nu": "go northup",
    "eu": "go eastup",
    "wu": "go westup",
    "su": "go southup",
    "nd": "go northdown",
    "ed": "go eastdown",
    "wd": "go westdown",
    "sd": "go southdown",
    "ne": "go northeast",
    "se": "go southeast",
    "nw": "go northwest",
    "sw": "go southwest",
    "u": "go up",
    "d": "go down",
}

NON_DIRECTION_ALIASES: dict[str, str] = {
    "l": "look",
    "i": "inventory",
    "tf": "team fight",
    "tt": "team talk",
    "tt*": "team talk*",
}


class CommandHookBranch(StrEnum):
    """command_hook 四分支类型（按优先级顺序）。"""

    DIRECTION_SHORTCUT = "direction_shortcut"  # 无参方向快捷（arg=="" 且房间有 exit）
    NORMAL_COMMAND = "normal_command"  # find_command 查找并执行
    EMOTE = "emote"  # EMOTE_D->do_emote
    CHANNEL = "channel"  # CHANNEL_D->do_channel


# ── 函数级规格 ────────────────────────────────────────────────────────


_func_command_hook = FunctionSpec(
    signature=FunctionSignature(
        name="command_hook",
        params=[
            LPCParam(name="arg", lpc_type="string", description="命令参数（去掉动词后的部分）"),
        ],
        return_type="int",
        lpc_file="feature/command.c",
        line_range=(32, 76),
    ),
    preconditions=[
        Precondition(
            description=(
                "调用者必须是 living 状态且已通过 enable_player 注册 "
                "command_hook 为 add_action"
            ),
            lpc_expr="enable_commands() 已调用 && add_action('command_hook', '', 1) 已注册",
            kind="require",
        ),
        Precondition(
            description="verb = query_verb() 去除前导空格后非空",
            lpc_expr='(verb = remove_leading_space(query_verb())) != ""',
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="成功匹配任一分支时返回 1",
            return_value="1=命令已处理",
            kind="ensure",
        ),
        Postcondition(
            description="四分支全部未命中时返回 0",
            return_value="0=未匹配任何命令",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="四分支短路求值：首个命中即返回，后续分支不执行",
            scope="function",
        ),
        Invariant(
            description="分支优先级顺序：direction_shortcut -> normal_command -> emote -> channel",
            scope="function",
        ),
        Invariant(
            description="command_hook 本身不改变玩家状态，状态变更仅由被调命令的副作用产生",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description=(
                "分支 A：若 arg 为空且房间有对应 exit，"
                "调 find_command('go') 并 call_other 执行 go 命令"
            ),
            lpc_call='call_other(file, "main", this_object(), verb)',
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="分支 B：find_command(verb) 查找命令文件，call_other 执行命令 main 函数",
            lpc_call='call_other(file, "main", this_object(), arg)',
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="分支 C：EMOTE_D->do_emote 处理 emote 命令",
            lpc_call="EMOTE_D->do_emote(this_object(), verb, arg)",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.EXTERNAL,
            description="分支 D：CHANNEL_D->do_channel 处理频道命令",
            lpc_call="CHANNEL_D->do_channel(this_object(), verb, arg)",
        ),
    ],
    random_specs=[],
    notes=(
        "command_hook 注册为 add_action 的 catch-all（verb=''，flag=1），"
        "所有未被前述 add_action 匹配的输入都会进入 command_hook。"
        "分支 A 的方向快捷是隐式 'go'：玩家输入方向名（如 north）且无参数时，"
        "若房间有对应 exit，直接执行 go 命令。"
        "PROFILE_COMMANDS 编译开关启用时记录性能数据，不影响逻辑。"
    ),
)

_func_enable_player = FunctionSpec(
    signature=FunctionSignature(
        name="enable_player",
        params=[],
        return_type="void",
        lpc_file="feature/command.c",
        line_range=(97, 150),
    ),
    preconditions=[
        Precondition(
            description="调用者有 id 或 name 属性（用于 set_living_name）",
            lpc_expr='stringp(query("id")) || stringp(query("name"))',
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="living name 已设置（id 优先，否则 name）",
            state_change="set_living_name(query('id') or query('name'))",
            kind="effect",
        ),
        Postcondition(
            description="disabled 临时标记已清除",
            state_change='delete_temp("disabled")',
            kind="effect",
        ),
        Postcondition(
            description="command_hook 已注册为 add_action（catch-all）",
            state_change='add_action("command_hook", "", 1)',
            kind="effect",
        ),
        Postcondition(
            description="path 已按身份设置（NPC/未注册/admin/arch/wiz/...）",
            state_change="set_path(NPC_PATH | UNR_PATH | ADM_PATH | ... )",
            kind="effect",
        ),
        Postcondition(
            description=(
                "巫师身份（admin/arch/wizard/creator/virtuoso/designer/"
                "caretaker/apprentice）额外调用 enable_wizard()"
            ),
            state_change="enable_wizard()",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description=(
                "身份到路径的映射不可变：admin->ADM_PATH, "
                "arch->ARC_PATH, wizard->WIZ_PATH, "
                "creator/virtuoso/designer/caretaker/apprentice->APR_PATH, "
                "immortal->IMM_PATH, default->PLR_PATH"
            ),
            scope="system",
        ),
        Invariant(
            description="enable_player 是 nomask，子类不可覆盖",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 living name",
            lpc_call="set_living_name(query('id') or query('name'))",
            target="this_object.living_name",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="清除 disabled 标记",
            lpc_call='delete_temp("disabled")',
            target="this_object.temp.disabled",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="启用命令系统",
            lpc_call="enable_commands()",
            target="this_object.commands_enabled",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="注册 command_hook 为 catch-all add_action",
            lpc_call='add_action("command_hook", "", 1)',
            target="this_object.action_table",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="按身份设置命令路径",
            lpc_call="set_path(PATH_CONSTANT)",
            target="this_object.path",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="巫师身份额外启用 wizard 模式",
            lpc_call="enable_wizard()",
            target="this_object.wizard_mode",
        ),
    ],
    random_specs=[],
    notes=(
        "未注册玩家（query('registered')==0）使用 UNR_PATH，不区分巫师等级。"
        "NPC（!userp）使用 NPC_PATH，不调 enable_wizard。"
        "virtuoso/designer/caretaker/apprentice 四个等级共用 APR_PATH。"
    ),
)

_func_disable_player = FunctionSpec(
    signature=FunctionSignature(
        name="disable_player",
        params=[
            LPCParam(name="type", lpc_type="string", description="禁用原因描述，存入 disable_type"),
        ],
        return_type="void",
        lpc_file="feature/command.c",
        line_range=(153, 164),
    ),
    preconditions=[
        Precondition(
            description="调用者必须是 ROOT_UID 或 this_object() 自身",
            lpc_expr='geteuid(previous_object())==ROOT_UID || previous_object()==this_object()',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="disable_type 已设置为指定 type",
            state_change='set("disable_type", type)',
            kind="effect",
        ),
        Postcondition(
            description="disabled 临时标记已设置",
            state_change='set_temp("disabled", 1)',
            kind="effect",
        ),
        Postcondition(
            description=(
                "命令系统已禁用但立即重新启用（living 标记保留），"
                "实际命令阻断在 alias.c 处理"
            ),
            state_change="disable_commands() 然后 enable_commands()",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="disable_player 是 nomask，子类不可覆盖",
            scope="class",
        ),
        Invariant(
            description=(
                "disable/enable 连续调用保证对象仍标记为 living，"
                "命令阻断通过 temp/disabled 标记在 process_input 中实现"
            ),
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置禁用类型",
            lpc_call='set("disable_type", type)',
            target="this_object.disable_type",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 disabled 临时标记",
            lpc_call='set_temp("disabled", 1)',
            target="this_object.temp.disabled",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="禁用命令系统（清除 add_action 表）",
            lpc_call="disable_commands()",
            target="this_object.commands_enabled",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="重新启用命令系统（保留 living 标记，但 command_hook 未重新注册）",
            lpc_call="enable_commands()",
            target="this_object.commands_enabled",
        ),
    ],
    random_specs=[],
    notes=(
        "disable 后紧接着 enable_commands 是修复 add_action bug 的特殊处理（注释 by xuy）。"
        "目的是保持对象 living 状态，实际命令阻断在 alias.c process_input 中检查 "
        "query_temp('disabled') 实现。"
    ),
)

_func_process_input = FunctionSpec(
    signature=FunctionSignature(
        name="process_input",
        params=[
            LPCParam(name="str", lpc_type="string", description="玩家原始输入"),
        ],
        return_type="string",
        lpc_file="feature/alias.c",
        line_range=(21, 110),
    ),
    preconditions=[
        Precondition(
            description="输入非 null（但可以是空串）",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回处理后的命令字符串（可能经别名展开、历史替换、全局别名替换）",
            return_value="string=处理后的命令字符串",
            kind="ensure",
        ),
        Postcondition(
            description="输入为空串时返回空串",
            return_value='""',
            kind="ensure",
        ),
        Postcondition(
            description="玩家被强制 quit 或非 living 时返回空串",
            return_value='""',
            lpc_expr='query_temp("quit/forced") || !living(this_object())',
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="处理优先级：刷屏检测 -> 历史替换 -> 自定义别名 -> 全局别名",
            scope="function",
        ),
        Invariant(
            description="历史缓冲区固定 10 条（HISTORY_BUFFER_SIZE=10），环形覆盖",
            scope="class",
        ),
        Invariant(
            description="命令计数 cnt 在 tick 重置时减 2*CMDS_PER_TICK，不低于 0",
            lpc_expr="cnt >= 0",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="记录 last_input",
            lpc_call="last_input = str",
            target="this_object.last_input",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="递增命令计数 cnt",
            lpc_call="cnt++",
            target="this_object.cnt",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="刷屏检测超阈值时输出警告消息",
            lpc_call='tell_object(me, "滥用指令警告")',
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="超过 CMDS_PER_TICK 时扣气或精",
            lpc_call='me->receive_damage("qi", j) 或 receive_damage("jing", j/2)',
            target="this_object.qi / this_object.jing",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="超过 3*CMDS_PER_TICK 时设置 quit/forced 标记并强制 quit",
            lpc_call='set_temp("quit/forced", 1); command("quit")',
            target="this_object.temp.quit_forced",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.EXTERNAL,
            description="记录刷屏日志",
            lpc_call='log_file("FLOODER", ...)',
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="非历史命令时写入历史缓冲区",
            lpc_call="history[last_cmd] = str",
            target="this_object.history",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="自定义别名展开（含 $N / $* 参数替换）",
            lpc_call="alias[str] 或 alias[cmd] 替换",
            target="return value",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.EXTERNAL,
            description="全局别名处理（委托 ALIAS_D->process_global_alias）",
            lpc_call="ALIAS_D->process_global_alias(str)",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(2)",
            probability_model="0.5 概率",
            semantic="刷屏超限惩罚时 50% 概率天雷劈中（昏迷），50% 概率劈空",
            seed_inputs=["无外部 seed，使用系统 RNG"],
            determinism_note="刷屏惩罚的随机性在本层，非 combat 范围，不需要确定性 RNG",
        ),
    ],
    notes=(
        "刷屏检测仅对 userp 且 living 的对象生效。"
        "历史替换以 '!' 开头：'!N' 替换为第 N 条历史，'!' 替换为最近一条。"
        "自定义别名支持 $N（位置参数）和 $*（全部参数）替换。"
        "语言转换（BIG5->GB）在本函数中处理但属于后置范围。"
        "clear_cmd_count 由 tick 调用，每 tick 减 2*CMDS_PER_TICK。"
    ),
)

_func_find_command_commandd = FunctionSpec(
    signature=FunctionSignature(
        name="find_command",
        params=[
            LPCParam(name="verb", lpc_type="string", description="命令动词"),
            LPCParam(name="path", lpc_type="string *", description="命令搜索路径列表"),
        ],
        return_type="string",
        lpc_file="adm/daemons/commandd.c",
        line_range=(28, 48),
    ),
    preconditions=[
        Precondition(
            description="path 必须是数组（pointerp）",
            lpc_expr="pointerp(path)",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="找到命令时返回完整路径（如 '/cmds/std/go'）",
            return_value="string=命令文件完整路径",
            kind="ensure",
        ),
        Postcondition(
            description="未找到或 valid_cmd 不通过时返回 0",
            return_value="0=未找到或不允许",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="搜索方向为逆序：从 path 尾部向头部（while(i--)），尾部路径优先",
            scope="function",
        ),
        Invariant(
            description="每条命令必须通过 SECURITY_D->valid_cmd 校验才能返回",
            lpc_expr='SECURITY_D->valid_cmd(cmd, this_player(), "cmd_file")',
            scope="system",
        ),
        Invariant(
            description="首次访问某路径时触发 rehash 建立缓存，后续从缓存读取",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="首次访问路径时调 rehash 建立命令文件缓存",
            lpc_call="rehash(path[i])",
            target="search[path[i]]",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="调用 SECURITY_D 校验命令权限",
            lpc_call='SECURITY_D->valid_cmd(cmd, this_player(), "cmd_file")',
        ),
    ],
    random_specs=[],
    notes=(
        "search 是 mapping，key 为目录路径（含尾部 /），value 为该目录下命令名数组。"
        "rehash 过滤掉非 .c 文件，只缓存 .c 文件名（去掉 .c 后缀）。"
        "注意 command.c 也有一个 find_command 包装函数，委托给 COMMAND_D。"
    ),
)

_func_rehash = FunctionSpec(
    signature=FunctionSignature(
        name="rehash",
        params=[
            LPCParam(name="dir", lpc_type="string", description="要扫描的目录路径"),
        ],
        return_type="void",
        lpc_file="adm/daemons/commandd.c",
        line_range=(10, 26),
    ),
    preconditions=[
        Precondition(
            description="dir 是有效目录路径",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="search[dir]（dir 含尾部 /）已更新为该目录下所有 .c 文件名（去 .c 后缀）",
            state_change="search[dir + '/'] = cmds",
            kind="effect",
        ),
        Postcondition(
            description="目录无 .c 文件时不写入 search（保持 undefined）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只缓存 .c 文件，非 .c 文件被过滤",
            scope="function",
        ),
        Invariant(
            description="dir 自动补尾部 /（若无）",
            lpc_expr='dir[sizeof(dir)-1]==\'/\' || dir += "/"',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="扫描目录并缓存命令文件列表",
            lpc_call="get_dir(dir); search[dir] = cmds",
            target="search[dir]",
        ),
    ],
    random_specs=[],
    notes="rehash 在 find_command 首次访问某路径时自动调用，也可手动调用来刷新缓存。",
)

_func_process_global_alias = FunctionSpec(
    signature=FunctionSignature(
        name="process_global_alias",
        params=[
            LPCParam(name="arg", lpc_type="string", description="玩家输入字符串"),
        ],
        return_type="string",
        lpc_file="adm/daemons/aliasd.c",
        line_range=(39, 54),
    ),
    preconditions=[
        Precondition(
            description="arg 非空且长度 >= 1",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="输入以 ' 开头时返回 'say ' + 剩余部分",
            return_value='"say " + arg[1..]',
            kind="ensure",
        ),
        Postcondition(
            description="首个词在 global_alias 中时返回替换后的完整命令",
            return_value="替换后的命令字符串",
            kind="ensure",
        ),
        Postcondition(
            description="无匹配时返回原始 arg",
            return_value="arg（未修改）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只替换首个词（word[0]），后续参数保持不变",
            scope="function",
        ),
        Invariant(
            description="current_alias 在处理前被设置为原始 arg（用于调试/查询）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="记录当前别名输入（调试用）",
            lpc_call="current_alias = arg",
            target="aliasd.current_alias",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="替换首个词为全局别名值",
            lpc_call="word[0] = global_alias[word[0]]",
            target="return value",
        ),
    ],
    random_specs=[],
    notes=(
        "say 快捷方式：以 ' 开头的输入自动转为 say 命令（如 'hello -> say hello）。"
        "全局别名在 process_input 的最后一步调用，优先级低于自定义别名。"
    ),
)

_func_find_command_wrapper = FunctionSpec(
    signature=FunctionSignature(
        name="find_command",
        params=[
            LPCParam(name="verb", lpc_type="string", description="命令动词"),
        ],
        return_type="string",
        lpc_file="feature/command.c",
        line_range=(16, 19),
    ),
    preconditions=[
        Precondition(
            description="path 已通过 set_path 设置（enable_player 时）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="委托 COMMAND_D->find_command(verb, path) 查找，返回命令文件路径或 0",
            return_value="string=命令路径 | 0=未找到",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="此函数是 commandd.c find_command 的薄包装，使用对象的 path",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes=(
        "此函数暴露给其他对象（如 help）搜索当前对象的命令。"
        "path 是 static 属性，不会被 restore_object 读取。"
    ),
)

_func_force_me = FunctionSpec(
    signature=FunctionSignature(
        name="force_me",
        params=[
            LPCParam(name="cmd", lpc_type="string", description="要强制执行的命令字符串"),
        ],
        return_type="int",
        lpc_file="feature/command.c",
        line_range=(89, 95),
    ),
    preconditions=[
        Precondition(
            description="调用者必须是 ROOT_UID",
            lpc_expr='geteuid(previous_object())==ROOT_UID',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="命令经 process_input 处理后执行，返回 command() 的结果",
            return_value="int=command() 返回值",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="force_me 是特权操作，只有 ROOT_UID 可以调用",
            scope="system",
        ),
        Invariant(
            description="命令先经 process_input（别名/历史/刷屏检测）再执行",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="调用 process_input 处理命令（可能触发别名展开/历史替换）",
            lpc_call="this_object()->process_input(cmd)",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="执行命令",
            lpc_call="command(processed_cmd)",
        ),
    ],
    random_specs=[],
    notes="force_me 是 CLAUDE.md 架构不变量中的 PrivilegedAction：ROOT 门控 + 强制审计。",
)

_func_set_alias = FunctionSpec(
    signature=FunctionSignature(
        name="set_alias",
        params=[
            LPCParam(name="verb", lpc_type="string", description="别名键"),
            LPCParam(
                name="replace",
                lpc_type="string",
                description="替换模板（含 $N/$* 占位符），null 表示删除",
            ),
        ],
        return_type="int",
        lpc_file="feature/alias.c",
        line_range=(120, 132),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="replace 为 null 时删除已有别名，返回 1",
            return_value="1=成功",
            kind="ensure",
        ),
        Postcondition(
            description="replace 非空且别名数未超限时添加别名，返回 1",
            return_value="1=成功",
            kind="ensure",
        ),
        Postcondition(
            description="别名数超过 MAX_ALIASES(40) 时返回 notify_fail，不添加",
            return_value="0=超出上限",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="单对象别名数上限 MAX_ALIASES=40",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="添加或删除别名映射",
            lpc_call="alias[verb]=replace 或 map_delete(alias, verb)",
            target="this_object.alias",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="超出上限时输出提示消息",
            lpc_call='notify_fail("您设定的 alias 太多了...")',
        ),
    ],
    random_specs=[],
    notes="玩家自定义别名管理。本层规格中仅提取契约，自定义别名的完整实现后置。",
)


# ── 命令前置 deny 规则规格（ADR-0016 第二批层1 谓词集） ────────────────
# 本节规格化 cmds/std/kill.c 与 cmds/std/ask.c 的命令前置 deny 检查，作为
# 层1 EventRule(event=command) 的规格源（[ADR-0016](../../docs/adr/
# ADR-0016-layer1-predicate-expansion-batch2.md) 决策 6/7/8）。层1 仅管前置
# deny 条件，命令主体（副作用）仍层3（"层1 管条件，层3 管副作用"分工）。


class CommandDenyRule(BaseModel):
    """命令前置 deny 规格条目（层1 command 事件规则的规格源）。

    每条对应 LPC 命令主体内的一处 ``notify_fail`` 前置检查。``layer1_predicates``
    列出可表达该条件的层1 谓词组合（ADR-0016 扩充集），用于校验"逃生舱层3"
    KPI（kill criteria 4）：能用扩充后谓词集表达即不算逃生舱。
    """

    verb: str  # 命令动词（LPC add_action verb，如 "kill" / "ask" / "knock"）
    deny_message: str  # LPC notify_fail 的提示文本
    lpc_expr: str  # 对应 LPC 判定表达式
    lpc_file: str  # 源文件
    line_range: tuple[int, int]
    # 表达该条件的层1 谓词（ADR-0016 扩充集），任一非空即该规则可层1 化
    layer1_predicates: list[str] = Field(default_factory=list)
    notes: str | None = None


# cmds/std/kill.c 的 7 条前置 deny（ADR-0016 决策 6 实证）。
# 行号对齐 kill.c 源（cmds/std/kill.c）。
COMMAND_DENY_RULES_KILL: list[CommandDenyRule] = [
    CommandDenyRule(
        verb="kill",
        deny_message="这里不准战斗。",
        lpc_expr="environment(me)->query(\"no_fight\") 或等价 no_fight 标记",
        lpc_file="cmds/std/kill.c",
        line_range=(15, 17),
        layer1_predicates=["has_flag(flag=no_fight)"],
        notes="场所禁止战斗标记（环境层 deny）。",
    ),
    CommandDenyRule(
        verb="kill",
        deny_message="你想杀谁？",
        lpc_expr='arg == ""',
        lpc_file="cmds/std/kill.c",
        line_range=(18, 20),
        layer1_predicates=["attr_eq(attr=__arg, value_str=\"\")"],
        notes="无目标参数 deny；属命令输入约束。",
    ),
    CommandDenyRule(
        verb="kill",
        deny_message="这里没有这个人。",
        lpc_expr="!objectp(obj) || !present(obj, environment(me))",
        lpc_file="cmds/std/kill.c",
        line_range=(21, 23),
        layer1_predicates=["present_npc(npc_id=target)"],
        notes="目标对象不在场 deny；present_npc 反向（目标缺席）。",
    ),
    CommandDenyRule(
        verb="kill",
        deny_message="你不能杀这个人！",
        lpc_expr='SECURITY_D->get_status(me)=="(immortal)" && get_status(obj)!="(immortal)"',
        lpc_file="cmds/std/kill.c",
        line_range=(25, 27),
        layer1_predicates=["all(is_wizard, not(derived_state(state=immortal)(target)))"],
        notes="巫师(immortal 身份) 不可杀非 immortal；is_wizard 谓词覆盖身份判断。",
    ),
    CommandDenyRule(
        verb="kill",
        deny_message="你不能杀这个人！",
        lpc_expr="me->query_temp(\"last_persuader\") == obj->query(\"id\")",
        lpc_file="cmds/std/kill.c",
        line_range=(29, 31),
        layer1_predicates=["status_eq(flag=last_persuader, source=temp, value_str=target_id)"],
        notes="劝降保护：temp 标记 == 目标 id；has_flag source=temp 扩展（决策 4）。",
    ),
    CommandDenyRule(
        verb="kill",
        deny_message="他/她已经投降了,你现在不能杀！",
        lpc_expr='me->query(\"id\") == obj->query_temp(\"surrender/ownder\")',
        lpc_file="cmds/std/kill.c",
        line_range=(33, 34),
        layer1_predicates=["same_object"],
        notes="目标已投降本 actor：对象引用相等（same_object 谓词，决策 6）。",
    ),
    CommandDenyRule(
        verb="kill",
        deny_message="你刚投降过别人，别老想着干坏事！",
        lpc_expr='me->query_temp(\"surrender/ownder\") != 0',
        lpc_file="cmds/std/kill.c",
        line_range=(36, 37),
        layer1_predicates=["has_flag(flag=surrender/ownder, source=temp)"],
        notes="本 actor 刚投降过：temp 标记存在性（决策 4 has_flag 扩展）。",
    ),
    CommandDenyRule(
        verb="kill",
        deny_message="你感到一丝内疚，手突然软了下来！",
        lpc_expr='PKer 内疚 || obj->query(\"mud_age\") < 18000',
        lpc_file="cmds/std/kill.c",
        line_range=(50, 53),
        layer1_predicates=["any(has_flag(flag=pker_guilt), mud_age_lt(value=18000))"],
        notes="目标游戏年龄过小或 PKer 内疚 deny；mud_age_lt 谓词（决策 6）。",
    ),
]

# cmds/std/ask.c 对话分支（ADR-0016 决策 7 实证）。
COMMAND_DENY_RULES_ASK: list[CommandDenyRule] = [
    CommandDenyRule(
        verb="ask",
        deny_message="你要问谁什么事？",
        lpc_expr='arg == "" 或 arg 缺少目标/topic',
        lpc_file="cmds/std/ask.c",
        line_range=(40, 42),
        layer1_predicates=["attr_eq(attr=__arg, value_str=\"\")"],
        notes="无参数 deny；命令输入约束。",
    ),
    CommandDenyRule(
        verb="ask",
        deny_message="这里没有这个人。",
        lpc_expr="!objectp(ob) || !present(ob, environment(me))",
        lpc_file="cmds/std/ask.c",
        line_range=(43, 45),
        layer1_predicates=["present_npc(npc_id=target)"],
        notes="目标 NPC 不在场 deny。",
    ),
    CommandDenyRule(
        verb="ask",
        deny_message="何必问自己？",
        lpc_expr="ob == me",
        lpc_file="cmds/std/ask.c",
        line_range=(46, 48),
        layer1_predicates=["same_object"],
        notes="自问自答 deny；same_object 谓词（决策 6）。",
    ),
    CommandDenyRule(
        verb="ask",
        deny_message="<topic 对话分支>",
        lpc_expr='ob->query(\"inquiry/\" + topic)',
        lpc_file="cmds/std/ask.c",
        line_range=(68, 70),
        layer1_predicates=["has_inquiry(topic=<topic>)"],
        notes="NPC inquiry 列表含 topic 时走该分支；has_inquiry 谓词（决策 7）。",
    ),
    CommandDenyRule(
        verb="ask",
        deny_message="<attitude 响应分支>",
        lpc_expr='att = ob->query(\"attitude\"); att in {\"good\", \"bad\", ...}',
        lpc_file="cmds/std/ask.c",
        line_range=(81, 110),
        layer1_predicates=["attr_in(attr=attitude, values=[\"good\",\"bad\",...])"],
        notes="按 attitude 枚举分支响应；attr_in 谓词（决策 7，字面量列表不正则）。",
    ),
]

# kill.c + ask.c 命令前置 deny 规格全集（供层1 command 事件规则生成校验）。
COMMAND_DENY_RULES: list[CommandDenyRule] = COMMAND_DENY_RULES_KILL + COMMAND_DENY_RULES_ASK


# ── 层规格实例 ────────────────────────────────────────────────────────

LAYER_SPEC: LayerSpec = LayerSpec(
    layer_id="C",
    layer_name="命令系统",
    lpc_files=[
        "feature/command.c",
        "feature/alias.c",
        "adm/daemons/commandd.c",
        "adm/daemons/aliasd.c",
        "include/command.h",
    ],
    function_specs=[
        _func_command_hook,
        _func_enable_player,
        _func_disable_player,
        _func_process_input,
        _func_find_command_commandd,
        _func_rehash,
        _func_process_global_alias,
        _func_find_command_wrapper,
        _func_force_me,
        _func_set_alias,
    ],
    cross_layer_refs=[
        "SECURITY_D->valid_cmd (层 H 安全系统)",
        "EMOTE_D->do_emote (emote 系统，本层仅调用)",
        "CHANNEL_D->do_channel (频道系统，本层仅调用)",
        "ALIAS_D->process_global_alias (aliasd.c，本层内)",
        "COMMAND_D->find_command (commandd.c，本层内)",
        "enable_commands/disable_commands (层 A 驱动桥梁)",
        "add_action (层 A 驱动桥梁)",
        "set_living_name (层 A 驱动桥梁)",
        "receive_damage (层 E 战斗系统)",
        "unconcious (层 E/D 伤损与状态)",
        "command() efun (层 A 驱动桥梁)",
    ],
    notes=(
        "本层是命令分发管线，连接驱动桥梁（A）与各命令实现（散布多层）。"
        "command_hook 四分支优先级是核心不变量。"
        "process_input 的刷屏检测包含天雷惩罚随机性（random(2)），"
        "但此随机性属本层而非 combat 范围，不需要确定性 RNG。"
        "方向别名映射（DIRECTION_ALIASES）和命令路径常量（COMMAND_PATHS）"
        "作为模块级常量导出，供其他层引用。"
    ),
)
