# ADR-0052：C5 残留裁决--SMASHED 跳过 + 动态 exit 后置交通系统

- 状态：已通过（2026-07-15）
- 日期：2026-07-15
- 阶段：M3 收官后产品化收尾窗口（C5 残留裁决）
- 关联：[ADR-0049](ADR-0049-multi-opponent-select-and-key-system.md) §不做（C5 残留后置项本 ADR 裁决）/ [ADR-0044](ADR-0044-door-open-close-locked.md)（SMASHED 死代码实证）/ [10-坐骑与交通系统](../xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/10-坐骑与交通系统.md)（动态 exit 真实需求源）/ [04 §六](../xkx-arch/04-迁移路径与避坑清单.md)（收敛优先于完备）

## 背景

[ADR-0049](ADR-0049-multi-opponent-select-and-key-system.md) §不做 将 C5 残留（动态 exit 模式 + SMASHED 位）后置，理由"标准 doors+locked+钥匙+valid_leave 够用，动态 exit 风险高收益低；SMASHED 死代码"。本轮用户要求"做掉 C5 残留"，综合交通系统文档 + 全仓库调研重新裁决。

## 调研

### SMASHED 位--全仓库死代码确认

[ADR-0044](ADR-0044-door-open-close-locked.md) 已实证 SMASHED 死代码（[include/room.h:5-7](../../include/room.h) 定义位掩码 CLOSED=1/LOCKED=2/SMASHED=4，但全仓库无 set/check）。本次再确认：`adm/`/`inherit/`/`feature/`/`cmds/`/`d/`/`clone/`/`kungfu/` **全无 SMASHED/smashed 用法**。无 smash 命令、无攻击门逻辑、无标准 lock/unlock 触发 SMASHED。

### 动态 exit--真实需求 = 交通系统

[10-坐骑与交通系统](../xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/10-坐骑与交通系统.md) 揭示动态 exit 的真实场景：

- **FERRY 渡口**（[ferry.c](../../inherit/room/ferry.c)）：`yell boat` -> 渡口 `set("exits/enter", 渡船)` + 渡船 `set("exits/out", 渡口)` -> 15s `on_board` 删出口 -> 对岸 `set exits/out` -> `out` -> `close_passage` 删出口。**动态 set/delete exits 临时缝合两岸**（§10.2.1）
- **HARBOR+SHIP 海船**（[harbor.c](../../inherit/room/harbor.c)+[ship.c](../../inherit/room/ship.c)）：`yell chuan` -> 港口 `set exits/enter1 -> seaboat` + 船 `set exits/out -> 港口` -> `start` 删港口出口 + 坐标导航 -> 靠岸 `set exits/out -> 海岛`。**动态 exits + 坐标导航**（§10.2.2）
- §10.4.1 明确："交通系统是运行时动态桥梁，FERRY 运行时动态注入 exits 将断开两岸临时缝合"

[ship.c](../../inherit/room/ship.c) 实测：`set/delete("exits/out")`/`set/delete("exits/enter"+num)` 动态改出口（船移动/靠岸）。

### 当前 greenfield 无交通场景

- [xueshan_micro](../../engine/scenes/xueshan_micro/)（大轮寺旗舰 demo）：无水域，标准 doors+locked+钥匙+valid_leave 够用
- [age_of_sail_micro](../../engine/scenes/age_of_sail_micro/)（航海微场景）：极简 2 房间静态 exits（port/dock <-> ship/deck），是阶段 -1 CombatKernel 主题无关性验证场景，**非交通系统**（无渡船/海船动态 exit/坐标导航）
- 其他微场景（academy/wuxia/zhongnan）：无水域
- 交通系统（FERRY/SHIP）= 全量迁移内容（6414 房间/21 门派含水域），非 M3 demo 阶段

## 决策

### 1. SMASHED 跳过（死代码）

SMASHED 位不做。LPC 全仓库无任何触发机制（无 smash 命令、无攻击门逻辑，[ADR-0044](ADR-0044-door-open-close-locked.md) + 本次全仓库再确认）。做了是凭空发明规格，违反"LPC 是规格源"原则。正式关闭该坑。

### 2. 动态 exit 后置交通系统迁移阶段

动态 exit 不在当前阶段实施。理由（修正 [ADR-0049](ADR-0049-multi-opponent-select-and-key-system.md) §不做"风险高收益低"）：

- **真实需求 = 交通系统**（FERRY/SHIP），非当前 demo 场景
- **当前 greenfield 无交通场景**（xueshan 无水域，age_of_sail 极简静态 exits 非交通系统）
- **交通系统 = 全量迁移内容**（6414 房间/21 门派含水域），非 M3 demo 阶段
- **现在实施 = 无场景驱动，过度工程**（违反 [04 §六](../xkx-arch/04-迁移路径与避坑清单.md) 收敛优先于完备）

动态 exit 后置到交通系统迁移阶段，**场景驱动连带实施**（FERRY/SHIP 迁移时一并实现 set/delete exits + 序列化 + 双向同步 + 定时器）。届时标准 doors 仍是静态连接主体，动态 exit 是交通系统的运行时补丁（对照 §10.4.1"动态桥梁"）。

## 不做（范围边界）

- **现在实施动态 exit 基础设施**（set/delete exits API + 序列化 + 双向同步）：无场景驱动，过度工程
- **SMASHED 位**：死代码，跳过
- **现在实施 FERRY/SHIP 交通系统**：全量迁移内容，非当前阶段
- **不修改 LPC 源**（只读规格）

## 不变量

- **LPC 规格源保真**：SMASHED 死代码不发明规格；动态 exit 真实需求源自交通系统（FERRY/SHIP），后置场景驱动
- **收敛优先于完备**（[04 §六](../xkx-arch/04-迁移路径与避坑清单.md)）：动态 exit 不提前建基础设施，待交通系统迁移场景驱动
- **存储/序列化**：动态 exit 涉及运行时 set/delete exits + 序列化语义（LPC reload 重置 vs greenfield 持久化粘住），交通系统迁移时落定（届时 ADR）

## 关联

- [ADR-0049](ADR-0049-multi-opponent-select-and-key-system.md) §不做（C5 残留后置项本 ADR 裁决关闭）
- [ADR-0044](ADR-0044-door-open-close-locked.md)（SMASHED 死代码实证）
- [10-坐骑与交通系统](../xkx-arch/_archive/_侠客行%20MUD%20架构拆解说明书/10-坐骑与交通系统.md)（动态 exit 真实需求源，FERRY/SHIP）
- [04 §六](../xkx-arch/04-迁移路径与避坑清单.md)（收敛优先于完备）
