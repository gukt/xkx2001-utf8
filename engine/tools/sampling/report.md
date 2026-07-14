# 抽样校准实验阶段 A 报告

> 阶段 0 任务 6 抽样校准实验阶段 A 产出。方法论见 [ADR-0046](../../../docs/adr/ADR-0046-sampling-calibration-methodology.md)，实施计划见 [17](../../../docs/xkx-arch/17-抽样校准实验实施计划.md)。
>
> 生成命令：`cd engine && uv run python -m tools.sampling.scan_callothers`（4.2s）

## 一、总量验证 + 口径对账

| 口径 | 全仓 | 仅 d/ | 来源 |
|---|---|---|---|
| **精确 call_other（本脚本）** | **59270** | 30592 | scan_callothers.py（过滤注释/字符串 + 要求 `->method(`） |
| 粗略 grep `->` | 67919 | 36333 | `grep -rohF '->'`（不过滤注释/字符串） |
| _archive/01 记录 | 68771 | 36333 | [_archive/01](../../../docs/xkx-arch/_archive/01-关键修正与避坑清单.md) §19 |

**对账结论**：

- _archive/01 的 68771 是**粗略 grep 口径**（仅 d/ = 36333 完全吻合，全仓 67919 vs 68771 差 1.2% 为扫描时点差异）
- 精确口径 59270 比粗略少 8649（12.7%）：注释/字符串里的 `->` + 不带括号的 `->`（非 call_other）
- **以 59270 为准**（可复现、精确，过滤了非调用噪声）
- call_other() efun 形式 89 个（动态调用走 efun，量少，印证 ADR-0046 后置决策）
- 动态方法名（`->"func"()`）0 个（全仓库无此形式，动态调用全部走 call_other efun）

## 二、子系统分布

| 子系统 | 调用点 | 占比 | .c 文件数 | 密度（调用点/文件） |
|---|---|---|---|---|
| d | 30592 | 51.6% | 6414 | 4.8 |
| kungfu | 18174 | 30.7% | 798 | 22.8 |
| clone | 4200 | 7.1% | 479 | 8.8 |
| cmds | 3411 | 5.8% | 230 | 14.8 |
| adm | 1502 | 2.5% | 95 | 15.8 |
| inherit | 809 | 1.4% | 72 | 11.2 |
| feature | 568 | 1.0% | 36 | 15.8 |
| u | 14 | 0.0% | 27 | 0.5 |
| **合计** | **59270** | 100% | 8151 | 7.3 |

d + kungfu = 82.3%，集中在区域内容 + 武学。kungfu 密度最高（22.8/文件，武学文件逻辑密集），d 密度低（4.8/文件，大量纯数据房间拉低均值）。

## 三、方法名分布 + 类别聚类

top 30 方法名见 [summary.json](output/summary.json)。按功能聚类：

| 类别 | 代表方法 | 调用点 | 占比 | 迁移性质 |
|---|---|---|---|---|
| C1 dbase 读写 | query/set/add/delete + temp 变体 | 33398 | 56.3% | **模式化**（组件字段访问，框架统一处理） |
| C2 技能 | query_skill/set_skill/map_skill/improve_skill/query_skill_mapped | 6509 | 11.0% | SkillSystem 统一处理 |
| C3 战斗 | is_fighting/is_busy/start_busy/kill_ob/receive_damage/receive_wound/do_attack | 4014 | 6.8% | 已实现（M3 CombatSystem） |
| C4 装备 | wear/wield | 1864 | 3.1% | EquipSystem |
| C5 条件 | apply_condition/query_condition | 1183 | 2.0% | ConditionSystem |
| C6 移动 | move | 1880 | 3.2% | 已实现 |
| C7 其他 top30 | name/query_respect/query_rude/is_character/set_amount | 4179 | 7.0% | 混合 |
| C8 长尾（508 方法） | top30 之外 | 6243 | 10.5% | 混合（平均 12.3/方法） |
| 合计 | | 59270 | 100% | |

**关键发现**：C1 dbase 读写占 56.3%（33398 个 query/set/add/delete），是模式化的组件字段访问，新引擎框架统一处理，**不需逐个迁移**。这是"迁移单位不应是调用点"的硬数据支撑。

## 四、文件分布

含调用的文件 3512 / 8135（43%）；57% 文件无调用点（纯数据房间）。

top 文件（调用点密度最高）：

| 文件 | 调用点 |
|---|---|
| d/dali/npc/ba-tianshi.c | 472 |
| d/dali/npc/fan-ye.c | 470 |
| d/dali/npc/hua-hegen.c | 469 |
| d/taohua/npc/jiading.c | 422 |
| d/bwdh/sjsz/obj/control.c | 294 |
| kungfu/class/misc/linzhennan.c | 282 |
| d/bwdh/sjsz3/obj/control.c | 281 |
| clone/npc/xibei.c | 266 |
| adm/daemons/combatd.c | 246 |
| adm/daemons/s_combatd.c | 239 |

top 文件集中在 NPC（d/dali/npc、d/taohua/npc、clone/npc）+ 复杂系统（bwdh 武林大会、combatd）。完整 top 20 见 [summary.json](output/summary.json)。

## 五、迁移单位建议（阶段 B 拍板）

基于分布数据，**强烈建议迁移单位不是调用点**：

1. C1 dbase 读写占 56.3%（33398 个），新引擎组件字段访问，框架统一处理，逐个迁移无意义
2. 调用点工时方差极大：一个 `query("combat_exp")`（组件字段读）vs `do_attack()`（七步管线）工时差 100 倍+
3. 调用点数量与迁移工时不成正比

**建议迁移单位：函数**（LPC 函数级）。理由：

- 30 文件校准已用"语义单元"概念（文件内逻辑块），函数是自然边界
- 调用点是函数内语句，按函数测工时涵盖调用点 + 控制流 + 逻辑
- 函数总数可枚举（阶段 B 可扩展脚本统计函数级分布）

抽样仍用阶段 A 的调用点分布作为**函数复杂度的代理指标**（调用点密度高的函数 = 复杂函数）。

## 六、抽样方案框架

分层：子系统 × 方法类别。样本量 80（50-100 区间）。

| 子系统 | 样本配额 | 其中 C1（欠采样） | 其中 C2-C8（正常采样） |
|---|---|---|---|
| d | 32 | 4 | 28 |
| kungfu | 20 | 3 | 17 |
| clone | 8 | 1 | 7 |
| cmds | 8 | 1 | 7 |
| adm | 6 | 1 | 5 |
| inherit + feature | 6 | 1 | 5 |
| **合计** | **80** | **11** | **69** |

原则：

- **C1（dbase 读写）欠采样**：模式化，每子系统抽 1-4 个代表确认低工时即可
- **C2-C8 过采样**：工时变异大，是工时估算的主要信息源
- 按子系统比例分配（d 40% / kungfu 25% / clone+cmds 各 10% / adm+inherit+feature 15%）

具体样本选择 + 实测在阶段 B 执行。

## 七、阶段 A 交付物

| 交付物 | 路径 |
|---|---|
| 枚举脚本 | [scan_callothers.py](scan_callothers.py) |
| 调用点清单 | output/callothers.jsonl（59270 行） |
| 汇总统计 | [output/summary.json](output/summary.json) |
| 本报告 | [report.md](report.md) |
| 方法论 ADR | [ADR-0046](../../../docs/adr/ADR-0046-sampling-calibration-methodology.md) |
| 实施计划 | [17-抽样校准实验实施计划](../../../docs/xkx-arch/17-抽样校准实验实施计划.md) |

## 八、阶段 B 启动条件

1. **迁移单位决策**：本报告建议"函数"，待确认
2. **抽样方案确认**：本报告框架，待确认
3. **阶段 B 工时实测**：80 样本 × 函数级迁移，记录工时 + 推算全量 + 置信区间

## 九、遗留

- call_other() efun 89 个未纳入（ADR-0046 后置，量少 0.15%）
- 动态方法名 0（全仓库无 `->"func"()` 形式）
- 函数级分布统计（阶段 B 启动时扩展脚本，按函数聚合调用点）

---

*生成：2026-07-14*
