# 12 — 交战与战斗命令：Engaged 组件 + tick 自动回合 + attack/flee + 战斗事件点

**What to build:** 把 02 号票的 `resolve_attack` 纯函数接入真实 ECS 与命令层，落地 spec Implementation Decisions「A1」的调度部分：新增 `Engaged(opponent: EntityId)` 组件（交战关系，双方各挂一份互相指向，运行时可变进存档——不是散落临时变量）；`attack <目标>`（别名 `kill`）命令建立交战关系（不直接结算伤害）；`flee` 命令尝试脱离交战（可能失败并挨一次攻击）；一个挂 `on_tick` 的系统（类似 `ai.py` 的 `AIController` 遍历模式）每 tick 遍历所有处于交战状态的实体对，跳过已失效（死亡/脱离）的交战关系，从真实 `Vitals`/`BaseAttributes`/`SkillLevels` 组件构造 02 号票的 `CombatContext`，调 `resolve_attack`，把结果 apply 回真实组件（扣血、生成战斗播报消息）。新增三个战斗事件点（挂 `world.events`，空挂不改默认行为）：`on_before_combat_round`（可否决）、`on_combat_round`、`on_combat_end`。MVP 战斗简化为 1 对 1（一个实体同一时刻只与一个对手交战）。本票**不**处理气血归零后的死亡判定（那是 17 号票消费本票产出的伤害结果）、**不**接入 `SkillBehavior` 钩子实际生效（16 号票）、**不**处理 NPC 主动攻击（19 号票，仅复用本票"建立交战关系"的共享函数）。

**Blocked by:** 02（`resolve_attack`/`CombatContext`/`PowerModel`），03（`SkillData` 提供技能/招式候选），05（`Vitals`/`BaseAttributes`/`SkillLevels` 真实组件）。

**Status:** resolved

- [x] `Engaged(opponent: EntityId)` 组件落地，双方各挂一份，走 01 号票的注册表模式（本组件是运行时动态产生，不从 YAML 声明，但存档序列化仍走统一 codec 注册模式，保持"新组件加进注册表"这一条纪律一致）。
- [x] `attack <目标>`（`kill` 别名）：同房间目标建立双向 `Engaged`；已在交战中再次 attack 给出提示；目标不存在给提示。
- [x] `flee`：脱离交战有一定失败概率（结构与是否失败的判定逻辑由实现阶段决定，需可测试、确定性可控——如接受一个可注入 seeded RNG）；失败时对手（挂 `on_tick` 系统）本回合视为"脱离失败"触发一次额外攻击。
- [x] on_tick 系统：遍历带 `Engaged` 的实体对（避免同一对双向各算一次），从真实组件构造 `CombatContext`（读 `Vitals`/`BaseAttributes`/`SkillLevels`，技能招式候选查 03 号票 `SKILLS`），调 `resolve_attack` 后把结果写回 `Vitals`（扣血），生成清晰战斗播报（命中/闪避/招架/伤害数值/招式名/剩余气血提示，对应用户故事 3）。
- [x] `on_before_combat_round`（可否决）/`on_combat_round`/`on_combat_end` 三个事件点挂 `world.events`，M1 默认无 handler 时零回归。
- [x] MVP 1 对 1 约束：一个实体同一时刻只允许一份 `Engaged`（尝试对已在交战中的第三方 `attack` 给出"对方正在和别人打"一类提示，不建立第二份 `Engaged`）。
- [x] `hit_ob`/`hit_by`/`post_action` 钩子调用点（02 号票已留占位）在本票的真实 tick 调度路径里被正确调用一次（即使当前招式都没有 `SkillBehavior` 实现，调用本身要发生——为 16 号票接入真实钩子铺路，16 号票验收时应能观察到"调用发生了但无副作用"到"调用发生且产生副作用"的行为切换，不需要改本票代码）。
- [x] tick 层测试（`TickLoop.advance`/`dispatch(ON_TICK,...)` seam）：反复推进 tick，断言交战双方气血按 `resolve_attack` 确定性结果变化；命令层测试覆盖 attack/flee 的各分支。
- [x] 现有测试全绿不回归。

## Comments

- 2026-07-21：`combat_system.py` + `Engaged` codec；`flee_success_chance` 可注入；tick 内每对双方各出手一次。
