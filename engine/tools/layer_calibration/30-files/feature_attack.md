# feature_attack 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/feature/attack.c
- basename: feature_attack
- 引擎侧/内容侧: 引擎侧（攻击特性，do_attack 七步的敌人管理+触发入口）
- 总语义单元数: 14
- 各层计数: 层0=2  层1=0  层2=0  层3=12
- 层3 项: 12 项（见下表理由）

## 语义单元标注

| 语义单元 | 层 | 引擎侧/内容侧 | 理由 |
|---|---|---|---|
| MAX_OPPONENT=4 常量 | 层0 | 引擎侧 | 纯数据声明，同时攻击目标上限 |
| S_COMBAT_D 路径常量 + enemy/killer 数组初始值 | 层0 | 引擎侧 | 纯数据声明，阵法 daemon 路径 + 数组初始值 |
| query_enemy() / query_killer() | 层3 | 引擎侧 | 运行时状态查询接口 |
| is_fighting(ob) / is_killing(id) | 层3 | 引擎侧 | varargs + member_array 查找，过程逻辑 |
| fight_ob(ob) | 层3 | 引擎侧 | ob 有效性+set_heart_beat(1)+去重+enemy+=ob，启动 tick=1s 心跳（架构不变量） |
| kill_ob(ob) | 层3 | 引擎侧 | no_fight 守卫+killer 去重+tell_object 通知+fight_ob，多步副作用交织 |
| clean_up_enemy() | 层3 | 引擎侧 | 遍历+三重条件清理+enemy-=({0})，killing 关系敌人即使非 living 也不清除 |
| select_opponent() | 层3 | 引擎侧 | random(MAX_OPPONENT)+边界回退 enemy[0]，combat 范围随机性（需 seeded RNG） |
| remove_enemy/remove_killer/remove_all_enemy/remove_all_killer（4 函数） | 层3 | 引擎侧 | is_killing 守卫+数组操作+双向解除，过程逻辑 |
| reset_action() | 层3 | 引擎侧 | weapon/prepare/unarmed 三分支确定 type+mapped skill 分支（functionp actions）+set，多分支过程逻辑 |
| special_attack(opponent) | 层3 | 引擎侧 | stand/anubis temp 检查+S_COMBAT_D->fight，阵法合击入口（后置） |
| attack() | 层3 | 引擎侧 | heart_beat 步骤 5 入口：clean_up_enemy+select_opponent+last_opponent+yield 守卫+COMBAT_D->fight，多步副作用交织 |
| init() auto_fight 三触发 | 层3 | 引擎侧 | 六重前置守卫+hatred>vendetta>aggressive 三触发优先级+COMBAT_D->auto_fight，多分支过程逻辑 |

## 备注

- attack.c 的 do_attack 七步核心管线实际定义在 adm/daemons/combatd.c（见 layer_e_combat.py 规格），本文件只含敌人管理+触发入口。
- 架构不变量：fight_ob/kill_ob 中的 set_heart_beat(1) 是 tick=1s 驱动核心，不得引入 50ms/20Hz 框架。
- select_opponent 的 random(MAX_OPPONENT) 属 combat 范围随机性，层 E 实现时需要 seeded RNG。
- init() 的 auto_fight 三触发（hatred/vendetta/aggressive）经 COMBAT_D->auto_fight -> call_out("start_"+type, 0) 延迟执行，给受害者溜走机会（已有规格见 layer_g_npc_ai.py）。
- kill_ob 在 no_fight 房间直接返回（不追杀），这是房间级安全约束。
- special_attack（s_combatd 阵法合击）后置，但调用点在此记录。
- 新引擎预期：演变为 ECS System 中的 CombatSystem / EnemyManagementSystem / AutoFightTriggerSystem，Python 原生实现，语义上属层3。
- 注意：本文件不含 do_attack 本体（在 combatd.c），do_attack 七步副作用交织不可分离是架构不变量（见 layer_e_combat.py 的 49 个 SideEffect）。
