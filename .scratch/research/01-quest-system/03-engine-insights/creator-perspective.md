# 创作者视角：LPC 任务系统的可扩展性审视

## 1. 当前 LPC 任务创作的工作流程与门槛

### 1.1 典型的创作路径

当前《侠客行》LPC 源码中的任务并非由统一的声明式工具生成，而是**以代码为中心**、分散在 NPC、房间、物品、条件（condition）四类对象中的产物。创作者要完成一个可玩任务，通常需要以下步骤：

1. **创建/复用一个 NPC 文件**，在 `set("inquiry", ...)` 中注册任务触发词（如 `job`、`工作`、`帮务`），并在函数里写死任务分配逻辑。
2. **定义任务目标与奖励**，常见做法是把目标直接编码在 NPC 的 `ask_job()` 中，或引用外部 `.h`/`.c` 配置表（如 `/d/huanghe/changle/bangjob5000.c` 的 `bangjobs` mapping）。
3. **在玩家身上写状态**，例如 `player->set(JOB_NAME+"/target_room", ...)`、`player->set("bangs/asktime", time())` 等，任务进度完全依赖玩家对象的 dbase 键值对。
4. **创建任务专属物品**，如 `/d/shaolin/obj/letter-job.c` 的推荐信、`/d/huanghe/obj/bangling.c` 的帮令，物品本身几乎没有通用任务标记，靠 `id` 与 NPC 的 `accept_object()` 硬匹配。
5. **在房间或全局 daemon 中增加触发器**，如一灯任务链在 `yideng1.c` 的 `do_dive()` 中判定轻功并跳转房间（`/d/dali/yideng1.c`），`yideng4.c` 在 `valid_leave()` 中检查樵夫存在。
6. **注册到全局控制/奖励系统**，较规范的任务会调用 `/clone/obj/job_server.c` 的 `start_job()`、`reward()` 以记录开始时间与 exp/pot 上限；主动型门派任务则由 `/d/wizard/center.c` 统一开关。

> 证据来源：
> - `/d/city/npc/ftb_zhu.c`：`ask_job()` 触发 → `assign_job()` 生成目标房间与刺客 → `JOB_SERVER->start_job()` → `tell_job()` 结算（第 192–418 行）。
> - `/d/huanghe/npc/bangzhu.c` + `/d/huanghe/npc/bangzhu_duty.h`：`ask_job()` 根据 `levels` 选择 bangjob 文件，按类型（寻/杀/截镖/送礼/护驾/摊费/示威/买卖/伙计）分发任务（第 75–267 行）。
> - `/d/dali/yideng1.c`：房间 `do_dive()` 中根据 `dodge` 技能判定生死并移动到 `yideng2`（第 35–59 行）。
> - `/clone/obj/job_server.c`：全局奖励接口 `reward()` 按 exp_rate/pot_rate × 耗时结算经验与潜能，并写入直方图与统计（第 131–200、563–652 行）。

### 1.2 创作门槛分析

| 门槛维度 | 具体表现 |
|----------|----------|
| **编程门槛高** | 必须掌握 LPC 语法、MUDlib 继承链（`NPC`、`ROOM`、`ITEM`、`F_SAVE`）、`call_out`/`add_action` 等运行时机制。 |
| **上下文耦合重** | 任务逻辑散落在 NPC、房间、物品、玩家状态、全局 daemon 中，无法单文件自洽。 |
| **调试成本高** | 没有可视化任务流，失败/超时/并发问题需要在线运行或查看 `log_file()` 输出。 |
| **版本管理弱** | 任务数据（如 `/clone/obj/job.sav/` 下的 `.o` 数据、job_server 的 save 文件）与源码混在一起，难以分支开发。 |
| **平衡性靠经验** | exp/pot 上限、任务刷新率、NPC 强度等通过硬编码数字和经验公式人工调节，没有参数化面板。 |

> 证据来源：
> - `/clone/obj/job_server.c` 第 571–588 行：`reward_func()` 直接修改 `player->add("combat_exp", ...)` 与 `player->add("potential", ...)`，并手写 cap 逻辑。
> - `/d/wizard/center.c` 第 629–682 行：主动任务系统的开启/关闭依赖巫师手动执行 `start_system`/`close_system`，并配合 `CHANNEL_D` 全服广播。

---

## 2. 不同题材包复用 LPC 任务模式的难易度

### 2.1 武侠题材（MVP 官方包）

**难度：低，但仍有大量手工代码。**

武侠是 LPC 原生的语境：门派、师门任务、走镖、追杀、悬赏、护驾、送礼等概念可以直接复用。最大的好处是**叙事与机制天然对齐**——找刺客、送信、护镖、踢馆都是武侠文本。但创作者仍需为每个任务写 NPC 对话分支与房间触发器，不能仅通过数据表配置。

> 证据来源：
> - `/d/city/npc/ftb_zhu.c`："斧头帮" 刺客任务完整复用了武侠叙事，但目标房间选择、刺客生成、奖励公式全部硬编码在 NPC 中。
> - `/d/huanghe/npc/bangzhu_duty.h`：帮派任务类型（寻/杀/截镖/送礼/护驾/示威/摊费/买卖/伙计）是武侠/江湖语境的原子动作。

### 2.2 仙侠题材

**难度：中等。**

仙侠在武侠基础上增加了飞行、渡劫、灵根、洞府、宗门大比等机制。LPC 现有模式可以**局部复用**（如护驾 → 护送仙舟，送礼 → 送丹药），但以下能力需要扩展：

- **分层/多维空间**：仙侠常有 "下界—仙界—秘境" 多层地图，LPC 的房间 exits 是扁平的，需要引擎支持跨层传送与副本隔离。
- **时间/天劫触发**：现有 `condition` 机制（如 `hz_job.c`）只是简单倒计时，无法表达 "修炼满 30 天触发雷劫" 这种长周期事件。
- **法宝/灵宠绑定任务**：当前物品任务以 `id` 匹配为主，仙侠需要 "物品品质、灵气、绑定主人" 等属性的任务判定。

### 2.3 科幻题材

**难度：中高。**

科幻任务的核心是 **信息收集、骇入、飞船驾驶、派系声望、科技树解锁**。LPC 以 "近战击杀 + 经验潜能" 为中心的奖励模型（`/clone/obj/job_server.c` 的 `reward_func()` 只产出 exp/pot）与科幻的 "信用点、数据、图纸、声望" 奖励体系不匹配。

- **目标类型扩展**：从 "杀 NPC" 到 "骇入终端、修复设备、扫描行星、走私货物"。
- **失败条件复杂化**：任务失败可能不是玩家死亡，而是被发现、超时导致派系敌对。
- **全局状态**：需要引擎级的 faction/reputation 系统，而不是每个 NPC 自己维护 `query_temp("bangs/fam")`。

> 对比证据：
> - `/d/huanghe/npc/bangzhu_duty.h` 第 284–285 行：任务结算直接写死 `who->add("combat_exp", record)` 与 `who->add("shen", -bonus)`，没有可扩展的奖励抽象。

### 2.4 校园/现代都市题材

**难度：高。**

校园任务的典型形态是 "好感度事件链 + 时间片管理 + 分支对话"，例如：

- 周一到周五不同 NPC 在不同教室出现；
- 选择对话选项影响好感度；
- 没有战斗，也不产出经验/潜能。

LPC 当前模式对此极不友好：

- **没有对话树/选项系统**：`inquiry` 只是关键词 → 文本/函数映射，无法做分支选择。
- **没有日程/时间片机制**：虽然有 `localtime.h`，但任务里没有按星期/时段触发的例子。
- **奖励模型不匹配**：校园任务奖励应是 "好感度、道具、剧情解锁"，而非 `combat_exp`/`potential`。

### 2.5 横向对比结论

| 题材 | 机制复用度 | 需新增引擎能力 | 主要冲突点 |
|------|------------|----------------|------------|
| 武侠 | 高 | 少量封装 | 手工代码多，但概念对齐 |
| 仙侠 | 中 | 多层空间、长周期事件、法宝属性判定 | 空间模型与时间模型不足 |
| 科幻 | 中低 | 声望/派系、非战斗目标、科技奖励 | 奖励模型与失败条件过于战斗-centric |
| 校园 | 低 | 对话树、日程、好感度、剧情锁 | 完全没有非战斗任务基础设施 |

---

## 3. 必须暴露给创作者的原子能力

基于源码中反复出现的模式，以下能力应当作为题材无关的 engine 原子能力暴露：

### 3.1 任务生命周期管理

- **开始/放弃/完成/失败**：对应 `job_server.c` 的 `start_job()`、`abort_job()`、`reward()`，但应去掉硬编码的 exp/pot，改为通用奖励表。
- **超时与倒计时**：现有 `condition` 系统（`gb_job.c`、`ypjob.c`、`hz_job.c`、`lmjob.c`）的通用模式是 `duration - 1` 直到归零触发结果，应抽象为任务级 timer。

> 证据来源：
> - `/clone/obj/job_server.c` 第 95–112 行：`start_job`/`abort_job`/`get_start_time` 是生命周期原语。
> - `/kungfu/condition/ypjob.c`：duration 归零时增加失败计数 `yipin/failure`。

### 3.2 目标生成与放置

- **在指定区域/房间生成目标 NPC 或物品**：`ftb_zhu.c` 的 `put_objects()` 使用 traverser 在目标房间周围 range 内随机放置刺客；`bangzhu.c` 的 "截镖" 任务会动态创建 `BIAOTOU`。
- **路径/区域查询**：`find_target_room()` 调用 `/clone/obj/mapdb` 与 `/clone/obj/traverser`，说明任务需要知道 "某区域附近有哪些房间"。

> 证据来源：
> - `/d/city/npc/ftb_zhu.c` 第 88–156 行：`find_target_room`、`put_object`、`put_objects`。

### 3.3 条件检查与触发器

- **玩家属性检查**：战斗经验区间（`ftb_zhu.c` 的 1万–1100万）、技能值（`yideng1.c` 的 `dodge >= 120`）、门派/帮派归属（`bangzhu_duty.h` 的多处判定）。
- **物品持有/交付检查**：`accept_object()` 中检查 `bang ling` 与任务 mapping。
- **房间进入/离开检查**：`yideng4.c` 的 `valid_leave()` 检查樵夫存在。
- **对话触发**：`inquiry` 映射。

### 3.4 奖励结算

- **通用奖励表**：应支持经验、潜能、金钱、物品、技能熟练度、声望、贡献度、称号等可配置条目，而不是 `job_server.c` 里只写 exp/pot。
- **奖励上限与直方图**：`job_server.c` 的 `exp_limit`/`pot_limit` 和 `exp_hist`/`pot_hist` 是平衡性运营利器，应保留为通用指标。

> 证据来源：
> - `/clone/obj/job_server.c` 第 541–561 行：`set_exp_limit_func`/`set_pot_limit_func`。
> - `/clone/obj/job_server.c` 第 688–718 行：`print_hist_func` 输出奖励分布。

### 3.5 运营观测

- **任务统计与单玩家追踪**：`center.c` 的 `do_check_player()`、`do_check_do_job()`、`job_stat` 命令是运营不可或缺的视图。
- **全局开关**：`start_system`/`close_system` 用于开启/关闭主动任务系统。

---

## 4. 容易滥用或导致体验崩坏的能力（需要引擎限制）

### 4.1 无上限奖励与负奖励

`job_server.c` 的注释明确说："exp_rate and pot_rate are expected to be numbers between 0 and 100, but I don't check it so that you could reward some player negative or over 100%." 这在 UGC 环境下极易被滥用。

> 证据来源：
> - `/clone/obj/job_server.c` 第 119–124 行注释。

**引擎限制建议**：
- rate 强制 clamp 到 [0, 100] 或题材包声明的区间；
- 负奖励需要二次确认/白名单；
- 单任务每小时 exp/pot 上限由 engine 强制生效，不允许 NPC 代码绕过。

### 4.2 任意修改玩家属性的 "奖励"

`award.c` 只能授予 `title` 和 `9yin`，且需要 arch/admin/wizard/caretaker 权限。但 NPC 任务代码里可以直接 `player->add("max_neili", 1)`（`ftb_zhu.c` 第 382–385 行）。如果创作者能直接写玩家属性，会导致属性通胀、存档污染。

> 证据来源：
> - `/cmds/wiz/award.c` 第 17 行：权限检查 `wizhood(me)`。
> - `/d/city/npc/ftb_zhu.c` 第 382–385 行：任务奖励直接改 `max_neili`/`eff_jingli`。

**引擎限制建议**：
- 创作者只能通过声明式奖励表影响玩家；
- 对 `max_neili`、`combat_exp`、`potential` 等核心属性的写操作应走 engine 审计通道；
- 禁止 NPC 代码直接调用玩家属性的 `add()`/`set()`。

### 4.3 动态 NPC/物品的不可控生成

`ftb_zhu.c` 会动态创建刺客 NPC 并写入 `player->set(JOB_NAME+"/obj_list", obj_list)`，如果任务异常中断或玩家下线，这些对象可能残留或泄漏。`bangzhu.c` 的 "截镖" 任务动态生成 `BIAOTOU`，并用 `children()` 做全局数量限制（最多 10 个），这是运营经验积累的结果，但普通创作者不一定知道。

> 证据来源：
> - `/d/city/npc/ftb_zhu.c` 第 144–156 行：`put_objects()` 生成 obj_list 并绑定玩家。
> - `/d/huanghe/npc/bangzhu_duty.h` 第 164 行：`obj = filter_array(children(BIAOTOU), (: clonep :)); if( sizeof(obj) < 10 )`。

**引擎限制建议**：
- 任务生成的对象必须注册到任务作用域，任务结束/放弃/超时时自动清理；
- 提供全局配额管理（同类型动态 NPC 上限），不让每个创作者手写 `children()` 过滤。

### 4.4 房间与 exits 的硬编码耦合

很多任务逻辑依赖 `explode(base_name(room), "/")[1]` 判断区域（如 `ftb_zhu.c` 用 `region_names[explode(room_msg, "/")[1]]`），一旦目录结构调整就会失效。这对 UGC 题材包的版本演进是隐患。

> 证据来源：
> - `/d/city/npc/ftb_zhu.c` 第 297–300 行：从房间路径解析 region。

**引擎限制建议**：
- 区域/标签应通过房间元数据而非文件路径推断；
- 任务目标配置使用逻辑 ID（如 `region:yangzhou`）而非物理路径。

### 4.5 全服广播与权限滥用

`center.c` 里的系统开关会触发 `CHANNEL_D->do_channel(..., "sys", ...)` 和 `rumor` 广播。如果普通创作者任务也能随意调用频道，将造成信息噪音。

> 证据来源：
> - `/d/wizard/center.c` 第 651–653 行、678–680 行：开关任务系统时全服广播。

**引擎限制建议**：
- 频道/全服广播作为受权限保护的能力，不应暴露给普通创作者；
- 题材包可声明 "系统事件"，由 engine 按模板统一播报。

---

## 5. UGC 任务质量的治理思路

### 5.1 审核与分级

| 级别 | 要求 | 示例 |
|------|------|------|
| **L0 官方认证** | 引擎团队或官方题材包作者出品，通过完整测试与平衡审计。 | MVP 官方武侠包的门派任务。 |
| **L1 社区推荐** | 通过玩家投票 + 自动化测试（如奖励速率不超标、无死任务）。 | 热门创作者副本。 |
| **L2 普通上架** | 基础语法与沙箱检查通过，可玩但无官方背书。 | 个人创作者的新手村任务。 |
| **L3 草稿/仅本地** | 仅作者自己世界可见，用于迭代。 | 开发中的实验任务。 |

**具体审核项**：
- 奖励速率是否在题材包上限内（参考 `job_server` 的 exp_limit/pot_limit）。
- 动态对象是否有注册与清理。
- 是否所有玩家状态读写都通过 engine 奖励表。
- 任务是否有超时/放弃/失败路径，避免死锁。

### 5.2 自动化护栏

借鉴 `job_server.c` 的奖励直方图与统计，engine 可以：

- **运行时采样**：记录每个任务的完成时间、奖励分布、失败率，超过阈值自动告警或降速。
- **沙箱执行**：创作者脚本在受限环境中运行，禁止直接操作玩家核心属性、禁止 `destruct` 非任务对象、禁止写日志文件之外的文件系统。
- **A/B 测试窗口**：新任务先在 5% 玩家中灰度，观察数据后再全量。

> 证据来源：
> - `/clone/obj/job_server.c` 第 600–620 行：per-user 统计；第 622–649 行：per-job 直方图。

### 5.3 社区反馈与快速下线

- **玩家举报**：任务存在卡死、奖励过高、叙事不适时，玩家可一键举报。
- **运营一键下线**：类似 `center.c` 的 `close_system` 或 `job_clear`，但权限应下沉到题材包管理员。
- **版本回滚**：题材包任务应以独立版本发布，出现问题可回滚到上一版本，而不是像 LPC 那样直接改线上 `.c` 文件。

### 5.4 经济安全与反刷

当前 LPC 任务存在多处可被刷取的设计：

- `bangzhu.c` 的 `ask_job()` 用 `time() < asktime + 180` 做冷却，但不同 NPC/任务之间没有共享冷却。
- `ftb_zhu.c` 的 `adjust_rate()` 会在 20 分钟无人做任务时自动提高奖励，吸引玩家回来刷。

> 证据来源：
> - `/d/huanghe/npc/bangzhu_duty.h` 第 115–120 行：180 秒 asktime 冷却。
> - `/d/city/npc/ftb_zhu.c` 第 158–189 行：`adjust_rate()` 的自动奖励上涨与 cap。

**治理建议**：
- 每日/每周任务次数上限由 engine 统一控制；
- 同一任务链的奖励随完成次数递减；
- 高价值奖励物品绑定 "首次完成" 或 "账号级别"。

---

## 6. 结论：对新引擎的启示

1. **任务系统必须题材无关**：核心生命周期、触发器、目标放置、奖励结算、运营统计应作为 engine 层能力；武侠/仙侠/科幻/校园只提供内容配置与叙事包装。
2. **创作者界面应声明式为主、脚本为辅**：NPC 对话、房间触发、奖励表应尽量通过 YAML/JSON 类配置完成；只有特殊机制才需要受限脚本。
3. **安全护栏是 UGC 的前提**：直接修改玩家属性、无上限奖励、动态对象泄漏、全服广播都是高危能力，必须由 engine 强制限制。
4. **运营观测要内建**：从 `job_server.c` 与 `center.c` 可以看出，任务上线后需要奖励直方图、单玩家追踪、全局开关、异常清理等工具，这些应成为 engine 默认功能，而不是每个题材包重复实现。
