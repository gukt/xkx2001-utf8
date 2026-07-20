> 本文是 2026-07-19 M1 扩展调研的**原始 subagent 输出**（物品系统调研员），完整保留，未做二次精简。汇总与 scope 决策见 [../research-m1-extension-items-npc-nature.md](../research-m1-extension-items-npc-nature.md)。
>
> 立场：LPC 是设计灵感与术语参考，不是规格源（ADR-0001）。下文每条标出处，最后给出"题材无关引擎地基 / 武侠题材内容 / 过时机制"的三档判断与 M1 scope 建议。

---

# 侠客行 LPC 物品系统调研 -- 为新引擎 M1 物品打磨提供决策输入

## 1. 物品系统全景（核心设计思想）

LPC 物品系统是 **"基类骨架（inherit/）+ 特性混入（feature/）+ 原型克隆（clone_object）"** 三层组合，全部状态走统一 `dbase` 映射（`set/query`），能力维度 = 是否混入对应 feature + 是否设置对应 key。三层各自职责清晰：

- **inherit/ 基类只声明混入哪些 feature，几乎不含业务逻辑**（`item.c` 仅 17 行）。
- **能力真正实现在 feature/**：移动负重 `F_MOVE`、命名 `F_NAME`、装备 `F_EQUIP`、食物 `F_FOOD`、液体 `F_LIQUID`、丹药 `F_PILL`、唯一性 `F_UNIQUE`、商人 `F_DEALER` 等。
- **所有"可持有物品的对象"（房间 / 角色 / 容器物品）共用同一套 `move()` + `add_encumbrance()` 接口**，命令层只做参数解析与业务校验，最终都落到 `obj->move(dest)` 一个入口。这是最值得借鉴的核心思想：**转移是统一原语，容器/玩家/房间只是"同一能力的不同实例"**。

新引擎的 ECS 已经走这条路（`Container` 组件 = 通用"持有 entity id 集合"，房间地面与玩家物品栏同构），方向正确。

---

## 2. 核心功能点清单（按 10 个维度）

### 维度 1：物品继承体系与通用能力

- **出处**：`inherit/item/item.c`（ITEM 基类，混入 F_CLEAN_UP/F_DBASE/F_MOVE/F_NAME/F_CLONEABLE）、`inherit/item/combined.c`（堆叠）、`inherit/item/money.c`（金钱薄壳）、`inherit/misc/equip.c`（EQUIP = ITEM+F_EQUIP，武器防具共同祖先）、各 `feature/*.c`。
- **关键机制**：ITEM 是最薄基类；COMBINED_ITEM 加 `amount` 字段 + move 自动合并；MONEY 继承 COMBINED_ITEM，`value()` = `amount * base_value`。能力维度全靠 feature 混入。
- **抽象出的"物品通用能力维度"**（每条标实现位置）：

| 能力维度 | 实现 | 关键字段/标志 |
|---|---|---|
| 可命名/可识别 | F_NAME | `name`/`id`/`my_id`，支持多 id |
| 可移动/有重量/有负重 | F_MOVE | `weight`/`encumb`/`max_encumb`，递归传递 |
| 可存储属性 | F_DBASE | 路径式 `set/query` + temp 层 + `default_ob` 原型共享 |
| 可克隆/原型共享 | F_CLONEABLE | 蓝图设属性，克隆回退蓝图省内存 |
| 可堆叠 | combined.c | `amount`+`base_weight/unit/value`，move 自动合并 |
| 有价值/可交易 | dbase `value` + F_FINANCE | `set("value",N)`；`no_sell/no_drop/no_get` 控流转 |
| 可装备 | F_EQUIP | `weapon_prop/armor_prop` 叠入 `apply` 临时层 |
| 可造成/承受装备特效 | `hit_ob/hit_by/hit_weapon` 回调 | 剑破衣、毒衣、重器震断武器 |
| 可消耗（饮食/吃药） | F_FOOD/F_LIQUID/F_PILL | `food_remaining` 按口扣减 |
| 可持久化/可自动加载 | F_SAVE + `query_autoload/autoload` | 玩家重登恢复 |
| 唯一性 | F_UNIQUE | `violate_unique()` 全局克隆数检查 + `create_replica` 替代品 |
| 多部件 | F_MULTI | `components` 映射 |

- **对新引擎设计启发**：LPC 的"feature 混入"= ECS 的"组件挂载"，能力维度正交。新引擎应显式列出这些能力维度作为可选组件（Stackable/Valuable/Equippable/Consumable/Unique 等），按需挂载，而不是用一个大而全的 Item 组件。**F_UNIQUE 不是 `set("unique")` 字段而是混入 feature**，这点对设计唯一性机制有启发：唯一性是行为（spawn 时检查全局实例数）而非标志。

### 维度 2：物品命令全量

- **出处**：`cmds/std/`（get/drop/put/give/eat/wield/wear/unwield/remove/throw/steal/look/open/close/feed）、`cmds/usr/inventory.c`、商店命令靠 NPC/Room `add_action` 局部注册（无全局 sell/buy/value.c）。
- **关键机制（逐个）**：
  - **get/take**（合并，无独立 take）：`get <物> [from <容器>]`、`get <数量> <物>`、`get all`。从活物身上 get 需权限；战斗中只能拿一个。
  - **drop**：`drop <物>`/`drop <数量>`/`drop all`；不值钱物品丢弃自动销毁。
  - **put**（放进容器）：`put <物> in <容器>`；目标须 `is_container()` 或可骑乘；容器可 `reject(obj)` 拒绝。
  - **give**：`give <物> to <人>`；NPC 须 `accept_object(me,obj)` 返回 1 才接受（quest trigger 入口）；给 NPC 有 value 物品而 NPC 不接受时物品被 destruct（NPC"吞掉"）。
  - **eat/chi**（中文别名）：调 `obj->feed_ob(me)`；`food_remaining` 按口递减，吃完 destruct，首口 value 置 0。
  - **wield/wear**：调 `ob->wield()/wear()`；防具按 `armor_type` 互斥（11 槽），武器主/副手+盾占用模型。
  - **unwield/remove**：共用 `unequip()`，减法还原 apply 临时属性。
  - **throw**：暗器走 `throw_ob`，普通走 `do_throw`；可嵌入身体（embed）。
  - **steal**：`steal <物> from <人>`，3 秒延迟、技能成长、PK 关系。
  - **sell/buy/list/value**：**靠 NPC/Room 局部 add_action 注册，非全局命令**；两套实现（F_DEALER 挂 NPC、hockshop 挂 Room）。
  - **look <物>**：只展示 `obj->long()` + 容器内容，**不主动展示数值面板**（weight/value/状态需 value 命令估价）。
  - **inventory**：展示直接持有物一层（不递归 deep_inventory），前缀标记 `□` 装备 / `√` 嵌入 / 空格携带，并显示负重百分比。
- **对新引擎设计启发**：LPC 命令"薄壳委托对象方法"= 新引擎命令调 handler、handler 操作组件，边界一致。但 LPC 的"商店命令靠 NPC 局部 add_action"是个**过时机制**（命令存在性依赖玩家在场且 NPC init 过），新引擎应把买卖统一为全局命令 + 资格校验（"你附近有商人吗"），而非命令注册依赖。look 不展示数值面板是题材风格选择，新引擎可保留"look 看描述、单独命令看数值"的分层。

### 维度 3：转移机制

- **出处**：`feature/move.c`（F_MOVE 核心）、`inherit/item/combined.c`（堆叠 move 重写）、`cmds/std/{get,drop,put}.c`。
- **关键机制**：`move(dest, silently)` 统一入口，流程：①若 equipped 先 unequip（失败则拒转移）->②解析 dest（对象或字符串，字符串触发加载）->③超重校验->④旧环境 `add_encumbrance(-weight)`、新环境 `add_encumbrance(+weight)`、驱动 `move_object` 搬迁->⑤转移后自检（防析构/被移走）->⑥玩家被移动自动 look。
- **钩子**：F_MOVE 层只有**超重**一个硬校验点；容器级拒绝靠鸭子类型 `is_container()` + `reject(obj)`（由 put 命令主动调，非 move 内部）；`over_encumbrance()` 仅提示不阻断；`unequip()` 装备卸下钩子；`move_or_destruct` 容器销毁时内物品迁移到 VOID_OB 兜底。
- **转移失败条件**：超重 / 目标不可达 / 装备卸不下 / 转移后被析构 / 容器 reject / 非容器目标 / `no_get` / `no_drop` / 活物限制 / busy 或战斗。
- **关键细节**：**环境链上溯超重豁免**--从自己背的包里往外拿东西不卡超重（因为玩家能背动包，假定包里的也能背），只有 dest 不在祖先链时才校验超重。`feature/move.c:74-82`。
- **对新引擎设计启发**：转移统一原语 + 超重校验 + 转移前后校验钩子这套设计可直接借鉴。**环境链豁免是个有价值的人性化设计**，新引擎若做容器嵌套应保留。容器拒绝用 `reject(obj)` 钩子（鸭子类型）= 新引擎的"可放物校验回调"，比硬编码规则灵活。

### 维度 4：容量与重量

- **出处**：`feature/move.c`（weight/encumb/max_encumb 三静态变量）、`adm/daemons/chard.c:109-111`（角色负重上限公式）、`inherit/room/room.c:17`（房间上限 10^11 实际无限）、容器 `set_max_encumbrance(N)`。
- **关键机制**：`weight()` = 自重 + 负重（容器递归）；`add_encumbrance(w)` 递归向上 `environment()->add_encumbrance(w)` 让重量沿环境链上传；堆叠物品总重 = `amount × base_weight` 动态重算。角色负重上限公式 `str*5000 + (query_str - str)*1000`（基础膂力贡献是加成的 5 倍）。超重**不阻断**已发生的转移，只提示；inventory 显示百分比。**未发现"超重则不能走/不能打"的硬规则**--负重主要影响"还能拿多少"。
- **对新引擎设计启发**：负重系统是**半题材相关**--重量数值与负重上限公式是武侠数值（str 贡献），但"物品有重量、容器有容量上限、超重提示"是通用引擎地基。建议 M1 只做"物品有 weight 字段 + 容器有 max_capacity + 超限拒绝放入"，角色负重上限公式推迟到 M2（属战斗/属性系统）。

### 维度 5：买卖

- **出处**：`feature/dealer.c`（F_DEALER，挂 NPC）、`inherit/room/hockshop.c`（当铺，挂 Room）、`feature/vendor.c`（基础版，只买不卖）。
- **关键机制**：两套并存实现，命令靠 `add_action` 局部注册（玩家须在场）。定价以物品 `value` 为基准（铜钱数）：商人收购 7 折、卖出 1.2 倍（堆叠 1.0 倍）；当铺典当 6 折、卖断 8 折。货币走 `MONEY_D->player_pay`（三态：0 不够 / 2 银票找不开 / 默认成功）。库存用 `quantity` 字段，缺货有判定；不收物品类（no_drop/no_sell/剩菜/少林庙产/暗器/value 过高或过低）；买断上限（>10 件或 >1000000 文拒大宗）。**无真正回购**：商人卖货进库存流转，当铺典当后直接 destruct。
- **对新引擎设计启发**：买卖是**题材内容+经济系统**，非引擎地基。但"商店 NPC 作为一种带商品清单+定价规则+货币支付的实体"是可抽象的引擎能力。M1 不做买卖（属 M2+ 经济系统），但应预留：物品有 `value` 字段、货币是独立抽象（见维度 10）、买卖命令是全局命令 + "附近有 vendor"校验。LPC 的两套并存实现是历史包袱，新引擎应统一一套。

### 维度 6：给与

- **出处**：`cmds/std/give.c`、典型 quest NPC `d/city/npc/dingdian.c`（丁典 accept_object）。
- **关键机制**：`give <物> to <人>`。前置 busy/战斗/目标 living/不能给自己/目标 `no_accept` 拒收。核心：NPC 须 `accept_object(me,obj)` 返回 1 才接受--**这是 quest trigger 主入口**（丁典收绿菊花回赠《神照经》、铁匠收钱给铁链）。给 NPC 有 value 物品而 NPC 不接受时物品被 destruct（"吞掉"）。无自动拾取（那是 get 的职责）。
- **对新引擎设计启发**：give 命令本身很简单（转移物品到对方容器），**关键设计点是 `accept_object` 钩子作为 NPC 行为层入口**。新引擎应把"接受/拒绝/触发任务"做成 NPC 侧的可挂载钩子（受限 Python），give 命令只负责转移+调钩子。这是典型的"命令薄壳 + 行为在 NPC 层"边界。

### 维度 7：物品唯一性

- **出处**：`feature/unique.c`（F_UNIQUE）、`inherit/room/room.c`（reset 唯一化）、各命令的 `no_*` 标志。
- **关键机制**：
  - **F_UNIQUE feature**：`violate_unique()` 在 create 时检查同 `base_name` 克隆数 >1 即自毁；`create_replica()` 生成 `replica_ob` 替代品；`is_unique()` 标志。**唯一性是行为（spawn 时检查）而非字段标志**。
  - **标志位**（实测 grep）：`no_get`（禁拾取）、`no_drop`（禁丢弃/给出/放入/投掷，**支持字符串自定义提示**）、`no_put`（禁放入容器）、`no_steal`（禁偷）、`no_refresh`（防 reset 销毁/重生=一次性物品）、`no_clean_up`（防 driver 回收）、`money_id`（金钱标识）、`embedded`（嵌入物，combined move 跳过合并）。
  - **门派 NPC 唯一化**：靠 `children()+clonep()` 计数 + `npc_clean_up()` 强制单一实例，非标志位。
  - **未 grep 到独立的 `noremove/noinvis` 标志实现**（任务提及，当前命令集未命中对应检查）。
- **对新引擎设计启发**：唯一性机制分两层：①spawn 层（全局实例数检查）②流转层（`no_get/no_drop` 标志控制能否拾取/丢弃）。新引擎 M1 应先做流转层标志（`no_get/no_drop`，题材无关的引擎地基），spawn 层唯一检查推迟（需 reset/spawn 机制先就位，属 M2+）。**`no_drop` 支持字符串自定义提示**是个好设计，值得保留（quest 物品"这是师门之物，不能丢弃"）。

### 维度 8：spawn 机制

- **出处**：`inherit/room/room.c`（reset/make_inventory/setup）、`config.xkx`（reset 周期 1800s、clean_up 180s）、`feature/clean_up.c`。
- **关键机制**：
  - **clone_object/new**：从蓝图克隆独立实例。
  - **场景加载即生成**：房间 `create()` 只 `set("objects", ([file:数量]))` 声明清单；`setup()` 末尾调 `reset()` 首次生成。
  - **reset 定期重生**：driver 每 1800s 对加载房间调 `reset()`，补齐缺失 NPC/物品、召回 wander NPC。
  - **一次性 vs 可再生**：默认可再生；物品 `set("no_refresh",1)` 既防销毁也防重生（一次性）。
  - **声明清单外物品**：reset 会 destruct 非清单非角色非 no_refresh 的克隆物品（玩家临时丢弃物会被定期清）。
- **对新引擎设计启发**：spawn/reset 是**核心引擎地基**，M1 必做最小版（场景加载时生成 items/npc，已有 placed_in 机制即此雏形）。但"定期 reset 补齐缺失"涉及心跳/调度/对象生命周期，复杂度高，**M1 可只做"加载时 spawn"，定期 reset 推迟 M2+**。`no_refresh` 标志（一次性）应在 M1 物品标志位里预留位置。

### 维度 9：装备系统

- **出处**：`feature/equip.c`（F_EQUIP 真实现）、`inherit/misc/equip.c`（EQUIP 基类）、`include/armor.h`（11 槽位 TYPE_）、`include/weapon.h`（flag 位掩码）、`inherit/weapon/sword.c`（hit_ob 磨损）。
- **关键机制**：
  - **slot 体系**：防具按 `armor_type` 字符串键互斥（head/neck/cloth/armor/surcoat/waist/wrists/shield/finger/hands/boots 共 11 槽），同类不能同时穿；武器主/副手 + 盾占用模型，flag 位（TWO_HANDED/SECONDARY/EDGED...）控制使用方式。**没有结构化 slot 列表，是字符串键 + 双手占用模型**。
  - **装备效果施加**：`armor_prop`/`weapon_prop` 整体叠入 `owner->set_temp("apply",...)` 临时层（已存在则 +=）；卸下用**减法还原**（`applied_prop[key] -= prop[key]`），非 remove。武器额外 `reset_action()` 重算战斗动作。
  - **耐久/磨损**：剑击中穿 cloth 目标概率扣 `armor_prop/armor`，分阶段改 `long`/`name`（加"破"前缀）/`value`（归零或减半）--**直接 mutate 物品自身，非独立耐久字段**。
  - **卸下副作用**：清 temp 槽 + 减 prop + 重算战斗动作；独孤九剑卸剑清 dodge 映射（题材特化）。
- **对新引擎设计启发**：装备系统**大部分属战斗/武侠题材**，但"装备效果用临时属性层施加、卸下用减法还原"是**极佳的引擎地基设计**（可逆效果施加，天然适配 ECS：装备时挂 EffectComponent，卸下时移除）。slot 体系建议 M1 只抽象为"每类装备占一个槽位、同类互斥"的通用机制，具体槽位定义（头/身/手...）是题材内容。M1 不做装备（属 M2 战斗系统），但应在物品能力维度里预留 `Equippable` 组件位置。

### 维度 10：金钱系统

- **出处**：`adm/daemons/moneyd.c`、`inherit/item/money.c`、`clone/money/{coin,silver,gold,thousand-cash}.c`、`feature/finance.c`。
- **关键机制**：
  - **四种货币**：铜 coin（1 文）/ 银 silver（100 文）/ 金 gold（10000 文）/ 千两银票 thousand-cash（100000 文），均继承 MONEY（=COMBINED_ITEM 薄壳）。
  - **换算**：1 金=10000 文=100 银，1 银票=10 金=1000 银。靠各 `base_value` 比例推导。
  - **金钱是特殊物品**：玩家持有 = 身上带若干 money 克隆对象，`amount` 字段表示堆叠数；COMBINED_ITEM.move 自动合并同蓝图，所以玩家每种货币只有一个堆叠对象。定位用 `present("gold_money",who)`。
  - **钱庄存款**是独立玩家属性 `balance`（整数，非物品）。
  - **支付底层**：`pay_player(who,amount)` 系统发钱（按金/银/铜拆分生成对象）；`player_pay(who,amount)` 玩家付款（三态返回）；带全服现金总量上限的变体（反通胀，`MAX_CASHFLOW_ALLOWED=400000`）。
- **对新引擎设计启发**：金钱**是特殊物品还是独立账本**是关键设计抉择。LPC 选了"特殊物品"（继承 COMBINED_ITEM，有重量、可堆叠、可掉落），导致金钱转移走物品 move 机制、有全服总量上限反通胀逻辑。**对新引擎的建议**：M1 不做金钱（属 M2 经济系统），但应决策--金钱是 `Wallet` 组件（独立账本，整数余额，题材无关，简单）还是 money-as-item（可掉落/可堆叠/有重量，更拟真但复杂）。**倾向 Wallet 组件**：题材无关引擎应抽象"货币种类+余额+支付"为独立能力，金钱作为物品是武侠题材的特殊化。这点在 ADR 层面值得记录。

---

## 3. 与其他系统关联点

- **战斗系统**：装备效果（apply 临时层）+武器 flag+`hit_ob/hit_by` 回调+embed 嵌入暗器+负重通过 query_str 间接影响伤害。**装备系统是物品与战斗的耦合点**，M1 做物品时要为装备效果施加预留接口（临时属性层/Effect 组件）。
- **状态系统**：饮食 `eat_func`/`finish_eat` 钩子施加状态（回 food/jingli）；液体 `drink_func` 可被药粉注入施加 condition（中毒）；护甲 `hit_by` 被徒手攻击者中毒。**消耗品触发状态效果是物品-状态耦合点**。
- **NPC 系统**：`accept_object` 是 give->quest 的主入口；F_DEALER 把商人能力挂 NPC；门派 NPC 唯一化靠 children 计数。**NPC 行为钩子（接受物品/买卖）是物品-NPC 耦合点**。
- **经济系统**：金钱支付（player_pay 三态）+商店定价+全服现金总量上限反通胀。**金钱/买卖是物品-经济耦合点**。
- **存档系统**：物品一般不存盘（F_SAVE 锦囊/信件等容器类除外）；MONEY 用 `autoload` 序列化数量；玩家物品栏通过玩家存档间接持久化。**物品实例的存档边界**：堆叠数量要存，物品定义本身是声明式不需存。
- **reset/clean_up 生命周期**：物品 spawn 与销毁与房间 reset 周期绑定；`no_refresh`/`no_clean_up` 控制生命周期。

---

## 4. M1 scope 建议（三档）

### 当前已实现基线（take/drop/inventory）

- `Container` 组件：通用"持有 entity id 集合"，房间地面/玩家物品栏同构（`engine/src/mud_engine/components.py:138`）。
- take/drop/inventory 三命令（`commands.py:256-299`）：只在房间地面容器与玩家物品栏之间搬 entity id 集合，**无重量/价值/堆叠/容器物品/装备/买卖/给与/spawn 标志**。
- YAML 场景 DSL（`engine/data/m1_default_scene.yaml`）：items 段只支持 `name/aliases/short/long/placed_in`。
- 门与动态出口已就位（04 号票）。

### M1 必做（引擎地基，不做 M2 会返工）

1. **物品能力维度组件化** -- 把 LPC 的 feature 混入映射为正交可选组件：`Stackable`（amount+base_weight/base_unit）、`Valuable`（value）、`Equippable`（占位，slot+apply）、`Consumable`（占位）。理由：M2 战斗/状态/经济都要挂这些能力，若 M1 只用一个臃肿 Item 组件，M2 必然返工拆分。
2. **转移统一原语 + 校验钩子** -- 把 take/drop/put/give 收敛到一个 `transfer(item, src_container, dst_container)` 底层函数，带"可否放入"校验钩子（对应 LPC `reject`）。理由：转移是物品系统核心，命令层共用一个原语避免散落校验逻辑。
3. **堆叠物品** -- Stackable 组件 + move 时自动合并同定义物品 + `take <数量>` 拆分。理由：金钱、暗器、药丸都需要，是基础能力；合并/拆分逻辑一旦写散难回收。
4. **物品标志位（流转层）** -- `no_get`/`no_drop`（与 LPC 同名；`no_drop` 支持字符串自定义提示）。理由：quest 物品/师门之物是 MVP 题材包刚需，标志位是引擎地基。
5. **容器物品** -- 物品本身可挂 Container 组件（箱子/背包），put/take 支持"放进/取出容器"。理由：LPC 的 `is_container()`/`reject()` 设计证明容器是通用能力，新引擎 Container 已是通用组件，只需让物品也能挂。M1 场景可不放箱子实例但接口要通。
6. **物品查看增强** -- `look <物>` 展示 long + 容器内容 + 数值（weight/value/堆叠数）。理由：当前 look 物品能力不足，M1 打磨物品必含可见性。
7. **重量与容量上限（最小版）** -- 物品 weight 字段 + 容器 max_capacity + 超限拒绝放入。理由：容量上限是转移校验的一部分（维度 3/4），不做则容器无意义。**角色负重上限公式推迟 M2**（属战斗/属性）。

### M1 可选（能做但可推迟）

8. **`put` 命令** -- 依赖容器物品（必做项 5），有了容器就顺手做。若容器接口先通，put 可同批落地。
9. **`give` 命令 + `accept_object` 钩子** -- 转移到 NPC 容器 + NPC 侧接受/拒绝钩子（受限 Python）。理由：MVP 题材包有 NPC 交互需求，但 quest trigger 可用对话系统代替，非阻塞。
10. **spawn 加载时生成** -- 场景加载时按 items 清单 spawn（已有 placed_in 雏形）。理由：M1 已有，扩展为完整 spawn 接口即可。
11. **物品 value 字段** -- 只是数据，不做买卖。理由：为 M2 经济系统预留，零成本。

### 延后 M2+（需题材内容/复杂度不值得）

12. **装备系统（wield/wear/unwield/remove）** -- 依赖战斗系统的 apply 临时层与 slot 体系。M2 战斗系统一起做。
13. **消耗品（eat/drink/pill）** -- 依赖状态系统的效果施加。M2 状态系统一起做。
14. **买卖（sell/buy/list/value）+ 金钱支付** -- 依赖经济系统与金钱抽象。M2+。**金钱作为 Wallet 组件还是 money-as-item 的决策建议先写 ADR**。
15. **定期 reset 重生** -- 依赖心跳调度+对象生命周期。M2（reset 周期属世界运行时）。
16. **唯一性 spawn 检查（F_UNIQUE）** -- 依赖 spawn 机制就位。M2+。
17. **throw/steal** -- 战斗/技能相关。M2+。
18. **装备磨损/耐久** -- 战斗副产物。M2+。
19. **环境链上溯超重豁免** -- 容器嵌套较深时的优化，M1 容器层次浅可不做，M2 补。

---

## 5. DSL 动态规则表达（YAML 声明式 + 受限 Python 钩子）

LPC 的动态规则全靠在物品/NPC/房间对象里写 LPC 代码（`init` 注册 verb、`accept_object`/`reject`/`hit_ob` 回调、`call_out` 延时）。新引擎 DSL 需把"声明式数据"与"受限 Python 钩子"分层：静态属性 YAML 声明，动态行为挂钩子函数。

### 物品相关的动态规则需求归纳

- **流转限制**："此物品只能被特定职业拾起""quest 物品不能丢弃""师门之物只能给师父"。
- **消耗效果**："喝水后 10 秒回血""吃药后中毒 30 秒""食物吃了饱食度+20"。
- **spawn 规则**："唯一物品被取走后该房间不再刷新""夜间才刷新的 NPC""随机生成 1-3 个"。
- **商店规则**："商店夜间打烊""只卖给特定阵营""限量供应每天 10 个"。
- **装备规则**："只有内功≥50 才能装备""装备后每秒扣血（诅咒）""卸下时中毒"。
- **查看规则**："look 此物品触发机关""只有会鉴定技能才看到真实属性"。

### DSL 草稿示意（3 个，用于讨论，非最终格式）

**草稿 1：流转限制 + 字符串自定义提示（声明式为主，钩子兜底）**

```yaml
items:
  shifu_sword:
    name: 师门佩剑
    aliases: [剑, 佩剑]
    short: 一柄寒光凛凛的长剑
    long: 少林寺方丈亲赐的佩剑，剑柄刻有"少林"二字。
    placed_in: start_yard
    stackable: false
    weight: 3000
    value: 5000
    flags:
      no_drop: "这是师门之物，不可随意丢弃。"   # 字符串=自定义提示
      no_give: true
    # 受限 Python 钩子：拾取前校验（声明式表达不了的才用钩子）
    hooks:
      on_before_take: |
        # ctx.player, ctx.item 可用；返回 (allow: bool, message: str|None)
        if "shaolin" not in ctx.player.get("factions", []):
            return (False, "此剑认主，唯有少林弟子方可拾起。")
        return (True, None)
```

**草稿 2：消耗效果 + 延时回调（声明式触发 + 钩子逻辑）**

```yaml
items:
  healing_potion:
    name: 金创药
    aliases: [药, 药丸]
    short: 一颗暗红色的药丸
    long: 江湖中常见的金创药，吞服可止血疗伤。
    placed_in: storage_room
    stackable:
      base_unit: 颗
      base_weight: 10
    consumable:
      charges: 1              # 吃一口就消耗（food_remaining）
      on_consume: |           # 受限 Python：消耗时触发
          # 10 秒后回血（call_out 等价物由引擎调度）
          ctx.schedule(delay=10, action="heal", target=ctx.player, amount=200)
          ctx.player.add_status("regenerating", duration=10)
          ctx.world.message(ctx.player, "你吞下药丸，一股暖流在体内化开。")
```

**草稿 3：唯一性 + spawn 规则 + 商店规则（声明式标志 + 钩子条件）**

```yaml
items:
  dragon_sword:
    name: 屠龙刀
    aliases: [刀]
    short: 一柄通体漆黑的重刀
    long: 传闻中的屠龙宝刀，号令天下莫敢不从。
    placed_in: dragon_cave
    unique: true              # 唯一物品，全局实例数检查（F_UNIQUE 等价）
    flags:
      no_refresh: true        # 被取走后房间不再刷新（一次性）
    hooks:
      on_spawn_check: |       # spawn 前校验是否允许生成
          # 唯一物品：世界已存在则不刷新
          if ctx.world.count_instances("dragon_sword") > 0:
              return (False, None)
          # 夜间才刷新（拆解说明书未提，但常见武侠规则）
          if not ctx.world.is_night():
              return (False, None)
          return (True, None)

npcs:
  night_vendor:
    name: 夜行商
    in_room: night_market
    vendor:
      goods: [healing_potion, antidote]
      buy_factor: 1.2
      sell_factor: 0.7
      open_hours: [18, 6]    # 夜间 18:00-次日 6:00 营业（声明式）
    hooks:
      on_trade_check: |       # 交易前校验（打烊/限量等声明式表达不了的）
          if not ctx.npc.is_open_now():
              return (False, "夜行商白天打烊了，入夜再来。")
          if ctx.item.id == "healing_potion" and ctx.world.today_sold("healing_potion") >= 10:
              return (False, "今日金创药已售罄，明日请早。")
          return (True, None)
```

**DSL 分层原则建议**：
- 声明式层（YAML 字段）：`flags`/`stackable`/`consumable`/`vendor`/`unique`/`weight`/`value` 等静态属性与开关--覆盖 80% 场景，非工程师可改。
- 钩子层（受限 Python `hooks:` 块）：`on_before_take`/`on_consume`/`on_spawn_check`/`on_trade_check`/`accept_object` 等--覆盖条件逻辑、延时、跨对象操作。受限 Python（无文件 IO/无网络/沙箱内）沿用旧方案已验证的教训（CLAUDE.md 提及"UGC 脚本用受限 Python 非 WASM"）。
- `ctx` 注入：`player`/`item`/`npc`/`world`/`schedule` 等受控 API，钩子只能通过 ctx 访问世界，不能直接拿引擎内部对象。
- 命名约定：钩子用 `on_<event>` 前缀，事件名与引擎内部 transfer/spawn/consume 调度点一一对应，便于文档化。

---

## 关键 LPC 出处索引（绝对路径）

- 物品基类：`/Users/gukt/github/xkx2001-utf8/inherit/item/{item,combined,money}.c`
- 装备基类：`/Users/gukt/github/xkx2001-utf8/inherit/misc/equip.c`、`/Users/gukt/github/xkx2001-utf8/feature/equip.c`（F_EQUIP 真实现）
- 武器/防具类型：`/Users/gukt/github/xkx2001-utf8/inherit/weapon/{sword,blade,throwing,_heavy}.c`、`/Users/gukt/github/xkx2001-utf8/inherit/armor/{armor,cloth}.c`
- 药品/食物/液体：`/Users/gukt/github/xkx2001-utf8/inherit/medicine/{pill,powder}.c`、`/Users/gukt/github/xkx2001-utf8/feature/{food,liquid,pill}.c`
- 唯一性：`/Users/gukt/github/xkx2001-utf8/feature/unique.c`
- 转移核心：`/Users/gukt/github/xkx2001-utf8/feature/move.c`、`/Users/gukt/github/xkx2001-utf8/inherit/room/room.c`
- 命令：`/Users/gukt/github/xkx2001-utf8/cmds/std/{get,drop,put,give,eat,wield,wear,unwield,remove,throw,steal,look,open,close,feed}.c`、`/Users/gukt/github/xkx2001-utf8/cmds/usr/inventory.c`
- 买卖：`/Users/gukt/github/xkx2001-utf8/feature/{dealer,vendor}.c`、`/Users/gukt/github/xkx2001-utf8/inherit/room/hockshop.c`
- 金钱：`/Users/gukt/github/xkx2001-utf8/adm/daemons/moneyd.c`、`/Users/gukt/github/xkx2001-utf8/clone/money/{coin,silver,gold,thousand-cash}.c`、`/Users/gukt/github/xkx2001-utf8/feature/finance.c`
- 配置：`/Users/gukt/github/xkx2001-utf8/config.xkx`（reset 1800s/clean_up 180s）
- 头文件：`/Users/gukt/github/xkx2001-utf8/include/{armor,weapon,globals,room}.h`
- 典型 quest NPC：`/Users/gukt/github/xkx2001-utf8/d/city/npc/dingdian.c`、`/Users/gukt/github/xkx2001-utf8/d/city/npc/tiejiang.c`、`/Users/gukt/github/xkx2001-utf8/d/city/npc/huoji.c`

## 现有 engine 基线（绝对路径）

- Container 组件：`/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/components.py:138`
- take/drop/inventory 命令：`/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/commands.py:256-299`
- YAML 场景格式：`/Users/gukt/github/xkx2001-utf8/engine/data/m1_default_scene.yaml`（items 段当前仅 name/aliases/short/long/placed_in）
- 场景加载：`/Users/gukt/github/xkx2001-utf8/engine/src/mud_engine/scene_loader.py`

## 给决策者的关键判断（供拍板）

1. **物品能力应组件化**（M1 必做项 1）--这是最重要的架构决策，决定 M2 战斗/状态/经济能否干净接入。
2. **金钱抽象先写 ADR**--Wallet 组件（独立账本）vs money-as-item（特殊物品），题材无关引擎倾向前者。
3. **买卖/装备/消耗/spawn-reset 都推迟 M2+**--M1 聚焦"转移原语+堆叠+容器+标志位+查看+重量容量"，这些是 M2 各子系统都要复用的地基。
4. **DSL 钩子层命名约定**（`on_<event>` + ctx 注入）应尽早定，M1 物品钩子是 M3 UGC DSL 的第一块试验田。
