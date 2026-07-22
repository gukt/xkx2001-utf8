# Session 笔记：星宿房间机关 → Pre-M4 官方房间钩子（2026-07-22）

> 来源：架构师对照 `d/xingxiu/`（白玉峰 / 岔路 / 全区自定义扫读）与当前引擎/DSL 的问答 + grill。  
> 用途：兄弟 effort 骨架与 [ADR-0012](../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md) 的输入；**实现须等** [pre-m4-engine-room-fidelity](../pre-m4-engine-room-fidelity/) 整包关闭后再 `/to-spec`。  
> 索引：[README.md](README.md)

## 1. Shared understanding（已确认）

### 排期与组织

1. **档 B**：原语切片 + 星宿代表机关全套（每类至少一条验收路径）；**不**整区移植星宿。
2. **另开兄弟 effort**（不并入房间保真；保真按原 scope 关完）。
3. **S3 + S1**：现在只落骨架 / ADR / PROGRESS；**实现开工门闩** = 房间保真整包关闭之后。
4. **不自动开 M4**。

### 硬门闩（γ：几乎全抬成硬门闩）

验收包名：**`xingxiu_mechanics`**（计划路径 `engine/data/xingxiu_mechanics.yaml`；无 `m2_` 前缀）。

关 effort 前须可玩证明（同构，非 LPC 等价）：

| # | 能力 | LPC 灵感锚 |
|---|---|---|
| 1 | 动态出口 + 时限 | `baiyufeng` dig / `close_cave` |
| 2 | 加载期 `random_of` 出口 | `chalu*` / `shanlu3`（声明式小原语即可） |
| 3 | 多步房间状态机 | `jaderoad3` 刮锈→拔斧→推门 |
| 4 | `valid_leave` 步数迷途 | `shamo.h`（扣水可同批最小切片） |
| 5 | jump/climb 技能门槛 | `baiyufeng` jump、`tianroad3/4`、`tianchi` |
| 6 | 时段耦合开秘道 | `jaderoom2` 玉桌日光 |
| 7 | 入室磁力吸铁 | `jadehall` |
| 8 | 劫匪刷拦 | `shanjiao` / `xxroad3` |
| 9 | 杀令介入（简化） | `riyuedong` |
| 10 | 柔丝索跨玩家捕获 | `rousi-suo` + `rousiroom`（双 `PlayerSession`） |

### 表达面（相对「RestrictedPython」口头说法的收窄）

| 决策 | 结论 |
|---|---|
| 信任边界 | **T1**：仅官方 / 题材包作者 |
| 运行时 | **R1**：可信 Python **模块** + 窄 `ctx`（非 YAML 内联 RP，本批不上 RestrictedPython 沙箱） |
| UGC | 禁止钩子；校验失败 |
| 旧 OOS 改判 | 禁止「契约级任意脚本 / UGC 可执行改出口」；**允许**官方钩子经 `ctx` 改出口 |
| ADR | [0012](../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md)；部分修正 ADR-0005 |

曾考虑后否决：纯声明式原语全覆盖（C）、UGC 也可嵌钩子（T2）、本批 YAML+RestrictedPython（R2）。

### 明确仍后置

整区星宿移植、UGC RestrictedPython、液体灌装/饮用、防拐带、雪岭比武寄存全套、空能力橱窗包、自动开 M4。

### 流程

骨架（本文件）→ 房间保真关闭 → `/to-spec` → `/to-tickets` → `/implement`  
**现在不**写完整 spec、不拆实现票、不动引擎代码。

## 2. 引擎现状对照（grill 前勘察摘要）

- 白玉峰 `dig` / `call_out` 崩塌 / `jump`：**现引擎 ≈ 0**；Pre-M4 房间保真只做 `details`/剧情门（翰林），且原 OOS 排除通用改出口。
- 岔路：`create()` 时 `random()` 定拓扑 → 需加载期 `random_of` 或静态降级；静态降级**不满足**本批硬门闩 #2。
- 星宿区另有沙漠步数迷途、冰洞周期伤害、柔丝索等——本批用上表硬门闩收口，不把全区自定义房当移植清单。

## 3. 与房间保真的边界（勿混）

| 归房间保真 | 归本 effort |
|---|---|
| `details`、语义色、藏书、`day_shop`、翰林剧情门三件套 | 官方房间钩子运行时 + `xingxiu_mechanics` 机关硬门闩 |
| 扩展 `m2_mvp_scene` 扬州验收 | **不**把白玉峰塞进扬州；独立切片包 |

## 4. 下一步（实现未开）

1. 继续 / 完成 [pre-m4-engine-room-fidelity](../pre-m4-engine-room-fidelity/) Wave 3 收口。  
2. 该 effort 关闭后：对本目录开 `/to-spec`（硬门闩 γ + ADR-0012 + S1/S2/S3 测试接缝）。  
3. 再 `/to-tickets` → `/implement`；收口回写契约 / GAP / CONTEXT。
