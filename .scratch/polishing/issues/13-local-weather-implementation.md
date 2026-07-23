---
Status: resolved
---

# 13 — C14b 局部天气继承：实现

**What to build:** 按票 `12` 产出的 ADR 落地局部天气继承——具体数据模型（房间级静态天气「贴纸」/ region 树 + 每 region 一个可选 `NatureState` 覆盖 / 其它 ADR 选定方案）以 ADR 结论为准，本票不预先指定实现模块。至少支持「某些房间/区域天气与 world 默认不同」（如山顶终年多雾、渡船区域独立于城镇天气）；影响范围覆盖户外 `look` 描述文案与条件 DSL 里 `is_raining`/`is_night` 类谓词在该房间的取值；未声明局部覆盖的房间无条件回退到 ADR 选定的默认态；不新增天气→数值的玩法影响（移动/战斗/坐骑等）。

对应 spec：`.scratch/polishing/spec.md` §C14（User Stories 42–44；Implementation Decisions「C14」）。

**Blocked by:** `12`（C14a 局部天气继承 ADR——本票的具体实现模块、字段形状、回退语义均以该 ADR 结论为准，ADR 未 Accepted 前不得开工）。

- [x] 按 ADR `0013`（或票 `12` 最终确定的编号）选定的数据模型实现局部天气覆盖（模块/组件命名以 ADR 结论为准）。
- [x] `scene_loader.py`：房间/区域声明局部天气覆盖的字段解析（字段名/形状以 ADR 结论为准）；契约新增字段——`docs/creator-contract-v0.md` 同步补写。
- [x] 户外 `look` 描述文案在有局部覆盖的房间正确反映覆盖态，无覆盖房间回退到 world 单例 `NatureState`。
- [x] 条件 DSL `is_raining`/`is_night` 类谓词在有局部覆盖的房间求值时使用该房间的局部取值，无覆盖房间使用 world 单例取值。
- [x] 确认未新增天气→数值的玩法影响（移动/战斗/坐骑等相关代码路径不因本票改动）。
- [x] `docs/gap-ledger.md`：「局部 / 区域天气继承」行从「未支持」更新为「已支持」并指向 ADR 与新契约字段。
- [x] `CONTEXT.md`：补写「局部天气」（或 ADR 选定命名）词条。
- [x] 新测试：覆盖有局部覆盖房间的 `look` 描述与条件谓词取值、无覆盖房间回退 world 单例、（如 ADR 选定多级 region）多级回退链。
- [x] `just test` 全绿。

## Comments

- **组件 / YAML**：`LocalNature`；`local_nature: { weather?: clear|rain, phase?: <DEFAULT_PHASES ∪ 场景 nature.day_phases 名> }`；两面皆缺不挂组件。
- **合成 API**：`nature.resolve_effective_nature(world, room_id)` / `outdoor_desc_for_room`；回退两级 `房间贴纸已声明面 → World.nature`（无 region 中间层）。
- **接入点**：户外 `look`；`EntityGateContext`（默认演员当前房；`entry_guard` 显式 `room_id=to_room`）；`RoomHookContext`；`_JoinContext`；AI `behaviors[].when` 按 NPC 所在房。
- **ADR-0013**：`proposed` → `accepted`。
- **不做**：天气→移动/战斗/坐骑数值；第二 `NatureState`；按房分裂 `on_nature_change` 广播。
