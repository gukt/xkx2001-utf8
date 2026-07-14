# ADR-0047：greenfield 工时语义与已实现/待迁移分类（阶段 B 方法论修正）

- 状态：已采纳
- 日期：2026-07-14
- 阶段：0 任务 6 抽样校准实验阶段 B（设计定稿）
- 关联：[ADR-0046](ADR-0046-sampling-calibration-methodology.md)（A/B 分阶段 + 迁移单位推迟）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) 专家 6 工时模型 / [00](../xkx-arch/00-愿景约束与总纲.md) §11（greenfield 重写非增量迁移）/ [报告 §五§六](../../engine/tools/sampling/report.md)

## 背景

[ADR-0046](ADR-0046-sampling-calibration-methodology.md) 决策阶段 A 先按调用点枚举 + 给出迁移单位建议，阶段 B 启动前拍板。阶段 A [报告 §六](../../engine/tools/sampling/report.md) 给出"对全 59270 调用点抽 80 样本"的抽样方案框架，§五建议迁移单位为函数。

阶段 B 启动调研发现一个报告未充分覆盖的关键张力：项目是 **greenfield 重写**（[00](../xkx-arch/00-愿景约束与总纲.md) §11："新引擎从零按规格实现，非增量迁移"），新引擎已实现 C1-C6 系统级等价（[engine/src/xkx/runtime/](../../engine/src/xkx/runtime/) + `combat/`：`dbase_map`+`components` / `skill` / `combat` / `equipment` / `conditions` / `world`）。报告 §三类别分布中 C1-C6 合计 48848 调用点（82.4%）的等价行为**已实现**，工时≈0。若按报告 §六对全 59270 调用点抽样实测，会重复计已实现部分，严重高估全量迁移工时。

## 决策

1. **greenfield 工时语义**：工时只计"新引擎尚未实现等价行为"的迁移。已实现部分（C1-C6 系统级）工时≈0，不计入待迁移工时。这是 greenfield 重写（非增量迁移）的本质要求--工时估算是回答"剩余规格迁完需多少工时"，不是"重做已实现部分"。

2. **已实现/待迁移分类**（方法类别级，对照新引擎模块）：
   - **implemented**（C1-C6，48848 调用点 82.4%）：dbase 读写 / 技能 / 战斗 / 装备 / 条件 / 移动，新引擎框架级已实现
   - **pending**（C7/C8，10422 调用点 17.6%）：其他 top30 + 长尾，待迁移

3. **工时三分法**（pending 内再分）：
   - **框架已实现**：工时≈0（已完成）
   - **内容填充**（pending/data，80 函数）：NPC/房间/物品数据定义，低工时数据录入，可批量
   - **新逻辑实现**（pending/logic，1079 函数）：新引擎尚无的等价行为，代码实现，工时变异大 -- **实测主对象**

4. **抽样面修正**：从全 59270 调用点缩到 10422（17.6%）/ 1159 函数。抽样聚焦 pending，implemented + pending/data 欠采样确认。

5. **迁移单位 = 函数**（采纳报告 §五建议）：函数是 greenfield 重写下"等价行为单元"的自然代理，涵盖调用点 + 控制流 + 逻辑，可枚举（7991 个有调用点的函数）。

6. **类别级近似而非逐方法核对**：不逐方法核对新引擎 API 是否已实现（成本高）。用报告 §三类别聚类（C1-C6 = implemented）作一阶近似。C8 长尾含少量应归 C2-C7 的变体方法（如 `prepare_skill`/`unwield`），已实现判定**偏保守**（高估待迁移面），使工时承诺更安全。

## 数据支撑（scan_callothers.py 阶段 B 扩展产出）

| 指标 | 值 |
|---|---|
| 调用点总数 | 59270（对账阶段 A 一致）|
| implemented 调用点 | 48848（82.4%）|
| pending 调用点 | 10422（17.6%）|
| 有调用点的函数 | 7991 |
| pending 函数 | 1159（logic 1079 + data 80）|
| 每函数调用点 p50/p90/max | 4 / 18 / 355 |

待迁移函数按子系统：d 584 / adm 152 / kungfu 125 / cmds 103 / clone 89 / inherit 62 / feature 42。adm 待迁移比例高（daemon 特有逻辑）。

## 不做（本轮边界）

- 不手工实测工时（留后续，基于 80 样本候选清单）
- 不迁移代码到 `src/xkx/`（留后续）
- 不逐方法核对新引擎 API（类别级近似，保守）
- 不扫描 `call_other()` efun / `.h`（[ADR-0046](ADR-0046-sampling-calibration-methodology.md) 后置）

## 后续

- 实测执行：基于 [sample_candidates.json](../../engine/tools/sampling/output/sample_candidates.json) 80 候选取样，记录分层工时 + 推算全量 + t 分布置信区间
- 实测方法论定稿见 [报告 §十](../../engine/tools/sampling/report.md)
- 若实测发现类别级近似偏差大（如 C7 多数实际已实现），回调分类阈值

## 与 ADR-0046 的关系

ADR-0046 决策 3 定分层维度为"方法名 + 子系统"，未涉及 greenfield 已实现/待迁移维度。本 ADR 补充该维度，修正 ADR-0046 报告 §六的抽样面（从全量到 pending），不推翻 A/B 分阶段与迁移单位推迟决策。
