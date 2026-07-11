"""层 B：对象基础规格（映射 ADR-0010 九层范围）。

本层覆盖 LPC feature/ 目录下 6 个基础对象特性模块：

- **F_DBASE** (``feature/dbase.c``)：对象数据存储，set/query/add/delete + temp 变体。
  路径访问语义（``"skill/axe"`` 分层 key）通过 F_TREEMAP 的 ``_set``/``_query``/``_delete``
  实现嵌套 mapping 读写。dbase 是所有对象的数据存储基础，combat/go/look 全依赖。
- **F_NAME** (``feature/name.c``)：对象命名与描述，set_name/id/name/short/long。
  short() 是 look 命令输出基础，含 apply 掩码、状态修饰（打坐/鬼气/断线等）。
- **F_MOVE** (``feature/move.c``)：对象移动，move/weight/encumbrance/remove。
  move() 涉及 weight/encumbrance 校验链，是 go/get/drop 的核心。
- **F_MESSAGE** (``feature/message.c``)：消息接收，receive_message/msg_buffer。
  含 subclass 路由（channel/outdoor/weather）与 block_msg 遮罩。
- **F_SAVE** (``feature/save.c``)：存档，save/restore。委托 efun save_object/restore_object。
- **F_CLEAN_UP** (``feature/clean_up.c``)：对象销毁回收。

不做（边界）：
- F_TREEMAP（dbase 底层实现细节，路径访问语义在 dbase 规格中描述但不提取 treemap 函数）
- F_CLONEABLE
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
    RandomSpec,
    SideEffect,
    SideEffectType,
)

# ──────────────────────── F_DBASE ────────────────────────

_set_spec = FunctionSpec(
    signature=FunctionSignature(
        name="set",
        params=[
            LPCParam(name="prop", lpc_type="string", description="属性键，可含 '/' 路径分隔符"),
            LPCParam(name="data", lpc_type="mixed", description="属性值，可为任意 LPC 类型（含 function）"),
        ],
        return_type="mixed",
        lpc_file="feature/dbase.c",
        line_range=(25, 33),
    ),
    preconditions=[
        Precondition(
            description="prop 必须是合法字符串",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="prop 对应的值被设为 data，返回 data",
            state_change="dbase[prop] = data（路径模式则嵌套 mapping 写入）",
            return_value="data（设置后的值）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="set 后 query(prop) 立即可读到刚写入的值",
            lpc_expr="query(prop, 1) == data",
            scope="class",
        ),
        Invariant(
            description="dbase 为 NULL 时自动初始化为空 mapping ([ ])",
            lpc_expr="if(!mapp(dbase)) dbase = ([])",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="若 dbase 未初始化则初始化为空 mapping",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="若 prop 含 '/'，通过 _set() 拆路径写入嵌套 mapping；否则直接 dbase[prop]=data",
        ),
    ],
    notes="路径访问：prop 含 '/' 时按 '/' 分割为路径部件，逐层进入嵌套 mapping。中间节点不存在时自动创建空 mapping。F_TREEMAP._set 是实现细节，不单独提取。",
)

_query_spec = FunctionSpec(
    signature=FunctionSignature(
        name="query",
        params=[
            LPCParam(name="prop", lpc_type="string", description="属性键，可含 '/' 路径分隔符"),
            LPCParam(name="raw", lpc_type="int", description="raw=1 返回原始值不调用 evaluate(); raw=0（默认）对 function 类型调用 evaluate()"),
        ],
        return_type="mixed",
        is_varargs=True,
        lpc_file="feature/dbase.c",
        line_range=(35, 52),
    ),
    preconditions=[
        Precondition(
            description="prop 必须是合法字符串",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 prop 对应的值；不存在时返回 0（undefined）",
            return_value="data 或 0（属性不存在时）",
            kind="observable",
        ),
        Postcondition(
            description="raw=0 时若 data 为 function 类型，调用 evaluate(data, this_object()) 返回执行结果",
            return_value="evaluate(data, this_object()) 或 data",
            kind="ensure",
        ),
        Postcondition(
            description="当前对象 dbase 中找不到 prop 时，若 default_ob 存在则委托 default_ob->query(prop, 1) 查找默认值",
            state_change="无状态变更（只读查询）",
            return_value="default_ob 的默认值（当前对象无此 key 时）",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="query 不会修改 dbase 状态（只读操作）",
            scope="function",
        ),
        Invariant(
            description="set 后 query 立即可读（读写一致性）",
            lpc_expr="query(prop, 1) == set(prop, data)",
            scope="class",
        ),
        Invariant(
            description="temp dbase 与常规 dbase 分离，互不干扰",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="无状态变更（只读）。但 raw=0 时可能触发 function 类型值的 evaluate 执行，其副作用取决于 function 体",
            target="无直接状态变更",
        ),
    ],
    notes="default_ob 机制：master copy 对象提供默认值。query 先查自身 dbase，未找到且 default_ob 存在时递归查 default_ob。default_ob 的查询使用 raw=1（不再递归 evaluate）。路径访问：prop 含 '/' 时用 _query() 拆路径逐层进入嵌套 mapping。",
)

_delete_spec = FunctionSpec(
    signature=FunctionSignature(
        name="delete",
        params=[
            LPCParam(name="prop", lpc_type="string", description="属性键，可含 '/' 路径分隔符"),
        ],
        return_type="int",
        lpc_file="feature/dbase.c",
        line_range=(54, 64),
    ),
    preconditions=[
        Precondition(
            description="prop 必须是合法字符串",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="删除 prop 对应的属性；返回 1 表示成功删除（简单 key 模式），路径模式返回 _delete 递归结果",
            return_value="1（简单 key 删除成功）或 _delete 返回值（路径模式）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="dbase 未初始化时 delete 返回 0 且不产生副作用",
            lpc_expr="if(!mapp(dbase)) return 0",
            scope="function",
        ),
        Invariant(
            description="delete 后 query(prop) 返回 0（或 default_ob 的默认值）",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="简单 key 模式调用 map_delete(dbase, prop)；路径模式递归调用 _delete 删除嵌套节点",
        ),
    ],
    notes=None,
)

_add_spec = FunctionSpec(
    signature=FunctionSignature(
        name="add",
        params=[
            LPCParam(name="prop", lpc_type="string", description="属性键，可含 '/' 路径分隔符"),
            LPCParam(name="data", lpc_type="mixed", description="增量值（int/string/mapping 等，需与原值类型兼容）"),
        ],
        return_type="mixed",
        lpc_file="feature/dbase.c",
        line_range=(66, 77),
    ),
    preconditions=[
        Precondition(
            description="若 prop 已有值且为 function 类型则报错",
            lpc_expr="if(functionp(old)) error(\"dbase: add() - called on a function type property.\")",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="prop 无旧值时等同于 set(prop, data)；有旧值时返回 old + data",
            return_value="set(prop, old + data) 的返回值",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="add 等价于 query 旧值 + set 新值，保持读写一致性",
            scope="function",
        ),
        Invariant(
            description="对 function 类型旧值调用 add 会抛错（不可对函数类型做加法）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="先 query(prop, 1) 取原始旧值，再 set(prop, old + data) 写回",
        ),
    ],
    notes="add 依赖 query(raw=1) 取旧值和 set 写新值，是组合操作。类型兼容性由 LPC + 运算符语义保证（int+int、string+string、mapping+mapping 等）。",
)

_set_temp_spec = FunctionSpec(
    signature=FunctionSignature(
        name="set_temp",
        params=[
            LPCParam(name="prop", lpc_type="string", description="临时属性键，可含 '/' 路径分隔符"),
            LPCParam(name="data", lpc_type="mixed", description="临时属性值"),
        ],
        return_type="mixed",
        lpc_file="feature/dbase.c",
        line_range=(88, 96),
    ),
    preconditions=[
        Precondition(
            description="prop 必须是合法字符串",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="tmp_dbase[prop] 被设为 data，返回 data",
            return_value="data",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="temp dbase 与常规 dbase 完全分离，set_temp 不影响 query 读取",
            scope="class",
        ),
        Invariant(
            description="tmp_dbase 为 NULL 时自动初始化为空 mapping",
            lpc_expr="if(!mapp(tmp_dbase)) tmp_dbase = ([])",
            scope="function",
        ),
        Invariant(
            description="set_temp 后 query_temp 立即可读",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="若 tmp_dbase 未初始化则初始化为空 mapping",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="路径模式通过 _set 写入嵌套 mapping；简单模式直接 tmp_dbase[prop]=data",
        ),
    ],
    notes="tmp_dbase 声明为 static（不参与 save_object 存档），这是 temp 变体的核心语义差异。",
)

_query_temp_spec = FunctionSpec(
    signature=FunctionSignature(
        name="query_temp",
        params=[
            LPCParam(name="prop", lpc_type="string", description="临时属性键，可含 '/' 路径分隔符"),
            LPCParam(name="raw", lpc_type="int", description="raw=1 返回原始值；raw=0（默认）对 function 类型调用 (*data)(this_object())"),
        ],
        return_type="mixed",
        is_varargs=True,
        lpc_file="feature/dbase.c",
        line_range=(98, 113),
    ),
    preconditions=[
        Precondition(
            description="prop 必须是合法字符串",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 tmp_dbase 中 prop 对应的值；不存在时返回 0",
            return_value="data 或 0",
            kind="observable",
        ),
        Postcondition(
            description="raw=0 且 data 为 function 类型时，调用 (*data)(this_object()) 返回结果",
            return_value="(*data)(this_object()) 或 data",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="query_temp 不修改 tmp_dbase 状态（只读操作）",
            scope="function",
        ),
        Invariant(
            description="temp dbase 不委托 default_ob 查找（与 query 行为不同）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="无状态变更（只读）。raw=0 时可能触发 function 类型值执行，副作用取决于 function 体",
        ),
    ],
    notes="与 query 的差异：(1) 不委托 default_ob；(2) function 求值方式不同（query 用 evaluate()，query_temp 用 (*data)(this_object()) 直接调用）。两者语义等价但实现路径不同。",
)

_delete_temp_spec = FunctionSpec(
    signature=FunctionSignature(
        name="delete_temp",
        params=[
            LPCParam(name="prop", lpc_type="string", description="临时属性键，可含 '/' 路径分隔符"),
        ],
        return_type="int",
        lpc_file="feature/dbase.c",
        line_range=(115, 125),
    ),
    preconditions=[
        Precondition(
            description="prop 必须是合法字符串",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="删除 tmp_dbase 中 prop 对应的属性",
            return_value="1（简单 key 删除成功）或 _delete 返回值（路径模式）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="tmp_dbase 未初始化时 delete_temp 返回 0 且不产生副作用",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="简单 key 模式 map_delete(tmp_dbase, prop)；路径模式递归 _delete",
        ),
    ],
    notes=None,
)

_add_temp_spec = FunctionSpec(
    signature=FunctionSignature(
        name="add_temp",
        params=[
            LPCParam(name="prop", lpc_type="string", description="临时属性键"),
            LPCParam(name="data", lpc_type="mixed", description="增量值"),
        ],
        return_type="mixed",
        lpc_file="feature/dbase.c",
        line_range=(127, 138),
    ),
    preconditions=[
        Precondition(
            description="若 prop 已有临时值且为 function 类型则报错",
            lpc_expr='if(functionp(old)) error("dbase: add_temp() - called on a function type property.")',
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="prop 无旧值时等同于 set_temp(prop, data)；有旧值时返回 old + data",
            return_value="set_temp(prop, old + data)",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="add_temp 等价于 query_temp(raw=1) + set_temp，保持读写一致性",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="先 query_temp(prop, 1) 取原始旧值，再 set_temp(prop, old + data) 写回",
        ),
    ],
    notes=None,
)

_set_default_object_spec = FunctionSpec(
    signature=FunctionSignature(
        name="set_default_object",
        params=[
            LPCParam(name="ob", lpc_type="mixed", description="默认对象（master copy），提供 dbase 默认值"),
        ],
        return_type="void",
        lpc_file="feature/dbase.c",
        line_range=(16, 23),
    ),
    preconditions=[
        Precondition(
            description="调用者需要有 euid（若无则自动 seteuid(getuid())）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="default_ob 设为 ob，ob 的 no_clean_up 计数 +1（防止默认对象被回收）",
            state_change="default_ob = ob; ob->add('no_clean_up', 1)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="default_ob 提供 query 的默认值回退路径",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="若当前对象无 euid 则 seteuid(getuid())",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="default_ob = ob",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="ob->add('no_clean_up', 1)，防止默认对象被 clean_up 回收",
        ),
    ],
    notes="源码中 euid 权限检查被注释掉，实际不检查 previous_object 的 euid 是否为 ROOT_UID。",
)

# ──────────────────────── F_NAME ────────────────────────

_set_name_spec = FunctionSpec(
    signature=FunctionSignature(
        name="set_name",
        params=[
            LPCParam(name="name", lpc_type="string", description="对象中文名"),
            LPCParam(name="id", lpc_type="string *", description="ID 列表（string 数组），id[0] 作为主 ID"),
        ],
        return_type="void",
        lpc_file="feature/name.c",
        line_range=(11, 16),
    ),
    preconditions=[
        Precondition(
            description="id 数组非空（至少含一个元素，id[0] 用作主 ID）",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="dbase['name'] 设为 name，dbase['id'] 设为 id[0]，my_id 设为 id 数组",
            state_change="set('name', name); set('id', id[0]); my_id = id",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="set_name 后 name() 和 id() 均可返回正确值",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="set('name', name) 写入 dbase",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="set('id', id[0]) 写入 dbase",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="my_id = id（设置局部 ID 列表变量）",
        ),
    ],
    notes="set_name 是对象初始化的标准入口，同时设置 dbase 中的 name/id 和局部 my_id。",
)

_id_spec = FunctionSpec(
    signature=FunctionSignature(
        name="id",
        params=[
            LPCParam(name="str", lpc_type="string", description="待匹配的 ID 字符串"),
        ],
        return_type="int",
        lpc_file="feature/name.c",
        line_range=(44, 65),
    ),
    preconditions=[
        Precondition(
            description="str 必须是合法字符串",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="若 apply/id 临时掩码存在且非空，仅匹配 apply/id 列表，不检查原始 my_id",
            return_value="1=匹配, 0=不匹配",
            kind="ensure",
        ),
        Postcondition(
            description="无 apply/id 掩码时，检查 str 是否在 my_id 数组中",
            return_value="1=str 在 my_id 中, 0=不在",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="当 this_player() 存在且对象对玩家不可见时，id() 返回 0",
            lpc_expr="if(this_player() && !this_player()->visible(this_object())) return 0",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="无状态变更（只读匹配）",
        ),
    ],
    notes='apply/id 机制允许对象"伪装"为其他 ID。当 apply/id 存在时，原始 my_id 被完全屏蔽，防止用 id 命令破解伪装。这是 LPC MUD 的安全相关设计。',
)

_name_spec = FunctionSpec(
    signature=FunctionSignature(
        name="name",
        params=[
            LPCParam(name="raw", lpc_type="int", description="raw=1 忽略 apply/name 掩码，返回真实名称"),
        ],
        return_type="string",
        is_varargs=True,
        lpc_file="feature/name.c",
        line_range=(78, 90),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="raw=0 且 apply/name 掩码存在时返回掩码值（最后一个元素）",
            return_value="mask[sizeof(mask)-1] 或 query('name') 或 file_name(this_object())",
            kind="ensure",
        ),
        Postcondition(
            description="无掩码时返回 dbase['name']；name 未设置时返回 file_name(this_object())",
            return_value="query('name') 或 file_name(this_object())",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="apply/name 掩码是栈式结构，name() 返回最后一个（最新）掩码",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="无状态变更（只读查询）",
        ),
    ],
    notes=None,
)

_short_spec = FunctionSpec(
    signature=FunctionSignature(
        name="short",
        params=[
            LPCParam(name="raw", lpc_type="int", description="raw=1 忽略所有 apply 掩码和状态修饰"),
        ],
        return_type="string",
        is_varargs=True,
        lpc_file="feature/name.c",
        line_range=(99, 147),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="raw=0 且 apply/short 掩码存在时返回掩码值（最后一个元素）",
            return_value="mask[sizeof(mask)-1]",
            kind="ensure",
        ),
        Postcondition(
            description="无掩码时构建 short 字符串：colorname 或 name + (id)；含 nickname 和 title 前缀",
            return_value="构建的 short 字符串",
            kind="ensure",
        ),
        Postcondition(
            description="raw=0 时附加状态修饰：打坐/吐纳/静坐文本、鬼气前缀、断线/输入/编辑/发呆标记、昏迷标记",
            return_value="附加状态修饰后的 short 字符串",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="非角色对象（!is_character()）不附加状态修饰，直接返回 short",
            scope="function",
        ),
        Invariant(
            description="raw=1 跳过所有 apply 掩码和状态修饰，仅返回基础 short",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="无状态变更（只读构建字符串）。但会调用 query/query_temp 查询多项属性",
        ),
    ],
    notes="short() 是 look 命令的核心输出基础。状态修饰顺序：打坐/吐纳/静坐 > apply/short 掩码 > nickname/title 前缀 > 鬼气/断线/输入/编辑/发呆/昏迷标记。pending/exercise, pending/respirate, pending/jingzuo 三种状态会完全替换 short 文本。",
)

_long_spec = FunctionSpec(
    signature=FunctionSignature(
        name="long",
        params=[
            LPCParam(name="raw", lpc_type="int", description="raw=1 忽略 apply/long 掩码"),
        ],
        return_type="string",
        is_varargs=True,
        lpc_file="feature/name.c",
        line_range=(149, 162),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="raw=0 且 apply/long 掩码存在时返回掩码值（最后一个元素）",
            return_value="mask[sizeof(mask)-1]",
            kind="ensure",
        ),
        Postcondition(
            description="无掩码且 dbase['long'] 未设置时，返回 short() + '。\\n' 作为默认描述",
            return_value="short(raw) + '。\\n' 或 query('long')",
            kind="ensure",
        ),
        Postcondition(
            description="若 extra_long() 返回非空字符串则追加到 long 描述末尾",
            return_value="str + extra_long()",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="long 至少返回 short 级别的描述信息（long 未设时回退到 short）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="无状态变更（只读构建字符串）",
        ),
    ],
    notes=None,
)

# ──────────────────────── F_MOVE ────────────────────────

_move_spec = FunctionSpec(
    signature=FunctionSignature(
        name="move",
        params=[
            LPCParam(name="dest", lpc_type="mixed", description="目标对象（object）或目标路径（string）"),
            LPCParam(name="silently", lpc_type="int", description="silently=1 时不触发自动 look/brief 显示"),
        ],
        return_type="int",
        is_varargs=True,
        lpc_file="feature/move.c",
        line_range=(47, 121),
    ),
    preconditions=[
        Precondition(
            description="若对象已装备（query('equipped')）则必须先成功 unequip()，否则失败返回 notify_fail",
            lpc_expr='if(query("equipped") && !this_object()->unequip()) return notify_fail(...)',
            kind="require",
        ),
        Precondition(
            description="dest 为 object 或 string；string 时通过 call_other 加载并 find_object 确认存在",
            kind="input_constraint",
        ),
        Precondition(
            description="目标对象的负重不超限：ob->query_encumbrance() + weight() <= ob->query_max_encumbrance()。若目标在当前对象的环境链中（如从背包中的袋子取物）则跳过负重检查",
            lpc_expr="!env && (int)ob->query_encumbrance() + weight() > (int)ob->query_max_encumbrance()",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="成功移动后返回 1；失败返回 notify_fail 结果（0）",
            return_value="1=成功, 0=失败",
            kind="ensure",
        ),
        Postcondition(
            description="旧环境减去对象重量，新环境加上对象重量",
            state_change="environment()->add_encumbrance(-weight()); ob->add_encumbrance(weight())",
            kind="effect",
        ),
        Postcondition(
            description="interactive 且 living 且 !silently 的对象移动后自动执行 look 或 brief 模式显示",
            state_change="command('look') 或 brief 列表输出",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="move_object 后 this_object 可能被 destruct 或被移到其他环境，需检查 this_object() 和 environment() 的一致性",
            scope="function",
        ),
        Invariant(
            description="move 后 environment() == dest（除非 move_object 触发了 destruct 或二次移动）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="若已装备则先调用 unequip() 卸下装备",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="若 dest 为 string，call_other(dest, '???') 加载对象，find_object 获取引用",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="负重检查：若目标在环境链中则跳过；否则比较 ob 的 encumbrance + weight() 与 max_encumbrance",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="旧环境 add_encumbrance(-weight()) 减重",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="新环境 ob->add_encumbrance(weight()) 加重",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="move_object(ob) 执行实际移动",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="interactive+living+!silently 时：brief 模式输出 short+inv 列表，否则 command('look') 触发自动 look",
        ),
    ],
    notes="move() 是 go/get/drop 等命令的核心。环境链检查（第 74-75 行）处理从嵌套容器取物不重复计重的场景。move_object 后的 destruct/二次移动检查是 LPC 的防御性编程（xuy 1997-08-10 添加）。",
)

_weight_spec = FunctionSpec(
    signature=FunctionSignature(
        name="weight",
        params=[],
        return_type="int",
        lpc_file="feature/move.c",
        line_range=(45, 45),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回对象自身重量 + 所含物品总重量（encumb）",
            return_value="weight + encumb",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="weight() = 基础重量 + 当前负重，是 move() 负重检查的基础",
            scope="class",
        ),
    ],
    side_effects=[],
    notes="nomask 函数，不可被 shadow 覆盖。注意区分 query_weight()（仅自身重量）与 weight()（含内容物总重量）。",
)

_set_weight_spec = FunctionSpec(
    signature=FunctionSignature(
        name="set_weight",
        params=[
            LPCParam(name="w", lpc_type="int", description="对象基础重量"),
        ],
        return_type="void",
        lpc_file="feature/move.c",
        line_range=(32, 40),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="weight 设为 w；若对象在环境中且 w != 旧 weight，环境的 encumbrance 相应调整",
            state_change="weight = w; environment()->add_encumbrance(w - old_weight)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="无环境时仅设 weight 不调整 encumbrance",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="若有环境且 w != weight，environment()->add_encumbrance(w - weight) 调整环境负重",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="weight = w",
        ),
    ],
    notes="nomask 函数。",
)

_add_encumbrance_spec = FunctionSpec(
    signature=FunctionSignature(
        name="add_encumbrance",
        params=[
            LPCParam(name="w", lpc_type="int", description="负重增量（正数加重，负数减重）"),
        ],
        return_type="void",
        lpc_file="feature/move.c",
        line_range=(16, 23),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="encumb += w；若 encumb < 0 记录 move.bug 日志；若 encumb > max_encumb 触发 over_encumbrance()",
            state_change="encumb += w",
            kind="effect",
        ),
        Postcondition(
            description="若对象有环境，环境的 encumbrance 也级联调整 w",
            state_change="environment()->add_encumbrance(w)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="encumbrance 级联传播：对象负重变化会传递到父环境",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="encumb += w",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="若 encumb < 0，log_file('move.bug', ...) 记录负重下溢",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="若 encumb > max_encumb，调用 over_encumbrance()（对 interactive 对象输出 '你的负荷过重了！'）",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="若 environment() 存在，environment()->add_encumbrance(w) 级联调整",
        ),
    ],
    notes="nomask 函数。负重级联是 move 系统的核心不变量：移动对象时，源环境和目标环境的 encumbrance 都要正确更新。",
)

_remove_spec = FunctionSpec(
    signature=FunctionSignature(
        name="remove",
        params=[
            LPCParam(name="euid", lpc_type="string", description="调用者的 euid，用于权限检查"),
        ],
        return_type="void",
        lpc_file="feature/move.c",
        line_range=(123, 146),
    ),
    preconditions=[
        Precondition(
            description="只能由 destruct() simul efun 调用（检查 previous_object 是 SIMUL_EFUN_OB）",
            lpc_expr="base_name(previous_object()) == SIMUL_EFUN_OB",
            kind="guard",
        ),
        Precondition(
            description="销毁 user 对象需要 ROOT_UID 权限",
            lpc_expr='userp(this_object()) && euid != ROOT_UID => error',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="若对象已装备则尝试 unequip()，失败则记录 destruct 日志",
            state_change="unequip() 或 log_file('destruct', ...)",
            kind="effect",
        ),
        Postcondition(
            description="若有环境则从环境减去自身重量",
            state_change="environment()->add_encumbrance(-weight)",
            kind="effect",
        ),
        Postcondition(
            description="若有 default_ob 则 default_ob 的 no_clean_up 计数 -1",
            state_change="default_ob->add('no_clean_up', -1)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="remove 是 destruct 的回调，不是直接销毁接口",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="权限检查：非 SIMUL_EFUN_OB 调用则 error",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="user 对象权限检查：euid != ROOT_UID 则 error 并 log_file('destruct')",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="若 equipped 则 unequip()，失败则 log_file('destruct') 记录",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="若 environment() 存在则 environment()->add_encumbrance(-weight) 减重",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="若 default_ob 存在则 default_ob->add('no_clean_up', -1) 解除引用计数",
        ),
    ],
    notes="remove() 的权限模型：只有 destruct() simul efun 可以调用，防止玩家直接销毁对象。user 对象的销毁需要 ROOT_UID。",
)

# ──────────────────────── F_MESSAGE ────────────────────────

_receive_message_spec = FunctionSpec(
    signature=FunctionSignature(
        name="receive_message",
        params=[
            LPCParam(name="msgclass", lpc_type="string", description="消息类别，可含子类前缀（如 'channel:gossip'、'outdoor'、'weather'）"),
            LPCParam(name="msg", lpc_type="string", description="消息内容"),
        ],
        return_type="void",
        lpc_file="feature/message.c",
        line_range=(11, 54),
    ),
    preconditions=[
        Precondition(
            description="msgclass 和 msg 为合法字符串",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="非 interactive 对象委托 relay_message(msgclass, msg) 处理",
            return_value="void（relay_message 返回）",
            kind="effect",
        ),
        Postcondition(
            description="channel 子类：检查 query('channels') 是否包含该频道，不在则丢弃",
            kind="observable",
        ),
        Postcondition(
            description="outdoor 子类：检查环境是否 outdoors，非户外则丢弃",
            kind="observable",
        ),
        Postcondition(
            description="weather 子类：检查环境是否有 weather 属性，无则丢弃",
            kind="observable",
        ),
        Postcondition(
            description="block_msg/all 或 block_msg/<msgclass> 临时遮罩存在时丢弃消息",
            kind="observable",
        ),
        Postcondition(
            description="in_input 或 in_edit 状态下消息存入 msg_buffer（上限 MAX_MSG_BUFFER=500），否则直接 receive(msg)",
            state_change="msg_buffer += ({msg}) 或 receive(msg)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="msg_buffer 上限 MAX_MSG_BUFFER=500，超出时丢弃新消息",
            scope="class",
        ),
        Invariant(
            description="盲人状态（blind condition）有概率丢失消息：random(blind*2) > 0 时丢弃",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="非 interactive 对象调用 relay_message(msgclass, msg) 委托处理",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="subclass 路由：channel/outdoor/weather 子类检查，不匹配则 return",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="block_msg 遮罩检查：query_temp('block_msg/all') 或 query_temp('block_msg/' + msgclass)",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="盲人判定：random(blind*2) > 0 时丢弃消息",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.EXTERNAL,
            description="BIG5 语言转换：query('language')=='BIG5' 时调用 languaged 转码",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="in_input/in_edit 时存入 msg_buffer（上限 500）；否则 receive(msg) 直接输出",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(this_object()->query_condition('blind')*2)",
            probability_model="blind*2 > 0 时每次消息有 blind*2/(2^31) 的概率被丢弃（random 返回 0 时通过）",
            semantic="盲人消息丢失判定",
            seed_inputs=["blind condition 等级"],
            determinism_note="combat-only 确定性范围外。盲人条件下消息接收有随机丢失，但此 random 不影响战斗确定性。",
        ),
    ],
    notes="receive_message 是所有消息输出的统一入口。subclass 路由（channel/outdoor/weather）是 LPC MUD 的消息过滤机制。BIG5 转码是台湾 Big5 繁体支持。blind condition 的 random 调用是本层唯一的随机性来源。",
)

_write_prompt_spec = FunctionSpec(
    signature=FunctionSignature(
        name="write_prompt",
        params=[],
        return_type="void",
        lpc_file="feature/message.c",
        line_range=(56, 65),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="若 msg_buffer 非空，先输出 '[输入时暂存讯息]' 标题再逐条输出缓冲消息，然后清空 msg_buffer",
            state_change="msg_buffer = ({})",
            kind="effect",
        ),
        Postcondition(
            description="最后输出 '> ' 提示符",
            kind="observable",
        ),
    ],
    invariants=[
        Invariant(
            description="write_prompt 清空 msg_buffer 后缓冲为空",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="若 msg_buffer 非空，receive(BOLD '[输入时暂存讯息]\\n' NOR) 输出标题",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="逐条 receive(msg_buffer[i]) 输出暂存消息",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="msg_buffer = ({}) 清空缓冲",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="write('> ') 输出提示符",
        ),
    ],
    notes="write_prompt 在 in_input/in_edit 结束后被调用，将 receive_message 期间暂存的消息刷出。",
)

# ──────────────────────── F_SAVE ────────────────────────

_save_spec = FunctionSpec(
    signature=FunctionSignature(
        name="save",
        params=[],
        return_type="int",
        lpc_file="feature/save.c",
        line_range=(4, 13),
    ),
    preconditions=[
        Precondition(
            description="对象必须实现 query_save_file() 且返回有效文件路径",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="成功时调用 save_object(file) 持久化，返回 save_object 结果",
            return_value="save_object(file) 的返回值（1=成功, 0=失败）",
            kind="ensure",
        ),
        Postcondition(
            description="assure_file 确保存档文件目录存在",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="query_save_file() 返回非 string 时 save 返回 0（不保存）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.PERSISTENCE,
            description="assure_file(file + __SAVE_EXTENSION__) 确保目录存在",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.PERSISTENCE,
            description="save_object(file) 执行实际持久化",
        ),
    ],
    notes="F_SAVE 只提供 save/restore 框架，具体存档路径由对象的 query_save_file() 决定。save_object 是 FluffOS efun，写入 dbase 中所有非 static 变量。tmp_dbase（static mapping）不被存档。",
)

_restore_spec = FunctionSpec(
    signature=FunctionSignature(
        name="restore",
        params=[],
        return_type="int",
        lpc_file="feature/save.c",
        line_range=(15, 22),
    ),
    preconditions=[
        Precondition(
            description="对象必须实现 query_save_file() 且返回有效文件路径",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="成功时调用 restore_object(file) 恢复数据，返回 restore_object 结果",
            return_value="restore_object(file) 的返回值（1=成功, 0=失败/无存档）",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="query_save_file() 返回非 string 时 restore 返回 0",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.PERSISTENCE,
            description="restore_object(file) 执行实际恢复",
        ),
    ],
    notes="restore_object 恢复 dbase 中非 static 变量。tmp_dbase 不被恢复（static mapping）。",
)

# ──────────────────────── F_CLEAN_UP ────────────────────────

_clean_up_spec = FunctionSpec(
    signature=FunctionSignature(
        name="clean_up",
        params=[],
        return_type="int",
        lpc_file="feature/clean_up.c",
        line_range=(5, 26),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回 1 表示不清理（保留对象）；返回 0 表示已执行 destruct",
            return_value="1=保留, 0=已销毁",
            kind="ensure",
        ),
        Postcondition(
            description="非 clone 对象且 query('no_clean_up') 为真时返回 1（不清理）",
            kind="observable",
        ),
        Postcondition(
            description="interactive 对象返回 1（不清理在线玩家/对象）",
            kind="observable",
        ),
        Postcondition(
            description="有环境的对象返回 1（由环境负责清理）",
            kind="observable",
        ),
        Postcondition(
            description="deep_inventory 中含 interactive 对象时返回 1（不清理含在线玩家的容器）",
            kind="observable",
        ),
        Postcondition(
            description="以上条件均不满足时调用 destruct(this_object()) 销毁自身，返回 0",
            state_change="destruct(this_object())",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="clean_up 是 driver 周期性调用的回收机制，对象可通过 set('no_clean_up', 1) 禁止回收",
            scope="system",
        ),
        Invariant(
            description="有环境的对象不自行清理，由顶层环境递归触发",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="条件检查链：no_clean_up / interactive / environment / deep_inventory interactive",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="条件全不满足时 destruct(this_object()) 销毁对象",
        ),
    ],
    notes="clean_up 由 driver 定期调用（heart_beat 机制之外的对象回收）。no_clean_up 计数器由 set_default_object 增加、remove 减少。",
)


# ──────────────────────── 层规格汇总 ────────────────────────

LAYER_SPEC = LayerSpec(
    layer_id="B",
    layer_name="对象基础",
    lpc_files=[
        "feature/dbase.c",
        "feature/name.c",
        "feature/move.c",
        "feature/message.c",
        "feature/save.c",
        "feature/clean_up.c",
    ],
    function_specs=[
        # F_DBASE
        _set_spec,
        _query_spec,
        _delete_spec,
        _add_spec,
        _set_temp_spec,
        _query_temp_spec,
        _delete_temp_spec,
        _add_temp_spec,
        _set_default_object_spec,
        # F_NAME
        _set_name_spec,
        _id_spec,
        _name_spec,
        _short_spec,
        _long_spec,
        # F_MOVE
        _move_spec,
        _weight_spec,
        _set_weight_spec,
        _add_encumbrance_spec,
        _remove_spec,
        # F_MESSAGE
        _receive_message_spec,
        _write_prompt_spec,
        # F_SAVE
        _save_spec,
        _restore_spec,
        # F_CLEAN_UP
        _clean_up_spec,
    ],
    cross_layer_refs=[
        "evaluate() — F_DBASE query 对 function 类型值的求值（driver efun，层 A）",
        "move_object() — F_MOVE move() 调用的 driver efun（层 A）",
        "call_other() — F_MOVE move() 加载目标对象（层 A）",
        "find_object() — F_MOVE move() 查找已加载对象（层 A）",
        "destruct() — F_MOVE remove() / F_CLEAN_UP clean_up() 的销毁 efun（层 A）",
        "save_object() / restore_object() — F_SAVE 的 efun（层 A）",
        "notify_fail() — F_MOVE move() 失败反馈（层 A）",
        "command() — F_MOVE move() 触发自动 look（层 D 命令派发）",
        "tell_object() — F_MOVE over_encumbrance() 输出（层 G 通信）",
        "receive() — F_MESSAGE 直接输出到底层连接（层 A driver efun）",
        "query_condition() — F_MESSAGE 盲人状态查询（层 F 状态系统）",
        "visible() — F_NAME id() 可见性检查（层 B 对象基础，跨对象调用）",
        "is_character() / is_ghost() / living() / interactive() — F_NAME/F_MOVE 角色状态查询（层 A driver efun / 层 F）",
        "query_save_file() — F_SAVE 存档路径（由具体对象实现，层 C+）",
        "all_inventory() / deep_inventory() — F_MOVE/F_CLEAN_UP 库存查询（层 A driver efun）",
        "environment() — F_MOVE/F_NAME/F_MESSAGE 环境查询（层 A driver efun）",
        "log_file() — F_MOVE/F_CLEAN_UP 日志输出（层 G 通信）",
    ],
    notes=(
        "层 B 是所有对象的数据存储和生命周期基础。dbase 的 set/query 是 combat/go/look 全依赖的核心。"
        "路径访问语义（'skill/axe' 分层 key）通过 F_TREEMAP 的 _set/_query/_delete 实现嵌套 mapping 读写，"
        "treemap 函数不单独提取（实现细节）。"
        "temp 变体与常规 dbase 分离（tmp_dbase 为 static，不存档）。"
        "move() 的负重级联是系统不变量：对象移动时源/目标环境的 encumbrance 都要正确更新。"
        "receive_message 中的 blind condition random 是本层唯一随机性，不影响战斗确定性。"
    ),
)
