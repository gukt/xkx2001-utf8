# ADR-0061：job_data 子系统"源码不可读但存档可读"的行为等价边界裁决

- 状态：Accepted
- 日期：2026-07-16
- 阶段：AI 分批迁移 第四批（job_data 子系统）
- 关联：[ADR-0057](ADR-0057-daemon-store-per-object-save.md) 决策 1 DaemonStore + "不做"第 2 条 job_data 措辞（本 ADR 纠正） /
  [ADR-0059](ADR-0059-bboard-subsystem-migration-scope.md) bboard 两层模式范例 /
  [ADR-0056](ADR-0056-abandon-effort-estimation-ai-batched-migration.md) pilot id=2 卡点 /
  [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 4（基线测试断言）/ dissent 8（存储收缩丢失语义）/ 专家 3（Command 保真）

## 背景

LPC 侧有两个独立 job 系统，[ADR-0057](ADR-0057-daemon-store-per-object-save.md) 此前混为一谈：

**系统 1：job_server.c**（`clone/obj/job_server.c` 718 行，源码+存档双可读，完全可迁移）

- F_SAVE 单例，`query_save_file = /data/npc/job_server`。每个 `_func` 方法 `restore()` + 改 dbase + `save()`。
- dbase keys：`exp_limit/<job>` / `pot_limit/<job>` / `stat/<job>`（per-user 统计） / `exp_hist/<job>` / `pot_hist/<job>`（直方图） / `job_data/<job>_<data>`（KV）。
- API：`start_job` / `abort_job` / `get_start_time` / `reward` / `set_exp_limit` / `get_exp_limit` / `set_pot_limit` / `get_pot_limit` / `set_job_data` / `get_job_data` / `get_job_hist` / `get_job_stat`。
- 调用方：`d/city/npc/ftb_zhu.c`（job=ftb_search）、`kungfu/class/wudang/zhike.c`（job=wudang_volunteer）。源码完整可读，低风险。

**系统 2：job_data**（LPC 路径 `/clone/obj/job/job_data`，**源码文件缺失**，存档可读）

- **关键纠正 [ADR-0057](ADR-0057-daemon-store-per-object-save.md)**：ADR-0057"不做"第 2 条判断"job_data
  二进制 .sav 无法从 LPC 源提取"不完全准确。实际是 `/clone/obj/job/` 目录在仓库中不存在
  （`job_data.c` / `job_menpai.c` / `job_system.c` / `job_produce.c` 源码全部缺失），而非源码是二进制。
  但存档 `data/job_system/job_data.o` 是 **UTF-8 编码的 LPC .o 文本格式**（`file` 命令确认为
  Unicode text，非二进制），数据结构可从存档完整反推，API 契约可从调用方 `d/wizard/center.c`
  （1339 行，17 个 wizard 命令）反推。**但算法级逻辑（贡献度计算 `choose_of_player` 排序、
  任务分配）只能推断，无法逐行验证。**

- 这是 [ADR-0056](ADR-0056-abandon-effort-estimation-ai-batched-migration.md) 所指 pilot id=2 卡点。
  门派任务数据库：11 门派策略配置 + 玩家任务分配 + 贡献度统计。

- **数据结构（从存档 `data/job_system/job_data.o` 反推，UTF-8 文本 57 行）**：

  | dbase key | 类型 | 说明 | 示例值 |
  |---|---|---|---|
  | `ASSESS_NUM` | int | 评估基数 | `10000` |
  | `assess_<fac>` | int × 11 | 门派评估基数 | `assess_wd 7000` |
  | `strategy_<fac>` | mapping × 11 | 门派策略（6 策略权重） | `strategy_wd (["protect":30,...])` |
  | `luck_<fac>` | int × 11 | 门派运气值 | `luck_wd 3` |
  | `luck_<fac>rate` | int × 11 | 门派运气率 | `luck_wdrate 30` |
  | `money_<fac>` | int × 11 | 门派金钱系数 | `money_wd 5` |
  | `power_<fac>` | mapping × 11 | 门派势力（5 区域） | `power_wd (["南疆":5,"东北":5,...])` |
  | `job_datas` | array | 活跃任务数组 | 每条含 `job_player` / `job_master` / `job_strategy` / `job_area` / `job_menpai` 等 |
  | `family_job_data` | array × 11 | 门派贡献度数组 | 每条含 `job_contribute` + `family_name` + 各玩家贡献值 |
  | `family_assess` | array | 门派评估（存档为空） | `({})` |
  | `assess_player_data` | array | 玩家评估数组 | 每条含 `family` + `player_id:"bad"/"good"` |
  | `START_JOB_SYSTEM` | int | 任务系统开关 | `1` |

  门派缩写对照（11 门派）：`wd`=武当派 / `xx`=星宿派 / `hs`=华山派 / `th`=桃花岛 /
  `gb`=丐帮 / `em`=峨嵋派 / `bt`=白驼山 / `qz`=全真教 / `xs`=雪山派 / `dl`=大理段家 / `sl`=少林派。

  `job_datas` 每条活跃任务含 `job_command_mode`（"传话"）/ `job_player`（玩家 id）/
  `job_master_place`（NPC 房间路径）/ `job_area`（区域中文名）/ `job_master`（NPC 英文 id）/
  `job_strategy`（策略名）/ `job_master_cname`（NPC 中文名）/ `job_askjob`（标志）/
  `job_master_prompt_time`（时间戳）/ `job_menpai`（门派中文名）。反对 PK 类任务另有
  `job_oppose_pker_place_chinses` / `job_oppose_pker_place` / `job_oppose_pker_mode` /
  `job_oppose_pker_time` 字段。

  `family_job_data` 每条含多个 `player_id:contribute` 值对 + `job_contribute`（总贡献度）+
  `family_name`（门派中文名）。

- **API 契约（从 `d/wizard/center.c` 调用方反推）**：

  | 方法 | 签名（推断） | center.c 调用行 | 返回语义 |
  |---|---|---|---|
  | `restore()` | `-> None` | L161/L235/L639/L666/L702/L810 | 从存档恢复 dbase |
  | `save()` | `-> None` | L714 | 保存 dbase 到存档 |
  | `reset()` | `-> None` | L704 | 重置所有任务数据（`player_name=="all"` 时调） |
  | `query_familys_job_data()` | `-> list[mapping]` | L163 | 返回所有门派任务数据数组 |
  | `query_family_job_data(family)` | `-> mapping` | L171 | 返回单门派任务数据 |
  | `query_family_jobdata(family)` | `-> str` | L239 等 | 门派任务完成统计文本 |
  | `choose_of_player(family, kind)` | `-> list[str]` | L240/L255 | 贡献度 top/bottom 玩家名列表 |
  | `query_job_start()` | `-> bool` | L644/L671 | 任务系统是否开启 |
  | `set_job_start()` | `-> None` | L647 | 开启任务系统 |
  | `set_close_start()` | `-> None` | L674 | 关闭任务系统 |
  | `query_job_data()` | `-> list[mapping]` | L709/L811 | 活跃任务数组 |
  | `detract_job_data(player)` | `-> None` | L711 | 删除玩家任务 |

- 调用方仅 `d/wizard/center.c`（1339 行，注册 17 个 wizard 命令，`can_used` 门控 id 白名单
  `server`/`poke`/`xuanyuan` + `wizardp`）。

**engine 承接**：[DaemonStore](../../engine/src/xkx/runtime/daemon_store.py)（ADR-0057）已实现
`register` / `get` / `save` / `save_async` / `restore_all`，`DaemonSerializable` Protocol
（`to_dict` / `from_dict`），存档 `<root>/daemon/<name>.json`，已覆盖 bboard。bboard 范例
（ADR-0059）：数据层 `daemons/bboard.py`（`BboardData` dataclass + `DaemonSerializable`） +
命令层 `bboard_commands.py`（`do_read` / `do_list` / `do_discard` 函数族
`(game, ctx, board) -> list[str]`），配套 `capability.cmp_wiz_level` + `components.BoardLastRead`。

pilot 样本 id=2
[`center_c_do_check_menpai_job.py`](../../engine/tools/sampling/pilot/samples/center_c_do_check_menpai_job.py)
有 `JobDataLike` Protocol（`restore` / `query_family_jobdata` / `choose_of_player` 三方法最小契约），
已验证 `do_check_menpai_job` 迁移逻辑（11 段门派同构去重为参数化循环）。
[`daemons/__init__.py`](../../engine/src/xkx/runtime/daemons/__init__.py) L6 注释"job_data
二进制 .sav 无法提取，留 Protocol 占位"需修正（决策 4）。

**卡点**：依赖 `job_menpai`（源码缺失，存档 `data/job_system/menpai.o` 可读 LPC .o 文本） /
`job_system`（源码缺失，存档不可读）/ `CHANNEL_D`（未迁，桩）/ `start_more`（分页后置 M3）/
`can_used` 门控（映射 `capability.cmp_wiz_level`）/ GBK 中文门派名解码（存档实测为 UTF-8）。

## 决策

### 1. 行为等价边界三档（核心裁决）

"源码不可读但存档可读"子系统的行为等价不能笼统要求，必须分三档裁决：

| 档位 | 可验证性 | 验证手段 | 裁决 |
|---|---|---|---|
| **数据结构级** | 可验证 | 存档往返测试：解析 `job_data.o`（LPC .o 文本）为 `JobData` dataclass -> `to_dict` -> JSON -> `from_dict` -> 断言字段一致 | **必做**，覆盖全部 12 类 dbase key |
| **API 契约级** | 可验证 | 调用方契约测试：从 `center.c` 调用方反推 API 签名与返回类型，构造测试用例验证方法行为。`do_check_menpai_job` 输出格式用 pilot id=2 已验证的测试逻辑覆盖 | **必做**，覆盖 12 个 job_data 方法 |
| **算法级** | **不可逐行验证** | 用存档快照作基线数据断言输出与存档数据一致（数据一致但不保证算法逻辑等价），明确标注"推断实现" | **接受为权衡**，不可逐行验证 |

**算法级不可验证的具体范围**：

- `choose_of_player(family, kind)`：贡献度排序逻辑。源码缺失，无法确认排序算法细节
  （按 `job_contribute` 值排序？相同值如何处理？top/bottom 取几个？）。只能从存档数据
  推断：`family_job_data` 中每门派有 `job_contribute` 总值和各玩家贡献值，`choose_of_player`
  应按玩家贡献值排序取 top/bottom，但排序细节只能推断。
- `query_family_jobdata(family)`：返回门派任务完成统计文本。文本拼接逻辑只能从
  `do_check_menpai_job` 调用方（`_format_menpai` 中 `msg += job_data.query_family_jobdata(family)`）
  反推拼接位置，但具体文本内容（哪些字段如何拼接）只能推断。
- 任务分配逻辑（`job_datas` 的生成）：`job_system` 源码缺失，无法验证。
- 贡献度计算（`job_contribute` 的更新）：源码缺失，无法验证更新算法。

**风险**：算法级行为漂移不可检测（无源码基线）。此风险记为本 ADR 接受权衡：数据结构级 +
API 契约级可验证已覆盖子系统可观察行为的主体（存档数据 + 调用方契约），算法级漂移影响
限于内部计算细节，外部可观察行为（命令输出文本格式、存档数据结构）仍可验证。

### 2. 迁移范围：参照 bboard 两层模式 + 17 命令分类

参照 [ADR-0059](ADR-0059-bboard-subsystem-migration-scope.md) 两层模式：数据层
（`daemons/job_data.py`，`JobData` dataclass + `DaemonSerializable`） + 命令层
（`job_commands.py`）。center.c 17 命令按操作对象分三类：

| 命令 | LPC 行 | 操作对象 | 本批 | 理由 |
|---|---|---|---|---|
| `do_check_menpai_job` | L199-628 | job_data | 迁移 | pilot id=2 已验证，合一到引擎层 |
| `do_check_player` | L796-823 | job_data | 迁移 | 低卡点（`get_mapping`/`p_map` 可从 `lpc_math.h` 反推，只读查询） |
| `do_cut_job` | L685-717 | job_data | 迁移 | DaemonStore save 闭环（类比 bboard `do_discard` 删帖后 save） |
| `do_check_do_job` | L830-864 | job_data | 迁移 | 低卡点（只读查询在线玩家任务） |
| `do_check_menpai_assess` | L139-198 | job_data + job_menpai | 暂缓 | 依赖 `job_menpai` 数据层 + `start_more` 分页 |
| `do_start_system` | L629-655 | job_data + job_system | 暂缓 | 依赖 `job_system`（源码缺失）+ `CHANNEL_D` |
| `do_close_system` | L656-682 | job_data + job_system | 暂缓 | 同上 |
| `do_set_job_contribute` | L719-756 | job_menpai | 暂缓 | 需先迁 `job_menpai` 数据层 |
| `do_change_rate` | L757-794 | job_menpai | 暂缓 | 同上 |
| `do_setorg_pwoer` | L910-947 | job_menpai | 暂缓 | 同上 |
| `do_setorg_strategy` | L948-983 | job_menpai | 暂缓 | 同上 |
| `do_setorg_luck` | L984-1015 | job_menpai | 暂缓 | 同上 |
| `do_setorg_money` | L1016-1048 | job_menpai | 暂缓 | 同上 |
| `do_setorg_default` | L1049-1122 | job_menpai | 暂缓 | 同上 |
| `do_start` | L866-909 | job_produce | 暂缓 | 依赖 `job_produce`（源码缺失）+ `CHANNEL_D` |
| `do_stop` | 未定位 | job_system | 暂缓 | 依赖 `job_system`（源码缺失） |
| `do_check` | L1123-1339 | 待确认 | 暂缓 | 需迁移时确认操作对象 |

本批迁移 4 个命令（均直接操作 job_data，低卡点），暂缓 13 个（依赖 `job_menpai` 数据层 /
`job_system` + `job_produce` 源码缺失 / `CHANNEL_D` / `start_more`）。暂缓符合
[04](../xkx-arch/04-迁移路径与避坑清单.md) §一"收敛优先于完备"：不为大卡点建桩绕过，
留触发条件明确的后续批。

**job_server.c（系统 1）顺带迁移数据层**：源码完整可读（718 行），低风险。
`daemons/job_server.py`（`JobServerData` dataclass + `DaemonSerializable`），
dbase keys 从源码直接提取（非反推）。命令层留后续 job_server 子系统批
（调用方 `ftb_zhu.c` / `zhike.c` 门派任务触发逻辑较重）。

### 3. 依赖处理策略

| 依赖 | 状态 | 处理 |
|---|---|---|
| `job_menpai` | 源码缺失，存档 `data/job_system/menpai.o` 可读 LPC .o 文本 | 同 job_data 走存档反推（数据结构级可验证）。数据层 `daemons/job_menpai.py` 留后续批，本批 `do_check_menpai_assess` 等依赖它的命令暂缓 |
| `job_system` | 源码缺失，无存档可读 | 用桩（`load_object` 占位返回成功）。`do_start_system` / `do_close_system` 命令暂缓，不为本批建桩 |
| `job_produce` | 源码缺失，存档 `data/job_system/produce.o` 可读 | 同 job_menpai 走存档反推，留后续批 |
| `CHANNEL_D` | 未迁 | 用桩（`do_channel` no-op），命令暂缓时不引入 |
| `start_more` | 分页后置 M3 | 内联 `return [msg]`（对齐 bboard `do_list` 模式，真实 pager 后置 M3） |
| `can_used` 门控 | 映射已有 | `capability.cmp_wiz_level`（ADR-0059 已落地）+ id 白名单 `server`/`poke`/`xuanyuan` 映射 `Identity.prototype_id` |
| GBK 中文门派名 | 存档实测 UTF-8 | 存档 `job_data.o` 实测为 UTF-8 编码（`file` 命令确认 Unicode text），非 GBK。引擎统一 UTF-8，无需转码 |

### 4. 纠正 [ADR-0057](ADR-0057-daemon-store-per-object-save.md) 措辞

ADR-0057"不做"第 2 条原文：

> 不做 job_data 完整数据建模：job_data 二进制 .sav 无法从 LPC 源提取。保留 pilot id=2
> 的 `JobDataLike` Protocol 契约...不试图反推二进制 .sav 结构。

**纠正**：job_data 存档 `data/job_system/job_data.o` 是 UTF-8 编码的 LPC .o 文本格式（非二进制
.sav），数据结构可从存档完整反推（决策 1 数据结构级可验证）。ADR-0057 的"无法提取"判断
不准确，应修正为"源码文件缺失（`/clone/obj/job/` 目录不存在），但存档可读 LPC .o 文本，
数据结构从存档反推、API 契约从调用方反推，算法级接受推断权衡"。

**`daemons/__init__.py` L6 注释修正**：

- 原：`job_data：门派任务/贡献度统计（二进制 .sav 无法提取，留 Protocol 占位）`
- 改：`job_data：门派任务/贡献度统计（源码 /clone/obj/job/ 缺失，存档 data/job_system/job_data.o
  可读 LPC .o 文本，数据结构从存档反推，见 ADR-0061）`

"源码不可读但存档可读"不等于"无法提取"。这是一类子系统的通用模式：源码缺失但存档可读时，
数据结构级 + API 契约级可验证，算法级接受推断权衡。后续遇同类子系统（如 `job_menpai` /
`job_produce`）照此三档裁决。

## 关联 [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent

- **专家 3（MUD 玩法与文化专家）承重论断**：`call_other` 退化为进程内同步调用天然契合
  LPC 语义，单房间串行是 MUD 固有硬约束而非缺陷。job_data 的 API 契约从 `center.c` 调用方
  反推正是这种保真的体现--调用方源码可读（`center.c` 1339 行完整），契约可完整反推
  （12 个方法签名 + 返回类型），不依赖被调用方源码可读。行为等价硬约束在 API 契约级适用。
- **dissent 4（规则冲突语义漂移）**："LPC 靠注册顺序隐式覆盖触发器命中...靠基线测试断言
  原 LPC 命中行为。"同理，job_data 算法级（`choose_of_player` 排序、贡献度计算）无源码基线，
  靠存档快照作基线数据断言输出一致，但不保证算法逻辑等价。本 ADR 明确此为接受权衡，
  不伪造算法级等价。
- **dissent 8（存储收缩丢失语义）**：内存+JSON 丢失事务原子性/崩溃恢复/并发写 CAS/关系完整性。
  job_data 存档从 LPC .o 文本迁为 JSON（DaemonStore），数据结构级往返可验证。但贡献度计算
  等算法级逻辑在内存态下的行为等价只能靠推断，无法逐行验证--这是"源码不可读"叠加"存储
  收缩"的双重不可验证性，标注为已知风险。
- **行为等价硬约束的适用边界**：[04](../xkx-arch/04-迁移路径与避坑清单.md) §五检查点 7
  "逐子系统行为等价验证"是 greenfield 硬约束。本 ADR 裁决该硬约束在"源码不可读存档可读"
  子系统的适用边界：数据结构级 + API 契约级硬约束适用（可验证必做），算法级硬约束降级为
  "尽力保真"（推断实现 + 基线数据断言，不伪造逐行等价）。

## 与 [04](../xkx-arch/04-迁移路径与避坑清单.md) 验收关系

- **§三 阶段 2 子系统行为等价 + 门派边界切割**：job_data 是门派任务子系统核心数据载体，
  本批落地数据层 + 4 命令，行为等价分三档裁决是子系统级等价的明确体现。
- **§五检查点 7（逐子系统行为等价验证）**：数据结构级存档往返 + API 契约级调用方测试
  是可验证档的验收手段；算法级标注推断是等价边界的明确声明。
- **§四 kill criteria 8（迁 PG）**：daemon save 同 entity save，迁 PG 时 `DaemonStore` 换
  `PostgresDaemonBackend`（策略切换，同 [ADR-0057](ADR-0057-daemon-store-per-object-save.md)）。

## 不做（范围边界）

- **13 个依赖不可读对象/CHANNEL_D/start_more 的命令迁移**（决策 2，暂缓）。
- **job_menpai / job_produce 数据层**（存档可读反推，留后续批，本批只做 job_data）。
- **job_system 数据建模**（源码缺失 + 无存档可读，只用桩占位）。
- **算法级逐行验证**（决策 1，接受推断权衡，不伪造等价）。
- **job_server.c 命令层**（数据层顺带，命令层留后续 job_server 子系统批）。
- **COMMAND_REGISTRY 注册**（同 ADR-0059，房间-center 关联未接，只迁函数 + 测试）。
- **不修改 LPC 源**（只读规格，且 `/clone/obj/job/` 源码已缺失）。

## 产出位置

- `engine/src/xkx/runtime/daemons/job_data.py`：`JobData` dataclass + `DaemonSerializable`，
  字段从存档反推（12 类 dbase key + 11 门派缩写对照）。
- `engine/src/xkx/runtime/daemons/job_server.py`：`JobServerData` dataclass + `DaemonSerializable`，
  字段从源码直接提取（系统 1，完全可读）。
- `engine/src/xkx/runtime/job_commands.py`：`do_check_menpai_job` / `do_check_player` /
  `do_cut_job` / `do_check_do_job` 引擎层命令（函数族 `(game, ctx, job_data) -> list[str]`）。
- `engine/src/xkx/runtime/daemons/__init__.py`：L6 注释修正（决策 4）。
- `engine/tests/test_job_data.py`：存档往返测试（数据结构级）+ API 契约测试（API 契约级）。
- `engine/tests/test_job_commands.py`：4 命令行为测试（含 `do_cut_job` DaemonStore save 闭环）。
- `engine/tools/sampling/pilot/samples/center_c_do_check_menpai_job.py`：顶部加标注
  "已被引擎层 do_check_menpai_job 替代"（桩不动，参照 ADR-0059 决策 6）。

## 后续

- `do_check_menpai_assess` + `do_setorg_*` 系列（7 命令）：待 `job_menpai` 数据层迁移后。
- `do_start_system` / `do_close_system` / `do_start` / `do_stop`：待 `job_system` /
  `job_produce` 数据建模 + `CHANNEL_D` 迁移后。
- `do_check`：待迁移时确认操作对象。
- 算法级验证补强：若后续获得 job_data 运行时快照（在线服务日志），可补算法级基线断言。
- 迁 PG（kill criteria 8）：`DaemonStore` 与 `StorageSystem` 同步策略切换。
