# M3 实施计划：单题材（武侠）完整可玩 demo

> 本计划是 [04 §三 M3](04-迁移路径与避坑清单.md) 的实施细化。阶段 2 全部完成（1598 tests，2.7 门派切割收官，核心引擎无武侠烙印），M3 在阶段 2 基础上：把武侠内容以 CPK 形式入库，串成完整可玩循环（拜师/练功/战斗/任务/死亡轮回），配套内容审核 pipeline MVP + 版权清洗方案 + 全仿真确定性决策点评估。
>
> 开工前必读：本文件 + [PROGRESS.md](../../PROGRESS.md) + [04](04-迁移路径与避坑清单.md) §三 M3 + §四 kill criteria + [03](03-DSL-UGC与Agent协作.md) §四 CPK + §八 内容合规与版权。

## 一、总览

### 目标

在阶段 2 引擎能力（Query/Vitals/Attribute/Skill/Combat/Title/Governance/门派切割）基础上，产出单题材（武侠）完整可玩 demo：1 个门派的完整核心循环（拜师 -> 练功 -> 战斗 -> 任务 -> 死亡轮回）可跑可玩，武侠内容以 CPK 形式入库，配套内容审核 pipeline MVP + 版权清洗方案。M3 之后才投入全量迁移与多题材。

### 范围（04 §三 M3 的 5 个任务）

| 任务 | 内容 | 风险 | 依赖 |
|---|---|---|---|
| M3-1 | 武侠核心循环可玩（拜师/练功/战斗/任务/死亡轮回） | 中 | 阶段 2 全部 ✅ + M3-2 |
| M3-2 | 官方 StdLib CPK（武侠内容以 CPK 形式入库） | 中 | 2.7 门派切割 ✅ |
| M3-3 | 内容审核 pipeline MVP（自动化预检 + 专家审核） | 低 | M3-2 CPK 格式 |
| M3-4 | 版权清洗（金庸衍生 71 文件处理方案落地） | 中 | M3-1 选门派 |
| M3-5 | 全仿真确定性决策点（M3 后评估） | 低 | M3-1 完成 |

### 不做（后置/砍掉，对齐 [04 §六](04-迁移路径与避坑清单.md) + [03 §十](03-DSL-UGC与Agent协作.md)）

- **2482 房间全量迁移**后置 M3 后（M3 只做 1 门派完整内容 + 1 版权示范）
- **19 门派全量内容**后置（M3 聚焦 1 门派完整循环）
- **内容市场/分账/多题材/热重载**后置
- **PG 迁移**外部玩家测试前才迁（kill criteria 8），M3 仍内存 + JSON
- **社区众审/平台终审**后置（M3 pipeline MVP 只做自动化预检 + 专家审核）
- **provenance 全量回填**后移到门 3（[03 §四](03-DSL-UGC与Agent协作.md)：首次对外发布前强制回填，M3 开发期用简单版本号）
- **全仿真确定性实施**后置 M3 后（M3-5 只评估不实施，combat-only 确定性仍是当前范围）

### 与 [04 §八](04-迁移路径与避坑清单.md) M3->后置 决策检查点对齐

04 §八的 M3->后置决策检查点是"单进程容量是否实测达 80% / 是否需要外部玩家测试（触发 PG 迁移）/ 第二题材是否真实存在"。M3 本身的验收是 04 §三 M3 任务表的 5 项产出。

---

## 二、现状盘点（阶段 2 产出可复用）

### 代码资产

- **runtime 30+ 模块**：[family.py](../../engine/src/xkx/runtime/family.py) / [race.py](../../engine/src/xkx/runtime/race.py) / [theme.py](../../engine/src/xkx/runtime/theme.py) / [governance.py](../../engine/src/xkx/runtime/governance.py) / [death.py](../../engine/src/xkx/runtime/death.py) / [heal.py](../../engine/src/xkx/runtime/heal.py) / [title.py](../../engine/src/xkx/runtime/title.py) / [equipment.py](../../engine/src/xkx/runtime/equipment.py) / [query.py](../../engine/src/xkx/runtime/query.py) / [conditions.py](../../engine/src/xkx/runtime/conditions.py) / [systems.py](../../engine/src/xkx/runtime/systems.py) 等
- **combat 完整**：[resolve_attack.py](../../engine/src/xkx/combat/resolve_attack.py)（七步管线）/ [combat_sim.py](../../engine/src/xkx/combat/combat_sim.py) / [conformance.py](../../engine/src/xkx/combat/conformance.py)（8 项）/ [replay.py](../../engine/src/xkx/combat/replay.py) / [modifier.py](../../engine/src/xkx/combat/modifier.py)（阵法合击）
- **dsl**：[layer0.py](../../engine/src/xkx/dsl/layer0.py)（YAML 声明式）/ [layer1.py](../../engine/src/xkx/dsl/layer1.py)（事件规则）/ [ir.py](../../engine/src/xkx/dsl/ir.py)（编译）/ [validator.py](../../engine/src/xkx/dsl/validator.py)（四检查）
- **2.7 门派切割产出**：RaceProfile + FamilyBonus（声明式载体，setup_race 纯函数 + apply_family_bonuses 不认识门派名）+ ThemeConfig（房间路径外提）+ test_theme_neutrality 收官硬门禁
- **WS 服务器 + CLI REPL**：[ws_server.py](../../engine/src/xkx/runtime/ws_server.py) / [connection.py](../../engine/src/xkx/runtime/connection.py) / [account.py](../../engine/src/xkx/runtime/account.py) / [cli.py](../../engine/src/xkx/cli.py)（parse_and_run 命令分发）
- **1598 tests 全绿**

### 场景资产

5 个微场景（3-6 文件级，[engine/scenes/](../../engine/scenes/)）：

- `wuxia_micro`（城市街道 + 茶馆，武侠通用，3 文件）
- `xueshan_micro`（雪山派，6 文件，最大）
- `zhongnan_micro`（终南山，4 文件）
- `academy_micro`（书院，非武侠题材验证，3 文件）
- `age_of_sail_micro`（大航海，非武侠题材验证，3 文件）

e2e 覆盖：take/look/inventory/kill/ask/give/hp/quest/死亡处理/CLI REPL/多回合战斗（[test_s5_playtest.py](../../engine/tests/test_s5_playtest.py)）。

### 规格资产

- 9 层 LPC 规格（160 FunctionSpec / 631 SideEffect / 52 RandomSpec）
- 层 E 战斗 26 函数 + 层 H 守护进程 26 函数 + 层 I 角色登录 18 函数
- 灵魂系统盘点（[09](09-灵魂系统盘点.md)）：阴间/法院阶段 2 已实现代表性元素，武林大会/vote/intermud 后置

### M3 的 gap

| 维度 | 阶段 2 现状 | M3 目标 |
|---|---|---|
| 内容深度 | 微场景（3-6 文件，单点验证） | 1 门派完整循环（拜师/练功/战斗/任务/死亡轮回闭环） |
| 内容组织 | 散装 scenes 目录 | CPK 形式入库（manifest + 依赖 + 命名空间） |
| 审核 | 无 | pipeline MVP（自动化预检 + 专家审核） |
| 版权 | 未处理 | 71 文件处理方案落地 + 1-2 示范 |
| 确定性 | combat-only | 全仿真决策点评估（不实施） |

---

## 三、任务分解与依赖排序

### 依赖图

```text
M3-2 CPK 格式固化 ──┬──> M3-1 核心循环内容生产 ──> M3-5 全仿真确定性决策点
（StdLib CPK 骨架）  │                          （评估，M3 收官）
                    ├──> M3-3 内容审核 pipeline MVP
                    └──> M3-4 版权清洗方案（依赖 M3-1 选门派）
```

### M3-2：CPK 格式固化 + StdLib CPK 骨架（前置基础）

- **目标**：固化 CPK manifest 格式（[03 §四](03-DSL-UGC与Agent协作.md)），实现 CPK 加载器，把现有 5 个微场景重整为 CPK 形式，wuxia 题材包静态注册。
- **输入**：03 §四 CPK manifest schema + 2.7 ThemeConfig + 现有 5 微场景
- **产出**：
  - CPK manifest 格式固化（schema_version + theme + pack_type + dependencies + capabilities + resource_quota + entry_points + market 预留字段）
  - CPK 加载器（manifest -> 资产集合 -> 命名空间隔离 -> 依赖图拓扑排序）
  - 现有 5 微场景重整为 CPK（wuxia_micro/xueshan_micro/zhongnan_micro -> wuxia 题材包 module_pack；academy/age_of_sail -> 独立题材）
  - ThemeRegistry 静态加载（wuxia 题材包注册：component_schemas + condition_predicates + action_verbs + combat_resolver + themed_governance_policies）
  - provenance 开发期用简单版本号（后移门 3）
- **依赖**：2.7 门派切割 ✅ + 03 §四 CPK 设计
- **验收**：5 微场景以 CPK 形式加载可跑；命名空间隔离无冲突；依赖图拓扑排序正确
- **需 ADR**：ADR-0031 CPK 格式固化 + StdLib 内容包入库

### M3-1：武侠核心循环内容生产（主线）

- **目标**：选 1 个门派做完整核心循环内容（拜师/练功/战斗/任务/死亡轮回），串成可玩 demo。
- **输入**：阶段 2 全部子系统 + M3-2 CPK 格式 + LPC 规格源（kungfu/ d/ 只读参考）
- **产出**：
  - 1 门派完整内容（拜师 NPC 对话 + 入门条件 / 练功技能学习 + 熟练度 / 战斗 PK + NPC 战 / 任务门派任务链 / 死亡轮回阴间还阳衔接 2.6）
  - 内容以 CPK 形式入库（module_pack）
  - 可玩 demo（CLI REPL 可跑完整循环）
  - 行为等价验证（关键 NPC/任务与 LPC 规格对照）
- **依赖**：M3-2 CPK 格式 ✅ + 阶段 2 子系统 ✅
- **验收**：完整循环可跑（拜师 -> 练功 -> 战斗 -> 任务 -> 死亡轮回 -> 还阳）；行为等价关键点通过；test_theme_neutrality 不退化
- **需 ADR**：ADR-0032 门派核心循环设计（拜师/练功/任务链/死亡整合）
- **kill criteria**：内容生产人工修订量 >40%（3 轮迭代后）-> 先扩 DSL 层1-2 表达力；>30% -> Agent 降级辅助（kill criteria 5）

### M3-3：内容审核 pipeline MVP

- **目标**：实现自动化预检 + 专家审核两层的 MVP，社区众审/平台终审后置。
- **输入**：[03 §八](03-DSL-UGC与Agent协作.md) 分层内容审核 pipeline + M3-2 CPK 格式
- **产出**：
  - 自动化预检（暴力/敏感词/赌博/版权关键词扫描 CPK 资产）
  - 专家审核（review checklist MVP，人工 review 流程）
  - 预检结果与 CPK manifest 关联（审核状态字段）
  - 社区众审/平台终审后置
- **依赖**：M3-2 CPK 格式 ✅
- **验收**：自动化预检可扫描 CPK 资产 + 专家审核 checklist 可用
- **需 ADR**：ADR-0033 内容审核 pipeline MVP

### M3-4：版权清洗方案落地

- **目标**：金庸衍生 71 文件处理方案落地 + 1-2 示范处理，全量改完后置。
- **输入**：[03 §八](03-DSL-UGC与Agent协作.md) 版权框架 + 71 文件清单（需盘点）+ M3-1 选定门派
- **产出**：
  - 71 文件盘点与分类（金庸衍生角色/门派/剧情）
  - 处理策略（改编化：角色改名/门派虚构化；标注同人非商用；授权路径评估）
  - 1-2 文件示范处理（改编化 or 标注）
  - provenance 版权链扩展（作者/模型/prompt/父版本）
- **依赖**：M3-1 选定门派（决定示范范围）
- **验收**：71 文件分类 + 处理策略落地 + 1-2 示范
- **需 ADR**：ADR-0034 版权清洗策略（71 文件）

### M3-5：全仿真确定性决策点评估

- **目标**：评估全仿真确定性（combat-only -> 全 System）的可行性与成本，M3 后决策。
- **输入**：[ADR-0023](../adr/ADR-0023-combat-determinism-boundary-simplification-ledger.md) combat 确定性边界 + 阶段 2 全子系统
- **产出**：
  - 全仿真确定性评估报告（哪些 System 可 seeded + input log / 成本 / 收益）
  - 决策建议（采纳/部分采纳/否决）
- **依赖**：M3-1 完成（全子系统在可玩 demo 中跑通）
- **验收**：评估报告 + 决策建议
- **需 ADR**：ADR-0035 全仿真确定性决策点评估

---

## 四、并行化计划（Wave 划分）

### Wave 1：CPK 格式固化（串行，前置）

M3-2 是后续所有任务的基础（CPK 格式），不可并行。

- M3-2 CPK 格式固化 + StdLib CPK 骨架 + 5 微场景重整

> 类似阶段 2 Wave 1，M3-2 是 M3 的基础，先做。

### Wave 2：核心循环内容生产（主线，依赖 Wave 1）

M3-1 是 M3 主线，内容生产是瓶颈：

- M3-1 1 门派完整核心循环内容生产 + 可玩 demo

> 内容生产方式（Agent+DSL vs 人工转译）是关键决策（见开放问题）。

### Wave 3：审核 pipeline + 版权清洗（2 路并行，依赖 Wave 1/2）

M3-3 依赖 M3-2（CPK 格式），M3-4 依赖 M3-1（选门派），2 路并行：

- **Agent A**：M3-3 内容审核 pipeline MVP（自动化预检 + 专家审核）
- **Agent B**：M3-4 版权清洗方案（71 文件盘点 + 策略 + 示范）

> M3-4 示范范围依赖 M3-1 选定的门派，可等 M3-1 选定后启动。

### Wave 4：确定性决策点 + M3 收官（串行，依赖 Wave 2/3）

- M3-5 全仿真确定性评估 + M3 收官（可玩 demo 对外可跑 + 决策检查点）

### 时间预估

| Wave | 任务 | 预估 | 说明 |
|---|---|---|---|
| 1 | M3-2 CPK 格式 | 2-3 周 | 基础，manifest + 加载器 + 5 微场景重整 |
| 2 | M3-1 核心循环 | 4-6 周 | 主线，内容生产是瓶颈 |
| 3 | M3-3/M3-4 并行 | 3-4 周 | 2 路并行 |
| 4 | M3-5 收官 | 1-2 周 | 评估 + 收官 |
| 合计 | | 8-12 周 | 04 估计 6-8 月，吻合 |

> 预估乐观，实际可能因内容生产迭代、版权清洗争议、CPK 格式边界讨论超时。超时触发范围裁剪（第 2 门派/全量版权处理后置）。

---

## 五、关键设计决策（需 ADR）

| ADR | 主题 | 关联 03/05 | 对应任务 |
|---|---|---|---|
| ADR-0031 | CPK 格式固化 + StdLib 内容包入库 | 03 §四 / dissent 8 | M3-2 |
| ADR-0032 | 门派核心循环设计（拜师/练功/任务链/死亡整合） | 05 §五 dissent 1/5/6/7/10 | M3-1 |
| ADR-0033 | 内容审核 pipeline MVP | 03 §八 | M3-3 |
| ADR-0034 | 版权清洗策略（71 文件） | 03 §八 | M3-4 |
| ADR-0035 | 全仿真确定性决策点评估 | 05 §五 dissent 1 | M3-5 |

> ADR-0031（M3-2 Wave 1）+ ADR-0032（M3-1 Wave 2）是前置，必须先写。ADR-0033~0035 可随对应 Wave 启动时写。

### 关键不变量（CLAUDE.md，实施中不可违反）

- tick=1s + compute<100ms（M3 内容不得导致性能退化）
- combat 确定性范围=combat-only（M3-5 评估不实施）
- PronounContext 必须携带 viewer
- JSON 存档崩溃安全（M3 新内容必须可序列化）
- 三层粒度 Theme > Module Pack > UGC CPK（门派是 module pack）
- themed 治理是平台级 fail-closed Python
- CombatKernel 从武侠提取、用非武侠验证（test_theme_neutrality 不退化）
- 版权清洗：金庸衍生 71 文件必须处理后方可对外发布（[03 §十](03-DSL-UGC与Agent协作.md) 硬约束 7）

---

## 六、验收标准

| 任务 | 验收标准 |
|---|---|
| M3-1 核心循环 | 1 门派完整循环可跑（拜师 -> 练功 -> 战斗 -> 任务 -> 死亡轮回 -> 还阳）+ 行为等价关键点 + test_theme_neutrality 不退化 |
| M3-2 StdLib CPK | 5 微场景以 CPK 形式加载可跑 + 命名空间隔离 + 依赖图拓扑排序 |
| M3-3 审核 pipeline | 自动化预检可扫描 CPK + 专家审核 checklist |
| M3-4 版权清洗 | 71 文件分类 + 处理策略 + 1-2 示范 |
| M3-5 确定性决策点 | 评估报告 + 决策建议 |

### 测试基线

- 1598 tests 不退化
- test_theme_neutrality 硬门禁持续通过
- test_load_test CI 门禁不退化（tick p99 < 100ms，阶段 1 基线 12.6ms）
- M3-1 新增可玩循环 e2e（完整循环闭环测试）

---

## 七、风险与 kill criteria

### 风险

| 风险 | 应对 | 对应任务 |
|---|---|---|
| 内容生产人工修订量超标（kill criteria 5） | 监控修订量 KPI，>40% 扩 DSL 表达力，>30% Agent 降级辅助 | M3-1 |
| CPK 格式过度设计 | provenance 后移门 3，M3 开发期简单版本号 | M3-2 |
| 版权清洗范围蔓延 | M3 只做方案 + 1-2 示范，全量后置 | M3-4 |
| 性能退化（内容增多） | tick profiler 监控，test_load_test 门禁 | M3-1 |
| M2 独立 LLM 验证未完成 | M3 内容生产方式需决策（见开放问题） | M3-1 |

### kill criteria 触发条件

| kill criteria | 触发条件 | 应对 |
|---|---|---|
| Agent 创作修订量超标（kc 5） | 单 CPK 3 轮迭代后 >40% | 扩 DSL 层1-2；扩后 >30% Agent 降级辅助 |
| 性能退化（kc 6） | M3 内容导致 tick p99 >= 100ms | 冻结功能范围纯做优化 |
| 项目级（kc 7） | 18 个月未达 M3 | 冻结迁移，聚焦已迁移内容产品化 |

---

## 八、与其他阶段的关系

### 与阶段 2 的关系

阶段 2 全部子系统是 M3 的基础设施。M3 不重写引擎，而是在其上生产内容 + 串成可玩循环 + 配套审核/版权。2.7 门派切割（RaceProfile + FamilyBonus + ThemeConfig）是 M3-2 CPK 入库的直接基础。

### 与 M1/M2 的关系

- **M1**（combat 确定性回放开源）：阶段 1 T9 Combat Replay Viewer 已完成前身，M3 可作为开源交付时机
- **M2**（DSL+Agent 创作闭环 demo）：阶段 -1 copilot 验证（24.5% 修订量，范式污染偏差），**独立 LLM + Langfuse 真验证状态待确认**（见开放问题）。M3 内容生产方式依赖 M2 结论。

### 与后置阶段的关系

M3 后：全量迁移（2482 房间）/ 多题材 / 内容市场 / PG 迁移（外部玩家测试前）/ 全仿真确定性（M3-5 决策）。

---

## 九、启动前置清单 + 开放问题（已裁决）

### 启动前置

- [x] 阶段 2 全部完成（1598 tests，2.7 门派切割收官）
- [x] ADR-0031 CPK 格式固化（Wave 1 前置，已评审通过 2026-07-13）
- [x] 用户评审本计划文档 + 确认 M3 范围与开放问题（2026-07-13，"按建议走"）

### 开放问题（已裁决，2026-07-13 用户"按建议走"）

1. **M2 独立 LLM 验证状态**：阶段 -1 copilot 验证有范式污染偏差（Agent = 本 session LLM，24.5% 修订量），M2 独立 LLM + Langfuse 真验证此前未完成。
   - **裁决**：Wave 2 用独立 LLM 生产雪山派完整内容 + Langfuse 追踪修订量（兼顾 M2 验证 + M3 内容生产）。若修订量 >40% 触发 kill criteria 5（Agent 降级为辅助）。
2. **门派选择**：M3 选哪个门派做完整内容？
   - **裁决**：扩展 xueshan_micro 做完整内容（雪山派，现有 8 房间最大微场景）+ 选 1 个金庸衍生门派做版权示范（需盘点版权归属，M3-4 落地）。
3. **可玩 demo 交付形态**：CLI REPL 够不够，还是要 WS 客户端（HTML/JS）？
   - **裁决**：CLI REPL 够内部验证（阶段 -1 S5a 已有最小 CLI）；WS 客户端后置外部玩家测试（触发 PG 迁移）。
4. **版权清洗范围**：M3 做处理方案 + 1-2 示范，还是全部改完？
   - **裁决**：方案 + 1-2 示范，全量后置（M3 是内部 demo，03 §八硬约束 7"对外发布前必须处理"不强制 M3 全量）。
5. **CPK provenance**：M3 固化还是后移门 3？
   - **裁决**：后移门 3（03 §四明确"首次对外发布前强制回填"，M3 开发期用简单版本号）。

---

*本计划核心立场：阶段 2 引擎能力是 M3 的起点；M3 聚焦 1 门派完整可玩循环（非全量内容）；CPK 格式固化是基础；内容审核 + 版权清洗是配套；全仿真确定性是评估非实施；收敛优先于完备，2482 房间全量迁移后置。*

*最后更新：2026-07-13*
