# Done 归档 - 阶段 0（LPC 规格提取 + 方法论）

> 从 PROGRESS.md 归档于 2026-07-14。阶段 0 已完成条目的历史记录，按需检索。
> 当前活状态见 [PROGRESS.md](../../PROGRESS.md)。

## Done

- [x] **阶段 0 任务 2：FluffOS 编译可行性评估完成**（[ADR-0009](docs/adr/ADR-0009-original-driver-runnable.md)）：
  - 发现仓库 `driver` 是 FluffOS 3.0.20170907 x86_64 macOS 二进制（非 config.xkx 注释的 MudOS 0.9.20）
  - 通过 Rosetta 2 + libevent 符号链接（2.1.6 -> 2.1.7）在 arm64 macOS 成功运行
  - 全部 daemon 加载成功，端口 8888 监听，nc 连接可见登录界面
  - 结论：现有二进制可运行，无需编译；golden trace 定位为辅助验证手段（非主线）
  - 修正 04 §六不做清单"旧系统不可运行"假设；为 dissent 4 基线测试提供运行时验证路径

- [x] **阶段 0 任务 1 前置：规格提取方法论与实施计划完成**（[ADR-0010](docs/adr/ADR-0010-lpc-spec-extraction-methodology.md) / [08-阶段-0-实施计划.md](docs/xkx-arch/08-阶段-0-实施计划.md)）：
  - 分析侠客行架构拆解说明书（14 份文档 / 36 子系统），发现 go/move/combat 三条路径不足以覆盖核心可玩循环
  - 定义 9 层范围（A-I）：驱动桥梁 / 对象基础 / 命令系统 / 世界构建 / 战斗 / 死亡轮回 / NPC AI / 核心守护进程 / 角色登录，约 4500-5000 行 LPC
  - 方法论：函数级契约（签名+前置/后置条件+不变量+副作用+随机性）+ pydantic v2 模型 + 3 个 Wave 并行提取
  - 避免穷尽细节：不碰 kungfu/(798) + d/(6414)，condition 只提取框架，阴间流程后置，不做 LPC 解析器自动化
  - 为新 session 准备好可直接执行的 9 层并行提取计划

- [x] **阶段 0 任务 1：LPC 规格提取管线 9 层全部完成**（[ADR-0010](docs/adr/ADR-0010-lpc-spec-extraction-methodology.md) / [08-阶段-0-实施计划.md](docs/xkx-arch/08-阶段-0-实施计划.md)）：
  - 基础类型 [base.py](engine/src/xkx/spec/base.py)：FunctionSpec 六要素（签名/前置/后置/不变量/副作用/随机性）+ LayerSpec 集合
  - 3 个 Wave 串行启动、Wave 内 agent 并行提取（Wave 1: A+B+C+D / Wave 2: E+F+G / Wave 3: H+I），9 个 spec 文件 + 9 个 test 文件
  - **总计 160 FunctionSpec / 631 SideEffect / 52 RandomSpec / 151 跨层引用**，覆盖约 7000 行 LPC
  - 层 A 驱动桥梁（25 函数）：master.c 驱动回调 + simul_efun 核心路径（connect/epilog/valid_* / destruct/getoid/living）
  - 层 B 对象基础（24 函数）：F_DBASE 路径访问语义 + temp 变体差异 + F_NAME short() 状态修饰 + F_MOVE 负重级联
  - 层 C 命令系统（10 函数）：command_hook 四分支（direction_shortcut->normal->emote->channel）+ 18 条方向别名 + find_command 逆序搜索
  - 层 D 世界构建（9 函数）：valid_leave 基类契约 + 8 种 override 模式分类（516 文件实证扫描）+ go main() 14 个交织副作用
  - 层 E 战斗系统（26 函数，核心）：**do_attack 七步 49 个副作用严格交织**（state_mutation 与 message_output 不可分离）+ **31 处 random 概率模型**（闪避 dp/(ap+dp)、招架 pp/(ap+pp)、伤害随机化等）+ 三层资源不变量（0<=qi<=eff_qi<=max_qi）+ skill_power 公式
  - 层 F 死亡轮回（10 函数）：die vs unconcious 触发区别（eff_qi<0 直接死 vs qi<0 先昏迷，昏迷中再受创升级死亡）+ death_penalty 完全确定性 + make_corpse 物品转移
  - 层 G NPC AI（12 函数）：heart_beat 七步管线 + auto_fight 三触发优先级（hatred>vendetta>aggressive，call_out 延迟给受害者溜走机会）+ chat 随机对话
  - 层 H 核心守护进程（26 函数）：LOGIN_D 13 阶段状态机（logon->get_id->get_passwd->make_body->enter_world）+ SECURITY_D valid_cmd fail-closed（每条命令都过）+ NATURE_D 时间系统（真实 1 秒=游戏 1 分钟）+ 10 级 wiz_level
  - 层 I 角色与登录（18 函数）：visible() 三级判定（wiz_level > invisibility > 鬼魂）+ user.c save 三步交织（autoload->::save->clean_up）+ PronounContext viewer 不变量 + JSON 存档崩溃安全要求
  - 任务 1 验收标准（08 §四）全部满足：9 层规格产出 / 属性测试骨架 / go+move+combat 覆盖 / 29 处 random 提取 / 三层资源不变量 / do_attack 七步交织顺序 / ruff+pytest 全过
  - **599 tests 全绿（+481），ruff 全过**
  - agent teams 并行提取高效：Wave 内 4/3/2 agent 并行，9 层总提取时间约 25 分钟

- [x] **阶段 0 任务 3 路径 B：规格符合性检查器完成**（[ADR-0011](docs/adr/ADR-0011-spec-conformance-checker.md)）：
  - impl_map（[impl_map.py](engine/src/xkx/spec/impl_map.py)）：do_attack 14 项检查条目三状态标注（12 implemented + 2 simplified），每条关联 ADR-0002 简化台账
  - ConformanceChecker（[conformance.py](engine/src/xkx/combat/conformance.py)）：8 项单次 result 检查（result_code 合法 / damage 非负 / 非命中 damage=0 / effect target 合法 / 命中有 DAMAGE / 闪避招架无 DAMAGE / 三层资源不变量 / 交织顺序）
  - CombatRoundResult 升级 ledger 字段（[result.py](engine/src/xkx/combat/result.py)）：记录 msg/eff 统一调用顺序，验证交织不变量；向后兼容（messages/effects 列表不变，S1 7 tests 不回归）
  - 统计性属性测试 6 项：确定性 / 三分支可达 / 闪避概率 ≈ dp/(ap+dp) / 招架条件概率 ≈ pp/(ap+pp) / ap-dp-pp>=1 / TYPE_QUICK damage<=TYPE_REGULAR
  - 核心价值：resolve_attack S1 简化版与 do_attack 规格的符合性可**自动区分"已知简化"与"真正违反"**（impl_map 三状态过滤），规格演进时检查项自动跟进
  - **612 tests 全绿（+13），ruff 全过**

- [x] **阶段 0 任务 3 路径 A：9 层规格一致性属性测试完成**（[ADR-0011](docs/adr/ADR-0011-spec-conformance-checker.md)）：
  - 9 层 test_spec_*.py 从固定断言升级为 hypothesis 属性测试（4 类属性）：随机函数索引（签名完整 / order 递增连续 / kind 非空 / pre+post 条件）/ 副作用子集（随机子集 order 仍递增）/ random_specs 完整性（probability_model + semantic + lpc_call 非空）/ invariants-side_effects 对应（状态不变量 -> STATE_MUTATION）
  - 跨层一致性测试（[test_spec_cross_layer.py](engine/tests/test_spec_cross_layer.py)）：9 层完整性（layer_id A-I 唯一 / 层名不重 / 单层 lpc_files 不重）+ cross_layer_refs 跨层可解析（目标层 ID 在 A-I 范围 + 非全自引用）+ hypothesis 全局函数索引（跨层任意函数签名完整 / 有副作用或 notes）
  - agent teams 两批并行：批 1（B+C+D+E）+ 批 2（F+G+H+I），层 A 手动示范建立共享模式
  - 智能适配层特点：层 B/H 无前置条件函数仅断言 postcondition / 层 G 用 re 词边界匹配 max_ 避免 MAX_OPPONENT 误命中 / 层 F/I 否定语境排除（"不修改状态"不要求 STATE_MUTATION）/ 层 E 保留 do_attack 七步交织 + 三层资源不变量 + skill_power 公式等核心契约
  - 删除与 hypothesis 重复的固定断言（signature 完整 / order 连续 / random_spec 字段非空），保留层特有契约（do_attack 七步交织 / LOGIN_D 状态机 / visible 三级 / heart_beat 七步 / valid_leave 8 模式等）
  - **676 tests 全绿（+64），ruff 全过**

- [x] **阶段 0 任务 7：灵魂系统盘点完成**（[09-灵魂系统盘点.md](docs/xkx-arch/09-灵魂系统盘点.md)）：
  - 5 个 agent 并行盘点阴间/武林大会/vote/法院/intermud 五个子系统，每个按 7 项模板产出（文件清单/职责/数据流/核心循环关系/themed 治理属性/关键函数/后置建议）
  - **阴间系统**（d/death/ 15 文件）：死亡->阴间->还阳完整路径，黑白无常 5 段对话剧情 + inn1 隐藏还阳路径，gate.c 物品销毁是关键副作用，平台级 fail-closed，阶段 1 实现
  - **武林大会**（d/bwdh/ 297 文件）：个人赛（8 年龄组擂台赛）+ 团体赛（试剑山庄夺旗积分赛），exec 代理机制是 LPC 特有 hack，control.c 53KB 需拆分，sjsz/sjsz2/sjsz3 三份副本需参数化，平台级 fail-closed，阶段 2 实现
  - **vote 投票**（cmds/std/vote/ + condition）：玩家自治频道管理（chblk/unchblk），投票发起->计票->结果执行->超时清理，动议类型封闭枚举，平台级 fail-closed，阶段 2 实现
  - **法院系统**（combatd + condition + NPC）：PK 通缉 + 官府执法 + 监狱服刑 + 玩家投票治理四线交织，killer/xakiller/dlkiller/bjkiller 四种区域通缉，courthouse 反机器人审判是独立子系统，平台级 fail-closed，阶段 1 实现
  - **intermud**（adm/daemons/network/ 24 UDP 服务）：跨 MUD 网络通信，**违反收缩约束**（不考虑分布式架构/网关），建议砍掉/无限期后置，仅跨服频道广播接口预留
  - themed 治理属性汇总：五系统全部平台级 fail-closed，验证 CLAUDE.md 不变量
  - 题材文化系统台账：补充天雷/婚姻/师徒/门派/称号/频道/经济/邮件/emote/finger 十个系统定位
  - 验收标准（04 §三）"无遗漏"满足

- [x] **阶段 0 任务 4 阶段 0 部分：性能 micro-benchmark 完成**（[ADR-0012](docs/adr/ADR-0012-performance-microbenchmark.md)）：
  - [benchmark.py](engine/tools/benchmark.py)：resolve_attack μs 基准（timeit + 三分支 hit/dodge/parry + GC on/off 双测）+ GC 基准（tracemalloc 单次峰值 + gc.get_stats gen0 回收）+ PYTHONHASHSEED 跨进程验证（subprocess 跑 0/1/random 各 3 次比较输出）
  - [test_benchmark.py](engine/tests/test_benchmark.py)：4 项回归门禁（中位数 < 200μs / 单次 < 100KB / 5k 次 gen0 < 1000 / 同 seed 100 次一致），宽松阈值防退化（ADR-0012 决策 6）
  - **μs 基准数据**：hit median 25.9μs / dodge 17.2μs / parry 17.3μs（< 50μs 阈值，p99 < 18μs < 200μs 阈值）；GC on/off 差异 ~0.1μs（resolve_attack 几乎不触发 GC）
  - **GC 基准数据**：单次峰值 5336 bytes（~5KB，CombatRoundResult + Effect + LedgerEntry）；20k 次调用 gen0 回收 0 次（验证 04 §六"CombatRoundResult/Effect 对象池化...GC 是非问题"，对象池决策后置阶段 1 tick profiler 实测后）
  - **PYTHONHASHSEED 验证**：跨进程（0/1/random）输出完全一致（resolve_attack 用 random.Random(seed) 不依赖 hash，combat 确定性基础成立）
  - **go/no-go 判定：GO**（阶段 0 μs 前置数据点充分；1000+100 负载 + 1s tick 预算实测后置阶段 1 框架，kill criteria 3 完整判定需阶段 1）
  - 阈值推导：1000 实体 * tick<100ms，combat 占 50% 预算 -> 1000*X < 50,000μs -> X < 50μs（保守上界，实际 1000 在线活跃战斗者远少于此）
  - 不引入 pytest-benchmark（标准库 timeit 足够，符合 04 §一核心立场 7 收敛原则）
  - **680 tests 全绿（+4），ruff 全过**

- [x] **阶段 0 任务 5：引擎工具链 PRD（最小三件）完成**（[ADR-0013](docs/adr/ADR-0013-engine-toolchain-prd.md)）：
  - 3 个 PRD 文档产出（[entity-inspector](docs/xkx-arch/10-引擎工具链PRD-entity-inspector.md) / [tick-profiler](docs/xkx-arch/10-引擎工具链PRD-tick-profiler.md) / [combat-replay-viewer](docs/xkx-arch/10-引擎工具链PRD-combat-replay-viewer.md)），统一**定位为阶段 1 开发期工具**（非生产运维工具），进程内模块
  - Entity Inspector：只读快照（< 0.1ms/查询）+ LPC F_DBASE 语义映射表（`query("skill/axe")`->`Skills.levels["axe"]`，`query_temp("marks/酥")`->`Marks.flags`）+ CLI `inspect` 命令 + 程序化 API
  - Tick Profiler：per-System compute 统计（mean/p99/max）+ `enabled=False` 零开销 contextmanager + ring buffer；与 ADR-0012 benchmark 分工（μs 微基准 vs tick 宏观，互补构成 kill criteria 3 完整 go/no-go）
  - Combat Replay Viewer：非侵入消费 CombatRoundResult ledger（不修改 combat 内核）+ 可离线回放 + 确定性 diff（同 seed 同 input->同输出）+ 与 ADR-0011 ConformanceChecker 联动（8 项检查）+ 战报归档格式衔接 M1 开源交付物
  - 关联 dissent 3/4/7（性能基线 / 规则冲突语义漂移 / 派生变更审计）
  - 阶段 0 -> 1 决策检查点"引擎工具链 PRD 评审通过"满足
  - agent teams 并行：3 agent 各写一件工具 PRD

- [x] **阶段 0 任务 8：32 守护进程职责重新设计完成**（[ADR-0014](docs/adr/ADR-0014-daemon-responsibility-redesign.md)）：
  - 2 个盘点文档产出（[核心运行时组 15 个](docs/xkx-arch/11-守护进程职责重新设计-核心运行时组.md) / [社交辅助组 16 个](docs/xkx-arch/11-守护进程职责重新设计-社交辅助组.md)），31 个 .c 守护进程逐一标注归属
  - 四类归属：6 ECS System（logind / natured / combatd / channeld / moneyd + ConnectionSystem）/ 12 无状态服务 / 2 新能力（securityd->PermissionService+CapabilityToken / regid->AccountService）/ 12 砍掉后置
  - 关键决策：securityd fail-closed + exclude 优先 trusted / combatd 七步交织 combat 确定性 / rankd PronounContext 三元组 viewer / intermud 三件套砍掉（dns_master/ftpd/socket）/ channeld chblk 平台级 fail-closed / languaged+languanged 完全副本砍掉
  - 关联 dissent 2/5/8（ECS 取代 daemon / themed 治理 / UGC 红线）
  - agent teams 并行：2 agent 各盘点一组

- [x] **阶段 0 任务 9（30 文件表达力校准）完成**（[ADR-0015](docs/adr/ADR-0015-layer-calibration-methodology.md) + [ADR-0016](docs/adr/ADR-0016-layer1-predicate-expansion-batch2.md)）：
  - 30 文件 5 批 agent 并行转译，290 语义单元，30 YAML + 30 MD 标注表（[stats.md](engine/tools/layer_calibration/stats.md)）
  - 修正 KPI = 逃生舱层3 11/171 ≈ 6.4% < 15% ✓（区分预期层3 ~56 项 vs 逃生舱层3 ~11 项）
  - KPI 定义修正：回归 03/04 "逃生舱使用率"原意（非"所有层3 占比"），原始层3 35.7% 超标是定义失真非表达力不足
  - 谓词集 8 类缺口扩充决策（attr_eq/is_wizard/has_item 扩展/has_flag 扩展/derived_state/status_eq 系列/has_inquiry+attr_in/命令事件钩子），实现后置阶段 1
  - **阶段 0 -> 1 决策检查点全部满足**，不触发 kill criteria 4
  - agent teams 并行：5 agent 各转译 6 文件

