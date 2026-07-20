# 32 - transfer↔commands 循环 import 拆模块（#8）

**Smell:** `transfer.py:149` 惰性 import `commands.ON_DROP/ON_GET/TransferContext`，`transfer.py:308` 惰性 import `commands.Deny`（注释自承避免 `transfer ↔ commands` 循环）。transfer 域概念（事件常量 / 上下文 / 结果类型）住在 commands 模块，应拆到第三模块。

**Fix:** 把 `ON_GET`/`ON_DROP`/`TransferContext`/`Deny` 移出 commands（到 `transfer.py` 或 `events.py` 或新 `transfer_events` 模块），commands 改从该处 import，transfer 不再 import commands。关联 #33（`_run_transfer_veto` 复制），一起拆可同时解决。

**From:** BCD re-pass code-review 物品批 Standards #8（commit 79b831ef）。

**Status:** resolved

- [x] transfer 不再 import commands，惰性 import 注释删除
- [x] just gate 全绿

**Resolved:** 2026-07-20，commit `b67a9f06`。
ON_GET/ON_DROP/TransferContext 移至 `transfer.py`（转移域概念归转移模块），Deny 与共享的 `run_vetoable` 移至 `events.py`。transfer.py 删除对 commands 的惰性 import 及循环依赖注释；commands 重新导出这些符号保持命令钩子 API 不变（兼容 test_domain_events / test_items_extension 的 import）。398 绿。
