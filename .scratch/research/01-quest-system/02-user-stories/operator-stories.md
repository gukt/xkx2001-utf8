# 巫师/运营人员 User Stories：任务系统运维路径

> 本文件从巫师（wizard/arch/admin）与运营人员视角，梳理 LPC 源码中任务系统的开关、监控、奖励、调试、补偿、限额等运维路径。每条故事均附带源码中真实存在的命令或操作示例，并标注证据来源。

---

## 1. 任务系统总开关

### Story 1.1
**作为高级巫师，我想在特殊活动或版本更新时开启/关闭全服主动性任务系统，并通过系统频道通知玩家。**

**操作示例**：

```text
start_system          # 开启主动性任务系统
close_system          # 关闭主动性任务系统
```

执行后会通过 `CHANNEL_D` 向全服发送 `rumor` 与 `sys` 频道消息，例如：

```text
天地间微微颤动，似乎预示着什么玄机。
<巫师名>：我将任务系统开启了。
```

**权限要求**：
- 必须是巫师（`wizardp(this_player())`）。
- 在 `center.c` 中，部分命令还要求玩家 id 为 `server`、`poke`、`xuanyuan` 之一（`can_used()`），但 `start_system`/`close_system` 只检查 `wizardp`。

**证据来源**：
- `/d/wizard/center.c` 第 629–682 行：`do_start_system()` 与 `do_close_system()`。
- `/d/wizard/center.c` 第 124–138 行：`can_used()` 的 id 白名单逻辑。

---

## 2. 查看系统运行状态

### Story 1.2
**作为巫师，我想查询当前主动性任务系统是否已开启。**

**操作示例**：

```text
job_check -help       # 查看 job_check 帮助
job_check -menpai     # 查看门派列表
job_check -rate       # 查看门派任务产生比率
job_check -luck       # 查看门派幸运数值列表
job_check -money      # 查看门派金钱系数列表
job_check -wudang     # 查看武当派完整数据
```

**说明**：
- `-menpai_name` 选项可查看指定门派完全详细列表。
- 支持的 `-menpai_name` 包括：`-wudang`、`-xingxiu`、`-huashan`、`-taohua`、`-gaibang`、`-emei`、`-baituo`、`-quanzhen`、`-xueshan`、`-dali`、`-shaolin`。

**证据来源**：
- `/d/wizard/center.c` 第 65–91 行：`show_word()` 列出的命令说明。
- `/d/wizard/center.c` 第 1123–1337 行：`do_check()` 的实现。

---

## 3. 手动发布任务

### Story 1.3
**作为巫师，我想给某个玩家单独发布一次武林幻境任务，或让系统立即刷新一批任务。**

**操作示例**：

```text
job_start             # 系统立即 produce_job(0)，刷新任务
job_start <玩家名>    # 给指定玩家发布任务
```

**说明**：
- 无参数时调用 `/clone/obj/job/job_produce` 的 `produce_job(0)`。
- 带玩家名时调用 `produce_job(player_name)`，若玩家不在线则返回 "没有这个玩家"。

**证据来源**：
- `/d/wizard/center.c` 第 866–908 行：`do_start()`。

---

## 4. 查询玩家任务信息

### Story 1.4
**作为巫师，我想查看某个玩家当前的任务数据与执行进度。**

**操作示例**：

```text
do_check_player <玩家名>
```

**说明**：
- 从 `/clone/obj/job/job_data` 中恢复数据，按 `job_player` 键查找玩家 mapping，并输出。
- 若玩家没有任何任务记录，提示 "没有这个 player 的信息"。

**证据来源**：
- `/d/wizard/center.c` 第 796–823 行：`do_check_player()`。

### Story 1.5
**作为巫师，我想查看所有在线玩家的任务执行情况。**

**操作示例**：

```text
check_do_job
```

**输出结构**：

```text
现在已经得到任务的人有:
<玩家1>
<玩家2>

现在正在执行任务的人有:
<玩家3>

现在已经完成任务的人有:
<玩家4>
```

**说明**：
- 分别读取 `job_data` 中的 `finish_job`、`ask_job`、`oppose_pker` 列表，并过滤掉不在线的玩家。

**证据来源**：
- `/d/wizard/center.c` 第 830–864 行：`do_check_do_job()`。

---

## 5. 删除玩家任务信息

### Story 1.6
**作为巫师，我想删除某个玩家的任务数据，或在全服大重置时清空所有任务数据。**

**操作示例**：

```text
job_cut <玩家名>      # 删除指定玩家所有任务数据
job_cut all           # 重置整个 job_data（所有玩家）
```

**说明**：
- 删除指定玩家时，会先打印该玩家的任务 mapping，再调用 `detract_job_data(player_name)`，最后 `save()`。
- 使用 `all` 参数会调用 `job_data->reset()`，风险极高，需要 `can_used()` 通过。

**证据来源**：
- `/d/wizard/center.c` 第 685–718 行：`do_cut_job()`。

---

## 6. 手动发放奖励（award.c）

### Story 1.7
**作为高级巫师，我想手动授予玩家比武大会等活动的特殊奖励（称号或九阴真经权限）。**

**操作示例**：

```text
award <玩家id> title $HIR$武林至尊
award <玩家id> 9yin granted
```

**说明**：
- 支持两种 `type`：`title`（称号）和 `9yin`（九阴真经权限）。
- `title` 的 `value` 中可嵌入 ANSI 颜色码，如 `$HIR$`、`$NOR$`。
- 若玩家不在线，会临时 `new(USER_OB)` 并 `restore()` 玩家数据，修改后 `save()`。
- 权限要求：`wizhood(me)` 为 `(arch)`、`(admin)`、`(wizard)` 或 `(caretaker)`。

**证据来源**：
- `/cmds/wiz/award.c` 第 8–71 行：`main()`。
- `/cmds/wiz/award.c` 第 73–86 行：`help()` 与示例。

---

## 7. 调试 job_server

### Story 1.8
**作为巫师，我想查看或修改某个具体任务的经验/潜能上限，以调试平衡性。**

**操作示例**：

```text
set_exp_limit <任务名> <整数>
set_pot_limit <任务名> <整数>
job_info              # 查看所有已注册任务的 exp/pot limit
job_info <任务名>     # 查看指定任务的 exp/pot limit
```

**说明**：
- 这些命令通过 `/clone/obj/job_server.c` 物品对象提供。
- 修改后会写入 `log_file("job_server", ...)` 审计日志。

**证据来源**：
- `/clone/obj/job_server.c` 第 284–353 行：`do_set_exp_limit()`、`do_set_pot_limit()`、`do_job_info()`。

### Story 1.9
**作为巫师，我想查看某个任务的奖励分布直方图，判断是否存在奖励异常。**

**操作示例**：

```text
job_hist <任务名>
```

**输出示例**：

```text
Exp Histogram for ftb_search:
0 - 9: 10 jobs, average: 123/job 456/hour
...
In Total: 100 jobs, average: 200/job 800/hour
```

**说明**：
- 将 exp_rate/pot_rate 按 10% 分段统计。

**证据来源**：
- `/clone/obj/job_server.c` 第 449–469 行：`do_job_hist()`。
- `/clone/obj/job_server.c` 第 698–718 行：`print_hist_func()`。

### Story 1.10
**作为巫师，我想查看某个任务按玩家的详细完成统计。**

**操作示例**：

```text
job_stat <任务名>          # 默认按完成次数排序
job_stat <任务名> name     # 按玩家名排序
job_stat <任务名> exp      # 按 exp/hour 排序
job_stat <任务名> pot      # 按 pot/hour 排序
```

**输出字段**：

```text
User-Id #jobs exp/hour exp/job (rate) pot/hour pot/job (rate)
```

**说明**：
- 数据来自 `job_server` 保存的 `stat/<job_name>` mapping。
- 可用于发现刷任务或奖励效率过高的玩家。

**证据来源**：
- `/clone/obj/job_server.c` 第 383–445 行：`do_job_stat()`。

### Story 1.11
**作为巫师，我想清空某个 job_server 任务的统计与直方图（用于版本更新后重置数据）。**

**操作示例**：

```text
job_clear <任务名>
```

**说明**：
- 清除 `stat/<任务名>`，并将 `exp_hist`/`pot_hist` 归零。
- 注意：源码中注释掉了删除 `exp_limit`/`pot_limit` 与 `job_data` 的逻辑，因此上限会保留。

**证据来源**：
- `/clone/obj/job_server.c` 第 472–480 行：`do_job_clear()`。
- `/clone/obj/job_server.c` 第 654–671 行：`clear_func()`。

### Story 1.12
**作为巫师，我想模拟玩家开始/完成一个任务，以在测试环境验证流程。**

**操作示例**：

```text
job_start <任务名> <玩家名>   # 模拟开始任务
job_reward <任务名> <玩家名>  # 模拟结算（使用随机 rate）
```

**说明**：
- 这些命令只是示例用法，实际调用 `JOB_SERVER->start_job()` 与 `JOB_SERVER->reward()`。
- `job_reward` 使用 `random(100)` 作为 rate，生产环境不应如此。

**证据来源**：
- `/clone/obj/job_server.c` 第 488–531 行：`do_job_start()`、`do_job_reward()`。

---

## 8. 处理任务异常与补偿

### Story 1.13
**作为巫师，我发现某个玩家因任务 bug 卡死，想手动结束其任务状态并补偿奖励。**

**操作示例**：

```text
do_check_player <玩家名>        # 定位异常任务
job_cut <玩家名>                 # 删除其任务记录（可选）
award <玩家id> title $HIY$补偿使者  # 若补偿为称号
# 经验/潜能补偿需通过其他巫师指令或 job_server 模拟 reward
```

**说明**：
- LPC 源码中没有专门的 "任务补偿" 命令，通常需要组合 `do_check_player` + `job_cut` + `award` 或其他自定义指令完成。
- 新引擎应提供 "任务强制完成/放弃 + 补偿发放" 的原子操作，避免巫师手动改数据。

**证据来源**：
- `/d/wizard/center.c` 第 796–823 行：`do_check_player()`。
- `/d/wizard/center.c` 第 685–718 行：`do_cut_job()`。
- `/cmds/wiz/award.c` 第 38–65 行：奖励类型仅 `title`/`9yin`。

### Story 1.14
**作为巫师，我想查看任务系统运行期间的所有开关与参数变更日志。**

**操作示例**：

```text
# 读取日志文件（LPC 中通常通过 more/cat 文件命令）
more /log/test/job_system_set
more /log/job_server
```

**说明**：
- `center.c` 的开关、参数修改都会写入 `/log/test/job_system_set`。
- `job_server.c` 的 limit 修改、clear 操作写入 `/log/job_server`。
- 奖励明细按任务写入 `/log/job_server-<任务名>`。

**证据来源**：
- `/d/wizard/center.c` 第 648–651 行、675–678 行等：多处 `log_file("test/job_system_set", ...)`。
- `/clone/obj/job_server.c` 第 298–301 行、319–324 行：`log_file("job_server", ...)`。
- `/clone/obj/job_server.c` 第 592–598 行：`log_file("job_server-"+job, ...)`。

---

## 9. 配置任务限额与门派参数

### Story 1.15
**作为巫师，我想调整某个门派的任务出现比率，以平衡不同门派的任务热度。**

**操作示例**：

```text
change_rate <门派名> <比率>
# 例如：
change_rate 武当派 50
```

**约束**：
- 比率最大不超过 100。
- 修改后会广播到 `sys` 与 `rumor` 频道。

**证据来源**：
- `/d/wizard/center.c` 第 757–793 行：`do_change_rate()`。

### Story 1.16
**作为巫师，我想调整某个门派的贡献度基数。**

**操作示例**：

```text
set_contribute <门派名> <数值>
# 例如：
set_contribute 少林派 5000
```

**约束**：
- 数值最大不超过 100000。
- 修改后会写入 `job_menpai` 并广播。

**证据来源**：
- `/d/wizard/center.c` 第 719–755 行：`do_set_job_contribute()`。

### Story 1.17
**作为巫师，我想调整门派幸运值、金钱系数、策略系数与区域势力。**

**操作示例**：

```text
set_orgluck <门派名> <幸运值>        # 最大 10
set_orgmoney <门派名> <金钱系数>
set_orgstrategy <门派名> <策略名> <数值>   # 最大 100
set_orgpwoer <门派名> <区域> <数值>        # 最大 100，注意命令拼写为 pwoer
```

**说明**：
- 这些参数会影响门派任务生成与奖励。
- `set_orgpwoer` 命令在源码中拼写为 `pwoer`（typo），对应 `add_action("do_setorg_pwoer", "set_orgpwoer")`。

**证据来源**：
- `/d/wizard/center.c` 第 984–1046 行：`do_setorg_luck()`、`do_setorg_money()`。
- `/d/wizard/center.c` 第 910–983 行：`do_setorg_pwoer()`、`do_setorg_strategy()`。
- `/d/wizard/center.c` 第 105–106 行：`add_action("do_setorg_pwoer", "set_orgpwoer")`。

### Story 1.18
**作为巫师，我想把所有门派参数重置为默认值。**

**操作示例**：

```text
job_setorg_default all
job_setorg_default wudang    # 仅重置武当（源码中实现不完整）
```

**说明**：
- `all` 会调用 `job_menpai->set_default()`，然后依次为 11 个门派写入默认策略、幸运、金钱、势力、贡献度。
- 指定门派时，源码中只完整实现了 `wudang` 与 `xingxiu` 分支，其余返回失败。

**证据来源**：
- `/d/wizard/center.c` 第 1049–1122 行：`do_setorg_default()`。

---

## 10. 查看门派任务完成情况

### Story 1.19
**作为巫师，我想查看各门派任务的完成统计与贡献最高/最低玩家。**

**操作示例**：

```text
check_menpai_job -wudang
check_menpai_job -shaolin
```

**输出内容**：
- 该门派的任务数据。
- 贡献度最高的玩家（可能多个并列）。
- 贡献度最低的玩家（可能多个并列）。

**证据来源**：
- `/d/wizard/center.c` 第 199–628 行：`do_check_menpai_job()`。

### Story 1.20
**作为巫师，我想查看各门派当前的贡献度与贡献度基数。**

**操作示例**：

```text
check_menpai_assess
```

**输出示例**：

```text
武当派    当前的贡献度为 1234    贡献度基数为 1000
```

**证据来源**：
- `/d/wizard/center.c` 第 139–198 行：`do_check_menpai_assess()`。

---

## 11. 运营路径汇总表

| 运营意图 | 命令/操作 | 关键源码 | 风险点 |
|----------|-----------|----------|--------|
| 开启/关闭主动任务系统 | `start_system` / `close_system` | `center.c:629–682` | 影响全服，需谨慎 |
| 查看系统状态 | `job_check -help/...` | `center.c:1123–1337` | 信息量大 |
| 手动发布任务 | `job_start [玩家名]` | `center.c:866–908` | 可能产生异常对象 |
| 查看玩家任务 | `do_check_player <玩家>` | `center.c:796–823` | 隐私/运营数据 |
| 查看在线任务 | `check_do_job` | `center.c:830–864` | 仅在线玩家 |
| 删除玩家任务 | `job_cut <玩家>` / `job_cut all` | `center.c:685–718` | `all` 会清空全服 |
| 手动发奖 | `award <id> title/9yin <值>` | `cmds/wiz/award.c` | 仅支持两种类型 |
| 设置任务上限 | `set_exp_limit` / `set_pot_limit` | `job_server.c:284–326` | 影响经济平衡 |
| 查看奖励分布 | `job_hist <任务名>` | `job_server.c:449–469` | — |
| 查看玩家统计 | `job_stat <任务名> [name|exp|pot]` | `job_server.c:383–445` | — |
| 清空任务统计 | `job_clear <任务名>` | `job_server.c:472–480` | 不删上限 |
| 模拟任务开始/奖励 | `job_start <任务> <玩家>` / `job_reward ...` | `job_server.c:488–531` | 测试用途 |
| 调门派比率 | `change_rate <门派> <比率>` | `center.c:757–793` | — |
| 调门派贡献度 | `set_contribute <门派> <数值>` | `center.c:719–755` | — |
| 调门派幸运/金钱/策略/势力 | `set_orgluck/money/strategy/pwoer` | `center.c:910–1046` | 多参数易配错 |
| 重置门派参数 | `job_setorg_default all` | `center.c:1049–1122` | 全服重置 |
| 查看门派完成情况 | `check_menpai_job -<门派>` | `center.c:199–628` | — |
| 查看门派贡献度 | `check_menpai_assess` | `center.c:139–198` | — |

---

## 12. 对新引擎运营工具的启示

1. **权限分级要明确**：当前 LPC 中 `start_system` 只检查 `wizardp`，而 `job_cut all` 还要过 `can_used()`，权限模型较混乱。新引擎应区分 "系统开关"、"数据查询"、"数据修改"、"奖励发放" 四类权限。
2. **危险操作需要二次确认与审计**：`job_cut all`、参数重置、上限修改都应进入不可篡改的审计日志，并支持回滚。
3. **补偿机制应原子化**：当前 LPC 没有任务补偿命令，运营需要组合多条指令并可能直接操作玩家属性。新引擎应提供 "强制完成任务 + 发放补偿" 的原子能力。
4. **运营面板应可视化**：`job_hist`/`job_stat` 是很好的数据，但依赖命令行输出。新引擎应提供按题材包、按任务、按时间维度的图表。
5. **开关与灰度**：`start_system`/`close_system` 是全局开关，无法按服务器/按玩家群/按题材包灰度。新引擎应支持分片开关与灰度发布。
