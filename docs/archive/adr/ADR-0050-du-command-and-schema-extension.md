# ADR-0050：du 研读命令 + ItemDef/QuestReward schema 扩展（demo 打磨）

- 状态：已通过（2026-07-15）
- 日期：2026-07-15
- 阶段：M3 收官后产品化收尾窗口（demo 打磨）
- 关联：[ADR-0043](ADR-0043-drink-command-initial-items-tea-block.md)（drink 命令接入惯例）/ [ADR-0049](ADR-0049-multi-opponent-select-and-key-system.md)（钥匙系统，C1 开锁链前置）/ [lx-jing.c](../../d/qilian/obj/lx-jing.c) do_study（LPC 规格源）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md)

## 背景

M3 收官后 §八 三问裁决=产品化收尾窗口（Q2 暂否，聚焦已迁移内容产品化）。demo 打磨 9 项（A1/B1/B2/B3/B5/C1/C2/C3/B4），其中 C3 du 命令是新命令接入 8 段管线 + ItemDef/QuestReward schema 扩展，C1/C2/B4 是内容填充 + quest reward 扩展，按 [ADR-0043](ADR-0043-drink-command-initial-items-tea-block.md)/[ADR-0044](ADR-0044-door-open-close-locked.md)/[ADR-0049](ADR-0049-multi-opponent-select-and-key-system.md) 命令接入惯例记本 ADR。小修复（A1 提示引号 / B1 起始房间 / B2 alias / B3 combat_exp 便利 / B5 quest 列出）非功能决策，不展开。

调研发现：[lx-jing.c](../../d/qilian/obj/lx-jing.c) 是可研读经书（`do_study`/`do_du`），持经书 + `class=lama` + potential -> `improve_skill("longxiang-banruo", random(int*3/2))`。greenfield 无 `du`/`study` 命令，skills.yaml 注释"practice 所需经书"是误标（实际是 du 研读，非 practice 检查）。

## 决策

### 1. du/study 研读命令（对照 LPC lx-jing.c do_study）

`du|study <经书>` 命令（[commands.py](../../engine/src/xkx/runtime/commands.py) `du` + `_adapter_du` + COMMAND_REGISTRY `"du"`/`"study"`）：

- 检查持有经书（`_resolve_item_id` in inv）+ 经书 `read_skill` 非空 + `class=lama`（kneel 后）+ `potential>=1` + `jing>=cost`（`1500/int`）+ 非 busy/fighting
- `improve_skill(read_skill, random(int*3/2))` + 扣 jing + 扣 potential
- 对照 [lx-jing.c:24](../../d/qilian/obj/lx-jing.c) `do_study`（`random(int*3/2)` + `receive_damage(jing, 1500/int)` + `potential-1`）
- 简化（后置）：literate 门控 / `lamaism>=150` 门控后置（demo 无门槛或 class=lama 即可）

### 2. ItemDef schema 扩展（read_skill + qi_recover）

[ItemDef](../../engine/src/xkx/dsl/layer0.py) 加两字段：

- `read_skill: str = ""`：非空 = 可 du 研读，加该技能（lx-jing/fojing = `longxiang-banruo`）
- `qi_recover: int = 0`：drink 恢复气（`min(max_qi, qi+recover)`，对照丹药；drink 命令加 qi_recover 分支）

`model_dump` 透传到 `item_registry` dict，du/drink 用 `spec.get` 读（同 drink_supply 机制）。

### 3. QuestReward schema 扩展（potential）

[QuestReward](../../engine/src/xkx/dsl/layer0.py) 加 `potential: int = 0`：完成任务奖潜能（`min(max_potential)`）。`_complete_quest` 加 potential 分支。B4 kill 野狼 quest reward `potential: 50`。

### 4. C1 藏经阁填充（般若经 + 取经 quest）

- [items.yaml](../../engine/scenes/xueshan_micro/items.yaml) 加 `xueshan/obj/fojing`（般若经，`read_skill=longxiang-banruo`，对照 LPC [fojing4.c](../../d/xueshan/obj/fojing4.c)）
- [rooms.yaml](../../engine/scenes/xueshan_micro/rooms.yaml) `cangjing` 加 `items: [fojing]`
- [quests.yaml](../../engine/scenes/xueshan_micro/quests.yaml) 加 `xueshan/quest/cangjing`（giver 拉章，trigger 藏经阁，`reach_room cangjing`，reward exp 300）
- 链路：长廊 take 铁钥匙 -> 大殿 `unlock north` -> 藏经阁 reach + take 般若经 -> du 研读

### 5. C2 密室填充（雪莲丹 + drink qi）

- [items.yaml](../../engine/scenes/xueshan_micro/items.yaml) 加 `xueshan/obj/dan`（雪莲丹，`qi_recover=150` + `jing_recover=100`）
- [rooms.yaml](../../engine/scenes/xueshan_micro/rooms.yaml) `mishi` 加 `items: [dan]`
- [cli.py](../../engine/src/xkx/cli.py) 补 drink 分支（原 drink 仅 WS COMMAND_REGISTRY，CLI 未接；C2 顺带补全 demo drink 闭环）
- 链路：忘忧谷 `open north` 铁门 -> 密室 take 雪莲丹 -> drink 恢复气+精

### 6. B4 kill 野狼 quest（新手可达目标）

- [quests.yaml](../../engine/scenes/xueshan_micro/quests.yaml) 加 `xueshan/quest/wolf`（giver 葛伦布，trigger 野狼，`kill_npc yelang`，reward exp 200 + potential 50）
- `advance_combat` 已支持 `kill_npc` objective（[ADR-0049](ADR-0049-multi-opponent-select-and-key-system.md) 前置）
- 达尔巴"引见金轮法王"保持高阶（不降难度，保 LPC 规格），野狼 quest 提供新手可达短期目标 + 攒 exp/potential 途径

## 不做（范围边界）

- **literate / `lamaism>=150` 门控**：[lx-jing.c:31](../../d/qilian/obj/lx-jing.c)/:39 门控后置（demo 无 literate，lamaism 门槛对新手过高）
- **A1/B1/B2/B3/B5 小修复**：fight 提示引号 / 起始 dshanlu / NPC 中文 alias / combat_exp 便利 / quest 列出 -- 非功能决策，不展开
- **lx-jing 钥匙折断 / `longxiang>200` 额外消耗**：后置
- **不修改 LPC 源**（只读规格）

## 不变量

- **Command 仅外部意图**：du 是玩家外部意图，走 COMMAND_REGISTRY（8 段管线）+ cli parse_and_run；System tick 派生变更不经 Command
- **题材包数据**：经书/quest/物品在 CPK yaml（scenes/xueshan_micro/），引擎不硬编码武侠语义
- **combat 确定性范围=combat-only**：du 的 `random(int*3/2)` 是练功系统 RNG（同 learn），非 combat 范围，不纳入 combat seed
- **存储/序列化**：read_skill/qi_recover/potential 是 ItemDef/QuestReward 定义字段，`model_dump` 序列化（CPK yaml 定义，非运行态，不进存档）

## 产出位置

- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py)：`du` + `_adapter_du` + COMMAND_REGISTRY `"du"`/`"study"` + drink qi_recover 分支 + `_complete_quest` potential 分支
- [dsl/layer0.py](../../engine/src/xkx/dsl/layer0.py)：ItemDef `read_skill`/`qi_recover` + QuestReward `potential`
- [cli.py](../../engine/src/xkx/cli.py)：du/drink 分支 + help 文本
- [scenes/xueshan_micro/items.yaml](../../engine/scenes/xueshan_micro/items.yaml)：lx-jing read_skill + fojing + dan
- [scenes/xueshan_micro/rooms.yaml](../../engine/scenes/xueshan_micro/rooms.yaml)：cangjing/mishi items
- [scenes/xueshan_micro/quests.yaml](../../engine/scenes/xueshan_micro/quests.yaml)：cangjing/wolf quest
- [tests/test_xueshan_e2e.py](../../engine/tests/test_xueshan_e2e.py)：du×2 + cangjing + mishi + wolf 测试

## 关联

- [ADR-0043](ADR-0043-drink-command-initial-items-tea-block.md)（drink 命令接入惯例）
- [ADR-0049](ADR-0049-multi-opponent-select-and-key-system.md)（钥匙系统，C1 开锁链前置）
- [lx-jing.c](../../d/qilian/obj/lx-jing.c) `do_study` / [fojing4.c](../../d/xueshan/obj/fojing4.c)（LPC 规格源）
