# 02 — `load_pack` 组合入口 + `World.pack_manifest` + restore 后重挂

**What to build:** 落地 spec Implementation Decisions「B1/B2」：在 `mud_engine.pack`（01 号票已建的模块）新增 `load_pack(pack_dir: Path) -> tuple[World, EntityId]`——调 `load_manifest(pack_dir)`，再委托现有 `scene_loader.load_scene(pack_dir / "scene.yaml")`（**不修改 `load_scene` 一行代码**，纯组合），把 `load_manifest` 返回的 `PackManifest` 赋给返回 `world.pack_manifest`。`World`（`world.py`）新增字段 `pack_manifest: PackManifest | None = None`，注释与 `world.nature`/`world.ai`/`world.spawners` 同风格（运行时态，不进存档，`save.py` 本票**不改动一行**）。再新增 `reattach_pack_manifest(world: World) -> None`（同放 `mud_engine.pack`）：若 `world.scene_path` 非空且其 `.parent / "manifest.yaml"` 存在，重新 `load_manifest` 一遍填回 `world.pack_manifest`；文件不存在（默认场景走这条路径的情形）静默保持 `None`，不报错——这条函数设计上必须是幂等、可在任意时刻安全重复调用（对齐 `attach_nature`/`attach_ai_system` 等既有 `attach_xxx` 函数的幂等惯例，即便本函数命名是 `reattach_` 前缀而非 `attach_`，语义与调用时机一致）。本票**不改动 `__main__.py`**——CLI 何时调用 `load_pack`/`reattach_pack_manifest` 是 03 号票的范围，本票只交付这两个函数本身 + `World` 字段，用直接函数调用的方式单测。

**Blocked by:** `01`（依赖 `load_manifest`/`PackManifest`/`PackManifestError`）。

**Status:** done

- [x] `World.pack_manifest: PackManifest | None = None` 字段落地于 `world.py`；`World.__init__` 里的注释位置与既有运行时态字段（`nature`/`ai`/`spawners`/`ferries`）风格一致，说明"不进存档"与理由。
- [x] `load_pack(pack_dir)` 成功路径：给一个临时构造的最小合法内容包目录（`manifest.yaml` + `scene.yaml`，`scene.yaml` 内容可以是现有测试夹具里最简单的合法场景），断言返回的 `world.pack_manifest` 字段值与直接调 `load_manifest(pack_dir)` 的结果一致，且 `world`/`player_id` 与直接调 `load_scene(pack_dir / "scene.yaml")` 产出的世界状态一致（房间/NPC/物品都在，`world.scene_path` 指向 `pack_dir / "scene.yaml"` 的绝对路径）。
- [x] `load_pack(pack_dir)` 失败路径——manifest 坏：抛 `PackManifestError`（`load_scene` 完全不会被调用，用 mock/spy 或"断言错误消息明确提到 manifest 而不是场景内容"两种方式之一验证顺序：先校验 manifest 再加载场景）。
- [x] `load_pack(pack_dir)` 失败路径——manifest 合法但 `scene.yaml` 结构性错误（如出口指向不存在的房间）：抛出的仍是现有 `SceneLoadError`（不是被本票包装成别的类型、不是被吞掉），证明组合不改变场景层已有的错误契约。
- [x] `reattach_pack_manifest(world)`：给一个 `world.scene_path` 指向"某目录下的 scene.yaml，该目录也有合法 manifest.yaml"的 `World`（可以是刚 `load_pack` 出来的，也可以手工构造 `scene_path` 后调用），断言调用后 `world.pack_manifest` 被正确填充/刷新；再给一个 `world.scene_path` 指向"该目录没有 manifest.yaml"（如默认官方场景路径）的 `World`，断言调用后 `world.pack_manifest` 仍是 `None`、且不抛任何异常。
- [x] `reattach_pack_manifest(world)` 在 `world.scene_path is None` 时静默 no-op（不抛异常）——对应"存档里从来没记过 scene_path"这种边界情况的防御。
- [x] 端到端复合场景（为 03 号票铺路，本票用直接函数调用而非 CLI 验证）：`load_pack` 建 world → 用现有 `save.py` 的 `save_world`/`restore_world` 走一次存档/恢复 → 对恢复后的新 `World` 手动调 `reattach_pack_manifest` → 断言恢复后的 `pack_manifest` 与恢复前一致。这条测试证明"不扩展 `save.py`"这条决策确实成立，不是纸上假设。
- [x] `save.py` 未被本票改动（跑一下 `git diff --stat` 或等价确认，防止实现时不小心手滑加了字段序列化）。
- [x] 现有测试全绿不回归。

## Comments

- 2026-07-21 `/code-review`（fixed point `m3-wave1-start`）：Spec 轴无缺口（`save.py`/`__main__.py`/`load_scene` 均未改）。Standards 轴 fix——拆开 `load_pack` 成功路径与 save/restore/reattach 的复合断言（对齐 `engine/README.md` 测试约定「一方法一焦点」）。
