# 技术债补缺口第 3 轮实施计划

> 分支：`feat/stage-3-techdebt-r3` | 基线：1782 tests 全绿 | LPC 规格源只读参考

## 范围（用户已确认）

7 子项，3 个 ADR。后置：多对手 select_opponent / berserk / 钥匙系统 / 动态 exit / SMASHED（LPC 死代码）。

| 类 | 子项 | ADR |
|---|---|---|
| C5 | open/close 命令 + LOCKED 位 | ADR-0044 |
| C4 | drink 命令 + 厨房初始 buttertea + 持茶挡路 | ADR-0043 |
| B-2 | hatred（killer_ids）+ vendetta（标记式追杀） | ADR-0045 |

## 实施顺序（依赖 + 风险排序）

1. **阶段 1：C5 门扩展**（ADR-0044）-- 独立，低风险，纯增量
2. **阶段 2：C4 drink 闭环**（ADR-0043）-- 独立，低风险
3. **阶段 3：B-2 hatred + vendetta**（ADR-0045）-- 中风险，改战斗触发 + 死亡处理

每阶段：写代码 → `ruff check` → pytest → 写 ADR。阶段间不耦合，可独立提交。

---

## 阶段 1：C5 门扩展（ADR-0044）

### 1a. open/close 命令

**LPC 保真点**：标准 `cmds/std/open.c`+`close.c` 调 `room.open_door/close_door`，**无定时关门**；定时关只属于 knock（gate.c 模式）。两者语义不同，open 不复用 knock 的定时关。

**改动**：
- `runtime/doors.py`：抽出公开函数
  - `open_door(world, room_eid, direction) -> str | None`：开门（`closed=False` + `_sync_other_side`），**不 schedule 定时关**。无门/已开/锁着分别返回提示。
  - `close_door(world, room_eid, direction) -> str | None`：关门（`closed=True` + `_sync_other_side` + `_remove_door_close_effect` 取消未到期的定时关）。
  - `knock_door` 改为：调 `open_door` 开门 + schedule `door_close` EffectComp 定时关（保留 knock 独有的定时关语义）。
- `runtime/commands.py`：
  - `open(game, actor_id, direction)`：调 `open_door`。locked 门提示"门锁着，需要钥匙"（钥匙系统后置，但 locked 检查就位）。
  - `close(game, actor_id, direction)`：调 `close_door`。
  - `_adapter_open`/`_adapter_close` + COMMAND_REGISTRY 注册 `"open"`/`"close"`。
  - `go` 挡路提示：`{door.name}关着，也许敲一敲(knock)或打开(open)会开。`（同时提示两动词）。

### 1b. LOCKED 位

**LPC 发现**：`DOOR_LOCKED`/`DOOR_SMASHED` 在全仓库是死代码（定义于 `include/room.h:5-7` 但无任何代码 set/check）。SMASHED 跳过（凭空发明规格）。LOCKED 加独立 bool 字段（非位掩码 int，可读性 + 类型安全 + 序列化简单）。

**改动**：
- `runtime/components.py`：`DoorEntry` 加 `locked: bool = False`。
- `dsl/layer0.py`：`DoorDef` 加 `locked: bool = False`。
- `runtime/world.py`：`build_world` 构造 DoorEntry 时透传 `locked=spec.get("locked", False)`（:114-122）。
- `dsl/ir.py`：`compile_room` model_dump 自动透传（验证无需改）。
- `open` 命令检查 `door.locked`（见 1a）。
- `look`/`_dir_label`：locked 门标注（如 `west(铁门锁关)`），可选。

### 测试（test_doors.py 扩展）
- `test_open_command_opens_door`：open 开门 + go 通过
- `test_close_command_closes_door`：close 关门 + go 再挡路
- `test_open_no_timer`：open 开门后推进 tick，门不自动关（对照 knock 的定时关，验证语义差异）
- `test_knock_still_has_timer`：knock 开门后推进 tick，门自动关（不回归）
- `test_locked_door_blocks_open`：locked 门 open 提示需钥匙，go 仍挡路

---

## 阶段 2：C4 drink 闭环（ADR-0043）

### 2a. drink 命令（通用）

**LPC 语义**（`d/xueshan/obj/buttertea.c:33-96` do_drink）：恢复 water+50/food+30/jing+5（clamp eff_jing），remaining=3 多次饮用，fighting 时 start_busy(2)。

**改动**：
- `dsl/layer0.py`：`ItemDef` 加 consumable 字段（默认 0 = 不可饮用）：
  - `drink_supply: int = 0` / `food_supply: int = 0` / `jing_recover: int = 0`
- `scenes/xueshan_micro/items.yaml`：buttertea 加 `drink_supply: 50` / `food_supply: 30` / `jing_recover: 5`
- `runtime/commands.py`：
  - `_resolve_item_id` 扩展支持 aliases（当前只匹配精确 id/中文名，与 `_find_npc_in_room` 不对称；drink tea 解析有 gap）。修复同时惠及 take/give（需回归）。
  - `drink(game, actor_id, item_query)`：resolve item → 查 consumable（全 0 则拒"这东西不能喝"）→ `is_busy` 拒 → `vitals.water += drink_supply` / `vitals.food += food_supply` / `vitals.jing = min(eff_jing, jing + jing_recover)` → 从 Inventory 移除（set 语义，喝一次消失）。
  - `_adapter_drink` + COMMAND_REGISTRY 注册 `"drink"`。
- item_registry 携带 consumable：`cli.py` 构建 item_registry 处扩展（drink 命令需查 consumable 数据；具体存 `{id: ItemDef}` 或 `{id: {name, consumable...}}` 实施时定，倾向存完整 ItemDef 供 drink 查询）。

**简化（记 GAP）**：remaining 多次饮用（set 语义喝一次消失，对齐 ADR-0040 set 语义）/ water 上限检查（无 max_water 字段）/ fighting start_busy(2) / value 清零（无 value 字段）。

### 2b. 厨房初始 buttertea

**LPC**（`d/xueshan/chufang.c:18-21`）：`set("objects", buttertea:3)` 初始 3 杯。

**改动**：`scenes/xueshan_micro/rooms.yaml`：`xueshan/chufang` 加 `items: [buttertea]`（1 杯，set 语义简化，3 杯数量后置需扩 RoomComp.items 为 dict）。

### 2c. 厨房 valid_leave 持茶挡路

**LPC**（`d/xueshan/chufang.c:28-36`）：`valid_leave` west + `present("tea", me)` 挡路"别着急，喝完茶再走！"。

**改动**：`scenes/xueshan_micro/rules.yaml` 加规则（**零代码**，layer1 `has_item` 谓词已支持）：
```yaml
- id: xueshan_chufang_tea_block
  event: valid_leave
  dir: west
  condition: {kind: has_item, item_id: buttertea}
  action: deny
  message: 别着急，喝完茶再走！
```

### 测试（test_xueshan_e2e.py 扩展）
- drink 闭环：take buttertea → drink 恢复 jing/water/food + 物品消失
- drink 不可饮用物品拒
- valid_leave 闭环：持茶 go west 被挡 → drink 喝完 → go west 放行
- `_resolve_item_id` aliases 扩展：take/give 用别名解析（回归）

---

## 阶段 3：B-2 hatred + vendetta（ADR-0045）

### 3a. hatred（killer_ids，重入房间重触）

**LPC 语义**（`feature/attack.c`）：`killer` 数组 = NPC"要杀到死的目标"。`kill_ob` 写 killer（fight_ob 不写）。`init()` 优先级最高：`is_killing(player.id)` → hatred。`remove_enemy` 检查 `is_killing` 拒移除 killer 目标（逃离后记忆保留）。`die()` 清 killer。"跨房间追杀"实相是 pursuer+random_move 重遇触发（NPC AI 范畴，后置）；greenfield 做"重入房间重触"。

**改动**：
- `runtime/components.py`：`CombatState` 加 `killer_ids: list[int] = field(default_factory=list)`。
- `runtime/auto_fight.py`：`initiate_combat(..., to_death=True)` 时**双向**加 killer_ids（attacker.killer_ids 加 target，target.killer_ids 加 attacker）；`to_death=False`（fight 模式）不写（对齐 LPC fight_ob 不写 killer）。
- `runtime/commands.py`：`_trigger_room_enter_fight` 扩展为遍历房间**所有** NPC（不限 aggressive），三触发优先级（对齐 LPC init() if-else）：
  1. **hatred**：`player_id in npc.killer_ids` → `auto_fight(npc, player, HATRED)`
  2. **vendetta**：`npc.vendetta_mark` 且 player 有 `vendetta:<mark>` flag → `auto_fight(npc, player, VENDETTA)`
  3. **aggressive**：`npc.attitude == "aggressive"` → `auto_fight(npc, player, AGGRESSIVE)`（现有逻辑）
  - 每个 NPC 只触发其一（elif 链，对齐 LPC 优先级）。auto_fight 内 `looking_for_trouble` 防重入 + `is_fighting` 防御检查保留。
- `runtime/auto_fight.py`：注册 `hatred_start_fight_handler` → `initiate_combat(to_death=True)`（与 aggressive handler 实质相同）。
- `cli.py`：`load_game` 注册 HATRED handler（对齐现有 AGGRESSIVE handler 注册）。

**不变量**：hatred 触发在 `go` Command 内（玩家意图驱动的移动事件），非 System tick；建敌对关系后持续攻击由 CombatBridge tick 驱动（ADR-0039）。符合"Command 仅外部意图，System tick 派生变更"。

### 3b. vendetta（标记式追杀，非门派世仇）

**LPC 语义**（`combatd.c:1091-1092` killer_reward + `attack.c:250-253` init）：杀有 `vendetta_mark` 的 NPC → 击杀者获 `vendetta/<mark>` 标记；带标记者遇同类 NPC → vendetta 触发。`death_penalty`（combatd.c:1017）玩家死亡清所有 vendetta 标记。

**改动**：
- `dsl/layer0.py`：`NpcDef` 加 `vendetta_mark: str = ""`。
- `runtime/components.py`：`NpcBehavior` 加 `vendetta_mark: str = ""`。
- `runtime/world.py`：`_spawn_npc` 构造 NpcBehavior 透传 `vendetta_mark=n.get("vendetta_mark", "")`（:200-209）。
- 玩家 vendetta 标记存 `Marks.flags`（如 `"vendetta:authority"`），复用 set[str]，无需新组件。
- `runtime/commands.py`：
  - `_handle_npc_death` 扩展：NPC 有 `vendetta_mark` → 给 killer 设 `vendetta:<mark>` flag（对齐 killer_reward）。
  - `_trigger_room_enter_fight` vendetta 分支（见 3a）。
  - 玩家死亡清 vendetta 标记：`_handle_player_death` 或 `die()` 清所有 `vendetta:*` flags（对齐 death_penalty）。
- `runtime/auto_fight.py`：注册 `vendetta_start_fight_handler` → `initiate_combat(to_death=True)`。
- `cli.py`：`load_game` 注册 VENDETTA handler。
- `scenes/xueshan_micro/npcs.yaml`：加 vendetta 验证场景（2 个同 `vendetta_mark` 的 NPC，如 `xueshan/guard_a`/`guard_b`，杀一个获标记后遇另一个触发；或复用现有 NPC 设 vendetta_mark）。

### 测试（新 test_auto_fight_triggers.py 或 test_xueshan_e2e.py 扩展）
- hatred：玩家 kill NPC（to_death）→ flee → 重入房间 → NPC hatred 重触攻击（killer_ids 保留）；fight 模式（to_death=False）不写 killer，重入不触发 hatred
- vendetta：杀 vendetta_mark NPC → 玩家获 `vendetta:<mark>` flag → 进另一同类 NPC 房间 → vendetta 触发；玩家死亡清 vendetta 标记
- 三触发优先级：同 NPC 同时满足 hatred+vendetta+aggressive 时走 hatred（elif 链）
- 回归：现有 aggressive e2e（yelang）不回归

---

## 风险与回归

- **`_resolve_item_id` 扩 aliases**（C4）：影响 take/give 既有 e2e，需回归。aliases 扩展是修复不对称 gap，行为更宽松（多匹配别名），既有用 id/中文名的测试不受影响。
- **CombatState 加 killer_ids**（B-2）：影响所有战斗路径。killer_ids 默认空 list，向后兼容；initiate_combat 双向加 killer 仅 to_death 模式，fight 模式不变。需回归 kill/fight/aggressive 测试。
- **多对手后置的已知限制**：`advance_combat` 仍硬编码 `enemy_ids[0]`。hatred/vendetta 触发多敌对关系时只打首个（多对手 select_opponent 后置，记 GAP）。战斗结束判定仍看 enemy_ids[0] 死亡。
- **combat 确定性**：hatred/vendetta 触发在 go Command（外部意图），不涉及 combat seed（多对手的 random select 才涉及，后置）。无确定性不变量冲突。
- **序列化**（ADR-0022）：CombatState.killer_ids（list[int]）、DoorEntry.locked（bool）、NpcBehavior.vendetta_mark（str）全基本类型，可序列化。NPC 实体的 killer_ids 随实体存在（NPC 死亡实体移除，killer 自然消失，对齐 LPC die() 清 killer）。

## 验证与收尾

- 每阶段 `cd engine && ruff check src tests` + `cd engine && PYTHONPATH=src python -m pytest`（无 .venv，pyenv python3.12）。
- 收尾全量 pytest（基线 1782，目标 +N 全绿）。
- 可玩 demo：CLI `python -m xkx.cli` 验证 drink 闭环 + open/close 门 + hatred/vendetta 触发。
- ADR：ADR-0043（C4）/ ADR-0044（C5）/ ADR-0045（B-2），命名递增，关联 05 dissent。
- PROGRESS.md：Done 加本轮（7 子项 + 3 ADR + tests 数）；已知技术债更新（多对手/berserk/钥匙/动态exit/SMASHED 仍后置）；归档纪律（Done 单条 ≤2 行）。
