# 13 - Nature 时辰循环引擎（B1）

**What to build:** 数据驱动的昼夜时辰循环：YAML 声明相位序列（phase 名 / length 游戏分钟 / time_msg / desc_msg），挂 `on_tick` 推进（比例可配，默认 60:1）。`NatureState` 纯内存、不进存档；重启时按可注入时钟对齐当前相位。题材无关默认四相（dawn/day/dusk/night），题材包可自定义。

这是块 B 的地基票：后续谓词、文案、广播、天气都挂在它推进的相位上。

**Blocked by:** 07 - 复用 `on_tick` 分发驱动相位推进。

**Status:** resolved

- [x] 存在 `NatureState`（或等价 world 级状态），持有当前相位与推进进度，不进存档
- [x] day_phase 配置数据驱动（YAML 或等价），含 phase 名 / length / time_msg / desc_msg
- [x] 挂 `on_tick` 按可配比例推进相位（默认 60:1）
- [x] 重启/构建时按可注入时钟对齐当前相位（测试不依赖墙钟）
- [x] 默认四相 dawn/day/dusk/night 可用；题材包可换序列
- [x] 调 `tick_loop.advance()` 快进到目标相位，断言相位切换
- [x] 现有测试全绿（不回归）
