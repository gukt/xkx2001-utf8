---
Status: resolved
---

# 02 — 语义色 token（校验 + CLI 渲染）

**What to build:** 权威内容文本可用 `<c:name>…</c>` 着色（七色：`red`/`green`/`yellow`/`blue`/`magenta`/`cyan`/`white`）。加载与 `--validate` 拒绝原始 ANSI、LPC 色宏、未知色名、未闭合 token；不支持嵌套。核心层权威回文保留 token；官方 CLI 在 TTY 或 `--color` 时映为亮色 ANSI，管道与测试默认剥为纯文本。

对应 spec：US6–US12；ADR-0011；Testing S1/S2 + CLI 适配层。

**Blocked by:** None — 可立即开始（可与 `01` 并行；风景文案可后加色）。

- [x] 解析与校验覆盖：合法七色；拒 ANSI 转义、`HIG`/`HIR`/`NOR` 等 LPC 宏名、未知色名、未闭合 `<c:…>`；拒嵌套。
- [x] 校验挂在场景加载与 `--validate`/`--strict` 路径；坏 markup 早失败。
- [x] 命令回文等权威消息保留语义色 token（核心不提前染成 ANSI）。
- [x] CLI：TTY 默认或 `--color` → 七色亮色 ANSI；非 TTY / 管道默认剥 token 出纯文本；自动化测试走剥除路径。
- [x] 本波无背景色、闪烁/粗体 token、独立 `NOR` token（`</c>` 复原）。
- [x] 测试：非法色/未闭合/ANSI/LPC 宏 → 加载或 validate 失败；CLI 着色 vs 剥除输入输出（适配层）；权威回文含 token。
- [x] `just test` 全绿。

## Comments

实现摘要（供 07 回写契约）：

- **语法**：`<c:name>…</c>`；色名仅 `red|green|yellow|blue|magenta|cyan|white`；无嵌套；`</c>` 复原。
- **模块**：`mud_engine.semantic_color` — `validate_markup` / `strip_tokens` / `render_ansi`。
- **校验挂点**：`scene_loader._validated_description_texts`（房间/物品 `_attach_identity_and_description` + NPC `SpawnerBlueprint` 登记）；`capabilities._parse_room_details`（details 文案）。`--validate` 经 `load_pack`→`load_scene` 同路径。
- **CLI**：`run_repl(..., color=None|True|False)`；`python -m mud_engine --color` / `--no-color`；默认 `output_stream.isatty()`。
- **官方**：`yangzhou_guangchang.details.旗杆` 含 `<c:yellow>旗角</c>`。
