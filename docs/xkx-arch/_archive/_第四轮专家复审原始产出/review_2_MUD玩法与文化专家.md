# 第四轮专家复审：MUD 玩法与文化专家

> 评审重点：LPC 命令语义保真、do_attack 七步管线、PronounContext、技能三层、NPC AI/heart_beat、灵魂系统、门派与拜师练功任务链。

## 总体裁定

**verdict：risky**

`do_attack` 七步管线、`PronounContext` 三元组与称谓框架、`Command` 8 段管线已具备可验证骨架，是本轮最大亮点；但 21 门派 / 97 技能的招式数据、`heart_beat` 驱动的 NPC AI、灵魂 / 阴间轮回、门派拜师与练功任务链等侠客行核心文化玩法仍大量处于 stub 或明确后置状态。M3 可玩 demo 之前，玩法深度与 LPC 行为等价缺口显著，存在「引擎骨架过早平台化」的风险。

## 当前实现与侠客行核心系统的缺口

### 1. LPC 命令语义保真

- **状态**：partial
- **风险等级**：中
- **证据**：
  - `engine/src/xkx/runtime/commands.py` 已落地 30+ 命令（go / kill / fight / ask / give / quest / take / look / inventory / hp / bai / kneel / learn / practice / dazuo / tuna / enable 等），并跑通雪山、终南、书院多门派 e2e。
  - 但大量命令带简化 / 后置注释：`practice` 的 `SkillData` 为 stub、`du` 的 literate 门控未完整、`recruit` 依赖 NPC AI 路径未闭合；`get / drop / wear / wield / remove / put / open / close / save / quit / who / score / time` 等 `/cmds/std` 标准命令仍缺失（`docs/xkx-arch/_archive/_第四轮专家复审原始产出/context_original_A.md` 2.3）。
  - 命令文件即插即用的文件系统注册表未采用，`command_hook` 四分支与 `COMMAND_D.rehash` 语义未完整复现。
- **建议**：阶段 0 优先补齐 `/cmds/std` 最小集（get / drop / wear / wield / remove / save / quit / who）的行为等价基线；对现有命令补全「成功 / 失败 / notify_fail」消息与 LPC 消息路径对比测试，避免 verbs 面宽但语义漂移。

### 2. do_attack 七步管线

- **状态**：partial（内核 solid，外围缺口大）
- **风险等级**：中
- **证据**：
  - `engine/src/xkx/combat/resolve_attack.py` 已实现完整七步交织：AP/DP 计算、`skill_power` 完整公式（level³/3 + jingli_bonus + str/dex 加成 + `is_fighting` 折减 + 低技能经验补偿）、dodge / parry / hit / damage / wound / exp / jingli / skill_improve 与 riposte 递归，并保留 message 与 effect 交织入账本，符合 CLAUDE.md「不得先算后 apply」不变量。
  - `combat.resolve_attack` 为纯函数 + `DeterministicRNG` + `CombatSnapshot`，hypothesis 属性测试覆盖，combat-only 确定性边界守住（ADR-0023）。
  - 但 `perform` / `exert` / `jiali` / `jiajin`、武器标志位（EDGED / TWO_HANDED / SECONDARY）、阵法合击、NPC `auto_perform`、特殊反击等明确后置；`CombatState.action_message` 仍 hard-code 为 "$N一招「试探」，攻向$n$l"，`SkillData` 招式表未注入（`engine/src/xkx/runtime/skill.py` `_SKILL_DATA_REGISTRY` 空 stub）。
- **建议**：M3-1 必须完成 21 门派核心招式 `SkillData` 注入 + `query_action` 招式选择，并补全 `perform`/`exert` 的最小调用路径；否则战斗会退化为「试探」一招通吃，严重削弱武侠文化表达。

### 3. PronounContext

- **状态**：partial（框架 implemented，数据待填充）
- **风险等级**：中
- **证据**：
  - `engine/src/xkx/runtime/pronoun.py` 已实现 10 变量 `PronounContext`（$N/$n/$P/$p/$C/$c/$R/$r/$S/$s）、viewer 显式传参、角色互换时的 viewer 翻转、不可见目标退化门控，符合 rankd.c 三元组语义与 CLAUDE.md 不变量。
  - `engine/src/xkx/runtime/title.py` 已提取 RANK_D 7 函数为无状态纯函数，并预留题材包注入 `CLASS_RANK_TABLE` 等 class 表，核心引擎保持主题中立。
  - 但 class 表仅在 `themes/wuxia.py` 注册一条武当派加成，完整 21 门派职业称谓表未注入；`visible()` 的 invisibility / astral_vision / wiz_level 判定仍 TODO；combat 内 `_render` 仅处理 4 个占位符，未调用 `PronounService.render`。
- **建议**：M3 前将 combat `_render` 接入 `PronounService`，并补齐 21 门派 class 称谓表；同时把 invisibility / astral_vision 判定写入阶段 2.6 门禁，否则隐身、鬼魂等玩法文本会泄露信息。

### 4. 技能三层

- **状态**：partial（组件就绪，数据与求值未闭合）
- **风险等级**：高
- **证据**：
  - `engine/src/xkx/runtime/components.py` `Skills` 组件已区分 `levels`（永久基础层）、`apply_*`（临时修正层）、`skill_map` / `skill_prepare` / `learned`（映射 / 准备 / 学习进度层），符合 ADR-0026 技能三层设计。
  - `engine/src/xkx/runtime/skill.py` 的 `improve_skill` 实现 learned 阈值升级公式，多技能惩罚、weak_mode 等行为对齐 `feature/skill.c:149-182`。
  - 但 `SkillData` 注册表为空 stub，`valid_learn` / `practice_skill` / `valid_enable` 的丰富 LPC 条件未迁移；`query_skill` 三层叠加求值虽已存在，但 enable / prepare / map 的 LPC 动态条件（如「force >= 20 才能 enable dodge」）未落地；`skill_power` 已完整但缺少 jiali / jiajin / neili 的武侠资源交互。
- **建议**：M3-1 将 `SkillDef` CPK 资产与 `SkillData` 注册表打通，补齐 enable / prepare / map 的校验与三层求值基线测试；jiali / jiajin 作为战斗资源前置条件应优先于 perform/exert。

### 5. NPC AI / heart_beat

- **状态**：partial（组件存在，行为严重不足）
- **风险等级**：高
- **证据**：
  - `engine/src/xkx/runtime/components.py` `NpcBehavior` 已声明 `attitude`（friendly / heroism / aggressive）、`chat_chance_combat` / `chat_msg_combat`、`inquiry`、拜师配置、`vendetta_mark` 等字段。
  - `engine/src/xkx/runtime/world.py` `_spawn_npc` 按 `RoomComp.objects` 生成 NPC，但 `heart_beat` 中 NPC 专用 `chat()` 调度、`random_move`、门 / 精力 / 户外约束、`attitude` 驱动的主动攻击、世仇 `vendetta`、以多打少逻辑均未完整实现（`context_original_B.md` 2.6）。
  - `engine/src/xkx/runtime/auto_fight.py` 提供 NPC 自动战斗，但 `auto_perform` / `cast_spell` / `exert_function` 未落地；房间 `reset()` / `make_inventory` / `return_home` / `startroom` 召回未完整；唯一 NPC 防重复克隆缺失。
- **建议**：阶段 0 必须实现最小 NPC `heart_beat` 闭环：chat 概率触发、random_move 与门状态检查、aggressive attitude 的 init 主动攻击、NPC 自然恢复与死亡回收；否则世界会显得「死寂」，无法验证核心探索 / 战斗 / 社交循环。

### 6. 灵魂系统（死亡与轮回）

- **状态**：partial（死亡触发与昏迷实现，阴间与社交连锁缺失）
- **风险等级**：高
- **证据**：
  - `engine/src/xkx/runtime/death.py` 已实现 `check_death`、`unconcious`、`revive`、`die`、`reincarnate`、尸体生成与鬼魂标记，并接入 `ThemeConfig.death_room` 避免硬编码武侠路径。
  - 但阴间区域 `/d/death/` 未迁移；黑白无常多阶段 `call_out` 复活流程未实现；尸体腐烂四阶段与 `no_drop` 特殊物品保护未完整；鬼魂视觉隔离与 `astral_vision` 未实现；社交连锁（解散队伍、解除婚姻、师徒）未接入；PK 谣言频道与 `pker`/`killer` condition 不完整；丐帮「死亡奖励」特例未实现（`context_original_B.md` 2.4）。
- **建议**：M3 前至少实现最小阴间闭环：玩家死亡后 move 阴间入口、启动 `death_stage` EffectComp 计时、黑白无常 30 秒后触发还阳 / 惩罚选择；同时补全鬼魂不可见与 astral_vision 例外，否则 PronounContext 的可见性门控无法完整验证。

### 7. 门派与拜师练功任务链

- **状态**：partial（配置模型就绪，任务链与门派文化未闭合）
- **风险等级**：高
- **证据**：
  - `engine/src/xkx/dsl/layer0.py` 已声明 `ApprenticeDef` / `ApprenticeConditions` / `KneelDef`，支持声明式拜师条件、剃度、门派代际；`NpcDef.apprentice` 与 `NpcBehavior.apprentice_config` 已打通，`commands.py` 已落地 `bai` / `kneel` 命令。
  - `engine/src/xkx/runtime/components.py` `FamilyComp` 承载 family 7 字段 + betrayer 计数，`world.py` 生成师傅 NPC 时写入师傅门派信息。
  - 但 `themes/wuxia.py` 仅注入武当派一条 `FamilyBonus`，21 门派 family bonuses / class 表 / 门派任务链数据未迁移；`learn`、`practice`、`dazuo`、`tuna` 等练功命令与 `SkillData` 未闭合；门派专属任务（如雪山派入派、喇嘛剃度、丐帮拜师）的多步 chain 虽有 `QuestDef.objectives` 但缺少官方 CPK 内容。
- **建议**：M3-1 Wave 2 必须完成 1-2 个完整门派（如雪山派、武当派）的拜师条件、练功命令、门派任务链 CPK，作为门派文化保真的行为等价基线；并将 human.c 19 门派 if-else 加成逐步迁移为 `FamilyBonus` 数据。

## UGC 核心指标 / 系统分层建议

| 指标 / 系统 | 推荐 owner | 理由 | 主题无关性影响 |
|---|---|---|---|
| `do_attack` 七步管线与 `CombatKernel` 接口 | framework | 战斗内核必须是主题无关的纯函数；武侠 / 非武侠仅通过 `SkillData` 数据差异表达 | 强主题无关；第二题材唯一承重边界 |
| `PronounContext` 10 变量与 `visible` 门控 | framework | 文本渲染核心；`rankd.c` 三元组是 engine 层不变量 | 强主题无关；题材包只注入 class 表 |
| 技能三层（levels / apply_* / skill_map / prepare / learned） | framework | 是技能状态机的通用抽象；具体数值与条件由 CPK 注入 | 机制主题无关；门派技能数据主题相关 |
| `SkillData` 招式表与 `valid_learn` / `practice_skill` 条件 | official_cpk | 武侠招式、门派前置条件、武器类型是 `wuxia` 题材包 StdLib 资产 | 主题相关；必须走 `ThemeRegistry` 注入 |
| 门派加成 `FamilyBonus` / race_profile / class 称号表 | official_cpk | 21 门派文化数据是武侠题材包资产；引擎只提供分发框架 | 主题相关；`default` 题材包可注入非武侠 profile |
| 拜师配置 `ApprenticeDef` / 入门条件 / 剃度 / 门派任务链 | official_cpk / user_cpk | M3 由官方 CPK 闭合；后期可开放玩家自创门派 / 支线，但核心门派链在 UGC 开放前须官方锁定 | 主题相关；需受 `ThemeRegistry` 词汇表约束 |
| NPC `heart_beat` 调度框架（chat / random_move / attitude / vendetta） | framework | 是通用 NPC AI 更新机制；具体行为数据与对话由 CPK 提供 | 机制主题无关；野兽 / 商人 / 守卫等行为模式主题相关 |
| 灵魂系统核心（die / unconcious / reincarnate / death_penalty） | framework | 生死状态机是世界运行的基础设施；阴间剧情、死亡惩罚数值可由题材包配置 | 强主题无关；阴间地图 / 黑白无常文案主题相关 |
| 阴间区域 / 黑白无常 / 鬼魂视觉 / astral_vision | official_cpk | 属于武侠世界观下的具体剧情与区域设计 | 主题相关；核心提供 `ThemeConfig` 房间路径与 `visible` 钩子 |
| 自动化预检（暴力 / 赌博 / 版权 / license） | framework | 平台级内容审核基础设施 | 强主题无关；词表可配置 |

## 其他全局关注点

1. **层1 原语蠕变风险**：`dsl/layer1.py` 已扩展至 15+ 谓词与 4 类事件，ask / spawn_items / clear_flag 等新增能力符合 M2 需求，但需持续监控「层3 逃生舱使用率」KPI。若大量 LPC 触发器无法被层1/层2 表达而被迫下沉层3，说明层1 抽象不足，应优先扩充层1/层2 而非放松沙箱（ dissent #3）。

2. **Command / System 边界与 `force_me`**：当前 PrivilegedAction 已落地并带审计，但随着 M3 门派任务链复杂化，NPC / 触发器可能倾向于用 PrivilegedAction 驱动玩家动作（如师傅强制玩家 kneel）。必须保持 PrivilegedAction 为 ROOT 门控 + 强制审计的稀缺逃生舱，NPC AI 常规行为应走 `System.update`，否则 Command 仅覆盖外部意图的架构不变量会被侵蚀（dissent #6）。

3. **call_out 与 heart_beat 语义四分**：NPC AI、door 定时关闭、revive 延迟、黑白无常复活等依赖 call_out / 延迟事件，当前由 ConditionSystem `EffectComp` 承载。需确认 ConditionSystem 与 ActionScheduler 的边界已被显式文档化，避免 call_out 被错误统一进规则求值（dissent #5）。

4. **平台特性与核心循环并行风险**：M2 UGC 闭环（Agent / MCP / RAG / workbench）已落地 MVP，但阶段 0 核心循环（命令 / 战斗 / NPC / 死亡 / 门派）仍大量缺口。建议严格执行 ADR-0053 的 CLI workbench 范围，避免 FastAPI / WebSocket UI 过度投入挤占玩法实现人力（dissent #10）。

5. **版权与文化合规**：金庸衍生 71 文件必须处理后方可对外发布。`content_review` 当前仅将门派名 / 角色名标记为 `needs_review` 而不 block，符合 M3-4 后置清洗策略，但需在门3 前强制回填 provenance 链。

## Top 3-5 风险

1. **门派与技能数据缺口导致战斗文化空心化**：`SkillData` 注册表为空、`CombatState.action_message` 硬编码，若 M3 前不补齐 21 门派招式与称谓 class 表，demo 将退化为无武侠灵魂的 generic RPG。（高）

2. **NPC heart_beat 与 AI 未闭环使世界「死寂」**：chat / random_move / aggressive init / auto_perform / 商人 / 野兽均未完整实现，核心探索与社交循环无法验证。（高）

3. **灵魂 / 阴间系统缺失影响生死体验与 PronounContext 验证**：鬼魂视觉隔离、黑白无常复活、死亡社交连锁未落地，侠客行标志性的死亡惩罚与轮回文化无法体现。（高）

4. **Command 语义保真不足**：标准命令集缺失、大量命令带简化 / 后置注释，玩家日常交互（穿戴、存取、社交频道）的行为等价验证不足。（中）

5. **层1 原语蠕变与层3 使用率失控风险**：随着任务链复杂化，若层1/层2 表达力跟不上，可能被迫下沉 RestrictedPython，违反 <15% KPI 与「否决独立规则引擎」的裁决。（中）
