# Session Q&A 出处对照（2026-07-23 · 本 Agent 窗口）

> **用途**：保留「架构师对照 LPC / 引擎 YAML 提问 → 答复要点」的原始出处，供后续  
> `/grill-with-docs`、`/to-spec` 找回上下文。  
> **不是** grill 拍板稿；拍板与 Polishing 清单见 [session-notes-2026-07-23.md](session-notes-2026-07-23.md)。  
> **范围**：本 Cursor Agent 会话内的问答（Ask/澄清为主）。同日在**另一窗口**对 session-notes 的 grill 拍板（出口导航 A1/A2、details A4、决策矩阵勾选等）以 session-notes 正文为准，本文件不重复其规格全文。

## 如何使用

| 读者 | 建议 |
|------|------|
| `/grill-with-docs` | 先读 session-notes 矩阵与已拍板节；对本文件按 ID 回翻「用户原问 + LPC 锚点」 |
| `/to-spec` | 对标 Polishing ✓ 项时，用本文件的「出处」填 Problem / 验收锚点；用 session-notes 填 Solution 拍板规格 |
| 实现票 | 以 session-notes 已拍板规格为权威；本文件只防丢失「为什么会问到这」 |

候选 ID（A1…C15）与 [session-notes-2026-07-23.md](session-notes-2026-07-23.md) 决策矩阵一致。

---

## Q1 · 房间资源 `resource/grass` / `resource/water`

| | |
|--|--|
| **用户原问** | 侠客行源码里 `set("resource/grass", 1)` 或 `set("resource/water", 1)` 到底是什么？ |
| **出处** | `d/xixia/hytan.c` L15–16（`resource/grass`）；同区如 `d/xixia/cave.c`（`resource/water`） |
| **答复摘要** | 房间**环境资源布尔标记**，非可采集库存。`water`：灌水（`feature/liquid.c` `do_fill`）、喂动物喝水（`cmds/std/yin.c`）。`grass`：坐骑进房自食恢复 food/jingli（`clone/horse/horse.h`）。常与 `cost` / `outdoors` 并列。 |
| **引擎对照** | 无等价房间资源字段；液体灌装 GAP 后置（→ C10）。 |
| **映射** | 事实表「resource/*」；候选 **C10** |

### 追问 · water「数量」会不会喝完？

| | |
|--|--|
| **用户原问** | `daoguan.c` 的 `set("resource", (["water":1]))` 能否指定数量？喝完有没有？河边如何表示永远装不完？ |
| **出处** | `d/xixia/daoguan.c` L22–24；对照 `d/shaolin/hanshui1.c`（`resource/water`, 1） |
| **答复摘要** | 与 `set("resource/water",1)` 经 dbase `/` 路径等价。消费者只做真假；全库无对房间水位 `add(...,-1)`。江/湖/井同开关 = **天然无限**。有限泉水需新字段。 |

---

## Q2 · `no_clean_up`

| | |
|--|--|
| **用户原问** | `set("no_clean_up", 0)` 具体做什么？ |
| **出处** | `d/xixia/bingku.c` L17 |
| **答复摘要** | MudOS **对象回收**开关。`feature/clean_up.c`：master 且 `no_clean_up` 真 → 拒 destruct。`0` = 允许空闲回收（西夏房常见模板冗余；`ROOM` reset 也会置 0）。`1` = 钉住房间。游荡 NPC 回不了家时 `add("no_clean_up",1)` 暂钉。 |
| **映射** | 事实表「no_clean_up」；未进 Polishing 矩阵（引擎无同名语义） |

---

## Q3 · NPC 挡路 vs 引擎实现

| | |
|--|--|
| **用户原问** | `dating.c` 的 `valid_leave`（武士挡 west）在 engine 里如何实现？DSL / 规则 / 受限 Python？ |
| **出处** | `d/xixia/dating.c` L27–35（`present("wu shi")` + dir west） |
| **答复摘要** | **声明式** `block_exits: { west: { npc: <模板键> } }`；`go` 查同房模板在场则拒（`commands._cmd_go`）。固定文案 `{名}挡住了{方向}…`。复杂条件走官方 hooks（ADR-0012）；UGC 禁 hooks；无 RestrictedPython 房间脚本。`entry_guard` 是进房条件门，不是「某向被 NPC 挡」。 |
| **映射** | 事实表「NPC 挡路」；候选 **A5**（deny_message）、**C12/C15** |

### 追问 · 挡路还有一系列逻辑时 DSL 怎么办？

| | |
|--|--|
| **用户原问** | 若 NPC 挡路还有更多具体逻辑，DSL 如何配置？ |
| **答复摘要** | `block_exits` **只有**「模板在场→挡向」，无自定义 message/条件/豁免。复杂：拆 `entry_guard` / 门钥 / 官方钩子（如 `bandit_ambush`+block_exits）；**不要**把 block_exits 扩成迷你 `valid_leave`。 |
| **映射** | **A5**、**C12**、**C15** |

---

## Q4 · `invalid_startroom`

| | |
|--|--|
| **用户原问** | `invalid_startroom` 是什么意思？ |
| **出处** | `d/xixia/duchuan.c` L20 |
| **答复摘要** | `cmds/usr/quit.c`：有标记则 **禁止**把当前房记为 `startroom`，强制 `/d/city/kedian`，提示「不能进入游戏的地方」。用于船舱/擂台/临时空间，避免登录落入已销毁对象。对照 `valid_startroom`（客店等明确允许起点）。 |
| **引擎对照** | 未对齐。 |
| **映射** | **B7**（grill 标 GAP·后置） |

---

## Q5 · `cost` 与 eat/drink 排期

| | |
|--|--|
| **用户原问** | `set("cost",1)` 引擎实现了吗？eat/drink 何时实现？ |
| **出处** | `d/xixia/gate.c` L21；LPC 步行扣精力见 `cmds/std/go.c`（约 `jingli -= cost*2`） |
| **答复摘要** | `cost`/`terrain` → `Terrain`：**已支持**，主要用于**骑乘**（ability 门槛 + 坐骑 jingli）。**未**做步行扣玩家精力。eat/drink/fill：**无命令**；`Consumable` 占位；GAP「液体灌装/饮用」后置；Pre-M4 保真 OOS；无固定里程碑日期。 |
| **映射** | **B6**（步行 cost）、**C10**（液体；grill 已升格 Polishing） |

---

## Q6 · 客店旗标 `sleep_room` / `no_fight` / `hotel`

| | |
|--|--|
| **用户原问** | 这几个标记分别对应什么逻辑？ |
| **出处** | `d/xixia/kedian3.c` L18–20 |
| **答复摘要** | `sleep_room`：允许 `sleep`（非丐帮）；睡房禁多数练功（dazuo 等）。`no_fight`：禁 kill/fight/attack 等。`hotel`：须 `rent_paid` 才能睡；睡完清标记；与小二付钱、`valid_leave` 清标记配套。引擎：`no_fight` 已有；`no_sleep_room` 可声明但 inert；无 sleep/hotel。 |
| **映射** | **B8** |

---

## Q7 · 落日林随机 objects

| | |
|--|--|
| **用户原问** | `random(3)` + switch 设 objects——是设置分支和随机 NPC 吗？引擎有没有？ |
| **出处** | `d/xixia/luorilin2.c` L16–41 |
| **答复摘要** | **出口固定**；随机的是**放置表**（`branch*`=小树枝物品 + 乌鸦/野兔/蛇）。引擎：固定 `objects` 有；出口加载期 `random_of` 有；**无**「多套 objects 抽一套」。 |
| **映射** | **C11** |

---

## Q8 · 土门子进房刷马贼

| | |
|--|--|
| **用户原问** | `init()` 这段在干什么？ |
| **出处** | `d/xixia/tumenzi.c` L23–43（及 L44–50 `valid_leave`） |
| **答复摘要** | 进房：扫背包非金钱 `value>=10000` → `rob_victim`；1/3 概率刷 `mazei`。离开：有标记且马贼在场则挡。近引擎 `bandit_ambush`，但**无**贵重物条件。 |
| **映射** | **C12** |

---

## Q9 · 出口简写 DSL

| | |
|--|--|
| **用户原问** | `exits` 能否 `south: start_yard`，复杂再用 dict（对齐 xkx）？ |
| **出处** | `engine/data/m1_default_scene.yaml` L23–29 |
| **答复摘要** | **已支持**（契约 + `_exit_target`）。简写无门/别名/`random_of`；复杂用映射。`m1` 全写 dict 是范本偏好。 |
| **映射** | 事实表；**A3**（范本规范化） |

---

## Q10 · 户外风景括号名 + 颜色

| | |
|--|--|
| **用户原问** | 广场 look 石狮/旗杆应否括号加英文/拼音（对齐 xkx）？括号内不同颜色怎么做？ |
| **出处** | 终端 verify 广场 look；YAML `m2_mvp_scene.yaml` `yangzhou_guangchang.details`（石狮/旗杆）；旗杆已有 `<c:yellow>旗角</c>` |
| **答复摘要** | Pre-M4 **刻意不做** `牌子(paizi)` 括号 id 语法；`look 石狮` 靠中文键。着色：ADR-0011 `<c:name>…</c>`，禁止 ANSI/LPC 宏。long 手写括号不自动变 look 目标。 |
| **后续** | 另一窗口 grill 已拍板 **A4**：K2 英键+aliases、long 纯文本 `名(id)` 扫描展示等——以 session-notes「Grill 已拍板：房间风景 details」为准。 |
| **映射** | **A4** |

---

## Q11 · 出口 aliases：方位默认 vs 地名挂目标房

| | |
|--|--|
| **用户原问** | 标准方位是否不必再写 aliases？「武庙」是否更好只写在 `yangzhou_wumiao`？ |
| **出处** | `engine/data/m2_mvp_scene.yaml` L57–77（广场 exits）；武庙 northeast aliases |
| **答复摘要** | **现状**：仅 `n/s/e/w` 整行简写；`go 东` 须出口 aliases。`go` **不**读目标房 aliases——武庙挂目标房则导航失败。产品上「方位默认」「邻房名回退」合理但未实现。 |
| **后续** | 另一窗口 grill 已拍板 **A1+A2 合并**（内置十向中英、目标房 name/aliases 回退、中文须带 `go` 等）——以 session-notes「Grill 已拍板：出口导航」为准。 |
| **映射** | **A1**、**A2**、**A3** |

---

## Q12 · `objects` 跨目录引用

| | |
|--|--|
| **用户原问** | objects 如何引用跨层级目录的 npc/items？ |
| **出处** | `engine/data/m2_mvp_scene.yaml` L444–446（`escort_chief` / `escort_cargo`） |
| **答复摘要** | **不能**写路径。键 = **同场景文件** `items.*` / `npcs.*` 扁平 id（ADR-0010）。无 include/多文件合并。跨包/跨文件需未来加载器能力。 |
| **用户意愿** | 希望未来支持路径引用跨层级 templates。 |
| **映射** | **C13**（grill 标 Polishing） |

---

## Q13 · 局部天气 + 父级回退

| | |
|--|--|
| **用户原问** | 能否 DSL 配置局部天气（海上、山顶寺庙），无则回退父级（如华山）？ |
| **出处** | `m2_mvp_scene.yaml` `outdoors: true`（如 L510 一带） |
| **答复摘要** | **不支持**。`outdoors`=bool；`NatureState` **World 单例**（一套相位+晴雨）。无 region/parent 天气链。LPC `outdoors,"city"` 字符串区域标签也未做成作用域天气。 |
| **映射** | **C14**（矩阵空 / 需 ADR） |

---

## Q14 · 条件 DSL 适用场景与示例

| | |
|--|--|
| **用户原问** | `entry_guard` condition 体系适应哪些场景？请给 DSL 案例。 |
| **出处** | `m2_mvp_scene.yaml` L512–520（少林山门）；另 `skills.luohan_quan.learn_condition`、`day_shop` |
| **答复摘要** | 共用受限 AST：进房门禁、日间店、学艺门槛、NPC `when`（多为 Nature）。字段：昼夜/雨、faction/gender/edged、属性 gte、and/or/not。**不**适合：定制挡路文案、贵重物刷怪、局部气候、任意任务旗标（除非扩协议）。 |
| **映射** | **B9**（仅文档+范例）；查询面扩默认非 polish |

---

## Q15 · 收束进文档 / polishing grill

| | |
|--|--|
| **用户原问** | 将本 session 细节收进文档；新 session `/grill-with-docs` 定 polishing 范围。后：按稿写入 `.scratch/polishing-candidate-review/`。 |
| **产物** | 本目录 `README.md`、`session-notes-2026-07-23.md`（后经他窗 grill 扩充）；`PROGRESS.md` Next Up 指向本目录。 |
| **本文件** | 补「出处丢失」：即本文。 |

---

## 索引：出处文件 → 问答

| LPC / 引擎文件 | 问答 |
|----------------|------|
| `d/xixia/hytan.c` | Q1 |
| `d/xixia/daoguan.c` | Q1 追问 |
| `d/xixia/bingku.c` | Q2 |
| `d/xixia/dating.c` | Q3 |
| `d/xixia/duchuan.c` | Q4 |
| `d/xixia/gate.c` | Q5 |
| `d/xixia/kedian3.c` | Q6 |
| `d/xixia/luorilin2.c` | Q7 |
| `d/xixia/tumenzi.c` | Q8 |
| `engine/data/m1_default_scene.yaml` | Q9 |
| `engine/data/m2_mvp_scene.yaml`（广场/门禁/出口/objects） | Q10–Q14 |
| `cmds/std/{yin,sleep,go,quit}.c`、`feature/{liquid,clean_up}.c`、`clone/horse/horse.h` | 答复中的 LPC 消费者 |

## 索引：候选 ID → 问答

| ID | 问答 |
|----|------|
| A1 A2 A3 | Q11（拍板规格见 session-notes） |
| A4 | Q10（拍板规格见 session-notes） |
| A5 | Q3 追问 |
| B6 | Q5 |
| B7 | Q4 |
| B8 | Q6 |
| B9 | Q14 |
| C10 | Q1、Q5 |
| C11 | Q7 |
| C12 | Q8、Q3 |
| C13 | Q12 |
| C14 | Q13 |
| C15 | Q3 |
