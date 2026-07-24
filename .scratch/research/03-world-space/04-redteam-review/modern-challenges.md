# 红队评审：现代玩法挑战者对 modern-design-review 的尖锐质疑

> 角色：现代世界/关卡设计师（红队 / 现代玩法挑战者，03-world-space 调研团队 / 现代评审组）。
> 质疑对象：`03-engine-insights/modern-design-review.md` 的「保留 vs 现代化」结论，以及与其耦合的 `player-psychology.md`、`commercialization.md`、`abstraction-options.md` 的相关判定。
> 立场：作为「现代玩法挑战者」，本文件的任务不是否定现代化，而是**对抗 modern-design-review 中未经充分论证就倒向「必须现代化」的判定**，逼评审委员会在裁决前看到另一面。
> 证据规则：每条质疑标注被质疑文件与段落 + LPC/engine 一手证据。禁止凭空推断。

---

## 0. 摘要：modern-design-review 的核心问题

modern-design-review（下称 MDR）在 §0 声称「在『文本沉浸感』与『空间具身感』上仍有不可替代的价值」，但随后在 §1-§4 系统性地给出**六条「必须/应现代化」判定**：必须补地图概览（§1.3）、必须引入 fast travel（§2.3）、天气应升级为机制变量（§3.3）、昼夜应放慢到 1-2 小时（§3.3）、玩家船不值得复刻（§4.5）、渡船等待应可互动化或付费跳过（§4.5）。

这些判定存在三类问题：
1. **受众错配**：用 WoW/原神/BotW 的留存曲线论证一个**文本 MUD 引擎 + UGC 平台**的体验风险，而 CLAUDE.md「项目一句话」明确这是题材无关的 niche MUD 引擎，不是大众 MMO。
2. **内部矛盾**：MDR 的 fast travel「必须」论与 player-psychology「自动寻路会消解探索」论直接冲突；MDR 的「玩家船不值得」与 abstraction-options「载具实体抽象（方向 B，支持 ship）」、commercialization「玩家船是体验型消费点」冲突。
3. **证据遗漏**：MDR §1.1 用 grep `fast_travel|recall|...` 零命中论证「LPC 无 fast travel 是技术限制非设计选择」，但**完全没提** `clone/obj/genmap.c`（BFS 地图生成器，作者 chu@xkx，1998-05-09）与 `clone/obj/mapdb.c`（路径数据库）的存在--这两份文件证明**原作者建了寻路工具却刻意不暴露给玩家**，这是设计选择的有力证据，不是技术限制。

下文逐条展开。每条以「裁决建议」收尾，供评审委员会定夺。

---

## 质疑 1：fast travel「必须」论与文本沉浸价值根本矛盾，且与 player-psychology 直接打架

### 被质疑结论

- MDR §2.3 判定：「**必须引入 fast travel 层**（已发现地点间快速移动，最好带经济/解锁成本），否则移动疲劳会劝退当代玩家。」
- MDR §1.3 判定：「auto-path 非必须，但『已发现地点 fast travel』是当代基本预期。」
- MDR §5.3 陷阱：「别把『无 fast travel』当硬核特色：LPC 无 fast travel 是技术/时代限制，不是设计选择。」

### 质疑

**（1）fast travel 本质上是 auto-path 的一种，MDR 自己却把它当必须。**
player-psychology.md §六 底线 5 明确写道：「不必做自动寻路（**那会消解探索**），但官道/主干道应在房间呈现里给『前方 X 抵达 <地标>』的渐进提示」。这两份报告对「跳过房间序列」的态度是矛盾的：player-psychology 认为跳过=消解探索（反对），MDR 认为跳过=消除疲劳（必须）。已发现地点 fast travel 与 auto-path 的功能差异只是「触发条件」而非「是否跳过房间」--两者都让玩家**绕过中间房间的 `long` 文案与拓扑体验**。如果 auto-path 消解探索，fast travel 同样消解。

player-psychology.md §1.1 自己承认「房间 `long` 文案是第二驱动...**每条 `long` 都是一次手写的小型悬念广告**」（证据：`d/village/alley1.c:9-13` long、`d/village/eroad1.c` 「往东就是出村的路了」）。fast travel 让玩家跳过这些悬念广告，直接摧毁 player-psychology 识别出的核心留存驱动。MDR 没有 reconcile 这个矛盾。

**（2）「LPC 无 fast travel 是技术限制非设计选择」是未经证据的断言，且被一手源码反驳。**
MDR §1.1 用 `grep fast_travel|recall|waypoint|teleport|...` 零命中作为「无 fast travel」的证据。但本次红队核查发现：`clone/obj/genmap.c`（BFS 地图生成器，`#define MAX_NODE 5`，注释「since it is really expensive and may cause server crash, we try to be very prudent here」）与 `clone/obj/mapdb.c`（`query_room_exits()`/`query_map()` 路径数据库）**确实存在且可计算路径**。player-psychology.md §2.1 已记录这两份文件的消费者是 `d/city/npc/ftb_zhu.c`、`d/beijing/gulou2.c`、`d/wudang/sheshenya.c` 等特定 NPC/任务的局部 BFS，**没有任何玩家命令暴露这套地图**。

这是关键证据：**原作者在 1998 年就建了 BFS 寻路数据库（`genmap.c` 作者 chu@xkx，日期 5/9/98），却刻意只给 NPC/任务用、不给玩家用**。这不是「技术上做不出 fast travel」，而是「做了寻路工具但设计上决定不给玩家自动寻路」。MDR 把一个**有工具却选择不暴露**的设计决策降格为「技术限制」，是对一手证据的误读。

**（3）MVP 场景清单已经内含「交通即 fast travel」层，再加传送式 fast travel 会让坐骑/渡船冗余。**
CLAUDE.md 架构不变量第 7 条 MVP 场景清单含「坐骑（官道/野外可骑乘）+ 水陆交通（渡口/渡船）」。坐骑的作用正是降低单步消耗（`cmds/std/go.c:225-227` 骑乘马付 cost×2 而非玩家，engine `commands.py:513` `MOUNT_JINGLI_PER_TERRAIN_COST=1` vs 步行 `WALK_JINGLI_PER_TERRAIN_COST=2`），渡船的作用是跨越水域（`inherit/room/ferry.c`）。这**就是该题材的 fast travel 层**--它有题材风味（骑马/渡船）、有资源成本（jingli）、有空间逻辑（沿官道/跨水）。再叠一层「已发现地点传送」会让坐骑与渡船的存在意义被掏空：玩家发现地点后就传送，谁还骑马走官道？

### 裁决建议

- **驳回 MDR §2.3「必须引入 fast travel」的「必须」定性**。改为：fast travel 是否引入是**题材包级别的设计选择**，不是引擎必须项。武侠题材包可用「坐骑+渡船+官道驿站换马」作为题材风味的 fast travel；科幻题材包可用「传送门」。引擎只需保证 `Exits` mutable（`components.py:115`）与载具抽象（abstraction-options §4 方向 B）能支撑题材包自己声明交通层。
- **驳回 MDR §5.3「无 fast travel 是技术限制非设计选择」的断言**。`clone/obj/genmap.c` + `mapdb.c` 的存在证明这是设计选择。评审委员会应要求 MDR 修正这一表述。
- **采纳 player-psychology §六 底线 5 的「渐进提示」方案**（官道给「前方 X 抵达 <地标>」），作为比 fast travel 更温和、不消解探索的方位感补强。这与 MDR §1.3「补文字版区域/已发现地点列表」可并存（列表 ≠ 传送）。

---

## 质疑 2：「迷路=D1 高危流失」基于错误受众假设，且混淆了 LPC 全量与 MVP 范围

### 被质疑结论

- player-psychology.md §2.3：「新手从华山村（33 房间）进入扬州城（134 房间）是典型的从『可记忆规模』跨入『不可记忆规模』的临界点...**D1 高危**。」
- MDR §1.3：「6414 房间无任何空间总览，新手在扬州 441 房间内迷路是必然事件...这不是『硬核特色』，是 1990 年代技术约束下的被动选择。」
- MDR §2.3：「6414 房间规模下，若无 fast travel，跨区往返的单次时间成本对当代玩家不可接受。」

### 质疑

**（1）受众错配：用大众 MMO 的留存曲线套文本 MUD 引擎。**
CLAUDE.md「项目一句话」：这是「题材无关的核心 MUD 引擎 + UGC 创作层 + 一个官方轻量武侠题材包（MVP）」。目标用户是 **UGC 创作者 + MUD 爱好者**，不是 WoW/原神的大众玩家。文本 MUD 玩家是**自我筛选**进入的群体--他们选择 MUD 而非图形游戏，恰恰**因为**想要文字探索、想要在自己脑中建构地图的挑战。player-psychology.md §1.1 自己承认「世界规模本身是第一驱动力」「区域名本身就是『想去看看』的钩子」（`d/REGIONS.h` 35 区域）。把这群人用大众留存曲线衡量是类别错误。

MDR 反复引用 BotW/TotK/原神/艾尔登法环/WoW/FFXIV 作为对标（§1.3、§3.3、§4.5）。但这些是**图形开放世界**，其导航预期（小地图、POI 标记、传送点）建立在「玩家无法在脑中持有 3D 空间」的前提上。文本 MUD 的空间是**一维方向链**（`exits` 方向映射，`d/village/alley1.c:14-17`），玩家本就在用文字建构心智地图--这正是 MUD 的核心玩法，不是要被消除的摩擦。

**（2）范围混淆：6414 房间是 LPC 全量，MVP 只有 ~30-500 房间。**
commercialization.md §0.3 已确认：「MVP 场景清单已收窄到『华山村+扬州子集+少林+沿途』」。`m2_mvp_scene.yaml` 实测约 30 房间（creator-perspective.md §3.1）。在 30 房间规模下谈「6414 房间导致 D1 流失」是稻草人论证--MVP 的扬州子集根本不是 441 房间的全扬州。MDR 用 LPC 全量世界的迷路风险论证 MVP 必须加 fast travel，但 MVP 范围已经通过场景收窄解决了这个问题（10 号票决策）。fast travel 是在解决一个 MVP 不会遇到的问题。

**（3）「迷路」在 MUD 里是留存钩子还是流失点，缺乏一手玩家数据支撑。**
player-psychology.md 与 MDR 都把「迷路」默认为负体验，但没有任何 LPC 时代的玩家行为数据支持「迷路导致流失」。相反，`d/village/alley1.c:12` 的 long「正人君子是不会往那边走去的」、`d/village/eroad1.c` 的「往东就是出村的路了」表明**房间文案主动在制造方向悬念**--这是设计意图，不是无意的迷路。把作者刻意写的悬念当 bug 修掉（用地图概览提前剧透方向），是在破坏 player-psychology §1.1 识别的第二驱动。

### 裁决建议

- **驳回「D1 高危流失」的定性**。在缺乏 LPC 时代玩家行为数据、且 MVP 场景已收窄到 ~30 房间的前提下，此风险被高估。降级为「需观察项」：MVP 上线后用埋点（commercialization §3.3 已建议移动事件埋点）实测新手在哪个房间流失，再用数据决定是否补方位感。
- **要求 MDR 区分「LPC 全量 6414 房间」与「MVP ~30 房间」两个语境**。在 MVP 语境下重写 §1.3/§2.3 的风险评级。
- **采纳 player-psychology §六 底线 1（房间标注当前区域归属）与底线 5（主干道渐进提示）**，作为比「地图概览+fast travel」更轻、不剧透的方案。区域归属数据 `d/REGIONS.h` 已存在（35 区域 `region_names`），engine 对照显示 `world.py:97` `room_ids` 无区域分组（engine-comparison N2）--补区域标签是数据层小改，不是引入 fast travel 层。

---

## 质疑 3：玩家船 591 行「不值得复刻」论证不充分，且与另外两份报告冲突

### 被质疑结论

- MDR §4.5 判定：「玩家船网格导航系统**不值得原样复刻**...用『渡船式』定时航线即可覆盖 90% 体验，砍掉网格导航/暗礁/抢船/沉船销毁。」
- MDR §4.3：「10 档随机事件 `ship.c:143-183` 全是空文案，无任何机制后果。」
- MDR §5.2：「沉船销毁全背包...现代设计几乎不这么做。」

### 质疑

**（1）「90% 体验」是无依据的百分比，且忽略了 ship.c 的独有机制。**
MDR 断言渡船式定时航线覆盖「90% 体验」，但没有论证这 90% 是什么、剩下 10% 是什么。核查 `inherit/room/ship.c`，ship 有三类渡船无法替代的独有机制：
- **网格导航 + 瞭望/定位的信息玩法**（`ship.c:341` `do_lookout` 算最近岛屿方位、`ship.c:423` `do_locate` 算距港口海哩数且非巫师有 10% 抖动 `ship.c:448`）。这是「玩家拼凑信息找岛」的探索机制（player-stories US-6 验收：瞭望辨识方位、定位报距离有误差）。渡船式定时航线没有这层信息获取玩法。
- **荒岛守船的社交/策略张力**（`clone/ship/harbor.h:27` `wildharbors = ({"/d/island/icefire1"})`，`ship.c:549` 荒岛需等 100s 让人守船）。player-stories US-9 把这列为独立故事。渡船没有荒岛概念。
- **PvP 抢船**（`ship.c:475-482` `is_owner` 按 `combat_exp` 比较）。player-stories US-10、player-psychology §5.2 都把它当社交留存点。

把这三类一笔勾销说「渡船覆盖 90%」，是低估了 ship 的玩法深度。

**（2）「10 档随机事件全是空文案」是过度概括，红队核查证伪。**
红队核查 `inherit/room/ship.c:143-183` 实际代码：
- case 0/1/2（海怪/财宝/海盗）确实是注释占位空实现（`/* monster 海怪 */ break;`）。
- **case 3-9 共 7 档是已实现的 `tell_room` 氛围文案**：case 3 神迹青光、case 4 Titanic 幽灵船、case 5 燃烧火鸟、case 6 海妖歌声、case 7 大海眼、case 8 美人鱼、case 9 极光（带多层 ANSI 色彩）。

MDR 把这 7 档已实现文案称「空文案无机制后果」，是用**图形游戏的「机制=数值效果」标准**衡量文本 MUD。在文本 MUD 里，`tell_room` 氛围事件**就是玩法**--player-psychology §1.1 明确「房间 long 文案是第二驱动」。航海中的极光/美人鱼/Titanic 彩蛋是长途航行的氛围回报，与陆地房间的 `long` 悬念广告等价。MDR 在陆地文案上承认沉浸价值（§5.1 保留「户外昼夜相位广播」），在航海文案上却称「空壳」，标准不一。

**（3）MDR 的「砍 ship」与 abstraction-options、commercialization 直接冲突。**
- abstraction-options.md §4.3 方向 B（推荐基线）明确要建「载具实体 + 周期调度 + 动态 exit 绑定」三层抽象，并说「为未来马车/飞行器留位」「修复 engine ferry 缺船 room 的偏差」--这个抽象**正是为了支撑 ship**。MDR 砍 ship，等于让 abstraction-options 方向 B 的载具抽象失去一半论证依据。
- commercialization.md §2.3 把玩家船识别为「体验型消费点」（非 pay-to-win）：航海抗风浪 buff、触礁保险、荒岛救援召唤都是合规的便利性付费。§5.1 还列了 post-MVP ship 抽象的预留项。MDR 砍 ship，等于砍掉 commercialization 识别的一个商业化方向。

**（4）「沉船销毁全背包=现代设计不这么做」是大众游戏标准，非 MUD 标准。**
MUD 玩家群体普遍接受高惩罚（permadeath 在 many MUD 变体中存在）。player-psychology §5.2 虽标「毁灭性损失」，但其底线 4 的建议是「交通意外应分级（轻损/重损/全损），全损只在玩家明显冒险时触发」--这是**分级改造**，不是**砍掉**。MDR 把 player-psychology 的「分级」偷换成「砍掉沉船销毁」，夸大了改造的激进程度。且 commercialization §2.3 已指出「触礁保险（不沉只受损）」本身就是付费点--惩罚越重，保险消费点越有价值。MDR 没有把这层商业逻辑纳入权衡。

### 裁决建议

- **驳回 MDR §4.5「玩家船不值得复刻」的笼统判定**。修正为：**MVP 不做玩家船**（CLAUDE.md 场景清单列的是「渡口/渡船」非「船只航海」，本就不在 MVP 范围，无需 MDR 来砍）；但**引擎应保留载具抽象（abstraction-options §4 方向 B）**，为 post-MVP 玩家船/马车/飞行器留位。
- **要求 MDR 修正「10 档随机事件全是空文案」**为「3 档（case 0-2）未实现、7 档（case 3-9）已实现为氛围文案」。
- **采纳 player-psychology §六 底线 4 的「惩罚分级」改造**（轻损/重损/全损），而非 MDR 的「砍掉沉船销毁」。`time_out`（`ship.c:49` 900+random(500) 秒无操作翻船）在单机下确实不合理（玩家可能 AFK），应改安全靠岸而非翻船--这一点 MDR 与 player-psychology 一致，可采纳。
- **沉船销毁全背包**（`ship.c:519-527` `do_drop` 仅保留 `tie lian`）：建议保留为「全损档」但改为玩家可选择的冒险行为（如无视暴风警告仍出海），而非随机触发。这与 commercialization 的「触礁保险」付费点协同。

---

## 质疑 4：昼夜放慢到「1-2 小时」与天气「机制化」是过度现代化，且破坏 day_shop 玩法

### 被质疑结论

- MDR §3.3 判定：「昼夜循环周期建议放慢（1-2 小时级），让『时间』成为玩家可规划的资源而非背景噪声。」
- MDR §3.3 判定：「天气**应从纯文案升级为机制变量**（至少影响视野/移动消耗/特定 NPC 出没）。」

### 质疑

**（1）放慢昼夜会破坏 day_shop 门控玩法与「单会话见全日」的沉浸优势。**
LPC 昼夜 24 真实分钟一轮（`natured.c:46-48` 注释「1 minute == 1 second in RL」，8 时段 length 合计 1440 分钟=1440 秒）。红队核查 `day_shop` 房间：`d/city/` 下至少 10 间商店 gated by 时段（钱庄 `qianzhuang.c`、当铺 `dangpu.c`、药铺 `yaopu.c`、酒楼 `jujinge.c`、酒店 `jiuguan.c`、杂货铺 `zahuopu.c`、书院 `shuyuan.c`、打铁铺 `datiepu.c`、茶馆 `chaguan.c`、天宝阁 `tianbaoge.c`），`cmds/std/go.c:101-103` 在 `event_night`/`event_midnight` 拒绝进入。

24 分钟一轮意味着**玩家在一个会话内必然经历昼夜**，day_shop 门控因此是「现在去不了，等几分钟天亮了再来」的轻度节奏--这是**feature**。放慢到 1-2 小时后，玩家可能整个会话都是夜里，10 间商店全程关门，day_shop 从「节奏」退化为「要么等一小时要么下线」的死锁。MDR 称快循环「让时辰失去仪式感」（§3.3），但没考虑放慢会让 day_shop 玩法失效。player-psychology §4.2 反而肯定「时段是唯一稳定的环境节拍」「sunrise 自动存档给玩家隐性每日仪式锚点」（`natured.c:83` `event_sunrise`）--快循环支撑了这种仪式感。

**（2）「时间成为可规划资源」假设玩家想规划，但 MUD 玩家要的是氛围而非日程表。**
MDR §3.3 的论证是「让时辰成为玩家可规划的资源」。但这把 MUD 变成了带日程的模拟经营。文本 MUD 的时段价值是**氛围异变**（player-psychology §4.2：dawn「东方微曦」、evening「馀晖火红」的 ANSI 色彩广播），不是「18:00 去打铁铺」的规划工具。MDR 的现代化方向会把时段从「沉浸」推向「效率」，与 §0 声称要保留的「文本沉浸感」反向。

**（3）天气「机制化」是范围蔓延，且与 ADR-0001 无关。**
LPC 天气是死代码（`natured.c:11` `weather_msg` 全库零引用，source-inventory §0.3、mechanisms §9.1、engine-comparison §1.2 多方证实）。ADR-0001 明确「不做 LPC 行为等价验证」--所以没有义务还原 5 档天气。engine 已有 2 态天气（`nature.py:37` CLEAR/RAIN）+ `ON_NATURE_CHANGE` 事件点（`nature.py:29`），**MVP 够用**。MDR 推「天气影响视野/移动/NPC 出没」是纯新增机制设计，属于 post-MVP 范畴（CLAUDE.md 架构不变量 5：M3 最小切片=包外声明式内容包->加载->可玩，不含天气机制化）。在调研阶段就判「天气应升级为机制变量」是越界给 MVP 加需求。

engine-comparison.md §1.2 的判定更克制：「双方都未把天气接入视野/移动等机制」--这是「一致」而非「遗漏」。MDR 单方面把它升格为「应现代化」，与 engine-comparison 的对照结论冲突。

### 裁决建议

- **驳回 MDR §3.3「放慢到 1-2 小时」的判定**。采纳 engine 现状（`nature.py:148` `game_minutes_per_tick=1`，与 LPC 60:1 同节奏）。若题材包要放慢，由题材包 YAML `nature: { game_minutes_per_tick }` 自决（engine 已支持，ugc-surface §3.1），**不在引擎层强制**。day_shop 门控（`go.c:101-103`）依赖快循环，放慢需同步评估对 10+ 商店的影响。
- **驳回 MDR §3.3「天气应升级为机制变量」的「应」**。改为：MVP 保持天气为文案（engine 2 态 + `rain_desc_msg` 二维文案已超越 LPC 死代码）；天气机制化列 post-MVP backlog，由需要该玩法的题材包用 `ON_NATURE_CHANGE` 事件点（`nature.py:517`）自行订阅实现。
- **采纳 MDR §5.3「别把 LPC 空壳当遗产还原」**（天气 5 档是死代码，不照搬）--这一点 MDR 是对的，与 source-inventory §0.3 一致。

---

## 质疑 5：渡船「纯被动等待=枯燥」忽略了节奏价值，且付费跳过与免费红线张力未澄清

### 被质疑结论

- MDR §4.5 判定：「渡船作为『跨水域门控』保留，但应把等待窗口变成可互动时间...或允许付费优先/包船跳过等待（消费点）。」
- MDR §5.2：「渡船纯被动等待...等待窗口可互动化（船上事件/交易）或允许付费优先。」

### 质疑

**（1）55 秒等待是节奏设计，不是 bug。**
`inherit/room/ferry.c` 的 call_out 链（`ferry.c:90` on_board 15s + `:111` arrive 20s + `:138` close_passage 20s ≈ 55s）制造的是**跨水域的仪式感**--player-psychology §5.1 明确：「55 秒同步等待窗口是天然的社交停留点」「错过上船则 exits/enter 被删，需重新 yell，制造『等下一班』的群体节奏」。gameplay-slices §3 把渡口列为独立切片，验收含「错过窗口被留岸」的轻度紧张感。

MDR 在多人语境承认这是社交停留点，在单机语境直接判「枯燥」并要改--但单机下 55 秒也是**让玩家看一眼江面文案、读 `item_desc`（`d/shaolin/hanshui1.c` 「近岸处有一叶小舟」）**的时间。engine 把渡船改成纯定时翻转（`ferry.py:102-113` `_on_ferry_tick` 无 yell 无船房，engine-comparison §5 N4）已经**丢掉了喊船+登船房+渡河叙事**的交互性。MDR 不去批评 engine 丢了交互性，反而建议再叠加「付费跳过等待」，等于把渡船从「有节奏的体验」推向「花钱跳过的摩擦」。

**（2）「付费优先/包船」与不 pay-to-win 红线的边界没澄清。**
commercialization.md §2.2 明确渡船「完全免费」，付费只能「缩短等待（时间便利）」且「绝不可付费锁渡口本身」。但 MDR §4.5 的「包船跳过等待」措辞模糊--「包船」是包一艘专属船（便利）还是包一条专属航线（锁可达性）？若是后者就踩 commercialization §5.2 的红线「付费解锁渡口可达区域=力量优势」。MDR 没有区分这两种「包船」。

**（3）「等待窗口可互动化」是范围蔓延且无具体方案。**
MDR 说「把等待窗口变成可互动时间（船上事件/交易/对话）」但没给任何具体设计。在 ferry.c 的模型里，渡船房间（`query("boat")`）就是一个普通 ROOM，玩家本来就能 `look`、能与同房 NPC 对话。engine 丢掉船房（engine-comparison §5）后，玩家根本不在「船上」，没有等待窗口可互动。MDR 的建议前提（有船房）已被 engine 砍掉，建议落空。

### 裁决建议

- **采纳 engine-comparison §5 的判定**：engine ferry 丢掉船房+ yell 交互是**负面偏差（N4）**，应补回船房实体与 yell 触发（abstraction-options §4.2 已指出 engine ferry 缺船 room）。这比 MDR 的「付费跳过等待」更贴合 LPC 体验。
- **驳回 MDR §4.5「付费优先/包船跳过等待」**作为 MVP 建议。改为 post-MVP 商业化方向（commercialization §2.2 已列），且须明确「包船=专属船便利」非「包航线=锁可达性」。
- **保留渡船 55s 等待作为节奏 feature**。单机下若担心 AFK，可加宽限（player-psychology §5.1 已提），但不改为互动化或付费跳过。

---

## 质疑 6：MDR 与 player-psychology 的内部矛盾需评审委员会显式裁决

### 被质疑的跨文件矛盾

| 议题 | MDR 立场 | player-psychology 立场 | 冲突 |
|---|---|---|---|
| 跳过房间序列 | fast travel「必须」（§2.3） | 自动寻路「会消解探索」，反对（§六底线5） | **直接冲突** |
| 迷路 | 「必然事件」「不是硬核特色」（§1.3） | 是探索驱动的一部分，需渐进提示而非地图剧透（§六底线5） | 方向冲突 |
| 沉船惩罚 | 「现代设计不这么做」，砍掉（§4.5） | 「分级」改造，保留全损档（§六底线4） | 激进度冲突 |
| 昼夜速度 | 放慢到 1-2 小时（§3.3） | 24 分钟是「唯一稳定环境节拍」「sunrise 仪式锚点」（§4.1-4.2） | 反向 |

### 裁决建议

- 评审委员会（Phase 3）须对这四项**逐条裁决**，不能让两份报告的矛盾结论同时进入最终报告。
- 倾向：在四项冲突中，**player-psychology 的方向更贴合文本 MUD 受众与 MVP 范围**，MDR 的方向更贴合大众图形游戏。鉴于 CLAUDE.md 明确这是 MUD 引擎（非大众 MMO），建议以 player-psychology 为基线，MDR 的现代化建议降级为「post-MVP 可选方向」。

---

## 质疑 7：MDR 未承认「累积性现代化漂移」--六条建议的合力会把 MUD 变成「带文字皮的现代游戏」

### 被质疑的系统性问题

MDR §0 声称保留「文本沉浸感」与「空间具身感」，但 §1-§4 的六条「应现代化」判定各自削弱一层沉浸：

| 现代化建议 | 削弱的沉浸维度 | 证据 |
|---|---|---|
| 补地图概览（§1.3） | 削弱「未知感」--地图剧透结构，消除 player-psychology §1.1 的「悬念广告」 | `genmap.c` 存在但不暴露证明原作有意保留未知 |
| fast travel（§2.3） | 削弱「距离感」--距离不再有重量，坐骑/渡船冗余 | `go.c:225-230` cost×2 精力消耗本是为距离赋重 |
| 天气机制化（§3.3） | 把「氛围」变「数值优化对象」--玩家从欣赏雨景转为算雨天的移动惩罚 | LPC 天气是死代码，机制化是纯新增 |
| 昼夜放慢（§3.3） | 削弱「单会话见全日」的节奏异变，day_shop 死锁 | `d/city/` 10 间 day_shop 依赖快循环 |
| 砍玩家船（§4.5） | 砍掉唯一的网格探索+信息拼凑玩法（lookout/locate） | `ship.c:341-473` 独有机制无替代 |
| 渡船付费跳过（§4.5） | 把「节奏仪式」变「花钱消除摩擦」 | `ferry.c` 55s 是 feature 非 bug |

**单条看每条都「合理」，合力看是把 MUD 的核心沉浸维度（未知/距离/氛围/节奏/探索/仪式）系统性替换为现代便利。** MDR 没有做这层「累积影响评估」--它只评估每条建议的边际收益，没评估六条叠加后「文本 MUD 还是文本 MUD 吗」。

CLAUDE.md「项目一句话」的卖点正是「核心 MUD 引擎」--若现代化漂移把核心 MUD 特质磨平，引擎就失去了与通用游戏引擎（甚至通用文字冒险引擎）的差异化。商业化上（commercialization §0.3）「探索深度是 MUD 核心留存抓手」--砍掉探索深度等于砍掉留存抓手。

### 裁决建议

- **要求最终报告（Phase 3）加入「现代化累积影响评估」章节**，显式列出每条现代化建议对「未知感/距离感/氛围/节奏/探索/仪式」六个沉浸维度的削弱，并给出「保留阈值」--超过阈值的建议降级为 post-MVP。
- **确立判据**：一条现代化建议若同时满足「削弱某个沉浸维度」+「该削弱无法通过题材包配置关闭」+「MVP 范围内无明确需求驱动」三条，则降级 post-MVP。按此判据，MDR 的 fast travel（削弱距离感+不可配置+MVP 30 房间无需求）、天气机制化（削弱氛围+不可配置+无需求）、昼夜放慢（削弱节奏+部分可配但 day_shop 依赖快循环）三条应降级。

---

## 附录：本红队未质疑的 MDR 结论（承认正确）

为公平起见，列出 MDR 中红队核查后**认同**的判定：

1. **§5.1 保留「纯文本方向移动 + exits 方向映射」**（`d/village/alley1.c:14-17`、`feature/move.c:47`）--正确，这是 MUD 空间基底，engine `commands.py:414` `_cmd_go` 已合理继承。
2. **§5.1 保留「逐房间 cost + 精力/负重消耗」**（`alley1.c:21`、`move.c:16-29`）--正确，赋予地形与重量意义。
3. **§5.1 保留「户外昼夜相位广播」**（`natured.c:71`、`natured.c:144`）--正确，文本氛围核心。
4. **§5.1 保留「门（开/关/锁）状态」**（`room.c:158-275`）--正确，空间门控基础。
5. **§5.3「别把 LPC 空壳当遗产还原」**（天气 5 档死代码、6/8 event_fun 空操作）--正确，source-inventory §0.3、mechanisms §8.3/§9.1 多方证实。
6. **§4.5「坐骑体力机制保留，补恢复回路」**--正确，engine 缺吃草恢复（`components.py:577` RoomResources 注释「grass 未打通」），59 个 `resource/grass` 房间（红队核查）无消费方，是真实缺口。
7. **§5.2「随机事件空壳要么接机制要么砍掉」**（指 ship case 0-2 未实现部分）--正确，但应限定为 case 0-2，不含 case 3-9 已实现氛围文案（见质疑 3）。

---

## 证据索引

### LPC 一手源码（红队核查）
- `clone/obj/genmap.c`（BFS 地图生成器，作者 chu@xkx，1998-05-09，`#define MAX_NODE 5`，注释「may cause server crash, we try to be very prudent」）--证明寻路工具存在但未暴露玩家
- `clone/obj/mapdb.c`（路径数据库，`query_room_exits`/`query_map`）--同上
- `inherit/room/ship.c:143-183`（随机事件 case 0-9，红队核查 case 3-9 已实现 `tell_room` 氛围文案）
- `d/city/qianzhuang.c` / `dangpu.c` / `yaopu.c` / `jujinge.c` / `jiuguan.c` / `zahuopu.c` / `shuyuan.c` / `datiepu.c` / `chaguan.c` / `tianbaoge.c`（10 间 day_shop 商店，依赖昼夜快循环）
- `cmds/std/go.c:101-103`（day_shop 夜间门控）
- `cmds/std/go.c:225-230`（骑乘/步行 jingli 消耗 cost×2）
- `clone/horse/*.c`（21 个马匹，value 10-500 梯度）
- `d/` 下 59 个 `resource/grass` 房间（马匹吃草恢复点，无 engine 消费方）
- `adm/daemons/natured.c:46-48`（1 真实秒=1 游戏分钟，24 分钟一轮）
- `adm/daemons/natured.c:83`（event_sunrise 自动存档仪式）
- `inherit/room/ferry.c:90,111,138`（渡船 55s call_out 周期）
- `d/village/alley1.c:9-13`（房间 long 悬念文案）

### engine 模块（批判对照）
- `engine/src/openmud/nature.py:37`（Weather 2 态）/`:29`（ON_NATURE_CHANGE 事件点）/`:148`（game_minutes_per_tick=1）/`:517`（_broadcast_nature_change）
- `engine/src/openmud/ferry.py:102-113`（_on_ferry_tick 无 yell 无船房）
- `engine/src/openmud/components.py:577`（RoomResources 注释「grass 未打通」）/`:705`（Mount）/`:733,737`（精力消耗常量）
- `engine/src/openmud/commands.py:414`（_cmd_go）/`:513`（骑乘 drain）

### 被质疑文件
- `03-engine-insights/modern-design-review.md` §1.3/§2.3/§3.3/§4.3/§4.5/§5.2/§5.3
- `03-engine-insights/player-psychology.md` §1.1/§2.1/§2.3/§4.1-4.2/§5.1-5.2/§六底线1/4/5
- `03-engine-insights/commercialization.md` §0.3/§2.2/§2.3/§5.2
- `03-engine-insights/abstraction-options.md` §4.2/§4.3 方向 B
- `06-engine-critique/engine-comparison.md` §1.2/§5 N4

### 项目决策文档
- `CLAUDE.md`「项目一句话」+ 架构不变量 1/5/7
- `docs/adr/0001-no-lpc-behavior-equivalence-verification.md`（不做行为等价）
- `.scratch/mvp-scope/issues/10-mvp-scenes-selection.md`（MVP 场景收窄）
