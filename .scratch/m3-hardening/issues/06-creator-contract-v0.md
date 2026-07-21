# 06 — 创作者契约 v0 一页纸

**What to build:** 有一份明确写着"这些字段现在可以用、语义已冻结、只会新增不会改义"的文档，而不是要去读引擎源码里的 `_ROOM_KNOWN_FIELDS`/`_NPC_KNOWN_FIELDS` 等常量才知道能写什么。`scene_loader.py` 顶部注释不再自称"M1 内部过渡格式，不是 M3 要交给创作者的正式 DSL"，而是改口"现行创作契约 v0"，让代码内文档与对外承诺的措辞一致。这份契约明确写出"透传字段（`extension_data`）不算冻结契约的一部分，随时可能变化"。

对应 spec：[.scratch/m3-hardening/spec.md](../spec.md) P0-6。

**Blocked by:** 05（`--validate`/`--strict` 的确定行为——本文档需要引用它作为契约的机器可检查侧）。

**Status:** resolved

- [x] 新增 `docs/creator-contract-v0.md`：冻结当前 `scene_loader.py` 的顶层段已知集合（`rooms:`/`items:`/`npcs:`/`player:`/`skills:`/`factions:`/`death_policy:` 等）与各层级已知字段集合（`_ROOM_KNOWN_FIELDS`/`_ITEM_KNOWN_FIELDS`/`_NPC_KNOWN_FIELDS`/`_PLAYER_KNOWN_FIELDS`），以及 `manifest.yaml` 的已知字段（`id`/`version`/`creator`/`title`）。
- [x] 承诺条款：v0 只做加法（新增字段/新增顶层段），不做破坏性语义变更；已知字段之外的透传（`extension_data`）不在冻结范围内，随时可能被未来版本收编为正式字段或改变行为。
- [x] 文档引用 05 号票的 `--validate`/`--strict` 作为契约的机器可检查侧；预留一个指向 GAP 台账（11 号票产出的 `docs/gap-ledger.md`）的引用位置，11 号票落地后补链接（不阻塞本票收尾）。
- [x] 同步改写 `scene_loader.py` 顶部模块 docstring（现文案"M1 内部过渡格式...不是 M3 要交给创作者的正式 UGC DSL"）为指向"现行创作契约 v0"的措辞，不改变任何解析逻辑，纯文案。
- [x] 无自动化测试要求（纯文档产出），验收标准是人工核对文档内容与引用链完整、`scene_loader.py` docstring 措辞已改。

## Comments
