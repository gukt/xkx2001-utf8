# 32 - transfer↔commands 循环 import 拆模块（#8）

**Smell:** `transfer.py:149` 惰性 import `commands.ON_DROP/ON_TAKE/TransferContext`，`transfer.py:308` 惰性 import `commands.Deny`（注释自承避免 `transfer ↔ commands` 循环）。transfer 域概念（事件常量 / 上下文 / 结果类型）住在 commands 模块，应拆到第三模块。

**Fix:** 把 `ON_TAKE`/`ON_DROP`/`TransferContext`/`Deny` 移出 commands（到 `transfer.py` 或 `events.py` 或新 `transfer_events` 模块），commands 改从该处 import，transfer 不再 import commands。关联 #33（`_run_transfer_veto` 复制），一起拆可同时解决。

**From:** BCD re-pass code-review 物品批 Standards #8（commit 79b831ef）。

**Status:** ready-for-agent

- [ ] transfer 不再 import commands，惰性 import 注释删除
- [ ] just gate 全绿
