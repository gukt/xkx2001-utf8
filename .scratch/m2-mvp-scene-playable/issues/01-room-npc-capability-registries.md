# 01 — 房间级 / NPC 级能力自描述注册表（防 Shotgun Surgery 预制票）

**What to build:** 把 `engine/src/mud_engine/capabilities.py` 里 31 号票（M1）验证过的 `CapabilitySpec`（YAML 解析 + 已知字段集合 + 存档序列化/反序列化四元组）模式，从"仅覆盖物品能力"推广到**房间级**与**NPC 级**能力。当前 `scene_loader.py` 的 `_ROOM_KNOWN_FIELDS`（`{"name","aliases","short","long","exits","outdoors"}`）与 `_NPC_KNOWN_FIELDS`（`{"name","aliases","short","long","in_room","startroom","count","respawn","inquiry","behaviors","tick_interval"}`）是硬编码 frozenset，`save.py` 的 `_CODECS` 对房间/NPC 组件也是硬编码字典。本票新增两个注册表（可复用 `capabilities.py` 一个模块，或拆成 `room_capabilities.py`/`npc_capabilities.py`，实现阶段自行决定），把 `_ROOM_KNOWN_FIELDS`/`_NPC_KNOWN_FIELDS` 改为从注册表聚合（同 `_ITEM_KNOWN_FIELDS` 现在的写法），`save.py` 的房间/NPC 相关 codec 同理迁移。这是本 spec Implementation Decision「H1」明确要求的地基："块 B~G 每新增一个需要 YAML 声明的能力…都在对应的能力注册表里追加一条自描述规格…不再各自散改 scene_loader.py/save.py 的多处已知字段集合与 codec 字典"（spec 用户故事 67）。本票**先行**做这件事（不是等 B~G 做完后再回头搬），后续块 B/C/E/F 新增的房间能力（`Terrain`/`NoDeathZone`/`EntryGuard`/`Ferry`）与 NPC 能力（`Vitals`/`BaseAttributes`/`SkillLevels`/`Faction`/`Gender`/`Mount`/`ShopInventory`）只需要往注册表追加一条 spec，不再改 `scene_loader.py`/`save.py` 本体。本票只做**基础设施迁移**，不新增任何新组件——验收标准是"现有房间/NPC 能力（如 `outdoors`、`inquiry`、`behaviors`）改走注册表后，全部现有测试零回归"。

**Blocked by:** None — 可立即开始，是全部后续票的地基（prefactor-first）。

**Status:** resolved

- [x] 新增房间级能力注册表（如 `ROOM_CAPABILITIES: list[CapabilitySpec]`），至少把现有 `outdoors` 迁移进去；`_ROOM_KNOWN_FIELDS` 改为从该注册表 + 房间固有字段（`name`/`aliases`/`short`/`long`/`exits`）聚合。
- [x] 新增 NPC 级能力注册表（如 `NPC_CAPABILITIES: list[CapabilitySpec]`），至少把现有 `inquiry`/`behaviors`/`tick_interval` 迁移进去；`_NPC_KNOWN_FIELDS` 改为从该注册表 + NPC 固有字段聚合。
- [x] `save.py` 的房间/NPC 组件 codec（`Description`/`Inquiry`/`Behaviors`/`AIController` 等已迁移进注册表的部分）改走注册表的 `to_dict`/`from_dict`，不再在 `save.py` 里单独硬编码。
- [x] 注册表的 `CapabilitySpec` 形状与物品用的保持一致（`component_type`/`known_fields`/`from_yaml`/`to_dict`/`from_dict`），使块 B~G 后续票能直接照抄物品能力的写法追加新能力，不需要发明新形状。
- [x] 明确记录（代码注释或本票 Comments）：`_PLAYER_KNOWN_FIELDS`（`{"name","start_room"}`）与 `_TOP_LEVEL_KNOWN_SECTIONS`（`{"rooms","items","npcs","player"}`）**不**在本票扫平范围内——player 段字段少（后续如需给玩家挂 `Currency`/`Faction` 初始值，直接加进 `_PLAYER_KNOWN_FIELDS` 判断，不为个别字段建注册表，避免过度设计）；新顶层段（`factions:`/`skills:`）是全局注册表模式，不是"实体能力"模式，留给 02/03 号票各自决定。
- [x] `engine/tests/test_scene_loader.py`、`engine/tests/test_save.py` 现有测试全绿，不回归；`just verify-npc`/`just verify-nature`/`just verify-items` 一键矩阵全绿。
- [x] 新增至少一条测试证明"注册表驱动的未知字段透传"仍然成立（给房间/NPC 塞一个注册表之外的字段，断言它落进 `entity_extension_data` 而不是被判定为已知字段）。
