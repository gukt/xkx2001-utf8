# 方案设计·ECS实体系统

## 设计概述
核心理念：XKX 的 feature 混入体系已是"组合优于继承"的雏形——F_DBASE 即数据袋、heart_beat 即系统循环、daemon 即无状态逻辑服务、apply/ 修饰符堆叠即 ECS 组件聚合。ECS 是其自然演进而非颠覆。方案用自研 SparseSet ECS 替换 LPC 的 inherit 编译期静态混入，实现四个根本转变：(1) 组件运行时动态挂载/卸载（支持 UGC 多题材实体），克服 feature 编译期固定无法运行时组合的痛点；(2) System 替代 daemon+heart_beat 做批处理调度，可并行、可分片、可分布式，破除单进程单线程瓶颈与每实体独立 heart_beat；(3) 事件总线解耦跨系统 this_object()->method() 隐式耦合，DamageEvent/EquipEvent/MoveEvent 等显式化控制流；(4) Prefab/Archetype 替代 default_ob 单级回退，升级为完整原型/深克隆，统一 UGC 场景定义。身份用 64 位 EntityID 解耦身份与代码路径（解决 file_name 强绑定），对象引用全部替换为可序列化 EntityRef。技能系统保留策略对象多态（472 个 SKILL_D 仍为 OOP 行为定义），实体仅挂 SkillRef 组件引用技能 ID+等级，SkillSystem 通过 ID 查找策略执行——技能是行为而非数据，不做纯组件。设计遵循"LPC 邻近但非真 ECS"的痛点结论：数据与行为分离、System 显式 (entity, components) 调用替代动态分派、带命名空间组件类型替代扁平 18-feature 命名空间。持久化采用 snapshot+event log 双轨（对应 save_object+log_file），永久/瞬时两层数据分离保留（对应 dbase vs tmp_dbase）。

## 组件
- **ECS 运行时核心 (World/Registry/Archetype)**：Entity 的创建/销毁/组件挂载/查询的总入口。Entity 是 64 位整数 ID（高位编码 shard/region，低位自增），不再与代码路径绑定。组件存储采用 SparseSet：每个组件类型一个稀疏数组（entity->dense index 映射 + 紧凑数据数组），支持 O(1) 挂载/卸载/查询，遍历时 cache-friendly 连续内存。Archetype 记录组件组合，相同组件集的实体聚簇存储以加速批量 System 遍历。提供 create_entity(prefab, overrides)、destroy_entity、add/remove_component、get_component[T]、query(T1,T2,...) 按 SparseSet 求交。这是替换 inherit 编译期静态组合、支持运行时动态挂载/卸载（UGC 多题材实体）的基础。（技术：自研轻量 Python ECS，不依赖 entt-py（C++ 绑定增部署复杂度）或 esper（活跃度低）。组件用 dataclass + __slots__ 减少内存与属性访问开销；SparseSet 用 array.array/ndarray 存紧凑数据。uvloop 提速 IO，但仿真 tick 为单分片内串行保证确定性。）
- **组件族 (Component Schema，按领域聚合)**：按领域聚合设计而非 1:1 映射 18 个 feature。核心组件：(1) Identity(name/id/title/desc/long) 对应 F_NAME+F_DBASE 身份键；(2) Vitals(qi/jing/jingli/neili 的 current/eff_max/max 三档) 对应 F_DAMAGE 三层资源；(3) Attributes(str/int/con/dex/kar/per 基础值) 对应 F_ATTRIBUTE；(4) DerivedAttributes(query_str 等派生值 + dirty 缓存)；(5) ModifierStack(apply/ 堆叠表) 对应 tmp_dbase['apply'] 修饰符聚合；(6) SkillSet(skills/learned/skill_map/skill_prepare) 对应 F_SKILL；(7) CombatState(enemy_id[]/killer_id[]/target/wimpy) 对应 F_ATTACK，用 EntityID 数组替换 object 指针；(8) EquipmentSlots(weapon/secondary_weapon/armor_by_type) 对应 F_EQUIP；(9) Conditions(状态效果表，含到期时间与 CND_CONTINUE 标志) 对应 F_CONDITION；(10) Position(room_id/weight/encumbrance/max_encumbrance) 对应 F_MOVE；(11) Inventory(容器内 EntityID 列表) 对应容器语义；(12) Wallet(gold/silver/coin 余额) 对应 F_FINANCE，替换实体货币对象；(13) TeamRelation/SpouseRelation(关系 EntityID) 对应 F_TEAM/F_MARRY；(14) ActionState(busy/interrupt/queue) 对应 F_ACTION；(15) DynamicProps(路径式 PropertyBag) 承载 UGC DSL 动态键，复用 F_DBASE 路径语义但类型化访问走组件。（技术：pydantic v2 dataclass 做 schema 校验与序列化，字段标 @persist/@transient 区分持久与易失（对应 dbase vs tmp_dbase 的 static 修饰）。每个组件实现 to_snapshot()/from_snapshot() 与 delta 计算。）
- **System 调度器 (替代 daemon+heart_beat)**：无状态逻辑服务，以 (entity, components) 为参数执行。System 替换 daemon 单例与每实体 heart_beat 独立循环，改为全局调度器批量遍历查询结果集。核心 System：(1) CombatSystem 执行 do_attack 七步管线（选技能->取招式->AP/DP 命中->PP 招架->伤害计算->施加伤害->反击），对应 COMBAT_D；(2) VitalsSystem 处理 DamageEvent/HealEvent 扣减恢复 + 死亡/昏迷判定，对应 F_DAMAGE+heart_beat 死亡检查；(3) HealSystem 恢复 qi/jing/jingli，对应 heal_up；(4) ConditionSystem tick 状态效果衰减，对应 update_condition；(5) AttributeSystem 重算 DerivedAttributes（dirty 标记触发，对应 query_str 缓存失效）；(6) SkillSystem 处理 improve_skill/learning + 通过 skill_id 查找策略对象执行（SKILL_D 保留为 OOP 策略）；(7) EquipmentSystem 处理 EquipEvent 更新 ModifierStack->标记 AttributeSystem dirty；(8) MovementSystem 处理 MoveEvent + weight 传播；(9) ActionSystem 处理 busy/interrupt/continue_action；(10) FinanceSystem/WalletSystem 处理 pay_money 账本；(11) NPCAISystem 处理 chat/auto_perform。调度器支持非均匀 tick（char.c tick=5+random(10) 降频思想）：高频系统（Combat）每 tick，低频系统（Condition）每 N tick。（技术：System 为纯函数类，update(world, dt, ctx) 无副作用于全局，仅读写传入组件 + 发布事件。调度器维护优先级队列与 tick 计数器。System 可按 region 分片独立执行。）
- **事件总线 (EventBus，解耦 this_object()->method())**：替换 LPC feature 间直接方法调用（this_object()->reset_action()、equip 后隐式触发 attribute 重算）。发布订阅模型：System 发布领域事件，订阅者 System 响应。同进程内存分发（dict[event_type]->handlers），跨分片经 Redis Stream/NATS JetStream。关键事件：DamageEvent(source,target,type,amount,weapon_id,skill_id)->VitalsSystem 扣血+ConditionSystem 检死亡+FinanceSystem 记战报；EquipEvent(item_id,slot)->EquipmentSystem 更新 ModifierStack->AttributeSystem 标 dirty；MoveEvent(from_room,to_room,entity)->MovementSystem 更新 Position+Inventory+AOI 广播；SkillUsedEvent->SkillSystem improve；ConditionAppliedEvent/ExpiredEvent；MoneySpentEvent/MoneyReceivedEvent（双记账反作弊）；DeathEvent->killer_reward/death_penalty 策略链；TeamJoinEvent/MarryEvent。事件携带单调 seq 支持断线重放（对应 WebSocket delta 同步）。（技术：进程内用 dispatch table（事件类型->handler 列表），同步派发（单分片内 tick 串行保证确定性）。跨分片事件经 Redis Stream（热）/NATS JetStream（扇出）。事件结构用 msgpack 序列化，追加写 PostgreSQL events 表为权威审计源（对应 log_file PLAYER_DEATH/PKILL_DATA）。）
- **Prefab/Archetype 系统 (替代 default_ob 原型回退)**：替换 F_DBASE 的 default_ob 单级回退与 LPC blueprint/clone 双层模型。Prefab 是只读的组件组合模板（YAML/JSON DSL 资源），克隆时实例化组件副本（深拷贝可变字段）。武器/防具/NPC 的只读定义作为 Prefab 资源，改 Prefab 即全局生效（对应改 blueprint 影响所有 clone）。UGC 场景定义即用户编写的 Prefab，多题材（武侠/航海/书院）即不同组件集的 Prefab 族。支持 Prefab 继承（子 Prefab 覆盖父组件字段），超越单级 default_ob。instantiate(prefab_id, overrides) 返回新 Entity。（技术：Prefab 资源存储为 JSON（DSL 编译产物 IR），内存中用不可变 frozen dataclass 缓存。克隆走 copy.deepcopy 组件实例 + 应用 overrides。版本化 Prefab（content-addressed hash）支持 UGC 版本管理与回滚。）
- **Query/索引层**：替换全局 users()/livings()/children() O(n) 遍历。SparseSet 按 component 集合求交提供 query(CombatState, Vitals) 获取所有战斗中实体；维护二级索引：room_id->entities（房间内实体，对应 tell_room 广播）、team_id->members、region->entities。索引在 MoveEvent 时增量更新。避免 filter_array(users()) 全量扫描。（技术：SparseSet 交集查询为内存操作。二级索引用 dict 维护，事件驱动增量更新。跨分片查询走投影/读模型服务（如排行榜、银行流水），不在游戏 tick 热路径执行。）
- **迁移适配层 (LPC 兼容桥)**：增量迁移期桥接 LPC 行为与 ECS。用 actor 适配器封装现有 LPC 对象为 Entity 抽象：query/set 路由到 DynamicProps 组件或类型化组件，call_other 映射为 System 调用或事件。保持同步返回值语义（move() 后立即可查 Position）在单进程适配期成立，待目标系统迁移完成再切异步。逐子系统替换：先 Identity/Vitals/Position 核心组件，再 Combat，再 Skill，最后边缘 feature(marry/team/finance)。（技术：适配器在单进程 asyncio actor 内运行，逐步将 LPC feature 行为迁入 Python System。每个迁移阶段保持游戏可运行，避免一次性全量重写。）

## 关键接口/事件
- World/Registry API: create_entity(prefab_id: str | None, overrides: dict | None) -> EntityID; destroy_entity(eid); add_component(eid, comp); get_component[T](eid) -> T | None; remove_component(eid, T); has_component(eid, T) -> bool; query(*comp_types) -> SparseSetIter（按组件集求交，替代 users()/livings()/children() 全量遍历）
- EntityID 与 EntityRef: EntityID 为 64 位整数（高位 shard/region，低位自增），可序列化跨进程；EntityRef(addr) 是跨节点透明代理，禁止 actor 间传裸引用，仅传 EntityID 或值快照（沿用 LPC save 不保留引用的安全特性）
- System 接口: class System: def update(self, world: World, dt: float, ctx: TickContext) -> None; def subscriptions(self) -> list[type[Event]]（声明订阅的事件类型）；System 为纯函数，仅读写传入组件 + 发布事件，无全局可变状态
- EventBus: publish(event: Event) -> None; subscribe(event_type: type[Event], handler: Callable) -> SubscriptionToken; unsubscribe(token)。事件携带 seq: int 单调序号支持断线重放
- 关键领域事件: DamageEvent(source_id, target_id, type: 'qi'|'jing'|'jingli', amount, weapon_id?, skill_id?)->VitalsSystem+ConditionSystem+FinanceSystem；HealEvent(type, amount)；DeathEvent(victim_id, killer_id?)->DeathPenaltyPolicy 链；MoveEvent(entity_id, from_room, to_room, silently)->MovementSystem+AOI 广播；EquipEvent(item_id, slot, owner_id)->EquipmentSystem->AttributeSystem dirty；UnequipEvent；SkillUsedEvent(actor_id, skill_id, target_id?)->SkillSystem improve；ConditionAppliedEvent(target_id, cnd_name, info)/ConditionExpiredEvent；MoneySpentEvent(payer_id, amount, merchant_id?)/MoneyReceivedEvent（双记账反作弊）；StatChangedEvent(entity_id, stat, delta)；TeamJoinEvent/TeamLeaveEvent(team_id, member_id)；MarriageEvent
- Prefab/Archetype: register_prefab(prefab_id: str, components: list[ComponentSpec]); instantiate(prefab_id, overrides: dict | None) -> EntityID（深拷贝组件实例 + 应用 overrides，对应 LPC new() 克隆）；inherit_prefab(child, parent)（多级原型继承，超越 default_ob 单级回退）
- ComponentStore (SparseSet): get(eid)->T; set(eid, val); contains(eid)->bool; iter()->Iterator[(eid, T)]（连续内存遍历，cache-friendly）
- TickContext: 携带 region_id、seeded_rng、current_tick、active_only: bool（仅活跃实体 tick，对应 set_heart_beat(0) 熄火）；schedule_delayed(callback, delay)（对应 call_out，但持久化到调度器）
- SkillRef + SkillStrategy 注册表: SkillRef(skill_id: str, level: int) 组件挂在实体上；SkillRegistry.get(skill_id)->SkillStrategy（hit_ob/perform_action/exert_function 策略对象，对应 472 个 SKILL_D）；SkillSystem 通过 skill_id 查找策略执行，技能是行为定义而非实体数据
- ConditionRegistry: get(cnd_name)->ConditionStrategy（update_condition 返回 CND_CONTINUE/CND_NO_HEAL_UP 标志，对应 72 个 condition daemon）；策略对象可热加载

## 数据模型
实体身份：EntityID 为 64 位整数（高位 shard/region，低位自增），解耦身份与代码路径——解决 file_name 即身份的强绑定，支持热重载与多版本共存（UGC 必需）。EntityID 跨进程可序列化，替代 LPC object 指针。

组件 schema：用 pydantic v2 dataclass 定义类型化字段，杜绝散落全库的 query('xxx') 字符串键拼写错误。每个组件实现 to_snapshot()/from_snapshot()。字段标注 @persist（持久，入快照，对应 dbase）或 @transient（易失，仅内存，对应 tmp_dbase static）。这保留了 F_DBASE 永久/瞬时两层数据分离的清晰边界。

核心组件字段示例：
- Vitals: qi/eff_qi/max_qi、jing/eff_jing/max_jing、jingli/max_jingli、neili/max_neili（current/eff_max/max 三档，区分疲劳与创伤）
- Attributes: str/int/con/dex/kar/per（基础值，派生值在 DerivedAttributes 缓存）
- ModifierStack: dict[str, int] apply 修饰符表（对应 tmp_dbase['apply/strength'] 等），dirty 标记触发 AttributeSystem 重算
- CombatState: enemy_ids: list[EntityID]（MAX_OPPONENT 概念保留但可升级为带仇恨值的表）、killer_ids: list[str]、target_id、wimpy_ratio
- SkillSet: skills: dict[str,int]、learned: dict[str,int]、skill_map: dict[str,str]、skill_prepare
- Conditions: dict[str, ConditionInfo(duration, info, continue_flag)]
- Position: room_id: str（world://region/room 寻址）、weight、encumbrance、max_encumbrance
- EquipmentSlots: weapon_id/secondary_weapon_id/armor_by_type: dict[str,EntityID]
- Wallet: gold/silver/coin: int（三币制 10000/100/1 保留，但不再是实体对象）
- Inventory: item_ids: list[EntityID]

DynamicProps 扩展点：每个实体可挂一个 DynamicProps 组件承载 UGC DSL 动态键，复用 F_DBASE 的 '/' 路径式访问语义与 functionp evaluate 惰性计算，但已知/类型化访问走对应组件字段。这平衡了类型安全与 UGC 灵活 schema。

持久化：双轨制。snapshot（组件 JSON 快照，对应 save_object .o）+ event log（事件溯源追加表，对应 log_file PLAYER_DEATH/PKILL_DATA/MONEY 审计）。玩家状态存 PostgreSQL（snapshot 表 + events append-only 表）+ Redis（热状态缓存）。崩溃时由最近 snapshot + 重放 events 恢复，解决原 .o 全量覆盖无历史无并发保护问题。分片键用 region，房间持久化路径 /data/user/<首字母>/<id>.o 的分片前缀思想保留为 region 前缀寻址。

确定性随机：每场战斗/每个 region 分配独立 seeded RNG，回合结果写 append-only 事件日志支持回放与反作弊审计——分布式下调试与公平性的前提。

## 旧->新映射
- inherit F_DBASE + dbase/tmp_dbase mapping + 路径式 set/query（148 行 feature/treemap.c/dbase.c） -> **类型化 Component schema（pydantic dataclass）+ DynamicProps 组件承载 UGC 动态键**（已知字段升为类型化组件杜绝拼写错误；未知/DSL 键进 DynamicProps 保留路径式语义与 evaluate 惰性）
- default_ob 单级原型回退（query 找不到则查 blueprint） -> **Prefab/Archetype 资源，克隆时实例化组件副本，支持多级继承覆盖**（超越单级回退；改 Prefab 全局生效；UGC 场景定义即 Prefab）
- inherit F_ATTACK（enemy/killer object 数组，MAX_OPPONENT=4，attack()->COMBAT_D->fight） -> **CombatState 组件（enemy_id[]/killer_id[]）+ CombatSystem**（object 指针改 EntityID 数组可跨进程；select_opponent 留作可升级仇恨表扩展点）
- receive_damage/receive_wound/receive_heal/receive_curing（feature/damage.c 直接 set dbase） -> **Vitals 组件 + DamageEvent/HealEvent + VitalsSystem**（逻辑层不再直接改底层数据，经事件->System；三层资源 current/eff_max/max 保留）
- query_str/int/con/dex/kar/per（feature/attribute.c 读 apply/ 聚合 + skill 派生） -> **Attributes(基础值) + ModifierStack(apply 堆叠) + DerivedAttributes(dirty 缓存) + AttributeSystem**（保留派生计算公式；dirty 缓存避免每次重算；apply/ 堆叠语义精确迁移防数值漂移）
- skills/learned/skill_map/skill_prepare 四 mapping（feature/skill.c）+ 472 个 SKILL_D 策略对象 -> **SkillSet 组件(技能等级/学习度/映射) + SkillSystem(查策略对象执行) + SKILL_D 保留为 OOP 策略**（技能是行为定义非实体数据，保留策略对象多态(hit_ob/perform/exert)；实体挂 SkillRef(skill_id, level)）
- conditions mapping + CONDITION_D(name) 外部 daemon + CND_CONTINUE 生命周期（feature/condition.c） -> **Conditions 组件(状态效果表+到期时间) + ConditionSystem tick 衰减 + 状态效果策略注册表**（保留 CND_CONTINUE 自主存活语义；condition daemon 迁为可热加载策略对象）
- wear/wield + set_temp('apply', ...) 聚合到 tmp_dbase（feature/equip.c） -> **EquipmentSlots(weapon/secondary/armor_by_type) + ModifierStack + EquipmentSystem + EquipEvent**（装备卸下显式触发 ModifierStack 重算；双手/盾占位逻辑保留为槽位规则）
- weight/encumb + move() 跨容器 + environment()（feature/move.c） -> **Position(room_id) + Inventory(容器) + MovementSystem + MoveEvent**（environment() 改 Position.room_id 查询；weight 传播经 MoveEvent 链式更新容器 max_encumb）
- present('gold_money') 硬编码查找实体货币对象 + pay_money（feature/finance.c） -> **Wallet 组件(gold/silver/coin 余额) + FinanceSystem + MoneySpentEvent 双记账**（货币不再是 clone 实体对象；账本聚合替代 children() 全量扫描审计流通量）
- heart_beat() 上帝方法（战斗/治疗/状态/衰老/频道/熄火，inherit/char/char.c） -> **System 调度器拆分：CombatSystem/VitalsSystem/HealSystem/ConditionSystem/... 各自独立 tick**（非均匀调度高频+低频；空闲 set_heart_beat(0) 映射为实体退出活跃 System 查询集）
- this_object()->method() 动态分派（feature 间隐式调用，如 reset_action） -> **System(entity, components) 显式调用 + EventBus 事件**（消除隐式契约，可静态分析与单元测试）
- 18 个 feature 方法压平到单一对象命名空间（nomask 消歧） -> **带命名空间的 Component 类型（CombatState/SkillSet/EquipmentSlots...）**（组件方法不冲突；跨组件访问经显式 get_component）
- query('xxx') 散落 8400 文件的字符串键 -> **类型化 Component schema 字段访问**（IDE 补全与静态检查；DynamicProps 仅留给 UGC/未知键）
- save_object .o 全量覆盖 + autoload 重建引用 -> **组件 snapshot(JSON) + event log 追加 + @persist/@transient 字段标注**（持久组件入快照、易失组件仅内存；autoload 演进为实体引用的快照/投影重建）
- per-object heart_beat 每实体独立更新循环 -> **全局 System 批量遍历查询结果集（可批处理/并行/分片）**（批处理提升 cache locality；可按 region 分片并行）
- call_other 同步阻塞 + 同步返回值依赖（move() 后查 environment()） -> **单分片内 System 仍同步（保确定性）；跨分片改异步消息 + EntityRef**（适配期保持同步语义，目标系统迁移后再切异步）

## 分布式扩展策略
实体 ID 自带 shard/region 前缀，placement 按区域共同体分片（基于 6414 房间出口图社区凝聚），同区域实体尽量同节点。EntityRef(addr) 替代裸对象指针，跨进程为透明代理、本地为直接引用，禁止 actor 间传裸引用仅传 addr 或值快照。

同房间战斗参与者保持同节点亲和：CombatSystem 实例化为 region/战斗级 Coordinator，串行裁决回合避免分布式事务。战斗确定性靠 per-region seeded RNG + append-only 事件日志，支持回放与反作弊审计。

System 可按 region 分片独立执行：每个分片跑自己的 System 调度器 tick，跨分片事件经 Redis Stream（热事件）/NATS JetStream（扇出）。高频事件（房间内广播、战斗）本进程内派发，低频高价值事件（频道、跨区移动）走总线。

跨分片移动（go 命令跨区）：冻结玩家->快照 dbase/inventory/combat/team 组件写入 Redis 附 TTL->目标分片 restore->源分片注销（对应 LPC move 的环境切换，但分布化）。组队迁移按队形批量 handoff 保持顺序。

组件查询 SparseSet 内存内本分片执行；跨分片查询（排行榜、银行流水、全局频道）走投影/读模型服务，不在游戏 tick 热路径。全局守护进程（channeld/natured）迁出为共享状态服务，channeld 改 pub/sub topic 路由替代 users() 全量遍历。

无状态 WebSocket 网关水平扩展，session->shard 路由表存 Redis 支持断线重连定位；游戏分片有状态持有房间/NPC/玩家/AOI。单分片设计承载 5000-8000 并发，1 万在线玩家需 5-8 分片。

## 技术选型
- 自研轻量 SparseSet ECS 运行时：不依赖 entt-py（C++ 绑定增部署复杂度）或 esper（纯 Python 但活跃度低）；自研可针对 MUD 访问模式优化（房间查询、AOI、战斗批处理）并与 WebSocket 后端深度集成，避免外部依赖风险
- Python 3.11+ dataclasses + __slots__：组件定义紧凑，减少内存与属性访问开销
- pydantic v2：组件 schema 校验、序列化、字段标注 @persist/@transient；DSL 编译产物 IR 的运行时校验
- uvloop + asyncio：事件循环提速 IO，仿真 tick 单分片内串行保证确定性
- msgspec：高频战斗/状态同步事件序列化（比 JSON 快，对齐 WebSocket MsgPack 协议）；UGC DSL 用 JSON 兜底动态内容
- PostgreSQL + Redis：权威存储（events append-only 表 + snapshots 表）+ 热状态缓存，替代 .o 平文件
- NATS JetStream：跨分片事件扇出与联邦（替代 InterMUD UDP+|| 字符串协议）
- Ray（可选）：作为执行后端与 UGC/ML 生成工作负载，游戏主循环 actor 自研以掌控延迟、消息序与确定性——不直接用 Akka/Orleans（非 Python 增跨语言成本）
- Prefab 资源：JSON/YAML DSL 编译为不可变 frozen dataclass 缓存，content-addressed hash 支持版本管理

## 风险
- 迁移面极大：8400+ LPC 文件大量依赖 this_object()->method() 隐式 feature 间调用与 query('xxx') 字符串键，难以静态分析全部依赖，需逐子系统替换并用适配层桥接，周期以月计
- 同步返回值依赖深：现有代码 move() 后立即查 environment()、do_attack 内联读写 dbase 返回值，单分片适配期需保持同步语义，切异步时调用方需大量重构（背景明确标注迁移成本高）
- ModifierStack 聚合语义须精确还原：apply/ 堆叠顺序、equip.c 的聚合规则、attribute.c 的派生公式（skill 派生 improve/10 等）若迁移有误会导致数值漂移，玩家感知明显（战斗平衡敏感），需建立回归测试基线对比
- 战斗确定性：LPC random() 隐式全局 RNG，分布式下需 per-region/per-战斗 seeded RNG 且 do_attack 递归（反击 riposte）调用顺序需可复现，否则回放与反作弊审计失效
- Python ECS 性能：LPC 编译期方法分派 vs Python 运行时组件查询，高密度战斗（万对象 tick）可能成为瓶颈，需 SparseSet 紧凑存储 + Archetype 聚簇 + dirty 缓存避免无谓重算，必要时热点系统用 Cython/numpy 向量化
- 组件拆分粒度权衡：过细（每 feature 一组件）导致 query 求交多、缓存局部性差；过粗（大 Vitals 含所有生命字段）违反单一职责且 UGC 难组合。需按访问模式与变更频率聚类（Vitals 高频写、Attributes 低频派生应分离）
- 状态一致性：组件跨 System 共享（CombatSystem 写 Vitals，VitalsSystem 也写 Vitals），单分片内 tick 串行可保证，但跨分片事件异步派发时需明确组件归属与锁粒度，避免竞态（如同房间两人同时移动）
- LPC 行为语义还原风险：F_DBASE 的 functionp 自动 evaluate、default_ob 回退、simul_efun 隐式覆写（destruct 先 remove）等魔法行为易在迁移中遗漏，需建立行为对比测试
- call_out 闭包捕获对象引用：perform/exert 用 start_call_out(回调) 实现持续效果，闭包捕获对象引用无法序列化/跨进程，须改为 tick 调度的显式 Effect 对象（可序列化可中断），现有持续技能逻辑需逐个重写

---

## 🔍 对抗验证

**裁定**：risky：方案对 LPC 旧系统的模式研究扎实、组件映射大体准确（18 feature / 472 SKILL_D / 72 condition / 6414 room / 989 dbase 键均已核实），方向正确（ECS 确是 feature mixin 的自然演进而非颠覆）。但有三个架构级硬伤使其在迁移可行性与高并发成立性上存在高风险：(1) query_entire_dbase() 活引用直改模式（46 文件，combatd.c 交叉读写双方 11+ 字段含 combat_exp/potential，这些字段在 15 个组件中无归属）直接破坏组件边界，方案完全未识别；(2) 自研 SparseSet+Archetype 双存储 ECS 是迁移期范围膨胀反模式，且 Archetype 在 5000 实体规模下收益微乎其微；(3) dbase 中 92 处闭包即数据（含战斗 actions 函数指针）和 call_out 闭包捕获对象引用未纳入组件/System 设计。若不补齐这些缺口，CombatSystem 迁移将卡在组件归属与行为闭包翻译上，"月计"周期严重低估。

**严重度**：high

### 问题与修复
- **query_entire_dbase() 活引用直改模式未被识别为组件边界破坏者**
  - 影响：combatd.c (行 356-357, 441-455, 696-712) 通过 my=query_entire_dbase() 拿到整个 dbase 映射的活引用后直接交叉读写 my["combat_exp"]、my["potential"]、my["jingli"]、your["combat_exp"]、your["potential"] 等跨 11+ 字段。组件拆分后这些字段分属 Vitals/Attributes/Progression，CombatSystem 需同时 get_component 多个组件且对两个实体都写。更严重的是 combat_exp(被查 1275 次，全库第 3 高频键) 和 potential/max_potential 在方案的 15 个组件中无任何归属，会落入 DynamicProps，彻底抵消类型化收益。
  - 修复：必须在迁移 CombatSystem 前明确：每个 query_entire_dbase 活引用点都要改为按组件类型化访问，并补充一个 Progression 组件（combat_exp/potential/max_potential/death_times/PKS/MKS/behavior_exp）承载战斗成长数据。对 my['int']/my['dex'] 这类绕过 query_int() 读裸值的点，必须区分是读基础值(Attributes.int)还是派生值(DerivedAttributes.int)，逐一核对。建议先用静态分析工具枚举全部 query_entire_dbase 调用点的读写键集合，建立字段到组件的完整映射表后再动 CombatSystem。
- **自研 SparseSet+Archetype 双存储 ECS 是迁移期的范围膨胀反模式**
  - 影响：方案同时声称用 SparseSet 做 O(1) 挂载/查询 + Archetype 做同组件集聚簇遍历。这两者是互斥的存储策略（enTT 用 SparseSet，ECS-DOTS 用 Archetype），混用意味着组件 add/remove 时要在两套结构间同步迁移，实现复杂度高。对 5000-8000 实体/分片的 MUD 规模，Archetype 聚簇的 cache locality 收益微乎其微（L1 cache 对 5000 对象级别的遍历无感），徒增框架复杂度。
  - 修复：放弃 SparseSet + Archetype 双存储。5000-8000 实体规模下选 SparseSet 单一存储即可（enTT 也是 SparseSet 为主，Archetype 仅用于特定批量场景）。若确实需要批量战斗遍历优化，在 CombatSystem 内对 query 结果做一次排序聚簇缓存即可，不需要全局 Archetype 存储。
- **dbase 中 92 处闭包即数据(functionp as data)未纳入迁移方案**
  - 影响：reset_action() (attack.c 行 143-171) 将 (: call_other, SKILL_D(skill), 'query_action', me, ob :) 闭包存入 dbase['actions']，combatd.c 行 384 读取后行 399/401 执行，行 762 evaluate(action['post_action']) 触发后置行为。这些闭包在 move() 跨容器时随实体序列化/反序列化，承载战斗行为语义。方案的 SkillSystem 说'通过 skill_id 查找策略对象执行'但未说明 dbase['actions'] 这个实体级行为闭包如何迁移到组件模型——它既不是纯数据也不是纯策略，是挂在实体上的延迟求值行为。
  - 修复：CombatSystem 必须将 actions 闭包映射显式建模为 ActionResolver：实体挂 ActionState 组件(记录当前 action_flag/weapon_id/prepare)，CombatSystem 通过 skill_id 查 SkillRegistry 获取 SkillStrategy，再调 strategy.query_action(me, victim, weapon) 返回结构化 ActionResult(action_text/damage_type/post_action_hook) 而非闭包。post_action 改为 SkillStrategy.post_attack() 方法调用。闭包场景逐个迁移并建立等价测试。
- **Python ECS 高密度战斗性能风险被低估**
  - 影响：do_attack 一次调用约 6+ 次 random()、多次 query_skill()(每次做 apply/ 聚合+mapping 查找)、query_str()/query_dex()(每次做 6 技能遍历取 max+apply 聚合)。LPC 是编译期方法分派，Python ECS 每次 get_component[Vitals] + get_component[Attributes] + get_component[ModifierStack] + get_component[SkillSet] 都是运行时 dict 查找。单次 do_attack 可能产生 20-30 次组件查询。万对象 tick 下 Python 解释器开销将成为瓶颈，且战斗是 per-fight 串行的，无法向量化。方案提到'必要时 Cython/numpy 向量化'但 combat 本质不可向量化。
  - 修复：接受战斗不可向量化的事实，将优化重心放在：(1) 组件引用缓存——CombatSystem 在进入战斗回合时一次性取齐双方所有组件引用，后续字段访问走本地变量而非重复 get_component；(2) 预计算 action/skill_power 缓存，回合内不重复求值；(3) 若仍不足，用 Cython 仅编译 do_attack 热路径为编译模块而非全量向量化。明确 Python 后端单分片承载目标应下调到 2000-3000 并发(非 5000-8000)并相应调整分片数。
- **call_out 闭包改 Effect 对象的设计停留在风险清单，未落到组件/System 定义**
  - 影响：perform/exert 用 start_call_out(闭包) 实现持续效果(action.c 行 62-74)，196 个技能文件用 call_out。闭包捕获 this_object() 引用，无法序列化/跨进程/断线重放。方案在 risks 中正确识别了这一点('改为 tick 调度的显式 Effect 对象')但未在组件族或 System 中给出 Effect 组件设计——Effect 应是一等公民组件(挂在实体上、可序列化、可中断、可跨分片迁移)，而非风险清单里的一句话。
  - 修复：在适配层中引入 Effect 组件：承载 (skill_id, effect_type, remaining_ticks, payload, source_id) 的可序列化持续效果列表，由调度器 tick 衰减并回调 SkillStrategy.on_tick_effect()。start_call_out/eval_function 闭包逐个翻译为 Effect 实例，建立闭包到 Effect 的映射表与等价回归测试（特别是 huashan/feng.c 的 auto_perform 链和 exert 持续内功效果）。
- **do_attack 递归 riposte 的跨分片同步语义未明确**
  - 影响：combatd.c 行 772/777 do_attack(victim, me, ...) 递归调用假定同步返回。方案说'同房间战斗参与者保持同节点亲和'但 auto_fight init() (attack.c 行 229-258) 可在 move 进入房间时触发跨实体战斗，且 killer 列表(attack.c 行 16) 用 object 指针/字符串 id 混存。若迁移后某个参与者因分片边界不同节点，递归 do_attack 跨节点同步调用会破坏'单分片内串行确定性'。
  - 修复：明确 CombatSystem 实例化为 per-battle Coordinator：战斗开始时校验所有参与者(含 auto_fight 可能加入的)同分片，否则用 EntityRef 跨分片调用时必须降级为异步消息往返(放弃递归同步语义)，riposte 改为发起 RiposteEvent 由对方分片的 CombatSystem 下一 tick 处理。文档中需明确：跨分片战斗不支持同步递归反击，仅同分片战斗保持递归确定性。

### 改进建议
- 先补齐字段映射再动核心系统：用静态分析枚举 989 个 dbase 键的读写点，建立完整字段->组件映射表，至少覆盖前 100 高频键(占 90%+ 访问)。特别补 Progression 组件(combat_exp/potential/death_times) 和 Social 组件(family/* 用 949 次)。未覆盖键明确归 DynamicProps 并标注降级访问。
- 砍掉 Archetype 双存储，只用 SparseSet：5000 实体规模下 SparseSet 的 O(1) 查询和连续遍历已足够，Archetype 聚簇的 cache 收益对万级对象无感，省下的复杂度用于迁移本身。
- 放弃自研 ECS 运行时，先用 esper(虽低活跃但 API 稳定、纯 Python、无 C 编译) 或更简单的 component-as-dict 模型跑通迁移。若性能证实不足再针对性优化或换 entt-py。不要在迁移期同时做框架研发。
- 把 Effect 组件提升为一等公民：设计 EffectList(skill_id, effect_type, remaining_ticks, payload, source_id) 可序列化可中断组件 + EffectSystem tick 衰减，提前从 call_out 闭包迁移，这是断线重放和跨分片的前提，不能延后。
- 下调 Python 单分片承载目标到 2000-3000 并发(非 5000-8000)，相应按 1 万在线需 4-5 分片规划。CombatSystem 优化重点放在组件引用缓存(回合内一次取齐、本地变量访问)和 skill_power 预计算缓存，而非向量化。
- 迁移顺序调整为风险递增：先迁 Query/索引层(room_id->entities 二级索引)验证分片框架 -> 再迁 Identity/Position/Inventory(低耦合) -> 再迁 Vitals/Heal/Condition(只读为主) -> 最后迁 Combat(最高耦合、活引用、递归、闭包全在此)。Combat 迁移前必须先建立数值回归基线(per-attribute/per-skill 的输入输出快照对比)。
- 明确跨分片战斗降级语义：同分片战斗保持同步递归(确定性回放)；跨分片战斗降级为异步事件往返，riposte 改 RiposteEvent 下一 tick 处理。文档中显式声明此约束避免后续架构争议。
