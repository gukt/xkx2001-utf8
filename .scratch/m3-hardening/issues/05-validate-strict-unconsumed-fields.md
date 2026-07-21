# 05 — `--validate` 未消费字段 warn / `--strict`

**What to build:** 跑 `mud_engine --pack <dir> --validate` 时，如果场景 YAML 里有字段被引擎透传进 `extension_data` 而没有被任何能力消费，能看到一条明确的警告列出具体是哪些字段、在哪个实体上，以便及时发现拼写错误或过时字段，而不是加载"成功"却发现游戏里毫无效果。默认行为是 warn（不阻断校验通过），但可以加 `--strict` 让未消费字段变成校验失败，日常创作不被打断，正式发布前可以选择更严格的把关。这条检查复用已经存在的已知字段集机制，不新建一套平行的字段登记表。

对应 spec：[.scratch/m3-hardening/spec.md](../spec.md) P0-7。这张票是 06 号票（创作者契约 v0）的前置依赖，因为该文档需要准确引用这里确定的 `--strict` 行为。

**Blocked by:** None — 可立即开始。

**Status:** resolved

- [x] `__main__.py` 新增 `--strict` 参数（须搭配 `--validate`，否则报参数错误，与现有 `--validate` 须搭配 `--pack` 的校验方式一致）。
- [x] `_validate_pack` 扩展：加载成功后遍历 `world.extension_data`（顶层未知段）与 `world.all_entities()` 上非空的 `entity_extension_data(entity)`（实体级未消费字段），汇总成一份"字段 → 出现位置"的报告。
- [x] 默认（无 `--strict`）打印为警告（stdout 或 stderr），退出码仍为 0。
- [x] 有 `--strict` 且报告非空时，退出码改为非 0（复用现有 `_format_pack_or_scene_error` 附近的错误路径风格，给出汇总而不是逐字段刷屏）。
- [x] 不新建平行的字段登记表：已知字段集合直接复用 `scene_loader.py` 现有的 `_ROOM_KNOWN_FIELDS` 等常量与 `world.extension_data`/`entity_extension_data()` 现有透传机制。
- [x] 测试（命令层 seam，模式与 `test_main_cli.py` 一致）：`--validate`（无 `--strict`）对含未消费字段的包 warn + 退出码 0；`--validate --strict` 对同一个包退出码非 0；对不含未消费字段的包两种模式都退出码 0、无警告。
- [x] `just test` 全绿。

## Comments
