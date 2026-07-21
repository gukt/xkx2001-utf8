# Pre-M4：引擎房间 / 交互保真补全

> **排期窗口**：M3 停机加固 **整体完成之后**、开启 **M4 之前**。  
> **不要**并入 [.scratch/m3-hardening/](../m3-hardening/)（那是停机门闩 S0 + 选定 B3）。  
> **不要**写入 [.scratch/mvp-scope/post-mvp-backlog.md](../mvp-scope/post-mvp-backlog.md)（那是 M4 **之后**）。  
> **与频道/spawn/任务**：同属 Pre-M4；**建议** [.scratch/pre-m4-channels-spawn-quest/](../pre-m4-channels-spawn-quest/) **先于本 effort**（机制先于房间表达力）。

## 一句话

对照 LPC《侠客行》房间写法与当前 YAML/引擎能力，补一轮「房间风景、色 markup、日夜店铺、门机关、液体灌装」等引擎侧能力；书院读书可作为本波候选或明确后置，grill 时拍板。

## 状态

| 项 | 值 |
|---|---|
| 状态 | **排队**：等 M3 停机加固 Wave P0+B3 关完 |
| 入口文档 | [session-notes-2026-07-21.md](session-notes-2026-07-21.md)（本 session 详细对照与缺口清单） |
| 下一步 skill | 加固完成后新 session：`/grill-with-docs` → `/to-spec` → `/to-tickets` → `/implement` |
| 不走 | `/wayfinder`（清单已清，只需范围裁剪）；不直接 `/implement` |

## 与相邻交付物的关系

| 交付物 | 关系 |
|---|---|
| M3 停机加固票 `11` GAP 台账 | **文档**：「声明式 YAML 表达不了什么」。本 effort 是 **补能力**；加固期可先把本清单若干条写入 GAP，实现落地后再改「已支持」。 |
| 创作者契约 v0（加固票 `06`） | 本波能力若进 YAML schema，需回写契约 / `--validate`。 |
| [Pre-M4 频道/spawn/任务](../pre-m4-channels-spawn-quest/) | 兄弟 effort（假多人频道 + 物品 respawn + 声明式任务）。**建议该批优先于本房间保真**（机制先于表达力）；最终顺序 grill 时可改判。 |
| M4 | 本 effort **插入在加固与 M4 之间**（与上表兄弟 effort 同窗口）；关完后再决定是否开 M4。 |

## 建议目录（grill / to-spec 之后）

- `spec.md` — grill 塌缩后产出  
- `issues/` — `/to-tickets` 产出  
- `implement-plan.md` — 可选  

当前仅有 session 笔记，**尚未**开 `/to-spec`。
