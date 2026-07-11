# ADR-0016：层1 谓词集扩充（第二批，8 类缺口）

- 状态：已采纳（决策，实现后置阶段 1）
- 日期：2026-07-11
- 阶段：0 任务 9（30 文件表达力校准发现）
- 关联 dissent：[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 3（层1 原语蠕变护栏）；[04](../xkx-arch/04-迁移路径与避坑清单.md) kill criteria 4；[ADR-0005](ADR-0005-layer1-predicate-expansion.md) 第一批谓词护栏；[ADR-0015](ADR-0015-layer-calibration-methodology.md) 校准方法论与结果

## 背景

[ADR-0015](ADR-0015-layer-calibration-methodology.md) 30 文件表达力校准执行后，识别出 ~11 个"逃生舱层3"项（本可用层1 表达但谓词集不足）。这些项分布在 8 类谓词缺口中，均有 LPC 规格源实证。

本 ADR 是 [ADR-0005](ADR-0005-layer1-predicate-expansion.md) 第一批谓词（dir + all/any/not + family_eq/has_item）的后续扩充，沿用其 dissent 3 护栏模式：每个新谓词需 LPC 实证 + 护栏清单。

校准结论（[ADR-0015 结果](ADR-0015-layer-calibration-methodology.md#结果2026-07-11-校准执行)）：修正 KPI = 11/171 ≈ 6.4% < 15% ✓，任务 9 通过。本 ADR 扩充谓词后将逃生舱层3 进一步降级，预期 KPI 降至 ~3%。

## 当前层1 谓词基线（ADR-0005 采纳集）

- 叶子（7）：`always` / `attr_lt` / `age_lt` / `present_npc` / `has_flag` / `family_eq` / `has_item`
- 组合（3）：`all` / `any` / `not`
- 规则维度：`dir` + `priority` + `deny-wins`
- 事件钩子：`init` / `valid_leave` / `accept_object` / `chat_msg`

## 决策（8 类缺口扩充）

### 1. `attr_eq` 谓词

actor 属性 == value（LPC `me->query("gender")=="女性"` 等）。

- **实证**：d/shaolin/shanmen.c valid_leave 的 gender=="女性" 分支
- **语义**：`attr_eq(attr, value)`，与 `attr_lt` 对称
- **护栏**：仅 == 比较；范围查询仍走 `attr_lt`，不引入 `attr_gt`/`attr_le`/`attr_ge`（按需再走 ADR）

### 2. `is_wizard` 谓词

actor 是 wizard（LPC `wizardp(me)`）。

- **实证**：d/forest/foot.c valid_leave `wizardp(me)` 放行；d/bwdh/kantai.c valid_leave up/out `wizardp(me)` 放行
- **语义**：`is_wizard()`，无参数叶子谓词
- **护栏**：wizard 身份是运维侧 ACL 概念（[03](../xkx-arch/03-DSL-UGC与Agent协作.md) §三安全模型 (a)），此处仅作只读判断（UGC 可读不可写 wizard 身份）；不引入 `is_admin`/`is_arch` 等细分（wizard 够用，细分走 ACL 层）

### 3. `has_item` 扩展（item_category + item_name）

`has_item` 当前只支持 item_id。扩展两种匹配：

- **item_category=weapon**：actor 持有某类物品（LPC 兵刃检查）
  - 实证：d/shaolin/shanmen.c valid_leave 检查是否持兵刃
- **item_name**：actor 持有指定名称物品（LPC `present("hong biao", me)`）
  - 实证：d/city/guangchang.c 红镖检查 `present("hong biao", me)`
- **语义**：`has_item(item_id="", item_category="", item_name="")`，三选一
- **护栏**：不引入 `has_item_count`（数量检查走层3）；item_category 仅支持主题包注册的类别（weapon/armor/key 等有限集），不开放任意字符串

### 4. `has_flag` 扩展（source=temp）

`has_flag` 当前查 `query("flag")`。扩展支持 `query_temp` 标记。

- **实证**：多文件 `query_temp("biao")` / `query_temp("zhu")` / `query_temp("exit_blocked")` / `query_temp("target_found")` / `query_temp("rided")` / `query("luohan_winner")`
- **语义**：`has_flag(flag, source="query")`，source 可选 `query`（默认）/`temp`
- **护栏**：source 仅两值（query/temp），不引入第三种存储层；flag 名由层3 平台代码维护，UGC 只读

### 5. `derived_state` 谓词（派生状态统一抽象）

LPC 大量方法调用（`is_busy()` / `is_fighting()` / `is_ghost()` / `living()` 等）需统一抽象为派生状态判断。

- **实证**：多文件的 `me->is_busy()` / `me->is_fighting()` / `me->is_ghost()` / `living(me)`
- **语义**：`derived_state(state)`，state 取主题包注册的有限集（busy/fighting/ghost/alive 等）
- **护栏**：state 是有限枚举（主题包注册），不开放任意字符串；不每个方法一个谓词（避免蠕变）；`is_wizard` 因高频且语义独立仍单独列（决策 2）

### 6. `status_eq` + `same_object` + `mud_age_lt`（kill.c deny 规则）

cmds/std/kill.c 有 7 条前置 deny 检查，暴露 3 类缺口：

- **`status_eq`**：actor 状态 == value（LPC `me->query_temp("immortal")` 等状态标记）
  - 实证：kill.c immortal 检查、投降保护检查
- **`same_object`**：两个对象是同一对象（LPC 对象引用比较）
  - 实证：kill.c "自身投降"检查（target == me）
- **`mud_age_lt`**：actor 游戏年龄 < value（LPC `me->query("mud_age")`）
  - 实证：kill.c PKer 内疚/年龄门禁
- **护栏**：这三个谓词仅用于命令前置 deny，不扩展为通用比较框架；`status_eq` 的 value 是有限枚举

### 7. `has_inquiry` + `attr_in`（ask.c 对话分支）

cmds/std/ask.c 的对话调度暴露 2 类缺口：

- **`has_inquiry`**：NPC 当前提问列表含指定 topic（LPC INQUIRY_D 查询）
  - 实证：ask.c inquiry/<topic> 查询分发
- **`attr_in`**：actor 属性在枚举集合中（LPC attitude in {"good","bad"} 等）
  - 实证：ask.c 按 attitude 分支响应
- **护栏**：`has_inquiry` 只查不写（inquiry 列表由层2 对话树维护）；`attr_in` 的集合是字面量列表，不引入正则/模式匹配

### 8. 命令事件钩子维度（层1 事件类型扩展）

层1 当前事件钩子（init/valid_leave/accept_object/chat_msg）未覆盖自定义命令（add_action 注册）。

- **实证**：d/zhongnan/gate.c `add_action("do_knock", "knock")`；d/city/guangchang.c `add_action("do_enter", "enter")`
- **决策**：层1 扩展 `command` 事件类型，支持声明式命令前置 deny（条件 + deny-wins）；命令主体（副作用）仍层3
- **护栏**：仅覆盖命令前置条件 deny（"层1 管条件，层3 管副作用"分工，见 [ADR-0015](ADR-0015-layer-calibration-methodology.md) 校准发现）；不把命令主体搬进层1

## dissent 3 护栏（原语蠕变控制）

本 ADR 新增 5 个叶子谓词（attr_eq/is_wizard/derived_state/has_inquiry/attr_in）+ 3 个扩展（has_item/has_flag/status_eq 系列）+ 1 个规则维度（same_object）+ 1 个事件类型（command），**均有 LPC 规格源实证**（校准 30 文件中具体调用点），非预判抽象。

**不引入**：

- 独立规则引擎 / RETE / OPA / Drools（[02](../xkx-arch/02-三个开放架构问题裁决.md) Q2 否决）
- `attr_gt`/`attr_le`/`attr_ge`（按需再走 ADR，避免一次引入全套比较）
- `has_item_count`（数量检查走层3）
- 每个派生状态方法一个谓词（用 `derived_state` 统一抽象）
- 通用比较框架（`same_object` 仅限命令 deny 上下文）
- 正则/模式匹配（`attr_in` 仅字面量列表）

**KPI 影响**：扩充后逃生舱层3 从 ~11 项降至 ~3-5 项（命令维度缺口 2 项 + 部分 accept_fight 前置 4 项可降级），修正 KPI 预期 ~3%。

## 产出位置（后置阶段 1 实现）

阶段 0 是规格提取期，层1 运行时实现后置阶段 1。本 ADR 决策影响：

- [layer1.py](../../engine/src/xkx/dsl/layer1.py)：Predicate 模型扩展（新叶子谓词字段 + has_item/has_flag 扩展字段 + same_object）
- [layer1.py](../../engine/src/xkx/dsl/layer1.py)：EventRule 扩展 `command` 事件类型
- [components.py](../../engine/src/xkx/runtime/components.py)：EvalContext 扩展（wizard 身份 + derived_state 查询 + inquiry 列表）
- spec/layer_c_command.py：命令 deny 规则规格补充（kill.c 7 条 + ask.c 分支）

实现时机：阶段 1 层1 运行时落地时，或在 M2 DSL+Agent 创作闭环需要时。

## 结果

- **决策已采纳**：8 类缺口扩充，均有 LPC 实证
- **实现后置**：阶段 1 层1 运行时落地时实现
- **KPI 影响**：预期修正 KPI 从 6.4% 降至 ~3%
- **校准闭环**：[ADR-0015](ADR-0015-layer-calibration-methodology.md) 任务 9 通过，本 ADR 是其后续原语扩充

## 不做（范围边界）

- 不立即实现（后置阶段 1）
- 不引入独立规则引擎（02 Q2 否决）
- 不每方法一谓词（derived_state 统一抽象）
- 不引入全套比较运算符（attr_gt/le/ge 按需再 ADR）
- 不修改 LPC 源（只读规格）
- 不把命令主体/副作用搬进层1（仅前置 deny）

## 关联

- [ADR-0005](ADR-0005-layer1-predicate-expansion.md) 第一批谓词（本 ADR 是其后续）
- [ADR-0015](ADR-0015-layer-calibration-methodology.md) 校准方法论与结果（本 ADR 是其发现的缺口）
- [04](../xkx-arch/04-迁移路径与避坑清单.md) kill criteria 4（本 ADR 扩充后 KPI 进一步降低）
- [03](../xkx-arch/03-DSL-UGC与Agent协作.md) §二四层 DSL + §三安全模型
