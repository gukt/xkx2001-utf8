---
Status: ready-for-agent
---

# 13 — C14b 局部天气继承：实现

**What to build:** 按票 `12` 产出的 ADR 落地局部天气继承——具体数据模型（房间级静态天气「贴纸」/ region 树 + 每 region 一个可选 `NatureState` 覆盖 / 其它 ADR 选定方案）以 ADR 结论为准，本票不预先指定实现模块。至少支持「某些房间/区域天气与 world 默认不同」（如山顶终年多雾、渡船区域独立于城镇天气）；影响范围覆盖户外 `look` 描述文案与条件 DSL 里 `is_raining`/`is_night` 类谓词在该房间的取值；未声明局部覆盖的房间无条件回退到 ADR 选定的默认态；不新增天气→数值的玩法影响（移动/战斗/坐骑等）。

对应 spec：`.scratch/polishing/spec.md` §C14（User Stories 42–44；Implementation Decisions「C14」）。

**Blocked by:** `12`（C14a 局部天气继承 ADR——本票的具体实现模块、字段形状、回退语义均以该 ADR 结论为准，ADR 未 Accepted 前不得开工）。

- [ ] 按 ADR `0013`（或票 `12` 最终确定的编号）选定的数据模型实现局部天气覆盖（模块/组件命名以 ADR 结论为准）。
- [ ] `scene_loader.py`：房间/区域声明局部天气覆盖的字段解析（字段名/形状以 ADR 结论为准）；契约新增字段——`docs/creator-contract-v0.md` 同步补写。
- [ ] 户外 `look` 描述文案在有局部覆盖的房间正确反映覆盖态，无覆盖房间回退到 world 单例 `NatureState`。
- [ ] 条件 DSL `is_raining`/`is_night` 类谓词在有局部覆盖的房间求值时使用该房间的局部取值，无覆盖房间使用 world 单例取值。
- [ ] 确认未新增天气→数值的玩法影响（移动/战斗/坐骑等相关代码路径不因本票改动）。
- [ ] `docs/gap-ledger.md`：「局部 / 区域天气继承」行从「未支持」更新为「已支持」并指向 ADR 与新契约字段。
- [ ] `CONTEXT.md`：补写「局部天气」（或 ADR 选定命名）词条。
- [ ] 新测试：覆盖有局部覆盖房间的 `look` 描述与条件谓词取值、无覆盖房间回退 world 单例、（如 ADR 选定多级 region）多级回退链。
- [ ] `just test` 全绿。
