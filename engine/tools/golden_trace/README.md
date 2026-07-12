# golden trace 录制方法

> LPC 原版侠客行 do_attack 七步 combat 文本流基线录制工具。
> 定位：**定点辅助验证**（[ADR-0009](../../../docs/adr/ADR-0009-original-driver-runnable.md)），非主线门禁。
> 用途：阶段 2.4 文本体验流 diff 基准（[dissent 4](../../../docs/xkx-arch/05-第三轮专家对抗复审报告.md) 基线测试）。

## 一、概述

主线门禁是单元级行为规约（[layer_e_combat.py](../../src/xkx/spec/layer_e_combat.py) 26 函数 + 49 副作用 order + 31 random 概率模型），golden trace 仅在"难以从代码静态推断"处定点录制运行时行为，提升行为等价验证置信度。不录全量命令流（8412 文件不可穷尽）。

## 二、编码事实（实测探明）

| 项 | 值 | 说明 |
|---|---|---|
| driver 输出编码 | **UTF-8** | 选 BIG5=n 后 driver 输出 UTF-8（非 GBK） |
| 中文输入编码 | **GBK** | LPC `check_legal_name` 用 `strlen` 按字节判定，中文名字节长须 2-8 且偶数；UTF-8 中文 3 字节/字不满足偶数约束，GBK 2 字节/字方可（1-4 中文字） |
| 英文名 | 纯字母 a-z，长度 3-8 | 含数字被拒"只能用英文字母" |
| 密码 | ASCII，>=5 字元 | |
| 电子邮件 | id@address 格式 | 空字符串被拒 |
| telnet IAC | 0xff 协商字节 | 须先过滤（`strip_iac`）再 decode，否则 UTF-8 decode 失败 |
| ANSI 颜色码 | `\x1b[...m` | 录制保留（diff 时剥离），关键词匹配/状态机判断时剥离 |

## 三、登录流程（10 步，实测探明，对应 adm/daemons/logind.c）

1. 连接 8888，读标题画面
2. "Do you want to use BIG5 code?(y/n)" -> 发 `n`（选 GB/UTF-8 输出）
3. "您的英文名字" -> 发纯字母英文名（3-8 字符）
4. "使用 X 这个名字将会创造一个新的人物，您确定吗(y/n)" -> 发 `y`
5. "您的中文名字" -> 发 GBK 编码中文名（1-4 中文字，`.encode("gbk") + b"\n"`）
6. "请设定您的密码" -> 发密码（ASCII >=5）
7. "请再输入一次您的密码" -> 发密码确认
8. "您接受这一组天赋吗" -> 发 `y`（接受随机天赋；`n` 重新随机）
9. "您的电子邮件地址" -> 发 `id@address` 格式 email
10. "您要扮演男性(m)或女性(f)" -> 发 `m`/`f` -> 进游戏

进游戏后出生在 **d/xiakedao/shatan1.c**（封闭引导房间：`set("exits", ([]))` 无出口 + `set("no_fight","1")` 禁止战斗 + `block_cmd` 屏蔽非 wizard 的所有命令，**只允许** quit/goto/suicide/follow/tell/say/reply/look）。

## 四、引导流程（离开出生点）

出生点 shatan1.c 不能战斗也不能走出口，必须跟"罚恶使"李四/张三对话触发传送：

1. 进 shatan1.c，李四 greeting（1s 后）：`bow` + `say 侠客岛罚恶使...请跟我来。(follow li si)`
2. 发 `follow li si`（block_cmd 允许 follow）
3. **等 18s**：李四 `check_follow`（greeting 后 5s 第一次，若 leader 未设则 +10s 第二次因 count>0 强制 move）把玩家 move 到 `/d/xiakedao/register`（侠客岛挂名处）
4. 发 `register <email>`（register 房间 block_cmd 允许 register）-> **密码被重置为随机串**（如 `vxrux`），driver 输出"您的新密码是 XXX，请用新的密码连线"，连接断开
5. 重新连接，**老玩家登录 3 步**：`n` -> 英文名 -> 新密码 -> 进侠客岛正式场景 d/xiakedao/shatan.c（"蓝蓝的大海...渔夫"，**有出口** north/east/northwest）

## 五、导航到可战斗场景

侠客岛是高手岛，多数房间 `no_pk_room`（禁玩家 PK 但允许 kill NPC）+ NPC 为各派高手。录制用的可战斗弱 NPC 路径：

- shatan.c（正式沙滩，no_fight，有渔夫）-> `go north` -> xiaolu.c（小路，可战斗，NPC 是 item bush）-> `go north` -> ybting.c（迎宾厅，可战斗，NPC 凌逍 huashan dizi）
- ybting 的凌逍 id：`huashan dizi` / `dizi` / `lingxiao`（`set_name("凌逍", ({"huashan dizi","dizi","lingxiao"}))`）
- `kill dizi` 触发战斗（no_pk_room 的 kill 拦截已注释，走正常 kill.c）

> 凌逍是华山弟子（中等强度），新角色裸装会被秒杀（~14 回合），但能录到完整 do_attack 七步文本 + 死亡轮回衔接。2.4 实施期可 wield 武器（xiaolu `push bush` 获短剑）+ 找更弱 NPC（monkey 在 shibi.c 断头路，需特殊命令进入）补 30+ 回合。

## 六、录制用法

```bash
cd engine

# 1. 录制登录会话（验证登录流程）
.venv/bin/python -m tools.golden_trace.recorder --login

# 2. 录制 combat（需先完成注册 + register 重置密码，见引导流程）
XKX_ACCOUNT=goldtcg XKX_NPC=dizi .venv/bin/python -m tools.golden_trace.recorder --sample

# 3. 探索（找 NPC 用）
.venv/bin/python -m tools.golden_trace.recorder --explore
```

> `--sample` 当前只发单次 kill + 读响应；多回合采样需循环 `_read_until` 累积（combat heart_beat 1 回合/秒，回合间有静默，单次 `_read_until` 静默返回会提前结束）。参考 `record_full2.py` 的持续读循环。

## 七、baseline 文件

| 文件 | 内容 |
|---|---|
| `login_session.txt` | 完整登录会话（10 步输入输出 + look） |
| `combat_huashan.txt` | combat 文本流 raw（含 ANSI） |
| `combat_huashan_clean.txt` | combat 文本流（去 ANSI，94 行，14 回合） |
| `combat_session.txt` | 录制会话完整日志（send/recv 时序） |
| `combat_stats.json` | 概率统计（命中/闪避/招架频率 + 伤害分布） |
| `meta.json` | 录制元信息（driver/角色/NPC/房间/采样/可复现命令） |

## 八、实测统计（14 回合，玩家 vs 凌逍，玩家裸装被秒杀）

| 观测 | 次数 | 概率 | 对应 LPC 公式（layer_e spec） |
|---|---|---|---|
| 闪避 dodge | 4 | 26.67% | dp/(ap+dp) |
| 命中 hit | 11 | 73.33% | 1 - dodge - parry |
| 招架 parry | 0 | 0% | pp/(ap+pp)（凌逍空手不招架？） |
| 瘀伤 wound | 9 | -- | wound: 空手kill 1/4 |
| n_decided | 15 | -- | dodge + parry + hit |

**do_attack 七步文本结构实测**（每回合）：
1. 取招式：`凌逍提起拳头往你的右臂捶去！` / `你挥拳攻击凌逍的右耳！`
2. AP/DP 计算：（内部，无文本）
3. 闪避判定：`但是凌逍身子一侧，闪了开去。` / `但是被他及时避开。`
4. 招架判定：（本轮未观测到）
5. 伤害结算：`结果在你的右脚造成一处瘀青。` / `结果一击命中，我的左脚登时肿了一块老高！`
6. 状态报告：`( 你看起来可能受了点轻伤。 )` / `( 你已经陷入半昏迷状态... )`
7. 战斗行为：`你目不转睛地盯著凌逍的动作，寻找进攻的最佳时机。` / `你慢慢地移动著脚步，伺机出手。`

死亡衔接（层 F）：`你的眼前一黑，接著什么也不知道了....` -> `你倒在地上，挣扎了几下就死了。` -> `【谣言】某人：金录庚被凌逍杀死了。` -> 鬼门关（阴间，白无常/龙八引导，衔接 2.6 GovernanceSystem）。

## 九、diff 建议（供 2.4 文本体验流 diff）

| 差异类型 | 处理 | 说明 |
|---|---|---|
| ANSI 颜色码 | 剥离后 diff | raw 保留 ANSI，clean 已剥离 |
| 时序 | 按回合分隔 diff | combat heart_beat 1 回合/秒，回合间静默；按"攻击动作行"切分回合 |
| 随机性 | 概率分布 diff（非逐字） | LPC random() 每次采样结果不同；同 seed 同 input 才逐字一致；2.4 用 greenfield resolve_attack(seed) 对比 LPC 概率分布 |
| 伤害描述 | 按描述文本分类 diff | LPC 伤害文本是描述性（瘀青/瘀伤/肿/轻伤/重伤），非数值；diff 须按描述分类映射 greenfield damage 输出 |
| 语义 | 语义差异标记 | 文本表述差异（如占位符 $N/$n/$w 渲染）须对照 PronounContext（2.5） |

## 十、边界与注意事项

- **不重启 driver**（PID 22753）：kill -9 会导致 UE 状态端口 8888 不释放，需重启电脑（[ADR-0009](../../../docs/adr/ADR-0009-original-driver-runnable.md)）
- **串行单连接**：driver 单进程共享，录制采样时多连接会互相干扰概率采样
- **不修改 LPC 源**：仓库根 adm/ cmds/ d/ kungfu/ 只读
- **定点辅助**：不录全量命令流（ADR-0009）；只录 combat 相关
- **样本受限**：新角色裸装被秒杀（14 回合）；2.4 实施期 wield 武器 + 找弱 NPC 补 30+ 回合提升概率统计置信度

## 十一、2.4 实施期补充计划

- [ ] wield 武器（xiaolu `push bush` 获短剑 duanjian）后重新录制，提高命中 + 延长战斗
- [ ] 找弱 NPC（monkey combat_exp 30 在 shibi.c，需探进入路径）录 30+ 回合
- [ ] 多次采样取概率分布（dodge/hit/parry 频率），对照 layer_e 31 处 random 概率模型
- [ ] 基于 baseline combat 文本，开发 2.4 文本体验流 diff 工具（按回合分隔 + ANSI 剥离 + 概率分布对比）
