# 截至 M3 的引擎架构综合评审报告

> 面向项目架构师的可决策报告。  
> 日期：2026-07-21  
> 依据：四份独立专家 raw + [Phase 2 交叉对抗](../adversarial/cross-review.md)  
> 约束：本报告不改 `engine/` 代码；不推动商业化与创作者平台实现。

---

## 1. 一页结论

**可否宣布 M3 交付停机？可以，但附条件。**

1. **相对 M3 自身 spec（ADR-0005/0006）**：包外声明式内容包 → `load_pack` → `--validate` → 可玩 → 存档重挂，已兑现；649 测试绿 + `just verify-m3` 锁死。**M3 里程碑可宣布完成。**
2. **相对「停住并对外诚实」**：在落盘下列条件前，**不要**把叙事写成「ADR-0004 字面不变量已齐」或「mvp-scope 18 个 MVP 必做子系统已全部引擎化」。
3. **停机附带条件（P0 门闩）**：
   - Effect：最小实现 **或** 正式修订 ADR-0004 / 摘要（二选一，禁止悬空）；
   - 昏迷：补自然苏醒/休息 **或** 改 M2 US23 并加回归测（二选一）；
   - 持刃门禁与「可收刀」语义对齐；消灭战斗回合进程全局缓冲；统一 `wire_runtime`；
   - 创作者契约 v0 文档化 + `--validate` 未消费字段 warn；刷齐已实现票 Status；单机阶段频道/登录范围降级脚注。
4. **明确不做（本窗口）**：M4 账本/分成/埋点实现、Web 创作者平台、编辑器、留言板、脚本沙箱、分布式、LPC 行为等价。
5. **建议节奏**：进入 **M3 停机加固窗口**（可称 M2.5 / M3-hardening），消化 P0（及可选 P1），**暂缓** PROGRESS 中的「下一步 M4」。
6. **M2 对外表述**：工程上「一条 MVP 场景端到端可玩」成立；规格上应标 **部分→接近符合**（Effect / US23 空洞）。
7. **架构总评**：运行时命令/tick 边界与多处深模块健康；尖峰上帝模块与 ADR 落差是主要结构债，非推倒重来信号。
8. **侠客行对照**：仅灵感；灵感缺口 ≠ 规格债（见第 4 节）。

---

## 2. 架构设计总评

### 2.1 总体判断

绿场 `mud_engine`（约 9.4k 行、扁平包、649 测）已形成自洽单机 CLI 闭环：内容加载 → ECS World → 解析/意图 → 命令 → tick/`on_tick` → JSON 原子存档。对抗确认：这不是「勉强能跑」，而是 **接缝手法一致**（声明式数据 + Protocol + 注册表/`attach_*` + 可否决事件）在 M1→M2→M3 上复用成功。

### 2.2 优点（保留）

| 优点 | 对抗确认 |
|---|---|
| 命令路径 vs tick 路径职责清晰 | 共识；与 M1 用户故事一致 |
| 深模块真实存在：`resolve_attack`、`conditions.evaluate`、`transfer`、`EventBus`/`run_vetoable`、`pack.load_pack`、存档原子发布 | 架构师主证；QA 测试分层同构 |
| M3 范围纪律：组合而非改造 `load_scene`；非武侠包实证加载题材无关 | UGC/架构师/QA 共识 |
| 运行时态与存档态分离有意识 | 架构师；QA 存档 seam 达标 |
| 渡口动态 Exit 验证了预留机制 | 架构师；主策 L7 低风险亮点 |

### 2.3 结构风险（对抗后排序）

| 风险 | 停机优先级 | 说明 |
|---|---|---|
| ADR-0004 Effect 机制空白 | **P0 决策** | 共识最大规格债 |
| `commands.py` / `capabilities.py` 上帝模块 | **P1** | 可测但冲突面大；不阻塞宣布 M3 |
| `World` 挂件增多 | **搁置反模式指控**；P0 只统一接线 | 单机规模可接受 |
| 全局注册表 vs World 实例 | **文档锚定单 World** | 迁表搁置 |
| `_ROUND_EXTRA_FRAGMENTS` 进程全局 | **P0** | 破坏纯函数叙事；多 World 隐患 |
| 循环依赖靠延迟 import | **P1** 抽 `room_say` | |
| 默认武侠语义渗入 | **P1 软** | 不否定题材无关加载主张 |
| 多人能力未做 | **范围降级文档** | 非实现阻塞 |

### 2.4 不变量符合度（摘要）

| 不变量 / ADR | 符合度 |
|---|---|
| 单机、纯 Python、内存+JSON | 高 |
| ADR-0001 不做 LPC 等价 | 高 |
| ADR-0002/0003 绿场与包名 | 高 |
| ADR-0004 战斗骨架+钩子；**Effect 生命周期** | 骨架高；**Effect 低（须 A/B）** |
| ADR-0005 M3 创作面 | 高（相对刻意切片） |
| ADR-0006 无编辑器/留言板 | 高 |
| 商业化四支撑点「留位置」 | 仅元数据雏形——**勿声称齐全** |

---

## 3. Spec 符合度总评

| 里程碑 | 符合度 | 说明 |
|---|---|---|
| **M0** | 符合 | mvp-scope 10/10；CLAUDE 重写 |
| **M1** | 符合 | 骨架+扩展 seam；个别票 Status 未刷（治理） |
| **M2** | **部分→接近符合** | 六分区连通、战斗/成长/死亡/金钱/门派/坐骑交通主路径可玩且有 e2e；**Effect（ADR-0004）与 US23 昏迷苏醒未兑现**；若干票 Status 漂移 |
| **M3** | **符合** | 块 A–D 与 OOS 纪律满足；示例包刻意子集不构成失败 |
| **M4** | 不适用 | 本轮不评实现；且建议暂缓开做 |

**关键漂移（须在停机叙事中显式出现）**：

- **D1** ADR-0004 Effect 生命周期：高。
- **D2** M2 US23 自然苏醒：中（产品上接近软锁）。
- **D3** 战斗轮事件点缺契约测：中。
- **D4/D5** issue Status 与实现脱节：治理中/低。

**已知非漂移（勿误判为漏做）**：默认 CLI 仍 M1 场景；示例包无战斗/坐骑；riposte/ThreatTable/PvP；编辑器/Web 台——均有 Spec/ADR OOS。

---

## 4. 相对侠客行 / MVP 系统缺口

> **硬规则**：灵感对照 ≠ 规格债（ADR-0001）。下表左栏不得单独构成「停机失败」理由。

### 4.1 规格债 / 产品债（应对齐文档或实现）

| 项 | 性质 | 处置 |
|---|---|---|
| Effect 生命周期 | ADR / 必做 #31 | P0：实现或改判 |
| 昏迷自然苏醒 | M2 US23 | P0：实现或改 US23 |
| 持刃=背包标签 | 设计体验债 | P0 |
| 装备/消耗无命令面 | 组件占位未接玩法 | P1 |
| 创作者契约未产品化、静默透传 | UGC 停机产品债 | P0 文档+validate warn |
| 频道/登录相对「MVP 必做」清单 | 范围错位 | P0 降级脚注，不强制实现 |
| 票 Status 漂移 | 治理 | P0 刷票 |

### 4.2 灵感缺口（非规格；停机不阻塞）

| 体验层（侠客行启发） | 现状体感 | 备注 |
|---|---|---|
| 频道/表情社交 | 单机 say | 多人里程碑再议 |
| 完整武学博弈（busy/运功/兵器特效） | 数值互殴+瞬时钩子 | 依赖 Effect 决策 |
| 城镇生活纵深 | 扬州多地标布景 | P1 内容加厚 |
| 阴间叙事 | 刻意不做 | 保持 OOS |
| 区域多文件世界树 | 单 YAML | 内容体量驱动后再开 |
| Driver/网络会话层 | CLI 即 IO | 联网时再拆 |

### 4.3 MVP 必做 18：停机期正确读法

主策对照约 **8 已实现 / 6 部分 / 状态严重未实现 / 登录刻意不做 / 频道·表情未实现**。  
**正确对外表述**：当前交付 = **单机可玩内核 + UGC 加载契约**，不是「18 项全部引擎化完成」。

---

## 5. 联动测试达标总评

测试架构本身是强项：纯函数 → 命令 seam → tick seam → 存档 → e2e / verify 双轨（pytest 回挂防漂移）。

| 联动链 | 达标 | 停机含义 |
|---|---|---|
| 交战→tick 扣血→播报 | 达标 | |
| 昏迷→再击→惩罚复活；免死区 | 达标（流程） | 缺自然苏醒 = 规格/体验洞 |
| NPC loot/respawn；1v1；aggro | 达标 | |
| 坐骑×地形×渡船×e2e 旅程 | 达标 | 骑乘×渡船刻意交叉、坐骑休整为 P1 |
| 门禁×门派×消歧（ask/attack） | 达标 | 持刃语义体验另案 |
| Pack×validate×CLI restore（移动/物品） | 达标 | Pack×交战 restore = P1 |
| **持续 Effect** | **未达标** | 随 P0-1 |
| **昏迷自然恢复** | **未达标** | 随 P0-2 |
| 战斗轮事件点契约 | 部分 | P0 最小测 |
| 双玩家同房广播 | 未达标 | P2；单机降级 |
| 全命令同名消歧 | 未达标（相对加码） | P2 |

**总判**：联动对「已承诺可玩主路径」基本达标；对「ADR 字面效果系统 + 苏醒故事」未达标。停机可信度取决于 P0 诚实化，而非再堆大量新测。

---

## 6. 统一 P0 / P1 / P2 行动清单

> 负责人仅为**角色建议**，不派工。详细对抗溯源见 [cross-review.md](../adversarial/cross-review.md)。

### P0 — 停机门闩

| ID | 行动 | 角色建议 |
|---|---|---|
| P0-1 | Effect：**最小骨架+契约测** 或 **修订 ADR-0004 + CLAUDE 摘要**（二选一） | 架构师 / 领域建模 |
| P0-2 | 昏迷：tick/rest 苏醒 **或** 改 US23 + 回归测 | 主策划 + 实现/QA |
| P0-3 | 持刃：改门禁条件或最小 wield/unwield/stash | 主策划 + 实现 |
| P0-4 | 消灭 `combat` 模块级回合碎片全局态 | 实现 |
| P0-5 | `wire_runtime`（load/restore 接线单一事实来源） | 实现 |
| P0-6 | 创作者契约 v0 一页纸；冻结对外表述；PROGRESS 边界声明 | UGC / 文档 |
| P0-7 | `--validate` 报告未消费字段（默认 warn，`--strict` 失败） | 实现 |
| P0-8 | 刷 M2 已实现票 Status；战斗事件点 before veto / end 最小契约测 | 治理 + QA |
| P0-9 | 频道/登录单机降级脚注（短 ADR 或 PROGRESS/CLAUDE 注） | 架构师 / 治理 |

**若建议改判 ADR**：P0-1 选项 B、P0-9 范围降级——须单独开 ADR/修订条目，不得只改口头叙事。

### P1 — 强烈建议

| ID | 行动 | 角色建议 |
|---|---|---|
| P1-1 | 拆分 `commands.py`；分区 `capabilities.py` | 实现 |
| P1-2 | 文档写明「单进程单 World」注册表策略 | 架构师 |
| P1-3 | 抽出 `room_say`，解开 `ai↔commands` | 实现 |
| P1-4 | 官方包化或范本文档（消除双轨误解） | UGC / 内容 |
| P1-5 | 扬州地标加厚；`use`/消耗品；坐骑休整 | 主策划 + 内容 |
| P1-6 | Pack×交战 restore；SkillBehavior×World tick；骑乘×渡船交叉测 | QA |
| P1-7 | 能力橱窗包 + GAP 台账 | UGC |
| P1-8 | 可选 `power_model` 场景/manifest 声明 | 架构师 + 实现 |
| P1-9 | `$N`/`$n` 表情模板瘦身（若 #10 未完全改判） | 主策划 + 实现 |

### P2 — 后置 / 有余力

目录分层大搬家；默认 CLI 进 M2；双玩家广播契约；全命令消歧加码；e2e 断言收紧与拆分；`extension_data` 语义终裁；多文件场景；脚本层；阴间；PvP；覆盖率门禁。

---

## 7. 明确不做 / 后置项

| 项 | 依据 | 本窗口 |
|---|---|---|
| M4 商业化数据模型实现（账本/分成/强制埋点） | 用户停 M3；06 号票仅「留位置」 | **不做** |
| Web 创作者一站式平台 | ADR-0006；post-mvp-backlog | **不做** |
| 游戏内编辑器、留言板 | ADR-0006 | **不做** |
| RestrictedPython / WASM 脚本、Ink 树、LLM Orchestrator | ADR-0005；M3 OOS | **不做**（先 GAP 台账） |
| LPC 行为等价 / golden trace | ADR-0001 | **永不做**（当前目标） |
| 分布式、K8s、PG/Redis、多进程世界隔离 | mvp-scope 05 | **不做** |
| 完整阴间、混战仇恨表、驯服夺骑、21 门派 | M2 OOS / 非规格 | **后置** |
| 空沙箱 Protocol「先留接缝」 | 对抗 D19 | **不做** |
| 假装四商业支撑点已齐 | 对抗 D20 | **禁止该叙事** |

---

## 8. 附录：文档索引

### 本评审目录

| 路径 | 内容 |
|---|---|
| [README.md](../README.md) | 状态、目录树、阅读顺序 |
| [experts/01-senior-architect-raw.md](../experts/01-senior-architect-raw.md) | 高级架构师独立评审 |
| [experts/02-ugc-expert-raw.md](../experts/02-ugc-expert-raw.md) | UGC/DSL 专家独立评审 |
| [experts/03-lead-designer-raw.md](../experts/03-lead-designer-raw.md) | 主策划独立评审 |
| [experts/04-spec-qa-raw.md](../experts/04-spec-qa-raw.md) | 规格/QA 独立评审 |
| [adversarial/cross-review.md](../adversarial/cross-review.md) | Phase 2 交叉对抗裁决 |
| **本文件** | 最终综合报告 |

### ADR（重设后）

| ADR | 主题 |
|---|---|
| [0001](../../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md) | 不做 LPC 行为等价 |
| [0002](../../../docs/adr/0002-engine-workspace-greenfield-reset.md) | engine 绿场重置 |
| [0003](../../../docs/adr/0003-python-package-mud-engine.md) | 包名 `mud_engine` |
| [0004](../../../docs/adr/0004-combat-effects-boundary-engine.md) | 战斗/Effect 边界——**本轮焦点修订候选** |
| [0005](../../../docs/adr/0005-m3-ugc-loop-creation-surface.md) | M3 包外创作面 |
| [0006](../../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md) | 无编辑器；平台 post-MVP |

### Scratch / 规格

| 路径 | 用途 |
|---|---|
| [PROGRESS.md](../../../PROGRESS.md) | 活状态 |
| [CLAUDE.md](../../../CLAUDE.md) | 架构不变量摘要 |
| [.scratch/mvp-scope/](../../mvp-scope/) | 新目标定稿（含 08 子系统归类、10 场景、07 治理、post-mvp-backlog） |
| [.scratch/m1-core-engine-skeleton/](../../m1-core-engine-skeleton/) | M1 spec |
| [.scratch/m2-mvp-scene-playable/](../../m2-mvp-scene-playable/) | M2 spec；票 16 Effect 降级；票 26 e2e |
| [.scratch/m3-ugc-loop-creation-surface/](../../m3-ugc-loop-creation-surface/) | M3 spec；example-pack |

### 引擎证据入口（只读）

- `engine/src/mud_engine/`（尤其 `pack.py`、`combat.py`、`death_flow.py`、`commands.py`、`scene_loader.py`）
- `engine/tests/test_m2_e2e_script.py`、`test_m3_pack_loop.py`、`test_verify_*_matrix.py`
- `engine/scripts/verify_m2_*.py`、`verify_m3_pack_loop.py`
- `engine/data/m2_mvp_scene.yaml`

---

*本报告为评审委员会主席综合裁决，供架构师决策；落地实现需另开加固票 / ADR 修订，不在本文件自动改代码。*
