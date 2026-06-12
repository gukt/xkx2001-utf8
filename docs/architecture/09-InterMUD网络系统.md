# InterMUD 网络系统

## 目录

- [概述](#概述)
- [InterMUD 协议架构](#intermud-协议架构)
- [核心网络服务](#核心网络服务)
- [HTTP 服务](#http-服务)
- [邮件系统](#邮件系统)
- [网络安全](#网络安全)
- [与其他系统的关联](#与其他系统的关联)

---

## 概述

《侠客行》MUD 的 InterMUD 网络系统是一套完整的跨 MUD 通信基础设施，允许本站点与其他运行相同或兼容 MudOS/FluffOS 驱动的 MUD 站点进行实时数据交换。该系统实现了经典的 **I3（Intermud-3）协议** 的一个子集，同时引入了《侠客行》特有的安全控制和中文适配。

InterMUD 系统的核心目标包括：

1. **MUD 发现与注册**：自动发现网络上的其他 MUD 站点，维护动态的 MUD 列表
2. **跨站通信**：支持玩家跨 MUD 私聊（tell）、频道聊天（channel）、远程查询（finger/locate/who）
3. **跨站邮件**：允许玩家向其他 MUD 站点的玩家发送邮件
4. **Web 服务**：内置 HTTP 服务器，提供对外的 Web 访问接口
5. **安全隔离**：通过白名单机制和地址验证防止伪造和攻击

所有网络守护进程集中位于 `/adm/daemons/network/` 目录下，配置文件位于 `/include/net/` 目录。系统在驱动启动时由 `master.c` 的 `epilog()` 预加载初始化。

---

## InterMUD 协议架构

### I3 协议在《侠客行》中的实现

《侠客行》的 InterMUD 实现基于 TMI-2 Mudlib 的 UDP 协议栈，后经 Annihilator@ES2 移植并针对中文 MUD 环境进行了适配。协议采用 **UDP 数据报** 作为底层传输机制，所有跨 MUD 通信都封装在固定的包格式中。

#### 数据包格式

每个 UDP 数据包遵循如下格式：

```
@@@<服务名>||<键1>:<值1>||<键2>:<值2>||...@@@\n
```

以 `@@@` 作为起始和结束标记，`||` 分隔字段，每个字段为 `键:值` 对。例如，一个典型的 ping 请求包如下：

```c
"@@@ping_q||NAME:xkx||PORTUDP:5559@@@\n"
```

在 `dns_master.c` 的 `read_callback()` 中，系统对接收到的数据包进行解析：

```c
void read_callback(int sock, string msg, string addr)
{
    string func, rest, *bits, name, arg;
    mapping args;
    int i, port;

    // 提取服务名
    if( !sscanf(msg, "@@@%s||%s@@@%*s", func, rest)) {
        if (!sscanf(msg, "@@@%s@@@%*s", func)) return;
        rest = "";
    }

    // 解析参数为 mapping
    bits = explode(rest, "||");
    args = allocate_mapping(sizeof(bits));
    i = sizeof(bits);
    while (i--)
        if (bits[i] && sscanf(bits[i], "%s:%s", name, arg) == 2)
            args[name] = arg;
    args["HOSTADDRESS"] = addr;
    // ...
}
```

#### 服务路由

解析后的数据包根据 `<服务名>` 路由到 `/adm/daemons/network/services/` 目录下对应的处理文件。`dns_master.c` 中的核心路由逻辑：

```c
if (file_size(AUX_PATH + func + ".c") > 0)
    (AUX_PATH + func)->incoming_request(args);
```

其中 `AUX_PATH` 定义为 `/adm/daemons/network/services/`。

### DNS 主控如何管理 MUD 列表和地址解析

`dns_master.c` 是整个 InterMUD 系统的核心，承担以下职责：

#### 1. 自举与 MUD 列表获取

系统启动时，`create()` 函数完成初始化：

```c
void create()
{
    my_port = SRVC_PORT_UDP(mud_port());   // 游戏端口 + 4
    muds = allocate_mapping(MUDS_ALLOC);   // 已知 MUD 数据库
    mud_svc = allocate_mapping(MUDS_ALLOC); // 各 MUD 支持的服务
    xkx_muds = LISTNODES;                   // 硬编码的白名单节点
    this_host = ([ /* 自身信息 */ ]);
    if (startup_udp()) init_database();
}
```

`init_database()` 向配置好的引导服务器（`LISTNODES`，定义于 `net/config.h`）发送启动消息和 MUD 列表请求：

```c
void init_database()
{
    message = sprintf("@@@%s%s@@@\n", DNS_STARTUP, start_message());
    list = values(LISTNODES);
    i = sizeof(list);
    while(i--) {
        sscanf(list[i], "%s %d", bootsrv[0], bootsrv[1]);
        send_udp(bootsrv[0], bootsrv[1], message);
        MUDLIST_Q->send_mudlist_q(bootsrv[0], bootsrv[1]);
    }
    call_out("init_database", 60);  // 每 60 秒重试
}
```

#### 2. MUD 信息数据库

`dns_master` 维护三张核心表：

| 表名 | 类型 | 用途 |
|------|------|------|
| `muds` | `mapping` | 存储每个已知 MUD 的元信息（名称、地址、端口、版本等） |
| `mud_svc` | `mapping` | 存储每个 MUD 支持的服务及协议类型（TCP/UDP） |
| `xkx_muds` | `mapping` | 白名单，仅接受来自列表中地址和端口的通信 |

`set_mud_info()` 用于添加或更新 MUD 信息。关键的安全检查逻辑确保只有白名单中的 MUD 才能被加入数据库：

```c
void set_mud_info(string name, mapping junk)
{
    // 白名单验证：只接受 LISTNODES 中定义的站点
    if (stringp(addr = xkx_muds[junk["NAME"]])) {
        if (sscanf(addr, "%s %s", addr, port) != 2) return;
        if (addr != junk["HOSTADDRESS"]) return;
        if (port != junk["PORTUDP"]) return;
    } else return;
    // ...
}
```

#### 3. 心跳保活

`do_pings()` 每 30 分钟向所有已知 MUD 发送 ping 请求，连续 3 次未响应的 MUD 将被从数据库中移除：

```c
void do_pings()
{
    call_out("do_pings", PING_INTERVAL);  // 30 分钟
    mud_names = keys(muds);
    i = sizeof(mud_names);
    while (i--) {
        muds[mud_names[i]][DNS_NO_CONTACT]++;
        PING_Q->send_ping_q(muds[mud_names[i]]["HOSTADDRESS"],
                            muds[mud_names[i]]["PORTUDP"]);
        if (muds[mud_names[i]][DNS_NO_CONTACT] >= MAX_RETRYS)
            zap_mud_info(mud_names[i], 0);
    }
}
```

#### 4. 服务查询与协商

当新 MUD 加入数据库时，`dns_master` 会向其查询支持的服务（mail、finger、tell、rwho_q、gwizmsg），并通过 `support_q` / `support_a` 协议确定每项服务使用 TCP 还是 UDP：

```c
void support_q_callback(mapping info)
{
    // 根据对方回复更新 mud_svc[mud][service] 的协议标志
    // SVC_TCP | SVC_UDP | SVC_KNOWN | SVC_NO_TCP | SVC_NO_UDP
}
```

---

## 核心网络服务

`/adm/daemons/network/services/` 目录下包含了所有 InterMUD 协议的具体实现。以下逐个分析每个服务的职责、协议格式和请求/响应模式。

### 1. 启动与关闭服务

#### startup.c

`startup` 服务是 MUD 启动时发送给引导服务器的问候消息，携带本 MUD 的基本信息。它通常由 `dns_master` 的 `init_database()` 自动触发。

#### shutdown.c

`shutdown` 服务用于在 MUD 关闭时通知其他站点将其从数据库中移除。`dns_master` 的 `send_shutdown()` 遍历所有已知 MUD 发送关闭消息：

```c
void send_shutdown(string host, int port)
{
    DNS_MASTER->send_udp(host, port, "@@@shutdown||NAME:"+Mud_name()+
                         "||PORTUDP:"+udp_port()+"@@@\n");
}
```

接收方验证来源地址与数据库一致后，调用 `DNS_MASTER->zap_mud_info()` 删除该 MUD。

### 2. 心跳服务（ping_q / ping_a）

ping 是维持 MUD 网络存活的根本机制。

**ping_q（查询）**：

```c
void send_ping_q(string host, mixed port)
{
    DNS_MASTER->send_udp(host, port, "@@@ping_q||NAME:"+Mud_name()+
                         "||PORTUDP:"+udp_port()+"@@@\n");
}
```

**ping_a（应答）**：

收到 `ping_q` 后，被查询 MUD 回复 `ping_a`，并携带完整的 `start_message()` 信息（名称、中文名、版本、MUDLIB、主机、端口、时间、TCP 支持级别）。

```c
void incoming_request(mapping info)
{
    DNS_MASTER->send_udp(info["HOSTADDRESS"], info["PORTUDP"],
        "@@@ping_a" + DNS_MASTER->start_message() + "@@@\n");
}
```

`ping_a` 的接收方还会触发邮件队列检查：`MAIL_Q->check_for_mail(info["NAME"], 3)`。

### 3. MUD 列表服务（mudlist_q / mudlist_a）

**mudlist_q** 请求对方发送其已知的 MUD 列表。由 `dns_master` 在初始化和定期刷新（每 5 分钟）时发送。

**mudlist_a** 返回 MUD 列表，每个 MUD 的信息被编码为：

```
||<序号>:|NAME:<名称>|CNAME:<中文名>|HOST:<主机>|HOSTADDRESS:<IP>|PORT:<端口>|PORTUDP:<UDP端口>|MUDLIB:<库名>|TCP:<tcp级别>
```

由于 UDP 包大小限制，过长的列表会被拆分为多个包发送。接收方 `mudlist_a.c` 对每个条目进行白名单验证：

```c
old = LISTNODES;
if (!mapp(old[New["NAME"]])) return 0;  // 不在白名单中，丢弃
sscanf(old[New["NAME"]], "%s %*s", addr);
if (New["HOSTADDRESS"] != addr) return 0;  // 地址不匹配，丢弃
```

### 4. 支持查询服务（support_q / support_a）

用于协商两 MUD 之间某项服务支持的传输协议（TCP 或 UDP）。

**support_q** 发送方：

```c
DNS_MASTER->send_udp(host, port,
    "@@@support_q||NAME:"+Mud_name()+"||PORTUDP:"+udp_port()+
    "||CMD:<服务名>||ANSWERID:<序号>@@@\n");
```

**support_a** 接收方检查本地是否存在对应的 `.c` 文件，并回复 `SUPPORTED:yes` 或 `NOTSUPPORTED:yes`。`dns_master` 的 `support_q_callback()` 根据应答更新 `mud_svc` 标志位。

### 5. 跨 MUD 私聊（gtell）

`gtell.c` 实现了跨 MUD 的私密对话功能。

**发送**：

```c
void send_gtell(string mud, string wiz_to, object source, string msg)
{
    DNS_MASTER->send_udp(minfo["HOSTADDRESS"], minfo["PORTUDP"],
        "@@@gtell||NAME:"+Mud_name()+"||PORTUDP:"+udp_port()+
        "||WIZTO:"+wiz_to+"||WIZFROM:"+capitalize(geteuid(source))+
        "||CNAME:"+source->name(1)+"||MSG:"+msg+"@@@\n");
}
```

**接收与处理**：

收到 `gtell` 后，系统验证发送方地址是否与数据库一致。若不一致，判定为伪造消息，记录日志并发送 `warning` 回执。验证通过后，调用 `TELL_CMD->remote_tell()` 将消息投递给本地目标玩家，并通过 `affirmation_a` 向发送方确认送达。

```c
if( TELL_CMD->remote_tell(info["CNAME"], info["WIZFROM"], info["NAME"],
    info["WIZTO"], info["MSG"]) )
    reply = "你告诉...";
else
    reply = "没有这个人……。\n";

(AUX_PATH+"affirmation_a")->send_affirmation_a(..., reply, "gtell");
```

### 6. 跨 MUD 频道（gchannel / gwizmsg）

`gchannel.c` 和 `gwizmsg.c` 实现了跨 MUD 的频道广播，分别用于普通频道和巫师频道。

两者的核心发送逻辑类似：

```c
void send_msg(string channel, string id, string name, string msg, int emoted, mixed filter)
{
    names = keys(svcs);
    while(i--)
        if (names[i] != mud_nname() && evaluate(filter, muds[names[i]])) {
            DNS_MASTER->send_udp(minfo["HOSTADDRESS"], minfo["PORTUDP"],
                "@@@gchannel||NAME:"+Mud_name()+"||PORTUDP:"+udp_port()+
                "||USRNAME:"+capitalize(id)+"||CNAME:"+name+
                "||MSG:"+msg+"||CHANNEL:"+channel+
                (emoted?"||EMOTE:1":"")+"@@@\n");
        }
}
```

接收方验证来源后，调用 `CHANNEL_D->do_channel()` 将消息注入本地频道系统。这使得不同 MUD 的玩家可以在同一频道中实时聊天。

### 7. 远程玩家查询（gfinger_q / gfinger_a）

`gfinger` 允许玩家查询其他 MUD 上某个用户的资料。

**查询方**：

```c
void send_gfinger_q(string mud, string wiz, object them)
{
    DNS_MASTER->send_udp(minfo["HOSTADDRESS"], minfo["PORTUDP"],
        "@@@gfinger_q||NAME:"+Mud_name()+"||PORTUDP:"+udp_port()+
        "||PLAYER:"+wiz+"||ASKWIZ:"+them->query("id")+"@@@\n");
}
```

**应答方**：

收到请求后，调用本地 `FINGER_D->finger_user()` 获取玩家信息，并通过 `gfinger_a` 回复。

### 8. 远程 who（rwho_q / rwho_a）

`rwho` 服务提供跨 MUD 的在线玩家列表查询，同时被 `mudlist.c` 用于收集各站点的在线人数。

**rwho_q** 收到请求后，根据 `ASKWIZ` 字段判断请求类型：

- 若 `ASKWIZ == DNS_RWHO_A`，返回简略统计：`sprintf("%d/%d", sizeof(users()), uptime())`
- 否则，调用 `WHO_CMD->main()` 生成格式化的 who 列表

**rwho_a** 缓存各 MUD 的在线人数和运行时间，每 60 秒刷新一次，供 `mudlist` 命令展示：

```c
void refresh_cache()
{
    call_out("refresh_cache", 60);
    muds = keys(mud_list);
    while(i--) {
        this_object()->set(mud_list[muds[i]]["NAME"]+"/UPTIME", -1);
        (AUX_PATH+DNS_RWHO_Q)->send_rwho_q(muds[i], this_object(), "");
    }
}
```

### 9. 玩家定位（locate_q / locate_a）

`locate` 服务用于在全网搜索某个玩家当前所在的 MUD 站点。

**查询方**（`locate_q.c`）：

向所有已知 MUD 广播 `locate_q` 请求：

```c
void send_locate_q(string who)
{
    i = sizeof(muds = keys(info=DNS_MASTER->query_muds()));
    while(i--) {
        DNS_MASTER->send_udp(info[muds[i]]["HOSTADDRESS"],
            info[muds[i]]["PORTUDP"],
            "@@@locate_q||NAME:"+Mud_name()+"||PORTUDP:"+udp_port()+
            "||TARGET:"+lower_case(who)+"||ASKWIZ:"+this_player()->query("id")+
            "@@@\n");
    }
}
```

**应答方**：

在本地搜索目标玩家，若找到且未达到隐身等级 10，则回复 `LOCATE:YES`；否则回复 `LOCATE:NO`。

玩家通过 `locate` 命令触发全网搜索：

```c
mixed main(object me, string arg)
{
    LOCATE_Q->send_locate_q(arg);
    write("正在找寻，请稍候。\n");
    // ...
}
```

### 10. inetd 的端口监听和连接管理

`inetd.c` 是 TCP 服务的统一入口，负责监听外部 TCP 连接并将请求分发给对应的服务对象。

#### 服务注册

`inetd` 从 `/adm/etc/services` 文件加载服务映射：

```c
void load_services()
{
    file = read_file(INETD_SERVICES);
    lines = explode(file, "\n");
    for (i = 0; i < sizeof(lines); i++) {
        if (sscanf(lines[i], "%s %s", svc, path) == 2)
            service[svc] = path;
    }
}
```

#### 监听端口

`inetd` 在 `mud_port() + 5` 端口上创建 STREAM 类型的监听 socket：

```c
void create_listen_socket()
{
    listen_fd = socket_create(STREAM, "read_callback", "close_callback");
    socket_bind(listen_fd, (int)DNS_MASTER->get_mudresource(mud_nname(), "inetd"));
    socket_listen(listen_fd, "read_callback");
}
```

#### 连接握手协议

新连接建立后，`inetd` 与对方进行简单的文本握手：

1. **服务端**：接受连接后发送 `SERVICE?\n`
2. **客户端**（`open_service()`）：连接成功后收到 `SERVICE?\n`，回复请求的服务名和参数
3. **服务端**：根据服务名查表，将对应的服务对象设为 socket owner，调用 `service_request()`
4. **双方**：后续数据通过 `read_callback()` 和 `write_socket()` 交换

```c
void process_incoming(int fd)
{
    switch(sockets[fd]["service_status"]) {
        case AWAITING_CONNECT_ACK:
            if (msg == "SERVICE?\n") {
                write_socket(fd, sockets[fd]["service_desired"] + "\n");
                sockets[fd]["service_status"] = AWAITING_DATA;
                call_other(sockets[fd]["owner"], sockets[fd]["service_callback"], fd);
            }
            break;
        case AWAITING_SERVICE:
            svc = msg[0..-2];
            if (!service[parms[0]]) {
                write_socket(fd, "SERVICE NOT AVAILABLE\n");
                close_socket(fd);
            }
            service[svc]->dummy();
            sockets[fd]["owner"] = find_object(service[svc]);
            service[svc]->service_request(fd, parms[1..]);
            break;
    }
}
```

---

## HTTP 服务

《侠客行》内置了两个 HTTP 服务器实现：`http.c` 和 `http_d.c`，分别代表了不同时期的技术演进。

### http.c —— 经典 NCSA 风格服务器

`http.c` 是一个较为完整的 HTTP/1.0 服务器，由 Truilkan@Basis 和 Jacques 编写，2000 年由 sdong 移植到《侠客行》。

#### 核心特性

1. **标准端口监听**：在 `PORT_HTTP`（通常为 80 或配置端口）上监听 TCP 连接
2. **GET/POST 支持**：处理标准的 HTTP GET 和 POST 请求
3. **虚拟目录映射**：
   - `/` 或绝对路径映射到 `DIR_WWW`
   - `/~user/` 映射到该玩家的个人主页目录
   - `/user/name/` 同样映射到玩家主页
4. **CGI Gateway 支持**：`DIR_WWW_GATEWAYS` 目录下的对象可以通过 `gateway(args)` 方法动态生成内容
5. **自动 `.html` 到 `.c` 映射**：若请求的 `.html` 文件不存在，尝试调用同名 `.c` 文件的 `gateway()`
6. **NCSA 格式日志**：访问日志记录在 `LOG_HTTP` 中，格式兼容标准 httpd 日志分析工具
7. **域名反向解析**：通过 `resolver.c` 将客户端 IP 解析为主机名

#### 请求处理流程

```c
static void read_callback(int fd, string str)
{
    request = explode(replace_string(str, "\r", ""), "\n");
    line0 = request[0];
    sscanf(line0, "%s %s %s", cmd, file, args);
    switch(lower_case(cmd)) {
        case "get":  do_get(fd, file, line0);  break;
        case "post": do_post(fd, file, url, line0); break;
        default:     http_error(fd, bad_cmd, "400 Bad Request"); break;
    }
}
```

`do_get()` 的核心逻辑包括路径转换、权限检查、目录索引、文件读取和 gateway 调用。

### http_d.c —— Lima 风格现代化服务器

`http_d.c` 是较晚引入的 HTTP/1.1 风格服务器，采用 `SOCKET` 对象和 binary socket 模式，支持大文件分块传输。

#### 改进之处

1. **Binary Socket**：支持传输非文本内容（如图片）
2. **Write Callback**：通过 `set_write_callback()` 实现大文件的流式传输
3. **HTTP/1.1 响应头**：发送标准的 `Date`、`Server`、`Connection`、`Content-Type` 头
4. **Form 解析**：内置 `form_parse()` 函数，支持 POST 数据的 URL decode 和表单解析
5. **安全 CGI 目录**：`scgi/` 前缀映射到 `SECURE_CGI_DIR`，与普通 CGI 分离

#### 动态内容生成

对于 `.c` 扩展名的请求，`http_d.c` 调用该对象的 `main()` 方法，可传入解析后的表单参数：

```c
case "c":
    if(args)
        err = catch(result = call_other(file, "main", args));
    else
        err = catch(result = call_other(file, "main"));
    http_send(result+"\n", socket);
    break;
```

### HTTP 服务的作用

内置 HTTP 服务器使《侠客行》MUD 具备了以下能力：

- **对外展示**：无需额外 Web 服务器即可提供游戏介绍、玩家主页、排行榜等静态页面
- **动态接口**：通过 Gateway/CGI 机制，Web 页面可以实时查询游戏内部数据（如在线玩家、MUD 列表）
- **管理工具**：巫师可以通过 Web 界面执行部分管理操作
- **玩家个性化**：支持 `~/public_html/` 风格的个人主页

---

## 邮件系统

《侠客行》的邮件系统分为两个层次：**站内邮件**（由 `POSTAL_D` / `MAILBOX_D` 处理）和 **跨 MUD 邮件**（由 InterMUD 网络层处理）。

### 跨 MUD 邮件与站内邮件的区别

| 维度 | 站内邮件 | 跨 MUD 邮件 |
|------|----------|-------------|
| 协议 | 本地函数调用 | UDP（mail_q/mail_a）或 TCP（inetd + mail） |
| 守护进程 | `POSTAL_D`、`MAILBOX_D` | `mail_serv.c`、`netmail.c`、`ms.c`、`mail_q.c`、`mail_a.c` |
| 地址格式 | `player_id` | `player_id@mud_name` |
| 存储方式 | 直接写入玩家邮箱 | 先进入出站队列，异步发送 |
| 可靠性 | 即时投递 | 队列重试、分片传输、超时老化 |

### mail_serv.c 的实现

`mail_serv.c`（即 `ms.c` 的前身/变体）是一个基于 **TCP + inetd** 的邮件传输守护进程，使用 `INETD->open_service()` 建立到目标 MUD 的 TCP 连接。

#### 出站队列

待发邮件存储在 `mail_queue` mapping 中，以目标 MUD 名为键：

```c
mail_queue[mud] += ({ ([
    "recipient": who,
    "to": borg["to"],
    "cc": borg["cc"],
    "from": borg["from"],
    "subject": borg["subject"],
    "date": borg["date"],
    "message": borg["message"]
]) });
```

#### 出站流程

`flush_mail_queue()` 按顺序处理队列中的每个目标 MUD：

```c
void flush_mail_queue()
{
    outgoing = mail_queue[mqi[0]];
    id = INETD->open_service(mqi[0], "mail");
    // 建立 TCP 连接...
}
```

连接建立后的 `service_callback()` 发送邮件内容，使用 `%EOF%` 分隔每封邮件，使用 `%EOT%` 标记传输结束：

```c
void service_callback(int id)
{
    INETD->write_socket(id, lower_case(mud_name()) + "\n");
    for(i=0; i<sizeof(outgoing); i++) {
        INETD->write_socket(id, outgoing[i]["recipient"] + "\n");
        INETD->write_socket(id, implode(outgoing[i]["to"], " ") + "\n");
        INETD->write_socket(id, implode(outgoing[i]["cc"], " ") + "\n");
        INETD->write_socket(id, outgoing[i]["from"] + "\n");
        INETD->write_socket(id, outgoing[i]["subject"] + "\n");
        INETD->write_socket(id, outgoing[i]["date"] + "\n");
        INETD->write_socket(id, outgoing[i]["message"] + "\n");
        INETD->write_socket(id, EOF + "\n");
    }
    INETD->write_socket(id, EOT + "\n");
    INETD->close_socket(id);
}
```

#### 入站处理

`read_callback()` 累积接收到的数据，直到收到 `%EOT%\n` 后调用 `process_message()`。`process_message()` 解析每封邮件，将本地收件人投递给 `POSTAL_D`，对不存在的收件人发送退信（Mail Bounce）。

### UDP 邮件协议（mail_q / mail_a）

除了 TCP 方式，《侠客行》还实现了基于 UDP 的邮件传输，用于无法建立 TCP 连接的场景。

**mail_q** 将邮件内容分片发送（默认每片 512 字节），通过 `ENDMSG` 标记最后一包：

```c
package = "@@@mail_q||NAME:"+Mud_name()+"||PORTUDP:"+udp_port();
if (!mail_outgoing[mudname]["index"]) {
    package += "||WIZTO:"+outmsg["WIZTO"]+"||WIZFROM:"+outmsg["WIZFROM"];
    // ... 首部信息
}
package += "||MSG:"+outmsg["MSG"][index..index+MAIL_PACKET_SIZE];
package += "@@@\n";
```

**mail_a** 确认收到每一包，若发现丢包则发送 `RESEND:1` 请求重传。完整接收后，`netmail.c` 将 UDP 邮件格式转换为本地邮件格式，交由 `MAILBOX_D->send_mail()` 处理。

### 队列老化与错误处理

`mail_serv.c` 和 `ms.c` 都实现了队列老化机制：超过 7 天（`AGE_TIME = 604800`）未成功发送的邮件将被丢弃并记录日志。此外，若连接目标 MUD 失败，系统会向发件人发送退信通知。

### 玩家如何使用邮件

玩家通过 `/cmds/usr/` 下的邮件相关命令（如 `mail`、`post` 等，由 `POSTAL_D` 和 `MAILBOX_D` 支持）编写和阅读邮件。发送跨 MUD 邮件时，只需在收件人地址后加上 `@mud_name`，例如：

```
mail server@ln
```

邮件系统会自动识别 `@` 后的 MUD 名称，将邮件放入对应出站队列。

---

## 网络安全

### 远程 MUD 身份验证

《侠客行》采用 **白名单 + 地址绑定** 的双重验证机制，这是其区别于原版 TMI-2 协议栈的关键安全增强。

#### 1. 白名单机制

`net/config.h` 中硬编码了允许互联的 MUD 列表：

```c
#define LISTNODES ([ \
    "ZS" : "202.99.174.190 5559", \
    "LN" : "202.96.91.22 5559", \
    "KF" : "202.96.91.22 5682", \
])
```

`dns_master.c` 在接收任何 UDP 包时，首先检查发送方是否在白名单中：

```c
if (stringp(addr = xkx_muds[args["NAME"]])) {
    if (sscanf(addr, "%s %s", addr, port) != 2) return;
    if (addr != args["HOSTADDRESS"]) return;
    if (port != args["PORTUDP"]) return;
} else return;
```

不在 `LISTNODES` 中的 MUD，无论发送什么数据包都会被直接丢弃。

#### 2. 地址一致性验证

对于已在数据库中的 MUD，各服务处理请求时还会再次核对 `HOSTADDRESS`：

```c
minfo = DNS_MASTER->query_mud_info(info["NAME"]);
if (minfo && minfo["HOSTADDRESS"] != info["HOSTADDRESS"]) {
    // 伪造消息！
    dns_log("dns_fake", ...);
    DNS_MASTER->send_udp(info["HOSTADDRESS"], info["PORTUDP"],
        "@@@warning||MSG: Fake gtell msg ...@@@\n");
    return;
}
```

若检测到地址不一致，系统会：
- 在 `dns_fake` 日志中记录伪造事件
- 向伪造来源发送 `warning` 警告包
- 拒绝处理该请求

#### 3. ACCESS_CHECK 权限控制

所有网络服务函数开头都包含权限检查：

```c
#define ACCESS_CHECK(x) ((!x)||(geteuid((x)) == ROOT_UID))
```

这确保了只有 `ROOT_UID` 权限的对象（即系统守护进程）才能调用网络发送函数，防止普通玩家对象或恶意代码伪造跨站消息。

### 封禁机制在跨 MUD 通信中的作用

`BAN_D`（封禁守护进程）主要用于管理本 MUD 的 IP/账号封禁，而 InterMUD 层面的安全则主要依靠上述白名单和地址验证。

此外，部分玩家级别的封禁也会体现在跨站通信中：

- 在 `tell.c` 中，玩家可以设置 `env/block` 来屏蔽特定玩家或全部悄悄话，这一设置同样作用于跨 MUD 的 `gtell`：

```c
if (ob->query("env/block")=="ALL")
    return notify_fail(ob->name()+"现在不想和人说话。\n");
```

- `gchannel` 和 `gwizmsg` 中，消息内容会过滤掉 `|` 和 `@@@` 字符，防止注入攻击：

```c
msg = replace_string(msg, "|", "");
msg = replace_string(msg, "@@@", "");
```

---

## 与其他系统的关联

InterMUD 网络系统并非孤立存在，它与《侠客行》的多个核心子系统紧密协作。

### 与 [[01-架构总览]] 的关联

InterMUD 系统是《侠客行》整体架构的 **外部通信层**，与驱动层（MudOS socket efun）、MUDLIB 层和命令层形成垂直调用链。所有网络守护进程通过驱动提供的 `socket_create`、`socket_bind`、`socket_listen`、`socket_accept`、`socket_write`、`socket_read` 等 efun 与操作系统网络栈交互，这是架构总览中 "驱动-库-游戏逻辑" 三层模型的典型体现。

### 与 [[02-守护进程系统]] 的关联

InterMUD 守护进程本身就是守护进程系统的重要组成部分：

- `DNS_MASTER` 和 `INETD` 属于 **网络基础设施 Daemon**
- `mail_serv.c`、`netmail.c` 与 `POSTAL_D`、`MAILBOX_D` 协作完成邮件全链路
- `CHANNEL_D` 是 `gchannel` / `gwizmsg` 的下游消费者，跨站频道消息最终通过频道系统分发给本地玩家
- `FINGER_D` 为 `gfinger_q` 提供玩家数据查询接口

这些 Daemon 之间的调用关系体现了守护进程系统 "各司其职、标准接口" 的设计哲学。

### 与 [[07-多人交互系统]] 的关联

InterMUD 网络系统是多人交互系统的 **跨站延伸**：

- **`tell` 命令**：本地 tell 通过 `find_player()` 直接投递；跨站 tell 通过 `GTELL->send_gtell()` 经由 UDP 转发
- **`who` 命令**：本地 who 枚举 `users()`；`mudlist` 命令通过 `rwho` 协议聚合全网在线数据
- **`finger` 命令**：本地 finger 调用 `FINGER_D`；跨站 finger 触发 `gfinger_q`
- **`locate` 命令**：向全网广播 `locate_q`，汇总各站回复
- **频道聊天**：`CHANNEL_D->do_channel()` 同时处理本地和来自 `gchannel`/`gwizmsg` 的远程消息

可以说，InterMUD 网络系统让《侠客行》的 "多人交互" 突破了单一服务器的物理边界，形成了真正意义上的分布式 MUD 网络。

---

## 总结

《侠客行》的 InterMUD 网络系统是一个功能完整、架构清晰的跨 MUD 通信平台。它以 `dns_master.c` 为核心，通过 UDP 协议实现 MUD 发现、心跳保活、服务协商和轻量级消息传输，同时以 `inetd.c` 为 TCP 服务入口，支持邮件等大数据量传输。内置的 HTTP 服务器提供了对外的 Web 接口，而邮件系统则实现了站内与跨站邮件的统一管理。

安全方面，系统通过 `LISTNODES` 白名单和严格的地址验证，有效防止了伪造和未授权访问，这是中文 MUD 社区在互联实践中积累的重要经验。整个系统的设计充分体现了 LPC MUD 开发的典型模式：利用 MudOS 驱动提供的 socket efun，在 MUDLIB 层构建高可用的网络服务层，最终通过命令层向玩家暴露简洁的交互接口。
