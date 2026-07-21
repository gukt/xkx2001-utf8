# M3 引擎架构全面评审

> 日期：2026-07-21  
> 状态：**Phase 1 完成 · Phase 2 对抗完成 · Final 已发布**

## 本轮评审目的

用户停在 **M3** 做全面评审：对照 M0–M3 的规格 / ADR / 验收承诺，审视引擎实现、测试与架构是否诚实对齐，并在**不进入 M4（商业化）与创作者平台**的前提下，给出可决策的停机条件与加固清单。

原则提醒：

- **不做** LPC 行为等价验证（[ADR-0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md)）。
- 验收与测试只锁 **新引擎自身 spec / 契约**。
- 本目录为评审工件；**对抗与综合阶段仍不直接改引擎代码**（加固实现另开票）。

## 推荐阅读顺序

1. **[final/m3-engine-architecture-review-report.md](final/m3-engine-architecture-review-report.md)** — 一页结论与行动清单（架构师主入口）
2. **[adversarial/cross-review.md](adversarial/cross-review.md)** — 共识 / 分歧矩阵 / 伪共识检查 / 对抗后优先级
3. **`experts/*-raw.md`** — 四方独立调研原文（需要追溯论据时再读）

## 专家分工（Phase 1 已完成）

| 编号 | 角色 | 产出文件 | 焦点 |
|---|---|---|---|
| 01 | 游戏高级架构师 | [`experts/01-senior-architect-raw.md`](experts/01-senior-architect-raw.md) | 模块图、深/浅模块、不变量符合度、结构风险、与侠客行灵感对照 |
| 02 | UGC / DSL / 内容创作层 | [`experts/02-ugc-expert-raw.md`](experts/02-ugc-expert-raw.md) | 创作面契约、M3 符合度、静默透传、示例包、停机产品化 |
| 03 | 游戏主策划 | [`experts/03-lead-designer-raw.md`](experts/03-lead-designer-raw.md) | MVP 必做 18、场景走查、联动玩法、可重复游玩断链 |
| 04 | 规格符合度与测试架构（兼 QA） | [`experts/04-spec-qa-raw.md`](experts/04-spec-qa-raw.md) | 里程碑矩阵、测试地图、联动达标、规格漂移、契约测缺口 |

Phase 1：**独立调研，专家间不协商。**  
Phase 2：主席主持交叉对抗并写入 `adversarial/` + `final/`。

## 完整目录树

```text
.scratch/m3-engine-architecture-review/
├── README.md                          ← 本文件（状态与索引）
├── experts/
│   ├── 01-senior-architect-raw.md     ← Phase 1 架构师
│   ├── 02-ugc-expert-raw.md           ← Phase 1 UGC
│   ├── 03-lead-designer-raw.md        ← Phase 1 主策划
│   └── 04-spec-qa-raw.md              ← Phase 1 规格/QA
├── adversarial/
│   └── cross-review.md                ← Phase 2 交叉对抗裁决
└── final/
    └── m3-engine-architecture-review-report.md  ← 最终综合报告
```

## 状态说明

| 阶段 | 含义 | 当前 |
|---|---|---|
| Phase 1 | 各专家独立写 `experts/*-raw.md` | **完成**（01–04 齐） |
| Phase 2 | 交叉对抗 → `adversarial/cross-review.md` | **完成** |
| Final | 综合报告 → `final/m3-engine-architecture-review-report.md` | **已发布** |
| 收口（项目侧） | 更新 `PROGRESS.md`、开加固票或修订 ADR、决定是否暂缓 M4 | **拍板已落**（2026-07-21：S0+P0；P1 续 grill→W1/B3/Q3；ADR-0007～0009；暂缓 M4；实现待 hardening `/to-spec`） |

## 一页结论摘要（Final）

**可以宣布 M3 里程碑交付并停住**，但须附带 P0：Effect/ADR-0004 二选一落盘、昏迷苏醒二选一、持刃语义、战斗全局缓冲、`wire_runtime`、创作者契约 v0 + validate warn、票 Status、单机范围降级脚注。  
**明确不做**：商业化实现、创作者平台、编辑器、脚本沙箱、LPC 等价。  
详情见 Final 第 1 节与对抗优先级总表。

## 必读入口（评审共用）

- [PROGRESS.md](../../PROGRESS.md)、[CLAUDE.md](../../CLAUDE.md)
- `.scratch/m1-core-engine-skeleton/`、`m2-mvp-scene-playable/`、`m3-ugc-loop-creation-surface/`
- [docs/adr/](../../docs/adr/)
- `engine/tests/`、`engine/scripts/verify_*.py`、根目录 `justfile` 的 `verify-*`

---

*评审工件已收口；实现与 PROGRESS 更新不在本 README 自动完成。*
