# 19 - 转移统一原语 transfer（C2）

**What to build:** 底层 `transfer(world, item, src, dst) -> TransferResult`，take/drop（及后续 put/give）收敛到它；携带成功/失败原因（`no_take`/`no_drop`/`over_capacity` 等由后续票填实）。reject 校验钩子复用已有 `on_take`/`on_drop` 事件点。转移逻辑只写一份。

**Blocked by:** 18 - 能力组件形状就绪后再收敛转移路径更稳（也可与标志位票协作；最低依赖现有 Container）。

**Status:** resolved

- [x] 存在 `transfer` 原语，返回成功/失败 + 原因
- [x] `_cmd_take` / `_cmd_drop` 走 `transfer`，外部可观察行为与现有一致
- [x] `on_take` / `on_drop` 否决仍生效
- [x] 契约测试锁定 `TransferResult` 形状
- [x] 现有测试全绿（不回归）
