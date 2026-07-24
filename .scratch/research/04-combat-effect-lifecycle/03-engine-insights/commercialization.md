# 战斗与效果生命周期簇：商业化与增长评估

> 角色：商业化与增长专家。从付费设计、UGC 创作者经济、题材包消费、用户增长角度评估「战斗与效果生命周期簇」商业潜力。
> 红线来源：[CLAUDE.md](../../../../CLAUDE.md)「架构不变量」第 6 条 + [06 号票](../../../../.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md)（不 pay-to-win；双货币 + 订阅；创作者按题材包消费分成；四个支撑点 MVP 留位置不实现）。
> 证据规则：每条结论标注来源（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名）。

---

## 0. 商业化前提与红线框架

[06 号票](../../../../.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md) 定下叠加方案：玩家侧照 Iron Realms（双货币 + 订阅 + 不 pay-to-win），创作者侧照 Roblox/Fortnite（题材包消费按比例分成）。四条硬红线贯穿全文：

| 红线 | 含义 | 战斗簇关联 |
|------|------|-----------|
| **不 pay-to-win** | 花钱买加速/便利，不买压倒性优势 | 武功/装备/复活付费必须区分「便利性」与「数值」 |
| **双货币** | 免费金币 + premium 点数，可在玩家间市场互换 | 战斗消费须能区分货币来源 |
| **创作者分成** | 题材包内消费按比例分给对应创作者 | 武功/装备/Effect 须能追溯到题材包 + 创作者 |
| **横向扩展** | 承载扩展靠题材包数量，不是单世界做大 | 战斗机制须题材无关，数值归题材包 |

ADR-0004 已定下「流程归引擎、数值归题材包」边界（`docs/adr/0004-combat-effects-boundary-engine.md`）：引擎内嵌七步 + AP/DP 概率判定结构为不变量；题材包注入每步具体数值/文案/钩子行为 + PowerModel 求值公式。这条边界正是商业化的分水岭——**引擎层做不得任何偏向某题材包数值的付费捷径**，否则破坏横向扩展与不 pay-to-win。

---

## 1. 战斗付费点评估（逐项标注 pay-to-win 红线）

### 1.1 死亡惩罚减免——最强付费潜力，但红线最密

**LPC 死亡惩罚实证**（`adm/daemons/combatd.c:death_penalty()` :987-1025，`s_combatd.c:death_penalty()` :874-907 同构）：

- `combat_exp` 损失 = `combat_exp / 100`，上限 5000，下限 20（:1001-1011）
- `potential`（潜力）腰斩（:1007-1008）
- `balance`（金钱余额）超过 10000 的部分减半（:1013-1015：`amount = balance - 10000; if (amount > 0) victim->add("balance", -amount/2)`）
- `shen`（善恶/阵营）-20%（:999）
- `behavior_exp` -20%（:1000）
- `skill_death_penalty()`（`feature/skill.c:121-147`）：所有技能等级 -1，`skill_map` 清空
- `death_count` 累加（:1016）
- `death_times` 按 `combat_exp >= 10000 * death_times` 阈值累加（:997-998）

**死亡是 LPC 里惩罚最重的单一事件**：同时打击经验、潜力、金钱、技能等级、阵营五条成长线。`feature/damage.c:die()` :184 还会 `clear_condition()` 清空所有 Effect（含正面 buff）。

**付费潜力**（Iron Realms 式便利性付费，非数值付费）：

| 付费项 | 性质 | 红线判定 |
|--------|------|---------|
| 死亡后保留 `skill_map`（不用重新 map 技能） | 便利性 | **安全**——LPC `skill_death_penalty()` :145 已清 `skill_map`，重 map 是纯操作负担，不涉及数值 |
| 死亡后缩短地府轮回路径（`d/death/road2.c:24-46` 的「走五次才出」迷宫） | 便利性 | **安全**——`road2.c:valid_leave()` 的 `long_road` 计数是纯时间消耗，不影响数值 |
| 死亡后选择复活点（不回默认 `reincarnate` 后的出生地） | 便利性 | **安全**——engine `death_flow.py:DeathPolicy.revive_room_key` 已是题材包可声明字段（:82），付费选点是便利 |
| 死亡后不掉落背包物品 | **数值边界** | **红线**——LPC `die()` :226-228 `make_corpse` 会产尸体含物品；engine `DeathPolicy.drop_items` :84 默认 True。付费免掉落 = 用钱保住装备 = 变相数值优势。**若做，必须对所有人开放同等免掉落（如订阅福利）或限定「绑定物品」不可掉落且绑定物品本身无数值溢价** |
| 死亡后减免 `combat_exp` / `potential` 惩罚 | **数值付费** | **红线，禁止**——直接减少数值损失 = pay-to-win |
| 死亡后减免 `balance` 金钱损失 | **货币付费** | **红线，禁止**——等于用 premium 换游戏内货币保全，破坏双货币经济 |

**结论**：死亡惩罚的付费空间集中在「便利性」（保 skill_map、跳地府迷宫、选复活点），这三项对应 LPC `skill.c:skill_death_penalty()` :145、`d/death/road2.c:valid_leave()` :24、`damage.c:die()` :247 的 `move(DEATH_ROOM)`。engine 已在 `death_flow.py:DeathPolicy` 预留 `revive_room_key` :82 与 `penalty_ratio` :81 字段，便利性付费可挂在这些字段上做条件分支，不碰数值。**数值减免（exp/potential/balance/skill level）一律不得付费减免。**

### 1.2 武功/技能——作为内容资产的付费，不是数值付费

**LPC 武功结构实证**（`inherit/skill/skill.c` + `kungfu/skill/*.c`）：

- 每个武功是独立 daemon（`inherit/skill/skill.c` 基类，:7 `inherit F_CLEAN_UP`），含 `action` 映射数组（每招 force/dodge/parry/damage/lvl/damage_type）
- `kungfu/skill/18-zhang.c`（降龙十八掌）：18 招，force 330-650，damage 20-120，lvl 5-90（:52-218），高阶招有 `post_action` 连击钩子（:264 `sanhui`）
- `kungfu/skill/beiming-shengong.c`（北冥神功）：`hit_by()` :26-49 钩子，命中时吸对方 `max_neili`（:36-37 `victim->add("max_neili", +N); me->add("max_neili", -N)`）
- `feature/skill.c:improve_skill()` :149-182：技能升级有 `learned` 经验积累，超 `(skills[skill]+1)^2` 才升一级；学太多技能有惩罚（:167 `if (sizeof(learned) > spi) amount /= sizeof(learned) - spi`，spi 默认 30）
- `feature/skill.c:map_skill()` :42-58：技能映射（如把 strike 映射到 18-zhang），战斗时 `reset_action()` 查映射调 daemon

**付费潜力**：

| 付费项 | 性质 | 红线判定 |
|--------|------|---------|
| 付费解锁「额外」武功（超出题材包默认武功集） | 内容解锁 | **安全，但有条件**——engine `skills.py:SKILLS` :54 是全局注册表，题材包声明 `skills:` 段填充（`load_skills_from_mapping` :151）。付费解锁 = 题材包内额外内容包。**但解锁的武功数值不得高于免费武功上限**，否则 pay-to-win |
| 付费加速技能升级（双倍经验） | 便利性 | **边界安全**——LPC `improve_skill` :176 升级阈值 `(skills+1)^2` 是平方曲线，加速只省时间不破上限。**但加速倍率须全玩家可获取（订阅福利），不能是 premium 独占的更高倍率** |
| 付费购买「顶级」武功（数值碾压免费武功） | **数值付费** | **红线，禁止**——直接用钱买更强武功 = pay-to-win |
| 付费重置技能（退还不满意的选择） | 便利性 | **安全**——LPC `delete_skill()` :27-38 已支持删除，付费重置是便利 |
| 付费购买技能栏位（突破 30 上限 `spi`） | **数值边界** | **红线**——LPC `improve_skill` :167 的 `spi=30` 是技能数量惩罚上限，突破 = 减少学习惩罚 = 数值优势 |

**结论**：武功付费的安全区是「内容解锁（等价或更低数值）」+「便利性加速（全玩家可获取同等倍率）」。engine `skills.py:SkillData` :37 已是纯数据声明式结构（skill_id/skill_type/level_req/moves/practice costs/exp_thresholds），天然支持作为题材包资产打包——**这正是创作者经济的核心资产形态**（见 §2）。

### 1.3 装备——磨损与消耗的付费空间

**LPC 装备结构实证**（`feature/equip.c` + `inherit/weapon/` + `inherit/armor/`）：

- `feature/equip.c:wield()` :46-107：装备武器时把 `weapon_prop` 叠加到 `apply` temp（:101-102），支持双手/副手/双手互博
- `feature/equip.c:wear()` :7-44：穿戴护具时把 `armor_prop` 叠加到 `apply`（:36-40），同类型护具只能一件（:29-30）
- `inherit/weapon/sword.c:hit_ob()` :24-67：**武器会磨损对方护具**——每次命中 `random(weapon->query("weapon_prop/damage")) >= 10` 时，对方 `armor/cloth` 的 `armor_prop/armor` -1（:37），累计到 `k/4` 时护具变「破」`value=0`（:44-49）
- `inherit/skill/skill.c:hit_ob()` :142-157：武器可带毒（`poison_applied`），命中时 `apply_condition("snake_poison", ...)`（:147-148）

**付费潜力**：

| 付费项 | 性质 | 红线判定 |
|--------|------|---------|
| 付费修理磨损装备（恢复 `armor_prop/armor`） | 便利性 | **安全**——LPC `sword.c:hit_ob` :37 的护具磨损是纯消耗，付费修理是便利。engine `death_flow.py:LootTable` 无修理概念，须新增 |
| 付费购买「外观」装备（数值等价，仅文案不同） | 纯外观 | **安全**——不碰数值 |
| 付费购买「更高数值」装备 | **数值付费** | **红线，禁止** |
| 付费购买「不磨损」装备 | **数值边界** | **红线**——LPC `sword.c:hit_ob` 的磨损是战斗平衡的一部分（强武器磨损对方护具），免磨损 = 数值优势 |
| 付费购买带毒武器（`poison_applied` > 0） | **数值边界** | **红线**——`skill.c:hit_ob` :146 带毒武器命中即挂 condition，是数值优势 |

**结论**：装备付费安全区是「修理便利」+「纯外观」。engine `components.py:ShopEntry` :657 已支持物品商店（`item_template_key` + `price` + `resell_discount`），但无耐久/磨损字段——**若做磨损修理付费，须在物品模板预留耐久字段（MVP 不实现）**。

### 1.4 复活与保护期——地府流程的付费空间

**LPC 地府流程实证**（`d/death/` + `feature/damage.c`）：

- `feature/damage.c:die()` :247：`this_object()->move(DEATH_ROOM); DEATH_ROOM->start_death(this_object())`——死后变鬼进入地府
- `feature/damage.c:die()` :246：`ghost = 1`——鬼魂态标记
- `d/death/gate.c:36`：进鬼门关时 `destruct(inv[i])` **销毁所有携带物品**（非角色物品全毁）
- `d/death/road2.c:24-46`：`valid_leave()` 的 `long_road` 计数，须走 5 次才能通过（:30 `if (i == 5) return 1`）
- `d/death/inn1.c:67-83`：`do_stuff()` 调 `ob->reincarnate()` 后 `move("/d/city/wumiao")`——轮回复活回武庙
- `feature/damage.c:reincarnate()` :255-264：复活后回满气血内力（`set("jing", max_jing)` 等）
- `d/death/gate.c:46-55` / `road2.c:54-59` / `inn1.c:44-49`：地府内 `suicide` 命令被 block（「你还死着呢」）

**付费潜力**：

| 付费项 | 性质 | 红线判定 |
|--------|------|---------|
| 付费跳过地府迷宫（直接 reincarnate） | 便利性 | **安全**——`road2.c` 的 `long_road` 五次走是纯时间消耗 |
| 付费保留地府入口不被销毁的物品 | **数值边界** | **红线**——`gate.c:36` 销毁携带物是死亡惩罚的一部分，付费保留 = 减轻惩罚 |
| 付费选择复活点（不回默认武庙） | 便利性 | **安全**——engine `death_flow.py:DeathPolicy.revive_room_key` :82 已可声明 |
| 付费缩短复活冷却时间 | 便利性 | **安全**——engine `death_flow.py:DeathPolicy.unconscious_recovery_ticks` :85 已可声明，付费缩短昏迷苏醒时间不碰数值 |
| 付费购买「免死」保护期（一段时间不死亡） | **数值付费** | **红线**——等于用钱买无敌 |

**结论**：复活付费安全区是「跳迷宫便利」+「选复活点」+「缩短昏迷冷却」。engine `death_flow.py` 已有 `DeathPolicy` 数据类（:77-86）承载这些参数，但地府迷宫流程（`d/death/` 的 room 流转）在 engine 中**不存在**——engine 用 `revive_room_key` 直接传送（:256-258），更简单。**地府迷宫是 LPC 特色内容，可作为题材包可选内容，付费跳过是便利**。

### 1.5 战斗保护期与 PvP 调控

**LPC PvP 机制实证**：

- `feature/attack.c:kill_ob()` :51-62：`kill_ob` 加 `killer` 列表，通知对方
- `cmds/std/kill.c:51-53`：`pker` condition > 240 或对方 `mud_age < 18000` 时禁止 kill（新手保护）
- `adm/daemons/combatd.c:killer_reward()` :1047：城内 PK 加 `killer` condition 100 时长（官府通缉）
- `adm/daemons/combatd.c:killer_reward()` :1089：重复 PK 加 `pker` condition +120（PK 惩罚递增）
- `feature/attack.c:MAX_OPPONENT=4` :12：最多同时 4 个对手
- `feature/attack.c:init()` :247-257：`vendetta` / `aggressive` / `hatred` 自动战斗触发

**付费潜力**：

| 付费项 | 性质 | 红线判定 |
|--------|------|---------|
| 付费购买 PvP 保护期（一段时间不被强制 PK） | 便利性 | **边界安全**——LPC `kill.c:51-53` 已有新手保护（`mud_age < 18000`），付费延长保护期是便利。**但不得在 PvP 区域提供「强制保护」**，否则破坏 PvP 玩法 |
| 付费查看对手战斗数值（AP/DP/PP） | 便利性 | **安全**——LPC `combatd.c:734-742` 的 verbose 模式只给 wizard，付费给玩家是信息便利，不碰数值 |
| 付费购买更多对手槽位（突破 MAX_OPPONENT=4） | **数值付费** | **红线**——`attack.c:12` 的 4 对手上限是战斗平衡，突破 = 数值优势 |

**结论**：PvP 付费安全区是「保护期便利」+「信息查看」。engine `combat_system.py:try_engage()` :93-114 目前是 1v1（`Engaged` 单对手，:112-113），LPC 的 `MAX_OPPONENT=4` 多对手未实现——**多对手是未来扩展点，但不得作为付费项**。

---

## 2. 武功/装备/Effect 作为题材包资产：归属、版本溯源、创作者分成

### 2.1 LPC 的资产分离结构——天然适合题材包化

LPC 已将「内容资产」与「引擎机制」分离，这正是题材包经济的结构基础：

| 资产类 | LPC 路径 | engine 对应 | 资产化可行性 |
|--------|---------|------------|-------------|
| 武功招式 | `kungfu/skill/*.c`（每个武功独立 daemon，含 `action` 映射 + `hit_ob`/`hit_by` 钩子） | `engine/src/openmud/skills.py:SkillData` :37 + `SkillBehavior` :60 协议 | **高**——engine 已是声明式纯数据 + 可选钩子 |
| Effect/状态 | `kungfu/condition/*.c`（每个 condition 独立 daemon，含 `update_condition` 逻辑） | engine **无对应**（`conditions.py` 是布尔求值器，非 Effect 引擎，见 §4 批判） | **须新建**——Effect handler 是题材包资产核心 |
| 武器 | `inherit/weapon/*.c`（15 类，`weapon_prop` + `hit_ob` 钩子） | `components.py:ShopEntry` :657 + `Valuable` 组件 | **中**——engine 有物品商店但无 `hit_ob` 钩子 |
| 护具 | `inherit/armor/*.c`（`armor_prop`） | engine 有装备组件但无磨损 | **中** |
| 门派武功集 | `kungfu/class/*/`（19 门派，武功打包归属） | engine `components.py:Faction` :681 | **高**——门派是天然的内容包单元 |
| 死亡流程 | `d/death/`（地府 room 流转） | `death_flow.py:DeathPolicy` :77（仅参数，无地府内容） | **中**——地府是题材包可选内容 |

**关键发现**：LPC 的 `kungfu/class/` 目录（19 门派：baituo/dali/emei/gaibang/gumu/huashan/lingjiu/mingjiao/murong/quanzhen/shaolin/shenlong/taohua/wudang/xingxiu/xixia/xuedao/xueshan）本身就是「门派 = 内容包」的天然分组——每个门派有自己的武功集。这直接映射到「题材包 = 创作者内容包」的商业模式。

### 2.2 归属与版本溯源支撑点

[06 号票](../../../../.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md) 第 2 点要求「题材包资产元数据：带创作者归属 + 版本来源（provenance）」。

**LPC 证据**：LPC 无任何归属/版本元数据——`kungfu/skill/18-zhang.c` 只有 `// Modified by xQin 1/99` 注释（:3），`kungfu/skill/beiming-shengong.c` 有 `// Acep, modified by xuy`（:4），这些是源码注释，不是运行时元数据。**LPC 没有资产归属概念，这是新引擎必须从零建的支撑点。**

**engine 现状**：
- `skills.py:SkillData` :37 有 `skill_id` 字段，但无创作者归属 / 版本号 / 来源题材包 ID
- `skills.py:SKILLS` :54 是全局注册表，`load_skills_from_mapping` :151 从 YAML `skills:` 段加载，但加载后丢失「来自哪个包」的信息
- `components.py:ItemTemplateKey` :431 有 `key` 字段（物品模板键），但同样无归属
- `death_flow.py:LootTable` :90 的 `item_template_keys` 引用物品模板，但模板本身无归属

**应在 engine 预留的支撑点**（MVP 不实现，但留位置）：

1. **SkillData 增加 `pack_id` / `creator_id` / `version` 字段**：`skills.py:SkillData` :37 当前是 `@dataclass(frozen=True)`，追加这三个可选字段不破坏现有形状（默认 None）。这让每条武功能追溯到「哪个题材包 + 哪个创作者 + 哪个版本」。
2. **Effect handler 注册表带归属**：Effect handler（对应 LPC `kungfu/condition/*.c` 的 `update_condition`）目前 engine 无对应模块，新建时须从一开始就带 `pack_id` / `creator_id`。
3. **物品模板带归属**：`components.py:ItemTemplateKey` :431 追加 `pack_id` / `creator_id`，让武器/护具/消耗品可追溯。
4. **全局注册表改为「按 pack_id 分区」**：`skills.py:SKILLS` :54 当前是扁平 `dict[str, SkillData]`，多包加载时 skill_id 冲突无法处理。应改为 `dict[str, dict[str, SkillData]]`（外层 pack_id，内层 skill_id），或 skill_id 前缀 pack_id。

### 2.3 创作者分成机制的战斗簇接缝

[06 号票](../../../../.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md) 第 1 点要求「每一笔消费要能追溯到『题材包 + 物品 + 创作者』三元」。

**战斗簇的消费场景**（基于 LPC 实证）：

| 消费场景 | LPC 证据 | 分成对象 | engine 接缝 |
|---------|---------|---------|------------|
| 付费解锁武功 | `feature/skill.c:set_skill()` :17-25 / `map_skill()` :42-58 | 武功所属题材包创作者 | `skills.py:SkillData` 须带 `pack_id` |
| 付费购买装备 | `feature/equip.c:wield()` :46-107 / `cmds/std/wield.c` | 装备所属题材包创作者 | `components.py:ShopEntry` :657 须带 `pack_id` |
| 付费修理装备 | `inherit/weapon/sword.c:hit_ob()` :24-67（磨损机制） | 装备所属题材包创作者 | engine 无磨损，须新增 |
| 付费跳过地府 | `d/death/road2.c:valid_leave()` :24-46 | 地府内容所属题材包创作者 | `death_flow.py:DeathPolicy` :77 须带 `pack_id` |
| 付费缩短昏迷 | `feature/damage.c:unconcious()` :134（`call_out("revive", random(100-con)+30)`） | 复活机制所属题材包创作者 | `death_flow.py:DeathPolicy.unconscious_recovery_ticks` :85 |
| 付费重置技能 | `feature/skill.c:delete_skill()` :27-38 | 技能系统（引擎，不分成） | 无须——这是引擎便利 |

**结论**：分成机制要求每笔战斗相关消费能追溯到 `pack_id`。当前 engine 的 `Currency` 组件（`components.py:Currency` :650）是单一 `amount: int`，**无货币来源标记**——无法区分「免费金币」与「premium 点数」，也无法记录消费去向。这是分成机制的最大缺口（见 §5）。

---

## 3. 死亡惩罚与商业化：付费减免的安全边界

### 3.1 LPC 死亡惩罚的五大维度——逐项评估付费空间

`adm/daemons/combatd.c:death_penalty()` :987-1025 的五条惩罚线：

| 惩罚维度 | LPC 代码 | 严重度 | 付费减免红线 |
|---------|---------|--------|-------------|
| 经验损失 | `combat_exp -= amount`（:1006，1/100 上限 5000） | 高 | **禁止付费减免**——经验是成长核心，用钱保经验 = pay-to-win |
| 潜力损失 | `potential -= potential/2`（:1008） | 高 | **禁止付费减免**——潜力是技能成长资源 |
| 金钱损失 | `balance -= (balance-10000)/2`（:1013-1015） | 中 | **禁止付费减免**——等于用 premium 保游戏内货币 |
| 技能等级损失 | `skill_death_penalty()`（`feature/skill.c:121-147`，所有技能 -1） | 高 | **禁止付费减免**——技能等级是战斗数值 |
| 阵营损失 | `shen -= shen/20`（:999） | 低 | **可付费保留**——阵营是社交/门派属性，非战斗数值；但须全玩家可获取 |

### 3.2 engine 的死亡惩罚模型——已预留但无分层

**engine 现状**（`death_flow.py`）：

- `DeathPolicy` :77-86：`penalty_ratio: float = 0.1`（统一比例，不区分经验/金钱/技能）
- `_apply_currency_penalty()` :291-296：`loss = int(currency.amount * ratio)`——按统一比例扣钱
- `_apply_skill_exp_penalty()` :299-305：`loss = int(prog.exp * ratio)`——按统一比例扣技能经验
- `_drop_inventory_to_room()` :283-288：掉落整个背包

**LPC 与 engine 的关键差异**：
1. LPC 的金钱惩罚是「超过 10000 的部分减半」（`combatd.c:1013`），有免税额；engine 是「按比例全扣」（`death_flow.py:295`），无免税额——**engine 比 LPC 更严**。
2. LPC 的经验惩罚是「1/100 上限 5000 下限 20」（`combatd.c:1001-1011`），非线性；engine 是「按比例全扣」，线性——**engine 更简单但损失了 LPC 的分级保护**。
3. LPC 的技能惩罚是「每技能 -1 级 + 清 skill_map」（`skill.c:121-147`）；engine 是「按比例扣经验」（`death_flow.py:299-305`），不降等级——**engine 更温和**。
4. LPC 有地府轮回流程（`d/death/`）；engine 无，直接传送复活点——**engine 省略了 LPC 的内容**。

### 3.3 付费减免的安全设计原则

基于以上分析，死亡惩罚付费减免须遵循三条原则：

1. **数值惩罚不可付费减免**：经验、潜力、金钱、技能等级四条线（对应 LPC `combatd.c:1006/1008/1013/skill.c:121`），付费减免任一都构成 pay-to-win。
2. **便利性惩罚可付费减免**：地府迷宫时间（`d/death/road2.c:24`）、skill_map 重置（`skill.c:145`）、复活点选择（`damage.c:247`）——这些是操作负担不是数值损失。
3. **惩罚参数须题材包可声明且公开**：`death_flow.py:DeathPolicy` :77-86 的 `penalty_ratio` / `drop_items` / `drop_currency` 须在题材包 manifest 中明示，玩家付费前知情。**不得隐藏惩罚参数或付费后秘密降低**——这违反不 pay-to-win 的透明性原则。

**engine 预留建议**：`DeathPolicy` :77-86 增加 `mitigations: tuple[MitigationSpec, ...]` 字段（MVP 不实现），让题材包可声明「付费跳迷宫」「付费选复活点」等便利性减免，引擎层只做参数承载不做付费逻辑（付费逻辑在平台层，见 [post-mvp-backlog](../../../../.scratch/mvp-scope/post-mvp-backlog.md)）。

---

## 4. 战斗数值埋点：可打点到题材包 ID 的支撑点

### 4.1 LPC 已有的埋点雏形——可直接借鉴

**LPC 死亡日志实证**（`feature/damage.c:die()` :208-224）：

```c
if ( userp(this_object()) ) {
    if (stringp(query_temp("last_eff_damage_from")) ) {
        log_file("PKILL_DATA", sprintf("%s(%s) 被 %s 杀死了(PlayerKill) on %s。\n", ...));
        log_file("PLAYER_DEATH", sprintf("%s(%s) 被 %s 杀死了(PlayerKill) on %s。\n", ...));
    }
    else if (objectp(killer)){
        log_file("PLAYER_DEATH", sprintf("%s(%s) 被 %s 杀死了 on %s。\n", ...));
    }
}
```

LPC 已有「玩家死亡 + 凶手 + 时间」的埋点（`log_file("PLAYER_DEATH")` :213），但**无题材包 ID 维度**——因为 LPC 只有单一世界。

### 4.2 engine 的事件点——埋点的天然接缝

engine 在战斗/死亡流程中已埋下多处事件分发点，这些是埋点的天然接缝：

| 事件点 | engine 位置 | 可埋点维度 | 题材包 ID 接缝 |
|--------|------------|-----------|---------------|
| 战斗回合前 | `combat_system.py:ON_BEFORE_COMBAT_ROUND` :41 / `resolve_one_strike()` :143 | 攻击者/防御者/招式/时间 | `CombatRoundContext` :50 须带 `pack_id` |
| 战斗回合后 | `combat_system.py:ON_COMBAT_ROUND` :42 / `resolve_one_strike()` :155 | 伤害/命中/闪避/招架 | `CombatRoundResult` :59 须带 `pack_id` |
| 战斗结束 | `combat_system.py:ON_COMBAT_END` :43 / `clear_engagement()` :128 | 结束原因/双方 | `CombatEndContext` :60 须带 `pack_id` |
| 死亡前（可否决） | `death_flow.py:ON_BEFORE_DEATH` :43 / `_execute_player_death()` :224 | 死亡者/凶手/房间 | `DeathContext` :99 须带 `pack_id` |
| 死亡 | `death_flow.py:ON_DEATH` :44 / `_execute_player_death()` :239 | 死亡者/凶手/惩罚 | `DeathContext` :99 须带 `pack_id` |
| 复活 | `death_flow.py:ON_REVIVE` :45 / `_execute_player_death()` :266 | 复活者/复活点 | `DeathContext` :99 须带 `pack_id` |
| tick | `events.py:ON_TICK`（combat_system `_on_combat_tick` :248 / death_flow `_on_unconscious_tick` :417） | 全局战斗/昏迷 tick | `TickContext` 须带 `pack_id` |

**关键缺口**：以上所有事件上下文（`CombatRoundContext` / `CombatEndContext` / `DeathContext` / `TickContext`）均**无 `pack_id` 字段**。`DeathContext` :99 有 `entity_id` / `world` / `death_room` / `killer_id`，但无「发生在哪个题材包」的维度。

### 4.3 应打点的战斗消费行为

基于 LPC 实证，以下战斗行为应打点到题材包 ID：

| 行为 | LPC 证据 | 打点维度 | 用途 |
|------|---------|---------|------|
| 玩家死亡 | `damage.c:die()` :152 / `combatd.c:death_penalty()` :987 | 死亡次数/原因/凶手/题材包 | 题材包难度调优 / 死亡率分析 |
| PvP 击杀 | `combatd.c:killer_reward()` :1027 / `damage.c:die()` :210-214 | 凶手/受害者/地点/题材包 | PvP 热力图 / 题材包 PvP 活跃度 |
| 技能使用 | `combatd.c:do_attack()` :340-780 / `skill.c:query_skill_mapped()` :80 | 技能 ID/命中率/伤害/题材包 | 技能平衡性分析 / 题材包技能使用率 |
| 装备使用 | `equip.c:wield()` :46 / `equip.c:wear()` :7 | 装备模板/属性/题材包 | 装备流行度 / 题材包装备消费 |
| Effect 触发 | `condition.c:apply_condition()` :79 / `condition.c:update_condition()` :21 | Effect ID/时长/来源/题材包 | Effect 平衡性 / 题材包 Effect 使用率 |
| 商店购买 | `components.py:ShopEntry` :657 | 物品/价格/货币类型/题材包 | 消费分成结算 / 题材包营收分析 |
| 昏迷与苏醒 | `damage.c:unconcious()` :105 / `revive()` :137 | 昏迷次数/苏醒时间/题材包 | 玩家挫败分析 / 题材包难度 |

**结论**：engine 的事件分发机制（`events.py:ON_TICK` + `combat_system.py` 三事件 + `death_flow.py` 三事件）是埋点的天然基础，但所有事件上下文缺 `pack_id` 维度。**应在 `World` 层面挂载 `pack_id`**（单进程单世界，见 [ADR-0009](../../../../docs/adr/0009-single-process-single-world.md)），事件上下文从 `world.pack_id` 读取——这是最小改动且覆盖所有事件点的方案。

---

## 5. 商业支撑点在 engine 的预留建议

[06 号票](../../../../.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md) 定下四个支撑点「MVP 不要求实现，但要留位置」。逐项评估战斗簇的预留：

### 5.1 货币/账本抽象——战斗簇的最大缺口

**现状**：`components.py:Currency` :650 是单一 `amount: int`（银两），无货币类型区分、无来源标记、无消费去向。

**战斗簇需求**：
- 死亡金钱惩罚（`death_flow.py:_apply_currency_penalty()` :291）须区分「扣的是免费金币还是 premium」——LPC `combatd.c:1013` 的 `balance` 是单一货币，但新引擎双货币下须分别扣减
- 商店购买装备（`components.py:ShopEntry` :657）须记录「用哪种货币买的」——分成只对 premium 消费生效
- 付费解锁武功须记录「消费去向哪个题材包」——这是分成结算的依据

**预留建议**（MVP 不实现，但留位置）：
1. `Currency` :650 增加可选 `currency_type: str` 字段（默认 `"silver"`），区分免费金币与 premium 点数
2. 新增 `LedgerEntry` 数据类（不进存档，纯内存）：记录 `{timestamp, from_entity, to_entity, amount, currency_type, pack_id, item_key, creator_id}`——这是分成结算的账本行
3. `_apply_currency_penalty()` :291 按货币类型分别扣减（免费金币全扣 / premium 不扣或低比例扣——premium 是真钱，重罚会引发客诉）
4. `_grant_loot()` :352 的 `currency.amount += amount` 须标记来源为「战利品」（免费金币）

### 5.2 题材包资产元数据——已在 §2.2 详述

**预留建议**：`SkillData` :37 / `ItemTemplateKey` :431 / Effect handler（新建）均追加 `pack_id` / `creator_id` / `version` 三字段。

### 5.3 消费/参与度埋点——已在 §4 详述

**预留建议**：`World` 挂载 `pack_id`，所有事件上下文从 `world.pack_id` 读取。事件分发点已有，只缺维度。

### 5.4 世界实例隔离——战斗簇的隔离边界

[ADR-0009](../../../../docs/adr/0009-single-process-single-world.md) 定下单进程单 World。[06 号票](../../../../.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md) 第 4 点要求「每个题材包/世界实例独立进程运行」。

**战斗簇的隔离边界**：
- `combat_system.py:CombatSystem` :70 是纯内存运行时态（`rng` / `flee_success_chance`），每个 World 实例独立——**已天然隔离**
- `skills.py:SKILLS` :54 是全局注册表（`dict[str, SkillData]`），`replace_skills_registry()` :170 每次 `load_scene` 清空重建——**单 World 下安全，但多 World 并行时是全局共享状态，须改为按 World 隔离**
- `skills.py:_SKILL_BEHAVIORS` :56 同理是全局注册表——**同上**
- `combat.py:_DEFAULT_POWER_MODEL` :116 是全局单例——**多 World 须各自挂载**（`attach_power_model()` :119 已支持 per-world 挂载，但默认单例共享）

**预留建议**：
1. `SKILLS` / `_SKILL_BEHAVIORS` 从模块级全局改为 `World` 实例属性（`world.skills_registry` / `world.skill_behaviors`），让每个 World 实例独立持有
2. `combat_system.py:attach_combat_system()` :77 已是 per-world 挂载，保持
3. 保留「单进程单 World」运行形态，但数据结构按「未来一进程多 World」隔离——这是最小成本的预留

---

## 6. 综合结论与风险提示

### 6.1 战斗簇商业化潜力排序

| 商业化方向 | 潜力 | 红线风险 | engine 预留状态 |
|-----------|------|---------|----------------|
| 死亡便利性付费（跳迷宫/选复活点/缩短昏迷） | 高 | 低（纯便利） | `DeathPolicy` 已有参数字段 |
| 武功内容解锁（题材包额外武功） | 高 | 中（须数值等价） | `SkillData` 须加归属字段 |
| 装备修理付费 | 中 | 低（纯消耗） | engine 无磨损，须新增 |
| PvP 保护期便利 | 中 | 中（不得破坏 PvP） | engine 无保护期机制 |
| 技能重置付费 | 低 | 低（便利） | engine 无重置命令 |
| 死亡数值减免 | — | **禁止** | — |
| 顶级武功/装备售卖 | — | **禁止** | — |

### 6.2 关键风险提示

1. **conditions.py 概念错位是商业化最大隐患**：`conditions.py` 是布尔求值器（`Predicate`/`Equals`/`Gte`/`And`/`Or`/`Not`，:92-142），用于门条件/物品限制/NPC 行为，**完全不是** LPC `feature/condition.c` 的时效性 Effect 引擎（`apply_condition`/`update_condition`/`CND_CONTINUE`）。这意味着 Effect 作为题材包资产的载体在 engine 中**根本不存在**——创作者无法定义「中毒」「醉酒」「包扎」等 Effect。这是 UGC 创作者经济的核心缺口，须新建 Effect handler 模块。

2. **双货币在死亡惩罚中的处理未定义**：LPC `combatd.c:1013` 的金钱惩罚是单一货币，engine `Currency` :650 也是单一货币。引入双货币后，死亡扣哪种货币、premium 是否豁免、如何避免「用 premium 换游戏内金币再被罚」的套利——这些都未定义，须在平台层设计。

3. **`SKILLS` 全局注册表是多 World 隔离的障碍**：`skills.py:SKILLS` :54 和 `_SKILL_BEHAVIORS` :56 是模块级全局变量，`replace_skills_registry()` :170 每次加载清空重建。单 World 下安全，但 [06 号票](../../../../.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md) 第 4 点要求「每个题材包独立进程」——若未来一进程跑多 World，这两个全局表会串包。应尽早改为 per-World 属性。

4. **LPC 的 `skill_death_penalty()` 是「每技能 -1 级」（`feature/skill.c:131`），engine 是「按比例扣经验」（`death_flow.py:303-305`）**——两者惩罚力度差异巨大。LPC 的 -1 级对高等级玩家极痛（高等级升级经验是 `(level+1)^2`，:176），engine 的按比例扣经验对高等级相对温和。**商业化时若做「付费保技能等级」，LPC 的 -1 级模式付费空间更大（痛感更强），engine 的按比例模式付费空间更小。** 须在数值平衡阶段定稿惩罚模型。

5. **LPC 地府流程的 `gate.c:36` 销毁所有携带物**——这在 engine 中完全不存在（engine `death_flow.py:_drop_inventory_to_room()` :283 是掉落到房间，不是销毁）。若题材包要做地府内容，销毁机制是重大惩罚，**不得作为付费减免项**（否则等于「付费保装备」= pay-to-win）。

### 6.3 engine 应预留的支撑点清单（MVP 不实现）

| 支撑点 | engine 位置 | 预留方式 | 商业化用途 |
|--------|------------|---------|-----------|
| 双货币 | `components.py:Currency` :650 | 加 `currency_type` 字段 | 死亡惩罚分别扣减 / 商店分货币 |
| 消费账本 | `death_flow.py` / `combat_system.py` 事件点 | 新增 `LedgerEntry` 数据类 | 分成结算依据 |
| 资产归属 | `skills.py:SkillData` :37 / `components.py:ItemTemplateKey` :431 | 加 `pack_id`/`creator_id`/`version` | 分成追溯 |
| 题材包 ID | `World` 层 | 挂载 `world.pack_id` | 埋点维度 |
| 死亡减免 | `death_flow.py:DeathPolicy` :77 | 加 `mitigations` 字段 | 便利性付费承载 |
| Effect handler | 无（新建） | 新建 Effect 注册表带归属 | Effect 作为题材包资产 |
| 装备耐久 | `components.py` 物品组件 | 加 `durability` 字段 | 修理付费 |
| 注册表隔离 | `skills.py:SKILLS` :54 | 改为 `world.skills_registry` | 多 World 隔离 |

> 以上预留均不改变 MVP 交付（单机可玩内核 + UGC 加载契约），只在数据结构层面留位置，待平台层（[post-mvp-backlog](../../../../.scratch/mvp-scope/post-mvp-backlog.md) M5 Web 创作者平台）接入时填充。
