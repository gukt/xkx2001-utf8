# 17 — 死亡流程执行：DeathPolicy + 事件点 + 掉落/惩罚/复活

**What to build:** 把 06 号票的两段式判定状态机接入真实战斗伤害路径（12 号票），落地 spec Implementation Decisions「C1」的流程执行部分：`Vitals.qi_current` 归零时调用 06 号票的判定纯函数决定下一状态（昏迷/死亡），转 `Dead` 时立即执行死亡流程（不等待额外命令）：分发可否决的 `on_before_death`（M1 默认无 handler 即放行）；按 `DeathPolicy`（纯数据参数：惩罚比例、复活点房间 key、是否掉落金钱，场景可声明，缺省给 MVP 默认值，复活点默认华山村）把玩家物品栏物品转移到死亡房间地面容器（复用 `transfer` 原语，不新写一套物品转移）；按惩罚比例扣减金钱（走 07 号票 `Currency`）/技能经验（不扣到负数，下限截断）；移除 `Dead`/`Unconscious`，`Position` 设为复活点房间，`Vitals` 恢复满值；分发 `on_revive`。玩家侧死亡到复活是**同一次流程内直接完成**（不做"停留在死亡状态等待玩家操作"这一步）。本票只处理**玩家**死亡流程；NPC 死亡是完全不同的语义（18 号票）。

**Blocked by:** 06（两段式判定状态机），07（`Currency` 扣款），12（真实战斗伤害路径触发气血归零）。

**Status:** ready-for-agent

- [ ] `Vitals.qi_current<=0` 时（战斗 tick 结算路径内）调用 06 号票判定函数，正确区分"转昏迷"与"转死亡"两条分支。
- [ ] `on_before_death`（可否决）/`on_death`/`on_revive` 三个事件点挂 `world.events`，M1 默认无 handler 时死亡流程按缺省 `DeathPolicy` 正常执行（零回归基线）。
- [ ] `DeathPolicy(penalty_ratio, revive_room_key, drop_currency: bool, ...)` 纯数据参数，场景可选声明（YAML 顶层或 player 段字段，具体挂载位置由实现阶段决定并写清楚），缺省给出 MVP 默认值（复活点默认华山村——若华山村场景本身尚未存在于当前测试场景，测试夹具需要自建一个最小复活点房间，不依赖真正的题材场景内容）。
- [ ] 死亡流程执行顺序：`on_before_death` 不否决 -> 物品栏物品转移到死亡房间地面（`transfer` 原语）-> 按 `penalty_ratio` 扣金钱（不扣到负数）/扣技能经验（不扣到负数）-> 移除 `Dead`/`Unconscious` -> `Position` 设为复活点房间 -> `Vitals` 恢复满值 -> 分发 `on_revive`。
- [ ] `on_before_death` 返回 `Deny` 时死亡流程整体不执行（复用现有 `run_vetoable`/`Deny` 机制）。
- [ ] tick 层测试覆盖：气血归零在免死区域只昏迷不掉落不惩罚；非免死区域第一次归零转昏迷、昏迷中再次归零转死亡并触发完整流程；死亡流程各步骤（物品转移/扣款/扣经验/复活满状态/复活点房间正确）逐条断言。
- [ ] 现有测试全绿不回归。
