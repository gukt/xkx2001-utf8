# 条件 DSL（创作者可读）

> 四个接入点共用同一套结构化条件表达式（受限 AST，非裸 Python）。  
> 解析入口：`mud_engine.ai.condition_from_data`；求值：`mud_engine.conditions.evaluate`。  
> 契约索引见 [creator-contract-v0.md](creator-contract-v0.md)；能力缺口见 [gap-ledger.md](gap-ledger.md)。  
> 产出自 Polishing 票 [`07`](../.scratch/polishing/issues/07-condition-dsl-docs.md)。

本文档承诺：**下列语法与接入点现在可用**；不在「现在不支持」清单里的查询面**不要**按文档摸索发明。

## 共用语法

条件是 YAML 映射，形状与引擎节点一一对应：

| 写法 | 含义 |
|---|---|
| `{predicate: <名>}` | 查 context 上的布尔谓词 |
| `{field: <名>, value: <字面量>}` | 相等（`Equals`）；亦接受嵌套 `{equals: {field, value}}` |
| `{gte: {field: <名>, value: <数>}}` | 数值 `>=`；亦接受 `{op: gte, field, value}` |
| `{and: [子条件…]}` / `{or: […]}` | 逻辑组合；空 `and` 为真、空 `or` 为假 |
| `{not: <子条件>}` | 取反 |

### 谓词（`predicate`）

`is_night`、`is_day`、`is_raining`、`is_wielding_edged_weapon`

> 持刃谓词仍存在，但**没有** `wield` / `unwield` 命令面——官方少林山门已去掉持刃条件。勿在门禁里要求玩家「收刀」。见 GAP「装备槏位与真实 wield / unwield」。

### 字段相等 / `gte` 常用字段

| 字段 | 典型用途 |
|---|---|
| `phase` | 时辰名字符串（如 `"night"` / `"day"`） |
| `faction_id` | 门派 id；无归属为 `null`（YAML 写空/省略需注意求值侧） |
| `gender` | 性别标记（如 `"male"`） |
| `has_faction` | 是否已有门派（布尔） |
| `str` / `con` / `dex` / `int` | 基础属性（`gte` 常用） |

嵌套深度有上限（引擎 `MAX_DEPTH`）；超过则求值失败。

---

## 接入点 1：`rooms.*.entry_guard`

进房前求值；不通过则拒绝并返回 `deny_message`。与 `day_shop` **互斥**（同房二者并存 → 加载失败）。

真实片段（官方 `engine/data/m2_mvp_scene.yaml` · 少林山门）：

```yaml
shaolin_shanmen:
  name: 少林山门
  # …
  entry_guard:
    condition:
      and:
      - field: gender
        value: male
      - or:
        - field: has_faction
          value: false
        - field: faction_id
          value: shaolin
    deny_message: 少林山门：须为男子、未属他派。
```

---

## 接入点 2：`rooms.*.day_shop`

布尔简写。加载期编译为「白天可进」的 `entry_guard`：谓词 `is_day`，拒入文案「晚上不开门。」。勿再手写并行时间守卫。

真实片段（官方 `engine/data/m2_mvp_scene.yaml` · 打铁铺）：

```yaml
yangzhou_datiepu:
  name: 打铁铺
  long: 炉火正旺，铁砧上火星四溅。墙上挂着新打的刀剑与农具。
  day_shop: true
  exits:
    south:
      to: yangzhou_xidajie
  objects:
    steel_blade: 1
    blacksmith: 1
```

等价于加载后挂上：

```yaml
entry_guard:
  condition:
    predicate: is_day
  deny_message: 晚上不开门。
```

（以上等价形来自加载器编译结果，不是场景文件手写内容。）

---

## 接入点 3：`skills.*.learn_condition`

学艺（`learn`）额外门槏；与 `level_req` 等并存。不满足则拒学。

真实片段（官方 `engine/data/m2_mvp_scene.yaml` · 罗汉拳）：

```yaml
skills:
  luohan_quan:
    type: martial
    level_req: 0
    learn_condition:
      gte:
        field: con
        value: 10
    practice:
      neili: 5
      jingli: 5
      exp: 10
```

---

## 接入点 4：`npcs.*.behaviors[].when`

NPC 行为（如 chatter）的可选触发条件；未写 `when` 则无额外门禁。求值 context 优先取 World 的 Nature（昼夜/雨），否则 stub。

真实片段（官方 `engine/data/m1_default_scene.yaml` · 夜猫子）：

```yaml
night_owl:
  name: 夜猫子
  aliases:
  - 夜猫
  short: 一个昼伏夜出的人
  long: 此人白天打瞌睡，夜里才精神。
  behaviors:
  - kind: chatter
    chat_msgs:
    - 夜深了，该歇歇了。
    chat_chance: 1.0
    when:
      predicate: is_night
```

---

## 现在不支持

下列查询面**不在**本 DSL 内；勿在场景 YAML 里发明对应字段。措辞与 [gap-ledger.md](gap-ledger.md) 对齐：

| 缺口 | 与 GAP 台账的关系 |
|---|---|
| **背包任意物查询**（如「背包是否有某模板物品」作通用谓词） | 条件 DSL **当前没有** `has_item` / 任意背包查询原语。GAP「装备槏位与真实 wield / unwield」行虽在降级建议里提到 `has_item`，那是设计指引而非已实现谓词——勿在 YAML 条件里写 `has_item`。持刃谓词是特例且命令面未齐。 |
| **任务旗标查询**（在条件里读 `QuestProgress` 旗标） | 对齐「脚本化任务 / 剧情分支」：声明式旗标任务已支持接取/交物完成，但条件 DSL **不**暴露任务旗标作通用谓词；勿在 `entry_guard` / `learn_condition` / `when` 里写旗标查询。 |
| **局部天气查询**（按房间覆盖全局 Nature） | 对齐「局部 / 区域天气继承」：**未支持**（Nature 为 World 单例）。实现前只用全局昼夜/雨；勿假设房间局部天气。Polishing C14 另票。 |

贵重物刷怪等玩法条件扩展走**官方 hooks `params`**，**不**往本 DSL 加专用谓词（见 GAP「运行时改世界机关」与 ADR-0012）。

持续 Effect / buff 不在本 DSL 范围（见 [ADR-0007](adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)）。
