# ADR-0001：Python 工具链与项目骨架

- 状态：已采纳
- 日期：2026-07-10
- 阶段：-1

## 背景

进入阶段 -1 垂直切片平台验证，需确定 `engine/` 的 Python 工具链与包结构。架构基线（[00-04](../xkx-arch/)）要求纯 Python + asyncio + 内存+JSON，[04 §三](../xkx-arch/04-迁移路径与避坑清单.md) 明确要求 hypothesis 属性测试（resolve_attack 纯函数、规则命中行为）。六条收缩约束要求收敛优先，不为不存在的规模建设基础设施。

## 决策

- **Python >=3.12**：match 语句、asyncio 性能、类型提示成熟。
- **包名 `xkx`**：与仓库 xkx2001 一致，短。
- **src layout**（`src/xkx/`）：避免导入歧义，强制通过安装访问包。
- **测试 pytest + hypothesis**：架构明确要求属性测试；resolve_attack 纯函数（输入组件快照+seed -> CombatRoundResult）、533 valid_leave 命中行为基线测试都用得上。
- **lint/format ruff**：快、现代、单工具覆盖 lint+format。
- **类型**：暂不全局强制 mypy strict；安全相关模块（CapabilityToken/PermissionService）落地时再开严格类型。
- **依赖**：运行时 pydantic v2（组件/IR schema 校验）+ PyYAML（层0 YAML 加载）；dev 依赖 pytest/hypothesis/ruff。

## 不做（收敛）

- 不引入 mypy strict 全局（阻碍垂直切片速度，后置）。
- 不引入 uvloop（[04 §六](../xkx-arch/04-迁移路径与避坑清单.md)：stdlib asyncio 优先，1000 连接 I/O 非瓶颈）。
- 不引入 ORM/PG 驱动（内存+JSON 阶段，外部玩家测试前才迁 PG）。
- 不预先建 combat/dsl/ecs 子目录（第一个切片规划后按需建，避免空抽象层）。

## 关联

- [04 §一](../xkx-arch/04-迁移路径与避坑清单.md)（收敛优先）、§六（不做清单：uvloop/PG）。
- [05 §五](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent 9（存储收缩丢失语义）、dissent 10（平台特性并行范围过载 -> 先验证核心循环）。
