# GAP 台账

> 声明式场景 YAML / 内容包**当前表达不了什么**、撞墙时怎么降级。  
> 对应 CONTEXT.md「GAP 台账」词条；创作者契约见 [creator-contract-v0.md](creator-contract-v0.md)。  
> 产出自 M3 停机加固票 [`11`](../.scratch/m3-hardening/issues/11-gap-ledger.md)。

本文档**不是**能力橱窗包：不新建专门展示引擎全部能力的示例内容包，也不预留空脚本沙箱接缝。只列缺口与推荐绕过。

| 缺口 | 现状 | 推荐降级方式 |
|---|---|---|
| **持续 Effect**（buff / debuff、持续伤害、状态叠层） | 引擎战斗七步骨架与 `SkillBehavior` 瞬时钩子可用；完整 Effect 调度 / 衰减 / 移除**未**在 M2/M3 停机范围兑现。归属仍归引擎，见 [ADR-0007](adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)（收窄 [ADR-0004](adr/0004-combat-effects-boundary-engine.md) 的停机范围，不改归属）。 | 用 `SkillBehavior.hit_ob` / `hit_by` / `post_action` 做一次性伤害加成与播报文案；不要在 YAML 里假设「挂 buff 持续 N tick」。 |
| **脚本化任务 / 剧情分支** | M3 创作面是包外声明式 YAML（manifest + scene），无 RestrictedPython / WASM / Ink 对话树。见 [ADR-0005](adr/0005-m3-ugc-loop-creation-surface.md) OOS。 | 用静态房间图 + `entry_guard` 条件 + `ask` 问答表 + NPC `behaviors`（Chatter / Aggro）表达线性或浅分支；深剧情留给后续创作面，不在 YAML 里嵌脚本。 |
| **多人频道 / 双玩家广播** | 单机 CLI：`say` + `room_say` 同房间广播即可玩。频道与登录**不是**停机门闩。见 [ADR-0008](adr/0008-single-player-channel-login-out-of-stop-scope.md)。 | 单机内容按「房间内一人」设计文案与触发；不要依赖跨房间频道、私聊或登录会话层。 |
| **装备槏位与真实 wield / unwield** | 物品可有 `equippable` / `item_tags`（如 `edged`）；门禁求值器仍保留 `is_wielding_edged_weapon`，但**没有** `wield` / `unwield` / `stash` 命令，玩家无法主动改变「持刃」态。官方少林山门已去掉持刃条件（加固票 [`02`](../.scratch/m3-hardening/issues/02-shaolin-gate-drop-edged-condition.md)）。 | 门禁只用玩家可操作的条件（性别、门派、`has_item` 等）；武器差异用背包标签或属性字段表达，勿要求玩家「收刀」。 |
| **坐骑驯服 / 被抢** | 支持场景内展示马、`buy` 坐骑、`ride` / `unride`、骑乘同步移动与 `Terrain.cost` 校验。无驯服流程、无骑乘争夺 / 抢马。 | 把坐骑当商店货或房间固定 NPC；用购买门槛代替驯服；不要设计「野马驯服」或「打落对方坐骑」。 |
| **多文件 / 大世界树场景** | 单包单 `scene.yaml`（或默认 CLI 单文件官方场景）；无多文件 include / 世界树拼接加载。 | 按区域拆成多个内容包，或把 MVP 规模地图收进一份 YAML；超大世界留待后续加载器能力，勿在 v0 契约外发明私有多文件约定。 |
