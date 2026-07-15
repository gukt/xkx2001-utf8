# bboard 留言板子系统迁移（AI 分批迁移第三批）

> 推进方向：PROGRESS Next Up 第 1 条「bboard 完整子系统」。选它而非武器数据/job_data，
> 因为能**闭环验证刚补的 DaemonStore**（ADR-0057）在真实命令路径（do_discard 用 save）中
> 可用，同时解卡 pilot id=9、消除样本桩与引擎层重复。job_data 二进制 .sav 无法提取
> （ADR-0057 明确留后续）、武器数据是机械内容生产，优先级低。

## 背景

- LPC 规格：[inherit/misc/bboard.c](inherit/misc/bboard.c)（368 行，5 个 do_* 命令）。
- 现状：pilot id=9 已迁 `do_read`（样本桩 [bboard_c_do_read.py](engine/tools/sampling/pilot/samples/bboard_c_do_read.py) + 测试 [test_bboard_c_do_read.py](engine/tests/test_bboard_c_do_read.py)）；引擎层只有数据建模 [daemons/bboard.py](engine/src/xkx/runtime/daemons/bboard.py)（BboardData/Note）。
- DaemonStore（[daemon_store.py](engine/src/xkx/runtime/daemon_store.py)）已就绪，挂 `world.daemon_store`（动态属性，[world.py:160](engine/src/xkx/runtime/world.py#L160)）。
- 命令执行函数签名 `(game, ctx) -> list[str]`，token 在 `ctx.capability_token`（[action_context.py:78](engine/src/xkx/runtime/action_context.py#L78)）。

## bboard.c 命令清单（调研结论）

| 命令 | LPC 行 | 现状 | 本批 |
|---|---|---|---|
| `do_read` | L167-230 | pilot 已迁（样本桩） | **合一**到引擎层 |
| `do_list` | L73-93 | 未迁 | **迁移** |
| `do_discard` | L233-253 | 未迁 | **迁移**（DaemonStore.save 闭环） |
| `do_post` | L121-165 | 未迁 | **暂缓**（edit() 交互编辑器卡点） |
| `do_store` | L279-367 | 未迁 | **暂缓**（EDITOR_D runtime 卡点） |

## 范围（收敛）

### 做

**A. 补 src 缺口（修路）**：
1. `cmp_wiz_level(token, level_str)` -> [capability.py](engine/src/xkx/runtime/capability.py)
2. `BoardLastRead` 组件 -> [components.py](engine/src/xkx/runtime/components.py)
3. BboardData 补 `capacity` + `poster_level` -> [daemons/bboard.py](engine/src/xkx/runtime/daemons/bboard.py)

**B. 迁移命令（引擎层函数 + 测试）**：
4. 新建 [runtime/bboard_commands.py](engine/src/xkx/runtime/bboard_commands.py)：`do_list` + `do_discard` + 引擎层 `do_read`
5. `do_discard` 内部调 `game.world.daemon_store.save(...)` 验证 per-object save 闭环

**C. do_read 合一**：pilot 样本桩改用引擎层 BboardData/Note/BoardLastRead/cmp_wiz_level，删除样本内重复定义

**D. 文档**：ADR-0059（bboard 迁移范围 + 暂缓理由）+ PROGRESS 更新

### 不做（暂缓，留 ADR 标注）

- **do_post**：核心依赖 `the_player->edit(callback)` 行编辑器（LPC feature/edit.c input_to 逐行接收），客户端交互层，阶段 1 未接。暂缓到客户端交互层就绪。
- **do_store**：依赖 `EDITOR_D->get_file_num/add`（spec 存在 layer_h_daemons2.py:3339/3398 但无 runtime），需先迁 editord daemon。暂缓到 EDITOR_D runtime 批。
- **COMMAND_REGISTRY 注册**：房间-bboard 关联未接，本批只迁函数 + 测试，注册留命令管线集成批。
- **Note.stored 字段**：仅 do_store 用，随 do_store 暂缓。

## 关键设计决策

### D1: cmp_wiz_level 真实实现
- 签名：`cmp_wiz_level(token: CapabilityToken | None, level_str: str) -> int`
- 实现：`token=None` 返回 -1（fail-closed，未授权视为最低等级）；否则 `list(WizLevel).index(token.status) - list(WizLevel).index(WizLevel(level_str))`，非法 level_str 降级 `WizLevel.PLAYER`。
- 放 [capability.py](engine/src/xkx/runtime/capability.py)（与 WizLevel 同模块，CLAUDE.md 要求安全模块类型完整）。
- 对照 LPC securityd.c:173 `cmp_wiz_level = get_wiz_level(ob) - member_array(lvl, wiz_levels)`；WizLevel StrEnum 序与 LPC wiz_levels 数组序对齐（capability.py:45-57）。
- 替代 pilot 样本桩 `_entity_wiz_level`/`_compare_wiz_level`（默认 PLAYER + monkeypatch）。

### D2: BoardLastRead 组件
- 放 [components.py](engine/src/xkx/runtime/components.py)，`@dataclass class BoardLastRead: records: dict[str, int] = field(default_factory=dict)`。
- 对照 LPC `me->query("board_last_read")` mapping（board_id -> 最后阅读时间戳）。
- 玩家级 ECS 组件，`world.get(eid, BoardLastRead)` / `world.add(eid, BoardLastRead(records=...))`，对齐 pilot 样本桩用法。
- 可序列化（字段全基本类型，ADR-0022 存档崩溃安全）。

### D3: BboardData 补字段
- `capacity: int = 50`（LPC BOARD_CAPACITY 宏，do_post 截断 L110-111 用；本批虽暂缓 do_post，但字段补齐让数据建模完整）。
- `poster_level: str | None = None`（投稿等级门槛，do_post 用 wumiao_b.c:11；同上补齐）。
- `to_dict`/`from_dict` 同步补两字段（向后兼容，旧存档无该字段走默认值）。
- Note 暂不补 `stored`（随 do_store 暂缓）。

### D4: 命令代码组织
- 新建 [runtime/bboard_commands.py](engine/src/xkx/runtime/bboard_commands.py)（类比 [items.py](engine/src/xkx/runtime/items.py) 独立模块模式）。
- 函数签名：`do_read(game: Game, ctx: ActionContext, board: BboardData) -> list[str]` / `do_list(...)` / `do_discard(...)`，接受 `board` 参数（从 daemon_store 取后传入，解耦 board 来源解析）。
- board 来源：调用方/adapter 从 `game.world.daemon_store.get("bboard_<board_id>")` 取。本批测试直接构造 board 传入。
- `do_discard` 删帖后调 `game.world.daemon_store.save("bboard_" + board.board_id)`（闭环验证 ADR-0057 per-object save；daemon save 不走 dirty-flag）。
- 失败语义：LPC `notify_fail` 改返回单元素消息列表（对齐 pilot do_read 已验证模式）；`tune_channels/open_channels` 频道副作用跳过（channeld 后置）。

### D5: do_read 合一策略
- pilot 样本 [bboard_c_do_read.py](engine/tools/sampling/pilot/samples/bboard_c_do_read.py) 删除内嵌 `Note`/`BoardItem`/`BoardLastRead`/`cmp_wiz_level`/`_entity_wiz_level`/`_compare_wiz_level`/`_player_family` 重复定义，改 import 引擎层。
- 样本 `bboard_c_do_read` 函数体改用引擎层 `cmp_wiz_level(ctx.capability_token, ...)` + `BoardLastRead` 组件。
- 样本测试 [test_bboard_c_do_read.py](engine/tests/test_bboard_c_do_read.py) 改用引擎层类（BoardItem -> BboardData）。
- 引擎层 `do_read` 落地到 bboard_commands.py（逻辑与样本一致，已 pilot 验证）。
- **不变量**：合一后样本测试 + 引擎层测试都跑通，行为等价不变。

## 不变量约束（review 重点）

1. `cmp_wiz_level` fail-closed：token=None 返回 -1（未授权视为最低），不放过。
2. daemon save 走 `DaemonStore.save`（原子写 + 不走 dirty-flag），不退回 LPC 全量覆盖。
3. weight 双重语义不涉及（bboard 无 weight），但 `BoardLastRead` 是玩家级 ECS 组件非 daemon（daemon 是 board 数据单例，玩家读帖记录是 per-player）。
4. 合一不破坏 pilot do_read 14 个测试的行为等价。
5. 暂缓命令明确标注卡点，不偷偷 monkeypatch 绕过。

## 文件清单

**新增**：
- `engine/src/xkx/runtime/bboard_commands.py`（do_read/do_list/do_discard）
- `engine/tests/test_bboard_commands.py`（do_list/do_discard 引擎层单测）
- `engine/tests/test_cmp_wiz_level.py`（cmp_wiz_level 单测）
- `docs/adr/ADR-0059-bboard-subsystem-migration-scope.md`

**修改**：
- `engine/src/xkx/runtime/capability.py`（+ cmp_wiz_level）
- `engine/src/xkx/runtime/components.py`（+ BoardLastRead）
- `engine/src/xkx/runtime/daemons/bboard.py`（BboardData 补 capacity/poster_level）
- `engine/tools/sampling/pilot/samples/bboard_c_do_read.py`（合一，删重复桩，用引擎层）
- `engine/tests/test_bboard_c_do_read.py`（合一，用引擎层类）
- `PROGRESS.md`（Done/Next Up 更新）

## 执行方式（agent 编排，pipeline）

```
阶段 1 ─ Agent A（修路）：cmp_wiz_level + BoardLastRead + BboardData 补字段 + 单测
            │ 文件：capability.py / components.py / daemons/bboard.py + 测试
            ▼
阶段 2 ─ Agent B（迁移+合一，A 完成后）：bboard_commands.py 新建 do_list/do_discard/do_read
            │ + 合一 pilot 样本桩 + 全部 bboard 测试
            ▼
阶段 3 ─ 我：review 不变量 + 合跑全量 + ADR-0059 + PROGRESS
```

- 串行 pipeline：B 依赖 A 的 cmp_wiz_level/BoardLastRead，A 先跑。
- 文件隔离：A 改 capability/components/bboard 数据层，B 建 bboard_commands + 改样本桩，无写冲突。
- 各 agent 跑自己的新测试避免并发干扰，我最后合跑全量。

## 验收标准

1. 全量 tests 全绿（当前 2237 + 本批新增，预计 +30~50）。
2. `just lint`（ruff）全过，行长 <=100。
3. do_discard 真调 `DaemonStore.save`（单测断言存档文件生成 + 原子写）。
4. do_read 合一后 pilot 14 测试行为等价不变。
5. cmp_wiz_level fail-closed（token=None 返回 -1）。
6. ADR-0059 关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) dissent（专家 1 存档崩溃安全 / 专家 2 物品消息架构）。
7. do_post/do_store 暂缓在 ADR + PROGRESS 标注卡点。

## 预估 AI 成本（替代人工工时，ADR-0056）

- Agent A（修路）：~1 个 agent，补 3 缺口 + 单测。
- Agent B（迁移+合一）：~1 个 agent，3 命令 + 合一 + 测试。
- 边跑边记 token / 运行时间，写入 PROGRESS。
