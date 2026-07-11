# d_death_gate 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/d/death/gate.c
- basename: d_death_gate
- 总语义单元数: 6
- 各层计数: 层0=4  层1=0  层2=0  层3=2
- 层3 项: 有（2 项，见下）

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set("short", HIW"鬼门关"NOR) | 层0 | 纯数据声明；ANSI 颜色转译时剥离 |
| create() set("long", 字符串拼接) | 层0 | 纯数据声明 |
| create() set("exits",north)+set("objects",wgargoyle) | 层0 | 纯数据声明，north 出口 + 石像鬼 x1 |
| create() set("no_fight",1)+set("cost",0)+setup() | 层0 | 纯数据声明；无 replace_program 但有 init 自定义钩子（层3） |
| init() | 层3 | themed 治理平台代码（阴间入口强制净化）：all_inventory 遍历 destruct 所有非 character 物品（剥夺亡魂阳间物品）+clear_condition（清状态）+清除 sanxiao/smile 临时标记+add_action(suicide)。环境遍历破坏物品+跨域状态清理，非 UGC 规则可表达，层3 |
| do_suicide(arg) | 层3 | themed 治理平台代码（阴间生死状态约束）：禁止在阴间再自杀，tell_object 提示"你还死着呢"。属阴间 themed 治理的命令覆写，层3 |

## 备注

- 本房间是架构明确的 themed 治理系统（阴间）的入口，按架构 themed 治理是平台级 fail-closed Python System，不进 UGC 层1。init() 的强制净化与 do_suicide 的生死约束均标层3，理由注明"themed 治理平台代码"。
- init() 的物品破坏逻辑（destruct 所有非 character 物品）涉及环境遍历+对象类型判断+破坏副作用，且语义上属阴间规则（亡魂不得携阳间物），不应暴露为 UGC 可编辑规则，必须平台代码实现。
- do_suicide 虽形态简单（单条 tell_object），但其语义是"覆写全局 suicide 命令在阴间的行为"，属 themed 治理的命令拦截，随 init 整体标层3。
- short 含 HIW（高亮白）ANSI，转译时剥离颜色码，仅保留文本"鬼门关"。
