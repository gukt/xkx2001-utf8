# 04 — 非武侠示例内容包：废弃探测站（`example-pack/`）

**What to build:** 落地 spec Implementation Decisions「D1」：在 `.scratch/m3-ugc-loop-creation-surface/example-pack/` 下手写一份完整、可玩通的最小内容包（`manifest.yaml` + `scene.yaml`），题材是与"侠客行"武侠世界完全无关的科幻小场景（"废弃探测站"），**只复用现有已交付的声明式能力**（房间/出口/门与钥匙、物品 `valuable`、NPC `inquiry` 问答、NPC `shop` 商店、玩家 `currency`），**不新增任何引擎能力/组件/字段**——本票是纯内容创作票，不改 `engine/src/mud_engine/` 下任何一个模块。场景结构：3 个房间（气闸舱起点 → 补给舱 → 主控室终点），补给舱到主控室之间是一道上锁的门，钥匙（如"通行卡"）放在补给舱地面上可以先拾取；主控室里一个 NPC（如"维修机器人"），有 `inquiry` 问答（至少一条关于这个站/关于自己的话题 + `default`）与 `shop`（出售至少一件带 `valuable` 的物品）；玩家 `manifest`/`player` 段带初始 `currency` 足够买下商店里的物品。`manifest.yaml` 填 `id`/`version`/`creator`/`title`（四个字段都给，作为"完整示例"的示范）。

**Blocked by:** `02`（示例包需要能被 `load_pack` 成功加载才算完成，验收时要跑一次真实加载确认；不依赖 `03` 的 CLI 层，可与 `03` 并行）。

**Status:** done

- [x] `example-pack/manifest.yaml`：`id`/`version`/`creator`/`title` 四个字段齐全，`load_manifest` 能成功解析（用 01 号票交付的函数手动验证一次）。
- [x] `example-pack/scene.yaml`：3 个房间连通图（气闸舱 ↔ 补给舱 ↔ 主控室），气闸舱是玩家 `start_room`；补给舱→主控室的出口带 `door: locked` + `key:` 指向补给舱地面的钥匙物品；`load_scene(example-pack/scene.yaml)` 能独立成功加载（不经过 `load_pack`，先确认场景内容本身没问题）。
- [x] `load_pack(example-pack 目录)` 端到端成功：返回的 `world.pack_manifest` 字段值与 `manifest.yaml` 内容一致，场景房间/NPC/物品齐全。
- [x] 至少一个 NPC 挂 `inquiry`（含一条非 `default` 话题 + 一条 `default`）与 `shop`（至少一件商品，商品物品声明了 `valuable`）。
- [x] 玩家初始 `currency` 数值 >= 商店商品的 `valuable`（保证"能买得起"这一验收路径可达，不是玩家永远缺钱走不完剧情）。
- [x] 全程走一遍手动命令序列（look → 移动到补给舱 → 拾取钥匙 → 解锁门 → 移动到主控室 → 与 NPC 问答 → 购买物品 → 到达并确认终点房间描述），记录在本票 Comments 里作为 05 号票编写自动化剧本测试时的现成命令清单（不要求本票写自动化测试——那是 05 号票的范围，本票只要求人工跑通一次并把步骤记下来）。
- [x] 若创作过程中发现现有声明式字段确实撑不起某个诉求（真正的表达力缺口，不是"中文文案命名喜好"这类假缺口——后者直接改 YAML 展示文案即可），在本票 Comments 里记一条 GAP 说明（题材+具体缺什么），**不**因此改动引擎代码；若全程没撑上这类缺口（大概率），本票 Comments 明确写"未发现 GAP"，不要留空当作遗漏。
- [x] 场景内容/物品/NPC 命名（房间键、物品键、NPC 键）全程使用与武侠题材包（`huashan_*`/`yangzhou_*`/`shaolin_*` 等）不冲突的独立命名空间（如 `outpost_*`），即便两者永远不会在同一进程里同时加载，命名隔离仍是低成本的卫生习惯。

## Comments

- 2026-07-21 `/implement` 人工走通命令清单（供 05 号票自动化剧本）：
  1. `look` — 气闸舱
  2. `go east` — 补给舱
  3. `get 通行卡`
  4. `unlock east` → `open east` → `go east` — 主控室
  5. `ask 维修机器人 about 站点`
  6. `ask 维修机器人 about <任意未知话题>` — 触发 default
  7. `buy 备用能量芯` — 花费 25（初始 currency 50）
  8. 确认当前房间为「主控室」
- GAP：**未发现 GAP**。现有门锁/钥匙、inquiry、shop、currency、valuable 足够撑起本科幻迷你闭环；中文展示文案由 YAML 提供，无需改引擎字段名。
- 包位置：`.scratch/m3-ugc-loop-creation-surface/example-pack/`（不在 `engine/data/`）。`id=derelict-outpost` / `version=0.1.0`。`--validate` 摘要：`校验通过：derelict-outpost v0.1.0，3 个房间`。
