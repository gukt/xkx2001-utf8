# 33 - _run_transfer_veto 复制 _run_vetoable 去重（#9）

**Smell:** `transfer._run_transfer_veto`（transfer.py:306-314）与 `commands._run_vetoable`（commands.py:319）同语义（遍历 `handlers_for` + 判 `Deny`），注释自承重复。两处独立实现。

**Fix:** 抽公共 `run_vetoable(world, event_name, ctx)`（放 `events.py` 或关联 #32 拆出的模块），transfer 和 commands 都调。关联 #32（循环 import），一起拆可同时解决（`Deny` 移出后 veto 逻辑可放公共处）。

**From:** BCD re-pass code-review 物品批 Standards #9 / Spec #4（commit 79b831ef，两轴共识）。

**Status:** ready-for-agent

- [ ] veto 逻辑单一实现，两处调用
- [ ] just gate 全绿
