# 六篇架构文档核心系统摘要（第四轮专家复审原始产出）

> 来源：[`docs/xkx-arch/_archive/_侠客行 MUD 架构拆解说明书/`](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/) 08-13。
> 对应 engine：[`engine/src/xkx/`](engine/src/xkx/)。
> 说明：本摘要以 LPC 规格源为基准，按 engine 当前文件名与注释反推实现覆盖度，未逐行验证行为等价性。

---

## 一、总览表

| 系统 | 来源文档 | engine 主要对应模块 | 实现估计 | 风险等级 |
|------|----------|---------------------|----------|----------|
| 世界观与文案 | [08-世界观与文案.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/08-世界观与文案.md) | `themes/wuxia.py`、`dsl/layer0.py`、`content_gen/prompts.py`、`content_gen/llm_client.py`、`workbench/` | partial / missing | 中 |
| InterMUD 网络系统 | [09-InterMUD网络系统.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/09-InterMUD网络系统.md) | 无直接对应模块 | missing | 低 |
| 坐骑与交通系统 | [10-坐骑与交通系统.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/10-坐骑与交通系统.md) | `runtime/components.py`（`MountComp`/`VehicleComp` 待补）、`runtime/world.py`、`runtime/query.py` | missing | 中 |
| 死亡与轮回系统 | [11-死亡与轮回系统.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/11-死亡与轮回系统.md) | `runtime/death.py`、`runtime/governance.py`、`runtime/components.py`（`Vitals`/`Marks`）、`runtime/heal.py` | partial | 高 |
| 武林大会与竞技系统 | [12-武林大会与竞技系统.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/12-武林大会与竞技系统.md) | 无直接对应模块 | missing | 低 |
| NPC AI 与行为系统 | [13-NPC-AI与行为系统.md](docs/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/13-NPC-AI与行为系统.md) | `runtime/components.py`（`NpcBrain`/`Chat`/`Schedule` 待补）、`runtime/auto_fight.py`、`runtime/skill.py`、`runtime/world.py` | partial | 高 |

---

## 二、各系统详细摘要

### 2.1 世界观与文案

| 项目 | 内容 |
|------|------|
| **关键概念** | 金庸武侠融合世界观、区域势力分布（正/邪/中立）、房间 `long` 叙事、`item_desc` 交互线索、NPC `inquiry` 对话与 `greeting`、门派文化文案、任务暗语与谜题、欢迎信息 ANSI 艺术、半文半白文案风格 |
| **engine 对应模块** | `themes/wuxia.py`（题材配置与默认区域氛围）、`dsl/layer0.py`（`RoomDef`/`NpcDef` 的描述字段）、`content_gen/prompts.py`+`llm_client.py`（LLM 辅助文案生成）、`workbench/`（UGC 文案 workbench）、`runtime/pronoun.py`（称谓代词上下文） |
| **实现估计** | partial / missing |
| **主要缺口** | 8000+ 房间/NPC 的原始文案未迁移；无统一文案仓库/术语表；`item_desc` 与 `inquiry` 的交互式描述未在 DSL 中完整建模；LLM 生成文案的风格一致性、版本控制与人工审核流程待固化；区域势力表 `REGIONS.h` 未导入；欢迎画面/登录横幅未实现 |
| **风险等级** | 中 |

### 2.2 InterMUD 网络系统

| 项目 | 内容 |
|------|------|
| **关键概念** | I3/UDP 跨 MUD 协议、`dns_master` MUD 发现与服务路由、白名单 `LISTNODES`、心跳保活 `ping_q`/`ping_a`、跨站私聊 `gtell`、跨站频道 `gchannel`/`gwizmsg`、远程查询 `gfinger`/`rwho`/`locate`、TCP 入口 `inetd`、内置 HTTP 服务器（`http.c`/`http_d.c`）、跨 MUD 邮件（TCP `mail_serv` / UDP `mail_q`）、网络安全与地址验证 |
| **engine 对应模块** | 无直接对应模块 |
| **实现估计** | missing |
| **主要缺口** | 整套 InterMUD 协议栈未实现；`dns_master`、`inetd`、HTTP 服务、跨站邮件、跨站频道均未开始；六条收缩约束明确不考虑分布式架构，因此本系统在 UGC 验证前不在实施范围内 |
| **风险等级** | 低 |

### 2.3 坐骑与交通系统

| 项目 | 内容 |
|------|------|
| **关键概念** | 坐骑继承 `NPC_TRAINEE`、`ridable`/`ability` 属性、驯服 `train_it`/`wildness`/`loyalty`、骑乘 `ride`/`unride` 双向绑定、精力消耗转移与路口冲撞、马厩购买/野外驯服/任务获取、草地自食/马夫托管、FERRY 渡船定时器、`HARBOR`+`SHIP` 坐标航海、天气/触礁/翻船风险、特殊坐骑（白龙马 `duhe`、小红马 `whistle`）、镖车任务 |
| **engine 对应模块** | `runtime/components.py`（`Vitals`/`Inventory` 可作为坐骑属性基础）、`runtime/world.py`（房间 `exits` 与 `valid_leave`）、`runtime/query.py`（`move_to` 移动）、`runtime/commands.py`（`go` 指令）；`MountComp`/`VehicleComp`/`FerryComp`/`ShipComp` 等待设计 |
| **实现估计** | missing |
| **主要缺口** | 无坐骑/载具组件；无 `ability` 与房间 `cost` 的耦合校验；无驯服、骑乘、下骑命令；无 FERRY/HARBOR/SHIP 三类交通状态机；无坐标航海与天气事件；无马夫/马厩/镖车经济链；道路 `cost` 属性未在 DSL 中落地 |
| **风险等级** | 中 |

### 2.4 死亡与轮回系统

| 项目 | 内容 |
|------|------|
| **关键概念** | 当前值与有效值两层生命、`heart_beat` 死亡判定、昏迷-死亡两段式、`receive_damage`/`receive_wound`、`no_death` 免死区域、玩家/NPC 死亡分岔、`COMBAT_D->announce`/`death_penalty`/`killer_reward`、尸体对象与四阶段腐烂、鬼魂状态与视觉隔离、阴间地图/黑白无常/复活流程、死亡惩罚（经验/潜能/神/行为经验/存款/技能-1/掉落物品）、PvP 击杀标记/通缉/正气转移/谣言频道、丐帮死亡奖励 |
| **engine 对应模块** | `runtime/death.py`（`die`/`unconcious`/`revive`、尸体生成、鬼魂标记）、`runtime/governance.py`（PK 通缉/法院/阴间治理）、`runtime/components.py`（`Vitals`/`Marks`/`Inventory`）、`runtime/heal.py`（`heal_up` 与有效值恢复）、`runtime/skill.py`（`skill_death_penalty`）、`runtime/commands.py`（`kill` 触发战斗） |
| **实现估计** | partial |
| **主要缺口** | 阴间区域 `/d/death/` 未迁移；黑白无常多阶段 `call_out` 复活流程未实现；尸体腐烂四阶段与 `no_drop` 特殊物品保护未完整；鬼魂视觉隔离与 `astral_vision` 未实现；社交连锁（解散队伍、解除婚姻、师徒）未接入；PK 谣言频道与 `pker`/`killer` condition 不完整；丐帮“死亡奖励”特例未实现；银行存款惩罚未接入经济系统 |
| **风险等级** | 高 |

### 2.5 武林大会与竞技系统

| 项目 | 内容 |
|------|------|
| **关键概念** | 巫师手动启动的阶段性活动、广场-看台-擂台三层空间、8 年龄组、报名门槛（年龄/经验/败场）、擂主守擂/挑战者攻擂/排队候补、`no_fight`/`no_death` 区域隔离、装备仲裁 `cangku.c`+兵器架、伤害覆盖 `damage.c`、胜负自动判定、`auto_check` 定时器、龙虎榜排名、观众下注、试剑山庄团体赛、现场直播 `live.c`/`camera.c` |
| **engine 对应模块** | 无直接对应模块 |
| **实现估计** | missing |
| **主要缺口** | 武林大会整套竞技状态机未实现；专用场景 `/d/bwdh/` 未迁移；装备仲裁与标准兵器架未设计；排名/下注/直播机制均未开始；依赖于已完整实现的战斗、命令、频道、经济系统，当前不具备独立实施条件 |
| **风险等级** | 低 |

### 2.6 NPC AI 与行为系统

| 项目 | 内容 |
|------|------|
| **关键概念** | NPC 继承 `npc.c`/`char.c`+`F_CLEAN_UP`、dbase 属性体系、`heart_beat` 驱动、`random_move` 随机移动、`chat_chance`/`chat_msg` 双模式对话与自动恢复、`init()` 触发主动攻击、`attitude`（peaceful/friendly/aggressive/killer/heroism）、`accept_fight`/`accept_kill`、绝招 `perform_action`/`cast_spell`/`exert_function`、ask/inquiry 对话、任务触发（`accept_object`、`init` 条件、`call_out` 链）、师父收徒与教学限制、商人 `vendor`/`dealer`、任务 NPC/守卫 NPC/野兽 NPC/跟随 NPC、房间 `reset()`/`make_inventory`、唯一 NPC `unique.c`、clean_up 生命周期 |
| **engine 对应模块** | `runtime/components.py`（`Identity`/`Attributes`/`Vitals`/`Skills`/`CombatState`/`Inventory` 等组件基座）、`runtime/auto_fight.py`（NPC 自动战斗）、`runtime/skill.py`（技能查询与 `perform`/`exert` 接口）、`runtime/world.py`（房间 `reset` 与 NPC 生成）、`runtime/commands.py`（`ask` 指令）、`runtime/conditions.py`（状态效果）；`NpcBrain`/`Chat`/`Schedule`/`Vendor`/`Master` 等组件待补 |
| **实现估计** | partial |
| **主要缺口** | `heart_beat` 中 NPC 专用的 `chat()` 调度未完整；`random_move` 与门/精力/户外约束未实现；双模式 `chat_msg`/`chat_msg_combat` 与函数指针行为未落地；`attitude` 驱动的主动攻击、世仇 `vendetta`、以多打少逻辑未完整；师父收徒/教学/门派代际未实现；商人买卖/估价/库存未实现；野兽种族 `setup_beast` 与特殊战斗动作未实现；房间 `reset()`/`make_inventory`/`return_home`/`startroom` 召回未完整；唯一 NPC 防重复克隆未实现 |
| **风险等级** | 高 |

---

## 三、补充说明

- 当前 engine 另有 `content_gen/`、`content_review/`、`orchestrator/`、`workbench/` 等模块，对应 M2 / ADR-0053 的 UGC 创作闭环，其中部分能力（如 LLM 文案生成）与 08 世界观与文案相关，但尚未覆盖传统 LPC 文案体系。
- 09 InterMUD 与 12 武林大会在当前阶段风险等级为“低”，原因是六条收缩约束已将分布式架构后置，而武林大会属于可选竞技玩法，不影响核心闭环验证。
- 10 坐骑与交通、11 死亡与轮回、13 NPC AI 均与核心探索/战斗/社交闭环强相关，其中 11 与 13 风险等级为“高”，是实现 LPC 行为等价的关键路径。
- 实现估计含义：`implemented` = 核心契约已基本落地并伴随测试；`partial` = 骨架或最小可行版本已存在，但大量细节/内容未迁移；`missing` = 几乎未开始；`unclear` = 从目录难以判断。上表主要使用 `partial` 与 `missing`。
