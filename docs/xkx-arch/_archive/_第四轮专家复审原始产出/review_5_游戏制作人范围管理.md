# 第四轮专家评审：游戏制作人 / 范围管理

> 评审身份：第四轮专家团 · 游戏制作人 / 范围管理  
> 评审日期：2026-07-15  
> 评审范围：M2/M3 范围、kill criteria、里程碑可行性、内容生产（LLM）vs 引擎能力边界、版权与合规、主题无关性验收  
> 依据上下文：context_engine.md / context_original_A.md / context_original_B.md / context_third.md / context_ugc.md，以及 ADR-0046、ADR-0053、ADR-0054、PROGRESS.md、04-迁移路径与避坑清单

---

## 总体裁定

**verdict：risky**

M2/UGC 创作闭环 MVP 已落地（layer0/1 闭合、Orchestrator + MCP + CLI workbench、revision 30.3% 低于 40% 走弱线），这是本阶段最大正面证据；但 DSL 层3 沙箱缺失、阶段 0 性能硬门禁尚未产出报告、引擎核心系统（门派/技能/房间/NPC AI/频道/经济/死亡轮回）与侠客行规格缺口仍然巨大，平台特性与引擎重构并行推进，M3（单题材可玩 demo）的 6-8 个月窗口承受显著范围过载风险。

---

## 当前实现与侠客行核心系统的缺口

| 系统 | 状态 | 风险等级 | 证据 | 建议 |
|------|------|----------|------|------|
| **架构总览 / ECS 骨架** | partial | 中 | `engine/src/xkx/runtime/ecs.py`、`runtime/components.py`、`runtime/world.py` 已就位；`runtime/systems.py` 仍是基类 stub，`System.update` 抛 `NotImplementedError` | 阶段 1 必须将 CombatSystem / ConditionSystem / HealSystem / DoorSystem / GovernanceSystem / StorageSystem 收敛到统一 System 注册表，否则 tick 驱动语义四分无法落地 |
| **守护进程系统** | partial | 高 | `runtime/login.py`、`runtime/commands.py`+`middleware/`、`runtime/conditions.py`、`runtime/heal.py`、`runtime/storage.py`、`runtime/governance.py` 部分落地；`CHANNEL_D` / `NATURE_D` / `MONEY_D` / `UPDATE_D` / `ALIAS_D` / `EMOTE_D` / `BAN_D` / `FINGER_D` / `VIRTUAL_D` / `WEAPON_D` / `MARRY_D` 缺失 | 按 ADR-0014  daemon 职责重设计逐一标注：被 ECS System 取代 / 保留无状态服务 / 演进为新能力；优先补齐 NATURE_D（昼夜天气）、MONEY_D（经济）、CHANNEL_D（社交） |
| **命令系统** | partial | 中 | `runtime/commands.py` + 8 段中间件已落地；覆盖 go/kill/fight/ask/give/quest/take/look/hp 等约 30 条 | 命令面宽但深度参差，大量命令带简化/后置注释；建议按 M3 核心循环（拜师/练功/战斗/任务/死亡）列命令缺口清单，避免无差别补全 |
| **对象与继承体系** | partial | 高 | `runtime/components.py` 16 个组件；`runtime/equipment.py`、`runtime/skill.py`、`runtime/death.py`、`runtime/serialization.py` 就位 | F_AUTOLOAD / F_SAVE 分目录 `.o` 模型、F_TEAM / F_MARRY / F_APPRENTICE、负重传递链、消息缓冲 `F_MESSAGE` 未完整；M3 前必须明确组件-特性映射表 |
| **世界构建系统** | partial | 高 | `dsl/layer0.py`、`dsl/ir.py`、`runtime/world.py`、`runtime/doors.py`、`themes/wuxia.py`/`default.py` 就位 | 6000+ `/d/` 房间未迁移；VIRTUAL_D、`reset()` / `make_inventory()`、商店/钱庄/海港/渡船、户外天气缺失；M3 前必须完成代表区域（如雪山-终南-书院）全量 DSL 化 |
| **武功与战斗系统** | partial | 高 | `combat/resolve_attack.py` 七步管线 + `skill_power` 公式 + hypothesis 属性测试；`combat/replay.py` 确定性回放 | 21 门派 / 97 技能未迁移；`perform` / `exert` / `jiali` / `jiajin`、阵法合击、武器标志位、多数 condition handler 缺失；M3 前必须补齐技能三层与招式数据 |
| **多人交互系统** | partial / missing | 高 | `runtime/connection.py`、`runtime/governance.py` 部分落地 | 频道/组队/跟随/表情/婚姻/交易/银行/`say`/`tell` 缺失；这些是 M3 可玩 demo 的社交骨架，建议尽早补齐最简经济 + 组队 + 房间/频道消息 |
| **死亡与轮回系统** | partial | 高 | `runtime/death.py`、`runtime/governance.py`、`runtime/heal.py` 就位 | 阴间 `/d/death/` 区域、黑白无常多阶段 `call_out`、尸体腐烂、鬼魂视觉隔离、`astral_vision`、PK 谣言频道不完整；M3 必须能跑通“死亡-阴间-复活”主循环 |
| **坐骑与交通系统** | missing | 中 | `MountComp` / `VehicleComp` / `FerryComp` / `ShipComp` 待补 | 当前无组件；如 M3 不包含交通玩法可明确后置，但需在 04 / kill criteria 中写明 |
| **NPC AI 与行为系统** | partial | 高 | `runtime/components.py` 基座、`runtime/auto_fight.py`、`runtime/skill.py` 就位 | `chat_chance`/`chat_msg`、`random_move`、attitude 驱动主动攻击、师父收徒、商人、野兽种族、`reset()` / `return_home`、唯一 NPC 防重复均未完整；M3 可玩性高度依赖 NPC AI |
| **世界观与文案** | partial / missing | 中 | `themes/wuxia.py`、`dsl/layer0.py`、`content_gen/prompts.py`、`workbench/` 就位 | 8000+ 房间/NPC 原始文案未迁移；`item_desc` / `inquiry` 交互式描述未完整建模；区域势力表 `REGIONS.h` 未导入；LLM 生成文案的风格一致性与版本控制待固化 |
| **InterMUD 网络系统** | missing | 低 | 无直接对应模块 | 与六条收缩约束一致，UGC 验证前明确不做；风险可控 |
| **武林大会与竞技系统** | missing | 低 | 无直接对应模块 | 属于 M3 后可选项，不影响核心闭环验证；风险可控 |

---

## UGC 核心指标 / 系统分层建议

| 指标 / 系统 | 推荐 owner | 理由 | 主题无关性影响 |
|-------------|------------|------|----------------|
| heart_beat tick 周期（1s，compute<100ms） | framework | 引擎核心调度不变量，所有题材共享 | 强主题无关，不允许题材包覆盖 |
| ECS 组件生命周期 | framework | 核心运行时基础设施 | 强主题无关 |
| Command 管线（意图 → ActionContext → Capability 校验） | framework | 外部意图抽象 | 强主题无关；具体命令实现可下沉题材包 |
| `do_attack` 七步管线 | framework | CombatKernel 抽象，主题无关 | 强主题无关；招式数据走 SkillData |
| PronounContext 三元组 | framework | 文本渲染核心，`rankd.c` 实证 | 强主题无关 |
| JSON 存档原子写 + dirty-flag | framework | 持久化边界抽象 | 强主题无关 |
| 层1 规则求值器 | framework | 唯一规则表示层，引擎内求值 | 主题无关；谓词/动词词汇表由题材包注册 |
| layer0 schema 验证框架 | framework | schema 由 ThemeRegistry 注册，核心提供验证框架 | 框架主题无关；具体 schema family 题材相关 |
| ThemeRegistry 静态加载 | framework | 启动时注册表，引擎层机制 | 强主题无关；内容题材相关 |
| CPK 加载器 + 四道校验 | framework | DSL 编译与依赖校验基础设施 | 强主题无关 |
| **RestrictedPython 沙箱（层3）** | **framework** | UGC 脚本执行环境，当前缺失；必须平台级统一实现 | 强主题无关；具体 capability 由题材包声明 |
| 自动化预检（暴力/赌博/版权/license） | framework | 内容审核基础设施 | 强主题无关；词表可配置 |
| 专家审核 checklist 模板 | framework | 六维矩阵与人工 review 框架 | 强主题无关 |
| 武侠门派加成 / race_profile / class 表 / SkillData | official_cpk | `wuxia` 题材包 StdLib 资产 | 主题相关；必须走 ThemeRegistry 注入 |
| 武侠房间路径（start/death/jail rooms） | official_cpk | `wuxia` 题材包 ThemeConfig | 主题相关；核心通过 ThemeConfig 抽象 |
| 门派任务链数据 | official_cpk / user_cpk | 内容生产产出；M3 官方，后期可 UGC | 主题相关 |
| 原创第三方门派 / 区域 CPK | user_cpk | UGC 创作者产出，受沙箱与审核约束 | 主题相关；需声明 theme 与 capabilities |
| 玩家自建房间 / NPC 事件规则 | user_cpk | UGC layer0/1 资产 | 主题相关；受 ThemeRegistry 词汇表限制 |
| 市场分发（浏览/搜索/安装/评分/分账） | framework | 平台级能力，manifest 字段 Day1 预留 | 强主题无关；M3 不做 |
| 版权清洗状态与 provenance 链 | framework | 平台级合规与内容追踪 | 强主题无关；命中内容由题材包产生 |
| Agent 修订量 / token 预算追踪 | framework | M2 创作闭环度量基础设施 | 强主题无关 |

### 制作人视角的关键分层判断

1. **层3 沙箱是当前最大 UGC 能力缺口**。M2 MVP 通过延后 layer2/3 成功闭合 loop，但真正的“用户可编辑规则”必须依赖 RestrictedPython 沙箱 + 资源配额。建议将 layer3 沙箱从“M3 后”提前到“M3 前原型验证”，否则 UGC 只能停留在官方 CPK 级别，创作者经济假设无法验证。
2. **层1 原语蠕变需持续监控**。当前 layer1 已扩展 ask/clearflag/spawnitems 等原语（ADR-0040），符合“可声明式且跨规则复用才扩层1”原则；但需每轮 Agent 产出后统计层1/2/3 使用占比，确保层3 < 15% KPI 不被绕过。
3. **ThemeRegistry 静态加载与“第二个题材真实存在”触发条件**。当前仅 wuxia/default 两个 descriptor，default 只有海盗帮 FamilyBonus 作为边界测试。建议在 M3 前至少完成一个完整非武侠微场景（如 academy / age_of_sail），独立跑通 CombatKernel，否则主题无关性只是文档声明。

---

## 其他全局关注点

### 1. 里程碑可行性与范围过载

- **M2 已交付**：DSL+Agent 闭环 demo、revision 30.3% 低于 40% 线，是正向信号。
- **M3 压力巨大**：6-8 个月内需完成“拜师、练功、战斗、任务、死亡轮回可玩” + 官方 StdLib CPK + 审核 pipeline MVP + 版权清洗。当前 engine 距此目标仍有大量系统处于 partial/missing 状态。
- **平台特性与引擎重构并行**：content_gen / orchestrator / workbench / MCP / RAG 与 runtime / combat / NPC AI / 世界构建同步推进，存在挤占人工/算力的风险。建议在 M3 前将 Agent/UGC 投入压缩到“维持闭环可用即可”，把主力集中到核心循环验证。

### 2. 内容生产（LLM）vs 引擎能力边界

- LLM 当前产出 layer0/1 为主，layer2 对话树刚落地（InquiryNode），layer3 完全缺失。若后续发现大量创作者需求必须下沉到层3，将直接冲击沙箱与配额设计。
- `semantic_ratio` 30.3% 是单 CPK / 单轮次结果，需在更多样本、更复杂规则（含 layer2 对话分支、层1 条件组合）上验证稳定性。
- 火山方舟主 LLM + `LLMClient` Protocol 设计合理，但需保留未来接入 Claude/GLM 的回归测试位，避免被单一供应商锁定。

### 3. 版权与合规

- 当前 `content_review` 对金庸角色名 / 门派名 / 出处小说仅标记 `needs_review`，不 block（M3-4 版权清洗后置）。
- 04 / kill criteria 明确“金庸衍生 71 文件必须处理后方可对外发布”。M3 前必须制定清洗 SOP（替换名 / 重写描述 / 标注 provenance），否则 M3 demo 无法公开。
- 自动化预检的 SENSITIVE 词表当前为空表，需法务确认后填充； license 校验在 M3 宽松，但需在门3 前严格化白名单。

### 4. 主题无关性验收

- CombatKernel 从武侠 do_attack 七步提取已完成，但主题无关性验证仍依赖 wuxia 数据。
- `themes/default.py` 仅含海盗帮 FamilyBonus，未形成可独立运行的非武侠微场景。
- 建议在阶段 0/阶段 1 交界处增设“非武侠微场景 e2e 测试”硬门禁：5-10 房间 + 2 NPC + 1 战斗 + 1 任务，全部走 default 题材包，且不得引用任何武侠语义。

### 5. 性能与 kill criteria

- `TickProfiler` 已就位，但阶段 0 的 micro-benchmark go/no-go 报告尚未产出。
- 1000+100 负载测试、PYTHONHASHSEED=0、GC 基准均未执行；kill criteria 3/6/9 的触发条件尚未被验证。
- 建议在外部玩家测试前严格执行“JSON 存档迁 PG”硬止损线，当前 `JsonFileBackend` 已标注事务原子性 / CAS / 关系完整性 / append-only 防篡改为 PG 语义，符合 ADR-0022 台账。

---

## Top 3-5 风险

1. **M3 范围过载：平台特性与引擎重构并行，挤压核心循环验证时间**
   - severity: high
   - 细节：M2/UGC 闭环虽落地，但 M3 需在 6-8 月内补齐战斗外大量核心系统（门派/技能/频道/经济/死亡/NPC AI/世界构建）。若继续向 Agent/LLM/MCP/workbench 投入过多，核心循环可能无法按期可玩。

2. **层3 RestrictedPython 沙箱缺失，UGC 规则下沉受阻**
   - severity: high
   - 细节：当前 UGC 创作停留在 layer0/1/2，真正的创作者自定义逻辑无安全执行环境。若 M3 前不实现沙箱 + 资源配额，要么限制创作者能力（削弱 UGC 价值主张），要么被迫让 UGC 走无沙箱 module_pack（安全风险）。

3. **阶段 0 性能硬门禁未验证，纯 Python 1000+100 仍是未证实的赌注**
   - severity: high
   - 细节：`TickProfiler` 就位但无 go/no-go 报告，1000+100 负载测试未执行。kill criteria 3/6/9 的触发条件（达标 / 降级 / 重新评估 Rust/Go）尚未有数据支撑。

4. **主题无关性未独立验证，CombatKernel 仍围绕武侠数据塑形**
   - severity: medium
   - 细节：`themes/default.py` 仅有海盗帮 FamilyBonus，无完整非武侠微场景。若 CombatKernel 接口在迁移更多武侠招式时回渗武侠语义，第二题材扩展将背负高额重构债务。

5. **金庸衍生内容合规清洗未启动，外部发布存在版权阻断**
   - severity: medium
   - 细节：当前预检仅标记不 block；71 文件清洗 SOP 未制定。M3 可玩 demo 如包含未清洗的武侠门派/角色名，将无法对外发布或触发法律风险。

---

*评审人：第四轮专家团 · 游戏制作人 / 范围管理*  
*日期：2026-07-15*
