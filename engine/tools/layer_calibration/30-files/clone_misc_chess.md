# clone_misc_chess 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/clone/misc/chess.c
- basename: clone_misc_chess
- 总语义单元数: 15
- 各层计数: 层0=5  层1=1  层2=0  层3=9
- 层3 项: 9 项（do_move / do_toss / do_draw / do_lose / do_save+do_deploy+do_reset 合并 / do_review / long 渲染 / do_check / init_tab）

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set_name("象棋棋盘",...) + set_weight(3000000) + set_max_encumbrance(0) | 层0 | 纯数据声明，物品身份与重量（3000 斤不可移动） |
| create() set("unit","张") + set("long",...) + set("value",0) + set("material","wood") + set("no_get",1) + set("no_drop",1) + set("no_refresh",1) + setup() | 层0 | 纯数据声明，物品属性 |
| TABLE mapping（20 行 x 17 列棋盘初始布局，每格 4 元素 [边框,棋子,类型,阵营]） | 层0 | 纯数据声明，棋盘初始状态（车马相仕帅炮兵 + 楚河汉界），约 350 格数据 |
| tossText 数组（骰子 6 面文本 + 边框） | 层0 | 纯数据声明，骰子渲染文本 |
| query_save_file() 按 bb 标志切换存档路径（默认 cchess/cchess / 玩家 cchess/<首字符>/<id>） | 层0 | 存档路径公式，bb 标志驱动的二选一，属数据声明范畴 |
| init() init_tab() + add_action(move/toss/reset/csave/deploy/lose/draw/review) | 层1 | 事件钩子：init 触发，init_tab 初始化 + 注册 8 个命令，可用谓词+注册表达（init_tab 的 sort_array 部分边界层3，但整体归层1） |
| init_tab() table=keys(TABLE)+sort_array(table,1) | 层3 | 排序+keys 操作，运行时初始化计算（简单，但属计算非声明；边界可层0，按计算归层3） |
| do_move(arg) 核心走棋逻辑 | 层3 | sscanf 解析 "sCOL sROW to tCOL tROW" + 边界校验(9x9) + 棋子存在 + 阵营(round)校验 + 7 种棋子走法判定（车直线+路径蹩/马日字+蹩马腿/相田字+塞象眼+不过河/仕九宫斜/帅九宫直/炮直线+翻山吃子(tem3 计数)/兵直走+过河横走）+ 吃子判定 + 胜负判定(吃将 type==5) + 王见王死棋检测(tem4) + 棋谱记录(平/进/退+chinese_number+坐标转换) + TABLE 状态更新 + round 切换 + c_chess 战绩 + pending/draw_chess 清理，大量嵌套 if/for + 棋盘状态机 + 棋谱字符串构建，图灵完备 |
| do_toss() 投骰子 | 层3 | random(6) + 重复投骰防平(num 相等再 random) + tossText 渲染 + name1/name2/id1/id2 注册 + first(先行)判定 + num 记录，随机+状态机+多副作用 |
| do_draw() 和局提议 | 层3 | find_player 对手 + 多分支校验(over/局外人/步数<30/回合判定/在场) + pending/draw_chess 双方确认状态机 + message_vision + 议和成功 set over=drawn_game + 战绩更新，多分支+双方确认状态机 |
| do_lose() 认输 | 层3 | 多分支校验(局外人/已结束/无吃子 bche==""&&rche=="") + find_player 对手 + set over + 战绩更新 + message_vision |
| do_save()/do_deploy()/do_reset() 存档/部署/重置 | 层3 | do_save: bb=1+save+write；do_deploy: bb=1+在场校验+restore+setup+delete start_time；do_reset: bb=0+在场校验+new(base_name)新棋盘+move+set startroom+destruct(this_object)，状态切换+对象重建销毁 |
| do_review() 复盘 | 层3 | 时间计算 t=time()-start_time 拆解为 月/天/时/分/秒 + chinese_number 拼接时间字符串 + 棋谱 aaa 输出 + aa 步数，时间计算+字符串构建 |
| long() 棋盘渲染 | 层3 | 按 me->name 是否==first 决定正/反视角 + 双重 for 遍历 table 渲染每格(边框 vs 棋子) + 动态修改 TABLE 边框字符(翻转视角时┌<->┘/┐<->└/├<->┤/┬<->┴) + 楚河汉界状态消息拼接(轮次/胜负) + 所吃棋子列表(bche/rche)拼接，双重循环+视角翻转+动态字符串构建 |
| do_check() 将军检测 | 层3 | 定位当前方帅(type==5)位置 + 4 方向卒/兵威胁检测(tem1±2) + 4 方向车/炮威胁检测(含翻山炮 tem3 计数，扫描到第一个棋子后判断是否炮+第二个棋子) + 8 方向马威胁检测(含蹩马腿 TABLE[tem1±2][tem±2]==0 校验)，多重 for 循环+8 方向扫描+威胁判定，图灵完备棋局分析 |

## 备注

- 象棋棋盘是本批 6 个文件中最复杂的层3 实体：完整实现了中国象棋的全部规则（7 种棋子走法 + 将军检测 + 王见王 + 投骰先行 + 和局双方确认 + 认输 + 复盘 + 存档/部署残局 + 视角翻转渲染）。do_move 单函数约 400 行，do_check 约 170 行，long 约 130 行，三者均含大量嵌套 if/for 和棋盘状态操作，是典型的图灵完备游戏逻辑，无法用层1 谓词或层2 对话树表达。
- TABLE 数据本身是层0（棋盘初始布局的静态声明，约 350 格 x 4 元素），但其消费方 do_move/do_check/long 全是层3。数据层0 + 消费行为层3。
- 棋谱记录使用中国象棋传统记法：平(横走)/进(向前)/退(向后) + chinese_number(列号)。红方用 10-(COL/2+1)（一二三...九），蓝方用 COL/2+1，体现红蓝双方视角差异。
- 将军检测（do_check）的翻山炮逻辑较精巧：扫描方向上遇到第一个棋子(tem3 从 0->1)，若第二个棋子是炮(type==6)且非己方则 check=1；若第一个棋子是车(type==1)且非己方则 check=1。这是中国象棋"炮翻山吃子"规则的逆运用（检测威胁而非实际吃子）。
- 存档路径按 bb 标志切换：bb=0 时存到 cchess/cchess（公共默认局），bb=1 时存到 cchess/<玩家 id 首字符>/<玩家 id>（玩家个人残局）。do_save/do_deploy 时设 bb=1，do_reset 时设 bb=0。
- 视角翻转（long 的 if me->name != first 分支）会动态修改 TABLE 的边框字符：正视角 ┌┐┖┚ / 反视角 ┘└┐┌，├<->┤，┬<->┴。这是为了让两位玩家从各自视角看到正确的棋盘方向。
- init_tab() 的 sort_array 是简单的运行时计算，边界可归层0（只是对 keys 排序）；但严格按"计算非声明"归层3。转译中将 init 整体归层1（命令注册是主体），init_tab 的计算部分在备注中说明。
