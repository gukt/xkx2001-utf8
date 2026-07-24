# Session notes：LPC 房间语义对照 → Polishing 候选（2026-07-23）

> 目的：收束本 session 对照《侠客行》房间/DSL 与当前 `mud_engine` 的差距，供下一 session
> `/grill-with-docs`（grilling + domain-modeling）拍板：**哪些进 polishing / 打磨抛光里程碑**，
> 哪些进 GAP 后置 / post-MVP，哪些明确不做。
>
> 背景：Pre-M4 三批已关；PROGRESS 下一步是 **M4 评估、不自动开 M4**。本笔记**不是** ADR，
> 也不是已拍板的 polishing scope——只是 grill 输入。
>
> 对照源：LPC 只读参考（如 `d/xixia/*`）；引擎权威：`docs/creator-contract-v0.md`、
> `docs/gap-ledger.md`、ADR-0010/0011/0012。
>
> **问答出处（本 Agent 窗口原始提问 + 答复摘要）**：  
> [session-qa-provenance-2026-07-23.md](session-qa-provenance-2026-07-23.md)  
> — 含 LPC/YAML 行级锚点、消费者文件、与候选 ID（A1…C15）对照；`/to-spec` / 续 grill 时先翻该文件再读本文件拍板规格。

## 下一 session 怎么开

1. 读：`PROGRESS.md` + **本文件** + [session-qa-provenance-2026-07-23.md](session-qa-provenance-2026-07-23.md) + `docs/gap-ledger.md` + `CONTEXT.md`
2. `/grill-with-docs` 或 `/to-spec`：矩阵与已拍板节以**本文件**为准；「当初为什么问 / 出处」以 **provenance** 为准
3. 拍板后：更新 GAP / 可选 ADR / CONTEXT 词条 / 开 `.scratch/<effort>/` 或并入 M4 评估结论
4. **不要**未 grill 就扩契约字段或改加载器

## 本 session 已澄清的「现状事实」（非待办）

| 话题 | 结论（引擎现状） |
|------|------------------|
| `resource/water` / `resource/grass` | 房间布尔资源标记；水：灌装/喂饮；草：坐骑自食。数值非储量，不耗尽。 |
| `set("resource", {water:1})` vs `resource/water` | dbase 路径等价；值只做真假。 |
| `no_clean_up` | MudOS 回收开关；`0` 允回收（常冗余）。 |
| NPC 挡路 `valid_leave` | 引擎 = 声明式 `block_exits`（模板在场挡向）；复杂逻辑 ≠ 扩 block_exits，走官方 hooks（ADR-0012）。UGC 禁 hooks。 |
| `invalid_startroom` | quit 时禁止存起点 → 强制客店；引擎未对齐（若要 polishing 单列）。 |
| `cost` / `terrain` | **已支持** YAML； chiefly **骑乘** ability + 坐骑精力。**未**做 LPC 式步行扣玩家 jingli。 |
| `eat` / `drink` / 液体 | GAP **未支持/后置**；Consumable 占位；Pre-M4 保真 OOS。 |
| `sleep_room` / `no_fight` / `hotel` | LPC：可睡+禁练功 / 禁战 / 付费住宿。引擎：`no_fight` 已有；`no_sleep_room` inert；无 sleep/hotel。 |
| 随机 `objects` 三选一（落日林） | LPC `create` 时 random；引擎 **无** 随机 objects 表（有出口 `random_of`）。 |
| 进房刷马贼（土门子） | 按背包 value 标记 + 概率刷；近 `bandit_ambush`，**无**贵重物条件。 |
| 出口简写 `south: room_key` | **已支持**；dict 留给门/别名/`random_of`。 |
| 风景 details 括号 id | Pre-M4 **刻意不做** `石狮(shi shi)` 语法；键名可 look。着色用 `<c:name>`（ADR-0011）。 |
| 出口方位中文 aliases | **无**内置 东↔east；须手写或接受英文/`nsew`。 |
| `go 武庙` 地名 | 只能挂**出口** aliases；挂目标房 `aliases` **不能**导航（go 只匹配当前出口表）。 |
| `objects` 跨目录路径引用 | **不支持**；同文件扁平模板键。GAP 已有「多文件/大世界树」。 |
| 局部天气 + 父级回退 | **不支持**；`outdoors`=bool；Nature **World 单例**。 |
| 条件 DSL | 共用受限 AST：`entry_guard` / `day_shop` / `learn_condition` / NPC `when`；查询面见 session 内说明。 |

### 条件 DSL 查询面速查（接入点）

| 接入点 | YAML | 上下文 |
|--------|------|--------|
| 进房门禁 | `rooms.*.entry_guard` | 玩家 EntityGateContext |
| 日间店 | `day_shop: true` → `is_day` | 同上 |
| 学艺 | `skills.*.learn_condition` | 同上 |
| NPC 行为 | `behaviors[].when` | 多为 Nature（昼夜/雨） |

可用：`predicate`（is_night/is_day/is_raining/is_wielding_edged_weapon）、`field`+`value`（phase/faction_id/gender/has_faction/属性）、`gte`、`and`/`or`/`not`。无背包任意物、任务旗标、局部天气等。

## Polishing 候选清单（供 grill 逐项拍板）

> 标签建议：`P0-polish`（体验/契约打磨） / `P1-engine-gap`（能力缺口） / `defer` / `wontfix`。  
> grill 时每项问：不做是否阻塞题材包创作？是否原语膨胀？是否官方钩子即可？是否 M4 范围？

### A. DSL / 创作体验打磨（偏 polishing）

1. **标准方位中文默认同义词**  
   - 诉求：`east` 等不必再写 `aliases: [东]`；`northeast`/`up`/`down` 等同理。  
   - 风险：与出口绰号 aliases 冲突时的优先级；look 出口列表是否显示中文。

2. **邻房名 / 目标房 aliases 导航**（`go 武庙`）  
   - 诉求：地名写在目标房一次，邻接出口可解析；多出口歧义策略。  
   - 与「出口绰号」正交——grill 是否拆成两原语。

3. **官方场景 YAML 简写规范化**  
   - 出口裸字符串、去掉冗余方位 aliases（依赖 A1 后）、`m1`/`m2` 范本一致性。  
   - 纯内容/文档，无引擎语义变更时可并入 polishing。

4. **风景/实体展示：括号拼音或 id（彩色）**  
   - 与 Pre-M4「不做括号 id 语法」冲突——grill 是 **改判**、仅 long 手写规范、还是 `wontfix`。  
   - 若只做「look 列表展示名(alias)」而不做解析，是否算 polishing。

5. **`block_exits` 自定义拒走文案**（可选 deny_message）  
   - 对齐 LPC「一言不发地挡在你前面」；仍不扩展条件树。

### B. 已有能力的语义补齐（polish vs 新能力边界模糊）

6. **步行 `cost` → 玩家精力**  
   - LPC：`jingli -= cost*2`。引擎现仅骑乘。  
   - grill：算 polishing 保真还是玩法新特性？昏迷阈值？

7. **`invalid_startroom` / 存档出生点策略**  
   - 渡船等临时空间；依赖存档/登录模型成熟度（ADR-0008 频道登录非停机）。

8. **客店三件套：`sleep` + `sleep_room` + `hotel`/`rent_paid`**  
   - 与液体同档「生活闭环」；体积可能超过 polishing。

9. **条件 DSL 文档化 + 查询面小扩**（若 polishing 只做文档/范例）  
   - 现状字段见上表。扩背包/任务旗标 → 多半不是 polish。

### C. 明确偏「新能力 / GAP」（默认候选 defer，除非 grill 升格）

10. **液体灌装 / drink / 醉酒 / eat** — GAP 已后置。  
11. **随机 objects 表**（落日林式）— 与出口 `random_of` 不同。  
12. **进房刷怪条件扩展**（贵重物/标记）— 超 `bandit_ambush`。  
13. **多文件 / 路径引用 templates**（跨层级 npc/items）— GAP「多文件/大世界树」；用户希望未来做。  
14. **局部/区域天气 + 父级继承** — 需 region 树；与全局 Nature 模型冲突需 ADR。  
15. **复杂挡路 = valid_leave 脚本** — 官方 hooks，不进 UGC DSL；勿原语膨胀。

### D. 本 session 用户已表达「希望未来做」的显式意愿

- 路径引用跨层级 npc/items（→ C13）  
- （隐含）方位默认中文、地名 go（→ A1/A2）若进入 polishing 需 grill 确认优先级  
- 局部天气继承（→ C14）— 更可能 defer + ADR

## 建议的 grill 决策矩阵（本 session 填）

> **桶（2026-07-23 grill 拍板）**：`Polishing` / `GAP·后置` / `post-MVP` / `wontfix`。  
> **无「进 M4」列**——M4 = 商业化数据模型，与本清单正交；M4 评估另开。  
> Polishing = M4 前可选命名 effort（见 CONTEXT），非新 M 号。  
> **准入**：宽（对照 LPC/创作摩擦即可讨论）；**不确定时问架构师**。  
> **纳入即承诺**：标 `Polishing` 的项本阶段必须实现（可拆细票，不得再踢出本阶段）。

| ID | 候选 | Polishing | GAP·后置 | post-MVP | Wontfix | 备注 |
|----|------|:---------:|:--------:|:--------:|:------:|------|
| A1 | 方位中文默认 | ✓ | | | | 见「出口导航」；look=中英并列(3) |
| A2 | go 邻房名 | ✓ | | | | 并入目标房 name/aliases 回退 |
| A3 | YAML 简写规范 | ✓ | | | | 随 A1/A2 清官方范本+文档 |
| A4 | 括号 id/展示 | ✓ | | | | **K2+U**：details 英键+aliases；long 纯文本`名(id)`；扫描/归一；无`<d:>`；纳入即做 |
| A5 | block_exits 文案 | ✓ | | | | deny_message；纳入即做 |
| B6 | 步行 cost 精力 | ✓ | | | | **F1**：扣 cost×2；不足拒走；纳入即做 |
| B7 | invalid_startroom | | ✓ | | | GAP·后置 |
| B8 | sleep/hotel | ✓ | | | | 客店三件套；纳入即做 |
| B9 | 条件 DSL 文档 | ✓ | | | | **D**：仅文档+范例，不扩查询面；纳入即做 |
| C10 | 液体/eat/drink | ✓ | | | | 升格 Polishing；纳入即做 |
| C11 | 随机 objects | ✓ | | | | 纳入即做；抽次时机落地时钉 |
| C12 | 刷怪条件扩展 | ✓ | | | | **P+hooks**：官方钩子/参数实现贵重物等；**不**扩 DSL 原语；纳入即做 |
| C13 | 路径引用 templates | ✓ | | | | 多文件/路径引用；纳入即做 |
| C14 | 局部天气继承 | ✓ | | | | 升格 Polishing；需 ADR；纳入即做 |
| C15 | valid_leave 脚本化 | | ✓ | | | 现有 hooks+block_exits；不另扩 |

## Grill 已拍板：出口导航（A1 + A2 合并语义）（2026-07-23）

> 归属：**Polishing**（纳入即做）。下列为架构师口述规格的完整记录；落地时写进契约 / 解析器，未 grill 完前勿改加载器。

### 目标体验（对齐侠客行「看起来」）

对方向键 `east` 的出口，玩家以下输入均应能走（在该向出口存在且可通时）：

| 形式 | 示例 |
|------|------|
| `go` + 英文全写 | `go east` |
| `go` + 中文方位 | `go 东` |
| 无 `go` 的英文全写 | `east` |
| 无 `go` 的英文简写 | `e` |
| 无 `go` 的中文方位 | **否**（2026-07-23 **改判 N**：裸 `东` / `上` 不合法，须 `go 东` / `go 上`） |

`up` / `down` 同理：`go up` / `go 上`；裸 `u` / `d` 合法；裸 `上` / `下` 不合法。

YAML **不必**为标准方位手写 `aliases: [东]`；由引擎按方向键挂**内置默认别名**。

### 内置方向同义词表（方向键 → 默认可解析名）

Canonical 出口键仍为英文（`north` / `northeast` / …）。每个方向键自带默认别名集合（含自身英文全写、英文简写、中文）。创作时可不写出口 `aliases`。

| 方向键 | 英文简写 | 中文（默认） |
|--------|----------|--------------|
| `north` | `n` | `北` |
| `south` | `s` | `南` |
| `east` | `e` | `东` |
| `west` | `w` | `西` |
| `northeast` | `ne` | `东北` |
| `northwest` | `nw` | `西北` |
| `southeast` | `se` | `东南` |
| `southwest` | `sw` | `西南` |
| `up` | `u` | `上` |
| `down` | `d` | `下` |

（若引擎另有 `in` / `out` 等，本批是否纳入内置表——待实现前再钉，默认本表十向。）

现状对照：`parsing.DIRECTION_SHORTCUTS` 仅 `n/s/e/w`；无中文、无 `ne`/`u`、无裸全写 `east`。

### 别名嵌套（出口 → 目标房）——原 A2 并入

解析某个「怎么走」的 token 时，对**当前房间每一条出口**，候选别名按层合并（**先出口、后目标房、再方向内置**）：

1. **出口自身** `exits.<dir>.aliases`（若有）  
2. **目标房间** `rooms.<target>.name` **与** `rooms.<target>.aliases`（2026-07-23 拍板：**N**——二者都参与 `go` 回退）  
3. **该方向键的内置同义词**（上表）

因此推荐写法从：

```yaml
exits:
  north:
    target: secret_tunnel
    aliases: [秘道, 北]   # 旧：方位与绰号都写在出口上
```

改为：

```yaml
rooms:
  secret_tunnel:
    name: 秘道
    aliases: [秘道]        # 地名/绰号定义在目标房一次
    # ...
  here:
    exits:
      north: secret_tunnel # 或 mapping 且可不写 aliases
      # 若只要错别字/额外绰号，仍可出口级补：
      # north: { target: secret_tunnel, aliases: [密道] }
```

**验收示例**（出口 `north → secret_tunnel`，房 `name`/`aliases` 含 `秘道`，出口 aliases 另含 `密道`）：

- `go 密道`（出口 aliases）
- `go 秘道`（目标房 name/aliases）
- `go north` / `north` / `n` / `go 北`（方向键 + 内置）
- **不合法**：裸 `秘道` / 裸 `武庙` / 裸 `东`（中文地名与中文方位均须带 `go`；2026-07-23 拍板 **G**）

### 与旧「look 显示 1/2/3」问题的关系

**已拍板 3**（2026-07-23）：`look` 出口列表 **中英并列**，示意 `东(east)、北(north)`（有门仍附「（关）」/「（锁）」等既有后缀）。解析规则不变。

### 创作契约含义（落地时回写）

- 出口 `aliases`：**可选**；用于出口级绰号 / 错别字，不再承担「标准中文方位」义务。  
- 房间 `aliases`：除实体 look/称呼外，**还参与邻接 `go` 导航回退**（本决策新增语义）。  
- 标准方位中文 / `ne`/`u` 等：引擎内置，不进每房 YAML。

### 待架构师确认（记录时发现的歧义）

1. ~~斜向中文~~ **已拍板 C**：按英文中文释义——`southeast`/`se`↔东南，`southwest`/`sw`↔西南。  
2. ~~无 `go` 时裸中文方位~~ **改判 N**（原 Y）：中文须 `go 东`；仅英文全写/简写可裸输入。  
3. ~~目标房回退是否包含房间 `name`？~~ **已拍板 N**：`name` + `aliases` 都回退。  
4. ~~多出口歧义~~ **已拍板 A**：命中多出口 → 现有 `Ambiguous`（列候选、要求消歧）。  
5. ~~A2 是否并入~~ **已并入**本决策且标 Polishing。  
6. ~~中文地名裸输入~~ **已拍板 G**：仅 `go 武庙`；裸 `武庙` 不合法（与中文方位一致）。  
7. ~~`look` 出口列表~~ **已拍板 3**：中英并列 `东(east)`。

## Grill 已拍板：房间风景 details（A4）（2026-07-23）

> 归属：**Polishing**（纳入即做）。部分修正 Pre-M4「仅键→字符串、不做括号语法」——**仍不**从 long 正文解析 `石狮(shi shi)` 登记别名；改为结构化 `details` + **生成**展示。

### 键模型 **K2**

```yaml
details:
  shi_shi:
    text: 一对<c:yellow>石狮</c>蹲在旗杆两侧…
    aliases: [石狮, "shi shi", ss]
```

| 规则 | 约定 |
|------|------|
| **键** | 无空格英文 id（`shi_shi`）；**不是**中文、**不是**带空格拼音 |
| **text** | 风景描述；语义色写在 text 内（`<c:name>…</c>`） |
| **aliases** | `look` 匹配用；含中文主名、可含空格的拼音、短码 |
| **匹配** | 精确匹配键或任一 alias（不做中文分词）；`look 石狮` / `look shi shi` / `look ss` / `look shi_shi` |
| **旧写法** | `details: { 石狮: 一段话 }` 兼容策略落地时再钉（迁移官方包或双轨加载） |

颜色：加在 `text`（及若手写 long 时的 long）；**不**给 aliases 着色。

### long 展示与可点 **U**（2026-07-23 拍板，取代对 T/B 的推荐）

- 作者在 `long`（等可见文本）里**手写纯文本**：`石狮(shi_shi)` 或 `石狮(shi shi)` 均可；习惯上括号内写 **`shi shi`（空格）**。
- **不**引入 `<d:…>` / `{{…}}` 标签（对创作者与 AI 更友好）。
- 引擎对 `details`：**键 + 全部 aliases** 归一成同一条风景的多个 look 名（多 key 命中同一 item）。
- **look target 归一**：帮助文档提醒——括号里常见空格写法；玩家 `look` 时可将空格换成 `_`；**连字符 `-` 亦参与 target 解析归一**（与键 `shi_shi` 等同视，细节下一问钉死）。
- 引擎可**扫描**可见文本中的 `名(id)` 形态，用于高亮 / Web 可点等；**不**靠独特标签。

> **已钉（2026-07-23）**  
> - 扫描安全阀 **S1**：仅当 `名(id)` 能解析到**本房已声明**的某条 `details` 时才高亮/可点；未见登记则当纯文本。  
> - **嵌套 look**：`details.*.text` 内同样可写 `石球(shi_qiu)`；内嵌可 look 项也必须在**同一房间 `details` 扁平登记**（不是 text 内联子树）。对 text 做与 long 相同的 S1 扫描。  
> - **已钉**：`shi shi` = `shi_shi` = `shi-shi` = `shishi`（分隔符空格/`_`/`-` 与全粘连同一骨架；**N1**）。大小写策略落地时再钉（建议 look id 大小写不敏感）。

### 明确不做（本项）

- 从 `long` 字符串里 **解析** `名(id)` 并自动登记 aliases（真·括号语法解析）  
- 用带空格字符串当 details **主键**

## Grill 收口摘要（2026-07-23 · **共享理解已确认**）

### 治理

- Polishing = M4 前命名 effort（非新 M 号、非 M4 子集）
- 决策桶无「进 M4」；准入宽；**纳入即承诺实现**（可拆票）

### Polishing ✓（13 项）

A1+A2 出口导航 · A3 YAML 简写 · A4 details(K2+U+S1+N1) · A5 deny_message · B6 步行精力(F1) · B8 客店 · B9 条件 DSL 仅文档 · C10 液体/eat/drink · C11 随机 objects · C12 刷怪条件(hooks only) · C13 多文件路径引用 · C14 局部天气(需 ADR)

### GAP·后置（2 项）

B7 `invalid_startroom` · C15 额外 valid_leave 脚本化

### 下一步（已确认，待下令执行）

1. `/to-spec` 或开 `.scratch/polishing-…/` effort 底稿  
2. 回写 `docs/gap-ledger.md`（升格项与 B7/C15）  
3. C14 先 ADR 再实现  
4. **不**自动开 M4

## 相关代码 / 文档锚点

- **问答出处**：[session-qa-provenance-2026-07-23.md](session-qa-provenance-2026-07-23.md)（Q1–Q15 ↔ LPC/YAML ↔ 候选 ID）
- 契约：`docs/creator-contract-v0.md`（exits 字符串\|映射、details、outdoors、entry_guard、block_exits）
- GAP：`docs/gap-ledger.md`（液体；多文件场景；剧情门；运行时机关）
- 条件：`engine/src/mud_engine/ai.py` `condition_from_data`；`entity_gate.py`
- 出口解析：`scene_loader._exit_target`（已支持裸字符串）
- 方位简写：`parsing.DIRECTION_SHORTCUTS`（仅 n/s/e/w）——**A1 拍板后将扩展**，见上文「出口导航」
- Nature：`engine/src/mud_engine/nature.py`（World 单例）
- 风景决策：`.scratch/pre-m4-engine-room-fidelity/`（旧：不做括号 id）——**A4 拍板部分修正**，见上文「房间风景 details」
- 范本：`engine/data/m2_mvp_scene.yaml`（少林 entry_guard、翰林 block_exits、旗杆语义色）
- 外部参照（可选）：`.scratch/research/02-evennia/vs-mud-engine-2026-07-23.md`

## 非目标（本笔记不主张改）

- LPC 行为等价验证（ADR-0001）
- UGC 可写 hooks / RestrictedPython 房间脚本（ADR-0012）
- 未 grill 先改 ADR-0010 放置模型
