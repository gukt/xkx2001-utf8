# cmds_std_ask 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/cmds/std/ask.c
- basename: cmds_std_ask
- 总语义单元数: 5
- 各层计数: 层0=3  层1=1  层2=1  层3=2
- 引擎侧/内容侧: 引擎侧（msg 常量与 inquiry 分发表可由内容侧扩展，但 ask 命令调度本身是引擎侧）
- 层3 项: 有（2 项）

## 语义单元标注

| 语义单元 | 层 | 引擎侧/内容侧 | 理由 |
|---|---|---|---|
| help() 帮助文本 | 层0 | 引擎侧 | 纯文本声明 |
| msg_dunno 数组（5 条未知回复） | 层0 | 内容侧可扩展 | 纯数据声明，随机回复池，UGC 可扩展 |
| msg_foreign 数组（3 条外国话回复） | 层0 | 内容侧可扩展 | 纯数据声明，随机回复池 |
| main() 前置检查（ob==me 自问禁止） | 层1 | 引擎侧 | 可用 attr_lt 谓词表达 deny 规则 |
| main() 对话分发（inquiry/name/here/unknown 分支） | 层2 | 内容侧可扩展 | 对话树节点：condition(topic/attitude) -> response，inquiry 映射是典型对话树叶子，name 分支按 attitude 子分支是对话树中间节点 |
| main() 对话调度主逻辑（sscanf/present/parse_inquiry/字节检查/seteuid） | 层3 | 引擎侧 | sscanf 解析 "X about Y"、present 查找 NPC、is_character/can_speak 检查、INQUIRY_D 委托、topic[0]<128 字节级外国话判定、seteuid 特权提升、switch+random+EMOTE_D 副作用交织，调度整体属层3 |
| seteuid(getuid()) | 层3 | 引擎侧 | LPC 命令特权提升，引擎侧平台代码 |

## 备注

- ask 命令是命令管线末端命令对象，属引擎侧。但其对话内容（msg_dunno/msg_foreign/inquiry 映射/attitude 分支响应）是 UGC 可扩展的数据，标内容侧可扩展。
- 本文件是本批中唯一有层2 对话树成分的文件：inquiry/<topic> 查询和 attitude 分支响应天然符合对话树模型。
- 层2 表达中使用了未在现有谓词集的 has_inquiry/attr_eq/attr_in/eq/random_choice，是对话树 DSL 的扩展候选点。
- INQUIRY_D->parse_inquiry 是扩展钩子（job system 等），其内部逻辑不在本文件，属引擎侧服务调用。
- topic[0]<128 字节级检查（判定是否中文）是 LPC 字符串处理细节，Python 实现需用 Unicode ord 判断，属层3 实现细节。
- main 中"不可问自己"检查（ob==me）实际是对象引用比较，层1 用 attr_lt 近似表达，严格说需"same_object"谓词，是层1 谓词集扩展候选。
