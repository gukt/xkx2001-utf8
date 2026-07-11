# d_beijing_andingmen 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/d/beijing/andingmen.c
- basename: d_beijing_andingmen
- 含 #include: d/beijing/outer_gate.h（文本展开，语义计入本房间）
- 总语义单元数: 13
- 各层计数: 层0=6  层1=1  层2=0  层3=6
- 层3 项: 有（6 项，见下）

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| 本体 GATE_DESC_SHORT/LONG/EXITS/OBJECTS/ENTER_DIR 常量声明 | 层0 | 纯数据常量，供 outer_gate.h create() 引用 |
| outer_gate.h create() set 块（short/long/exits/is_outer_gate/enter_dir/enter_room/gate_name/night_exits/objects/item_desc/outdoors/cost） | 层0 | 纯数据声明；night_exits 由 GATE_EXITS 去掉 enter_dir 派生 |
| outer_gate.h create() set("item_desc", gaoshi: (: look_gaoshi :)) | 层0 | item_desc 注册（描述内容见下层1 规则） |
| outer_gate.h look_gaoshi() | 层1 | 动态 item_desc：night 标记二选一文案，condition->describe 形态，可用 has_flag(night) 谓词表达 |
| outer_gate.h init() add_action(guard/allow/climb) | 层3 | 命令注册入口；三个命令体均复杂（见下），整体层3。themed 治理平台代码（北京城门治安/御林军值班系统） |
| outer_gate.h gen_killer() | 层3 | call_out 闭包每 10s 循环；昼夜切换 set("exits",night_exits)+跨房间 fix_inside()->fix_exits_for_night()；生成天地会杀手 new(npc)->move->upgrade；御林军 reward_shiwei()->HELPER->job_reward。状态机+跨房间副作用+job 系统，层3 |
| outer_gate.h do_guard(string) | 层3 | 御林军 guard 命令：IS_SHIWEI/SHIWEI_LEVEL 权限+current_job 校验+辰时/戌时时段门控（is_sunrise/is_sunset）+set_temp 多状态。复杂状态校验+job 集成，层3 |
| outer_gate.h do_allow(string) | 层3 | 侍卫私放带兵器者：can_allow 权限+present 目标+活人校验+set_temp("outer_gate_allowed")+allow_num 计数。命令体副作用+计数，层3 |
| outer_gate.h do_climb(string) + finish_climb(object) | 层3 | 爬墙：night 前提+is_busy 检查+dodge 技能五档分级伤害（receive_damage max_qi/qi/jingli）+call_out("finish_climb",4)+成功后 find_object(load_object) inner_side->move。技能分级计算+延迟回调+跨房间 move，层3 |
| outer_gate.h valid_leave(me,dir) dir==enter_dir 分支 | 层3 | 多守卫环境遍历（all_inventory 扫描 bing_present+shiwei_present）+武器检查（weapon_prop）+三态分支文案（bing+shiwei / 仅 bing / 仅 shiwei）+check_auto_kill()->kill_ob 战斗触发。环境遍历+多对象交互+战斗触发，层3 |
| outer_gate.h fix_inside() | 层3 | 跨房间 exits 同步：find_object(load_object) enter_room->inner_side->fix_exits_for_night(0/1)+昼夜文案。跨房间副作用，层3 |
| outer_gate.h check_auto_kill(me,bing,shiwei) | 层3 | NPC 自动战斗触发：attempt_outer_gate 标记状态机+kill_ob 双向。战斗触发+状态机，层3 |
| outer_gate.h reward_shiwei(rank,player) | 层3 | 御林军换班奖励：清 temp 状态+HELPER->job_reward(rank,kill_num,allow_num)。job 系统集成，层3 |

## 备注

- 本房间是北京外城门模板（outer_gate.h）的实例之一，本体仅提供 5 个数据常量，全部行为逻辑来自共享 header。转译时需把 header 语义计入每个外城门实例（anddingmen/deshengmen 等共用同一模板）。
- 接近 themed 治理边界：御林军值班/天地会杀手生成/城门昼夜管控是平台级治安系统，但不在架构明确的 themed 清单（阴间/法院/武林大会）内，属"复杂 UGC 场景"。其复杂度（call_out 状态机+跨房间操作+job 集成+战斗触发）远超层1/层2 表达力，整体标层3。
- look_gaoshi() 是本房间唯一可层1 的语义单元：动态 item_desc 的二选一文案，night 谓词即可。但 night 标记由 gen_killer() 状态机维护，故层1 规则依赖层3 平台代码先设置 night flag。
- valid_leave 中"IS_SHIWEI+can_allow 不得离开"子条件形态可层1，但与多守卫武器检查整体交织，无法干净拆分，整体随 valid_leave 标层3。
