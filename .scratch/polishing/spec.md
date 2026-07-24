Status: ready-for-agent

# Polishing（打磨抛光）：LPC 房间语义对照拍板 13 项落地

> 依据：[CLAUDE.md](../../CLAUDE.md)「架构不变量」第 8 条（Polishing 是 M3 停机加固之后、M4 之前的可选命名 effort，非新 M 号）；[CONTEXT.md](../../CONTEXT.md)「Polishing（打磨抛光）」「出口导航别名」「房间风景」等词条；[PROGRESS.md](../../PROGRESS.md) Next Up §1；grill 权威拍板 [.scratch/polishing-candidate-review/session-notes-2026-07-23.md](../polishing-candidate-review/session-notes-2026-07-23.md)；问答出处 [.scratch/polishing-candidate-review/session-qa-provenance-2026-07-23.md](../polishing-candidate-review/session-qa-provenance-2026-07-23.md)；[docs/gap-ledger.md](../../docs/gap-ledger.md)；[docs/creator-contract-v0.md](../../docs/creator-contract-v0.md)；[ADR-0001](../../docs/adr/0001-no-lpc-behavior-equivalence-verification.md)（不做行为等价）、[ADR-0005](../../docs/adr/0005-m3-ugc-loop-creation-surface.md)/[ADR-0006](../../docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md)（UGC 创作面边界）、[ADR-0007](../../docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)（Effect 生命周期仍冻结）、[ADR-0009](../../docs/adr/0009-single-process-single-world.md)（单进程单 World）、[ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md)（房间中心 objects 放置）、[ADR-0011](../../docs/adr/0011-semantic-color-tokens.md)（语义色 token）、[ADR-0012](../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md)（可信房间钩子 + 窄 ctx）。

**候选 ID 对照表**（沿用 grill 拍板编号，`/to-tickets` 拆票时复用）：

| ID | 候选 | 一句话 |
|----|------|--------|
| A1+A2 | 出口导航别名 | 内置十向中英同义词 + 出口/目标房 aliases 分层回退 |
| A3 | YAML 简写规范化 | 官方范本随 A1+A2 落地后清理冗余方位 `aliases` |
| A4 | 房间风景 details 升级 | 英键 `details` + `text`/`aliases` + `名(id)` 扫描高亮（K2+U+S1+N1） |
| A5 | `block_exits` 拒走文案 | 可选 `deny_message` |
| B6 | 步行 `cost` 精力 | 步行按地形 `cost` 扣玩家精力，不足拒走 |
| B8 | 客店三件套 | `sleep` + `sleep_room`/`no_sleep_room` + `hotel`/`rent_paid` |
| B9 | 条件 DSL 文档化 | 仅补文档 + 范例，不扩查询面 |
| C10 | 液体 / eat / drink | 房间 `resource` 布尔资源 + 灌装/饮用/进食一次性效果 |
| C11 | 随机 objects 表 | 补刷时按候选组随机抽签（区别于加载期一次性 `random_of` 出口） |
| C12 | 刷怪条件扩展 | 贵重物等条件走官方 hooks 参数化，不扩 DSL 原语 |
| C13 | 多文件路径引用 templates | 跨文件 `items`/`npcs` 模板引用 |
| C14 | 局部天气继承 | 需先出 ADR，本 spec 只锁需求边界 |

## Problem Statement

2026-07-23 的 LPC 房间语义对照 session（`d/xixia/*` 只读参考 vs 当前 `openmud`）找出了一批创作者/玩家能感知到的摩擦点和空白：出口只能用英文简写或手写中文别名，导航体验比 LPC 生硬；房间风景没有统一的「括号展示名」心智，玄机跟《侠客行》玩家习惯脱节；NPC 挡路只有一句固定文案；步行不消耗玩家精力（骑乘却会），策略深度打折；没有客店/睡觉/液体/进食这些「生活闭环」原语，声明式内容包做不出对应体验；进房刷怪写不出「背包带贵重物才刷」这类条件；场景内容仍锁死单文件，无法引用跨文件模板；房间天气永远是全局一套，做不出「山顶终年多雾」。这些缺口此前散落在 GAP 台账「未支持/后置」里，或完全没有被记录。

这批缺口已经过两轮 `/grill-with-docs`（本文档目录 `session-notes-2026-07-23.md` + `session-qa-provenance-2026-07-23.md`）逐项拍板：13 项（A1+A2、A3、A4、A5、B6、B8、B9、C10、C11、C12、C13、C14）纳入一个新命名 effort「Polishing（打磨抛光）」，**纳入即承诺本阶段实现**（可拆细票，不得以体量为由后置出本阶段）；另 2 项（B7 `invalid_startroom`、C15 `valid_leave` 脚本化）留在 GAP·后置，不进本 effort。

当前缺的是：这 13 项还只是 grill 拍板的规格要点，散落在 session-notes/provenance 两份文档里，没有整理成一份可交给 `/to-tickets` → `/implement` 的完整规格；`docs/gap-ledger.md`、`docs/creator-contract-v0.md`、`CONTEXT.md` 也还没有按拍板结果回写落地细节（部分词条如「出口导航别名」「房间风景」已提前写入 CONTEXT，其余词条待实现时补）。

## Solution

开一个新命名 effort `.scratch/polishing/`（与三批已关闭的 Pre-M4 effort 同级、非新 M 号、非 M4 子集），把 grill 拍板的 13 项转成本 spec，覆盖：出口导航（内置方向同义词 + 别名分层回退）、房间风景 details 结构升级、`block_exits` 自定义拒走文案、步行精力消耗、客店三件套（睡觉/睡房/付费住宿）、条件 DSL 文档化、液体/进食一次性效果、补刷期随机 objects 候选组、刷怪条件通过官方 hooks 参数化扩展、跨文件模板引用、局部天气继承的需求边界（具体数据模型留给独立 ADR）。所有新增字段延续 `docs/creator-contract-v0.md`「只做加法」承诺；不改动已冻结的放置模型（ADR-0010）、UGC 禁 hooks 边界（ADR-0012）、Effect 停机范围（ADR-0007）。`/to-spec` 之后按 ID 拆成 `.scratch/polishing/issues/NN-*.md` 细票，C14 的第一张票必须是「先出 ADR」而非实现票。

## User Stories

### A1+A2 出口导航别名

1. 作为题材包创作者，我希望标准方位（`east`/`up` 等十向）不必在每个出口手写 `aliases: [东]`，以便少写重复样板 YAML。
2. 作为题材包创作者，我希望把一个地名（如「武庙」）只在目标房间的 `name`/`aliases` 里定义一次，邻接出口就能被 `go 武庙` 命中，以便不用在每条通往该房间的出口上重复抄写地名。
3. 作为玩家，我希望输入 `go east`、`east`、`e`、`go 东` 都能走同一条向东的出口，以便按习惯的任意一种方式表达方向。
4. 作为玩家，我希望裸输入中文方位（`东`）或裸输入中文地名（`武庙`）被拒绝、必须带 `go`，以便中文自然语言输入不会与聊天/其他命令产生歧义。
5. 作为玩家，我希望 `look` 的出口列表用中英并列展示（如 `东(east)`），以便同时看到可用的英文简写与中文习惯说法。
6. 作为玩家，我希望当某个方向候选名字同时匹配多条出口时得到 `Ambiguous` 提示并列出候选，以便消歧后再选。
7. 作为题材包创作者，我希望斜向方位的中文按英文释义对应（`southeast`↔东南），以便创作时不必猜测方位命名规则。

### A3 YAML 简写规范化

8. 作为题材包创作者，我希望官方范本（`m1_default_scene.yaml`/`m2_mvp_scene.yaml` 等）在 A1+A2 落地后去掉不再必要的标准方位 `aliases`，以便把范本当作「当前推荐写法」的参考直接抄。
9. 作为新加入的题材包创作者，我希望场景创作文档同步说明「标准方位不必手写、地名写在目标房」的新推荐写法，以便第一次写 YAML 就用对写法而不是抄旧范本的冗余样板。

### A4 房间风景 details 升级

10. 作为题材包创作者，我希望 `details` 用无空格英文 id 做键、`text`/`aliases` 做值，以便风景描述的匹配名（中文、带空格拼音、短码）和引擎内部键分开维护。
11. 作为题材包创作者，我希望在 `long`/`text` 里手写 `石狮(shi shi)` 这样的纯文本就能让「石狮」成为一个可 `look` 的风景，以便不用学习额外的标签语法。
12. 作为玩家，我希望 `look 石狮`、`look shi shi`、`look ss`、`look shi_shi`、`look shi-shi`、`look shishi` 都能命中同一条风景，以便不用记住某一种固定拼写。
13. 作为客户端/Web 前端开发者，我希望引擎能扫描可见文本里的 `名(id)` 形态并判断是否命中本房已注册的 details，以便只在真正可 look 的地方做高亮/可点，不误伤纯文本括号。
14. 作为题材包创作者，我希望 `details.*.text` 内嵌套的风景（如描述石狮时提到的「石球」）也能被 `look` 到，前提是它在同一房间 `details` 里被扁平注册，以便描述可以互相引用而不产生「文本里凭空冒出一个不可 look 的括号」。
15. 作为题材包创作者，我希望旧的「键 → 纯字符串」写法在迁移期仍有明确的兼容或迁移路径，以便不必在同一次 PR 里被迫改光全部官方范本。

### A5 `block_exits` 拒走文案

16. 作为题材包创作者，我希望给 `block_exits` 的某个方向声明自定义 `deny_message`，以便挡路 NPC 能说出符合场景氛围的台词而不是固定的「{名}挡住了{方向}方向的去路」。
17. 作为玩家，我希望没有自定义文案的挡路仍然显示现有默认提示，以便旧场景不必逐个补写文案也能正常运行。

### B6 步行 `cost` 精力

18. 作为玩家，我希望步行穿过地形较难的房间（`terrain.cost` 较高）比穿过平地更消耗精力，以便地形选择在不骑乘时也有策略意义。
19. 作为玩家，我希望精力不足以支付某次步行消耗时移动被拒绝并提示原因，而不是移动后精力变成负数或直接昏迷，以便我能提前判断该不该走这一步。
20. 作为题材包创作者，我希望这个消耗只影响玩家步行、不影响骑乘时坐骑精力扣减的既有规则，以便骑乘/步行两套消耗互不干扰。

### B8 客店三件套

21. 作为玩家，我希望在声明了 `sleep_room`（或未声明 `no_sleep_room` 的默认允许房间——具体极性以实现票钉死为准）的房间执行 `sleep`，以便恢复状态或推进剧情。
22. 作为玩家，我希望在声明 `hotel: true` 的房间，只有先向店家付钱（`rent_paid`）才能 `sleep`，以便体验「先付房钱再睡觉」的经济闭环。
23. 作为玩家，我希望离开客店房间后 `rent_paid` 状态被清除，以便不会「付一次钱、无限次回来睡」。
24. 作为题材包创作者，我希望睡房（`sleep_room`）默认禁止大多数练功类命令（如 `practice`），以便复刻「客店不能打坐练功」的场景规则而不必额外声明。

### B9 条件 DSL 文档化

25. 作为题材包创作者，我希望有一份文档把 `entry_guard`/`day_shop`/`learn_condition`/NPC `behaviors[].when` 四个接入点共用的条件 DSL（`predicate`/`field`+`value`/`gte`/`and`/`or`/`not`）讲清楚并配上真实范例，以便不用翻源码就能写出正确的门禁/学艺条件。
26. 作为题材包创作者，我希望文档明确标注「DSL 现在能表达什么、不能表达什么」（如不支持背包任意物、任务旗标、局部天气查询），以便不会浪费时间去尝试文档说明不支持的写法。

### C10 液体 / eat / drink

27. 作为玩家，我希望在声明了水资源的房间（如引擎既有事实「`resource/water`」布尔标记落地为房间字段）执行灌装类命令为水袋类物品加水，以便像 LPC 一样在河边/井边补给。
28. 作为玩家，我希望喝下装了水的容器物品能获得一次性效果（如补充部分精力），以便液体系统对玩法有实际作用而不是纯文案。
29. 作为玩家，我希望进食可食用物品（`Consumable`）能获得一次性效果并消耗掉该物品的剩余使用次数，以便干粮/食物类道具有实际用途。
30. 作为题材包创作者，我希望这批效果都是即时的一次性数值变化，不需要接入完整的 Effect 持续生命周期系统，以便不必等 Effect 系统完整落地就能用上液体/进食玩法。
31. 作为题材包创作者，我希望没有声明水资源的房间灌装会被拒绝并给出提示，以便「河边才能打水」这种地理限制能被声明式表达。

### C11 随机 objects 表

32. 作为题材包创作者，我希望一个房间的某个放置槏位能声明「候选模板组，每次补刷从中抽一个」（如落日林三选一的树枝/乌鸦/野兔/蛇），而不是「加载时只抽一次、永远固定」，以便复刻 LPC `reset()` 每次进入房间/补刷都可能变的随机放置效果。
33. 作为玩家，我希望同一个房间在不同游戏时段/多次补刷之间，随机放置槏位展示出不同的候选结果，以便重复探索该房间时仍有新鲜感。
34. 作为题材包创作者，我希望这个「补刷时随机候选组」与既有加载期一次性的出口 `random_of` 是两个正交概念，不会被混用或互相覆盖，以便我在文档/代码里能分清「出口随机」和「放置随机」。

### C12 刷怪条件扩展（官方 hooks 参数化）

35. 作为官方题材包作者，我希望能配置进房刷怪钩子（如 `bandit_ambush`）按「玩家背包非货币物品总价值 ≥ 阈值」这类条件决定是否触发概率刷怪，以便复刻土门子「贵重物才刷马贼」的场景设计。
36. 作为架构师，我希望这类条件通过给既有官方 hook 增加可选 `params`（如 `min_item_value`）实现，而不是往 `entry_guard`/条件 DSL 里新增查询面原语，以便不为单个玩法在通用 DSL 里堆一条只服务它的谓词。
37. 作为 UGC 创作者，我希望这批扩展仍然完全在官方钩子轨内，UGC 内容包依旧不能声明 `hooks`，以便信任边界（ADR-0012）不因为这次扩展被打破。

### C13 多文件路径引用 templates

38. 作为题材包创作者，我希望能在一个场景文件里引用另一个文件定义的 `items`/`npcs` 模板，以便把大世界拆成多个文件维护而不必把所有模板塞进同一个 `scene.yaml`。
39. 作为题材包创作者，我希望跨文件引用的模板 id 在合并后仍保持全局唯一校验，重复 id 会在加载期报错，以便尽早发现拼写冲突而不是运行时才发现指向了错的模板。
40. 作为内容包维护者，我希望文档明确这批多文件能力在官方轨、内容包轨（`manifest.yaml`）两条加载路径上分别是否可用，以便知道我的题材包该怎么组织目录结构。
41. 作为架构师，我希望这不是「引用任意路径的裸文件系统穿越」，而是一个受限、可校验、路径相对场景文件目录解析的机制，以便加载器行为可预测、可 `--validate`。

### C14 局部天气继承

42. 作为题材包创作者，我希望能让某个房间（如山顶寺庙、海上渡船）呈现和世界其他地方不同的天气/描述，而不必等所有房间共享同一个 `NatureState` 单例的相位与晴雨，以便地理特征能反映在环境描述上。
43. 作为架构师，我希望在实现前先有一份 ADR 说明这如何与既有「Nature 为 World 单例」「单进程单 World」（ADR-0009）架构不变量共存，以便这次扩展不会悄悄引入区域树/多实例状态而没有决策记录。
44. 作为玩家，我希望局部天气的影响范围明确（至少覆盖户外 `look` 描述与条件 DSL 里 `is_raining`/`is_night` 类谓词在该房间的取值），不会产生「隔壁房间天气不同却互相看得见对方广播」之类的怪异体验。

## Implementation Decisions

> 以下按 ID 分组；每组列模块/接口/schema 决策与已知的开放子决策（留给 `/to-tickets` 拆票或 `/implement` 时钉死，不阻塞本 spec 发布）。所有新增字段遵循 `docs/creator-contract-v0.md` 的「只做加法」承诺（新增顶层段 / 新增已知字段，不改义已冻结字段）。

### A1+A2 出口导航别名

- **模块**：`parsing.py`（`DIRECTION_SHORTCUTS` 扩容 + 新增裸英文全写识别）、`scene_loader.py`（出口/目标房别名合并解析）、`commands.py`（`_cmd_go` 复用同一套候选解析，`look` 出口展示改中英并列）。
- **规格权威**：完整规格已由另一窗口 grill 拍板并写入 [session-notes-2026-07-23.md](../polishing-candidate-review/session-notes-2026-07-23.md)「Grill 已拍板：出口导航」一节与 [CONTEXT.md](../../CONTEXT.md)「出口导航别名」词条，本 spec 不重复全文，只摘要要点：
  - Canonical 出口键仍为英文十向（`north`/`south`/`east`/`west`/`northeast`/`northwest`/`southeast`/`southwest`/`up`/`down`）；每个方向键自带内置默认别名集合（英文全写、英文简写、中文），创作者不必手写。
  - 解析某个「怎么走」token 时按层合并候选：① 出口自身 `aliases` → ② 目标房间 `name` 与 `aliases` → ③ 该方向键内置同义词。
  - 合法输入形式：`go` + 英文全写、`go` + 中文方位、裸英文全写、裸英文简写；**不合法**：裸中文方位、裸中文地名（均须带 `go`）。
  - 多出口同名命中 → 走既有 `Ambiguous`（列候选、要求消歧）。
  - `look` 出口列表中英并列展示（如 `东(east)`），有门仍附既有「（关）」/「（锁）」后缀。
- **开放子决策**（拆票时钉）：内置表是否收录 `in`/`out`（session-notes 明确留白，本批默认十向）；内置别名与出口/目标房自定义别名重名时的展示去重策略。

### A3 YAML 简写规范化

- **模块**：仅内容变更，无引擎语义代码改动——`engine/data/m1_default_scene.yaml`、`engine/data/m2_mvp_scene.yaml`（及后续 `xingxiu_mechanics.yaml` 等官方范本）清理因 A1+A2 落地而冗余的标准方位 `aliases`；`docs/scene-authoring-guide.md` 补充「标准方位不必手写、地名写在目标房一次」的推荐写法段落。
- **依赖**：必须排在 A1+A2 实现完成之后（否则清理范本会破坏当前导航行为）。
- **验收**：现有场景相关测试（`test_scene_yangzhou_hub.py`、`test_scene_shaolin.py`、`test_verify_m2_matrices.py` 等）在清理后仍全绿，且不新增依赖已删别名的断言。

### A4 房间风景 details 升级

- **模块**：`components.py`（`RoomDetails` 从 `dict[str, str]` 升级为 `dict[str, DetailEntry]`，`DetailEntry` 含 `text: str` + `aliases: tuple[str, ...]`）、`scene_loader.py`（`details` 段解析升级 + 旧写法兼容/迁移策略）、`commands.py`（`look` 匹配逻辑扩展为「键或任一 alias 精确匹配（不做中文分词），且做 N1 分隔符归一：空格/`_`/`-`/全粘连视为同一骨架」）、新增文本扫描辅助（供 `long`/`details.*.text` 里 `名(id)` 形态按 S1 规则判定是否命中本房已注册 details）。
- **规格权威**：完整规格已拍板并写入 session-notes「Grill 已拍板：房间风景 details（A4）」一节与 CONTEXT「房间风景」词条，摘要：
  - 键模型 **K2**：`details.<id>` 为无空格英文 id；值为 `{text, aliases}`；颜色写在 `text` 内（`<c:name>…</c>`），**不给 aliases 着色**。
  - 展示 **U**：作者在 `long`/`text` 里手写纯文本 `石狮(shi_shi)` 或 `石狮(shi shi)`；**不引入** `<d:…>` 等标签。
  - 归一 **N1**：`shi shi` = `shi_shi` = `shi-shi` = `shishi`（分隔符空格/`_`/`-`/全粘连同一骨架）；大小写策略建议 look id 大小写不敏感（留给实现票钉死）。
  - 安全阀 **S1**：仅当 `名(id)` 能解析到本房已声明的某条 `details` 时才高亮/可点；未登记则当纯文本，不误伤。
  - 嵌套 look：`details.*.text` 内同样可写 `石球(shi_qiu)`，但嵌套目标必须在同一房间 `details` **扁平**登记（不是 text 内联子树）；对 `text` 做与 `long` 相同的 S1 扫描。
  - **明确不做**：从 `long` 字符串里自动解析 `名(id)` 并**登记** aliases（真·括号语法解析）；用带空格字符串当 details 主键。
- **开放子决策**：旧写法 `details: { 石狮: 一段话 }`（键→纯字符串）的兼容策略——双轨加载（旧格式自动转 `{text: 值, aliases: [键]}`）或强制迁移官方范本，落地时钉死；大小写敏感性落地时钉死。

### A5 `block_exits` 拒走文案

- **模块**：`components.py`（`BlockExits.by_direction` 值从裸模板键字符串升级为携带可选 `deny_message` 的结构，如 `dict[str, BlockEntry]`，`BlockEntry` 含 `npc_template: str` + `deny_message: str | None`）、`scene_loader.py`（`block_exits: { <dir>: { npc: <key>, deny_message?: <str> } }` 解析）、`commands.py`（`_cmd_go` 挡向分支：有 `deny_message` 用之，否则回退现有默认文案 `{名}挡住了{方向}方向的去路。`）。
- **契约新增字段**：`rooms.*.block_exits.<dir>.deny_message`（可选字符串）。
- **兼容**：不声明 `deny_message` 的既有场景行为不变（默认文案）。

### B6 步行 `cost` 精力

- **模块**：`commands.py`（`_cmd_go` 非骑乘分支）、复用既有 `Terrain.cost` 与玩家 `Vitals`（`jingli_current`/`jingli_max`）组件，不新增契约字段。
- **规则**（provenance Q5 + 矩阵 F1）：步行按 `cost * 2` 扣玩家 `jingli_current`（`cost` 缺省地形按 1 计，与骑乘分支的缺省一致）；**精力不足则拒绝移动**（不产生「移动后精力为负」或「步行导致玩家昏迷」——昏迷路径仍只走战斗/既有 Unconscious 触发点，不因步行引入新的昏迷来源）。
- **与骑乘的关系**：本规则只影响玩家步行分支；骑乘时坐骑精力扣减规则（`MOUNT_JINGLI_PER_TERRAIN_COST`）不变、互不干扰——即当 `Riding` 组件存在时走既有骑乘分支，不叠加步行消耗。
- **开放子决策**：拒走提示文案措辞；`jingli_current` 恰好等于所需消耗时是否放行（建议放行，扣至 0，不放行需消耗后精力 `>0`——按现有骑乘分支「扣到 0 才摔」的对称性，落地时钉死）。

### B8 客店三件套

- **模块**：`components.py`（新增 `HotelRoom`/`RentState` 或等价组件表达 `hotel: true` + `rent_paid` 状态）、`scene_loader.py`（房间字段 `hotel: bool`；`sleep_room`/`no_sleep_room` 极性沿用既有 `RoomFlags.no_sleep_room`，是否新增正向 `sleep_room` 字段留待实现票钉死——见下）、`commands.py`（新增 `sleep` 命令：`no_sleep_room` 为真则拒绝；`hotel: true` 且未 `rent_paid` 则要求先付钱；`practice` 命令在睡房内的既有房间旗标拦截逻辑复用/对齐「藏书」词条同类模式）、事件订阅（离开客店房间清 `rent_paid`，复用既有 `on_leave_room` 事件点，不新增 hook 协议方法）。
- **契约新增字段**：`rooms.*.hotel`（布尔，默认 false）；付钱命令（如 `pay` 或复用既有 `shop`/`give` 机制向店家 NPC 交银两）触发 `rent_paid` 置真的具体动词，留待实现票钉死。
- **开放子决策**（provenance Q6，需在拆票 / 实现时钉死，本 spec 先列出候选而非预先拍死）：
  1. `sleep_room` 极性——沿用现有 `no_sleep_room`（默认允许睡、显式关闭）还是新增正向 `sleep_room: true`（默认不允许睡、显式开启，更贴近 LPC「非丐帮客店才能睡」的心智）？
  2. 付费动词——新增专门 `pay` 命令，还是复用既有交易/给钱路径？
  3. 睡房拦练功是否复用 `library` 词条「同房挂 `library` 即拦 `practice`」的既有模式（`RoomFlags`/`LibraryRoom` 已有先例），还是独立实现同等效果。
  - 以上三点在 `/to-tickets` 拆票文件里必须写明选定方案（不得留白进 `/implement`）。

### B9 条件 DSL 文档化

- **模块**：仅文档，无代码变更——`docs/creator-contract-v0.md` 新增「条件 DSL」一节（或独立 `docs/condition-dsl.md`，被 v0 引用），覆盖四个接入点（`rooms.*.entry_guard`、`day_shop` 派生的 `is_day`、`skills.*.learn_condition`、`npcs.*.behaviors[].when`）、可用语法（`predicate`：`is_night`/`is_day`/`is_raining`/`is_wielding_edged_weapon`；`field`+`value` 精确匹配（`phase`/`faction_id`/`gender`/`has_faction`/属性）；`gte`；`and`/`or`/`not` 组合）、每个接入点至少一个取自现有官方范本（如少林山门 `entry_guard`、打铁铺 `day_shop`、`luohan_quan.learn_condition`）的真实 YAML 片段。
- **明确不做**：不新增查询面字段（如背包任意物、任务旗标、局部天气查询）——文档需显式列出「现在不支持」清单，对齐 GAP 台账「条件 DSL」相关表述，避免创作者按文档摸索出不存在的写法。
- **可选测试**：文档里嵌入的 YAML 范例可用既有 `load_scene` seam 跑一次「能加载、条件求值符合预期」的验证测试，防文档漂移（非必需，实现票可自行决定是否加）。

### C10 液体 / eat / drink

- **模块**：`components.py`（房间新增 `RoomResources` 组件，字段至少含 `water: bool`，`grass: bool` 视既有骑乘/坐骑喂食逻辑是否已用等价字段决定是否复用或新增；物品侧复用既有 `Consumable`（`uses` 递减），液体容器物品新增可选字段如 `liquid_capacity`/`filled` 状态）、`scene_loader.py`（房间 `resource: { water?: bool, grass?: bool }` 字段解析；物品模板液体容器相关字段解析）、`commands.py`（新增 `fill`/`drink`/`eat` 命令动词）。
- **契约新增字段**：`rooms.*.resource.water`（布尔）、`rooms.*.resource.grass`（布尔，若坐骑既有喂食逻辑尚未消费该字段则一并接上，否则保持现状不动并在 GAP 台账注明）；物品侧液体容器字段（具体命名留实现票钉死，如 `liquid_container: true` + 灌装后置 `filled_liquid: <id>`）。
- **规则**：
  - `fill <容器>` 只在房间 `resource.water` 为真时成功，否则拒绝并提示（对齐 LPC 「河边/井边才能打水」）。
  - `drink <已灌装容器>` 产生一次性数值效果（如恢复部分 `jingli_current`，具体数值留实现票钉死作为可调参数，不阻塞 spec）并消耗该次灌装（容器变回未灌装态，或如为一次性水袋则消耗掉）。
  - `eat <consumable>` 产生一次性数值效果，并按既有 `Consumable.uses` 语义递减/耗尽销毁。
  - **不做**：醉酒/持续中毒/持续 buff 等任何跨 tick 的持续状态——这批效果全部是命令执行当次结算内的一次性数值变化，不接入、不模拟 Effect 完整生命周期（ADR-0007 停机范围不变）。
- **开放子决策**：液体容器数据形状（新组件 vs 复用 `Container` + `item_tags`）；具体恢复数值；`grass` 字段与坐骑既有喂食逻辑（`clone/horse` 对照的 jingli 恢复）是否需要打通——留实现票钉死。

### C11 随机 objects 表

- **模块**：`scene_loader.py`（房间 `objects` 某槏位值支持新形状 `{ random_of: [tpl_a, tpl_b, tpl_c], count?: <int> }`，与既有「模板键 → 数量」写法并存、只做加法）、`ai.py`（`spawn_scan`：补刷/初始生成该槏位时，从候选组按 rng 抽签选定具体模板后再创建实例，而不是在加载期一次性选定）。
- **与既有 `random_of` 出口的区别**（provenance Q7 + session-notes C11 备注「与出口 `random_of` 不同」）：出口 `random_of` 是**加载期**一次性选定、落地为普通 `to` 出口，此后固定；本项是**补刷期**（每次该槏位需要重新生成实例——初始生成或已销毁且 `respawn: true` 触发补刷时）重新抽签，可能选到不同模板。两者数据形状相似但求值时机不同，实现时不得共用同一段加载期代码路径悄悄改成运行时求值（会破坏出口 `random_of` 现有「加载期定死」的既有测试预期）。
- **契约新增字段**：`rooms.*.objects.<slot>` 支持 `{ random_of: [...], count?: int }` 形状（`count` 缺省 1）。
- **开放子决策**：抽签 rng 是否可复用 `load_scene(rng=...)` 已有的注入点做确定性测试，还是 `spawn_scan` 需要单独的 rng 注入参数（`test_spawner.py` 现有测试模式表明 `spawn_scan` 目前不接受 rng 参数，需评估是否要加）；同一槏位在多次补刷之间是否允许连续抽到同一模板（建议允许，纯独立抽签，不做「不放回」——落地时钉死）。

### C12 刷怪条件扩展（官方 hooks 参数化）

- **模块**：`room_hooks.py`（既有 `bandit_ambush` 一类刷怪钩子的 `on_enter`/`on_tick` 实现，读取 `RoomHookBinding.params` 里新增的可选条件参数，如 `min_item_value: <int>`；扫描触发实体背包非货币物品 `value` 总和/单件是否达到阈值，达到才进入既有概率刷怪判定）、无需改动 `ai.py` 条件求值器或 `conditions.py`。
- **规格边界**（session-notes C12「**P+hooks**：官方钩子/参数实现贵重物等；**不**扩 DSL 原语」+ 硬约束提醒）：
  - **只**在官方轨可信 hook 实现内部读取/判断背包价值等条件，通过 `hooks.params` 声明式传参（如 `hooks: { hook_id: bandit_ambush, params: { min_item_value: 10000 } }`）。
  - **不**往 `entry_guard`/`day_shop`/`learn_condition`/`behaviors[].when` 共用的条件 DSL（`conditions.py`/`ai.condition_from_data`）新增任何谓词或字段（如不新增 `has_item_value_gte`）。
  - UGC 内容包仍不能声明 `hooks`（ADR-0012 边界不变，本项只扩展官方钩子内部实现，不下放到 UGC）。
- **验收对照**：provenance Q8「土门子进房刷马贼」——背包非金钱物品 `value >= 10000` 才有概率触发刷怪，机制对齐但**不做行为等价验证**（ADR-0001），阈值/概率数值是本引擎自己的可调参数，不追求与 LPC 数值位等价。

### C13 多文件路径引用 templates

- **模块**：`scene_loader.py`（新增顶层段，如 `includes: [<relative_path>, ...]`，加载期在解析 `items`/`npcs`/`rooms` 之前先读取并合并被 include 文件里的 `items`/`npcs` 模板定义进当前场景的模板命名空间）、`pack.py`（内容包轨 `manifest.yaml` 场景是否允许 `includes`，以及路径解析基准目录——相对当前场景文件所在目录，不允许穿出包目录/仓库范围）。
- **契约新增字段**：场景 YAML 顶层新增可选段 `includes: [<path>, ...]`（相对当前文件路径的文件列表，仅贡献 `items`/`npcs` 模板，不贡献 `rooms`/`player`/其它段——避免多文件合并出「哪个文件定义了房间拓扑」的歧义）。
- **规则**：
  - 合并后模板 id（`items.*`/`npcs.*` 键）必须全局唯一；跨文件重复 id 视为加载错误（对齐 ADR-0010「同文件扁平模板键」的唯一性精神，只是把「同文件」放宽为「同一次合并后的命名空间」）。
  - 官方轨（无 `manifest.yaml`）与内容包轨（带 `manifest.yaml`）是否都允许 `includes`、`--pack --validate`/`--strict` 对 include 路径的校验规则（文件缺失/越权路径如何报错）——需在实现票里明确并各自补测试。
  - 本项**不**引入「引用任意路径的裸文件系统穿越」——路径解析限定在场景文件所在目录及其子目录内，越界路径加载失败。
- **开放子决策**：是否支持嵌套 include（A include B include C）；`--validate --strict` 下 include 文件本身的未消费字段是否同样报错（建议是，复用同一套已知字段校验）。

### C14 局部天气继承

- **模块**：**本 spec 不预先指定实现模块**——具体数据模型（房间级静态天气「贴纸」/ region 树 + 每 region 一个可选 `NatureState` 覆盖 / 其它方案）留给独立 ADR 决定。
- **前置阻塞**：`/to-tickets` 拆出的 C14 第一张票必须是「写 ADR」（而非实现票），ADR 需正面回答：
  1. 与 [ADR-0009](../../docs/adr/0009-single-process-single-world.md)「单进程单 World」的关系——局部天气是否意味着引入多个 `NatureState` 实例？若是，是否违反或需要收窄 ADR-0009？
  2. 与 `nature.py` 现有「`NatureState` 是 world 级纯内存态单例」设计注释的关系——是否改造为每 room/region 可覆盖，还是新增一层独立于 tick 推进的静态覆盖（不随时间/天气翻转变化，只是「这个房间描述永远长这样」）？
  3. 影响范围边界：至少覆盖户外 `look` 描述文案与条件 DSL 里 `is_raining`/`is_night` 类谓词在该房间求值时的取值；**不**引入跨房间气候传播、不引入需要额外调度的独立天气循环（除非 ADR 明确论证需要）。
  4. 回退语义：房间未声明局部覆盖时必须无条件回退到 world 单例 `NatureState`（对齐 provenance Q13「回退父级（如华山）」的诉求，具体是「回退到父级 region」还是「回退到 world 单例」由 ADR 定，但两级回退链不能丢，最终必须能回退到某个确定态，不能出现「无覆盖也无默认」的未定义态）。
- **本 spec 锁定的需求边界**（供 ADR 讨论时对齐，不是实现细节）：
  - 至少支持「某些房间/区域天气与 world 默认不同」这一诉求（如山顶终年多雾、渡船区域独立于城镇天气）。
  - 不要求做到「任意粒度、任意继承深度」的通用区域树——ADR 可以裁剪到「本效力只做一层房间覆盖，不做多级 region 继承」这种最小满足需求的形状，只要写清楚裁剪理由。
  - 不做局部天气对玩法数值的额外影响（移动/战斗/坐骑等）——本项只影响描述性文本与既有条件谓词读数，不新增天气→数值的映射（如「雨天移速降低」不在本项范围）。

## Testing Decisions

好的测试只验证外部可观察行为（玩家能看到的输出、`load_scene`/`load_pack` 能否成功及加载后组件形状），不验证内部实现细节（如某个私有辅助函数的中间返回值）。

**复用的既有 seam**（本仓库贯穿全部子系统的标准手法，13 项优先复用，不新增 seam 除非该项确实需要）：

- **S1 `execute_line`**（`openmud.parsing.execute_line`）：命令级黑盒测试，构造场景 YAML（或复用 `load_mvp_scene()` 官方范本）→ `load_scene` → 逐条 `execute_line` 断言输出文案/状态变化。适用于 A1+A2（导航输入形式矩阵）、A4（`look` 风景匹配矩阵）、A5（挡路文案）、B6（步行精力扣减/拒走）、B8（`sleep`/`hotel`/`rent_paid` 全流程）、C10（`fill`/`drink`/`eat`）、C12（刷怪触发条件）。Prior art：`test_room_details.py`、`test_doors.py`、`test_story_doors.py`、`test_day_shop.py`、`test_mount.py`。
- **S2 `load_scene`（契约字段消费）**：断言新字段被解析成组件而不是落进 `world.entity_extension_data(entity)`/`World.extension_data`（透传），以及非法形状（如同时写 `to` 与 `random_of`、`hotel` 与旧字段冲突等）加载失败并给出定位到场景文件的错误信息。适用于 A4/A5/B8/C10/C11/C13 的字段解析部分。Prior art：`test_room_details.py::TestRoomDetailsLoad`（`assert "details" not in extras` 模式）、`test_scene_loader.py`。
- **S3 `--pack --validate[--strict]` CLI**：适用于 C12（UGC 包声明 `hooks` 必须失败——复用既有 ADR-0012 边界测试模式）、C13（include 路径越界/文件缺失/内容包轨是否允许 include 的校验）。Prior art：`test_load_pack.py`、`test_pack_manifest.py`、`test_room_hooks.py` 里 UGC 边界相关用例。
- **S4 `ai.spawn_scan`**：C11 需要在补刷粒度（不止加载粒度）断言「多次触发补刷得到不同候选」，用注入的确定性 rng 或多次运行统计分布，不能只在 `load_scene` 一次性加载后断言（否则测不出「补刷时重新抽签」这个区别于出口 `random_of` 的核心行为）。Prior art：`test_spawner.py`（现有 `spawn_scan` 测试范式）。
- **S5 verify matrix 脚本 + pytest 封装（effort 收口用）**：参考 `scripts/verify_pre_m4_room_fidelity.py` + `test_verify_pre_m4_room_fidelity_matrix.py` 的「场景化步骤矩阵 + `all_scenarios()` + 单个 pytest 汇总断言」手法，本 effort 收口时建议同样产出 `scripts/verify_polishing.py` + `test_verify_polishing_matrix.py`，覆盖 13 项每项至少一条端到端场景步骤，防手测脚本与实现漂移。Prior art：`test_verify_pre_m4_room_fidelity_matrix.py`、`test_verify_pre_m4_xingxiu_matrix.py`、`test_verify_m2_matrices.py`。

**逐项测试落点提示**（拆票时细化，不是最终测试清单）：

- A1+A2/A3：`test_parsing.py`（方向解析单元）+ S1 全套导航矩阵（含 Ambiguous、裸中文拒绝）。
- A4：`test_room_details.py` 扩展（新形状、别名归一、S1 扫描高亮判定、嵌套 look）。
- A5：`test_doors.py`/`test_story_doors.py` 同目录新增 `deny_message` 用例。
- B6：`test_terrain.py`/新测试文件，覆盖精力足够/不足/恰好边界。
- B8：新测试文件（`test_hotel.py` 或并入 `test_room_flags.py`），覆盖 sleep 允许/拒绝、hotel 未付款拒绝、付款后允许、离房清状态。
- B9：文档 + 可选 `test_conditions.py`/`test_entry_guard.py` 范例回归。
- C10：新测试文件（`test_liquid_consumable.py` 或并入 `test_items_extension.py`），覆盖 `resource.water` 门槏、灌装/饮用/进食效果与耗尽。
- C11：`test_spawner.py` 扩展 + S2（加载期形状校验）。
- C12：`test_room_hooks.py`/`test_xingxiu_mechanics_08.py`（现有 `bandit_ambush` 测试文件）扩展 `params` 用例 + S3 UGC 边界回归。
- C13：新测试文件（`test_scene_includes.py`）+ `test_load_pack.py` 扩展。
- C14：ADR 落地后再定；本 spec 阶段不产出测试（无实现）。

## Out of Scope

- **B7 `invalid_startroom`**：grill 拍板维持 GAP·后置，不进本 effort。
- **C15 `valid_leave` 脚本化**：grill 拍板维持 GAP·后置；仍走既有官方 hooks + `block_exits`，不新增创作者可写的脚本面。
- **M4（商业化数据模型）评估**：与本 effort 正交，独立拍板，不因本 effort 关闭而自动开始（PROGRESS.md Next Up §2）。
- **LPC 行为等价验证**：无论位等价、统计等价还是 golden trace 对照，任何形式都不做（ADR-0001）；C12 的刷怪条件、C10 的液体数值等均为「机制对齐、数值自定」，不追求与 LPC 源码位一致。
- **UGC 可写 `hooks` / RestrictedPython 房间脚本**：C12/C14 均不下放到 UGC 内容包，ADR-0012 边界不变。
- **完整 Effect 持续生命周期系统**：C10 的液体/进食效果是命令结算内一次性数值变化，不是持续 buff/debuff/衰减（ADR-0007 停机范围不变，归属仍归引擎但不在本 effort 兑现）。
- **重开放置模型（ADR-0010）**：C11 只在既有房间中心 `objects` 契约上做加法（新增候选组形状），不改「模板键→数量」放置权威语义、不改补刷占槏位规则。
- **C14 的具体实现**：本 spec 只锁需求边界并要求先出 ADR；ADR 本身与后续实现票不在本次 `/to-spec` 产出范围内，留给下一步。
- **契约破坏性变更**：本 effort 全部字段变更为新增，不修改、不删除、不改变已冻结字段的类型/必填性/含义（`docs/creator-contract-v0.md` 承诺条款 1）。
- **改契约/加载器的具体代码落地**：本 session 只产出 spec；`--strict`/`--validate` 行为、`scene_loader.py`/`pack.py` 代码改动留给 `/to-tickets` 之后的 `/implement` 阶段。

## Further Notes

- **治理**：Polishing 不是新 M 号、不是 M4 子集；纳入的 13 项本阶段必须实现（可拆细票，不得以「太大」为由后置出本阶段）；不确定的实现细节（本 spec 中标注的「开放子决策」）由拆票或实现时的架构师会话钉死，不影响本 spec 发布。
- **C14 排序**：`/to-tickets` 必须把 C14 拆成「先出 ADR」与「后实现」两张独立票，且实现票 `Blocked by` 该 ADR 票；ADR 编号建议续接现有序号（当前最新 [0012](../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md)，即 `0013`），具体编号由写 ADR 时确认无冲突后确定。
- **CONTEXT.md 现状**：「出口导航别名」「房间风景」两个词条已在 grill 拍板时提前写入 `CONTEXT.md`（覆盖 A1+A2、A4 的完整规格），本 spec 的对应小节是摘要引用，不是重复定义；实现落地时如与词条原文有出入，以 `CONTEXT.md` 原文为准并同步更新差异。其余 9 项（A3/A5/B6/B8/B9/C10/C11/C12/C13）目前 `CONTEXT.md` 里没有专门词条，实现落地时按惰性维护原则补写。
- **收尾回写清单**（每张实现票关闭时同步，effort 整体关闭时再核对一次）：
  1. `docs/gap-ledger.md`：把 C10（液体/eat/drink）、C11（随机 objects）、C13（多文件路径引用）三行现状从「未支持/单包单文件」更新为「已支持」并指向新契约字段；C12 在「运行时改世界机关」行补一句「贵重物等条件走官方 hooks params，已落地」；B7/C15 维持 GAP·后置不动。
  2. `docs/creator-contract-v0.md`：按加法承诺补写本 effort 新增的全部顶层段/字段（`rooms.*.details` 新形状、`rooms.*.block_exits.*.deny_message`、`rooms.*.hotel`、`rooms.*.resource.*`、`rooms.*.objects.<slot>.random_of`、顶层 `includes`）。
  3. `CONTEXT.md`：为 A3/A5/B6/B8/B9/C10/C11/C12/C13 补写词条（惰性创建，参考现有词条的 `_Avoid_` 小节写法）。
  4. `PROGRESS.md`：Done 滑动窗口新增本 effort 关闭条目，Next Up 回到「M4 评估」或下一命名 effort。
- **Effort 目录命名**：选定 `.scratch/polishing/`（不加 `-dsl-ux` 限定词）——13 项范围横跨创作 DSL/UX（A 组）与引擎能力（B/C 组），窄化命名会误导后续检索；与 `CONTEXT.md`「Polishing（打磨抛光）」词条同名，检索时二者互为唯一入口。
- **下一步**（本 session 到此为止，不在本 session 执行）：`/to-tickets` 把上述 13 项拆成 `.scratch/polishing/issues/NN-*.md`（建议每 ID 一票，A1+A2 合并一票，C14 拆两票如上），之后 `/implement`；每票关闭按上面「收尾回写清单」同步文档。
