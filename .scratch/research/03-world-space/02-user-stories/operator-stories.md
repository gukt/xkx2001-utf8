# 巫师/运营视角 User Stories：世界空间层

> 角色产出（UGC 游戏专家）。覆盖巫师/运营如何搭建与维护世界空间（地图拓扑 / Nature / 交通三层）。每条 Story 标注证据来源（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名）。
>
> 「巫师/运营」= 题材包创作者 + 世界维护者 + 运营人员，对应 LPC 的 wizard 角色与新引擎的 pack creator 角色。

## A. 房间与拓扑搭建

### A1. 摆一个新房间
作为题材包创作者，我想在 `scene.yaml` 的 `rooms:` 段加一个房间键，填 `name`/`long`/`outdoors`/`exits`，引擎加载时校验字段类型与目标房间存在性，以便我拼错出口目标时启动那一刻就报错而不是等玩家走到才发现断链。
- **证据**：LPC 对比 `d/village/alley1.c:14-17` `set("exits", (["east":__DIR__"sroad3"]))` 是无校验字符串路径；engine `scene_loader.py:580-584` `_build_exits` 校验 `target_key not in room_ids` 抛 `SceneLoadError`。

### A2. 连接两个区域
作为题材包创作者，我想用房间键（而非文件路径）连接两个区域（如华山村 `huashan_birth` 南出口指向扬州官道 `road_huashan_yz`），引擎在加载期校验所有跨区出口目标都已定义，以便我能放心构建跨区域拓扑而不用担心区域边界断链。
- **证据**：`m2_mvp_scene.yaml:9-11` `exits: { south: road_huashan_yz }`；engine 房间键引用 + `scene_loader.py:580` 全量校验。对比 LPC `d/taihu/matou2.c:14-16` 跨区仍用 `__DIR__"matou"` 字符串。

### A3. 检测孤岛房间
作为世界维护者，我想在加载/校验时得到「没有任何入口的孤岛房间」列表，以便我发现漏写了入口出口或误删了连接的房间，不让玩家永远无法到达的死房间混进发布包。
- **证据**：LPC 无此工具（6414 房间靠人眼）；engine `scene_loader.py` 当前**未实现**图遍历孤岛检测（只有出口目标存在性校验 `_build_exits:580`，无入度统计）。**这是缺口**。

### A4. 批量校验大世界
作为运营人员，我想对一个 6414 房间级别的题材包跑 `--validate`，在秒级时间内确认全部出口/门/渡口/NPC 引用都成立，以便我在发布前一次性扫出所有断链而不必人工走遍每个房间。
- **证据**：engine `--validate` 模式（M3 块 C，`m3-ugc-loop-creation-surface/spec.md` 块 C User Story 10）走 `load_scene` 全部结构性校验但不启动 REPL。当前校验覆盖出口目标（`scene_loader.py:580`）、渡口互指（`scene_loader.py:1425`）、商店引用（`scene_loader.py:1437`）、门派引用（`scene_loader.py:1474`），但**不覆盖**孤岛/死路/门两侧一致性。

## B. 门与通路

### B1. 单侧声明带钥匙的门
作为题材包创作者，我想在一个出口条目里声明「这扇门锁着、需要 X 物品当钥匙、解锁后一次性消耗钥匙」，引擎自动处理对岸门状态同步与钥匙扣除，以便我不必像 LPC 那样在两个房间各写一次 `create_door` 并手维护两侧一致性。
- **证据**：LPC `d/city/bingqiku.c:22` `create_door("north","铁门","south",DOOR_CLOSED)` 只建本侧，对岸 `bingyin.c` 须独立建；engine `scene_loader.py:728-744` `_exit_door` 单侧声明 `{door: locked, key: <物品键>, consume_key: true}`（`m2_mvp_scene.yaml:95-100` 翰林闺房门锁 + hanlin_key）。

### B2. 隐藏通道
作为题材包创作者，我想声明一扇「未解锁前在 exits 列表里不可见」的隐藏门，玩家解锁后才看到这条通路，以便我设计密室/暗道这类探索玩法而不用写运行时脚本。
- **证据**：engine `scene_loader.py:589-601` `hidden_until_unlocked: true` 进 `HiddenExits` 组件，声明期校验必须配 `door: locked`（`scene_loader.py:593-597`）。LPC 无此声明式能力，靠 room 逻辑脚本实现。

### B3. NPC 拦路
作为题材包创作者，我想声明「某出口被某 NPC 拦住，玩家需满足条件才能过」，引擎在 NPC 在场时拦截并给自定义拒绝文案，以便我设计「守门人放行」「交费过路」这类关卡而不用写 valid_leave 脚本。
- **证据**：engine `block_exits: {<方向>: {npc: <键>, deny_message: ...}}`（`scene_loader.py:612-658` `_attach_block_exits`；`m2_mvp_scene.yaml:101-103` ling_hanlin 拦西向）。LPC 靠 `room.c:267` `valid_leave` 脚本逻辑。

## C. 交通与跨区移动

### C1. 配置渡口两岸
作为题材包创作者，我想在两岸房间各声明 `ferry: {far_bank: <对岸>, cross_interval: <tick>, direction: <方向>}`，引擎校验两岸互相指向并自动驱动渡船周期切换可用出口，以便我不必像 LPC 那样手填 `boat`/`opposite` 字符串路径还担心写反。
- **证据**：LPC `d/taihu/matou2.c:20-22` `set("boat",...)` + `set("opposite",...)` 无配对校验，`ferry.c:70` 静默 `ERROR: boat not found`；engine `m2_mvp_scene.yaml:220-235` 两岸声明 + `scene_loader.py:1400-1434` `_resolve_ferry_refs` 互指校验 + `ferry.py:102` `_on_ferry_tick` 周期驱动。

### C2. 卖坐骑给玩家
作为题材包创作者，我想在一个 NPC 商店里挂「出售某坐骑」，声明坐骑的 `ability`/`jingli_max` 与价格，玩家购买后获得可骑乘的坐骑实体，引擎在骑乘移动时自动扣坐骑精力并在力竭时坠骑，以便我设计官道骑乘玩法而不用手写 horse.h 的 condition_check。
- **证据**：LPC `clone/horse/baima.c` + `horse.h:8-41` condition_check（含 jingli<=10 坠骑、<=30 喘气、<=mj/3 大口喘气、草地吃草恢复）；engine `m2_mvp_scene.yaml:535-554` yangzhou_horse mount 声明 + stable_groom shop 挂售；engine `commands.py:513-521` 移动 drain + jingli==0 昏厥+坠骑。**部分覆盖**：engine 无周期性衰减与中间警告与草地恢复。

### C3. 配置官道骑乘难度
作为题材包创作者，我想给官道房间设 `cost: 8`（陡坡）或 `terrain: <类型>`，引擎在玩家步行/骑乘时按地形消耗精力，骑乘还与坐骑 `ability` 比较（能力不足须下马步行），以便我用纯声明式数据控制移动节奏与骑乘门槛。
- **证据**：LPC `d/village/alley1.c:21` `set("cost",1)`；engine `Terrain` 能力 `known_fields={cost,terrain}`（`capabilities.py:1030-1036`）；`m2_mvp_scene.yaml:189` `cost: 8`（陡坡）；`commands.py:476` `if cost > mount.ability` 判定骑乘门槛、`commands.py:481-482` 步行 drain、`commands.py:513` 骑乘 drain。

### C4. 跨海航行（当前缺口）
作为题材包创作者，我想让玩家驾驶船只跨海探索（start/go/stop/lookout/locate 导航、海遇随机事件、天气影响航行），以便我设计航海类题材包--但当前引擎无任何玩家船支撑，我无法用声明式数据实现这类玩法。
- **证据**：LPC `inherit/room/ship.c`（591 行）`do_start`/`navigate`/`do_go`/`do_lookout`/`do_locate`/`shipweather`/`do_drop`（`ship.c:73-590`）+ 港口/岛屿硬编码 `seashape.h`（`ship.c:11`）；engine grep `engine/src/openmud/` 无 `ship`/`navigate`/`lookout`/`harbor`/`island` 模块。**这是真实表达力缺口**。

## D. Nature 环境配置

### D1. 自定义昼夜时段
作为题材包创作者，我想在场景顶层 `nature: day_phases:` 段声明自己题材的时段（如科幻包用「晨曦/日间/黄昏/夜深」4 段，每段 length/time_msg/desc_msg/rain_desc_msg），引擎按我声明的时长循环驱动并广播文案，以便我不必接受 LPC 固定的 8 时段武侠文案。
- **证据**：LPC `adm/etc/nature/day_phase` 固定 8 段（dawn/sunrise/morning/noon/afternoon/evening/night/midnight），全局共享；engine `m1_default_scene.yaml:173-194` 自定义 4 段 + `nature.py:145-163` `NatureState(phases=...)` 接受任意段数。

### D2. 房间局部 Nature 贴纸
作为题材包创作者，我想给特定房间贴「永远黑夜」「强制下雨」的局部 Nature，覆盖全局时段/天气，以便我设计鬼屋/密洞/幻境这类需要固定氛围的房间而不用改全局 Nature。
- **证据**：engine `LocalNature` 能力（`capabilities.py:1072-1078` `known_fields={"local_nature"}`）+ `EffectiveNature`（`nature.py:334-356` `resolve_effective_nature` 合成房间贴纸与全局）。LPC `natured.c` 是全局单例，所有户外房间共享同一 Nature，无此能力。

### D3. 户外广播到达校验
作为运营人员，我想确认哪些房间被标记 `outdoors: true` 并能收到 Nature 广播，以便我审计「该收广播的户外房没收到、不该收的室内房误收了」这类配置错误。
- **证据**：LPC 户外判定 `set("outdoors","xxx")`（`alley1.c:19`），`natured.c:71` `message("outdoor:vision", msg, users())` 全员广播；engine `Description` 能力 `known_fields={outdoors}`（`capabilities.py:1003-1008`），广播经 `on_nature_change` 事件 + 户外订阅者（`nature.py:282-284`）。**当前无运营侧户外房清单导出工具**。

## E. 维护与运营

### E1. 透传字段排查
作为世界维护者，我想排查「我写的字段被引擎静默透传吞掉、房间实际没生效」的情况（如 `outdoors` 拼成 `outdors`、`cost` 拼成 `cst`），以便我在 6414 房间规模下不被「字段生效了」的假象误导。
- **证据**：engine 未知字段透传到 `world.extension_data`（`world.py:71`）/ `entity_extension_data`（`world.py:266`），`scene_loader.py:174-177` 注释「透传不是设计、只是不丢弃」。**这是双刃剑**：保护向后兼容但让拼错静默失效。当前无「未识别字段警告」工具。

### E2. 包升级兼容性
作为运营人员，我想在引擎升级后用旧 manifest/scene 跑 `--validate` 确认旧题材包仍可加载，以便我判断升级是否破坏了已上架包的兼容性。
- **证据**：engine `load_pack`（`pack.py:63`）+ `--validate`（M3 块 C）；透传机制保证旧字段不报错（`world.py:71`）。但 `manifest.yaml` 无「依赖引擎版本」声明（`pack.py:25-33` `PackManifest` 只有 `id`/`version`/`creator`/`title`），无法提前声明兼容范围。

### E3. 多包存档隔离
作为运营人员，我想让不同题材包的存档天然隔离（每个包的存档落在自己的目录下），以便同一台机器跑多个外部包时存档不互相污染。
- **证据**：engine M3 块 B User Story 8（`m3-ugc-loop-creation-surface/spec.md`）明确「`--pack` 模式下存档目录默认落在该内容包目录自己的子目录下」；ADR-0009 单进程单 World 保证运行时隔离。

### E4. 非武侠题材验证
作为项目验证者，我想用一个非武侠题材的最小包跑通「创作->`--pack` 加载->`--validate` 校验->可玩」全流程，以便我证明「题材无关」不是宣言而是有证据的承诺。
- **证据**：M3 块 D `derelict-outpost` 科幻示例包（`m3-ugc-loop-creation-surface/example-pack/`，3 房间：气闸舱->补给舱->主控室，门锁+钥匙+NPC 问答+商店+货币），`issues/04` 记录「未发现 GAP，现有声明式能力足够」。

### E5. 图拓扑可视化（当前缺口）
作为世界维护者，我想把 `scene.yaml` 的房间拓扑导出为可视化地图（节点=房间、边=出口、门/渡口/拦路标注），以便我在大题材包里直观审查结构、发现死路与孤岛。
- **证据**：engine 当前**无此能力**（ADR-0006 明确编辑器/Web 评审台 post-MVP，`--validate` 只输出文本摘要如「校验通过：<id> v<version>，N 个房间」）。LPC 同样无编辑器。**这是 post-MVP 创作者工具需求**。

## F. 规模演进

### F1. 拆分大场景文件（当前缺口）
作为题材包创作者，当我的包长到数百房间时，我想把 `rooms:` 段拆分到多个 YAML 文件再 include 合并，以便我按区域分文件管理、git diff 审查友好、多人并行编辑不冲突。
- **证据**：engine `includes` 当前只允许 `items`/`npcs` 模板段（`scene_loader.py:200` `_INCLUDE_ALLOWED_SECTIONS = frozenset({"items","npcs"})`），**rooms 段不可拆分**。M3 spec A1 明确「不支持目录里有多份场景文件拼接」。**这是大题材包的硬约束**。

### F2. 坐骑变体复用（当前缺口）
作为题材包创作者，我想声明一组坐骑「模板」（共享 jingli 衰减/坠骑逻辑，只差属性数值与文案），引擎复用同一套运行时逻辑，以便我不必像 LPC 那样为每匹马手写一份 .c（22 个马匹文件大量重复）。
- **证据**：LPC `clone/horse/` 22 个独立 .c（baima.c/heima.c/hongma.c... 差异仅在 set_name/set 属性数值），`horse.h` 共享 condition_check；engine 坐骑声明已数据化（`m2_mvp_scene.yaml:542-545` mount 能力字段），**但无「坐骑模板继承/复用」机制**--每匹马仍是独立 NPC 模板条目。engine 的 `includes` 可复用 NPC 模板（`scene_loader.py:253` `_merge_includes_templates`），但只合并到模板段，不提供「基于模板覆盖少量字段」的继承。
