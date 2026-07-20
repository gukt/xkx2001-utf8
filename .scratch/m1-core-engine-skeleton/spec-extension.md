Status: ready-for-agent

# M1 扩展 - 物品 / NPC / Nature + DSL 动态规则深化

> 本 spec 是 [M1 spec](spec.md)（"空场景 + 命令-移动-存档最小闭环"骨架基线，01~06 号票已 resolved，166 测试全绿）的**范围扩展**，不是替代。原 spec 的 Problem Statement / Solution / 对象模型 / 命令调度 / 心跳 / 存档 / CLI 前端等基线决策继续生效，本 spec 只在其上深化四块能力。
>
> 依据：[CLAUDE.md 架构不变量](../../CLAUDE.md) 全 8 条 + [ADR-0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md)（不做行为等价）+ [ADR-0002](../../docs/adr/0002-engine-workspace-greenfield-reset.md)（绿场重写）+ [ADR-0004](../../docs/adr/0004-combat-effects-boundary-engine.md)（战斗/效果边界，"骨架固定 + 钩子策略注入"手法）+ [08 号票四档归类](../mvp-scope/issues/08-subsystem-classification-research.md) + [调研综合笔记](research-m1-extension-items-npc-nature.md)（4 subagent 调研 + scope 决策，2026-07-19 用户拍板）。LPC 源码与旧架构文档仅作设计灵感/术语参考，不是规格源（ADR-0001）。
>
> 范围与 seam 已与用户核对确认（2026-07-19，见本 session 对话）：独立扩展 spec（不改原 spec.md）；测试 seam 沿用 `execute_line` + `tick_loop.advance` 两个现有 seam，条件求值器纯函数直接测。

## Problem Statement

M1 骨架基线已落地"空场景 + 命令-移动-存档最小闭环"，但只覆盖了移动/查看/拾取丢弃/门与锁/存档这几条最浅的机制。要让 M2（一个 MVP 场景端到端可玩）能干净推进，必须先在 M1 阶段把四块共同前置能力打磨扎实，否则 M2 要么反复改引擎接口、要么背着半成品子系统往前走：

1. **引擎缺事件分发基础设施**：`commands.execute` 直接调 handler、无 before/after 钩子环绕；`TickLoop.advance` 只调 `save_fn`、无 tick 事件分发；`World` 是纯数据容器、无钩子注册表。ADR-0004 拍板的"声明式 policy + Protocol 钩子 + 注册表注入"手法要推广到非战斗系统（门/物品/NPC/Nature），当前 M1 代码缺这块共同地基--不补则 M2 引入 Nature 时辰推进、NPC 行为、物品使用效果时都要回头改引擎接口。
2. **物品只有 take/drop/inventory 基线**：没有能力组件化、堆叠、容器、重量容量、标志位--M2 引入战斗装备、经济买卖时没有干净的接入点。
3. **NPC 只有静态展示型**（06 号票改判进 M1 的"房间摆件"）：没有任何行为、不能对话。要让 NPC 在 M2 之前的"不依赖战斗/状态/死亡"的最小可信切片先跑起来（ask 对话、say 广播、Chatter 闲聊），为 DSL 动态规则提供第一批真实用例。
4. **没有 Nature 系统**：昼夜时辰、天气都不存在，房间文案纯静态--这是"随时间推进的世界演化"在 M1 的唯一自然落脚点，也是条件求值器第一个真实查询源。
5. **DSL 动态规则表达**：当前 YAML 是纯静态数据，未识别段会被加载器忽略或报错。要为未来 UGC 创作层（M3）的动态规则预留"不锁死"的演进空间--预留事件点 + 透传未识别段，但 M1 不实现规则引擎、不预支 M3 设计。

这五件事的共同特征是：它们都是"机制归引擎、内容/数值/具体行为归题材包"这条 ADR-0004 边界在非战斗系统的延伸，且彼此互为地基（事件点是 Nature/NPC/物品的共同前置；条件求值器是门/物品/NPC 动态规则的共同子语言）。M1 阶段把它们一次打磨到位，M2 引入战斗/经济/状态/任务时就能直接挂载，不需要重新设计驱动机制或存储形状。

## Solution

在 M1 骨架基线上，落地四块相互咬合的深化能力（块 A/B/C/D），每块都按"引擎内嵌机制不变量 + 题材包经注册表/Protocol 注入内容"这条 ADR-0004 手法组织：

- **块 A（引擎基础设施，三系统共同地基）**：补事件点/钩子环绕层（`on_tick` 订阅分发 + 命令 before/after + 移动/物品/门事件点，空挂调用）+ 通用条件表达式求值器最小版 + YAML 未识别段透传 + 组件字段三态标注。空挂成本极低，不挂则 B/C/D 要改引擎接口。
- **块 B（Nature 系统）**：数据驱动的时辰循环引擎（挂 TickLoop 推进、纯内存、重启对齐真实时钟不存档）+ 结构化查询谓词（`phase`/`is_night`/`is_day`/`game_time_str`/`is_raining`）+ 户外房间文案动态拼接时辰/天气 + 时辰切换广播 + 天气晴雨两态骨架。
- **块 C（物品系统）**：能力维度组件化（`Stackable`/`Valuable`/`Equippable` 占位/`Consumable` 占位，按需挂载）+ 转移统一原语 `transfer` + reject 校验钩子 + 堆叠合并/拆分 + 标志位 `no_take`/`no_drop`（后者支持字符串自定义提示）+ 容器物品（put/take from 容器）+ look 物品增强 + 重量与容量上限最小版。
- **块 D（NPC 系统）**：行为机制地基组件（`Behavior` + `AIController` 骨架，挂 TickLoop 搭"tick 遍历 AIController + behavior.tick"骨架，不实现战斗行为）+ NPC 生成/重生地基（`count`/`respawn`/`startroom`，低频 Spawn/Reset 扫描挂 tick）+ `ask <npc> about <topic>` 对话命令 + `say` 命令 + 房间广播 + Chatter 行为（第一个不依赖战斗的行为，DSL 动态规则试金石）。

战斗/经济/任务/装备消耗/Nature 延伸全部推 M2+（[ADR-0004](../../docs/adr/0004-combat-effects-boundary-engine.md) 已定战斗边界）。本 spec 完全不涉及战斗/技能/状态/死亡轮回，因此可在 02 号票之后立即推进。

## User Stories

### 块 A：引擎基础设施（三系统共同地基）

1. 作为引擎开发者，我想 `commands.execute` 外包一层 `on_command_before` / `on_command_after` 钩子环绕（M1 空实现直接放行），以便未来"夜里 NPC 不卖酒""诅咒物品拿不起"这类前置否决规则有挂载点，M2 引入时不需要改 `execute` 签名。
2. 作为引擎开发者，我想 `TickLoop.advance` 增加"tick 事件订阅者分发"机制（一个按订阅 key 路由的注册表 + 遍历调用），M1 唯一订阅者仍是 `save_fn`，以便 Nature 时辰推进、NPC 行为、未来 Effect 衰减都挂在同一个统一驱动点上。
3. 作为引擎开发者，我想移动路径预留 `on_before_enter_room`（可否决）/ `on_enter_room` / `on_leave_room` 事件点（挂在 `_cmd_go` 前后），空挂调用，以便"门锈住打不开""进房触发 NPC 反应"这类规则有触发点。
4. 作为引擎开发者，我想物品路径预留 `on_take` / `on_drop` 事件点（可否决），空挂调用，以便"任务物品不能丢""诅咒物品拿不起"这类规则有触发点。
5. 作为引擎开发者，我想门路径预留 `on_door_state_change` 事件点，空挂调用，以便"门被打开触发机关""门状态联动出口增删"这类规则有触发点。
6. 作为引擎开发者，我想事件点钩子签名尽量通用（如命令前置 `(world, player, intent) -> Allow | Deny | Replace`），并用契约测试锁定形状，以防 M2 引入真实规则时签名不够用要改接口。
7. 作为引擎开发者，我想钩子经 `register_xxx(name, handler)` 挂进引擎，与 `commands.register` 同构（ADR-0004 的 `register_condition` 同源），以便题材包把自己的策略/钩子注入引擎而引擎不知具体实现。
8. 作为引擎开发者，我想有一个通用条件表达式求值器最小版，支持 `phase == night` / `is_night` / `and` / `or` / `not` 布尔组合，求值时查 Nature 状态，以便门条件、物品使用限制、NPC 行为条件共用同一个条件子语言地基，而不是各自散落字符串 if 比较（LPC 反例）。
9. 作为引擎开发者，我想条件表达式字段形状按"未来可换受限 AST"设计（白名单运算符、无副作用、无循环、深度上限），M1 暂用结构化 Python 字面量/字符串占位但**不引入裸 Python lambda 作为字段值**，以便 M3 落地受限表达式解析器时不需要回头改 DSL 字段形状（避坑清单 §F）。
10. 作为未来题材包创作者（M3 UGC 筹备），我想 YAML 场景文件里在房间/物品/NPC/出口下写 `rules:` / `on_use:` / `effect:` / `world_rules:` / `dialogue:` 等未识别段时，加载器不报错而是透传到一个"扩展数据"容器留着不丢（M1 不解析不执行），以便 M2/M3 引入动态规则解析时旧场景数据不必重写。
11. 作为引擎开发者，我想组件字段标注三态--"运行时可变且进存档" / "启动固定" / "瞬时（运行时可变不进存档）"，补上当前缺失的第三态（避坑清单 §28），以便未来"短延迟内存态 vs 长周期持久态"分层有标注依据（避坑清单 §37）。
12. 作为引擎开发者，我想事件点注册表与钩子 Protocol 是 ADR-0004 手法在非战斗系统的直接推广，与战斗侧的 `SkillBehavior` / `register_condition` / `StackingPolicy` 同构，以便全引擎只有一套"机制归引擎、内容归题材包"的接缝手法。

### 块 B：Nature 系统

13. 作为终端玩家，我想游戏世界有昼夜时辰循环，户外房间的描述会随时辰变化（如"夜深了，庭院一片寂静"），以便感受到世界在随时间演化，而不是永远停在一个静态时刻。
14. 作为终端玩家，我想时辰切换时收到一条文案提示（如"天渐渐黑了"），以便我感知到时间在流动。
15. 作为引擎开发者，我想时辰相位配置数据驱动（YAML：phase 名 / length 分钟 / time_msg / desc_msg），挂 TickLoop 推进（比例可配，默认 60:1），以便题材包自定义相位序列与文案，引擎只管推进机制。
16. 作为引擎开发者，我想 Nature 状态纯内存、重启时按真实时钟对齐当前相位而不进存档，以便不增加存档负担（Nature 是衍生状态，可从真实时钟重算，对应 LPC `natured.c` 的重启对齐行为）。
17. 作为引擎开发者，我想 Nature 暴露结构化查询谓词 `phase` / `is_night` / `is_day` / `game_time_str`，供条件求值器与命令处理函数查询，而不是用 LPC 那种散落字符串比较反例。
18. 作为终端玩家，我想有晴 / 雨两种天气按时辰 tick 随机切换，户外房间描述升级为"时辰 × 天气"二维（如"白天，下着小雨"），以便世界更有生气。
19. 作为引擎开发者，我想 Nature 暴露 `is_raining` 谓词，与 `is_night` 同级，供条件求值器查询天气条件。
20. 作为引擎开发者，我想户外房间用 `Description` 组件加一个 `outdoors` 字段标记（而非新建专属组件），look 渲染时户外房间才追加当前时辰/天气 desc，室内房间不追加，以便"是否户外"这条属性与描述文本内聚在同一组件。
21. 作为引擎开发者，我想时辰切换广播走"给所有户外房间在线玩家推一条 time_msg"机制（对应 LPC `message("outdoor:vision")`），挂在 `on_nature_change` 事件点（M1 落地，因为它就是 Nature 切换时触发），以便广播机制本身可复用于未来天气变化。

### 块 C：物品系统

22. 作为引擎开发者，我想把物品能力拆成正交可选组件 `Stackable`（amount + base_weight/unit）、`Valuable`（value）、`Equippable`（占位 slot + apply 钩子）、`Consumable`（占位），按需挂载而非大而全 Item 组件，对应 LPC"基类骨架 + feature 混入"映射为 ECS 组件，以便 M2 战斗装备、经济买卖、状态消耗干净接入。
23. 作为引擎开发者，我想 take/drop/put/give 收敛到一个底层转移原语 `transfer(item, src, dst)` + reject 校验钩子（对应 LPC `reject` 机制），所有转移走同一路径，以便转移的校验/事件/堆叠合并逻辑只写一份。
24. 作为终端玩家，我想同类可堆叠物品放入容器时自动合并成一堆，`take <物品> <数量>` 可以从一堆里拆出指定数量，以便物品栏不被同名物品刷屏。
25. 作为终端玩家，我想某些物品拿不起来（`no_take`，如固定家具）或丢不掉（`no_drop`，且 `no_drop` 支持自定义提示文案，如"这是任务物品，不能丢弃"），以便任务物品与固定场景物件有合理行为。
26. 作为终端玩家，我想把物品栏的物品放进房间里的箱子（`put <物品> in <容器>`）、从箱子里拿出（`take <物品> from <容器>`），以便管理物品与发现隐藏内容。
27. 作为终端玩家，我想 `look <物品>` 能看物品的 long 描述、若是容器还能看里面装了什么、若是堆叠/有价值/有重量能看数值，以便了解物品详情。
28. 作为终端玩家，我想容器有重量与容量上限，把超重或超容量的物品放进去会被拒绝并给提示，以便世界有合理的物理约束。
29. 作为引擎开发者，我想 `no_drop` 的自定义提示字符串、`Stackable` 的 amount、`Valuable` 的 value 等都是声明式数据字段（非闭包/函数，避坑清单 §29），动态计算字段（如"长描述随天气变"）运行时求值不进存档，以便存档可序列化、可恢复。
30. 作为引擎开发者，我想物品装备效果用"挂临时属性层、卸下用减法还原"的方式施加（天然适配 ECS：挂 EffectComponent / 卸下移除），M1 只占位 `Equippable` 不实现具体装备效果，以便 M2 战斗装备直接复用这套施加/移除机制。
31. 作为未来题材包创作者，我想物品的 placed_in、堆叠、价值、重量、标志位等都在 YAML 显式声明（不开"任意键"口子，避坑清单 §B4），以便场景数据可静态校验、AI 生成准确率高。

### 块 D：NPC 系统

32. 作为引擎开发者，我想新增 `Behavior`（行为列表 + 调度元数据）+ `AIController`（驱动源标记 + tick 频率）两个组件骨架，挂 TickLoop，搭"tick 遍历所有 AIController 实体 + 逐个 behavior.tick(context)"骨架，M1 不实现战斗行为，以便 M2 引入 Aggro/attack 时直接挂载。
33. 作为引擎开发者，我想玩家与 NPC 挂同一批基础组件（Identity/Description/Position/Container），区别只在是否挂 `AIController`（NPC 驱动源）/ `PlayerSession`（玩家驱动源）这个驱动源组件，对应 LPC"玩家与 NPC 唯一区别是 `interactive()`/`userp()`"，以便玩家与 NPC 共用组件池。
34. 作为引擎开发者，我想场景 npcs 段支持 `count` / `respawn` / `startroom` 字段，挂低频 Spawn/Reset 扫描到 tick，对应 LPC"唯一召回 / 多实例补齐"模式，M1 NPC 不死不触发重生但机制地基先埋，以便 M2 NPC 死亡重生时直接复用。
35. 作为终端玩家，我想 `ask <npc> about <topic>` 能向 NPC 提问，NPC 按预设 inquiry 映射返回字符串响应或走钩子，以便与 NPC 交互（这是 NPC 交互的最低门槛，对应 LPC `ask` 命令--LPC 无 talk 命令，对话全走 ask）。
36. 作为终端玩家，我想 `say <内容>` 能向同房间所有人广播一句话，并触发 `on_hear_say` 钩子，以便与房间内 NPC/玩家交流。
37. 作为终端玩家，我想 NPC 会按概率在 tick 时 `say` 预设的闲聊消息（Chatter 行为，对应 LPC `chat_msg` + `chat_chance` 平移），以便场景有生气，NPC 不再是纯静态摆件。
38. 作为引擎开发者，我想 Chatter 是"第一个不依赖战斗/状态/死亡的行为"，作为 DSL 动态规则的第一批真实用例（NPC 行为条件 + 概率 + 事件触发），以便验证事件点 + 条件求值器 + 注册表注入这套手法在非战斗场景确实成立。
39. 作为引擎开发者，我想 NPC 的可变状态（如未来库存计数、对话进度）能进存档（避坑清单 §L），M1 的 Chatter 无可变状态故不涉及，但 `Behavior` 组件形状要为"未来可变状态进存档"留好，以便 M2 NPC 有可变状态时不需要改存储形状。
40. 作为引擎开发者，我想 NPC 行为条件（如"只在夜里闲聊""只在玩家在场时说话"）用块 A 的条件求值器表达，不散落字符串比较，以便 NPC 行为规则与门/物品规则共用同一条件子语言。

### DSL 分层与不预支 M3

41. 作为未来题材包创作者，我想 M1 的 YAML 过渡格式保留"声明为主、脚本为辅"的分层精神（旧方案统计论据：约 30% 纯数据可声明、70% 含动态逻辑），但层数与每层职责从零定、不照搬旧四层，以便分层动机在新题材下依然成立而不背旧方案技术栈。
42. 作为未来题材包创作者，我想 M1 打磨层 1（声明式条件表：字段值/模板/枚举 policy/stacking）+ 预留层 2 事件点（`on<event> when<cond> do<actions>`，M1 只留事件点不实现规则引擎），层 3 受限 Python 钩子逃生舱与层 0 静态数据分别归 M3 与 M1 已有，以便动态规则有演进空间但不预支 M3 设计工作。
43. 作为引擎开发者，我想 M1 明确不做 when/do 规则引擎解析执行、不做受限 Python 钩子沙箱（RestrictedPython/fuel/能力令牌）、不做对话树/原子交易、不做 Effect 系统、不做表达式语言受限 AST 解析器--这些都推 M2/M3，M1 只"预留事件点 + 透传未识别段 + 条件求值器最小版"，以便不违反原 spec 反复强调的"M1 不预支 M3 设计"。
44. 作为项目架构师，我想 ADR-0004 的三要素（声明式 policy 枚举 + Protocol 钩子 + 注册表注入）整体推广到门/物品/NPC/Nature 全部非战斗系统，边界是"机制归引擎、内容/数值/具体行为归题材包"，以便全引擎只有一套接缝手法，战斗侧与非战斗侧同构。

## Implementation Decisions

> 贯穿四块的架构主线（来自 [调研综合笔记第三节](research-m1-extension-items-npc-nature.md)）：ADR-0004 拍板的"骨架固定 + 钩子策略注入"手法推广到非战斗系统。下表是这条主线的全貌，每块的具体决策在其后展开。

| 系统 | 引擎内嵌不变量（不可改） | 题材包经注册表/Protocol 注入 | 声明式 policy |
|---|---|---|---|
| 门/锁（M1 已有） | 门三态枚举 + go 遇非开则拒 | 锁策略钩子（密码/解谜/NPC 在场） | `LockPolicy: key_item\|password\|quest_flag\|custom` |
| 出口动态增删（M1 已有） | Exits.by_direction 运行时可增删 | 增删规则钩子 | `ExitChangePolicy: once\|reversible\|timed` |
| 物品使用（M1 占位） | use 骨架 + Effect 施加/移除（M2） | `ItemUseHandler` 钩子 + 效果文案/数值 | `UsePolicy: consumable\|reusable\|cooldown` + `StackingPolicy` |
| NPC 对话（M1 ask 骨架） | 对话导航骨架 + 原子交易回滚（M2） | `DialogueHandler` 钩子 + 对话树 | `DialogueNodePolicy: narrative\|transaction\|quest` |
| Nature（本扩展） | tick 推进 + 广播机制 | `NaturePhaseHandler` 钩子 + 相位文案/效果 | `NatureEffectPolicy: cosmetic\|mechanical` |
| 房间文案拼接（本扩展） | 占位符替换骨架 | 占位符取值函数 | （纯声明式，无 policy） |

### 块 A：引擎基础设施

**事件点/钩子环绕层（A1，空挂，最核心）**

- 引入一个事件总线/钩子注册表（挂在 `World` 上或独立模块，实现阶段定），按事件 key 路由到 handler 列表。注册接口与 `commands.register` 同构（ADR-0004 `register_condition` 同源）。
- `commands.execute` 外包 `on_command_before` / `on_command_after` 环绕：前置返回 `Allow` / `Deny` / `Replace`（M1 默认 `Allow` 直接放行）；后置可修饰消息列表。空实现不改现有 11 个命令的行为。
- `TickLoop.advance` 增加 `on_tick` 订阅者分发：`save_fn` 退化为 `on_tick` 的一个订阅者（或保留 `save_fn` 并额外分发 `on_tick`，实现阶段定，但 `on_tick` 分发机制必须就位）。M1 唯一订阅者仍是存档。
- 移动路径 `on_before_enter_room`（可否决）/ `on_enter_room` / `on_leave_room` 挂在 `_cmd_go` 前后；`on_traverse_blocked` 挂在出口存在但被门挡住时（可选）。
- 物品路径 `on_take` / `on_drop`（均可否决）挂在 `_cmd_take` / `_cmd_drop` 前后。
- 门路径 `on_door_state_change` 挂在门状态切换处。
- `on_nature_change` 挂在 Nature 相位/天气切换处（块 B 落地时填实，M1 块 A 只留调用点）。
- 事件点签名尽量通用并加契约测试锁定形状（同原 spec"解析失败信号形状被测试锁定"思路），防 M2 改接口。

**通用条件表达式求值器最小版（A2）**

- 纯函数模块：`evaluate(condition, context) -> bool`，`context` 提供 Nature 查询接口与玩家/世界状态。
- 最小支持：字面量谓词 `is_night` / `is_day` / `is_raining`、相等比较 `phase == night`、布尔组合 `and` / `or` / `not`。
- 表达式形状按"未来可换受限 AST"设计：M1 用结构化 Python 字面量（嵌套 tuple/dict 或小型 dataclass 表达式节点）占位，**不引入裸 Python lambda 作为字段值**（避坑清单 §F）。M3 落地受限 AST 解析器时换实现，不换字段形状。
- 多规则按 any/all 聚合不互斥（避坑清单 §12）。

**YAML 未识别段透传（A3）**

- `scene_loader` 遇 `rules` / `on_use` / `effect` / `world_rules` / `dialogue` / `behaviors` / `nature` 等未识别段时不报错，透传到一个"扩展数据"容器（挂在 world 或 entity 上的 dict）。
- M1 不解析不执行这些段，只"留着不丢"。这是"不锁死未来"的关键，且不违反"M1 不预支 M3 设计"（透传不是设计，只是不丢弃）。
- 已识别段（房间/物品/NPC/出口/门/玩家的现有字段）仍按现有校验逻辑处理；加载器对"已识别但值非法"（如 `door: ajar`）仍抛 `SceneLoadError`，对"未识别段"透传不报错--两者区分明确。

**组件字段三态标注（A4）**

- 现有 `components.py` 注释已标"运行时可变 vs 启动固定"两态。补第三态"瞬时（运行时可变不进存档）"（避坑清单 §28）。
- 成本极低（注释 + 存档序列化层的字段过滤依据），为 §37"短延迟内存态 vs 长周期持久态"分层铺路。
- 存档序列化（`save.py`）按三态决定哪些字段进存档：瞬时字段（如 Nature 衍生态、临时计数器）不进存档。

### 块 B：Nature 系统

**时辰循环引擎（B1）**

- 数据驱动 day_phase 配置（YAML：phase 名 / length 游戏分钟 / time_msg 切换文案 / desc_msg 描述片段），挂 TickLoop 推进。推进比例可配（默认 60:1，即 1 真实秒 = 60 游戏秒）。
- `NatureState` 纯内存组件（或 world 级状态），重启时按真实时钟对齐当前相位，不进存档（Nature 是衍生状态，可从真实时钟重算）。
- 默认相位序列题材无关（如 dawn/day/dusk/night 四相），题材包可自定义。

**结构化查询谓词（B2）**

- Nature 暴露 `phase` / `is_night` / `is_day` / `game_time_str` / `is_raining` 谓词，供条件求值器与命令查询。不用 LPC 字符串比较反例。

**文案动态拼接（B3）**

- `Description` 组件加 `outdoors: bool` 字段（标记是否户外，与描述文本内聚，不新建专属组件）。
- `look` 渲染时：户外房间追加当前时辰 + 天气 desc_msg（"时辰 × 天气"二维）；室内房间不追加。
- 文案模板占位符（`{time_phase}` / `{weather}`）M1 可不求值或走 `long_fallback` 回退，但形状按"未来占位符取值函数注册表"设计。

**时辰切换广播（B4）**

- 相位/天气切换时给所有户外房间在线玩家推一条 time_msg，挂 `on_nature_change` 事件点。对应 LPC `message("outdoor:vision")`。

**天气晴雨骨架（B5，M1 必做）**

- 晴 / 雨两态按时辰 tick 随机切换，`NatureState.weather` 字段 + `is_raining` 谓词。描述表升级为"时辰 × 天气"二维。不做对玩家机制影响（如视野/移动）。

### 块 C：物品系统

**物品能力组件化（C1，最重要架构决策）**

- 新增正交可选组件（来自 [物品调研原型](research/01-items.md)，type shape）：
  - `Stackable`：`amount` + `base_weight` / `unit_weight`，可堆叠合并。
  - `Valuable`：`value`（纯数据，金钱未引入故仅占位）。
  - `Equippable`：`slot`（占位）+ `apply` 钩子引用（M1 占位不实现具体装备效果）。
  - `Consumable`：占位（M1 不实现 eat/drink，依赖状态系统推 M2）。
- 按需挂载而非大而全 Item 组件。对应 LPC"基类骨架 + feature 混入"映射为 ECS 组件。
- 现有 `Identity` / `Description` 继续复用（物品已有）。

**转移统一原语 + 校验钩子（C2）**

- 新增底层 `transfer(world, item, src_container, dst_container) -> TransferResult`，take/drop/put/give 收敛到它。
- `TransferResult` 携带成功/失败 + 失败原因（`no_take` / `no_drop` / `over_capacity` / `over_weight` 等），由调用方翻译成玩家提示。
- reject 校验钩子（对应 LPC `reject` 机制）挂 `on_take` / `on_drop` 事件点，可否决转移。

**堆叠（C3）**

- `Stackable` 物品 `transfer` 到容器时，若目标已有同规范物品则合并 amount；`take <物品> <数量>` 从一堆拆出指定数量。
- 同规范判定（Identity.name 相同 + 同为 Stackable）由实现阶段定，需处理歧义（同名不同物）。

**标志位 `no_take` / `no_drop`（C4）**

- 物品可挂标志位组件或字段：`no_take`（拿不起，如固定家具）、`no_drop`（丢不掉，且 `no_drop` 支持字符串自定义提示，如"这是任务物品，不能丢弃"）。quest 物品刚需。
- `no_drop` 的自定义提示是声明式字符串字段（非闭包，避坑清单 §29）。

**容器物品（C5）**

- 物品可挂 `Container`（箱子/背包复用现有组件，不新建）。`put <物品> in <容器>` / `take <物品> from <容器>`。
- 容器可选 `open/closed` 状态（复用门思路还是独立，实现阶段定；M1 最小可先做"始终打开"）。

**look 物品增强（C6）**

- `look <物品>` 展示 long 描述 + 容器内容（若是容器）+ 数值（weight/value/堆叠数）。

**重量与容量上限最小版（C7）**

- `weight` 字段（Stackable 的 base_weight 或独立 Weight 组件，实现阶段定）+ 容器 `max_capacity` + 超限拒绝放入。
- 角色负重公式（cumulative weight → 移动惩罚等）推迟 M2，M1 只做"单容器超重/超容量拒绝"。

### 块 D：NPC 系统

**行为机制地基组件（D1）**

- 新增 `Behavior`（行为列表 + 调度元数据）+ `AIController`（驱动源标记 + tick 频率）组件骨架。
- 挂 TickLoop（走块 A 的 `on_tick` 分发）：tick 遍历所有 `AIController` 实体，逐个调 `behavior.tick(context)`。
- 不实现战斗行为（Aggro/attack/flee 推 M2）。
- 玩家与 NPC 挂同一批基础组件，区别只在驱动源组件（NPC 挂 `AIController`，玩家不挂或挂 `PlayerSession`，实现阶段定）。

**NPC 生成/重生地基（D2）**

- 场景 npcs 段加 `count`（实例数）/ `respawn`（重生开关）/ `startroom`（起始房间，与 `in_room` 关系实现阶段定）。
- 挂低频 Spawn/Reset 扫描到 tick（对应 LPC reset 机制）。M1 NPC 不死不触发重生，机制地基先埋。
- `Behavior` 组件形状为"未来可变状态进存档"留好（避坑清单 §L），M1 Chatter 无可变状态故不涉及。

**ask 对话命令 + inquiry 映射（D3）**

- `ask <npc> about <topic>`：解析层 NPC 候选为同房间、且挂 `Inquiry` 或 `NpcSpawnMeta` 的实体（排除玩家与裸 `Position` decoy）；topic 是自由 token。见「范围修订记录」2026-07-20。
- NPC 响应支持 inquiry 映射（topic -> 字符串响应）+ 钩子占位（`Inquiry.handler: str | None`，同 `Equippable.apply_hook`；M1 不执行）。对应 LPC `ask`（LPC 无 talk 命令）。
- 原子交易节点（带交易的对话，避坑清单 §21）推 M2，M1 ask 只做字符串响应。

**say 命令 + 房间广播（D4）**

- `say <内容>`：广播给同房间所有实体（玩家 + NPC），触发 `on_hear_say` 钩子。

**Chatter 行为（D5，DSL 动态规则试金石）**

- LPC `chat_msg` + `chat_chance` 平移：NPC 挂 `Behavior` 含 Chatter 行为（预设消息列表 + 触发概率），tick 时按概率 `say` 一条。
- 行为条件（如"只在夜里""只在玩家在场"）用块 A 条件求值器表达。
- 这是第一个不依赖战斗/状态/死亡的行为，验证事件点 + 条件求值器 + 注册表注入手法在非战斗场景成立。

### DSL 分层（从零设计，不照搬旧四层，吸收"声明为主脚本为辅"精神）

```
层3 受限 Python 钩子逃生舱（<15% KPI，避坑清单 §22/§23）         M3
层2 事件触发器 on<event> when<cond> do<actions>                  M1 预留事件点、不实现规则引擎
层1 声明式条件表（字段值/模板/枚举 policy/stacking）              M1 打磨核心
层0 静态场景数据（房间/物品/NPC/出口/门，M1 已有）                M1 已有
```

- M1 打磨层 1（声明式条件表）+ 预留层 2 事件点（空挂不实现规则引擎）。
- 层 3 受限 Python 钩子（RestrictedPython + fuel + 能力令牌，避坑清单 §23，已写进 CLAUDE.md 架构不变量第 5 条）推 M3。
- 条件表达式（层 1/2 的条件子语言）M1 用结构化字面量占位，形状按受限 AST 可解析设计（避坑清单 §F）。

### 硬约束（来自避坑清单，已用真实代码验证过的坑）

- 动态效果必须可序列化 Effect 组件，禁闭包（§4/§29）。M1 不做 Effect 但 DSL 字段形状预留。
- 周期类规则挂 `TickLoop`，不靠命令触发（§8）。
- 多规则按 any/all 聚合不互斥（§12）。
- 持续效果声明 tick/wallclock 时间模式（§T）。M1 存档是"崩溃恢复级耐久"，持续效果要能进存档、恢复后正确续算。
- 面向 UGC 的表达式进受限 AST 不用裸 Python lambda（§F）。
- 对话带交易走原子节点（§21）。M1 ask 不带交易。
- 短延迟内存态 vs 长周期持久态分层（§37）。
- UGC 脚本用受限 Python 非 WASM（§23）。
- NPC 本地可变状态进存档（§L）。M1 Chatter 无可变状态。

## Testing Decisions

- **测试只验证外部可观察行为**：给定一行命令输入或一次 tick 推进，断言返回消息内容/世界状态查询结果，不断言组件存储内部实现细节（如用了什么数据结构）。延续原 spec Testing Decisions。
- **两个 seam（沿用现有，零新 seam）**：
  - **命令路径 seam `execute_line(world, player_id, line)`**：所有玩家命令触发的状态变更（物品 put/give、ask/say、look 拼接 Nature 文案、门命令）。这是原 spec Further Notes 决策 2 已确立的最高 seam，现有 166 测试同款。
  - **时间推进 seam `tick_loop.advance()`**：所有 tick 驱动行为（Nature 时辰推进、NPC Chatter、Spawn/Reset 扫描、on_tick 钩子触发）。测试循环调 `advance()` 快进到目标相位/触发周期，断言世界状态/Nature 相位/NPC 副作用。这是原 spec tick 测试 seam 的扩展（原 tick 测试只测存档触发，本扩展首次测"tick 驱动行为"）。
  - **条件求值器纯函数直测**：`evaluate(condition, context) -> bool` 直接调，断言返回值。它也被上面两个 seam 间接覆盖（夜里 look 输出不同即证明求值器工作），但纯函数直接测更清晰、bug 更易定位。
- **钩子触发 seam（复用上面两个 seam）**：注册一个测试 handler（如计数器/记录参数），通过 `execute_line` 或 `advance` 触发对应事件，断言 handler 被调用且收到正确参数。这是"钩子被正确触发"的行为测试，不测注册表内部实现。
- **覆盖点**：
  - 块 A：事件点钩子在对应时机被触发且参数正确（命令 before/after、on_tick、移动/物品/门事件点）；条件求值器各谓词/运算符/组合正确；YAML 未识别段透传不丢且不报错、已识别段非法值仍报错；组件三态标注与存档过滤一致。
  - 块 B：时辰按配置推进、相位切换触发广播、户外房间 look 带时辰/天气、室内不带；Nature 谓词返回正确；天气晴雨切换；重启对齐真实时钟（用可注入的时钟避免测试依赖墙钟）。
  - 块 C：能力组件按需挂载；转移原语 take/drop/put/give 走同一路径且 reject 正确；堆叠合并/拆分；no_take/no_drop（含自定义提示）；容器 put/take from；look 物品 long+内容+数值；超重/超容量拒绝。
  - 块 D：tick 遍历 AIController 实体调 behavior.tick；ask 解析 NPC 候选 + topic 响应；say 广播同房间 + 触发 on_hear_say；Chatter 按概率触发（测试用确定性概率或断言"至少触发过"）；行为条件用条件求值器表达。
  - 存档与恢复（延续原 spec）：动态规则产生的可变状态（M1 主要是 Nature 不进存档、NPC Chatter 无可变状态）语义正确；瞬时字段不进存档、恢复后 Nature 从真实时钟重算。
- **Prior art**：现有 `engine/tests/` 下 e2e 测试已建立"构建 world -> 调 `execute_line`/命令函数 -> 断言返回消息与之后可查询的世界状态"这一结构（`test_commands.py` / `test_doors.py` / `test_scene_loader.py`）；`test_tick.py` 的"调 `advance()` -> 断言 `save_count`/世界状态"是 tick seam 的直接参照。M1 扩展新测试在写法上沿用，不复用具体断言。
- **时钟可注入**：Nature 重启对齐真实时钟，测试需可注入虚拟时钟（避免依赖墙钟导致测试不确定）。这与原 spec 存档测试"可注入 save_dir"同思路。

## Out of Scope

> 本节是与原 M1 spec Out of Scope 的叠加（原 spec 的 Out of Scope 仍生效，本节只列本扩展明确不做或推迟的）。其中"NPC 行为"是对原 spec Out of Scope 的范围修订（见「范围修订记录」），其余是新增的边界声明。

- **战斗、技能、状态/效果、死亡与轮回**：[ADR-0004](../../docs/adr/0004-combat-effects-boundary-engine.md) 已定边界，四子系统归类 MVP 必做但落地在 M2（有内容的题材场景可玩后）。M1 完全不涉及。`Equippable`/`Consumable` 只占位不实现效果。
- **经济/买卖/金钱**：`sell`/`buy`/`list`/`value`、金钱支付、商店 NPC（Vendor）推 M2。`Valuable.value` 只占位纯数据。Wallet 组件 vs money-as-item 的 ADR 推迟到引入买卖时再定。
- **任务/师徒/宠物**：QuestGiver 状态机、师父收徒教技能、Tameable/Follow/忠诚度推 M2+。
- **Nature 延伸**：NPC 作息（白天卖货/夜里睡觉）、天气对战斗/移动/视野影响、季节系统、随机自然事件推 M2+。本扩展只做时辰 + 天气晴雨骨架 + 文案 + 广播 + 条件查询。
- **物品延伸**：定期 reset 重生、唯一 spawn 检查（F_UNIQUE）、`throw`/`steal`、耐久磨损、环境链超重豁免推 M2+。
- **NPC 战斗相关行为**：Aggro/attack/accept_fight/accept_kill/flee/perform/cast、死亡/尸体/掉落、守卫主动攻击推 M2+。本扩展 NPC 行为只做 Chatter（闲聊）+ ask/say 对话，不碰战斗。
- **DSL 规则引擎**：when/do 规则解析执行（层 2）推 M2/M3。M1 只预留事件点 + 透传未识别段。
- **受限 Python 钩子沙箱**（层 3，RestrictedPython/fuel/能力令牌，避坑清单 §23）推 M3。M1 只在 DSL 形状上预留钩子引用字段。
- **对话树/原子交易**（避坑清单 §21）推 M2。M1 ask 只做字符串响应 + inquiry 映射，不带交易。
- **Effect 系统**：[ADR-0004](../../docs/adr/0004-combat-effects-boundary-engine.md) 已确认 Effect 归引擎，但落地在 M2 战斗/状态子系统时。M1 不做。
- **表达式语言受限 AST 解析器**（避坑清单 §F）：推 M3。M1 条件表达式用结构化字面量占位。
- **NPC random_move 行为、give + accept_object 钩子、Disposition/Faction 组件**：可选，有余量且不阻塞时做，否则推 M2。
- **组件类型强类型 schema 校验层**：原 spec 已明确不引入，本扩展延续。
- **网络协议层、登录/账号系统**：原 spec 已排除，本扩展延续。

## Further Notes

- **与原 M1 spec 的关系**：本 spec 是 [spec.md](spec.md) 的范围扩展，不替代。原 spec 的 Problem Statement / Solution / 对象模型 / 命令调度 / 心跳 / 存档 / CLI 前端等基线决策继续生效，本扩展在其上深化四块。原 spec 的"范围修订记录"已有 2026-07-18 YAML DSL 一条，本扩展新增 2026-07-19 修订（见下）。
- **推进方式与依赖**（来自 [调研综合笔记第七节](research-m1-extension-items-npc-nature.md)）：`/to-tickets` 拆票按 A/B/C/D 四块，注意依赖：**块 A 事件点地基是 B/C/D 动态规则的共同前置**（A1 的 `on_tick` 给 B1 Nature 推进 + D1 NPC 行为 + 未来 Effect 衰减；A2 条件求值器给 B Nature 谓词 + C 物品限制 + D 行为条件）。建议拆票顺序 A → B/C/D（B/C/D 之间相对独立，可并行）。分批 `/implement`，每批过 `/code-review`。
- **止损线**（07 号票）：某 ticket 落地到 `/implement` 后实际工作量超预估 3 倍强制停下重估范围；单 session 接近 smart zone（~120K token）无进展信号强制 `/handoff`。
- **已与用户确认的关键决策**（供 `/to-tickets` 与 `/implement` 对齐，不需重新讨论）：
  1. 独立扩展 spec，不改原 spec.md（原 spec 保持为骨架基线）。
  2. 测试 seam 沿用 `execute_line` + `tick_loop.advance` 两个现有 seam + 条件求值器纯函数直测，零新 seam。
  3. NPC 深度：轻量行为 NPC（D1-D5：Behavior/AIController 地基 + ask/say/Chatter，不碰战斗 + Spawn/Reset 重生地基），是对原 spec "NPC 行为 Out of Scope" 的范围修订。
  4. Nature 范围：时辰 + 条件求值器 + 文案 + 广播 + 天气晴雨骨架（B1-B5 全做），不做对玩家影响。NPC 作息/天气影响/季节/随机事件推 M2+。
  5. 物品组件化范围：全做能力组件占位（C1 Stackable/Valuable/Equippable 占位/Consumable 占位 + C2-C7），为 M2 干净接入。
  6. 金钱：M1 不引入，Wallet vs money-as-item 的 ADR 推迟到引入买卖时定。
  7. ADR-0004 手法推广到非战斗系统是贯穿四块的架构主线，全引擎一套接缝手法。
- **LPC 出处索引**（设计灵感/术语参考，不是规格源）：物品基类 `inherit/item/{item,combined,money}.c` + `feature/{move,unique,dealer,vendor,food,liquid,pill,equip}.c`；NPC `inherit/char/{char,npc,master,trainee}.c` + `feature/{attack,damage,team,unique,apprentice,vendor,dealer}.c`（注：`living.c` 不存在）；Nature `adm/daemons/natured.c` + `adm/etc/nature/day_phase`。完整索引见 [调研综合笔记附录](research-m1-extension-items-npc-nature.md) 与各原始调研报告。

## 范围修订记录

- **2026-07-19（M1 扩展定稿）**：用户要求 M1 不进 M2、深入打磨物品/NPC/Nature + DSL 动态规则。经 4 个并行 subagent 调研（物品/NPC/Nature/DSL，精读拆解说明书 + LPC + 旧方案/避坑清单）+ 用户拍板 scope（见 [调研综合笔记第六节](research-m1-extension-items-npc-nature.md)），改判/新增：
  1. **NPC 行为**：原 spec Out of Scope"NPC 的行为/AI...推到 M2 及以后"改判为 M1 内的"轻量行为 NPC"（D1-D5：Behavior/AIController 地基 + ask/say/Chatter + Spawn/Reset 重生地基，不碰战斗）。静态展示型 NPC（06 号票已改判进 M1）是本扩展 NPC 的无行为子集，本扩展在其上加行为。
  2. **Nature 系统**：原 spec 未涉及，新增为 M1 内（B1-B5：时辰循环 + 谓词 + 文案 + 广播 + 天气晴雨骨架）。Nature 在 08 号票四档归类为"现代化改造"，用户主动提进 M1。
  3. **物品能力组件化**：原 spec 物品只有 take/drop/inventory 基线（03 号票），本扩展深化为能力组件化（C1-C7），`Equippable`/`Consumable` 占位为 M2 接入。
  4. **DSL 动态规则**：原 spec"UGC/DSL 正式设计留给 M3"不变，本扩展做的是"预留事件点 + 透传未识别段 + 条件求值器最小版"（块 A），不预支 M3 设计。
  5. **事件分发基础设施**：原 spec 未涉及（当时命令直接 mutate、tick 只存档、world 无总线），本扩展补块 A 作为 B/C/D 共同地基。
  
  战斗/经济/任务/Nature 延伸/物品延伸仍推 M2+，本扩展 Out of Scope 已列。本修订不影响原 spec 已落地的 01~06 号票代码（ECS 存储/命令调度/解析/存档/tick 基线完全复用，只在其上扩展）。

- **2026-07-20（BCD re-pass / code-review 跟进）**：
  1. **ask 候选收窄**：D3 由「同房间任意 `Position`（排除玩家）」改为须挂 `Inquiry` 或 `NpcSpawnMeta`（`npc_query.is_askable_npc`），避免裸 Position 实体被当成可对话 NPC。
  2. **PlayerSession**：玩家驱动源显式组件；Nature 户外广播与 say 旁观判定改用它（废止 Container 启发式）。
  3. **restore 场景路径**：`world.scene_path` + 存档 `world_meta.json`，恢复后按原场景重读 `nature:`，不写死默认场景。
