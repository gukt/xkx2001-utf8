# d_zhongnan_gate 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/d/zhongnan/gate.c
- basename: d_zhongnan_gate
- 总语义单元数: 13
- 各层计数: 层0=7  层1=2  层2=0  层3=4
- 层3 项: 有（4 项，见下表）

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set("short", HIR"重阳宫大门"NOR) | 层0 | 纯数据声明（ANSI 颜色标记属渲染层） |
| create() set("long", @LONG@) | 层0 | 纯数据声明 |
| create() set("exits", mapping) | 层0 | 纯数据声明，southdown 出口；north 出口由层3 门状态机动态管理 |
| create() set("outdoors","shaolin") | 层0 | 纯数据声明 |
| create() set("item_desc", "door":(: look_door :)) | 层0 | 纯数据声明，item_desc 的 look_door 回调返回静态文本，可内联为数据 |
| create() set("objects", mapping) | 层0 | 纯数据声明，全真教丘道长 NPC x1 |
| create() set("cost",1) + setup() + 无 replace_program | 层0 | 纯数据声明；未 replace_program 表示有自定义钩子 |
| valid_leave: dir==north 的门派/持香检查 | 层1 | 3 条规则：deny(非全真且无香) / allow(全真教) / allow(持香非全真)，family_eq + has_item + not/any/all |
| init() add_action("do_knock","knock") | 层3 | 动态注册自定义命令 knock，层1 谓词集无 add_action 维度，需层3 |
| do_knock() 门状态机开门 | 层3 | knock door 动态添加 exits/north + 跨房间设 gate1 exits/south + call_out(close_door,10) 延时回调闭包。跨房间双向 exits 同步 + 延时状态机 |
| close_door() 门状态机关门 | 层3 | 删除本房 exits/north + 跨房间删 gate1 exits/south + 按 NPC 在场选不同消息。跨房间状态操作 + 条件消息 |
| look_door() item_desc 回调 | 层0 | 返回静态文本，已内联到 item_desc.door，不独立成层3 |
| NATURE_D->outdoor_room_event() 调用 | 层3 | do_knock 中调用外部 daemon NATURE_D，赋值后未参与分支，但外部 daemon 依赖标层3备查 |

## 层3 项详情

### 1. init() add_action("do_knock","knock")
- 理由：层1 谓词集（always/attr_lt/age_lt/present_npc/has_flag/family_eq/has_item + all/any/not）只覆盖 valid_leave 等"条件->deny/allow"事件钩子，无 add_action 命令注册维度。knock 是自定义命令动词，需层3 注册命令处理器。

### 2. do_knock() 门状态机开门
- 理由：图灵完备逻辑。流程：
  1. 检查门是否已开（query("exits/north")）
  2. find_object/load_object 跨房间获取 gate1
  3. 本房间 set("exits/north", gate1)
  4. 跨房间 room->set("exits/south", __FILE__)
  5. 双房间发不同消息
  6. call_out("close_door", 10) 延时回调闭包
- 无法降层：跨房间 exits 双向同步 + call_out 延时闭包，超出层0-2 表达力。

### 3. close_door() 门状态机关门
- 理由：与 do_knock 对称的关门外加跨房间状态操作。删除双向 exits + 按 present("姬清虚") 选择不同关门 NPC 消息文本。

### 4. NATURE_D->outdoor_room_event() 调用
- 理由：外部 daemon 依赖。虽然本文件中 `event` 变量赋值后未参与任何分支（疑似遗留代码），但 NATURE_D 调用本身属外部状态查询，标层3 备查。若确认死代码可删除则此项消失。

## 层1 规则与 LPC 对照

对应 LPC `valid_leave(me, dir)` 第 95-122 行：
```c
if (dir != "north") return ::valid_leave(me, dir);  // 非 north 方向放行，基类处理
if (!::valid_leave(me, dir)) return 0;               // 基类 deny 则 deny
if (family == "全真教") { write("道兄辛苦了"); return 1; }  // 全真教 allow
else if (has_item("incense")) { write("贵客驾到"); return 1; }  // 持香 allow
else { return notify_fail("如果不是进香，请回吧"); }  // 其余 deny
```
转译为 3 条层1 规则（deny + 2 个 allow），deny-wins + priority 编码顺序。与 `engine/scenes/zhongnan_micro/rules.yaml` 的 v1 转译一致（该版只写了 deny 规则，本版补充 2 条 allow 规则带消息）。

## 备注

- 本文件是"门状态机"表达力缺口的典型用例，已有 `zhongnan_micro/rules.yaml` 注明"门状态机无法表达，近似门常开，缺口见 ADR-0004"。
- valid_leave 部分可完整层1化（与 zhongnan_micro 参考一致），门状态机部分（do_knock/close_door/init add_action）必须层3。
- look_door 虽是函数，但返回纯静态文本，内联到 item_desc 数据后属层0，不独立成层3。
