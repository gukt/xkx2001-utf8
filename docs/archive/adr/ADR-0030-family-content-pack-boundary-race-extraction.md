# ADR-0030：门派内容包边界切割 + race 层剥离

- 状态：已采纳（2026-07-12 用户评审通过，三个开放问题按倾向裁决）
- 日期：2026-07-12
- 阶段：2 Wave 4 2.7（阶段 2 收官硬门禁）
- 关联 dissent：[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 1（CombatKernel 主题无关性延伸）/ dissent 5（themed 治理，门派内容是题材包资产非治理逻辑）/ dissent 10（平台特性范围过载，只切割不全量迁移）

## 背景

[04](../xkx-arch/04-迁移路径与避坑清单.md) §五检查点 8 / kill criteria 2 要求：**门派内容包边界干净切割（核心引擎无武侠烙印残留）**。2.7 是阶段 2 收官硬门禁，依赖 2.4 CombatKernel 主题无关性（已完成）+ 2.3 Attribute（已完成）。

三个主题无关性先例已建立，本 ADR 把同一模式扩展到 race 层 + 门派加成 + 房间路径，完成阶段 2 主题无关性收官：

- **[ADR-0003](ADR-0003-combatkernel-theme-neutrality.md)**（S2）：武器->技能映射从内核推断改为题材数据声明（`attack_skill`/`weapon_label` 外提）+ `inspect.getsource` 源码级硬门禁（resolve_attack 不含 `"sword"`/`"blade"` 字面量）。
- **[ADR-0028](ADR-0028-rank-d-spec-and-pronoun-context.md) 决策 6**：class 分支表数据从题材包加载，核心引擎 `rank_service` 不硬编码 `"bonze"`/`"taoist"` 等武侠字面量，只提供查表框架（`CLASS_TITLE_TABLE` 由题材包注册填充），测试用注入的非武侠表。
- **[ADR-0029](ADR-0029-world-governance-system.md) 开放问题 3**：阴间位置用 room_id 字符串常量（`"death/gate"`），房间系统实现后映射到实际房间实体。

## 问题：核心引擎残留武侠烙印

### 1. human.c race 层混合（[adm/daemons/race/human.c](../../adm/daemons/race/human.c)）

`setup_human()` 把通用人类种族逻辑与 13 门派加成混在一个函数（429 行）：

- **通用（主题无关）**：属性随机 `10+random(21)`、年龄分层 `max_jing`/`max_qi`/`max_jingli` 公式（age<=14/<=30/>30 三段 + 70 岁衰减）、`max_potential` 公式、`base_weight` + str 加成、limbs 部位列表、`combat_action` 徒手招式、dead/unconcious/revive 消息。
- **门派加成（武侠烙印，需剥离）**：武当/全真道家保精保气（taoism）、少林/峨嵋/大理/雪山/血刀佛家养精保气（buddhism/mahayana/lamaism）、丐帮地刹炼魂+天魔解体（death_times+huntian-qigong）、华山紫氤吟+正气诀（ziyin-yin/zhengqi-jue/zixia-gong）、桃花五音十二律+奇门遁甲（music/qimen-dunjia/bitao-xuangong）、古墓玉女二十四诀+心经（yunu-jue/yunu-xinjing）、灵鹫八荒功（bahuang-gong）、星宿/白驼聚毒练气（poison/huagong-dafa/hamagong）、明教光明心法（guangming-xinfa/shenghuo-xuanming）。

### 2. 核心引擎残留武侠房间路径

- [governance.py](../../engine/src/xkx/runtime/governance.py) `JAIL_ROOMS`：`bonze_jail -> "shaolin/guangchang1"`、`dali_jail -> "dali/taihejie5"`（ADR-0029 §5 监狱表，当时作为运行时常量）。
- [cli.py](../../engine/src/xkx/cli.py) `START_ROOM = "xueshan/shanmen"`（S5a 试玩起始房间）。
- [death.py](../../engine/src/xkx/runtime/death.py) `DEATH_ROOM = "death/gate"`（ADR-0029 开放问题 3，`death` 通用但路径格式题材特定）。

### 3. kungfu/class 19 门派脚本

[kungfu/class/](../../kungfu/class/) 19 门派（baituo/dali/emei/gaibang/gumu/huashan/lingjiu/mingjiao/misc/murong/quanzhen/shaolin/shenlong/taohua/wudang/xingxiu/xixia/xuedao/xueshan）的 NPC/武学/招式是题材内容。2.7 只切割边界，不迁移全量（后置 M3）。

### 4. dbase key 兼容层（保真让步，非引擎语义）

[dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py) 的 `"dali/rank"` 前缀分发 + [components.py](../../engine/src/xkx/runtime/components.py) `TitleComp.dali_rank` 字段名含 "dali"。这是 LPC dbase key 兼容保真让步（LPC 规格源用 `"dali/rank"` key，greenfield 必须支持），类比 [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) `qi`/`jing`/`jingli`/`neili` 拼音保留。非引擎语义硬编码，硬门禁需豁免。

## 决策

### 决策 1：RaceProfile + FamilyBonus 声明式载体（race 层切割）

类比 [ADR-0028](ADR-0028-rank-d-spec-and-pronoun-context.md) 决策 6 class 分支表注入 + [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) 武器映射外提，把 `setup_human` 拆为"通用种族基础（引擎层）"+"门派加成（题材包 CPK 资产）"两层。

**RaceProfile**（引擎层数据声明接口，题材包注入）：

| 字段 | 类型 | 对照 LPC |
|---|---|---|
| `limbs` | `list[str]` | human.c `set("limbs", ...)` |
| `combat_actions` | `list[CombatAction]` | human.c `combat_action` 数组（action + damage_type） |
| `dead_message` / `unconcious_message` / `revive_message` | `str` | human.c `set("dead_message", ...)` 等 |
| `base_weight` / `str_weight_factor` | `int` | human.c `BASE_WEIGHT=40000` + `(str-10)*2000` |
| `attr_min` / `attr_max` | `int` | human.c `10 + random(21)`（min=10, max=30） |

**`setup_race(entity, profile)`** 纯函数（引擎层，`runtime/race.py` 新建）：
- 年龄分层 `max_jing`/`max_qi`/`max_jingli` 公式（读 profile 参数，公式参数化：`age_threshold_young=14`/`age_threshold_prime=30`/`age_senior=70` 等）
- 70 岁衰减
- `max_potential` / `max_encumbrance` 公式
- **不硬编码任何门派名 / 技能名**；公式参数从 profile 读取

**FamilyBonus**（题材包 CPK 资产，声明式载体，`runtime/family.py` 新建）：

| 字段 | 类型 | 对照 LPC human.c |
|---|---|---|
| `family_name` | `str` | `my["family"]["family_name"] == "武当派"` |
| `target` | `Literal["max_jing", "max_qi"]` | 加成目标 |
| `condition_skill` | `str` | `ob->query_skill("taoism", 1)` |
| `condition_threshold` | `int` | `> 39` |
| `age_adjusted` | `bool` | 30 岁前补/30 岁后长逻辑（`xism_age = skill/2; if(age<=30) -=age; else -=30`） |
| `bonus_skill` | `str` | `ob->query_skill("force")` / `"zixia-gong"` 等 |
| `divisor` | `int` | `*(skill1/10)` 的除数 |
| `extra_condition_key` / `extra_condition_threshold` | `str \| None` / `int \| None` | 华山 `huashan/yin-jue > 1` 等额外条件（可选） |
| `extra_divisor` | `int \| None` | 额外条件满足时的除数（如华山 `/10` vs `/15`） |

**`apply_family_bonuses(entity, family_name, bonuses)`** 分发函数（引擎层）：
- 按 `family_name` 过滤匹配的 FamilyBonus 列表
- 条件检查（技能等级 > 阈值 + 额外条件）
- 公式计算（读 bonus 参数，年龄调整统一逻辑）
- **不认识任何具体门派名**，只做 `family_name == bonus.family_name` 字符串匹配

题材包（武侠 CPK）注入 13 条 FamilyBonus + 人类 RaceProfile。测试用非武侠 RaceProfile + FamilyBonus（如大航海"海盗帮派"航行加成 max_qi、书院"学派"学问加成 max_jing）。

> **特殊门派处理**：丐帮 `death_times` 加成（地刹炼魂/天魔解体）和明教双技能公式不完全 fit 通用 FamilyBonus 载体。倾向：2.7 只定义载体接口 + 1-2 标准门派验证（xueshan + 非武侠），丐帮/明教等特殊加成作为开放问题（见下），全量覆盖后置 M3。

### 决策 2：ThemeConfig 房间路径外提

类比 [ADR-0029](ADR-0029-world-governance-system.md) 开放问题 3 房间路径常量，把引擎层硬编码的房间路径外提为题材包注入。

**ThemeConfig**（引擎层接口，`runtime/theme.py` 新建）：

| 字段 | 类型 | 对照当前硬编码 |
|---|---|---|
| `start_room` | `str` | cli.py `START_ROOM = "xueshan/shanmen"` |
| `death_room` | `str` | death.py `DEATH_ROOM = "death/gate"` |
| `revive_room` | `str` | 还阳房间（LPC REVIVE_ROOM 宏，后置实现） |
| `jail_rooms` | `dict[str, str]` | governance.py `JAIL_ROOMS`（city_jail/dali_jail/bonze_jail -> 释放房间） |

注入方式：`build_world(..., theme_config: ThemeConfig | None = None)`（类比 `storage_backend` 可选参数注入模式，[world.py:51-64](../../engine/src/xkx/runtime/world.py#L51-L64)）。`theme_config=None` 时用 `ThemeConfig.default()`（测试用非武侠路径），生产路径由题材包注入武侠路径。

`governance.py` / `death.py` / `cli.py` 改读 `world.theme_config` 而非模块级常量。

### 决策 3：dbase key 兼容层保真让步豁免

[dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py) 的 `"dali/rank"` 等 LPC dbase key 字面量 + [components.py](../../engine/src/xkx/runtime/components.py) `TitleComp.dali_rank` 字段名是 LPC dbase key 兼容保真让步，类比 [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) `qi`/`jing`/`jingli`/`neili` 拼音保留。

**test_theme_neutrality 硬门禁豁免边界**：
- 豁免 `dbase_map.py` 的 dbase key 字面量（`"dali/rank"` 等 LPC key 字符串，保真让步）
- 豁免 `components.py` 的 `TitleComp.dali_rank` / `family_rank` 字段名（LPC dbase key 派生命名，字段本身是通用 `int`）
- **不豁免**引擎语义代码（`governance.py` / `death.py` / `cli.py` / `race.py` / `family.py` 等）中的门派名 / 武侠房间路径

> 替代方案（否决）：把 `dali_rank` 重命名为通用 `faction_rank`。代价：偏离 [ADR-0028](ADR-0028-rank-d-spec-and-pronoun-context.md) 决策 5 已定字段名 + dbase_map 映射全改，违反收敛优先于完备。保真让步豁免更收敛。

### 决策 4：test_theme_neutrality 扩展（收官硬门禁）

扩展扫描范围 + 黑名单，把 [04](../xkx-arch/04-迁移路径与避坑清单.md) §五检查点 8 "核心引擎无武侠烙印"落为可回归断言：

**扫描范围**（当前仅 `combat/`，扩展到全引擎语义代码）：
- `combat/`（现有，ADR-0003/0027 覆盖）
- `runtime/`（除 `dbase_map.py` dbase key 兼容层豁免 + `components.py` TitleComp 字段名豁免）
- `dsl/`（DSL 层不应有武侠字面量）

**黑名单**（当前仅 sword/blade/阵法/合击/anubis，扩展）：
- 武器：`sword` / `blade`（现有）
- 门派名：`武当` / `少林` / `峨嵋` / `华山` / `丐帮` / `桃花` / `古墓` / `灵鹫` / `星宿` / `白驼` / `明教` / `雪山派` / `血刀` / `大理段` / `全真`
- 武侠房间路径：`shaolin/` / `dali/` / `xueshan/` / `huashan/` / `wudang/` / `emei/`（作为路径前缀字面量）

**非武侠微场景验证**（race/family 边界）：
- 大航海"海盗帮派"FamilyBonus（航行加成 max_qi）+ 书院"学派"RaceProfile（学问加成 max_jing）
- 断言 `setup_race` + `apply_family_bonuses` 走题材声明数据，不 fallback 到武侠默认

### 决策 5：1-2 门派验证

- **xueshan 微场景**（S2-S4f 已有）：补 RaceProfile + FamilyBonus 数据（雪山派 lamaism 养精保气），验证武侠题材包注入路径
- **非武侠微场景**（1 个）：大航海"海盗帮派"或书院"学派"，验证 FamilyBonus 边界主题无关性（非武侠 family_name + 非武侠技能条件 + 非武侠加成公式）

### 决策 6：kungfu/class 边界切割不全量迁移

- 19 门派脚本是题材内容，2.7 只定义 CPK 资产边界（FamilyBonus + SkillData + FormationData 载体接口）
- 全量迁移后置 M3（[04](../xkx-arch/04-迁移路径与避坑清单.md) §三 M3 官方 StdLib CPK）
- [ADR-0027](ADR-0027-combat-callout-formation-golden-trace.md) CombatModifier 接口已就绪，2.7 验证阵法数据 CPK 边界（pozhen/buzhen/heji 是题材包武学脚本，不进内核）

## 开放问题（已裁决，2026-07-12）

1. **setup_human 规格提取**：layer_h_daemons.py 有 CHAR_D `setup_char` 规格（行 1161，种族分派 Postcondition），但 `setup_human` 无独立 FunctionSpec。按 [08](../xkx-arch/08-阶段-0-实施计划.md) §七"实现到时才补"原则，2.7 补 `setup_human` 函数级规格（前置/后置/不变量）还是直接按 human.c 源码实现？**裁决**：补最小规格（setup_race + apply_family_bonuses 的契约），不穷尽 13 门派公式规格。

2. **丐帮/明教特殊加成**：丐帮 `death_times` 加成（地刹炼魂/天魔解体）和明教双技能公式不完全 fit 通用 FamilyBonus 载体。**裁决**：2.7 只定义标准 FamilyBonus 载体 + 1-2 标准门派验证，特殊加成作为"扩展点"标注（`extra_condition_key` 尽量覆盖，覆盖不了的后置 M3），不为此过度泛化载体。

3. **RaceProfile 是否支持非人类种族**：LPC 有 MONSTER_RACE/BEAST_RACE 等（[layer_h](../../engine/src/xkx/spec/layer_h_daemons.py) setup_char 种族分派）。**裁决**：2.7 只做人类 RaceProfile（M3 单题材武侠只需人类），非人类种族后置 M3（怪物 NPC 用 NpcDef 直接声明属性，不走 race daemon）。

## 不做（范围边界）

- `kungfu/` + `d/` 全量内容迁移（后置 M3，[04](../xkx-arch/04-迁移路径与避坑清单.md) §三 M3）
- 门派系统完整逻辑（拜师/出师/门派任务/门派 NPC AI，后置 M3）
- 19 门派全量 FamilyBonus 数据填充（2.7 只填 1-2 门派验证边界，全量后置 M3）
- 多题材运行时热插拔（后置 M3，[04](../xkx-arch/04-迁移路径与避坑清单.md) §六不做清单）
- `TitleComp.dali_rank` 重命名为通用字段（保真让步，决策 3 豁免）
- `qi`/`jing`/`jingli`/`neili` 重命名（[ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) 已定保真让步）
- 非人类种族 RaceProfile（开放问题 3，后置 M3）
- `setup_human` 13 门派公式穷尽规格提取（开放问题 1，只补最小契约）

## kill criteria

- **切割不干净**（核心引擎残留武侠语义，test_theme_neutrality 扩展后不通过）-> 暂停，先做主题无关性重构（[04](../xkx-arch/04-迁移路径与避坑清单.md) §五检查点 8 / kill criteria 2）

## 验收标准（对应 04 §八阶段 2->M3 决策检查点"门派内容包边界干净切割"）

- [ ] `test_theme_neutrality` 扩展全通过（扫描范围 combat/+runtime/+dsl/，黑名单含门派名+武侠房间路径，dbase key 兼容层豁免）
- [ ] 核心引擎源码无 sword/blade/门派名/武侠房间路径字面量（豁免 dbase_map.py dbase key 兼容 + components.py TitleComp 字段名）
- [ ] 非武侠微场景可跑（race/family 边界：大航海或书院 FamilyBonus 走题材声明数据）
- [ ] 1-2 门派验证（xueshan + 非武侠）
- [ ] RaceProfile + FamilyBonus + ThemeConfig 载体可序列化（[ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)）
- [ ] test_load_test CI 门禁不退化（tick p99 < 100ms）
- [ ] 全量 tests 绿 + ruff 全过

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 1（CombatKernel 主题无关性延伸：race 层 + 门派加成是 combat 之外的主题无关性收官）
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 5（themed 治理平台级 fail-closed，门派内容是题材包资产非治理逻辑）
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 10（平台特性范围过载，2.7 只切割边界不全量迁移）
- [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md)（S2 主题无关性先例：映射外提 + 源码硬门禁 + qi/jing 保真让步）
- [ADR-0027](ADR-0027-combat-callout-formation-golden-trace.md)（CombatModifier 接口，阵法数据 CPK 边界）
- [ADR-0028](ADR-0028-rank-d-spec-and-pronoun-context.md) 决策 6（class 分支表注入先例：查表框架 + 题材包数据 + 测试用非武侠表）
- [ADR-0029](ADR-0029-world-governance-system.md) 开放问题 3（房间路径常量先例）+ §5 监狱表
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §五检查点 8 / kill criteria 2（门派切割硬门禁）
- [15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.7（实施计划）
