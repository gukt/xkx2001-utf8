# 第四轮专家复审 Digest

> 整理日期：2026-07-15  
> 评审对象：`feat/m2-ugc-loop-r2` 分支 engine 实现现状（M2/UGC 创作闭环 MVP 后）  
> 源文件：同目录下 6 份专家评审 + 1 份对抗质证 + 2 份上下文摘要

---

## 1. 评审目的

在 M2/UGC 创作闭环 MVP 落地后，对 engine 实现进行一次跨领域的集中复审，判定：

- 引擎核心系统（ECS、tick、命令管线、战斗、NPC、死亡轮回、持久化）距 M3 可玩 demo 的缺口；
- UGC 分层边界（framework / official_cpk / user_cpk）是否仍然清晰、题材无关性是否守住；
- 第三轮专家复审中 10 条 dissent（尤其是 dissent 3/5/6/7/10）的缓解状态；
- M3 范围、kill criteria、版权合规、性能硬门禁的可行性。

---

## 2. 专家组成

| 角色 | 文件名 | 总体裁定 |
|---|---|---|
| 游戏服务器架构师 | `review_0_游戏服务器架构师.md` | solid |
| 游戏引擎 / ECS 专家 | `review_1_游戏引擎ECS专家.md` | risky |
| MUD 玩法与文化专家 | `review_2_MUD玩法与文化专家.md` | risky |
| UGC 平台 / 插件架构专家 | `review_3_UGC平台插件架构专家.md` | risky |
| DSL / 规则引擎专家 | `review_4_DSL规则引擎专家.md` | risky |
| 游戏制作人 / 范围管理 | `review_5_游戏制作人范围管理.md` | risky |
| 对抗质证人 | `critic.md` | 对架构师「solid」评定提出过度乐观质疑，并建议将若干 dissent 风险重新上调 |

---

## 3. 总体裁定

**M2/UGC 创作闭环 MVP 已落地，revision 30.3% 低于 40% 走弱线，是本轮最大正面证据；但引擎核心系统与侠客行规格的缺口仍然显著，且多个 dissent 风险未真正消除。整体应判定为 risky with mitigations in progress。**

- 正面：DSL layer0/1 闭合、Orchestrator + MCP + CLI workbench 跑通、命令 8 段管线 + 30+ 命令 e2e、combat-only 确定性边界守住、JSON 存档崩溃安全三要素（原子写 / offload / dirty-flag）已落地。
- 负面：
  - 100 并发命令与 1000 真实 WS 连接均未纳入性能实测；
  - System 基类仍是 stub，tick 驱动语义四分未收敛；
  - System 派生变更审计仅 combat 完整，heal / condition / death / governance 直接 mutate 组件无统一 ledger；
  - DSL 层3 RestrictedPython 沙箱缺失，`module_pack` / `ugc` 边界名存实亡；
  - ThemeRegistry 词汇表未启用，层1 原语蠕变风险被低估；
  - 21 门派 / 97 技能 `SkillData` 招式表为空，战斗文化表达空心化；
  - 金庸衍生 71 文件版权清洗尚未启动，外部发布存在真实阻断点。

---

## 4. 十大关键发现

1. **M2/UGC 闭环 MVP 已闭合**。Orchestrator 跑通生成 -> MCP 校验 -> 修订 -> 预检，CLI workbench 替代 Web UI，语义修订率 30.3% 低于 40% 走弱线（ADR-0053）。
2. **System 基类仍是 stub**。`runtime/systems.py` 的 `System.update` 抛出 `NotImplementedError`；`CombatBridge` / `ConditionSystem` / `HealSystem` / `GovernanceSystem` / `DoorSystem` 等以 ad-hoc 方式接入 `Engine`，未收敛到统一注册表与 phase 机制。
3. **100 并发命令未纳入 tick 预算实测**。`tools/load_test.py` 只构造 1000 个内存 `ConnectionSession` 并跑 System tick，未在 tick 内注入真实命令 dispatch；8 段中间件 + 世界查询的热路径开销未知。
4. **1000 真实 WS 连接容量未验证**。压测未真正打开 1000 个 WebSocket 长连接；`websockets` 库、asyncio 事件循环、FD 限制、GC 行为在真实高连接下仍是未知数。
5. **System 派生变更审计覆盖缺口**。仅 `CombatSystem` 有 `CombatBridge` / `pending_messages` 副作用账本；`HealSystem`、`ConditionSystem`、`GovernanceSystem` 直接 mutate 组件，缺少统一 mutation ledger， dissent 7 未真正缓解。
6. **DSL 层3 RestrictedPython 沙箱缺失**。UGC 脚本无法安全下沉，任何图灵完备逻辑仍依赖进程级 Python；`module_pack` / `ugc` 仅靠字符串字段区分，无签名 / 白名单 / 沙箱 / 配额，安全边界名存实亡。
7. **ThemeRegistry 词汇表未启用**。`condition_predicates` / `action_verbs` / `class_tables` 为空或仅部分填充，CPK 加载器不校验规则谓词 / 动作是否注册，层1 实际上已成无硬门禁的事实规则引擎（ dissent 3 风险应上调为 high）。
8. **`command` 事件未接入 8 段命令管线**。`layer1.py` 已实现 `evaluate_command`，但 `runtime/commands.py` 的 `COMMAND_REGISTRY` / 中间件未调用；自定义命令前置 deny（如 `knock` / `enter`）可能绕过层1 护栏。
9. **SkillData 招式表为空，战斗文化表达空心化**。`CombatState.action_message` 仍 hard-code 为「试探」，21 门派 / 97 技能招式数据未迁移，`perform` / `exert` / `jiali` / `jiajin` 后置，M3 demo 有退化为 generic RPG 的风险。
10. **金庸衍生 71 文件版权清洗未启动**。`content_review` 仅将角色名 / 门派名 / 出处小说标记为 `needs_review` 而不 block；71 文件清单、替换名 SOP、同人标注规范均未产出，M3 对外发布存在法律阻断点。

---

## 5. UGC 分层结论

| 层级 | 推荐 owner | 核心职责 |
|---|---|---|
| **framework** | 平台核心开发者 | ECS / tick 调度 / Command 8 段管线 / `do_attack` CombatKernel / PronounContext / JSON 存档持久化边界 / DSL 层1 求值器 / ThemeRegistry 机制 / CPK 加载器与四道校验 / RestrictedPython 沙箱 / 自动化预检与审核 pipeline / 市场分发字段 Day1 预留 / provenance 与版权追踪基础设施 |
| **official_cpk** | 受信任开发者 / 官方 StdLib | 武侠 `wuxia` 题材包数据：`RaceProfile` / `FamilyBonus` / class 称号表 / `SkillData` 招式表 / 房间路径（`ThemeConfig`）/ 门派任务链 / 拜师配置 / 非武侠 `default` 测试题材数据 |
| **user_cpk** | 普通创作者（后置 Wave 3） | 原创第三方门派 / 区域 / 任务 / 玩家自建房间 / NPC 事件规则 / 层2 对话树；必须声明 theme 与 capabilities，受沙箱与配额约束 |

**守住题材无关性的三个硬约束**：

- `EffectComp` 应增加 `owner_system` 字段，禁止多 System 靠字符串 `effect_id` 隐式过滤；
- `SkillData` 解析必须完全隔离在 runtime adapter 层，CombatKernel 只接收泛化 `attack_type` / `skill_id` + 数值参数；
- `module_pack` 必须引入受信任发布者白名单或签名机制，关闭外部作者任意声明 `module_pack` 的路径。

---

## 6. 最大风险

1. **M3 范围过载**：平台特性（Agent / MCP / RAG / workbench）与引擎重构（门派 / 技能 / NPC AI / 死亡 / 世界构建）并行推进，6-8 个月窗口内核心循环验证时间被挤压。
2. **性能硬门禁未验证**：100 并发命令 + 1000 真实 WS 连接 + 长时间 GC 压力均未实测，纯 Python 单机 1000+100 仍是未证实的赌注。
3. **UGC 安全边界悬空**：层3 沙箱、`module_pack` 受信任模型、capabilities 与 ThemeRegistry 词汇表绑定均未实现，外部 CPK 可借 `module_pack` 执行任意进程级 Python。
4. **System 变更审计缺口**：非 combat System 直接 mutate 组件，缺少统一 ledger，未来反作弊、bug 追溯、数据修复能力受限。
5. **版权合规债务**：71 文件金庸衍生内容未清洗，M3 demo 无法对外发布。

---

## 7. 下一步建议

### 7.1 立即设置 5 个硬门禁

1. **100 并发命令注入压测**：在 `tools/load_test.py` 中每 tick 注入 100 条随机命令，确认 tick p99 仍 <100ms；作为 kill criteria 3 完整判定必选项。
2. **1000 真实 WS 连接压测**：验证 `websockets` 库、asyncio 事件循环、FD/GC 在单进程下的承载边界；作为 kill criteria 5 完整判定必选项。
3. **非武侠微场景 e2e 硬门禁**：在 `default` 题材下构造 5-10 房间 + 2 NPC + 1 战斗 + 1 任务，全部不得引用武侠语义。
4. **ThemeRegistry 词汇表启用 + CPK 规则词汇校验**：填充 `condition_predicates` / `action_verbs`，加载器对未注册谓词 / 动作报错。
5. **`command` 事件接入 8 段命令管线**：在中间件或 adapter 中调用 `evaluate_command`，确保 deny-wins 与 `notify_fail` 语义对齐。

### 7.2 重新评级 dissent 缓解状态

| dissent | 当前评级 | 建议评级 | 理由 |
|---|---|---|---|
| dissent 3：层1 原语蠕变 | medium | **high** | 谓词从 4 个增至 15+，词汇表为空，加载器无校验 |
| dissent 5：call_out 归属 | medium | **high** | `ActionScheduler` 仍未实现，call_out 分散于各 System |
| dissent 7：System 审计 | medium | **high** | 仅 combat 有 ledger，heal/condition/governance 直接 mutate |
| dissent 10：Agent 挤占核心循环 | high | **medium-high** | ADR-0053 已收缩 M2 范围，但 `workbench/` FastAPI/WebSocket 后端仍存在执行落差 |

### 7.3 题材无关性保护动作

- 为 `EffectComp` 增加 `owner_system: str` 字段；
- 将 `SkillData` 解析完全隔离在 runtime adapter，禁止 CombatKernel 依赖武侠 schema；
- `module_pack` 引入受信任发布者白名单 / 签名，关闭外部作者任意声明 `module_pack` 的路径。

### 7.4 版权合规落地

- 产出 71 文件金庸衍生清单；
- 制定替换名 / 同人标注 SOP；
- 在门3 前实现 `content_hash` / `prompt_hash` provenance 回填。

---

## 8. 建议新增的 ADR

| 建议 ADR | 标题 | 核心 rationale |
|---|---|---|
| ADR-0055 | 100+1000 性能门禁测试策略 | kill criteria 3/5/6 要求 1000 实体 tick、100 并发命令、1000 WS 连接的 go/no-go 判定；当前仅单函数微基准，需明确测试矩阵、阈值、降级策略与 CI 集成方式。 |
| ADR-0056 | System 变更审计与 mutation ledger | dissent 7 要求 Command 与 System tick 派生变更均留下审计轨迹；需统一 `SystemContext` / `World` 的 mutation 钩子与 `LedgerEntry` schema，覆盖 combat 之外 System。 |
| ADR-0057 | ThemeRegistry 词汇表与 capability 绑定 | 层1 作为唯一规则表示层，必须通过 ThemeRegistry 显式注册谓词 / 动作 / 事件；CPK `capabilities_required` 应映射为词汇表子集 + 运行时权限，防止层1 原语蠕变。 |
| ADR-0058 | module_pack 受信任发布者模型 | `pack_type` 字段不足以构成安全边界；需定义签名、白名单、内容哈希校验与发布者审计，使 `module_pack` 与 `ugc` 的区分具备可执行性。 |
| ADR-0059 | 金庸衍生内容清洗 SOP | 04 / kill criteria 明确 71 文件金庸衍生必须处理后方可对外发布；需制定替换名标准、同人标注规范、provenance 回填流程与门3 检查点。 |
| ADR-0060 | ActionScheduler 与 call_out 归属 | dissent 5 要求把延迟 / 自递归调度从 `EffectComp.next_tick` 与各 System 隐式过滤中剥离；需明确 ActionScheduler 与 ConditionSystem / 层1 事件 / combat 仿真的边界。 |

---

*本 digest 为同目录 6 份专家评审与 1 份质证报告的综合摘要，详细证据与引用请见各原始文件。*
