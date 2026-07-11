# d_bwdh_kantai 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/d/bwdh/kantai.c
- basename: d_bwdh_kantai
- 总语义单元数: 12
- 各层计数: 层0=4  层1=1  层2=0  层3=7
- 层3 项: 有（7 项，见下）

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set("short","看台") | 层0 | 纯数据声明 |
| create() set("long", (: long_desc :)) + set("valid_startroom",1) | 层0 | long 注册为动态函数（内容见 long_desc 层3）；valid_startroom 纯数据 |
| create() set("no_fight",1)+set("no_practice",1) | 层0 | 纯数据声明 |
| create() set("exits",up+out)+set("objects",xiaolongnu)+setup() | 层0 | 纯数据声明，up/out 出口 + 小龙女 x1 |
| long_desc() | 层3 | themed 赛事平台代码：动态 long，含 ASCII 擂台图 + query("age") 条件文案 + nRank for 循环构造排行榜（query rank/i/name/id/win/loss + strlen 对齐填充）+ 12 行空行填充。循环+字符串构造，层3 |
| init() | 层3 | themed 赛事平台代码：bwdh/fighting 玩家进场归道具（all_inventory 遍历 destruct）+cangku 仓库道具归还（find_object/load_object + basket 数组遍历 move + delete basket/id）+restore+清 bwdh/admitted|fighting|once+add_action(practice/study/报名/放弃/start/stop)。环境遍历+跨房间对象操作+多状态清理+命令注册，层3 |
| valid_leave(me,dir) dir==up | 层1 | condition->deny 形态：NOT(is_wizard OR has_flag temp/organizer) -> deny。可用 is_wizard+has_flag 组合表达。organizer 是 themed 赛事状态标记，但谓词形态可层1 |
| valid_leave(me,dir) dir==out | 层1 | condition->deny 形态：NOT(is_wizard) AND has_flag(temp/admitted) -> deny。可用 is_wizard+has_flag 组合表达。admitted 是 themed 赛事状态标记，但谓词形态可层1 |
| sort_rank(ob,n) | 层3 | themed 赛事平台代码：排行榜插入排序，for 循环查找已有 id+未找到则 nRank++ 追加+向前比较 win 数冒泡交换（set rank/i 多字段）。循环+多字段状态机，层3 |
| do_start(arg) + do_stop(arg) | 层3 | themed 赛事平台代码：wizard 发动/终止比武大会，sscanf age+set age/start+find_player host/challenger+move KANTAI+清 bwdh 状态+message_vision。赛事生命周期管理+call_out，层3 |
| do_baoming() | 层3 | themed 赛事平台代码：报名，call_out("auto_check",0)+age 超龄/已报名/连输三场校验+首报设 host+call_out("let")+排队 set boy/time+挑战者设 challenger+call_out("start",25/30)。多分支状态机+call_out 闭包，层3 |
| start(host,challenger) + auto_check() + let(arg) + full_all(me) | 层3 | themed 赛事核心状态机：auto_check 自调度 call_out（30s/20s/1s 多档）+存活判定+败者 move+sort_rank+胜者 full_all+连胜下场+boy 队列消费+no_challenger 计数+断线兜底（new USER_OB+restore）；let 上台道具保管+move LEITAI；full_all 全属性重置。call_out 闭包+跨房间 move+全属性重置+插入排序，层3 |

## 备注

- 本房间是架构明确的 themed 治理系统（武林大会赛事）的核心场所，按架构 themed 治理是平台级 fail-closed Python System，不进 UGC 层1。赛事状态机（auto_check/sort_rank/do_baoming/start/let/full_all）均标层3，理由注明"themed 赛事平台代码"。
- valid_leave 的两个分支（up/out）形态可层1（is_wizard + has_flag 组合），保留层1 表达。但 organizer/admitted 标记由层3 赛事状态机维护，层1 规则依赖层3 平台代码先设置这些 flag。这是 themed 系统中"UGC 可读不可写"的边界：UGCi 可声明"选手不得离开"规则，但"谁是选手"由平台代码决定。
- long_desc() 是动态 long，含 ASCII 艺术图 + 排行榜循环构造，无法层0 静态表达，标层3。YAML 中 long: null 占位，实际由层3 生成。
- auto_check() 是本批最复杂的层3 项：call_out 自调度 + 多档延时（1s/20s/30s）+ 双方存活判定 + boy 队列消费 + no_challenger 计数 + 断线兜底（new USER_OB + restore），是典型的图灵完备状态机，必须层3。
- do_practice/do_study 在 init 中注册但本文件未定义实现（可能继承自 ROOM 或其他 include），转译时不单独标注。
