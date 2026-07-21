# 10 — 坐骑与骑乘：Mount / Riding 组件 + 购买 + ride/unride + 人马同步移动

**What to build:** 落地 spec Implementation Decisions「F1」：坐骑本质是挂了 `Mount(ability: int, jingli_current: int, jingli_max: int, ridden_by: EntityId | None = None)` 组件的普通实体，复用 `Identity`/`Description`/`Position`/`Container`（坐骑能驮东西），场景 YAML 的 `npcs:` 段新增 `mount:` 字段声明这些参数（复用现有 NPC 建造管线，不新起 `mounts:` 顶层段），走 01 号票的 NPC 级能力注册表。`Riding(mount_id: EntityId)` 挂在骑手身上；`ride <坐骑>`/`unride` 命令互相设置/清除 `Riding.mount_id` 与对应 `Mount.ridden_by`（双向保持一致）。`go` 命令扩展：玩家有 `Riding` 时，移动同步把坐骑实体的 `Position` 也改到同一新房间（坐骑不单独走出口判定）。**购买坐骑**（spec 用户故事 47："向马厩的马夫 NPC buy 一匹坐骑，消耗银两，成为该坐骑的主人"）：本票需要决定并落地一个具体机制——推荐方案是扩展 07 号票的 `buy` 命令，当商店清单的 `ShopEntry` 引用的不是 `items:` 物品模板而是一个"坐骑模板"（NPC 段声明的、带 `for_sale` 标记或类似的 `mount:` NPC 模板）时，`buy` 实例化一份新的坐骑 NPC 放进玩家当前房间（而非放进玩家物品栏——坐骑不是物品）。**MVP 明确不做**坐骑归属校验（`ridden_by` 之外不设 owner 字段，`ride` 命令不检查"是否是我买的"，对齐 spec Out of Scope"坐骑被抢/被盗留给后续"），"成为主人"在 MVP 只是叙事措辞，机制上体现为"坐骑出现在你能立刻骑乘的位置"。

**Blocked by:** 01（`Mount`/`Riding` 走注册表挂载），07（购买坐骑复用/扩展 `buy` 命令与 `Currency` 扣款）。

**Status:** ready-for-agent

- [ ] `Mount(ability, jingli_current, jingli_max, ridden_by)` 组件落地，走 NPC 级能力注册表（YAML `mount:` 字段）；`Riding(mount_id)` 组件挂骑手身上。
- [ ] `ride <坐骑>`：目标须是玩家可达（同房间）且未被骑乘的坐骑，成功后双向设置 `Riding.mount_id`/`Mount.ridden_by`；已在骑乘中再次 `ride` 给出提示；`unride`：清空双向引用，坐骑留在当前房间。
- [ ] `go` 命令扩展：骑乘状态下移动，坐骑 `Position` 与骑手同步换房间；命令测试覆盖"骑乘时移动后 `look` 坐骑所在房间与骑手一致"。
- [ ] 明确记录本票关于"购买坐骑"机制的具体实现选择（无论是扩展 `buy` 命令、还是新增专属 `buy_mount`/`hire` 一类命令，选一个写清楚并在本票 Comments 追加说明），供 23 号票（扬州马厩场景内容）直接对照使用，不留歧义给内容票现场发明。
- [ ] 购买坐骑：扣款走 `Currency`（复用 07 号票机制）；成功后坐骑实体出现在玩家当前房间（立即可 `ride`），不进玩家 `Container`。
- [ ] 移动效率/描述差异（spec"移动描述与移动效率都会体现'骑着走'"）：至少在 `go` 命令消息文案层面体现骑乘状态（本票不要求实现真实移动速度数值差异，MVP 移动始终是"一步到位"，见 spec F1 决策）。
- [ ] 存档往返：`Mount`/`Riding` 双向引用 save→restore 后一致。
- [ ] 现有测试全绿不回归。
