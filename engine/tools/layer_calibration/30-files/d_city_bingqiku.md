# d_city_bingqiku 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/d/city/bingqiku.c
- basename: d_city_bingqiku
- 总语义单元数: 6
- 各层计数: 层0=6  层1=0  层2=0  层3=0
- 层3 项: 无

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set("short","兵器库") | 层0 | 纯数据声明 |
| create() set("long", @LONG@) | 层0 | 纯数据声明 |
| create() set("exits", mapping) | 层0 | 纯数据声明，north 出口 |
| create() set("objects", ...) | 层0 | 本文件无 objects，但 set 调用块整体属层0（此处为空） |
| create() create_door("north","铁门","south",DOOR_CLOSED) | 层0 | 门声明：方向绑定+名称+反向方向+初始状态，纯数据 |
| create() set("cost",0) + replace_program(ROOM) | 层0 | 纯数据声明；replace_program(ROOM) 表示无自定义事件钩子 |

## 备注

- `create_door(dir, name, reverse_dir, state)` 是 LPC 房间的门声明接口，4 参数全为常量数据，属层0。
- `replace_program(ROOM)` 强信号：无自定义事件钩子，整个文件完全层0。
