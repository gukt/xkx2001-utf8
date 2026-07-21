# 05 — 端到端收口：剧本测试 + `verify-m3` 转录 + 里程碑文档更新

**What to build:** 把 03 号票交付的 CLI 机制与 04 号票交付的示例包串成一条锁死的回归测试 + 一份给人看的转录，并完成 M3 里程碑收口文档更新。新增 `engine/tests/test_m3_pack_loop.py`：(a) 用 `tmp_path` 复制一份 `example-pack/` 内容（结构性证明"任意磁盘位置都能被 `--pack`/`load_pack` 指向加载"，不依赖它恰好在仓库某个固定路径下）跑一遍 04 号票记录的完整命令序列，断言每一步返回消息的关键信息；(b) 对该临时包故意破坏 `manifest.yaml`（删 `id`）与 `scene.yaml`（出口指向不存在房间）两种坏包场景，跑 `_main([..., "--validate"])`，断言分别报 `PackManifestError`/`SceneLoadError` 风格消息、非零退出；(c) 存档/退出/重启恢复到同一进度（复用 02 号票已验证的 `reattach_pack_manifest` 路径，这里走一遍真实 CLI 层）。新增 `engine/scripts/verify_m3_pack_loop.py`（转录风格对齐 `engine/scripts/verify_m2_*.py`：不读写真实存档、每次 `load_pack` 加载 fresh 示例包，跑一遍 04 号票的命令序列并打印 PASS/FAIL），`justfile` 加 `verify-m3` recipe。收尾更新：`PROGRESS.md`（Done 滑动窗口追加"M3 UGC 闭环打通一次"条目，超出 5 条的旧条目移进 `.scratch/progress-archive.md`；当前状态速览一行更新为"M3 完成"；Next Up 换成 M4 相关待办——对照 [07 号票](../mvp-scope/issues/07-governance-cost-tracking.md) 的 M4 定义"商业化支撑点的数据模型落地，不要求真实计费"）；确认 [ADR-0005](../../docs/adr/0005-m3-ugc-loop-creation-surface.md) 的"M3 最小切片"描述与本次实际落地一致（若实现中有偏离，在 ADR 里补一条修订记录而不是让文档与代码脱节）。

**Blocked by:** `03`, `04`（需要 CLI 层与示例包都已交付才能串起端到端测试）。

**Status:** done

- [x] `test_m3_pack_loop.py`：`tmp_path` 复制 `example-pack/` 场景，用 `_main`（或直接 `load_pack` + `execute_line` 组合，取决于 03 号票实际交付的可测试性）跑完整条 04 号票记录的命令序列，全程断言关键返回消息（不断言内部实现细节）。
- [x] `test_m3_pack_loop.py`：坏 manifest（缺 `id`）与坏 `scene.yaml`（出口引用不存在房间）两个独立测试用例，均通过 `--validate` 路径验证报错类型与文案区分、退出码非零、不产生 `save/` 目录副作用。
- [x] `test_m3_pack_loop.py`：存档/重启恢复场景——走一遍"`--pack` 加载 → 执行几条命令改变状态（如移动/拾取）→ 触发存档（quit 或达到 tick 周期）→ 用同一 `--pack` 路径重新启动 → 断言恢复后玩家位置/物品栏与退出前一致，且 `world.pack_manifest` 正确重挂"。
- [x] `engine/scripts/verify_m3_pack_loop.py` 落地，风格/结构对齐现有 `verify_m2_*.py`（复用 `verify_harness.py` 里已有的断言/转录 helper，不重新发明一套）；`just verify-m3` recipe 加入 `justfile`。
- [x] `just verify-m3` 与 `just test` 全绿。
- [x] `PROGRESS.md` 更新：Done 追加 M3 收口条目（含日期、指向本 spec/本票的链接）；滑动窗口保持 5 条（超出的移进 `.scratch/progress-archive.md`，措辞保留当时表述不回改，对齐现有归档惯例）；当前状态速览行更新；Next Up 换成 M4 相关待办。
- [x] `ADR-0005` 若需要因实现细节偏离原描述而修订，补一条"范围修订记录"风格的说明（对齐 [M2 spec](../m2-mvp-scene-playable/spec.md) 末尾"范围修订记录"一节的既有写法），不需要改判 ADR 的 `Status`。
- [x] 全量测试套件（`just test`）与 lint（`just lint`）均绿。

## Comments

- 2026-07-21 `/implement`：落地如上。ADR-0005 与本次实现一致（manifest + 声明式包外内容 + `--validate` 校验契约）；补「落地核对」段，不改判 Status。
- 2026-07-21 `/code-review` fix：拆复合断言；`test_full_loop_asserts_every_step_message` 逐步断言；补 `test_verify_m3_matrix.py`；ruff 清仓库既有 I001/F401，使 `just lint` 全绿。
