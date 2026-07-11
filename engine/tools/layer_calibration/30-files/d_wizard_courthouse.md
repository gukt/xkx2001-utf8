# d_wizard_courthouse 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/d/wizard/courthouse.c
- basename: d_wizard_courthouse
- 总语义单元数: 5
- 各层计数: 层0=4  层1=0  层2=0  层3=1
- 层3 项: 有（1 项，见下）

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set("short","法院") | 层0 | 纯数据声明 |
| create() set("long", @LONG@) | 层0 | 纯数据声明 |
| create() set("no_fight",1)+set("no_sleep_room",1) | 层0 | 纯数据声明 |
| create() set("objects",judge x1)+set("cost",0)+setup() | 层0 | 纯数据声明，NPC 审判官 x1；无 replace_program 但有 test_me 方法（层3，由外部调用） |
| test_me(me) | 层3 | themed 治理平台代码（机器人审判强制传唤）：set_temp old_startroom 保存原起点+set("startroom",__FILE__) 强制改起点为法院（答错三次处刑后回这里）+set_temp last_location 记录原位置+message_vision 文案（天上掉枷锁+机械手牵走）+me->move(this_object()) 强制传送。强制改玩家 startroom+跨房间强制 move+位置记录，层3 |

## 备注

- 本房间是架构明确的 themed 治理系统（法院/机器人审判）的场所，按架构 themed 治理是平台级 fail-closed Python System，不进 UGC 层1。test_me() 标层3，理由注明"themed 治理平台代码"。
- 本文件无 init()，test_me(me) 是供外部调用的方法（由 npc/judge 审判官在判定玩家像机器人时调用）。转译时注意：test_me 不是事件钩子，是 themed 平台代码的 API 入口。
- test_me 的关键副作用是 `me->set("startroom", __FILE__)`：强制把玩家的起点改为法院，这意味着"答错三次处刑后玩家会回到法院而非原起点"。这是 themed 治理的惩罚机制，必须平台代码实现，不可暴露为 UGC 规则。
- 实际审判逻辑（三个问题、记号、处刑）在 npc/judge.c 中，本文件只提供场所 + 传唤入口。judge NPC 的行为逻辑不在本文件转译范围。
- `__FILE__` 在 LPC 中是编译期常量（当前文件路径），转译时 startroom 值取房间 id "d/wizard/courthouse"。
