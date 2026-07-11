# d_shaolin_shanmen 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/d/shaolin/shanmen.c
- basename: d_shaolin_shanmen
- 总语义单元数: 11
- 各层计数: 层0=7  层1=4  层2=0  层3=0
- 层3 项: 无

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set("short","少林寺") | 层0 | 纯数据声明 |
| create() set("long", @LONG@) | 层0 | 纯数据声明 |
| create() set("exits", mapping) | 层0 | 纯数据声明，eastup/west 两方向 |
| create() set("outdoors","shaolin") | 层0 | 纯数据声明 |
| create() set("objects", mapping) | 层0 | 纯数据声明，虚通+虚明两位僧人 NPC |
| create() set("cost",1) | 层0 | 纯数据声明 |
| create() setup() + 无 replace_program(ROOM) | 层0 | setup() 初始化；未 replace_program 表示有自定义钩子 |
| valid_leave: 女性拦截（虚通优先/虚明 fallback） | 层1 | 两条规则：dir=eastup + gender=女性 + !luohan_winner + present_npc，deny-wins + priority 区分虚通/虚明 |
| valid_leave: 兵刃拦截（虚通优先/虚明 fallback） | 层1 | 两条规则：dir=eastup + !family_eq(少林派) + has_item(weapon类) + present_npc，deny-wins + priority 区分虚通/虚明 |
| RANK_D->query_respect(me) 敬称插值 | 层1 | 消息模板占位符 {respect}，渲染期由 PronounContext 解析，不独立成层 |
| valid_leave 末尾 return ::valid_leave(me,dir) | 层0 | 基类默认放行，无自定义逻辑 |

## 层1 规则与谓词集映射

### 规则1+2：女性拦截（对应 LPC 第 39-48 行）
- dir: eastup
- condition: all([attr_eq(gender,女性), not(has_flag(luohan_winner)), present_npc(xu-tong/xu-ming)])
- action: deny
- 虚通 priority=10 > 虚明 priority=9，deny-wins 表达 if/else if 优先序

### 规则3+4：兵刃拦截（对应 LPC 第 50-65 行）
- dir: eastup
- condition: all([not(family_eq(少林派)), has_item(weapon类), present_npc(xu-tong/xu-ming)])
- action: deny
- 虚通 priority=8 > 虚明 priority=7

## 谓词集缺口

- `has_item` 当前定义是"持有物品(item_id)"，本文件需要"持有武器类物品"。建议扩展为 `has_item(item_category=weapon)`，仍属层1谓词，不需层3。
- `attr_eq(属性==值)` 是 `attr_lt` 的对称补充，当前谓词集只有 `attr_lt`，建议补充 `attr_eq`。补后本文件全层1。
- `has_flag(luohan_winner)` 对应 `me->query("luohan_winner")`，是 has_flag 的标准用法。

## 备注

- 本文件是层1 谓词表达力的良好校准用例：方向绑定 + 组合谓词 + deny-wins + priority + NPC fallback 顺序，全部可表达。
- 两段拦截逻辑（女性/兵刃）各自有虚通/虚明两个 NPC 的 fallback 顺序，用 priority 数字精确编码。
