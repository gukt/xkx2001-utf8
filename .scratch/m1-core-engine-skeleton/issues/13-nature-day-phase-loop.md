# 13 - Nature 时辰循环引擎（B1）

**What to build:** 数据驱动的昼夜时辰循环：YAML 声明相位序列（phase 名 / length 游戏分钟 / time_msg / desc_msg），挂 `on_tick` 推进（比例可配，默认 60:1）。`NatureState` 纯内存、不进存档；重启时按可注入时钟对齐当前相位。题材无关默认四相（dawn/day/dusk/night），题材包可自定义。

这是块 B 的地基票：后续谓词、文案、广播、天气都挂在它推进的相位上。

**Blocked by:** 07 - 复用 `on_tick` 分发驱动相位推进。

**Status:** resolved（2026-07-20 re-pass：验收复核 + restore 保留题材包相位配置）

- [x] 存在 `NatureState`（或等价 world 级状态），持有当前相位与推进进度，不进存档
- [x] day_phase 配置数据驱动（YAML 或等价），含 phase 名 / length / time_msg / desc_msg
- [x] 挂 `on_tick` 按可配比例推进相位（默认 60:1）
- [x] 重启/构建时按可注入时钟对齐当前相位（测试不依赖墙钟）
- [x] 默认四相 dawn/day/dusk/night 可用；题材包可换序列
- [x] 调 `tick_loop.advance()` 快进到目标相位，断言相位切换
- [x] 现有测试全绿（不回归）

## Comments

### 2026-07-20 re-pass

- 复核既有 `TestDayPhaseLoop`（6）+ 补 `test_restore_reattach_keeps_custom_phases_from_scene_file`：restore 后从场景 YAML 重读 `nature:`，避免题材包相位静默降级为 `DEFAULT_PHASES`。
- 新增 `load_nature_config_from_scene`；`__main__` restore 路径接入。
- `/code-review` 双轴：0 硬伤。全量 365 测试绿。
