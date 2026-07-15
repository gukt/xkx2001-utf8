# ADR-0059：bboard 留言板子系统迁移范围与行为等价裁决

- 状态：已采纳
- 日期：2026-07-16
- 阶段：AI 分批迁移 第三批（bboard 完整子系统）
- 关联：[ADR-0056](ADR-0056-abandon-effort-estimation-ai-batched-migration.md) 决策 5 后续批 /
  [ADR-0057](ADR-0057-daemon-store-per-object-save.md) DaemonStore per-object save /
  [ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) CapabilityToken /
  [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 1（存档崩溃安全）/ 专家 2（物品消息架构）

## 背景

[ADR-0056](ADR-0056-abandon-effort-estimation-ai-batched-migration.md) 决策 5：后续批按子系统/
缺口类型 agent 并行迁移。pilot id=9 已迁 `bboard.c:do_read`（样本桩
[samples/bboard_c_do_read.py](../../engine/tools/sampling/pilot/samples/bboard_c_do_read.py)），
但仅是测量代码（ADR-0048 决策 8 不污染 `src/xkx`），引擎层只有数据建模
[daemons/bboard.py](../../engine/src/xkx/runtime/daemons/bboard.py)（BboardData/Note），命令层缺失。

bboard.c 共 5 个 `do_*` 命令。本批目标：把命令层落地到引擎层，**闭环验证 ADR-0057
DaemonStore** 在真实命令路径（do_discard 删帖后 save）中可用，同时解卡 id=9、消除样本桩
与引擎层的重复定义。

## 决策

### 1. 迁移范围：do_read / do_list / do_discard 迁移，do_post / do_store 暂缓

| 命令 | LPC 行 | 本批 | 理由 |
|---|---|---|---|
| `do_read` | L167-230 | 迁移（引擎层权威） | pilot 已验证逻辑，合一到引擎层 |
| `do_list` | L73-93 | 迁移 | 依赖少（start_more 桩 + BoardLastRead） |
| `do_discard` | L233-253 | 迁移（DaemonStore.save 闭环） | 卡点最少（cmp_wiz_level + save 已有） |
| `do_post` | L121-165 | **暂缓** | 核心依赖 `the_player->edit(callback)` 行编辑器（LPC feature/edit.c `input_to` 逐行接收），是客户端交互层，阶段 1 未接 |
| `do_store` | L279-367 | **暂缓** | 依赖 `EDITOR_D->get_file_num/add`（spec 存在 [layer_h_daemons2.py](../../engine/src/xkx/dsl/layer_h_daemons2.py) 但无 runtime），需先迁 editord daemon |

暂缓符合 [04](../xkx-arch/04-迁移路径与避坑清单.md) §一"收敛优先于完备"：不为大卡点
（客户端交互层 / 独立 daemon）建桩绕过，留触发条件明确的后续批。

### 2. 补 src 缺口（修路，子任务前置）

- **`cmp_wiz_level(token, level_str) -> int`**（[capability.py](../../engine/src/xkx/runtime/capability.py)）：
  对照 LPC `securityd.c:173` `get_wiz_level(ob) - member_array(lvl, wiz_levels)`。`token=None`
  返回 -1（**fail-closed**，未授权视为最低等级）；否则 `list(WizLevel).index(token.status) -
  list(WizLevel).index(WizLevel(level_str))`，非法 level_str 降级 `WizLevel.PLAYER`。
  WizLevel StrEnum 序已验证与 LPC `wiz_levels` 数组序 1:1 对齐（securityd.c:24-34）。
  替代 pilot 样本桩 `_entity_wiz_level`/`_compare_wiz_level`（默认 PLAYER + monkeypatch）。
  token 从 `ActionContext.capability_token`（[action_context.py](../../engine/src/xkx/runtime/action_context.py)
  L78，段 2 注入）取，无需 entity->token 映射。
- **`BoardLastRead` 组件**（[components.py](../../engine/src/xkx/runtime/components.py)）：
  `records: dict[str, int]`，对照 LPC `me->query("board_last_read")` mapping（board_id ->
  最后阅读时间戳）。**玩家级 ECS 组件**（per-player 读帖记录），非 daemon（daemon 是 board
  数据单例 per-board，二者不混）。替代 pilot 样本桩 BoardLastRead。
- **BboardData 补 `capacity: int = 50` + `poster_level: str | None = None`**
  （[daemons/bboard.py](../../engine/src/xkx/runtime/daemons/bboard.py)）：对照 LPC
  `BOARD_CAPACITY` 宏（do_post 截断）+ `poster_level`（wumiao_b.c:11 投稿门槛）。
  `to_dict`/`from_dict` 同步补，向后兼容旧存档（`.get` 走默认值）。Note 暂不补 `stored`
  （仅 do_store 用，随其暂缓）。

### 3. 命令代码组织（[bboard_commands.py](../../engine/src/xkx/runtime/bboard_commands.py)）

新建引擎层命令模块，类比 [items.py](../../engine/src/xkx/runtime/items.py) 函数族模式：

- 签名 `(game, ctx, board: BboardData) -> list[str]`，`board` 由调用方从
  `game.world.daemon_store.get("bboard_<board_id>")` 取后传入（解耦 board 来源解析）。
- arg 从 `ctx.raw_args` 取（对齐 commands.py 现有命令取参模式）。
- 失败语义：LPC `notify_fail` 改返回单元素消息列表（对齐 pilot do_read 已验证模式）。
- `tune_channels`/`open_channels` 频道副作用跳过（channeld 后置）。
- `start_more` 内联 `return [msg]`（对齐 LPC `start_more`，真实 pager 后置 M3，不依赖 pilot stubs）。
- **本批不注册 COMMAND_REGISTRY**：房间-bboard 关联未接，只迁函数 + 测试，注册留命令管线集成批。

### 4. DaemonStore per-object save 闭环（do_discard，验证 ADR-0057）

`do_discard` 删帖后调 `game.world.daemon_store.save("bboard_<board_id>")`（ADR-0057 决策 1/3，
主动同步 save，**不走 dirty-flag**）。`daemon_store` 是 world 动态属性（[world.py](../../engine/src/xkx/runtime/world.py)
L160），可能为 None（demo 未接）；None 则跳过 save + 记 warning（对齐 LPC 无存档时 no-op）。

测试 `test_discard_own_note_saves` + `test_discard_save_roundtrip`：构造 `DaemonStore(tmp_path)`
+ `store.register(...)` + 设 `game.world.daemon_store`，调 do_discard 后断言存档文件生成
+ `restore_all` 反序列化往返一致（notes 少一条）。闭环验证 ADR-0057 的 `write_json_atomic`
原子写在真实命令路径可用。

### 5. do_list 无门控--行为等价裁决（关键，修正实施偏离）

**LPC do_list（L73-93）原文无任何 `wizard_only`/`poster_family`/`cmp_wiz_level` 门控**：
`short()`/`long()`/`do_list()` 三者均无门控，标题列表对所有人可见，仅读正文 `do_read`（L182-198）
才检查 wizard_only + poster_family 权限。这是 LPC 一致设计（标题是 metadata 公开，正文是内容受限）。

实施 agent 初版在引擎层 do_list 补了 wizard_only/poster_family 门控（理由"标题也不应被无权者
窥视"）。**本 ADR 裁决移除该门控，严格对齐 LPC**。理由：

- 行为等价是 greenfield 硬约束（[CLAUDE.md](../../CLAUDE.md)"LPC 是规格源，从零按规格实现，
  行为等价验证"；[04](../xkx-arch/04-迁移路径与避坑清单.md) §五检查点 7"逐子系统行为等价验证"）。
- LPC 无门控是有意设计（short/long/do_list 一致公开），非遗漏。补门控是擅自安全增强，
  迁移职责是复现规格非修正规格。
- 若将来判定"标题也该受限"是产品决策，应独立 ADR 关联 dissent，非迁移时夹带。

测试相应改为断言无门控（wizard_only/poster_family 板标题列表凡人/外人可见）。

### 6. 务实合一：pilot 样本保留标注（对计划 D5 的收敛调整）

引擎层 [bboard_commands.py](../../engine/src/xkx/runtime/bboard_commands.py) 是权威实现 +
[test_bboard_commands.py](../../engine/tests/test_bboard_commands.py) 完整覆盖（do_read 迁 pilot
14 测试逻辑 + do_list 5 + do_discard 9）。**这是合一的核心价值**：后续迁移用引擎层，不各自
monkeypatch（ADR-0056 决策 4 修路目标达成）。

pilot 样本 `bboard_c_do_read.py` + `test_bboard_c_do_read.py` **保留不动**（ADR-0056 决策 2
明确保留 pilot 副产出作历史记录），仅在样本顶部 docstring 加标注"已被引擎层 do_read 替代"。
**不删不改样本的 cmp_wiz_level/Note/BoardItem/BoardLastRead 桩**：cmp_wiz_level 签名差异
（样本 `(world, eid, str)` vs 引擎层 `(token, str)`）会连锁改样本 14 测试，穷尽细节违反收敛；
样本是历史测量记录，引擎层权威实现已达成合一价值。

### 7. author 格式 name(id) 的 id 来源占位

`do_discard` 权限比对 `notes[num].author == name(id)`（bboard.c L244，LPC `query("id")` =
玩家账号 id）。引擎层 [`_author_signature`](../../engine/src/xkx/runtime/bboard_commands.py)
用 `Identity.name` + `Identity.prototype_id` 占位。

`Identity.prototype_id` 语义是"NPC/玩家 def id"（[components.py](../../engine/src/xkx/runtime/components.py)
L19），不完全等同 LPC `query("id")`（账号 id）。但 do_post 暂缓（发帖路径未实现），author
来源待 do_post 落地时统一（届时确定 greenfield 玩家 id 字段，发帖写入与删帖比对用同一来源即可
一致）。当前测试用 `Identity(name, prototype_id)` 匹配手填 `note.author` 验证功能，占位可工作。

## 关联 [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent

- **专家 1（存档崩溃安全）承重论断 2/3**：do_discard 走 DaemonStore.save（ADR-0057 复用
  `write_json_atomic` 原子写 + 不走 dirty-flag），闭环验证 per-object save 在真实命令路径
  的崩溃安全。death 回档风险（ADR-0057 决策 5 滑坡论证）同样适用：bboard 删帖到下次 entity
  persist 间崩溃可能丢删除，但 daemon save 是主动同步写（删帖即存），风险窗口仅 fsync ms 级，
  远小于 entity 周期 persist 30s。kill criteria 8 迁 PG 时统一补齐。
- **专家 2（物品/消息架构）dissent**：bboard 作为 daemon 单例承载（非 ItemComp，ADR-0057），
  命令层用函数族模式（类比 items.py），物品实体化留 M3。do_list 的列表头用 `board_id` 占位
  （LPC 用 `query("name")`，BboardData 无 name 字段--daemon 不建模物品 ItemComp 域字段），
  待门派/物品数据建模批统一。

## 与 [04](../xkx-arch/04-迁移路径与避坑清单.md) 验收关系

- §三阶段 2.6 WorldGovernanceSystem（代表性治理元素）：bboard 留言板是治理类子系统
  （wizard_only/poster_family 权限门控 + 删帖审计），本批落地 3 命令 + 数据建模。
- §五检查点 7（逐子系统行为等价验证）：do_list 无门控裁决是行为等价的明确体现。
- §四 kill criteria 8（迁 PG）：daemon save 同 entity save，迁 PG 时 `DaemonStore` 换
  `PostgresDaemonBackend`（策略切换）。

## 不做（范围边界）

- **do_post / do_store 迁移**（决策 1，大卡点暂缓）。
- **COMMAND_REGISTRY 注册**（房间-bboard 关联未接）。
- **Note.stored 字段 / EDITOR_D runtime**（随 do_store 暂缓）。
- **pilot 样本桩删除/改写**（决策 6，保留作历史）。
- **do_list 安全增强门控**（决策 5，行为等价裁决移除）。
- **author id 来源最终统一**（决策 7，待 do_post 落地）。

## 产出位置

- `engine/src/xkx/runtime/bboard_commands.py`：do_read/do_list/do_discard 引擎层命令。
- `engine/src/xkx/runtime/capability.py`：cmp_wiz_level 函数。
- `engine/src/xkx/runtime/components.py`：BoardLastRead 组件。
- `engine/src/xkx/runtime/daemons/bboard.py`：BboardData 补 capacity/poster_level。
- `engine/tests/test_bboard_commands.py`：33 测试（do_read 19 + do_list 5 + do_discard 9）。
- `engine/tests/test_cmp_wiz_level.py`：13 测试（cmp_wiz_level fail-closed + BoardLastRead 往返）。
- `engine/tools/sampling/pilot/samples/bboard_c_do_read.py`：顶部加标注（桩不动）。

## 后续

- do_post：待客户端交互层（input_to 等价 / 行编辑器）就绪后迁移。
- do_store：待 EDITOR_D runtime 实现（先迁 editord daemon）后迁移。
- author id 来源：do_post 落地时统一（Identity 字段或 Account 账号 id）。
- COMMAND_REGISTRY 注册：房间-bboard 关联接通后（房间配置 bboard_id）。
- 迁 PG（kill criteria 8）：DaemonStore 与 StorageSystem 同步策略切换。
