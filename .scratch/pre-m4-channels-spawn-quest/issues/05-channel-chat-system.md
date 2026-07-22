---
Status: resolved
---

# 05 — Channel：`chat` + `system` + 默认订阅

**What to build:** 在票 `03` 的按会话收件箱之上，加一层薄 Channel：预置两条命名管道 `chat`（玩家可写的世界闲聊，跨房间投给订阅者）与 `system`（仅引擎 API/测试注入可写的系统公告）。创建 `PlayerSession` 时默认订阅两者（本波无 `tune`/退订，订阅集合创建后即固定）。玩家用显式命令 `chat <text>` 发言，投给所有默认订阅者（不限同房间）；玩家尝试用命令写 `system` 必须被拒绝并给出清晰提示（"该频道仅系统可写"一类文案），不能被冒充。命令路由必须是显式注册表（`chat` 命令映射到 `channel:chat` 的投递），不做 LPC 式"未知 verb 命中频道 ID 就当频道发言"的 fallthrough——这是与 LPC 刻意分歧之处（见 research 笔记 §6.2/§6.6）。

对应 spec：[.scratch/pre-m4-channels-spawn-quest/spec.md](../spec.md) US3–10；[ADR-0008](../../../docs/adr/0008-single-player-channel-login-out-of-stop-scope.md)（本票落地后确认澄清仍成立，不需要新 ADR）。

**Blocked by:** 03（需要按会话收件箱才能做跨会话投递）。

- [ ] 极薄 Channel registry：`{"chat": {player_writable: True}, "system": {player_writable: False}}`，不做题材频道表/ACL/匿名/Intermud。
- [ ] `commands.py` 新增显式命令 `chat <text>`：投递给所有当前订阅 `chat` 的 `PlayerSession`（复用票 `03` 的按会话收件箱），非频道命令的解析路径不受影响（不引入"未知命令查频道表"的 fallthrough 分支）。
- [ ] `system` 频道：不提供玩家可用的写命令；提供引擎 API 或测试辅助（如 `broadcast_system(world, text)` 之类）供运行时/测试直接注入，投给所有订阅 `system` 的会话。若玩家尝试通过某种途径（如误用 `chat` 写 `system` 或直接调用受限 API）写入，必须被拒绝并给出提示。
- [ ] `PlayerSession` 创建时默认订阅集合包含 `chat` 与 `system`（本波无 `tune`，订阅集合创建后固定，不提供改订阅的玩家命令）。
- [ ] 回归测试锁定：未知/未注册命令不会被当作频道 ID 处理（即命令表解析优先，找不到命令就报"未知命令"，不去查 Channel registry）。
- [ ] 测试（S1）：两个 `PlayerSession`（可不同房间）都收到彼此 `chat` 发言；玩家写 `system` 被拒且状态不变；API/测试注入 `system` 后两会话收件箱都收到；未订阅场景（若本波暴露测试改订阅集合的手段）验证过滤，否则只测"默认订阅者收到"。
- [ ] 对外文档确认：不修改 ADR-0008 的结论（假多人 seam ≠ 登录/联网层），如发现文案需要补一句才继续成立，追加澄清而不是重开决策。
- [ ] `just test` 全绿。

## Comments

- 2026-07-22 实现：薄 `CHANNELS` registry（chat 可写 / system 不可写）；`PlayerSession.subscriptions` 默认订两者；显式 `chat` 命令 + `broadcast_system` / `publish_channel`；未知 verb 不 fallthrough。ADR-0008 澄清仍成立，未改。测：`test_channel_chat_system.py`。
