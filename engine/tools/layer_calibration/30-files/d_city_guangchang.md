# d_city_guangchang 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/d/city/guangchang.c
- basename: d_city_guangchang
- 总语义单元数: 16
- 各层计数: 层0=9  层1=1  层2=0  层3=6
- 层3 项: 有（6 项，见下表）

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set("short","中央广场") | 层0 | 纯数据声明 |
| create() set("long", @LONG@) | 层0 | 纯数据声明 |
| create() set("no_sleep_room",1) + set("outdoors","city") | 层0 | 纯数据声明 |
| create() set("item_desc", "dong":...) | 层0 | 纯数据声明 |
| create() set("exits", mapping) | 层0 | 纯数据声明，4 方向出口 |
| create() set("objects", mapping) | 层0 | 纯数据声明，4 NPC |
| create() set("cost",1) + setup() | 层0 | 纯数据声明 |
| create() locations 数组（49 个目标房间） | 层0 | 纯数据声明，maskman 目标候选池 |
| create() remove_call_out + call_out("determine_target",50) | 层3 | create 即启动 call_out 延时闭包，maskman 周期任务启动点 |
| init() 红镖扒手随机事件 | 层3 | interactive 玩家进入触发，嵌套 random + combat_exp 比较 + destruct 物品 + 多 set_temp 标记 + 分支消息 |
| init() maskman 随机触发 | 层3 | random(10)==5 + !target_found 时 call_out(determine_target,1)，概率触发 + 延时 + 状态标记 |
| init() add_action("do_enter","enter") | 层3 | 动态注册自定义命令 enter，层1 无 add_action 维度 |
| do_enter() 钻洞移动 | 层3 | arg=="dong" 时 move 玩家到 /d/gaibang/inhole + 跨房间双消息；前置 deny 条件已层1化 |
| is_suitable() 目标筛选 | 层3 | maskman 目标筛选：combat_exp<100000 / wizardp / is_ghost / no_fight / 房间名==监狱类 / is_busy / is_fighting / !living，多条件组合供 determine_target 调用 |
| copyvictim() NPC 技能复制 | 层3 | switch(random(4)) 4 大分支 + 每分支内 set_skill/map_skill/prepare_skill/carry_object/wield + 复制 max_qi/max_jing/max_neili/combat_exp/jiali + add_temp apply 修正，典型层3 |
| determine_target() + resume_targeting() maskman 周期搜索系统 | 层3 | while 双层循环 + random 选房间 + load_object 跨房间 + all_inventory 遍历 + is_suitable 筛选 + copyvictim 复制 + call_out 链（determine_target 1200s + resume_targeting 900s） |

## 层3 项详情

### 1. create() call_out("determine_target", 50)
- 理由：房间创建即 call_out 启动 50s 延时闭包，触发 maskman 周期任务。call_out 闭包启动点，层3。

### 2. init() 红镖扒手随机事件
- 理由：interactive 玩家进入时检查 has_temp("biao/zhu") + present("hong biao") + random(3)==1，触发扒手动作。内含嵌套 random(combat_exp) 比较决定是否扒走镖物，destruct 物品 + delete_temp/set_temp 多标记 + 分支消息。嵌套随机 + 物品销毁 + 多标记副作用，超出层1。

### 3. init() maskman 随机触发
- 理由：random(10)==5 && !query("target_found") 时 call_out("determine_target",1) + set("target_found",1)。概率触发 + 延时 + 状态标记，层3。

### 4. init() add_action("do_enter","enter") + do_enter()
- 理由：动态注册自定义命令 enter。do_enter 的 arg=="dong" 分支执行 move 玩家到 /d/gaibang/inhole + 跨房间双消息。命令注册维度层1 无，跨房间移动+双消息超出层1。前置 deny 条件（exit_blocked/rided/busy/fighting）已层1化，移动主体层3。

### 5. is_suitable() + copyvictim()
- 理由：is_suitable 是 maskman 目标筛选谓词（combat_exp/wizardp/ghost/no_fight/房间名/busy/fighting/living 多条件），供 determine_target 调用。copyvictim 是 NPC 技能复制：switch(random(4)) 4 大武学分支 + 每分支 set_skill/map_skill/prepare_skill/carry_object/wield + 复制属性 + add_temp apply 修正。两者合为一个层3 语义单元（maskman 核心逻辑）。

### 6. determine_target() + resume_targeting()
- 理由：maskman 周期搜索系统。determine_target 含 while 双层循环（attempt2<10 外层 + attempt1<k 内层）+ random 选房间 + find_object/load_object 跨房间 + all_inventory 遍历筛选角色 + is_suitable + copyvictim + new(NPC) + move + call_out 链（resume_targeting 900s + determine_target 1200s 周期）。完整状态机 + 循环 + 随机 + 跨房间 + call_out 闭包链，典型层3。

## 层1 规则说明

### 规则1: guangchang_enter_dong_prereq
- 对应 LPC do_enter 中 3 个前置 deny 检查：
  - `me->query_temp("exit_blocked")` -> deny "你正忙着挡住别人的出路呢！"
  - `me->query("rided")` -> deny "骑着东西钻洞？！"
  - `me->is_busy() || me->is_fighting()` -> deny "你正忙着呢！"
- 转译为 any(has_flag(exit_blocked), has_flag(rided), has_flag(busy), has_flag(fighting)) -> deny。
- 注意：do_enter 的移动主体（move 到 /d/gaibang/inhole）属层3，此层1 规则仅覆盖前置 deny 条件。
- 注意：has_flag 当前定义需扩展支持 exit_blocked/rided/busy/fighting 等 temp 标记。busy/fighting 是 LPC 方法调用（is_busy()/is_fighting()），可视为派生 flag。

## 谓词集缺口

- `has_flag` 需支持 query_temp 标记（biao/zhu, exit_blocked, target_found）和 query 标记（rided, luohan_winner 等）两种来源。
- `is_busy()` / `is_fighting()` / `is_ghost()` / `living()` / `wizardp()` 等 LPC 方法调用，建议统一抽象为派生 flag（busy/fighting/ghost/alive/wizard），由层1 has_flag 谓词查询。
- `present("hong biao", ob)` 是 has_item 的变体（按名称而非 id），建议 has_item 支持 item_name 参数。
- 这些扩展后，init 红镖扒手和 maskman 触发的"条件判断"部分可部分层1化，但其"副作用动作"（destruct/set_temp/call_out/new NPC/move）仍需层3。

## 备注

- 本文件是 6 个文件中复杂度最高的，maskman 系统是典型层3 场景：周期性 call_out + 循环搜索 + 跨房间 + NPC 动态生成与属性复制。
- locations 数组（49 个房间）虽是层0 数据，但仅服务于层3 的 determine_target 逻辑。
- do_enter 的前置 deny 可层1化，但移动主体层3，体现了"层1 管条件 deny，层3 管命令副作用"的分工模式。
