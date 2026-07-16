# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
> 历史 Done 已按阶段归档至 [docs/progress-archive/](docs/progress-archive/)，本文件只保留当前阶段滚动窗口 + 活状态。

**最后更新**：2026-07-16（wear 命令批完成，ADR-0064）

## 当前状态速览

- **阶段**：阶段 0 pilot 收尾 -> 转 AI agent 按架构依赖分批迁移（[ADR-0056](docs/adr/ADR-0056-abandon-effort-estimation-ai-batched-migration.md)）
- **分支**：feat/sampling-pilot
- **tests**：2416 全绿，ruff 全过（wear 命令批 +19 tests + 数据层 CPK 17->26）
- **关键 ADR**：[ADR-0057](docs/adr/ADR-0057-daemon-store-per-object-save.md)（DaemonStore）/ [ADR-0058](docs/adr/ADR-0058-item-catalog-transition-layer.md)（ItemCatalog 过渡层）/ [ADR-0059](docs/adr/ADR-0059-bboard-subsystem-migration-scope.md)（bboard 范围）/ [ADR-0060](docs/adr/ADR-0060-weapon-data-extraction-scope.md)（门派武器填表范围）/ [ADR-0061](docs/adr/ADR-0061-job-data-binary-source-equivalence.md)（job_data 等价边界）/ [ADR-0062](docs/adr/ADR-0062-weapon-cpk-wiring-postpone.md)（武器 CPK 接线）/ [ADR-0063](docs/adr/ADR-0063-wield-command-batch.md)（wield 命令批）/ [ADR-0064](docs/adr/ADR-0064-wear-command-batch.md)（wear 命令批）/ [ADR-0056](docs/adr/ADR-0056-abandon-effort-estimation-ai-batched-migration.md)（弃工时改 AI 分批）
- **pilot 报告**：[REPORT](engine/tools/sampling/pilot/REPORT.md)（工时数据归档，副产出保留）
- **新增规格子层**：`H-2` 第二梯队守护进程 / `C-VOTE` 玩家投票 / `F-HELL` 阴间流程
- **扩展现有子层**：`H-RACE` human.c 剩余规格 / 层 H `lpc_files` 补 rankd.c

## Done

> 早期 Done（规格补充 / pilot / 架构补全 / bboard / B 类，至 2312 tests）已归档至 [stage-0-pilot-arch-done.md](docs/progress-archive/stage-0-pilot-arch-done.md)。

- [x] **wear 命令批**（[ADR-0064](docs/adr/ADR-0064-wear-command-batch.md)）：armor_extract+finalize 脚本（235->145 护甲 21 门派，marker merge 进 items.yaml 不覆盖武器，9 新门派 CPK 补 manifest）+ ItemDef 扩 armor_prop/armor_type + wear/remove 命令（armor_type 消息分支+all+remove 只管护甲槽）；+19 tests，2416 全绿
- [x] **wield 命令批**（[ADR-0063](docs/adr/ADR-0063-wield-command-batch.md)）：wield/unwield 命令（双路径 CLI+COMMAND_REGISTRY）+ weapon_prop 注入 apply/<key> + flag 槽位判定 + skill_type 桥接 CombatState.attack_skill + is_busy/perform 门控 + wield all；WeaponDef/SAMPLE_WEAPONS/get_weapon_def 删除；+16 -6 tests，2397 全绿
- [x] **门派武器 CPK 接线**（[ADR-0062](docs/adr/ADR-0062-weapon-cpk-wiring-postpone.md) 决策 2）：wuxia_weapons 搬 17 数据层 CPK（wuxia_common + 16 门派，manifest 无 entry_points + items.yaml）；cli.py `_load_theme_data_items` glob 按题材前缀发现合并进 item_registry（149 武器）；ThemeRegistry 未改；wield 未实现；+4 tests，2387 全绿
- [x] **ADR-0060/0061 定稿**：[ADR-0060](docs/adr/ADR-0060-weapon-data-extraction-scope.md) 门派武器填表范围（填 ItemDef 非 WeaponDef/去重/四维拆分/flag 逐类型确认）/ [ADR-0061](docs/adr/ADR-0061-job-data-binary-source-equivalence.md) job_data 等价边界三档 + 纠正 ADR-0057 措辞
- [x] **job_data 子系统迁移**（[ADR-0061](docs/adr/ADR-0061-job-data-binary-source-equivalence.md)）：daemons/job_data.py（JobData + DaemonSerializable + from_lpc_o + 12 API）+ job_server.py + job_commands.py（4 命令）+ daemons/__init__ 注释修正；算法级推断标注（choose_of_player/query_family_jobdata/query_list）；+50 tests，2371 全绿
- [x] **门派武器提取脚本**（[ADR-0060](docs/adr/ADR-0060-weapon-data-extraction-scope.md)）：[weapon_extract.py](engine/tools/weapon_extract.py)，全量提取 267 武器，flag 14 类型全确认，后置 34 标注，草表待填表
- [x] **门派武器数据填表**（[ADR-0060](docs/adr/ADR-0060-weapon-data-extraction-scope.md) + [ADR-0062](docs/adr/ADR-0062-weapon-cpk-wiring-postpone.md)）：[weapon_finalize.py](engine/tools/weapon_finalize.py) 草表去重分类（267→152 唯一→149 条，em 折叠 emei/跳过 3 COMBINED_ITEM）落 [scenes/wuxia_weapons/](engine/scenes/wuxia_weapons/) common.yaml(98)+sect/16 门派(51)；WeaponDef 标 deprecated；+12 tests，2383 全绿

## In Progress

**wear 命令批已完成（ADR-0064）。装备命令侧完备**（wield/unwield + wear/remove，149 武器 + 145 护甲 = 301 item_registry）。**下批转 2.4 Combat 迁移专项**（候选 2，装备侧已铺路 attack_skill/armor_prop 进 apply_*，combat 可切）。

## Blocked

**当前无阻塞项。**

## Next Up

> 装备命令侧完备（wield/unwield + wear/remove，ADR-0063/0064），301 item_registry（149 武器 + 145 护甲）。wield->combat 衔接已通（[resolve_attack.py:163](engine/src/xkx/combat/resolve_attack.py#L163) 用 `attack_skill`/`weapon_label`），无需额外衔接批。

1. **2.4 Combat 迁移专项**（高价值大工程，装备侧已铺路）：do_attack 七步管线副作用账本 + 29 处 `random()` 收口 DeterministicRNG + 闭包 call_out->Effect + 阵法合击 CombatModifier（[04 §三 2.4](docs/xkx-arch/04-迁移路径与避坑清单.md)）。
2. **job_data/bboard 暂缓命令**（待基础设施）：do_check_menpai_assess/do_setorg_*（job_system+CHANNEL_D）/ do_post（input_to）/ do_store（EDITOR_D）。
3. **门派 CPK 正式化**（[ADR-0062](docs/adr/ADR-0062-weapon-cpk-wiring-postpone.md) 决策 2 后置）：数据层 CPK（现 26，含护甲新增 9）补 rooms/npcs。
4. **迁 PG**（kill criteria 8）/ **记 AI 成本**（[ADR-0056](docs/adr/ADR-0056-abandon-effort-estimation-ai-batched-migration.md)）。

## kill criteria 状态（开工必读）

阶段 -1/0/1/2 与 M3 仍全部通过（详见 [stage-m2-mvp-done.md](docs/progress-archive/stage-m2-mvp-done.md)）。本次规格补充为阶段 0 后续补强，不引入新的 kill criteria 风险。

完整 9 条 kill criteria 见 [04 §四](docs/xkx-arch/04-迁移路径与避坑清单.md)。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [04](docs/xkx-arch/04-迁移路径与避坑清单.md) §三/§四。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- **commit & push 自主决定**：每完成一个可交付推进单元（子系统迁移 / 一批填表 / 一个 ADR / 测试全绿），可自行决定是否 commit & push 到当前分支，无需逐次询问用户。完整可交付单元即提交并推送；零散探索 / 调试 / 中间态不提交。仍遵守 master 分支先开分支（[CLAUDE.md](CLAUDE.md)）。
- Done 单条 ≤2 行，细节进 ADR。每开新阶段归档 Done 到 [docs/progress-archive/](docs/progress-archive/) `stage-N-done.md`。
- 偏离 00-04 基线写 ADR（编号递增），关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) dissent。
- 跑测试：`just test`（或 `cd engine && uv run pytest`）；lint：`just lint`（或 `cd engine && uv run ruff check src tests`）。统一用 `uv run`（.venv 未装 dev 依赖，裸 pytest/ruff 不可用）。全部命令见仓库根 [justfile](justfile)，`just --list` 自举。
