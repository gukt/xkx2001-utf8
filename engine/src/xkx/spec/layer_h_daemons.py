"""层 H：核心守护进程 -- LPC 规格提取（ADR-0010）。

覆盖范围：
- ``adm/daemons/logind.c`` -- LOGIN_D：logon 连接入口 + 登录状态机
  （get_id / get_passwd / confirm_id / get_name / new_password / confirm_password /
  get_gift / get_email / get_gender / make_body / init_new_player / enter_world /
  reconnect / check_legal_id / check_legal_name / find_login / find_body / set_wizlock）
- ``adm/daemons/chard.c`` -- CHAR_D：setup_char（角色初始化：种族分派 / 属性钳位 /
  内力精力上限 / 负重 / shen / reset_action）+ break_relation（华山派师徒关系解除）
- ``adm/daemons/securityd.c`` -- SECURITY_D：valid_cmd（命令权限校验，fail-closed）/
  valid_write / valid_read / get_status / get_wiz_level / set_status /
  valid_wiz_login / valid_seteuid
- ``adm/daemons/natured.c`` -- NATURE_D：时间推进（真实 1 秒 = 游戏 1 分钟）+
  update_day_phase / event_sunrise（自动保存触发）/ event_common（通用定时事件）
- ``adm/daemons/chinesed.c`` -- CHINESE_D：chinese_number（数字转中文）/
  chinese_date（日期转中文干支）/ chinese（英中翻译查询）

核心契约要点：
1. **LOGIN_D 状态机完整性**（logind.c）：
   连接入口 logon -> confirm_big5 -> get_id -> [存档存在] get_passwd ->
   [存档不存在] confirm_id -> get_name -> new_password -> confirm_password ->
   get_gift -> get_email -> get_gender -> make_body -> init_new_player ->
   enter_world。重连路径：get_passwd -> find_body -> reconnect。
   各阶段有输入校验（check_legal_id/check_legal_name）和失败重试。
2. **SECURITY_D valid_cmd 每条命令都过**（CLAUDE.md 架构不变量）：
   command_hook 每条命令执行前调 valid_cmd，返回 1=允许，0=拒绝。
   fail-closed：euid 为空或权限不足时返回 0。 cmds/std/cmds/skill/cmds/usr
   目录对所有玩家开放；cmds/adm 仅 admin；cmds/arch 需 admin+arch 等。
3. **NATURE_D 时间系统**：真实 1 秒 = 游戏 1 分钟（TIME_TICK = time()*60）。
   8 个日间阶段循环（凌晨/日出/上午/正午/下午/傍晚/夜晚/午夜），
   每阶段长度以游戏分钟计（240/120/180/...）。event_sunrise 触发全局自动保存。
4. **JSON 存档崩溃安全**（CLAUDE.md 架构不变量）：
   NATURE_D event_sunrise 遍历所有在线玩家的 link_ob + body 并 save()。
   Python 实现需用 write-temp + os.replace 原子写，不得重蹈 LPC save_object
   全量覆盖无原子写的覆辙。
5. **CHINESE_D 无随机性**：chinese_number 和 chinese_date 均为确定性映射函数。

关键不变量：
- **valid_cmd fail-closed**：euid 为空或权限不匹配时返回 0（拒绝），不得默认放行。
- **valid_write/valid_read exclude 优先于 trusted**：先检查 exclude 列表（命中即拒绝），
  再检查 trusted 列表（命中即允许）。ROOT_UID 直接放行。
- **NATURE_D 时间推进**：真实 1 秒 = 游戏 1 分钟，call_out 延迟以游戏分钟为单位。
- **setup_char 属性钳位**：jing/qi/jingli 未定义时初始化为 max 值；
  eff_jing/eff_qi 不超过 max；neili/jingli 有技能相关上限钳位。
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
# 层 H 特定模型
# ---------------------------------------------------------------------------


class LoginState(StrEnum):
    """LOGIN_D 状态机各阶段（logind.c 状态转换序列）。

    从 logon 入口到 enter_world 的完整流程，每个状态对应一个 input_to 回调。
    各阶段有输入校验和失败重试（如 check_legal_id 失败后重新 input_to get_id）。
    """

    LOGON = "logon"
    """连接入口：BAN_D 检查 + MAX_USERS 检查 + 显示欢迎信息。"""

    CONFIRM_BIG5 = "confirm_big5"
    """选择编码（BIG5/GB），显示在线人数，请求输入英文名。"""

    GET_ID = "get_id"
    """输入英文名：check_legal_id 校验 + 存档存在性判断 +
    wiz_lock 检查 + REGBAN_D 检查。"""

    GET_PASSWD = "get_passwd"
    """输入密码：crypt 校验 + SUICIDE_LIST 自杀检查 +
    find_body 重连判定 + make_body + restore + enter_world。"""

    CONFIRM_ID = "confirm_id"
    """确认创建新人物（y/n）。"""

    GET_NAME = "get_name"
    """输入中文名：check_legal_name 校验 + banned_name 检查。"""

    NEW_PASSWORD = "new_password"
    """设定密码：长度 >= 5 校验 + crypt 加密。"""

    CONFIRM_PASSWORD = "confirm_password"
    """确认密码：crypt 比对 + random_gift 天赋生成。"""

    GET_GIFT = "get_gift"
    """接受/拒绝天赋（y 重新随机，Y 进入下一步）。"""

    GET_EMAIL = "get_email"
    """输入电子邮件：格式校验 + make_body + 设置天赋属性。"""

    GET_GENDER = "get_gender"
    """选择性别（m/f）+ init_new_player + enter_world。"""

    ENTER_WORLD = "enter_world"
    """进入游戏世界：link/body 关联 + exec + setup + save + 移到起始房间。"""

    RECONNECT = "reconnect"
    """重连路径：link/body 关联 + exec + reconnect + 房间消息。"""


class WizLevel(StrEnum):
    """巫师等级层次（securityd.c wiz_levels 数组，从低到高）。

    权限校验基于此层次：高等级包含低等级权限。
    authorized_cmds/exclude_cmds/trusted_write/exclude_read 等权限表
    均以 WizLevel 为粒度控制访问。
    """

    PLAYER = "(player)"
    """普通玩家：可执行 cmds/std、cmds/skill、cmds/usr 目录命令。"""

    IMMORTAL = "(immortal)"
    """不朽者：可执行 cmds/imm 目录命令。"""

    APPRENTICE = "(apprentice)"
    """学徒巫师。"""

    VIRTUOSO = "(virtuoso)"
    """高手巫师。"""

    CARETAKER = "(caretaker)"
    """管理员巫师。"""

    CREATOR = "(creator)"
    """创造者巫师。"""

    DESIGNER = "(designer)"
    """设计者巫师。"""

    WIZARD = "(wizard)"
    """巫师：可执行 cmds/wiz 目录命令。"""

    ARCH = "(arch)"
    """大巫师：可执行 cmds/arch 目录命令。"""

    ADMIN = "(admin)"
    """最高管理员：可执行 cmds/adm 目录命令，拥有全部权限。"""


# ---------------------------------------------------------------------------
# LOGIN_D 函数规格（logind.c）
# ---------------------------------------------------------------------------

_logon = FunctionSpec(
    signature=FunctionSignature(
        name="logon",
        params=[
            LPCParam(name="ob", lpc_type="object", description="新创建的连接对象（LOGIN_OB）"),
        ],
        return_type="void",
        lpc_file="adm/daemons/logind.c",
        line_range=(116, 142),
    ),
    preconditions=[
        Precondition(
            description="ob 是新创建的 LOGIN_OB 连接对象",
            lpc_expr="objectp(ob)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="BAN_D 封禁的 IP 地址被拒绝并 destruct(ob)",
            state_change='if(BAN_D->is_banned(query_ip_name(ob))) { destruct(ob); return; }',
            kind="effect",
        ),
        Postcondition(
            description="在线人数达到 MAX_USERS-4 时拒绝新连接并 destruct(ob)",
            state_change="if(sizeof(users()) >= MAX_USERS-4) { destruct(ob); return; }",
            kind="effect",
        ),
        Postcondition(
            description="通过检查后显示欢迎信息（cat(WELCOME) + MUDLIST）并进入 confirm_big5 状态",
            state_change='input_to("confirm_big5", ob)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="logon 是连接的唯一入口，所有后续交互通过 input_to 链推进",
            scope="system",
        ),
        Invariant(
            description="BAN_D 和 MAX_USERS 检查在显示欢迎信息之前执行（fail-closed）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="BAN_D->is_banned(query_ip_name(ob)) 检查 IP 封禁",
            lpc_call='BAN_D->is_banned(query_ip_name(ob))',
            target="ob",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="IP 封禁时 destruct(ob) 销毁连接对象",
            lpc_call="destruct(ob)",
            target="ob",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="MAX_USERS 检查：sizeof(users()) >= MAX_USERS-4 时拒绝",
            lpc_call="if(sizeof(users()) >= MAX_USERS - 4) { destruct(ob); return; }",
            target="ob",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="显示欢迎信息：cat(WELCOME) + MUDLIST_CMD->main",
            lpc_call='cat(WELCOME); MUDLIST_CMD->main(this_object(), "")',
            target="ob",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="输出编码选择提示 'Do you want to use BIG5 code?(y/n)'",
            lpc_call='write_ob(ob, "\\nDo you want to use BIG5 code?(y/n)\\n")',
            target="ob",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.EXTERNAL,
            description="进入 confirm_big5 状态：input_to('confirm_big5', ob)",
            lpc_call='input_to("confirm_big5", ob)',
            target="ob",
        ),
    ],
    random_specs=[],
    notes=(
        "logon 是玩家连接的入口点，由 driver 在新连接建立时调用。"
        "BAN_D 和 MAX_USERS 检查是 fail-closed 设计：先检查再显示欢迎信息。"
        "编码选择（BIG5/GB）后进入 get_id 状态，开始登录/注册流程。"
    ),
)

_get_id = FunctionSpec(
    signature=FunctionSignature(
        name="get_id",
        params=[
            LPCParam(name="arg", lpc_type="string", description="玩家输入的英文名"),
            LPCParam(name="ob", lpc_type="object", description="连接对象"),
        ],
        return_type="void",
        lpc_file="adm/daemons/logind.c",
        line_range=(144, 232),
    ),
    preconditions=[
        Precondition(
            description="ob 是有效的连接对象",
            lpc_expr="objectp(ob)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="check_legal_id 校验失败时重新请求输入（回到 get_id 状态）",
            state_change='if(!check_legal_id(arg, ob)) input_to("get_id", ob); return;',
            kind="effect",
        ),
        Postcondition(
            description="存档存在时 restore 成功进入 get_passwd 状态，失败 destruct",
            state_change="if(ob->restore()) input_to('get_passwd', 1, ob); else destruct(ob);",
            kind="effect",
        ),
        Postcondition(
            description="存档不存在时进入 confirm_id 状态（创建新人物确认）",
            state_change='input_to("confirm_id", ob)',
            kind="effect",
        ),
        Postcondition(
            description="wiz_level 低于 wiz_lock_level 时拒绝连线并 destruct",
            state_change="if(wiz_level(arg) < wiz_lock_level) { destruct(ob); return; }",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="英文名校验规则：长度 3-8 个纯小写字母（player），wiz 可更短",
            lpc_expr="strlen(id) >= 3 && strlen(id) <= 8 || SECURITY_D->get_status(id) != '(player)'",
            scope="function",
        ),
        Invariant(
            description="MAX_USERS 超限时仅允许重连已有在线玩家，不允许新玩家登录",
            lpc_expr="sizeof(users()) >= MAX_USERS-4 && get_status(arg)=='(player)' => 仅允许 reconnect",
            scope="function",
        ),
        Invariant(
            description="巫师登录需通过 valid_wiz_login IP 校验，失败记日志并 destruct",
            lpc_expr='wiz_level(arg) && !SECURITY_D->valid_wiz_login(arg, query_ip_number(ob)) => destruct',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="arg = lower_case(arg) 转小写",
            lpc_call="arg = lower_case(arg)",
            target="arg",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="check_legal_id 校验英文名合法性",
            lpc_call="check_legal_id(arg, ob)",
            target="ob",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="MAX_USERS 超限 + player 时检查 find_body 是否可重连",
            lpc_call="if(sizeof(users())>=MAX_USERS-4 && get_status(arg)=='(player)') { ppl=find_body(arg); if(!ppl||!interactive(ppl)) destruct(ob); }",
            target="ob",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.EXTERNAL,
            description="巫师登录 IP 校验：valid_wiz_login",
            lpc_call='if(wiz_level(arg) && !SECURITY_D->valid_wiz_login(arg, query_ip_number(ob))) { log_file(...); destruct(ob); return; }',
            target="ob",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="wiz_lock 检查：wiz_level < wiz_lock_level 时 destruct",
            lpc_call="if(wiz_level(arg) < wiz_lock_level) { destruct(ob); return; }",
            target="ob",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="ob->set('id', arg) 设置玩家 ID",
            lpc_call='ob->set("id", arg)',
            target="ob.id",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.PERSISTENCE,
            description="存档存在时 ob->restore() 恢复连接对象数据",
            lpc_call="if(file_size(ob->query_save_file() + __SAVE_EXTENSION__) >= 0) ob->restore()",
            target="ob",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="restore 成功后输出 '请输入密码：' 并进入 get_passwd",
            lpc_call='write_ob(ob, "请输入密码："); input_to("get_passwd", 1, ob)',
            target="ob",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.EXTERNAL,
            description="REGBAN_D 检查（新人物创建限制）",
            lpc_call='if(REGBAN_D->is_banned(query_ip_name(ob))) { destruct(ob); return; }',
            target="ob",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="存档不存在时输出 '使用 <id> 这个名字将会创造一个新的人物，您确定吗(y/n)？'",
            lpc_call='write_ob(ob, "使用 " + ob->query("id") + " 这个名字将会创造一个新的人物，您确定吗(y/n)？"); input_to("confirm_id", ob)',
            target="ob",
        ),
    ],
    random_specs=[],
    notes=(
        "get_id 是登录状态机的核心分支点：存档存在则走密码验证路径（get_passwd），"
        "存档不存在则走新人物创建路径（confirm_id）。"
        "MAX_USERS/wiz_lock/valid_wiz_login/REGBAN_D 四重前置检查均为 fail-closed。"
    ),
)

_get_passwd = FunctionSpec(
    signature=FunctionSignature(
        name="get_passwd",
        params=[
            LPCParam(name="pass", lpc_type="string", description="玩家输入的密码"),
            LPCParam(name="ob", lpc_type="object", description="连接对象"),
        ],
        return_type="void",
        lpc_file="adm/daemons/logind.c",
        line_range=(234, 293),
    ),
    preconditions=[
        Precondition(
            description="ob 的存档已 restore 成功（password 字段已加载）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="密码错误时 destruct(ob) 并记录巫师失败日志",
            state_change="if(crypt(pass, my_pass) != my_pass) { log_file(...); destruct(ob); return; }",
            kind="effect",
        ),
        Postcondition(
            description="自杀列表中的 ID 被拒绝还魂并 destruct",
            state_change='if(strsrch(tmp[cnt], "*"+id+" commits")>=0) { destruct(ob); return; }',
            kind="effect",
        ),
        Postcondition(
            description="已有在线 body 时：netdead 走 reconnect，非 netdead 走 confirm_relogin",
            state_change="if(user=find_body(id)) { user->query_temp('netdead') ? reconnect : confirm_relogin }",
            kind="effect",
        ),
        Postcondition(
            description="无在线 body 时 make_body + restore + enter_world",
            state_change="user=make_body(ob); user->restore(); enter_world(ob, user)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="密码校验使用 crypt(pass, stored_salt) 比对存储的密码哈希",
            lpc_expr="crypt(pass, my_pass) == my_pass",
            scope="function",
        ),
        Invariant(
            description="自杀列表（SUICIDE_LIST）中的 ID 永久禁止登录",
            lpc_expr='strsrch(line, "*"+id+" commits") >= 0 => destruct',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="密码校验：crypt(pass, my_pass) != my_pass 时 destruct + 日志",
            lpc_call="if(crypt(pass, my_pass) != my_pass) { log_file('WIZ_LOGIN', ...); destruct(ob); return; }",
            target="ob",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="SUICIDE_LIST 自杀检查：读取并逐行匹配",
            lpc_call='file = read_file(SUICIDE_LIST); strsrch(tmp[cnt], "*"+ob->query("id")+" commits")',
            target="ob",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="find_body 查找已有在线 body",
            lpc_call='user = find_body(ob->query("id"))',
            target="user",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.EXTERNAL,
            description="netdead 玩家重连：reconnect(ob, user)",
            lpc_call='if(user->query_temp("netdead")) reconnect(ob, user)',
            target="user",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="非 netdead 在线玩家：输出 '您要将另一个连线中的相同人物赶出去，取而代之吗？(y/n)'",
            lpc_call='write_ob(ob, "您要将另一个连线中的相同人物赶出去，取而代之吗？(y/n)"); input_to("confirm_relogin", ob, user)',
            target="ob",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="无在线 body 时：make_body(ob) 创建角色 body 对象",
            lpc_call="user = make_body(ob)",
            target="user",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.PERSISTENCE,
            description="user->restore() 恢复角色存档",
            lpc_call="user->restore()",
            target="user",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.EXTERNAL,
            description="restore 成功后 enter_world(ob, user) 进入游戏世界",
            lpc_call="enter_world(ob, user)",
            target="user",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.EXTERNAL,
            description="restore 失败时 destruct(user) + confirm_id('y', ob) 重新创建",
            lpc_call="destruct(user); confirm_id('y', ob)",
            target="user",
        ),
    ],
    random_specs=[],
    notes=(
        "get_passwd 是存档玩家的登录验证入口。密码校验通过后检查自杀列表和在线状态。"
        "已有在线 body 时区分 netdead（断线重连）和正常在线（踢出旧连接）。"
        "make_body + restore + enter_world 是正常登录路径的完整序列。"
    ),
)

_make_body = FunctionSpec(
    signature=FunctionSignature(
        name="make_body",
        params=[
            LPCParam(name="ob", lpc_type="object", description="连接对象（LOGIN_OB）"),
        ],
        return_type="object",
        lpc_file="adm/daemons/logind.c",
        line_range=(485, 505),
    ),
    preconditions=[
        Precondition(
            description="ob 已设置 'body' 属性（USER_OB 或种族 body 路径）",
            lpc_expr='ob->query("body")',
            kind="require",
        ),
        Precondition(
            description="ob 已设置 'id' 属性",
            lpc_expr='ob->query("id")',
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="成功时返回新创建的 user body 对象（已 clone + set euid + set id/name）",
            return_value="object=body 对象，0=clone 失败",
            kind="ensure",
        ),
        Postcondition(
            description="body 对象的 euid 设为 ob 的 id",
            state_change="seteuid(ob->query('id')); export_uid(user); export_uid(ob)",
            kind="effect",
        ),
        Postcondition(
            description="body 对象已设置 id 和 name（从 ob 复制）",
            state_change='user->set("id", ob->query("id")); user->set_name(ob->query("name"), ({ob->query("id")}))',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="make_body 是连接对象（link_ob）到角色 body 的转换函数",
            scope="class",
        ),
        Invariant(
            description="euid 设置序列：seteuid(id) -> export_uid(user) -> export_uid(ob) -> seteuid(getuid())",
            lpc_expr="seteuid(ob->query('id')); export_uid(user); export_uid(ob); seteuid(getuid())",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="new(ob->query('body')) clone 角色 body 对象",
            lpc_call='user = new(ob->query("body"))',
            target="user",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="设置 euid 链：seteuid(ob->id) -> export_uid(user) -> export_uid(ob) -> seteuid(getuid)",
            lpc_call="seteuid(ob->query('id')); export_uid(user); export_uid(ob); seteuid(getuid())",
            target="user.ob",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="user->set('id', ob->query('id')) + set('language', ob->query('language'))",
            lpc_call='user->set("id", ob->query("id")); user->set("language", ob->query("language"))',
            target="user",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="user->set_name(ob->query('name'), ({ob->query('id')})) 设置角色名称",
            lpc_call='user->set_name(ob->query("name"), ({ ob->query("id") }))',
            target="user",
        ),
    ],
    random_specs=[],
    notes="make_body 是登录流程中从连接对象创建角色 body 的关键步骤，设置 euid 和基本属性。",
)

_enter_world = FunctionSpec(
    signature=FunctionSignature(
        name="enter_world",
        params=[
            LPCParam(name="ob", lpc_type="object", description="连接对象（link_ob）"),
            LPCParam(name="user", lpc_type="object", description="角色 body 对象"),
            LPCParam(name="silent", lpc_type="int", description="silent=1 安静进入（不输出 MOTD/消息）"),
        ],
        return_type="void",
        is_varargs=True,
        lpc_file="adm/daemons/logind.c",
        line_range=(533, 676),
    ),
    preconditions=[
        Precondition(
            description="ob 和 user 是有效对象",
            lpc_expr="objectp(ob) && objectp(user)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="link/body 双向关联已建立：user->set_temp('link_ob', ob); ob->set_temp('body_ob', user)",
            state_change="user->set_temp('link_ob', ob); ob->set_temp('body_ob', user)",
            kind="effect",
        ),
        Postcondition(
            description="exec(user, ob) 将连接控制权从 link_ob 转移到 body",
            state_change="exec(user, ob)",
            kind="effect",
        ),
        Postcondition(
            description="user->setup() 已调用（启用 heart_beat + enable_player + setup_char）",
            state_change="user->setup()",
            kind="effect",
        ),
        Postcondition(
            description="ob->save() + user->save() 已执行（存档持久化）",
            state_change="ob->save(); user->save()",
            kind="effect",
        ),
        Postcondition(
            description="非 silent 时输出 MOTD/规则/上次连线信息并移到起始房间",
            state_change="if(!silent) { write(MOTD); user->move(startroom); }",
            kind="effect",
        ),
        Postcondition(
            description="起始房间选择：ghost -> DEATH_ROOM; 无 startroom/family -> /d/xiakedao/shatan",
            state_change="startroom = is_ghost ? DEATH_ROOM : query('startroom') || '/d/xiakedao/shatan'",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="exec(user, ob) 是 LPC driver 级别的连接转移：将 socket 从 link_ob 转到 body",
            lpc_expr="exec(user, ob)",
            scope="system",
        ),
        Invariant(
            description="起始房间选择优先级：ghost -> DEATH_ROOM; 注册检查 -> /d/xiakedao/shatan1; "
            "death_count>200+exp<50000 -> /d/death/block; startroom 有效 -> startroom; fallback -> START_ROOM",
            scope="function",
        ),
        Invariant(
            description="enter_world 是玩家进入游戏世界的最终步骤，之后玩家完全可控",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="建立 link/body 双向关联：set_temp('link_ob'/'body_ob')",
            lpc_call='user->set_temp("link_ob", ob); ob->set_temp("body_ob", user)',
            target="user.ob",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="exec(user, ob) 将连接控制权从 link_ob 转移到 body",
            lpc_call="exec(user, ob)",
            target="user.ob",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="输出权限信息 '目前权限：<wizhood>'",
            lpc_call='write_ob(user, "\\n目前权限：" + wizhood(user) + "\\n")',
            target="user",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.EXTERNAL,
            description="user->setup() 初始化角色（heart_beat + enable_player + setup_char）",
            lpc_call="user->setup()",
            target="user",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.PERSISTENCE,
            description="ob->save() 保存连接对象（link_ob）存档",
            lpc_call="ob->save()",
            target="ob",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.EXTERNAL,
            description="MARRY_D->validate_marriage + 结婚戒指 move",
            lpc_call='if(MARRY_D->validate_marriage(user)) new("/d/city/obj/pring")->move(user)',
            target="user",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.EXTERNAL,
            description="UPDATE_D->login_check(user) 登录数据检查",
            lpc_call="UPDATE_D->login_check(user)",
            target="user",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="豹胎易筋丸检查：超时未服时属性衰减 + 红色警告消息",
            lpc_call='if(yijin_wan && yijin_wan < age-14) { random_gift(my); user->set("str", ...); tell_object(user, HIR "你一年内未服豹胎易筋丸，功力大损！！！\\n" NOR); }',
            target="user",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.PERSISTENCE,
            description="user->save() 保存角色存档",
            lpc_call="user->save()",
            target="user",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="非 silent 时输出 MOTD/规则/上次连线地址信息",
            lpc_call='if(!silent) { write(MOTD); write("上次连线地址：\\t%s( %s )\\n", last_from, last_on); }',
            target="user",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="非 silent 时 user->move(startroom) 移到起始房间",
            lpc_call="user->move(startroom)",
            target="user",
        ),
        SideEffect(
            order=12,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="tell_room 输出 '<角色名>连线进入这个世界。'（不含玩家自身）",
            lpc_call='tell_room(startroom, user->query("name") + "连线进入这个世界。\\n", ({user}))',
            target="room",
        ),
        SideEffect(
            order=13,
            kind=SideEffectType.EXTERNAL,
            description="CHANNEL_D->do_channel 系统频道广播 '<角色>(<id>)由<ip>连线进入。'",
            lpc_call='CHANNEL_D->do_channel(this_object(), "sys", sprintf("%s(%s)由%s连线进入。", ...))',
            target="channel",
        ),
    ],
    random_specs=[],
    notes=(
        "enter_world 是登录流程的终点，完成 link/body 关联、exec 连接转移、setup 初始化、"
        "存档持久化、MOTD 显示和房间移动。"
        "起始房间选择有优先级链：ghost/注册/死亡次数/startroom/fallback。"
        "cross_layer_refs: setup 属层 G，move 属层 B，CHANNEL_D 属本层。"
    ),
)

_reconnect = FunctionSpec(
    signature=FunctionSignature(
        name="reconnect",
        params=[
            LPCParam(name="ob", lpc_type="object", description="新连接对象（link_ob）"),
            LPCParam(name="user", lpc_type="object", description="已有 body 对象"),
            LPCParam(name="silent", lpc_type="int", description="silent=1 安静重连"),
        ],
        return_type="void",
        is_varargs=True,
        lpc_file="adm/daemons/logind.c",
        line_range=(678, 691),
    ),
    preconditions=[
        Precondition(
            description="ob 和 user 是有效对象，user 是已有在线 body",
            lpc_expr="objectp(ob) && objectp(user)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="link/body 双向关联已建立",
            state_change="user->set_temp('link_ob', ob); ob->set_temp('body_ob', user)",
            kind="effect",
        ),
        Postcondition(
            description="exec(user, ob) 将连接控制权转移到已有 body",
            state_change="exec(user, ob)",
            kind="effect",
        ),
        Postcondition(
            description="user->reconnect() 调用 body 侧重连回调",
            state_change="user->reconnect()",
            kind="effect",
        ),
        Postcondition(
            description="非 silent 时向房间输出 '<角色名>重新连线回到这个世界。'",
            state_change='tell_room(environment(user), name+"重新连线回到这个世界。\\n", ({user}))',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="reconnect 不调用 setup（body 已初始化），仅恢复连接",
            scope="function",
        ),
        Invariant(
            description="reconnect 是断线重连的专用路径，与 enter_world（新登录）区别在于不 setup/save",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="建立 link/body 双向关联",
            lpc_call='user->set_temp("link_ob", ob); ob->set_temp("body_ob", user)',
            target="user.ob",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="exec(user, ob) 将连接控制权从 link_ob 转移到 body",
            lpc_call="exec(user, ob)",
            target="user.ob",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.EXTERNAL,
            description="user->reconnect() 调用 body 侧重连回调",
            lpc_call="user->reconnect()",
            target="user",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="非 silent 时 tell_room 输出重连消息",
            lpc_call='tell_room(environment(user), user->query("name") + "重新连线回到这个世界。\\n", ({user}))',
            target="room",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.EXTERNAL,
            description="CHANNEL_D->do_channel 系统频道广播重连消息",
            lpc_call='CHANNEL_D->do_channel(this_object(), "sys", sprintf("%s(%s)由%s重新连线进入。", ...))',
            target="channel",
        ),
    ],
    random_specs=[],
    notes="reconnect 是断线重连专用路径，不调用 setup/save，仅恢复连接控制权。",
)

_check_legal_id = FunctionSpec(
    signature=FunctionSignature(
        name="check_legal_id",
        params=[
            LPCParam(name="id", lpc_type="string", description="待校验的英文名"),
            LPCParam(name="ob", lpc_type="object", description="连接对象（用于消息输出）"),
        ],
        return_type="int",
        lpc_file="adm/daemons/logind.c",
        line_range=(693, 711),
    ),
    preconditions=[
        Precondition(
            description="id 已转小写",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="合法返回 1，非法返回 0 并输出错误消息",
            return_value="1=合法, 0=非法",
            kind="ensure",
        ),
        Postcondition(
            description="player 名字长度必须 3-8 个英文字母",
            state_change='if(strlen(id)<3 || strlen(id)>8 && get_status(id)=="(player)") return 0',
            kind="effect",
        ),
        Postcondition(
            description="名字只能包含小写字母 a-z",
            state_change="if(id[i]<'a' || id[i]>'z') return 0",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="巫师 ID 不受长度限制（get_status != '(player)' 时跳过长度检查）",
            lpc_expr='strlen(id) < 3 || strlen(id) > 8 && SECURITY_D->get_status(id) == "(player)"',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="非法时输出 '对不起，你的英文名字必须是 3 到 8 个英文字母。' 或 '只能用英文字母'",
            lpc_call='write_ob(ob, "对不起，你的英文名字必须是 3 到 8 个英文字母。\\n")',
            target="ob",
        ),
    ],
    random_specs=[],
    notes="check_legal_id 是 get_id 阶段的输入校验函数，player 有严格长度和字符限制。",
)

_check_legal_name = FunctionSpec(
    signature=FunctionSignature(
        name="check_legal_name",
        params=[
            LPCParam(name="name", lpc_type="string", description="待校验的中文名"),
            LPCParam(name="ob", lpc_type="object", description="连接对象（用于消息输出）"),
        ],
        return_type="string",
        lpc_file="adm/daemons/logind.c",
        line_range=(713, 740),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="合法返回 name 字符串，非法返回 0 并输出错误消息",
            return_value="string=合法名字, 0=非法",
            kind="ensure",
        ),
        Postcondition(
            description="中文名长度必须 2-8 字节（1-4 个中文字），且字节数为偶数",
            state_change='if(strlen(name)<2 || strlen(name)>8 || i%2) return 0',
            kind="effect",
        ),
        Postcondition(
            description="banned_name 列表中的名字被拒绝",
            state_change='if(member_array(name, banned_name)!=-1) return 0',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="banned_name 包含代词和特殊名字：你/我/他/她/它/韦小宝/某人/您/谣言/蒙面人/金庸等",
            scope="class",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="非法时输出 '对不起，你的中文名字必须是 1 到 4 个中文字。' 或 '会造成其他人的困扰'",
            lpc_call='write_ob(ob, "对不起，你的中文名字必须是 1 到 4 个中文字。\\n")',
            target="ob",
        ),
    ],
    random_specs=[],
    notes="check_legal_name 校验中文名的长度、字符和禁用词。banned_name 是静态列表。",
)

_random_gift = FunctionSpec(
    signature=FunctionSignature(
        name="random_gift",
        params=[
            LPCParam(name="my", lpc_type="mapping", description="待填充的属性 mapping"),
        ],
        return_type="void",
        lpc_file="adm/daemons/logind.c",
        line_range=(41, 67),
    ),
    preconditions=[
        Precondition(
            description="my 是空 mapping（待填充）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="str/int/con/dex 通过 50 次 random(5) 分配，各项起始 10，上限 30",
            state_change="str/int/con/dex = 10 + 50 次 random(5) 分配（上限 30）",
            kind="effect",
        ),
        Postcondition(
            description="end = 100 - str - int - con - dex（耐力为剩余值）",
            state_change='my["end"] = 100 - my["dex"] - my["str"] - my["int"] - my["con"]',
            kind="effect",
        ),
        Postcondition(
            description="kar = 10 + random(21), pat = 10 + random(21), per = 60 - kar - pat",
            state_change='my["kar"] = 10 + random(21); my["pat"] = 10 + random(21); my["per"] = 60 - my["kar"] - my["pat"]',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="str+int+con+dex+end = 100（五项天赋总和恒为 100）",
            lpc_expr="str + int + con + dex + end == 100",
            scope="function",
        ),
        Invariant(
            description="kar+pat+per = 60（三项隐藏属性总和恒为 60）",
            lpc_expr="kar + pat + per == 60",
            scope="function",
        ),
        Invariant(
            description="str/int/con/dex 上限 30（超过 30 封顶）",
            lpc_expr="if(tmpstr <= 30) my['str'] = tmpstr; else my['str'] = 30",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="50 次 random(5) 分配 str/int/con/dex（起始 10，上限 30）",
            lpc_call="for(i=0; i<50; i++) switch(random(5)) { case 0: tmpstr++; ... }",
            target="my.str/int/con/dex",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="end = 100 - str - int - con - dex",
            lpc_call='my["end"] = 100 - my["dex"] - my["str"] - my["int"] - my["con"]',
            target="my.end",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="kar = 10 + random(21), pat = 10 + random(21)",
            lpc_call='my["kar"] = 10 + random(21); my["pat"] = 10 + random(21)',
            target="my.kar.pat",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="per = 60 - kar - pat",
            lpc_call='my["per"] = 60 - my["kar"] - my["pat"]',
            target="my.per",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(5) * 50 次",
            probability_model="50 次独立 random(5)，每次等概率分配到 str/int/con/dex/end 之一",
            semantic="天赋随机分配：50 次随机分配到五项属性",
            seed_inputs=["无外部 seed"],
            determinism_note="角色创建随机性，不需要确定性 RNG",
        ),
        RandomSpec(
            lpc_call="random(21) * 2",
            probability_model="kar = 10 + random(21)，范围 [10, 30]；pat 同理",
            semantic="隐藏属性 kar/pat 随机生成",
            seed_inputs=["无外部 seed"],
            determinism_note="角色创建随机性，不需要确定性 RNG",
        ),
    ],
    notes=(
        "random_gift 是新角色天赋生成的核心函数。"
        "五项天赋（str/int/con/dex/end）总和恒为 100，通过 50 次随机分配。"
        "三项隐藏属性（kar/pat/per）总和恒为 60。"
    ),
)

_init_new_player = FunctionSpec(
    signature=FunctionSignature(
        name="init_new_player",
        params=[
            LPCParam(name="user", lpc_type="object", description="新角色 body 对象"),
        ],
        return_type="void",
        lpc_file="adm/daemons/logind.c",
        line_range=(507, 530),
    ),
    preconditions=[
        Precondition(
            description="user 是新创建的 body 对象（天赋已设置）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="title 设为 '普通百姓'",
            state_change='user->set("title", "普通百姓")',
            kind="effect",
        ),
        Postcondition(
            description="birthday 设为当前时间 time()",
            state_change='user->set("birthday", time())',
            kind="effect",
        ),
        Postcondition(
            description="potential=99, max_neili=400, eff_jingli=300, max_jingli=300",
            state_change='user->set("potential", 99); user->set("max_neili", 400); ...',
            kind="effect",
        ),
        Postcondition(
            description="channels 设为 ({'chat', 'rumor', 'gchat'})",
            state_change='user->set("channels", ({ "chat", "rumor", "gchat" }))',
            kind="effect",
        ),
        Postcondition(
            description="create_human_body() 已调用（种族初始化）",
            state_change="user->create_human_body()",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="init_new_player 设置新角色的默认属性和频道",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="set('title', '普通百姓') + set('birthday', time())",
            lpc_call='user->set("title", "普通百姓"); user->set("birthday", time())',
            target="user",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="set('potential', 99) + set('max_neili', 400) + set('eff_jingli', 300) + set('max_jingli', 300)",
            lpc_call='user->set("potential", 99); user->set("max_neili", 400); user->set("eff_jingli", 300); user->set("max_jingli", 300)',
            target="user",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="set('channels', ({'chat', 'rumor', 'gchat'}))",
            lpc_call='user->set("channels", ({ "chat", "rumor", "gchat" }))',
            target="user",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.EXTERNAL,
            description="create_human_body() 种族初始化（HP/max_qi/max_jing 等）",
            lpc_call="user->create_human_body()",
            target="user",
        ),
    ],
    random_specs=[],
    notes="init_new_player 设置新角色的初始属性默认值和频道列表。create_human_body 属种族 daemon。",
)


# ---------------------------------------------------------------------------
# CHAR_D 函数规格（chard.c）
# ---------------------------------------------------------------------------

_setup_char = FunctionSpec(
    signature=FunctionSignature(
        name="setup_char",
        params=[
            LPCParam(name="ob", lpc_type="object", description="待初始化的角色对象"),
        ],
        return_type="void",
        lpc_file="adm/daemons/chard.c",
        line_range=(22, 114),
    ),
    preconditions=[
        Precondition(
            description="ob 是有效对象，dbase 已初始化",
            lpc_expr="objectp(ob) && ob->query_entire_dbase()",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="race 未设置时默认为 '人类'",
            state_change='if(!stringp(race=ob->query("race"))) { race="人类"; ob->set("race","人类"); }',
            kind="effect",
        ),
        Postcondition(
            description="按种族分派对应 race daemon 的 setup_*方法",
            state_change="HUMAN_RACE->setup_human(ob) / MONSTER_RACE->setup_monster(ob) / ...",
            kind="effect",
        ),
        Postcondition(
            description="jing/qi/jingli 未定义时初始化为 max 值",
            state_change='if(undefinedp(my["jing"])) my["jing"]=my["max_jing"]; (qi/jingli 同理)',
            kind="effect",
        ),
        Postcondition(
            description="eff_jing/eff_qi 未定义或超过 max 时钳位到 max",
            state_change='if(undefinedp(my["eff_jing"]) || my["eff_jing"]>my["max_jing"]) my["eff_jing"]=my["max_jing"]',
            kind="effect",
        ),
        Postcondition(
            description="玩家内力上限钳位：max_neili <= force_skill * con * 2/3",
            state_change='if(userp && force>force_base) my["max_neili"] = min(my["max_neili"], force*con*2/3)',
            kind="effect",
        ),
        Postcondition(
            description="玩家精力上限钳位：max_jingli <= force_skill * con / 2（下限 100）",
            state_change='if(userp && force>force_base) my["max_jingli"] = min(my["max_jingli"], force*con/2); if(<100) =100',
            kind="effect",
        ),
        Postcondition(
            description="NPC 无 force 技能但有 max_neili 时自动设置 force = max_neili/6",
            state_change='if(!userp && my["max_neili"] && force<1) ob->set_skill("force", max_neili/6)',
            kind="effect",
        ),
        Postcondition(
            description="max_encumbrance 未设置时 = str*5000 + (query_str-str)*1000",
            state_change='if(!query_max_encumbrance()) set_max_encumbrance(str*5000 + (query_str()-str)*1000)',
            kind="effect",
        ),
        Postcondition(
            description="reset_action() 已调用（重新计算战斗动作集）",
            state_change="ob->reset_action()",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="jing <= eff_jing <= max_jing（qi 同理），setup_char 后保证此层次",
            lpc_expr="jing <= eff_jing <= max_jing; qi <= eff_qi <= max_qi",
            scope="class",
        ),
        Invariant(
            description="种族分派是互斥的：switch(race) 仅匹配一个 case，default 抛 error",
            lpc_expr='switch(race) { case "人类": ...; default: error("undefined race"); }',
            scope="function",
        ),
        Invariant(
            description="shen 未定义时：玩家 shen=0，NPC shen=shen_type*combat_exp/10",
            lpc_expr='if(undefinedp(my["shen"])) my["shen"] = userp(ob) ? 0 : shen_type*combat_exp/10',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="race 默认值：未设置时设为 '人类'",
            lpc_call='if(!stringp(race)) { race="人类"; ob->set("race", "人类"); }',
            target="ob.race",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="按种族分派 race daemon：HUMAN_RACE->setup_human(ob) 等",
            lpc_call="HUMAN_RACE->setup_human(ob) / MONSTER_RACE->setup_monster(ob) / ...",
            target="ob",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="jing/qi/jingli 未定义时初始化为 max 值",
            lpc_call='if(undefinedp(my["jing"])) my["jing"] = my["max_jing"]; (qi/jingli 同理)',
            target="ob.jing/qi/jingli",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="eff_jing/eff_qi 钳位到 max（未定义或超过时）",
            lpc_call='if(undefinedp(my["eff_jing"]) || my["eff_jing"]>my["max_jing"]) my["eff_jing"]=my["max_jing"]',
            target="ob.eff_jing/eff_qi",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="jiajin 未定义时设为 1",
            lpc_call='if(undefinedp(my["jiajin"])) my["jiajin"] = 1',
            target="ob.jiajin",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="玩家内力上限钳位：max_neili <= force*con*2/3",
            lpc_call='if(userp && force>force_base) { if(max_neili > force*con*2/3) max_neili = force*con*2/3; if(neili>max_neili) neili=max_neili; }',
            target="ob.max_neili/neili",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="玩家精力上限钳位：max_jingli <= force*con/2（下限 100）",
            lpc_call='if(userp && force>force_base) { if(max_jingli > force*con/2) max_jingli = force*con/2; if(jingli>max_jingli) jingli=max_jingli; if(max_jingli<100) max_jingli=100; }',
            target="ob.max_jingli/jingli",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="NPC 无 force 时自动设置 force = max_neili/6",
            lpc_call='if(!userp && my["max_neili"] && force<1) ob->set_skill("force", max_neili/6)',
            target="ob.skills.force",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.STATE_MUTATION,
            description="shen_type 未定义时设为 0；shen 未定义时按 userp/NPC 分别设置",
            lpc_call='if(undefinedp(my["shen_type"])) my["shen_type"]=0; if(undefinedp(my["shen"])) my["shen"] = userp ? 0 : shen_type*combat_exp/10',
            target="ob.shen_type/shen",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.STATE_MUTATION,
            description="behavior_exp = shen（未定义时）；quest_exp = age*10（未定义时）",
            lpc_call='if(undefinedp(my["behavior_exp"])) my["behavior_exp"]=my["shen"]; if(undefinedp(my["quest_exp"])) my["quest_exp"]=my["age"]*10',
            target="ob.behavior_exp/quest_exp",
        ),
        SideEffect(
            order=11,
            kind=SideEffectType.STATE_MUTATION,
            description="max_encumbrance 未设置时 = str*5000 + (query_str-str)*1000",
            lpc_call="if(!query_max_encumbrance()) set_max_encumbrance(str*5000 + (query_str()-str)*1000)",
            target="ob.max_encumbrance",
        ),
        SideEffect(
            order=12,
            kind=SideEffectType.EXTERNAL,
            description="reset_action() 重新计算战斗动作集",
            lpc_call="ob->reset_action()",
            target="ob",
        ),
    ],
    random_specs=[],
    notes=(
        "setup_char 是角色初始化的核心函数，由 setup() 调用（层 G）。"
        "按种族分派 race daemon 设置基础属性，然后执行属性钳位和默认值填充。"
        "内力/精力上限钳位仅对玩家生效（userp），NPC 有独立的 force 自动设置逻辑。"
        "cross_layer_refs: setup 属层 G，reset_action 属层 E。"
    ),
)

_break_relation = FunctionSpec(
    signature=FunctionSignature(
        name="break_relation",
        params=[
            LPCParam(name="player", lpc_type="object", description="解除师徒关系的玩家"),
        ],
        return_type="int",
        lpc_file="adm/daemons/chard.c",
        line_range=(173, 192),
    ),
    preconditions=[
        Precondition(
            description="player 是有效对象",
            lpc_expr="objectp(player)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="华山派弟子解除师徒关系：delete('family') + set('title', '普通百姓')",
            state_change='if(family=="华山派") { player->delete("family"); player->set("title","普通百姓"); }',
            kind="effect",
        ),
        Postcondition(
            description="风清扬 NPC 的 students 列表中删除此玩家 + 设置 pending 标记",
            state_change='ob->delete("students/"+std_id); ob->set("pending", std_id); ob->save()',
            kind="effect",
        ),
        Postcondition(
            description="非华山派弟子直接返回 1（无副作用）",
            return_value="1=已处理",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="break_relation 仅处理华山派风清扬的师徒关系，其他门派不受影响",
            lpc_expr='player->query("family/family_name") == "华山派"',
            scope="function",
        ),
        Invariant(
            description="风清扬 NPC 对象从 /d/huashan/xiaofang 房间查找",
            lpc_expr='room = find_object("/d/huashan/xiaofang") || load_object("/d/huashan/xiaofang")',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="查找/加载华山派小房间的风清扬 NPC",
            lpc_call='room = find_object("/d/huashan/xiaofang") || load_object("/d/huashan/xiaofang"); ob = present("feng qingyang", room)',
            target="room",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="player->delete('family') 删除门派信息",
            lpc_call='player->delete("family")',
            target="player.family",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="player->set('title', '普通百姓') 重设头衔",
            lpc_call='player->set("title", "普通百姓")',
            target="player.title",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="tell_object 输出 '你已非风清扬的弟子了，好自为之吧！'",
            lpc_call='tell_object(player, RED "\\n\\n你已非风清扬的弟子了，好自为之吧！\\n\\n" NOR)',
            target="player",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="风清扬 NPC: delete('students/'+id) + set('pending', id)",
            lpc_call='ob->delete("students/"+std_id); ob->set("pending", std_id)',
            target="feng_qingyang",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.PERSISTENCE,
            description="风清扬 NPC->save() 保存",
            lpc_call="ob->save()",
            target="feng_qingyang",
        ),
    ],
    random_specs=[],
    notes=(
        "break_relation 是死亡惩罚的一部分（层 F die() 中调用），专门处理华山派风清扬的师徒解除。"
        "cross_layer_refs: die 属层 F。"
    ),
)


# ---------------------------------------------------------------------------
# SECURITY_D 函数规格（securityd.c）
# ---------------------------------------------------------------------------

_valid_cmd = FunctionSpec(
    signature=FunctionSignature(
        name="valid_cmd",
        params=[
            LPCParam(name="file", lpc_type="string", description="命令文件路径"),
            LPCParam(name="user", lpc_type="mixed", description="调用者对象（通常为 this_player()）"),
            LPCParam(name="func", lpc_type="string", description="调用类型，必须为 'cmd_file'"),
        ],
        return_type="int",
        lpc_file="adm/daemons/securityd.c",
        line_range=(710, 772),
    ),
    preconditions=[
        Precondition(
            description="user 必须是对象（objectp），否则 error",
            lpc_expr="objectp(user)",
            kind="require",
        ),
        Precondition(
            description="func 必须为 'cmd_file'，否则返回 0（fail-closed）",
            lpc_expr='func == "cmd_file"',
            kind="input_constraint",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 1=允许执行命令，0=拒绝执行命令（fail-closed）",
            return_value="1=允许, 0=拒绝",
            kind="ensure",
        ),
        Postcondition(
            description="ROOT_UID 直接返回 1（最高权限）",
            state_change="if(euid==ROOT_UID) return 1",
            kind="effect",
        ),
        Postcondition(
            description="cmds/std/cmds/skill/cmds/usr 目录对所有玩家开放",
            state_change='if(dir=="cmds/std" || dir=="cmds/skill" || dir=="cmds/usr") return 1',
            kind="effect",
        ),
        Postcondition(
            description="exclude_cmds 命中的目录/用户返回 0（exclude 优先于 authorized）",
            state_change="if(member_array(euid/status, exclude_cmds[dir])!=-1) return 0",
            kind="effect",
        ),
        Postcondition(
            description="authorized_cmds 匹配的等级返回 1（如 cmds/adm 需 (admin)）",
            state_change="if(member_array(euid/status, authorized_cmds[dir])!=-1) return 1",
            kind="effect",
        ),
        Postcondition(
            description="所有检查未通过时记录 CMD_LOG 并返回 0",
            state_change='log_file("/static/CMD_LOG", ...); return 0',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="fail-closed：euid 为空时返回 0（拒绝），不得默认放行",
            lpc_expr="if(!euid) return 0",
            scope="function",
        ),
        Invariant(
            description="exclude 优先于 authorized：先检查 exclude_cmds，再检查 authorized_cmds",
            lpc_expr="exclude_cmds check before authorized_cmds check",
            scope="function",
        ),
        Invariant(
            description="权限检查按路径从深到浅遍历：file path 逐级向上检查目录权限",
            lpc_expr="for(i=sizeof(path)-1; i>=0; i--) { dir = implode(path[0..i], '/'); ... }",
            scope="function",
        ),
        Invariant(
            description="authorized_cmds 权限模型：cmds/adm=(admin), cmds/arch=(admin)+(arch), cmds/wiz=(admin)+(arch)+(wiz), cmds/imm=(admin)+(arch)+(wiz)+(imm)",
            scope="system",
        ),
        Invariant(
            description="valid_cmd 被 command_hook 每条命令调用（CLAUDE.md 架构不变量）",
            lpc_expr="command_hook -> valid_cmd(file, user, 'cmd_file')",
            scope="system",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="func != 'cmd_file' 时返回 0（fail-closed）",
            lpc_call='if(func != "cmd_file") return 0',
            target="return_value",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="获取 euid 和 status：euid=geteuid(user); status=get_status(user)",
            lpc_call="euid = geteuid(user); status = get_status(user)",
            target="euid.status",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="ROOT_UID 直接返回 1",
            lpc_call="if(euid == ROOT_UID) return 1",
            target="return_value",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="exclude_cmds 检查：命中返回 0",
            lpc_call="for(i=...) { if(member_array(euid, exclude_cmds[dir])!=-1) return 0; if(member_array(status, exclude_cmds[dir])!=-1) return 0; }",
            target="return_value",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="cmds/std/cmds/skill/cmds/usr 对所有玩家开放",
            lpc_call='if(dir=="cmds/std" || dir=="cmds/skill" || dir=="cmds/usr") return 1',
            target="return_value",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="authorized_cmds 匹配返回 1",
            lpc_call="if(member_array(euid/status, authorized_cmds[dir])!=-1) return 1",
            target="return_value",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.EXTERNAL,
            description="未通过时记录 CMD_LOG 日志并返回 0",
            lpc_call='log_file("/static/CMD_LOG", sprintf("%s(%s) cmds attempt on %s failed.\\n", ...)); return 0',
            target="log",
        ),
    ],
    random_specs=[],
    notes=(
        "valid_cmd 是命令权限校验的核心函数，被 command_hook（层 C）每条命令调用。"
        "fail-closed 设计：euid 为空或权限不匹配时返回 0。"
        "exclude 优先于 authorized：先排除再授权。"
        "cmds/std/cmds/skill/cmds/usr 是玩家通用命令目录，对所有玩家开放。"
        "CLAUDE.md 架构不变量：valid_cmd 每条命令都过。"
    ),
)

_valid_write = FunctionSpec(
    signature=FunctionSignature(
        name="valid_write",
        params=[
            LPCParam(name="file", lpc_type="string", description="文件路径"),
            LPCParam(name="user", lpc_type="mixed", description="调用者对象"),
            LPCParam(name="func", lpc_type="string", description="操作类型：write_file/save_object 等"),
        ],
        return_type="int",
        lpc_file="adm/daemons/securityd.c",
        line_range=(579, 639),
    ),
    preconditions=[
        Precondition(
            description="user 必须是对象（objectp），否则 error",
            lpc_expr="objectp(user)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 1=允许写入，0=拒绝写入（fail-closed）",
            return_value="1=允许, 0=拒绝",
            kind="ensure",
        ),
        Postcondition(
            description="LOG_DIR 下 write_file 操作直接允许",
            state_change='if(sscanf(file, LOG_DIR+"%*s") && func=="write_file") return 1',
            kind="effect",
        ),
        Postcondition(
            description="securityd.c/promote.c/purge.c/globals.h 文件禁止写入",
            state_change='if(file=="/adm/daemons/securityd.c" || ...) return 0',
            kind="effect",
        ),
        Postcondition(
            description="save_object 操作：clone 对象可写自己的存档文件",
            state_change='if(func=="save_object" && clonep(user) && file==query_save_file()) return 1',
            kind="effect",
        ),
        Postcondition(
            description="ROOT_UID 直接允许",
            state_change="if(euid==ROOT_UID) return 1",
            kind="effect",
        ),
        Postcondition(
            description="/u/<euid>/ 个人目录直接允许",
            state_change='if(sscanf(file, "/u/"+euid+"/%*s")) return 1',
            kind="effect",
        ),
        Postcondition(
            description="exclude_write 命中返回 0（优先于 trusted_write）",
            state_change="if(member_array(euid/status, exclude_write[dir])!=-1) return 0",
            kind="effect",
        ),
        Postcondition(
            description="trusted_write 匹配返回 1",
            state_change="if(member_array(euid/status, trusted_write[dir])!=-1) return 1",
            kind="effect",
        ),
        Postcondition(
            description="所有检查未通过时记录 WRITE_LOG 并返回 0",
            state_change='log_file("/static/WRITE_LOG", ...); return 0',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="fail-closed：euid 为空时返回 0",
            lpc_expr="if(!euid) return 0",
            scope="function",
        ),
        Invariant(
            description="exclude 优先于 trusted：先检查 exclude_write，再检查 trusted_write",
            lpc_expr="exclude_write check before trusted_write check",
            scope="function",
        ),
        Invariant(
            description="权限检查按路径从深到浅遍历",
            lpc_expr="for(i=sizeof(path)-1; i>=0; i--) { dir = implode(path[0..i], '/'); ... }",
            scope="function",
        ),
        Invariant(
            description="关键系统文件不可写：securityd.c/promote.c/purge.c/globals.h",
            lpc_expr='file == "/adm/daemons/securityd.c" || file == "/cmds/adm/promote.c" || ...',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="LOG_DIR 写操作直接允许",
            lpc_call='if(sscanf(file, LOG_DIR+"%*s") && func=="write_file") return 1',
            target="return_value",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="关键系统文件检查：securityd.c/promote.c/purge.c/globals.h 返回 0",
            lpc_call='if(file=="/adm/daemons/securityd.c" || ...) return 0',
            target="return_value",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="save_object 操作：clone 对象写自己存档文件时允许",
            lpc_call='if(func=="save_object" && clonep(user) && file==query_save_file()) return 1',
            target="return_value",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="获取 euid 和 status",
            lpc_call="euid = geteuid(user); status = get_status(user)",
            target="euid.status",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="ROOT_UID 直接允许",
            lpc_call="if(euid == ROOT_UID) return 1",
            target="return_value",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="/u/<euid>/ 个人目录直接允许",
            lpc_call='if(sscanf(file, "/u/" + euid + "/%*s")) return 1',
            target="return_value",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="exclude_write 检查：命中返回 0",
            lpc_call="for(i=...) { if(member_array(euid/status, exclude_write[dir])!=-1) return 0; }",
            target="return_value",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="trusted_write 检查：匹配返回 1",
            lpc_call="for(i=...) { if(member_array(euid/status, trusted_write[dir])!=-1) return 1; }",
            target="return_value",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.EXTERNAL,
            description="未通过时记录 WRITE_LOG 日志并返回 0",
            lpc_call='log_file("/static/WRITE_LOG", sprintf("%s %s(%s) write attempt on %s failed.\\n", ...)); return 0',
            target="log",
        ),
    ],
    random_specs=[],
    notes=(
        "valid_write 是文件写入权限校验的核心函数。"
        "exclude 优先于 trusted 的权限模型与 valid_cmd 一致。"
        "save_object 操作有特殊豁免：clone 对象可写自己的存档文件。"
        "关键系统文件（securityd.c/promote.c/purge.c/globals.h）永远不可写。"
    ),
)

_valid_read = FunctionSpec(
    signature=FunctionSignature(
        name="valid_read",
        params=[
            LPCParam(name="file", lpc_type="string", description="文件路径"),
            LPCParam(name="user", lpc_type="mixed", description="调用者对象"),
            LPCParam(name="func", lpc_type="string", description="操作类型：read_file/file_size 等"),
        ],
        return_type="int",
        lpc_file="adm/daemons/securityd.c",
        line_range=(642, 707),
    ),
    preconditions=[
        Precondition(
            description="user 必须是有效对象（非 null 时检查 objectp）",
            lpc_expr="!user || objectp(user)",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="返回 1=允许读取，0=拒绝读取（fail-closed）",
            return_value="1=允许, 0=拒绝",
            kind="ensure",
        ),
        Postcondition(
            description="file_size/stat 操作直接允许",
            state_change='if(func=="file_size" || func=="stat") return 1',
            kind="effect",
        ),
        Postcondition(
            description="/data/、/log/、/adm/etc/ 目录直接允许读取",
            state_change='if(sscanf(file, "/data/%*s") || sscanf(file, "/log/%*s") || sscanf(file, "/adm/etc/%*s")) return 1',
            kind="effect",
        ),
        Postcondition(
            description="adm/ 和 cmds/ 前缀的 euid 直接允许",
            state_change='if(sscanf(euid, "adm/%*s") || sscanf(euid, "cmds/%*s")) return 1',
            kind="effect",
        ),
        Postcondition(
            description="ROOT_UID 直接允许",
            state_change="if(euid==ROOT_UID) return 1",
            kind="effect",
        ),
        Postcondition(
            description="/u/<euid>/ 个人目录直接允许",
            state_change='if(sscanf(file, "/u/"+euid+"/%*s")) return 1',
            kind="effect",
        ),
        Postcondition(
            description="exclude_read 命中返回 0（优先于 trusted_read）",
            state_change="if(member_array(euid/status, exclude_read[dir])!=-1) return 0",
            kind="effect",
        ),
        Postcondition(
            description="trusted_read 匹配返回 1",
            state_change="if(member_array(euid/status, trusted_read[dir])!=-1) return 1",
            kind="effect",
        ),
        Postcondition(
            description="所有检查未通过时记录 READ_LOG 并返回 0",
            state_change='log_file("/static/READ_LOG", ...); return 0',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="fail-closed：euid 为空时 error + 返回 0",
            lpc_expr="if(!euid) { error(...); return 0; }",
            scope="function",
        ),
        Invariant(
            description="exclude 优先于 trusted：先检查 exclude_read，再检查 trusted_read",
            lpc_expr="exclude_read check before trusted_read check",
            scope="function",
        ),
        Invariant(
            description="/data/、/log/、/adm/etc/ 是公共可读目录",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="file_size/stat 操作直接允许",
            lpc_call='if(func=="file_size" || func=="stat") return 1',
            target="return_value",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="/data/、/log/、/adm/etc/ 目录直接允许",
            lpc_call='if(sscanf(file, "/data/%*s") || sscanf(file, "/log/%*s") || sscanf(file, "/adm/etc/%*s")) return 1',
            target="return_value",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="user 非对象时 error + 返回 0",
            lpc_call='if(!user || !objectp(user)) { error(...); return 0; }',
            target="return_value",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="获取 euid 和 status",
            lpc_call="euid = geteuid(user); status = get_status(user)",
            target="euid.status",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.STATE_MUTATION,
            description="adm/ 和 cmds/ 前缀的 euid 直接允许",
            lpc_call='if(sscanf(euid, "adm/%*s") || sscanf(euid, "cmds/%*s")) return 1',
            target="return_value",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.STATE_MUTATION,
            description="ROOT_UID 直接允许",
            lpc_call="if(euid == ROOT_UID) return 1",
            target="return_value",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.STATE_MUTATION,
            description="/u/<euid>/ 个人目录直接允许",
            lpc_call='if(sscanf(file, "/u/" + euid + "/%*s")) return 1',
            target="return_value",
        ),
        SideEffect(
            order=8,
            kind=SideEffectType.STATE_MUTATION,
            description="exclude_read 检查：命中返回 0",
            lpc_call="for(i=...) { if(member_array(euid/status, exclude_read[dir])!=-1) return 0; }",
            target="return_value",
        ),
        SideEffect(
            order=9,
            kind=SideEffectType.STATE_MUTATION,
            description="trusted_read 检查：匹配返回 1",
            lpc_call="for(i=...) { if(member_array(euid/status, trusted_read[dir])!=-1) return 1; }",
            target="return_value",
        ),
        SideEffect(
            order=10,
            kind=SideEffectType.EXTERNAL,
            description="未通过时记录 READ_LOG 日志并返回 0",
            lpc_call='log_file("/static/READ_LOG", sprintf(...)); return 0',
            target="log",
        ),
    ],
    random_specs=[],
    notes=(
        "valid_read 是文件读取权限校验。与 valid_write 相比更宽松："
        "/data/、/log/、/adm/etc/ 是公共可读目录，file_size/stat 操作不受限。"
        "exclude 优先于 trusted 的权限模型与 valid_write 一致。"
    ),
)

_get_status = FunctionSpec(
    signature=FunctionSignature(
        name="get_status",
        params=[
            LPCParam(name="ob", lpc_type="mixed", description="对象或 uid 字符串"),
        ],
        return_type="string",
        lpc_file="adm/daemons/securityd.c",
        line_range=(152, 165),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回对象的巫师等级字符串，如 '(player)'、'(admin)' 等",
            return_value="string: WizLevel 之一",
            kind="ensure",
        ),
        Postcondition(
            description="对象先取 euid 再查 wiz_status；字符串直接查",
            state_change="euid = objectp(ob) ? geteuid(ob)||getuid(ob) : ob",
            kind="effect",
        ),
        Postcondition(
            description="wiz_status 中有记录则返回记录值",
            state_change='if(!undefinedp(wiz_status[euid])) return wiz_status[euid]',
            kind="effect",
        ),
        Postcondition(
            description="wiz_status 中无记录但 euid 本身是 wiz_level 之一则返回 euid",
            state_change="if(member_array(euid, wiz_levels)!=-1) return euid",
            kind="effect",
        ),
        Postcondition(
            description="均不匹配时返回 '(player)'（默认最低等级）",
            state_change='return "(player)"',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="get_status 是权限校验的基础函数，被 valid_cmd/valid_write/valid_read 调用",
            scope="system",
        ),
        Invariant(
            description="未知 uid 默认为 '(player)'（最低权限，fail-closed 思路）",
            lpc_expr='return "(player)" (default)',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="获取 euid：对象取 geteuid||getuid，字符串直接使用",
            lpc_call="euid = objectp(ob) ? (geteuid(ob) || getuid(ob)) : ob",
            target="euid",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="查 wiz_status 映射",
            lpc_call='if(!undefinedp(wiz_status[euid])) return wiz_status[euid]',
            target="return_value",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="查 wiz_levels 数组",
            lpc_call="if(member_array(euid, wiz_levels) != -1) return euid",
            target="return_value",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="默认返回 '(player)'",
            lpc_call='return "(player)"',
            target="return_value",
        ),
    ],
    random_specs=[],
    notes="get_status 是 SECURITY_D 权限模型的基础函数，将 uid 映射到 WizLevel。",
)

_valid_wiz_login = FunctionSpec(
    signature=FunctionSignature(
        name="valid_wiz_login",
        params=[
            LPCParam(name="ob", lpc_type="mixed", description="巫师 uid 字符串或对象"),
            LPCParam(name="site", lpc_type="string", description="登录 IP 地址"),
        ],
        return_type="int",
        lpc_file="adm/daemons/securityd.c",
        line_range=(132, 149),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回 1=允许巫师登录，0=拒绝（IP 不在登记列表中）",
            return_value="1=允许, 0=拒绝",
            kind="ensure",
        ),
        Postcondition(
            description="wiz_sites 中无记录时返回 0（fail-closed）",
            state_change='if(undefinedp(wiz_sites[euid])) return 0',
            kind="effect",
        ),
        Postcondition(
            description="site 匹配 wiz_sites 中的正则模式时返回 1",
            state_change="if(sizeof(regexp(({site}), wiz_sites[euid]))==1) return 1",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="valid_wiz_login 是巫师登录的 IP 限制检查（xuy@XKX 添加）",
            scope="system",
        ),
        Invariant(
            description="wiz_sites 存储正则模式（如 '.*' 表示任意 IP），site 需匹配模式才允许",
            lpc_expr="sizeof(regexp(({site}), wiz_sites[euid])) == 1",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="获取 euid",
            lpc_call="euid = objectp(ob) ? (geteuid(ob)||getuid(ob)) : ob",
            target="euid",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="wiz_sites 无记录返回 0",
            lpc_call='if(undefinedp(wiz_sites[euid])) return 0',
            target="return_value",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="正则匹配 site 与 wiz_sites 模式",
            lpc_call='if(sizeof(regexp(({site}), wiz_sites[euid])) == 1) return 1',
            target="return_value",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="不匹配返回 0",
            lpc_call="return 0",
            target="return_value",
        ),
    ],
    random_specs=[],
    notes="valid_wiz_login 是巫师登录 IP 白名单校验，在 get_id 阶段调用。",
)

_set_status = FunctionSpec(
    signature=FunctionSignature(
        name="set_status",
        params=[
            LPCParam(name="ob", lpc_type="mixed", description="对象或 uid 字符串"),
            LPCParam(name="status", lpc_type="string", description="巫师等级字符串"),
            LPCParam(name="sites", lpc_type="string", description="允许登录的 IP 正则"),
            LPCParam(name="promoter", lpc_type="string", description="操作者（提升者）"),
        ],
        return_type="int",
        lpc_file="adm/daemons/securityd.c",
        line_range=(178, 212),
    ),
    preconditions=[
        Precondition(
            description="调用者必须为 ROOT_UID（geteuid(previous_object())==ROOT_UID）",
            lpc_expr='geteuid(previous_object()) == ROOT_UID',
            kind="require",
        ),
        Precondition(
            description="若 /cmds/adm/promote 存在，调用者必须为 promote 命令本身",
            lpc_expr='if(find_object("/cmds/adm/promote")) previous_object() == find_object("/cmds/adm/promote")',
            kind="guard",
        ),
    ],
    postconditions=[
        Postcondition(
            description="status='(player)' 时删除 wiz_status 和 wiz_sites 中的记录",
            state_change='if(status=="(player)") { map_delete(wiz_status, uid); map_delete(wiz_sites, uid); }',
            kind="effect",
        ),
        Postcondition(
            description="其他 status 时写入 wiz_status[uid]=status，sites 非空时写入 wiz_sites",
            state_change='wiz_status[uid] = status; if(sites) wiz_sites[uid] = sites; else if(undefinedp) wiz_sites[uid] = ".*"',
            kind="effect",
        ),
        Postcondition(
            description="记录 promotion_log 日志（uid/status/sites/promoter/时间）",
            state_change='log_file("/static/promotion_log", ...)',
            kind="effect",
        ),
        Postcondition(
            description="save() 持久化权限数据",
            state_change="save()",
            kind="effect",
        ),
        Postcondition(
            description="成功返回 1，权限不足返回 0",
            return_value="1=成功, 0=权限不足",
            kind="ensure",
        ),
    ],
    invariants=[
        Invariant(
            description="set_status 是巫师等级管理的唯一入口，仅 ROOT_UID 或 promote 命令可调用",
            lpc_expr='geteuid(previous_object()) == ROOT_UID',
            scope="function",
        ),
        Invariant(
            description="降为 '(player)' 时同时清除 IP 白名单记录",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="ROOT_UID 权限检查",
            lpc_call='if(geteuid(previous_object()) != ROOT_UID) return 0',
            target="return_value",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="promote 命令检查（若存在）",
            lpc_call='if(find_object("/cmds/adm/promote") && previous_object() != find_object("/cmds/adm/promote")) return 0',
            target="return_value",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="status='(player)' 时删除记录",
            lpc_call='if(status == "(player)") { map_delete(wiz_status, uid); map_delete(wiz_sites, uid); }',
            target="wiz_status.wiz_sites",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.STATE_MUTATION,
            description="其他 status 时写入 wiz_status 和 wiz_sites",
            lpc_call='wiz_status[uid] = status; if(sites) wiz_sites[uid] = sites; else if(undefinedp(wiz_sites[uid])) wiz_sites[uid] = ".*"',
            target="wiz_status.wiz_sites",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.EXTERNAL,
            description="记录 promotion_log 日志",
            lpc_call='log_file("/static/promotion_log", capitalize(uid) + " become a " + status + " with access ip: " + sites + " on " + ctime(time()) + " by " + promoter + ". \\n")',
            target="log",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.PERSISTENCE,
            description="save() 持久化",
            lpc_call="save()",
            target="securityd",
        ),
    ],
    random_specs=[],
    notes="set_status 是巫师等级管理函数，由 promote 命令调用。有严格的 ROOT_UID 权限检查。",
)


# ---------------------------------------------------------------------------
# NATURE_D 函数规格（natured.c）
# ---------------------------------------------------------------------------

_update_day_phase = FunctionSpec(
    signature=FunctionSignature(
        name="update_day_phase",
        params=[],
        return_type="void",
        lpc_file="adm/daemons/natured.c",
        line_range=(54, 77),
    ),
    preconditions=[
        Precondition(
            description="NATURE_D 已初始化（create() 已调用，day_phase 已加载）",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="current_day_phase 递增到下一个阶段（模 sizeof(day_phase)）",
            state_change="current_day_phase = (++current_day_phase) % sizeof(day_phase)",
            kind="effect",
        ),
        Postcondition(
            description="向所有户外玩家输出时段切换消息（message('outdoor:vision', ...)）",
            state_change='message("outdoor:vision", day_phase[current_day_phase]["time_msg"]+"\\n", users())',
            kind="effect",
        ),
        Postcondition(
            description="若该阶段有 event_fun 则调用对应事件函数（如 event_sunrise）",
            state_change='if(!undefinedp(day_phase[current_day_phase]["event_fun"])) call_other(this_object(), event_fun)',
            kind="effect",
        ),
        Postcondition(
            description="event_common() 已调用（通用定时事件）",
            state_change="this_object()->event_common()",
            kind="effect",
        ),
        Postcondition(
            description="安排下一次 update_day_phase 的 call_out（延迟 = 下一阶段长度）",
            state_change='call_out("update_day_phase", day_phase[current_day_phase]["length"])',
            kind="effect",
        ),
        Postcondition(
            description="current_day_phase 回绕到 0 时重新 init_day_phase() 同步时间",
            state_change="if(current_day_phase==0) { init_day_phase(); synchronize=1; }",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="真实 1 秒 = 游戏 1 分钟（TIME_TICK = time()*60），call_out 延迟以游戏分钟为单位",
            lpc_expr="TIME_TICK = time() * 60; call_out delay in game minutes",
            scope="system",
        ),
        Invariant(
            description="8 个日间阶段循环：凌晨(240)->日出(120)->上午(180)->正午(180)->下午(180)->傍晚(180)->夜晚(120)->午夜(240)",
            lpc_expr="sizeof(day_phase) == 8",
            scope="system",
        ),
        Invariant(
            description="时段切换消息仅发送给户外（outdoor:vision）玩家",
            lpc_expr='message("outdoor:vision", ...)',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.CALL_OUT,
            description="remove_call_out('update_day_phase') 取消旧的定时器",
            lpc_call='remove_call_out("update_day_phase")',
            target="call_out_queue",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="current_day_phase==0 时 init_day_phase() 重新同步 + synchronize=1",
            lpc_call='if(current_day_phase==0) { init_day_phase(); synchronize = 1; }',
            target="current_day_phase",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.STATE_MUTATION,
            description="current_day_phase 递增取模",
            lpc_call="current_day_phase = (++current_day_phase) % sizeof(day_phase)",
            target="current_day_phase",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.CALL_OUT,
            description="非 synchronize 时安排下一次 update_day_phase",
            lpc_call='if(!synchronize) call_out("update_day_phase", day_phase[current_day_phase]["length"])',
            target="call_out_queue",
        ),
        SideEffect(
            order=5,
            kind=SideEffectType.MESSAGE_OUTPUT,
            description="向户外玩家输出时段切换消息",
            lpc_call='message("outdoor:vision", day_phase[current_day_phase]["time_msg"] + "\\n", users())',
            target="outdoor_users",
        ),
        SideEffect(
            order=6,
            kind=SideEffectType.EXTERNAL,
            description="若该阶段有 event_fun 则调用对应事件函数（event_sunrise/event_dawn 等）",
            lpc_call='if(!undefinedp(day_phase[current_day_phase]["event_fun"])) call_other(this_object(), day_phase[current_day_phase]["event_fun"])',
            target="this_object",
        ),
        SideEffect(
            order=7,
            kind=SideEffectType.EXTERNAL,
            description="event_common() 通用定时事件",
            lpc_call="this_object()->event_common()",
            target="this_object",
        ),
    ],
    random_specs=[],
    notes=(
        "update_day_phase 是 NATURE_D 时间系统的核心循环函数。"
        "真实 1 秒 = 游戏 1 分钟，8 个日间阶段循环。"
        "每个阶段切换时输出消息 + 调用对应 event_fun + event_common。"
    ),
)

_event_sunrise = FunctionSpec(
    signature=FunctionSignature(
        name="event_sunrise",
        params=[],
        return_type="void",
        lpc_file="adm/daemons/natured.c",
        line_range=(83, 97),
    ),
    preconditions=[
        Precondition(
            description="NATURE_D 已初始化，update_day_phase 触发了 sunrise 阶段",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="所有在线玩家的 link_ob 和 body 均已 save()（自动保存）",
            state_change="for each online player: link_ob->save(); body->save()",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="event_sunrise 是全局自动保存的触发点（每日日出时触发）",
            scope="system",
        ),
        Invariant(
            description="JSON 存档崩溃安全（CLAUDE.md 架构不变量）：Python 实现需用 write-temp + os.replace 原子写",
            lpc_expr="write-temp + os.replace (Python impl); NOT LPC save_object 全量覆盖",
            scope="system",
        ),
        Invariant(
            description="仅对有 link_ob 的在线玩家执行 save（link_ob 和 body 双重保存）",
            lpc_expr='if(objectp(link_ob = ob[i]->query_temp("link_ob"))) { link_ob->save(); ob[i]->save(); }',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="遍历 users() 获取所有在线玩家",
            lpc_call="ob = users()",
            target="users",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.PERSISTENCE,
            description="对每个有 link_ob 的玩家：link_ob->save() 保存连接对象",
            lpc_call='for(i=0; i<sizeof(ob); i++) if(objectp(link_ob = ob[i]->query_temp("link_ob"))) link_ob->save()',
            target="link_ob",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.PERSISTENCE,
            description="对每个有 link_ob 的玩家：ob[i]->save() 保存角色 body",
            lpc_call="ob[i]->save()",
            target="body",
        ),
    ],
    random_specs=[],
    notes=(
        "event_sunrise 是全局自动保存的触发点，每日日出阶段由 update_day_phase 调用。"
        "同时保存 link_ob 和 body 两份数据。"
        "CLAUDE.md 架构不变量：JSON 存档崩溃安全，Python 实现需原子写。"
    ),
)

_event_common = FunctionSpec(
    signature=FunctionSignature(
        name="event_common",
        params=[],
        return_type="void",
        lpc_file="adm/daemons/natured.c",
        line_range=(100, 142),
    ),
    preconditions=[
        Precondition(
            description="NATURE_D 已初始化，由 update_day_phase 触发",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="无环境的 NPC 被 destruct；无环境的玩家被 move 到 /d/city/wumiao.c",
            state_change="if(!where) { !userp ? destruct(ob[i]) : ob[i]->move('/d/city/wumiao.c'); }",
            kind="effect",
        ),
        Postcondition(
            description="所有在线玩家执行 UPDATE_D->inventory_check（物品检查）",
            state_change="UPDATE_D->inventory_check(ob[i])",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="event_common 在每个时段切换时调用，执行清理和物品检查",
            scope="system",
        ),
        Invariant(
            description="无环境的 living 对象被清理：NPC destruct，玩家移到安全房间",
            lpc_expr='if(!where||!objectp(where)) { !userp(ob[i]) ? destruct(ob[i]) : ob[i]->move("/d/city/wumiao.c"); }',
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="遍历 livings() 获取所有 living 对象",
            lpc_call="ob = livings()",
            target="livings",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="无环境的 NPC 被 destruct",
            lpc_call='if(!where) { if(!userp(ob[i])) destruct(ob[i]); }',
            target="npc",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.OBJECT_LIFECYCLE,
            description="无环境的玩家被 move 到 /d/city/wumiao.c",
            lpc_call='else ob[i]->move("/d/city/wumiao.c")',
            target="player",
        ),
        SideEffect(
            order=4,
            kind=SideEffectType.EXTERNAL,
            description="遍历 users() 执行 UPDATE_D->inventory_check",
            lpc_call='for(count=sizeof(ob); count-->0;) { UPDATE_D->inventory_check(ob[i]); i=(i+1)%sizeof(ob); }',
            target="users",
        ),
    ],
    random_specs=[
        RandomSpec(
            lpc_call="random(sizeof(ob))",
            probability_model="1/sizeof(users()) 均匀分布选择起始玩家",
            semantic="inventory_check 遍历的起始索引随机选择",
            seed_inputs=["users()"],
            determinism_note="非战斗随机性，不影响 combat-only 确定性范围。",
        ),
    ],
    notes=(
        "event_common 是时段切换时的通用清理函数：清理无环境对象 + 物品检查。"
        "无环境的 NPC 直接 destruct，玩家移到安全房间（/d/city/wumiao.c）。"
        "UPDATE_D->inventory_check 属第二梯队守护进程，此处仅引用为副作用。"
    ),
)

_init_day_phase = FunctionSpec(
    signature=FunctionSignature(
        name="init_day_phase",
        params=[],
        return_type="void",
        lpc_file="adm/daemons/natured.c",
        line_range=(28, 52),
    ),
    preconditions=[
        Precondition(
            description="day_phase 表已通过 read_table 加载",
            kind="require",
        ),
    ],
    postconditions=[
        Postcondition(
            description="根据当前游戏时间计算 current_day_phase",
            state_change="local = localtime(TIME_TICK); t = local[2]*60 + local[1]; current_day_phase = ...",
            kind="effect",
        ),
        Postcondition(
            description="安排下一次 update_day_phase 的 call_out（延迟 = 下一阶段剩余长度）",
            state_change='call_out("update_day_phase", day_phase[(current_day_phase+1)%sizeof]["length"] - t)',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="TIME_TICK = time()*60：真实 1 秒 = 游戏 1 分钟",
            lpc_expr="TIME_TICK = time() * 60",
            scope="system",
        ),
        Invariant(
            description="init_day_phase 在 create() 和 current_day_phase 回绕到 0 时调用（时间同步）",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.STATE_MUTATION,
            description="获取当前游戏时间的时分：local = localtime(TIME_TICK); t = hour*60 + minute",
            lpc_call="local = localtime(TIME_TICK); t = local[2] * 60 + local[1]",
            target="t",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.STATE_MUTATION,
            description="计算 current_day_phase：遍历 day_phase 减去各阶段长度",
            lpc_call="for(i=0; i<sizeof(day_phase); i++) if(t >= day_phase[i]['length']) t -= day_phase[i]['length']; else break; current_day_phase = (i==0) ? sizeof-1 : i-1",
            target="current_day_phase",
        ),
        SideEffect(
            order=3,
            kind=SideEffectType.CALL_OUT,
            description="安排下一次 update_day_phase call_out",
            lpc_call='call_out("update_day_phase", day_phase[(current_day_phase+1)%sizeof(day_phase)]["length"] - t)',
            target="call_out_queue",
        ),
    ],
    random_specs=[],
    notes="init_day_phase 在 create() 和日阶段回绕时调用，同步当前日阶段并安排下一次切换。",
)

_game_time = FunctionSpec(
    signature=FunctionSignature(
        name="game_time",
        params=[],
        return_type="string",
        lpc_file="adm/daemons/natured.c",
        line_range=(154, 157),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回中文格式的游戏时间字符串",
            return_value="string: 中文干支日期时间",
            kind="ensure",
        ),
        Postcondition(
            description="时间基于 TIME_TICK = time()*60（真实 1 秒 = 游戏 1 分钟）",
            state_change="return CHINESE_D->chinese_date(TIME_TICK)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="game_time 委托 CHINESE_D->chinese_date 进行中文格式化",
            lpc_expr="CHINESE_D->chinese_date(TIME_TICK)",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="调用 CHINESE_D->chinese_date(TIME_TICK) 获取中文游戏时间",
            lpc_call="return CHINESE_D->chinese_date(TIME_TICK)",
            target="chinese_d",
        ),
    ],
    random_specs=[],
    notes="game_time 返回基于游戏时间（TIME_TICK = time()*60）的中文干支日期时间。",
)


# ---------------------------------------------------------------------------
# CHINESE_D 函数规格（chinesed.c）
# ---------------------------------------------------------------------------

_chinese_number = FunctionSpec(
    signature=FunctionSignature(
        name="chinese_number",
        params=[
            LPCParam(name="i", lpc_type="int", description="待转换的整数"),
        ],
        return_type="string",
        lpc_file="adm/daemons/chinesed.c",
        line_range=(37, 102),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回输入整数的中文数字表示字符串",
            return_value="string: 中文数字",
            kind="ensure",
        ),
        Postcondition(
            description="负数返回 '负' + 正数部分",
            state_change='if(i<0) return "负" + chinese_number(-i)',
            kind="effect",
        ),
        Postcondition(
            description="0-10 返回 c_num[i]（零一二三四五六七八九十）",
            state_change="if(i<11) return c_num[i]",
            kind="effect",
        ),
        Postcondition(
            description="11-19 返回 '十' + c_num[i-10]",
            state_change="if(i<20) return c_digit[1] + c_num[i-10]",
            kind="effect",
        ),
        Postcondition(
            description="支持百/千/万/亿/兆的递归转换，每四位一组",
            state_change="递归调用 chinese_number(i % unit) 处理余数",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="chinese_number 是确定性映射函数，无随机性",
            lpc_expr="no random() in chinese_number()",
            scope="function",
        ),
        Invariant(
            description="中文数字单位层次：个 < 十 < 百 < 千 < 万 < 亿 < 兆",
            lpc_expr="c_digit = {'零','十','百','千','万','亿','兆'}",
            scope="class",
        ),
        Invariant(
            description="零的处理：余数为零时省略（如 100 = 一百，不输出一百零）",
            lpc_expr="if(i%100==0) return c_num[i/100] + c_digit[2] (no trailing zero)",
            scope="function",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes=(
        "chinese_number 是纯函数，将整数递归转换为中文数字表示。"
        "支持负数、百千万亿兆等单位。被 LOGIN_D（在线人数显示）和 NATURE_D 等广泛调用。"
    ),
)

_chinese_date = FunctionSpec(
    signature=FunctionSignature(
        name="chinese_date",
        params=[
            LPCParam(name="date", lpc_type="int", description="时间戳（game time ticks）"),
        ],
        return_type="string",
        lpc_file="adm/daemons/chinesed.c",
        line_range=(141, 154),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="返回中文干支日期时间字符串，格式：'<天干><地支>年<月>月<日>日<地支>时<刻>刻'",
            return_value="string: 如 '甲子年一月初一日子时一刻'",
            kind="ensure",
        ),
        Postcondition(
            description="年干支由 LT_YEAR % 10/12 计算",
            state_change="sym_tian[year%10] + sym_di[year%12]",
            kind="effect",
        ),
        Postcondition(
            description="月 = chinese_number(LT_MON + 1)",
            state_change="chinese_number(local[LT_MON] + 1)",
            kind="effect",
        ),
        Postcondition(
            description="日 = chinese_number(LT_MDAY + (LT_HOUR>23 ? 1 : 0))",
            state_change="chinese_number(local[LT_MDAY] + (local[LT_HOUR] > 23 ? 1 : 0))",
            kind="effect",
        ),
        Postcondition(
            description="时辰 = sym_di[((LT_HOUR+1)%24)/2]（十二时辰）",
            state_change="sym_di[((local[LT_HOUR] + 1) % 24) / 2]",
            kind="effect",
        ),
        Postcondition(
            description="刻 = chinese_number((LT_MIN+1)%2*2 + LT_MIN/30 + 1)（一刻/二刻）",
            state_change="chinese_number((local[LT_MIN]+1) % 2 * 2 + local[LT_MIN] / 30 + 1)",
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="chinese_date 是确定性映射函数，无随机性",
            lpc_expr="no random() in chinese_date()",
            scope="function",
        ),
        Invariant(
            description="天干 10 个（甲乙丙丁戊己庚辛壬癸），地支 12 个（子丑寅卯辰巳午未申酉戌亥）",
            lpc_expr="sym_tian = {'甲','乙','丙','丁','戊','己','庚','辛','壬','癸'}; sym_di = {'子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥'}",
            scope="class",
        ),
        Invariant(
            description="时辰按十二地支划分：每 2 小时一个时辰，子时 = 23:00-01:00",
            lpc_expr="sym_di[((LT_HOUR + 1) % 24) / 2]",
            scope="function",
        ),
    ],
    side_effects=[
        SideEffect(
            order=1,
            kind=SideEffectType.EXTERNAL,
            description="localtime(date) 转换时间戳为本地时间数组",
            lpc_call="local = localtime(date)",
            target="local",
        ),
        SideEffect(
            order=2,
            kind=SideEffectType.EXTERNAL,
            description="sprintf 组装中文干支日期时间字符串",
            lpc_call='sprintf("%s%s年%s月%s日%s时%s刻", sym_tian[year%10], sym_di[year%12], chinese_number(mon+1), chinese_number(mday+...), sym_di[...], chinese_number(...))',
            target="return_value",
        ),
    ],
    random_specs=[],
    notes=(
        "chinese_date 将时间戳转换为中文干支日期时间。"
        "天干地支纪年（60 年一循环），十二时辰（每 2 小时一个时辰）。"
        "被 NATURE_D->game_time 调用，显示游戏内时间。"
    ),
)

_chinese = FunctionSpec(
    signature=FunctionSignature(
        name="chinese",
        params=[
            LPCParam(name="str", lpc_type="string", description="待翻译的英文字符串"),
        ],
        return_type="string",
        lpc_file="adm/daemons/chinesed.c",
        line_range=(109, 115),
    ),
    preconditions=[],
    postconditions=[
        Postcondition(
            description="dict 中有对应翻译时返回中文翻译",
            return_value="string: 中文翻译（如有）或原英文",
            kind="ensure",
        ),
        Postcondition(
            description="dict 中无记录时返回原字符串",
            state_change='if(undefinedp(dict[str])) return str',
            kind="effect",
        ),
    ],
    invariants=[
        Invariant(
            description="chinese 是英中翻译查询函数，使用 dict mapping（可通过 add_translate/remove_translate 修改）",
            scope="class",
        ),
        Invariant(
            description="dict 持久化存储（F_SAVE），可动态增删",
            scope="system",
        ),
    ],
    side_effects=[],
    random_specs=[],
    notes="chinese 是简单的字典查询函数，无副作用。dict 通过 add_translate/remove_translate 动态管理。",
)


# ---------------------------------------------------------------------------
# 层 H 规格集合
# ---------------------------------------------------------------------------

LAYER_SPEC = LayerSpec(
    layer_id="H",
    layer_name="核心守护进程",
    lpc_files=[
        "adm/daemons/logind.c",
        "adm/daemons/chard.c",
        "adm/daemons/securityd.c",
        "adm/daemons/natured.c",
        "adm/daemons/chinesed.c",
    ],
    function_specs=[
        # LOGIN_D
        _logon,
        _get_id,
        _get_passwd,
        _make_body,
        _enter_world,
        _reconnect,
        _check_legal_id,
        _check_legal_name,
        _random_gift,
        _init_new_player,
        # CHAR_D
        _setup_char,
        _break_relation,
        # SECURITY_D
        _valid_cmd,
        _valid_write,
        _valid_read,
        _get_status,
        _valid_wiz_login,
        _set_status,
        # NATURE_D
        _update_day_phase,
        _event_sunrise,
        _event_common,
        _init_day_phase,
        _game_time,
        # CHINESE_D
        _chinese_number,
        _chinese_date,
        _chinese,
    ],
    cross_layer_refs=[
        "command_hook / find_command / enable_player (层 C: command) -- valid_cmd 被 command_hook 每条命令调用",
        "setup (层 G: NPC AI) -- enter_world 调 user->setup() 启动 heart_beat + enable_player + setup_char",
        "set_heart_beat (层 A: driver) -- setup 中调用",
        "exec (层 A: driver) -- enter_world/reconnect 中连接转移",
        "destruct / new (层 A: driver) -- logon/get_id 中连接对象销毁，make_body 中 clone body",
        "save / restore (层 B: F_SAVE) -- 登录流程中的存档恢复",
        "set / query / set_temp / delete (层 B: F_DBASE) -- 状态读写",
        "move (层 B: F_MOVE) -- enter_world 中移到起始房间",
        "message / tell_room / tell_object (层 B: F_MESSAGE) -- 消息输出",
        "set_name / set_short / set_long (层 B: F_DBASE) -- make_body 中设置角色名称",
        "reset_action (层 E: combat) -- setup_char 中重新计算战斗动作集",
        "die / unconcious / make_corpse (层 F: 死亡轮回) -- break_relation 被 die 调用",
        "CHANNEL_D->do_channel (第二梯队守护进程) -- enter_world/reconnect 中系统频道广播",
        "UPDATE_D->login_check / inventory_check (第二梯队守护进程) -- enter_world/event_common 中引用",
        "BAN_D / REGBAN_D (第二梯队守护进程) -- logon/get_id 中 IP 封禁检查",
        "MARRY_D->validate_marriage (第二梯队守护进程) -- enter_world 中婚姻检查",
        "create_human_body (race daemon) -- init_new_player 中种族初始化",
        "CHINESE_D->chinese_date (本层) -- NATURE_D->game_time 调用",
        "CHINESE_D->chinese_number (本层) -- LOGIN_D confirm_big5 中在线人数显示",
    ],
    notes=(
        "层 H 覆盖 5 个核心守护进程的函数级规格契约：\n"
        "\n"
        "1. LOGIN_D（10 个函数）：logon 连接入口 -> get_id 英文名校验 -> get_passwd 密码验证 -> "
        "make_body 创建 body -> enter_world 进入世界。重连路径：get_passwd -> find_body -> reconnect。"
        "新角色路径：get_id -> confirm_id -> get_name -> new_password -> confirm_password -> "
        "get_gift -> get_email -> get_gender -> make_body -> init_new_player -> enter_world。\n"
        "状态机共 12 个阶段（LoginState 枚举），从 LOGON 到 ENTER_WORLD/RECONNECT。\n"
        "\n"
        "2. CHAR_D（2 个函数）：setup_char 角色属性初始化（种族分派 + 属性钳位 + 默认值填充），"
        "break_relation 华山派师徒解除。make_corpse 属层 F 已提取。\n"
        "\n"
        "3. SECURITY_D（6 个函数）：valid_cmd 命令权限校验（fail-closed，每条命令都过），"
        "valid_write/valid_read 文件读写权限，get_status 权限查询，"
        "valid_wiz_login 巫师 IP 校验，set_status 巫师等级管理。\n"
        "权限模型：exclude 优先于 trusted，ROOT_UID 直接放行，未知 uid 默认 (player)。\n"
        "WizLevel 10 级层次：(player) < (immortal) < ... < (admin)。\n"
        "\n"
        "4. NATURE_D（5 个函数）：时间推进（真实 1 秒 = 游戏 1 分钟），"
        "update_day_phase 8 阶段循环，event_sunrise 全局自动保存触发，"
        "event_common 通用清理 + 物品检查，init_day_phase 时间同步，game_time 中文时间显示。\n"
        "\n"
        "5. CHINESE_D（3 个函数）：chinese_number 数字转中文，chinese_date 日期转干支，"
        "chinese 英中翻译查询。均为确定性映射函数，无随机性。\n"
        "\n"
        "关键不变量：\n"
        "- valid_cmd fail-closed（CLAUDE.md 架构不变量）\n"
        "- NATURE_D 时间系统：真实 1 秒 = 游戏 1 分钟（ADR-0010）\n"
        "- JSON 存档崩溃安全：event_sunrise 触发自动保存，Python 需原子写\n"
        "- LOGIN_D 状态机完整性：从连接到进入游戏的完整流程\n"
        "- SECURITY_D 权限模型：exclude 优先于 trusted，ROOT_UID 放行\n"
        "\n"
        "边界：CHANNEL_D/MONEY_D/UPDATE_D/RANK_D 属第二梯队，任务 1 完成后按需提取。"
        "ANSI/TELNET 协议细节后置。securityd.c 的权限表不逐条提取，仅提取权限模型契约。"
    ),
)
