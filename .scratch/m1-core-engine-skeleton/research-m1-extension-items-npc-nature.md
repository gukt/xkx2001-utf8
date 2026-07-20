# M1 扩展调研综合：物品 / NPC / Nature + DSL 动态规则

> 2026-07-19 用户要求：M1 阶段不进 M2，深入打磨物品系统（全量命令、转移、容量、买卖、给与、唯一性、spawn）+ 引入 NPC + 引入 Nature（及与其他系统的关联：文案、门、条件规则判定）+ 打磨 DSL 动态规则与自定义逻辑表达。
>
> 本文是 4 个并行 subagent 调研（物品 / NPC / Nature / DSL 动态规则，精读 `docs/archive/xkx-arch/_archive/_侠客行 MUD 架构拆解说明书/` + LPC 源码 + 旧方案/避坑清单）+ [08 号票四档归类](../mvp-scope/issues/08-subsystem-classification-research.md) + [ADR-0004](../../docs/adr/0004-combat-effects-boundary-engine.md) + 当前引擎现状的综合。作为 M1 范围扩展的 `/to-spec` 输入。立场：LPC 是设计灵感与术语参考，不是规格源（ADR-0001）。

## 〇、原始调研报告索引（完整 subagent 输出）

本笔记是四份原始调研报告的**综合 + scope 决策**。每份原始报告含完整的逐维度分析、LPC 出处索引、DSL 草稿，比本笔记丰富，需要细节时直接查阅：

| 文件 | 调研对象 | 关键内容 |
|---|---|---|
| [research/01-items.md](research/01-items.md) | 物品系统 | 物品继承体系 / 命令全量 / 转移机制 / 容量重量 / 买卖 / 给与 / 唯一性 / spawn / 装备 / 金钱（10 维度）+ 3 个 DSL 草稿 |
| [research/02-npc.md](research/02-npc.md) | NPC 系统 | 继承链 / 属性 / AI 驱动 / 行为全量 / 对话 / 商店 / 任务 / 守卫 / 跟随 / spawn / 死亡（12 维度）+ 3 个 DSL 草稿 |
| [research/03-nature.md](research/03-nature.md) | Nature 系统 | **认知纠偏**（天气半成品 / 季节 / 随机事件不存在）+ 全景 + 11 维度 + 6 个系统关联详尽展开 + 4 个 DSL 草稿 |
| [research/04-dsl-dynamic-rules.md](research/04-dsl-dynamic-rules.md) | DSL 动态规则 | 旧四层与避坑清单逐条提炼（§4/§8/§12/§E/§T/§F/§21/§23/§28/§29/§37 等）+ ADR-0004 推广 + 5 范式对比 + 5 个 DSL 草稿 + 事件点清单 |

下文各块（A/B/C/D）的结论均可在对应原始报告中找到完整论证；本文引用时标注如"见物品调研维度 3"即指 [01-items.md](research/01-items.md) 的维度 3。

## 一、调研全景与认知纠偏

重要的认知纠偏（LPC 实际比拆解文档描述的窄 / 不同，源码验证）：

1. **Nature 实际比文档描述窄**（`adm/daemons/natured.c` 194 行验证）：天气是声明了 `weather_msg` 数组但**未接线**的半成品；季节系统不存在；"自然事件"只是固定时辰触发的固定函数（`event_sunrise`/`event_common`），不是随机事件。所以新引擎做"天气+季节+随机事件"本质是**从零设计**，不是复刻。
2. **NPC 无 talk 命令**：对话全走 `ask <npc> about <topic>`；`living.c` 不存在（"living" 是 driver efun 状态 `enable_commands`，非类）；商店 `buy/sell/list/value` 靠 NPC 手动 `add_action` 注册（过时机制，命令存在性依赖玩家在场且 NPC init 过）。
3. **物品 F_UNIQUE 是行为不是标志**：唯一性靠 spawn 时检查全局克隆数自毁，是行为（spawn 检查）而非字段标志；金钱是特殊物品（继承 COMBINED_ITEM，有重量可堆叠可掉落）。
4. **避坑清单是已验证过的坑**（`01-关键修正与避坑清单.md`，权重最高）：Effect 必须可序列化组件禁闭包（§4/§29）；随时间推进挂 tick（§8）；多规则按 any/all 聚合不互斥（§12）；持续效果声明 tick/wallclock 时间模式（§T）；面向 UGC 表达式进受限 AST 不用裸 Python lambda（§F）；对话带交易走原子节点（§21）；短延迟内存态 vs 长周期持久态分层（§37）；UGC 脚本用受限 Python 非 WASM（§23，已写进 CLAUDE.md 架构不变量第 5 条）。

## 二、三系统核心设计思想（对新引擎的启发）

### 物品：转移统一原语 + 能力维度组件化
LPC 是"基类骨架 + 特性混入（feature）+ 原型克隆"，能力维度 = 混入哪些 feature。**转移是统一原语（`move()`），容器/玩家/房间是"同一能力的不同实例"**。新引擎 `Container` 组件已走对路。启发：把 feature 映射为正交可选组件（`Stackable`/`Valuable`/`Equippable`/`Consumable`/`Unique`），按需挂载而非大而全 Item 组件。几个值得保留的好设计：`no_drop` 支持字符串自定义提示；装备效果用临时属性层施加、卸下用减法还原（天然适配 ECS：挂 EffectComponent / 卸下移除）；转移的"环境链上溯超重豁免"（从自己背的包拿东西不卡超重）。

### NPC：玩家/NPC 共用组件池 + 行为靠 chat() 声明式调度
LPC 的 CHARACTER 通过混入 14 个 feature 构建角色能力，NPC 只在其上叠加 `carry_object`/`random_move`/`chat` 等专属方法。玩家与 NPC 唯一区别是 `interactive()`/`userp()`。**feature = ECS 组件，inherit 链 = 组件组合预设**。启发：玩家与 NPC 挂同一批组件，区别只在是否挂 `AIController`/`PlayerSession` 驱动源组件。NPC 行为统一由 `chat()` 调度（字符串/函数指针塞 `chat_msg` + 概率触发，heart_beat 轮询）= 新引擎"tick 遍历 AIController 实体 + behavior.tick"。

### Nature：全局单例 + 被动查询 + 时辰切换广播
NATURE_D 是常驻单例，持有 `current_day_phase` + `day_phase` 配置，对外暴露极简查询接口。驱动是 `call_out` 定时器（非 heart_beat）。**重启靠真实时钟对齐，不存档**。关联以"被动查询"为主（房间 look 时查当前时辰 desc），唯一主动推送是时辰切换时给所有在线玩家发一条文案。启发：挂 TickLoop 推进、被动查询、重启对齐真实时钟、不存档；保留"时辰切换广播"。**散落各处的字符串比较条件判定是反例**，新引擎要做结构化条件表达式求值器。

### 共同指向：声明式数据 + 钩子注入（与 ADR-0004 同构）
三系统 + 战斗都指向同一个 DSL 形状："YAML 声明静态属性 + 受限 Python 钩子表达动态行为"。这正是 ADR-0004 的"骨架固定 + 钩子策略注入"手法。

## 三、贯穿三系统的架构主线

### ADR-0004 手法推广到非战斗系统
ADR-0004 拍板的战斗边界手法三要素：①声明式 policy 枚举（`StackingPolicy`/`EffectMode`）②Protocol 钩子（`SkillBehavior`）③注册表注入（`register_condition`）。这套手法可整体推广到非战斗系统，边界仍是"机制归引擎、内容/数值/具体行为归题材包"：

| 系统 | 引擎内嵌不变量（不可改） | 题材包经注册表/Protocol 注入 | 声明式 policy |
|---|---|---|---|
| 门/锁（M1 已有） | 门三态枚举 + go 遇非开则拒 | 锁策略钩子（密码/解谜/NPC 在场） | `LockPolicy: key_item\|password\|quest_flag\|custom` |
| 出口动态增删（M1 已有） | Exits.by_direction 运行时可增删 | 增删规则钩子 | `ExitChangePolicy: once\|reversible\|timed` |
| 物品使用 | use 骨架 + Effect 施加/移除 | `ItemUseHandler` 钩子 + 效果文案/数值 | `UsePolicy: consumable\|reusable\|cooldown` + `StackingPolicy` |
| NPC 对话 | 对话导航骨架 + 原子交易回滚（§21） | `DialogueHandler` 钩子 + 对话树 | `DialogueNodePolicy: narrative\|transaction\|quest` |
| Nature | tick 推进 + 广播机制 | `NaturePhaseHandler` 钩子 + 相位文案/效果 | `NatureEffectPolicy: cosmetic\|mechanical` |
| 房间文案拼接 | 占位符替换骨架 | 占位符取值函数 | （纯声明式，无 policy） |

### 当前 M1 缺一个核心基础设施（DSL 调研发现）
四系统动态规则要挂上去，但当前 M1 代码缺事件分发层：
- `commands.execute` 是 `handler(world, player_id, intent)` 直接调用，**无 before/after 钩子环绕**；命令处理函数直接 mutate 组件，无"前置校验可否决/后置通知"接缝。
- `TickLoop.advance` 只调 `save_fn`，**无"分发 tick 事件给订阅者"接缝**。
- `World` 是纯数据容器，**无事件总线/钩子注册表**（只有 `should_quit` 一个全局态）。

这是 M1 扩展必须先补的地基（空挂事件点，成本极低，不挂则 M2 要改引擎接口）。

### 通用条件表达式求值器是三系统共同地基
Nature 状态、门条件、物品限制、NPC 行为条件都需要"求值一个条件表达式"。LPC 用散落的字符串 if 比较是反例。新引擎做一个通用条件求值器（最小版：`phase == night` / `is_night` / `and`/`or`/`not` 布尔组合，求值查 Nature），是门/物品/NPC 三类动态规则的共同地基，也是 DSL 声明式条件表达式的解析器。

### DSL 分层（从零设计，不照搬旧四层，吸收"声明为主脚本为辅"精神）
```
层3 受限 Python 钩子逃生舱（<15% KPI，§22/§23）         M3
层2 事件触发器 on<event> when<cond> do<actions>          M1 预留事件点、不实现规则引擎
层1 声明式条件表（字段值/模板/枚举 policy/stacking）      M1 打磨核心
层0 静态场景数据（房间/物品/NPC/出口/门，M1 已有）          M1 已有
```

## 四、M1 scope 建议

按"引擎基础设施 / Nature / 物品 / NPC"四块，每块分必做/可选/推迟。

### 块 A：引擎基础设施（三系统共同地基，DSL 调研；详见 [research/04-dsl-dynamic-rules.md](research/04-dsl-dynamic-rules.md) 第六、八节）

**M1 必做**：
- **A1. 事件点/钩子环绕层（空挂）**：`on_tick` 订阅分发（`TickLoop.advance` 加 `dict[subscriber, handler]` 遍历，最核心）、`on_command_before`/`on_command_after`（`execute` 外环绕）、`on_before_enter_room`/`on_enter_room`/`on_leave_room`（`_cmd_go` 前后）、`on_get`/`on_drop`、`on_door_state_change`。空挂成本极低，不挂则 M2 改引擎接口。
- **A2. 通用条件表达式求值器最小版**：支持 `phase == night`、`is_night`、`and`/`or`/`not`，求值查 Nature。门/物品/NPC 动态规则地基。
- **A3. YAML 透传未识别段**：`scene_loader` 遇 `rules`/`on_use`/`effect`/`world_rules`/`dialogue` 等未识别段时不报错而透传到"扩展数据"容器，M1 不解析不执行只留着不丢。**"不锁死未来"的关键**，且不违反"M1 不预支 M3 设计"（透传不是设计）。
- **A4. 组件字段三态标注**：补"瞬时（运行时可变不进存档）"第三态（§28），当前已标"运行时可变 vs 启动固定"。

**M1 不做**：when/do 规则引擎（层2 解析执行）、受限 Python 钩子沙箱（层3，M3）、对话树/原子交易、Effect 系统、表达式语言解析器（受限 AST，M3）。条件表达式暂用 Python 字面量/字符串占位，但**形状按"未来可换受限 AST"设计**（不引入裸 Python lambda 作为字段值，§F）。

### 块 B：Nature 系统（08 票归类：现代化改造；用户主动提 M1；详见 [research/03-nature.md](research/03-nature.md)）

**M1 必做**：
- **B1. 时辰循环引擎**：数据驱动 day_phase 配置（YAML：phase 名 / length 分钟 / time_msg / desc_msg），挂 TickLoop 推进（比例可配，默认 60:1）。NatureState 纯内存，重启对齐真实时钟不存档。
- **B2. Nature 结构化查询谓词**：`phase` / `is_night` / `is_day` / `game_time_str`（不用 LPC 字符串比较反例）。
- **B3. 文案动态拼接**：Description 组件加 `outdoors` 字段；look 命令拼描述时户外房间追加当前时辰 desc_msg。
- **B4. 时辰切换广播**：时辰切换时给所有户外房间在线玩家推 time_msg（对应 LPC `message("outdoor:vision")`）。

**M1 可选**（有余量且不阻塞）：
- **B5. 天气晴雨骨架**：晴/雨两态按时辰 tick 随机切换 + NatureState.weather 字段 + `is_raining` 谓词 + 描述表升级为「时辰×天气」二维。不做对玩家影响。

**推迟 M2+**：NPC 作息、天气对战斗/移动/视野影响、季节、随机自然事件、天气影响物品可用性。

### 块 C：物品系统（08 票归类：物品继承 MVP 必做；当前基线 take/drop/inventory；详见 [research/01-items.md](research/01-items.md)）

**M1 必做**：
- **C1. 物品能力组件化（最重要架构决策）**：`Stackable`（amount+base_weight/unit）、`Valuable`（value）、`Equippable`（占位 slot+apply）、`Consumable`（占位）。为 M2 战斗/状态/经济干净接入。
- **C2. 转移统一原语 `transfer(item, src, dst)` + 校验钩子**（对应 LPC `reject`）：take/drop/put/give 收敛到一个底层函数。
- **C3. 堆叠**：Stackable + move 自动合并 + `take 数量` 拆分。
- **C4. 标志位 `no_get`/`no_drop`**（no_drop 支持字符串自定义提示，quest 物品刚需）。
- **C5. 容器物品**：物品可挂 Container（箱子/背包），put/take from 容器。
- **C6. look 物品增强**：long + 容器内容 + 数值（weight/value/堆叠数）。
- **C7. 重量与容量上限最小版**：weight 字段 + 容器 max_capacity + 超限拒绝放入。角色负重公式推迟 M2。

**M1 可选**：put 命令（依赖 C5）、give + accept_object 钩子、spawn 加载生成（已有 placed_in 雏形）、value 字段（纯数据）。

**推迟 M2+**：装备 wield/wear、消耗 eat/drink、买卖 sell/buy + 金钱支付、定期 reset 重生、唯一 spawn 检查（F_UNIQUE）、throw/steal、耐久磨损、环境链超重豁免。

### 块 D：NPC 系统（08 票归类：角色继承 MVP 必做 + NPC-AI 现代化改造；当前基线静态展示型；详见 [research/02-npc.md](research/02-npc.md)）

**M1 必做**：
- **D1. 行为机制地基组件**：`Behavior`（行为列表+调度元数据）+ `AIController`（驱动源标记+tick 频率）骨架，挂 TickLoop。搭"tick 遍历 AIController 实体 + behavior.tick(context)"骨架。不实现战斗行为。
- **D2. NPC 生成/重生地基**：场景 npcs 段加 `count`/`respawn`/`startroom`，挂低频 Spawn/Reset 扫描到 tick。LPC"唯一召回/多实例补齐"模式。M1 NPC 不死不触发重生，机制地基先埋。
- **D3. ask 对话命令 + inquiry 映射**：`ask <npc> about <topic>`，响应支持字符串 + 钩子。NPC 交互最低门槛。
- **D4. say 命令 + 房间事件广播**：say 广播同房间，触发 `on_hear_say` 钩子。
- **D5. Chatter 行为（第一个不依赖战斗的行为）**：LPC `chat_msg`+`chat_chance` 平移，NPC 按概率 tick 时 say 预设消息。DSL 动态规则试金石。

**M1 可选**：random_move 行为、give + accept_object 钩子、Disposition/Faction 组件骨架。

**推迟 M2+**：战斗相关全部行为（Aggro/attack/flee/死亡/尸体/掉落）、商店 NPC（Vendor）、任务 NPC 框架、师父 NPC、跟随者/宠物、守卫主动攻击、NPC 死亡、装备系统。

**关于"M1 是否引入有行为 NPC"**：调研倾向引入"轻量行为 NPC"（D1-D5），理由：①TickLoop 已就绪是最大机会 ②ask/say/Chatter 是不依赖战斗/状态/死亡的最小可信切片 ③DSL 动态规则第一批真实用例 ④不债留 M2。但这是对 M1 spec"NPC 行为 Out of Scope"的范围修订，需用户确认。

## 五、推迟 M2+ 清单（汇总）

- **战斗相关**（ADR-0004 边界已定，战斗推 M2）：Aggro/attack/accept_fight/accept_kill/flee/perform/cast、死亡/尸体/掉落、装备 wield/wear、消耗 eat/drink（依赖状态）、状态系统本体。
- **经济相关**：买卖 sell/buy/list/value、金钱支付、商店 NPC Vendor。
- **任务/师徒/宠物**：QuestGiver 状态机、师父收徒教技能、Tameable/Follow/忠诚度。
- **Nature 延伸**：NPC 作息、天气对战斗/移动/视野影响、季节、随机自然事件。
- **物品延伸**：定期 reset 重生、唯一 spawn 检查、throw/steal、耐久磨损。

## 六、已拍板的范围决策（2026-07-19，用户确认）

1. **NPC 深度**：**轻量行为 NPC**（D1-D5：Behavior/AIController 地基 + ask/say/Chatter，不碰战斗 + Spawn/Reset 重生地基）。是对 M1 spec "NPC 行为 Out of Scope" 的范围修订（类似 2026-07-18 YAML DSL 修订，需在 spec 加范围修订记录）。
2. **Nature 范围**：**时辰+条件求值器+文案+广播+天气晴雨骨架**（B1-B5 全做，含天气晴雨两态切换 + is_raining 谓词 + 时辰×天气二维文案，不做对玩家影响）。NPC 作息/天气影响/季节/随机事件推迟 M2+。
3. **物品组件化范围**：**全做能力组件占位**（C1 Stackable/Valuable/Equippable 占位/Consumable 占位 + C2-C7）。架构决策，为 M2 干净接入。
4. **金钱**：**M1 不引入**（买卖推迟 M2），Wallet 组件 vs money-as-item 的 ADR 推迟到引入买卖时再定。

最终 M1 扩展 scope = 块 A（A1-A4）+ 块 B（B1-B5）+ 块 C（C1-C7）+ 块 D（D1-D5），约 21 个必做项 + 若干可选项。推迟 M2+ 清单见第五节不变。

## 七、建议推进方式

这批 M1 扩展规模较大（A-D 四块，约 20+ 必做项），建议走结构化流程：
1. 用户拍板上述 4 个决策点（尤其 NPC 深度 + Nature 范围）。
2. 用 `/to-spec` 产出一个"M1 扩展"spec，或更新现有 M1 spec 加范围修订记录（类似 2026-07-18 YAML DSL 修订）。
3. `/to-tickets` 拆票，按 A/B/C/D 四块，注意依赖：**A 块事件点地基是 B/C/D 动态规则的共同前置**（A1 的 on_tick 给 B1 Nature 推进 + D1 NPC 行为 + 未来 Effect 衰减；A2 条件求值器给 B/Nature 门规则 + C 物品限制 + D 行为条件）。
4. 分批 `/implement`，每批过 `/code-review`。

止损线（07 号票）：某 ticket 落地到 `/implement` 后实际工作量超预估 3 倍强制停下重估；单 session 接近 smart zone（~120K token）无进展信号强制 `/handoff`。

## 附：四个 subagent 调研的核心 LPC 出处索引

- 物品基类/继承：`inherit/item/{item,combined,money}.c`、`inherit/misc/equip.c`、`feature/{move,unique,dealer,vendor,food,liquid,pill,equip}.c`
- 物品命令：`cmds/std/{get,drop,put,give,eat,wield,wear,unwield,remove,throw,steal,look}.c`、`cmds/usr/inventory.c`
- 金钱：`adm/daemons/moneyd.c`、`clone/money/{coin,silver,gold,thousand-cash}.c`、`feature/finance.c`
- NPC 继承：`inherit/char/{char,npc,master,trainee}.c`（注：`living.c` 不存在）
- NPC 行为：`feature/{attack,damage,team,unique,apprentice,vendor,dealer}.c`、`cmds/std/{ask,say,kill,give}.c`、`adm/daemons/chard.c`（make_corpse）
- Nature：`adm/daemons/natured.c`、`adm/etc/nature/day_phase`、`inherit/room/room.c`（门系统 + reset）、`cmds/std/{look,go,sleep}.c`、`d/zhongnan/gate.c`、`d/xingxiu/muding.c`
- 旧 DSL/避坑：`docs/archive/xkx-arch/_archive/03-DSL-UGC与Agent协作.md`、`docs/archive/xkx-arch/_archive/01-关键修正与避坑清单.md`
- 当前引擎：`engine/src/mud_engine/{components,commands,world,tick,scene_loader,intent,save}.py`、`engine/data/m1_default_scene.yaml`
