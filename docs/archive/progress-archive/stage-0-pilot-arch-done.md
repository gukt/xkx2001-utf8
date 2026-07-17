# 阶段 0 pilot + 规格补充 + 架构补全 Done 归档

> 从 [PROGRESS.md](../../PROGRESS.md) 归档（2026-07-16），主文件只留门派迁移批滚动窗口。
> 细节见各 ADR。归档时 tests 数为当时快照。

- [x] 规格补充 Batch 1：修复 `layer_h_daemons.py` 漏列 `rankd.c`；新建 `layer_h_daemons2.py` 覆盖 CHANNEL_D / MONEY_D / UPDATE_D / ALIAS_D - 1926 tests
- [x] 规格补充 Batch 2：扩展 `layer_h_daemons2.py` 覆盖 FINGER_D / BAN_D / REGBAN_D / REGI_D / MARRY_D；新建 `layer_c_vote.py` 覆盖 vote / chblk / unchblk / vote_clear / vote_suspension - 1970 tests
- [x] 规格补充 Batch 3：扩展 `layer_h_daemons2.py` 覆盖 EMOTE_D / INQUIRY_D / PIG_D / PROFILE_D / ADS_D / EDITOR_D / WEAPON_D / LANGUAGE_D / VIRTUAL_D；扩展 `layer_h_race.py` 覆盖 human.c `create` / `query_action` / `default_actions` / `set_default_object` / eff_jingli / max_neili 交互；新建 `layer_f_hell.py` 覆盖阴间主路径 + 关键惩罚房间 - 1970 tests
- [x] 规格补充 Batch 4：新增 [ADR-0055](../../docs/adr/ADR-0055-spec-supplement-vote-human-hell-daemons2.md) 记录子层分类与范围决策 - 1970 tests
- [x] **pilot 样本 id=1 `xue.c:main`**：迁移 [samples/xue_c_main.py](../../engine/tools/sampling/pilot/samples/xue_c_main.py) + 16 单测 [tests/test_xue_c_main.py](../../engine/tests/test_xue_c_main.py)；扩展 stubs.py 3 个 A 类回落桩；记 effort 125min 到 effort_records.jsonl；1994 tests 全绿
- [x] **pilot 样本 id=3 `tieyanling.c:do_qingjiao`**：迁移 [samples/tieyanling_c_do_qingjiao.py](../../engine/tools/sampling/pilot/samples/tieyanling_c_do_qingjiao.py) + 15 单测 [tests/test_tieyanling_c_do_qingjiao.py](../../engine/tests/test_tieyanling_c_do_qingjiao.py)；扩展 stubs.py 1 个 teach_skillsname 桩；记 effort 65min；2009 tests 全绿
- [x] **pilot 剩余 11 样本并行迁移 + 区间承诺**：两阶段（预建 7 组共享桩 + Workflow 11 agent 并行），13 样本全绿 2189 tests，区间 [781,1724]h 详见 [REPORT](../../engine/tools/sampling/pilot/REPORT.md)；退路未触发（误分类 7.7%，high-tier CV 0.24）
- [x] [ADR-0056](../../docs/adr/ADR-0056-abandon-effort-estimation-ai-batched-migration.md)：放弃人工工时估算（项目由 AI agent 迁移，工时语义错位），改按架构依赖分批迁移；退役 ADR-0048 工时承诺部分，保留 pilot 副产出（缺口情报/桩/13 样本）
- [x] **第一批架构补全：message facade**：建 [message.py](../../engine/src/xkx/runtime/message.py)（tell_object/tell_room/message_vision 三段视角，照 simul_efun/message.c），收敛 death/governance _tell，修 death persist_now(eid) 断裂；+7 单测，2196 全绿
- [x] **第二批架构补全 A：per-object save DaemonStore**（[ADR-0057](../../docs/adr/ADR-0057-daemon-store-per-object-save.md)）：DaemonStore 独立 StorageSystem 复用原子写不走 dirty-flag；death 走 mark_dirty 不引入 per-eid 同步 persist（滑坡论证）；修第一批 persist_now 断裂+pilot 假绿+补 death 真单测；+22 tests
- [x] **第二批架构补全 B：item-as-entity ItemCatalog 方案 B**（[ADR-0058](../../docs/adr/ADR-0058-item-catalog-transition-layer.md)）：复用扩展 item_registry 台账+item_weight/item_query/item_move_to_room 函数族（写副作用 no-op 规避滚雪球）+WeaponDef schema；weight 双重语义/weapon_prop mapping 不变量；+19 tests，2237 全绿
- [x] **bboard 子系统迁移**（[ADR-0059](../../docs/adr/ADR-0059-bboard-subsystem-migration-scope.md)）：cmp_wiz_level fail-closed + BoardLastRead 组件 + BboardData 补字段 + bboard_commands（do_read/do_list/do_discard）+ DaemonStore save 闭环；do_post/do_store 暂缓（edit()/EDITOR_D 卡点）；do_list 无门控行为等价；+46 tests，2289 全绿
- [x] **B 类前 3 项架构补全**：skill 变更 API（[skill.py](../../engine/src/xkx/runtime/skill.py) set/delete/map/prepare + 读函数，补 3 处 LPC 行为）+ reset_action（[equipment.py](../../engine/src/xkx/runtime/equipment.py)，无 CombatState no-op/无武器 type 推断）+ setup_char（[chard.py](../../engine/src/xkx/runtime/chard.py) 新建，调 setup_race + 编排层）；stubs re-export；+32 tests，2312 全绿
