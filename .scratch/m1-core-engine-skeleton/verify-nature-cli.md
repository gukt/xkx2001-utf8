# M1 Nature 时辰 / 天气手测 · 一键矩阵

> 范围：块 B（B1–B5）+ 块 A2 条件求值器（Nature 查询源）  
> 对照调研：[research/03-nature.md](research/03-nature.md)、[research-m1-extension-items-npc-nature.md](research-m1-extension-items-npc-nature.md)  
> 不含：季节 / 随机自然事件 / 天气机制影响 / 门 `open_when` demo / NPC 作息（M2+ 或调研「可做」未拍板）

## 推荐：一键矩阵（免手动敲命令）

仓库根执行：

```bash
just verify-nature
```

会用 fresh 默认场景跑相位 / look / 广播 / 天气 / 谓词矩阵，打印每条输出与 ✔ / ✖，末尾给场景级摘要。  
实现：[engine/scripts/verify_m1_nature.py](../../engine/scripts/verify_m1_nature.py)（pytest：`tests/test_verify_m1_nature_matrix.py`）。

不读、不写 `engine/save`。

单元测细节（时钟对齐、restore 重挂、多相位 tick 等）见 [`engine/tests/test_nature.py`](../../engine/tests/test_nature.py)。

## 可选：手动 `just run`

需要自己摸手感或调试单条命令时再用。

1. **先清存档**（否则可能恢复旧档）：

```bash
rm -rf engine/save
just run
```

2. 起始在**起始庭院**（`outdoors: true`）。每输入一条命令推进 1 tick（≈ 1 游戏分钟），户外可能收到时辰切换广播。

## 场景夹具（默认 YAML）

| 房间 | outdoors | 用途 |
|---|---|---|
| `start_yard` 起始庭院 | true | 户外 look / 广播 |
| `corridor` 长廊 | false | 室内不拼 Nature 文案、不收户外广播 |
| 顶层 `nature.day_phases` | — | dawn/day/dusk/night + `rain_desc_msg` |

## 1. 挂载与相位序列（B1）

| # | 检查 | 期望要点 |
|---|---|---|
| 1 | 加载默认场景 | `world.nature` 非空 |
| 2 | 相位名序列 | `dawn` → `day` → `dusk` → `night`（与 YAML 一致） |

## 2. 户外 look × 时辰（B3）

矩阵用 `_set_phase` 固定相位（不依赖墙钟等待）。

| # | 相位 | 输入 | 期望要点 |
|---|---|---|---|
| 1 | day | `look` | 含「日正当空，天色晴朗。」 |
| 2 | night | `look` | 含「夜深了，四下一片寂静。」；**无**白天文案 |

## 3. 室内不拼 Nature（B3）

| # | 输入 | 期望要点 |
|---|---|---|
| 1 | `n` | 进入长廊 |
| 2 | `look` | **无**时辰/天气 desc（如「日正当空」「夜雨潇潇」） |

## 4. 相位切换广播（B4）

矩阵把 `elapsed` 推到相界再 `TickLoop.advance`（与单元测 seam 一致）。

| 条件 | 期望 |
|---|---|
| 玩家在户外（庭院） | `pending_messages` 含对应 `time_msg`（如 dawn→day：「天光大亮。」） |
| 玩家在室内（长廊） | 同 tick **无**户外广播文案 |

## 5. 天气二维文案 + 切换（B5）

| # | 检查 | 期望要点 |
|---|---|---|
| 1 | `phase=dawn` + 强制下雨 + `look` | 含 `rain_desc_msg`：「东方微曦，细雨蒙蒙。」 |
| 2 | `weather_change_chance=1` + 确定性 rng + tick | 广播「天阴了下来，下起了雨。」或「雨停了，天空放晴。」；`is_raining` 翻转 |

## 6. 谓词 / 条件求值器（B2 + A2）

对 `world.nature` 直接 `evaluate(...)`（矩阵内断言，与 `TestQueryPredicates` 同源）：

| 相位 | `is_night` | `is_day` | `phase == dawn` |
|---|---|---|---|
| dawn | true | false | true |
| day | false | true | false |
| night | true | false | false |

`game_time_str` 在 day 相位应含「白天」。

## 7. 短回归（旁证）

| 条件 | 期望 |
|---|---|
| `phase=night` + tick（Chatter） | 出现「夜猫子说：夜深了，该歇歇了。」（Nature `is_night` 驱动；完整 NPC 矩阵见 `just verify-npc`） |

## 预期缺失（不当 bug）

- 季节 / 随机自然事件 / 天气对移动·战斗·视野的机械影响
- NPC 作息（除 Chatter `when: is_night` 外无统一作息）
- 门 `open_when` Nature 条件 demo（调研可做、未进 B1–B5）
- 房间级 `nature_desc` 覆盖表（DSL 草稿）
- 多玩家 per-session 消息桶（M1 单玩家 `pending_messages` 扁平 list）
- Nature 时间状态不进存档（重启对齐墙钟，属设计）

## 完成度摘要（验证时点）

| 调研项 | 票 | 代码 | CLI 矩阵 |
|---|---|---|---|
| B1 时辰循环 | 13 | 已落地 | 挂载 + 相位序列 |
| B2 结构化谓词 | 14 | 已落地 | evaluate 组 |
| B3 户外 look | 15 | 已落地 | look 户外/室内 |
| B4 相位广播 | 16 | 已落地 | tick + pending_messages |
| B5 晴雨骨架 | 17 | 已落地 | 雨 look + 天气切换 |
| A2 条件求值器 | 10 | 已落地 | evaluate 组（Nature 作 context） |

## 若矩阵失败

把 `just verify-nature` 里 ✖ 的步骤、实际输出、期望子串发回来，在验证分支修 + 补测。
