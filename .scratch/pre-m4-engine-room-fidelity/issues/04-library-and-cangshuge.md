---
Status: resolved
---

# 04 — 藏书子系统 + 官方藏书阁（硬门闩）

**What to build:** 完整藏书主路径可玩：书架（经 `details`）展示 TOC（可分页）→ 书名缩写解析 → `read` 选书 → 按章付费阅读（余额不足失败且不扣费）→ 长文分页。书档为题材包内文本资产。官方扬州藏书阁挂上该路径，并声明房间旗标与禁练——**缺本票不算关 effort**。

对应 spec：US17–US23；Testing S1/S2/S3。付费单位见 [to-tickets-notes.md](../to-tickets-notes.md) 决策 1。

**Blocked by:** 01（书架经 `details`）、03（旗标与禁练）。

- [x] 题材包声明式书档（schema 在本票钉死并写进 Comments）：足够章节支撑付费读章与分页可测；不强制移植全部 LPC `jybooks`。
- [x] 玩家主路径：`look` 书架 → TOC（可分页）；缩写 → 中文书名/书档 id；选书；按章付费读出正文；余额不足不扣费。
- [x] 付费走现有 `Currency`（银两）整数；章节费用为包内声明的非负整数；不引入双币种。
- [x] 官方 `m2_mvp_scene` 新增扬州藏书阁（或等价键），挂 `details` 书架、书档引用、`no_fight` 等旗标与禁练；可从既有扬州图到达。
- [x] 命令动词与 YAML 字段名在实现时选定后写入本票 Comments，供契约票 `07` 回写。
- [x] 测试（S1）：TOC/选书/付费成功/余额不足不扣费/分页。测试（S3）：加载扩展场景后走通藏书阁主路径。
- [x] `just test` 全绿。

## Comments

### Schema / 命令（供 07 回写）

- 顶层 `books.<id>`：`title`、`abbrevs`（列表）、`chapter_cost`（非负整数银两）、`chapters`（字符串列表）。
- 房间 `library: true`（仅禁练）或 `library: {shelf: 书架, books: [id…]}`（引用顶层书档）；组件 `LibraryRoom`。
- `look <shelf>`（默认键 `书架`）→ TOC（可 `more` 分页）；优先于同名 `details`。
- `read <缩写|书名|id>` 选书；`read <章号>` 扣 `Currency.amount` 后展示正文（可 `more`）；余额不足不扣费。
- 分页：`MoreBuffer` + 命令 `more`；页长 `MORE_PAGE_SIZE=8`。
- 官方锚点：`yangzhou_cangshuge`（武庙 `north`）；挂 `no_fight`/`no_steal`/`no_sleep_room` + `library`。
