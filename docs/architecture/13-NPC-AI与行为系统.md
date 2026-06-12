# 13. NPC AI 与行为系统

NPC（Non-Player Character，非玩家角色）是《侠客行》MUD 游戏世界的灵魂，它们构成了江湖中的师父、商人、守卫、野兽、任务发布者等丰富角色。本章将深入剖析 NPC 的继承架构、行为驱动机制、交互系统以及生成管理方式。

---

## 1. NPC 基础架构

### 1.1 继承链与核心模块

在 LPC 的继承体系中，NPC 的根基可以追溯到 `/inherit/char/char.c`，但开发者通常直接继承 `/inherit/char/npc.c`。完整的继承链如下：

```
npc.c
  ├── inherit CHARACTER     (/inherit/char/char.c)
  │     ├── F_ACTION        动作执行
  │     ├── F_ALIAS         指令别名
  │     ├── F_APPRENTICE    师徒关系
  │     ├── F_ATTACK        战斗系统
  │     ├── F_ATTRIBUTE     人物属性
  │     ├── F_COMMAND       指令解析
  │     ├── F_CONDITION     状态效果
  │     ├── F_DAMAGE        伤害计算
  │     ├── F_DBASE         数据属性系统
  │     ├── F_EDIT          编辑功能
  │     ├── F_FINANCE       财务系统
  │     ├── F_MARRY         婚姻系统
  │     ├── F_MESSAGE       消息系统
  │     ├── F_MORE          分页显示
  │     ├── F_MOVE          移动系统
  │     ├── F_NAME          姓名系统
  │     ├── F_SKILL         武功技能
  │     └── F_TEAM          队伍系统
  └── inherit F_CLEAN_UP    清理机制
```

`char.c` 是所有角色的公共基类，无论是玩家还是 NPC 都继承自它。它通过 `setup()` 启动 `heart_beat`，并整合了武功、战斗、属性、师徒等数十个功能模块。`npc.c` 则在 `char.c` 的基础上进一步封装了 NPC 特有的行为逻辑，如 `random_move()`、`chat()`、`carry_object()` 等。

### 1.2 NPC 与玩家的本质区别

NPC 与玩家对象虽然共享同一套 `char.c` 基类，但存在几个关键差异：

1. **交互性差异**：玩家对象具有 `interactive()` 返回值为真的特性，表示有真实玩家连接；NPC 则没有。`heart_beat()` 中通过 `userp(this_object())` 和 `interactive(this_object())` 来区分处理逻辑。

2. **生命周期管理**：玩家的生命周期由登录/登出控制，而 NPC 由房间的 `reset()` 和驱动器的 `clean_up()` 机制管理。当房间内没有玩家时，NPC 的 `heart_beat` 会逐渐停止以节省 CPU。

3. **AI 驱动方式**：玩家的行为由真实玩家输入指令驱动；NPC 的行为则由 `heart_beat()` 定期触发，或通过 `init()` 在玩家进入房间时触发。

4. **数据持久化**：玩家数据通过存档系统持久化；普通 NPC 在销毁后数据即丢失，但特殊 NPC（如随从 `/clone/npc/suicong.c`）可以通过 `F_SAVE` 实现持久化存储。

### 1.3 NPC 的 dbase 属性体系

NPC 的属性存储依托于 `F_DBASE`（`/feature/dbase.c`），这是一个基于 `mapping` 的键值对系统，支持嵌套路径访问。核心 API 包括：

```c
mixed set(string prop, mixed data);      // 设置属性
varargs mixed query(string prop, int raw); // 查询属性
mixed add(string prop, mixed data);      // 数值累加
int delete(string prop);                 // 删除属性
```

NPC 的典型 dbase 属性可分为以下几类：

- **基础信息**：`name`（姓名）、`id`（标识）、`gender`（性别）、`age`（年龄）、`long`（描述）
- **战斗属性**：`str`、`int`、`con`、`dex`、`kar`（先天属性），`max_qi`、`max_jing`、`max_neili`、`max_jingli`（气血内力上限）
- **行为属性**：`attitude`（态度，如 `peaceful`、`aggressive`、`heroism`、`killer`、`friendly`）、`chat_chance`（闲聊概率）、`chat_msg`（闲聊内容）
- **社会关系**：`family`（门派信息，包含 `family_name`、`master_id`、`generation` 等）、`title`（头衔）
- **位置信息**：`startroom`（出生房间），用于 `reset()` 后让 NPC 返回原位

dbase 还支持 `set_temp()` / `query_temp()` 存储临时数据（如 `tmp_dbase`），这些数据不会持久化，适合存储战斗中的临时状态。

---

## 2. NPC 行为模式

### 2.1 heart_beat 机制

`heart_beat` 是 MudOS/FluffOS 驱动器提供的定时回调机制，默认每秒触发一次。在 `/inherit/char/char.c` 中，`heart_beat()` 承担了 NPC 和玩家的核心驱动逻辑：

```c
void heart_beat()
{
    // 1. 玩家专属：清理指令计数、频道发言限制
    if( userp(this_object()) ) { ... }

    // 2. 上限检查：防止内力、精力等异常膨胀
    if( my["neili"] > my["max_neili"]*2 ) { ... }

    // 3. 濒死与昏迷处理
    if( my["eff_qi"] < 0 || my["eff_jing"] < 0) { die(); return; }
    if( my["qi"] < 0 || my["jing"] < 0 ) { unconcious(); return; }

    // 4. 战斗循环
    if( is_busy() ) {
        continue_action();
        return;
    } else {
        if( is_fighting() && 需要逃跑 ) GO_CMD->do_flee(this_object());
        attack();  // 执行攻击
    }

    // 5. NPC 专属：调用 chat()
    if( !userp(this_object()) ) {
        this_object()->chat();
        if( !this_object() ) return;  // chat() 可能销毁对象
    }

    // 6. 条件更新与心跳优化
    if( tick-- ) return;
    else tick = 5 + random(10);
    cnd_flag = update_condition();

    // 7. 非战斗、非交互状态下停止 heart_beat 以节省资源
    if( ((cnd_flag & CND_NO_HEAL_UP) || !heal_up())
        && !is_fighting() && !interactive(this_object()) ) {
        if( 房间内没有玩家 ) set_heart_beat(0);
    }
}
```

关键设计要点：

- `tick` 变量引入了一个 5~15 秒的慢速周期，用于 `update_condition()`（状态效果更新）和 `heal_up()`（自然恢复），避免每秒执行这些开销较大的操作。
- 当 NPC 不战斗、不交互且周围没有玩家时，`heart_beat` 会自动停止。一旦玩家进入房间，驱动器会重新激活它。
- 战斗优先级最高：如果 NPC 处于 `busy` 状态（执行复杂动作中），则只推进动作进度；否则检查是否需要逃跑，然后执行 `attack()`。

### 2.2 random_move：NPC 的随机移动

`random_move()` 是 `npc.c` 提供的默认移动行为，通常被放入 `chat_msg` 中作为函数指针调用：

```c
int random_move()
{
    mapping exits, doors;
    string *dirs, dir;

    if( !objectp(environment()) 
        || !mapp(exits = environment()->query("exits")) 
        || query("jingli") < query("max_jingli") / 2 ) return 0;

    dirs = keys(exits);
    if( this_object()->query("race") == "人类"
        && mapp(doors = environment()->query_doors()) ) {
        dirs += keys(doors);
    }
    if( sizeof(dirs) == 0 ) return 0;

    dir = dirs[random(sizeof(dirs))];
    if ( mapp(doors) && !undefinedp(doors[dir])
      && (doors[dir]["status"] & DOOR_CLOSED) )
        command("open " + dir);
    command("go " + dir);
    return 1;
}
```

这个机制让 NPC 可以在房间之间随机游荡。值得注意的是：

- 人类 NPC 会尝试开门（`command("open " + dir)`），而野兽不会。
- 精力低于一半时停止随机移动，模拟疲劳状态。
- 如果移动方向是门且门关闭，NPC 会尝试打开它。

### 2.3 chat_chance / chat_msg：NPC 的随机对话

`chat()` 函数是 NPC 行为的核心调度器，在 `heart_beat()` 中被调用。它同时负责**自动恢复**和**随机对话**：

```c
int chat()
{
    string *msg;
    int chance, rnd;

    if( !environment() || !living(this_object()) ) return 0;

    // 自动恢复：内力充足时自动运功疗伤
    if ( query("neili") > 100 && living(this_object()) ) {
        if( (int)query("jingli")*100/(int)query("max_jingli") < 90 )
            SKILL_D("force")->exert_function(this_object(), "refresh");
        if( (int)query("qi")*100/((int)query("eff_qi")+2) < 80 )
            SKILL_D("force")->exert_function(this_object(), "recover");
        if( (int)query("jing")*100/((int)query("eff_jing")+2) < 70 )
            SKILL_D("force")->exert_function(this_object(), "regenerate");
    }

    // 随机对话/行为
    if( !chance = (int)query(is_fighting()? "chat_chance_combat": "chat_chance") )
        return 0;

    if( arrayp(msg = query(is_fighting()? "chat_msg_combat": "chat_msg"))) {
        if( random(100) < chance && sizeof(msg) ) {
            rnd = random(sizeof(msg));
            if( stringp(msg[rnd]) )
                say(msg[rnd]);
            else if( functionp(msg[rnd]) )
                return evaluate(msg[rnd]);
        }
        return 1;
    }
}
```

关键特性：

- **双模式对话**：NPC 支持平时（`chat_chance` / `chat_msg`）和战斗中（`chat_chance_combat` / `chat_msg_combat`）两套对话体系。
- **内容多样性**：`chat_msg` 可以是字符串（直接说出），也可以是函数指针（如 `(: this_object(), "random_move" :)`），后者让 NPC 执行复杂行为。
- **自动恢复内置**：这是 NPC 相比玩家的巨大优势——它们会在 `chat()` 中自动运功恢复精力、气血、精神，不需要玩家手动操作。

示例——野狗的随机行为（`/d/city/npc/dog.c`）：

```c
set("chat_chance", 6);
set("chat_msg", ({
    (: this_object(), "random_move" :),   // 函数指针：随机移动
    "野狗用鼻子闻了闻你的脚。\n",
    "野狗在你的脚边挨挨擦擦的，想讨东西吃。\n",
    "野狗对著你摇了摇尾巴。\n",
    "野狗用後腿抓了抓自己的耳朵。\n"
}) );
```

### 2.4 NPC 的战斗行为

NPC 的战斗行为分散在多个模块中协同工作：

#### 2.4.1 自动反击与主动攻击

`/feature/attback.c`（实际文件名为 `attack.c`）定义了战斗的核心机制。其中 `init()` 函数是 NPC 自动攻击的关键：

```c
void init()
{
    object ob;
    string vendetta_mark;

    // 前置条件过滤：自己正在战斗、对方不是玩家、已死亡等
    if( is_fighting() || !living(this_object()) || !(ob = this_player()) )
        return;

    // 情况 1：NPC 正在追杀该玩家（kill_ob 标记）
    if( userp(ob) && is_killing(ob->query("id")) ) {
        COMBAT_D->auto_fight(this_object(), ob, "hatred");
        return;
    }
    // 情况 2：NPC 对该门派有世仇（vendetta）
    else if( stringp(vendetta_mark = query("vendetta_mark"))
        && ob->query("vendetta/" + vendetta_mark) ) {
        COMBAT_D->auto_fight(this_object(), ob, "vendetta");
        return;
    }
    // 情况 3：NPC 态度为 aggressive，主动挑衅玩家
    else if( userp(ob) && (string)query("attitude")=="aggressive" ) {
        COMBAT_D->auto_fight(this_object(), ob, "aggressive");
        return;
    }
}
```

`init()` 是 MudOS 驱动器在对象被移动到同一环境时自动调用的函数。当玩家进入 NPC 所在房间时，`init()` 会被触发，NPC 根据预设条件决定是否主动攻击。

#### 2.4.2 战斗中的攻击循环

在 `heart_beat()` 中，`attack()` 函数负责执行实际攻击：

```c
int attack()
{
    object opponent;
    clean_up_enemy();              // 清理已死亡或离开的对手
    opponent = select_opponent();  // 从 enemy 数组中随机选择对手
    if( objectp(opponent) ) {
        set_temp("last_opponent", opponent);
        if( !this_object()->query_temp("yield") )
            COMBAT_D->fight(this_object(), opponent);
        return 1;
    } else
        return 0;
}
```

NPC 同时最多面对 `MAX_OPPONENT`（4 个）敌人，`select_opponent()` 会随机选择其中一个作为当前攻击目标。

#### 2.4.3 accept_fight 与 accept_kill

`npc.c` 中定义了 NPC 对 `fight` 和 `kill` 指令的响应：

```c
int accept_fight(object who)
{
    string att;
    att = query("attitude");

    if( is_fighting() ) {
        switch(att) {
            case "heroism":
                command("say 哼！出招吧！\n");
                break;
            default:
                command("say 想倚多为胜，这不是欺人太甚吗！\n");
                return 0;  // 拒绝以多打少
        }
    }

    // 状态良好时才接受切磋
    if( (int)query("jing") * 100 / (int)query("max_jing") >= 90
    &&  (int)query("qi") * 100 / (int)query("max_qi") >= 90
    &&  (int)query("jingli") * 100 / (int)query("max_jingli") >= 90 ) {
        switch(att) {
            case "friendly": return 0;  // 友好型 NPC 拒绝切磋
            case "aggressive":
            case "killer":
                command("say 哼！出招吧！\n");
                break;
            default:
                command("say 既然...只好奉陪。\n");
        }
        return 1;
    } else
        return 0;  // 状态不佳时拒绝
}

int accept_kill(object who)
{
    return 1;  // 默认接受生死相搏
}
```

NPC 的 `attitude` 属性决定了其社交和战斗风格：

| 态度值 | 行为特征 |
|--------|----------|
| `peaceful` | 和平，不主动攻击 |
| `friendly` | 友好，拒绝切磋 |
| `aggressive` | 好斗，玩家进入房间时主动挑衅 |
| `killer` | 杀手，主动攻击且不留情 |
| `heroism` | 豪侠，接受以多打少，拒绝欺负弱者 |

#### 2.4.4 NPC 的绝招与法术

`npc.c` 还提供了三个高级战斗函数，供 `chat_msg_combat` 中的函数指针调用：

```c
void cast_spell(string spell)     // 施展法术
int exert_function(string func)   // 运功（如 heal、recover）
int perform_action(string action) // 施展武功绝招（如 sword.jianzhang）
```

以 `/clone/npc/suicong.c` 中的战斗 AI 为例，随从 NPC 会根据不同门派自动施展对应的绝招：

```c
switch (me->query("menpai")) {
    case "huashan":
        if ( objectp(weapon) && weapon->query("skill_type") == "sword" )
            return perform_action("sword.jianzhang");
        // ...
    case "wudang":
        if ( objectp(weapon) && weapon->query("skill_type") == "sword" )
            return perform_action("sword.chan");
        // ...
}
```

---

## 3. NPC 交互系统

### 3.1 ask 命令：玩家与 NPC 的对话

`/cmds/std/ask.c` 实现了玩家向 NPC 打听消息的核心机制：

```c
int main(object me, string arg)
{
    string dest, topic, msg;
    object ob;

    if( !arg || sscanf(arg, "%s about %s", dest, topic)!=2 )
        return notify_fail("你要问谁什么事？\n");

    if( !objectp(ob = present(dest, environment(me))) )
        return notify_fail("这里没有这个人。\n");

    // 查询 NPC 的 inquiry 属性
    if( msg = ob->query("inquiry/" + topic) ) {
        if( stringp(msg) ) {
            message_vision(CYN "$N说道：" + msg + "\n" NOR, ob);
            return 1;
        }
    }
    // ... 默认回答
}
```

NPC 通过 `set("inquiry", ([ "话题": "回答内容", ... ]))` 来注册可询问的话题。话题回答既可以是字符串，也可以是函数指针，实现动态回答。例如随从 NPC 的复杂 inquiry 处理：

```c
set("inquiry", ([
    "老爷" : (: answer_inqiry, "laoye" :),
    "武功" : (: answer_inqiry, "wugong" :),
    "疗伤" : (: answer_inqiry, "healme" :),
]));
```

当玩家 `ask suicong about 疗伤` 时，`answer_inqiry("healme")` 会被调用，根据上下文返回不同结果甚至执行动作（如 `yun lifeheal`）。

如果 NPC 没有注册该话题，会随机从 `msg_dunno` 数组中选择一句默认回答，如：

> "$n 摇摇头，说道：没听说过。"

### 3.2 任务/剧情触发机制

NPC 的任务触发不局限于 `ask` 命令，常见机制包括：

1. **物品交付（accept_object）**：玩家给予特定物品触发剧情。例如野狗接受骨头后 `set_leader(who)`：

```c
int accept_object(object who, object ob)
{
    if( ob->id("bone") ) {
        set_leader(who);
        message("vision", name() + "高兴地汪汪叫了起来。\n", environment());
        return 1;
    }
}
```

2. **init() 中的条件触发**：NPC 在 `init()` 中检查玩家状态，触发特殊对话或战斗。

3. **call_out 驱动的定时任务**：如随从 NPC 的刺杀任务，通过 `call_out` 链驱动 NPC 寻敌、移动、战斗：

```c
void start_cisha(string target)
{
    set_temp("cisha_task", 1);
    set_temp("cisha_target_id", target);
    remove_call_out("goto_cisha_target");
    call_out("goto_cisha_target", 5);
    remove_call_out("check_cisha_status");
    call_out("check_cisha_status", CISHA_ROUND_LENGTH);
}
```

### 3.3 师父 NPC 的收徒与教技能逻辑

师父类 NPC 通过 `/inherit/char/master.c` 和 `/feature/apprentice.c` 实现师徒关系管理。

**收徒流程**：

```c
// apprentice.c
int recruit_apprentice(object ob)
{
    mapping my_family, family;

    if( ob->is_apprentice_of(this_object()) ) return 0;
    if( !mapp(my_family = query("family")) ) return 0;

    family = allocate_mapping(sizeof(my_family));
    family["master_id"] = query("id");
    family["master_name"] = query("name");
    family["family_name"] = my_family["family_name"];
    family["generation"] = my_family["generation"] + 1;
    family["enter_time"] = time();
    ob->set("family", family);
    ob->assign_apprentice("弟子", 0);
    return 1;
}
```

**教学限制**（`master.c`）：

```c
int prevent_learn(object me, string skill)
{
    // 非嫡传弟子只能学到师父技能等级的一半
    if( !me->is_apprentice_of(this_object())
    &&  (int)this_object()->query_skill(skill, 1) <= (int)me->query_skill(skill, 1) * 3 ) {
        command("say 虽然你是我门下的弟子，可是并非我的嫡传弟子 ....");
        return 1;  // 阻止学习
    }
    return 0;
}
```

师父 NPC 通常在 `create()` 中调用 `create_family("门派名", 代数, "头衔")` 来初始化门派信息。例如岳灵姗：

```c
create_family("华山派", 14, "弟子");
```

### 3.4 商人 NPC 的交易逻辑

商人 NPC 通常继承 `F_VENDOR`（`/feature/vendor.c`）或 `F_DEALER`（`/feature/dealer.c`）。

**简单商人（vendor.c）**：

```c
int buy_object(object me, string what)
{
    string ob;
    if( stringp(ob = query("vendor_goods/" + what)) )
        return ob->query("value");  // 返回价格
    else
        return 0;
}
```

NPC 通过 `set("vendor_goods", ([ "商品id": "/path/to/object", ... ]))` 定义可售商品。

**复杂商人（dealer.c）**：

`dealer.c` 实现了完整的买卖循环，包括：

- `do_buy()`：购买商品，支持数量、现金流水控制、库存管理（`quantity`）
- `do_sell()`：向商人出售物品，价格为原价的 70%
- `do_list()`：按分类（weapon、armor、drug、book、misc）列出商品
- `do_value()`：估价

商人 NPC 身上可以携带实际的物品对象（`all_inventory(this_object())`），实现真实的库存系统；也可以通过 `vendor_goods` 虚拟生成商品。

---

## 4. 特殊 NPC 类型

### 4.1 任务 NPC

任务 NPC 是驱动游戏剧情的核心。以 `/clone/npc/suicong.c`（随从/刺客 NPC）为例，它展示了复杂任务 NPC 的设计模式：

- **持久化存储**：继承 `F_SAVE`，数据存储在 `/data/npc/suicong/` 目录下，死亡后技能降级但不会完全消失。
- **门派专属 AI**：根据 `menpai` 属性自动配置武功技能和战斗绝招。
- **任务状态机**：通过 `cisha_task`、`cisha_target_id`、`cisha_result` 等 temp 属性管理刺杀任务的生命周期。
- **自主寻敌**：`goto_cisha_target()` 使用 `find_player()` 定位目标，并 `move()` 到目标所在房间。
- **装备管理**：`wield_new_weapon()`、`drop_all_weapon()` 实现动态武器切换。

### 4.2 守卫 NPC（block 命令相关）

`/cmds/std/block.c` 实现了阻挡功能，虽然这是玩家指令，但 NPC 同样可以使用这套机制。守卫 NPC 通常会通过 `set_temp("exit_blocked", dir)` 和 `environment()->set("exit_blockers/"+dir, me)` 来阻挡特定方向的出口，阻止玩家通过。

某些 NPC 会在 `init()` 或 `chat()` 中主动执行 `block` 指令，扮演守门人的角色。

### 4.3 野兽 NPC

野兽 NPC 继承自 `/inherit/char/trainee.c`（标记为 `NPC_TRAINEE`），并通过 `/adm/daemons/race/beast.c` 初始化种族特性。

`beast.c` 定义了野兽的默认属性：

```c
void setup_beast(object ob)
{
    mapping my = ob->query_entire_dbase();
    ob->set("default_actions", (: call_other, __FILE__, "query_action" :));
    my["unit"] = "只";
    if( undefinedp(my["gender"]) ) my["gender"] = "雄性";
    if( undefinedp(my["str"]) ) my["str"] = random(40) + 5;
    // ... 根据年龄自动计算气血、精力上限
}
```

野兽的战斗动作也与人类不同，使用爪、咬、拍等攻击方式：

```c
mapping *combat_action = ({
    ([ "action": "$N扑上来张嘴往$n的$l狠狠地一咬",
       "damage": 50, "damage_type": "咬伤" ]),
    ([ "action": "$N举起爪子往$n的$l抓了过去",
       "damage": 30, "damage_type": "抓伤" ]),
    ([ "action": "$N跃起来用前掌往$n的$l猛地一拍",
       "damage": 30, "damage_type": "瘀伤" ]),
});
```

野兽通常 `set("attitude", "aggressive")`，玩家进入房间即触发攻击。

### 4.4 跟随 NPC（suicong / trainee）

跟随系统由 `/feature/team.c` 中的 `set_leader()` 和 `set_lord()` 实现：

- `leader`：跟随对象，当被跟随者移动时，`follow_me()` 会自动触发跟随。
- `lord`：主人关系，通常用于驯服系统（如 `trainee.c`）。

`/inherit/char/trainee.c`（野兽/随从基类）实现了完整的驯服逻辑：

```c
int train_it(object ob, object me, int pts)
{
    if(query_temp("trainer") != ob->name()) {
        set_temp("trainer", ob->name());
        set_temp("training_pts", pts);
    } else
        add_temp("training_pts", pts);

    if(query_temp("training_pts") > 100) {
        me->set_lord(ob);           // 设置主人
        if(me->query("auto_follow"))
            me->set_leader(ob);     // 自动跟随
    }
}
```

驯服后，玩家可以通过 `gen`/`come` 命令召唤跟随，`ting`/`stay` 命令让随从停留，`fang`/`release` 命令释放随从。随从还会响应 `yao`/`attack` 命令攻击指定目标。

---

## 5. NPC 生成与管理

### 5.1 房间的 reset() 如何生成 NPC

房间的 NPC 生成由 `/inherit/room/room.c` 中的 `reset()` 函数统一管理。房间通过 `set("objects", ([ "/path/npc": 数量, ... ]))` 声明需要生成的 NPC：

```c
// 房间配置示例
set("objects", ([
    CLASS_D("huashan") + "/lingshan" : 1,  // 岳灵姗，唯一
    __DIR__"npc/dizi" : 3,                   // 华山弟子，3 个
]));
```

`reset()` 的执行逻辑：

```c
void reset()
{
    mapping ob_list, ob;
    object *inv;
    string *list;
    int i, j;

    ob_list = query("objects");      // 获取配置
    inv = all_inventory(this_object()); // 获取当前房间内所有对象

    // 1. 清理非 character、非 no_refresh 的克隆对象
    for(i=0; i<sizeof(inv); i++) {
        if(inv[i]->is_character() || inv[i]->query("no_refresh") || !clonep(inv[i]))
            continue;
        destruct(inv[i]);
    }

    // 2. 遍历 objects 配置，生成或召回 NPC
    for(i=0; i<sizeof(list); i++) {
        switch(ob_list[list[i]]) {
        case 1:  // 唯一 NPC
            if( !ob[list[i]] ) ob[list[i]] = make_inventory(list[i]);
            // 如果 NPC 不在房间，尝试召回
            if( environment(ob[list[i]]) != this_object()
                && ob[list[i]]->is_character() ) {
                if( !ob[list[i]]->return_home(this_object()) )
                    add("no_clean_up", 1);
            }
            break;
        default: // 多个同类 NPC
            for(j=0; j<ob_list[list[i]]; j++) {
                if( !objectp(ob[list[i]][j]) )
                    ob[list[i]][j] = make_inventory(list[i]);
                else if( environment(ob[list[i]][j]) != this_object()
                      && ob[list[i]][j]->is_character() ) {
                    ob[list[i]][j]->return_home(this_object());
                }
            }
        }
    }
    set_temp("objects", ob);  // 缓存生成的对象引用
}
```

`make_inventory()` 负责实际创建对象并设置 `startroom`：

```c
object make_inventory(string file)
{
    object ob;
    if( objectp(ob = new(file)) ) {
        // 对 /kungfu/class/ 下的唯一 NPC 做防重复克隆处理
        if(strsrch(base_name(ob), "/kungfu/class/") == 0
            && sizeof(filter_array(children(base_name(ob)), (: clonep :))) > 1) {
            npc_clean_up(file);  // 清理所有已有克隆再重新生成
            ob = new(file);
        }
        ob->move(this_object());
        ob->set("startroom", base_name(this_object()));
        return ob;
    }
    return 0;
}
```

### 5.2 NPC 的清理机制（clean_up）

`/feature/clean_up.c` 提供了对象的自清理能力：

```c
int clean_up()
{
    object *inv;
    int i;

    if( !clonep() && this_object()->query("no_clean_up") ) return 1;
    if(interactive(this_object())) return 1;  // 玩家不清理
    if(environment()) return 1;               // 在容器/房间内不主动清理

    inv = deep_inventory(this_object());
    for(i=sizeof(inv)-1; i>=0; i--)
        if(interactive(inv[i])) return 1;     // 携带玩家时不清理

    destruct(this_object());  // 销毁对象
    return 0;
}
```

注意：NPC 的 `clean_up` 通常不会直接触发，因为 NPC 大多处于某个房间中（`environment()` 不为空），而房间的 `clean_up` 会间接管理其中的 NPC。房间的 `no_clean_up` 属性由 `reset()` 动态控制——如果 NPC 无法返回原位，`no_clean_up` 会递增，防止房间被过早清理。

### 5.3 唯一 NPC（unique）与随机 NPC 的区别

**唯一 NPC**：

通过 `/feature/unique.c` 实现。继承该模块的 NPC 在 `create()` 时会检查是否已有克隆存在：

```c
nomask int violate_unique()
{
    object *ob;
    if( !clonep(this_object()) ) return 0;
    ob = filter_array(children(base_name(this_object())), (: clonep :) );
    return sizeof(ob) > 1;  // 如果克隆数超过 1，返回真
}

void create()
{
    if (violate_unique())
        destruct(this_object());  // 销毁重复克隆
}
```

唯一 NPC 通常是门派掌门、关键剧情角色（如 `/kungfu/class/huashan/` 下的岳不群等），通过 `room.c` 中的 `make_inventory()` 防重复逻辑双重保护。

**随机 NPC**：

普通的野兽、路人、士兵等，可以存在多个克隆实例，通常配置为 `set("objects", ([ ...: N ]))` 中的 `N > 1`。这类 NPC 没有 `unique.c` 的限制，由 `reset()` 根据缺失数量自动补充。

---

## 6. 与其他系统的关联

### 6.1 架构总览与对象继承体系

NPC 系统深度依赖 [[04-对象与继承体系]] 中描述的 LPC 多重继承机制。`npc.c` 通过 `inherit CHARACTER` 获得角色基类能力，再通过 `inherit F_CLEAN_UP` 获得清理能力。各个功能模块（F_ATTACK、F_SKILL、F_DBASE 等）以 Mixin 方式被 `char.c` 组合，构成了高度模块化的角色系统。

### 6.2 世界构建系统

NPC 的分布与生成完全由 [[05-世界构建系统]] 中的房间系统控制。`room.c` 的 `reset()` 是 NPC 进入游戏世界的唯一入口，`objects` 属性声明了每个房间的生态构成。NPC 的 `return_home()` 和 `startroom` 属性则保证了世界状态的自我恢复能力——即使 NPC 被杀或移动，房间刷新时仍会将其召回原位。

### 6.3 武功与战斗系统

NPC 的战斗力由 [[06-武功与战斗系统]] 驱动。`npc.c` 中的 `exert_function()`、`perform_action()`、`cast_spell()` 都是战斗系统向 NPC 开放的接口。NPC 通过 `set_skill()` 和 `map_skill()` 配置武功，其战斗 AI 通过 `chat_msg_combat` 中的函数指针调用绝招，实现了不亚于玩家的战斗复杂度。

### 6.4 坐骑与交通系统

虽然本项目中的 `/inherit/char/trainee.c` 主要面向野兽随从，但它同样构成了 [[10-坐骑与交通系统]] 的基础。野兽被驯服后通过 `set_leader()` 跟随主人，部分野兽可进一步配置为坐骑（通过 `rider` / `rided` 属性）。`trainee.c` 中处理了骑乘者与被骑乘者的关系绑定和解绑逻辑。

---

## 总结

《侠客行》的 NPC AI 与行为系统是一个分层清晰、模块化的设计典范：

- **底层**：`char.c` + `dbase.c` 提供角色通用能力和属性存储；
- **中间层**：`npc.c` 封装 NPC 特有的移动、对话、战斗行为；
- **表现层**：各类具体 NPC（`kungfu/class/`、`d/xxx/npc/`）通过 dbase 配置个性化参数；
- **驱动层**：`heart_beat()` 提供定时脉冲，`init()` 提供事件触发，`reset()` 提供世界刷新；
- **交互层**：`ask`、`beg`、`steal`、物品交付等命令构建玩家与 NPC 的丰富互动。

这套系统在 20 世纪 90 年代的 LPC MUD 框架下，通过简洁的 `heart_beat` + `call_out` + `init()` 三重驱动模型，实现了包括自动恢复、随机游荡、主动攻击、任务追踪、门派专属 AI 在内的复杂行为，为中文 MUD 游戏的发展树立了技术标杆。
