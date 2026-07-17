# ADR-0014：32 守护进程职责重新设计

> 阶段 0 任务 8 产出。将 LPC 31 个 .c 守护进程逐一标注新引擎归属（ECS System / 无状态服务 / 新能力 / 砍掉），满足阶段 0 任务 8"32 守护进程职责重新设计"。
>
> 创建：2026-07-11
> 关联：[04 §六](../xkx-arch/04-迁移路径与避坑清单.md) 不做清单 / [09](../xkx-arch/09-灵魂系统盘点.md) themed 治理 / 层 H/C/E 规格 / [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent 2/5/8 / [CLAUDE.md](../../CLAUDE.md) 关键不变量

## 背景

LPC 侠客行有 31 个 .c 守护进程（adm/daemons/，04 称"32 守护进程"含子目录辅助文件），承担登录/战斗/权限/经济/频道/封禁等职责。greenfield 重写需逐一标注新引擎归属。

04 §六不做清单明确"不修 securityd 旧代码"（greenfield 重新设计）。04 §三阶段 1 ECS System 架构取代 LPC daemon 模型。

## 决策

四类归属：
- **ECS System 取代**：有状态守护进程 -> System（tick 驱动）
- **保留无状态服务**：纯函数/查询服务（进程内模块）
- **演进为新能力**：新需求驱动（如 securityd -> CapabilityToken）
- **砍掉/后置**：违反收缩约束或后置阶段

### 盘点产出

- [11-守护进程职责重新设计-核心运行时组.md](../xkx-arch/11-守护进程职责重新设计-核心运行时组.md)（15 个：logind/chard/securityd/natured/chinesed/commandd/aliasd/combatd/s_combatd/updated/virtuald/inquiryd/profiled/rankd/fingerd）
- [11-守护进程职责重新设计-社交辅助组.md](../xkx-arch/11-守护进程职责重新设计-社交辅助组.md)（16 个：channeld/emoted/marryd/moneyd/pigd/adsd/band/regband/regid/dns_master/editord/ftpd/socket/languaged/languanged/weapond）

### 统计（31 个合计）

| 归属 | 数量 | daemon |
|---|---|---|
| ECS System | 6 | logind / natured / combatd（+logind 连接管理可独立为 ConnectionSystem）/ channeld / moneyd |
| 无状态服务 | 12 | chard / chinesed / commandd / aliasd / inquiryd / rankd / fingerd + emoted / marryd / band / regband / weapond（band+regband 可合并） |
| 演进为新能力 | 2 | securityd -> PermissionService + CapabilityToken / regid -> AccountService |
| 砍掉（后置） | 6 | s_combatd（阵法合击 M3）/ pigd / adsd / editord（M3 后视需求）/ updated 部分砍（inventory_check 后置） |
| 砍掉（永久） | 6 | virtuald（空实现）/ profiled（OTel 替代）/ dns_master / ftpd / socket（分布式砍）/ languaged / languanged（UTF-8 替代） |

### 关键决策

1. **securityd -> PermissionService + CapabilityToken**：LPC euid/uid 模型映射为不可伪造的 CapabilityToken，valid_cmd 映射为命令管线第 1 段权限校验中间件。fail-closed 核心不变量（euid 为空或权限不匹配时拒绝，不得默认放行）。exclude 优先于 trusted。CLAUDE.md 要求安全模块类型完整。themed 治理平台级 fail-closed，不落入 UGC。04 §六不做清单"不修 securityd 旧代码"落地。

2. **combatd -> CombatSystem（七步交织 + combat 确定性）**：do_attack 七步管线的 SideEffect.order 记录 message_output 与 state_mutation 严格交织顺序，不得"先算后 apply"。29+ 处 random() 全部提取为 RandomSpec，combat 确定性范围=combat-only（全仿真后置 M3）。三层资源不变量（0<=qi<=eff_qi<=max_qi）。CombatKernel 从武侠提取、用非武侠验证（CLAUDE.md 不变量）。

3. **rankd -> PronounContext 三元组（speaker/viewer/target）**：query_close/query_self_close 中 `this_player()->query("age")` 依赖 viewer，是 CLAUDE.md 关键不变量"PronounContext 必须携带 viewer"的实证。System tick 无"当前说话者"时需定义回退（04 §七避坑 5）。阶段 2.5 TitleSystem 前置条件为 RANK_D 7 函数规格提取。

4. **intermud 三件套砍掉（dns_master/ftpd/socket）**：dns_master 违反收缩约束第 1/3 条（不考虑分布式架构/分布式网关），ftpd 与游戏无关，socket.c 被 Python asyncio 原生替代。channeld 的 intermud 频道（gwiz/gchat）同步砍掉，仅预留跨服广播接口。与任务 7 盘点建议一致。

5. **channeld chblk 平台级 fail-closed**：chblk 执行端硬编码在 ChannelSystem 中，不暴露为 UGC 可编辑规则。vote 投票结果通过 Event 通知 ChannelSystem 更新状态，形成"玩家自治投票 -> 平台强制执行"闭环。验证 CLAUDE.md 不变量"themed 治理是平台级 fail-closed Python"。

6. **languaged.c 和 languanged.c 完全副本**：逐字节对比确认完全相同，均因 UTF-8 统一编码砍掉。体现 LPC 代码冗余，greenfield 自然消除。

7. **regid -> AccountService（新能力）**：LPC crypt() 密码哈希必须替换为 argon2，新引擎账号系统重新设计（02 裁决：HS256/内存 session token+内存吊销集合）。平台级安全基础设施。

## 关联 dissent

- **dissent 2（ECS System 取代 daemon）**：本 ADR 将 6 个有状态 daemon 标注为 ECS System（logind/natured/combatd/channeld/moneyd + 可能的 ConnectionSystem），回应"ECS System 如何取代 LPC daemon"的架构问题。
- **dissent 5（themed 治理属性）**：securityd/channeld 的 themed 治理属性确认平台级 fail-closed，不落入 UGC。任务 7 盘点 + 本 ADR 共同回应"themed 治理如何落地"。
- **dissent 8（UGC 红线）**：emoted/weapond 归入题材包资产（UGC 可扩展/非硬编码），securityd/channeld chblk 不落入 UGC。[02](../xkx-arch/02-三个开放架构问题裁决.md) Q2 否决（UGC 红线）在本 ADR 中落地。

## 不做（后置/砍掉）

- 阵法合击（s_combatd）-> M3 后置为 CombatModifier
- 小游戏（pigd）/ 运营公告（adsd）/ 文选（editord）-> M3 后视需求
- intermud（dns_master/ftpd/socket）-> 砍掉，分布式后置阶段触发（单进程达 80% 承载 + UGC 验证成立后，需用现代协议 gRPC/WebSocket 替换 UDP）
- 编码转换（languaged/languanged）-> 砍掉，UTF-8 统一（如需简繁转换用 opencc）
- 虚拟对象（virtuald）-> 砍掉，ECS 实体工厂替代
- 命令性能分析（profiled）-> 砍掉，OTel + tick profiler 替代

## 验收

阶段 0 任务 8"32 守护进程职责重新设计"满足：31 个 .c 守护进程逐一标注归属，四类归属清晰（6 System / 12 服务 / 2 新能力 / 12 砍掉后置），关键决策关联 CLAUDE.md 不变量（PronounContext viewer / combat 确定性 combat-only / themed fail-closed）+ 04 收缩约束（intermud 砍）+ 09 themed 治理，衔接层 H/C/E 已提取规格。

阶段 1 实施时按本 ADR 归属落地：6 个 ECS System 随阶段 1 核心循环开发，2 个新能力（PermissionService/AccountService）随阶段 1 认证授权开发，无状态服务按需实现。
