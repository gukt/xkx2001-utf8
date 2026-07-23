---
Status: ready-for-agent
---

# 11 — C13 多文件路径引用 templates（`includes`）

**What to build:** 场景 YAML 顶层新增可选段 `includes: [<relative_path>, ...]`（相对当前场景文件所在目录，仅贡献 `items`/`npcs` 模板，不贡献 `rooms`/`player`/其它段）；加载期在解析当前文件 `items`/`npcs`/`rooms` 之前先读取并合并被 include 文件里的 `items`/`npcs` 模板定义进当前场景的模板命名空间；合并后模板 id 必须全局唯一，跨文件重复 id 视为加载错误。路径解析限定在场景文件所在目录及其子目录内（不允许穿出包目录/仓库范围的裸文件系统穿越）。官方轨、内容包轨（`manifest.yaml`）两条加载路径分别是否允许 `includes`、以及 `--pack --validate`/`--strict` 对 include 路径的校验规则（文件缺失/越权路径报错）本票明确并各自补测试。

对应 spec：`.scratch/polishing/spec.md` §C13（User Stories 38–41；Implementation Decisions「C13」）；LPC 出处 [session-qa-provenance-2026-07-23.md](../../polishing-candidate-review/session-qa-provenance-2026-07-23.md) Q12。

**Blocked by:** None — 可立即开始。

- [ ] `scene_loader.py`：新增顶层段 `includes: [<path>, ...]` 解析；在解析 `items`/`npcs`/`rooms` 之前先读取并合并被 include 文件的 `items`/`npcs` 模板进当前场景模板命名空间。
- [ ] 路径解析基准目录为当前场景文件所在目录；越界路径（穿出该目录及其子目录）加载失败；文件缺失加载失败并给出定位到具体 include 路径的错误信息。
- [ ] 合并后模板 id（`items.*`/`npcs.*` 键）全局唯一校验：跨文件重复 id 视为加载错误（对齐 ADR-0010「同文件扁平模板键」唯一性精神，放宽为「同一次合并后的命名空间」）。
- [ ] 嵌套 include（A include B include C）是否支持——本票钉死方案：**不支持嵌套**（仅当前场景文件顶层可 `includes`，被 include 文件本身若再写 `includes` 视为加载错误），保持解析图为一层，降低越权/循环引用复杂度。
- [ ] `pack.py`：内容包轨 `manifest.yaml` 场景是否允许 `includes`——本票钉死方案：**允许**，路径解析基准目录仍为该场景文件所在目录，且不允许穿出包目录范围（与官方轨「不允许穿出仓库范围」的精神一致，边界收紧到包目录）。
- [ ] `--validate --strict` 下 include 文件本身的未消费字段同样报错（复用同一套已知字段校验，不新建平行校验路径）。
- [ ] 契约新增字段：顶层 `includes`——`docs/creator-contract-v0.md` 同步补写；官方轨/内容包轨可用性说明写入 `docs/scene-authoring-guide.md`。
- [ ] `docs/gap-ledger.md`：「多文件 / 大世界树场景」行更新为「已支持（单层 includes，仅 items/npcs）」并指向新契约字段。
- [ ] 新测试文件（`test_scene_includes.py`）：合法跨文件引用加载成功、重复 id 加载失败、越界路径加载失败、文件缺失加载失败、嵌套 include 加载失败。
- [ ] `test_load_pack.py` 扩展：内容包轨 `includes` 合法用例 + `--pack --validate --strict` 校验。
- [ ] `just test` 全绿。
