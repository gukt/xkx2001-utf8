# 现状分析·守护进程(Daemon)架构 — XKX MUD 全局服务层

## 概述
XKX 采用 MudOS 单进程单例守护进程模型。守护进程作为全局服务在启动时经 master.c 的 epilog/preload 列表加载为主副本（非克隆），通过 globals.h/daemons.h 的宏路径常量（COMBAT_D、CHANNEL_D、SECURITY_D 等）定位，再用 find_object/call_other 实现进程内同步调用（等价于本地 RPC）。securityd 作为安全中枢经 master.c 的 valid_write/valid_seteuid 钩子接入驱动，以 euid/status 做 trusted/exclude 双向路径 ACL。定时任务分两类：call_out 自重排循环（natured 昼夜相位、moneyd 现金校验）与 per-object heart_beat（F_ATTACK 在心跳里调 COMBAT_D->fight）。状态共享依赖 F_DBASE 的 mapping 中枢与 F_SAVE 的 .o 文件持久化。

## 现有模式
- **单例守护进程模式(Singleton Daemon)**：守护进程作为主副本(master copy)在启动时经 preload 列表加载一次，全局共享单实例状态。combatd/securityd/logind 等均不克隆，通过宏路径常量(COMBAT_D='/adm/daemons/combatd')全局定位。映射为微服务时每个 daemon 对应一个无状态或有状态服务实例。
- **call_other/find_object 同步通信**：守护进程间及对象对守护进程的调用通过 call_other(path, func, args...) 同步完成，等价于进程内同步 RPC。combatd 被 F_ATTACK 的 attack() 在 heart_beat 中调用 COMBAT_D->fight()；combatd 内部又回调 SKILL_D/CHANNEL_D。映射为同步→异步 RPC/消息总线，需引入超时熔断。
- **宏路径注册表 + preload 启动注册**：globals.h(41-66行)与 daemons.h 集中定义所有 daemon 路径宏，形成静态服务注册表。master.c 的 epilog() 读取 adm/etc/preload 列表逐个 call_other(file,'??') 拉起。映射为服务注册中心(Nacos/Consul)+显式服务清单。
- **call_out 自重排定时器**：natured 用 call_out('update_day_phase', delay) 自我重排实现昼夜循环；adsd/ftpd/dns_master 同模式。一次 call_out 在回调末尾再次 call_out 形成循环。映射为分布式定时任务调度器(如 Celery beat / XXL-Job)。
- **heart_beat 对象级心跳**：每个 living 对象有独立 heart_beat，fight_ob() 触发 set_heart_beat(1)，驱动在心跳间隔回调 attack()→COMBAT_D->fight()。这是 per-object 的周期 tick。映射为事件驱动循环/Actor 模型，跨节点需分布式调度。
- **securityd 安全中枢 + euid/status ACL**：securityd 经 master.c 的 valid_write/valid_seteuid/valid_read 驱动钩子接入，以 euid(user id)与 status(巫师等级)二元组做 trusted/exclude 路径回溯 ACL，状态 save 到 /data/securityd.o。映射为统一鉴权服务(JWT/OAuth2)+RBAC+策略缓存。
- **F_DBASE 属性中枢**：所有 daemon 继承 F_DBASE，以 set/query/add 操作一棵共享 mapping 作为配置与运行时状态树(如 channeld 的 channels 映射、securityd 的 wiz_status)。映射为配置中心(Apollo/Nacos)+分布式缓存(Redis)。
- **F_SAVE .o 文件持久化**：securityd 继承 F_SAVE，query_save_file() 返回 /data/securityd.o，create 时 restore、remove 时 save。映射为数据库持久化+对象关系映射。

## 痛点
- 单进程强耦合无隔离: 所有 daemon 共享同一地址空间与事件循环，combatd 抛错可拖垮整个 MUD，无熔断降级机制
- 同步阻塞调用链: call_other 同步执行，combatd.do_attack 内链式回调 SKILL_D->hit_ob、weapon->hit_ob、armor->hit_by，无超时无重试，长链路放大延迟
- 全局可变状态强一致难: moneyd.query_total_xkx_cashflow 每次 O(n) 遍历所有金钱对象求和做总量调控；securityd.wiz_status 纯内存态，分布式下无法直接共享
- 定时器单点不可扩展: call_out/heart_beat 绑定单进程事件循环，natured 的昼夜 tick、moneyd 的现金校验均为单点，水平扩展时无协调(需分布式锁/选主)
- 安全钩子迁移成本高: securityd 依赖 MudOS 驱动的 valid_write/valid_seteuid 回调，文件路径回溯式 ACL 在网络服务化后无对应物，鉴权模型需整体重建
- 无显式接口契约: daemon 方法签名散落各处，靠 include 头文件与注释约定，调用方与被调方无类型约束，重构易引入运行时错误
- 守护进程状态持久化弱: 仅 securityd 用 F_SAVE，channeld 频道配置等纯内存，宕机即丢

## 应保留思想
- 宏路径解耦服务定位的思想: globals.h/daemons.h 用常量引用 daemon 路径而非硬编码，迁移为服务注册中心+服务发现，调用方只依赖服务名不依赖地址
- 按领域拆分的无状态服务边界: combatd/combat/moneyd/economy/securityd/auth 等天然的服务划分，直接对应微服务领域
- securityd 的 trusted/exclude 双向 ACL + 审计日志思想: 黑白名单并存 + grant_log/WRITE_LOG 审计，迁移为现代授权策略(ABAC)+操作审计
- moneyd 全局货币总量调控(MAX_CASHFLOW_ALLOWED): 经济系统通胀控制思想，迁移为可配置的经济规则引擎
- natured 事件驱动的时间相位系统: day_phase 配置表+event_fun 回调，迁移为数据驱动的世界事件调度器，契合多题材 UGC 世界时间推进
- preload 显式服务清单: 启动时声明依赖的守护进程列表，迁移为服务依赖描述+健康检查清单
- channeld 的频道过滤+中继注册(register_relay_channel): 频道订阅与额外监听者模式，迁移为 pub/sub topic 路由

## 应废弃设计
- 共享地址空间的单进程模型——微服务按领域拆分独立部署
- call_other 同步直接对象引用——改为 RPC/消息异步通信
- heart_beat 驱动级全局心跳——改为事件总线+调度器，去除隐式全局 tick
- euid 字符串+巫师等级权限模型——改为现代 RBAC/JWT/OAuth2
- save_object/restore_object 的 .o 文件持久化——改为关系/文档数据库
- input_to 阻塞式 telnet 登录状态机——改为 Web 异步鉴权流程
- master.c 的 valid_* 驱动内置钩子耦合——改为中间件/网关层统一鉴权
- 全局 users()/livings()/children() 遍历——改为分片查询+聚合

## 复杂度热点
- combatd.c (1098行): do_attack 单函数近700行，AP/DP/PP多层概率判定、skill/weapon/armor多重回调嵌套，是整个系统最复杂的逻辑核心，拆为微服务时需重构为规则引擎+伤害流水线
- securityd.c (786行): valid_write/valid_read 对文件路径逐级回溯 implode(path[0..i]) 做 trusted/exclude 双向 ACL，逻辑重复且性能开销大，迁移后需改 RBAC+策略缓存
- logind.c (781行): 9个 input_to 回调构成的线性登录状态机，分支多且与连线对象/角色对象的双重对象生命周期管理纠缠，是迁移到 Web 鉴权流程时最需重写的部分
- moneyd.c query_total_xkx_cashflow: 对全部金钱对象做 O(n) 遍历求和且每次支付都查询，高并发下是瓶颈，分布式下需改为账本服务+异步汇总
- channeld.c do_channel: 频道过滤 filter_array(users())+门派判定+emote 解析+intermud 转发混在单函数，分布式 pub/sub 时需解耦为 topic 路由层

## 关键文件
- /home/gukt/github/xkx2001-utf8/adm/daemons/combatd.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/securityd.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/logind.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/channeld.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/moneyd.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/natured.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/chard.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/commandd.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/virtuald.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/profiled.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/updated.c
- /home/gukt/github/xkx2001-utf8/adm/single/master.c
- /home/gukt/github/xkx2001-utf8/feature/attack.c
- /home/gukt/github/xkx2001-utf8/feature/dbase.c
- /home/gukt/github/xkx2001-utf8/feature/save.c
- /home/gukt/github/xkx2001-utf8/include/globals.h
- /home/gukt/github/xkx2001-utf8/include/daemons.h
- /home/gukt/github/xkx2001-utf8/adm/etc/preload
- /home/gukt/github/xkx2001-utf8/adm/etc/nature/day_phase
- /home/gukt/github/xkx2001-utf8/config.xkx
