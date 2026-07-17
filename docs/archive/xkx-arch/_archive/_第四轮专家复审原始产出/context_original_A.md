# 七篇架构文档核心系统摘要（第四轮专家复审原始产出）

> 来源：[`docs/xkx-arch/_archive/_侠客行 MUD 架构拆解说明书/`](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/) 01-07。
> 对应 engine：[`engine/src/xkx/`](engine/src/xkx/)。
> 说明：本摘要以 LPC 规格源为基准，按 engine 当前文件名与注释反推实现覆盖度，未逐行验证行为等价性。

---

## 一、总览表

| 系统 | 来源文档 | engine 主要对应模块 | 实现估计 | 风险等级 |
|------|----------|---------------------|----------|----------|
| 架构总览 | [01-架构总览.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/01-架构总览.md) | `spec/layer_a_driver.py`、`runtime/ecs.py`、`runtime/components.py`、`runtime/world.py`、`runtime/engine.py`、`runtime/storage.py`、`runtime/serialization.py`、`dsl/layer0.py`/`ir.py` | partial | 中 |
| 守护进程系统 | [02-守护进程系统.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/02-守护进程系统.md) | `runtime/login.py`、`runtime/connection.py`、`runtime/commands.py`+`middleware/`、`runtime/conditions.py`、`runtime/heal.py`、`runtime/governance.py`、`runtime/storage.py`、`runtime/death.py`、`runtime/title.py`、`runtime/capability.py` | partial | 高 |
| 命令系统 | [03-命令系统.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/03-命令系统.md) | `runtime/commands.py`、`runtime/middleware/s0_flood_check.py`~`s7_execute_audit.py`、`runtime/action_context.py`、`runtime/capability.py`、`runtime/query.py`、`spec/layer_c_command.py` | partial | 中 |
| 对象与继承体系 | [04-对象与继承体系.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/04-对象与继承体系.md) | `runtime/ecs.py`、`runtime/components.py`、`runtime/equipment.py`、`runtime/conditions.py`、`runtime/heal.py`、`runtime/death.py`、`runtime/skill.py`、`runtime/pronoun.py`、`runtime/serialization.py`、`runtime/dbase_map.py`、`spec/layer_b_object_base.py` | partial | 高 |
| 世界构建系统 | [05-世界构建系统.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/05-世界构建系统.md) | `dsl/layer0.py`、`dsl/ir.py`、`runtime/world.py`、`runtime/components.py`、`runtime/doors.py`、`runtime/query.py`、`themes/wuxia.py`/`default.py`、`spec/layer_d_world.py` | partial | 高 |
| 武功与战斗系统 | [06-武功与战斗系统.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/06-武功与战斗系统.md) | `combat/system.py`、`combat/resolve_attack.py`、`combat/context.py`、`combat/modifier.py`、`combat/replay.py`、`combat/result.py`、`combat/rng.py`、`runtime/components.py`、`runtime/auto_fight.py`、`runtime/skill.py`、`runtime/conditions.py`、`spec/layer_e_combat.py` | partial | 高 |
| 多人交互系统 | [07-多人交互系统.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/07-多人交互系统.md) | `runtime/connection.py`、`runtime/governance.py`、`runtime/components.py`、`runtime/account.py`、`runtime/theme.py` | partial / missing | 高 |

---

## 二、各系统详细摘要

### 2.1 架构总览

| 项目 | 内容 |
|------|------|
| **关键概念** | MudOS Driver、Master 对象、`simul_efun`、全局头文件 `globals.h`、Feature/Inherit Mixin 模式、对象生命周期（创建 / swap / clean_up / destruct）、`.o` 存档、目录拓扑（`/adm/`、`/inherit/`、`/feature/`、`/d/`、`/cmds/`、`/kungfu/`） |
| **engine 对应模块** | `spec/layer_a_driver.py`（驱动桥接规格）、`runtime/ecs.py`（ECS 世界）、`runtime/components.py`（dbase / Feature 组件映射）、`runtime/world.py`（IR 转 ECS）、`runtime/engine.py`（统一 tick 循环）、`runtime/storage.py`+`runtime/serialization.py`（JSON 存档与崩溃恢复）、`runtime/schema.py`、`dsl/layer0.py`/`dsl/ir.py`（声明式房间/NPC/任务数据）、`themes/wuxia.py`/`themes/default.py`（题材配置） |
| **实现估计** | partial |
| **主要缺口** | 无真实 MudOS Driver / Master 运行时；`simul_efun` 全局函数未实现；对象 swap / clean_up / autoload 未实现；完整 Feature -> Component 映射未完成；eval cost 限制缺失；prototype / default_object 模式缺失 |
| **风险等级** | 中 |

### 2.2 守护进程系统

| 项目 | 内容 |
|------|------|
| **关键概念** | 单例 Daemon、`epilog()`/`preload()` 预加载、LOGIN_D、COMMAND_D、COMBAT_D、CHANNEL_D、NATURE_D、CHINESE_D、SECURITY_D、MONEY_D、CHAR_D、RANK_D、UPDATE_D、VIRTUAL_D、ALIAS_D、EMOTE_D、BAN_D 等 |
| **engine 对应模块** | `runtime/login.py`（LOGIN_D 状态机）、`runtime/connection.py`（会话与超时）、`runtime/commands.py`+`runtime/middleware/`（COMMAND_D / ALIAS_D / SECURITY_D 权限管线）、`runtime/conditions.py`（ConditionSystem）、`runtime/heal.py`（HealSystem）、`runtime/governance.py`（GovernanceSystem）、`runtime/storage.py`（StorageSystem 持久化）、`runtime/death.py`（CHAR_D 尸体/死亡）、`runtime/title.py`（RANK_D 称谓）、`runtime/account.py`+`runtime/capability.py`（SECURITY_D 权限）、`runtime/profiler.py`（PROFILE_D）、`runtime/theme.py`（区域/户外配置） |
| **实现估计** | partial |
| **主要缺口** | CHANNEL_D 闲聊/门派/谣言/网际频道缺失；NATURE_D 昼夜/天气/定时事件缺失；CHINESE_D 数字/日期本地化缺失；MONEY_D 货币换算与现金流控制缺失；UPDATE_D 登录数据检查缺失；ALIAS_D 玩家自定义别名缺失；EMOTE_D、BAN_D、FINGER_D、VIRTUAL_D、WEAPON_D、MARRY_D 未实现；SECURITY_D 巫师等级与文件权限不完整 |
| **风险等级** | 高 |

### 2.3 命令系统

| 项目 | 内容 |
|------|------|
| **关键概念** | `process_input`、全局别名、方向快捷、`command_hook` 四分支、COMMAND_D `find_command`/`rehash`、命令路径与优先级、SECURITY_D `valid_cmd`、命令文件 `main()`/`help()` 标准结构、标准/技能/巫师/管理命令分层 |
| **engine 对应模块** | `runtime/commands.py`（Game 与 dispatch）、`runtime/middleware/s0_flood_check.py`~`s7_execute_audit.py`（8 段管线：刷屏/别名/权限/查找/方向/参数/上下文/审计）、`runtime/action_context.py`、`runtime/capability.py`、`runtime/query.py`、`spec/layer_c_command.py` |
| **实现估计** | partial |
| **主要缺口** | 仅实现约 10 条命令（go / kill / ask / give / quest / take / look / inventory / hp 等）；大量 `/cmds/std`（get / drop / wear / wield / remove / put / open / close / save / quit / who / score / time 等）、技能命令、巫师命令、管理员命令缺失；频道/表情回退分支未完整接入；命令文件即插即用的文件系统注册表未采用 |
| **风险等级** | 中 |

### 2.4 对象与继承体系

| 项目 | 内容 |
|------|------|
| **关键概念** | `inherit` 基类链 + `feature/` Mixin、F_DBASE 键值存储、F_NAME 命名/ID/描述、F_MOVE 移动与负重、F_MESSAGE 消息缓冲、F_ATTACK 敌人管理、F_DAMAGE 伤害/昏迷/死亡/恢复、F_SKILL 技能映射与升级、F_CONDITION 状态、F_EQUIP 装备、F_AUTOLOAD、F_SAVE、F_FINANCE、F_TEAM、F_APPRENTICE、F_MARRY、F_MULTI |
| **engine 对应模块** | `runtime/ecs.py`（ECS 世界）、`runtime/components.py`（Identity / Attributes / Vitals / Skills / Equipment / CombatState / Inventory / Marks / TitleComp / FamilyComp 等）、`runtime/equipment.py`（穿戴/卸下/属性副本）、`runtime/conditions.py`（condition handler）、`runtime/heal.py`（`heal_up` 自然恢复）、`runtime/death.py`（die / unconcious / revive）、`runtime/skill.py`（技能学习与查询）、`runtime/pronoun.py`（代词上下文）、`runtime/serialization.py`+`runtime/storage.py`（存档）、`runtime/dbase_map.py`、`spec/layer_b_object_base.py` |
| **实现估计** | partial |
| **主要缺口** | F_MOVE 完整负重传递链未实现；F_MESSAGE 消息缓冲/编码转换缺失；F_NAME `apply` 掩码与状态修饰不完整；F_AUTOLOAD 未实现；F_SAVE 按玩家 ID 分目录的 `.o` 模型未复现；F_MULTI 多部件对象缺失；F_TEAM/F_MARRY/F_APPRENTICE 完整逻辑缺失；F_ACTION busy 队列未完整；F_FINANCE 缺失；prototype / default_object 机制缺失；对象 clean_up / swap 缺失 |
| **风险等级** | 高 |

### 2.5 世界构建系统

| 项目 | 内容 |
|------|------|
| **关键概念** | `/d/` 区域目录、`REGIONS.h`、ROOM 基类、`short`/`long`/`exits`/`objects`、`valid_leave`、门系统 `create_door`/`open_door`/`close_door`、reset / make_inventory、NPC 回家、特殊房间（BANK / HARBOR / FERRY / SHOP）、VIRTUAL_D、户外天气、动态世界事件 |
| **engine 对应模块** | `dsl/layer0.py`（`RoomDef` / `NpcDef` / `ItemDef` / `QuestDef`）、`dsl/ir.py`（`compile_scene`）、`runtime/world.py`（`build_world` IR -> ECS）、`runtime/components.py`（`RoomComp` / `DoorEntry`）、`runtime/doors.py`（门状态机）、`runtime/query.py`（`move_to`）、`themes/wuxia.py`/`themes/default.py`（题材路径）、`spec/layer_d_world.py` |
| **实现估计** | partial |
| **主要缺口** | 6000+ `/d/` 房间未迁移，当前仅有示例 YAML 场景；VIRTUAL_D 虚拟区域未实现；`reset()` / `make_inventory()` / NPC `return_home()` 不完整；商店/钱庄/海港/渡船等特殊房间未实现；户外天气与 NATURE_D 未接入；区域名映射 `REGIONS.h` 未使用；动态事件（如蒙面人袭击）缺失 |
| **风险等级** | 高 |

### 2.6 武功与战斗系统

| 项目 | 内容 |
|------|------|
| **关键概念** | `/kungfu/class/` 21 门派、`/kungfu/skill/` 97 技能、技能映射 `map_skill` / 准备 `prepare_skill`、战斗状态 `enemy`/`killer`、COMBAT_D `fight`/`do_attack` 七步管线、AP/DP/PP 判定、`skill_power`、伤害类型与消息、condition（毒/醉/失明/点穴等）、内力 `jiali`/`jiajin`、绝招 `perform`/`exert`、NPC `auto_perform`、阵法合击 |
| **engine 对应模块** | `combat/system.py`、`combat/resolve_attack.py`、`combat/context.py`、`combat/modifier.py`、`combat/replay.py`、`combat/result.py`、`combat/rng.py`（combat-only 确定性内核）、`runtime/components.py`（`CombatState` / `Skills` / `Equipment` / `Vitals`）、`runtime/commands.py`（kill / 战斗启动）、`runtime/auto_fight.py`、`runtime/skill.py`、`runtime/conditions.py`（condition handler）、`spec/layer_e_combat.py` |
| **实现估计** | partial |
| **主要缺口** | 21 门派与 97 技能未迁移；`perform` / `exert` / `jiali` / `jiajin` 未实现；完整 NPC AI（chat / `auto_perform`）缺失；组队阵法/集体攻击缺失；riposte / 特殊反击未完整；武器标志位（EDGED / TWO_HANDED / SECONDARY）未实现；`skill_power` 完整公式与伤害类型覆盖不足；多数具体 condition handler 仍为 stub |
| **风险等级** | 高 |

### 2.7 多人交互系统

| 项目 | 内容 |
|------|------|
| **关键概念** | 消息分类路由（个人/房间/队伍/频道/全局）、`tell_object`/`tell_room`/`say`、CHANNEL_D、组队 `team` / 跟随 `follow`、经济（MONEY_D / give / get / drop / buy / sell / bank）、表情 EMOTE_D、婚姻 MARRY_D、公告板、PK（kill/fight/死亡惩罚/日志）、多部件 multi |
| **engine 对应模块** | `runtime/connection.py`（会话与 ring buffer 重连）、`runtime/governance.py`（PK 通缉/法院/阴间治理）、`runtime/components.py`（`Inventory` / `Marks` / `TitleComp` / `FamilyComp`）、`runtime/account.py`、`runtime/theme.py`；`content_gen` / `orchestrator` / `workbench` 为 M2 UGC 闭环，不在 01-07 覆盖范围内 |
| **实现估计** | partial / missing |
| **主要缺口** | CHANNEL_D 全部频道缺失；组队系统（F_TEAM / `cmds/std/team.c`）缺失；表情系统 EMOTE_D 缺失；婚姻系统 MARRY_D 缺失；公告板缺失；货币经济/商店交易/银行未实现；`say` / `tell` / `whisper` / `shout` 未实现；网际 InterMUD 缺失；PK 死亡日志与频道谣言不完整 |
| **风险等级** | 高 |

---

## 三、补充说明

- 当前 engine 另有 `content_gen/`、`content_review/`、`orchestrator/`、`workbench/` 等模块，对应 M2 / ADR-0053 的 UGC 创作闭环，不在 01-07 旧文档的七个子系统范围内，故未列入上表。
- 实现估计含义：`implemented` = 核心契约已基本落地并伴随测试；`partial` = 骨架或最小可行版本已存在，但大量细节/内容未迁移；`missing` = 几乎未开始；`unclear` = 从目录难以判断。上表主要使用 `partial` 与 `missing`。
