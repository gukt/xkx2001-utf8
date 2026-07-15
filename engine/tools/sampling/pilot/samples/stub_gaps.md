# pilot 建桩缺口清单（workflow 13 路三态对照汇总）

> 来源：workflow `wpn2dje17`（13 路 LPC->新引擎三态对照 + 汇总）。
> 这是 AI 铺路交付的纠偏数据：workflow 发现的缺口远超 ADR-0048 点名 7 桩。
> 样本 id = manifest id（1-13）：1=xue.c:main 2=center.c 3=tieyanling.c 4=murong.c
> 5=songshan-jian.c 6=damage.c 7=emoted.c 8=shizi.c 9=bboard.c 10=snake.c
> 11=char.c 12=s_combatd.c 13=bai.c

## 纠偏信号（重要）

workflow 汇总出 **~40 个建桩缺口**，远超 ADR-0048 点名的 5+2=7 桩。说明 13 路样本
真实迁移工时可能**高于**"补 8 后置分支"预期--大量缺口是 dbase key 回落、efun 适配、
架构层（item-as-entity / 消息分发 / 路径对象模型）。

若人工实测确认分类漂移大（误分类率 >30% 或 high-tier CV>1.0），触发 ADR-0048 决策 5
退路（升级接力补测）。**首批测 xue.c:main 即可校准**。

## 已建桩（stubs.py，6 个，xue.c:main 核心依赖）

| 桩 | used_by | 状态 |
|---|---|---|
| is_spouse_of | 1,3 | ✅ 已建（默认 False） |
| recognize_apprentice | 1,3 | ✅ 已建（默认 False） |
| prevent_learn | 1,3 | ✅ 已建（默认 False） |
| query_skill_name | 1,3 | ✅ 已建（默认 None） |
| to_chinese | 1,3 | ✅ 已建（默认 skill_id） |
| receive_damage(通用化) | 1,3 | ✅ 已建（扣 Vitals clamp） |

## 待建桩（workflow 发现，按"简单桩 / 架构层缺口"分类）

### A. 简单桩（dbase key 回落 / efun 适配，测时按需建，可快速补）

| 桩 | used_by | 说明 |
|---|---|---|
| env/* dbase keys（no_teach/immortal/invisibility） | 1,3,6,7 | POSTPONED_KEYS，query raise，回落 None |
| family/ 子路径（family_name/generation/master_id） | 1,6,13 | PATH_PREFIX_MAP 未路由，回落 FamilyComp |
| POSTPONED/统计 dbase key 回落（id/death_times/balance 等） | 6,7,12 | query None+warn / set raise，回落默认值 |
| query("jiali") | 5,8 | 未映射，回落 0 |
| LPC efun 适配包装层（userp/living/objectp/name 等） | 1,3,5,6,7,12,13 | 薄适配层读组件字段 |
| 命令输出 efun 适配（notify_fail/write/printf） | 1,2,3,5,7,9,13 | append messages / Abort |
| wizardp(ob) | 6,7,12,13 | 回落 False（无 wiz_level 组件） |
| query_kar/query_per | 10 | 回落 0 |
| chinese_number | 13 | 回落 str(number) |
| SECURITY_D.cmp_wiz_level | 9 | WizLevel 枚举序比较 |
| ANSI 颜色（normal_color/HIW/NOR 等） | 5,7 | identity / strip |
| INTERMUD_MUD_NAME | 7 | 回落空串（单机排除） |
| set_living_name/find_living | 11 | no-op 占位 |

### B. 架构层缺口（非 pilot 桩层，测时若卡则记为"待迁移面"或触发退路）

| 缺口 | used_by | 说明 |
|---|---|---|
| 物品对象模型（item-as-entity） | 3,5,8,9 | weight/rigidity/value/move/unequip/amount |
| 消息分发 facade（message/tell_room/tell_object） | 1,3,5,7,13 | 房间广播+定向发送 |
| LPC 路径对象模型（find_object/load_object/clone_object） | 2,6 | greenfield 用 entity_id |
| job_data 子系统 | 2 | 门派任务数据对象整体未迁移 |
| skill-feature 变更 API（set_skill/map_skill/prepare_skill） | 4 | Skills dict 已就绪无命名函数 |
| reset_action 完整重算 | 4,5,8,11 | 招式映射刷新 |
| CHAR_D.setup_char 完整编排（8 种族+shen 公式） | 11 | setup_race 仅 human |
| per-object save/restore（F_SAVE 语义） | 9 | StorageSystem 全量非 per-object |
| per-object add_action 自定义命令（bian/convert/tan） | 8,10 | COMMAND_REGISTRY 仅全局 verb |
| NPC_TRAINEE 驯兽能力 | 10 | trainable/wildness/auto_follow |
| bboard 物品 dbase（board_id/notes/last_read） | 9 | ItemComp 承接 |
| start_more 分页显示 | 2,9 | 全引擎无 pager |
| remove_all_killer/remove_all_enemy | 6 | CombatState.enemy_ids 无清理方法 |
| interrupt_me / dismiss_team / log_file | 6 | 打断/队伍/日志 efun |
| CHANNEL_D.do_channel / CHAR_D.break_relation | 6 | 后置 M3 stub |
| SKILL_D.valid_combine / query_str sefun | 4,5,8 | SkillData 无字段 / 无派生 |
| relay_emote / find_player | 7 | NPC 感知 / 全局查玩家 |
| tune/open channels | 9 | channeld 未实现 |
| bai/pending 握手 dbase keys（possessed/special_master/score） | 13 | unknown raise |

## 建议

1. **首批测 xue.c:main**：6 桩已建，但 env/no_teach（A 类）query 会 raise，测时需临时回落
   或补建 safe_query 桩。xue 的 family/family_name（L58-60）同理。
2. **A 类桩**（13 个简单桩）可快速补建（各 5-15min），若多样本共用建议一次性补。
3. **B 类架构缺口**：非 pilot 桩层，测时若某样本卡在 B 类缺口，记为"该样本待迁移面
   扩大"（工时含缺口处理），或触发退路。
4. **纠偏校准**：测完 xue 后，对比预期（115-190min）vs 实测，若实测显著超（因 A/B 类
   缺口），说明 high-tier 锚点偏低，回调 ADR-0048 锚点 + 考虑退路。
