# clone_npc_murong 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/clone/npc/murong.c
- basename: clone_npc_murong
- 总语义单元数: 14
- 各层计数: 层0=6  层1=0  层2=1  层3=7
- 层3 项: 7 项（chat_msg random_move / init / do_destory / accept_fight / accept_kill / do_copy / return_home / is_unarmed，其中 chat_msg 与 is_unarmed 辅助性质）

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set_name/long/gender/age/attitude/shen_type | 层0 | 纯数据声明，NPC 身份与描述 |
| create() set(str/int/con/dex 30/max_qi 3000/max_jing 2000/neili 3000/max_neili 3000/jiali 100/combat_exp 1800000/score 5000) + set_temp(apply/armor 100/damage 60/dodge 30/attack 30) | 层0 | 纯数据声明，NPC 属性与临时修正 |
| create() set_skill(force/dodge/parry/finger/strike 200 + hunyuan-yiqi/shaolin-shenfa/sanhua-zhang/yizhi-chan 200) + map_skill 5 项 + prepare_skill 2 项 | 层0 | 纯数据声明，技能等级+映射+预备 |
| create() set("chat_chance",40) + set("chat_msg",({ (: random_move :) })) | 层3 | chat_chance 是数据，但 chat_msg 是函数指针 (: random_move :)，执行体是图灵完备移动逻辑，整体行为层3（数据壳层0+行为层3，按行为归层3） |
| create() set("inquiry", mapping 8 项静态回复) | 层2 | inquiry 静态对话树：8 个关键词映射到固定字符串回复，纯对话节点 |
| create() set("stay_chance",1) + set("no_clean_up",1) + setup() + carry_object(cloth)->wear() + homes 数组(16 房间) | 层0 | 纯数据声明，杂项属性+初始装备+游走房间表 |
| init() 正邪判定自动攻击 + spouse 查找 | 层3 | 多分支状态机：combat_exp<100000 return / family not in 邪派四门 return / interactive && shen>1000 -> 喝道+say+set_leader+do_copy+kill_ob / spouse find_player 或 new USER_OB+restore+call_out do_destory / spouse family 正派校验（注释），call_out 闭包+动态对象操作+多分支 |
| do_destory(ob) call_out 回调 destruct(ob) | 层3 | call_out 闭包回调 + destruct 动态对象销毁，对象生命周期操作 |
| accept_fight(ob) qi 百分比判定 + sneer + do_copy + kill_ob | 层3 | qi*100/max_qi<=80 百分比计算 + command(sneer) + message_vision + do_copy(ob) + kill_ob(ob)，条件计算+多副作用+触发 do_copy 链 |
| accept_kill(ob) haha + say + do_copy | 层3 | command("haha"/"say 天底下居然还有这种傻瓜？！") + do_copy(ob)，多副作用+触发 do_copy 链 |
| do_copy(ob) 核心技能拷贝 | 层3 | 3 套 for 循环删除 me 的 skills/maps/prepares + for 遍历 ob->query_skills 调 is_unarmed/SKILL_D->valid_enable 判定后 set_skill 200 + 第二轮 for 重设 map/prepare（含 valid_combine 双 prepare 组合校验）+ 兜底默认技能 + reset_action，循环+动态派发+条件嵌套 |
| return_home(home) 随机游走 | 层3 | environment 校验 + living/is_fighting/is_busy 状态守卫 + homes[random(sizeof)] 随机选目标 + move(home)，状态机+随机 |
| is_unarmed(skill) 辅助判定函数 | 层3 | member_array 查 + for 循环遍历 unarmed_types 调 SKILL_D(skill)->valid_enable 判定，循环+动态派发，被 do_copy 调用 |

## 备注

- 慕容博是"正邪判定自动攻击 + 技能镜像拷贝"型 NPC：init 时若玩家是邪派且正神高则自动 do_copy（镜像玩家技能）+ kill_ob。do_copy 的核心是遍历玩家技能并通过 is_unarmed/SKILL_D->valid_enable 动态判定哪些技能可映射到 dodge/force/unarmed，无法用层1 谓词或层2 对话树表达，必须层3。
- inquiry 8 项是纯静态字符串回复（慕容复/慕容/慕容氏/大燕国/邪派/正派/名门正派），无 ask->action 触发，属层2 对话树叶子节点。
- chat_msg 使用 LPC 函数指针语法 `(: random_move :)`，是层3 的强信号：数据声明外壳下包裹的是图灵可执行逻辑。这与普通字符串 chat_msg（可层0/层1）不同。
- 注释掉的 random_walk() 函数（line 306-340）若启用也是层3（exits/doors 查询 + random 选向 + last_room 记忆 + command open/go），当前已注释。
- homes 数组本身是层0 数据，但被 return_home 的 random(sizeof(homes)) 消费，数据层0+消费行为层3。
