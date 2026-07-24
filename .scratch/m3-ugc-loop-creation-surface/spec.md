Status: ready-for-agent

# M3 — UGC 创作闭环打通一次：包外内容包 → 指向加载 → 校验 → 可玩

> 依据：[CLAUDE.md 架构不变量](../../CLAUDE.md) 第 5 条（UGC/DSL 创作层从零设计，M3 最小切片："包外声明式内容包 → 加载 → 可玩"）；[ADR-0005](../../docs/adr/0005-m3-ugc-loop-creation-surface.md)（M3 创作面边界：manifest + 声明式场景数据，不交付编辑器/Web 评审台/对话树/RestrictedPython 逃生舱，不强制 LLM Orchestrator）；[ADR-0006](../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md)（编辑器/留言板丢弃，创作者 Web 平台是独立后续产品，引擎只留"内容包加载/校验契约 + 运行时护栏"）；[.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md](../mvp-scope/issues/03-ugc-dsl-design-inheritance.md)（Refinement 节：M3 创作闭环最小切片的四条明确决定）；[.scratch/mvp-scope/issues/07-governance-cost-tracking.md](../mvp-scope/issues/07-governance-cost-tracking.md)（M3 里程碑定义："UGC 创作闭环打通一次，哪怕只是一个非官方小场景，走完创作→加载→可玩全流程"——这是一个刻意收窄到"一次"的最小切片里程碑，不是"UGC 平台"或"正式 DSL"里程碑）；[.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md](../mvp-scope/issues/06-scaling-commercialization-support-points.md)（支撑点 #2 题材包资产元数据——本 spec 落地其"简化版"）。技术地基是 [M2 spec](../m2-mvp-scene-playable/spec.md) 已交付的场景 YAML 加载器（`scene_loader.load_scene`）与能力注册表模式，本 spec **不改动**其已知字段集与表达力，只加一层"指向哪个包、这个包是谁的"的外壳。
>
> **范围校准（写在最前面，供 `/to-tickets` 与 `/implement` 反复核对）**：M3 治理定义是"打通一次"，不是"设计一套完整 UGC 平台"。这份 spec 因此刻意比 [M2 spec](../m2-mvp-scene-playable/spec.md) 小得多——不新增任何声明式能力/组件（房间/物品/NPC 的表达力保持 M2 交付时的样子），只做三件事：①给场景数据加一层"包"外壳（manifest：id/版本/可选创作者字段）；②让引擎能被指向加载**引擎自身数据目录之外**的一个包（而不是像 M1/M2 一样永远加载 `engine/data/` 下硬编码的场景文件）；③交付一个不启动完整游玩循环、可反复快速迭代用的校验模式（人或 Agent 写包时用它当"评审台"，因为正式 Web 评审台是 [ADR-0006](../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md) 明确的 post-MVP 产品）。全部工作落地后，用一个刻意选择**非武侠题材**的最小示例包走一遍"创作→加载→可玩"，证明引擎与题材包之间的边界是真实的、题材无关的（对齐 CLAUDE.md"项目一句话"），而不是"因为一直只跑武侠内容而没被检验过"的一条隐藏假设。

## Problem Statement

M1 与 M2 交付的场景 YAML 加载器（`load_scene`）已经证明"机制归引擎、内容归题材包"这条边界在**官方**内容上成立——但引擎目前只知道怎么加载它自己 `engine/data/` 目录下两份硬编码路径的场景文件（`m1_default_scene.yaml`/`m2_mvp_scene.yaml`），`python -m openmud` 与 `scenes.build_world()` 都没有任何方式指向仓库之外、由别人写的一份内容。场景数据也没有任何"这是谁的包、什么版本"的自我描述——`SceneLoadError` 报错时定位到文件路径与字段键，但没有"包身份"这个概念。换句话说，"题材无关的核心引擎"这半句项目宣言目前完全没有被检验过：迄今为止加载过的两份场景数据都是仓库自带的、且都是同一个武侠题材，"引擎真的能装下引擎作者从未设想过的、外部写的、甚至完全不同题材的内容"这条最基本的 UGC 承诺还停留在架构意图层面，没有一次真实的端到端验证。同时，创作者（人或 Agent）今天若想试写一份内容包，唯一的反馈方式是启动真实游玩循环（`run_repl`）从错误消息里摸索——没有一个"我刚写的这份包语法对不对、字段全不全"的快速迭代通道，而 [ADR-0006](../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md) 已经明确"游戏内编辑器"与"Web 评审台"都不是引擎该做的事，引擎侧唯一该留的是"内容包加载/校验契约"。

## Solution

按 [03 号票 Refinement](../mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 与 [ADR-0005](../../docs/adr/0005-m3-ugc-loop-creation-surface.md) 拍板的最小切片，落地三块能力 + 一次示例内容包的完整走通：

- **块 A（内容包外壳：manifest）**：在现有场景 YAML（`scene.yaml`）旁边加一份最小 manifest（`manifest.yaml`：必需 `id`/`version`，可选 `creator`/`title`，其余字段透传不丢——延续 M1/M2 已验证的"已知字段集 + 透传"手法）。**内容包** = 一个目录，装这两份文件；manifest 与场景内容是两个独立文件、两套字段集，不往现有 `scene_loader` 的已知顶层段集合里加东西（场景数据本身的表达力零变化）。
- **块 B（指向加载）**：引擎新增一个组合入口 `load_pack(pack_dir) -> (World, EntityId)`：读 manifest、校验、再委托给现有 `load_scene(pack_dir/"scene.yaml")` 加载场景内容，把 manifest 挂到 `World` 上（运行时态，不进存档——与 `world.nature`/`world.ai` 同构，restore 后从 `pack_dir/manifest.yaml` 重新读回）。命令行入口新增 `--pack <目录>`，指向仓库任意位置（不要求在 `engine/` 之下）的一个内容包目录，取代默认的官方场景加载路径；默认行为（不传 `--pack`）与今天完全一致，不破坏已发布的 M1/M2 行为。
- **块 C（校验模式，不玩）**：命令行入口新增 `--validate`（须配合 `--pack`），只做"读 manifest + 走 `load_scene` 全部结构性校验"，成功打印一行确认（含 id/版本/校验通过的房间数等摘要），失败打印现有 `SceneLoadError`/新 `PackManifestError` 一致风格的定位诊断，两种情况都不启动 REPL、不接触存档目录——这是留给创作者/Agent 反复快速迭代用的"评审台的最小替身"，不是评审台本身（真正的 Web 评审台是 [ADR-0006](../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md) 点名的 post-MVP 独立产品，届时应该直接复用这条校验契约，而不是引擎内嵌 UI）。
- **块 D（一次真实走通：非武侠示例包 + 端到端证明）**：手写一个**故意选择非武侠题材**的最小内容包（3 个房间量级，复用块 A~C 落地前就已存在的能力——门锁、物品、NPC 问答、NPC 商店、货币，零新增声明式能力），存放在 `engine/data/` 之外的一个位置（证明"包外"不是一句空话），用它跑通"手写内容 → `--pack` 指向加载 → `--validate` 校验通过 → 真实玩一条完整路径"，并留一条端到端测试锁死这条路径不回归。

## User Stories

### 块 A：内容包 manifest

1. 作为题材包创作者（人或 Agent），我想在我的内容包目录里放一份 `manifest.yaml`，填上这个包的 `id`（唯一标识）与 `version`（版本号），以便这份内容有一个独立于"文件叫什么名字"的身份，供引擎、未来的存档、未来的创作者平台识别"这是哪个包、哪个版本"。
2. 作为题材包创作者，我想可选填一个 `creator` 字段留名，以便未来创作者归属/分成这类支撑点（[06 号票](../mvp-scope/issues/06-scaling-commercialization-support-points.md) 支撑点 #2）有数据可用，即便 M3 本身不实现任何归属校验/分成逻辑。
3. 作为题材包创作者，我想 `manifest.yaml` 缺少 `id`/`version`，或者这两个字段不是字符串时，得到一条清晰指明"缺什么/类型不对"的报错（不是裸 Python 异常堆栈），以便快速定位是 manifest 写错了、不是场景数据写错了——两类错误的报错来源应该可以一眼区分。
4. 作为引擎开发者，我想 manifest 里出现的、`id`/`version`/`creator`/`title` 之外的未知字段原样透传保留（不报错、不丢弃），延续 M1 「11 号票」已经验证过的"已知字段集 + 透传"手法，以便未来 manifest 需要新字段（如题材标签、封面图路径）时是纯新增，不是破坏性变更。

### 块 B：指向加载

5. 作为运行引擎的人，我想执行 `python -m openmud --pack <目录>`，引擎从指定目录加载这个内容包并进入真实可玩的 REPL 循环，而不是像今天一样只能加载引擎自带的两份场景文件之一，以便验证"内容包可以来自任何地方，不需要塞进 `engine/data/`、不需要重新打包发布引擎才能玩到新内容"。
6. 作为运行引擎的人，我想不传 `--pack` 时引擎行为与今天完全一致（加载 `engine/data/m1_default_scene.yaml` 默认场景，存档路径不变），以便这条新能力是纯新增，不影响已经在跑的默认路径与已有测试。
7. 作为终端玩家，我想在 `--pack` 模式下正常存档/退出/重新启动能恢复到上次进度（与默认模式的崩溃恢复级耐久语义一致），以便"包外内容包可玩"这句话包含"可以持续玩、不是一次性 demo"这层含义。
8. 作为引擎开发者，我想 `--pack` 模式下的存档目录默认落在该内容包目录自己的子目录下（而不是复用 `engine/save/`），以便同一台机器上多个不同的外部内容包各自的存档天然互不污染，不需要额外的手动路径管理。
9. 作为引擎开发者，我想指向了一个不存在的目录、缺 `manifest.yaml`、或场景数据本身有结构性错误（缺字段/引用了不存在的房间等）时，引擎在启动阶段就给出清晰报错并以非零退出码结束（不是加载到一半崩溃、也不是静默用默认场景顶替），以便"包坏了"这件事在启动那一刻就能被发现，不会在玩到一半才炸出堆栈。

### 块 C：校验模式

10. 作为题材包创作者，我想执行 `python -m openmud --pack <目录> --validate`，引擎完整走一遍"读 manifest + 加载场景数据的全部结构性校验"但不启动 REPL、不触碰任何存档目录，成功则打印一行确认摘要（如"校验通过：<id> v<version>，N 个房间"），以便我在反复改内容包的过程中有一个秒级的反馈通道，不用每次改完都真的进世界走一遍才知道有没有写错字段。
11. 作为题材包创作者，我想校验失败时看到的报错风格与真的启动游玩时看到的报错完全一致（同一份 `SceneLoadError`/`PackManifestError` 消息），以便"校验模式"与"真的加载"用的是同一套校验代码，不会出现"校验说过了、一启动却报另一种错"的不一致体验。
12. 作为未来的创作者 Web 平台开发者（post-MVP，[ADR-0006](../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md) 点名"验证应复用引擎侧包校验契约/CLI，而非在引擎内嵌 UI"），我想这条校验能力是一个稳定的命令行契约（可被子进程调用、看退出码与标准输出/错误即可判断通过与否），而不是只能在交互式 REPL 里手动看结果，以便未来平台可以直接 shell 出去调用它，不需要引擎为"给它提供校验服务"这件事再单独开一套 API。

### 块 D：非武侠示例包 + 端到端走通

13. 作为项目验证者，我想有一个真实存在、可运行的示例内容包，题材与"侠客行"武侠世界完全无关（如科幻/废弃设施），存放在 `engine/data/` 之外的一个位置，以便"题材无关"不是一句宣言，而是有一份可以指给任何人看、任何人可以亲手 `--pack` 加载并玩一遍的证据。
14. 作为终端玩家，我想这个示例包本身是一段完整、可玩通的小体验（有起点、需要拾取物品解锁一处通路、能与一个 NPC 问答互动、能在 NPC 处用货币买东西、有一个明确的终点房间），以便它不只是"三个空房间"式的语法验证，而是确确实实体现了"引擎已有的通用能力（移动/门锁/物品/NPC 问答/NPC 商店/货币）在一个从没设计给它用的题材上依然直接可用，不用碰引擎代码"。
15. 作为引擎开发者，我想这个示例包在编写过程中如果撞上某个"declarative 数据表达不了、只能靠加新引擎能力才能实现"的诉求，按 [03 号票 Refinement](../mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 的既定原则记成一条 GAP 说明（写进本 spec 或后续票据的 Comments），而不是借机新增引擎能力/扩表达力——这条示例包的价值在于"证明现有能力edge 到边"，不是"顺手再扩点表达力"。
16. 作为项目验证者，我想有一条自动化测试沿着这条完整路径跑一遍（`--pack` 加载 → 走完整条剧情路径的命令序列 → 断言每一步的可观察结果），以便这条"创作→加载→可玩"闭环被锁死为回归测试，不是一次手动跑完就再也没人验证过的孤证。

## Implementation Decisions

**内容包目录结构（A1）**

- 一个内容包是一个目录，固定包含两个文件：`manifest.yaml`（本 spec 新定义）与 `scene.yaml`（现有 `load_scene` 已经认识的格式，字段集**零改动**）。**不支持**目录里有多份场景文件拼接（对齐 [M2 spec](../m2-mvp-scene-playable/spec.md) H2 已经做过的同一个决定："一份不算太大的 YAML 完全够用，多文件拼接留给需要多个题材包并存时再设计"——M3 仍然不是那个"需要"出现的时间点，见 Out of Scope）。
- 为什么是"目录 + 两个独立文件"而不是"在 `scene.yaml` 顶层加一个 `pack:` 段"：manifest 关心的是"这份内容是谁的、什么版本"（供应链/身份问题），场景数据关心的是"这个世界长什么样"（内容问题），两者是完全不同的关注点、不同的读者（前者未来给平台/账本消费，后者给场景加载器消费）。混进同一份文件的同一层字段集会污染 `scene_loader._TOP_LEVEL_KNOWN_SECTIONS`（现有 `rooms`/`items`/`npcs`/`player`/`skills`/`factions`/`death_policy` 七个顶层段，全部是"世界内容"语义），也会让"只想读个 id/version 而不想解析整份场景"这个未来常见操作（如平台列表页展示已上架的包）被迫触发一次完整场景加载。分文件是零成本的关注点分离，不是过度设计。

**`PackManifest` 与 `load_manifest`（A2，纯函数层）**

- 新模块 `openmud.pack`，新数据类 `PackManifest(id: str, version: str, creator: str | None = None, title: str | None = None, extra: dict = field(default_factory=dict))`。`extra` 收纳 `id`/`version`/`creator`/`title` 之外的未知字段（透传手法，同 M1 11 号票/M2 场景加载器已验证的模式）。
- `load_manifest(pack_dir: Path) -> PackManifest`：读 `pack_dir/manifest.yaml`，校验 `id`/`version` 必需且为字符串；文件不存在、YAML 语法错误、顶层不是映射、`id`/`version` 缺失或类型不对，统一抛新错误类型 `PackManifestError`（下条）。这是一个不依赖 `World`/`scene_loader` 的纯粹"给一个路径，读出一个校验过的数据对象或抛错"函数，与 M1/M2 已经验证过的"纯函数直测"seam 同构（如 M2 的 `resolve_attack`、条件求值器）。

**`PackManifestError`（A3）**

- 新增在 `openmud.errors`（与 `SceneLoadError` 同一模块，同样的"避免循环 import + 错误类型不挂在消费者模块上造成心智错位"理由）。消息格式延续 `SceneLoadError` 已确立的风格：带路径、带具体缺失/类型不对的字段名。两种错误类型**不合并成一种**：manifest 校验与场景内容校验是两个不同的验证阶段（先读身份、再读内容），分开的错误类型让调用方（`--validate` 模式的诊断输出）能在需要时区分"包的身份信息本身就有问题"与"包的世界内容有问题"，尽管 M3 阶段两者的处理方式（打印消息 + 非零退出）完全一样。

**`load_pack` 组合入口 + `World.pack_manifest`（B1）**

- `openmud.pack.load_pack(pack_dir: Path) -> tuple[World, EntityId]`：调 `load_manifest(pack_dir)`，再调现有 `load_scene(pack_dir / "scene.yaml")`（**不修改** `load_scene` 一行代码——组合而非改造，这是本 spec 唯一必须成立的架构性约束：M3 不因为"要支持包外加载"而回头改动 M1/M2 已经验证过的场景加载器本体），把校验过的 `PackManifest` 挂到返回的 `world.pack_manifest` 字段上。
- `World` 新增字段 `pack_manifest: PackManifest | None = None`。定位与 `world.nature`/`world.ai`/`world.spawners`/`world.ferries` 完全同构：**运行时态、不进存档**（`save.py` 的序列化范围本 spec 不扩展一行——见下条为什么这样反而更简单）。默认（非 `--pack`，走 `scenes.build_world()`）路径 `pack_manifest` 始终是 `None`，行为对已有默认场景零影响。

**存档恢复后的 `pack_manifest` 重建（B2，复用既有"运行时态不进存档、restore 后重挂"模式，不新开一条持久化路径）**

- 不扩展 `save.py`：`world.scene_path` 已经在存档 `world_meta.json` 里被持久化（05 号票既有机制），`--pack` 模式下这个值天然就是 `<pack_dir>/scene.yaml` 的绝对路径，**pack 目录本身可以从它推出来**（`scene_path.parent`）。因此 restore 之后只需要一步"重新挂载"：`openmud.pack.reattach_pack_manifest(world)`——若 `world.scene_path` 存在且其同级目录下有 `manifest.yaml`，重新读一遍填回 `world.pack_manifest`；否则留 `None`（默认场景走这条路径天然是 no-op，因为 `engine/data/` 下没有 `manifest.yaml`）。这与 `__main__.py` 现有 restore 分支里 `attach_nature`/`attach_ai_system`/`attach_ferries`/`attach_combat_system`/`attach_entry_guards` 的"运行时态不持久化、restore 后按幂等函数重挂"是同一种手法的第 N 次复用，不是新发明一种持久化策略——这个决策直接消灭了"要不要扩展 `world_meta.json` 格式"这个原本以为需要做的工作项（一个真正的 prefactor 式简化，不是偷懒）。

**CLI：`--pack` 与 `--validate`（C1）**

- `openmud/__main__.py` 新增 `argparse`（当前 `main()` 不接受任何参数，需要引入）：`--pack PATH`（可选；缺省保持现有"加载 `DEFAULT_SCENE_PATH`/走 `has_save`/`restore_world` 默认存档目录"行为不变）、`--validate`（须搭配 `--pack`；单独出现报参数错误，非零退出，不静默忽略）。
- `--pack` 分支的存档目录：`<pack_dir>/save/`（与官方默认路径 `engine/save/` 同构的"数据目录旁边放存档目录"惯例，见 `scenes.py`/`__main__.py` 现有 `DEFAULT_SAVE_DIR` 的推导方式）。启动时若该子目录已有存档（`has_save`）走 restore（含 B2 的 `reattach_pack_manifest`），否则 `load_pack(pack_dir)` 全新加载；错误处理与现有 `main()` 的 `SceneLoadError` 分支同构，新增 catch `PackManifestError`（提示信息前缀区分是"包清单"还是"场景内容"出的错）。
- `--validate` 分支：只调 `load_pack(pack_dir)`（复用同一份校验逻辑，不写第二套），成功打印一行摘要到 stdout 并 `sys.exit(0)`；捕获 `PackManifestError`/`SceneLoadError` 打印到 stderr 并 `sys.exit(1)`；**不**创建/触碰 `<pack_dir>/save/`、不进入 `run_repl`。校验模式下即便 `<pack_dir>/save/` 已有存档也**不去 restore**（校验的是"这份包现在的样子加载起来对不对"，不是"某个存档还原得对不对"——两件事故意不混，校验应该对同一份包每次给出确定性结果，不受某次游玩产生的存档状态影响）。
- 为保持 `main()` 可测试（延续 `cli.py`/`run_repl` 已确立的"不用真实 subprocess/stdin 测试 CLI 逻辑"原则），把"解析参数→选择分支→返回退出码"这部分拆成一个不直接调 `sys.exit` 的纯函数（如 `_main(argv: list[str]) -> int`），`main()` 本身只是 `sys.exit(_main(sys.argv[1:]))` 这一行胶水；测试直接调 `_main([...])` 断言返回码与（用 `capsys`/临时替换 stdout）打印内容，不 fork 子进程。

**非武侠示例包（D1）**

- 内容：一个"废弃探测站"迷你科幻场景，3 个房间（气闸舱起点、补给舱、主控室终点），一道上锁的门（补给舱→主控室，钥匙是补给舱里能捡到的通行卡——复用 M1 04 号票已经交付的门/钥匙机制，零新代码），主控室里一个 NPC（维修机器人，复用 M2 的 `inquiry` 问答与 `shop` 商店能力出售一件物品），玩家带初始货币（复用 M2 的 `Currency`）。刻意**不用**任何战斗/技能/门派/坐骑相关字段——这些字段依然可用（表达力没有缩水），只是这份示例故意选择"用引擎能力子集也能撑起一个完整可玩闭环"，讨论价值不需要覆盖 M2 交付的每一寸能力面，那是 [engine/scripts/verify_m2_*.py](../../engine/scripts/) 已经在做的事。
- 位置：`.scratch/m3-ugc-loop-creation-surface/example-pack/`（与本 spec/票据同目录树，明确不在 `engine/`、不在 `engine/data/` 之下——这是"包外"最直接的证据：即便它物理上仍在同一个 git 仓库里，它也不在引擎自己的数据目录里，`--pack` 指向它时引擎代码走的是完全通用的路径解析，不存在任何"因为路径恰好在 `engine/` 之下所以能识别"的隐藏耦合）。测试侧再额外用 `tmp_path` 复制一份跑一次（结构性证明"任意磁盘位置"，不依赖仓库内固定路径这一点本身）。
- **GAP 记录（若实现中撞到）**：若示例包设计过程中发现现有声明式字段撑不起某个"非武侠题材更自然的说法"（如科幻题材更想叫"能量值"而不是"气血"），这类是**题材包侧的命名/文案自由度**，不是引擎表达力缺口（引擎的 `Vitals`/`Currency` 等字段名是英文标识符，中文展示文案完全由题材包 YAML 提供，M2 spec 已确立这条边界）——本条只记录真正"declarative 数据结构表达不了"的缺口，若走到实现阶段发现没有这类缺口（大概率，因为示例包刻意只用已验证过的能力子集），则本条无需真的写出任何 GAP。

## Testing Decisions

- 延续 M1/M2 已确立的测试 seam 分层，不新增测试基础设施：
  - **纯函数直测**：`load_manifest`（给定临时目录里的 `manifest.yaml` 内容，断言成功解析/各类缺字段类型错误场景下的 `PackManifestError` 消息）——不涉及 `World`/`scene_loader`。
  - **组合层 seam**：`load_pack`（给定一个临时构造的最小合法内容包目录，断言 `world.pack_manifest` 字段值与 `load_scene` 本该产出的世界状态一致；再给一个 manifest 合法但 `scene.yaml` 故意引用不存在房间的坏包，断言抛出的仍是现有 `SceneLoadError`——证明组合没有吞掉或篡改场景层的错误）。
  - **restore 层 seam**：走一遍"`load_pack` → 存档 → 全新 `World`/`restore_world` → `reattach_pack_manifest`"，断言恢复后的 `world.pack_manifest` 与恢复前一致、`world.scene_path` 仍指向包内的 `scene.yaml`（不是被 restore 逻辑意外改写成默认路径）。
  - **CLI seam**：直接调 `_main(argv)`（不 fork 子进程），覆盖：无参数（默认行为不变，走已有测试覆盖，本 spec 只需回归确认不炸）、`--pack 合法目录`（返回码与是否进入 `run_repl` 的可观察副作用）、`--pack 不存在目录` / `--pack 目录但缺 manifest.yaml` / `--pack 目录但 scene.yaml 结构性错误`（对应报错与非零退出码）、`--pack X --validate` 成功与失败两种路径（stdout/stderr 内容 + 退出码，不进入 `run_repl`、不产生 `<pack_dir>/save/`）、`--validate` 不带 `--pack`（参数错误，非零退出）。
  - **端到端剧本测试**：对 `.scratch/m3-ugc-loop-creation-surface/example-pack/` 跑一条完整命令序列（look → 拾取通行卡 → 解锁门 → 进入主控室 → 与 NPC 问答 → 购买物品 → 确认到达终点房间的可观察描述），断言每一步返回消息里的关键信息（对齐 M1/M2 已确立的"断言外部可观察行为，不断言内部实现细节"原则）。同一条剧本另配一份 `engine/scripts/verify_m3_pack_loop.py`（转录给人看，`just verify-m3` 收口，风格对齐 `engine/scripts/verify_m2_*.py`）。

## Out of Scope

- **正式 UGC DSL 设计**：manifest 与场景数据格式都不追求任何向后兼容承诺或版本协商机制（如"这份包声明它需要引擎 >= 某版本能力"）——那是留给 UGC 平台真正上线时才需要面对的问题，[03 号票](../mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 与 [ADR-0005](../../docs/adr/0005-m3-ugc-loop-creation-surface.md) 已明确"不要求一次定稿正式 DSL 语法"。
- **游戏内编辑器 / Web 评审工作台**：[ADR-0006](../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md) 已经把编辑器判为丢弃、Web 平台列入独立 post-MVP 产品；本 spec 的 `--validate` 是"给创作者一条能反复调用的校验契约"，不是这两者的替代品或缩水版，未来平台应该直接调用这条 CLI 契约，不是重新发明一套校验逻辑。
- **Ink 对话树 / RestrictedPython 逃生舱 / 任何脚本层**：[03 号票 Refinement](../mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 明确排除；`inquiry` 继续是静态问答表（不是对话树），本 spec 不新增任何"内容包可以携带可执行代码"的机制——这也是为什么"运行时安全护栏"这件事在 M3 阶段几乎不需要额外工作：内容包全程只是声明式数据（`yaml.safe_load`，天然不能定义可执行逻辑），风险面与"加载引擎自己的官方场景"完全相同，不因为"这份包来自外部/不受信"而多出新的攻击面；真正需要沙箱/权限模型是未来引入脚本层那一刻才该做的事（对齐 §19/§23 的既有教训：沙箱与运维权限模型现在都不存在，不要提前搭一个没有真实调用者的护栏）。
- **LLM Orchestrator / Agent 生成流水线**：[03 号票 Refinement](../mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 明确"人工写包也算打通"；本 spec 的示例包由人工（或 Agent 以文本创作者身份，非系统能力）手写，不交付任何"生成→校验→修订"的自动化编排系统。
- **多文件场景拼接 / 单进程多包共存**：见 A1 决策；`--pack` 一次进程只加载一个包，这与 [CLAUDE.md](../../CLAUDE.md) 架构不变量第 1 条"单机、不做分布式"、第 6 条"承载扩展靠题材包数量横向扩展（很多个独立单机世界并存），不是把一个世界做成分布式系统"完全兼容——事实上"一次进程一个包"这个约束不需要任何额外代码就自动满足了"每个题材包独立进程运行"这条 [06 号票](../mvp-scope/issues/06-scaling-commercialization-support-points.md) 支撑点 #4，值得在 Further Notes 里点出，但不构成本 spec 需要交付的工作项。
- **manifest 之外的题材包资产元数据完整方案**（双货币账本、消费/参与度埋点、创作者分成计算）：[06 号票](../mvp-scope/issues/06-scaling-commercialization-support-points.md) 明确这些是"架构支撑点，MVP 不要求实现"；本 spec 只落地 manifest 这一个最小切片（id/版本/可选创作者字段），不做账本、不做埋点、不计算任何分成。
- **`python -m openmud` 默认场景切换为 M2 官方 MVP 场景**：现状是不传任何参数时加载的是 M1 的极简默认场景（`m1_default_scene.yaml`），M2 的官方武侠内容目前只能通过 `scenes.load_mvp_scene()`（`engine/scripts/verify_m2_*.py` 直接在进程内调用）玩到，`python -m openmud` 从未被接到过它——这是一个与本 spec 目标无关的既有缺口（"默认玩到哪个场景"是产品选择问题，不是"UGC 闭环"问题），本 spec **不修复**它，只是顺带指出，避免被误认为遗漏（若要修，应该是一张独立的、单独讨论"默认场景该是什么"的票，不搭本 spec 的车）。

## Further Notes

- 本 spec 是刻意的"最小切片"而不是"顺手做大"——`/to-tickets` 阶段应该抵制住"既然要加 manifest，不如把版本协商/多文件拼接/资产元数据完整方案一起做了"的冲动：[07 号票](../mvp-scope/issues/07-governance-cost-tracking.md) 定义的 M3 验收标准就是"走完一次"，做多了反而偏离里程碑定义，且会把本该很小的一批票撑成不必要的规模。
- B2 的决策（`pack_manifest` 不进存档、restore 后从 `scene_path` 旁边的 `manifest.yaml` 重读）是本 spec 里最值得在 `/to-tickets` 时反复确认的一处——它把原本预期的"扩展 `save.py` 持久化格式"整个消除掉了，如果实现阶段发现这个假设不成立（比如未来某个理由要求 `pack_manifest` 必须在存档快照本身里可查，不依赖当时磁盘上是否还有那份 `manifest.yaml`），需要回来改这条决策，但那不应该是 M3 阶段就要预判的需求。
- 示例包故意选非武侠题材，是本 spec 里"验证成本最低、信号最强"的一个决定——不需要新写任何引擎代码，只需要老老实实用已有能力写一份完全不同风格的内容，就能把"题材无关"这条从项目一句话开始就存在、却从未被检验过的核心主张第一次落到一份可运行、可指给任何人看的产物上。
