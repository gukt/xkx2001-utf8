Status: ready-for-agent

# Pre-M4：假多人 Channel + 房间 objects 放置/槽位补刷 + 声明式 Quest

> 依据：[CLAUDE.md](../../CLAUDE.md) Pre-M4 窗口；[CONTEXT.md](../../CONTEXT.md)「Channel」「房间 objects 放置」「Quest（声明式旗标任务）」「Pre-M4 频道/spawn/任务」；[ADR-0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md)（不做行为等价）；[ADR-0008](../../docs/adr/0008-single-player-channel-login-out-of-stop-scope.md)（停机门闩仍成立 + 2026-07-22 澄清：假多人 seam ≠ 登录/联网）；[ADR-0009](../../docs/adr/0009-single-process-single-world.md)；[ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md)（房间中心 `objects`，弃用 `placed_in`/`in_room`）；grill 底稿与快照 [session-notes-2026-07-22.md](session-notes-2026-07-22.md) / [grill-paused-2026-07-22.md](grill-paused-2026-07-22.md) / [research-channels-lpc-2026-07-22.md](research-channels-lpc-2026-07-22.md)；兄弟 effort [pre-m4-engine-room-fidelity](../pre-m4-engine-room-fidelity/)（**放置模型不在其 scope**）。
>
> **范围边界（供 `/to-tickets` 核对，不可扩大）**：
> - 同 World 双（及以上）`PlayerSession` **测试/脚本 seam** + 薄 Channel（本批仅 `chat` / `system`）。
> - 场景放置改为房间 `objects` + 物品/NPC 槽位补刷（LPC 式「登记对象还在即占名额」）。
> - YAML `quests.<id>` 旗标状态机；接取 `quest accept <id>`；完成条件 = 交物 + 旗标；官方 `m2_mvp_scene` 挂 **1** 条镖局→华山向导闭环。
> - **OOS**：真实联网/登录、`tune`、通用对话树/脚本任务、房间保真（风景/色等）、升格为停机门闩。见 Out of Scope。
> - 测试接缝已确认：**S1** 命令/会话面 · **S2** 场景加载+补刷扫描 · **S3** 官方场景闭环。

## Problem Statement

M3 停机加固（P0+B3）已完成，单机可玩内核与 UGC 加载契约可以诚实对外。但进入 M4 之前，三类机制缺口仍然刺眼：世界里只有同房 `room_say`，没有跨房、按订阅的 Channel，也无法在测试里挂两个 `PlayerSession` 验证「假多人」；物品仍是加载期一次性摆放，没有与侠客行 `reset` 同构的槽位补刷，且放置仍用实体自带的 `placed_in`/`in_room`，与即将统一的房间中心心智分裂；任务完全缺失，官方扬州镖局有房间与镖头却接不成活。若跳过本批直接做房间保真或滑入 M4，会把「机制洞」留在表达力与商业化之前，并迫使放置模型在兄弟 effort 里二次搬家。

## Solution

在 M4 之前插入本独立 effort（优先于房间保真），严格切片交付三块：

1. **假多人 + Channel**：同一 `World` 可挂多个 `PlayerSession`（测试/脚本验收）；预置 `chat`（玩家可写）与 `system`（仅运行时/API 可写）两条 Channel，默认订阅两者；显式命令 `chat <text>`；与 `room_say` 并列。不改单玩家 REPL 为验收标准。
2. **房间 objects 放置 + 槽位补刷**：场景以房间声明 `objects`（模板键 → 数量）；全局仍保留物品/NPC 模板定义；加载器退役 `placed_in`/`in_room` 权威写法；补刷按登记槽位——对象仍存在（背包/别房也算）不补，销毁后且模板/`respawn` 允许才补。官方与示例场景迁完。
3. **声明式 Quest**：`quests.<id>` 表 + 玩家可存档旗标；`quest accept <id>` 接取（可要求同房 NPC）；完成靠交物与旗标；官方一条：龙门镖局镖头同房接取 → 华山向导处 `give` 交货领赏。

ADR-0008 停机结论不变；本批落地不宣称「多人/登录里程碑完成」。

## User Stories

### 假多人与 Channel

1. 作为引擎开发者，我想在同一 `World` 上挂两个带 `PlayerSession` 的实体并分别派发命令，以便用测试证明同房 `say` 与 Channel 投递，而不必先做联网客户端。
2. 作为引擎开发者，我想同房间内玩家 A 的 `say` 能进入玩家 B 的待显示消息，以便「假多人」至少覆盖现有房间广播语义。
3. 作为终端玩家（经由命令面），我想用显式命令 `chat <text>` 向 `chat` 频道发言，以便跨房间的订阅者都能收到闲聊，而不是靠未知命令 fallthrough 猜频道名。
4. 作为引擎开发者，我想未知动词**不会**被当成频道 ID 发送，以便命令路由保持显式注册表语义（与 LPC 频道 fallthrough 刻意不同）。
5. 作为引擎开发者，我想创建 `PlayerSession` 时默认订阅 `chat` 与 `system`，以便本波无需 `tune` 即可验收收发。
6. 作为引擎开发者，我想本波**没有** `tune`/退订命令，以便订阅模型保持最小切片。
7. 作为引擎开发者，我想通过引擎 API（或测试辅助）向 `system` 频道注入一条公告，使所有默认订阅者收到，以便系统公告与玩家闲聊分管道。
8. 作为终端玩家，我想对 `system` 使用玩家可写命令时被明确拒绝，以便系统管道不可被玩家冒充。
9. 作为引擎开发者，我想 `chat` 与 `system` 都出现在薄 Channel registry 中（`system` 标记为不可玩家写），以便扩展面统一、而不是把系统公告塞进 `room_say`。
10. 作为项目架构师，我想对外文档继续写明：本批 Channel ≠ 登录会话层 ≠ 真实联网多人（ADR-0008 澄清），以便停机叙事不被误读。

### 房间 objects 与槽位补刷

11. 作为场景作者，我想在房间上声明 `objects`（模板键 → 数量），并在全局段定义物品/NPC 模板，以便「这房有什么」与「模板长什么样」分开写，贴近侠客行房间 `objects` 心智。
12. 作为场景作者，我想不再把 `placed_in` / `in_room` 当作权威放置字段；若仍写上，加载应失败或按契约明确拒绝，以便不会存在两套互相打架的权威源（ADR-0010）。
13. 作为引擎开发者，我想官方默认场景与示例内容包场景都迁到 `objects` 写法，以便契约、校验与可玩场景一致。
14. 作为引擎开发者，我想物品模板也能声明 `count`/`respawn`（或等价字段）并参与槽位登记，以便物品与 NPC 共用「登记实例 + 补刷」心智。
15. 作为终端玩家，我想捡起一件占槽的地上物后，只要该实体还在（背包里），扫描**不会**在原房再刷一件，以便不会因拾取造成短暂超员。
16. 作为终端玩家，我想把该物丢到别的房间后，原房扫描仍因槽位对象存活而不补刷，以便与侠客行 `reset` 临时表指针语义一致。
17. 作为引擎开发者，我想当登记对象被销毁且 `respawn: true` 时，下一次补刷扫描会按蓝图在出生房补齐缺口，以便「销毁后再生」可测。
18. 作为引擎开发者，我想门钥匙等「引用唯一实体」的场景约束在 `count>1` 或可补刷槽上被加载期拒绝或文档化禁止，以便不破坏现有门锁语义。
19. 作为 UGC 创作者，我想创作者契约 v0 与 `--validate` 已知字段集反映 `objects` 与 Quest 相关字段变更，以便契约不撒谎。

### Quest

20. 作为终端玩家，我想在满足接取条件时输入 `quest accept <id>` 接到任务，以便接取动作显式、可测。
21. 作为终端玩家，我想接取条件可要求「与某 NPC 同房」；不满足时得到清晰失败提示且状态不变，以便不能远程凭空接活。
22. 作为终端玩家，我想 `ask` 仍然只返回打听文案、**不会**因话题而接任务，以便对话与任务入口不耦合。
23. 作为终端玩家，我想任务进行中把指定物品 `give` 给目标 NPC 后任务完成并获得声明的奖励（如金钱），以便闭环可玩。
24. 作为引擎开发者，我想完成条件本批只支持「交出指定物品」与「旗标满足」两类；到房只作为接取/交差前置，不单独作为完成类型，以便状态机保持最小。
25. 作为终端玩家，我想进行中/已完成等任务相关旗标能进入存档并在 restore 后仍在，以便中途存档不丢进度。
26. 作为主策划，我想官方 `m2_mvp_scene` 挂恰好一条示例任务：在 `yangzhou_biaoju` 与镖头同房 `quest accept …`，将镖货交给华山 `huashan_guide` 的向导并领赏，以便跨区走一趟验收移动+任务+交物。
27. 作为引擎开发者，我想重复 `quest accept` 同一进行中任务被拒绝，以便状态机不会叠接。
28. 作为 UGC 创作者，我想在场景 YAML 用声明式表配置任务的接取条件、完成条件与奖励，而不需要写脚本沙箱，以便与 ADR-0005 最小创作面一致。

### 治理与相邻 effort

29. 作为项目架构师，我想本 effort 全部关闭后才把 GAP 台账里「多人频道 / 物品 respawn / 任务」等条目改为已支持（或等价表述），以便文档与实现同步。
30. 作为项目架构师，我想房间保真 effort 的 grill **不得重开放置模型**，以便 ADR-0010 不被兄弟批推翻。

## Implementation Decisions

### 总则

- 严格切片：三条能力都做，但不做成完整多人网游或通用任务引擎。
- 本批优先于 Pre-M4 引擎房间保真；不并入 M3 停机加固；不升格为停机门闩。
- 已接受 ADR 只引用、不重开：0001、0008（含澄清）、0009、0010。
- 单玩家 REPL 体验**不是**本波验收标准；演示用多会话 CLI / 联网客户端显式 OOS。

### Channel 与假多人

- Channel 与 `room_say` 并列：跨房间、按订阅投递的命名管道；不是房间发言的子类。
- 本批 registry 预置：`chat`（`player_writable=true`）、`system`（`player_writable=false`）。不做 `rumor` / 门派 / wiz 频道表。
- 命令：显式注册 `chat <text>`；禁止未知命令 fallthrough 命中频道 ID。
- `system`：仅引擎 API / 测试注入可写；玩家命令写入必须失败并有提示。
- 订阅：创建 `PlayerSession` 时默认订 `chat`+`system`；本波不做 `tune`。
- 题材表 / ACL / 匿名 / 禁言运营策略后置；核心 = 投递 + 薄 registry + 订阅集合。
- 假多人验收：测试或脚本在同一 `World` 创建两个 `PlayerSession` 实体并分别派发命令（S1）。

### 房间 objects 与槽位补刷

- 权威放置：房间字段 `objects` 映射模板键 → 数量（可与全局 `items`/`npcs` 或等价模板段配合：模板定义属性，`objects` 决定摆哪里、几份）。
- 退役：`placed_in`、`in_room` 不再作为权威；加载器对旧写法失败或契约级拒绝；官方默认场景与示例包迁完。
- 槽位语义（物品与可补刷 NPC 对齐侠客行 `reset` 心智）：每条登记记住具体实例；`object` 仍存在（任意位置）则占名额；`get`/`drop` 不产生缺口；仅实例销毁后，若允许 `respawn`，扫描补齐至期望数量。
- NPC 现有 `count`/`respawn`/`SpawnerBlueprint`/`spawn_scan` 心智应收敛到同一槽位叙事（若今日 NPC 是「全图存活数」计数，本批在实现时改为或明确并存策略时以 **ADR-0010 槽位指针** 为准，避免物品一套、NPC 另一套对外说法）。
- 门钥匙等唯一实体引用：禁止与 `count>1` 或「可补刷槽」冲突的组合（加载期错误）。
- 回写创作者契约与校验已知字段；GAP 台账在本 effort 关闭后更新相关条。

### Quest

- 顶层（或场景约定段）`quests.<id>`：接取条件、完成条件、奖励、文案键等声明式字段（具体 schema 在 `/to-tickets` 钉死，须覆盖本 spec 用户故事）。
- 接取命令：`quest accept <id>`；条件可含「同房 NPC 模板/键」；失败不改状态。
- `ask` / `Inquiry`：保持纯文案；本批不挂接取副作用。
- 完成条件最小集：交出指定物品；旗标满足。到房仅作条件前置（如必须在某房才能 give/才能判定），不是独立完成类型。
- 奖励：至少支持给钱（Currency）；给物可选若实现成本低，否则票内注明本波只给钱。
- 玩家进度：可序列化旗标（或等价组件）进存档。
- 官方示例（恰好 1 条）：接取要求在 `yangzhou_biaoju` 与镖头同房；完成向 `huashan_guide` 向导交出任务物品并领赏；任务 id 与镖货模板键由实现票命名但须稳定可测。

### 建议实现顺序（非强制）

1. 房间 `objects` 迁移 + 物品槽位补刷（S2）——放置是后续内容与任务挂景的前置。
2. Quest 状态机 + 官方一条闭环（S1 命令 + S3）。
3. 双 `PlayerSession` + Channel（S1）——`messaging` 抽取已在加固 B3 落地，可复用扩展。

## Testing Decisions

- 只测外部行为（命令回文、组件可观察状态、存档往返、扫描后地上/槽位结果），不测私有函数结构。
- **S1 命令/会话面**（优先复用现有 dispatch + `PlayerSession` 待显示消息）：
  - 双 session 同房 `say` 互达。
  - `chat` 跨房投给订阅者；未订阅者（若测试构造）收不到——本波默认皆订阅，可用显式改订阅集合的测试辅助验证过滤（若本波不暴露改订阅 API，则只测「默认订阅者收到」即可）。
  - 玩家写 `system` 被拒；API/测试注入 `system` 可达。
  - `quest accept` 成功/失败文案与状态；`give` 完成与奖励。
- **S2 场景加载 + 补刷扫描**（复用 `load_scene` / `spawn_scan` 心智与现有 spawner 测风格）：
  - `objects` 加载出期望数量实例。
  - 旧 `placed_in`/`in_room` 权威写法被拒。
  - 拾取后不补；销毁后 `respawn: true` 才补；丢到别房不补。
- **S3 官方场景闭环**（加载官方 MVP 场景 + 脚本化命令序列，对齐现有 e2e 脚本测风格）：
  - 镖局接取 → 移动至华山向导 → `give` → 奖励与任务完成态。
  - 任务旗标 save/restore 仍在。
- 全量回归：本批合并后现有引擎测试基线保持绿。
- 纯文档/ADR 已完成项（0008 澄清、0010）不重复开「只写 ADR」票；契约/GAP 回写随实现票验收。

## Out of Scope

- 真实联网多人、TCP/WebSocket 客户端、独立登录/账号会话层、多进程多 World。
- `tune` / 退订 UI、谣言/门派/巫师频道表、禁言/防刷屏完整运营策略、匿名频道。
- 未知命令 fallthrough 命中频道（明确不做）。
- 用 `ask` 接任务、通用对话树、脚本沙箱任务引擎、多步剧情 DSL、师门贡献体系。
- 独立「踩房即完成」完成类型。
- 房间风景 / `item_desc` / 语义色 / `day_shop` / 液体灌装等（[pre-m4-engine-room-fidelity](../pre-m4-engine-room-fidelity/)）。
- 在房间保真中重开 `placed_in`/`in_room` vs `objects`。
- 把本批升格为 M3 停机门闩或改写「可诚实停机」定义。
- 留言板 / 创作者 Web 平台（ADR-0006 / post-mvp-backlog）。
- LPC 行为等价验证（ADR-0001）。
- M4 账本/分成/埋点实现。

## Further Notes

- **Shared understanding** 已于 2026-07-22 由架构师确认；测试接缝 S1/S2/S3 已单独确认。
- `/to-tickets` 拆票时建议按 Implementation Decisions 的建议顺序，并保证官方场景迁移与契约字段同一波可加载。
- NPC 计数若需从「全图存活数」迁到「槽位指针」以统一对外语义，属本 spec 允许的收敛，不另开决策票；若发现破坏性过大，停下来用短 grill 补一句，不得静默两套说法。
- 下一步：`/to-tickets` → 按票 `/implement`；不要跳过拆票直接整包实现。
