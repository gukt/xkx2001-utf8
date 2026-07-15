# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
> 历史 Done 已按阶段归档至 [docs/progress-archive/](docs/progress-archive/)，本文件只保留当前阶段滚动窗口 + 活状态。

**最后更新**：2026-07-15（M2-2 实现完成）

## 当前状态速览

- **阶段**：M2-2 UGC 创作闭环增强轮实现完成（分支 `feat/m2-ugc-loop-r2`）
- **分支**：feat/m2-ugc-loop-r2
- **tests**：1857 全绿，ruff 全过
- **关键 ADR**：[ADR-0053](docs/adr/ADR-0053-m2-ugc-loop-mvp-scope.md)（M2 MVP）/ [ADR-0054](docs/adr/ADR-0054-m2-2-langfuse-still-postponed.md)（M2-2 Langfuse 不接）
- **新增内容**：layer2 InquiryNode 交易原子节点 / FastAPI+WebSocket 评审工作台 / ClaudeClient adapter / `just serve-workbench`
- **工具链**：`fastapi` + `uvicorn[standard]` 作为 `[workbench]` optional dependency；`httpx` 进 dev 依赖供 TestClient

## Done

- [x] M2-2 layer2 Ink 对话树最小实现 - `dsl/layer2.py` 的 `InquiryNode` + `InkStory` + `compile_ink_to_inquiries`；`NpcDef.inquiry` 扩展为 `dict[str, str | InquiryNode]`；运行时 `ask()` 支持 transaction 副作用（flag/物品）+ `next_topic` 链 + `once` 移除；向后兼容纯字符串 inquiry - 1857 tests
- [x] M2-2 FastAPI + WebSocket 评审工作台 - 新建 `xkx.workbench` 包：`app.py` / `router.py` / `ws.py` / `runner.py` / `static/index.html` / `__main__.py`；REST endpoints（list/get/asset/review/create-job）+ WebSocket 实时阶段事件；Orchestrator 增加 `event_callback`，workbench 用 `asyncio.Queue` + `loop.call_soon_threadsafe` 线程安全桥广播 - 1857 tests
- [x] M2-2 ClaudeClient adapter - `content_gen.llm_client.ClaudeClient`（stdlib urllib 调用 Anthropic Messages API）+ `create_llm_client` 工厂；`orchestrator`/`content_gen` CLI 增加 `--provider volcano|claude`；`.env.example` 增加 Anthropic 配置；保留 VolcanoArk 为主 - 1857 tests
- [x] M2-2 Langfuse 不接决策记录 - [ADR-0054](docs/adr/ADR-0054-m2-2-langfuse-still-postponed.md) + `content_gen/__init__.py` docstring 清理过时暗示

## In Progress

**当前无进行中的阻塞性子任务。** M2-2 已按计划完成，等待 review 或进入下一阶段。

## Blocked

**当前无阻塞项。**

## Next Up

1. **pilot 实测**（`feat/sampling-pilot`）：阶段 0 验收硬交付物，AI 铺路建桩 + 人工计时。manifest id=1 `xue.c:main` 起步。
2. **规格补充**：层 H 第二梯队 / 层 C（vote）/ 层 I（human.c）/ 层 F（阴间流程）按 [08 §七](docs/xkx-arch/08-阶段-0-实施计划.md) "实现到时才补"。
3. **合并当前分支**：`feat/m2-ugc-loop-r2` 可合并 master 或保留。

## kill criteria 状态（开工必读）

阶段 -1/0/1/2 与 M3 仍全部通过（详见 [stage-m2-mvp-done.md](docs/progress-archive/stage-m2-mvp-done.md)）。M2-2 为增强轮，不引入新的 kill criteria 风险。

完整 9 条 kill criteria 见 [04 §四](docs/xkx-arch/04-迁移路径与避坑清单.md)。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [04](docs/xkx-arch/04-迁移路径与避坑清单.md) §三/§四。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 单条 ≤2 行，细节进 ADR。每开新阶段归档 Done 到 [docs/progress-archive/](docs/progress-archive/) `stage-N-done.md`。
- 偏离 00-04 基线写 ADR（编号递增），关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) dissent。
- 跑测试：`just test`（或 `cd engine && uv run pytest`）；lint：`just lint`（或 `cd engine && uv run ruff check src tests`）。统一用 `uv run`（.venv 未装 dev 依赖，裸 pytest/ruff 不可用）。全部命令见仓库根 [justfile](justfile)，`just --list` 自举。
