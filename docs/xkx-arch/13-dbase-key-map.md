# LPC dbase key -> ECS 组件字段映射表

> 阶段 1 Wave 1 T3 产出。对应 [04 §三](04-迁移路径与避坑清单.md) 阶段 1 里程碑 M1-3（字段->组件映射表）+ [12](12-阶段1-核心循环实施计划.md) T3。
>
> 创建：2026-07-11
> 前置：[T2 SchemaRegistry](../adr/ADR-0019-schema-registry-and-dsl-validator-boundary.md)（has_field / field_names 校验映射目标）
> 关联：[spec/layer_b_object_base.py](../../engine/src/xkx/spec/layer_b_object_base.py) F_DBASE 路径访问语义 / [08](08-阶段-0-实施计划.md) §四 68771 调用点抽样

## 一、背景

LPC dbase（[feature/dbase.c](../../feature/dbase.c)）是字符串 key 的 mapping，全仓约 **68771 个 query/set 调用点**（[08](08-阶段-0-实施计划.md) §四抽样校准实验）。`query("cobmat_exp")` 拼写错误静默返回 0（[spec/layer_b](_query_spec postcondition)："不存在时返回 0"），bug 难发现。

greenfield 用 ECS 结构化组件替代 dbase，但需保留 LPC key 语义以做行为等价验证 + 兼容 LPC 规格的函数契约。本表枚举 go/move/combat 核心路径键集，映射到 ECS 组件字段；[T2 SchemaRegistry](../adr/ADR-0019-schema-registry-and-dsl-validator-boundary.md).has_field 启动期校验映射目标合法。

## 二、已映射 key（DBASE_KEY_MAP）

`DBASE_KEY_MAP`（[runtime/dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py)）枚举 `components.py` 13 组件承接的 37 个简单 key：

| LPC key | 组件 | 字段 | LPC 来源 |
|---|---|---|---|
| `name` | Identity | name | set_name / query("name") |
| `str` | Attributes | str_ | human.c 属性 |
| `dex` | Attributes | dex_ | human.c 属性 |
| `int` | Attributes | int_ | human.c 属性 |
| `con` | Attributes | con_ | human.c 属性 |
| `age` | Attributes | age | char.c age_update |
| `gender` | Attributes | gender | human.c |
| `family` | Attributes | family | shanmen.c 守卫判断 |
| `family_name` | Attributes | family | 同 family（LPC 同义） |
| `qi` | Vitals | qi | combatd.c 三层资源 |
| `max_qi` | Vitals | max_qi | combatd.c |
| `eff_qi` | Vitals | eff_qi | combatd.c（eff_=有效上限） |
| `jing` | Vitals | jing | combatd.c |
| `max_jing` | Vitals | max_jing | combatd.c |
| `jingli` | Vitals | jingli | combatd.c |
| `max_jingli` | Vitals | max_jingli | combatd.c |
| `neili` | Vitals | neili | combatd.c |
| `max_neili` | Vitals | max_neili | combatd.c |
| `combat_exp` | Progression | combat_exp | ADR-0017 从 Vitals 拆出 |
| `potential` | Progression | potential | ADR-0017 |
| `max_potential` | Progression | max_potential | ADR-0017 |
| `apply_attack` | Skills | apply_attack | combatd.c skill_power |
| `apply_dodge` | Skills | apply_dodge | combatd.c |
| `apply_parry` | Skills | apply_parry | combatd.c |
| `apply_damage` | Skills | apply_damage | combatd.c |
| `apply_armor` | Skills | apply_armor | combatd.c |
| `weapon` | Skills | weapon | combatd.c 武器映射 |
| `attitude` | NpcBehavior | attitude | NPC AI |
| `chat_chance_combat` | NpcBehavior | chat_chance_combat | heart_beat chat |
| `chat_msg_combat` | NpcBehavior | chat_msg_combat | heart_beat chat |
| `inquiry` | NpcBehavior | inquiry | ADR-0006 ask 命令 |
| `exits` | RoomComp | exits | room.c |
| `objects` | RoomComp | objects | room.c NPC 刷新 |
| `short` | RoomComp | short | F_NAME short() |
| `long` | RoomComp | long | F_NAME long() |
| `outdoors` | RoomComp | outdoors | receive_message outdoor 子类 |
| `no_fight` | RoomComp | no_fight | combatd.c fight 检查 |

## 三、路径访问 key（PATH_PREFIX_MAP）

LPC dbase 支持 `"skill/axe"` 路径访问（[spec/layer_b](_set_spec notes)：prop 含 `/` 按分隔符拆路径进入嵌套 mapping）。

| 路径前缀 | 组件 | 字段 | 示例 | 变体 |
|---|---|---|---|---|
| `skill` | Skills | levels | `set("skill/axe", 30)` -> `Skills.levels["axe"]` | 常规 dbase |
| `marks` | Marks | flags | `set_temp("marks/酥", 1)` -> `Marks.flags`（S4 ADR-0006） | temp dbase |

`marks/` 是 temp 变体（`set_temp`/`query_temp`，tmp_dbase 不存档，[spec/layer_b](_set_temp_spec notes)）。路径访问的运行时读写接口由 T4 命令管线 / T6 combat 提供，本表只定映射。

## 四、动态拼接 key

LPC 用 `"eff_" + type` / `"max_" + type` 动态拼接 key（[spec/layer_e_combat.py](../../engine/src/xkx/spec/layer_e_combat.py) `set("eff_" + type, ...)`）。type 维度：

| type | eff_ | max_ |
|---|---|---|
| qi | eff_qi（Vitals.eff_qi） | max_qi（Vitals.max_qi） |
| jing | eff_jing（**后置**，Vitals 无字段） | max_jing（Vitals.max_jing） |
| jingli | eff_jingli（**后置**，Vitals 无字段） | max_jingli（Vitals.max_jingli） |

阶段 1 S1 简化：Vitals 只承接 eff_qi（combat 主资源），eff_jing/eff_jingli 后置 T6 combat 确定性扩展时补（[ADR-0002](../adr/ADR-0002-resolve-attack-extraction.md) 简化台账）。

## 五、后置 key（POSTPONED_KEYS）

以下 key 无对应组件，按"实现到时才补"原则（[08 §七](08-阶段-0-实施计划.md)）后置。POSTPONED_KEYS 集合见 [dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py)。

### 战斗/行为状态（T6 combat 扩展 / NPC AI）

`actions`（招式列表，SkillData）/ `action_flag` / `fight` / `disable_type` / `disabled` / `yield` / `winner` / `victim_name` / `free_rider` / `guarding` / `looking_for_trouble` / `pursuer` / `behavior_exp` / `thief`

战斗记忆（temp）：`last_opponent` / `last_damage_from` / `last_eff_damage_from` / `last_fainted_from` / `my_killer`

### 角色长期状态（阶段 2）

`title`（TitleSystem，[04 §三](04-迁移路径与避坑清单.md) 阶段 2.5）/ `shen`（道德值）/ `race`（human.c，阶段 2.7 门派包）/ `mud_age` / `mud_age_last` / `age_modify` / `month` / `birthday`（时间系统）/ `combat_exp_last` / `death_count` / `death_times`（死亡统计）

### PK/法院系统（阶段 1 法院 / 阶段 2）

`vendetta` / `vendetta_mark` / `pking` / `pktime`（[09](09-灵魂系统盘点.md) 法院系统盘点）

### 频道/消息系统（阶段 2）

`channels` / `chblk_on` / `channel_msg_cnt`（channeld，[ADR-0014](../adr/ADR-0014-daemon-responsibility-redesign.md)）/ `block_msg`（消息遮罩）/ `language`（BIG5 转码）

### 登录/重连（T7 WS 服务器）

`link_ob` / `body_ob` / `body` / `was_userp` / `netdead`（temp）/ `quit`（[spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) netdead 状态机）

### 对象/房间扩展

`startroom`（NPC 初始房间）/ `no_clean_up`（对象回收，[spec/layer_b](_clean_up_spec)）/ `no_death`（房间死亡限制）/ `cost`（go 精力消耗）/ `item_desc`（房间物品描述，路径）/ `id`（F_NAME my_id）/ `equipped`（装备系统，阶段 2）/ `env`（wiz 环境变量，路径）/ `apply`（apply 掩码，路径）/ `balance` / `pending`（打坐/吐纳状态，temp）

## 六、衔接关系

- **T2**（[ADR-0019](../adr/ADR-0019-schema-registry-and-dsl-validator-boundary.md)）：`validate_dbase_map(schema)` 启动期校验 `DBASE_KEY_MAP` + `PATH_PREFIX_MAP` 映射目标字段存在（`has_field`）；`build_world` 调用，问题非空 raise `SchemaError`。
- **T4**（命令 8 段管线）：命令执行中读写 dbase key 经 `resolve_dbase_key` 解析到组件字段。
- **T6**（combat 确定性）：combat 路径的 dbase key 读写（qi/eff_qi/combat_exp 等）经映射表定位组件字段。
- **T7**（WS 服务器）：登录/重连相关后置 key（link_ob/netdead 等）实现时补映射。
- **DSL SchemaValidator**（[ADR-0008](../adr/ADR-0008-schema-validator-four-checks.md)）：DSL IR 侧未知字段由 SchemaValidator 捕获，runtime 侧字段映射由本表 + SchemaRegistry 共防拼写错误。

## 七、验收（[12](12-阶段1-核心循环实施计划.md) T3）

- [x] 68771 调用点的核心键集（go/move/combat 路径）枚举完成：37 已映射 + 2 路径前缀 + 55 后置
- [x] 映射表覆盖 9 层规格涉及的 dbase 键：spec 82 key 全部归类（已映射/路径/后置）
- [x] 映射目标启动期校验（T2 has_field 衔接）：`validate_dbase_map` + `build_world`

## 不做（范围边界）

- **不扫全量 68771 调用点**：T3 聚焦核心键集（go/move/combat）+ 9 层规格涉及键。全量扫描后置任务 6 抽样校准实验（[08 §四](08-阶段-0-实施计划.md)）。
- **不实现运行时 query 接口**：本表只定映射，运行时读写接口由 T4/T6 提供。
- **不补后置 key 映射**：按"实现到时才补"原则，对应子系统实现时补 DBASE_KEY_MAP 条目。

*最后更新：2026-07-11*
