# Polishing：拆票分析笔记（`/to-tickets`）

> 本文件记录对 [spec.md](spec.md) 的拆分逻辑、依据，以及为消除实现歧义所做的架构师拍板。13 张票已发布在 [issues/](issues/)（`01`–`13`）。

## 勘察方法

- **spec**：[spec.md](spec.md) 全文（Problem/User Stories/Implementation Decisions/Testing Decisions/Out of Scope/Further Notes）。
- **上游**：[PROGRESS.md](../../PROGRESS.md)、[CLAUDE.md](../../CLAUDE.md)、[CONTEXT.md](../../CONTEXT.md)、[docs/gap-ledger.md](../../docs/gap-ledger.md)、[docs/creator-contract-v0.md](../../docs/creator-contract-v0.md)。
- **兄弟批 precedent**：[pre-m4-room-hooks-xingxiu/to-tickets-notes.md](../pre-m4-room-hooks-xingxiu/to-tickets-notes.md)（票编号=依赖顺序、单票即垂直切片、收口票依赖全部前置票的拆票惯例，本批沿用）。
- **代码勘察**：`components.py`（`RoomFlags.no_sleep_room`/`RoomDetails`/`BlockExits`/`Terrain`）、`commands.py`（`_cmd_practice` 的 `LibraryRoom` 拦截模式、`buy`/`sell`/`ShopInventory` 交易模型、`_cmd_go` 出口/挡向分支）、`library.py`（房间旗标独立拦截先例）、`room_hooks.py`（`bandit_ambush` 钩子与 `RoomHookBinding.params`）、`engine/data/m2_mvp_scene.yaml`（`yangzhou_kedian`/`kedian_waiter` 已存在，B8 可直接落地不必新建场景）。

## 拆分原则

1. **票编号与 spec 候选 ID 表顺序一一对应，不重新发明分组。** spec 已给出「建议每 ID 一票，A1+A2 合并一票，C14 拆两票」的明确拆票建议，13 项恰好映射 13 票，直接采纳比另起炉灶的分法更贴合 spec 权威规格的组织方式。
2. **A3 blocked by A1+A2，C14 实现票 blocked by C14 ADR 票，其余 11 票均无阻塞、可并行认领。** 依赖边界严格来自 spec 正文的显式声明（A3「必须排在 A1+A2 实现完成之后」；C14「`/to-tickets` 必须把 C14 拆成先出 ADR 与后实现两张独立票，且实现票 Blocked by 该 ADR 票」），不额外引入未在 spec 里出现的依赖假设——B/C 组各项分别落在不同模块（`commands.py` 新命令动词 vs `room_hooks.py` 钩子实现 vs `scene_loader.py` 新段解析），互不改同一份契约字段，天然可并行。
3. **C14 拆两票且不预先指定实现模块。** ADR 票（`12`）只产出决策记录，不写代码；实现票（`13`）留空「具体数据模型」，全部交给 ADR 结论决定——避免在 ADR 尚未写出的情况下于 to-tickets 阶段预判实现形状，重复 spec「本 spec 不预先指定实现模块」的克制。

## 关键设计决策（本次 `/to-tickets` 架构师拍板，不留白进 `/implement`）

B8 客店三件套的三个开放子决策已由架构师会话拍板（用户逐项确认），写入票 `06`：

1. **`sleep_room` 极性**：沿用现有 `RoomFlags.no_sleep_room`（默认允许睡，显式关闭），不新增正向 `sleep_room` 字段——`no_sleep_room` 已声明但 inert，本票是其「转正」的天然落点；避免两个极性相反字段并存造成语义混淆。
2. **付费动词**：新增专门 `pay` 命令，不复用 `buy`/`give`——`ShopInventory` 的 `buy`/`sell` 是具体商品条目模型，不适合表达「向 NPC 付一笔固定房钱换取房间服务」这种抽象交易。
3. **睡房拦练功**：独立实现（`_cmd_practice` 新增判定分支），不复用 `LibraryRoom` 组件本体——语义上「睡房」与「藏书房」是两类不同房间标记，即使实现模式（房间存在即拦）一致也不应共用同一组件；`library.py`/`RoomFlags` 已有「同房挂某标记即拦某命令」先例，本票遵循该先例的**模式**而非**组件**。

其余票内的「开放子决策」（如 A4 details 旧写法双轨兼容、C11 rng 注入方式、C13 是否允许内容包轨 include）已在各票内直接钉死方案（见票 `03`/`09`/`11` 正文），不留白进 `/implement`——遵循 spec「必须写明选定方案」的约束，或按 spec 允许的「本 spec 先列出候选，落地时钉死」条目由 `/to-tickets` 阶段代为钉死以缩短 `/implement` 决策链路。

## 与 spec 候选 ID 的映射

| spec ID | 票据 | 备注 |
|---|---|---|
| A1+A2 出口导航别名 | `01` | 无阻塞 |
| A3 YAML 简写规范化 | `02` | blocked by `01` |
| A4 房间风景 details 升级 | `03` | 无阻塞 |
| A5 `block_exits` 拒走文案 | `04` | 无阻塞 |
| B6 步行 `cost` 精力 | `05` | 无阻塞 |
| B8 客店三件套 | `06` | 无阻塞；三个开放子决策已钉死 |
| B9 条件 DSL 文档化 | `07` | 无阻塞；仅文档 |
| C10 液体 / eat / drink | `08` | 无阻塞 |
| C11 随机 objects 表 | `09` | 无阻塞 |
| C12 刷怪条件扩展 | `10` | 无阻塞；复用 `room_hooks.py` |
| C13 多文件路径引用 templates | `11` | 无阻塞 |
| C14 局部天气继承（ADR） | `12` | 无阻塞；C14 前置门闩 |
| C14 局部天气继承（实现） | `13` | blocked by `12` |

## 未纳入（与 spec Out of Scope 对齐）

B7 `invalid_startroom`、C15 `valid_leave` 脚本化（均维持 GAP·后置）、M4 商业化数据模型评估、LPC 行为等价验证（任何形式）、UGC 可写 `hooks`/RestrictedPython 房间脚本、完整 Effect 持续生命周期系统、重开放置模型（ADR-0010）、C14 的具体实现细节（留给票 `12` 产出的 ADR 与票 `13`）、契约破坏性变更。
