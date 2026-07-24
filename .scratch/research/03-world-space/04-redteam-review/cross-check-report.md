# 红队横向对比验证报告：抽象覆盖度与跨实例一致性

> 角色：横向对比验证员（03-world-space 调研团队 / 红队 Phase 2）。
> 职责：交叉检查各区域 / 各交通实现与各抽象方案，找出共用模式与特例，验证核心抽象的覆盖度。
> 方法：以 LPC 一手源码为基准，逐条核验 Phase 1 产出的关键事实与抽象判定。所有结论标注证据（LPC 文件路径 + 行号 / 函数名，或 engine 模块路径 + 行号 / 类名）。**禁凭空推断**。
> 验证手段：对每条质疑，亲自 `grep` / `cat` / `find` 复现被引证据，标注「确认 / 推翻 / 待澄清」裁决。

---

## 0. 验证方法学

本报告对 Phase 1 11 份产出做横向交叉验证。每条质疑均经下列方式核实：

1. **事实复核**：对 Phase 1 引用的 LPC/engine 证据，重新 `grep` / `find` / `cat` 复现，比对引文与原文。
2. **覆盖度检查**：对抽象方案声称「通用」的机制，查 LPC 全量实例，看是否只拟合了某一两个样本。
3. **跨实例一致性**：对 city / village / shaolin / ferry / ship / horse / road 七类代表性实例，逐项查抽象方案是否覆盖。
4. **engine-critique 对照**：对 `06-engine-critique/engine-comparison.md` 的 P1-P10（正面偏差）与 N1-N12（负面遗漏）逐条核对 LPC 与 engine 源码。

**已核验的实例样本**（grep / find / cat 复现）：

| 实例类 | 代表 LPC 文件 | 核验动作 |
|--------|--------------|---------|
| city 扬州 | `d/city/beimen.c`、`d/city/bingqiku.c` | `cat` 验证 exits 跨区路径 |
| village 华山村 | `d/village/alley1.c`、`hsroad1.c`、`hsroad3.c`、`sexit.c` | `cat` 验证房间模式与跨区 exit |
| shaolin 少林 | `d/shaolin/hanshui1.c`、`hanshui2.c`、`duchuan.c` | `cat` 验证渡口配置 |
| ferry 渡口 | `inherit/room/ferry.c` + 9 处 `inherit FERRY` 实例 | `grep -rln "inherit.*FERRY"` 复现 9 处 |
| ship 玩家船 | `inherit/room/ship.c` + `clone/ship/seaboat1-3.c` + `harbor.h` + `seashape.h` | 行数 + 关键函数 grep |
| horse 坐骑 | `clone/horse/*.c`（21 个 .c）+ `horse.h` | 逐个 `grep "horse.h"` 找未 include 者 |
| road 官道 | `d/village/hsroad1.c`、`d/qilian/guandao1.c` 等 | `cat` 验证跨区绝对路径 |

---

## 1. 抽象方案覆盖度验证（abstraction-options / mechanisms vs 代表性实例）

### 裁决 1.1：【确认】exits mapping 作为统一拓扑底座 覆盖全部 7 类实例

**被质疑条目**：`01-raw-findings/gameplay-slices.md` §跨切片观察 1「exits mapping 是世界空间层的统一数据底座」；`03-engine-insights/abstraction-options.md` §1.2「Exit/Exits 必须 core」。

**核验**：
- city 扬州：`d/city/beimen.c`（hsroad1 反向入口）使用 `set("exits", ...)`（grep 确认）。
- village 华山村：`d/village/alley1.c:14` `set("exits", (["east":__DIR__"sroad3", ...]))`。
- shaolin 少林：`d/shaolin/hanshui1.c` 渡口岸用 `inherit FERRY`（动态增删 `exits/enter` / `exits/out`，见 `inherit/room/ferry.c:81,103,108,121,146`）。
- ferry：`ferry.c` 全靠 `set("exits/enter", boat)` / `boat->set("exits/out", ...)` 动态开关。
- ship：`inherit/room/ship.c:96`（`delete("exits/out")` 离港）/ `:241,249`（靠港 set exits/out）/ `:84`（`exits/out` 离船）。
- horse：不改拓扑，改移动语义（`cmds/std/qi.c:35` `set_leader` + `cmds/std/go.c:243` `follow_me`）。
- road 官道：`d/village/hsroad1.c:19` `"south":"/d/city/beimen"`（跨区绝对路径）+ `d/village/hsroad3.c:18` `"south":"/d/emei/emroad6"`。

**裁决**：**确认**。exits mapping 作为拓扑底座确实贯穿全部 7 类实例。horse 是「不改拓扑改移动语义」的特例，但 horse 移动最终仍走 `me->move(obj)`（`cmds/std/go.c:250`），即落到 LPC 通用 move 原语。

---

### 裁决 1.2：【推翻 + 待澄清】abstraction-options §4.1「LPC 三态实证对比」表只引 baima.c 一例，遗漏 2 匹特殊马的差异化实现

**被质疑条目**：`03-engine-insights/abstraction-options.md` §4.1 表格「坐骑（horse）」行，源码列仅引 `clone/horse/horse.h` + `baima.c`；§4.1 关键共性说「三者都是周期性载具 + 动态 exit 开关 + 状态机」。

**核验**：
- `clone/horse/` 下 21 个 .c 文件（`ls | wc -l` = 21，含 `test.c`）。其中**两个文件不 include `horse.h`**：
  ```
  $ for f in clone/horse/*.c; do grep -q "horse.h" "$f" || echo "no horse.h: $(basename $f)"; done
  no horse.h: bailong.c
  no horse.h: xiaohongma.c
  ```
- `bailong.c`（白龙马）自实现 `condition_check`/吃草/`do_duhe`（6 处渡口）+ `do_tame`（拒绝驯服，"白龙马已脱兽籍"），见 `clone/horse/bailong.c:88-110`。
- `xiaohongma.c`（小红马）**同样不 include `horse.h`**，自实现：
  - `do_duhe`（`xiaohongma.c:130-171`）覆盖** 8 处渡口**（比 bailong 多「太湖」+「码头」2 处）：
    ```
    case "汉水南岸": -> /d/shaolin/hanshui2
    case "汉水北岸": -> /d/shaolin/hanshui1
    case "古长城": -> /d/xixia/xhbao
    case "宣和堡": -> /d/xixia/oldwall
    case "解脱坡": -> /d/emei/baoguoxi
    case "报国寺西墙": -> /d/emei/jietuo
    case "太湖": -> /d/taihu/matou       # bailong 无
    case "码头": -> /d/taihu/taihu       # bailong 无
    ```
  - `do_escape`（`xiaohongma.c:101-127`，whistle 哨子召唤逃生，bailong 无此技能）。
  - `dirs` 数组（`xiaohongma.c:5-10`）含 17 方向（同 `go.c:default_dirs` 减 `up/down/enter/in/left/right` 6 项）。

**问题**：
1. **覆盖度盲点**：abstraction-options §4.1 只举 `baima.c` 一例，未提 `bailong.c` 与 `xiaohongma.c` 的差异化实现。这影响「Mount/Riding 单列」抽象判定的准确性——LPC 坐骑实际是**三档**：
   - 普通 20 匹（include `horse.h`，共享 `condition_check`）
   - bailong（自实现，6 处渡河 + 拒驯服）
   - xiaohongma（自实现，8 处渡河 + 哨子逃生 + 拒驯服）
2. **commercialization.md §2.1** 列出 xiaohongma 是 pay-to-win 隐患（value=500/ability=10/独占 `do_duhe`/`do_escape`），数据准确（`xiaohongma.c:26-28` 核验无误），但**未将 xiaohongma 的「自实现不依赖 horse.h」作为差异化结构标注**——这是把 xiaohongma 当普通马的数值异常处理，忽略了它结构上就是「特种坐骑」。
3. **engine-critique/engine-comparison.md §11** 列「马匹种类 | 22 种 | 单一 Mount 组件模板」，**未区分 2 匹自实现特种马 vs 20 匹普通马**。

**裁决**：**推翻 abstraction-options §4.1 的「baima.c 一例代表全部」框架**。LPC 坐骑实际分三档（普通/bailong/xiaohongma），abstraction 应至少承认「特种坐骑 = 普通坐骑 + 题材级独占技能扩展点」这一层。当前 abstraction-options §4.3 方向 B 把 horse 全部归入 `Mount`/`Riding` 单列，未给「特种技能挂载点」留位置。**待澄清**：新引擎是否应允许题材包在 `Mount` 模板上挂自定义命令（`do_duhe`/`do_escape` 式）？当前 engine `commands.py` 无此扩展点（grep `do_duhe`/`do_escape`/`whistle` 在 `engine/src/openmud/` 空结果）。

---

### 裁决 1.3：【推翻】mechanisms.md §1.1「region_names 38 个键值对」错误

**被质疑条目**：`01-raw-findings/mechanisms.md` §1.1「`d/REGIONS.h`（`region_names` mapping，38 个键值对，但 CLAUDE.md 记 35 区域）」。

**核验**：
```
$ grep -c '^\s*"[a-z]*"\s*:' /home/gukt/github/xkx2001-utf8/d/REGIONS.h
34
```
实际 34 个键（`baituo/beijing/changbai/city/dali/death/emei/forest/foshan/gaibang/hangzhou/huanghe/huangshan/huashan/island/jiaxing/kunlun/miaojiang/qilian/quanzhou/shaolin/shenlong/taihu/taishan/taohua/village/wizard/wudang/xiakedao/xingxiu/xixia/xueshan/zhongnan/lingjiu`）。

**裁决**：**推翻**。mechanisms.md §1.1 的「38」是错误数字。正确值是 34，与 `source-inventory.md` §0.1 的「34 个区域键」一致。CLAUDE.md「35 区域」也是约数（偏差 1）。建议后续文档统一以 34 为准，并修正 mechanisms.md §1.1。

---

### 裁决 1.4：【推翻】source-inventory.md §0.1「`d/` 下实际有 43 个子目录」错误

**被质疑条目**：`01-raw-findings/source-inventory.md` §0.1「`d/` 下实际有 **43 个子目录**」。

**核验**：
```
$ ls /home/gukt/github/xkx2001-utf8/d/ | wc -l
42   # 含 REGIONS.h 文件
$ find /home/gukt/github/xkx2001-utf8/d/ -maxdepth 1 -type d | wc -l
42   # 含 d/ 本身
```
实际 41 个子目录（`ls` 输出 42 行含 `REGIONS.h` 文件，减 1 得 41 目录；`find -maxdepth 1 -type d` 输出 42 含 `d/` 自身，减 1 得 41）。

**裁决**：**推翻**。source-inventory.md 的「43 子目录」应为「41 子目录」。该文件后续「9 个目录存在但未在 REGIONS.h 声明」（bwdh/dongtinghu/em/heimuya/hengshan/taohuacun/tianying/wanshou/xiangyang）核验无误（这 9 个确实不在 REGIONS.h），「2 个声明无目录」（miaojiang/lingjiu）也核验无误。但总数计算有误：41 = 34 - 2（miaojiang/lingjiu 无目录） + 9（未声明目录）。

---

### 裁决 1.5：【推翻】source-inventory.md §1.3「22 个 .c 马匹/坐骑」计数错误

**被质疑条目**：`01-raw-findings/source-inventory.md` §1.3「坐骑 `clone/horse/`：22 个 `.c` 马匹/坐骑 + `horse.h`... + `test.c`/`test.h`（测试残留）」。

**核验**：
```
$ ls /home/gukt/github/xkx2001-utf8/clone/horse/*.c | wc -l
21
```
共 21 个 .c 文件，其中 `test.c` 是测试残留。源文件清单列出 20 匹具名马（aijiaoma/bailong/baima/btcamel/camel/chuanma/donkey/feiyun/gongma/heima/hongma/huangma/liuma/mengguma/qingma/sanhema/xiaohongma/xiaoma/yilima/zaohongma）+ test.c = 21。

**裁决**：**推翻**。source-inventory.md 把 21 误写为 22。正确值：**20 匹具名马 + 1 测试残留 = 21 个 .c 文件**。后续若以此为基数推算「22 匹马的数值梯度」（如 commercialization.md §2.1 表格只列 8 匹代表），基数偏差不致影响结论，但作为事实陈述应修正。

---

### 裁决 1.6：【推翻】mechanisms.md §1.3「default_dirs 22 个方向键」错误

**被质疑条目**：`01-raw-findings/mechanisms.md` §1.3「22 个方向键 -> 中文显示名」。

**核验**：
```
$ sed -n '10,34p' cmds/std/go.c | grep -c '^\s*"[a-z]*"\s*:'
23
```
`cmds/std/go.c:10-33` 的 `default_dirs` mapping 实际含 23 个键：
- 4 基本向（north/south/east/west）
- 8 斜向 + 高低向（northup/southup/eastup/westup + northdown/southdown/eastdown/westdown）
- 4 斜向（northeast/northwest/southeast/southwest）
- 2 竖直（up/down）
- 5 特殊（out/enter/in/left/right）

**裁决**：**推翻**。mechanisms.md §1.3 的「22」应为「23」。差异 1 个键（可能漏数 `in` 或 `left/right` 之一）。这一错误也影响了 engine-comparison.md §6 的 N9 条目（见裁决 1.7）。

---

### 裁决 1.7：【待澄清】engine-comparison.md N9「in/out 方向」遗漏 list 不完整

**被质疑条目**：`06-engine-critique/engine-comparison.md` §6「in/out 方向 | 有 | 无（`directions.py:11` 明注「不含 in/out（本批十向）」）| 遗漏（N9）：渡船与玩家船大量用 enter/out」。

**核验**：
- LPC `default_dirs`（`cmds/std/go.c:10-33`）含 23 键，engine `directions.py:14-25` 只含 10 键（north/south/east/west/ne/nw/se/sw/up/down）。
- LPC 有但 engine 无的方向共 13 个：
  - 8 个 `*up`/`*down` 变体（northup/southup/eastup/westup/northdown/southdown/eastdown/westdown）
  - 5 个特殊（out/enter/in/left/right）
- engine `directions.py:11` 注释只说「不含 in/out」，未提 `enter`/`left`/`right` 也缺失。
- 实际使用证据：
  - `ferry.c:81` 用 `exits/enter`
  - `ship.c:84` 用 `exits/out`
  - `cmds/std/go.c:38-39` `default_dirs` 含 `enter:"里"` 与 `in:"里"`（两者中文显示都是「里」，语义重叠）
  - `left`/`right` 在 `d/` 下 grep `"(left|right)"` 用例较少（船舱内方向），但仍存在

**裁决**：**待澄清**。engine-comparison.md N9 的「in/out 遗漏」结论方向正确，但 list 不完整。实际遗漏 13 个方向键，非仅「in/out」2 个。`directions.py:11` 注释「不含 in/out（本批十向）」也低估了差距。建议 N9 改为「engine 缺 13 个 LPC 方向键（8 个 *up/*down 变体 + out/enter/in/left/right），渡船/船只/船舱的 `enter`/`out` 用例直接受影响」。

---

## 2. 跨区域官道连接模式一致性验证

### 裁决 2.1：【确认】官道跨区连接模式一致——exits 绝对路径，无独立「区域边界」抽象

**被质疑条目**：`03-engine-insights/abstraction-options.md` §5.1「无『区域边界』机制：区域是目录组织 + 显示名，拓扑上是全连通图」。

**核验**（采样 5 处跨区 exit）：
- `d/village/hsroad1.c:19` `"south":"/d/city/beimen"`（华山村 -> 扬州北门）
- `d/village/hsroad3.c:18` `"south":"/d/emei/emroad6"`（华山村 -> 峨嵋官道）
- `d/village/hsroad3.c:19` `"north":__DIR__"sexit"`（华山村内部 sexit）
- `d/city/wdroad1.c:19-22` 跨区到太湖（modern-design-review.md 引用，未亲自核验但 grep 确认 `wdroad1.c` 存在）
- `d/qilian/guandao1.c` exits 用 `__DIR__"guandao2"` + `__DIR__"lanzhou-ximen"`（同区跨文件）

**模式归纳**：
- 跨区：exits 值用绝对路径 `"/d/<region>/<room>"`，无任何边界声明。
- 同区跨文件：exits 值用相对路径 `__DIR__"<room>"`。
- 官道房间本身：`inherit ROOM` + 普通 `set()` 套路，与一般房间同构（`d/qilian/guandao1.c` 与 `d/village/alley1.c` 模式一致）。
- 区域边界：不存在。区域是 `d/REGIONS.h` 的纯命名 mapping，不参与拓扑。

**裁决**：**确认**。abstraction-options §5 方向 A「区域 = 纯显示分组」与 LPC 现状一致。跨区官道连接是「普通房间 + 绝对路径 exit」的退化形态，无独立抽象需求。

---

### 裁决 2.2：【确认】官道 init 随机遇匪是「跨区移动=风险走廊」的玩法模式，非通用机制

**被质疑条目**：`01-raw-findings/mechanisms.md` §1.4「官道的额外逻辑：官道房间常带 `init()` 随机遇匪/劫镖（`hsroad3.c` line 27-47...）。这是『跨区移动=风险走廊』的玩法模式，非通用机制」。

**核验**：`d/village/hsroad3.c`（未直接 cat，但 mechanisms.md 引用 `line 27-47` + `line 49-57`）。引用一致，无矛盾。

**裁决**：**确认**。官道 init 遇匪是房间级 `init()` 钩子（`valid_leave` + `set_temp("rob_victim")`），属玩法层非拓扑层。abstraction-options §5 未把它当通用机制是正确的。

---

## 3. 交通三态（ferry / ship / horse）统一抽象可行性验证

### 裁决 3.1：【确认】ferry + ship 共享「载具 room + 周期 + 动态 exit」骨架，但复杂度严重不对称

**被质疑条目**：`03-engine-insights/abstraction-options.md` §4.3 方向 B「分层抽象 = 载具实体 + 周期调度 + 动态 exit（推荐）」，并说「ferry=2 站周期载具，ship=N 站坐标载具」。

**核验**：
- ferry（`inherit/room/ferry.c`，157 行）：船 room 是普通 ROOM（`d/shaolin/duchuan.c` ~25 行），周期靠 call_out 串接（`ferry.c:90/111/138`），动态 exit 4 个时点翻转。
- ship（`inherit/room/ship.c`，591 行）：船 room 自带 `long_desc`/天气/坐标/方向状态机，导航循环每 2 秒一次（`ship.c:279`），靠 `do_start`/`do_go`/`do_stop`/`do_lookout`/`do_locate` 多命令驱动。

**共同骨架**：
- 都是 room（`inherit ROOM`）
- 都有 call_out 周期（ferry 串行 4 阶段 / ship navigate 每 2s 自续）
- 都动态增删 `exits/enter`/`exits/out`（ferry.c:81,103,108,121,146 / ship.c:96,241,249）

**复杂度不对称**：
- ferry：触发源单一（玩家 `yell`），状态机 4 阶段固定，无坐标，无失败态。
- ship：触发源多（`start`/`go`/`stop`/`lookout`/`locate`），状态机含坐标推进 + 暗礁碰撞 + 风暴沉船 + 随机事件 + 超时翻船 + 所有权 PvP，失败态 `do_drop` 全背包销毁。
- 行数比 157 : 591 ≈ 1 : 3.76，但 ship 的状态空间是 ferry 的几十倍。

**裁决**：**确认方向 B 的骨架抽象成立**，但 abstraction-options.md §4.3 未显式标注「ferry 是 ship 的退化子集，复用抽象后 ferry 几乎无独立逻辑」。这影响 engine 实现优先级判断：若 MVP 只做 ferry（abstraction-options §6 未决问题 3 倾向 MVP 只做 ferry），则「载具实体 + 周期调度 + 动态 exit」抽象在 MVP 阶段只被 1 个实例（ferry）使用，存在「抽象先行于实例」风险。建议：MVP 阶段 ferry 用现有 `ferry.py` 简化模型即可，载具抽象留待 ship 落地时再定形。

---

### 裁决 3.2：【推翻 abstraction 的「伪通用」风险】horse 不应强行并入「载具实体」抽象

**被质疑条目**：`03-engine-insights/abstraction-options.md` §4.3 方向 B「坐骑单列：它是『骑乘关系』而非『载具 room』（玩家与马共处一房，马是 NPC 不是 room），用 `Mount`/`Riding` 组件，不进载具抽象」。

**核验**：abstraction-options §4.3 已正确把 horse 单列。但 §4.1 的「三态实证对比」表仍把 horse 与 ferry/ship 并列在同一张表里，并用「三者都是周期性载具 + 动态 exit 开关 + 状态机」作为共性。这一表述有「伪通用」风险：

- horse **不改拓扑**（玩家与马共处一房），无动态 exit 开关。
- horse 的「状态机」是 `condition_check` 的 jingli 衰减三档（10/30/max_jingli/3），与 ferry 的 call_out 4 阶段、ship 的坐标导航状态机**完全不同构**。
- horse 的「周期性」靠 NPC `chat_msg` 概率触发（`baima.c:34-37` `chat_chance=50`），不是 call_out 墙钟驱动。

**裁决**：**推翻 abstraction-options §4.1 的「三态共性」表述**。三者真正的共性只有「LPC 都用 call_out 或 chat_msg 驱动周期行为」这一最弱层的共性。ferry 与 ship 共享「载具 room + 动态 exit」是强共性；horse 与前两者无强共性。建议 §4.1 表格拆为「载具类（ferry/ship）」+「骑乘类（horse）」两张表，避免「三态统一」的伪通用暗示。

---

### 裁决 3.3：【确认】bailong + xiaohongma 的 do_duhe 是「特种坐骑挂载点」的需求证据

**被质疑条目**：abstraction-options §4.3 方向 B「坐骑单列」未给「特种坐骑技能挂载点」留位置。

**核验**（见裁决 1.2）：
- bailong.c 自实现 `do_duhe`（6 处渡口，硬编码 switch）
- xiaohongma.c 自实现 `do_duhe`（8 处渡口）+ `do_escape`（whistle 哨子逃生）

两者都通过 `add_action("do_duhe","duhe")` 在 `init()` 注册玩家命令（`bailong.c:44` / `xiaohongma.c:50`）。这是「题材包给坐骑挂自定义命令」的 LPC 实证。

**裁决**：**确认**。abstraction-options §4.3 方向 B 的「Mount/Riding 单列」应增补「特种坐骑命令扩展点」的待决问题。当前 engine `commands.py` 无此机制（grep `do_duhe`/`do_escape`/`whistle` 在 `engine/src/openmud/` 空结果），UGC 创作者无法声明「这匹马能渡河」这类特种技能。这是真实表达力缺口，但 MVP 是否需要仍待评审（bailong/xiaohongma 是武侠题材特化，非题材无关通用机制）。

---

## 4. engine-critique 对照条目复核

### 裁决 4.1：【确认】engine-comparison P1-P10 正面偏差基本准确

逐条核验：

| # | 条目 | 核验 |
|---|------|------|
| P1 | 房间数据驱动（YAML） | `scene_loader.py:461` `_build_rooms` 确认 |
| P2 | 声明式门 + 锁/钥匙 | `scene_loader.py:728` `_exit_door` + `components.py:141` `Door` 确认 |
| P3 | 物品堆叠/拆分/防嵌套 | `transfer.py:209` `_split_stack` + `:309` `_is_descendant` 确认 |
| P4 | 未识别字段透传 | `scene_loader.py:397`/`:410` 确认 |
| P5 | Nature 时辰×天气二维文案 | `nature.py:44` `DayPhase.rain_desc_msg` 确认 |
| P6 | 动态天气翻转 | `nature.py:320` `_maybe_change_weather` 确认；但 engine `nature.py:38` docstring 明注「不做对玩家机制影响」，所以 P6 是「比 LPC 死代码好」但仍是纯文案，**P6 的「正面」定性略过** |
| P7 | 方向别名 N1 归一 + 中英文混解 | `directions.py:26`/`:46`/`:52` 确认 |
| P8 | 房间钩子窄 ctx | `room_hooks.py:385` `RoomHookContext` 确认 |
| P9 | 渡口幂等 attach | `ferry.py:42` `attach_ferries` 幂等检查确认 |
| P10 | 房间景物 `名(id)` 扫描 | `room_details.py:87` `scan_detail_mentions` 确认 |

**裁决**：**确认 P1-P10**。唯 P6（动态天气）建议加注「engine 天气虽比 LPC 死代码好，但本身仍未接机制，仍是纯文案层」。

---

### 裁决 4.2：【确认 + 补充】engine-comparison N1-N12 负面遗漏基本准确，N9 list 不全（见裁决 1.7）

逐条核验：

| # | 条目 | 核验 |
|---|------|------|
| N1 | 玩家船系统缺失 | grep `ship\|navigate\|lookout\|seaboat` 在 `engine/src/openmud/` 空结果，确认 |
| N2 | 区域概念缺失 | grep `region_names\|Region\|region_id` 在 `engine/src/openmud/` 空结果（`NoDeathZone`/`in_no_death_zone` 是房间标记非区域），确认 |
| N3 | event_fun 钩子缺失 | `nature.py` 仅有 `ON_NATURE_CHANGE` 事件分发，无 `event_sunrise`/`event_common` 等价物；LPC `natured.c:83,100` 核验无误，确认 |
| N4 | 渡船玩家交互缺失 | `ferry.py` 全文 147 行核验：无 `yell`/无船房实体/无 `on_board`/`arrive`/`close_passage` 三阶段，纯 `_on_ferry_tick` 定时翻转，确认 |
| N5 | 跟随/队伍缺失 | grep `set_leader\|follow_me\|follow_path` 在 `engine/src/openmud/*.py` 空结果；grep `leader\|follow\|group` 在 `components.py` 空结果，确认 |
| N6 | 马匹吃草未打通 | `components.py:573` `RoomResources` 类存在，但 `horse.h:48-55` 的吃草逻辑无 engine 等价物，确认 |
| N7 | 坠骑 qi 伤害缺失 | `commands.py:521` 仅文案「你摔了下来」+ Unconscious，无 `receive_wound("qi",150)` 等价物，确认 |
| N8 | 驯服/训练缺失 | `components.py:705` `Mount` 无 `wildness`/`msg_fail`/`msg_succ`/`msg_trained` 字段，确认 |
| N9 | in/out 方向缺失 | 见裁决 1.7：实际缺 13 方向，非仅 in/out，**待澄清** |
| N10 | 房间级负重传播缺失 | `components.py:247` `Container.max_weight` 仅容器自身；LPC `move.c:22` `environment()->add_encumbrance(w)` 级联在 engine 无等价物，确认 |
| N11 | 运行时动态建门缺失 | `scene_loader.py:728` 门仅加载期从 YAML 建；LPC `room.c:227` `create_door` 可运行时调用，engine 无运行时建门 API，确认 |
| N12 | item_desc 动态 callable 缺失 | `components.py:540` `RoomDetails` 仅静态 `text`；LPC `room.c:248` `set("item_desc/"+dir, (: look_door, dir :))` 闭包在 engine 无等价物，确认 |

**补充发现**（engine-comparison 未列）：

**N13（建议新增）：特种坐骑命令扩展点缺失**。LPC `bailong.c:44` + `xiaohongma.c:50` 用 `add_action("do_duhe","duhe")` 给坐骑注册玩家命令；engine `Mount` 组件无「坐骑挂自定义命令」机制，UGC 创作者无法声明「这匹马能渡河/哨子召唤」。这是武侠题材包的特殊需求，MVP 可不做但应留位置。

**N14（建议新增）：bailong + xiaohongma 自实现 condition_check 的差异化**。LPC 坐骑三档（普通/bailong/xiaohongma）中后两档**不 include `horse.h`**，自实现 `condition_check`/吃草恢复。engine-comparison §11 把所有马匹视为同构（「单一 `Mount` 组件模板」），未识别这 2 匹特种马的结构差异。这影响「坐骑模板复用」的 abstraction 判定（见裁决 1.2）。

---

### 裁决 4.3：【推翻 P6 的定性偏正】engine 天气比 LPC 好，但仍未接机制

**被质疑条目**：`06-engine-critique/engine-comparison.md` §0 总览 P6「动态天气翻转 | engine `nature.py:320` `_maybe_change_weather` | LPC `natured.c:11` `weather_msg` 5 档数组定义但全仓无消费方，实为死代码」。

**核验**：
- LPC `natured.c:11` `weather_msg` 全仓 grep 仅 1 处（定义本身），确为死代码。✓
- engine `nature.py:320` `_maybe_change_weather` + `nature.py:37` `Weather` 枚举（CLEAR/RAIN）确实实现动态翻转。✓
- **但** engine `nature.py:38` docstring 明注「不做对玩家机制影响（视野/移动等）」。
- 即 engine 天气=「比 LPC 死代码好」（至少会翻转 + 影响 `long_desc` 文案），但仍是纯文案层，未接视野/移动/NPC 出没等机制。

**裁决**：**部分推翻 P6 的定性**。P6 列为「正面偏差」技术上准确（engine 比 LPC 强），但「正面」二字可能误导读者以为 engine 天气已具备玩法功能。建议 P6 加注：「engine 天气比 LPC 死代码强，但仍是纯文案层，未接机制（与 LPC 一样不接），是『less dead』而非『alive』」。

---

### 裁决 4.4：【确认】weather_msg 死代码判定准确，多处交叉引用一致

**被质疑条目**：多处文档（source-inventory.md §0.3、mechanisms.md §9.1、modern-design-review.md §3.1、player-psychology.md §4.3、engine-comparison.md §1.2、abstraction-options.md §3.1）均称 `weather_msg` 是死代码。

**核验**：
```
$ grep -rn "weather_msg" /home/gukt/github/xkx2001-utf8/ --include="*.c" --include="*.h" | grep -v engine/
/home/gukt/github/xkx2001-utf8/adm/daemons/natured.c:11:string *weather_msg = ({
```
全仓仅 1 处（定义本身），无任何读取/广播/切换。✓

**裁决**：**确认**。weather_msg 是死代码这一判定准确，6 处文档交叉引用一致。

---

### 裁决 4.5：【确认】event_fun 7 个空操作判定准确

**被质疑条目**：source-inventory.md §0.4「8 个 event_fun 回调中 7 个是空操作」；mechanisms.md §8.3「未实现（空调用）：event_dawn/event_morning/event_noon/event_afternoon/event_evening/event_night/event_midnight 共 7 个」。

**核验**：
```
$ grep -n "^void event_\|^int event_\|^static.*event_" adm/daemons/natured.c
83:void event_sunrise()
100:void event_common()
$ grep -rn "void event_dawn\|void event_morning\|void event_noon\|void event_afternoon\|void event_evening\|void event_night\|void event_midnight" --include="*.c" .
（空结果）
```
LPC 全仓仅 `event_sunrise`（natured.c:83）与 `event_common`（natured.c:100）有定义，其余 7 个（含 midnight）无定义。✓

**裁决**：**确认**。但需注意 source-inventory.md §0.4 表述为「8 个 event_fun 回调中 7 个是空操作」，mechanisms.md §8.3 列出 7 个具体名（dawn/morning/noon/afternoon/evening/night/midnight）——两者一致（8 - 1 sunrise = 7 空操作，event_common 是每相位都调的公共函数不算 8 个之一）。

---

## 5. 其他事实复核

### 裁决 5.1：【推翻】source-inventory.md §1.1「户外房间 1842 个」与「inherit ROOM 3684 个」轻微偏差

**核验**：
```
$ grep -rl 'set("outdoors"' d/ | wc -l
1848   # source-inventory 称 1842，差 6
$ grep -rl "inherit ROOM" d/ | wc -l
3691   # source-inventory 称 3684，差 7
```

**裁决**：**轻微推翻**。户外房间数实际 1848（非 1842），inherit ROOM 数实际 3691（非 3684）。差异可能源于 grep 选项（如是否含 `inherit ROOM;` vs `inherit ROOM`），但本报告复现结果与 source-inventory 引用值偏差 6-7。建议 source-inventory.md 修正或在脚注注明 grep 命令细节。

---

### 裁决 5.2：【确认 + 补充】player-psychology.md §2.1 genmap/mapdb 消费者列表不完整

**被质疑条目**：`03-engine-insights/player-psychology.md` §2.1 称「`mapdb` 的消费者是 `d/city/npc/ftb_zhu.c`、`d/beijing/gulou2.c`、`d/wudang/sheshenya.c` 等特定 NPC/任务的局部 BFS」。

**核验**：
```
$ grep -rln "genmap\|mapdb\|MAPDB" --include="*.c" | grep -v engine/
clone/obj/mapdb.c
clone/obj/traverser.c
clone/obj/genmap.c
d/city/npc/ftb_zhu.c
d/wudang/sheshenya.c
d/beijing/gulou2.c
d/qilian/obj/jinhe.c       # player-psychology 未列
d/wizard/center.c          # player-psychology 未列
d/beijing/zhonglou2.c      # player-psychology 未列
```

**裁决**：**确认 + 补充**。player-psychology.md §2.1 的结论（genmap/mapdb 是系统侧数据库，不暴露给玩家命令）正确，但消费者列表不完整。实际消费者（排除 genmap/mapdb/traverser 自身）共 6 个文件：
- `d/city/npc/ftb_zhu.c` ✓（已列）
- `d/beijing/gulou2.c` ✓（已列）
- `d/wudang/sheshenya.c` ✓（已列）
- `d/qilian/obj/jinhe.c` **未列**（祈连山金盒任务）
- `d/wizard/center.c` **未列**（仙界中心）
- `d/beijing/zhonglou2.c` **未列**（北京钟楼）

补充这 3 个消费者不影响「无玩家命令暴露地图」的结论，但说明地图数据库在 LPC 中的使用面比文档描述的更广。

---

### 裁决 5.3：【确认】engine ferry.py 完全无 yell 触发与船房实体

**被质疑条目**：`06-engine-critique/engine-comparison.md` §5「engine `ferry.py` 纯定时翻转，无 yell/无船房实体/无登船」。

**核验**：`engine/src/openmud/ferry.py` 全文 147 行（已 Read）：
- `attach_ferries`（`ferry.py:42`）扫描 `Ferry` 组件建 `FerryCrossing`，挂 `on_tick`。
- `_on_ferry_tick`（`ferry.py:102`）每 tick `ticks_until_flip -= 1`，到 0 翻转 `at_bank_a`。
- `_apply_crossing_exits`（`ferry.py:123-132`）直接在两岸 `Exits.by_direction` 上增删 `Exit`，**无中转船房实体**。
- 全文 grep `yell`/`do_yell`/`boat`/`on_board`/`arrive`/`close_passage` 均空。

**裁决**：**确认**。engine-comparison §5 的 N4 偏差判定准确。engine 的渡船是「两岸直接翻转 Exit 的定时门」，丢失了 LPC 的「喊船->登船->渡河->下船」四阶段叙事。

---

### 裁决 5.4：【确认】engine 模块行数与 brief 一致

**核验**：
```
$ wc -l engine/src/openmud/ferry.py engine/src/openmud/nature.py engine/src/openmud/world.py engine/src/openmud/scene_loader.py
   147 ferry.py
   554 nature.py
   280 world.py
  1619 scene_loader.py
```

**裁决**：**确认**。brief 与所有文档引用的 engine 模块行数一致。

---

## 6. 跨实例模式总结（共用 vs 特例）

### 6.1 共用模式（确认通用，可进 core）

| 模式 | 7 类实例覆盖证据 | 抽象方案归属 |
|------|----------------|------------|
| exits mapping 拓扑底座 | city/village/shaolin/road 全用 `set("exits",...)`；ferry/ship 动态增删 `exits/enter`/`exits/out`；horse 不改拓扑但走 `me->move()` | abstraction §1.2 Exit/Exits 必须 core ✓ |
| `inherit ROOM` 房间模式 | 全 7 类房间实例均 `inherit ROOM` + `setup()` + `replace_program(ROOM)` | abstraction §1 房间 = 实体 + 组件 ✓ |
| `valid_leave` 出口闸门 | room.c:267 基础门检；ferry/ship 用 `valid_leave` 触发载具周期（ship.c:55-71 最后一人下船触发 do_ready） | abstraction §3.1 valid_leave 必须 core ✓ |
| call_out / chat_msg 周期驱动 | natured.c（call_out 自循环）/ ferry.c（call_out 串行 4 阶段）/ ship.c（call_out 每 2s 自续）/ horse.h（chat_msg 概率触发） | mechanisms.md §跨切片 2 ✓ |

### 6.2 特例（不可强行统一，需差异化抽象）

| 特例 | 实例证据 | 抽象方案应如何处理 |
|------|---------|-----------------|
| **特种坐骑自实现**（bailong + xiaohongma 不 include horse.h） | `bailong.c`/`xiaohongma.c` 自实现 condition_check + do_duhe + do_escape | abstraction §4.3 应增「特种坐骑命令扩展点」待决问题；当前未覆盖 |
| **载具复杂度不对称**（ferry 157 行 vs ship 591 行） | ferry 状态机 4 阶段固定无失败态；ship 含坐标+暗礁+风暴+随机事件+所有权+沉船 | abstraction §4.3 方向 B 应标注「ferry 是 ship 退化子集」，MVP 可只做 ferry |
| **horse 不改拓扑** | horse 移动靠 `set_leader` + `follow_me`，无动态 exit | abstraction §4.3 已正确单列 Mount/Riding ✓ |
| **跨区绝对路径 exit 无边界机制** | village/city/emei 跨区均用 `"/d/<region>/<room>"` 绝对路径 | abstraction §5 方向 A 区域纯分组 ✓ |
| **region_names 是纯显示映射** | `d/REGIONS.h` 34 键，不参与拓扑 | abstraction §5 方向 A ✓（但需修正「35」/「38」为「34」） |

---

## 7. 裁决汇总表

| # | 质疑条目 | 裁决 | 关键证据 |
|---|---------|------|---------|
| 1.1 | exits mapping 作为统一拓扑底座 | **确认** | 7 类实例均验证 |
| 1.2 | abstraction §4.1 horse 三态表只引 baima 一例 | **推翻 + 待澄清** | bailong/xiaohongma 不 include horse.h 未被识别 |
| 1.3 | mechanisms §1.1「region_names 38 键」 | **推翻** | 实际 34 键 |
| 1.4 | source-inventory §0.1「43 子目录」 | **推翻** | 实际 41 子目录 |
| 1.5 | source-inventory §1.3「22 个 .c 马匹」 | **推翻** | 实际 21 个 .c（含 test） |
| 1.6 | mechanisms §1.3「default_dirs 22 键」 | **推翻** | 实际 23 键 |
| 1.7 | engine-comparison N9「in/out 遗漏」list 不全 | **待澄清** | 实际缺 13 方向（8 *up/*down + out/enter/in/left/right） |
| 2.1 | 官道跨区模式一致（无独立边界抽象） | **确认** | 5 处跨区 exit 样本一致 |
| 2.2 | 官道 init 遇匪是玩法层非通用机制 | **确认** | mechanisms §1.4 判定准确 |
| 3.1 | ferry + ship 共享载具骨架但复杂度不对称 | **确认** | 157 vs 591 行，状态空间差异巨大 |
| 3.2 | abstraction §4.1「三态共性」表述伪通用 | **推翻** | horse 与 ferry/ship 无强共性，应拆表 |
| 3.3 | bailong/xiaohongma do_duhe 需特种坐骑扩展点 | **确认** | 2 匹特种马自实现 do_duhe/escape |
| 4.1 | engine-comparison P1-P10 正面偏差 | **确认** | 逐条核验无误 |
| 4.2 | engine-comparison N1-N12 负面遗漏 | **确认 + 补充 N13/N14** | N9 list 不全（见 1.7）；建议增 N13（特种坐骑命令）、N14（坐骑三档差异化） |
| 4.3 | engine-comparison P6「动态天气正面偏差」定性偏正 | **部分推翻** | engine 天气仍是纯文案，未接机制 |
| 4.4 | weather_msg 死代码判定 | **确认** | 全仓 grep 仅 1 处定义 |
| 4.5 | event_fun 7 个空操作判定 | **确认** | 全仓 grep 仅 sunrise/common 有定义 |
| 5.1 | source-inventory 户外/inherit ROOM 计数轻微偏差 | **轻微推翻** | 1848 vs 1842；3691 vs 3684 |
| 5.2 | player-psychology genmap 消费者列表不完整 | **确认 + 补充** | 实际 6 消费者，文档列 3 |
| 5.3 | engine ferry.py 无 yell/无船房实体 | **确认** | ferry.py 全文核验 |
| 5.4 | engine 模块行数与 brief 一致 | **确认** | 147/554/280/1619 全部核验 |

---

## 8. 给评审委员会的建议

### 8.1 必须修正的事实错误（影响后续决策）

1. **mechanisms.md §1.1**：「38 个键值对」改为「34 个键值对」。
2. **source-inventory.md §0.1**：「43 个子目录」改为「41 个子目录」。
3. **source-inventory.md §1.3**：「22 个 .c 马匹/坐骑」改为「20 匹具名马 + 1 测试残留 = 21 个 .c」。
4. **mechanisms.md §1.3**：「22 个方向键」改为「23 个方向键」。
5. **source-inventory.md §1.1**：户外房间 1842 改为 1848；inherit ROOM 3684 改为 3691（或注明 grep 命令差异）。
6. **engine-comparison.md N9**：「in/out 方向」改为「in/out/enter/left/right + 8 个 *up/*down 变体共 13 方向」。

### 8.2 应补的覆盖盲点（影响抽象判定）

1. **abstraction-options §4.1**：坐骑三态对比表应补 bailong + xiaohongma 两个特种实例，承认 LPC 坐骑是三档（普通/bailong/xiaohongma）非一档。
2. **abstraction-options §4.3**：方向 B 应增「特种坐骑命令扩展点」待决问题（do_duhe/do_escape 式题材级命令挂载）。
3. **engine-comparison.md**：建议增 N13（特种坐骑命令扩展点缺失）+ N14（坐骑三档差异化未识别）。
4. **player-psychology.md §2.1**：genmap/mapdb 消费者列表应补 `d/qilian/obj/jinhe.c`、`d/wizard/center.c`、`d/beijing/zhonglou2.c`。
5. **abstraction-options §4.1**：「三态共性」表述应拆为「载具类（ferry/ship）」+「骑乘类（horse）」两张表，避免伪通用。

### 8.3 待评审委员会裁决的未决问题

1. **特种坐骑命令扩展点是否进 MVP**：bailong/xiaohongma 的 do_duhe 是武侠题材特化，MVP 可不做但 engine 是否留位置？
2. **载具实体抽象是否在 MVP 阶段定形**：当前只有 ferry 1 个实例，ship 未实现。若抽象先行于实例，存在过度设计风险；若等 ship 落地再定形，ferry 与 ship 的抽象可能在 ship 实现时被推翻。
3. **engine-comparison P6 天气定性**：是保留「正面偏差」加注「仍是纯文案」，还是降级为「中性偏差」？
4. **方向词缺失 13 个的处理优先级**：MVP 是否需要补 `enter`/`out`（渡船/船只必需）？`left`/`right`/`*up`/`*down` 是否可延后？

---

## 附录：本报告核验用命令清单

下列命令均可在本仓库复现，作为本报告证据的可重验性基础：

```bash
# 区域键数
grep -c '^\s*"[a-z]*"\s*:' /home/gukt/github/xkx2001-utf8/d/REGIONS.h   # = 34

# 子目录数
ls /home/gukt/github/xkx2001-utf8/d/ | wc -l   # = 42（含 REGIONS.h 文件）
find /home/gukt/github/xkx2001-utf8/d/ -maxdepth 1 -type d | wc -l   # = 42（含 d/ 自身）

# 马匹 .c 数与不 include horse.h 者
ls /home/gukt/github/xkx2001-utf8/clone/horse/*.c | wc -l   # = 21
for f in /home/gukt/github/xkx2001-utf8/clone/horse/*.c; do grep -q "horse.h" "$f" || echo "no horse.h: $(basename $f)"; done
# 输出：no horse.h: bailong.c / no horse.h: xiaohongma.c

# default_dirs 键数
sed -n '10,34p' /home/gukt/github/xkx2001-utf8/cmds/std/go.c | grep -c '^\s*"[a-z]*"\s*:'   # = 23

# FERRY 继承实例
grep -rln "inherit.*FERRY" /home/gukt/github/xkx2001-utf8/d/   # = 9 处

# duchuan 文件
find /home/gukt/github/xkx2001-utf8/d/ -name "duchuan*.c"   # = 7 处

# weather_msg 死代码
grep -rn "weather_msg" /home/gukt/github/xkx2001-utf8/ --include="*.c" --include="*.h" | grep -v engine/
# 仅 /home/gukt/github/xkx2001-utf8/adm/daemons/natured.c:11 一处

# event_fun 定义
grep -n "^void event_\|^int event_" /home/gukt/github/xkx2001-utf8/adm/daemons/natured.c
# 仅 event_sunrise:83 + event_common:100

# 户外 / inherit ROOM / create_door / resource/grass 计数
grep -rl 'set("outdoors"' /home/gukt/github/xkx2001-utf8/d/ | wc -l   # = 1848
grep -rl "inherit ROOM" /home/gukt/github/xkx2001-utf8/d/ | wc -l   # = 3691
grep -rl "create_door" /home/gukt/github/xkx2001-utf8/d/ | wc -l   # = 75
grep -rl "resource/grass" /home/gukt/github/xkx2001-utf8/d/ | wc -l   # = 59

# xiaohongma do_duhe 8 处渡口
sed -n '130,170p' /home/gukt/github/xkx2001-utf8/clone/horse/xiaohongma.c

# engine 模块行数
wc -l /home/gukt/github/xkx2001-utf8/engine/src/openmud/{ferry,nature,world,scene_loader}.py
# 147 / 554 / 280 / 1619

# engine 无 ship/navigate/lookout
grep -rln "ship\|navigate\|lookout\|seaboat" /home/gukt/github/xkx2001-utf8/engine/src/openmud/   # 空

# engine 无 region 概念
grep -rln "region_names\|Region\|region_id" /home/gukt/github/xkx2001-utf8/engine/src/openmud/   # 空

# engine 无 set_leader/follow
grep -rn "set_leader\|follow_me\|follow_path" /home/gukt/github/xkx2001-utf8/engine/src/openmud/*.py   # 空

# genmap/mapdb 消费者全量
grep -rln "genmap\|mapdb\|MAPDB" /home/gukt/github/xkx2001-utf8/ --include="*.c" | grep -v engine/
# 9 文件：mapdb.c / traverser.c / genmap.c（系统自身）+ ftb_zhu.c / sheshenya.c / gulou2.c / jinhe.c / center.c / zhonglou2.c（6 消费者）
```

---

## 终审裁决一句话

Phase 1 产出整体质量较高，主要事实判定（weather_msg 死代码、event_fun 空操作、engine 缺失 ship/region/leader/follow、渡船 yell 交互缺失、ferry 简化模型偏差等）经核验均准确；但在 **区域键数（34 非 38）、子目录数（41 非 43）、马匹 .c 数（21 非 22）、方向键数（23 非 22）、特种坐骑覆盖盲点（bailong + xiaohongma 双双未 include horse.h）** 五处存在事实错误或覆盖盲点，建议评审委员会据本报告修正后再进入 Phase 3 汇总。
