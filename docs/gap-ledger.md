# GAP 台账

> 声明式场景 YAML / 内容包**当前表达不了什么**、撞墙时怎么降级。  
> 对应 CONTEXT.md「GAP 台账」词条；创作者契约见 [creator-contract-v0.md](creator-contract-v0.md)；  
> 官方轨 / 内容包轨怎么选见 [scene-authoring-guide.md](scene-authoring-guide.md)。  
> 产出自 M3 停机加固票 [`11`](../.scratch/m3-hardening/issues/11-gap-ledger.md)；  
> Pre-M4 房间钩子收口增补见票 [`11`](../.scratch/pre-m4-room-hooks-xingxiu/issues/11-closeout-ugc-boundary-contract-gap.md)。  
> **Polishing grill（2026-07-23 已确认）**：若干缺口升格进 Polishing effort（待 `/to-spec` 落地）；见 [.scratch/polishing-candidate-review/session-notes-2026-07-23.md](../.scratch/polishing-candidate-review/session-notes-2026-07-23.md)。本表「现状」在实现关闭前仍写能力真相。

本文档**不是**能力橱窗包：不新建专门展示引擎全部能力的示例内容包，也不预留空脚本沙箱接缝。只列缺口与推荐绕过。

| 缺口 | 现状 | 推荐降级方式 |
|---|---|---|
| **持续 Effect**（buff / debuff、持续伤害、状态叠层） | 引擎战斗七步骨架与 `SkillBehavior` 瞬时钩子可用；完整 Effect 调度 / 衰减 / 移除**未**在 M2/M3 停机范围兑现。归属仍归引擎，见 [ADR-0007](adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)（收窄 [ADR-0004](adr/0004-combat-effects-boundary-engine.md) 的停机范围，不改归属）。 | 用 `SkillBehavior.hit_ob` / `hit_by` / `post_action` 做一次性伤害加成与播报文案；不要在 YAML 里假设「挂 buff 持续 N tick」。 |
| **脚本化任务 / 剧情分支** | 声明式旗标任务（YAML `quests.<id>` + `quest accept` + `give` 交物 / 旗标完成、给钱奖励）**已支持**（严格切片，非通用任务引擎；官方示例 `escort_delivery`）。RestrictedPython / WASM / Ink 对话树等脚本化剧情**仍未**提供。见 [ADR-0005](adr/0005-m3-ugc-loop-creation-surface.md) OOS 与 [pre-m4-channels-spawn-quest](../.scratch/pre-m4-channels-spawn-quest/)。 | 浅闭环（接取→交物领赏）用声明式 Quest；深剧情 / 多步对话树仍后置，不在 YAML 里嵌脚本。`ask` 仍只返回打听文案、不接任务。 |
| **多人频道 / 双玩家广播** | **已支持（严格切片）**：同 World 可挂多个带 `PlayerSession` 的实体（测试 / 脚本 seam）；预置 Channel `chat`（玩家命令 `chat <text>`）与 `system`（仅引擎 API / 测试注入）；创建会话默认订阅两者。**不是**登录会话层或真实联网多人；无 `tune` / 私聊 / 门派频道。频道与登录**仍不是**停机门闩。见 [ADR-0008](adr/0008-single-player-channel-login-out-of-stop-scope.md) 澄清与 [pre-m4-channels-spawn-quest](../.scratch/pre-m4-channels-spawn-quest/)。 | 需要完整多人网游、登录、私聊或运营级频道策略时仍不可用；单机 REPL 体验仍不以多人为验收标准。 |
| **物品 / NPC 槽位补刷** | **已支持**：房间 `objects`（模板键 → 数量）为放置权威；模板 `respawn` 控制销毁后是否补刷；登记实例仍在（背包 / 别房也算）则占名额。见 [ADR-0010](adr/0010-room-centric-objects-placement.md) 与 [pre-m4-channels-spawn-quest](../.scratch/pre-m4-channels-spawn-quest/)。 | 勿再写 `placed_in` / `in_room`；门钥匙等唯一引用物品不得 `objects` 合计 `>1` 或 `respawn: true`。 |
| **装备槏位与真实 wield / unwield** | 物品可有 `equippable` / `item_tags`（如 `edged`）；门禁求值器仍保留 `is_wielding_edged_weapon`，但**没有** `wield` / `unwield` / `stash` 命令，玩家无法主动改变「持刃」态。官方少林山门已去掉持刃条件（加固票 [`02`](../.scratch/m3-hardening/issues/02-shaolin-gate-drop-edged-condition.md)）。 | 门禁只用玩家可操作的条件（性别、门派、`has_item` 等）；武器差异用背包标签或属性字段表达，勿要求玩家「收刀」。 |
| **坐骑驯服 / 被抢** | 支持场景内展示马、`buy` 坐骑、`ride` / `unride`、骑乘同步移动与 `Terrain.cost` 校验。无驯服流程、无骑乘争夺 / 抢马。 | 把坐骑当商店货或房间固定 NPC；用购买门槛代替驯服；不要设计「野马驯服」或「打落对方坐骑」。 |
| **多文件 / 大世界树场景** | 单包单 `scene.yaml`（或默认 CLI 单文件官方场景）；无多文件 include / 世界树拼接加载。**Polishing C13 已拍板纳入**（待 to-spec/实现）。 | 实现前：按区域拆成多个内容包，或把 MVP 规模地图收进一份 YAML；勿在 v0 契约外发明私有多文件约定。 |
| **房间风景（details）** | **已支持（Pre-M4 形状）**：键 → 文本。**Polishing A4 已拍板**升级为英键 + `text`/`aliases`、纯文本`名(id)`扫描（S1）、id 归一 N1（待 to-spec/实现）。 | 实现前仍按现行键→字符串写作；勿把牌子做成 `objects` 假物品。 |
| **语义色 markup** | **已支持（严格切片）**：权威文本 `<c:name>…</c>`；七色；加载/`--validate` 拒 ANSI 与 LPC 色宏；CLI TTY/`--color` 映 ANSI，管道剥纯文本。见 [ADR-0011](adr/0011-semantic-color-tokens.md)。无嵌套/背景/闪烁/粗体 token。 | 勿在 YAML 写 ANSI 或 `HIG`/`NOR`；勿假定服务端已染成唯一真源。 |
| **藏书（library / books）** | **已支持（严格切片）**：顶层 `books.*` + 房间 `library`；TOC / 缩写选书 / 按章付费 / `more` 分页；同房禁 `practice`；旗标 `no_fight` 等可声明。官方扬州藏书阁。**不是**完整 `jybooks` 移植或通用阅读器。 | 书档放题材包内；勿用外部 URL；勿仅靠 `details` 书架文案冒充可读闭环。 |
| **日间店铺（day_shop）** | **已支持**：`day_shop: true` 加载期编成白天放行的 `entry_guard`（谓词 `is_day`）；与手写 `entry_guard` 并存则加载失败。官方打铁铺。 | 勿平行第二套进房时间系统；勿同房叠写冲突守卫。 |
| **剧情门（声明式三件套）** | **已支持（严格切片）**：出口 `consume_key` / `hidden_until_unlocked`；房间 `block_exits`（NPC 在场挡向）。官方翰林三件套。创作者契约路径止于此——**不是**通用 `add_exit`/`remove_exit` 脚本 API；运行时改出口见下行「运行时改世界机关」（官方钩子轨）。**Polishing A5**：`deny_message` 已拍板纳入。 | 标准门默认不耗钥；UGC / 契约场景用声明式三件套表达门感；勿在内容包 YAML 嵌钩子或运行时改图脚本。 |
| **运行时改世界机关**（动态出口/时限崩塌、多步状态机、迷途、jump·climb、时段秘道、磁力、劫匪刷拦、杀令介入、柔丝索捕获等） | **已支持（官方轨严格切片）**：可信房间钩子（`hooks` + 窄 `ctx`）与加载期小原语 `random_of`；验收挂 `xingxiu_mechanics.yaml`。UGC 内容包仍**禁止** `hooks`。**Polishing C12**：贵重物等刷怪条件扩展走**官方 hooks**（不扩 DSL）。**C15** 额外 valid_leave 脚本化 → 仍 GAP 后置。 | 纯声明式 YAML **独立表达不到**这类机关；UGC 用剧情门三件套 / 静态拓扑降级——勿在内容包写 `hooks`。 |
| **液体灌装 / 饮用 / eat** | **已支持（严格切片）**：房间 `resource.water`；物品 `liquid_container` + 运行时 `filled_liquid`；命令 `fill` / `drink` / `eat`。效果为当次一次性数值变化，不接持续 Effect（ADR-0007）。**未**打通：`resource.grass` / 坐骑喂食、醉酒/持续中毒等跨 tick 状态。 | 河边/井边标 `resource.water: true`；水袋标 `liquid_container: true`；干粮标 `consumable`。勿假设饮酒致醉或草场喂马已可用。 |
| **invalid_startroom / 存档出生点** | **未支持**（渡船等禁存起点）。**Polishing grill：B7 → GAP·后置**。 | 后置；勿假设 quit 会强制改写出生点到客店。 |
| **局部 / 区域天气继承** | **未支持**（Nature 为 World 单例）。**Polishing C14 已拍板纳入**（需 ADR，待 to-spec）。 | 实现前只用全局昼夜/雨；勿假设房间局部天气。 |
| **防拐带（NPC 进玩家容器）** | **未支持**：无 `valid_leave` 式防拐带规则。 | 后置；勿设计「把 NPC 塞进背包带走」玩法。 |
