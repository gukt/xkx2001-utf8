"""层 A：驱动桥梁规格（映射 ADR-0010 9 层范围定义）。

本层覆盖 LPC 驱动与 mudlib 之间的桥梁接口：

- ``adm/single/master.c`` -- Master 对象，提供连接入口、错误处理、启动回调、
  安全校验钩子等 apply 函数，由 FluffOS 驱动在特定时机回调。
- ``adm/single/simul_efun.c`` -- Simul Efun 聚合体，通过 ``#include`` 将
  object.c / path.c / wizard.c / file.c 等模块注入全局仿真 efun 命名空间。
- ``config.xkx`` -- 驱动配置文件，定义端口、预加载路径、各种限制。

提取范围限定在被核心路径调用的函数（任务要求"不做 simul_efun 9 个模块逐个提取"）。
Simul Efun 中仅提取 ``destruct`` 封装、``getoid``、``file_owner``、``domain_file``、
``creator_file``、``base_name``、``resolve_path`` -- 这些被 master.c 或核心路径
（command_hook / combat / login）直接调用的函数。

Master 对象中的 ``crash``、``compile_object``、``log_error``、``destruct_env_of``
等辅助函数也一并提取，因为它们是驱动回调契约的一部分。
"""

from __future__ import annotations

from xkx.spec.base import (
    FunctionSignature,
    FunctionSpec,
    Invariant,
    LayerSpec,
    LPCParam,
    Postcondition,
    Precondition,
    SideEffect,
    SideEffectType,
)

# ── master.c ──────────────────────────────────────────────────────────────

_connect = FunctionSpec(
    signature=FunctionSignature(
        name="connect",
        params=[],
        return_type="object",
        lpc_file="adm/single/master.c",
        line_range=(12, 25),
    ),
    preconditions=[
        Precondition(
            description="驱动收到新 TCP 连接后回调此函数，调用时 this_object() 为 master 对象",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 login 对象实例（LOGIN_OB = /clone/user/login）",
            return_value="login_ob 对象，或创建失败时 master 自身被 destruct",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="login_ob 通过 new(LOGIN_OB) 创建，失败时 catch 拦截异常",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="new(LOGIN_OB) 创建 login 对象，catch 包裹",
            lpc_call="new(LOGIN_OB)",
            target="login_ob",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="创建失败时向连接写入中文错误消息（含原始错误信息）",
            lpc_call='write("现在有人正在修改使用者连线部份的程式，请待会再来。\\n")',
            target="connection",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="创建失败时 destruct(this_object()) 销毁当前连接对象",
            lpc_call="destruct(this_object())",
            target="this_object()",
        ),
    ],
    notes="connect 是玩家进入游戏的唯一入口。返回的 login 对象属层 I（角色与登录）。"
    "FluffOS 驱动在新 TCP 连接到达时自动 apply 此函数。",
)

_crash = FunctionSpec(
    signature=FunctionSignature(
        name="crash",
        params=[
            LPCParam(name="error", lpc_type="string", description="驱动崩溃错误信息"),
            LPCParam(
                name="command_giver",
                lpc_type="object",
                description="当前 this_player()，可能为 null",
            ),
            LPCParam(
                name="current_object",
                lpc_type="object",
                description="崩溃时正在执行的对象，可能为 null",
            ),
        ],
        return_type="void",
        lpc_file="adm/single/master.c",
        line_range=(44, 58),
    ),
    preconditions=[
        Precondition(
            description="驱动发生段错误/总线错误等致命错误时回调",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="向全服广播崩溃消息并写入 CRASHES 日志",
            state_change="static/CRASHES 日志追加一条崩溃记录",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="此函数为 static（仅驱动可调用），不允许玩家或其他对象直接调用",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description='向全服 shout 崩溃消息："系统核心发出一声惨叫：哇-哩-咧-"',
            lpc_call='efun::shout("系统核心发出一声惨叫：哇-哩-咧-\\n")',
            target="all_users",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description='向全服 shout："系统核心告诉你：要当机了，自己保重吧！"',
            lpc_call='efun::shout("系统核心告诉你：要当机了，自己保重吧！\\n")',
            target="all_users",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="将崩溃时间、错误信息写入 static/CRASHES 日志",
            lpc_call='log_file("static/CRASHES", ...)',
            target="static/CRASHES",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.EXTERNAL,
            description="若 command_giver 非 null，记录 this_player 信息到 CRASHES 日志",
            lpc_call='log_file("static/CRASHES", sprintf("this_player: %O\\n", command_giver))',
            target="static/CRASHES",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.EXTERNAL,
            description="若 current_object 非 null，记录 this_object 信息到 CRASHES 日志",
            lpc_call='log_file("static/CRASHES", sprintf("this_object: %O\\n", current_object))',
            target="static/CRASHES",
        ),
    ],
    notes="crash 是驱动的致命错误回调。static 修饰符确保仅驱动可调用。",
)

_epilog = FunctionSpec(
    signature=FunctionSignature(
        name="epilog",
        params=[
            LPCParam(name="load_empty", lpc_type="int", description="是否空载启动标志"),
        ],
        return_type="string *",
        lpc_file="adm/single/master.c",
        line_range=(85, 91),
    ),
    preconditions=[
        Precondition(
            description="驱动启动完成后、进入主循环前回调",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 preload 文件列表（从 CONFIG_DIR + 'preload' 读取）",
            return_value="string * -- 预加载文件路径数组",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="update_file 过滤以 '#' 开头的注释行和空行",
            lpc_expr="每行不以 '#' 开头",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="读取 adm/etc/preload 文件内容",
            lpc_call="read_file(CONFIG_DIR + 'preload')",
            target="adm/etc/preload",
        ),
    ],
    notes="CONFIG_DIR = '/adm/etc/'（globals.h）。返回的列表由驱动逐条调用 preload()。",
)

_preload = FunctionSpec(
    signature=FunctionSignature(
        name="preload",
        params=[
            LPCParam(name="file", lpc_type="string", description="要预加载的文件路径"),
        ],
        return_type="void",
        lpc_file="adm/single/master.c",
        line_range=(94, 110),
    ),
    preconditions=[
        Precondition(
            description="参数 file 为 epilog() 返回列表中的某一项",
            kind="require",
        ),
        Precondition(
            description="文件存在（file_size(file + '.c') != -1），否则直接 return",
            lpc_expr="file_size(file + '.c') != -1",
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="对象被加载到内存（call_other(file, '??') 触发 create()）",
            state_change="对象加载到内存",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="加载错误被 catch 拦截，不中断后续 preload",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description='输出 "Preloading : <file>" 进度信息',
            lpc_call='write("Preloading : " + file)',
            target="stdout",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="call_other(file, '??') 加载对象（触发 create()）",
            lpc_call="call_other(file, '??')",
            target="file",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="加载成功输出 '.... Done.'，失败输出错误信息",
            lpc_call='write(" -> Error " + err + " when loading " + file + "\\n")',
            target="stdout",
        ),
    ],
    notes="驱动对 epilog() 返回的每条路径调用此函数。'??' 是 LPC 简写，等价于调用 create()。",
)

_error_handler = FunctionSpec(
    signature=FunctionSignature(
        name="error_handler",
        params=[
            LPCParam(
                name="error",
                lpc_type="mapping",
                description="错误信息映射，含 error/program/line/object/trace 键",
            ),
            LPCParam(
                name="caught",
                lpc_type="int",
                description="是否被 catch 拦截（1=被拦截, 0=未拦截）",
            ),
        ],
        return_type="string",
        lpc_file="adm/single/master.c",
        line_range=(236, 248),
    ),
    preconditions=[
        Precondition(
            description="运行时段错误发生时由驱动回调",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回格式化的错误追踪字符串，写入 debug.log",
            return_value="standard_trace 格式化的错误信息字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="this_player(1) 存在时，wizard 显示完整 trace，非 wizard 显示模糊消息",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="this_player(1) 是 wizard 时，tell_object 完整错误追踪",
            lpc_call="tell_object(this_player(1), standard_trace(error, caught))",
            target="this_player(1)",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="this_player(1) 非 wizard 时，tell_object 模糊消息（黄色 ANSI）",
            lpc_call='tell_object(this_player(1), "你发现事情不大对了，可是又说不上来。\\n")',
            target="this_player(1)",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="将当前别名写入 debug.log",
            lpc_call='log_file("debug.log", ALIAS_D->get_current_alias() + "\\n")',
            target="debug.log",
        ),
    ],
    notes="返回值由驱动写入 debug.log。standard_trace 生成包含调用栈的格式化字符串。"
    "ALIAS_D = /adm/daemons/aliasd。",
)

_valid_seteuid = FunctionSpec(
    signature=FunctionSignature(
        name="valid_seteuid",
        params=[
            LPCParam(name="ob", lpc_type="object", description="请求设置 euid 的对象"),
            LPCParam(name="str", lpc_type="string", description="目标 euid 字符串"),
        ],
        return_type="int",
        lpc_file="adm/single/master.c",
        line_range=(271, 274),
    ),
    preconditions=[
        Precondition(
            description="对象尝试 seteuid() 时由驱动回调",
            kind="require",
        ),
        Precondition(
            description="SECURITY_D 守护进程已加载（find_object(SECURITY_D) 非 null）",
            lpc_expr="find_object(SECURITY_D)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="委托 SECURITY_D 判断 euid 设置权限",
            return_value="1=允许设置, 0=拒绝",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="权限判定全部委托给 SECURITY_D，master 不做独立判断",
            scope="function",
        ),
    ],
    side_effects=[],
    notes="SECURITY_D = /adm/daemons/securityd。属层 H（核心守护进程）。",
)

_valid_override = FunctionSpec(
    signature=FunctionSignature(
        name="valid_override",
        params=[
            LPCParam(name="file", lpc_type="string", description="请求 override 的文件路径"),
            LPCParam(name="name", lpc_type="string", description="要 override 的 efun 名称"),
        ],
        return_type="int",
        lpc_file="adm/single/master.c",
        line_range=(256, 268),
    ),
    preconditions=[
        Precondition(
            description="对象编译期使用 efun:: 前缀时回调",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="simul_efun 和 master 可 override 任意 efun",
            return_value="1=允许, 0=拒绝",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="move_object 和 destruct 只能由 F_MOVE 定义的 move() override",
            lpc_expr="(name=='move_object'||name=='destruct') && file!=F_MOVE => 0",
            scope="system",
        ),
    ],
    side_effects=[],
    notes="此函数仅在编译期调用。F_MOVE = /feature/move.c（属层 B 对象基础）。",
)

_valid_write = FunctionSpec(
    signature=FunctionSignature(
        name="valid_write",
        params=[
            LPCParam(name="file", lpc_type="string", description="目标文件路径"),
            LPCParam(name="user", lpc_type="mixed", description="发起写操作的对象或 euid"),
            LPCParam(name="func", lpc_type="string", description="发起调用的函数名"),
        ],
        return_type="int",
        lpc_file="adm/single/master.c",
        line_range=(327, 335),
    ),
    preconditions=[
        Precondition(
            description="对象尝试写文件时由驱动回调",
            kind="require",
        ),
        Precondition(
            description="SECURITY_D 已加载（find_object(SECURITY_D) 非 null），否则返回 0",
            lpc_expr="find_object(SECURITY_D)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="委托 SECURITY_D 判断写文件权限",
            return_value="1=允许写, 0=拒绝",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="权限判定全部委托给 SECURITY_D",
            scope="function",
        ),
    ],
    side_effects=[],
    notes="SECURITY_D 未加载时默认拒绝（返回 0）。",
)

_valid_read = FunctionSpec(
    signature=FunctionSignature(
        name="valid_read",
        params=[
            LPCParam(name="file", lpc_type="string", description="目标文件路径"),
            LPCParam(name="user", lpc_type="mixed", description="发起读操作的对象或 euid"),
            LPCParam(name="func", lpc_type="string", description="发起调用的函数名"),
        ],
        return_type="int",
        lpc_file="adm/single/master.c",
        line_range=(338, 341),
    ),
    preconditions=[
        Precondition(
            description="对象尝试读文件时由驱动回调",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="读权限默认全允许",
            return_value="恒返回 1",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="valid_read 无条件返回 1，所有对象可读所有文件",
            scope="system",
        ),
    ],
    side_effects=[],
    notes="与 valid_write 不对称：读权限完全开放，写权限委托 SECURITY_D。",
)

_valid_shadow = FunctionSpec(
    signature=FunctionSignature(
        name="valid_shadow",
        params=[
            LPCParam(name="ob", lpc_type="object", description="被 shadow 的目标对象"),
        ],
        return_type="int",
        lpc_file="adm/single/master.c",
        line_range=(251, 251),
    ),
    preconditions=[
        Precondition(
            description="对象尝试 shadow 另一对象时由驱动回调",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="禁止所有 shadow",
            return_value="恒返回 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="valid_shadow 无条件返回 0，全局禁止 shadow",
            scope="system",
        ),
    ],
    side_effects=[],
    notes="侠客行全局禁用 shadow 机制。Python 重构中不涉及 shadow 概念。",
)

_valid_hide = FunctionSpec(
    signature=FunctionSignature(
        name="valid_hide",
        params=[
            LPCParam(name="who", lpc_type="object", description="请求 hide 或 see hidden 的对象"),
        ],
        return_type="int",
        lpc_file="adm/single/master.c",
        line_range=(299, 301),
    ),
    preconditions=[
        Precondition(
            description="对象使用 set_hide() efun 时由驱动回调",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="允许所有 hide 操作",
            return_value="恒返回 1",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="valid_hide 无条件返回 1",
            scope="system",
        ),
    ],
    side_effects=[],
    notes="hide 机制允许对象对非特权对象不可见。Python 重构中可后置。",
)

_log_error = FunctionSpec(
    signature=FunctionSignature(
        name="log_error",
        params=[
            LPCParam(name="file", lpc_type="string", description="编译出错的文件路径"),
            LPCParam(name="message", lpc_type="string", description="错误消息"),
        ],
        return_type="void",
        lpc_file="adm/single/master.c",
        line_range=(114, 129),
    ),
    preconditions=[
        Precondition(
            description="编译时段错误发生时由驱动回调",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="向 wizard 显示编译错误（非 Warning 时）",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="SIMUL_EFUN_OB 已加载时才计算 file_owner",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="this_player(1) 是 wizard 且非 Warning 消息时，write 编译错误信息",
            lpc_call='efun::write("编译时段错误：" + message + "\\n")',
            target="this_player(1)",
        ),
    ],
    notes="原始代码中 write_file 被注释掉（系统崩溃风险），实际不写日志文件。"
    "file_owner 和 user_path 用于确定日志目录但未实际写入。",
)

_destruct_env_of = FunctionSpec(
    signature=FunctionSignature(
        name="destruct_env_of",
        params=[
            LPCParam(name="ob", lpc_type="object", description="环境被销毁的对象"),
        ],
        return_type="void",
        lpc_file="adm/single/master.c",
        line_range=(162, 168),
    ),
    preconditions=[
        Precondition(
            description="对象所在环境被 destruct 时由驱动回调",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="interactive 玩家被移动到 VOID_OB 安全区",
            state_change="ob.move(VOID_OB)",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="非 interactive 对象直接 return，不做处理",
            lpc_expr="interactive(ob)",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="向 interactive 玩家发送空间毁灭消息",
            lpc_call='tell_object(ob, "你所存在的空间被毁灭了。\\n")',
            target="ob",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="将玩家移动到 VOID_OB",
            lpc_call="ob->move(VOID_OB)",
            target="ob",
        ),
    ],
    notes="VOID_OB = /clone/misc/void。防止玩家因环境销毁而掉入虚无。",
)

_get_root_uid = FunctionSpec(
    signature=FunctionSignature(
        name="get_root_uid",
        params=[],
        return_type="string",
        lpc_file="adm/single/master.c",
        line_range=(185, 188),
    ),
    preconditions=[
        Precondition(
            description="驱动启动时回调，获取 Root UID",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 ROOT_UID 常量",
            return_value="'Root'",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="ROOT_UID 是全局常量（globals.h #define ROOT_UID 'Root'）",
            scope="system",
        ),
    ],
    side_effects=[],
    notes="UID 系统在 Python 重构中映射为权限令牌（CapabilityToken）。",
)

_get_bb_uid = FunctionSpec(
    signature=FunctionSignature(
        name="get_bb_uid",
        params=[],
        return_type="string",
        lpc_file="adm/single/master.c",
        line_range=(190, 193),
    ),
    preconditions=[
        Precondition(
            description="驱动启动时回调，获取 Backbone UID",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 BACKBONE_UID 常量",
            return_value="'Backbone'",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="BACKBONE_UID 是全局常量（globals.h #define BACKBONE_UID 'Backbone'）",
            scope="system",
        ),
    ],
    side_effects=[],
    notes="Backbone UID 是非特权对象的默认 euid。",
)

_valid_object = FunctionSpec(
    signature=FunctionSignature(
        name="valid_object",
        params=[
            LPCParam(name="ob", lpc_type="object", description="被加载的对象"),
        ],
        return_type="int",
        lpc_file="adm/single/master.c",
        line_range=(305, 308),
    ),
    preconditions=[
        Precondition(
            description="驱动加载对象后回调，校验对象是否合法",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="非克隆对象或继承 F_MOVE 的克隆对象允许存在",
            return_value="1=合法, 0=非法",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="克隆对象必须继承 F_MOVE 才被视为合法",
            lpc_expr="!clonep(ob) || inherits(F_MOVE, ob)",
            scope="system",
        ),
    ],
    side_effects=[],
    notes="F_MOVE = /feature/move.c。确保所有可移动对象都实现了 move() 接口。",
)

_valid_bind = FunctionSpec(
    signature=FunctionSignature(
        name="valid_bind",
        params=[
            LPCParam(name="binder", lpc_type="object", description="发起 bind 的对象"),
            LPCParam(name="old_owner", lpc_type="object", description="原 owner"),
            LPCParam(name="new_owner", lpc_type="object", description="新 owner"),
        ],
        return_type="int",
        lpc_file="adm/single/master.c",
        line_range=(353, 359),
    ),
    preconditions=[
        Precondition(
            description="对象尝试 bind 时由驱动回调",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="新 owner 是 user 时拒绝；binder 是 ROOT 或 new_owner 是克隆对象时允许",
            return_value="1=允许, 0=拒绝",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="userp(new_owner) 恒为否才可能允许 bind",
            lpc_expr="!userp(new_owner)",
            scope="function",
        ),
    ],
    side_effects=[],
    notes="bind 用于函数指针的所有权转移。",
)

# ── simul_efun (object.c) ─────────────────────────────────────────────────

_destruct_simul = FunctionSpec(
    signature=FunctionSignature(
        name="destruct",
        params=[
            LPCParam(name="ob", lpc_type="object", description="要销毁的对象"),
        ],
        return_type="void",
        lpc_file="adm/simul_efun/object.c",
        line_range=(76, 83),
    ),
    preconditions=[
        Precondition(
            description="ob 非 null 时才执行 remove 回调",
            lpc_expr="ob",
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="对象先调用 remove(euid)，再由 efun::destruct 实际销毁",
            state_change="对象从内存中移除",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="remove() 回调在 efun::destruct 之前执行，确保清理逻辑有机会运行",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="ob->remove(geteuid(previous_object())) 或 ob->remove(0)",
            lpc_call="ob->remove(geteuid(previous_object()))",
            target="ob",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="efun::destruct(ob) 实际销毁对象",
            lpc_call="efun::destruct(ob)",
            target="ob",
        ),
    ],
    notes="simul_efun 封装的 destruct 覆盖了 efun::destruct，确保销毁前调用 remove()。"
    "valid_override 限制只有 F_MOVE 可以 override 此函数。",
)

_getoid = FunctionSpec(
    signature=FunctionSignature(
        name="getoid",
        params=[
            LPCParam(
                name="ob",
                lpc_type="object",
                description="目标对象，varargs，默认 previous_object()",
                is_varargs_tail=True,
            ),
        ],
        return_type="int",
        lpc_file="adm/simul_efun/object.c",
        line_range=(4, 11),
    ),
    preconditions=[
        Precondition(
            description="ob 为 null 时回退到 previous_object()",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="从 file_name(ob) 中解析 '#<id>' 部分返回对象 OID",
            return_value="克隆对象的数字 ID（从 file_name 的 # 后缀解析）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="file_name 格式为 '<路径>#<id>'，id 为非负整数",
            scope="function",
        ),
    ],
    side_effects=[],
    notes="varargs 函数。非克隆对象的 file_name 不含 '#' 后缀，sscanf 失败返回 0。",
)

_file_owner = FunctionSpec(
    signature=FunctionSignature(
        name="file_owner",
        params=[
            LPCParam(name="file", lpc_type="string", description="文件路径"),
        ],
        return_type="string",
        lpc_file="adm/simul_efun/object.c",
        line_range=(14, 25),
    ),
    preconditions=[
        Precondition(
            description="file 为字符串路径",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="/u/<dir>/<name>/<rest> 路径返回 name，否则返回 0",
            return_value="用户名或 0",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="路径必须以 /u/ 开头且有三层子路径才被认为是用户文件",
            lpc_expr='sscanf(file, "/u/%s/%s/%s", dir, name, rest) == 3',
            scope="function",
        ),
    ],
    side_effects=[],
    notes="被 master.c 的 log_error() 调用，用于确定错误日志归属的用户。",
)

_domain_file = FunctionSpec(
    signature=FunctionSignature(
        name="domain_file",
        params=[
            LPCParam(name="file", lpc_type="string", description="文件路径"),
        ],
        return_type="string",
        lpc_file="adm/simul_efun/object.c",
        line_range=(28, 36),
    ),
    preconditions=[
        Precondition(
            description="file 为字符串路径",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="/d/<domain>/... 路径返回 domain 名，否则返回 ROOT_UID",
            return_value="域名称或 'Root'",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="只有 /d/ 前缀的路径才返回非 ROOT_UID",
            lpc_expr='sscanf(file, "/d/%s/%*s", domain)',
            scope="function",
        ),
    ],
    side_effects=[],
    notes="被 master.c 的 domain_file() apply 调用。用于 UID/权限系统。",
)

_creator_file = FunctionSpec(
    signature=FunctionSignature(
        name="creator_file",
        params=[
            LPCParam(name="file", lpc_type="string", description="文件路径"),
        ],
        return_type="string",
        lpc_file="adm/simul_efun/object.c",
        line_range=(39, 64),
    ),
    preconditions=[
        Precondition(
            description="file 为字符串路径",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="根据路径首段返回 creator 身份",
            return_value="creator 名称：ROOT_UID / 'MudOS' / 'MudOB' / 用户名",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="adm 路径返回 ROOT_UID（SIMUL_EFUN_OB 返回 'MudOS'）",
            scope="function",
        ),
        Invariant(
            description="cmds 路径返回 ROOT_UID",
            scope="function",
        ),
        Invariant(
            description="u 路径返回 path[2]（用户名）",
            scope="function",
        ),
    ],
    side_effects=[],
    notes="被 master.c 的 creator_file() apply 调用。switch 无 break 的 fallthrough 行为"
    "（u 路径 fallthrough 到 d/open/ftp）是 LPC 特性，Python 实现需显式处理。"
    "this_player(1) 存在时 default 分支返回 getuid(this_player(1))。",
)

_base_name = FunctionSpec(
    signature=FunctionSignature(
        name="base_name",
        params=[
            LPCParam(name="ob", lpc_type="object", description="目标对象"),
        ],
        return_type="string",
        lpc_file="adm/simul_efun/file.c",
        line_range=(24, 32),
    ),
    preconditions=[
        Precondition(
            description="ob 为有效对象",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回去掉 '#<id>' 后缀的对象路径",
            return_value="对象蓝图路径（不含克隆 ID）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="file_name 格式为 '<路径>#<id>'，sscanf 成功时返回路径部分",
            scope="function",
        ),
    ],
    side_effects=[],
    notes="与 LPC efun file_name() 的区别：base_name 去掉克隆 ID 后缀。"
    "被核心路径广泛调用（look/combat/inventory 等）。",
)

_resolve_path = FunctionSpec(
    signature=FunctionSignature(
        name="resolve_path",
        params=[
            LPCParam(name="curr", lpc_type="string", description="当前目录（cwd）"),
            LPCParam(name="new_path", lpc_type="string", description="要解析的相对/绝对路径"),
        ],
        return_type="string",
        lpc_file="adm/simul_efun/path.c",
        line_range=(16, 51),
    ),
    preconditions=[
        Precondition(
            description="curr 为当前工作目录，null 时默认 '/'",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回绝对路径，已展开 ~ 和 .. 引用",
            return_value="规范化后的绝对路径字符串",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="'~' 前缀展开为 user_path(getuid(this_player()))",
            scope="function",
        ),
        Invariant(
            description="'..' 引用逐级回退，结果路径以 '/' 开头",
            scope="function",
        ),
        Invariant(
            description="'here' 关键字展开为当前环境房间的文件路径",
            scope="function",
        ),
    ],
    side_effects=[],
    notes="被 master.c 的 make_path_absolute() 调用（ed 编辑器路径解析）。"
    "也被 cmds 系列命令用于路径解析。new_path 为 '.' 时返回 curr。",
)

_living = FunctionSpec(
    signature=FunctionSignature(
        name="living",
        params=[
            LPCParam(name="ob", lpc_type="object", description="目标对象"),
        ],
        return_type="int",
        lpc_file="adm/simul_efun/object.c",
        line_range=(86, 91),
    ),
    preconditions=[
        Precondition(
            description="ob 非 null 时才检查",
            lpc_expr="ob",
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="ob 为 null 或 disabled 时返回 0，否则返回 efun::living(ob)",
            return_value="1=活物, 0=非活物或 disabled",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="query_temp('disabled') 为真时覆盖 efun::living 判定",
            lpc_expr="!ob->query_temp('disabled')",
            scope="function",
        ),
    ],
    side_effects=[],
    notes="simul_efun 封装的 living 覆盖了 efun::living，增加 disabled 状态检查。"
    "被 combat 系统用于判断对象是否可战斗。",
)

# ── 层规格集合 ────────────────────────────────────────────────────────────

LAYER_SPEC = LayerSpec(
    layer_id="A",
    layer_name="驱动桥梁",
    lpc_files=[
        "adm/single/master.c",
        "adm/single/simul_efun.c",
        "adm/simul_efun/object.c",
        "adm/simul_efun/path.c",
        "adm/simul_efun/wizard.c",
        "adm/simul_efun/file.c",
        "config.xkx",
    ],
    function_specs=[
        # master.c -- 驱动回调
        _connect,
        _crash,
        _epilog,
        _preload,
        _error_handler,
        _log_error,
        _destruct_env_of,
        # master.c -- 安全校验钩子
        _valid_seteuid,
        _valid_override,
        _valid_write,
        _valid_read,
        _valid_shadow,
        _valid_hide,
        _valid_object,
        _valid_bind,
        # master.c -- UID
        _get_root_uid,
        _get_bb_uid,
        # simul_efun -- 核心路径调用的仿真 efun
        _destruct_simul,
        _getoid,
        _file_owner,
        _domain_file,
        _creator_file,
        _base_name,
        _resolve_path,
        _living,
    ],
    cross_layer_refs=[
        "connect -> 层 I: 返回的 login 对象属 clone/user/login",
        "epilog -> 层 H: preload 列表包含 securityd/virtuald/logind/rankd"
        "/commandd/chinesed/emoted/aliasd/fingerd/channeld/natured/weapond 等",
        "valid_seteuid -> 层 H: SECURITY_D 委托权限判定",
        "valid_write -> 层 H: SECURITY_D 委托权限判定",
        "valid_override -> 层 B: F_MOVE (/feature/move.c) 约束",
        "valid_object -> 层 B: F_MOVE 继承校验",
        "destruct_env_of -> 层 D: VOID_OB 移动目标",
        "creator_file -> 层 H: SECURITY_D UID 体系",
        "living -> 层 E: combat 系统判断可战斗状态",
        "base_name -> 层 B/C/D: look/combat/inventory 等广泛调用",
    ],
    notes=(
        "config.xkx 关键配置项：\n"
        "- port number: 8888（玩家连接端口）\n"
        "- master file: /adm/single/master\n"
        "- simulated efun file: /adm/single/simul_efun\n"
        "- global include file: <globals.h>\n"
        "- log directory: /log\n"
        "- include directories: /include\n"
        "- save binaries directory: /binaries\n"
        "- time to clean up: 180\n"
        "- time to swap: 120\n"
        "- time to reset: 1800\n"
        "- maximum evaluation cost: 600000000\n"
        "- maximum array size: 15000\n"
        "- maximum mapping size: 15000\n"
        "- maximum string length: 200000\n"
        "- maximum users: 150\n"
        "- default fail message: 什么？\n"
        "- default error message: 你发现事情不大对了，但是又说不上来。\n"
        "\n"
        "preload 列表（adm/etc/preload）共 14 个守护进程：securityd, virtuald, "
        "logind, rankd, commandd, chinesed, emoted, aliasd, fingerd, channeld, "
        "natured, weapond, dns_master, ftpd, http。\n"
        "\n"
        "未提取的 master.c 函数（辅助/后置）：compile_object（虚拟对象，层 D 范围）、"
        "update_file（内部辅助）、save_ed_setup/retrieve_ed_setup（ed 编辑器，后置）、"
        "make_path_absolute（ed 路径解析）、get_save_file_name（ed 保存，后置）、"
        "standard_trace（error_handler 内部辅助）、creator_file/domain_file/author_file"
        "（apply 委托，已在 simul_efun 提取）、valid_socket/valid_asm/valid_compile_to_c/"
        "valid_link/valid_save_binary（全部恒返回常量，后置）、object_name（调试用）、"
        "create（初始化）。\n"
        "\n"
        "simul_efun 未提取的模块（任务边界：不逐个提取 9 个模块）：atoi.c（数字转换）、"
        "chinese.c（中文处理，层 H CHINESE_D 范围）、gender.c（性别）、mkmapping.c（映射）、"
        "message.c（消息输出，层 B F_MESSAGE 范围）、assure_file（文件保障）、"
        "wizhood/wizardp/wiz_level（权限查询，层 H SECURITY_D 范围）。"
    ),
)
