# 创作者契约 v0

> 现行场景 YAML / 内容包 manifest 的冻结字段集合。  
> 对应实现：`engine/src/mud_engine/scene_loader.py`、`engine/src/mud_engine/pack.py`。  
> 机器可检查侧：`mud_engine --pack <dir> --validate`（默认 warn）与 `--strict`（未消费字段失败）——见 M3 停机加固票 [`05`](../.scratch/m3-hardening/issues/05-validate-strict-unconsumed-fields.md)。  
> Pre-M4 房间保真加法：票 [`07`](../.scratch/pre-m4-engine-room-fidelity/issues/07-closeout-contract-gap.md)（字段形状见同 effort 票 `01`–`06` Comments）。  
> Pre-M4 房间钩子收口：票 [`11`](../.scratch/pre-m4-room-hooks-xingxiu/issues/11-closeout-ugc-boundary-contract-gap.md)（`hooks` 官方轨专属说明，非加法承诺）。

本文档承诺：**这些字段现在可以用、语义已冻结、只会新增不会改义。** 创作者不必去读引擎源码里的 `_ROOM_KNOWN_FIELDS` 等常量。

## 承诺条款

1. **只做加法**：v0 之后可以新增顶层段、新增已知字段；不会对本文列出的已知字段做破坏性语义变更（改名、改类型、改必填性、改含义）。
2. **透传不算契约**：已知集合之外的键会被引擎收进 `World.extension_data`（顶层段）或 `entity_extension_data(entity)`（实体级），**不在冻结范围内**——随时可能被未来版本收编为正式字段、改变行为，或继续保持透传。不要把自定义透传键当成稳定 API。
3. **事实来源唯一**：已知集合与 `scene_loader.py` / `pack.py` 中的常量一致；能力字段由 `capabilities.py` 各 `CapabilitySpec.known_fields` 聚合而来。本文是对外可读摘要，实现以代码为准；若文档与代码短暂漂移，以代码 + 本票后续修订为准。

## 场景 YAML：顶层已知段

| 段 | 含义（摘要） |
|---|---|
| `rooms` | 房间字典（必需） |
| `items` | 物品字典（可空） |
| `npcs` | NPC 字典（可空） |
| `player` | 玩家初值（必需） |
| `skills` | 全局技能注册表 |
| `factions` | 全局门派注册表 |
| `death_policy` | 死亡/昏迷策略覆盖 |
| `quests` | 声明式任务表（可空） |
| `books` | 藏书书档目录（可空；供房间 `library.books` 引用） |

未列入上表的顶层段（例如 `nature:`）走透传，**不是** v0 冻结契约的一部分。

## 实体级已知字段

下列集合为当前引擎「认识并消费」的字段。写出集合外的键 → 透传，可用 `--validate` / `--strict` 检出。

### `rooms.*`

`name`, `aliases`, `short`, `long`, `exits`, `objects`, `block_exits`, `outdoors`, `no_death`, `ferry`, `entry_guard`, `day_shop`, `cost`, `terrain`, `details`, `no_fight`, `no_steal`, `no_sleep_room`, `library`

`objects` 为放置权威（模板键 → 正整数数量），引用同文件 `items.*` / `npcs.*` 模板；见 [ADR-0010](adr/0010-room-centric-objects-placement.md)。已退役的 `placed_in`（物品）/ `in_room` 与模板段 `count` 若出现，加载失败。

房间风景：`details` 为键 → 描述字符串；可含语义色 markup；不占 `objects`、不可 `get`。`look <键>` 在同房实体未命中后查本映射。

房间旗标：`no_fight` / `no_steal` / `no_sleep_room`（布尔）。`no_fight` 拦 `attack`/`kill`；后二者可声明并校验，无对应命令面时行为 inert。

日间店：`day_shop: true` 加载期编成白天放行的 `entry_guard`（谓词 `is_day`，拒入文案「晚上不开门。」）。同房不得再手写 `entry_guard`（冲突则加载失败）。

藏书房：`library: true`（仅同房禁 `practice`）或 `library: {shelf, books: [id…]}`（`shelf` 默认 `书架`；`books` 引用顶层 `books.*`）。`look <shelf>` 出 TOC（可 `more`）；`read <缩写|书名|id>` 选书；`read <章号>` 按 `chapter_cost` 扣银两读章。

剧情挡向：`block_exits: { <dir>: {npc: <模板键>} }`——该向在对应 NPC 模板实例同房在场时拒走。

#### `rooms.*.exits.*`

出口可为字符串目标房键，或映射：

| 字段 | 含义 |
|---|---|
| `to` | 目标房间键（映射写法必填） |
| `aliases` | 出口级别名（可选）；标准十向中英同义词由引擎内置，不必手写；地名宜写在目标房 `name`/`aliases` |
| `door` | `open` / `closed` / `locked`（有门时） |
| `key` | 解锁所需物品模板键 |
| `consume_key` | 布尔；`true` 时 `unlock` 成功销毁钥匙（默认 `false`，标准门不耗钥） |
| `hidden_until_unlocked` | 布尔；`true` 时未解锁不进可见出口（须 `door: locked`）；解锁后迁入可见出口并开启 |

### `items.*`

`name`, `aliases`, `short`, `long`, `respawn`, `amount`, `stackable`, `unit_weight`, `valuable`, `value`, `equippable`, `consumable`, `no_drop`, `no_drop_message`, `no_get`, `container`, `max_capacity`, `max_weight`, `weight`, `item_tags`, `tags`

纯模板定义；摆放位置与份数写在房间 `objects`，不在本段。`respawn` 与 NPC 对齐：objects 槽位实例销毁后是否补刷；仍存在（背包/别房）则占名额。被门锁 `key` 唯一引用的物品不得 `objects` 合计 `>1` 或 `respawn: true`。

### `npcs.*`

`name`, `aliases`, `short`, `long`, `startroom`, `respawn`, `loot`, `inquiry`, `behaviors`, `tick_interval`, `vitals`, `attributes`, `skills`, `currency`, `shop`, `faction`, `mount`, `gender`

纯模板定义；初始位置与实例数由房间 `objects` 推导。`startroom` 可选，缺省即 `objects` 所在房，若显式写出须与之相同（补刷落点）。

### `player`

`name`, `start_room`, `inquiry`, `behaviors`, `tick_interval`, `vitals`, `attributes`, `skills`, `currency`, `shop`, `faction`, `mount`, `gender`

### `quests.*`

`name`, `accept`, `complete`, `reward`, `messages`

- `accept.require_npc`：接取时须与该 NPC 模板同房（模板键）。
- `complete.give_item` + `complete.to_npc`：对目标 NPC `give` 指定物品模板完成（二者须成对）。
- `complete.flags`：旗标满足完成（与交物完成二选一或可并存于不同任务）。
- `reward.currency`：完成时发放的银两。
- `messages.accept` / `messages.complete`：可选提示文案。

接取命令：`quest accept <id>`。`ask` 不触发接取。

### `books.*`

| 字段 | 含义 |
|---|---|
| `title` | 中文书名（展示 / 选书） |
| `abbrevs` | 缩写字符串或列表（选书别名） |
| `chapter_cost` | 每章银两（非负整数） |
| `chapters` | 非空字符串列表（章正文） |

## 语义色 markup

权威文本（房间/物品/NPC 的 `short`/`long`、`details` 值等）允许 `<c:name>…</c>`；色名仅 `red` / `green` / `yellow` / `blue` / `magenta` / `cyan` / `white`。禁止嵌套、原始 ANSI、LPC 色宏（如 `HIG`/`NOR`）。加载与 `--validate` 同路径校验；失败则加载失败。见 [ADR-0011](adr/0011-semantic-color-tokens.md)。

命令回文等权威消息保留 token；官方 CLI 仅在 TTY / `--color` 映亮色 ANSI，管道与测试默认剥为纯文本。

## 内容包 `manifest.yaml` 已知字段

| 字段 | 必填 | 含义 |
|---|---|---|
| `id` | 是 | 包身份 ID |
| `version` | 是 | 包版本字符串 |
| `creator` | 否 | 创作者标识 |
| `title` | 否 | 展示标题 |

其余键进入 `PackManifest.extra`（透传，同样不在冻结范围内）。

## 机器可检查侧

```bash
# 加载并校验；未消费（透传）字段打印警告，退出码 0
python -m mud_engine --pack <包目录> --validate

# 同上，但未消费字段视为失败（非 0 退出）
python -m mud_engine --pack <包目录> --validate --strict
```

`--strict` 必须搭配 `--validate`；`--validate` 必须搭配 `--pack`。检查复用上述已知字段集与透传容器，不另建平行登记表。语义色与本波新字段的消费/拒坏与 `load_scene` 同源——内容包轨经 `load_pack` → `load_scene` 覆盖。

## 官方轨与内容包轨

场景 YAML 字段集合被两条加载轨道共用：无 `manifest` 的官方单文件，与带 `manifest.yaml` 的内容包。入口差异与范本见 [场景创作：官方轨与内容包轨](scene-authoring-guide.md)（M3 停机加固票 [`09`](../.scratch/m3-hardening/issues/09-scene-authoring-two-tracks-doc.md)）。

## 官方轨专属：房间钩子引用（非创作者契约加法）

房间字段 `hooks: { hook_id, params? }` **不是** 本契约 v0 的加法承诺字段，也不在上文 `rooms.*` 已知集合的「创作者可用」清单内。

| 轨道 | 行为 |
|---|---|
| 官方单文件（无 `manifest.yaml`，如 `xingxiu_mechanics.yaml`） | 允许引用已注册的可信 `hook_id`；实现永远是引擎 / 题材包自带 Python，不是 YAML 内联脚本 |
| 内容包（带 `manifest.yaml`） | **禁止** 声明 `hooks`；`load_pack`、`--pack --validate`、`--pack --validate --strict` 与非严格加载路径一律 **失败**（信任边界，非「未消费字段只警告」） |

见 [ADR-0012](adr/0012-trusted-room-hooks-narrow-ctx.md)。创作者需要「运行时改世界」类机关时，勿在 UGC 包里写 `hooks`；降级方式见 [GAP 台账](gap-ledger.md)。

## 契约表达不到的地方

当前声明式 YAML **表达不了** / 需降级绕过的能力清单，见 [GAP 台账](gap-ledger.md)（M3 停机加固票 [`11`](../.scratch/m3-hardening/issues/11-gap-ledger.md)）。
