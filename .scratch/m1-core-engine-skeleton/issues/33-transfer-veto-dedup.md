# 33 - _run_transfer_veto 复制 _run_vetoable 去重（#9）

**Smell:** `transfer._run_transfer_veto`（transfer.py:306-314）与 `commands._run_vetoable`（commands.py:319）同语义（遍历 `handlers_for` + 判 `Deny`），注释自承重复。两处独立实现。

**Fix:** 抽公共 `run_vetoable(world, event_name, ctx)`（放 `events.py` 或关联 #32 拆出的模块），transfer 和 commands 都调。关联 #32（循环 import），一起拆可同时解决（`Deny` 移出后 veto 逻辑可放公共处）。

**From:** BCD re-pass code-review 物品批 Standards #9 / Spec #4（commit 79b831ef，两轴共识）。

**Status:** resolved

- [x] veto 逻辑单一实现，两处调用
- [x] just gate 全绿

**Resolved:** 2026-07-20，commit `b67a9f06`（与 #32 同 commit 一起拆）。
原 `commands._run_vetoable` 与 `transfer._run_transfer_veto` 两处同语义重复实现收敛为 `events.run_vetoable(world, event_name, ctx)`；commands._cmd_go 与 transfer() 均调用该单一实现。398 绿。
