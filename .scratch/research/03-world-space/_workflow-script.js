export const meta = {
  name: 'world-space-research',
  description: '多 Agent 并行调研「世界空间层」= 地图 + Nature + 交通子系统（LPC 考古 + 批判性对照现有 engine）',
  phases: [
    { title: 'Phase 1: 并行初稿' },
    { title: 'Phase 2: 红队对抗' },
    { title: 'Phase 3: 评审委员会汇总' },
  ],
};

const RESEARCH_DIR = '/home/gukt/github/xkx2001-utf8/.scratch/research/03-world-space';
const BRIEF_PATH = `${RESEARCH_DIR}/00-brief/brief.md`;
const REPO_ROOT = '/home/gukt/github/xkx2001-utf8';

const LPC_SOURCE_MAP = `LPC 一手源码关键指针（唯一真相源）：
- 地图：d/（35 区域、6414 房间，d/REGIONS.h 声明区域映射）、inherit/room/room.c（281 行基础房间：create_door/check_door/look_door/query_doors/valid_leave/reset/make_inventory/setup）、房间定义模式见 d/village/alley1.c（set exits/outdoors/objects/cost + setup + replace_program(ROOM)）、feature/move.c（154 行：move(dest,silently) + 负重/重量/装备卸下）
- Nature：adm/daemons/natured.c（193 行：day_phase 循环 call_out / weather_msg 5 档天气 / event_fun 回调 event_dawn/sunrise/noon / outdoor_room_description / message("outdoor:vision", msg, users()) 全户外广播）、adm/etc/nature/day_phase（8 时段：dawn/sunrise/morning/noon/afternoon/evening/night，每段 length/time_msg/desc_msg/event_fun）
- 交通：clone/horse/（22 马匹 + horse.h：condition_check() 体力衰减、jingli<=10 昏厥坠骑、rider/rided、set_leader）、inherit/room/ferry.c（157 行渡口：do_yell/check_trigger/on_board/arrive/close_passage call_out 周期）、inherit/room/ship.c（591 行玩家船：do_start/navigate/do_go/do_stop/do_lookout/do_locate/shipweather/niceweather/do_ready/do_drop，含导航/天气/瞭望/所有权）、clone/ship/seaboat1-3.c、d/*/road*.c 与 *road*.c（遍布各区官道，跨区域连接）`;

const ENGINE_MODULES = `新引擎已建模块（批判对照对象，仅 engine-comparison 角色与对照任务细读，其余角色只在需要时参考）：
- engine/src/openmud/nature.py(554 行) - 昼夜/天气
- engine/src/openmud/world.py(280 行) - 世界/房间注册表
- engine/src/openmud/room_hooks.py(732 行) - 房间钩子
- engine/src/openmud/room_details.py(112 行) - 房间景物细节
- engine/src/openmud/ferry.py(147 行) - FerryCrossing/FerryState/attach_ferries/_on_ferry_tick/_apply_all_exits/_apply_crossing_exits
- engine/src/openmud/directions.py(114 行) - builtin_aliases/resolve_english_bare/resolve_chinese_builtin/merge_exit_match_names/exit_display_label
- engine/src/openmud/transfer.py(363 行) - TransferResult/TransferContext/transfer()/重量/容量
- engine/src/openmud/scene_loader.py(1619 行) - 场景/房间加载
- engine/src/openmud/scenes.py(44 行)`;

const COMMON_TAIL = (outputPath) => `
证据要求：每条结论必须标注来源（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名）。禁止凭空推断。
输出：使用 Write 工具写入文件 ${outputPath}（绝对路径）。
最终回复：只需确认文件已写入，并给出 3-5 句话摘要。不要在回复中重复文件全文。`;

// ============ Phase 1: 并行初稿（11 席）============
phase('Phase 1: 并行初稿');

const p1Agents = [
  {
    label: 'LPC源码考古员',
    prompt: `你是「世界空间层」调研团队的 LPC 源码考古员。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：对地图 / Nature / 交通三个子系统相关的 LPC 源码做完整盘点。
必须覆盖：
1. 总体分布（d/ 区域与房间数、natured.c 结构、horse/ship/ferry 文件清单、官道分布）。
2. 关键文件清单表（文件路径 + 行数 + 职责 + 关键函数/对象）。
3. 调用链与数据结构：房间 exits mapping 如何驱动移动、move() 调用链、natured 的 day_phase 循环与广播通道、ferry/ship 的 call_out 周期、horse 的 rider/rided 与 condition_check。
4. 关键回调与状态变量（current_day_phase / weather_msg / doors / rider / jingli / ferry 状态等）。
5. 待深入文件清单（值得后续细读的代表性文件）。
${COMMON_TAIL(`${RESEARCH_DIR}/01-raw-findings/source-inventory.md`)}`,
  },
  {
    label: '玩法切片策划',
    prompt: `你是「世界空间层」调研团队的玩法切片策划。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

任务：从 LPC 源码中挑选 4-6 类代表性「世界空间层」玩法，做成「玩家视角 + 数据流」切片。建议覆盖：
- 城内导航（如扬州 city 的房间拓扑与门）
- 跨区官道骑乘（华山村 -> 少林 沿途 road + horse 体力衰减）
- 渡口过江（ferry.c 的 do_yell -> check_trigger -> on_board -> arrive 周期）
- 昼夜时段对户外的影响（natured 广播 + outdoors 房间 + event_fun 如昼夜商店）
- 天气影响（weather_msg 5 档）
- 玩家船航海（ship.c 的 navigate/do_go/shipweather/do_lookout）
每个切片：玩家操作步骤 + 背后数据流（涉及哪些文件/函数/状态）+ 体验要点。

同时产出玩家视角 User Stories（玩家在世界空间层会做什么、遭遇什么）。
${COMMON_TAIL(`${RESEARCH_DIR}/01-raw-findings/gameplay-slices.md`)}
再额外用 Write 写入玩家故事：${RESEARCH_DIR}/02-user-stories/player-stories.md（同一 agent 写两个文件）。`,
  },
  {
    label: '空间/移动机制设计师',
    prompt: `你是「世界空间层」调研团队的空间/移动机制设计师。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

任务：从 LPC 实现中抽象「世界空间层」通用机制（不绑定具体区域内容）。至少覆盖：
- 拓扑与出口：exits mapping（方向->目标房间）、方向词体系、跨区连接（官道）。
- 门：create_door/check_door/look_door 的状态机（开关/锁/方向对侧）。
- 导航：valid_leave、移动消耗 cost、负重限制（move.c）。
- 移动机制：move(dest, silently) 调用链、装备卸下、负重检查。
- 坐骑：rider/rided 关系、set_leader 跟随、jingli 体力衰减与昏厥坠骑、condition_check 周期。
- 渡船周期：ferry 的 yell->trigger->board->arrive->close 状态机与 call_out 驱动。
- 船只导航：ship.c 的 start/navigate/go/stop/lookout/locate/weather 状态机与海图坐标。
- 昼夜时段：day_phase 8 段循环、event_fun 回调、时段切换广播。
- 天气：weather_msg 5 档、与船 shipweather 的联动。
- 户外广播：outdoors 标志 + outdoor:vision 通道 + users() 全员推送。
对每个机制给出：LPC 出处 + 状态/数据结构 + 触发条件 + 与周边系统交互。

同时产出系统/NPC 自动触发视角 User Stories（时段切换、渡船周期、马匹体力、NPC 跟随等自动行为）。
${COMMON_TAIL(`${RESEARCH_DIR}/01-raw-findings/mechanisms.md`)}
再额外用 Write 写入系统故事：${RESEARCH_DIR}/02-user-stories/system-stories.md。`,
  },
  {
    label: '引擎架构师A',
    prompt: `你是「世界空间层」调研团队的引擎架构师 A。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：把「世界空间层」通用机制映射到题材无关 engine 核心，输出抽象方案与可选方向（不输出最终接口契约，止步于设计输入）。覆盖：
- 房间/拓扑/出口/门 作为 engine 核心原语的最小集（哪些必须进 core，哪些可下沉题材包）。
- 移动与移动消耗、负重 的抽象方向。
- Nature（昼夜/天气/户外广播）作为 engine 横切层的抽象：时段循环、广播通道、户外判定如何与房间解耦。
- 交通三态（坐骑/渡船/船只）的统一抽象：周期性载具/状态机/exit 动态开关（ferry._apply_crossing_exits 已是 exit 切换思路）。
- 跨区连接（官道）与区域/世界边界。
- 至少给出 2-3 个可选方向并比较权衡（不要只给一个"正确答案"）。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/abstraction-options.md`)}`,
  },
  {
    label: '引擎架构师B',
    prompt: `你是「世界空间层」调研团队的引擎架构师 B。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：思考题材包（UGC）创作层应暴露的最小表面（创作者如何摆放房间、连区域、设门、设交通、配 Nature）。覆盖：
- 创作者需要声明什么：房间、exits、outdoors、门、cost、objects、区域归属。
- 交通创作面：如何挂渡口/船/坐骑（ferry 的 trigger 机制、ship 的所有权与航线、horse 的属性）。
- Nature 创作面：时段表可否自定义、天气消息、event_fun 钩子如何暴露给题材包。
- 哪些应锁在 engine core 不让创作者碰（广播通道、拓扑一致性校验）。
- 创作者门槛与护栏（防止断链/孤岛房间/exit 指向不存在目标）。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/ugc-surface.md`)}`,
  },
  {
    label: 'UGC游戏专家',
    prompt: `你是「世界空间层」调研团队的 UGC 游戏专家。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：从创作者视角审视「世界空间层」可扩展性。覆盖：
- 创作者摆房间、连区域、设门、设交通、配 Nature 的工作流与痛点（LPC 当下是 inherit ROOM + 手写 exits mapping，断链风险高）。
- 哪些机制适合暴露给题材包创作者，哪些应封装。
- 6414 房间/35 区域 的规模对创作工具的要求（编辑器/校验/预览）。
- 创作者经济视角：地图资产作为题材包核心资产的可交易性（参考 CLAUDE.md 商业化支撑点）。
- 现有 engine 的 scene_loader（1619 行）与 world.py 对创作者友好度的影响（仅评估，不深读实现）。

同时产出巫师/运营视角 User Stories（创作者如何搭建与维护世界空间）。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/creator-perspective.md`)}
再额外用 Write 写入运营故事：${RESEARCH_DIR}/02-user-stories/operator-stories.md。`,
  },
  {
    label: '现代世界/关卡设计师',
    prompt: `你是「世界空间层」调研团队的现代世界/关卡设计师。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

任务：对标当前主流游戏（开放世界导航、fast travel、地图现代化、移动节奏、MMO 区域设计），评估 LPC「世界空间层」机制的当代可玩性与过时风险。覆盖：
- 导航与寻路：LPC 纯文本方向移动 vs 现代地图/小地图/auto-path；迷路问题。
- 移动节奏：逐房间移动 + cost + 负重 vs fast travel/传送/载具；移动疲劳。
- 昼夜/天气：LPC 时段广播 vs 现代动态环境；天气玩法深度。
- 交通载具：坐骑/渡船/玩家船 vs 现代载具玩法；玩家船（ship.c 591 行）的复杂度是否值得。
- 哪些 LPC 机制值得保留（文本沉浸感、空间感），哪些过时应现代化。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/modern-design-review.md`)}`,
  },
  {
    label: '玩家心理与留存专家',
    prompt: `你是「世界空间层」调研团队的玩家心理与留存专家。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

任务：从动机心理学、留存曲线、心流节奏、社交压力等角度点评「世界空间层」玩家体验。覆盖：
- 探索动机：6414 房间大世界的探索欲驱动与疲劳阈值。
- 迷路挫败：纯方向移动 + 无地图的迷失感与流失风险。
- 移动疲劳：逐房间移动 + cost + 负重 + 坐骑体力衰减的累积负担。
- 心流节奏：昼夜/天气/时段广播对沉浸与节奏的作用。
- 社交压力：渡船等待/船只所有权/坐骑竞争等社交触点。
- 必须保护玩家的体验底线（建议机制）。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/player-psychology.md`)}`,
  },
  {
    label: '商业化与增长专家',
    prompt: `你是「世界空间层」调研团队的商业化与增长专家。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

任务：从付费设计、UGC 创作者经济、题材包消费、用户增长角度评估「世界空间层」商业潜力。参考 CLAUDE.md 商业化支撑点（货币/账本、题材包资产元数据、消费埋点、世界实例隔离）。覆盖：
- 地图资产作为题材包核心资产：房间/区域/交通 的归属与版本溯源。
- 交通作为消费点：坐骑/船/渡口的付费潜力（注意 pay-to-win 红线）。
- 创作者经济：题材包地图创作与分成的支撑点。
- 大世界规模对留存/增长的影响（探索深度 vs 新手流失）。
- 哪些商业支撑点应在 engine 留位置（MVP 不实现但预留）。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/commercialization.md`)}`,
  },
  {
    label: '性能与可扩展性专家',
    prompt: `你是「世界空间层」调研团队的性能与可扩展性专家。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：评估「世界空间层」的性能与可扩展性维度。覆盖（单机 1000 在线 + 100 并发约束，见 CLAUDE.md）：
- 大世界拓扑：6414 房间/35 区域 的内存与查询开销；exit 解析；find_object/call_other 在 move() 中的开销。
- Nature 全员广播：message("outdoor:vision", msg, users()) 每时段切换向所有户外玩家推送的开销（1000 在线时）。
- 交通并发：渡船 call_out 周期、多玩家同时 yell/登船、玩家船 navigate 计算。
- call_out 周期与 tick：natured/ferry/ship 的定时器密度。
- 持久化：房间/状态/船只所有权的存档开销。
- 现有 engine（nature.py/world.py/ferry.py/scene_loader.py）的性能隐患（仅评估方向，不深读）。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/performance-review.md`)}`,
  },
  {
    label: 'engine批判对照员',
    prompt: `你是「世界空间层」调研团队的 engine 批判对照员（06-engine-critique 层）。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：逐项对照「现有 engine 实现」与「LPC 原始设计」，标注偏差与遗漏。engine 模块仅作批判对照对象，不作反向脑补来源；LPC 才是真相源。
对以下每个 engine 模块，产出对照条目（LPC 设计 -> engine 现状 -> 偏差/遗漏 -> 风险/影响）：
1. nature.py vs natured.c：昼夜时段循环、天气、户外广播通道是否对齐？event_fun 钩子有无？
2. world.py vs d/+room.c：房间/拓扑/区域注册、exits、outdoors 标志是否覆盖？
3. room_hooks.py vs room.c 回调：valid_leave/reset/门 等 hook 覆盖度？
4. room_details.py vs 房间景物：item_desc/look 机制？
5. ferry.py vs ferry.c：渡船周期状态机、exit 动态开关（_apply_crossing_exits）对齐度？
6. directions.py vs LPC 方向词：方向别名/中英文解析覆盖度？
7. transfer.py vs move.c：移动/负重/容量 对齐度？
8. scene_loader.py vs LPC 房间加载：inherit ROOM/setup/replace_program 模式如何映射？
9. scenes.py：场景抽象覆盖度？
额外：标注 engine 相对 LPC 的「正面偏差」（engine 做得更好的地方）与「负面遗漏」（engine 缺失的能力）。
${COMMON_TAIL(`${RESEARCH_DIR}/06-engine-critique/engine-comparison.md`)}`,
  },
];

await parallel(p1Agents.map(a => () => agent(a.prompt, {
  label: a.label,
  phase: 'Phase 1: 并行初稿',
  effort: 'high',
})));

log('Phase 1 初稿完成（11 席）');

// ============ Phase 2: 红队对抗（5 路）============
phase('Phase 2: 红队对抗');

const P1_OUTPUTS = `Phase 1 已产出文件（请先 Read 这些文件再质疑）：
- ${RESEARCH_DIR}/01-raw-findings/source-inventory.md
- ${RESEARCH_DIR}/01-raw-findings/gameplay-slices.md
- ${RESEARCH_DIR}/01-raw-findings/mechanisms.md
- ${RESEARCH_DIR}/02-user-stories/player-stories.md
- ${RESEARCH_DIR}/02-user-stories/system-stories.md
- ${RESEARCH_DIR}/02-user-stories/operator-stories.md
- ${RESEARCH_DIR}/03-engine-insights/abstraction-options.md
- ${RESEARCH_DIR}/03-engine-insights/ugc-surface.md
- ${RESEARCH_DIR}/03-engine-insights/modern-design-review.md
- ${RESEARCH_DIR}/03-engine-insights/player-psychology.md
- ${RESEARCH_DIR}/03-engine-insights/commercialization.md
- ${RESEARCH_DIR}/03-engine-insights/performance-review.md
- ${RESEARCH_DIR}/03-engine-insights/creator-perspective.md
- ${RESEARCH_DIR}/06-engine-critique/engine-comparison.md`;

const p2Agents = [
  {
    label: '红队:横向对比验证',
    prompt: `你是红队的横向对比验证员。先阅读调研总则：${BRIEF_PATH}

${P1_OUTPUTS}

任务：交叉检查各区域/各交通实现与各抽象方案，找出共用模式与特例，验证核心抽象的覆盖度。重点：
- 抽象方案（abstraction-options / mechanisms）是否覆盖了所有代表性实例（city 扬州/village 华山村/shaolin 少林/ferry/ship/horse/road）？
- 是否存在「伪通用」（抽象看似通用但实际只拟合了某一两个区域）？
- 跨区域官道连接模式是否一致？渡口/船只/坐骑三态交通能否统一抽象？
- engine-critique 的对照条目有无遗漏或误判？
每条质疑必须具体，引用被质疑的文件与段落（文件路径 + 小节/行）。给出「确认/推翻/待澄清」裁决建议。
${COMMON_TAIL(`${RESEARCH_DIR}/04-redteam-review/cross-check-report.md`)}`,
  },
  {
    label: '红队:现代玩法挑战',
    prompt: `你是红队的现代玩法挑战者。先阅读调研总则：${BRIEF_PATH}

${P1_OUTPUTS}

任务：对 LPC「世界空间层」机制与现代设计评审（modern-design-review）的结论提出尖锐质疑。重点：
- modern-design-review 是否过度现代化、丢弃了文本 MUD 的核心沉浸价值？
- fast travel/地图现代化 的建议是否会破坏空间感与探索乐趣？
- 保留 LPC 某些机制的论证是否充分？玩家船（591 行）这种重度机制真的值得现代化吗？
- 玩家心理与留存结论是否与现代玩法建议矛盾？
每条质疑引用被质疑文件与段落。给出裁决建议。
${COMMON_TAIL(`${RESEARCH_DIR}/04-redteam-review/modern-challenges.md`)}`,
  },
  {
    label: '红队:体验风险挑战',
    prompt: `你是红队的玩家体验风险挑战者。先阅读调研总则：${BRIEF_PATH}

${P1_OUTPUTS}

任务：识别「世界空间层」玩家流失点与必须的保护机制。重点：
- 6414 房间大世界 + 纯方向移动 + 无地图 的新手流失风险有多严重？player-psychology 的评估是否乐观？
- 移动疲劳/坐骑体力衰减/渡船等待 的累积挫败是否被低估？
- 昼夜/天气 是否会干扰而非增强体验（如夜间看不清路导致迷路）？
- 哪些保护机制是「必须」的（不是可选）？给出优先级。
每条质疑引用被质疑文件与段落。
${COMMON_TAIL(`${RESEARCH_DIR}/04-redteam-review/player-experience-risks.md`)}`,
  },
  {
    label: '红队:商业化风险挑战',
    prompt: `你是红队的商业化风险挑战者。先阅读调研总则：${BRIEF_PATH}

${P1_OUTPUTS}

任务：识别「世界空间层」的经济风险与 pay-to-win 陷阱。重点：
- 交通作为消费点（坐骑/船/渡口付费）是否会越线成 pay-to-win？商业化的红线在哪？
- 地图资产作为题材包资产 的归属/版本/分成 模型有无漏洞？
- 大世界规模与商业化是否冲突（重内容投入 vs 横向扩展题材包数量）？
- 现有 engine 留的商业支撑点位置是否足够？有无遗漏？
每条质疑引用被质疑文件与段落。
${COMMON_TAIL(`${RESEARCH_DIR}/04-redteam-review/commercial-risks.md`)}`,
  },
  {
    label: '红队:性能风险挑战',
    prompt: `你是红队的性能风险挑战者。先阅读调研总则：${BRIEF_PATH}

${P1_OUTPUTS}

任务：识别「世界空间层」的性能瓶颈与可扩展性风险。重点：
- Nature 全员广播（每时段切换推送所有户外玩家）在 1000 在线时的开销是否被低估？
- 6414 房间 + move() 的 find_object/call_over 开销；scene_loader（1619 行）加载开销。
- 交通并发（多渡船/多玩家船/navigate 计算）的峰值风险。
- call_out/natured/ferry/ship 定时器密度。
- 现有 engine 模块的潜在性能反模式（对照 engine-comparison）。
每条质疑引用被质疑文件与段落。给出量化量级估计。
${COMMON_TAIL(`${RESEARCH_DIR}/04-redteam-review/performance-risks.md`)}`,
  },
];

await parallel(p2Agents.map(a => () => agent(a.prompt, {
  label: a.label,
  phase: 'Phase 2: 红队对抗',
  effort: 'high',
})));

log('Phase 2 红队对抗完成（5 路）');

// ============ Phase 3: 评审委员会汇总（1 个 xhigh agent）============
phase('Phase 3: 评审委员会汇总');

const ALL_OUTPUTS = `${P1_OUTPUTS}
- ${RESEARCH_DIR}/04-redteam-review/cross-check-report.md
- ${RESEARCH_DIR}/04-redteam-review/modern-challenges.md
- ${RESEARCH_DIR}/04-redteam-review/player-experience-risks.md
- ${RESEARCH_DIR}/04-redteam-review/commercial-risks.md
- ${RESEARCH_DIR}/04-redteam-review/performance-risks.md`;

const synthesisPrompt = `你是「世界空间层」调研的评审委员会（5 人：玩法切片策划 + 引擎架构师 A + UGC 游戏专家 + 现代世界/关卡设计师 + 商业化与增长专家）。先阅读调研总则：${BRIEF_PATH}

${ALL_OUTPUTS}

任务：审阅 Phase 1 初稿与 Phase 2 红队报告，统一文风、消除矛盾、对分歧做裁决，生成最终报告。
要求：
1. 先 Read 上述所有文件（若某文件缺失/为空，在报告中标注「补全失败」并跳过，不要伪造内容）。
2. 使用 Write 写入：${RESEARCH_DIR}/05-synthesis/final-report.md
3. 报告结构：执行摘要 -> 范围与方法 -> 现状总览（地图/Nature/交通 三层脉络）-> 关键发现 -> 三层 User Stories 汇总 -> 设计建议（分 engine core / UGC 创作面 / 现代化方向）-> engine 对照结论（引用 06-engine-critique 要点）-> 红队质疑裁决表（逐条 accept/reject/待澄清 + 理由）-> 未决问题 -> 附录（文件清单）。
4. 统一中文文风；对 Phase 1 各文件之间的矛盾点显式裁决；对红队每条质疑给出 accept/reject/待澄清 裁决。
5. 不输出可直接落地的 engine 代码或接口契约（止步设计输入）。
6. 最终回复只需确认 final-report.md 已写入 + 5-8 句话执行摘要。`;

await agent(synthesisPrompt, {
  label: '评审委员会汇总',
  phase: 'Phase 3: 评审委员会汇总',
  effort: 'xhigh',
});

log('Phase 3 评审委员会汇总完成');

return { status: 'completed', researchDir: RESEARCH_DIR };
