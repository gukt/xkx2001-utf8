"""层 H-RACE：race daemon 种族初始化 -- LPC 规格提取（ADR-0030 开放问题 1）。

覆盖范围：
- ``adm/daemons/race/human.c`` -- ``create`` / ``setup_human`` / ``query_action`` /
  ``set_default_object`` 的 greenfield 对应。
  LPC 原版把"通用人类种族逻辑"与"13 门派加成"混在一个 429 行函数里，
  本层按 ADR-0030 决策 1 拆为多个独立函数规格：

  1. ``create`` -- race daemon 自身静态属性初始化（unit/gender/can_speak/
     attitude/limbs/dead/unconscious/revive 消息模板）。
  2. ``set_default_actions`` -- 将 ``query_action`` 回调绑定到
     ``entity.default_actions``（human.c:59）。
  3. ``query_action`` -- 返回 ``HUMAN_COMBAT_ACTIONS`` 中随机一个
     combat action 模板（含 action 文本与 damage_type）。
  4. ``set_default_object`` -- 标记 entity 的默认原型文件路径（human.c:421）。
  5. ``setup_race`` -- 通用种族基础（引擎层，主题无关）：
     属性随机 ``10+random(21)``、年龄分层 ``max_jing``/``max_qi``/``max_jingli``
     公式（age<=14/<=30/>30 三段 + 70 岁衰减）、``max_potential`` 公式、
     ``eff_jingli`` 与 ``max_neili`` 追加加成、force 技能上限钳位、
     ``base_weight`` + str 加成。不硬编码任何门派名 / 技能名。
  6. ``apply_family_bonuses`` -- 门派加成（题材包 CPK 资产，声明式载体）：
     按 ``family_name`` 过滤匹配的 FamilyBonus 列表，条件检查（技能等级 > 阈值 +
     额外条件），公式计算（读 bonus 参数，年龄调整统一逻辑）。不认识任何具体
     门派名，只做 ``family_name == bonus.family_name`` 字符串匹配。

核心契约要点（ADR-0030 决策 1）：
1. **setup_race 纯通用**：年龄公式参数化（``age_threshold_young=14`` /
   ``age_threshold_prime=30`` / ``age_senior=70``），不硬编码武侠字面量。
   公式参数从 RaceProfile 读取，题材包注入人类 RaceProfile。
2. **apply_family_bonuses 标准载体**：FamilyBonus 声明式载体（family_name /
   target / condition_skill / condition_threshold / age_adjusted / bonus_skill /
   divisor / extra_condition_* / extra_divisor）。13 门派全量公式规格后置 M3
   （ADR-0030 开放问题 2），本规格只定义标准载体契约。
3. **三层资源不变量**：``0 <= qi <= eff_qi <= max_qi``、``0 <= jing <= eff_jing
   <= max_jing``。setup_race 设置 max_*，jing/qi/eff_* 由层 H CHAR_D setup_char
   后续钳位（见 chard.c:64-69）。
4. **加成单调非递减**：apply_family_bonuses 的 max_jing/max_qi 只增不减
   （FamilyBonus 列表按顺序累加，每个 bonus 计算结果 >= 0 才应用）。
5. **主题无关性**（ADR-0030 决策 4）：setup_race + apply_family_bonuses 走题材
   声明数据，不 fallback 到武侠默认。测试用非武侠 RaceProfile + FamilyBonus
   （大航海"海盗帮派"航行加成 max_qi、书院"学派"学问加成 max_jing）。

不做（边界，ADR-0030 开放问题 1 裁决）：
- 13 门派全量公式穷尽规格提取（后置 M3，ADR-0030 开放问题 2）
- 丐帮 death_times / 明教双技能等特殊加成（2.7 只定义标准载体，特殊加成作为
  "扩展点"标注，覆盖不了的后置 M3）
- 非人类种族 RaceProfile（MONSTER/BEAST/STOCK 等，后置 M3，ADR-0030 开放问题 3）
- RaceProfile / FamilyBonus 数据类实现（本文件只提取函数级规格契约，数据类
  载体在 runtime/race.py + runtime/family.py 实现，属 2.7 后续任务）
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

# ---------------------------------------------------------------------------
# 人类基础 combat_action 模板（LPC human.c:14-30）
# ---------------------------------------------------------------------------

HUMAN_COMBAT_ACTIONS = [
    {"action": "$N挥拳攻击$n的$l", "damage_type": "瘀伤"},
    {"action": "$N往$n的$l一抓", "damage_type": "擦伤"},
    {"action": "$N往$n的$l狠狠地踢了一脚", "damage_type": "瘀伤"},
    {"action": "$N提起拳头往$n的$l捶去", "damage_type": "内伤"},
    {"action": "$N对准$n的$l用力挥出一拳", "damage_type": "瘀伤"},
]


# ---------------------------------------------------------------------------
# create() 函数规格（race daemon 自身初始化）
#
# LPC 对照：adm/daemons/race/human.c 行 32-49。
# ---------------------------------------------------------------------------

_create = FunctionSpec(
    signature=FunctionSignature(
        name="create",
        params=[],
        return_type="void",
        lpc_file="adm/daemons/race/human.c",
        line_range=(32, 49),
    ),
    postconditions=[
        Postcondition(
            description="设置 unit 为 '位'（human.c:35）",
            state_change='set("unit", "位")',
            kind="effect",
        ),
        Postcondition(
            description="设置 gender 为 '男性'（human.c:36）",
            state_change='set("gender", "男性")',
            kind="effect",
        ),
        Postcondition(
            description="设置 can_speak 为 1（human.c:37）",
            state_change='set("can_speak", 1)',
            kind="effect",
        ),
        Postcondition(
            description="设置 attitude 为 'peaceful'（human.c:38）",
            state_change='set("attitude", "peaceful")',
            kind="effect",
        ),
        Postcondition(
            description="设置 limbs 列表，含头顶/颈部/胸口等 21 个部位（human.c:40-44）",
            state_change='set("limbs", ({...}))',
            kind="effect",
        ),
        Postcondition(
            description="设置 dead_message 模板（human.c:46）",
            state_change='set("dead_message", "\\n$N倒在地上...\\n\\n")',
            kind="effect",
        ),
        Postcondition(
            description="设置 unconcious_message 模板（human.c:47）",
            state_change='set("unconcious_message", "\\n$N脚下一个不稳...\\n\\n")',
            kind="effect",
        ),
        Postcondition(
            description="设置 revive_message 模板（human.c:48）",
            state_change='set("revive_message", "\\n$N慢慢睁开眼睛...\\n\\n")',
            kind="effect",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 unit / gender / can_speak / attitude",
            lpc_call=(
                'set("unit", "位"); set("gender", "男性"); '
                'set("can_speak", 1); set("attitude", "peaceful")'
            ),
            target="race daemon self",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 limbs 列表（21 个部位）",
            lpc_call='set("limbs", ({...}))',
            target="race daemon self",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 dead_message / unconcious_message / revive_message 模板",
            lpc_call=(
                'set("dead_message", ...); set("unconcious_message", ...); '
                'set("revive_message", ...)'
            ),
            target="race daemon self",
        ),
    ],
    invariants=[
        Invariant(
            description="create 设置后 limbs 列表固定为 21 个部位，且 unit/gender/"
            "can_speak/attitude 均有值（human.c:35-44）",
            lpc_expr=(
                'sizeof(limbs) == 21 && unit == "位" && gender == "男性" '
                '&& can_speak == 1 && attitude == "peaceful"'
            ),
            scope="function",
        ),
    ],
    notes="human race daemon 启动时初始化自身静态属性，供 setup_human 与 entity 模板引用。",
)


# ---------------------------------------------------------------------------
# set_default_actions 函数规格（human.c:59）
#
# LPC 对照：adm/daemons/race/human.c setup_human() 内
# ob->set("default_actions", (: call_other, __FILE__, "query_action" :))。
# ---------------------------------------------------------------------------

_set_default_actions = FunctionSpec(
    signature=FunctionSignature(
        name="set_default_actions",
        params=[
            LPCParam(
                name="entity",
                lpc_type="object",
                description="待设置默认动作的角色实体",
            ),
        ],
        return_type="void",
        lpc_file="adm/daemons/race/human.c",
        line_range=(59, 59),
    ),
    preconditions=[
        Precondition(
            description="entity 已绑定且可写 default_actions 属性",
            lpc_expr="objectp(entity)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="entity.default_actions 设置为调用 query_action 的回调（human.c:59）",
            state_change='ob->set("default_actions", (: call_other, __FILE__, "query_action" :))',
            kind="effect",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="entity.default_actions 绑定 query_action 回调",
            lpc_call=(
                'ob->set("default_actions", '
                '(: call_other, __FILE__, "query_action" :))'
            ),
            target="entity.default_actions",
        ),
    ],
    invariants=[
        Invariant(
            description="default_actions 回调固定指向 query_action（human.c:59）",
            lpc_expr='default_actions == (: call_other, __FILE__, "query_action" :)',
            scope="function",
        ),
    ],
    notes="setup_human 内部调用，无门派默认动作时回退到 human 基础 combat_action。",
)


# ---------------------------------------------------------------------------
# query_action 函数规格（human.c:425-428）
# ---------------------------------------------------------------------------

_query_action = FunctionSpec(
    signature=FunctionSignature(
        name="query_action",
        params=[],
        return_type="mapping",
        lpc_file="adm/daemons/race/human.c",
        line_range=(425, 428),
    ),
    preconditions=[
        Precondition(
            description="combat_action 映射已初始化（create() 中设置）",
            lpc_expr="sizeof(combat_action) > 0",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description=(
                "返回 combat_action 中随机一个 action 条目，"
                "含 action 文本与 damage_type"
            ),
            return_value="combat_action[random(sizeof(combat_action))]",
            kind="effect",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="combat_action[random(sizeof(combat_action))]",
            probability_model="在 HUMAN_COMBAT_ACTIONS 5 个条目中均匀选择",
            semantic="人类基础无武器 combat action 随机选择",
            seed_inputs=["HUMAN_COMBAT_ACTIONS length"],
            determinism_note="非 combat 确定性范围，初始化/回退动作选择允许真随机",
        ),
    ],
    invariants=[
        Invariant(
            description="返回的 combat action 条目必含 action 与 damage_type 两个键"
            "（human.c:14-30）",
            lpc_expr='result["action"] && result["damage_type"]',
            scope="function",
        ),
    ],
    notes="返回 HUMAN_COMBAT_ACTIONS 中随机一项，供 entity.default_actions 回调使用。",
)


# ---------------------------------------------------------------------------
# set_default_object 函数规格（human.c:421）
# ---------------------------------------------------------------------------

_set_default_object = FunctionSpec(
    signature=FunctionSignature(
        name="set_default_object",
        params=[
            LPCParam(
                name="entity",
                lpc_type="object",
                description="待设置默认对象的角色实体",
            ),
            LPCParam(
                name="file_path",
                lpc_type="string",
                description="默认对象文件路径（LPC 中为 __FILE__）",
            ),
        ],
        return_type="void",
        lpc_file="adm/daemons/race/human.c",
        line_range=(421, 421),
    ),
    preconditions=[
        Precondition(
            description="entity 已创建且可写 default_object 属性",
            lpc_expr="objectp(entity)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="entity.default_object 设置为 file_path（human.c:421）",
            state_change="ob->set_default_object(__FILE__)",
            kind="effect",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="entity.default_object 设为 file_path",
            lpc_call="ob->set_default_object(__FILE__)",
            target="entity.default_object",
        ),
    ],
    invariants=[
        Invariant(
            description="default_object 设置后等于传入的 file_path（human.c:421）",
            lpc_expr="default_object == file_path",
            scope="function",
        ),
    ],
    notes="setup_human 末尾调用，标记 entity 的默认原型文件路径。",
)


# ---------------------------------------------------------------------------
# setup_race 函数规格（通用种族基础，引擎层）
#
# LPC 对照：adm/daemons/race/human.c setup_human() 的通用部分（行 51-70 + 73-83
# + 86-89 + 212-213 + 222-224 + 387-414 + 416-422）。
# greenfield setup_race 只含通用种族基础，门派加成由 apply_family_bonuses 分离
# （ADR-0030 决策 1）。
# ---------------------------------------------------------------------------

_setup_race = FunctionSpec(
    signature=FunctionSignature(
        name="setup_race",
        params=[
            LPCParam(
                name="entity",
                lpc_type="object",
                description="待初始化的角色实体（greenfield 对应 LPC ob）",
            ),
            LPCParam(
                name="profile",
                lpc_type="RaceProfile",
                description="种族配置数据声明（limbs/combat_actions/base_weight/"
                "attr_min/attr_max 等，题材包注入）",
            ),
        ],
        return_type="void",
        lpc_file="adm/daemons/race/human.c",
        line_range=(51, 423),
    ),
    preconditions=[
        Precondition(
            description="entity 已绑定 Attributes 组件（str/con/dex/int/per/kar "
            "可读写）",
            lpc_expr="entity has Attributes component",
            kind="require",
        ),
        Precondition(
            description="RaceProfile 已注入（profile 非空，含 attr_min/attr_max/"
            "base_weight/str_weight_factor 等字段）",
            lpc_expr="profile is not None and profile.attr_min/max defined",
            kind="require",
        ),
        Precondition(
            description="entity.age 可读（未设置时 setup_race 默认 14，对照 "
            'human.c:61 if(undefinedp(my["age"])) my["age"] = 14）',
            lpc_expr="entity.age readable or undefined (default 14)",
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="age 未定义时初始化为 14（人类初始年龄）",
            state_change='if(undefinedp(my["age"])) my["age"] = 14',
            kind="effect",
        ),
        Postcondition(
            description="str/con/dex/int/per/kar 未定义时按 profile.attr_min + "
            "random(profile.attr_max - profile.attr_min + 1) 随机初始化"
            "（human.c:62-67，10+random(21) -> [10, 30]）",
            state_change='if(undefinedp(my["str"])) my["str"] = attr_min + random(attr_max-attr_min+1) (con/dex/int/per/kar 同理)',
            kind="effect",
        ),
        Postcondition(
            description="max_jing 按年龄公式初始化：age<=14 时 =100；"
            "age<=30 时 =100+(age-14)*(int+con)/2；age>30 时 =(int+con)*8+100"
            "（human.c:75-78）",
            state_change='if(age<=14) max_jing=100; elif(age<=30) max_jing=100+(age-14)*(int+con)/2; else max_jing=(int+con)*8+100',
            kind="effect",
        ),
        Postcondition(
            description="max_qi 按年龄公式初始化：age<=14 时 =100；"
            "age<=30 时 =100+(age-14)*(con+str)/2；age>30 时 =100+(con+str)*8"
            "（human.c:80-83）",
            state_change='if(age<=14) max_qi=100; elif(age<=30) max_qi=100+(age-14)*(con+str)/2; else max_qi=100+(con+str)*8',
            kind="effect",
        ),
        Postcondition(
            description="max_jingli 按年龄公式初始化：age<=14 时 =100；"
            "age<=con 时 =100+(age-14)*(str+dex)；否则 =100+(str+dex)*(con-14)"
            "（human.c:389-392）",
            state_change='if(age<=14) max_jingli=100; elif(age<=con) max_jingli=100+(age-14)*(str+dex); else max_jingli=100+(str+dex)*(con-14)',
            kind="effect",
        ),
        Postcondition(
            description="70 岁衰减：age>70 时 max_jing 减 (age-70)*(int+con)/7"
            "（human.c:87-89），max_qi 减 (age-70)*(con+str)/7（human.c:222-224），"
            "max_jingli 减 (age-70)*con/5（human.c:395-396）",
            state_change='if(age>70) { max_jing-=(age-70)*(int+con)/7; max_qi-=(age-70)*(con+str)/7; max_jingli-=(age-70)*con/5; }',
            kind="effect",
        ),
        Postcondition(
            description="max_potential 公式：100+sqrt(combat_exp)/10+(max_jing-100)/30"
            "（human.c:69-70），玩家或未定义时计算",
            state_change='if(userp || undefinedp(max_potential)) max_potential=100+sqrt(combat_exp)/10+(max_jing-100)/30',
            kind="effect",
        ),
        Postcondition(
            description="max_encumbrance 未设置时按 str 公式计算（层 H CHAR_D "
            "setup_char 后续填充，setup_race 不直接设置，对照 chard.c:109-111）",
            state_change="max_encumbrance 由 CHAR_D setup_char 填充（str*5000+...）",
            kind="effect",
        ),
        Postcondition(
            description="base_weight + str 加成：weight 未设置时 = profile.base_weight"
            "+(str-10)*profile.str_weight_factor（human.c:422，BASE_WEIGHT=40000 + "
            "(str-10)*2000）",
            state_change='if(!query_weight()) set_weight(profile.base_weight + (str-10)*profile.str_weight_factor)',
            kind="effect",
        ),
        Postcondition(
            description="NPC max_jing/max_qi < 1 时钳位到 100（human.c:213,383，"
            "防止 NPC 属性异常）",
            state_change='if(!userp && max_jing<1) max_jing=100; if(!userp && max_qi<1) max_qi=100',
            kind="effect",
        ),
        Postcondition(
            description="eff_jingli 加成 max_jing：eff_jingli>0 时 max_jing += "
            "eff_jingli/4（human.c:212）",
            state_change='if(eff_jingli > 0) max_jing += eff_jingli / 4',
            kind="effect",
        ),
        Postcondition(
            description="max_neili 加成 max_qi：max_neili>0 时 max_qi += "
            "max_neili/4（human.c:382）",
            state_change='if(max_neili > 0) max_qi += max_neili / 4',
            kind="effect",
        ),
        Postcondition(
            description="eff_jingli 加成 max_jingli：eff_jingli>0 时 max_jingli += "
            "eff_jingli（human.c:404）",
            state_change='if(eff_jingli > 0) max_jingli += eff_jingli',
            kind="effect",
        ),
        Postcondition(
            description="eff_jingli 受 force 技能上限钳位：当有效 force 高于基础 "
            "force 且 eff_jingli > force*con/2 时，eff_jingli 与 max_jingli 均钳位到 "
            "force*con/2（human.c:405-409）",
            state_change=(
                'if(query_skill("force") > query_skill("force", 1) && '
                'eff_jingli > query_skill("force") * con / 2) { '
                'eff_jingli = query_skill("force") * con / 2; '
                'max_jingli = query_skill("force") * con / 2; }'
            ),
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="三层资源层次：0 <= qi <= eff_qi <= max_qi（setup_race 设置 "
            "max_qi，qi/eff_qi 由层 H CHAR_D setup_char 后续钳位）",
            lpc_expr="0 <= qi <= eff_qi <= max_qi",
            scope="class",
        ),
        Invariant(
            description="三层资源层次：0 <= jing <= eff_jing <= max_jing（setup_race "
            "设置 max_jing，jing/eff_jing 由层 H CHAR_D setup_char 后续钳位）",
            lpc_expr="0 <= jing <= eff_jing <= max_jing",
            scope="class",
        ),
        Invariant(
            description="年龄分层阈值参数化：age_threshold_young=14 / "
            "age_threshold_prime=30 / age_senior=70，公式不硬编码武侠字面量"
            "（ADR-0030 决策 1 主题无关性）",
            lpc_expr="age_threshold_young=14; age_threshold_prime=30; age_senior=70",
            scope="function",
        ),
        Invariant(
            description="属性随机范围参数化：attr_min/attr_max 从 RaceProfile 读取，"
            "不硬编码 10/30（human.c 10+random(21) 的参数化提取）",
            lpc_expr="str = attr_min + random(attr_max - attr_min + 1)",
            scope="function",
        ),
        Invariant(
            description="setup_race 不硬编码任何门派名 / 技能名（ADR-0030 决策 4 "
            "主题无关性硬门禁，门派加成由 apply_family_bonuses 分离）",
            lpc_expr='setup_race source contains no family_name/skill literals',
            scope="system",
        ),
        Invariant(
            description="max_jingli/max_neili 未定义时下限 1（human.c:416-419，"
            "防止后续计算除零或异常）",
            lpc_expr='if(undefinedp(max_jingli)) max_jingli=1; if(undefinedp(max_neili)) max_neili=1',
            scope="function",
        ),
        Invariant(
            description="eff_jingli / max_neili 追加公式：eff_jingli 同时加成 "
            "max_jing（1/4）与 max_jingli（全额），max_neili 加成 max_qi（1/4），"
            "并由 force 技能上限钳位 eff_jingli（human.c:212,382,404-409）",
            lpc_expr=(
                'eff_jingli > 0: max_jing += eff_jingli/4; max_jingli += eff_jingli; '
                'max_neili > 0: max_qi += max_neili/4; '
                'clamp: eff_jingli <= force*con/2'
            ),
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="age 未定义时初始化为 14（人类初始年龄）",
            lpc_call='if(undefinedp(my["age"])) my["age"] = 14',
            target="entity.age",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="str 未定义时按 profile.attr_min + random(attr_max-attr_min+1) "
            "随机初始化",
            lpc_call='if(undefinedp(my["str"])) my["str"] = profile.attr_min + random(profile.attr_max - profile.attr_min + 1)',
            target="entity.str",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="con 未定义时随机初始化（同 str 公式）",
            lpc_call='if(undefinedp(my["con"])) my["con"] = profile.attr_min + random(profile.attr_max - profile.attr_min + 1)',
            target="entity.con",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="dex 未定义时随机初始化（同 str 公式）",
            lpc_call='if(undefinedp(my["dex"])) my["dex"] = profile.attr_min + random(profile.attr_max - profile.attr_min + 1)',
            target="entity.dex",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="int 未定义时随机初始化（同 str 公式）",
            lpc_call='if(undefinedp(my["int"])) my["int"] = profile.attr_min + random(profile.attr_max - profile.attr_min + 1)',
            target="entity.int",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="per 未定义时随机初始化（同 str 公式）",
            lpc_call='if(undefinedp(my["per"])) my["per"] = profile.attr_min + random(profile.attr_max - profile.attr_min + 1)',
            target="entity.per",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="kar 未定义时随机初始化（同 str 公式）",
            lpc_call='if(undefinedp(my["kar"])) my["kar"] = profile.attr_min + random(profile.attr_max - profile.attr_min + 1)',
            target="entity.kar",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="max_potential 公式计算：100+sqrt(combat_exp)/10+(max_jing-100)/30"
            "（玩家或未定义时）",
            lpc_call='if(userp || undefinedp(max_potential)) max_potential = 100 + sqrt(combat_exp)/10 + (max_jing-100)/30',
            target="entity.max_potential",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.STATE_MUTATION,
            description="max_jing 按年龄公式初始化（age<=14/<=30/>30 三段）",
            lpc_call='if(age<=14) max_jing=100; elif(age<=30) max_jing=100+(age-14)*(int+con)/2; else max_jing=(int+con)*8+100',
            target="entity.max_jing",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.STATE_MUTATION,
            description="max_qi 按年龄公式初始化（age<=14/<=30/>30 三段）",
            lpc_call='if(age<=14) max_qi=100; elif(age<=30) max_qi=100+(age-14)*(con+str)/2; else max_qi=100+(con+str)*8',
            target="entity.max_qi",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.STATE_MUTATION,
            description="max_jingli 按年龄公式初始化（age<=14/<=con/else 三段）",
            lpc_call='if(age<=14) max_jingli=100; elif(age<=con) max_jingli=100+(age-14)*(str+dex); else max_jingli=100+(str+dex)*(con-14)',
            target="entity.max_jingli",
        ),
        SideEffect(
            order=12,
            kind=SideEffectType.STATE_MUTATION,
            description="70 岁衰减：max_jing 减 (age-70)*(int+con)/7",
            lpc_call='if(age>70) max_jing -= (age-70)*(int+con)/7',
            target="entity.max_jing",
        ),
        SideEffect(
            order=13,
            kind=SideEffectType.STATE_MUTATION,
            description="70 岁衰减：max_qi 减 (age-70)*(con+str)/7",
            lpc_call='if(age>70) max_qi -= (age-70)*(con+str)/7',
            target="entity.max_qi",
        ),
        SideEffect(
            order=14,
            kind=SideEffectType.STATE_MUTATION,
            description="70 岁衰减：max_jingli 减 (age-70)*con/5",
            lpc_call='if(age>70) max_jingli -= (age-70)*con/5',
            target="entity.max_jingli",
        ),
        SideEffect(
            order=15,
            kind=SideEffectType.STATE_MUTATION,
            description="NPC max_jing < 1 时钳位到 100（防止 NPC 属性异常）",
            lpc_call='if(!userp && max_jing<1) max_jing=100',
            target="entity.max_jing",
        ),
        SideEffect(
            order=16,
            kind=SideEffectType.STATE_MUTATION,
            description="NPC max_qi < 1 时钳位到 100（防止 NPC 属性异常）",
            lpc_call='if(!userp && max_qi<1) max_qi=100',
            target="entity.max_qi",
        ),
        SideEffect(
            order=17,
            kind=SideEffectType.STATE_MUTATION,
            description="max_jingli/max_neili 未定义时下限 1（防止后续计算异常）",
            lpc_call='if(undefinedp(max_jingli)) max_jingli=1; if(undefinedp(max_neili)) max_neili=1',
            target="entity.max_jingli/max_neili",
        ),
        SideEffect(
            order=18,
            kind=SideEffectType.STATE_MUTATION,
            description="weight 未设置时 = profile.base_weight+(str-10)*profile.str_weight_factor",
            lpc_call='if(!query_weight()) set_weight(profile.base_weight + (str-10)*profile.str_weight_factor)',
            target="entity.weight",
        ),
        SideEffect(
            order=19,
            kind=SideEffectType.STATE_MUTATION,
            description="eff_jingli 加成 max_jing：eff_jingli>0 时 max_jing += eff_jingli/4",
            lpc_call='if(eff_jingli > 0) max_jing += eff_jingli / 4',
            target="entity.max_jing",
        ),
        SideEffect(
            order=20,
            kind=SideEffectType.STATE_MUTATION,
            description="max_neili 加成 max_qi：max_neili>0 时 max_qi += max_neili/4",
            lpc_call='if(max_neili > 0) max_qi += max_neili / 4',
            target="entity.max_qi",
        ),
        SideEffect(
            order=21,
            kind=SideEffectType.STATE_MUTATION,
            description="eff_jingli 加成 max_jingli：eff_jingli>0 时 max_jingli += eff_jingli",
            lpc_call='if(eff_jingli > 0) max_jingli += eff_jingli',
            target="entity.max_jingli",
        ),
        SideEffect(
            order=22,
            kind=SideEffectType.STATE_MUTATION,
            description="eff_jingli 受 force 技能上限钳位",
            lpc_call=(
                'if(query_skill("force") > query_skill("force", 1) && '
                'eff_jingli > query_skill("force") * con / 2) { '
                'eff_jingli = query_skill("force") * con / 2; '
                'max_jingli = query_skill("force") * con / 2; }'
            ),
            target="entity.eff_jingli / entity.max_jingli",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="my['str'] = attr_min + random(attr_max - attr_min + 1)",
            probability_model="str 等六维属性均匀分布在 [attr_min, attr_max] "
            "（human.c 10+random(21) -> [10, 30]）",
            semantic="六维属性（str/con/dex/int/per/kar）未定义时随机初始化",
            seed_inputs=["profile.attr_min", "profile.attr_max", "RNG state"],
            determinism_note="属性随机性属角色生命周期初始化，非 combat 范围，"
            "不需要确定性 RNG（CLAUDE.md 架构不变量：combat 确定性范围=combat-only）",
        ),
    ],
    notes=(
        "greenfield setup_race 只含通用种族基础，门派加成由 apply_family_bonuses "
        "分离（ADR-0030 决策 1）。"
        "LPC human.c setup_human 把通用逻辑与 13 门派加成混在一个 429 行函数，"
        "greenfield 拆为两层：\n"
        "  (1) setup_race -- 引擎层纯通用（年龄公式 / 属性随机 / max_* 初始化 / "
        "70 岁衰减 / weight），公式参数从 RaceProfile 读取\n"
        "  (2) apply_family_bonuses -- 题材包 CPK 资产（FamilyBonus 声明式载体），"
        "按 family_name 匹配分发\n"
        "三层资源不变量（0 <= qi <= eff_qi <= max_qi）：setup_race 只设置 max_*，"
        "qi/eff_* 由层 H CHAR_D setup_char 后续钳位（chard.c:64-69）。\n"
        "主题无关性（ADR-0030 决策 4）：setup_race 不硬编码任何门派名 / 技能名，"
        "测试用非武侠 RaceProfile 验证。"
    ),
)


# ---------------------------------------------------------------------------
# apply_family_bonuses 函数规格（门派加成，题材包 CPK 资产）
#
# LPC 对照：adm/daemons/race/human.c setup_human() 的门派加成分支（行 92-149
# 道家/佛家、152-153 丐帮 death_times、156-182 华山/桃花、185-210 古墓/灵鹫、
# 226-381 max_qi 各门派加成）。
# greenfield apply_family_bonuses 把这些分支提取为标准 FamilyBonus 载体分发，
# 不认识任何具体门派名，只做 family_name 字符串匹配。
# ---------------------------------------------------------------------------

_apply_family_bonuses = FunctionSpec(
    signature=FunctionSignature(
        name="apply_family_bonuses",
        params=[
            LPCParam(
                name="entity",
                lpc_type="object",
                description="待应用门派加成的角色实体",
            ),
            LPCParam(
                name="family_name",
                lpc_type="string",
                description="门派名称（如 '武当派'，greenfield 不硬编码，由 entity.family 注入）",
            ),
            LPCParam(
                name="bonuses",
                lpc_type="FamilyBonus *",
                description="FamilyBonus 列表（题材包 CPK 资产，声明式载体，"
                "is_varargs_tail=True 表示可变长度列表）",
                is_varargs_tail=True,
            ),
        ],
        return_type="void",
        lpc_file="adm/daemons/race/human.c",
        line_range=(92, 381),
    ),
    preconditions=[
        Precondition(
            description="entity 已绑定 family_name（my['family']['family_name'] 可读）",
            lpc_expr='mapp(my["family"]) && stringp(my["family"]["family_name"])',
            kind="require",
        ),
        Precondition(
            description="entity 已绑定 Skills 组件（query_skill 可调用，用于条件检查）",
            lpc_expr="entity has Skills component",
            kind="require",
        ),
        Precondition(
            description="FamilyBonus 列表已注入（bonuses 非空列表，每条含 family_name/"
            "target/condition_skill/condition_threshold/bonus_skill/divisor 等字段）",
            lpc_expr="bonuses is list[FamilyBonus]",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="family_name 匹配的 FamilyBonus 应用到 max_jing/max_qi"
            "（bonus.target 决定加成目标）",
            state_change="for bonus in bonuses: if bonus.family_name == family_name: apply to bonus.target",
            kind="effect",
        ),
        Postcondition(
            description="family_name 不匹配的 FamilyBonus 跳过（不应用任何加成）",
            state_change="if bonus.family_name != family_name: skip",
            kind="effect",
        ),
        Postcondition(
            description="条件不满足的 bonus 跳过：query_skill(condition_skill,1) <= "
            "condition_threshold 时跳过（human.c 各分支 > 39 阈值检查）",
            state_change="if query_skill(bonus.condition_skill,1) <= bonus.condition_threshold: skip",
            kind="effect",
        ),
        Postcondition(
            description="年龄调整统一逻辑：age_adjusted=True 时 xism_age = skill/2；"
            "age<=30 时 xism_age -= age；else xism_age -= 30（human.c:113-115,160-162 等）",
            state_change="if bonus.age_adjusted: xism_age = skill/2; if(age<=30) xism_age-=age; else xism_age-=30",
            kind="effect",
        ),
        Postcondition(
            description="公式计算：bonus_amount = xism_age * (query_skill(bonus.bonus_skill)/bonus.divisor)"
            "（human.c:127,166,181,195,209 等 *(skill/10) 模式）",
            state_change="if xism_age > 0: bonus_amount = xism_age * (query_skill(bonus.bonus_skill) / bonus.divisor)",
            kind="effect",
        ),
        Postcondition(
            description="额外条件检查：extra_condition_key 满足时用 extra_divisor 计算"
            "（华山 huashan/yin-jue > 1 时 /10 否则 /15，human.c:165-168）",
            state_change="if extra_condition_key and query(extra_condition_key) > extra_condition_threshold: use extra_divisor",
            kind="effect",
        ),
        Postcondition(
            description="xism_age <= 0 时不应用加成（30 岁前补精但 xism_age 已被 age 抵消为负则跳过）",
            state_change="if xism_age <= 0: skip bonus",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="max_jing/max_qi 单调非递减：加成只增不减（FamilyBonus 计算结果 "
            ">= 0 才应用，xism_age<=0 时跳过）",
            lpc_expr="max_jing_after >= max_jing_before; max_qi_after >= max_qi_before",
            scope="function",
        ),
        Invariant(
            description="apply_family_bonuses 不认识任何具体门派名，只做 "
            "family_name == bonus.family_name 字符串匹配（ADR-0030 决策 1 主题无关性）",
            lpc_expr="no hardcoded family_name literals in source",
            scope="system",
        ),
        Invariant(
            description="FamilyBonus 列表顺序决定加成应用顺序（副作用 order 按 bonuses "
            "列表顺序递增，不重排）",
            lpc_expr="order(bonus[i]) < order(bonus[i+1]) for i in range(len(bonuses))",
            scope="function",
        ),
        Invariant(
            description="三层资源层次保持：0 <= qi <= eff_qi <= max_qi（apply_family_bonuses "
            "只增 max_*，不破坏 eff/qi 层次）",
            lpc_expr="0 <= qi <= eff_qi <= max_qi (max_qi only increases)",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="遍历 FamilyBonus 列表，按 family_name 过滤匹配的 bonus",
            lpc_call="for bonus in bonuses: if bonus.family_name == family_name: ...",
            target="entity",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="条件检查：query_skill(bonus.condition_skill,1) <= threshold 时跳过",
            lpc_call="if query_skill(bonus.condition_skill, 1) <= bonus.condition_threshold: continue",
            target="entity.skills",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="年龄调整：age_adjusted=True 时 xism_age = skill/2 - (age<=30 ? age : 30)",
            lpc_call="if bonus.age_adjusted: xism_age = skill/2; if(age<=30) xism_age-=age; else xism_age-=30",
            target="entity",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="公式计算：bonus_amount = xism_age * (query_skill(bonus.bonus_skill) / bonus.divisor)",
            lpc_call="if xism_age > 0: bonus_amount = xism_age * (query_skill(bonus.bonus_skill) / bonus.divisor)",
            target="entity",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="额外条件检查：extra_condition_key 满足时用 extra_divisor 重新计算 bonus_amount",
            lpc_call="if bonus.extra_condition_key and query(bonus.extra_condition_key) > bonus.extra_condition_threshold: bonus_amount = xism_age * (query_skill(bonus.bonus_skill) / bonus.extra_divisor)",
            target="entity",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="加成应用到目标：bonus.target == 'max_jing' 时 max_jing += bonus_amount；"
            "bonus.target == 'max_qi' 时 max_qi += bonus_amount",
            lpc_call='if bonus.target == "max_jing": my["max_jing"] += bonus_amount; elif bonus.target == "max_qi": my["max_qi"] += bonus_amount',
            target="entity.max_jing/max_qi",
        ),
    ],
    random_specs=[],
    notes=(
        "13 门派全量公式规格后置 M3（ADR-0030 开放问题 2），本规格只定义标准载体契约。"
        "LPC human.c 的门派加成分支（道家保精保气 / 佛家养精保气 / 丐帮 death_times / "
        "华山紫氤吟+正气诀 / 桃花五音十二律+奇门遁甲 / 古墓玉女二十四诀+心经 / "
        "灵鹫八荒功 / 星宿白驼聚毒练气 / 明教光明心法）提取为标准 FamilyBonus 载体：\n"
        "  - 标准载体字段：family_name / target / condition_skill / condition_threshold / "
        "age_adjusted / bonus_skill / divisor / extra_condition_key / extra_condition_threshold / "
        "extra_divisor\n"
        "  - 丐帮 death_times 加成（地刹炼魂/天魔解体）和明教双技能公式不完全 fit 通用载体，"
        "作为'扩展点'标注（ADR-0030 开放问题 2），覆盖不了的后置 M3\n"
        "  - apply_family_bonuses 不认识任何具体门派名，只做 family_name 字符串匹配\n"
        "加成单调非递减：FamilyBonus 计算结果 >= 0 才应用（xism_age<=0 时跳过），"
        "保证 max_jing/max_qi 只增不减。"
    ),
)


# ---------------------------------------------------------------------------
# 层 H-RACE 规格集合
# ---------------------------------------------------------------------------

LAYER_SPEC = LayerSpec(
    layer_id="H-RACE",
    layer_name="race daemon 种族初始化",
    lpc_files=[
        "adm/daemons/race/human.c",
    ],
    function_specs=[
        _create,
        _set_default_actions,
        _query_action,
        _set_default_object,
        _setup_race,
        _apply_family_bonuses,
    ],
    cross_layer_refs=[
        "setup_char (层 H: CHAR_D) -- setup_char 按种族分派调用 setup_human，"
        "greenfield 对应 setup_race（种族分派入口在 CHAR_D）",
        "query_skill (层 B: F_SKILL) -- apply_family_bonuses 条件检查读取技能等级，"
        "setup_race 中 eff_jingli 上限也读取 force 技能",
        "set / query / set_temp (层 B: F_DBASE) -- setup_race / create / "
        "set_default_actions / set_default_object 读写属性",
        "jing/qi/jingli/eff_jing/eff_qi 钳位 (层 H: CHAR_D setup_char) -- "
        "setup_race 只设置 max_*，qi/eff_* 由 setup_char 后续钳位",
        "default_actions / reset_action (层 E: combat) -- _set_default_actions "
        "绑定 query_action 回调，reset_action 由 setup_char 调用",
        "query_action (层 E: combat) -- query_action 返回 combat_action 模板，"
        "供 combat 系统在无门派动作时回退使用",
    ],
    notes=(
        "层 H-RACE 覆盖 race daemon 种族初始化（create 自身属性 / "
        "set_default_actions 默认动作绑定 / query_action 基础 combat_action / "
        "set_default_object 默认原型 / setup_race 通用基础 / "
        "apply_family_bonuses 门派加成分发），是 ADR-0030 决策 1 race 层切割的 "
        "规格契约。\n"
        "\n"
        "核心契约要点：\n"
        "1. setup_race 纯通用：年龄公式参数化（14/30/70 阈值），属性随机范围参数化"
        "（attr_min/attr_max），不硬编码武侠字面量。\n"
        "2. apply_family_bonuses 标准载体：FamilyBonus 声明式载体分发，不认识具体"
        "门派名，只做 family_name 字符串匹配。13 门派全量公式后置 M3。\n"
        "3. 三层资源不变量：0 <= qi <= eff_qi <= max_qi（setup_race 设置 max_*，"
        "qi/eff_* 由层 H CHAR_D setup_char 后续钳位）。\n"
        "4. 加成单调非递减：FamilyBonus 计算结果 >= 0 才应用。\n"
        "5. 主题无关性（ADR-0030 决策 4）：测试用非武侠 RaceProfile + FamilyBonus"
        "（大航海'海盗帮派'/书院'学派'）验证边界。\n"
        "\n"
        "边界（ADR-0030 开放问题 1 裁决）：\n"
        "- 13 门派全量公式穷尽规格提取后置 M3（开放问题 2）\n"
        "- 丐帮 death_times / 明教双技能等特殊加成作为'扩展点'标注，后置 M3\n"
        "- 非人类种族 RaceProfile（MONSTER/BEAST 等）后置 M3（开放问题 3）\n"
        "- RaceProfile / FamilyBonus 数据类实现属 runtime/race.py + runtime/family.py，"
        "本文件只提取函数级规格契约"
    ),
)
