# 红队评审：世界空间层商业化风险与 pay-to-win 陷阱

> 角色：商业化与增长专家（红队挑战席）。评审对象：Phase 1 产出（`03-engine-insights/commercialization.md` 为主，交叉 `creator-perspective.md`/`ugc-surface.md`/`modern-design-review.md`/`player-psychology.md`/`performance-review.md`/`engine-comparison.md`）。
> 立场：**挑战者**，不维护被质疑文件的结论，只找漏洞。每条质疑标注被质疑文件与段落 + LPC/engine 证据。
> 基线：[CLAUDE.md 架构不变量 6] + [mvp-scope/issues/06] 四支撑点（双货币+订阅+不 pay-to-win；创作者侧按题材包消费分成参考 Roblox/Fortnite）。

---

## 0. 评审结论速览

`commercialization.md` 的红线清单（§5.2）与四支撑点对照表（§5）方向正确，但存在 **5 类系统性盲区**：

1. **「便利性付费」边界过宽**：把「续航 buff」「触礁保险」「fast travel」全部标为「可接受便利」，忽略了「人为制造痛点再卖止痛药」与「把基础体验锁进付费」两种 predatorial 变体。
2. **分成模型的数据基础根本不成立**：`includes` 不贡献 rooms（`scene_loader.py:200`）+ `creator` 是自由字符串（`pack.py:34`）+ 透传字段不算契约（`creator-contract-v0.md:14`）三层叠加，导致「房间级 provenance」即便加上也无可承载的资产组合机制与法律效力的创作者身份。`commercialization.md` 把这三点分散列为「风险」而非合并判定「分成模型在当前 engine 形态下无法成立」。
3. **大世界规模与「横向扩展题材包」战略直接冲突**：6414 房间的官方武侠全量包在当前 engine 下根本无法产出（单文件 rooms 段天花板），「横向扩展」战略缺了官方包这个锚点；同时大世界无 fast travel 是 D1 流失高危（`player-psychology.md §2.3`），把「付费买 fast travel」标为可接受等于把留存必需品做成付费点。
4. **四支撑点的「遗漏项」未被识别**：至少 4 个支撑点缺失（跨包资产组合、版本兼容声明、内容审核、反作弊/反刷），`commercialization.md §5` 表格把它们归入「已满足」或未提，低估了商业化前置依赖。
5. **`ship.c is_owner` 红线判定悬空且定性不足**：engine 无 ship 模块（`engine-comparison.md N1`），红线清单第 4 条无法触发；更关键的是没区分「游戏内力量 PvP 规则」与「真钱替换游戏内规则」两种性质完全不同的越线。

---

## 1. 交通作为消费点：pay-to-win 红线被划得过宽

### 1.1 质疑：坐骑「付费买续航便利」是 pay-to-win 的灰色地带

**被质疑**：`commercialization.md §2.1` 「可接受的付费改造方向（便利性而非力量）」第一条「付费买续航便利：马匹 `max_jingli` 恢复速度/草场 buff（`horse.h:48-56` 的吃草恢复逻辑可参数化），不提升 `ability` 上限」。

**证据**：
- `clone/horse/horse.h:48-55`：马匹在 `resource/grass` 房间吃草恢复 `jingli`（恢复 `(max_jingli - jingli)/2`）。
- `cmds/std/go.c:226`：骑乘移动 `rided->add("jingli", -env->query("cost")*2)`，每步扣 `cost×2` 精力。
- `clone/horse/horse.h:18-30`：`jingli<=10` 坠骑 + `receive_wound("qi", 150)` 受伤。
- `engine/src/openmud/components.py:733` `MOUNT_JINGLI_PER_TERRAIN_COST` + `commands.py:513` 骑乘移动扣精力。
- `engine-comparison.md N6`：engine `RoomResources`（`components.py:577`）明注「grass 未打通」--LPC 的草地恢复机制在 engine 里**根本没实现**。

**挑战**：
- `commercialization.md` 自己承认「最贵=最强」的 `xiaohongma`（`xiaohongma.c:27-28` value=500/ability=10）是 pay-to-win 隐患，并提议把 `ability` 排除出付费。但「付费买续航」在 engine 现状下**直接等同于付费买可达性**：
  - engine 无草地恢复（`components.py:577` 未接），马匹精力是**单次消耗品**（`commands.py:513` 移动时扣，无恢复回路）。
  - 长途跨区（如华山村→少林，`d/village/hsroad1.c`→`/d/city/beimen` 跨区官道）单程消耗数匹马精力，无恢复 = 必须换马或步行。
  - 若「付费买续航」= 付费让马恢复精力（或付费买更慢衰减），则**不付费玩家跨区长途移动实际上不可行**（坠骑 + 150 qi 伤害，`horse.h:22`）。
  - 这等价于「付费解锁跨区移动」--与 `commercialization.md §5.2` 红线清单第 2 条「付费解锁渡口/船只可达区域 = 红线」性质相同，只是把「锁区域」伪装成「锁续航」。
- **红线补强建议**：续航恢复必须是**游戏内免费可获得**的基础能力（如 engine 应先接通 `RoomResources` 草地恢复，`components.py:577`），付费只能买「恢复速度加成」或「外观」，不能买「能否恢复」本身。`commercialization.md` 没有区分「恢复机制存在 vs 不存在」这两种 engine 状态下的付费边界。

### 1.2 质疑：渡口「付费缩短等待」在单机 MVP 下是 predatorial design

**被质疑**：`commercialization.md §2.2` 「商业化潜力（不 pay-to-win）：付费缩短等待：premium 货币买『优先登船』/『即时离岸』，省的是时间便利，不省能力。这与 Iron Realms 的『花钱买便利』完全吻合」。

**证据**：
- `inherit/room/ferry.c:90,111,138`：`call_out("on_board", 15)` + `call_out("arrive", 20)` + `call_out("close_passage", 20)`，单程约 55 秒被动等待。
- `player-psychology.md §5.1`：「单机语境：无其他玩家，社交停留失效。55 秒等待退化为纯等待--对单机玩家这是体验空窗」。
- `engine/src/openmud/ferry.py:102-113` `_on_ferry_tick`：engine 是**自动周期翻转**，无 `yell` 触发，玩家到岸看 `ferry_status_line`（`ferry.py:53-71`）干等。

**挑战**：
- Iron Realms 的「花钱买便利」成立的前提是「基础体验是可接受的」，付费只是锦上添花。但 LPC 渡船 55 秒 + engine 自动翻转无交互的等待，在单机 MVP 下（`player-psychology.md §5.1` 已判定为「体验空窗」）**本身就是设计缺陷**，不是「中性基础体验」。
- 在「基础等待 = 体验空窗」的前提下做「付费缩短等待」，本质是 **predatorial design（人为制造痛点再卖止痛药）**：先把等待设计得足够痛（55 秒无交互），再卖付费跳过。这与 Iron Realms 的「便利付费」不是同一回事--Iron Realms 的基础等待是多人社交窗口（有价值），这里的单机基础等待是纯损耗（无价值）。
- **红线补强建议**：渡口付费缩短等待**只有在基础等待本身被改造成可互动时间后**才允许（如 `modern-design-review.md §4.5` 建议的「船上可触发事件/交易/对话」）。若基础等待仍是纯倒计时，付费缩短 = 把设计缺陷变现，违反 [06 号票]「不 pay-to-win」精神（虽不买力量，但买的是「不被设计缺陷惩罚」）。

### 1.3 质疑：玩家船「付费抗风浪/触礁保险」是 pay-to-win 变体

**被质疑**：`commercialization.md §2.3` 「商业化潜力：体验型消费（不 pay-to-win）：航海本身是高风险探索体验，可做 premium 货币买『临时抗风浪 buff』『触礁保险（不沉只受损）』『荒岛召唤救援』。这些买的是容错便利，不买战斗力」。

**证据**：
- `inherit/room/ship.c:513-537` `do_drop()`：翻船 = 全员 `unconcious()` + **全背包销毁**（`destruct(invofusr[m])`，唯一保留 `tie lian` 铁链）+ 随机冲到某港口。
- `ship.c:128-132`：触礁即翻船（`jiaos` 坐标命中 ±random(3)-1）。
- `ship.c:135-141`：暴风（weather==2）+ 远海（locx>50||locy>50）+ 1% 概率翻船。
- `ship.c:423-473` `do_locate`：非巫师坐标 10% 随机抖动（`locx*9/10 + random(2*locx)/10`）--玩家**信息不足**却承担全损风险。
- `player-psychology.md §5.2`：「这是毁灭性损失…惩罚烈度与行为严重性严重不匹配…信息不足 + 全损惩罚 = 不公平感，是留存杀手」。
- `engine-comparison.md N1`：engine 完全无 ship 模块。

**挑战**：
- 「付费买触礁保险」在 `do_drop()` 全背包销毁的惩罚烈度下，不是「容错便利」，而是「用真钱规避游戏内毁灭性惩罚」。这等价于「不付费就承担全损风险，付费就免除风险」--这是保护费式 monetization，不是便利付费。
- `commercialization.md` 自己在红线清单（§5.2）把「付费买船只 PVP `is_owner` 优势」标为红线（力量优势），但「付费买触礁保险」与「付费买 PVP 优势」在「用真钱改变游戏内失败后果」这一点上是**同构的**：前者买的是「不损失背包」，后者买的是「不被抢船」，都是用真钱改变游戏内风险分布。
- 「付费买抗风浪 buff」同理：暴风翻船是 1% 概率（`ship.c:135-141`），付费买 buff = 把 1% 降到 0% = 买生存能力 = 力量优势的探索维度变体（虽非战斗力量，但是探索力量）。
- **红线补强建议**：触礁/翻船的惩罚烈度本身必须先降级（`player-psychology.md §六 底线4` 建议「轻损/重损/全损分级，全损只在玩家明显冒险时触发」），在此之后「付费买保险」才是便利而非保护费。`commercialization.md` 把惩罚改造与付费改造混在「体验型消费」一节，没区分先后顺序。

### 1.4 质疑：`ship.c is_owner` 红线判定悬空且定性不足

**被质疑**：`commercialization.md §5.2` 红线清单第 4 条「付费买船只 PVP `is_owner` 优势 = 红线」。

**证据**：
- `inherit/room/ship.c:475-482` `is_owner`：`living(ob) && userp(ob) && ob!=me && (int)ob->query("combat_exp") > (int)me->query("combat_exp")` 返回 1，视为「船主」。
- `ship.c:80-82,293-295,328-330`：`do_start`/`do_go`/`do_stop` 都先 `filter_array(all_inventory(this_object()), "is_owner", this_object(), me)`，若 `sizeof>0` 则「长这么大连一点江湖规矩都不懂？」。
- `engine-comparison.md N1`：engine 完全无 ship 模块。

**挑战**：
- **悬空**：engine 无 ship 模块，这条红线在 MVP 阶段无法触发，是「对未来不存在的系统的红线」，无约束力。
- **定性不足**：`commercialization.md` 把「付费买 is_owner 优势」笼统标为红线，但没区分两种性质完全不同的越线：
  - (a) **游戏内力量 PvP 规则**：LPC 的 `is_owner` 基于 `combat_exp`（游戏内力量），高战力玩家可占船--这是游戏内规则，本身不触 pay-to-win 红线（`commercialization.md §2.3` 自己也说「这是游戏内力量（非真钱），不触红线」）。
  - (b) **真钱替换游戏内规则**：如果把「船主优先」从 `combat_exp` 比较改成「付费玩家优先」（premium 货币买船主身份），这是**用真钱替换游戏内力量判定**，比单纯 pay-to-win 更恶劣--它破坏了游戏内公平（游戏内高战力玩家被真钱玩家剥夺船只控制权）。
- `commercialization.md` 只标了 (a) 的变体（「付费买 PVP 优势」），没识别 (b) 这个更严重的变体。如果 post-MVP 真做 ship，(b) 是必须显式禁止的。

---

## 2. 地图资产归属/版本/分成模型的漏洞

### 2.1 质疑：分成模型的数据基础在当前 engine 形态下根本不成立

**被质疑**：`commercialization.md §1.3` 「商业化建议：房间级 provenance 应升为契约字段」+ `§5` 表格支撑点 2「engine 现状：部分有，`PackManifest.creator/version` 在位但无房间级 provenance；缺口：无房间/区域级 provenance；建议预留 `rooms.*` 契约 `provenance` 段」。

**证据（三层叠加）**：
1. **`includes` 不贡献 rooms**：`engine/src/openmud/scene_loader.py:200` `_INCLUDE_ALLOWED_SECTIONS = frozenset({"items", "npcs"})`；`creator-perspective.md §F1` 明确「rooms 段不可拆分…这是大题材包的硬约束」；`commercialization.md §6 风险1` 自己承认「这意味着创作者无法把『一批房间』打包成可复用资产库供他人组合--阻碍了 Roblox 式『资产市场』的分成基础」。
2. **`creator` 是自由字符串**：`engine/src/openmud/pack.py:34` `creator: str | None = None`，`commercialization.md §6 风险3` 自己承认「无身份校验。分成需要强身份（账号体系）…它现在不能作为分成法律依据」。
3. **透传字段不算契约**：`docs/creator-contract-v0.md:14` 「透传不算契约…随时可能被未来版本收编为正式字段、改变行为，或继续保持透传。不要把自定义透传键当成稳定 API」；`commercialization.md §1.2` 自己承认「创作者现在可以塞一个 `author` 透传键，但它不在冻结契约内…随时可能被收编或丢弃，不能作为分成依据」。
4. **ADR-0009 单进程单 World**：`docs/adr/0009-single-process-single-world.md` 「单机阶段明确约定单进程只承载一个 `World`」；`creator-perspective.md §4.2` 「当前一个进程只能加载一个包（ADR-0009 单进程单 World），创作者无法把『我的地图』与『别人的 NPC 包』组合发售」。

**挑战**：
- `commercialization.md` 把上述四点分散列为「风险」或「缺口」，但没合并判定：**在当前 engine 形态下，分成模型的数据基础根本不成立**。
  - 房间级 `provenance` 字段即便加上（§1.3 建议），也无处承载--`includes` 不支持 rooms 意味着房间不能跨包组合，provenance 追溯的「混合资产」场景（官方包+UGC 房间）在架构层就不可能。
  - `creator` 字符串无身份校验意味着即使有 provenance，也无法确认「这个房间是谁写的」--作者可以随便填，平台无法核实。
  - 透传字段（`PackManifest.extra`，`pack.py:36`）是 `commercialization.md §5` 建议的「资产清单临时承载」，但 `creator-contract-v0.md:14` 明确「透传不算契约」，把分成数据基础放在透传字段上是脆弱的。
- [06 号票] 支撑点 1 要求「每一笔消费要能追溯到『题材包+物品+创作者』三元」。当前 engine：
  - 题材包 ID：`world.pack_manifest.id`（`world.py:105`）--**在位**。
  - 物品：`Currency` 单货币（`components.py:650-653`）+ `commands.py:1007,1033` 直接 `currency.amount -= price`--**无流水记录**，消费后无法回溯。
  - 创作者：`pack.py:34` 字符串--**无身份校验**。
  - 三元中两元不成立，分成机制在 engine 层根本无法启动。
- **红线补强建议**：`commercialization.md` 应显式声明「在 `includes` 支持 rooms + `creator` 升级为账号体系 + 消费流水落地之前，分成模型不是『MVP 不实现但留位置』，而是『engine 形态根本不支持』」。当前措辞「留位置」暗示只是时间问题，掩盖了架构层阻断。

### 2.2 质疑：`outdoors` 降级为 bool 使区域级分成/埋点失去前置依赖

**被质疑**：`commercialization.md §5` 表格支撑点 3「消费/参与度埋点：`world.pack_manifest.id` 是埋点锚点」+ `§4.3` 「留存指标埋点（engine 应留 hook）：移动事件、渡口等待、骑乘精力耗尽都应发出可订阅事件，供未来打点到 `pack_manifest.id`」。

**证据**：
- `engine/src/openmud/scene_loader.py:480` `outdoors=bool(data.get("outdoors", False))`--**bool 降级**，丢失 LPC `set("outdoors", "taihu")` 的区域标签字符串。
- `ugc-surface.md §1.4`：「engine 现状把两者合一为 bool 是损失…这对 Nature 广播作用域、fast travel、创作者经济（按题材包内区域统计参与度）都是前置依赖」。
- `engine-comparison.md N2`：「engine 全仓无 region/Region 概念…fast travel / 地图概览 / 区域级天气 / 区域广播等能力无挂载点」。
- LPC `d/REGIONS.h:5-39` `region_names` mapping 35 区域键（`"city":"扬州"`/`"village":"华山村"` 等）。

**挑战**：
- `commercialization.md §4.3` 建议「打点到 `pack_manifest.id`」，但只到包级。如果商业化要做「按区域统计参与度」（如「扬州城区域消费占包总消费 60%」），区域归属是前置依赖。
- engine `outdoors` 已降级为 bool（`scene_loader.py:480`），无 region 概念（`engine-comparison.md N2`），无法按区域分组埋点。
- 这影响分成模型的精细度：如果创作者 A 写了扬州区域、创作者 B 写了少林区域，两人的房间在同一个包里，包级分成无法区分谁的资产贡献更大。`commercialization.md §1.3` 提议房间级 provenance，但没把「区域级 provenance」作为中间粒度（介于包级与房间级之间）讨论，也没把 `outdoors` 降级与埋点挂钩。
- **红线补强建议**：engine 应先恢复 `outdoors` 的字符串标签语义（或新增 `region` 字段），再做埋点 hook 设计。`commercialization.md` 把埋点锚点简化为 `pack_manifest.id` 过于粗粒度，无法支撑区域级分成。

### 2.3 质疑：LPC 房间路径硬编码使「官方武侠全量包」的 provenance 不成立

**被质疑**：`commercialization.md §6 风险4` 「LPC 房间路径硬编码与 engine 键映射的迁移成本：LPC `exits` 用 `__DIR__"sroad3"` 焊死路径；engine 用 `room_ids: dict[str, EntityId]`（`world.py:97`）解耦了键与实体。但若要把 LPC 的 6414 房间作为『官方武侠包』资产导入，路径->键的映射需要一个迁移层，这影响『官方包』的创作成本与版本管理」。

**证据**：
- `d/village/alley1.c:15` `"east" : __DIR__"sroad3"`--路径硬编码。
- `d/village/alley1.c` 文件头注释 `//Cracked by Roath`--转码痕迹，非 provenance。
- LPC `d/` 6414 房间文件无任何作者/版本/来源标记（`source-inventory.md §1.1` 盘点确认）。
- `commercialization.md §1.1` 自己承认「无创作者字段：`alley1.c`/`room.c` 里没有任何作者/版本/来源标记。文件头注释 `//Cracked by Roath` 是转码痕迹，不是资产 provenance」。

**挑战**：
- `commercialization.md` 把这条标为「风险4」并放在「交红队深化」一节，但没追溯到底：**如果「官方武侠包」本身是混合来源（LPC 原作者 + 转码者 + 新引擎改写者），且无 provenance，那么官方包自身的分成基础就不成立**。
- 这影响的不是「UGC 创作者分成」，而是「官方包作为商业化锚点」的合法性：[06 号票] 商业模式是「承载靠题材包数量横向扩展」，官方包是第一个题材包，如果它的资产归属都无法追溯，横向扩展的「分成参考实现」就缺了样板。
- 更进一步：CLAUDE.md 架构不变量 2 明确「不做行为等价验证」，ADR-0001 把 LPC 源码定位为「设计灵感与术语参考，不是规格源」。这意味着 LPC 的 6414 房间**不是必须作为官方包资产导入**的。`commercialization.md` 隐含假设「官方武侠包 = LPC 6414 房间迁移」，但这个假设与 ADR-0001 冲突--新引擎的官方包应该是**新写的**，LPC 只是灵感。如果是新写，provenance 从零开始建，迁移层问题消失，但「官方包创作成本」会显著高于「迁移 LPC」。
- **红线补强建议**：`commercialization.md` 应明确「官方武侠包」是「LPC 迁移」还是「新写」，两条路的商业化前置工作完全不同。当前措辞模糊了这个战略选择。

---

## 3. 大世界规模与商业化的冲突

### 3.1 质疑：6414 房间官方包在当前 engine 下无法产出，横向扩展战略缺锚点

**被质疑**：`commercialization.md §4.3` 「增长阶段：靠 [06 号票]『题材包数量横向扩展』而非单世界做大」。

**证据**：
- `creator-perspective.md §F1`：「engine 的 `includes` 只允许 `items`/`npcs` 模板段，**不支持 rooms 段**（`scene_loader.py:200`）…6414 房间级别的官方武侠全量包无法用单份 YAML 组织」。
- `creator-perspective.md §3.2 要求2`：「单份 `scene.yaml` 装下 6414 房间不现实（m2_mvp_scene 737 行才约 30 房间，线性外推 6414 房间约 15 万行 YAML）」。
- `performance-review.md §1.3 隐患3`：「`scene_loader.load_scene` 一次性 `_build_rooms` 全量建 6414 房间，冷启动加载全图…UGC 题材包做大时加载时间随房间数线性增长」。

**挑战**：
- 「横向扩展题材包数量」战略要求平台能上架多个题材包，每个包都是独立可发布的世界。但官方武侠包（作为第一个、也是最大的题材包）在当前 engine 下**根本无法产出**：
  - 单文件 rooms 段天花板（`scene_loader.py:200`）使 6414 房间无法组织。
  - 全量加载（`load_scene`）使大包启动时间不可接受。
- `commercialization.md §4.3` 把「横向扩展」当作商业化战略，但没识别这个战略的**前置依赖是 engine 创作面与加载性能的突破**。如果 engine 不先解决 rooms 拆分与懒加载，横向扩展只是空话。
- 更深的矛盾：[10 号票] MVP 场景清单已收窄到「华山村+扬州子集+少林+沿途」（`commercialization.md §4.3` 自己引用），这意味着 MVP 阶段的官方包是小切片。但商业化战略需要「题材包数量横向扩展」，这要求每个包都有足够内容量支撑玩家付费--小切片包的付费意愿是否足够？`commercialization.md` 没讨论「多小的包能卖钱」这个阈值。
- **红线补强建议**：`commercialization.md` 应显式声明「横向扩展战略前置依赖：(a) engine `includes` 支持 rooms 或等效的多文件组织；(b) 懒加载或分区域加载；(c) 单包内容量阈值（多少房间/多少玩法切片才值得付费）」。当前战略陈述缺失这三条前置。

### 3.2 质疑：大世界无 fast travel 是 D1 流失高危，「付费买 fast travel」是 pay-to-win 变体

**被质疑**：`commercialization.md §5.2` 红线清单末行「付费买 fast travel（非战斗）= 可接受（便利）」+ `§4.3` 「LPC 无 fast travel 是过时设计」。

**证据**：
- `modern-design-review.md §1.1`：「全仓库 grep `fast_travel|recall|waypoint|teleport|minimap|map_view|auto_path|auto_walk` 在 `d/`、`feature/`、`inherit/`、`cmds/` 下零命中」。
- `modern-design-review.md §2.3 判定`：「**必须引入 fast travel 层**（已发现地点间快速移动，最好带经济/解锁成本），否则移动疲劳会劝退当代玩家」。
- `player-psychology.md §2.3`：「新手从华山村（33 房间）进入扬州城（134 房间）是典型的从『可记忆规模』跨入『不可记忆规模』的临界点…D1 流失高危」。
- `modern-design-review.md §2.3`：「LPC 把两者（探索性遍历 vs 重复性通勤）混为一谈，全部走逐房间，导致移动疲劳--跨区跑商/回门派/交任务的路途是纯时间税」。
- `engine` grep `fast_travel|recall|waypoint|teleport` 在 `engine/src/openmud/*.py` **零命中**（`modern-design-review.md §1.2` 确认）。

**挑战**：
- `modern-design-review.md` 已判定 fast travel 是「必须引入」的现代化能力，不是可选便利。`commercialization.md §5.2` 把「付费买 fast travel」标为「可接受（便利）」，等于**把留存必需品做成付费点**。
- 这与 `commercialization.md §2.2` 渡口「付费缩短等待」的 predatorial 逻辑同构：如果基础体验（无 fast travel 的长途通勤）本身是设计缺陷（`modern-design-review.md §2.3` 已判定为「过时设计」+「纯时间税」），那么「付费买 fast travel」= 把设计缺陷变现。
- 区分两种 fast travel 付费模型：
  - (a) **基础 fast travel 免费，付费买额外传送点/更远距离**：可接受（便利加成）。
  - (b) **fast travel 本身付费解锁**：不可接受（把基础体验锁进付费）。
- `commercialization.md §5.2` 没区分这两种，笼统标「可接受」。
- **红线补强建议**：fast travel 必须先作为免费基础能力引入（`modern-design-review.md §5.2` 已建议），付费只能买「额外传送点数量」「跨区域传送」等加成，不能买「能否 fast travel」本身。`commercialization.md` 红线清单应补一条「付费买基础 fast travel 能力 = 红线」。

### 3.3 质疑：大世界探索深度与新手机会流失的矛盾未被商业化消化

**被质疑**：`commercialization.md §4.1` 「6414 房间 / 35 区域…探索深度是 MUD 的核心留存抓手」+ `§4.2` 「但对新手是双刃剑」。

**证据**：
- `player-psychology.md §1.2`：「6414 房间的世界**没有渐进式发现机制**…没有任何『已探索房间数 / 区域』『本区域完成度』『此处距<地标>多远』之类的外在奖励梯度…探索欲的衰减速度完全取决于玩家内生好奇心，而外在反馈几乎为零」。
- `player-psychology.md §2.2`：「出口列表**不包含目标房间的任何信息**--你只知道『north 能走』，不知道『north 通向哪』」。
- `player-psychology.md §2.3`：「D1 流失高危…玩家不是『不喜欢这个世界』，而是『在世界里找不到自己』」。
- `commercialization.md §4.2` 自己承认：「移动消耗…无 fast travel…渡口/船只的时间门槛…这些都是**时间税**，对碎片化玩家不友好」。

**挑战**：
- `commercialization.md` 把「探索深度」当作「核心留存抓手」并用于商业化（「MVP 阶段需保留『探索深度』的留痕」），但 `player-psychology.md` 的证据表明：**当前 engine（与 LPC）的「探索深度」实际上是「迷路深度」**--无地图、无导航、无渐进反馈、出口不示目标。
- 商业化基础是留存，留存基础是体验。如果「大世界」在当前形态下导致 D1 流失（`player-psychology.md §2.3`），那么「探索深度是留存抓手」这个商业化前提就不成立。`commercialization.md` 没有把 `player-psychology.md` 的流失风险纳入商业化模型--它假设大世界=留存，但 `player-psychology.md` 证明大世界=流失（在无现代化改造时）。
- 这意味着商业化的前置不是「在大世界上做消费点」，而是「先把大世界改造成不流失的体验」（补地图、补 fast travel、补渐进反馈，见 `modern-design-review.md §5.2` 与 `player-psychology.md §六`）。`commercialization.md §4.3` 把这些标为「增长取舍建议」，但没把它们作为商业化的**硬前置**。
- **红线补强建议**：`commercialization.md` 应显式声明「商业化前置依赖体验现代化：地图/fast travel/渐进反馈必须先免费落地，否则大世界留存不成立，消费点设计无意义」。

---

## 4. 四支撑点的遗漏项

### 4.1 质疑：支撑点 4「世界实例隔离」被标为「已满足」，但忽略了它对 Roblox 模式的阻断

**被质疑**：`commercialization.md §5` 表格支撑点 4「世界实例隔离：engine 现状：`World` 单进程单 World（ADR-0009）；`pack_manifest` 是实例身份；缺口：已天然隔离，无缺口；已满足」。

**证据**：
- `docs/adr/0009-single-process-single-world.md`：「单机阶段明确约定单进程只承载一个 `World`」。
- [06 号票]：「创作者侧按题材包消费分成（参考 Roblox/Fortnite）」。
- `creator-perspective.md §4.2 缺口`：「当前一个进程只能加载一个包（ADR-0009 单进程单 World），创作者无法把『我的地图』与『别人的 NPC 包』组合发售…它限制了『地图作者 + 剧情/NPC 作者协作分成』这类模式」。
- Roblox/Fortnite UEFN 模式的核心是 **asset 可组合**：一个 game 用别人的 asset（模型/脚本/地图块），按 asset 消费分成。

**挑战**：
- `commercialization.md` 把支撑点 4 标为「已满足」，依据是「单进程单 World 天然隔离」。但 [06 号票] 参考的 Roblox 模式**不是「每个 game 独立进程」**，而是「一个 game 内组合多个创作者的 asset」。
- ADR-0009 单进程单 World + `includes` 不支持 rooms（`scene_loader.py:200`）共同阻断了 Roblox 式资产组合：创作者无法把「我的地图」与「别人的 NPC/房间」组合成一个可发售的包。
- 这意味着 `commercialization.md §5` 把支撑点 4 标「已满足」是**误判**：它满足的是「世界实例隔离」（每个包独立进程），但没满足「资产可组合」（一个包内多个创作者协作）。后者才是 Roblox 分成模式的核心。
- **红线补强建议**：支撑点 4 应拆分为 (a) 世界实例隔离（已满足）+ (b) 跨包/包内资产组合（未满足，被 `includes` 限制 + ADR-0009 阻断）。`commercialization.md` 应承认「Roblox 式分成模式在当前 engine 形态下无法成立」，而非把支撑点 4 标为「已满足」。

### 4.2 质疑：支撑点 2「题材包资产元数据」遗漏版本兼容性声明

**被质疑**：`commercialization.md §5` 表格支撑点 2「engine 现状：`PackManifest` 有 `id/version/creator/title`；建议预留 `rooms.*` 契约 `provenance` 段」。

**证据**：
- `engine/src/openmud/pack.py:22` `_KNOWN_FIELDS = frozenset({"id", "version", "creator", "title"})`--无「依赖引擎版本」字段。
- `creator-perspective.md §4.2 缺口`：「无版本兼容性声明：`manifest.yaml` 只有 `version` 字符串，没有『依赖引擎哪个版本』『依赖哪些能力』的声明。创作者升引擎后旧包是否还能跑，没有契约。这对平台化（一个平台跑多个不同版本题材包）是潜在摩擦点」。
- `operator-stories.md E2`：「`manifest.yaml` 无『依赖引擎版本』声明，无法提前声明兼容范围」。

**挑战**：
- 商业化要求「已购买/已分成的包在引擎升级后仍可用」。如果引擎升级破坏旧包，玩家付费购买的包失效，这是商业风险（退款/信任损失）。
- `PackManifest.version`（`pack.py:30`）是**包自身版本**，不是「依赖引擎版本」。两者不同：包 v1.0 可能依赖 engine v1.2 的 `ferry` 能力，engine 升级到 v2.0 改了 `ferry` 语义，包 v1.0 就可能跑不了。
- `commercialization.md` 完全没提这个支撑点缺口。`creator-perspective.md §4.2` 与 `operator-stories.md E2` 都识别了，但 `commercialization.md` 没纳入。
- **红线补强建议**：支撑点 2 应补「版本兼容性声明」子项：`PackManifest` 预留 `engine_compat` 字段（或能力依赖声明），engine 加载期校验包声明的兼容版本。这是商业化的基础信任机制。

### 4.3 质疑：完全未讨论「内容审核」支撑点

**被质疑**：`commercialization.md` 全文未提及内容审核。

**证据**：
- [ADR-0005] + [ADR-0012]：UGC 包禁止可执行逻辑（防代码层安全），但**文本内容**（房间 `long` 描述、NPC 对话、`time_msg`/`desc_msg` 文案）不受限。
- `creator-contract-v0.md`：`rooms.*` 的 `long`/`short`/`details` 等字段是自由文本。
- `commercialization.md §3.1`：「创作者可用声明式 YAML 摆房间、连出口、设门、配 objects、设 ferry/cost/terrain/outdoors 等」--全部是文本/数据，无审核机制。

**挑战**：
- 商业化平台（Roblox/Fortnite UEFN）都有内容审核：违规文本/版权侵权/不适内容必须可检测与下架。
- `commercialization.md` 讨论了 UGC 创作面（§3.1）、分成模型（§3.2）、engine 预留位置（§3.3），但完全没提「如果创作者在房间文案里放违规内容（如仇恨言论、版权侵权文本），engine/平台如何检测与拦截」。
- 这不是 MVP 必做，但作为商业化支撑点应「留位置」--至少 engine 应支持「包内容文本导出」供外部审核管道消费。当前 `--validate`（`commercialization.md §5` 提及）只校验语法/引用，不导出文本供审核。
- **红线补强建议**：补支撑点 5「内容审核导出」：engine 应支持把包内所有文本字段（`long`/`short`/`details`/`time_msg`/`desc_msg`/NPC 对话）导出为可机器审核的清单，供 post-MVP 平台审核管道消费。

### 4.4 质疑：完全未讨论「反作弊/反刷」支撑点

**被质疑**：`commercialization.md` 全文未提及反作弊/反刷。

**证据**：
- `clone/horse/horse.h:7` `condition_check()`：挂 NPC `chat_msg`（`baima.c:34-37` `chat_chance=50`），是**概率触发**--玩家可挂机让马匹自然衰减/恢复，无防刷机制。
- `inherit/room/ship.c:143-183`：`!random(40)`（1/40）触发 10 种随机海事件--可反复出海刷事件（虽然 `commercialization.md` 建议 ship post-MVP，但机制本身在 LPC 已有）。
- `clone/horse/horse.h:48-55`：马匹吃草恢复 `(max_jingli-jingli)/2`--玩家可在草地房间反复进出刷恢复。
- `commercialization.md §3.3`：「在 `_buy`/`_buy_mount`/`go`/`_on_ferry_tick`/骑乘精力耗尽等点发出可订阅事件，供未来打点到 `pack_manifest.id`」--埋点是为了分成，不是为了反刷。

**挑战**：
- 商业化需要防刷：如果「付费买马匹续航 buff」做成消费点（`commercialization.md §2.1` 建议），玩家会找最便宜的刷续航方式（如反复进出草地刷 `horse.h:48-55` 恢复），导致付费点失效。
- 如果「付费缩短渡口等待」做成消费点（`commercialization.md §2.2` 建议），玩家会找替代路径（如绕路）或挂机等免费等待，付费转化率低。
- 这些反刷机制在 engine 层完全没有位置：`commands.py` 的消费是直接 `currency.amount -= price`（`commands.py:1007,1033`），无冷却、无频次限制、无异常检测。
- `commercialization.md` 讨论了「消费三元组」（§3.2）与「埋点 hook」（§3.3），但都是为了分成追溯，不是为了反刷检测。反刷需要的是「同一玩家短时间内高频消费/恢复的异常检测」，这是另一套数据管道。
- **红线补强建议**：补支撑点 6「反刷/反作弊埋点」：消费/恢复事件应携带玩家身份 + 时间戳 + 频次，供 post-MVP 反刷管道检测异常模式。`commercialization.md §3.3` 的埋点建议应扩展为「分成追溯 + 反刷检测」双用途。

### 4.5 质疑：支撑点 1「货币/账本抽象」遗漏双货币兑换汇率

**被质疑**：`commercialization.md §5` 表格支撑点 1「engine 现状：`Currency`（`components.py:650-653`）单货币银两；建议：`Currency` 升级为双货币形状；消费调用点经可插拔账本接口；MVP 单货币+空账本即可」。

**证据**：
- `engine/src/openmud/components.py:650-653`：`class Currency: amount: int = 0`--单值。
- `engine/src/openmud/commands.py:1007,1033`：`currency.amount -= price`--直接扣，无货币类型区分。
- [06 号票]：「玩家侧照 Iron Realms（双货币 + 订阅 + 不 pay-to-win）」+ 「双货币（免费金币 + 真钱 premium 点数，**可在玩家间市场互换**）」。
- Iron Realms 模式的核心是「免费货币与 premium 货币可在玩家间市场互换」--这是其不 pay-to-win 的关键设计：免费玩家靠肝获取免费货币，在市场换成 premium 货币买便利；付费玩家用真钱买 premium 货币加速。

**挑战**：
- `commercialization.md §5` 把支撑点 1 简化为「`Currency` 升级为双货币形状 + 可插拔账本」，但完全没提「双货币兑换汇率」这个核心商业设计。
- Iron Realms 的「可在玩家间市场互换」意味着：
  - 需要市场抽象（玩家间交易 premium 货币）。
  - 需要汇率机制（免费货币换 premium 的比率，是固定还是浮动？）。
  - 需要反刷机制（防止免费玩家刷免费货币换 premium，冲击付费转化）。
- 这三个子项在 engine 层完全没有位置，`commercialization.md` 也没提。
- 如果只做「双货币形状」而不做「兑换市场」，Iron Realms 模式就不成立--免费玩家无法获得 premium 货币，付费墙就出现了，违反「不 pay-to-win」。
- **红线补强建议**：支撑点 1 应拆分为 (a) 双货币形状（`Currency` 升级）+ (b) 货币兑换市场抽象（玩家间互换）+ (c) 汇率机制（固定/浮动）+ (d) 反刷（防免费货币刷 premium）。`commercialization.md` 只提了 (a)，遗漏 (b)(c)(d)。

---

## 5. 综合判定：`commercialization.md` 的「最该留位置三件事」不足以支撑商业化

**被质疑**：`commercialization.md §0 结论4` 「最该在 engine 留位置、MVP 不实现的三件事：(a) 双货币账本与『消费三元组（题材包+物品+创作者）』流水；(b) 房间/区域级 provenance 扩展字段；(c) 可打点到 `pack_manifest.id` 的事件埋点 hook」。

**挑战**：
基于上述 1-4 节，这三件事不够。应扩展为**至少七件**：

1. 双货币账本 + **兑换市场抽象 + 汇率机制 + 反刷**（不只是「双货币形状」）。
2. 房间/区域级 provenance + **`includes` 支持 rooms 或等效资产组合机制**（否则 provenance 无处承载）+ **`creator` 升级为账号身份**（否则无法律效力）。
3. 消费埋点 hook + **反作弊/反刷埋点**（双用途）+ **区域级粒度**（`outdoors` 恢复字符串或新增 `region` 字段）。
4. **跨包/包内资产组合能力**（支撑 Roblox 分成模式，当前被 ADR-0009 + `includes` 阻断）。
5. **版本兼容性声明**（`PackManifest.engine_compat`，防引擎升级破坏旧包）。
6. **内容审核导出**（文本字段导出供审核管道）。
7. **fast travel 作为免费基础能力**（商业化的体验前置，非付费点）。

`commercialization.md` 的三件事只覆盖了 1-3 的表层，遗漏了 1-3 的深层子项与 4-7 全部。

---

## 附：证据索引

### LPC 一手源码
- `inherit/room/ferry.c:90,111,138` - 渡船 call_out 周期（55 秒等待）
- `inherit/room/ship.c:475-482` - `is_owner` 基于 `combat_exp` 比较
- `inherit/room/ship.c:513-537` - `do_drop` 全背包销毁（除 `tie lian`）
- `inherit/room/ship.c:128-132,135-141` - 触礁/暴风翻船
- `inherit/room/ship.c:423-473` - `do_locate` 非巫师坐标 10% 抖动
- `clone/horse/horse.h:7-41` - `condition_check` 体力衰减/坠骑
- `clone/horse/horse.h:18-30` - `jingli<=10` 坠骑 + `receive_wound("qi", 150)`
- `clone/horse/horse.h:48-55` - 草地吃草恢复 `(max_jingli-jingli)/2`
- `clone/horse/xiaohongma.c:26-28` - `wildness=20000, value=500, ability=10`
- `clone/horse/xiaohongma.c:50-51,101-171` - `do_duhe`/`do_escape` 独占技能
- `cmds/std/go.c:226` - 骑乘移动 `rided->add("jingli", -cost*2)`
- `d/village/alley1.c:15` - exits 路径硬编码 `__DIR__"sroad3"`
- `d/REGIONS.h:5-39` - 35 区域 `region_names` mapping

### engine 模块
- `engine/src/openmud/pack.py:22,26,30,34,36` - `PackManifest`（`_KNOWN_FIELDS` 无 `engine_compat`；`creator: str | None`；`extra` 透传）
- `engine/src/openmud/scene_loader.py:200` - `_INCLUDE_ALLOWED_SECTIONS = frozenset({"items", "npcs"})`（rooms 不支持）
- `engine/src/openmud/scene_loader.py:480` - `outdoors=bool(...)` 降级为 bool
- `engine/src/openmud/components.py:577` - `RoomResources` 明注「grass 未打通」
- `engine/src/openmud/components.py:650-653` - `Currency` 单值 `amount: int`
- `engine/src/openmud/components.py:705-737` - `Mount`/`Riding`/`Terrain` + 移动精力常量
- `engine/src/openmud/commands.py:1007,1033` - `currency.amount -= price`（无账本/流水）
- `engine/src/openmud/commands.py:513-521` - 骑乘移动扣精力 + `jingli==0` 坠骑（无 qi 扣减）
- `engine/src/openmud/ferry.py:102-113,53-71` - `_on_ferry_tick` 自动翻转 + `ferry_status_line`（无 yell/无船房）
- `engine/src/openmud/world.py:97,105` - `room_ids`/`pack_manifest`
- engine 无 `ship`/`navigate`/`harbor`/`island` 模块（`engine-comparison.md N1`）
- engine 无 `fast_travel`/`recall`/`waypoint`/`teleport`（`modern-design-review.md §1.2`）

### 决策文档
- [CLAUDE.md 架构不变量 6] - 商业化四支撑点
- [mvp-scope/issues/06] - 四支撑点原文 + Roblox/Fortnite 参考 + Iron Realms 双货币互换
- [docs/adr/0009] - 单进程单 World
- [docs/adr/0012] - UGC 禁 hooks
- [docs/adr/0001] - 不做 LPC 行为等价（LPC 是灵感不是规格）
- [docs/creator-contract-v0.md:14] - 「透传不算契约」

### 被质疑的 Phase 1 文件
- `03-engine-insights/commercialization.md` §0/§1.3/§2.1/§2.2/§2.3/§3.1/§3.2/§3.3/§4.1/§4.2/§4.3/§5/§5.2/§6
- `03-engine-insights/creator-perspective.md` §F1/§3.2/§4.2
- `03-engine-insights/ugc-surface.md` §1.4
- `03-engine-insights/modern-design-review.md` §1.1/§1.2/§2.3/§4.5/§5.2
- `03-engine-insights/player-psychology.md` §1.2/§2.2/§2.3/§5.1/§5.2/§六
- `03-engine-insights/performance-review.md` §1.3
- `06-engine-critique/engine-comparison.md` N1/N2/N6
- `02-user-stories/operator-stories.md` E2
