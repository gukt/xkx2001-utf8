# 06 — 死亡状态机核心：Unconscious / Dead 标记 + 两段判定纯函数 + NoDeathZone

**What to build:** 落地 spec Implementation Decisions「C1」的状态机**核心判定逻辑**（不含掉落/惩罚/复活流程执行，那是 17 号票）：新增 marker 组件 `Unconscious`（挂即"昏迷中，无法执行会触发交战/移动的命令"，运行时可变进存档）与 `Dead`（挂即"死亡，等待复活流程处理"，同样进存档）；存活态用"两个组件都不挂"表达，不新增 `Alive` marker（避免三态用两个独立布尔表达出非法组合）。落地两段式判定的**纯函数**（给定"当前状态（存活/昏迷）+ 是否免死区域 + 本次是否气血耗尽"，返回"下一状态"）：气血耗尽时，若当前房间挂 `NoDeathZone` 则只转 `Unconscious`（反复昏迷允许）；未挂 `NoDeathZone` 且已经是 `Unconscious`（昏迷中又被击中）则转 `Dead`；否则转 `Unconscious`（第一段，容错，不掉落不惩罚）。新增房间级 marker 组件 `NoDeathZone`（独立组件，不塞进 `Description`——这条能力与"户外/天气展示"完全不同的语义关注点，spec 明确要求不内聚复用），走 01 号票的房间级能力注册表挂载（YAML `no_death: true`）。本票**不**实现 `on_before_death`/`on_death`/`on_revive` 事件点与死亡流程的实际执行（掉落物品、扣钱、复活满状态）——那是 17 号票依赖本票产出的状态机；本票只保证"给定输入两次求值结果一致"这条纯函数契约可独立断言（spec Testing Decisions"死亡判定的两段式状态转移函数"直测 seam）。

**Blocked by:** 01（`NoDeathZone` 是房间级能力，需走注册表模式挂载）。

**Status:** ready-for-agent

- [ ] `Unconscious`/`Dead` 两个 marker dataclass 落地；两者都不挂 = 存活（不新增 `Alive`）。
- [ ] 两段式判定纯函数：签名建议类似 `next_death_state(current: DeathState, *, in_no_death_zone: bool) -> DeathState`（`DeathState` 用枚举或"是否挂 Unconscious/Dead"的最小表达，实现阶段自定），不依赖 `World`/组件读写，直接构造输入断言输出——对齐纯函数直测 seam。
- [ ] `NoDeathZone` 房间级 marker 组件，走 01 号票注册表挂载（YAML `no_death: true`），不挂在 `Description` 上。
- [ ] 判定逻辑覆盖 4 种输入组合的测试：（存活+免死区+耗尽）->昏迷；（存活+非免死区+耗尽）->昏迷；（已昏迷+免死区+耗尽）->仍昏迷（反复昏迷允许）；（已昏迷+非免死区+耗尽）->死亡。
- [ ] `Unconscious`/`Dead` 存档序列化走 01 号票注册表 codec（挂 marker 后 save→restore 该 marker 仍在）。
- [ ] 本票**不**要求任何命令（`attack`/`status` 等）读这两个 marker 做行为限制——"昏迷中无法执行会触发交战/移动的命令"这条行为限制留给 12/17 号票在真正接入战斗/移动路径时处理，本票只交付状态机与组件本身，避免在没有真实触发源的情况下改动现有命令行为。
- [ ] 现有测试全绿不回归。
