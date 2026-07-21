# 01 — 内容包 manifest：`PackManifest` 数据形状 + `load_manifest` 纯函数 + `PackManifestError`

**What to build:** 落地 spec Implementation Decisions「A2/A3」：新模块 `mud_engine.pack`，新增 `PackManifest` 数据类（`id: str` / `version: str` / `creator: str | None = None` / `title: str | None = None` / `extra: dict = field(default_factory=dict)`）；`load_manifest(pack_dir: Path) -> PackManifest` 读 `pack_dir/manifest.yaml`，校验顶层是映射、`id`/`version` 必需且为字符串，`creator`/`title` 若出现须为字符串或 `None`，其余未知字段原样收进 `extra`（透传手法对齐 `scene_loader._capture_top_level_unknown_sections` 已验证的模式，但这里不进 `world.extension_data`——manifest 的透传字段挂在 `PackManifest.extra` 本身上，因为此刻还没有 `World`）。任何校验失败（文件不存在、YAML 语法错误、顶层非映射、`id`/`version` 缺失或类型错误）统一抛新增的 `mud_engine.errors.PackManifestError`（与既有 `SceneLoadError` 同一模块，消息风格对齐：带路径 + 具体字段名）。本票是纯数据/纯函数层，**不涉及** `World`/`load_scene`/CLI——不依赖 02/03 号票，可独立单测。

**Blocked by:** None — 全新模块 + 全新错误类型，不改动任何现有文件的既有行为，可立即开工。

**Status:** done

- [x] `PackManifest` 数据类落地，字段与默认值如上；`extra` 默认是空字典（不同实例间不共享同一个可变默认值——用 `field(default_factory=dict)`，不是裸 `extra: dict = {}`）。
- [x] `PackManifestError` 新增于 `mud_engine/errors.py`（与 `SceneLoadError` 平级，`errors.py` 模块 docstring 顺带更新一句提到两个错误类型都在这里），并加入该模块的 `__all__`。
- [x] `load_manifest(pack_dir)` 覆盖以下场景，均抛 `PackManifestError` 且消息含 `pack_dir` 路径与具体出错原因：`manifest.yaml` 不存在；YAML 语法错误；顶层解析结果不是映射（如整份文件只是一个列表/标量）；缺 `id`；缺 `version`；`id`/`version` 存在但类型不是字符串（如写成整数——按"类型不对"报错，不做隐式 `str()` 转换，与 `scene_loader` 对必需字符串字段的既有严格程度一致）。
- [x] `load_manifest(pack_dir)` 成功路径：合法 manifest（含 `creator`/`title` 都给、都不给、只给一个的三种组合）都能正确解析；额外塞一个既知字段集之外的字段（如 `tags: [scifi]`），断言它出现在返回对象的 `extra` 里且值原样保留，同时不影响 `id`/`version`/`creator`/`title` 的正常解析。
- [x] `creator`/`title` 若出现但类型不是字符串（如 `creator: 123`），按与 `id`/`version` 一致的严格程度报 `PackManifestError`，不是静默接受非字符串再在别处出问题。
- [x] `mud_engine.pack` 模块 docstring 说明本模块与 `scene_loader` 的关系（manifest 是包身份，`scene_loader` 是包内容，两者是独立的校验阶段——对齐 spec A1 决策的理由），供后续 02 号票的读者一眼看懂分工。
- [x] 现有测试全绿不回归（本票不改动任何既有模块，理论上不可能回归，但仍需跑一遍确认）。

## Comments

- 2026-07-21 `/code-review`（fixed point `m3-wave0-start`）：Spec 轴无缺口。Standards 轴 fix——helper 只传 `manifest_path`（去掉 `pack_dir`+`manifest_path` Data Clump）、抽出 `_as_string`、`extra: dict[str, object]`。未跨模块抽 YAML 读入（与 `scene_loader._read_yaml` 重复属判断项，Wave 0 不侵）；未拒空串 `id`/`version`（票面只要求「必需且为字符串」）。
