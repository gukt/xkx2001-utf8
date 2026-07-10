# 模式研究·事件溯源/CQRS 与事件总线（用于 XKX 游戏状态重构）

## 概述
XKX 已具事件溯源雏形：dbase=状态、tmp_dbase=瞬态读模型、save/restore_object=快照、log_file 的 PLAYER_DEATH/PKILL_DATA/MONEY 等即领域事件审计日志、heart_beat 2s tick=天然事件批边界。建议以 CQRS+ES 分层落地：经济域先行(双记账反作弊)，战斗用回合聚合事件+周期快照，社交低频高价值最契合。总线分层 Redis Stream(热)+NATS JetStream(扇出)+PostgreSQL 追加表(权威)。热更新靠重建投影，反作弊靠任意时刻回放重建。

## 模式
- **命令/事件分离（CQRS Write/Read Split）**：当前 cmds/*.c 命令文件直接调用 set() 突变 dbase，意图与状态变更混在一起。CQRS 将玩家输入(kill/buy/drop/go/learn)建模为 Command（表达意图、可校验、可拒绝），其执行结果产出不可变 Event（DamageDealt/MoneySpent/ItemMoved/CharacterDied）。命令走写侧，查询走读侧投影。映射：cmds=CommandHandler，set=ApplyEvent，query=ReadModel。
  - 适用性：命令层重构 cmds/*.c 与守护进程(COMBAT_D/MONEY_D)为 CommandHandler；事件层为新增。覆盖全部玩家可输入动作与系统 tick 决策。
- **事件存储（Append-Only Event Store）**：现状 log_file() 的 PLAYER_DEATH/PKILL_DATA/MONEY/QUESTS/POISON 等已是手工追加审计日志，但分散、无 schema、不可机读回放。应统一为带 event_id/aggregate_id/version/timestamp/causation_id 的结构化事件流，写入 PostgreSQL 追加表（权威真相）+ 分层总线。事件只追加不修改，状态由 fold(apply) 得出。
  - 适用性：经济、社交、角色成长域强适用；战斗高频 tick 不入存储。
- **快照+回放重建（Snapshot + Replay）**：现状 save_object 写整份 dbase 快照、覆盖式无历史；restore_object 只能回到最近一次存档。改为：周期性（沿用 heart_beat 2s tick 自然边界，如每 30s 或关键节点）写 Snapshot 到事件库；崩溃恢复=加载最近 Snapshot + 回放其后事件。LPC 的 default_ob(蓝图默认值) 对应聚合工厂/默认投影值。
  - 适用性：全部持久化域。战斗连续态(qi/jing)必用快照，离散决策(FightStarted/KillDeclared)用事件。
- **聚合根封装不变量（Aggregate Root）**：把不变量封装进聚合：Wallet（资金余额、双记账不变量）、Character（属性上下限、技能前置）、Team（成员唯一性、队长一致性）。命令经聚合校验后才产出事件，保证不变量。映射 dbase 的路径式属性(family/master_id)为聚合内嵌实体。事件携带 version 做乐观并发控制，替代 LPC 无版本的全量覆盖写。
  - 适用性：经济(Wallet)、角色(Character)、团队(Team)、门派(Family)、库存(Inventory) 各为聚合。CHANNEL_D 聊天不建模为聚合，作为事件流。
- **读模型投影（CQRS Read Side Projection）**：将 query()/query_entire_dbase() 的读路径重建为物化投影：背包视图、属性面板、排行榜、银行流水、战报。投影从事件异步构建，可多份、可按需重建。tmp_dbase（瞬态、不持久）正是天然的非持久读模型。热更新时只重建投影，不动写侧——这是 ES 对热更新最大的收益。
  - 适用性：排行榜、背包、银行流水、战斗日志、战报、反作弊看板均走读模型，可独立于写侧迭代。
- **分层事件总线（Tiered Event Bus）**：三类事件按延迟/持久性/扇出需求分层：① Redis Stream——战斗 tick、伤害、心跳类亚毫秒热事件，支持消费组与回放；② NATS JetStream——聊天频道(CHANNEL_D 已是 fanout)、房间事件、跨服/跨区域社交事件，单二进制运维轻、主题扇出强；③ PostgreSQL 追加表——经济/角色/社交聚合的权威事件源，强一致、可事务、可回放审计。Kafka 仅在 UGC 多租户多区域、需要跨地域日志时才引入。
  - 适用性：战斗 tick/伤害：Redis Stream(亚毫秒)；聊天/房间广播/跨服社交：NATS JetStream(扇出+持久)；权威审计：PostgreSQL。Kafka 仅在 UGC 多区域规模引入。
- **双写绞杀者迁移（Strangler Fig + Dual-Write）**：重构期保留 set/save_object 为真相，新增 EventEmitShim：在 receive_damage/pay_money/skill_death_penalty/killer_reward 等关键写点旁挂事件发布（先只读旁路，不动写）。验证事件流与 dbase 一致后，逐步将写侧切到聚合，最后拆除 set 直写。LPC 的 log_file 可平滑并入 shim。
  - 适用性：迁移路径，全域适用，经济域为首个切换试点。
- **因果关联元数据（Causation/Correlation Id）**：现状 set_temp("last_damage_from", who)/set_temp("last_eff_damage_from", id) 已在手工跟踪因果。应规范化为事件元数据：command_id（触发命令）、causation_id（导致本事件的上游事件）、correlation_id（一次玩家动作贯穿整条事件链）。这是反作弊回溯与分布式追踪的基础。
  - 适用性：战斗链、击杀归属、经济转账链、UGC Agent 协作因果。

## 适用性
- 经济域(金钱/银行/交易/任务奖励)：最高优先级，CQRS+ES 双记账直接解决反作弊，MONEY_D 的 cashflow 统计是天然切入点
- 社交域(组队/婚姻/师徒/门派)：低频高价值，事件溯源契合度最高，关系可完整回溯
- 角色成长域(技能升级/属性/经验/死亡惩罚)：中频，事件+周期快照，支持成长曲线审计与异常检测
- 战斗域(攻击/伤害/死亡)：高频，用回合聚合事件+周期快照而非逐 tick 事件，避免事件爆炸
- UGC 平台域(DSL 剧情/Agent 协作)：跨题材多租户，事件流天然适配多生产者与剧情回放
- 跨网/聊天域(CHANNEL_D/InterMUD)：高频瞬态，用 NATS/Stream 做扇出而非聚合状态

## 权衡
- 事件溯源增加写路径复杂度：set() 一步突变 拆为 Command→校验→Event→Apply→投影，战斗高频域若逐 tick 事件化会爆炸，须用聚合事件(CombatRoundResolved)+快照控制量。
- 存储与运维成本上升：事件流只增不减，需设保留期/归档/压缩策略；新增 PG 事件库+NATS+Redis 三件套，单机 MUD 阶段偏重，应按域渐进引入。
- 最终一致性延迟：CQRS 读模型异步于写侧，玩家买完物品背包可能延迟几十 ms 才更新，需 UI 容错或对关键读走读己写(read-your-writes)补偿。
- 迁移期双写一致性风险：strangler fig 双写阶段若 set 与事件发布不同步会产生数据漂移，需对账脚本定期校验 dbase 快照与事件回放结果一致。
- 学习曲线：团队需从'直接 set 改状态'转向'发事件让聚合应用'的心智模型，LPC 的 set/query 习惯迁移成本不可低估，需先在经济域小范围验证。
- LPC 对象引用(enemy/killer/team 是 object 数组)无法直接持久化为事件载荷：需统一用 id 引用 + 在投影时解析，重构涉及 attack.c/team.c 的内存态重设计。
- 反作弊收益真实但非银弹：回放可重建历史状态检测异常(暴富/瞬移/属性溢出)，但无法防实时外挂/脚本行为，仍需行为侧风控配合。

## 推荐
- 阶段0-双写旁路(1-2月)：保留 set/save_object 为真相，在 receive_damage(feature/damage.c)、pay_money(feature/finance.c)、killer_reward/death_penalty(adm/daemons/combatd.c)、skill_death_penalty 等关键写点挂事件发布 shim，写入 PostgreSQL 追加表；把 log_file 的 PLAYER_DEATH/PKILL_DATA/MONEY 等并入。零风险获得结构化审计。
- 阶段1-经济域先行(2-3月)：Wallet 聚合双记账，事件 MoneySpent/MoneyReceived/TransferMoney，对接 MONEY_D 的 cashflow 统计；建回放检测脚本扫异常(余额负、转账双方不平、短时间内暴富)，产出反作弊看板读模型。
- 阶段2-角色快照+关键事件(2-3月)：SkillUp/LevelUp/StatChanged/CharacterDied 为事件；dbase 沿用 heart_beat tick 周期快照(每30s或关键节点)；战斗回合聚合事件 CombatRoundResolved 而非逐 tick。
- 阶段3-社交域(1-2月)：Team/Marry/师徒/门派 成员关系事件化，低频高价值，最易完整落地并显效。
- 阶段4-读模型分离与热更新(2-3月)：背包/排行/银行流水/战报 投影独立部署，投影逻辑热更新=重建投影不触写侧；前端走 WebSocket 订阅投影。
- 阶段5-UGC/分布式(按需)：DSL 剧情与 Agent 协作产出事件流到共享日志，多租户分区(NATS subject/PG schema 隔离)；仅在跨区域多租户达规模时引入 Kafka。
- 技术选型落地：权威存储 PostgreSQL(append-only events 表+snapshots 表)；热事件 Redis Stream；扇出 NATS JetStream；新增 Python EventStore/CommandBus/ProjectionRunner 三组件，复用 LPC 的 dbase/default_ob/heart_beat 概念平滑映射团队认知。
- 不要全量事件溯源战斗 tick：每 tick 事件会爆炸，用回合聚合+连续态快照；不要过早引入 Kafka，单区域 MUD 用 PG+NATS 足够且运维成本低。
