# 巫师/运营视角 User Stories

> 角色：UGC 游戏专家产出的「巫师/运营」层故事。覆盖创作者（题材包巫师）与运营如何配置、
> 维护、调优战斗 / Effect / 死亡内容。每条标注证据来源（LPC 文件或 engine 模块）。
>
> 三层故事分层：本文件=巫师/运营层（人工配置与维护）；玩家层见 `player-stories.md`；
> 系统自动层见 `system-stories.md`。

格式：`US-W##`（Wizard/Operator）。每条含「作为…我希望…以便…」+ 验收点 + 证据 + 当前缺口。

---

## A. 配武功（技能/招式创作与维护）

### US-W01 作为题材包巫师，我希望用 YAML 填表定义一招的数值，而不写代码

- **以便**：降低配招门槛，让非程序员创作者也能产出武功。
- **验收**：`skills:` 段下每招含 `name/force/dodge/damage_type/damage/lvl/text` 纯字段即可被引擎识别。
- **证据**：engine 已支持--`skills.py:23-33`(`SkillMove`) + `load_skills_from_mapping`(`:151`) +
  `m2_mvp_scene.yaml:639-644`（`luohan_quan` 的 `罗汉拳` 招）。对照 LPC `18-zhang.c:52-218`
  的 `action` 数组同样是数据，但 LPC 还需 `.c` 外壳。
- **缺口**：无。

### US-W02 作为题材包巫师，我希望声明招式的学习门槏（属性/技能/资源），而不写 valid_learn

- **以便**：控制武功学习进度，且门槏可被工具可视化校验。
- **验收**：`learn_condition` 用受限 AST（`gte`/`Equals`/`And`/`Or`）声明，如根骨≥10。
- **证据**：engine 已支持--`skills.py:234-242` + `m2_mvp_scene.yaml:628-631`（`gte: con>=10`）。
  对照 LPC `18-zhang.c:222-231` 的 `valid_learn` 硬编码「必须空手 / 混天气功≥20 / max_neili≥100」。
- **缺口**：LPC 的「必须空手」「未持械」这类装备态门槏，engine `learn_condition` 当前字段面
  不全（`conditions.py:37-87` 的 `ConditionContext` 有 `is_wielding_edged_weapon` 但无「是否空手」）。

### US-W03 作为题材包巫师，我希望配带连击/状态触发的复杂招式

- **以便**：实现降龙十八掌三悔连击、辟邪剑双击这类高阶武功。
- **验收**：能声明「当 force 技能==X 且内力>Y 时，本招替换为 Z 招并触发 post_action」。
- **证据**：LPC `18-zhang.c:241-291` 的 `query_action` 条件分支 + `post_action: (: sanhui :)`
  闭包（`:264`）。
- **缺口**：engine `SkillMove` 只静态字段（`skills.py:23-33`），无动态选招声明面；
  `SkillBehavior.post_action` 不许改伤害（`combat.py:274`），无法表达连击状态变更。
  创作者只能写 Python `SkillBehavior` 子类，违背「声明式优先」。

### US-W04 作为题材包巫师，我希望定义绝技（perform 大招）

- **以便**：每招武功附带主动释放的绝技（如亢龙有悔的 sanhui）。
- **验收**：武功下声明 `perform:` 子段，含绝技名/消耗/效果。
- **证据**：LPC 有 27 个 perform 子目录（`kungfu/skill/*/`），`18-zhang.c:304-307`
  `perform_action_file` 指向 `__DIR__"18-zhang/" + action`。
- **缺口**：engine 无 `perform` 概念，`SkillData`（`skills.py:36-53`）无绝技字段。

### US-W05 作为题材包巫师，我希望整体替换战斗公式以适配题材

- **以便**：武侠用 `(level^3)/3`，仙侠/科幻可换不同曲线。
- **验收**：实现 `PowerModel` 协议四个方法，挂到 world 即生效。
- **证据**：engine 已支持--`combat.py:72-83`(`PowerModel`) + `attach_power_model`(`:119`)。
  对照 LPC `s_combatd.c:212-245` 的 `skill_power` 硬编码 `(level^3)/3`，所有题材共用。
- **缺口**：无（但 `DefaultWuxiaPowerModel` 的 `str_factor`/`dex_factor` 是写死的，创作者只能
  整体替换不能微调系数，可考虑把系数也做成 YAML）。

### US-W06 作为题材包巫师，我希望给门派批量分配技能池

- **以便**：少林 60+ NPC 不用逐个指派技能。
- **验收**：`factions:` 段声明 `skill_pool` + `map_skill`，NPC 按门派继承。
- **证据**：engine 已支持--`m2_mvp_scene.yaml:653-664`（`shaolin` 的 `skill_pool:[luohan_quan,
  hunyuan_yiqi]` + `map_skill`）。对照 LPC `kungfu/class/shaolin/` 60+ NPC 文件逐个写。
- **缺口**：无。

---

## B. 挂 Effect（状态/特效创作与维护）

### US-W07 作为题材包巫师，我希望用 YAML 声明一个持续伤害 Effect（毒/灼烧）

- **以便**：配「中蛇毒每 tick 掉 5 点精、持续 20 tick」而不写 daemon。
- **验收**：`effects:` 段含 `type/duration/tick_damage(typed)/tick_message`。
- **证据**：LPC `bt_poison.c:7-42` 是 42 行 LPC daemon 实现「每 tick 掉 jing+jingli +
  按 eff_jing 三段文案 + duration 按 skill("poison") 自减」。
- **缺口**：**engine 完全无 Effect 引擎**--`conditions.py` 是布尔求值器（`:92-142`），
  与 LPC `condition.c` 的时效 Effect 引擎（`:21-69`）同名不同物。创作者当前无法声明任何
  持续性状态。这是最高优先级缺口。

### US-W08 作为题材包巫师，我希望声明 Effect 到期时的受限副作用（传送/拔甲）

- **以便**：配「坐牢到期传送到衙门」「中暗器嵌入自动拔甲」。
- **验收**：`expire_action` 从白名单枚举（`move_to_room`/`remove_equipped`/`clear_effect`）选，
  非任意代码。
- **证据**：LPC `city_jail.c:9` `me->move("/d/city/yamen")`；`embedded.c:23` 调
  `COMMAND_DIR"std/remove"->do_remove(me,ob)`--均为跨系统任意代码副作用。
- **缺口**：engine 无 Effect 引擎，无 `expire_action` 概念。LPC 的任意代码副作用是反面教材，
  应收敛为白名单。

### US-W09 作为题材包巫师，我希望声明 Effect 之间的覆盖/互斥/解毒关系

- **以便**：配「某药解某毒」「同毒不叠加只续命」。
- **验收**：Effect 声明 `tags`/`antidote_for`/`stack_rule`。
- **证据**：LPC `apply_condition` 直接覆盖无查重（`condition.c:79-85` 注释「不查重，由
  giver 负责」）；`bt_poison.c:36-38` duration 按 `skill("poison")` 缩--解毒机制各自为政。
- **缺口**：engine 无 Effect 引擎，无 Effect 关系声明面。

### US-W10 作为运营，我希望可视化查看某玩家当前 Effect 栈与剩余时长

- **以便**：处理「我中毒了为什么不掉血」类客服工单。
- **验收**：运营工具能列出玩家所有 active Effect + duration + 来源。
- **证据**：LPC `query_all_condition()`（`condition.c:10-13`）返回 conditions mapping。
- **缺口**：engine 无 Effect 引擎，无 Effect 栈可查。

---

## C. 调数值（数值平衡与公式调优）

### US-W11 作为数值运营，我希望预览一招在指定角色属性下的期望伤害

- **以便**：配招时即知强度，不用上线试。
- **验收**：输入角色 str/con/dex + 招式 force/damage，输出期望伤害 / 命中率 / 击杀回合。
- **证据**：LPC 无此工具，`s_combatd.c:637-644` 仅 wizard verbose 模式打印 AP/DP/PP/伤害。
  engine `PowerModel` 协议（`combat.py:72-83`）已为 dry-run 预留接口。
- **缺口**：engine 无数值沙盒/dry-run 求值器。

### US-W12 作为数值运营，我希望按伤害类型配置分级文案

- **以便**：「劈伤」「内伤」给不同档位文案，而非统一「造成 N 点伤害」。
- **验收**：YAML `damage_messages:` 段按 type + 区间配文案。
- **证据**：LPC `s_combatd.c:71-167` 的 `damage_msg` 硬编码 9 类 × 5-6 档文案表。
  engine `CombatRoundResult.message_fragments`（`combat.py:60-69`）只有「命中，造成 N 点伤害」。
- **缺口**：engine 无 damage_type 文案表声明面。

### US-W13 作为数值运营，我希望在题材包加载时跑平衡校验

- **以便**：同 lvl 招式 DPS 异常 / Effect 总伤过高 / 死亡惩罚占比过大时告警。
- **验收**：加载时输出校验报告，超阈值项标红。
- **证据**：LPC 无任何校验，`18-zhang.c` force 330-650 / damage 20-120 全凭作者手感。
- **缺口**：engine 无平衡校验工具。

### US-W14 作为数值运营，我希望微调 PowerModel 的系数而不整体替换

- **以便**：只改 `str_factor` 从 0.02 到 0.03，不重写整个 PowerModel。
- **验收**：`DefaultWuxiaPowerModel` 的 `str_factor`/`dex_factor` 可在 YAML 覆写。
- **证据**：engine `DefaultWuxiaPowerModel`（`combat.py:85-113`）系数是 dataclass 字段但
  无 YAML 覆写入口，只能 `attach_power_model` 传实例。
- **缺口**：系数无声明式覆写面。

---

## D. 设死亡惩罚与复活流程

### US-W15 作为题材包巫师，我希望用 YAML 配置死亡惩罚参数

- **以便**：不同题材包调不同死亡代价（武侠重惩 / 校园轻惩）。
- **验收**：`death_policy:` 段含 penalty_ratio/revive_room/drop_items/drop_currency。
- **证据**：engine 已支持--`death_flow.py:77-86`(`DeathPolicy`) + `parse_death_policy`(`:118`)
  + `m2_mvp_scene.yaml:665-667`。对照 LPC `s_combatd.c:874-907` 硬编码 combat_exp/shen/
  behavior_exp/potential/balance/skill 各项比例。
- **缺口**：engine `penalty_ratio` 是统一比例（`death_flow.py:291-305`），无法分项配置
  「掉 10% 经验但不掉钱」「死亡加善恶惩罚」--LPC 的分项惩罚表达力更强但焊死在 daemon，
  两者应折中：分项声明 + 仍纯数据。

### US-W16 作为题材包巫师，我希望配置「死后走地府」的叙事流程

- **以便**：复刻武侠死后变鬼走鬼门关解谜复活的体验，或换成题材自定流程。
- **验收**：声明死亡流程模板（房间序列 / 鬼魂态 / 复活触发点）。
- **证据**：LPC `d/death/` 13 房间 580 行手搓--`gate.c:30-47`（销毁 inventory + clear_condition）、
  `gateway.c:28-37`（单向封锁）、`inn1.c:51-83`（ask 谜题触发 `reincarnate()` + move）。
  `damage.c:246-248` 设 `ghost=1` + move DEATH_ROOM。
- **缺口**：engine 无 ghost 态（`death.py` 仅 ALIVE/UNCONSCIOUS/DEAD 三态）、无死亡区域、
  无轮回叙事--`_execute_player_death`（`death_flow.py:208-270`）直接掉物 + 复活到 revive_room。

### US-W17 作为运营，我希望配置 PvP 杀人的后果

- **以便**：城市内杀人给追杀标记、累计 PK 惩罚。
- **验收**：声明「在某区域杀人触发 Effect/计数」。
- **证据**：LPC `killer_reward`（`s_combatd.c:910-972`）硬编码 PKS/MKS 计数、`pker` condition
  100 tick（`:924`）、vendetta 世仇（`:965-966`）、城市内杀人特殊标记（`:923-924`）。
- **缺口**：engine 无 `killer_reward`、无 PK 计数、无 pker 追杀 Effect（因无 Effect 引擎）。

### US-W18 作为题材包巫师，我希望配置安全区（no_death）的死亡降级行为

- **以便**：比武场内死亡只昏迷不真死。
- **验收**：房间挂 `NoDeathZone`，死亡降级为昏迷。
- **证据**：engine 已支持--`death_flow.py:194-207` + `next_death_state(in_no_death_zone=...)`。
  对齐 LPC `damage.c:159-177` 的 `no_death` 降级。
- **缺口**：无，但无法配「安全区死亡仍扣 X%」（中间态），只能全降级或不降级。

### US-W19 作为运营，我希望配 NPC 战利品与击杀经验

- **以便**：山贼掉 15 银子 + 钱袋，给 10 经验。
- **验收**：NPC `loot:` 段声明 currency 区间 / items / kill_exp。
- **证据**：engine 已支持--`death_flow.py:89-97`(`LootTable`) + `parse_loot_table`(`:140`)
  + `m2_mvp_scene.yaml:603-609`（`wild_bandit`）。
- **缺口**：LPC `killer_reward` 还给 killer 加 shen/behavior_exp（`s_combatd.c:949-953`），
  engine 击杀只给 `kill_exp`（`death_flow.py:328-331`），无善恶/行为经验。

---

## E. 装备与战斗数值接入

### US-W20 作为题材包巫师，我希望配一把有数值的武器

- **以便**：钢刀伤害 30、影响战斗输出。
- **验收**：物品 `weapon_prop:` 段含 damage/skill_type 等。
- **证据**：LPC `inherit/weapon/sword.c:16-22` 的 `weapon_prop/damage` + `skill_type` +
  `inherit/equip.c:46-107` wield 堆叠进 `apply/*`。
- **缺口**：engine `Equippable` 是占位（`components.py:270-274`「M1 不实现 wield/wear」），
  `steel_blade` 只有 `tags:[weapon,edged]`（`m2_mvp_scene.yaml:406-414`）无数值。
  `combat_system.py:46` 用 `_DEFAULT_MOVE` 拳头，武器不喂战斗数值。

### US-W21 作为题材包巫师，我希望配武器命中时的特殊效果

- **以便**：钢剑命中削减对方护甲耐久。
- **验收**：武器声明 `hit_ob` 钩子或受限 effect 触发。
- **证据**：LPC `inherit/weapon/sword.c:24-67` 的 weapon `hit_ob` 削减 `armor_prop/armor`、
  改名「破X」、贬值--weapon 层副作用。`s_combatd.c:507-515` weapon `hit_ob` 接入点。
- **缺口**：engine 战斗钩子只有招式所属技能的 `SkillBehavior.hit_ob`（`combat.py:236-252`），
  无 weapon/armor 层钩子链。

### US-W22 作为运营，我希望装备分数值件与外观件

- **以便**：数值件不可付费（pay-to-win 红线），外观件可付费。
- **验收**：装备 schema 分 `stat_prop`（数值）/ `cosmetic`（外观）两槽。
- **证据**：CLAUDE.md 架构不变量 6（不 pay-to-win）。
- **缺口**：engine 装备占位无此区分（`components.py:270-274`）。

---

## F. 工具与运维

### US-W23 作为题材包巫师，我希望有效果编辑器造 Effect 而非写 daemon

- **以便**：72 个 Effect 不用逐个手搓。
- **验收**：可视化填 type/duration/tick_damage/tick_message/expire_action。
- **证据**：LPC 72 condition daemon 无统一 schema（`condition.c:79-85` `info` 是 mixed）。
- **缺口**：engine 无 Effect 引擎亦无编辑器。

### US-W24 作为运营，我希望死亡/战斗事件可埋点到题材包 ID

- **以便**：统计某题材包的战斗参与度、死亡率。
- **验收**：事件带 `source_pack` 元数据。
- **证据**：CLAUDE.md 架构不变量 6（消费/参与度埋点可打点到题材包 ID）。
- **缺口**：engine `CombatRoundResult`/`DeathContext`（`combat.py:60`/`death_flow.py:99-107`）
  无 `source_pack` 字段。

### US-W25 作为题材包巫师，我希望武功/装备/Effect 带创作者归属与版本元数据

- **以便**：支持跨题材包引用与创作者分成。
- **验收**：资产数据类含 `source_pack`/`author`/`version` 字段。
- **证据**：CLAUDE.md 架构不变量 6（题材包资产元数据：创作者归属 + 版本溯源）。
- **缺口**：engine `SkillData`/`LootTable`/`DeathPolicy` 均无此字段。

### US-W26 作为运营，我希望配置昏迷苏醒的 tick 数与恢复比例

- **以便**：调昏迷时长与醒来血量。
- **验收**：`death_policy:` 的 `unconscious_recovery_ticks`/`recovery_vitals_ratio`。
- **证据**：engine 已支持--`death_flow.py:84-85` + `:411-429` 苏醒逻辑。对照 LPC
  `damage.c:134` 的 `call_out("revive", random(100-con)+30)` 随机延迟（不可调）。
- **缺口**：无。
