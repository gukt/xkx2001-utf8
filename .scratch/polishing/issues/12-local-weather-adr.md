---
Status: ready-for-agent
---

# 12 — C14a 局部天气继承：ADR

**What to build:** 写一份 ADR（编号续接现有序号，当前最新 `0012`，本票产出 `docs/adr/0013-*.md`；具体文件名/编号在写作时确认无冲突后确定）正面回答局部天气继承如何与既有架构不变量共存，**本票不写任何实现代码**，只产出决策记录。

对应 spec：`.scratch/polishing/spec.md` §C14（User Stories 42–44；Implementation Decisions「C14」「前置阻塞」小节）；[ADR-0009](../../../docs/adr/0009-single-process-single-world.md)。

**Blocked by:** None — 可立即开始（本票是 C14 的前置门闩，票 `13` 的实现依赖本票的 ADR 结论）。

- [ ] ADR 正面回答：与 [ADR-0009](../../../docs/adr/0009-single-process-single-world.md)「单进程单 World」的关系——局部天气是否意味着引入多个 `NatureState` 实例？若是，是否违反或需要收窄 ADR-0009？
- [ ] ADR 正面回答：与 `nature.py` 现有「`NatureState` 是 world 级纯内存态单例」设计注释的关系——是否改造为每 room/region 可覆盖，还是新增一层独立于 tick 推进的静态覆盖（不随时间/天气翻转变化，只是「这个房间描述永远长这样」）。
- [ ] ADR 明确影响范围边界：至少覆盖户外 `look` 描述文案与条件 DSL 里 `is_raining`/`is_night` 类谓词在该房间求值时的取值；**不**引入跨房间气候传播、不引入需要额外调度的独立天气循环（除非 ADR 明确论证需要）。
- [ ] ADR 明确回退语义：房间未声明局部覆盖时必须无条件回退到某个确定态（回退到父级 region 还是直接回退到 world 单例 `NatureState`，由 ADR 定），两级回退链不能丢，不能出现「无覆盖也无默认」的未定义态。
- [ ] ADR 裁剪范围可以是「本效力只做一层房间覆盖，不做多级 region 继承」这种最小满足需求的形状，只要写清楚裁剪理由；不要求做到「任意粒度、任意继承深度」的通用区域树。
- [ ] ADR 明确不做局部天气对玩法数值的额外影响（移动/战斗/坐骑等）——只影响描述性文本与既有条件谓词读数，不新增天气→数值的映射。
- [ ] ADR 状态：`Proposed`（`/implement` 阶段落地后回写 `Accepted`，与既有 ADR 惯例一致）。
- [ ] `CONTEXT.md` / `PROGRESS.md` 无需在本票同步回写（留给票 `13` 实现落地时一并处理）。
