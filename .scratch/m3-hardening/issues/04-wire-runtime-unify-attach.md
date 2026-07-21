# 04 — `wire_runtime` 统一 restore/load 接线

**What to build:** "一份场景加载完成后需要挂哪些运行时子系统"（nature/AI/渡口/交战/门禁）只在一处定义，无论是 fresh load（`load_scene`）还是崩溃恢复（`__main__._reattach_runtime`）都调用同一个函数，新增一个 `attach_xxx` 子系统时只改一处，不会出现"restore 路径忘了挂新子系统"这类静默漂移。统一后的接线函数不依赖"fresh load 时 nature 配置还留在 `world.extension_data` 里、restore 后已经空了"这条隐藏的时序假设，而是每次都显式从 `scene_path` 重新读取 nature 配置。这次统一不引入依赖注入容器或改变 `World` 挂件的现有形状，只要求单一入口，改动范围收敛在"接线顺序"这一件事上。

对应 spec：[.scratch/m3-hardening/spec.md](../spec.md) P0-5。

**Blocked by:** None — 可立即开始（与 08 号票 `messaging.py` 抽取互相独立，可并行）。

**Status:** resolved

- [x] 新增 `wire_runtime(world: World, scene_path: Path) -> None`（放在 `world.py` 或新建一个不产生循环 import 的小模块）：固定顺序调用 `attach_nature(world, config_from_yaml=read_nature_config(scene_path))` → `attach_ai_system(world)` → `attach_ferries(world)` → `attach_combat_system(world)`（内部已调用 `attach_power_model`）→ `attach_entry_guards(world)`。两条调用路径统一显式传入 `scene_path` 重新读取 nature 配置。
- [x] `scene_loader.py` 的 `load_scene`（现有 5 行 `attach_*` 序列）改为调用 `wire_runtime(world, scene_path)`。
- [x] `__main__.py` 的 `_reattach_runtime` 删除，两处调用点（`_load_or_restore_default`、`_load_or_restore_pack`）改为直接调用 `wire_runtime(world, world.scene_path or DEFAULT_SCENE_PATH)`。
- [x] 复核 `commands.py` 内约 1194–1200 行处对 `attach_combat_system` 的延迟 import + 条件调用（命令执行时的防御性重挂）：判断是否属于同一类"接线分散"问题；若是，改为路由到 `wire_runtime`；若不是（例如"命令执行期间发现 `world.combat is None` 的防御性兜底"），保留但补充明确注释说明为何不能统一——不能留成新的第三份隐藏清单，必须做出可见决策。
- [x] `pack.py` 的 `load_pack` 不需要改动（已经通过委托 `load_scene` 间接获得统一后的 `wire_runtime`），确认这一点没有回归。
- [x] `just test` 全绿，尤其覆盖 restore 路径的测试（`test_save.py`、`test_load_pack.py`）与覆盖各 `attach_*` 子系统效果的现有测试。

## Comments
