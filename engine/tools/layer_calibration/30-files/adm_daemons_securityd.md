# adm_daemons_securityd 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/adm/daemons/securityd.c
- basename: adm_daemons_securityd
- 引擎侧/内容侧: 引擎侧（安全 daemon，平台级 fail-closed 代码）
- 总语义单元数: 24
- 各层计数: 层0=7  层1=0  层2=0  层3=17
- 层3 项: 17 项（见下表理由）

## 语义单元标注

| 语义单元 | 层 | 引擎侧/内容侧 | 理由 |
|---|---|---|---|
| wiz_levels 数组（10 个等级常量） | 层0 | 引擎侧 | 纯数据声明，wizard 等级枚举 |
| trusted_write 默认映射 ({tmp:["(admin)"]}) | 层0 | 引擎侧 | 纯数据声明，目录写权限 ACL |
| authorized_cmds 默认映射（4 个命令目录） | 层0 | 引擎侧 | 纯数据声明，命令目录权限 ACL |
| exclude_read / exclude_write / exclude_cmds 默认空映射 | 层0 | 引擎侧 | 纯数据声明，排除 ACL 初始值 |
| trusted_read 默认空映射 | 层0 | 引擎侧 | 纯数据声明，信任读 ACL 初始值 |
| query_save_file() 返回 DATA_DIR+"securityd" | 层0 | 引擎侧 | 纯数据声明，存档路径常量 |
| create() 中的 seteuid(ROOT_UID) | 层0 | 引擎侧 | 纯初始化数据（root 权限声明） |
| create() 解析 WIZLIST 构建 wiz_status/wiz_sites | 层3 | 引擎侧 | 文件 IO + sscanf 解析 + 循环，图灵完备过程逻辑 |
| remove() -> save() | 层3 | 引擎侧 | 生命周期钩子，过程逻辑 |
| query_wizlist() 生成 wizlist 字符串 | 层3 | 引擎侧 | 遍历 keys + 字符串拼接，过程逻辑 |
| query_wizstatus() 返回 wiz_status 映射 | 层3 | 引擎侧 | 运行时状态查询，依赖 create() 构建的状态 |
| get_wizlist() 返回 wiz_status keys | 层3 | 引擎侧 | 运行时状态查询 |
| valid_wiz_login(ob, site) | 层3 | 引擎侧 | regexp 正则匹配 wiz_sites[euid]，过程逻辑 |
| get_status(ob) | 层3 | 引擎侧 | object/string 双分支 + 查找 + 回退链，过程逻辑 |
| get_wiz_level(ob) / cmp_wiz_level(ob, lvl) | 层3 | 引擎侧 | 依赖 get_status + member_array，过程逻辑 |
| set_status(ob, status, sites, promoter) | 层3 | 引擎侧 | ROOT_UID+promote 双权限门 + 三分支取 uid + 删除/设置分支 + 日志 + save |
| query_cmdlist() / query_exclude_cmdlist() | 层3 | 引擎侧 | 遍历 keys + 路径修正 + sort_array + 字符串拼接，过程逻辑 |
| query_readlist() / query_writelist() | 层3 | 引擎侧 | 同上模式，过程逻辑 |
| query_exclude_readlist() / query_exclude_writelist() | 层3 | 引擎侧 | 同上模式，过程逻辑 |
| set_cmdlist / set_exclude_cmdlist（2 函数） | 层3 | 引擎侧 | ROOT_UID 权限门 + 路径修正 + check_redundancy + map_delete/赋值 + save |
| set_readaccess / set_writeaccess（2 函数） | 层3 | 引擎侧 | 同 set_cmdlist 模式 + grant_log 日志 |
| set_exclude_readaccess / set_exclude_writeaccess（2 函数） | 层3 | 引擎侧 | 同 set_cmdlist 模式 |
| check_redundancy(wizlist) | 层3 | 引擎侧 | 双重循环去重检查，过程逻辑 |
| valid_write(file, user, func) | 层3 | 引擎侧 | 路径反向搜索 exclude/trusted ACL + euid/status 双匹配 + 特例白名单，不可谓词化 |
| valid_read(file, user, func) | 层3 | 引擎侧 | 路径反向搜索 + /data/ /log/ 等白名单 + adm/cmds euid 放行，不可谓词化 |
| valid_cmd(file, user, func) | 层3 | 引擎侧 | 路径反向搜索 exclude_cmds/authorized_cmds + cmds/std/skill/usr 直放行，不可谓词化 |
| valid_seteuid(ob, uid) | 层3 | 引擎侧 | 四重条件分支（uid==0 / getuid / ROOT_UID / adm 路径 / admin 提权），不可谓词化 |

## 备注

- securityd 是平台级 fail-closed 安全守护进程（CLAUDE.md 架构不变量：themed 治理是平台级 Python）。
- ACL 数据本身（wiz_levels / trusted_write / authorized_cmds 等默认映射）可标层0，但运行时通过 set_*access 修改并 save 持久化，实际状态是动态的。
- valid_write/valid_read/valid_cmd/valid_seteuid 四个核心校验函数是 driver master 调用钩子，逻辑复杂（路径反向搜索 + 双重身份匹配 + 特例白名单），当前层1 谓词集（attr_lt/present_npc/has_flag 等）无法表达，必须层3。
- 新引擎预期：这些校验逻辑演变为 ECS System 中的 PermissionService（CLAUDE.md：CapabilityToken/PermissionService 等安全相关模块必须类型完整），Python 原生实现而非 RestrictedPython 逃生舱，但语义上仍属层3。
- set_status 中 `/cmds/adm/promote` 单对象权限门是硬编码安全让步，新引擎应改为 CapabilityToken 机制。
