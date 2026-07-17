# engine 实现现状摘要

本次扫描基于 `/home/gukt/github/xkx2001-utf8/engine/src/xkx/` 当前工作树（分支 `feat/m2-ugc-loop-r2`）。
代码总量约 **4.3 万行 Python**，覆盖 9 个顶层模块；测试在 `engine/tests/` 共约 70+ 个文件。

整体状态判断采用**保守口径**：只要代码存在但缺少对应 LPC 规格全覆盖、或行为等价验证不足、或关键功能明确后置，即标 `partial`。

## 模块清单

| 模块 | 用途 | 关键文件 | 状态 | 备注 |
|------|------|----------|------|------|
| **runtime** | 最小 ECS + 组件 + 命令管线 + 场景加载 + 持久化 | `runtime/ecs.py`, `runtime/components.py`, `runtime/commands.py`, `runtime/world.py`, `runtime/storage.py`, `runtime/conditions.py`, `runtime/death.py`, `runtime/governance.py`, `runtime/doors.py`, `runtime/middleware/s0_flood_check.py`~`s7_execute_audit.py`, `runtime/engine.py`, `runtime/ws_server.py` | **partial** | 命令管线已落地 30+ 命令（go/kill/fight/ask/give/quest/take/look/hp/bai/kneel/learn/practice/dazuo/tuna/enable 等），组件 16 个；但 `runtime/systems.py` 仍为基类 stub（`raise NotImplementedError`），tick 驱动 System 除 CombatSystem 外多为 ad-hoc 接入；pronoun/隐形/astral 等 TODO 后置。 |
| **combat** | 战斗纯函数 + seeded RNG + 副作用账本 + replay | `combat/resolve_attack.py`, `combat/system.py`, `combat/context.py`, `combat/result.py`, `combat/modifier.py`, `combat/rng.py`, `combat/replay.py`, `combat/conformance.py` | **partial** | `resolve_attack` 已实现七步管线与 `skill_power` 完整公式，hypothesis 属性测试覆盖；但确定性范围被刻意限制为 combat-only，perform/exert/阵法/特殊攻击等明确后置。 |
| **dsl** | DSL IR + 四层编译/校验 + CPK 加载 | `dsl/layer0.py`, `dsl/layer1.py`, `dsl/layer2.py`, `dsl/cpk.py`, `dsl/cpk_loader.py`, `dsl/validator.py`, `dsl/ir.py` | **partial** | 层0/1/2 已落地（层2 `InquiryNode` 对话原子），CPK manifest 与 validator 四道校验最小实现；**层3 RestrictedPython 沙箱缺失**，validator 对物品/skills 的引用完整性仍较薄。 |
| **content_gen** | LLM 内容生产管线（LPC -> DSL v0） | `content_gen/generate.py`, `content_gen/llm_client.py`, `content_gen/prompts.py`, `content_gen/__main__.py` | **partial** | 支持 room/npc/skill/quest/item/rule 生成与 `revise_asset`； revision 度量依赖 `tools/measure_revision.py`（在 engine 之外）；Langfuse 接入后置。 |
| **content_review** | 内容预检 + 审核状态 + 专家 checklist | `content_review/precheck.py`, `content_review/rules.py`, `content_review/review_status.py`, `content_review/checklist.py` | **partial** | 4 类词表 + license 检查已实现，命中结果落 `_review.json`；但版权清洗明确后置（M3-4），当前仅检测不 block。 |
| **orchestrator** | M2/UGC 创作闭环编排（生成->MCP 校验->修订->审核） | `orchestrator/loop.py`, `orchestrator/mcp.py`, `orchestrator/state_machine.py`, `orchestrator/capabilities.py`, `orchestrator/rag.py`, `orchestrator/types.py` | **partial** | 闭环 MVP 已落地，含 world-graph/schema/precheck/L4 等 verifier；L4 可跑通性校验依赖 measure_revision，workbench 事件回调已预留但前端较薄。 |
| **workbench** | FastAPI + WebSocket 评审工作台 | `workbench/app.py`, `workbench/router.py`, `workbench/runner.py`, `workbench/ws.py`, `workbench/__main__.py` | **partial** | 后端 API 与 WebSocket 连接管理就位；static 前端目录若不存在则回退，当前为可运行 MVP，UI 深度有限。 |
| **themes** | 题材包数据与默认注册表 | `themes/wuxia.py`, `themes/default.py`, `runtime/theme_registry.py`, `runtime/theme.py` | **partial** | `wuxia` 旗舰题材 + `default` 非武侠测试题材已注册；仅有 2 个 descriptor，门派/家族奖励数据部分填充。 |
| **spec** | LPC 规格提取（9 层 FunctionSpec / LayerSpec） | `spec/base.py`, `spec/layer_a_driver.py`, `spec/layer_b_object_base.py`, `spec/layer_c_command.py`, `spec/layer_c_vote.py`, `spec/layer_d_world.py`, `spec/layer_e_combat.py`, `spec/layer_f_death.py`, `spec/layer_f_hell.py`, `spec/layer_g_npc_ai.py`, `spec/layer_h_daemons.py`, `spec/layer_h_daemons2.py`, `spec/layer_h_race.py`, `spec/layer_i_character.py`, `spec/impl_map.py` | **partial** | 已提取 A~I 共 15 个文件、约 1.5 万行规格；`layer_i_login.py` 缺失，`__init__.py` 为空。规格是 Pydantic 契约数据，未覆盖全部 8412 个 LPC 文件，可执行属性测试仅覆盖部分关键层。 |

## 关键发现

1. **M2/UGC 闭环刚落地，层3 沙箱仍是缺口**。`orchestrator` + `workbench` + `content_gen/review` + `dsl/layer2` 构成当前分支最新增量，但 DSL 四层规划中 `layer3`（RestrictedPython 沙箱）尚未实现，UGC 规则仍以声明式层1/层2 为主。

2. **System 基类是 stub，tick 派生变更靠 ad-hoc 桥接**。`runtime/systems.py` 仅定义 `System.update` 抽象接口并抛出 `NotImplementedError`；实际 `CombatSystem` 独立在 `combat/` 包、`DoorSystem`/`GovernanceSystem`/`ConditionSystem`/`HealSystem` 等散落于 `runtime/` 并由 `engine.py`/`world.py` 直接调度，尚未统一收敛到单一 ECS System 注册表。

3. **combat 确定性边界守住了 combat-only**。`resolve_attack` + `DeterministicRNG` + `CombatSnapshot` + `replay` 已实现同 seed 同快照同输出，并有 hypothesis 属性测试；但 heal/exp/condition 等 System tick 随机性不在确定性范围内，符合 ADR-0023 决策。

4. **runtime 命令面宽但深度参差不齐**。命令管线 8 段中间件 + 30+ 终端命令已可跑通多门派 e2e（雪山、终南、书院等），但大量命令仍带“简化/后置”注释（如 practice 的 SkillData stub、du 的 literate 门控、recruit 的 NPC AI 路径等）。

5. **spec 提取体量很大但 executable coverage 不足**。`spec/` 是仅次于 `runtime/commands.py` 与 combat 规格的大模块，已产出 A~I 层 Pydantic 契约；但缺少 `layer_i_login.py`，且大量规格尚未反向映射到 executable 测试，行为等价验证仍是后续重点。
