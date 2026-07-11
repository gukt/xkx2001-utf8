# clone_misc_corpse 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/clone/misc/corpse.c
- basename: clone_misc_corpse
- 总语义单元数: 6
- 各层计数: 层0=4  层1=0  层2=0  层3=2
- 层3 项: 2 项（create call_out decay 启动 / decay 状态机）

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set_name("无名尸体",({"corpse"})) + set("long",...) + set("unit","具") + decayed=0 | 层0 | 纯数据声明，物品身份与描述 |
| create() clonep 时 call_out("decay",1,0) | 层3 | call_out 闭包启动腐烂状态机，触发 phase=0 的 decay，进入状态机循环 |
| is_corpse()/is_character()/is_container() 谓词 | 层0 | is_container() return 1 是纯声明；is_corpse() return decayed<2 / is_character() return decayed<1 是基于 decayed 状态的谓词，但属"状态查询"非"状态变更"，可视为层0 数据派生属性 |
| short() 覆写 return name()+"("+capitalize(query("id"))+")" | 层0 | 公式化 short 拼接，依赖运行时 name()/query("id")，属数据声明范畴（与基类 short 公式一致，仅覆写格式） |
| decay(phase) 4 阶段腐烂状态机 | 层3 | call_out 闭包链（0->1 120s / 1->2 60s / 2->3 60s）+ switch fallthrough 改名（男尸/女尸/默认，LPC switch 缺 break）+ message_vision 副作用 + delete/set food + set_weight(weight/5) + 改 long + phase 3 for 循环遍历 all_inventory move 非 no_drop 物品到 environment + destruct(this_object)，图灵完备状态机 |
| inherit ITEM + inherit F_FOOD | 层0 | 继承声明，尸体同时是物品和食物（腐烂前可被吃），纯声明 |

## 备注

- 尸体是死亡系统的核心物品，4 阶段腐烂状态机（fresh -> rotting -> skeleton -> ash）是典型的 call_out 驱动时间状态机：每个阶段定时触发下一阶段，期间动态改名/改重/改描述/改食物属性，最终 phase 3 将 inventory 物品掉落到环境并自我销毁。整套逻辑无法用层1 谓词（condition->action 是事件触发的无状态规则）或层2 对话树表达，必须层3。
- is_corpse()/is_character() 的返回值依赖 decayed 状态（decayed<2 / decayed<1），本质是状态查询谓词。这里归层0 的理由：它们是"只读派生属性"（查询当前状态，不改变状态），与 set() 声明的数据属性同属数据范畴。若新引擎将其实现为运行时计算的 property，仍属层0。但注意：decayed 本身由 decay() 状态机驱动变更，decayed 的变更逻辑属层3。
- LPC switch 缺少 break 的 fallthrough 语义（phase 1 的 switch(gender) 中"男性"case 会 fallthrough 到"女性"再 fallthrough 到 default）是转译陷阱：实际效果是无论 gender 为何都执行 default 分支的"腐烂的尸体"。新引擎层3 实现时需注意此 fallthrough 行为，或按实际效果直接映射到 default 分支。
- F_FOOD 继承使尸体在腐烂前（decayed<2，is_corpse 为真且 food_remaining 已设）可被食用（food_remaining=4, food_supply=weight/1000, food_race=野兽），这是死亡系统的黑色幽默设计。
