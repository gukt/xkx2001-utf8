# cmds_std_go 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/cmds/std/go.c
- basename: cmds_std_go
- 总语义单元数: 6
- 各层计数: 层0=2  层1=0  层2=0  层3=4
- 引擎侧/内容侧: 引擎侧
- 层3 项: 有（4 项）

## 语义单元标注

| 语义单元 | 层 | 引擎侧/内容侧 | 理由 |
|---|---|---|---|
| default_dirs mapping（22 方向中英文映射） | 层0 | 引擎侧 | 纯数据声明，方向名到中文的静态映射 |
| help() 帮助文本 | 层0 | 引擎侧 | 纯文本声明，无逻辑 |
| day_event() 包装 NATURE_D->outdoor_room_event() | 层3 | 引擎侧 | 运行时服务调用包装，委托 NATURE_D 查询当前时段事件 |
| create() seteuid(getuid()) | 层3 | 引擎侧 | LPC 对象生命周期初始化，设置 euid |
| main(me, arg) 移动主逻辑 | 层3 | 引擎侧 | 复杂命令处理：10+ 条件分支（超载/忙/禁移/战斗逃跑/jingli 不足/exit 查找/valid_leave 钩子/骑乘/镖车/家畜/出口阻塞/箫声拦截）+ random() 调用 + 对象状态读写与 move/follow_me 副作用交织，无法用层1谓词或层2对话树表达 |
| do_flee(me) AI 逃跑 | 层3 | 引擎侧 | 随机选方向（random(sizeof(directions))）调 main()，是战斗 AI 逃跑入口，属引擎侧平台代码 |

## 备注

- go 命令是命令管线末端命令对象（layer_c_command.py COMMAND_OBJECTS GO_CMD=/cmds/std/go），属引擎侧。
- default_dirs 的 22 项方向映射可作为层0 数据被引擎和别名系统（DIRECTION_ALIASES）共享引用。
- main() 中 valid_leave(me, arg) 是房间侧事件钩子（内容侧可覆盖），但 go 命令本身只负责调用，属引擎侧调度。
- 战斗中逃跑的 `5 + random(dex) <= random(enemy_dex)` 判定与 combat 确定性相关，但发生在移动命令而非 do_attack，按 CLAUDE.md "combat 确定性范围=combat-only" 此处不强制确定性 RNG。
