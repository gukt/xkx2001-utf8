---
Status: accepted
---

# 单机阶段：频道与登录不作为停机必做

[08 号票](../../.scratch/mvp-scope/issues/08-subsystem-classification-research.md) 将频道、表情、登录等列为 MVP 必做参考项。当前交付是单机 CLI（`say` + REPL 直入），尚未做多人频道或独立登录会话层。M3 停机加固拍板（2026-07-21）：**在单机阶段，频道与登录不作为停机门闩或「MVP 必做已引擎化」的验收项**；待多人/联网里程碑再评估。动机：避免按旧清单误开实现票，并与「单机可玩内核 + UGC 加载契约」的对外表述一致。

## 澄清（2026-07-22，Pre-M4 grill）

上述停机结论**仍然成立**。Pre-M4「频道/spawn/任务」可在单机内核落地：同一 `World` 挂多个 `PlayerSession` 的**测试/脚本 seam**，以及薄 Channel（本批 `chat` / `system`）。这**不等于**独立登录会话层，也**不等于**真实联网多人；不得据此宣称「频道/登录已作为停机或多人里程碑交付」。见 [.scratch/pre-m4-channels-spawn-quest/](../../.scratch/pre-m4-channels-spawn-quest/) 与 [CONTEXT.md](../../CONTEXT.md) 的 Channel / Pre-M4 词条。
