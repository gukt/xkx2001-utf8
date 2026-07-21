# 04 — 非武侠示例内容包：废弃探测站（`example-pack/`）

**What to build:** 落地 spec Implementation Decisions「D1」：在 `.scratch/m3-ugc-loop-creation-surface/example-pack/` 下手写一份完整、可玩通的最小内容包（`manifest.yaml` + `scene.yaml`），题材是与"侠客行"武侠世界完全无关的科幻小场景（"废弃探测站"），**只复用现有已交付的声明式能力**（房间/出口/门与钥匙、物品 `valuable`、NPC `inquiry` 问答、NPC `shop` 商店、玩家 `currency`），**不新增任何引擎能力/组件/字段**——本票是纯内容创作票，不改 `engine/src/mud_engine/` 下任何一个模块。场景结构：3 个房间（气闸舱起点 → 补给舱 → 主控室终点），补给舱到主控室之间是一道上锁的门，钥匙（如"通行卡"）放在补给舱地面上可以先拾取；主控室里一个 NPC（如"维修机器人"），有 `inquiry` 问答（至少一条关于这个站/关于自己的话题 + `default`）与 `shop`（出售至少一件带 `valuable` 的物品）；玩家 `manifest`/`player` 段带初始 `currency` 足够买下商店里的物品。`manifest.yaml` 填 `id`/`version`/`creator`/`title`（四个字段都给，作为"完整示例"的示范）。

**Blocked by:** `02`（示例包需要能被 `load_pack` 成功加载才算完成，验收时要跑一次真实加载确认；不依赖 `03` 的 CLI 层，可与 `03` 并行）。

**Status:** ready-for-agent

- [ ] `example-pack/manifest.yaml`：`id`/`version`/`creator`/`title` 四个字段齐全，`load_manifest` 能成功解析（用 01 号票交付的函数手动验证一次）。
- [ ] `example-pack/scene.yaml`：3 个房间连通图（气闸舱 ↔ 补给舱 ↔ 主控室），气闸舱是玩家 `start_room`；补给舱→主控室的出口带 `door: locked` + `key:` 指向补给舱地面的钥匙物品；`load_scene(example-pack/scene.yaml)` 能独立成功加载（不经过 `load_pack`，先确认场景内容本身没问题）。
- [ ] `load_pack(example-pack 目录)` 端到端成功：返回的 `world.pack_manifest` 字段值与 `manifest.yaml` 内容一致，场景房间/NPC/物品齐全。
- [ ] 至少一个 NPC 挂 `inquiry`（含一条非 `default` 话题 + 一条 `default`）与 `shop`（至少一件商品，商品物品声明了 `valuable`）。
- [ ] 玩家初始 `currency` 数值 >= 商店商品的 `valuable`（保证"能买得起"这一验收路径可达，不是玩家永远缺钱走不完剧情）。
- [ ] 全程走一遍手动命令序列（look → 移动到补给舱 → 拾取钥匙 → 解锁门 → 移动到主控室 → 与 NPC 问答 → 购买物品 → 到达并确认终点房间描述），记录在本票 Comments 里作为 05 号票编写自动化剧本测试时的现成命令清单（不要求本票写自动化测试——那是 05 号票的范围，本票只要求人工跑通一次并把步骤记下来）。
- [ ] 若创作过程中发现现有声明式字段确实撑不起某个诉求（真正的表达力缺口，不是"中文文案命名喜好"这类假缺口——后者直接改 YAML 展示文案即可），在本票 Comments 里记一条 GAP 说明（题材+具体缺什么），**不**因此改动引擎代码；若全程没撑上这类缺口（大概率），本票 Comments 明确写"未发现 GAP"，不要留空当作遗漏。
- [ ] 场景内容/物品/NPC 命名（房间键、物品键、NPC 键）全程使用与武侠题材包（`huashan_*`/`yangzhou_*`/`shaolin_*` 等）不冲突的独立命名空间（如 `outpost_*`），即便两者永远不会在同一进程里同时加载，命名隔离仍是低成本的卫生习惯。
