# 项目进度

> 本文件是跨 session 的"活的状态"——每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> **2026-07-17 项目重设，2026-07-18 新目标定稿+CLAUDE.md 重写完成**：原目标与取舍战略已放弃，新目标已用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 9/10 票决策（[02](.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md) 用户主动标"暂定"未拍板，不阻塞其他票）并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"章节。重设前的完整进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)（含更早的按阶段归档 [docs/archive/progress-archive/](docs/archive/progress-archive/)），仅作背景参考。

**最后更新**：2026-07-18（M1 05 号票落地：心跳循环 + 存档与崩溃恢复；01~06 号票全 resolved，166 测试全绿）

## 当前状态速览

- **阶段**：M0 完成；M1 spec 已产出，`/to-tickets` 已拆出 6 张票（[.scratch/m1-core-engine-skeleton/issues/01~06](.scratch/m1-core-engine-skeleton/issues/)）；**01~06 号票全 resolved**（01 引擎骨架；02 解析执行解耦+别名；03 物品与容器；04 门与动态出口；05 心跳循环+存档崩溃恢复；06 YAML 场景 DSL）。下一步：M1 里程碑收尾，准备 M2（一个 MVP 场景端到端可玩）`/to-spec`。
- **分支**：见当前 git 分支。
- **engine/ 现状**：`src/mud_engine/` 下已有 `world.py`/`components.py`/`commands.py`/`parsing.py`/`intent.py`/`matching.py`/`scenes.py`/`scene_loader.py`/`save.py`/`tick.py`/`cli.py`/`__main__.py`，场景数据在 `engine/data/m1_default_scene.yaml`，存档在 `engine/save/`（运行时产物，.gitignore 忽略）。`python -m mud_engine` 跑通真实终端闭环（`go`/`look`/`take`/`drop`/`inventory`(`i`)/`open`/`close`/`knock`/`unlock`/`help`(`h`)/`quit` + 方向别名 `go 北道` + 物品别名 `take 石` + 门状态在 `look` 出口列表标注 + 静态 NPC 在 `look` 中可见 + 周期存档/`quit` 立即存档/重启从存档恢复）。166 条测试，`just gate` 全绿。

## Done

- **M1 05 号票：心跳循环 + 存档与崩溃恢复**（[05-tick-loop-save-crash-recovery](.scratch/m1-core-engine-skeleton/issues/05-tick-loop-save-crash-recovery.md)，resolved）：新增 `save.py`（全量 per-entity JSON 存档 + staging 快照目录 + symlink 原子发布 + 容错 restore 跳过损坏条目记 warning）+ `tick.py`（`TickLoop`：tick 计数 + 间隔触发存档 + `force_save`）；`World` 加 `create_entity_with_id`/`all_entities`/`components_of` 供 restore/serialize（stable id，出口/门/容器引用直接生效）；`cli.run_repl` 接入 `tick_loop`（每命令 `advance`、退出前 `force_save`）；`__main__` 启动时 `has_save` 则 `restore_world` 否则 fresh scene。崩溃安全靠 staging 目录 + `os.replace` 原子发布 symlink（`current` 永远指向完整快照，写入中途崩溃留孤儿 staging 不影响上次发布）。新增 `test_save.py`（11）+ `test_tick.py`（6）+ `test_world`/`test_cli` 扩展，166 测试全绿，`/code-review` 双轴过（修了 `WithTheDefaultInterval` 嵌套类不在 `python_classes` 被静默跳过的硬违规 + 删 dead export `SaveError`）。
- **M1 04 号票：门与动态出口**（[04-doors-and-dynamic-exits](.scratch/m1-core-engine-skeleton/issues/04-doors-and-dynamic-exits.md)，resolved）：新增独立于 `Exits` 的 `Doors` 组件（`DoorState` 开/关/锁 + `Door` 钥匙物品 id）+ `open`/`close`/`knock`/`unlock` 命令（复用 02 的 `match_target` 方向解析，`_parse_go` 重构为 `_parse_direction(verb=...)`）；`go` 关/锁门拦截、`look` 出口标注门状态；YAML 加 `door`/`key` 字段（顺带补上 06 号票留的门/锁表达后续小补丁，loader 顺序改 rooms->items->exits 以让门锁引用物品 entity id）。默认场景 start_yard south 关门、corridor north 锁门 + iron_key 钥匙（放 corridor）、新增 storage_room。动态出口靠 `Exits.by_direction` 可变 dict（03 已设计）+ 测试验证增删后 look/go 反映。新增 `test_doors.py`（31）+ `test_scene_loader` 门加载测试（6），139 测试全绿，`/code-review` 双轴过（修了 `AfterOpening` 嵌套类不带 `When*` 前缀被 pytest 静默跳过的硬违规；3 个判断性 smell 接受）。
- **M1 06 号票：YAML 场景 DSL**（[06-yaml-scene-dsl](.scratch/m1-core-engine-skeleton/issues/06-yaml-scene-dsl.md)，resolved）：场景数据从 `scenes.py` 内嵌 Python 元组迁移到 `engine/data/m1_default_scene.yaml`；新增 `scene_loader.py`（YAML 解析+加载期校验+建世界，抛 `SceneLoadError` 带文件路径与出错条目键，`__main__` 捕获打印干净错误不抛裸堆栈）；`scenes.py` 瘦身为"默认场景文件 + 调 loader"入口。覆盖房间/物品/**静态展示型 NPC**（`Identity`+`Description`+`Position`，无行为，`look` 在场可见、`take` 当不存在物品处理）；门/锁状态（04 号票）未完成，按票留后续小补丁。`_cmd_look` 增在场 NPC 展示行。新增 `test_scene_loader.py`（15 条）。`/code-review` 双轴过（0 硬违规、0 spec 缺失，仅 DRY 判断题为保信息清晰度未抽 helper）。02/03 票产出测试不改断言全过，102 测试全绿。新增 PyYAML 运行时依赖。
- **代码质量调整**（用户要求）：① justfile 加 `run` recipe（`just run` -> `uv run python -m mud_engine` 启动真实终端 demo）；② `components.py` 每个字段加"是什么+例子"注释，面向未来 UGC 创作层 Agent 生成场景 DSL；③ `player: EntityId` 参数名 -> `player_id`（全 src+tests rename，`source="player"` 字符串值与 `_player_room`/`player_container` 保留），87 测试全绿。
- **M1 03 号票：物品与容器**（[03-items-and-containers](.scratch/m1-core-engine-skeleton/issues/03-items-and-containers.md)，resolved）：新增 `Container` 组件（房间地面与玩家物品栏同一种组件各挂一份）+ `Identity.aliases`（物品别名）；`take`/`drop`/`inventory`(`i`) 复用 02 的 `Intent` 管线 + `match_target`（物品目标解析层 match，`Intent.target`=规范名）；`ParseFailure` 加 `verb` 字段让失败提示按命令分（go 那个方向/take 这里没有/drop 你没有）；`look` 加地面物品展示；scenes 预置石头物品（别名"石"）。`/code-review` 双轴过（提 `_sorted_item_names` 消重 + 补 drop 后 inventory 断言）。
- **M1 02 号票：解析执行解耦 + 别名机制**（[02-parse-execute-decoupling-aliases](.scratch/m1-core-engine-skeleton/issues/02-parse-execute-decoupling-aliases.md)，resolved）：`execute_line` 拆「解析（文本->Intent/ParseFailure）+ 执行（Intent->效果）」两阶段；稳定中间表示 `Intent`（破循环独立成 `intent.py`）；通用别名工具 `matching.match_target`（03/04 复用）；`Exits` 加 `Exit(target,aliases)`；命令别名声式声明 + 冲突 fail-fast；方向简写 n/s/e/w；`ParserChain` 可插拔链。新增 `matching.py`/`parsing.py`/`intent.py` + `test_matching`/`test_parsing`；`/code-review` 双轴过。
- **M1 spec 范围修订 + 补 06 号票**：用户要求 M1 阶段加 YAML 场景数据 DSL(房间/物品/静态展示型 NPC),与 spec 原有"格式设计留给 M3""NPC 与 NPC AI 推到 M2"两条冲突,已跟用户确认收窄范围(YAML 是 M1 内部过渡格式,不是 M3 正式 UGC DSL;NPC 只开放"无行为的静态展示型")并更新 [M1 spec](.scratch/m1-core-engine-skeleton/spec.md)(「场景数据与引擎能力的边界」「Out of Scope」「范围修订记录」三处),补了 [06-yaml-scene-dsl](.scratch/m1-core-engine-skeleton/issues/06-yaml-scene-dsl.md)(阻塞:03,可与 05 并行)。**06 号票尚未 `/implement`**。
- **M1 `/to-tickets` 拆票**：6 张票发布到 [.scratch/m1-core-engine-skeleton/issues/01~06](.scratch/m1-core-engine-skeleton/issues/)（01 骨架→02 解析别名→03 物品/04 门可并行→05 存档、06 YAML DSL 可与 05 并行），阻塞关系已与用户确认。
- **M1 01 号票：引擎骨架落地**（[01-engine-skeleton-ecs-dispatch-cli](.scratch/m1-core-engine-skeleton/issues/01-engine-skeleton-ecs-dispatch-cli.md)，resolved）：ECS 最小存储（6 种操作）+ 命令注册表（`go`/`look`/`help`/`h`/`quit`）+ 静态三房间场景数据 + 真实终端 CLI 循环；`/code-review` 双轴过一遍后补了 `World.require_component`（收口重复的 `assert is not None` 场景数据完整性检查，避免 `python -O` 下失效）。
- **测试命名约定改为 BDD 嵌套类风格**（用户决定，记在 [engine/README.md](engine/README.md)「测试约定」）：Given/When 分组成嵌套类，方法名只写 Then；**踩坑**：这些嵌套类不带 `Test` 前缀，pytest 默认配置会静默跳过，已在 `engine/pyproject.toml` 把 `python_classes` 扩到 `["Test*", "When*", "Given*"]`，后续新增分组类名前缀要同步扩展这个列表。
- **Python 包 rename**（[ADR-0003](docs/adr/0003-python-package-mud-engine.md)）：`src/xkx/` → `src/mud_engine/`（`import mud_engine`）；发行名 `mud-engine`；archive tag 内旧路径不变。
- **M1 第 0 步：engine 工作区绿场重置**（[.scratch/m1-core-engine-skeleton/issues/00-engine-workspace-reset.md](.scratch/m1-core-engine-skeleton/issues/00-engine-workspace-reset.md)）：tag `archive/engine-pre-m1-rewrite`；移除旧 `src/tests/scenes/tools`；路径仍为 `engine/`；[ADR-0002](docs/adr/0002-engine-workspace-greenfield-reset.md)；CLAUDE/justfile/M1 spec 已同步。
- **`/to-spec` 产出 M1 spec**：[.scratch/m1-core-engine-skeleton/spec.md](.scratch/m1-core-engine-skeleton/spec.md)（Status: ready-for-agent）。范围=移动/查看/拾取丢弃/门与动态出口/存档骨架；CLI 真终端；ECS 组件按复用性拆分；解析/执行两阶段 + 别名。
- **`/wayfinder` mvp-scope 地图 9/10 票解决**（[.scratch/mvp-scope/map.md](.scratch/mvp-scope/map.md)，[02](.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md) 暂定挂起）。结论摘要见 [CLAUDE.md](CLAUDE.md)「架构不变量」；[ADR-0001](docs/adr/0001-no-lpc-behavior-equivalence-verification.md)。
- **重写 [CLAUDE.md](CLAUDE.md)** 项目一句话 + 架构不变量 8 条。

## In Progress

- **`/prototype` ECS×UGC 手感**（可选收尾）：`just proto-ecs-ugc`（`engine/prototypes/ecs_ugc/`）。结论已部分吸收进 M1 spec；若不再跑可标完成。

## Blocked

**当前无阻塞项。**

## Next Up

1. [M1 spec](.scratch/m1-core-engine-skeleton/spec.md)（注意文末「范围修订记录」，07-18 加了 YAML DSL 范围）。
2. M1 里程碑收尾：01~06 号票全 resolved，确认无遗留后准备 M2（一个 MVP 场景端到端可玩）`/to-spec`。
3. [02-engine-boundary-combat-effects](.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md)（mvp-scope 里的票，不要跟 M1 的 02 号票搞混）建议在 M2 `/to-spec` 前用 `/prototype` 或 `/design-an-interface` 补上--不阻塞 M1。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 单条 ≤2 行，细节进 ADR（[docs/adr/](docs/adr/)，重设后从头编号）。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
