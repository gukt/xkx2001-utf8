# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。

**最后更新**：2026-07-10
**当前阶段**：阶段 -1 垂直切片平台验证（2-3 月，★ 最高优先级）
**当前状态**：S1 第一垂直切片完成，端到端链路打通（30 tests），准备 S2 非武侠验证。

## Done

- [x] 三轮架构复审完成，v3 收敛版定稿（[docs/xkx-arch/](docs/xkx-arch/) 00-06 + README）
- [x] 3 个开放问题裁决（Q1 有条件采纳 / Q2 否决 6:0 / Q3 有条件采纳），见 [02](docs/xkx-arch/02-三个开放架构问题裁决.md)
- [x] 交接系统：[PROGRESS.md](PROGRESS.md) + [CLAUDE.md](CLAUDE.md) + [docs/adr/](docs/adr/) ADR
- [x] [engine/](engine/) Python 项目骨架（[ADR-0001](docs/adr/ADR-0001-python-toolchain-and-skeleton.md)）
- [x] **S1 第一垂直切片完成**（[06 实施计划](docs/xkx-arch/06-阶段-1-实施计划.md) / [ADR-0002](docs/adr/ADR-0002-resolve-attack-extraction.md)）：
  - resolve_attack 纯函数（从 combatd.c do_attack 七步提取，dodge/parry/hit + seeded RNG + 副作用账本）
  - 层0 schema（RoomDef/NpcDef + IR 编译）
  - 层1 事件规则（valid_leave + deny-wins 薄求值器）
  - 最小 ECS + 场景加载 + 战斗桥接（to_snapshot/apply_effects）
  - 命令管线（go 移动 + valid_leave / kill 战斗 + resolve_attack）
  - 最小场景（2 房间 + 1 官兵 + 1 valid_leave 规则）
  - 端到端：YAML -> IR -> ECS -> go(deny/allow) -> kill(resolve_attack) -> 确定性重放
  - **30 tests 全绿，ruff 全过**

## In Progress

（无 -- S1 已完成，S2 待启动）

## Blocked

（无）

## Next Up

**S2：非武侠微场景验证 CombatKernel 主题无关性**（阶段 -1 硬门禁）：

- 用非武侠微场景（如科幻/学院题材的最小战斗）跑在 S1 的 resolve_attack 上
- 验证核心引擎未硬编码武侠语义（武器类型枚举、无"经脉/内力"硬编码）
- 不通过则暂停，先做内核主题无关性重构（04 kill criteria 2）

S1 的简化项（hit_ob/hit_by mapping、riposte 递归、完整 skill_power、武器类型集）按 [ADR-0002](docs/adr/ADR-0002-resolve-attack-extraction.md) 表在后续切片/阶段 0 补全。阶段 -1 剩余子任务（S3 Agent 生成 / S4 全量场景 / S5 玩家试玩）见 [06](docs/xkx-arch/06-阶段-1-实施计划.md)。

## 阶段 -1 的 kill criteria（开工必读）

- DSL+Agent 创作闭环验证失败（垂直切片无法用 DSL+Agent 完成且行为等价）-> **停项**，不投入引擎重构。
- 非武侠微场景无法验证 CombatKernel 内核主题无关性 -> **暂停**，先做内核主题无关性重构。

完整 9 条 kill criteria 见 [04 §四](docs/xkx-arch/04-迁移路径与避坑清单.md)。

## 交接约定

- 新 session 第一件事：读本文件 + [CLAUDE.md](CLAUDE.md) + [04](docs/xkx-arch/04-迁移路径与避坑清单.md) §三（当前阶段）+ §四（kill criteria）。
- session 结束前：更新本文件的 Done / In Progress / Blocked / Next Up + 最后更新日期。
- 长任务跨 session：在 In Progress 写清"当前子任务 + 卡在哪 + 下一步具体动作"。
- 实施中发现架构假设需偏离 00-04 基线：在 [docs/adr/](docs/adr/) 写一条 ADR（编号递增），关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) 的对应 dissent。
- 跑测试：`pytest /home/gukt/github/xkx2001-utf8/engine`；lint：`ruff check /home/gukt/github/xkx2001-utf8/engine/src /home/gukt/github/xkx2001-utf8/engine/tests`。
