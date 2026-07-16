# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
> 历史 Done 已按阶段归档至 [docs/progress-archive/](docs/progress-archive/)，本文件只保留当前阶段滚动窗口 + 活状态。

**最后更新**：2026-07-16（B 类前 3 项架构补全 + ADR-0060/0061 + job_data 迁移 + 门派武器提取脚本）

## 当前状态速览

- **阶段**：阶段 0 pilot 收尾 -> 转 AI agent 按架构依赖分批迁移（[ADR-0056](docs/adr/ADR-0056-abandon-effort-estimation-ai-batched-migration.md)）
- **分支**：feat/sampling-pilot
- **tests**：2371 全绿，ruff 全过（+32 B 类前 3 项架构补全 + 50 job_data 迁移单测）
- **关键 ADR**：[ADR-0057](docs/adr/ADR-0057-daemon-store-per-object-save.md)（DaemonStore）/ [ADR-0058](docs/adr/ADR-0058-item-catalog-transition-layer.md)（ItemCatalog 过渡层）/ [ADR-0059](docs/adr/ADR-0059-bboard-subsystem-migration-scope.md)（bboard 范围）/ [ADR-0060](docs/adr/ADR-0060-weapon-data-extraction-scope.md)（门派武器填表范围）/ [ADR-0061](docs/adr/ADR-0061-job-data-binary-source-equivalence.md)（job_data 等价边界）/ [ADR-0056](docs/adr/ADR-0056-abandon-effort-estimation-ai-batched-migration.md)（弃工时改 AI 分批）
- **pilot 报告**：[REPORT](engine/tools/sampling/pilot/REPORT.md)（工时数据归档，副产出保留）
- **新增规格子层**：`H-2` 第二梯队守护进程 / `C-VOTE` 玩家投票 / `F-HELL` 阴间流程
- **扩展现有子层**：`H-RACE` human.c 剩余规格 / 层 H `lpc_files` 补 rankd.c

## Done

- [x] 规格补充 Batch 1：修复 `layer_h_daemons.py` 漏列 `rankd.c`；新建 `layer_h_daemons2.py` 覆盖 CHANNEL_D / MONEY_D / UPDATE_D / ALIAS_D - 1926 tests
- [x] 规格补充 Batch 2：扩展 `layer_h_daemons2.py` 覆盖 FINGER_D / BAN_D / REGBAN_D / REGI_D / MARRY_D；新建 `layer_c_vote.py` 覆盖 vote / chblk / unchblk / vote_clear / vote_suspension - 1970 tests
- [x] 规格补充 Batch 3：扩展 `layer_h_daemons2.py` 覆盖 EMOTE_D / INQUIRY_D / PIG_D / PROFILE_D / ADS_D / EDITOR_D / WEAPON_D / LANGUAGE_D / VIRTUAL_D；扩展 `layer_h_race.py` 覆盖 human.c `create` / `query_action` / `default_actions` / `set_default_object` / eff_jingli / max_neili 交互；新建 `layer_f_hell.py` 覆盖阴间主路径 + 关键惩罚房间 - 1970 tests
- [x] 规格补充 Batch 4：新增 [ADR-0055](docs/adr/ADR-0055-spec-supplement-vote-human-hell-daemons2.md) 记录子层分类与范围决策 - 1970 tests
- [x] **pilot 样本 id=1 `xue.c:main`**：迁移 [samples/xue_c_main.py](engine/tools/sampling/pilot/samples/xue_c_main.py) + 16 单测 [tests/test_xue_c_main.py](engine/tests/test_xue_c_main.py)；扩展 stubs.py 3 个 A 类回落桩；记 effort 125min 到 effort_records.jsonl；1994 tests 全绿
- [x] **pilot 样本 id=3 `tieyanling.c:do_qingjiao`**：迁移 [samples/tieyanling_c_do_qingjiao.py](engine/tools/sampling/pilot/samples/tieyanling_c_do_qingjiao.py) + 15 单测 [tests/test_tieyanling_c_do_qingjiao.py](engine/tests/test_tieyanling_c_do_qingjiao.py)；扩展 stubs.py 1 个 teach_skillsname 桩；记 effort 65min；2009 tests 全绿
- [x] **pilot 剩余 11 样本并行迁移 + 区间承诺**：两阶段（预建 7 组共享桩 + Workflow 11 agent 并行），13 样本全绿 2189 tests，区间 [781,1724]h 详见 [REPORT](engine/tools/sampling/pilot/REPORT.md)；退路未触发（误分类 7.7%，high-tier CV 0.24）
- [x] [ADR-0056](docs/adr/ADR-0056-abandon-effort-estimation-ai-batched-migration.md)：放弃人工工时估算（项目由 AI agent 迁移，工时语义错位），改按架构依赖分批迁移；退役 ADR-0048 工时承诺部分，保留 pilot 副产出（缺口情报/桩/13 样本）
- [x] **第一批架构补全：message facade**：建 [message.py](engine/src/xkx/runtime/message.py)（tell_object/tell_room/message_vision 三段视角，照 simul_efun/message.c），收敛 death/governance _tell，修 death persist_now(eid) 断裂；+7 单测，2196 全绿
- [x] **第二批架构补全 A：per-object save DaemonStore**（[ADR-0057](docs/adr/ADR-0057-daemon-store-per-object-save.md)）：DaemonStore 独立 StorageSystem 复用原子写不走 dirty-flag；death 走 mark_dirty 不引入 per-eid 同步 persist（滑坡论证）；修第一批 persist_now 断裂+pilot 假绿+补 death 真单测；+22 tests
- [x] **第二批架构补全 B：item-as-entity ItemCatalog 方案 B**（[ADR-0058](docs/adr/ADR-0058-item-catalog-transition-layer.md)）：复用扩展 item_registry 台账+item_weight/item_query/item_move_to_room 函数族（写副作用 no-op 规避滚雪球）+WeaponDef schema；weight 双重语义/weapon_prop mapping 不变量；+19 tests，2237 全绿
- [x] **bboard 子系统迁移**（[ADR-0059](docs/adr/ADR-0059-bboard-subsystem-migration-scope.md)）：cmp_wiz_level fail-closed + BoardLastRead 组件 + BboardData 补字段 + bboard_commands（do_read/do_list/do_discard）+ DaemonStore save 闭环；do_post/do_store 暂缓（edit()/EDITOR_D 卡点）；do_list 无门控行为等价；+46 tests，2289 全绿
- [x] **B 类前 3 项架构补全**：skill 变更 API（[skill.py](engine/src/xkx/runtime/skill.py) set/delete/map/prepare + 读函数，补 3 处 LPC 行为）+ reset_action（[equipment.py](engine/src/xkx/runtime/equipment.py)，无 CombatState no-op/无武器 type 推断）+ setup_char（[chard.py](engine/src/xkx/runtime/chard.py) 新建，调 setup_race + 编排层）；stubs re-export；+32 tests，2312 全绿
- [x] **ADR-0060/0061 定稿**：[ADR-0060](docs/adr/ADR-0060-weapon-data-extraction-scope.md) 门派武器填表范围（填 ItemDef 非 WeaponDef/去重/四维拆分/flag 逐类型确认）/ [ADR-0061](docs/adr/ADR-0061-job-data-binary-source-equivalence.md) job_data 等价边界三档 + 纠正 ADR-0057 措辞
- [x] **job_data 子系统迁移**（[ADR-0061](docs/adr/ADR-0061-job-data-binary-source-equivalence.md)）：daemons/job_data.py（JobData + DaemonSerializable + from_lpc_o + 12 API）+ job_server.py + job_commands.py（4 命令）+ daemons/__init__ 注释修正；算法级推断标注（choose_of_player/query_family_jobdata/query_list）；+50 tests，2371 全绿
- [x] **门派武器提取脚本**（[ADR-0060](docs/adr/ADR-0060-weapon-data-extraction-scope.md)）：[weapon_extract.py](engine/tools/weapon_extract.py)，全量提取 267 武器，flag 14 类型全确认，后置 34 标注，草表待填表

## In Progress

**门派武器数据填表**（[ADR-0060](docs/adr/ADR-0060-weapon-data-extraction-scope.md)）：提取脚本 [weapon_extract.py](engine/tools/weapon_extract.py) 就绪，全量提取 267 武器，flag 14 类型全确认（sword/blade\|EDGED、hammer/throwing/whip/bow 不合并、staff/stick/club/pike/hook\|LONG、dagger\|EDGED\|SECONDARY、fork\|POINTED），后置 34 标注。当前卡在：草表（/tmp/weapons_all.yaml）待落 ItemDef YAML + 去重（em/emei 复制，clone/weapon 为权威）+ 分公共/门派 CPK + load_items 加载测试 + 人工校验 long/weapon_prop。

## Blocked

**当前无阻塞项。**

## Next Up

1. **门派武器填表**（[ADR-0060](docs/adr/ADR-0060-weapon-data-extraction-scope.md)）：草表 267 武器落 ItemDef YAML + 去重（em/emei，clone/weapon 权威）+ 分公共/门派 CPK + load_items 测试 + 人工校验 long/weapon_prop。
2. **job_data 暂缓命令**（[ADR-0061](docs/adr/ADR-0061-job-data-binary-source-equivalence.md)）：do_check_menpai_assess + do_setorg_*（待 job_menpai 数据层）/ do_start_system 等（待 job_system + CHANNEL_D）。
3. **bboard 暂缓命令**：do_post（待 input_to）/ do_store（待 EDITOR_D）。
4. **迁 PG**（kill criteria 8）：DaemonStore 与 StorageSystem 同步策略切换。
5. **记 AI 成本**（[ADR-0056](docs/adr/ADR-0056-abandon-effort-estimation-ai-batched-migration.md)）：token/运行时间。

## kill criteria 状态（开工必读）

阶段 -1/0/1/2 与 M3 仍全部通过（详见 [stage-m2-mvp-done.md](docs/progress-archive/stage-m2-mvp-done.md)）。本次规格补充为阶段 0 后续补强，不引入新的 kill criteria 风险。

完整 9 条 kill criteria 见 [04 §四](docs/xkx-arch/04-迁移路径与避坑清单.md)。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [04](docs/xkx-arch/04-迁移路径与避坑清单.md) §三/§四。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 单条 ≤2 行，细节进 ADR。每开新阶段归档 Done 到 [docs/progress-archive/](docs/progress-archive/) `stage-N-done.md`。
- 偏离 00-04 基线写 ADR（编号递增），关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) dissent。
- 跑测试：`just test`（或 `cd engine && uv run pytest`）；lint：`just lint`（或 `cd engine && uv run ruff check src tests`）。统一用 `uv run`（.venv 未装 dev 依赖，裸 pytest/ruff 不可用）。全部命令见仓库根 [justfile](justfile)，`just --list` 自举。
