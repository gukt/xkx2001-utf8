# cmds_std_kill 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/cmds/std/kill.c
- basename: cmds_std_kill
- 总语义单元数: 4
- 各层计数: 层0=1  层1=1  层2=0  层3=2
- 引擎侧/内容侧: 引擎侧
- 层3 项: 有（2 项）

## 语义单元标注

| 语义单元 | 层 | 引擎侧/内容侧 | 理由 |
|---|---|---|---|
| help() 帮助文本 | 层0 | 引擎侧 | 纯文本声明，无逻辑 |
| main() 前置 deny 检查组（no_fight/immortal/投降保护/自身投降/骑马/侠客岛/PKer 内疚） | 层1 | 引擎侧 | 7 条 deny 规则可用 has_flag/family_eq/attr_lt 等现有谓词组合表达，是命令的权限/条件检查部分 |
| main() 战斗启动副作用（kill_ob/accept_kill/fight_ob/pking 标记/initiate_pk 追加） | 层3 | 引擎侧 | 通过检查后的启动链：present 查找、RANK_D 称呼、message_vision 喝道文本、kill_ob 启动追杀、NPC 分支 accept_kill+kill_ob、玩家分支 pking temp+fight_ob+initiate_pk 数组追加+tell_object 警告，对象状态写入与敌人列表操作交织，无法纯谓词表达 |
| create()（隐式 inherit F_CLEAN_UP） | 层3 | 引擎侧 | LPC 命令对象基类继承，引擎侧命令管线基础设施 |

## 备注

- kill 命令是命令管线末端命令对象（layer_c_command.py COMMAND_OBJECTS KILL_CMD=/cmds/std/kill），属引擎侧。
- kill 是本批中层1 谓词化比例较高的命令：7 条前置 deny 检查均可表达为层1 规则，体现了"命令的权限/条件检查"维度适合层1。但最终战斗启动副作用必须层3。
- 层1 规则中部分 condition 用了未在现有谓词集中的判断（如 path 前缀匹配、condition.pker 阈值、mud_age 阈值），这些是层1 谓词集的扩展候选点，校准时如实标注为层1 但需扩展谓词。
- kill_ob/kill_ob 启动追杀后，实际战斗回合由 CombatSystem（combatd.c -> ECS System，ADR-0014）的 do_attack 七步管线处理，不在本命令文件内。
- SECURITY_D->get_status 检查 immortal 属权限校验，可由层1 family_eq 谓词（扩展为 status_eq）表达。
