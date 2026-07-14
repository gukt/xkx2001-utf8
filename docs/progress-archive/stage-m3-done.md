# Done 归档 - M3 Wave 1/2 早期（CPK 格式化 + 门派核心循环子任务 1-5）

> 从 PROGRESS.md 归档于 2026-07-14。M3 Wave 1（M3-2 CPK 格式化）+ Wave 2 早期
> 子任务（M3-1 拜师 / 练功 / 任务链 / 内容生产 / demo 整合）已完成条目的历史记录，
> 按需检索。Wave 2 收尾（完整内容扩展 + kill criteria 5 达标）+ Wave 3（M3-3 内容
> 审核 pipeline）保留在 [PROGRESS.md](../../PROGRESS.md) 滚动窗口。

- [x] M3 启动前置（[ADR-0031](../../docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md) + [16-M3](../../docs/xkx-arch/16-M3-单题材武侠可玩demo实施计划.md)）- 5 Wave 分解 + ADR 编号映射 + 8-12 周预估
- [x] M3-2 CPK 格式化 + StdLib CPK 骨架（[ADR-0031](../../docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md) Wave 1）- CpkManifest + ThemeRegistry 静态加载 + 5 微场景重整 StdLib CPK - 1628 tests
- [x] M3-1 拜师机制（[ADR-0032](../../docs/adr/ADR-0032-family-core-loop-design.md) 决策 1，子任务 1）- FamilyComp + bai/kneel/recruit/betrayer + ApprenticeDef 声明式配置 - 1651 tests
- [x] M3-1 练功机制（[ADR-0032](../../docs/adr/ADR-0032-family-core-loop-design.md) 决策 2，子任务 2）- improve_skill + learn/practice/dazuo/tuna/enable + busy condition（EffectComp）- 1680 tests
- [x] M3-1 任务链扩展（[ADR-0032](../../docs/adr/ADR-0032-family-core-loop-design.md) 决策 3，子任务 3）- 多步 chain + fight 命令 + time-gate 可重复 + kill_npc/reach_room/fight_win - 1692 tests
- [x] M3-1 内容生产子集（[ADR-0036](../../docs/adr/ADR-0036-content-llm-volcano-ark-langfuse-postpone.md)，子任务 4）- 火山方舟 LLM 客户端 + 生成管线 + SkillData CPK 加载 + kill criteria 5 前 2 轮数据（37.0% / 56.9%）- 1724 tests
- [x] M3-1 子任务 5 可玩 demo 整合（[ADR-0037](../../docs/adr/ADR-0037-m3-1-subtask5-playtest-demo-integration.md)）- CLI 接 Engine 自动推进 + 消息缓冲 + 死亡轮回 die() + ConditionSystem 跳过 death_stage - 1733 tests
