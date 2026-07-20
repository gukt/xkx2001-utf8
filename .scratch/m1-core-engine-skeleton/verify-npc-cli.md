# M1 NPC 命令 / 行为手测 · 一键矩阵

> 范围：块 D（D1–D5）+ 票 25–29 / 34 / 35  
> 对照调研：[research/02-npc.md](research/02-npc.md)、[research-m1-extension-items-npc-nature.md](research-m1-extension-items-npc-nature.md)  
> 不含：Nature 完整手测、物品矩阵、战斗 / 商店 / give / random_move（M2+ 或可选未做）

## 推荐：一键矩阵（免手动敲命令）

仓库根执行：

```bash
just verify-npc
```

会用 fresh 默认场景跑 look / ask / say + tick 驱动 Chatter / spawn 扫描，打印每条输出与 ✔ / ✖，末尾给场景级摘要。  
实现：[engine/scripts/verify_m1_npc.py](../../engine/scripts/verify_m1_npc.py)（pytest：`tests/test_verify_m1_npc_matrix.py`）。

不读、不写 `engine/save`。

单元测细节（`on_hear_say` 参数、handler 占位存档、tick_interval 跳拍等）见 [`engine/tests/test_npc_extension.py`](../../engine/tests/test_npc_extension.py)。

## 可选：手动 `just run`

需要自己摸手感或调试单条命令时再用。

1. **先清存档**（否则可能恢复旧档，夹具不全）：

```bash
rm -rf engine/save
just run
```

2. 夹具在**起始庭院**（户外）。`look` 应看到：石像守卫、庭院闲人、夜猫子、巡逻兵×2。

## 命令面约定

| 规范动词 | 说明 |
|---|---|
| `look` / `l` | 房间看在场 NPC（「你看到：…」）；NPC **不是**物品，`look <NPC名>` / `get <NPC名>` 会当物品失败 |
| `ask <npc> about <topic>` | 同房间可 ask 实体（挂 `Inquiry` 或 `NpcSpawnMeta`）；文案前缀「说：」 |
| `say <内容>` | 玩家确认「你说：…」；空内容拒绝 |

## 场景夹具（默认 YAML）

| 键 | 名称 | 用途 |
|---|---|---|
| `stone_guard` | 石像守卫 | inquiry（天气 / default）；**无** AIController |
| `yard_gossip` | 庭院闲人 | Chatter 无条件、`chat_chance: 0.05`（手感；矩阵用确定性 rng） |
| `night_owl` | 夜猫子 | Chatter `when: is_night` |
| `patrol_pair` | 巡逻兵 | `count: 2` + `respawn: true`（扫描空转） |

## 1. look + 不能 get NPC

| # | 输入 | 期望要点 |
|---|---|---|
| 1 | `look` | 见石像守卫、庭院闲人、夜猫子、巡逻兵（两名）、石头 |
| 2 | `get 石像守卫` | 「这里没有 石像守卫。」（NPC 不在地面 Container） |

## 2. ask inquiry

| # | 输入 | 期望要点 |
|---|---|---|
| 1 | `ask 石像守卫 about 天气` | `石像守卫说：`…晴朗 |
| 2 | `ask 守卫 about 天气` | 别名 → 仍「石像守卫说：」 |
| 3 | `ask 石像守卫 about 武功` | default：没有回答 |
| 4 | `ask 不存在的人 about 天气` | 这里没有… |
| 5 | `ask` | 用法提示 |
| 6 | `ask 巡逻兵 about 天气` | 同名×2 → 「不确定你指的是哪个」 |
| 7 | `ask 庭院闲人 about 天气` | 无 Inquiry → 「似乎不想和你说话」 |

## 3. say

| # | 输入 | 期望要点 |
|---|---|---|
| 1 | `say 你好` | `你说：你好` |
| 2 | `say` / `say   ` | 用法提示 |

## 4. Chatter（一键矩阵用 tick；手动难稳定复现）

一键矩阵强制 `phase=day/night` + 确定性 rng，再 `TickLoop.advance`：

| 条件 | 期望 |
|---|---|
| day | `庭院闲人说：庭院真清静啊。`；**无**「夜猫子说：」 |
| night | 出现 `夜猫子说：夜深了，该歇歇了。` |
| 多拍 | **无**「石像守卫说：」（静态 NPC 不闲聊） |

手动 `just run` 时闲人约 5% 概率随 tick 开口（不再每命令必说）；夜猫依赖当前 Nature 是否算夜里（`dawn`/`night` 算夜里，`day`/`dusk` 不算）。

## 5. Spawn 地基（预期半成品）

| 检查 | 期望 |
|---|---|
| 加载 | 巡逻兵实例 = 2 |
| tick 扫描 | `respawn: true` 且已满员 → **空转不崩**、不增减 |
| **不当 bug** | 删除实例后 **M1 不补齐**（推 M2 死亡重生） |

## 6. 门钥匙短回归

与物品矩阵相同：庭院 `n` → 拿铁钥匙 → `unlock`/`open north` → 进静室。

## 预期缺失（不当 bug）

- `Inquiry.handler` 执行（仅 YAML/存档占位）
- Spawn 真补齐 / 全灭模板找回
- `give` / `random_move` / Faction / 战斗 / Vendor / 任务 / 跟随
- `look <NPC>` 详情（M1 look 目标只认物品）
- 受限 Python 对话钩子（M3）
- 同名序号消歧（`巡逻兵 2`）：推迟 M2，见 [M2 spec](../m2-mvp-scene-playable/spec.md) 用户故事 60a–60c

## 完成度摘要（验证时点）

| 调研项 | 票 | 代码 | CLI 矩阵 |
|---|---|---|---|
| D1 Behavior/AIController | 25 | 已落地 | tick 组覆盖 |
| D2 count/respawn/startroom | 26 | 已落地（补齐空转） | look + assert + 扫描 |
| D3 ask + inquiry | 27 | 已落地 | ask 组 |
| D4 say + on_hear_say | 28 | 已落地 | say 组；事件细节见单元测 |
| D5 Chatter + 条件 | 29 | 已落地 | tick day/night |
| entities_in_room / 文案「说：」 | 34 / 35 | 已落地 | look / ask 间接覆盖 |

## 若矩阵失败

把 `just verify-npc` 里 ✖ 的步骤、实际输出、期望子串发回来，在验证分支修 + 补测。
