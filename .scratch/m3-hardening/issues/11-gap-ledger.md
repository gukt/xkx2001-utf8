# 11 — GAP 台账

**What to build:** 有一份持续维护的清单，列出"当前声明式场景 YAML 表达不了什么、遇到时推荐怎么降级/绕过"（持续 Effect、脚本化剧情分支、多人频道广播、装备槏位与真实 wield、坐骑驯服/被抢等），让 UGC 创作者在设计内容时能提前知道边界在哪，而不是写到一半撞墙才发现。这份清单明确不是一个"能力橱窗包"（不新建一个专门用来展示引擎全部能力的示例内容包），与 CONTEXT.md 已经写明的"GAP 台账 ≠ 能力橱窗包"区分保持一致，不产生范围蔓延。

对应 spec：[.scratch/m3-hardening/spec.md](../spec.md) B3-5（P1-7/G1）。

**Blocked by:** None — 可立即开始；建议在 06 号票（创作者契约 v0）落地后补一条反向链接到 `docs/creator-contract-v0.md`，但不作为硬阻塞。

**Status:** ready-for-agent

- [ ] 新增 `docs/gap-ledger.md`：条目式列出至少覆盖——持续 Effect（buff/debuff，链接 ADR-0007）、脚本化任务/剧情分支（无沙箱，链接 ADR-0005 OOS）、多人频道/双玩家广播（链接 ADR-0008）、装备槏位与真实 wield/unwield（链接 02 号票）、坐骑驯服/被抢、多文件/大世界树场景。每条给"现状"+"推荐降级方式"两栏。
- [ ] 明确不新建能力橱窗内容包（与 CONTEXT.md「GAP 台账」词条的 `_Avoid_` 一致）。
- [ ] 若 06 号票已落地，在 `docs/creator-contract-v0.md` 里补一条指向本文档的引用链接。
- [ ] 无自动化测试要求，验收标准是人工核对清单条目完整、引用链正确。

## Comments
