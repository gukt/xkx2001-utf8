# feature_damage 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/feature/damage.c
- basename: feature_damage
- 引擎侧/内容侧: 引擎侧（伤害特性，三层资源模型核心）
- 总语义单元数: 13
- 各层计数: 层0=1  层1=0  层2=0  层3=12
- 层3 项: 12 项（见下表理由）

## 语义单元标注

| 语义单元 | 层 | 引擎侧/内容侧 | 理由 |
|---|---|---|---|
| int ghost = 0（鬼魂标志初始值） | 层0 | 引擎侧 | 纯数据声明，鬼魂状态初始值 |
| is_ghost() | 层3 | 引擎侧 | 引擎平台状态查询接口 |
| receive_damage(type, damage, who) | 层3 | 引擎侧 | 三层资源 qi 层写入点：校验+last_damage_from+扣减+set_heart_beat，多步副作用交织 |
| receive_wound(type, damage, who) | 层3 | 引擎侧 | 三层资源 eff 层写入点：校验+eff 扣减+qi 同步降低+set_heart_beat，保持 qi<=eff_qi 不变量 |
| receive_heal(type, heal) | 层3 | 引擎侧 | 当前值层恢复：校验+val+heal+上限截断（jingli 上限 max，其他上限 eff），过程逻辑 |
| receive_curing(type, heal) | 层3 | 引擎侧 | eff 层恢复：校验+val+heal+上限 max 截断+返回实际恢复量，过程逻辑 |
| unconcious() | 层3 | 引擎侧 | 昏迷：winner_reward+remove_all_enemy+interrupt_me+dismiss_team+消息+disable_player+资源归零+block_msg+announce+call_out revive（random(100-con)+30），多步副作用+随机性 |
| revive(quiet) | 层3 | 引擎侧 | 唤醒：remove_call_out+move 上层+enable_player+announce+block_msg 清除+消息，过程逻辑 |
| die() | 层3 | 引擎侧 | 死亡流程：no_death 守卫+clear_condition+announce+death_penalty+killer_reward+日志+make_corpse+资源归 1+save+move DEATH_ROOM+start_death+NPC destruct，极复杂多步副作用交织 |
| reincarnate() | 层3 | 引擎侧 | 转生重置：ghost=0+资源全恢复到 max，过程逻辑 |
| max_food_capacity() / max_water_capacity() | 层3 | 引擎侧 | 依赖 query_weight() 的计算函数，过程逻辑 |
| heal_up() | 层3 | 引擎侧 | 三层资源恢复：water/food 递减+水食不足不恢复+jing/qi/jingli/neili 公式恢复（战斗/非战斗双速）+eff 层+1 自愈，多步副作用交织 |
| do_attack 步骤 6 调用 receive_damage/receive_wound 的触发点 | 层3 | 引擎侧 | 见 layer_e_combat.py 规格，receive_damage 可能导致 qi<=0 触发 die() |

## 备注

- damage.c 是三层资源模型（0 <= qi <= eff_qi <= max_qi，jing/jingli/neili 同理）的核心契约实现。
- 架构不变量：三层资源不变量，receive_damage 只扣 qi 不扣 eff_qi，receive_wound 扣 eff 且同步 qi。
- die() 属层 F（死亡轮回），但 do_attack 步骤 6 的 receive_damage 可能导致 qi<=0 触发 die()，此处提取死亡触发链。
- heal_up() 是 heart_beat 步骤 7 的自愈机制，战斗中恢复速率大幅降低（con/9 vs con/3）。
- unconcious() 的 call_out("revive", random(100-con)+30) 是 NPC AI 层随机性，非 combat 范围。
- 已有完整规格见 layer_e_combat.py（receive_damage/receive_wound/receive_heal/receive_curing/die/unconcious/heal_up 均已提取 FunctionSpec）。
- 新引擎预期：演变为 ECS System 中的 ResourceSystem / CombatDamageSystem / DeathSystem，Python 原生实现，语义上属层3。
