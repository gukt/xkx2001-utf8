# UGC / DSL / 内容创作层专家 — 原始评审

## 元信息

| 项 | 值 |
|---|---|
| 角色 | UGC / DSL / 内容创作层专家（独立原始评审，未与其他专家协商） |
| 日期 | 2026-07-21 |
| 评审范围 | 截至 M3 的 UGC 创作面与内容包管线（包外声明式内容包 → 加载 → 校验 → 可玩） |
| 硬约束对齐 | ADR-0005、ADR-0006、mvp-scope 03/06/07、用户决策「先停在 M3，不推商业化与创作者平台」 |
| 产出性质 | 原始评审；不写 final / adversarial 综合稿；不改代码 |

---

## Executive summary

M3 对创作面的承诺（包外壳 + 包外指向加载 + `--validate` 契约 + 非武侠示例包端到端）**已兑现**，与 ADR-0005 / ADR-0006 无范围偏离。在「刻意最小切片」语义下，创作面**停得住**：闭环可复现、题材无关边界被实证、内容侧无脚本越界。

「可扩展」方面评价更审慎：停得住 ≠ 已具备正式 DSL。`scene_loader` 文档仍自称「M1 内部过渡格式，不是交给创作者的正式 UGC DSL」；作者可读契约主要靠代码注册表 + 一份子集示例，而非稳定 schema；未知字段静默透传、无 `engine_compat` / schema 版本协商、官方包与 UGC 包双轨（`engine/data/` 无 manifest）——这些是**暂停期可接受的技术债**，但若长期冻结而不做「创作者契约冻结」动作，后续题材包横向扩展与 Web 平台复用会摩擦上升。

**总判**：M3 作为「打通一次」里程碑合格；作为「UGC 创作面可长期停驻的契约基线」尚差一层文档化与契约硬化。建议用少量 P0（契约文档 + 未知字段策略澄清）把「停」从工程事实变成作者可依赖的产品事实，再按需开 P1/P2，而不是立刻推平台或脚本层。

---

## 创作面现状测绘

### 1. 交付物拓扑

```text
内容包目录（任意磁盘路径）
├── manifest.yaml     # 身份：id / version / 可选 creator、title；其余 → extra 透传
└── scene.yaml        # 世界内容：委托既有 load_scene（字段集零改动）

引擎契约
├── mud_engine.pack.load_manifest / load_pack / reattach_pack_manifest
├── World.pack_manifest（运行时态，不进存档；restore 后按 scene_path.parent 重挂）
├── CLI: --pack <dir>、--pack <dir> --validate
└── just verify-m3 / scripts/verify_m3_pack_loop.py / tests/test_m3_pack_loop.py

示例证据
└── .scratch/m3-ugc-loop-creation-surface/example-pack/（非武侠「废弃探测站」）
```

### 2. 创作者能声明什么（引擎已加载能力面）

| 层 | 可声明内容 | 机制入口 |
|---|---|---|
| 包身份 | `id`、`version`、可选 `creator`/`title`、未知键进 `extra` | `PackManifest` |
| 顶层已知段 | `rooms` / `items` / `npcs` / `player` / `skills` / `factions` / `death_policy` | `scene_loader` |
| 顶层未知段 | 如 `nature` 等：透传 `world.extension_data`，部分由挂载函数消费 | 透传 + `attach_nature` 等 |
| 房间 | 名/描述/出口；门三态+钥匙；`outdoors`/`no_death`/`ferry`/`entry_guard`/`cost`/`terrain` | `ROOM_CAPABILITIES` |
| 物品 | 放置、堆叠、价值、装备、消耗、不可拿/丢、容器、重量、标签等 | `CAPABILITIES` |
| NPC | inquiry 静态问答、shop、behaviors、vitals/attributes/skills、currency、faction、mount、gender、刷怪相关字段等 | `NPC_CAPABILITIES` |
| 玩家初值 | `start_room`、与 NPC 对齐的初值能力字段（currency 等） | `_PLAYER_KNOWN_FIELDS` |
| 全局注册 | 技能表、门派表、死亡策略 | 顶层段 |

### 3. 创作者明确不能声明 / 引擎不做的（M3 刻意边界）

- 游戏内编辑器、留言板、Web 评审台（ADR-0006；平台 post-MVP）
- Ink 对话树、RestrictedPython / 任意脚本、LLM Orchestrator（ADR-0005 / 03 Refinement）
- 多文件场景拼接、单进程多包共存
- 正式 DSL 向后兼容承诺、引擎能力版本协商（`engine_compat` 等）
- 完整商业化元数据（双货币账本、分成、埋点——06 号票仅要求「留位置」；M3 只落了 manifest 简化版）

### 4. 校验与反馈通道

- **结构校验**：`PackManifestError`（身份阶段）与 `SceneLoadError`（内容阶段）分型；CLI 前缀「包清单错误 / 场景内容错误」可区分。
- **校验模式**：`--validate` 复用 `load_pack`，不启 REPL、不触存档；stdout 摘要含 id / version / 房间数；退出码可被未来平台 shell 调用——对齐 ADR-0006「验证复用引擎侧契约」。
- **未知字段**：场景实体未知键、manifest 未知键、顶层未知段均**静默透传不报错**（已知字段集 + 透传手法）。利于演进，但作者拼写错误会被「加载成功」吞掉。
- **无**：JSON Schema / 能力目录导出、语义平衡校验、依赖图、资源配额（脚本层未引入故合理）。

### 5. 与官方内容路径的关系

- 默认 `python -m mud_engine` 仍走 `engine/data/m1_default_scene.yaml`，**无 manifest**；M2 官方武侠场景主要经测试/脚本路径，不经 `--pack`。
- UGC 路径与官方路径形成**双轨**：UGC 有身份外壳，官方场景仍是「裸 scene YAML」。对「打通一次」无碍；对「题材包横向扩展统一资产模型」是后续债。

### 6. 内容 vs 逻辑边界（当前实测）

- 内容包全程 `yaml.safe_load`，**无可执行载荷**——攻击面与加载官方 YAML 同构；M3 不引入沙箱是正确的。
- 「类逻辑」仅存在于**引擎已实现的声明式钩子**：`entry_guard` 条件、`behaviors` 枚举 kind、inquiry/shop 状态机外壳等——逻辑在引擎，内容包只填数据。
- `extension_data` / entity extras 允许声明引擎尚不认识的键并静默保留：边界清晰（不执行），但对作者是「写了但无效」的隐性体验。

---

## M3 规格符合度矩阵（承诺 vs 实现）

依据：`.scratch/m3-ugc-loop-creation-surface/spec.md` 块 A–D + ADR-0005/0006 + mvp-scope 03 Refinement。

| # | 承诺 | 实现状态 | 证据 | 评注 |
|---|---|---|---|---|
| A1 | 包 = 目录 + `manifest.yaml` + `scene.yaml`；场景字段零改动 | **满足** | `pack.py` 组合 `load_scene`；spec A1 | 关注点分离正确 |
| A2 | `PackManifest`：必需 id/version，可选 creator/title，未知透传 | **满足** | `PackManifest` + `extra`；`test_pack_manifest.py` | 商业化支撑点 #2 简化版已落位 |
| A3 | `PackManifestError` 与 `SceneLoadError` 分型 | **满足** | `errors` + CLI 前缀 | 可区分身份 vs 内容阶段 |
| B1 | `load_pack` → World + player；挂 `pack_manifest` | **满足** | `load_pack`；`test_load_pack.py` | 未改 `load_scene` 本体——架构约束守住 |
| B2 | manifest 不进存档；restore 后 `reattach_pack_manifest` | **满足** | `reattach_pack_manifest`；存档测 | 依赖磁盘上 manifest 仍在——M3 可接受 |
| B3 | `--pack` 任意路径；默认行为不变；存档落 `<pack>/save/` | **满足** | `__main__.py`；CLI 测 | 多包存档天然隔离 |
| C1 | `--validate` 须配 `--pack`；同校验码路径；不触存档 | **满足** | `_validate_pack`；坏包测 | 平台复用契约的最小形态已有 |
| D1 | 非武侠示例包在 `engine/data/` 外 | **满足** | `example-pack/` | 题材无关被实证 |
| D2 | 可玩闭环（门钥匙 / inquiry / shop / currency） | **满足** | 剧本测 + `verify_m3_pack_loop.py` | 故意用能力子集，非全能力目录 |
| D3 | 撞表达力缺口记 GAP，不借机扩引擎 | **满足** | 04 票 Comments：「未发现 GAP」 | 纪律正确 |
| D4 | 自动化锁死闭环 | **满足** | `test_m3_pack_loop.py`；649 绿（PROGRESS） | |
| OOS | 不做编辑器/脚本层/多文件/正式 DSL 定稿 | **遵守** | ADR-0005/0006；Out of Scope | 无范围蔓延 |
| 隐含 | 「题材无关引擎」可装外部、异题材内容 | **首次实证** | derelict-outpost | 项目一句话的关键缺口被补上 |

**符合度结论**：相对 M3 **刻意收窄**的承诺，符合度为满分档；相对「完整 UGC 创作产品」，本矩阵不适用——那是 post-MVP。

---

## 创作者能力缺口与风险

### A. 停得住（相对「先停在 M3」）

| 判断 | 说明 |
|---|---|
| **闭环可复现** | 手写包 → validate → 可玩 → 存档恢复路径齐备；示例包 + 测试锁死 |
| **边界诚实** | 不做编辑器/平台/脚本与 ADR 一致；创作者预期可对齐「手写 YAML + CLI」 |
| **安全面可控** | 无包内代码，暂停期不必背沙箱/配额复杂度 |
| **商业化位置已留** | `id`/`version`/`creator` + 一进程一包；不要求实现分成/埋点 |

### B. 可扩展性风险（暂停期若长期冻结）

1. **契约未产品化（高）**  
   `scene_loader` 开篇仍写「不是 M3 要交给创作者的正式 UGC DSL」。作者能力面真实存在于 `capabilities.py` 注册表与测试，但**没有**创作者面向的字段目录 / 示例矩阵 / 错误码手册。新人复制 `example-pack` 只能学会子集，易低估或误用全能力面。

2. **静默透传掩盖拼写错误（中高）**  
   未知字段不失败：作者写错 `inquirys` / `valuables` 会「校验通过」但行为缺失。对 Agent 写包尤其危险（生成器常 invent 字段）。`--validate` 目前只证明「结构可加载」，不证明「意图字段被消费」。

3. **双轨资产模型（中）**  
   官方 `engine/data/*.yaml` 无 manifest；UGC 有。未来「所有可发布世界统一为包」时要迁移或兼容层。横向扩展叙事（很多题材包）与「默认玩的是无身份的官方 YAML」略拧。

4. **无引擎/内容 schema 版本协商（中）**  
   Spec 明确 OOS。暂停可接受；一旦引擎增删字段，外部包何时失效无机器可读信号。`extra` 可塞自定义键，但引擎不读 `min_engine` 之类约定。

5. **声明式表达力天花板未标定（中）**  
   M1 调研（`research/04-dsl-dynamic-rules.md`）与旧方案统计均指出：纯声明式覆盖不了全部玩法；M3 用「先不引入脚本」回避。示例包「未发现 GAP」是因为场景被裁到已有能力内——**不是**证明「任意题材迷你体验都能声明式完成」。复杂任务链、多步交易 inquiry、动态出口规则等仍会撞墙；暂停期需要一份「已知 GAP / 推荐降级写法」清单，否则创作者会误以为引擎「什么都能 YAML」。

6. **restore ↔ manifest 磁盘耦合（低–中）**  
   `pack_manifest` 不进存档、依赖旁路文件重读：包目录被挪走/manifest 被改后，存档仍可玩世界态，但身份元数据可能丢或变。M3 合理；平台化上架版本钉死后需再议。

7. **单文件场景上限（低，已知）**  
   MVP 场景规模（华山村+扬州子集+少林+野外…）塞进单 YAML 在官方路径已证明可行；UGC 大包会痛。Spec 已推迟多文件——暂停 OK，但横向「大题材包」作者会早于平台出现需求。

8. **埋点 / 账本接缝未触达运行时（低，符合范围）**  
   有 `pack_manifest.id` 挂在 World，但未见消费/参与度打点强制带 pack id；货币仍是场景内单 `Currency`。位置「留了数据结构入口」，未留「调用约定」。用户决定不推 M4 商业化时，这是可接受缺口。

### C. 创作者体验：能 / 不能 摘要

**能（且合理）**：描述可探索空间图、门锁谜题、静态 NPC 问答与商店、物品属性、战斗/技能/门派/死亡/渡船/坐骑等 M2 已交付机制的数据面；用 CLI 秒级校验；包外任意目录发布。

**不能（且在 M3 合理）**：对话树、脚本钩子、包内可执行逻辑、游戏内编辑、多包拼接、平台上架流。

**不能（暂停期略疼、建议用文档/工具缓解而非立刻做平台）**：一次性看清「全部合法字段与示例」；区分「透传无效」与「校验失败」；声明「本包需要引擎 ≥X」；把官方武侠大场景当 UGC 包同构管理。

---

## 相对侠客行内容组织的启发（非规格）

> LPC / `docs/archive/xkx-arch` 仅作灵感，非行为等价规格（ADR-0001）。

1. **区域目录 vs 单包单文件**  
   侠客行 `/d/<region>/` 按地理/门派切目录，房间/NPC/物品分文件继承组装（世界构建说明书）。新引擎 M3「一目录两文件」是正确的最小切片，但**区域级组织习惯**会在官方 MVP 场景与未来大 UGC 包上回归——启发是：包内多文件/子目录是扩展轴，不必回到 LPC 继承树。

2. **继承+Feature 混入 vs 能力注册表**  
   LPC `inherit` + `F_*` 混入对应「对象能做什么」。新引擎 `CapabilitySpec` 注册表是同构思想的现代化：创作者组合字段而非继承 C 文件。启发：创作者文档应按「能力卡片」（inquiry / shop / ferry…）组织，而不是按 YAML 顶层段百科——更接近 Feature 心智。

3. **set() 任意键反模式**  
   旧避坑强调字段必须显式 schema。当前「已知集 + 透传」在演进期有用，但对 UGC 作者更接近「半开放 bag」——长期应把透传定位为「引擎内部演进缓冲」，对外部作者默认 **warn 或 strict 模式**，否则重蹈语义塞进 string bag。

4. **inquiry 是交易状态机非对话树（§21）**  
   M3 继续静态 inquiry，正确继承教训。示例包用问答+商店分离，避免把交易塞进叙事树——可复制为创作者指南范例。

5. **三层粒度 Theme > Module Pack > UGC CPK（旧架构）**  
   新目标改为题材包横向扩展。M3 的 `PackManifest` 更接近「一个可启动世界实例的身份」，尚未区分官方主题包 / 模块包 / 玩家微包。暂停期不必分层，但 manifest `extra` 或未来字段应预留 `kind`/`theme_id` 之类，避免所有包扁平等同。

6. **旧四层 DSL 的统计动机仍成立**  
   ~30% 纯数据 / ~70% 含逻辑的比例不因「不做复刻」而消失。M3 只验证了「纯声明式子集可玩」；启发是：停在 M3 时把「脚本层延后」写成**明确的产品边界**，并维护 GAP 清单，以免创作者把「未发现 GAP」误解为「永不需要脚本」。

---

## 改进建议 P0 / P1 / P2

### P0 — 暂停期也建议做（成本低，显著提高「停得住」的产品含义）

1. **创作者契约一页纸（或生成自代码）**  
   从 `_TOP_LEVEL_*` / `CAPABILITIES` / `ROOM_*` / `NPC_*` / `PackManifest` 导出「合法字段 + 类型要点 + 指向 example / 官方场景片段」。明确标注：`scene_loader` 对外部作者即现行契约（即使内部仍称过渡格式）。  
   *目的*：把「能声明什么」从源码考古变成可复制知识。

2. **`--validate` 增加「未消费字段」报告（默认 warn，可选 `--strict`）**  
   列出落入 `extra` / `entity_extension_data` / 未挂载能力的键。不改变加载成功语义（非严格模式），但消灭「校验通过却没效果」。  
   *目的*：守住「校验契约」对人或 Agent 的可信度。

3. **冻结一句对外表述**  
   在 PROGRESS / 创作者 README 级写清：当前创作面 = 声明式 YAML 包 + CLI 校验；不做编辑器/脚本/平台；已知表达力边界见 GAP 列表（可先空或链到 04 票「未发现」+ M1 调研结论）。  
   *目的*：用户「先停 M3」时预期对齐。

### P1 — 扩展前应做（不推平台也可做）

4. **官方场景包化（或双轨兼容策略 ADR）**  
   给 `m2_mvp_scene`（及默认场景）补最小 manifest，或文档规定「仅 UGC 需 manifest、官方豁免」——二选一，避免无意识分叉。

5. **manifest 演进字段约定（仍可不实现逻辑）**  
   在文档中约定保留键：`engine_api` / `schema_version` / `tags` / `kind`，继续走 `extra` 透传；引擎暂不强制。为 M4 / 平台列表页预留。

6. **能力子集示例矩阵**  
   在 example-pack 旁增加「能力橱窗」小包或文档表（每能力 5–15 行 YAML），与「废弃探测站剧情包」分离——剧情包保持可玩；橱窗包负责可复制性。

7. **GAP 台账**  
   把「声明式做不到、建议降级写法 / 等脚本层」记入 `.scratch` 或 docs，避免每个题材作者重复踩坑。

### P2 — 明确后置（与「不推平台/商业化」一致）

8. Web 创作者平台、上架流、分成（post-MVP backlog）——引擎侧只保 CLI 契约。  
9. 多文件 / 包内资源目录、热重载、包依赖。  
10. RestrictedPython 逃生舱 + 能力令牌 + fuel（仅当 GAP 台账显示声明式不够且有真实作者需求）。  
11. 运行时埋点强制带 `pack_id`、双货币账本（M4 范围，用户当前不推则可继续挂起）。

---

## 待交叉对抗争议点（≥5）

以下为故意留给其他专家 / adversarial 轮的张力点，本专家给出倾向但不裁定。

1. **「过渡格式」措辞 vs M3 已对外可加载**  
   代码仍称非正式 UGC DSL，但 M3 已把该格式当作包外创作面唯一载体。争议：是否应立刻宣布「格式冻结 v0」，还是继续「内部过渡」以免承诺过重？  
   *本专家倾向*：对外冻结 v0 字段集（可加不可乱改语义），对内可继续演进加载器实现。

2. **未知字段：透传友好 vs 作者友好**  
   演进派要透传；UGC 体验派要 fail/warn。争议：strict 是否应成为 `--validate` 默认？  
   *本专家倾向*：validate 默认 warn 列出未消费键；`--strict` 失败；运行时加载保持兼容透传直至 major。

3. **example-pack 用能力子集 vs 证明题材无关**  
   子集降低「全引擎可题材无关」的证明强度（战斗/渡船/坐骑等未进示例）。争议：是否需要第二份「全能力冒烟包」才算题材无关闭环完整？  
   *本专家倾向*：M3 定义已满足；全能力冒烟属 P1 质量工程，不否定 M3。

4. **manifest 不进存档**  
   简化正确，但与「版本归属可审计」张力（改磁盘 manifest 即改历史局身份）。争议：M4 前是否要把 `pack_id`+`version` 快照进 `world_meta`？  
   *本专家倾向*：暂停期可维持现状；一旦有多版本并存或分成，必须快照。

5. **脚本层时间点**  
   旧统计与 M1 调研主张终将需要逃生舱；ADR-0005 明确 M3 不做。争议：停在 M3 时是否应预留钩子接缝（空 Protocol），还是继续「无接缝直到第一张真实 GAP 票」？  
   *本专家倾向*：不预留空沙箱；先 GAP 台账；接缝随第一张真实需求票设计（避免无调用者的护栏）。

6. **官方默认场景仍非 M2 / 非 pack**  
   Spec 自觉 OOS。争议：对「创作者以官方为范本」是否造成错误范本（无 manifest、极简 M1）？  
   *本专家倾向*：产品债，应用「官方包化」或文档「范本以 example-pack + m2 yaml 为准」缓解。

7. **商业化支撑点「留位置」是否已够**  
   仅有 creator 字符串 + pack id，无 provenance 链、无强制 pack_id 埋点。争议：用户不推 M4 时，是否还要在引擎日志/命令路径强制带 pack_id 空实现？  
   *本专家倾向*：不强制空实现；但文档写明「World.pack_manifest 即埋点主键接缝」，避免 M4 时再找挂点。

8. **单 YAML 是否会在 MVP 官方场景前先爆**  
   UGC 暂停，但官方 MVP 场景清单很大。争议：多文件是否应在「UGC 扩展」之前因**官方内容工程**被迫提前？  
   *本专家倾向*：由内容体量驱动，不由 UGC 教条驱动；若官方先痛，用「包内多 scene 文件」票，仍保持一进程一包。

---

## 证据索引

| 材料 | 用途 |
|---|---|
| [CLAUDE.md](../../../CLAUDE.md) 架构不变量 5、6、7 | UGC 边界、商业化支撑点、MVP 场景 |
| [PROGRESS.md](../../../PROGRESS.md) | M3 Wave 0–3 完成、649 绿、下一步原 M4（用户现停 M3） |
| [ADR-0005](../../../docs/adr/0005-m3-ugc-loop-creation-surface.md) | 包外声明式创作面；落地核对 |
| [ADR-0006](../../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md) | 编辑器丢弃；平台 post-MVP；引擎留校验契约 |
| [.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md](../../mvp-scope/issues/03-ugc-dsl-design-inheritance.md) | 不沿用四层；M3 Refinement 四条 |
| [.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md](../../mvp-scope/issues/06-scaling-commercialization-support-points.md) | 支撑点 #2/#4 |
| [.scratch/mvp-scope/post-mvp-backlog.md](../../mvp-scope/post-mvp-backlog.md) | Web 平台范围 |
| [.scratch/m3-ugc-loop-creation-surface/spec.md](../../m3-ugc-loop-creation-surface/spec.md) | M3 承诺全文 |
| [issues/04-example-pack-derelict-outpost.md](../../m3-ugc-loop-creation-surface/issues/04-example-pack-derelict-outpost.md) | 示例包验收 +「未发现 GAP」 |
| [example-pack/manifest.yaml](../../m3-ugc-loop-creation-surface/example-pack/manifest.yaml) / [scene.yaml](../../m3-ugc-loop-creation-surface/example-pack/scene.yaml) | 非武侠内容实证 |
| [engine/src/mud_engine/pack.py](../../../engine/src/mud_engine/pack.py) | manifest / load_pack / reattach |
| [engine/src/mud_engine/scene_loader.py](../../../engine/src/mud_engine/scene_loader.py) | 过渡格式声明、顶层段、透传 |
| [engine/src/mud_engine/capabilities.py](../../../engine/src/mud_engine/capabilities.py) | 作者可声明能力注册表 |
| [engine/src/mud_engine/__main__.py](../../../engine/src/mud_engine/__main__.py) | `--pack` / `--validate` |
| [engine/scripts/verify_m3_pack_loop.py](../../../engine/scripts/verify_m3_pack_loop.py) | 人读转录闭环 |
| [engine/tests/test_m3_pack_loop.py](../../../engine/tests/test_m3_pack_loop.py) | 端到端锁 |
| [.scratch/m1-core-engine-skeleton/research/04-dsl-dynamic-rules.md](../../m1-core-engine-skeleton/research/04-dsl-dynamic-rules.md) | 声明式天花板、脚本层教训 |
| [docs/archive/xkx-arch/03-DSL-UGC与Agent协作.md](../../../docs/archive/xkx-arch/03-DSL-UGC与Agent协作.md) | 旧四层与校验模型（对照灵感） |
| [docs/archive/xkx-arch/_archive/_侠客行 MUD 架构拆解说明书/05-世界构建系统.md](../../../docs/archive/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/05-世界构建系统.md) | 区域目录组织 |
| [docs/archive/xkx-arch/_archive/_侠客行 MUD 架构拆解说明书/04-对象与继承体系.md](../../../docs/archive/xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/04-对象与继承体系.md) | Feature 混入 ↔ 能力组合 |

---

*本文件为 UGC 专家原始评审，供后续交叉对抗与综合稿引用；不代表项目最终裁决。*
