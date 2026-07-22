# Session 笔记：LPC 房间能力 vs 当前引擎（2026-07-21）

> 来源：架构师对照 `engine/data/m2_mvp_scene.yaml` 与 `d/city/*.c` 的问答 session。  
> 用途：M3 停机加固整体完成后、进入 M4 之前，开 `/grill-with-docs` 的输入底稿。  
> 索引：[README.md](README.md)

## 1. 拍板结论（本 session 已达成）

1. **排期**：这批补充逻辑要在 **M3 停机加固整体完成之后、M4 之前** 规划并实现（独立 effort，不并入 hardening）。
2. **流程（ask-matt）**：`/grill-with-docs` → `/to-spec` → `/to-tickets` → `/implement`；**不用** `/wayfinder`；**不要**直接 `/implement`。
3. **放置模型（2026-07-22 改判）**：原结论「保留 `in_room`/`placed_in`、不必改 `objects`」**已撤销**。Pre-M4 频道/spawn/任务 grill 选 **C**：房间中心 `objects` + 侠客行式槽位计数，弃用 `placed_in`/`in_room`；见 [ADR-0010](../../docs/adr/0010-room-centric-objects-placement.md)。**落地归兄弟 effort** [.scratch/pre-m4-channels-spawn-quest/](../pre-m4-channels-spawn-quest/)；本 effort grill **不得重开放置**。下文 §2 / 缺口 L / 议程第 4 条仅作历史对照。
4. **颜色**：服务端不宜继续塞 ANSI/`HIG`…`NOR`；倾向 **语义色 token + 客户端渲染**——须在 grill 中落 ADR。
5. **书院读书**：个人直觉为未来书院题材重点；是否进本波还是明确后置，grill 必问。

## 2. 放置：`in_room` / `placed_in` vs LPC `objects`

### LPC

```c
set("objects", ([
    CLASS_D("shaolin") + "/xingzhe" : 1,
]));
// 或
set("objects", ([
    "/d/city/npc/wang_lifa" : 1
]));
// 多实例
set("objects", ([
    "/d/city/obj/stone" : 2,
    "/d/emei/obj/flower" : 1,
]));
```

房间中心：房间声明「有什么、几份」；`setup()`/`reset()` 按路径 `new`。

### 当前引擎

- 物品：`items.<key>.placed_in: <room_key>` → 进房间 `Container`
- NPC：`npcs.<key>.in_room`（或 `startroom`）→ `Position`；支持 `count` / `respawn`
- 加载器文档定位：M1 过渡声明式 YAML，加载期校验坏引用（`SceneLoadError`）
- 参考：`engine/src/mud_engine/scene_loader.py`；`engine/data/m1_default_scene.yaml` 注释

### 考量（为何不做成 objects）

- 声明式 + 静态校验友好（实体自带位置）
- 与 ECS（Container / Position / SpawnerBlueprint / item_templates）一致
- ADR-0001：不做 LPC 行为等价，不强制复刻 FluffOS 对象树习惯

### 若改为房间 `objects` 的利弊

| 优点 | 缺点 |
|---|---|
| 读 LPC 房间时心智一致；「这房有什么」一眼看完；多实例 `stone: 2` 自然 | 跨房复用模板需模板库或重复；钥匙/商店等全局引用仍要 ID；与现有 spawner/templates 对账成本；UGC 校验模型要改 |

**折中候选（grill）**：全局 `items`/`npcs` 模板段 + 房间只写引用清单（接近 LPC「文件=模板」）。

### 多实例现状

| | 状态 |
|---|---|
| NPC `count` | **已有**（如城门守卫） |
| 物品 `count`（对齐 `stone: 2`） | **无**——需多键或本波补 `count`/初始堆叠 |

## 3. 缺口总表（实现状态）

| # | 题材点 | LPC 代表 | 当前状态 | 建议本波态度（待 grill） |
|---|---|---|---|---|
| A | 房间风景 / `item_desc` | `cangshuge` 书架、`jiuguan` 牌子、`datang` 对联、`houyuan` 门描述 | **未实现**；`look` 只命中实体 | **高优先**——大量房间「看起来像」依赖此 |
| B | long 内联括号提示 | `书架(shujia)` | 纯文本；不可 look | 随 A；括号可不做语法，靠 `item_desc` 键 |
| C | `no_fight` / `no_steal` / `no_sleep_room` | `cangshuge` | **未实现** | 中：按已有命令面裁剪（有战/有偷/有睡再禁） |
| D | `cost` | 多数房间 | **部分**：→ `Terrain`（骑乘），非走路体力全套 | 低：文档澄清即可，除非要走路扣费 |
| E | 藏书 / `read` / TOC / `jybooks` | `cangshuge.c` | **未实现** | **grill 必问**：本波最小切片 vs 后置书院题材 |
| F | 颜色 markup | `beijiao1` `HIG`…`NOR` | **未实现**；原文输出 | **高优先 + ADR**（语义色，非 ANSI 进 YAML） |
| G | `day_shop` | `datiepu` 等；`go.c` 夜间拒入 | **未实现**（Nature 已有 `is_night`） | 中：可用 `entry_guard` 近似或一等字段 |
| H | 防拐带 `valid_leave` | `datiepu` `present(npc, me)` | **未实现**（钩子有，规则无） | 低：当前 NPC 本就不进背包 |
| I | 标准门锁 | `jail` `create_door` | **已有** open/close/unlock/knock；钥匙不消耗 | 保持；补文档对照即可 |
| J | 剧情门（耗钥、动态出口、NPC 挡向） | `houyuan` | **无**（动态出口 API 测试有，内容规则未接） | 中：声明式「消耗钥匙 / 增删出口 / 在场挡向」 |
| K | 灌酒 / 液体 | `jiuguan` `fill_shaojiu` | **无**（Consumable 占位，无 eat/drink） | 中高：液体能力 + 房间/NPC 灌装动作 |
| L | 放置所有权 / 物品 count | 见 §2 | 见 §2 | **已迁出**：ADR-0010 + channels-spawn-quest；本波勿 grill |

## 4. 分项细节（对照原文）

### 4.1 藏书阁 `d/city/cangshuge.c`

- `item_desc["shujia"] = (: look_shujia :)` → `start_more(read_file(BOOKS_TOC))`
- `jybooks` 缩写 → 中文书名；`read <id>` 选定；`read <n>` 付 200 文读 `doc/books/jy/<id>/<id>-n.txt`
- 同房 `add_action` 拦截打坐/练功等（「你是来读书还是来练功」）
- 旗标：`cost 0`、`no_fight`、`no_steal`、`no_sleep_room`

**引擎**：上述均未做。完整子系统 = 内容资产 + 分页展示 + 货币 + 房间行为约束。

### 4.2 颜色 `d/city/beijiao1.c` + `include/ansi.h`

- `HIG`/`HIR`/`NOR` = ANSI 转义宏，服务 Telnet/终端
- **建议方案（待 ADR）**：
  - 服务端只发语义色（如 token / `<c:green>…</c>`）
  - 客户端渲染（终端→ANSI，Web→CSS）
  - YAML **禁止** 嵌入原始 ANSI / `HIG` 宏名
  - 服务端不负责最终像素，但 **定义并校验** 允许的色 token

### 4.3 对联 `d/city/datang.c`

- 仍是 `item_desc["duilian"]` 多行字符串；外包 `HIG`…`NOR` 整段着色
- **不是**独立格式；本波随风景 look + 色 markup 即可覆盖

### 4.4 `day_shop`（`datiepu.c` + `cmds/std/go.c`）

- 目标房间 `day_shop` 且夜间/午夜 → 拒入（「晚上不开」）
- `block.c` 亦与 `no_fight` 并列作不宜动武空间
- Nature `is_night` 已有；缺「进店门禁」一等语义或约定用 `entry_guard`

### 4.5 `valid_leave` 防拐带（`datiepu.c`）

- `present("wang tiejiang", me)` = NPC 在**玩家身上**，非「房间里有铁匠」
- 现模型 NPC 默认不进玩家 Container，坑不易复现；钩子可扩，非本波刚需

### 4.6 门：`houyuan.c` vs `jail.c`

| | jail | houyuan | 当前引擎 |
|---|---|---|---|
| 关门出口 | `create_door(..., DOOR_CLOSED)` | 东门可动态删 | `door: closed\|locked` **有** |
| 钥匙 | 标准门系统 | `guifang key` 一次性 `destruct` | 钥匙**不**消耗（测试锁定） |
| 动态出口 | 否 | 无钥时无 east；unlock 再 `set exits` | 运行时增删出口**可**，场景未用 |
| NPC 挡向 | 否 | 凌翰林在场挡东西 | `EntryGuard` / leave 钩子可近似，官方场景无 |

### 4.7 酒馆牌子与灌酒（`jiuguan.c`）

- `item_desc["paizi"]` = 价目**纯文本**；`翡翠豆腐(Doufu)` 等括号是 id/命令提示，**不是**自动可 look 实体
- `look paizi` 依赖 item_desc（引擎无）
- `fill_shaojiu` 等是 `add_action`：校验小二在场且活着 → 玩家持 liquid 容器 → 付铜板 → 写入液体属性（醉酒参数等）
- 商店 `buy` ≠ 灌装

## 5. 建议 grill 议程（加固完成后）

按优先级逼问并写回 `CONTEXT.md` / ADR：

1. **本波必做 vs 后置**：E 书院读书、K 液体、J 剧情门、C 房间旗标各自进不进。
2. **颜色 ADR**：token 集合、YAML 语法、CLI 是否可选渲染 ANSI。
3. **风景模型**：独立 `features`/`item_desc` 映射 vs `no_get` 风景实体；与 `look` 解析优先级。
4. ~~**放置**：维持现状 / 加房间 `objects` 糖衣 / 物品 `count`。~~ → **已决并迁出**（ADR-0010 / channels-spawn-quest）。
5. **与创作者契约**：是否在本波回写 `docs/creator-contract-v0.md` 与 `--validate`（放置字段变更由兄弟批先改）。
6. **验收场景**：是否用扬州子集（酒馆、藏书阁、打铁铺、翰林后院、北门外草地）做端到端，而非新建橱窗包。

## 6. 建议 skill 路径（下一 session）

| 阶段 | Skill |
|---|---|
| 开场 | `/grill-with-docs`（输入：本文 + [README.md](README.md)） |
| 词汇 / 决策 | `/domain-modeling`（至少颜色 ADR；可选风景物） |
| 可选前置阅读 | `/research`（LPC `feature/liquid`、分页 `start_more`）→ 笔记喂 grill |
| 塌缩 | 同一上下文 `/to-spec` → `/to-tickets`（勿 mid-phase compact） |
| 施工 | 每票新 session `/implement`（内含 `/tdd` + `/code-review`） |
| 上下文满 | `/handoff` 再续，勿硬撑过 smart zone |

## 7. 明确不在本笔记范围

- 改写 M3 停机加固 S0 / 已拆 11 张票
- 复刻 LPC 行为等价验证（ADR-0001）
- Web 创作者平台 / 留言板（post-mvp-backlog / ADR-0006）
- 把本 effort 误标为「GAP 台账实现」（GAP 是文档交付物）

## 8. 关键源码锚点（便于复查）

| 主题 | 路径 |
|---|---|
| 场景加载 / placed_in / in_room | `engine/src/mud_engine/scene_loader.py` |
| 门锁命令 | `engine/src/mud_engine/commands.py`（open/close/unlock） |
| 门锁测试（钥匙不消耗） | `engine/tests/test_doors.py` |
| EntryGuard / is_night | `engine/src/mud_engine/entity_gate.py`、`nature.py` |
| Consumable 占位 | `engine/src/mud_engine/components.py` |
| MVP 场景 YAML | `engine/data/m2_mvp_scene.yaml` |
| LPC 藏书阁 | `d/city/cangshuge.c` |
| LPC 酒馆灌酒 | `d/city/jiuguan.c` |
| LPC 翰林门 | `d/city/houyuan.c` |
| LPC day_shop 拒入 | `cmds/std/go.c`（约 101–103 行） |
| LPC look item_desc | `cmds/std/look.c`（`look_room_item`） |
| ANSI 宏 | `include/ansi.h` |
