# clone_misc_jinnang 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/clone/misc/jinnang.c
- basename: clone_misc_jinnang
- 总语义单元数: 9
- 各层计数: 层0=4  层1=0  层2=0  层3=6
- 层3 项: 6 项（set_owner / init 动态 long + add_action / do_read / do_add / do_cut / add_letter+cut_letter）

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set_name("锦囊",{"jin nang","nang"}) + set_weight(100) | 层0 | 纯数据声明，物品身份与重量 |
| create() set("unit","个") + set("material","silk") + set("no_get",1) + set("no_drop",...) + set("no_insert",1) | 层0 | 纯数据声明，物品属性（单位/材质/不可拾取/不可丢弃/不可放入） |
| query_autoload() return 1 | 层0 | 纯数据声明，玩家上线自动加载 |
| query_save_file() 按 owner_id 构造存档路径 | 层0 | 存档路径公式（DATA_DIR + "letter/" + id[0..0] + "/" + id + "_jin"），属数据声明范畴；但实际构造需运行时 query("owner_id")，边界在层0/层3 之间，按"路径公式"归层0 |
| set_owner(id) set("owner_id",id) + restore() | 层3 | set owner_id 是数据，但 restore() 触发存档恢复是状态驱动操作，整体属状态管理 |
| init() 动态 long 生成 + add_action | 层3 | for 循环遍历 letters mapping 数组拼接 letter_msg（第 N 封/标题/from/time）+ 按 letter_num 分支设 long（有信/无信两套模板）+ set master_id + set_owner + add_action(read/add/discard)，循环+动态字符串构建+多分支+命令注册 |
| do_read(arg) 读信 | 层3 | sscanf 解析编号 num + 边界校验（letters 存在/num 1..sizeof 范围）+ printf 格式化输出信件内容（title/to/text/from/time 五字段），多分支+格式化 I/O |
| do_add(arg) 添加信件 | 层3 | present(arg,this_player()) 查找物品 + 多分支校验（can_add_jinnang/be_read/letters 上限 9）+ query("letter") 取信件 mapping + add_letter + save + init（重新生成 long）+ destruct(ob_letter)，多分支+对象操作+状态变更+存档+对象销毁 |
| do_cut(arg) 丢弃信件 | 层3 | sscanf 解析编号 + 边界校验 + cut_letter + save + init（重新生成 long），多分支+状态变更+存档 |
| add_letter(letter)/cut_letter(letter) 辅助函数 | 层3 | letters 数组的增删操作，依赖 pointerp(letters) 判空初始化（首次时 letters=({letter})），数组操作辅助，被 do_add/do_cut 调用 |

## 备注

- 锦囊是"任务物品 + 动态内容容器"型：存放玩家的信函 mapping 数组，long 描述随信件数量和内容动态变化。init 时的 for 循环拼接 letter_msg 是典型的动态文本生成，无法用层0 静态数据或层1 谓词表达，必须层3。
- do_add 的流程（present 查找 -> 多重校验 -> query letter -> add_letter -> save -> init 重新生成 long -> destruct 原信物）是一个完整的状态变更链，涉及对象查找/校验/数据迁移/存档/副作用对象销毁，层3。
- letters 是 mapping 数组（每封信是含 title/to/text/from/time 五字段的 mapping），存储在锦囊对象的内存中，通过 F_SAVE 持久化到 DATA_DIR/letter/<id 首字符>/<id>_jin 文件。存档路径按 owner_id 分首字符目录，是 LPC 常见的哈希分目录策略。
- query_save_file() 的路径构造依赖运行时 query("owner_id")，严格说需层3 才能完整实现；但按"路径公式"的语义可归层0（公式本身是静态的）。转译中标层0，实际实现时若新引擎的存档路径需运行时计算，可由引擎层统一处理。
- no_get=1 + no_drop（带消息）+ no_insert=1 三重锁定，确保锦囊是随身绑定物品，不可丢弃/转移/被放入容器。query_autoload=1 确保玩家重新上线时自动恢复。
