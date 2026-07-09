# 现状分析·世界构建系统(World Building System)：ROOM基类、房间/区域/出口模型、reset机制、虚拟对象、地图连接、门与cost

## 概述
XKX世界由6414个手写LPC房间构成，分布在/d/下33个区域目录。房间继承/inherit/room/room.c(F_DBASE+F_CLEAN_UP)，用键值dbase存储short/long/exits/objects/item_desc/outdoors/cost等属性。无正式Region对象，区域仅是/d/<region>/路径命名空间(REGIONS.h仅做中文名映射)。出口是dir→绝对路径的映射，跨区域用绝对路径硬编码。reset()每1800秒由MudOS驱动调用，依据"objects"声明清单重刷NPC/物品。门为静态mapping+双面协调(DOOR_CLOSED/LOCKED状态位)。virtuald.c是恒返回0的空壳——没有任何真正虚拟对象生成，所有房间必须手写。cost为移动精力消耗。世界状态全内存单进程，无持久化与分片能力。

## 现有模式
- **ROOM基类+dbase属性模型**：ROOM基类(inherit/room/room.c)继承F_DBASE+F_CLEAN_UP，用set/query键值对存储short/long/exits/objects/item_desc/outdoors/indoors/cost/no_fight/no_clean_up等属性。dbase支持'/'分层路径与default_ob(蓝图)回退继承
- **房间生命周期 create→setup→reset**：房间create()设置静态属性→setup()(seteuid+调用reset())。MudOS驱动每1800秒(config.xkx 'time to reset:1800')调用reset()，clean_up()在空闲对象上由驱动触发(无交互用户则destruct)
- **出口=exits映射(dir→绝对路径)**：exits为mapping(dir字符串→目标房间绝对路径)。同区域用__DIR__宏，跨区域用绝对路径(如city/beimen的north指向/d/village/hsroad1)。go.c命令解析方向并load_object(dest)移动
- **reset声明式刷新机制**：reset()依据query('objects')映射(文件名→数量)与query_temp('objects')(已生成实例数组)对比：销毁不在清单的非角色对象，重生缺失对象(make_inventory:new+move+set startroom)，召唤漫游NPC回家(return_home)，累加no_clean_up计数
- **门=静态mapping+双面协调**：create_door(dir,name,other_side_dir,status)在房间上建静态mapping。状态位DOOR_CLOSED=1/LOCKED=2/SMASHED=4。双面门通过find_object(exits[dir])+open_door(other_side_dir,1)协调。valid_leave()校验关闭的门
- **cost移动精力消耗**：set('cost',N)表示地形移动消耗。go.c中me->add('jingli',-env->query('cost')*2)。cost>rided->query('ability')则骑乘无法通过，模拟地形难度(山路/沙漠)
- **区域=路径命名空间**：无正式Region对象。/d/REGIONS.h仅定义region_names(中文名映射)，区域=目录路径。区域归属靠explode(file,'/')[1]推断+outdoors/indoors属性标签。跨区域连接即绝对路径出口
- **虚拟对象系统=空壳**：virtuald.c的compile_object()恒返回0，master.c虽委托但无任何虚拟生成逻辑。所有6414个房间必须手写.c文件，无程序化生成
- **运行时出口动态重定向**：房间valid_leave()可设me->set_temp('new_valid_dest',路径)，go.c据此覆盖exit目标，实现沙漠/暗道/冰面等方向重定向。部分迷宫(bamboo3)在create()用random()随机化出口目标
- **特殊房间子类**：ROOM子类化覆盖init()/reset()/valid_leave()：ship.c(航海+天气+导航状态机)、harbor.c(yell召唤船)、ferry.c、bank.c、hockshop.c、pigroom.c(拱猪小游戏)、以及区域级no_pk_room.c变体
- **unique单例+replica机制**：feature/unique.c：violate_unique()检查克隆实例数>1则自毁，create_replica()生成替代品。用于唯一NPC/物品的全局单例约束

## 痛点
- 6414个房间全部手写.c文件，无数据驱动，UGC完全不可行——用户无法创作世界
- virtuald.c是返回0的空壳，未实现任何虚拟对象生成，浪费了LPC程序化生成房间的能力
- 区域无元数据对象，仅靠目录路径约定，无法承载天气/势力/分片/刷新策略等区域级逻辑
- exits硬编码绝对路径，房间重命名/迁移/重构会破坏大量引用，重构成本极高
- reset()每1800秒全量扫描所有已加载房间的inventory，无法水平扩展或分片调度，分布式部署下会成为瓶颈
- 单进程MudOS，房间状态全内存，无持久化与跨节点迁移能力，无法支撑高并发
- 双面门状态分散在两个房间的静态mapping中，靠运行时find_object协调，一侧未加载即静默失败，易不一致
- GBK编码(文件实为ISO-8859/GBK)+LPC强耦合，难以被现代工具链/编辑器/AI处理
- go.c中移动、战斗、骑乘、阻挡、cost、valid_leave高度交织，扩展移动语义风险大
- 迷宫房间random()仅作用于create()加载时，非每次进入重随机，行为难以预测且不可复现
- 无区域/世界版本概念，UGC世界无法版本管理与回滚

## 应保留思想
- dbase键值属性模型：可演进为房间组件/属性系统(Property Bag)，声明式、可组合，契合UGC
- exits+cost+门 模型简洁有效：dir→目标+地形消耗+状态门，可直接映射为图模型的边(edge)与边属性，支撑寻路与DSL
- reset的'声明式对象清单+系统收敛到期望状态'思想(objects映射即desired state)，是优秀的不可变基础设施模式，值得保留为'reconcile'语义
- valid_leave钩子：房间级离开校验是天然的UGC剧情触发点(门派规矩/任务门禁/场景条件)，应保留为事件钩子
- 特殊房间子类化思路(ship/harbor等)：可演进为可插拔的房间Behavior组件，而非继承链
- unique单例+replica：分布式下唯一性约束与副本替代的思想，对稀有世界资源的全局单例有借鉴价值
- new_valid_dest运行时重定向：方向→动态目标的解耦思想，可用于动态世界事件(传送/迷路/天气封路)
- outdoors/indoors+cost的地形建模：简洁的物理环境抽象，值得保留为环境属性

## 应废弃设计
- 路径=ID的硬编码命名约定(改UUID/数据驱动标识，房间可在区域间迁移而不破坏引用)
- 运行时find_object双面门协调(改集中式门状态服务或图模型边属性)
- 每房间手写create()函数体(改为DSL/数据声明，UGC核心)
- region=目录路径的隐式约定(改正式Region实体，承载元数据/天气/势力/分片策略)
- reset全量扫描所有房间对象(改为分片/按需/事件驱动刷新)
- LPC继承强耦合房间类型(房类型改为可组合Behavior组件，非继承链)
- go.c中移动语义与战斗/骑乘/阻挡硬交织(解耦为可插拔移动管线)
- 单进程内存内房间状态(改可序列化、可迁移、可持久化的房间状态)

## 复杂度热点
- /inherit/room/room.c reset()：交叉引用 make_inventory+return_home+no_clean_up 计数+objects 映射双重比对，逻辑纠缠且对 NPC 漫游状态敏感
- /cmds/std/go.c：valid_leave+new_valid_dest+exit_blockers+riding+cost+战斗逃跑 在单函数内交织，是移动语义的核心耦合点
- 双面门状态分散协调：open_door/close_door 通过 find_object(exits[dir]) 跨房间同步 status 位，任一侧未加载即静默失败，易不一致
- /inherit/room/ship.c 与 harbor.c：移动房间+天气状态机+导航 call_out+yell 召唤，构成独立的小型状态机子系统
- bamboo/wuxing 迷宫：create() 内 random() 设出口（仅加载时随机，非每次进入），与 reset 语义交互模糊，难以预测刷新行为
- dbase 的 default_ob 继承回退链：query() 先查自身再回退 master copy，克隆与蓝图属性混淆，调试困难

## 关键文件
- /home/gukt/github/xkx2001-utf8/inherit/room/room.c
- /home/gukt/github/xkx2001-utf8/feature/dbase.c
- /home/gukt/github/xkx2001-utf8/feature/clean_up.c
- /home/gukt/github/xkx2001-utf8/feature/unique.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/virtuald.c
- /home/gukt/github/xkx2001-utf8/adm/single/master.c
- /home/gukt/github/xkx2001-utf8/d/REGIONS.h
- /home/gukt/github/xkx2001-utf8/cmds/std/go.c
- /home/gukt/github/xkx2001-utf8/include/room.h
- /home/gukt/github/xkx2001-utf8/include/globals.h
- /home/gukt/github/xkx2001-utf8/inherit/room/ship.c
- /home/gukt/github/xkx2001-utf8/inherit/room/harbor.c
- /home/gukt/github/xkx2001-utf8/config.xkx
- /home/gukt/github/xkx2001-utf8/d/shaolin/shanmen.c
- /home/gukt/github/xkx2001-utf8/d/city/beimen.c
- /home/gukt/github/xkx2001-utf8/d/xiakedao/gate.c
- /home/gukt/github/xkx2001-utf8/d/xiakedao/no_pk_room.c
- /home/gukt/github/xkx2001-utf8/d/shaolin/bamboo3.c
- /home/gukt/github/xkx2001-utf8/d/xingxiu/shamo.h
