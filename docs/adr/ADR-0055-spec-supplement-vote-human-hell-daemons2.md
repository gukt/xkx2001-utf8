# ADR-0055：规格补充 -- Vote / human.c / 阴间流程 / 第二梯队守护进程

## 状态

- 日期：2026-07-15
- 决策：已采纳
- 影响范围：阶段 0 规格提取、层 H-2 / C-VOTE / H-RACE / F-HELL、测试覆盖

## 上下文

阶段 0 任务 1 的 9 层 LPC 规格提取已在 ADR-0010 中完成，覆盖核心可玩循环
（A-I）。按 [08 §七](../xkx-arch/08-阶段-0-实施计划.md) 的"实现到时才补"原则，
以下 4 类规格被明确后置：

1. 第二梯队守护进程（CHANNEL_D / MONEY_D / UPDATE_D 等）
2. Vote 玩家自治投票系统
3. `human.c` 种族初始化中未覆盖部分
4. 阴间世界流程

M2-2 UGC 创作闭环增强轮合并后，阶段 0 规格需要补充上述内容，为阶段 1/2
子系统实现提供完整契约。

## 问题

如何对上述 4 类 postponed 规格进行分类、分层与范围控制，避免污染已稳定的
9 层主规格？

## 决策

采用**子层（sub-layer）**方式补充，不修改 A-I 主层，仅通过 `cross_layer_refs`
用 prose 指向新增子层。

| 补充目标 | 文件 | layer_id | 说明 |
|---|---|---|---|
| 第二梯队守护进程 | `engine/src/xkx/spec/layer_h_daemons2.py` | `H-2` | 17 个子系统 / 81 个 FunctionSpec |
| Vote 玩家投票系统 | `engine/src/xkx/spec/layer_c_vote.py` | `C-VOTE` | 6 个 FunctionSpec |
| `human.c` 剩余规格 | 扩展 `engine/src/xkx/spec/layer_h_race.py` | `H-RACE` | 4 个新增 FunctionSpec |
| 阴间流程 | `engine/src/xkx/spec/layer_f_hell.py` | `F-HELL` | 35 个 FunctionSpec |

## 理由

1. **不污染主层**：A-I 9 层已完成并经过跨层一致性测试
   （`test_spec_cross_layer.py`）。子层独立导入，不破坏 9 层完整性约束。
2. **分类清晰**：Vote 独立为 `C-VOTE` 命令子层；阴间流程独立为 `F-HELL` 死亡
   下游子层；`human.c` 属于 race daemon，归入现有 `H-RACE` 而非角色登录层 I。
3. **范围可控**：第二梯队守护进程按"通信经济 → 登录安全社交 → 工具游戏"分
   3 个 incremental 批次推进，每批独立 review 与测试。
4. **测试可消费**：每个子层配套 hypothesis 属性测试骨架，与现有测试体系一致。

## 后果

- 正面：阶段 0 规格覆盖扩展至频道、经济、登录归一化、别名、玩家查询、IP 封禁、
  注册、婚姻、emote、inquiry、拱猪、广告、文选、武器动作、编码转换、投票、
  阴间流程等子系统，为阶段 1/2 实现提供输入。
- 负面：子层数量增加，需要维护跨层引用的准确性；部分第二梯队 daemon（如
  PIG_D / LANGUAGE_D）与武侠题材耦合较深，新引擎若砍掉对应功能，规格需标记
  为"预留/不做"。

## 不做边界

- 13 门派具体加成公式仍按 ADR-0030 后置 M3，本 ADR 不扩展。
- InterMUD 相关调用按 04 / 09 决策视为已砍/预留，规格中只记录接口形态。
- 尸体四阶段腐烂、PvP 通缉机制细节、NPC reset/trainee 等仍后置。
- `VIRTUAL_D.compile_object` 为占位实现，新引擎可保留接口或完全移除。

## 相关

- ADR-0010-lpc-spec-extraction-methodology.md
- ADR-0014-daemon-responsibility-redesign.md
- ADR-0030-family-content-pack-boundary-race-extraction.md
- [08 §七](../xkx-arch/08-阶段-0-实施计划.md)
