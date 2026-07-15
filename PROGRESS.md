# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
> 历史 Done 已按阶段归档至 [docs/progress-archive/](docs/progress-archive/)，本文件只保留当前阶段滚动窗口 + 活状态。

**最后更新**：2026-07-15（pilot AI 铺路完成）

## 当前状态速览

- **阶段**：阶段 0 pilot 实测（AI 铺路完成，待人工计时）
- **分支**：feat/sampling-pilot
- **tests**：1978 全绿，ruff 全过（+8 pilot estimate 单测）
- **关键 ADR**：[ADR-0055](docs/adr/ADR-0055-spec-supplement-vote-human-hell-daemons2.md)（规格补充分类决策）/ [ADR-0054](docs/adr/ADR-0054-m2-2-langfuse-still-postponed.md)（M2-2 Langfuse 不接）
- **新增规格子层**：`H-2` 第二梯队守护进程 / `C-VOTE` 玩家投票 / `F-HELL` 阴间流程
- **扩展现有子层**：`H-RACE` human.c 剩余规格 / 层 H `lpc_files` 补 rankd.c

## Done

- [x] 规格补充 Batch 1：修复 `layer_h_daemons.py` 漏列 `rankd.c`；新建 `layer_h_daemons2.py` 覆盖 CHANNEL_D / MONEY_D / UPDATE_D / ALIAS_D - 1926 tests
- [x] 规格补充 Batch 2：扩展 `layer_h_daemons2.py` 覆盖 FINGER_D / BAN_D / REGBAN_D / REGI_D / MARRY_D；新建 `layer_c_vote.py` 覆盖 vote / chblk / unchblk / vote_clear / vote_suspension - 1970 tests
- [x] 规格补充 Batch 3：扩展 `layer_h_daemons2.py` 覆盖 EMOTE_D / INQUIRY_D / PIG_D / PROFILE_D / ADS_D / EDITOR_D / WEAPON_D / LANGUAGE_D / VIRTUAL_D；扩展 `layer_h_race.py` 覆盖 human.c `create` / `query_action` / `default_actions` / `set_default_object` / eff_jingli / max_neili 交互；新建 `layer_f_hell.py` 覆盖阴间主路径 + 关键惩罚房间 - 1970 tests
- [x] 规格补充 Batch 4：新增 [ADR-0055](docs/adr/ADR-0055-spec-supplement-vote-human-hell-daemons2.md) 记录子层分类与范围决策 - 1970 tests

## In Progress

**pilot AI 铺路完成**（feat/sampling-pilot），交人工计时 `xue.c:main`：

- 建桩 [stubs.py](engine/tools/sampling/pilot/stubs.py)（6 桩）+ scan 扩展 `status_kind_tier` 交叉表（补 output/ 产出）+ 实现 [estimate.py](engine/tools/sampling/pilot/estimate.py) 推算核心 + 8 单测
- [xue 导航笔记](engine/tools/sampling/pilot/samples/xue_c_main.notes.md)（三态表+6桩+8后置分支+effort模板）；workflow 13 路三态对照完成，桩缺口清单 [stub_gaps.md](engine/tools/sampling/pilot/samples/stub_gaps.md)
- **纠偏信号**：workflow 发现 ~40 桩缺口（超 ADR-0048 点名 7 桩），含架构层（item-as-entity/消息分发）；首批测 xue 校准锚点，漂移大则触发 ADR-0048 退路

## Blocked

**当前无阻塞项。**

## Next Up

1. **人工计时 xue.c:main**（manifest id=1）：按 [导航笔记](engine/tools/sampling/pilot/samples/xue_c_main.notes.md) 补 8 后置分支 + 6 桩，记工时到 effort_records.jsonl。锚点 115-190min。
2. **后续 12 样本**：按 [stub_gaps.md](engine/tools/sampling/pilot/samples/stub_gaps.md) 桩缺口测，A 类简单桩按需补建，B 类架构缺口记为待迁移面或触发退路。
3. **推算区间承诺**：13 样本工时齐后跑 estimate.py，写报告 + 校验误分类率（>30% 触发退路）。

## kill criteria 状态（开工必读）

阶段 -1/0/1/2 与 M3 仍全部通过（详见 [stage-m2-mvp-done.md](docs/progress-archive/stage-m2-mvp-done.md)）。本次规格补充为阶段 0 后续补强，不引入新的 kill criteria 风险。

完整 9 条 kill criteria 见 [04 §四](docs/xkx-arch/04-迁移路径与避坑清单.md)。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [04](docs/xkx-arch/04-迁移路径与避坑清单.md) §三/§四。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 单条 ≤2 行，细节进 ADR。每开新阶段归档 Done 到 [docs/progress-archive/](docs/progress-archive/) `stage-N-done.md`。
- 偏离 00-04 基线写 ADR（编号递增），关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) dissent。
- 跑测试：`just test`（或 `cd engine && uv run pytest`）；lint：`just lint`（或 `cd engine && uv run ruff check src tests`）。统一用 `uv run`（.venv 未装 dev 依赖，裸 pytest/ruff 不可用）。全部命令见仓库根 [justfile](justfile)，`just --list` 自举。
