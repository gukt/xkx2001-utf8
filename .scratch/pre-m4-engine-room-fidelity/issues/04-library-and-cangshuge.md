---
Status: ready-for-agent
---

# 04 — 藏书子系统 + 官方藏书阁（硬门闩）

**What to build:** 完整藏书主路径可玩：书架（经 `details`）展示 TOC（可分页）→ 书名缩写解析 → `read` 选书 → 按章付费阅读（余额不足失败且不扣费）→ 长文分页。书档为题材包内文本资产。官方扬州藏书阁挂上该路径，并声明房间旗标与禁练——**缺本票不算关 effort**。

对应 spec：US17–US23；Testing S1/S2/S3。付费单位见 [to-tickets-notes.md](../to-tickets-notes.md) 决策 1。

**Blocked by:** 01（书架经 `details`）、03（旗标与禁练）。

- [ ] 题材包声明式书档（schema 在本票钉死并写进 Comments）：足够章节支撑付费读章与分页可测；不强制移植全部 LPC `jybooks`。
- [ ] 玩家主路径：`look` 书架 → TOC（可分页）；缩写 → 中文书名/书档 id；选书；按章付费读出正文；余额不足不扣费。
- [ ] 付费走现有 `Currency`（银两）整数；章节费用为包内声明的非负整数；不引入双币种。
- [ ] 官方 `m2_mvp_scene` 新增扬州藏书阁（或等价键），挂 `details` 书架、书档引用、`no_fight` 等旗标与禁练；可从既有扬州图到达。
- [ ] 命令动词与 YAML 字段名在实现时选定后写入本票 Comments，供契约票 `07` 回写。
- [ ] 测试（S1）：TOC/选书/付费成功/余额不足不扣费/分页。测试（S3）：加载扩展场景后走通藏书阁主路径。
- [ ] `just test` 全绿。

## Comments
