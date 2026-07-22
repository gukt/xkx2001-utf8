# Pre-M4 引擎房间保真：拆票分析笔记（/to-tickets）

> 本文件记录对 [spec.md](spec.md) 的拆分逻辑、依据，以及为消除实现歧义所做的决策。7 张票已发布在 [issues/](issues/)（`01`–`07`，编号即依赖顺序）。执行手册见 [implement-plan.md](implement-plan.md)。
>
> **核心校准**：硬门闩三项（`details` + 语义色 ADR-0011 + 完整藏书）缺一不可关 effort；`day_shop` 与剧情门为本波必做但**非硬门闩**（可止损）。不重开 ADR-0010 放置；不自动开 M4；不做 LPC 行为等价（ADR-0001）。

## 勘察方法

- **spec**：[spec.md](spec.md) 全文（范围边界、US1–35、Implementation / Testing / OOS）。
- **上游**：[PROGRESS.md](../../PROGRESS.md)、[CONTEXT.md](../../CONTEXT.md)、[ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md)、[ADR-0011](../../docs/adr/0011-semantic-color-tokens.md)、grill 底稿 [session-notes-2026-07-21.md](session-notes-2026-07-21.md)。
- **兄弟批 precedent**：[pre-m4-channels-spawn-quest](../pre-m4-channels-spawn-quest/)（7 票 / 3 Wave / implement-plan 形状）与 [m2 implement-plan](../m2-mvp-scene-playable/implement-plan.md)（Wave 提示词 + PROGRESS 对接）。
- **代码接缝（拆票时点）**：`look` 仅匹配物品、无 `details`；`entry_guard` + `is_night` 已有、无 `day_shop`；标准门钥匙不消耗、无剧情门三件套；`practice` 存在但不读房间旗标；`Currency` 为银两；语义色零实现；`m2_mvp_scene` 有打铁铺、无藏书阁/翰林；GAP 尚无本批专行。

## 拆分原则

1. **按可玩闭环切垂直片，不按「先全 schema 再全命令」横切。** 每张能力票尽量自带局部 S3（官方场景挂一点），收口票只做契约/GAP/清单核对与最小补齐。
2. **硬门闩与非门闩分开。** `04` 是硬门闩收口；`05`/`06` 可止损且不堵 `04` 的依赖链（`07` 要求二者落地**或**明文止损）。
3. **Prefactor 克制。** 不另开「注册表重整」票——房间能力追加走既有 `ROOM_CAPABILITIES` / 已知字段加法即可（兄弟批已证明此路径）。
4. **依赖按真实阻塞，不照抄主题字母。** `04` 必须等 `01`（书架经 `details`）与 `03`（旗标/禁练）；`02` 与风景交织但技术上可并行；`05`/`06` 无票级阻塞，并入 Wave 2 仅为控单 session 体量。

## 关键设计决策（实现时直接采纳）

1. **付费读章货币单位**：沿用现有 `Currency.amount`（银两）整数扣费；章节费用为题材包声明的非负整数。玩家可见文案可写「文/铜板」，**不**在本批引入双币种或铜板子系统。理由：引擎已有扣费 seam（`buy`/quest reward）；双币属商业化支撑点（mvp-scope 06），OOS。
2. **`day_shop` vs 手写 `entry_guard`**：同房二者并存 → **加载失败**（明确错误）。理由：spec 推荐「勿叠加歧义」；静默优先级会让契约撒谎。
3. **禁练挂载点**：不新增与 CONTEXT 清单冲突的第四个「inert 旗标名」作唯一真源；优先以「本房启用藏书阅读」的同房规则（或等价一等声明）拦 `practice`。票 `03` 交付通用拦截能力，票 `04` 在藏书阁上挂载。若实现发现必须独立布尔才能让「同构非藏书房」禁练，允许加一等字段并在 Comments + CONTEXT 短回写，不另开决策票。
4. **`look` 实体范围**：同房实体 = 地面物品 **+ NPC**，再查 `details`。理由：spec「实体优先于风景」；当前 `look` 只匹配物品会让「同名 NPC 盖不过牌子」的验收含糊。
5. **语义色单票**：校验与 CLI 渲染同属 ADR-0011 一条垂直切片，不拆成两张（避免「能校验但不能玩色 / 能染但不能拒坏 markup」的半交付）。
6. **官方验收扩展 `m2_mvp_scene`，不建橱窗包。** 藏书阁 / 打铁铺日间店 / 翰林 / 带色户外分别挂在 `04`/`05`/`06`/`01`–`02`（缺口由 `07` 补）。
7. **Wave 分组略宽于严格依赖。** `05`/`06` 可 Wave 1 提前开工；默认仍进 Wave 2，便于 `/code-review` fixed point 与硬门闩 `04` 同波审视。

## 与 spec 主题的映射

| spec 主题 | 票据 | 备注 |
|---|---|---|
| 房间风景 | `01` | 硬门闩之一 |
| 语义色 | `02` | 硬门闩之一；ADR-0011 |
| 房间旗标 + 禁练能力 | `03` | 硬门闩的一部分；藏书阁挂载在 `04` |
| 藏书 + 官方藏书阁 | `04` | 硬门闩收口 |
| 日间店铺 | `05` | 本波必做、非硬门闩 |
| 剧情门 + 翰林 | `06` | 本波必做、非硬门闩 |
| 契约 / GAP / 不自动开 M4 | `07` | 收口 |

## 未纳入（与 spec OOS 对齐）

液体灌装/饮用、防拐带、重开放置（ADR-0010）、橱窗包、通用 `add_exit`/`remove_exit` 契约 API、为 inert 旗标补 steal/睡眠、语义色嵌套/背景/ANSI 进 YAML、完整 `jybooks` 移植、升格停机门闩、自动开 M4。
