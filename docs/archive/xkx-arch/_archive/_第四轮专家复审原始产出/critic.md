# 第四轮专家复审 · 对抗质证报告

## 1. 专家结论的过度乐观 / 过度悲观

### 1.1 过度乐观：游戏服务器架构师的「solid」评定

架构师总体裁定为 **solid**，但证据链存在明显缺口：

- **100 并发命令未实测**：`tools/load_test.py` 仅构造 1000 个内存 `ConnectionSession`，未在 tick 内注入真实命令 dispatch。9.8ms p99 只反映 System tick，不包含 8 段中间件 + 世界查询的命令热路径。在单进程 asyncio 下，100 并发命令可能显著挤压 tick 预算。
- **1000 真实 WS 连接未验证**：压测未真的打开 1000 个 WebSocket 长连接；`websockets` 库在单进程下的 FD/GC/事件循环调度延迟仍是未知。
- **System 派生变更审计仅 combat 完整**：架构师承认 heal/condition/death/governance 直接 mutate 组件，但仍将整体评为 solid，对 dissent 7 的缓解状态过于宽松。

结论：在阶段 0 kill criteria 3/5/6 尚未完整判定前，「solid」评级过度乐观，应至少为 **risky with mitigations in progress**。

### 1.2 过度乐观：MUD 玩法与文化专家的部分「partial」评级

该评审将 `PronounContext` 标为 partial（框架 implemented，数据待填充），但实际上 `runtime/components.py` 的 `CombatState.action_message` 仍 hard-code 为 "一招「试探」"，且 `PronounService.render` 未接入 combat 渲染路径。framework 层功能尚未闭环，评级应为 **partial-at-risk**。

同样，`do_attack` 七步管线被评为「内核 solid」，但外围招式数据（`SkillData` 注册表为空 stub、`perform`/`exert` 后置）使战斗 demo 会退化为 generic RPG，文化表达已严重受损。

### 1.3 过度悲观：ECS 专家对 `ConditionSystem` 的批评部分可商榷

ECS 专家指出 `EffectComp` 被多 System 共用、靠 `effect_id` 字符串过滤存在遗漏风险。但源码中：

- `ConditionSystem` 已实现 `ConditionTickResult` 统一账本，handler 注册表机制完整；
- `death_stage` / `door_close` 的过滤约定虽未在类型系统显式表达，但 `JAIL_CONDITIONS` 与 governance 的调用链路已在 ADR-0029 中裁决；
- 这不是「未实现审计」，而是「审计契约未类型化」。风险等级应从中-高调为中，建议用 `owner_system` 字段显式标注而非重构整个机制。

### 1.4 过度悲观：制作人对 M3 窗口的估算

制作人判断 M3 范围过载，但忽略了 ADR-0053 已将 layer2/3、FastAPI workbench、Langfuse 明确延后，且 M2 MVP 已通过 revision 30.3% 的弱信号验证。M3 压力确实存在，但平台特性并非并行无限扩张——ADR-0053 的 CLI workbench 与 layer0/1 闭合策略实际上在收缩 M2 范围。建议将「范围过载」从 high 调为 medium-high，并强调 ADR-0053 的收敛作用。

---

## 2. 专家共同遗漏的关键缺口

### 2.1 `command` 事件未接入 8 段命令管线

DSL 规则引擎专家明确指出的问题，但架构师、ECS 专家、UGC 专家均未提及：`layer1.py` 已实现 `evaluate_command`，但 `runtime/commands.py` 的 `COMMAND_REGISTRY` / 中间件并未调用它。这意味着自定义命令前置 deny（如 `knock` / `enter`）存在绕过层1 护栏的路径，是 02 Q2「唯一规则表示层」裁决的直接侵蚀。

### 2.2 `status_eq` 的脆弱集合字符串编码

规则引擎专家指出 `EvalContext.actor_flags` 用 `flag=value` 字符串约定支持值比较，破坏集合语义且易被 UGC 文本误触发。该问题未在其他评审中出现，但会影响层1 规则的正确性与安全性。

### 2.3 `ThemeRegistry` 词汇表未真正启用

所有专家都提到 `condition_predicates` / `action_verbs` 为空，但没有人追问其后果：CPK 加载器目前不校验规则谓词/动作是否在 ThemeRegistry 注册，LLM 生成的规则可能使用未注册谓词，导致运行时静默失败或语义漂移。这是层1 原语蠕变的直接技术根因。

### 2.4 版权清洗的 71 文件清单未产出

多位专家提到金庸衍生内容需处理，但无人指出「71 文件清单」尚未存在具体文件或脚本。`content_review` 仅标记 `needs_review`，但清洗 SOP、替换名标准、同人标注规范均未落地。这是 M3 对外发布的真实阻断点。

### 2.5 非武侠微场景硬门禁缺失

制作人建议增设，但未检查 `themes/default.py` 当前状态：仅有「海盗帮」一条 `FamilyBonus`，无完整房间/NPC/任务/战斗链。第二题材尚未真实存在，主题无关性仍是文档声明。

---

## 3. UGC 分层判断中会让框架不再题材无关的陷阱

### 3.1 `module_pack` 与 `ugc` 边界名存实亡

UGC 平台专家指出 `pack_type` 只是字符串字段，Orchestrator 硬编码输出 `module_pack`，加载器不做区分。这不仅是安全问题，更是**题材无关性陷阱**：一旦外部作者将 `pack_type` 写成 `module_pack` 并注入武侠专属逻辑（如 `FamilyBonus` 硬编码门派名），框架将被迫识别和处理题材相关内容，破坏主题无关性边界。

### 3.2 层1 谓词/动作词汇表未绑定 ThemeRegistry

规则引擎专家指出 `capabilities_required` 与词汇表未绑定。当前 `Predicate` 中已有 `family_eq` / `has_item` 等谓词，但 `family_eq` 直接引用「门派」概念——若题材包未注册 `family_eq` 谓词，而 CPK 规则仍使用它，则引擎在运行时会默认按武侠语义解释，造成**隐式题材语义泄漏**。

### 3.3 `command` 事件动词下沉题材包的风险

`EventRule.verb` 允许命令动词绑定。若题材包注册的 action_verbs 包含武侠专属动词（如 `bai`、`kneel`、`dazuo`），而引擎未校验其注册来源，则非武侠题材包可能被迫理解这些动词，或引擎默认将其视为通用命令，导致命令管线语义漂移。

### 3.4 `SkillData` 招式表与 CombatKernel 的边界

多位专家认为 `SkillData` 是 official_cpk 资产、不进 combat 内核。但 `CombatState.action_message` 当前 hard-code「试探」，若未来 `query_action` 需要读取招式名/武器标志位/perform 条件，而 `SkillData` schema 由武侠题材定义，则 CombatKernel 接口可能被武侠数据结构塑形，主题无关性受损。必须保持 CombatKernel 只接收泛化的 `attack_type`/`skill_id` + 数值参数，招式解析完全在 runtime adapter 层完成。

---

## 4. 对第三轮 dissent 缓解状态评估是否过于草率？

### 4.1 dissent 5：call_out / ActionScheduler 归属仍未消除

ECS 专家正确指出风险，但评估仍显草率：

- 当前 `call_out` 被分散到 `EffectComp.next_tick`、`ConditionSystem`、`GovernanceSystem`、`DoorSystem`；
- `ActionScheduler` 抽象仍未实现；
- 专家仅建议「补一个原型」，但未要求写入 kill criteria 或 ADR 强制门。

建议：将「ActionScheduler 原型 + 694 文件/3109 处 call_out 归属映射」设为阶段 0/阶段 1 交界硬门禁。

### 4.2 dissent 7：System 派生变更审计覆盖不完整

架构师与 ECS 专家均承认 combat 外 System 缺少统一审计，但结论差异大：

- 架构师将其列为 medium risk；
- ECS 专家将其列为中-高。

实际上 `HealSystem` 直接 mutate `Vitals` 且无任何 ledger（仅 `update_flag` 计数），`GovernanceSystem` 也未产出统一 effect 账本。这是 dissent 7 的核心——System tick 派生变更缺少 Command 级审计轨迹。当前缓解仅为 dirty-flag 标记，不足以支撑未来反作弊、bug 追溯、数据修复。应统一标记为 **high**，并要求在 `SystemContext` / `World` 中增加 mutation 钩子。

### 4.3 dissent 3：层1 原语蠕变缓解被高估

多位专家认为当前层1 扩展「每次都有 ADR」是控制手段，但这不等于风险已缓解。事实是：

- 谓词从 S1 的 4 个增至 15+ 叶子 + 组合；
- ThemeRegistry 词汇表为空；
- CPK 加载器不校验规则词汇。

这意味着层1 实际上已经是一个**无词汇表门禁的事实规则引擎**。ADR 审批流程无法替代运行时硬门禁，dissent 3 风险应重新标为 **high**。

### 4.4 dissent 10：Agent/UGC 投入挤占核心循环

制作人正确指出风险，但 ADR-0053 已通过 CLI workbench、延后 layer2/3、Langfuse 后置进行范围收缩。当前评估应更精确：M2 闭环本身不挤占核心循环，但 `workbench/` 目录中 FastAPI/WebSocket 后端仍然存在（尽管 ADR-0053 说后置），这是实际的人力分散点。

---

## 5. 源码/ADR 与专家断言矛盾的证据

### 5.1 与架构师断言矛盾：System 基类并非「应尽快提供默认骨架」那么简单

架构师建议 `System` 基类提供默认 `update` 骨架。但 `systems.py` 第 17-34 行明确将 `System` 设计为抽象基类，注释引用 ADR-0014/dissent 7，要求子类 override `update` 并走 Effect 账本。直接提供默认骨架可能与 ADR-0017/0023 的 combat-only 确定性边界冲突——非 combat System 的 Effect 账本格式尚未统一。建议先统一 `Effect`/`LedgerEntry` schema，再提供默认骨架。

### 5.2 与 ECS 专家断言矛盾：`HealSystem` 已继承 `System`

ECS 专家原文：「`HealSystem` 已实现但**未继承 `System`**（源码第 37 行 `class HealSystem(System)` 已继承，OK）」。这是专家自我修正，但需指出：源码 `heal.py` 第 37 行确实 `class HealSystem(System)`，且 `update` 方法已实现。真正的问题不是继承，而是 `heal_up` 直接 mutate 组件无 ledger。

### 5.3 与 UGC 专家断言一致：Orchestrator 硬编码 `module_pack`

`orchestrator/loop.py` 第 187 行附近确实硬编码输出 `module_pack`（需精确验证），与 UGC 专家断言一致。这构成安全与题材无关性双重风险。

### 5.4 与规则引擎专家断言矛盾：`command` 事件求值函数存在但未接入命令管线

`layer1.py` 第 34 行定义 `EVENT_COMMAND`，且存在 `evaluate_command` 函数（虽未在本次读取范围内完整展示），但 `runtime/commands.py` 的 `run_pipeline` / 中间件未调用它。规则引擎专家的断言成立。

### 5.5 与制作人断言部分矛盾：ADR-0053 已收缩 M2 范围

制作人认为平台特性与引擎重构并行推进、存在挤占风险，但 ADR-0053 明确：

- 不实现 layer2/3；
- CLI workbench 替代 FastAPI/WebSocket Web UI；
- Langfuse 后置。

然而源码 `engine/src/xkx/workbench/` 仍然存在 FastAPI/WebSocket 后端，与 ADR-0053 的「CLI 替代 Web UI」存在执行落差。这是挤占风险的实际证据。

---

## 6. 关键建议（按优先级）

1. **立即设置 5 个硬门禁**：
   - 100 并发命令注入压测（kill criteria 3）
   - 1000 真实 WS 连接压测（kill criteria 5）
   - 非武侠微场景 e2e（default 题材，5-10 房间 + 战斗 + 任务）
   - ThemeRegistry 词汇表启用 + CPK 规则词汇校验
   - `command` 事件接入 8 段命令管线

2. **重新评级 dissent 缓解状态**：
   - dissent 3（层1 蠕变）：medium -> high
   - dissent 5（call_out）：medium -> high
   - dissent 7（System 审计）：medium -> high
   - dissent 10（挤占）：medium（因 ADR-0053 已收缩）

3. **题材无关性保护动作**：
   - 为 `EffectComp` 增加 `owner_system` 字段；
   - 将 `SkillData` 解析完全隔离在 runtime adapter，禁止 CombatKernel 依赖武侠 schema；
   - `module_pack` 引入受信任发布者白名单/签名，关闭外部作者任意声明 `module_pack` 的路径。

4. **版权合规落地**：
   - 产出 71 文件金庸衍生清单；
   - 制定替换名/同人标注 SOP；
   - 在门3 前实现 `content_hash`/`prompt_hash` provenance 回填。

---

*质证人：对抗 reviewer*  
*日期：2026-07-15*
