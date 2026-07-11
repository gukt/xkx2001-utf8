# d_xueshan_shanmen 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/d/xueshan/shanmen.c
- basename: d_xueshan_shanmen
- 总语义单元数: 7
- 各层计数: 层0=6  层1=1  层2=0  层3=0
- 层3 项: 无

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set("short","山门") | 层0 | 纯数据声明 |
| create() set("long", @LONG@) | 层0 | 纯数据声明 |
| create() set("exits", mapping) | 层0 | 纯数据声明，eastdown/north 出口 |
| create() set("item_desc", gate) | 层0 | 纯数据声明，gate 描述 |
| create() set("objects", mapping) | 层0 | 纯数据声明，葛伦布 x2 + 香客 x1 |
| create() set("outdoors","qilian-shan")+set("no_clean_up",1)+set("cost",1)+setup() | 层0 | 纯数据声明；无 replace_program 但也无其他自定义钩子（仅 valid_leave） |
| valid_leave(me, dir) dir==north 分支 | 层1 | condition->deny 形态：present_npc("ge lunbu") AND NOT(family 雪山派 OR family 血刀门 OR has_item 酥油供 OR has_flag marks/酥) -> deny。可用现有谓词集（present_npc/family_eq/has_item/has_flag + all/any/not）完整表达。对照 zhongnan/gate.c valid_leave 同构。副作用（clear_temp mark/comin、set_temp marks/酥=0）属层1 action 的 flag set/clear |

## 备注

- 本文件是层1 谓词集的典型可表达案例：present_npc + family_eq + has_item + has_flag 的组合，与已转译的 zhongnan/gate.c::valid_leave 结构一致。
- 副作用时序细节：valid_leave 进入 north 分支时先无条件 `delete_temp("mark/comin")`（清来自 guangchang 的进山标记），再判断供品；若通过（已有 marks/酥 标记或满足任一豁免）则 `set_temp("marks/酥",0)` 重置。这两步是规则 action 的 flag 副作用，层1 可承载，但需确认层1 规则引擎支持"无条件 on_enter 副作用"与"通过后 on_pass 副作用"两个钩子相位。
- `present("ge lunbu", environment(me))` 用 npc id 而非文件路径，转译时 npc_id 取 "ge lunbu"。
- 其他方向走 `::valid_leave`（基类默认），无自定义规则。
