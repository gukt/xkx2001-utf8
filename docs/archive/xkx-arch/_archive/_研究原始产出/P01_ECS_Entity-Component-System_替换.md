# 模式研究·ECS(Entity-Component-System) 替换 LPC inherit+feature 对象模型

## 概述
XKX 的 feature 混入已是组合优于继承的雏形，dbase 即数据袋、heart_beat 即系统循环、daemon 即无状态逻辑服务。ECS 是其自然演进而非颠覆。推荐自研 SparseSet ECS，按领域拆组件、系统替代 daemon+心跳、事件驱动跨系统通信，技能保留策略对象多态。

## 模式
- **实体即纯ID (Entity = pure ID)**：实体不再是一个包含数据和方法的完整对象，而仅仅是一个不透明的整数 ID。所有数据存在于组件中，所有行为存在于系统中。这彻底解耦了身份与状态。LPC 中对象 = 程序 + 状态(dbase) + 引用，三者绑定在一个对象实例上。
  - 适用性：高度适用。LPC 中对象身份与状态深度绑定（对象=程序+状态+引用），ECS 将三者分离。玩家=Connection+Identity+Vitals+Skills+Equipment+Inventory，NPC=Identity+Vitals+Skills+AIBehavior，物品=Identity+ItemDef+Weight，房间=Identity+RoomDef+Exits+Inventory。动态增删组件即可表达死亡变鬼、装备卸下、玩家断线等状态转换，无需继承层级。
- **组件即纯数据袋 (Component = pure data bag)**：组件是只含数据字段的 dataclass/struct，不含任何逻辑方法。系统通过组件类型查询实体集合并批量处理。LPC 的 dbase mapping 已经是数据袋雏形（set/query/add/delete + 路径访问），但混杂了持久化数据、临时状态(tmp_dbase)、函数值延迟求值三种性质。ECS 将其拆分为强类型、职责单一的组件。
  - 适用性：高度适用。LPC 的 dbase mapping 已是数据袋雏形，但混杂了持久化数据、临时状态、函数值。ECS 将其按领域拆分为强类型组件：Vitals(qi/jing/jingli/max_*/eff_*)、SkillSet(skills/learned/skill_map)、CombatState(enemy/killer 列表)、EquipmentSlots(weapon/armor 各槽位)、Identity(name/id/desc)、Position(location/weight/encumbrance)、Conditions(状态效果)。
- **系统即无状态逻辑服务 (System = stateless logic service)**：系统是遍历特定组件集合的纯逻辑函数，不持有实体状态。每个系统每 tick 查询其关心的组件组合并执行逻辑。系统间通过事件解耦。LPC 的 daemon 已经是无状态逻辑服务，heart_beat() 已经是系统循环——COMBAT_D->fight() 遍历敌人执行 do_attack，heal_up() 遍历 dbase 恢复气血。
  - 适用性：高度适用。XKX 的 daemon(COMBAT_D/CHAR_D/CONDITION_D 等 82 个)已经是无状态逻辑服务，heart_beat() 已经是系统循环且多个 feature(action/attack/damage)都调用 set_heart_beat(1) 唤醒实体。ECS 将其形式化：CombatSystem 替代 COMBAT_D->fight/do_attack，HealSystem 替代 heal_up()，ConditionSystem 替代 update_condition()。系统主动过滤活跃实体集合，替代 LPC 的 set_heart_beat(0/1) 机制。
- **事件驱动修饰器栈 (Event-driven modifier stack)**：装备穿戴/卸下、状态施加等操作产生事件，由对应系统监听并更新集中的 ModifierStack/Apply 组件。派生属性系统读取 base + modifiers 计算最终值。LPC 中 equip.c 直接修改 owner 的 tmp_dbase['apply']（wear/wield 往 apply 写入 armor_prop/weapon_prop），attribute.c 每次 query_str() 都重算 base+apply+skill_bonus。
  - 适用性：高度适用且是关键改进点。LPC 中 equip.c 直接修改 owner 的 tmp_dbase['apply']，attribute.c 每次 query_str() 都重新计算 base+apply+skill_bonus。ECS 中 EquipmentSystem 监听 EquipEvent 更新 ModifierStack，AttributeSystem 缓存派生值并在 modifier 变更时标记 dirty 重算，解决频繁查询的重复计算，利于大规模 NPC 批量属性更新。
- **原型/预制体替代 default_ob (Archetype/Prefab)**：用预定义的组件模板（Archetype/Prefab）替代 LPC 的 blueprint->clone->set_default_object 原型链。克隆实体时从预制体复制组件初始值，只读数据通过引用共享。LPC 的 default_ob 实现了原型模式：克隆对象 query 属性时 fallback 到蓝图对象。
  - 适用性：中高适用。LPC 的 default_ob 实现了原型模式（克隆对象查询时 fallback 到蓝图）。ECS 中可将武器/防具/NPC 的只读定义作为 Prefab 资源（JSON/DSL 定义），克隆时实例化组件副本。这与 UGC 平台的 DSL 剧情配置天然契合——用户用 DSL 定义的场景预制体就是 Prefab。
- **稀疏集存储与批量迭代 (SparseSet storage)**：每种组件类型维护一个稀疏集（entity_id -> 数据槽位），系统通过查询拥有特定组件组合的所有实体进行批量处理。数据按类型连续排列利于缓存预取。这是 ECS 相对 OOP 的核心性能优势，但需注意 Python 语言的限制。
  - 适用性：中等适用，需权衡。MUD 瓶颈是对象数量（数千房间/NPC/物品）而非每帧百万实体。Python 的 SparseSet 收益主要来自批量逻辑（一次性更新所有 NPC 心跳、批量战斗结算）而非纯缓存局部性。自研 ECS 应侧重批量查询+迭代 API 的便利性，而非过度追求内存布局优化。

## 适用性
- MUD 是 ECS 的理想场景之一：大量同类对象（NPC/物品/房间）需要批量 tick 处理，对象类型可通过组件组合动态表达而非固定继承树。CHARACTER 已混入 15 个 feature，再加功能需改基类，ECS 消除此瓶颈
- XKX 的 feature 混入 + daemon + heart_beat 三件套已天然具备 ECS 的组件 + 系统 + 循环结构，dbase 即数据袋、COMBAT_D 即系统、heart_beat 即遍历，迁移是形式化而非重设计
- 强属性交互（query_str 依赖 skills + apply + base 三源实时计算）在 ECS 中通过系统读取多组件解决，属正常模式。14/36 个 feature 文件使用 query_temp，修饰器数据需独立为 ModifierStack 组件
- UGC/DSL 平台需求与 ECS 的 Prefab/Archetype 模式高度契合：用户用 DSL 定义的剧情场景就是组件组合的 Prefab，多题材（武侠/大航海/书院）即不同组件集，天然支持运行时组合新世界
- 分布式部署：ECS 组件可按领域分区到不同服务器（战斗服务 / 社交服务 / 经济服务），实体 ID 做跨服寻址。系统无状态，可水平扩展多实例

## 权衡
- 优势：消除继承爆炸（CHARACTER 已混入 15 个 feature，再加功能需改基类影响所有子类）；组件可运行时增删表达状态转换（死亡/断线/装备）；系统批量处理利于大规模 NPC；数据与逻辑分离便于测试和分布式部署
- 优势：ECS 天然支持热重载——系统是无状态逻辑可独立更新；组件是纯数据序列化简单，利于存档/状态同步/UGC 场景导出导入。Pref 化的组件组合即用户可配置的游戏内容
- 代价：LPC 的函数值 dbase（set('short', (:...:)) 延迟求值）在纯数据组件中需改为事件回调或计算系统，增加间接层。这是 LPC 动态性与 ECS 静态数据的根本张力
- 代价：default_ob 原型链的透明 fallback 查询需显式实现为 Prefab 继承或默认值合并逻辑，失去 LPC 运行时透明委托的便利
- 代价：Python 中 ECS 的缓存局部性收益有限（Python 对象是堆分配指针，无法像 C++ struct 真正连续内存），不应照搬 C++ EnTT 的 Archetype 内存布局优化，应侧重批量迭代 API 便利性
- 代价：36 个 feature 文件与 82 个 daemon 的迁移工作量大，需分阶段进行（先核心战斗/属性/技能，后边缘 feature），LPC 兼容期需适配层桥接两种模型
- 风险：组件拆分过细会导致系统查询碎片化（一次战斗结算需 join Vitals+CombatState+EquipmentSlots+ModifierStack+SkillSet 5+ 组件）；过粗又退化为 God Object。需按访问模式聚合——常一起读写的字段放同一组件

## 推荐
- 采用自研轻量 SparseSet ECS，不依赖 entt-py（C++ 绑定增加部署复杂度）或 esper（纯 Python 但活跃度低）。自研可针对 MUD 访问模式优化，且与 WebSocket 后端深度集成，避免外部依赖风险
- 组件按领域聚合设计而非按 feature 文件 1:1 映射。核心组件：Identity(name/id/desc)、Vitals(qi/jing/jingli/max_*/eff_*)、Attributes(str/int/con/dex/kar/per)、SkillSet(skills/learned/skill_map)、CombatState(enemy/killer)、EquipmentSlots(weapon/secondary/armor)、ModifierStack(apply 临时加成)、Position(location/weight/encumbrance)、Conditions(状态效果)、Inventory(容器内容)
- 系统替代 daemon+heart_beat：CombatSystem(COMBAT_D)、HealSystem(heal_up)、ConditionSystem(update_condition)、AttributeSystem(query_str 等派生计算 + dirty 缓存标记)、SkillSystem(improve_skill/learning)、MovementSystem(move + weight 传播)、EquipmentSystem(wield/wear + apply 更新)、ActionSystem(busy/interrupt)
- 用事件总线解耦跨系统交互：EquipEvent->EquipmentSystem 更新 ModifierStack->AttributeSystem 标记 dirty；DamageEvent->VitalsSystem 扣血->ConditionSystem 检查死亡/昏迷。替代 LPC 中 feature 间直接方法调用（this_object()->reset_action() 等硬耦合）
- 技能系统保留策略对象多态：359 个技能(kungfu/skill/)作为 SKILL_D 仍用 OOP/策略模式实现(hit_ob/perform_action/exert_function)，技能是行为定义而非实体数据，不适合做成纯组件。技能实体挂载 SkillRef 组件(引用技能 ID + 等级)，SkillSystem 通过 ID 查找策略对象执行逻辑
- 用 Prefab/Archetype 系统替代 default_ob：武器/防具/NPC 的只读定义作为 DSL/JSON Prefab 资源，克隆时实例化组件副本。与 UGC 平台的'用户配置场景'需求统一——用户的 DSL 场景定义就是 Prefab，多题材（武侠/大航海/书院）即不同组件集
- 分阶段迁移：阶段 1 搭建 ECS 骨架 + Identity/Vitals/Position 核心组件 + HeartBeatSystem；阶段 2 迁移战斗(CombatSystem + CombatState + EquipmentSlots)；阶段 3 迁移技能与属性(AttributeSystem + SkillSet)；阶段 4 迁移边缘 feature(marry/team/finance 等)；保持 LPC 兼容期用适配层桥接
