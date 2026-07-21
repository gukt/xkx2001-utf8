# 03 — CLI：`--pack <目录>` 指向加载 + `--validate` 校验模式

**What to build:** 落地 spec Implementation Decisions「C1」：给 `mud_engine/__main__.py` 加 `argparse`（当前 `main()` 不接受任何参数）。把"解析参数 → 选择分支 → 返回退出码"这部分拆成一个不直接调 `sys.exit` 的纯函数（如 `_main(argv: list[str]) -> int`），`main()` 本身只是 `sys.exit(_main(sys.argv[1:]))` 这一行胶水（对齐 `cli.py`/`run_repl` 已确立的"CLI 逻辑不用真实 subprocess/stdin 测试"原则）。新增两个参数：`--pack PATH`（可选；不传时走现有默认行为——`build_world()` 加载 `DEFAULT_SCENE_PATH`、存档目录 `DEFAULT_SAVE_DIR`，**零改动**现有分支的代码路径与可观察行为）、`--validate`（bool flag；单独出现不搭配 `--pack` 时报参数错误、非零退出，不静默忽略也不报别的含糊错误）。`--pack` 分支：存档目录改为 `<pack_dir>/save/`；启动时先 `has_save(该目录)` 判断走 restore（用 02 号票的 `restore_world` + 现有 `attach_nature`/`attach_ai_system`/`attach_ferries`/`attach_combat_system`/`attach_entry_guards` 重挂逻辑 + 新增 `reattach_pack_manifest(world)` 调用）还是 `load_pack(pack_dir)` 全新加载，其余（`TickLoop`/`run_repl` 接入）与现有默认分支一致；错误处理捕获 `PackManifestError`/`SceneLoadError` 打印到 stderr、非零退出（消息前缀区分"包清单"还是"场景内容"出的错，供人一眼看出问题在哪层）。`--validate` 分支：只调 `load_pack(pack_dir)`，成功打印一行摘要到 stdout（含 `id`/`version`/房间数等）并返回 0；失败捕获同上两类错误打印到 stderr 返回 1；**不**触碰 `<pack_dir>/save/`（不判断 `has_save`、不走 restore、不管当前是否已有存档），不进入 `run_repl`。

**Blocked by:** `02`（依赖 `load_pack`/`reattach_pack_manifest`/`World.pack_manifest`）。

**Status:** done

- [x] `_main(argv) -> int` 函数落地；`main()` 精简为 `sys.exit(_main(sys.argv[1:]))`。
- [x] 无参数（`_main([])`）：行为与本票开工前的 `main()` 完全一致（回归确认，可复用/对照现有测试断言）——存档目录、加载路径、错误处理分支均不变。
- [x] `_main(["--pack", "<合法内容包目录>"])`：进入 `run_repl` 前完成 `load_pack`（或 restore 路径），存档目录使用 `<pack_dir>/save/`；用一种可观察的方式验证（如替换 `run_repl` 为可注入的 stub / 检查传给 `run_repl` 的 `world`/`tick_loop` 参数），不要求真实读 stdin。
- [x] `_main(["--pack", "<合法内容包目录>"])` 第二次调用（模拟"已经玩过一次、有存档了"）：走 restore 路径，`world.pack_manifest` 通过 `reattach_pack_manifest` 正确填充（断言与首次加载时的值一致）。
- [x] `_main(["--pack", "<不存在的目录>"])`：返回非零，stderr 含清晰提示（不是裸 traceback）。
- [x] `_main(["--pack", "<目录存在但缺 manifest.yaml>"])`：返回非零，stderr 明确提示"包清单"相关问题（区别于场景内容问题的文案）。
- [x] `_main(["--pack", "<manifest 合法但 scene.yaml 结构性错误>"])`：返回非零，stderr 明确提示"场景内容"相关问题（沿用现有 `SceneLoadError` 消息风格）。
- [x] `_main(["--pack", "<合法目录>", "--validate"])`：返回 0，stdout 含 `id`/`version` 摘要；**不**在该目录下创建 `save/` 子目录（断言文件系统层面没有副作用）；即便该目录下已存在 `save/`（模拟之前真的玩过），校验结果不受里面存档内容影响（每次都是对"包当前内容"的确定性校验）。
- [x] `_main(["--pack", "<坏包目录>", "--validate"])`：返回 1，stderr 与非 `--validate` 模式下报同一条错误消息（同一份校验代码路径，不是两套）。
- [x] `_main(["--validate"])`（不带 `--pack`）：返回非零，提示明确是参数用法错误（如"`--validate` 须搭配 `--pack`"），不是尝试对默认场景做什么奇怪的事。
- [x] 现有测试全绿不回归；新增测试文件命名与位置对齐 `engine/tests/` 现有关于 `__main__`/CLI 相关测试（若无先例，参照 `test_cli.py`/`test_m1_smoke.py` 一类既有文件的写法风格）。

## Comments

- 2026-07-21 `/implement`：`_main(argv) -> int` + `argparse`；`--pack`/`--validate`；错误前缀「包清单」/「场景内容」；测试 `engine/tests/test_main_cli.py`（stub `run_repl`）。默认路径 `SceneLoadError` 文案仍为「场景数据加载失败」。
- 2026-07-21 `/code-review` fix（fixed point `m3-wave2-start`）：缺目录不再套「包清单」前缀；无参路径断言 `DEFAULT_SAVE_DIR`；测试拆复合断言 + `When*` 嵌套；抽出 `_enter_repl`、去掉 Middle Man `_format_scene_error`。
