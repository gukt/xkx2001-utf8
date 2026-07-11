# adm_daemons_chard 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/adm/daemons/chard.c
- basename: adm_daemons_chard
- 总语义单元数: 5
- 各层计数: 层0=1  层1=0  层2=0  层3=4
- 引擎侧/内容侧: 引擎侧
- 层3 项: 有（4 项）

## 语义单元标注

| 语义单元 | 层 | 引擎侧/内容侧 | 理由 |
|---|---|---|---|
| race_daemon_map（8 种族 -> race daemon 路径映射） | 层0 | 引擎侧 | 纯数据声明，种族名到 daemon 文件路径的静态映射 |
| create() seteuid(getuid()) | 层3 | 引擎侧 | daemon 对象生命周期初始化 |
| setup_char(ob) 角色初始化 | 层3 | 引擎侧 | 属性钳位算法：race 默认值 + switch 分派 race daemon + jing/qi/jingli 初始化为 max + eff 钳位 + jiajin 默认 + 玩家内力/精力上限公式钳位 + NPC force 自动设置 + shen 默认值(玩家 0/NPC 公式) + max_encumbrance 公式 + reset_action。多公式+条件分支+userp/NPC 分支，层3 |
| make_corpse(victim, killer) 尸体生成 | 层3 | 引擎侧 | 对象生命周期操作：is_ghost 分支 + new(CORPSE_OB) 克隆 + 多属性设置 + mengzhu 查找 + was_userp 标记 + 物品循环转移(equipped worn 分支 wear())，对象克隆+循环+条件分支，层3 |
| break_relation(player) 华山派师徒解除 | 层3 | 引擎侧 | 跨对象状态写入：family 条件 + 房间/NPC 查找 + player.delete family + set title + tell_object + 风清扬 NPC delete students/set pending/save，跨对象+持久化+条件分支，层3 |

## 备注

- chard 按 ADR-0014 归属"无状态服务"（12 个之一：chard/chinesed/commandd/aliasd/inquiryd/rankd/fingerd + ...），是进程内模块。虽无状态，但 setup_char/make_corpse/break_relation 的逻辑是平台代码，属层3。
- race_daemon_map 是层0 数据，但 race daemon 本身（human.c/monster.c 等）的内容（种族基础属性公式）不在本文件，属内容侧可扩展的题材包数据。
- setup_char 是层 G（角色系统）的核心初始化函数，由 setup() 调用，已有完整规格 layer_h_daemons.py _setup_char（12 个 SideEffect）。
- make_corpse 涉及层 F（死亡轮回）的尸体生成，但定义在 chard.c 中。break_relation 同样由 die() 调用（层 F），专门处理华山派风清扬师徒解除。
- 本文件无层1/层2 成分：属性钳位是算法，尸体生成是对象生命周期操作，师徒解除是跨对象状态写入，均无法用谓词或对话树表达。
- break_relation 硬编码"华山派"/"/d/huashan/xiaofang"/"feng qingyang" 是 LPC 时代的内容耦合，greenfield 应抽象为可配置的师徒关系解除规则（仍属引擎侧平台代码，但数据驱动）。
