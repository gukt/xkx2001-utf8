# 07 — 货币与商店：Currency 组件 + buy/sell 命令 + ShopInventory 声明式配置

**What to build:** 落地 spec Implementation Decisions「D1」：`Currency(amount: int)` 组件（挂在需要持有货币的实体上：玩家、掉落金钱的 NPC 战利品来源、商店 NPC 若表达"钱庄本身有余额"可选挂）；`ShopInventory(entries: tuple[ShopEntry, ...])` + `ShopEntry(item_template_key: str, resell_discount: float = 1.0)`（NPC 声明式配置，`item_template_key` 引用场景 `items:` 段的一个物品模板）；新增 `buy <物品>`/`sell <物品>` 命令。`buy` 从商店清单模板按需实例化物品（不是从共享池搬运已存在实体，MVP 商店库存不设上限）；价格直接复用 M1 已埋的 `Valuable.value`（`buy` 按 `value` 收费，`sell` 按 `value` × 商店折扣率收购，未声明 `Valuable` 的物品不能被 buy/sell，配置错误在加载期报错）。`Currency`/`ShopInventory` 走 01 号票的 NPC 级能力注册表挂载。本票不做多币种/账本抽象（06 号票商业化支撑点，MVP 不要求），不做"钱庄钱不够收不了"限制（商店余额视为无限）。

**Blocked by:** 01（`Currency`/`ShopInventory` 是 NPC/玩家级能力，需走注册表模式）。

**Status:** resolved

- [x] `Currency(amount: int)` 组件落地，玩家与需要持有货币的 NPC 都可挂；玩家初始余额可由场景 `player:` 段声明（若走 01 号票注册表覆盖不到 `player:` 段，直接加进 `_PLAYER_KNOWN_FIELDS`，不为此单独建注册表）。
- [x] `ShopInventory`/`ShopEntry` 组件落地，走 NPC 级能力注册表（YAML `shop:` 字段，引用 `items:` 段的模板键，引用不存在的物品模板在加载期报 `SceneLoadError`）。
- [x] `buy <物品>` 命令：从同房间挂 `ShopInventory` 的 NPC 清单里按 `Valuable.value` 收费，实例化一份新物品放进玩家物品栏（走 `transfer` 原语或等价路径，复用 M1 机制不新写一套）；余额不足给明确提示，不扣款不发货。
- [x] `sell <物品>` 命令：把玩家物品栏物品卖给同房间挂 `ShopInventory` 的 NPC，按 `Valuable.value × resell_discount` 收购（商店清单未包含该物品类型时用什么折扣率——实现阶段决定一个明确默认策略并写进代码注释，不留未定义行为）。
- [x] 未声明 `Valuable` 的物品模板被 `ShopEntry` 引用时，在加载期（不是运行时 buy 那一刻）报 `SceneLoadError`，定位到具体商店/物品模板。
- [x] 命令层测试覆盖：正常 buy/sell、余额不足、物品栏没有要卖的物品、房间没有商店 NPC 四种路径。
- [x] 存档往返：`Currency.amount` 变化后 save→restore 一致。
- [x] 现有测试全绿不回归。
