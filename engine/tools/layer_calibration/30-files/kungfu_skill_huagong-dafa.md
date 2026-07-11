# kungfu_skill_huagong-dafa 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/kungfu/skill/huagong-dafa.c
- basename: kungfu_skill_huagong-dafa
- 引擎侧/内容侧: 内容侧（门派武学，星宿派化功大法，UGC CPK 资产）
- 总语义单元数: 7
- 各层计数: 层0=3  层1=0  层2=0  层3=4
- 层3 项: 4 项（见下表理由）

## 语义单元标注

| 语义单元 | 层 | 引擎侧/内容侧 | 理由 |
|---|---|---|---|
| check() 返回 "force" + inherit FORCE + valid_enable(usage) | 层0 | 内容侧 | 纯数据声明：技能类型 force，启用用途 force |
| exert_function_file(func) 路径模板（静态部分） | 层0 | 内容侧 | 纯数据声明：运功函数文件路径模板 `huagong-dafa/{func}`（但函数本身含门控逻辑，见层3） |
| hit_by 返回的 mapping 结构 {result, damage} | 层0 | 内容侧 | 纯数据声明：回调返回值结构约定（do_attack 步骤 5 期望的返回类型） |
| valid_learn(me) | 层3 | 内容侧 | t=2^(i/10) 指数+shen 动态阈值+4 教内功互斥+9 门内功互斥，跨技能查询+动态阈值，不可谓词化 |
| practice_skill(me) | 层3 | 内容侧 | 直接 notify_fail 禁止练习（只能 learn），过程逻辑 |
| hit_by(me, victim, damage, damage_bonus, factor) | 层3 | 内容侧 | do_attack 步骤 5 hit_by 回调：hua temp 守卫+dp/ap 计算+weapon 双分支+random(ap+dp)>ap 判定（combat seeded RNG）+8 种结果文本+neili 转移+返回 mapping，极复杂多分支+随机性+副作用交织 |
| exert_function_file(func) 运功门控逻辑 | 层3 | 内容侧 | 遍历统计 force 类技能数（>=2 冲突禁止）+返回路径，循环+条件分支 |

## 备注

- 化功大法是星宿派门派内功（force 类），属内容侧 UGC CPK 资产。
- hit_by 是 do_attack 步骤 5 的武学 hit_by 回调（见 layer_e_combat.py SideEffect order=32：
  "特殊闪避 hit_by 回调：dodge_skill 的 hit_by 可能返回 string/int/mapping"）。
  化功大法的 hit_by 返回 mapping {result, damage}，是"化掉对方内力"的核心机制：
  - random(ap+dp) > ap 时触发化功（ap=me.force，dp=victim.huagong-dafa+weapon/prepare 加成）
  - me.neili 减少 huagong-dafa/3*2，victim.neili 增加同量（内力转移）
  - damage_bonus = -random(4000)（将伤害化为负值，即反弹/吸收）
- hit_by 的随机性属 combat 范围，层 E 实现时需要 seeded RNG（与 do_attack 的 29+ 处 random 共享确定性 RNG）。
- valid_learn 的互斥检查（4 教内功 + 9 门内功）是跨技能查询逻辑，当前谓词集无法表达，标层3。
  - 互斥内功列表是硬编码数据，可考虑提取为层0 数据声明（互斥技能列表），但判定逻辑仍需层3。
- exert_function_file 的门控逻辑（force 类技能 >=2 冲突）与 wudu-xinfa 的 valid_learn 中相同逻辑重复，
  反映了"内功冲突"是门派武学的通用规则，新引擎可提取为通用层1/层0 规则。
- 与 wudu-xinfa 对比：化功大法无 curing_msg（无运功疗伤消息），但有 hit_by（伤害回调），
  体现了不同门派内功的差异化机制（五毒心法偏恢复，化功大法偏化功反击）。
- 新引擎预期：hit_by 演变为 CombatSystem 的武学回调钩子（ RestrictedPython 逃生舱），valid_learn 互斥规则可部分层0/层1化。
