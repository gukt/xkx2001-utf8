---
Status: ready-for-agent
---

# 07 — 收口：契约 / GAP / PROGRESS

**What to build:** 票 `01`–`06` 落地后做收口：创作者契约 v0 与 `--validate`/`--strict` 已知字段集**只做加法**覆盖本波新字段与语义色校验；GAP 台账将风景/语义色/藏书/日间店/剧情门相关条改判为已支持（措辞克制）；核对 `CONTEXT.md` 词条与最终实现一致；更新 `PROGRESS.md`；确认**不自动开 M4**。若户外语义色等 S3 锚点未在前票写全，本票补齐官方场景最小缺口（不新建橱窗包）。

对应 spec：US32–US35；Testing 全量回归。

**Blocked by:** 04、05、06（硬门闩与本波必做均已落地或已明文止损）；隐含 01–03 已完成。

- [ ] `docs/creator-contract-v0.md` + 加载器已知字段：加法覆盖 `details`、语义色约束、房间旗标、藏书相关字段、`day_shop`、剧情门声明；`--validate`/`--strict` 覆盖新字段与色校验。
- [ ] `docs/gap-ledger.md`：相关「表达不了」条改判已支持（或不越界的等价表述）；不宣称液体/防拐带/通用改出口 API 已做。
- [ ] `CONTEXT.md`：核对房间风景 / 语义色 / 房间旗标 / 藏书 / 日间店铺 / 剧情门 / Pre-M4 引擎房间保真词条与实现一致；小出入直接回写，大偏差先短 grill。
- [ ] 官方扬州 S3 清单核对：藏书阁主路径、打铁铺日间店、翰林三件套、至少一处带语义色与 `details` 的户外——缺则在本票最小补齐。
- [ ] `PROGRESS.md`：Done 增补本 effort 收口；Next Up 去掉本 effort，留下 M4 评估（**不自动开 M4**）；滑动窗口溢出移入 `.scratch/progress-archive.md`。
- [ ] 本 effort README / issues Status 收口为关闭态；不新开 ADR（0010/0011 结论不变）。
- [ ] `just test` 全绿。

## Comments
