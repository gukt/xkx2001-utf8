# Session 笔记：Pre-M4 频道 / 物品 spawn / 任务（2026-07-22）

> 来源：架构师询问「多人频道 / 物品自动 spawn / 任务系统」是否已实现，并决定在进 M4 前补齐。  
> 用途：M3 停机加固整体完成后、进入 M4 之前，开 `/grill-with-docs` 的输入底稿。  
> 索引：[README.md](README.md)

## 1. 现状核对（实现与否）

| 能力 | 结论 |
|---|---|
| 多人世界 + 频道广播 | **未实现**。单机 CLI；仅有同房间 `room_say`。ADR-0008：单机阶段频道/登录不作为停机必做。 |
| NPC 被清后自动 spawn | **已有**（`SpawnerBlueprint` + `spawn_scan`，`respawn: true`）。 |
| 物品被捡走后自动 spawn | **没有**（地上物为加载期预设实体）。 |
| 任务系统 | **未实现**（仅有 `no_drop` / `on_get`/`on_drop` 等钩子占位；无 Quest 状态机）。 |

## 2. 拍板结论（本 session 已达成）

1. **总体策略**：**B** — 三条都做，但严格切片（不做成完整多人网游 / 通用任务引擎）。
2. **排期**：放在 **M3 停机加固整体完成之后、M4 之前**；独立 effort，不并入 hardening，不进 post-MVP backlog。
3. **流程**：加固关完后 `/grill-with-docs` → `/to-spec` → `/to-tickets` → `/implement`；**不用** `/wayfinder`；**不要**直接 `/implement`。
4. **与房间保真**：同属 Pre-M4；**建议本批优先于** [pre-m4-engine-room-fidelity](../pre-m4-engine-room-fidelity/)（机制缺口先于房间表达力）；最终顺序 grill 时可再确认。
5. **文档落盘**：本目录 + 根目录 [PROGRESS.md](../../PROGRESS.md) Next Up / Done；[CONTEXT.md](../../CONTEXT.md) 增加词条。

### 2.1 假多人 + 频道 — 选 **A**

- 验收面：测试 / 脚本 seam，同一 `World` 挂两个 `PlayerSession`。
- 能力：互听同房间 `say`；1～2 个频道（候选名 grill 时钉死，如 `chat` / `rumor`）推给订阅者。
- **不改**现有单玩家 REPL 体验作为本波验收标准（演示 CLI / 联网客户端显式 OOS 或后置）。
- 明确不做：独立登录会话层、多进程、TCP/WebSocket 客户端（除非后续另开票）。

### 2.2 物品自动 spawn + 放置模型（2026-07-22 grill 改判）

- **计数（对齐侠客行 `reset`）**：按登记槽位记住实例；对象仍存在（背包/别房也算）占名额；`get`/`drop` **不**产生缺口；仅销毁后且 `respawn: true` 才补。
- **放置（选 C，重要）**：房间中心 `objects`（模板键 → 数量）；**弃用** `placed_in` / `in_room`；本 effort 落地迁移官方/示例场景与加载器。见 [ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md)。
- **与房间保真**：原「放置是否改 objects」议程**迁出并收口**；[.scratch/pre-m4-engine-room-fidelity/](../pre-m4-engine-room-fidelity/) 不得重开。
- 底稿曾写「对齐 NPC `count`/`respawn` + 离开地面即缺口」——计数缺口语义以本段为准；放置以 ADR-0010 为准。

### 2.3 任务 — 选 **B**（grill 钉死后）

- 声明式最小任务表：YAML `quests.<id>`（接取条件、完成条件、奖励）。
- 引擎：旗标 + 给物 / 给钱状态机；**不做**脚本沙箱 / 通用对话树任务引擎。
- **接取**：`quest accept <id>`（可要求同房某 NPC）；`ask` 保持纯文案，不接任务（有意偏离 LPC `ask … about 工作` 手感）。
- **完成条件最小集**：交物 + 旗标；到房只作前置，不单列为完成类型。
- **官方挂景（1 条）**：`yangzhou_biaoju` 镖头同房接取 → 华山 `huashan_guide` 向导处 `give` 交货领赏。
- 玩家侧：可序列化的 `flags`（或等价组件）进存档。

## 3. Out of Scope（本 effort 默认不做）

- 真实联网多人、账号登录、防刷屏完整运营策略（可留钩子，不要求本波齐）。
- 留言板 / 异步公告（仍见 post-MVP backlog / ADR-0006）。
- 通用任务脚本、多步剧情 DSL、师门贡献整套。
- 房间风景 / `item_desc` / 语义色等（属房间保真 effort）。
- 把本批升格为 M3 停机门闩或改写「可诚实停机」定义。

## 4. Grill 必问清单

1. ~~频道~~ → **已决**：`chat` + `system`；显式 `chat <text>`；`system` 仅 API；默认订两者；无 `tune`。
2. ~~物品计数 / 丢回~~ → **已决**：槽位指针；见 §2.2。
3. ~~放置~~ → **已决 C**：[ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md)。
4. ~~任务接取~~ → **已决**：`quest accept <id>`；不经 `ask`。
5. ~~完成条件~~ → **已决**：交物 + 旗标。
6. ~~ADR-0008~~ → **已决 A**：修订追加澄清（已写入）。
7. ~~与房间保真顺序~~ → **已决 A**（本批优先）。
8. ~~官方示例挂景~~ → **已决 A**：龙门镖局 → 华山向导交货（1 条）。

**下一步**：shared understanding 与接缝已确认 → [spec.md](spec.md) 已发布 → `/to-tickets` → `/implement`。

## 5. 建议实现顺序（grill 后可调）

1. 物品 spawner（复用 `spawn_scan` 心智，风险最低）。
2. 玩家 `flags` + `quests` 声明式状态机 + 1 条示例任务。
3. 双 `PlayerSession` messaging 扩展 + 1～2 频道（可能依赖 / 推动 hardening `08` `messaging.py` 抽取已落地）。

## 6. 与 PROGRESS 的对接

- 本笔记落盘日写入 PROGRESS Done + Next Up（Pre-M4 队列两项：本批建议先于房间保真）。
- 加固 B3 未完成前本 effort **只排队、不开 grill/实现**。
