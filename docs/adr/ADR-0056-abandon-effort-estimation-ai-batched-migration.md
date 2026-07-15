# ADR-0056：放弃人工工时估算，改 AI agent 按架构依赖分批迁移

- 状态：已采纳
- 日期：2026-07-15
- 阶段：阶段 0 pilot 收尾 -> 转入 AI 分批迁移
- 关联：[ADR-0048](ADR-0048-stage-b-degraded-interval-pilot.md)（工时承诺部分被退役）/ [ADR-0047](ADR-0047-greenfield-effort-semantics.md)（工时语义红线）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) 专家 6 工时模型 dissent / [04](../xkx-arch/04-迁移路径与避坑清单.md) 验收"工时承诺有数据支撑"

## 背景

[ADR-0048](ADR-0048-stage-b-degraded-interval-pilot.md) 降级为 pilot 12-16 样本 + 区间承诺。pilot 13 样本实测于 2026-07-15 完成（详见 [pilot REPORT](../../engine/tools/sampling/pilot/REPORT.md)），退路未触发（误分类 7.7% < 30%，high-tier CV 0.24 < 1）。

但 pilot 执行中暴露一个根本性语义错位：

1. **迁移工作实际由 AI agent 完成**：pilot 阶段二用 Workflow 编排 11 个 agent 并行迁移，30 分钟完成 11 个样本（851k tokens）。迁移代码 + 测试都是 agent 写的。
2. **pilot 记录的工时是"agent 估算的人工等价分钟"**：每个样本的 `read_spec/write_code/write_test/debug` 分项是 agent 按复杂度估算的"人类做这个要多久"，既非真实人工实测（没人掐表），也非 agent 运行时间。
3. **[ADR-0048](ADR-0048-stage-b-degraded-interval-pilot.md) 决策 7 已否决"LLM 辅助纳入工时承诺主线"**，理由是工时语义污染（greenfield 工时要回答"人迁完需多少工时"，LLM 辅助回答"用 LLM 时人需校验多少"是偷换）。但该决策仍预设"需要回答人工工时"。

用户判定：**项目实际基本完全与 coding agent 合作迁移，不存在"人工迁移"场景**。"人工工时估算"是一个无解的问题错位--没有人在干，估它没有落地用途。直接用 AI agent 分批迁移即可，无需预先估算工时。

## 决策

1. **退役 [ADR-0048](ADR-0048-stage-b-degraded-interval-pilot.md) 工时估算路径**：决策 1（区间承诺目标）/ 4（pilot 实测 + 类比基准外推）/ 6（窄区间升级按需后置）的工时承诺部分退役。`effort_records.jsonl` / `estimate.py` / `REPORT.md` 工时部分归档不删（历史记录 + 13 样本迁移代码/测试是有价值副产出）。

2. **保留 [ADR-0048](ADR-0048-stage-b-degraded-interval-pilot.md) pilot 副产出作为分批迁移输入**：
   - B 类架构缺口清单（[stub_gaps.md](../../engine/tools/sampling/pilot/samples/stub_gaps.md)）-> **分批依据**
   - 共享桩 + 迁移模式（[stubs.py](../../engine/tools/sampling/pilot/stubs.py) + xue/tieyanling 范式）-> 后续批次脚手架
   - 13 个已迁移样本（13/1159）-> 已完成真东西

3. **改 AI agent 按架构依赖分批迁移**：不为工时估算，直接开干。分批依据 = 架构依赖（B 类缺口），非工时层级。

4. **第一批 = 补架构缺口层**：pilot 发现多个样本卡同一架构缺口（item-as-entity 卡 id=4/5/8，message facade 卡 id=6/7，per-object save 卡 id=9，job_data 子系统卡 id=2）。不先补则每样本各自 monkeypatch 绕过，重复且不一致。第一批先在 `src/xkx` 落地这些基础实现，"修路"让后续迁移不卡。具体优先级与范围由第一批实施计划定（plan-before-execute）。

5. **后续批 = 按子系统/缺口类型 agent 并行迁移**，每批跑完测试验证闭环。AI 成本（token / 运行时间）边跑边记，替代人工工时作为规模参考。

## 关联 [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent

- **专家 6 工时模型 dissent**：工时语义红线（[ADR-0047](ADR-0047-greenfield-effort-semantics.md) 决策 1）。本 ADR 把"工时语义"问题推到极致--既然 AI 迁移，"人工工时"问题本身不成立，从根上消解 [ADR-0048](ADR-0048-stage-b-degraded-interval-pilot.md) 决策 7 的"LLM 辅助 vs 人工工时"口径之争：两者都不需要。
- **第一批补的架构缺口**（item-as-entity / per-object save / message facade）关联专家 1（存档崩溃安全）/ 专家 2（物品/消息架构），实施时各自再关联。

## 与 [04](../xkx-arch/04-迁移路径与避坑清单.md) 验收的关系

04 验收"工时承诺有数据支撑"。本 ADR 不否定该验收的初衷（评估迁移工作量规模以决策可行性），但变更落地形式：从"人工工时区间承诺"改为"AI agent 分批迁移 + 边跑边记 AI 成本"。pilot 已证明 13 样本 30min/851k token，全量 1159 函数的 AI 成本量级可边跑边收敛，无需预先人工工时承诺。

## 后续

- 第一批实施计划单独文档（plan-before-execute），定 item-as-entity / message facade / per-object save / job_data 的优先级与范围。
- [PROGRESS.md](../../PROGRESS.md) 更新：阶段 0 pilot 收尾，转入"AI 分批迁移"阶段。
- [ADR-0048](ADR-0048-stage-b-degraded-interval-pilot.md) 状态加注"工时承诺部分被 ADR-0056 退役，pilot 副产出保留"。

## 附录：第二批调研结论摘要（2026-07-15，3 agent 调研）

第一批（message facade）已完成。第二批两个缺口的调研结论供新 session 接力：

### per-object save（卡 id=2/9）

- 现状：`StorageSystem` 是 world 级周期快照（per-entity 文件按 eid 寻址），无"单例数据对象按自定义路径主动 save/restore"。
- 推荐：方案 B DaemonStore（独立于 StorageSystem，复用 `_write_entity_atomic` 原子写 helper，`register`/`get`/`save`/`restore_all`，存档 `<root>/daemon/`）。覆盖 job_data / bboard / job_server / mapdb 全部 F_SAVE 单例。
- 工程量：机制层小-中（半天-1 天）；数据建模（job_data 60+ 变量 / bboard notes 结构）随各子系统迁移批。崩溃安全复用原子写 + offload，daemon 主动 save 不走 dirty-flag（业务时机），不违反不变量。建议新 ADR 关联 [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)。

### item-as-entity（卡 id=5/8，已迁完收口性质）

- 现状：物品是 str `item_id` 无 `ItemComp`；`weight` -> 角色负重，`rigidity`/`value`/`weapon_prop` = unknown（raise）；`ItemDef` 仅 8 字段无武器属性。
- 纠正：id=4 `murong.do_copy` **不是** item 缺口（是 skill 变更 API，已桩）；真卡 item 的只有 id=5/8（已用样本桩迁完 tests_pass）。
- 推荐：方案 B 最小子集（`ItemCatalog` 台账 `item_id` -> 属性 + `item_weight`/`item_query`/`item_move_to_room` 函数族，读属性 + move 掉落，写副作用 set name/value 维持现状），明确标注过渡，方案 A 物品实体化留 M3。
- 工程量：小-中（3-5h）。风险：方案 B 滚雪球（per-instance 写副作用）+ LPC 武器属性提取的数据工程量（`WeaponDef` 缺失）。
