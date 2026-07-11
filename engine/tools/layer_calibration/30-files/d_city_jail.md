# d_city_jail 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/d/city/jail.c
- basename: d_city_jail
- 总语义单元数: 6
- 各层计数: 层0=6  层1=0  层2=0  层3=0
- 层3 项: 无

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set("short","监狱") | 层0 | 纯数据声明 |
| create() set("long", @LONG@) | 层0 | 纯数据声明 |
| create() set("exits", mapping) | 层0 | 纯数据声明，east 出口 |
| create() set("objects", mapping) | 层0 | 纯数据声明，NPC 丁典 x1 |
| create() create_door("east","铁门","west",DOOR_CLOSED) | 层0 | 门声明：方向绑定+名称+反向方向+初始状态，纯数据 |
| create() set("cost",0) + replace_program(ROOM) | 层0 | 纯数据声明；replace_program(ROOM) 表示无自定义事件钩子 |

## 备注

- `replace_program(ROOM)` 强信号：无自定义事件钩子，整个文件完全层0。
- 注意文件名 jail.c 但 short="监狱"，与同目录 bingqiku.c (short="兵器库") 通过 bingyin 中转。丁典是 NPC 对象引用，其行为逻辑不在本文件。
