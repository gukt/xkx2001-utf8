# 创作者契约 v0

> 现行场景 YAML / 内容包 manifest 的冻结字段集合。  
> 对应实现：`engine/src/mud_engine/scene_loader.py`、`engine/src/mud_engine/pack.py`。  
> 机器可检查侧：`mud_engine --pack <dir> --validate`（默认 warn）与 `--strict`（未消费字段失败）——见 M3 停机加固票 [`05`](../.scratch/m3-hardening/issues/05-validate-strict-unconsumed-fields.md)。

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

未列入上表的顶层段（例如 `nature:`）走透传，**不是** v0 冻结契约的一部分。

## 实体级已知字段

下列集合为当前引擎「认识并消费」的字段。写出集合外的键 → 透传，可用 `--validate` / `--strict` 检出。

### `rooms.*`

`name`, `aliases`, `short`, `long`, `exits`, `outdoors`, `no_death`, `ferry`, `entry_guard`, `cost`, `terrain`

### `items.*`

`name`, `aliases`, `short`, `long`, `placed_in`, `amount`, `stackable`, `unit_weight`, `valuable`, `value`, `equippable`, `consumable`, `no_drop`, `no_drop_message`, `no_get`, `container`, `max_capacity`, `max_weight`, `weight`, `item_tags`, `tags`

### `npcs.*`

`name`, `aliases`, `short`, `long`, `in_room`, `startroom`, `count`, `respawn`, `loot`, `inquiry`, `behaviors`, `tick_interval`, `vitals`, `attributes`, `skills`, `currency`, `shop`, `faction`, `mount`, `gender`

### `player`

`name`, `start_room`, `inquiry`, `behaviors`, `tick_interval`, `vitals`, `attributes`, `skills`, `currency`, `shop`, `faction`, `mount`, `gender`

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

`--strict` 必须搭配 `--validate`；`--validate` 必须搭配 `--pack`。检查复用上述已知字段集与透传容器，不另建平行登记表。

## 契约表达不到的地方

当前声明式 YAML **表达不了** / 需降级绕过的能力清单，见 GAP 台账（M3 停机加固票 [`11`](../.scratch/m3-hardening/issues/11-gap-ledger.md) 产出后补链接：`docs/gap-ledger.md`）。
