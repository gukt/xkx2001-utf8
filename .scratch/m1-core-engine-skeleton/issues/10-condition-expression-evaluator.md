# 10 - 通用条件表达式求值器最小版

**What to build:** 一个通用条件表达式求值器纯函数,支持 Nature 状态查询 + 布尔组合,作为门/物品/NPC 动态规则的共同条件子语言地基（替代 LPC 散落字符串 `if` 比较反例）。M1 用 stub context（B 块 Nature 落地时接真实查询）。

- **`evaluate(condition, context) -> bool` 纯函数**:独立模块,不依赖其他引擎模块（除 context 协议）。
- **支持字面量谓词** `is_night` / `is_day` / `is_raining`、相等比较 `phase == night`、布尔组合 `and` / `or` / `not`。
- **context 定义 Nature 查询协议**（M1 用 stub 可注入,B 块接真实 Nature）。
- **表达式形状按"未来可换受限 AST"设计**:M1 用结构化 Python 字面量（嵌套 tuple/dict 或小型表达式节点）占位,**不引入裸 Python lambda 作为字段值**（避坑清单 §F）;M3 落地受限 AST 解析器时换实现不换字段形状。
- **多规则按 any/all 聚合不互斥**（避坑清单 §12）。

**Blocked by:** None - 可立即开始（独立纯函数,不依赖 07-09;B 块 Nature 落地时接真实查询）。

**Status:** ready-for-agent

- [ ] `evaluate(condition, context) -> bool` 纯函数存在,独立模块
- [ ] 支持 `is_night` / `is_day` / `is_raining` 字面量谓词
- [ ] 支持 `phase == X` 相等比较
- [ ] 支持 `and` / `or` / `not` 布尔组合
- [ ] context 定义 Nature 查询协议,M1 用 stub 可注入
- [ ] 表达式形状不引入裸 Python lambda（结构化字面量占位,按受限 AST 可解析设计）
- [ ] 多规则按 any/all 聚合
- [ ] 纯函数直接测:`evaluate` 各种条件表达式返回正确 bool
