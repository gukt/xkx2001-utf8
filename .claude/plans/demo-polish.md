# Demo 打磨实施计划（产品化收尾窗口）

> 分支：`feat/stage-3-techdebt-r3` | 基线：1807 tests 全绿 | LPC 规格源只读参考
> 方向：M3 收官后产品化收尾窗口（Q2 暂否，聚焦已迁移内容产品化）。用户全选 4 包 9 项。

## 范围（用户已确认全选）

| 包 | 项 | 一句话 |
|---|---|---|
| 快速修复 | A1 | fight:571 提示缺闭合引号 `」` |
| 快速修复 | B1 | 起始房间山门卡门，改 dshanlu + 葛伦布引导消息 |
| 快速修复 | B5 | quest 全局列 6 任务，改只列 in_progress + 可接提示 |
| 内容填充 | C1 | 藏经阁开锁后空，放经书 + 取经 quest |
| 内容填充 | C2 | 密室空，放丹药宝物 |
| 内容填充 | C3 | lx-jing 经书用途未接通，加 du/study 研读命令（对照 LPC lx-jing.c do_study） |
| 练功引导 | B3 | combat_exp 500 门控卡练功，cli 给 5000 便利 + learn 提示引导 |
| 练功引导 | B2 | NPC 中文简称匹配不到，长名 NPC 加中文短 alias |
| 难度曲线 | B4 | 达尔巴新手不可达，加新手 kill 野狼 quest，达尔巴保持高阶 |

## 逐项方案

### A1. fight 提示缺 」
- 文件：[commands.py:571](engine/src/xkx/runtime/commands.py#L571)
- 改：`f"这里没有「{target_name}。"` -> `f"这里没有「{target_name}」。"`（其他 kill/ask/bai/learn 均正确，仅 fight 漏 」）
- 测试：test_commands 或 test_xueshan_e2e 加 `fight` 找不到 NPC 断言输出含 `」`

### B1. 起始房间 + 卡门引导
- 文件：[theme.py:77](engine/src/xkx/runtime/theme.py#L77) `start_room="xueshan/shanmen"` -> `"xueshan/dshanlu"`
- 文件：[rules.yaml](engine/scenes/xueshan_micro/rules.yaml) `xueshan_shanmen_guard.message` 改引导性：`葛伦布挡住你说：要进寺供奉佛爷，先去东边山路（eastdown）取一罐酥油来。`
- 依据：cli.py `load_game` 用 `theme_config.start_room`；e2e 测试自传 `start_room` 不读 theme_config，不受影响（已核实 test_xueshan_e2e `_game(start_room=...)`）
- 效果：玩家从山路起步，酥油在脚下，捡了 `wu` 到山门 ask 葛伦布，避免一进门卡门
- 测试：加 cli smoke（`load_game` 后玩家在 dshanlu）

### B5. quest 只列 in_progress
- 文件：[commands.py quest()](engine/src/xkx/runtime/commands.py#L725) 725-746
- 改：无参时只列 `status != "not_started"`（in_progress/completed 详细），末尾加一行 `可接任务 N 个，向 NPC 打听接取（如 ask 葛伦布 about 还愿）`；`quest <id>` 带参查单个保留
- 测试：改 [test_quest.py:65](engine/tests/test_quest.py#L65) `test_quest_list_and_status`（先 `ask 葛伦布 还愿` 接任务，再 `quest` 断言 in_progress 列出 + 可接提示）+ 新增"无进行中任务时显示可接提示"测试

### B2. NPC 中文短 alias
- 文件：[npcs.yaml](engine/scenes/xueshan_micro/npcs.yaml)
- 长名 NPC aliases 加中文短名：昌齐大喇嘛+`昌齐` / 萨木活佛+`萨木` / 嘉木活佛+`嘉木` / 拉章活佛+`拉章` / 灵智上人+`灵智` / 金轮法王+`金轮` / 鸠摩智+`鸠摩`
- 依据：`_find_npc_in_room` 精确匹配 name/aliases（忠实 LPC present），加中文短 alias 不破规格
- 测试：加 `_find_npc_in_room` 中文短 alias 匹配断言

### B3. combat_exp 门控引导
- 文件：[cli.py load_game](engine/src/xkx/cli.py#L122) 加 `prog.combat_exp = 5000`（同 potential=100 便利逻辑）
- 依据：longxiang-banruo 学到 30 需 `30³/10=2700 < exp`，给 5000 让学到 ~36，够拜萨木（门槛 30）；不动 [spawn_player](engine/src/xkx/runtime/world.py#L266) 默认 500（保 e2e）
- 文件：[commands.py:1380](engine/src/xkx/runtime/commands.py#L1380) `blocked_by_exp` 提示加引导：`你缺乏实战经验，无法领会这种武功（击败敌人可积累实战经验）。`
- 测试：cli smoke 验证初始 combat_exp 5000

### B4. 新手 kill 野狼 quest
- 文件：[quests.yaml](engine/scenes/xueshan_micro/quests.yaml) 加 `xueshan/quest/wolf`：giver `xueshan/npc/gelun1`，trigger `野狼`，objective `kill_npc xueshan/npc/yelang`，reward exp 200 + potential 50
- 依据：[advance_combat:514](engine/src/xkx/runtime/commands.py#L514) 已支持 `kill_npc` objective；野狼 exp200/qi40 弱，玩家 force30 可胜；野狼 aggressive 进忘忧谷即战，kill_npc 无论主动/被动致死均触发
- 达尔巴"引见金轮法王"保持高阶（不降难度，保 LPC 规格）
- 测试：加 kill_npc quest 完成 e2e（kill 野狼 -> quest completed + exp/potential）

### C1. 藏经阁填充（经书 + 取经 quest）
- 文件：[items.yaml](engine/scenes/xueshan_micro/items.yaml) 加 `xueshan/obj/fojing`（般若经，readable，read_skill=longxiang-banruo，对照 LPC [fojing4.c](d/xueshan/obj/fojing4.c)）
- 文件：[rooms.yaml](engine/scenes/xueshan_micro/rooms.yaml) `xueshan/cangjing` 加 `items: [xueshan/obj/fojing]`
- 文件：[quests.yaml](engine/scenes/xueshan_micro/quests.yaml) 加 `xueshan/quest/cangjing`：giver `xueshan/npc/lazhangfo`（诵经堂），trigger `藏经阁`，objective `reach_room xueshan/cangjing`，reward exp 300
- 链路：长廊 take 铁钥匙 -> 大殿 unlock north（铁锁门）-> 藏经阁 reach 完成 quest + take 般若经 -> du 研读
- 测试：加藏经阁开锁+取经+take 经书 e2e

### C2. 密室填充（丹药宝物）
- 文件：[items.yaml](engine/scenes/xueshan_micro/items.yaml) 加 `xueshan/obj/dan`（雪莲丹，consumable，drink_supply 恢复 qi+jing，对照 LPC 丹药）
- 文件：[rooms.yaml](engine/scenes/xueshan_micro/rooms.yaml) `xueshan/mishi` 加 `items: [xueshan/obj/dan]`
- 链路：忘忧谷 open north（铁门，非锁）-> 密室 take 雪莲丹 -> drink 恢复（探索奖励）
- 测试：加密室 open+take+drink e2e

### C3. du/study 研读命令
- 文件：[commands.py](engine/src/xkx/runtime/commands.py) 新增 `du`/`study` 命令（对照 LPC [lx-jing.c:24 do_study](d/qilian/obj/lx-jing.c#L24)）
- 逻辑：检查物品栏持经书 + 经书 `readable` + `class=lama`（kneel 后）+ `potential>=1` + `jing>=cost` + 非 busy/fighting -> `improve_skill(read_skill, random(int*3/2))` + 扣 jing(`1500/int`) + 扣 potential 1
- 简化（后置）：literate 门控、lamaism>=150 门控后置（demo 无门槛或 class=lama 即可）
- 文件：[items.yaml](engine/scenes/xueshan_micro/items.yaml) `lx-jing` + `fojing` 加 `readable: true` + `read_skill: longxiang-banruo`
- 文件：[skills.yaml](engine/scenes/xueshan_micro/skills.yaml) 修正 lx-jing 注释"practice 所需经书"->"du 研读加 longxiang-banruo"
- 文件：[cli.py](engine/src/xkx/cli.py) 注册 `du`/`study` + help 文本
- 测试：加 du 命令研读 e2e（持经书 + class=lama -> longxiang 提升 + 扣 potential/jing）

## 实施顺序（每步后 `just test` + `just lint`）

1. **A1**（1 行 bug，独立）
2. **B2**（npcs.yaml alias，独立低风险）
3. **B1**（theme.py start_room + rules.yaml 消息）
4. **B5**（quest 列出 + 改 test_quest）
5. **B3**（cli.py combat_exp + learn 提示）
6. **C3**（du 命令 + items readable + cli 注册，新命令）
7. **C1**（藏经阁 fojing + quest，依赖 C3 du）
8. **C2**（密室 dan）
9. **B4**（kill 野狼 quest）

## 文件改动清单

- `engine/src/xkx/runtime/commands.py` — A1, B5, B3 提示, C3 du 命令
- `engine/src/xkx/runtime/theme.py` — B1 start_room
- `engine/src/xkx/cli.py` — B3 combat_exp 便利, C3 du 注册+help, B1 smoke
- `engine/scenes/xueshan_micro/npcs.yaml` — B2 alias
- `engine/scenes/xueshan_micro/rooms.yaml` — C1 cangjing items, C2 mishi items
- `engine/scenes/xueshan_micro/items.yaml` — C1 fojing, C2 dan, C3 readable 字段
- `engine/scenes/xueshan_micro/quests.yaml` — C1 取经 quest, B4 kill 野狼 quest
- `engine/scenes/xueshan_micro/rules.yaml` — B1 葛伦布引导消息
- `engine/scenes/xueshan_micro/skills.yaml` — C3 修正注释
- `engine/tests/` — 各项回归 + 新测试（test_xueshan_e2e / test_quest / test_commands / 新 test_cli_smoke）

## 风险与边界

- **B1 start_room**：只影响 cli.py demo，e2e 不受影响（已核实）。改 dshanlu 改变入口语义但 demo 便利优先。
- **B5 quest**：破 test_quest_list_and_status，同步改测试（已识别）。
- **B3 combat_exp 5000**：玩家变强 vs 弱怪，但不影响 e2e（spawn_player 不动）。达尔巴 250000 仍远强，难度曲线不变。
- **C3 du 命令**：新命令接入 cli + COMMAND_REGISTRY，对照 LPC lx-jing.c。门控简化后置（literate/lamaism>=150）。
- **B4 野狼 aggressive**：进忘忧谷即战，玩家 force30 vs 野狼 qi40 可胜；kill_npc objective 无论主动/被动致死均触发。
- **不偏离架构基线**：均为 demo 体验/内容/小 bug，不需要新 ADR（C3 du 命令在 commit message 注明对照 LPC）。
- **不碰**：pilot 被测环节（人工工时红线）、berserk（语义裁决待用户）、动态 exit/SMASHED（无动手价值）。

## 验收

- `just test` 全绿（1807 + 新增 ~12-15 测试）
- `just lint` 全过
- cli demo 跑通完整循环：起步 dshanlu -> 捡酥油 -> 供奉过门 -> bai 昌齐/kneel -> learn+du longxiang -> 拜萨木 -> kill 野狼 quest -> 开锁取藏经阁般若经 -> 探密室雪莲丹
- 更新 PROGRESS.md（Done + 可玩 demo 描述）
