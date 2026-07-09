# 现状分析·命令系统与权限模型（XKX MUD / LPC）

## 概述
XKX 命令系统是 MudOS 驱动级的"动词+参数"分发管线。玩家输入经 process_input(alias/历史/洪水控制/编码转换) 预处理后，由 command_hook 这个 catch-all 动作钩子按"移动捷径→命令→emote→频道"顺序回退解析。命令解析依赖 COMMAND_D.find_command 按"路径数组"反向扫描目录(rehash 缓存)，再由 SECURITY_D.valid_cmd 二次授权。权限分三层：路径表(command.h 定义的 ADM/ARC/WIZ/PLR_PATH 等按 wizhood 分配) 决定可搜索目录；valid_cmd 的 authorized_cmds/exclude_cmds ACL 决定可执行；valid_read/write 控制文件读写。命令分 std(玩家)/usr(工具)/skill(功夫)/imm/wiz/arch/adm(巫师) 七级目录。全系统约 230 个命令文件，全部实现统一 main(object me, string arg) 契约。

## 现有模式
- **动词-文件映射 + rehash 缓存**：commandd.c 维护 mapping search（dir->动词列表）缓存，rehash() 用 get_dir 扫描目录剥离 .c 后缀。缓存从不自动失效，仅 /cmds/arch/rehash.c 手动刷新，新增命令需重载或重启驱动
- **路径数组分级路由**：find_command(verb, path) 反向遍历玩家 path 数组，返回首个命中目录的文件路径。path 既是搜索范围又是权限边界，路径顺序决定优先级（后者覆盖前者）
- **main(object,string) 统一入口契约**：每个命令文件 inherit F_CLEAN_UP 并实现统一契约 int main(object me, string arg) 与可选 int help(object me)，由 call_other(file,"main",me,arg) 调用。命令对象为驱动缓存的不可变单例
- **回退式解析链**：command_hook 按 出口捷径->命令->emote->channel 顺序依次尝试，任一命中即返回，构成隐式中间件链
- **路径=权限主闸门**：按 wizhood 等级（player/immortal/apprentice/.../admin 共 10 级）在 enable_player 中用大 switch 分配 *_PATH（command.h 定义 ADM/ARC/WIZ/APR/IMM/PLR/UNR/NPC_PATH），决定可搜索目录集合
- **valid_cmd 二次授权 ACL**：securityd.valid_cmd 用 authorized_cmds（dir->等级列表）+ exclude_cmds（dir->euid/等级黑名单）双层 ACL，拒绝优先于允许，但 cmds/std|skill|usr 被硬编码 return 1 绕过
- **对象内洪水控制 + 历史**：process_input 内置 cnt 计数器，超 3x 阈值触发天雷踢出，超阈值扣血，由 heart_beat 调 clear_cmd_count 复位；与历史记录(10 环形)混编
- **双层 alias 机制**：个人 alias（feature/alias.c mapping alias，支持 $1/$* 位置参数，上限 40）在 process_input 先展开，再交 ALIAS_D->process_global_alias 展开 n/e/i/' 等硬编码全局别名
- **wiz 登录 IP 白名单**：状态存 WIZLIST 文件（id 等级 登录IP正则），valid_wiz_login 用 regexp 校验来源 IP，set_status 仅 /cmds/adm/promote 或 ROOT 可调用

## 痛点
- 路径即权限过于粗粒度：整个目录授予/剥夺，无单命令级权限；cmds/std|skill|usr 被 valid_cmd 硬编码 return 1 绕过 ACL
- securityd.valid_cmd 存在拼写 bug：第 757 行 authorized_cmds["cmd"]（单数）应为 "cmds"，导致按 status 授权的分支静默失效；且 authorized_cmds 默认值在两处硬编码（第 48-53 行与 722-727 行回退）易漂移
- 命令动词大量重复：cmds/imm 与 cmds/wiz 间 clone/cat/cp/mv/rm/mkdir/rmdir/dest/snoop/update/summon/full 等 12 个同名，仅靠 path 顺序隐式覆盖，无冲突检测或显式优先级
- command_hook 是耦合所有路由的 god-function：出口捷径、命令分发、emote、channel 四类逻辑全塞一处，移动捷径属领域逻辑却混入通用路由
- process_input 单函数承载洪水控制+历史+Big5转码+个人alias+全局alias 五职责，且 disable_player 注释说要靠 alias.c 阻断但实际阻断机制脆弱（依赖 quit/forced 临时标志）
- commandd.c 的 search 缓存是进程内可变全局状态，无失效信号；新增/删除命令需手动 rehash 或重启驱动
- enable_player 的 wizhood->path 映射是硬编码 switch，新增等级或调整权限需改代码而非改配置
- 洪水控制基于对象内 cnt 计数器，无全局视角，分布式部署无法共享限流状态
- 编码转换 Big5->GB 内嵌在每条输入处理路径，内核无编码无关层
- force_me 依赖 previous_object 的 ROOT_UID 作为唯一授权凭证，特权逃逸通道脆弱且无审计
- alias 全局映射硬编码于 aliasd.c，运行时不可配置；个人 alias 与全局 alias 职责重叠却分两套存储与展开逻辑

## 应保留思想
- 动词->handler->main(me,arg) 的统一命令契约：每个命令是无状态函数签名 main(actor, args)，新架构应保留为 Action(ctx)->result 契约，便于测试与发现
- 每命令自带 help() 自文档化机制，应演进为命令元数据（usage/examples/category）随注册一并声明
- 解析回退链思想（捷径->命令->emote->channel）合理，应保留为显式有序中间件管线而非丢弃
- path-as-capability-set 把主体可用命令空间建模为集合，是良好的能力安全原语，需从目录级细化到单命令级授予
- ACL 中 exclude-before-trust（拒绝优先）的授权顺序是正确的安全原则，新权限服务应继承
- 路径限定搜索 + 二次授权的纵深防御思路有价值，应统一为单一策略引擎而非保留两套
- 历史回溯(!/!N) 与带位置参数($1/$*)的 alias 是 MUD 聊天式体验的实用 UX，应保留到新输入预处理器中间件
- wiz 登录 IP 白名单 + 操作审计日志(CMD_LOG/READ_LOG/WRITE_LOG/promotion_log) 的安全实践应保留并增强为结构化审计

## 应废弃设计
- enable_player 中硬编码的 *_PATH switch（command.h 的 8 套常量），改为权限服务按角色+显式授予/撤销计算可用命令集
- commandd.c 的 rehash+get_dir 目录扫描缓存，改为命令自注册的元数据登记表（DB 持久化，含动词/别名/所需权限/分类/冷却）
- securityd.c 的 valid_cmd ACL（含 authorized_cmds["cmd"] 拼写 bug 与硬编码目录），改为统一策略引擎按 (主体,动作,资源) 求值
- command_hook 单一巨函数，拆为显式中间件管线：解析->预处理(alias/history/限流)->路由->授权->执行->后处理(度量/审计)
- 对象内 cnt 洪水计数器+天雷，改为网关层全局令牌桶限流
- process_input 内联的 Big5->GB 转码，下移到 WebSocket 传输层，内核统一 UTF-8
- driver 单例命令对象 + call_other，改为无状态 handler 函数/类按请求实例化或池化
- force_me 的 ROOT_UID 后门，改为带审计日志的显式特权动作 API
- 命令_hook 内嵌的移动捷径（动词=出口名），下沉为 go 命令对多词动词的处理或注册为真实 alias（global_alias 已部分覆盖，此处冗余）
- 个人 alias + 全局 alias 双存储，合并为单一分层 alias 服务（系统默认 alias + 用户可覆盖）

## 复杂度热点
- /home/gukt/github/xkx2001-utf8/feature/command.c 的 command_hook + enable_player 巨型 switch：输入解析、移动捷径、命令分发、emote/channel 回退全部耦合
- /home/gukt/github/xkx2001-utf8/adm/daemons/securityd.c 的 valid_cmd：双默认值、硬编码目录、authorized_cmds["cmd"] 拼写 bug、与 command.h 路径表重复定义
- /home/gukt/github/xkx2001-utf8/feature/alias.c 的 process_input：洪水控制、历史、Big5 转码、个人 alias、全局 alias 调用五职责混合
- /home/gukt/github/xkx2001-utf8/adm/daemons/commandd.c 的 find_command + rehash 缓存：可变全局状态、无自动失效、新增命令需 /cmds/arch/rehash 手动刷新
- /home/gukt/github/xkx2001-utf8/cmds/imm 与 /home/gukt/github/xkx2001-utf8/cmds/wiz 间 12 个同名动词（clone/cat/cp/mv/rm/mkdir/rmdir/dest/snoop/update/summon/full），仅靠路径顺序决定覆盖关系，无显式优先级或冲突检测

## 关键文件
- /home/gukt/github/xkx2001-utf8/feature/command.c
- /home/gukt/github/xkx2001-utf8/feature/alias.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/commandd.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/aliasd.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/securityd.c
- /home/gukt/github/xkx2001-utf8/include/command.h
- /home/gukt/github/xkx2001-utf8/adm/simul_efun/wizard.c
- /home/gukt/github/xkx2001-utf8/cmds/usr/alias.c
- /home/gukt/github/xkx2001-utf8/cmds/std/go.c
- /home/gukt/github/xkx2001-utf8/cmds/wiz/clone.c
- /home/gukt/github/xkx2001-utf8/inherit/char/char.c
- /home/gukt/github/xkx2001-utf8/clone/user/user.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/emoted.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/channeld.c
