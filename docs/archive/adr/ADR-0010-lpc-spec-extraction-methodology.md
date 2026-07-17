# ADR-0010：LPC 规格提取方法论与 9 层范围定义

- 状态：已采纳（阶段 0 任务 1 前置）
- 日期：2026-07-11
- 阶段：0 任务 1（LPC 规格提取管线）
- 关联 dissent：[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 4（规则冲突语义漂移，"靠基线测试断言原 LPC 命中行为"）/ dissent 7（派生变更审计覆盖缺口）；[04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 0 任务 1/3；[ADR-0009](ADR-0009-original-driver-runnable.md)（golden trace 辅助验证）

## 背景

[04](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 0 任务表对"规格提取"只给了术语列表和验收标准：

> | LPC 规格提取管线 | 形式化规格契约：前置/后置条件、不变量、状态机、概率分布 | go/move/combat 核心路径覆盖 |

但文档**未定义**：规格契约的具体格式、提取粒度（函数级/文件级/路径级）、任务 1（规格）与任务 3（单元规约）的精确分工、表示形式（JSON/YAML/pydantic）。

初始分析按字面"go/move/combat 核心路径"规划了三条路径（go/move + combat + 命令分发），但对照侠客行架构拆解说明书（[01-13](../xkx-arch/_archive/_侠客行 MUD 架构拆解说明书/) 14 份文档、36 个子系统）后发现：**go/move/combat 三条路径无法覆盖完整核心可玩循环**，遗漏了多个不可跳过的子系统（F_DBASE 对象数据基础、死亡轮回 combat 下游、NPC heart_beat 驱动、核心守护进程等）。

## 发现：核心可玩循环远不止 go/move/combat

核心可玩循环是一个闭环，不是三条孤立路径：

```
玩家连接 -> LOGIN_D -> 进入游戏 -> command_hook -> [go/kill/ask/give/...]
                                                         |
                                                         v
                                               世界构建（ROOM/NPC/ITEM）
                                                         |
                                                         v
                                               战斗（do_attack + skill_power + damage）
                                                         |
                                                         v
                                               死亡判定（die + death_penalty + reincarnate）
                                                         |
                                                         v
                                               heart_beat（NPC AI + 自愈 + 状态更新）
                                                         |
                                                         v
                                               消息输出（F_MESSAGE）
```

遗漏这些子系统会导致规格不完整：

| 遗漏子系统 | 不可跳过的理由 |
|---|---|
| F_DBASE（set/query） | 所有对象的数据存储基础，combat/go/look 全依赖 |
| F_NAME / F_MESSAGE | 对象识别 + 消息输出，look 和所有文本依赖 |
| 死亡轮回（die/death_penalty/make_corpse/reincarnate） | combat 直接下游，不提取不知战斗怎么结束 |
| NPC heart_beat | 驱动 NPC 战斗/自愈/移动，是 NPC 侧 combat 入口 |
| NPC auto_fight（hatred/vendetta/aggressive） | PvE 入口，玩家进房间触发战斗 |
| skill_power 公式 | do_attack 的 AP/DP/PP 计算基础，不提取无法复现战斗判定 |
| 三层资源体系（qi/eff_qi/max_qi + jing + jingli + neili） | 伤害结算的双层生命系统 |
| CHAR_D（setup_char + make_corpse） | 角色初始化 + 尸体生成 |
| SECURITY_D | command_hook 每条命令都过 valid_cmd |
| NATURE_D | 时间系统 + 自动保存（真实 1 秒 = 游戏 1 分钟） |
| LOGIN_D 状态机 | 玩家从连接到进入游戏的完整流程 |

## 决策

### 1. 规格契约四要素格式

每个核心函数提取以下规格（pydantic v2 模型，存于 `engine/src/xkx/spec/`）：

| 要素 | 含义 | 示例（do_attack 步骤 3 闪避判定） |
|---|---|---|
| **签名** | 函数名、参数（含 LPC 类型）、返回值 | `varargs int do_attack(object me, object victim, object weapon, int attack_type)` |
| **前置条件** | 调用前必须满足的条件 | me/victim 非 null 且 living；weapon 已装备或为空手 |
| **后置条件** | 调用后保证的状态变更 | victim.qi 减少或 me/victim 获得经验；副作用账本已记录 |
| **不变量** | 执行过程中保持的不变量 | 0 <= qi <= eff_qi <= max_qi（三层资源不变量） |
| **副作用** | 状态变更 + 消息输出（按交织顺序） | receive_damage(qi) -> damage_msg -> message_vision -> skill_improve |
| **随机性** | random() 调用的语义和概率模型 | `random(ap+dp) < dp`，闪避概率 = dp/(ap+dp)，seeded RNG |

### 2. 提取粒度：函数级

提取每个核心函数的输入输出契约，**不逐行翻译实现**。理由：greenfield 重写需理解 why（行为契约）而非复制 what（实现细节）。阶段 -1 的 resolve_attack 提取（[ADR-0002](ADR-0002-resolve-attack-extraction.md)）已验证此粒度可行。

### 3. 表示格式：pydantic v2 模型

- 与现有代码风格一致（项目已用 pydantic v2 做层0 schema）
- 可被 hypothesis 属性测试直接消费（任务 3 衔接）
- 可序列化为 JSON 供 Agent 消费（M2 衔接）
- 类型完整，SchemaRegistry 可校验

### 4. 范围：9 层覆盖完整核心可玩循环

| 层 | 范围 | 核心 LPC 文件 | 预估行数 |
|---|---|---|---|
| **A: 驱动桥梁** | Master + Simul Efun + config | adm/single/master.c, simul_efun.c | ~300 |
| **B: 对象基础** | F_DBASE + F_NAME + F_MOVE + F_MESSAGE + F_SAVE + F_CLEAN_UP | feature/{dbase,name,move,message,save,clean_up}.c | ~700 |
| **C: 命令系统** | command_hook 四分支 + commandd + 命令路径 + 方向别名 | feature/command.c, adm/daemons/commandd.c, aliasd.c | ~400 |
| **D: 世界构建** | ROOM 基类 + valid_leave + reset + make_inventory + 门 | inherit/room/room.c, cmds/std/go.c | ~570 |
| **E: 战斗系统** | do_attack 七步 + skill_power + hit_ob + receive_damage + 三层资源 + select_opponent | combatd.c, feature/{attack,damage,skill}.c | ~1900 |
| **F: 死亡轮回** | die + death_penalty + make_corpse + reincarnate + unconcious | feature/damage.c(die), combatd.c(penalty), chard.c(corpse) | ~400 |
| **G: NPC AI** | heart_beat + chat + auto_fight + random_move | inherit/char/{char,npc}.c, feature/attack.c(init) | ~600 |
| **H: 核心守护进程** | LOGIN_D + CHAR_D + SECURITY_D + NATURE_D + CHINESE_D | adm/daemons/{logind,chard,securityd,natured,chinesed}.c | ~1500 |
| **I: 角色与登录** | CHARACTER 基类 + 用户对象 + LOGIN_D 状态机 | inherit/char/char.c, clone/user/user.c, logind.c | ~500 |

**总计约 4500-5000 行 LPC**（feature/ 36 文件 + 核心 inherit + 核心 daemon），完全可控。

### 5. 并行化策略：3 个 Wave

用 agent teams 按依赖关系分 Wave 并行提取（LPC 代码都在，提取规格不需运行时依赖）：

- **Wave 1（并行 4 层）**：A + B + C + D -- 基础层，互相依赖少
- **Wave 2（并行 3 层）**：E + F + G -- 战斗/死亡/AI，E 是核心，F/G 依赖 E 的规格但可同时读代码
- **Wave 3（并行 2 层）**：H + I -- 守护进程 + 登录，依赖前面层的规格但可同时读代码

每层产出：
- `engine/src/xkx/spec/<layer>.py` -- pydantic 模型（FunctionSpec 集合）
- `engine/tests/test_spec_<layer>.py` -- hypothesis 属性测试骨架

### 6. 避免穷尽细节的边界

**不做**（后置到阶段 2 或更后）：
- 不碰 kungfu/（798 文件）-- 门派武学是阶段 2 子系统迁移
- 不碰 d/（6414 文件）-- 区域内容是阶段 2
- 不碰 InterMUD/武林大会/坐骑交通/婚姻 -- 后置系统
- condition 状态系统只提取框架规格（apply/update/clear 接口），具体状态类型（蛇毒/醉/失明）后置
- 阴间世界流程（黑白无常/还阳路径）后置到阶段 1
- 别名的玩家自定义部分后置，只提取全局方向别名
- 不做 LPC 解析器自动化工具 -- 人工 + agent 提取，工具后置

**收敛原则**：核心路径覆盖（非全量 8412 文件）+ 函数级契约（非逐行翻译）+ 4500 行可控范围。

### 7. golden trace 定点辅助（ADR-0009 衔接）

对难以静态判断的路径，运行旧 driver（[ADR-0009](ADR-0009-original-driver-runnable.md)）录制 golden trace 辅助：
- 533 valid_leave 命中行为（dissent 4 基线测试）
- do_attack 七步副作用交织时序
- NPC auto_fight 触发条件实际行为

不做全量录制，仅定点辅助。

## 任务 1 与任务 3 的分工

| | 任务 1（规格提取管线） | 任务 3（单元级行为规约） |
|---|---|---|
| **产出** | 规格契约（pydantic 模型） | hypothesis 属性测试 |
| **定位** | why（行为契约） | 验证什么（基于契约的测试） |
| **关系** | 上游 | 下游，消费任务 1 的规格 |
| **依赖** | LPC 源码 | 任务 1 产出 + 新引擎实现 |

任务 1 每层产出 pydantic 模型后，任务 3 基于该模型生成 hypothesis 属性测试骨架，两者自然衔接。

## 产出位置

- `engine/src/xkx/spec/` -- 9 层规格契约 pydantic 模型
  - `base.py` -- FunctionSpec/SideEffect/RandomSpec 等基础类型
  - `layer_a_driver.py` ... `layer_i_login.py` -- 9 层规格
- `engine/tests/test_spec_*.py` -- 每层属性测试骨架
- `docs/xkx-arch/08-阶段-0-实施计划.md` -- 阶段 0 实施计划（含 9 层分解 + Wave 计划）

## 后续

- ADR-0010 定义方法论后，按 08-阶段-0-实施计划.md 的 3 个 Wave 推进
- 每个 Wave 完成后更新 PROGRESS.md
- 若提取中发现 9 层范围需调整（某层遗漏/某层过大），写 ADR 修订
- 任务 3（单元规约）在任务 1 各层产出后自然衔接，不单独启动
