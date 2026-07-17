# DSL、UGC 平台与 Agent 协作创作

> 这是用户重构愿景的核心。本方案已吸收 [01-关键修正与避坑清单](01-关键修正与避坑清单.md) 中 DSL/UGC/Agent 相关的全部修正（§21-27、§H/L/M/X 等）。

---

## 一、为什么需要 DSL

XKX 现状统计（实测）：
- 8412 个 LPC 文件中，**2482 个是 replace_program 纯声明式房间**（38.7%，可直接转声明式数据）
- 1113 个房间带自定义 add_action（17.3%，需事件规则或脚本）
- 424-434 个 inquiry 对话（**含 101 个同时耦合 inquiry+accept_object+set_temp 的交易 NPC**）
- 472 个技能文件，其中 163 个含 `mapping *action` 招式表、165 个用 query_action、131 个用 NewRandom、128 个用 auto_perform
- 72 个 condition 状态机守护进程
- 1626 个文件用 message_vision

结论：约 30% 是纯数据可直接转声明式，70% 含事件/对话/定时/战斗逻辑需要规则 DSL 或脚本逃生舱。**纯声明式无法表达所有逻辑，纯脚本对 30% 纯数据房间是浪费**--故采用分层混合 DSL。

---

## 二、四层 DSL 架构

```
┌─────────────────────────────────────────────────────┐
│ 层3 WASM / 受限Python 脚本逃生舱（平台级扩展/复杂逻辑）│  <15% KPI
├─────────────────────────────────────────────────────┤
│ 层2 Ink 对话树 + 交易原子节点（对话/交易流程）        │
├─────────────────────────────────────────────────────┤
│ 层1 事件规则 condition->action（触发器/副作用）       │
├─────────────────────────────────────────────────────┤
│ 层0 YAML 声明式场景数据（房间/NPC/技能/条件数据）     │  覆盖 60%+
└─────────────────────────────────────────────────────┘
         │ 全部编译为
         ▼
   JSON IR（唯一真相源）── 运行时只消费 IR，与创作语法解耦
```

### 层0：YAML 声明式数据
直接吸收 LPC 的 set() 调用。覆盖面最广、收益最大。

```yaml
# d/city/dongjiao1.scene.yaml
id: city/dongjiao1
short: 扬州东郊
long: |
  这是扬州城东门外的一片郊野。官道向东西延伸，
  北面是一片茂密的竹林。
exits:
  east: city/beidajie1     # 稳定 scene_id 引用，解耦路径=ID
  west: city/dongjiao2
  north: forest/bamboo_1
outdoors: city              # 天气/环境语义
cost: 2                     # 移动精力消耗
objects:                    # 声明式重生清单 = desired state
  clone/npc/bandit: 2
  clone/obj/herb: 1
item_desc:
  竹林: 一片青翠的竹林，随风沙沙作响。
events: []                  # 层1 事件规则引用
```

**schema 固化前必须穷举所有环境/语义字段**（objects spawn、resource、cost、outdoors、no_clean_up、resource/* 等）为显式字段，否则会把语义塞进 string bag 重演旧系统 `set("任意键")` 反模式。

### 层1：事件规则 condition->action
覆盖 init/add_action/valid_leave/accept_object/chat_msg 等事件钩子。

```yaml
# 规则语法：when/do 表达式
events:
  - on: command
    verb: 敲门
    do:
      - say: "$N 轻轻敲了敲门。"
      - set_temp: door_knocked
  - on: leave_room
    direction: north
    when: actor.has_temp("door_knocked") == false
    do:
      - deny_leave: "门还紧闭着，先敲门吧。"
  - on: give_item
    when: item.id == "letter" && actor.has_flag("quest_accepted")
    do:
      - quest_progress: deliver_letter
      - give_item: gold, 100
```

条件谓词（actor.has_temp/scene.has_flag/count_gt）与动作动词（say/tell/set_temp/deny_leave/allow_leave/spawn/give_item/schedule）从主题包注册表查询。复杂分支用嵌套 when/else。

**须扩充的原语**（否则逃生舱滥用）：`apply_buff_to_actors`（对多 actor 同时施加 buff）、`weighted_random`（加权随机选择）、`monitor_cooperation`（监控两 actor 是否仍共同战斗）、`spawn_coordinated_effect`。

### 层2：对话树 + 交易原子节点
采用 Ink 的 knot/stitch/divert/weave 语义模型，解决 inquiry 的 set_temp marks 临时旗标退化状态机。

```yaml
# 对话树示例
dialogue: qiu_medicine
knot: start
  - stitch: greet
    text: "丘处机道长看着你，问道：施主有何贵干？"
    options:
      - 买药: ask_buy
      - 询问武林事: ask_wulin
      - 告辞: leave
  - stitch: ask_buy
    text: "道长说：本门丹药，金创药500两，还魂丹5000两。"
    # 交易原子节点（修正 §21：inquiry 本质是交易状态机）
    transaction:
      preconditions:
        - actor.has_temp("marks/丸") == true   # 前置旗标
        - actor.gold >= 5000
        - npc.wan_count > 0
      atomic_actions:   # 单一原子单元，全部成功或全部回滚
        - take_money: 5000
        - decrement_stock: wan_count, 1
        - give_item: clone/obj/huanhun_dan
        - clear_temp: marks/丸
      on_success:
        text: "道长递过一颗还魂丹。"
      on_failure:
        text: "道长摇头：施主银两不足，或老道已无存货。"
    divert: start
```

**关键修正**：inquiry 不全转 Ink。简单字符串响应转层0，带交易流程的转"对话+交易原子节点"混合模型。先做 inquiry 子分类统计（纯字符串响应 vs 函数回调带交易）。

### 层3：脚本逃生舱
处理无法用声明式表达的复杂逻辑（两仪剑法双人和合、perform 持续效果状态机、NewRandom 加权随机）。

**关键修正**：
- **UGC 作者用受限 Python 子集**（RestrictedPython 或 Pyodide 沙箱执行），而非裸 WASM。UGC 作者是非程序员中文 MUD 爱好者。
- **WASM 仅保留给平台级已审计扩展**（可信编辑者）。
- **RestrictedPython 非安全边界**，需叠加运行时资源配额(fuel)+能力令牌校验作为纵深防御。
- 设**逃生舱使用率 KPI <15%**，超标触发层1-2 表达力迭代。
- WASM 定位为**无状态计算单元**（pure function），多 actor 协调态外部化为 Effect 实体。或对强状态 perform 扩展层1规则 DSL 的 Effect 原语。

---

## 三、IR 校验与安全模型

所有层编译为 JSON IR，经四道校验后方可注册运行：

1. **SchemaValidator**：jsonschema 结构校验
2. **CapabilityAuditor**：审核脚本引用的能力是否在 CPK manifest 声明范围内
3. **ResourceBudgetChecker**：fuel/wall_time/memory/call_out_quota 是否超限
4. **DependencyResolver**：networkx 依赖图拓扑排序与环检测

### 能力令牌安全模型
显式能力清单：
- `read_world` / `say` / `move_self` / `spawn_in_scene` / `schedule`（常规）
- `move_player` / `destroy` / `persist` / `log_file` / `privileged_force`（危险，需提升权限+审计）

对齐 LPC set_temp 旗标 + log_file 审计但显式化。**安全模型分两个独立域**（修正 §19）：
- (a) 运维侧 wizard ACL（admin/arch/wiz/player 命令权限）--先修 securityd bug 恢复可用
- (b) UGC 沙箱能力令牌（read_world/say/move_self 等）--仅作用于 UGC 脚本

### 资源配额（不可妥协硬约束）
对齐 config.xkx 的 eval_cost 语义固化为 per-CPK 配额：
- 每脚本每心跳指令上限（fuel）
- 墙钟超时
- 内存上限
- 递归深度
- call_out 配额（CPK 可挂起的未完成延迟任务总数）
- **分布式燃料聚合器**（修正 §M）：按 CPK 维度聚合跨调用 fuel，设滑动窗口配额，防小调用累计攻击

---

## 四、UGC 内容包（CPK）

```
内容包(CPK) = manifest + 资产集合
manifest:
  cpk_id: wuxia_shaolin_v3
  schema_version: 1
  theme: wuxia
  version: 3.1.0
  license: CC-BY-SA-4.0
  provenance:              # 溯源链（门3开启前才强制，修正 §24）
    content_hash: blake3:...
    parents: [wuxia_shaolin_v2]
    author: {type: agent, id: worldbuilder-7, model: claude}
    prompt_hash: sha256:...
  dependencies:
    - wuxia_core: ^2.0
    - common_dialogue: ^1.0
  capabilities_required: [read_world, say, spawn_in_scene]
  resource_quota:
    fuel_per_tick: 50000
    wall_time_ms: 50
    memory_mb: 64
    call_out_quota: 100
  entry_points:
    main_scene: shaolin/shanmen
```

### 内容生命周期
创作 -> 测试 -> 审核 -> 发布 -> 版本 -> 下架

- **内容寻址**：blake3 哈希，不可变快照，天然去重，版本回滚
- **依赖图**：networkx 拓扑排序，检测循环与缺失引用
- **命名空间隔离**：每 CPK 独立命名空间，跨包引用经依赖声明
- **资产（脚本/数据/素材）管理**：MinIO/S3 对象存储
- **多人协作与冲突**：provenance 链记录来源
- **版本控制**：内容寻址版本库，每次发布不可变快照
- **运行时沙箱与配额**：per-CPK 资源配额硬约束
- **市场分发与计费**：后期阶段，provenance 内建支持版权溯源

---

## 五、多题材机制（ThemeRegistry）

泛化现有 19 门派（kungfu/class/*）模式为题材包：

| 题材 | schema family | 特色谓词/动词 |
|---|---|---|
| wuxia（武侠） | 经脉/内力/招式 | 经脉运行、内力运转、招式连击 |
| nautical（大航海时代） | 航向/风向/货舱 | 起航、贸易、海战 |
| academy（书院） | 课业/师承/科举 | 读书、考试、论道 |
| modern（现代剧情） | 现代属性/职业 | 现代技能、社交、职业 |

**机制**：DSL 核心主题无关，每主题注册自己的条件谓词/动作动词/组件 schema family/默认资产。Python entry_points 插件机制运行时发现并加载。新增题材 = 注册新 schema family + 谓词包，不改核心。schema family 演进走 deprecation 周期避免漂移。

---

## 六、Agent 协作创作架构

### 核心理念
以 DSL 为唯一契约层，将 LLM 非确定性收敛到可验证终态。schema 强约束使多 Agent 交接零歧义。

### 协作模式
- **编排者-工作者分工**：Orchestrator 把"创意意图"拆解为 DAG 工作流分派给五角色 Worker
- **生成-评审-修订循环**：每条产出经验证+评审收敛到可验证终态
- **红蓝对抗验证**（后期质量放大器）：MVP 暂缓，待主干稳定后叠加

### 五角色 Worker
| 角色 | 职责 | 产出 |
|---|---|---|
| Worldbuilder（世界观设计师） | 世界圣经、场景拓扑 | 层0 场景 + 区域图 |
| Narrator（编剧） | 对话树、剧情事件 | 层2 对话 + 层1 剧情 |
| Behaviorist（NPC 行为作者） | condition 状态机、chat_msg | 层1 事件规则 + condition |
| Balancer（平衡测试） | 武功 action 数值、战斗模拟调参 | 层0 技能 + 数值表 |
| Continuity（连贯性审查） | 交叉验证世界圣经一致性 | 验证报告 |

### 人机协作三道审批门
1. **门1 创意意图**（创作启动前人类确认方向）--早期开启
2. **门2 世界圣经**（规模扩大后引入确认世界观一致性）--后期开启
3. **门3 发布前**（对外发布前最终审批）--早期开启

**修正**：早期只设门1+门3 避免门过多拖慢迭代。provenance 强制点后移到门3开启前。

### MCP 验证基底（共享给所有 Agent）
优先实现两高频验证 server（修正 §25/§26）：
1. **world-graph**（出口可达性）：纯 networkx 图分析，覆盖孤立房/死路/不可达区。**独立先行，无 ECS 依赖**。
2. **combat-sim**（伤害/胜率）：**先用独立纯 Python 数值模型**（从 LPC `*action` 招式表与 attack.c 伤害公式 seed 出来），不耦合运行时子系统；ECS 落地后再替换模拟器内核。

叠加**不变量回归集**：从 8400 LPC 解析入库形成基线断言（如"所有门派技能 force>0"、"主城互通"），任何变更须过全量回归。输出结构化指标（覆盖率/胜率分布/数值溢出）驱动精炼闭环。

### 闭环
```
人类创意意图(门1)
    │
    ▼
Orchestrator 拆解 DAG ──> 五角色 Worker 生成 DSL
    │                         │
    │                         ▼
    │                    MCP 验证(world-graph/combat-sim)
    │                         │
    │                    评审-修订循环
    │                         │
    │                    不变量回归集
    │                         │
    ▼ <─── 不通过则修订 ──────┘
资产入库(CPK + provenance)
    │
    ▼
人工审批(门3 发布前)
    │
    ▼
发布到题材世界
```

### 技术选型（MVP 最小集，修正 §T4）
| 组件 | 选型 | 说明 |
|---|---|---|
| DSL 解析 | Lark（EBNF）+ PyYAML + pydantic v2 | 外部 DSL |
| 对话树 | Ink 语义子集（自研解析器或 inkpy） | 避免外部二进制依赖 |
| 沙箱 | RestrictedPython（UGC）/ wasmtime-py（平台级） | 燃料计量 |
| Agent 编排 | **LangGraph（单进程起步）** | 状态机+checkpoint |
| LLM | Claude API 主 + 可插拔 GLM | 符合部署环境 |
| MCP 验证 | Model Context Protocol + networkx | 图可达性 |
| 资产存储 | blake3 + PostgreSQL + MinIO/S3 | 内容寻址 |
| 任务队列 | **MVP 不用 Celery**，单进程 asyncio | 验证收敛后再引入 |
| 评审工作台 | FastAPI + WebSocket + 可视化预览 | 场景图/对话图 |

**分布式协调**（修正 §26）：MVP 单进程 asyncio 编排。若需多实例，用 Postgres advisory lock 或 Redis SETNX 给 workflow 加租约串行化认领，或务实接受"单编排器 + 故障转移"。

---

## 七、存量迁移管线

把 8400 LPC 文件用 Agent 解析为 DSL 入仓形成基线回归集。

### 迁移优先级
1. **层0 纯数据房间**（2482 个 replace_program）：先建立基线回归集验证 schema 完备性。**但注意 1113 个带 add_action 的房间单独列为层1批次**（修正 §B4）。
2. **securityd 能力模型重建**（修正 §19）：作为 UGC 协作前置硬约束先行修复。
3. **inquiry 对话**（434 个）：子分类（纯字符串 vs 带交易）分别迁移。
4. **技能/复杂任务逻辑**（层3）：渐进迁移，保留 LPC 适配器桥接期。

### 迁移工具（修正 §M4）
**不押注 tree-sitter-lpc**（非成熟维护）。采用混合策略：
- 正则抽取结构化字段（exits/objects/inquiry/marks）
- 人工标注集覆盖动态分派长尾（this_object() 274 文件、previous_object() 51 文件、simul_efun 隐式覆写）
- 先用单区域（d/city 约 90 房）做端到端迁移试点，度量语义偏差率

### 表达力校准实验（修正 §22，不可跳过）
**启动 8400 文件批量迁移前**，取 30 个代表性文件（含 hebi.c 双人和合、auto_perform AI、inquiry 交易、condition 状态机）人工转译为 DSL，统计落入各层的分布与无法表达的比例。**若层3占比超 20%**，说明层1-2 表达力不足，需先扩充规则 DSL 原语（apply_buff_to_actors/weighted_random/monitor_cooperation）再推进迁移。

---

## 八、落地顺序与硬约束

```
1. 修 securityd.c（拼写+格式）恢复运维可用，分离 wizard ACL 与 UGC 沙箱
2. 层0 schema 固化（穷举环境/语义字段）
3. 2482 纯数据房间转层0（建立基线回归集）
4. 表达力校准实验（30 文件）
5. 层1-2 规则 DSL + 对话树（含交易原子节点）
6. WASM/RestrictedPython 沙箱 + per-CPK 配额（不可妥协硬约束）
7. CPK 格式固化（provenance 后移到门3前）
8. 单进程 LangGraph 编排 + world-graph MCP 验证
9. combat-sim（独立纯 Python 数值模型起步）
10. 多题材 ThemeRegistry
11. 红蓝对抗验证（后期质量放大器）
```

### 不可妥协的硬约束
1. **沙箱配额先行**：开放 UGC 脚本前 per-CPK 资源配额必须就位，否则等于开放拒绝服务。
2. **securityd 先修**：UGC 协作开放前必须先重建能力权限模型。
3. **表达力校准**：8400 文件批量迁移前必须先做 30 文件验证，层3占比超 20% 则先扩充层1-2。
4. **provenance 后移**：开发期用简单版本号，门3开启前才强制回填。
5. **combat-sim 独立**：不依赖未存在的 ECS 引擎，先用纯 Python 数值模型。
6. **LangGraph 单进程**：MVP 不做 active-active 多副本。

---

## 九、示例：Agent 协作创作一个新门派

以"创作一个新门派·天山派"为例展示完整闭环：

1. **门1 创意意图**：人类输入"创作天山派，以冰寒内力见长，驻扎天山雪峰"
2. **Orchestrator 拆解**：
   - Worldbuilder：设计天山派区域图（山门->练功房->雪峰）+ 世界圣经
   - Narrator：掌门对话树（拜师/切磋/下山历练）+ 交易原子节点
   - Behaviorist：冰寒内力 condition 状态机 + NPC chat_msg
   - Balancer：天山剑法 action 招式表 + 数值
   - Continuity：交叉验证与既有门派一致性
3. **Worker 生成 DSL**（各层 YAML）
4. **MCP 验证**：
   - world-graph：天山派区域可达性、与主城连接
   - combat-sim：天山剑法伤害/胜率分布、冰寒内力数值溢出检查
5. **不变量回归**：天山剑法 force>0、所有招式 damage_type 合法
6. **评审-修订循环**：Continuity 发现"冰寒内力与雪山派冲突"-> 修订
7. **资产入库**：CPK `wuxia_tianshan_v1` + provenance（agent_id=worldbuilder-7）
8. **门3 发布前审批**：人类预览场景图/对话图，确认发布
9. **发布到 wuxia 题材世界**：玩家可拜师天山派

---

*本方案的核心创新：以 DSL 为契约把 LLM 非确定性收敛到可验证终态，Agent 产出走与人类相同的审核与版本流程，多题材共享运行时但各自演进。*
