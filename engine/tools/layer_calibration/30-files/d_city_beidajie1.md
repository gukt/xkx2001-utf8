# d_city_beidajie1 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/d/city/beidajie1.c
- basename: d_city_beidajie1
- 总语义单元数: 5
- 各层计数: 层0=5  层1=0  层2=0  层3=0
- 层3 项: 无

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set("short","北集市") | 层0 | 纯数据声明 |
| create() set("long", @LONG@) | 层0 | 纯数据声明 |
| create() set("exits", mapping) | 层0 | 纯数据声明，5 方向出口 |
| create() set("objects", mapping) | 层0 | 纯数据声明，NPC 巡捕 x1 |
| create() set("outdoors","city") + set("cost",1) + replace_program(ROOM) | 层0 | 纯数据声明；replace_program(ROOM) 表示无自定义事件钩子，全部语义由基类 ROOM 承载 |

## 备注

- `replace_program(ROOM)` 是 LPC 的强信号：该房间无自定义 init/valid_leave/accept_object 等事件钩子，所有行为来自基类 ROOM 的默认实现。整个文件完全层0。
