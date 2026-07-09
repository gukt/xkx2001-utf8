# 模式研究·DSL设计与脚本引擎（UGC剧情/场景配置）— XKX LPC→Python+WebSocket重构

## 概述
分析XKX 8412个LPC文件发现：30%为纯声明式数据(2531个replace_program房间)，70%含事件/对话/定时逻辑(1254个add_action、931个call_out、436个inquiry)。据此推荐分层混合DSL：声明式YAML核心(场景/角色/事件/对话树)+WASM沙箱脚本逃生舱。外部DSL自带语法、编译为JSON IR使运行时语言无关。多题材通过主题清单插件化，泛化现有19个武林门派模式。

## 模式
- **分层混合DSL架构（声明式核心 + 脚本逃生舱）**：层0 声明式内容清单(YAML：场景/出口/生成物/item_desc/属性)；层1 声明式事件规则(trigger+condition→action)；层2 Ink风格对话树；层3 WASM/Lua脚本逃生舱。分层依据是XKX代码实际分布：30%纯数据、70%含事件/对话/定时逻辑。每层失败可优雅降级到下层。
  - 适用性：直接映射XKX现有分布：2531个replace_program纯数据房间归层0，1254个add_action事件房间归层1，436个inquiry对话归层2，少量复杂技能/任务逻辑归层3
- **外部DSL + JSON IR编译目标**：为层0-2设计专用语法(YAML方言+规则/对话语法)，编译为JSON中间表示作为唯一真相源。运行时(Python)只消费JSON，与创作语法解耦。借鉴Ink编译为JSON、Ren'Py编译为.rpyc的做法。好处：可视化编辑器与文本编辑器双向同步、跨语言运行时、可静态校验。
  - 适用性：Python+WebSocket后端原生解析JSON IR无语言耦合；可视化编辑器消费同一IR；分布式节点只需分发JSON无需编译器
- **声明式事件规则（Condition→Action）**：事件=触发器(on_enter/on_command/on_give/on_attack/on_ask/on_tick/timer)+条件表达式+动作列表。条件表达式是纯函数式DSL over世界状态(query_flag/stat/inventory/relationship/time/probability)。动作有say/move/spawn/give/take/set_flag/schedule/log/run_skill/branch。直接对齐RPG Maker事件页(条件+触发+命令列表)与XKX的init/add_action/call_out模式。
  - 适用性：覆盖eproom.c的do_knock、xiaoer2.c的greeting/accept_object、collector.c的accept_object等大部分交互逻辑，无需写脚本
- **Ink风格对话树（knot/stitch/divert/weave）**：对话以knot(节点)/stitch(子节)/divert(跳转)/choice(选项)/weave(汇聚)/局部变量/条件分支为核心。XKX现有inquiry是扁平映射+闭包回调，用临时旗标(如ask_oil)做状态分支——本质是对话树的退化形式。Ink的weave/gather比手写状态机更简洁，是分支叙事最佳实践。
  - 适用性：迁移XKX的436个inquiry对话NPC；天然支持多题材分支叙事(武侠恩怨/大航海事件/穿越抉择)
- **WASM沙箱脚本逃生舱**：仅~5%复杂逻辑(技能定义/复杂任务/自定义战斗AI)用嵌入式脚本。首选WASM：内存安全、燃料计量(每tick指令预算)、能力化(无FS/网络除非授权)、近原生速度、语言无关(作者可用Rust/AS/Go)。轻量替代为Lua(沙箱env表+sethook指令限制)。对齐Blueprint编译到Kismet VM、Ink运行时嵌入宿主的思路。
  - 适用性：用户上传的UGC脚本一律走WASM；平台可信编辑者可用受限Python/Lua；技能/战斗这类高频逻辑用WASM保证性能
- **能力化安全模型（Capability-based）**：脚本不直接访问系统，只能调用显式授权的API(read_world/say/move_self/spawn_in_scene/schedule)。危险动作(move_player/destroy/persist/log_file)需提升权限。所有flag变更与spawn记审计日志。借鉴WASM capability model与seccomp思路，避免Lua/Python裸嵌入的安全敞口(XKX原LPC可任意destruct/find_living)。
  - 适用性：对应XKX的set_temp/query_temp状态机、log_file审计、destruct危险操作；UGC场景必须强制能力清单
- **资源配额与燃料计量**：每脚本每心跳指令上限、墙钟超时、内存上限、递归深度、call_out配额。燃料耗尽则中止(防无限循环)。对齐WASM fuel metering与Lua debug.sethook。XKX原有'Too long evaluation'错误即资源限制的雏形，DSL需显式化、可配置、按作者配额分配。
  - 适用性：对应XKX的heart_beat(全局tick)、call_out(调度)、condition.c(持续效果)、reset(场景重置)；UGC必须防死循环/炸弹
- **主题清单插件化（多题材核心机制）**：主题清单定义领域词汇：武侠(技能/内力/经脉/门派)、大航海(船只/货物/海战)、书院(科考/声望)、穿越(时代桥接)、现代(职业/社交)。每主题注册自己的条件谓词、动作动词、Actor属性。DSL核心主题无关，主题是插件。将XKX的19门派模式泛化为任意题材。
  - 适用性：XKX现有19个门派(kungfu/class/*)即是题材包雏形，各含NPC+技能+任务+房间；泛化后直接支持武侠/大航海/书院/穿越/现代
- **可视化双向编辑**：层0场景编辑器=节点网格(房间为节点、出口为边，类Twine/RPG Maker地图)；层1事件=Blueprint式节点连线(condition→action流)；层2对话=Ink风格流程图(knot→choice→knot)；层3脚本=代码编辑器。可视化与文本双向同步，YAML为真相源。覆盖从非技术作者(Twine式)到程序员(代码式)的全谱。
  - 适用性：场景图→Twine风格节点边图；对话图→Ink风格流程图；事件流→Blueprint节点连线；技能→表单+效果链。YAML为canonical source
- **热重载与状态检查点**：文件监听→校验(schema+能力+资源预算)→编译JSON IR→在场景/事件/对话注册表原子切换→通知连接客户端重同步受影响场景。进行中的对话/任务状态通过检查点保留(XKX的set_temp旗标天然是存档点)。对齐Ren'Py的r键热重载与Ink的运行时重编译。
  - 适用性：迁移XKX时set_temp旗标即存档点；线上UGC作者改剧情不中断玩家；分布式场景注册表原子切换

## 适用性
- 纯数据房间(d/city/* 的 2531 个 replace_program 房间) → 层0声明式YAML，可1:1迁移
- 带事件钩子的房间(eproom.c 的 init/add_action，1254文件) → 层1事件规则
- 对话NPC(xiaoer2.c 的 inquiry + ask_me 闭包，436文件) → 层2对话树
- 定时/调度效果(call_out 的 do_back/kicking，931文件) → 事件规则的schedule动作 + 调度器
- 技能/武功系统(inherit/skill + kungfu/skill/*，exert_function/perform_action) → 技能定义 + WASM复杂逻辑
- 门派题材包(kungfu/class 下19个门派各自的NPC/技能/任务) → 主题清单插件，泛化为多题材
- 任务/剧情(collector.c 的 combat_exp门槛 + dalibook状态旗标 + log_file) → 条件表达式 + 全局状态 + 动作
- buff/状态系统(feature/condition.c 的 heart_beat持续效果) → on_tick事件 + 持续效果规则
- UGC多题材扩展(武侠/大航海/书院/穿越/现代) → 主题清单注册各自谓词/动作/属性，DSL核心不变

## 权衡
- 分层架构vs单一DSL：分层复杂度高、需维护多语法，但能精准匹配XKX内容分布(30%纯数据无需脚本、5%复杂逻辑需图灵完备)，单一方案要么过度(纯数据用脚本)要么不足(技能逻辑声明式表达不了)
- 外部DSL vs 内部DSL(Python builder)：外部DSL需写词法/语法/校验器且作者需学新语法，但获得严格校验、可视化友好、语言无关运行时、可控安全边界；内部DSL开发快但绑定Python且难以沙箱化
- WASM vs Lua vs 受限Python：WASM最安全最快且语言无关但工具链重(作者需会编译到WASM)、调试难；Lua轻量生态成熟但沙箱需手工加固、性能次之；受限Python开发体验好但彻底沙箱极难(AST/RestrictedPython有旁路)。建议WASM用于不可信UGC、Lua用于可信作者
- 声明式事件规则 vs 通用脚本：声明式可校验可可视化可热重载，但表达力有上限(复杂状态机/算法需逃生舱)；通用脚本灵活但难校验难可视化难限资源。80/20原则：声明式覆盖80%场景
- Ink对话树 vs 自研：Ink模型成熟(分支叙事最佳实践)但有学习曲线且部分XKX对话是命令式(ask_me带副作用)；自研可贴合XKX语义但重复造轮子。建议以Ink语义为基、扩展副作用动作节点
- 可视化双向编辑：实现成本高(需同步算法、冲突解决)，但显著降低UGC门槛；代价是YAML与图必须双向一致。可分阶段：先只读可视化、后双向
- JSON IR为真相源 vs YAML直接执行：多一层编译增加复杂度与调试距离，但换来可视化/跨语言/静态校验/预分发。对分布式高并发场景值得

## 推荐
- 采用分层混合DSL：YAML声明式(层0场景数据)+事件规则(层1 condition→action)+Ink对话树(层2)+WASM脚本逃生舱(层3)。不要用单一方案——纯声明式无法表达技能逻辑，纯脚本对30%纯数据房间是浪费
- 层0-2用外部DSL(YAML方言+规则/对话语法)，编译为JSON IR作为唯一真相源；运行时Python只消费JSON，与创作语法解耦，便于可视化双向编辑与跨节点分发
- 对话树直接采用Ink的knot/stitch/divert/weave模型——XKX现有inquiry+临时旗标本质是对话树退化形式，Ink的weave比手写状态机简洁得多
- 脚本逃生舱首选WASM(内存安全+燃料计量+能力化+近原生速度+语言无关)，而非裸Lua/Python；UGC一律走WASM，可信编辑者可用受限Python
- 安全模型用显式能力清单(read_world/say/move_self/spawn_in_scene/schedule)，危险动作(move_player/destroy/persist/log_file)需提升权限；对齐XKX的set_temp状态机+log_file审计但显式化
- 多题材通过主题清单插件化：DSL核心主题无关，每主题注册自己的条件谓词/动作动词/Actor属性。XKX现有19门派(kungfu/class/*)即是题材包雏形，直接泛化即可支持武侠/大航海/书院/穿越/现代
- 可视化编辑分三档：场景图(Twine式节点边图)、对话图(Ink式流程图)、事件流(Blueprint式节点连线)；YAML为canonical source，可视化与文本双向同步
- 热重载流程：文件监听→校验(schema+能力+资源预算)→编译JSON IR→注册表原子切换→通知客户端重同步；用set_temp旗标做存档点保留进行中状态
- 资源限制显式化可配置：每脚本每心跳指令上限、墙钟超时、内存上限、递归深度、call_out配额、燃料耗尽即中止(对齐XKX原'Too long evaluation'但可配置、按作者配额)
- 迁移优先级：先把2531个纯数据房间批量转YAML(层0，工作量小收益大)，再转436个inquiry对话为对话树(层2)，最后处理技能/复杂任务逻辑(层3 WASM)；事件房间(层1)作为中间过渡
