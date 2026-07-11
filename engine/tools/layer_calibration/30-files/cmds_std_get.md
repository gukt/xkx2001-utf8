# cmds_std_get 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/cmds/std/get.c
- basename: cmds_std_get
- 总语义单元数: 5
- 各层计数: 层0=1  层1=1  层2=0  层3=3
- 引擎侧/内容侧: 引擎侧
- 层3 项: 有（3 项）

## 语义单元标注

| 语义单元 | 层 | 引擎侧/内容侧 | 理由 |
|---|---|---|---|
| help() 帮助文本 | 层0 | 引擎侧 | 纯文本声明，无逻辑 |
| 权限/前置检查（非 wizard 搜身 living / wizard 等级不足搜身） | 层1 | 引擎侧 | 可用现有谓词 has_flag/attr_lt/present_npc 组合表达 deny 规则，是命令的权限/条件检查部分 |
| create() seteuid(getuid()) | 层3 | 引擎侧 | LPC 对象生命周期初始化 |
| main(me, arg) 拿取主逻辑 | 层3 | 引擎侧 | sscanf 解析 "X from Y" / "N item" 语法、present 查找容器、分堆 new+set_amount 双对象操作、"all" 循环 all_inventory+过滤、对象克隆与循环，无法纯谓词表达 |
| do_get(me, obj) 实际拿取 | 层3 | 引擎侧 | is_character/no_get/equipped 检查、obj->move(me)、start_busy、message_vision 按来源（地面/角色身上/容器中）分支生成文本，sprintf+三元嵌套，副作用与文本交织 |

## 备注

- get 命令是命令管线末端命令对象（layer_c_command.py COMMAND_OBJECTS GET_CMD=/cmds/std/get），属引擎侧。
- 层1 仅表达"权限/前置检查"维度（deny 规则），main 的语法解析与对象操作仍需层3。这体现层1 谓词集的边界：能表达条件 deny，不能表达对象克隆/分堆/循环。
- "no_get" 标志是物品侧（内容侧 UGC）设置的属性，但检查它的是引擎侧 get 命令，故整体仍标引擎侧。
- 分堆逻辑（new(base_name(obj)) + set_amount 双对象）是典型层3：涉及对象生命周期与状态同步，无谓词可表达。
