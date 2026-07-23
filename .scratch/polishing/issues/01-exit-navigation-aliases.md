---
Status: ready-for-agent
---

# 01 — A1+A2 出口导航别名（内置十向同义词 + 分层别名回退）

**What to build:** 出口方向解析升级为「层合并候选」：① 出口自身 `aliases` → ② 目标房间 `name` 与 `aliases` → ③ 该方向键（`north`/`south`/`east`/`west`/`northeast`/`northwest`/`southeast`/`southwest`/`up`/`down`）内置默认同义词集合（英文全写、英文简写、中文，斜向按英文释义对应，如 `southeast`↔东南）。创作者不必再在每条出口手写标准方位 `aliases`；地名（如「武庙」）只需写在目标房 `name`/`aliases` 一次，邻接出口即可被 `go 武庙` 命中。合法输入形式：`go` + 英文全写/简写/中文方位、裸英文全写、裸英文简写；**不合法**：裸中文方位、裸中文地名（均须带 `go`）。多候选同名命中走既有 `Ambiguous`（列候选）。`look` 出口列表改中英并列展示（如 `东(east)`），门状态后缀（`（关）`/`（锁）`）不变。

对应 spec：`.scratch/polishing/spec.md` §A1+A2（User Stories 1–7；Implementation Decisions「A1+A2」）；权威规格摘要另见 [CONTEXT.md](../../../CONTEXT.md)「出口导航别名」词条。

**Blocked by:** None — 可立即开始。

- [ ] `parsing.py`：`DIRECTION_SHORTCUTS`（或等价常量）扩容为十向键各自的内置默认同义词集合（英文全写/简写/中文），供解析器与 `look` 展示共用同一份数据源。
- [ ] 出口 token 解析函数按「① 出口 `aliases` → ② 目标房 `name`/`aliases` → ③ 方向键内置同义词」三层顺序合并候选；候选去重（内置同义词与自定义别名重名时不重复展示/不重复计数——展示去重策略拆票时钉：内置项与自定义重名时只展示一次）。
- [ ] 合法性校验：裸中文方位、裸中文地名解析为「不合法，须带 go」，不静默失败为「无此出口」之外的更友好提示信息（信息内容拆票时可自行措辞，但必须区分「不认识」与「须带 go」两种拒绝原因）。
- [ ] `commands.py::_cmd_go` 改用同一套候选解析（不得与 `look` 展示各写一套判定逻辑）。
- [ ] `commands.py` `look`：出口列表改「中(english)」并列展示；已有门状态后缀保留在英文键后。
- [ ] 多出口同名命中 → 复用既有 `Ambiguous` 提示路径（不新增消歧机制）。
- [ ] `test_parsing.py`：方向解析单元测试覆盖十向 × {英文全写, 英文简写, 中文, 斜向} 全矩阵 + 裸中文拒绝 + `go` 前缀放行。
- [ ] `test_navigation.py`（或按现有测试文件归类）：`execute_line` 黑盒覆盖 `go east`/`east`/`e`/`go 东`/`go 武庙`（地名命中目标房）/`Ambiguous` 场景。
- [ ] `just test` 全绿。
