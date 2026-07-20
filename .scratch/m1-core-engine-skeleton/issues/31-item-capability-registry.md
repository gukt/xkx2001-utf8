# 31 - 物品能力组件注册机制（#7 Shotgun Surgery）

**Smell:** 新增一个 item 能力组件要散落改三文件四点：`components.py`（组件类）+ `scene_loader._attach_item_capabilities`/`_ITEM_KNOWN_FIELDS`（加载）+ `save._ser_X`/`_des_X`/`_CODECS`（存档）。`_attach_item_capabilities`（scene_loader.py:155）显式串调 6 个 `_parse_X`，加一能力加一行调用。

**Fix:** 评估组件注册表机制（能力组件自描述 ser/des/attach，注册时统一接入），消除"加一能力改四处"。注意 M1 不预支 M3，但注册表是引擎机制非 UGC，可做。先评估工作量 vs 收益再定范围（可能超 3 倍预估需止损重估）。

**From:** BCD re-pass code-review 物品批 Standards #7（commit 79b831ef）。

**Status:** resolved

- [x] 新增能力组件的改动点收敛（不再散落三文件四点）
- [x] just gate 全绿

**Resolved:** 2026-07-20，commit `82d0c334`。
经评估后实现统一注册表：新建 `engine/src/mud_engine/capabilities.py`，7 个 item 能力（Stackable/Valuable/Equippable/Consumable/ItemFlags/Container/Weight）自描述 parse/ser/des/known_fields；scene_loader 遍历注册表挂载，_ITEM_KNOWN_FIELDS 由注册表聚合；save 的 item 能力 codec 来自注册表。新增能力只需：1) components.py 定义类；2) capabilities.py 注册一条 spec。Weight/Stackable 互斥通过 attached 上下文处理，注册表顺序保证 Stackable 先于 Weight。402 绿。
