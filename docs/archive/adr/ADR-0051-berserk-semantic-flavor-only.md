# ADR-0051：berserk 语义裁决=忠实 LPC flavor（look 邪派 NPC 不战斗）

- 状态：已通过（2026-07-15）
- 日期：2026-07-15
- 阶段：M3 收官后产品化收尾窗口（berserk 语义裁决）
- 关联：[ADR-0049](ADR-0049-multi-opponent-select-and-key-system.md) §不做（berserk 需单独 ADR 裁决）/ [look.c:189-193](../../cmds/std/look.c)（LPC 触发源）/ [combatd.c:869-902](../../adm/daemons/combatd.c) start_berserk（!userp 早退）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) Q3

## 背景

[ADR-0049](ADR-0049-multi-opponent-select-and-key-system.md) §不做 将 berserk 后置，标注"做成 NPC 第四触发是对 LPC 规格的有意偏离，需单独 ADR 裁决语义"。本轮裁决 berserk 语义。

**LPC 规格调研**（[look.c:189-193](../../cmds/std/look.c) + [combatd.c:869-902](../../adm/daemons/combatd.c)）：

- 玩家 `look <target>`（邪派 NPC，条件 `random(-obj.shen) > me.int*10`）-> 输出"突然转过头来瞪你一眼" + `auto_fight(NPC, 玩家, "berserk")`
- `auto_fight` -> `start_berserk(me=NPC, obj=玩家)`：[combatd.c:886](../../adm/daemons/combatd.c) 输出"用一种异样的眼神扫视著在场的每一个人" flavor -> [888](../../adm/daemons/combatd.c) `if (!userp(me) || ...)` 早退 -> **不 kill/fight**
- 即 LPC 忠实下，`look` 邪派 NPC = 双重 flavor（瞪眼+扫视），**无战斗**。berserk 真正的 kill/fight 只对邪派**玩家** me（PVP，单机无其他玩家，且玩家 look 自己不触发 `obj!=me`）

**结论**：忠实 LPC 则单机 demo `look` 邪派 NPC 仅 flavor，无法触发战斗。

## 决策

**忠实 LPC flavor**：补 `look <target>`（NPC 详情）+ 邪派 NPC（shen 负）被 look 时输出"瞪眼+异样眼神扫视"flavor，**不战斗**（忠实 `!userp` 早退）。

### 1. look <target> 命令（NPC 详情 + berserk flavor）

[look](../../engine/src/xkx/runtime/commands.py) 加 `target_name` 参数 + `_look_target` 辅助：

- 无参：房间视图（现有，不变）
- `look <target>`：找房间内 NPC -> 显示详情（名字/别名/性别/年龄/手持/气）+ 邪派 berserk flavor
- berserk flavor 触发（对照 [look.c:189-193](../../cmds/std/look.c)）：`shen < 0 && random.randint(0, -shen-1) > int*10` -> "突然转过头来瞪你一眼" + "用一种异样的眼神扫视著在场的每一个人"
- **忠实不战斗**：对照 [combatd.c:888](../../adm/daemons/combatd.c) `!userp(me)` 早退，flavor 后不调 kill/fight

### 2. NpcDef.shen 字段 + spawn 透传

- [NpcDef](../../engine/src/xkx/dsl/layer0.py) 加 `shen: int = 0`（道德值，正=侠负=魔，对照 TitleComp.shen）
- [world.py](../../engine/src/xkx/runtime/world.py) spawn NPC：`TitleComp(shen=n.get("shen", 0))`（原默认 TitleComp() shen=0）

### 3. demo 邪派 NPC（金轮法王）

[npcs.yaml](../../engine/scenes/xueshan_micro/npcs.yaml) 金轮法王 `shen: -300`（邪派法王，look 触发 berserk flavor）。金轮法王在鹿野苑（peaceful，look 不战斗，忠实）。

## 不做（范围边界）

- **NPC 第四触发（偏离 LPC）**：让邪派 NPC 被看时主动战斗（偏离 `!userp` 早退）-- **不采纳**。需新 ADR 承认偏离 + quest_exp + berserk_start_fight_handler + 邪派 NPC 战斗场景，且违背保真原则。FightType.BERSERK 枚举已定义但 handler 不实现（保留枚举供未来偏离 ADR）。
- **berserk 战斗（PVP）**：邪派玩家 me 主动 kill/fight -- 单机无其他玩家，无法触发，后置。
- **quest_exp / literate / lamaism>=150 门控**：flavor 不需这些（门控属 start_berserk 战斗分支，flavor 早退前），后置。
- **look <target> NPC long 描述**：NpcDef 无 long 字段，详情用现有字段（性别/年龄/手持/气）拼；long 描述后置。
- **不修改 LPC 源**（只读规格）

## 不变量

- **LPC 规格源保真**：`!userp(me)` 早退忠实（NPC berserk 仅 flavor 不战斗），不偏离
- **Command 仅外部意图**：look 是玩家外部意图，走 COMMAND_REGISTRY（8 段管线）+ cli parse_and_run
- **题材包数据**：NPC shen 在 CPK yaml（npcs.yaml），引擎不硬编码武侠语义
- **combat 确定性范围=combat-only**：look berserk flavor 的 random 是命令路径 RNG（非 combat System），不纳入 combat seed（同 learn/du 命令路径随机）

## 产出位置

- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py)：`look` 加 target_name + `_look_target` + `_adapter_look` 透传 raw_args
- [dsl/layer0.py](../../engine/src/xkx/dsl/layer0.py)：NpcDef `shen`
- [runtime/world.py](../../engine/src/xkx/runtime/world.py)：spawn NPC `TitleComp(shen=...)`
- [cli.py](../../engine/src/xkx/cli.py)：look 分支透传 target + help 文本
- [scenes/xueshan_micro/npcs.yaml](../../engine/scenes/xueshan_micro/npcs.yaml)：金轮法王 shen: -300
- [tests/test_xueshan_e2e.py](../../engine/tests/test_xueshan_e2e.py)：look <target> 详情 + 邪派 berserk flavor 测试

## 关联

- [ADR-0049](ADR-0049-multi-opponent-select-and-key-system.md) §不做（berserk 后置项本 ADR 裁决）
- [look.c:189-193](../../cmds/std/look.c)（LPC berserk 触发源）/ [combatd.c:869-902](../../adm/daemons/combatd.c) start_berserk（!userp 早退）
