# kungfu_skill_wudu-xinfa 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/kungfu/skill/wudu-xinfa.c
- basename: kungfu_skill_wudu-xinfa
- 引擎侧/内容侧: 内容侧（门派武学，五毒教内功，UGC CPK 资产）
- 总语义单元数: 8
- 各层计数: 层0=4  层1=1  层2=0  层3=3
- 层3 项: 3 项（见下表理由）

## 语义单元标注

| 语义单元 | 层 | 引擎侧/内容侧 | 理由 |
|---|---|---|---|
| check() 返回 "force" + inherit FORCE + valid_enable(usage) | 层0 | 内容侧 | 纯数据声明：技能类型 force，启用用途 force |
| exert_function_file(func) 返回路径模板 | 层0 | 内容侧 | 纯数据声明：运功函数文件路径模板 `wudu-xinfa/{func}` |
| curing_msg 的 apply_short/start_self/start_other/finish_self/finish_other/unfinish_self（6 条消息） | 层0 | 内容侧 | 纯数据声明：运功疗伤消息文本 |
| curing_msg 的 unfinish_other 字段（含条件分支） | 层3 | 内容侧 | eff_qi < max_qi*3/4 ? "喷血" : "吐瘀血"，消息文本条件选择，过程逻辑 |
| valid_learn(me) | 层3 | 内容侧 | t=2^(lvl/10) 指数+遍历统计 force 类技能数+gender/class 多分支+shen 动态阈值，不可谓词化 |
| practice_skill(me) 条件守卫部分 | 层1 | 内容侧 | 5 个属性阈值条件（wudu-xinfa>=150/空手/qi>=70/jingli>=70/neili>=70），可用 attr_lt+not(has_item) 谓词表达 |
| practice_skill(me) 资源扣减动作 | 层3 | 内容侧 | add(neili,-60)+receive_damage(jingli,60)+receive_damage(qi,60)，层3 函数调用（receive_damage 是引擎层3 接口） |
| #include force_list.h（force 类技能列表） | 层0 | 内容侧 | 纯数据声明：force 类技能注册（外部 include 文件） |

## 备注

- 五毒心法是五毒教门派内功（force 类），属内容侧 UGC CPK 资产（CLAUDE.md：三层粒度 Theme > Module Pack > UGC CPK，门派武学是 module pack 下的 CPK）。
- valid_learn 的复杂条件（指数增长阈值 t=2^(lvl/10) + 遍历统计 force 类技能数 + gender/class/shen 多分支）超出层1 谓词集表达能力，标层3。
  - 其中"force 类技能 >=2 则冲突"是跨技能查询逻辑，当前谓词集（attr_lt/has_flag/family_eq 等）无法表达。
  - "shen > -t*100" 是动态阈值（t 随等级指数增长），非固定阈值，attr_lt 无法表达。
- practice_skill 的条件守卫部分可层1化（practice_rule），但资源扣减动作调用 receive_damage（引擎层3 接口），整体仍需层3 编排。
  - 此处将条件提取为层1 practice_rule 是"能层1化的尽量层1"的尝试，实际执行仍需层3。
- curing_msg 是运功疗伤（exert_function "curing"）的消息文本，纯数据，但 unfinish_other 含条件分支故标层3。
- 新引擎预期：门派武学定义演变为 Theme/Module Pack 数据（层0）+ RestrictedPython 逃生舱（层3，valid_learn/hit_ob 等复杂触发），符合 CLAUDE.md 的 UGC CPK 治理模型。
