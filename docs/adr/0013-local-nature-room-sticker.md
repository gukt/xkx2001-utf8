---
Status: accepted
---

# 局部天气：房间级静态贴纸，不增殖 NatureState

Polishing C14（[.scratch/polishing/](../../.scratch/polishing/)）需要「山顶 / 渡船等少数房间呈现与世界默认不同的天气或时辰读数」，但现有 `NatureState` 是 **World 级纯内存单例**（见 `nature.py` 设计注释），且 [ADR-0009](0009-single-process-single-world.md) 钉死单机阶段单进程单 World。本 ADR 选定：**不引入第二套可 tick 的气候运行时**；在房间上挂一层声明式、**不随 tick / 天气翻转变化**的静态覆盖（「贴纸」），查询时按房间合成有效读数；未声明则无条件回退到该 World 的 `NatureState` 单例。

## 与 ADR-0009 的关系

局部天气**不**意味着多个 `NatureState`，也**不**意味着同进程多个 `World`。ADR-0009 约束的是进程 ↔ World 基数与全局注册表绑定假设；本决策仍是「一进程一 World、一 World 一可推进的 `NatureState`」。贴纸是房间上的声明式覆盖数据，不是并行 World / 并行 Nature 时钟。**无需收窄或修正 ADR-0009。**

## 与 `NatureState` 单例设计的关系

- **保留**：`World.nature` 仍是唯一会挂 `on_tick`、翻转晴雨、分发 `on_nature_change`、向户外玩家推送相位/天气广播的运行时态；题材包相位表仍挂在该单例上。
- **新增**：房间可选静态覆盖（建议组件名 `LocalNature`，YAML 键建议 `local_nature`）。覆盖字段在加载期写入、运行期不演进；实现票钉死字段形状时至少支持对 **`weather`**（`clear` / `rain`）与 **`phase`**（须为当前 World 相位表已有名）的**可选**覆盖——缺省字段表示「该面回退 World」。
- **合成读数**（查询时、按演员当前房间）：对 `phase` / `is_night` / `is_day` / `is_raining` 及户外 `look` 追加的 Nature 文案，先取房间覆盖中已声明的面，未声明面取 `world.nature`；两面都未声明覆盖的房间 ≡ 今日行为（直接读单例）。户外文案仍用 **World 相位表** 的 `desc_msg` / `rain_desc_msg`，只是代入合成后的 phase×weather，不另开一套文案表。
- **明确不选**：每 room / region 各持一个可推进的 `NatureState`（独立 RNG / 独立翻转 / 独立广播）——会打破「World 级单例」注释、引入跨房广播歧义，且超出「地理特征反映在描述上」的最小诉求。

## 影响范围边界

| 在范围内 | 不在范围内 |
|---|---|
| 户外 `look` 追加的 Nature 描述行（`Description.outdoors` 为真时） | 跨房间气候传播、邻房「看见」彼此局部天气 |
| 条件 DSL / 门禁 / NPC `when` 等既有查询面上的 `is_raining` / `is_night` / `is_day` / `phase`（求值上下文绑定演员所在房间时取合成读数） | 独立于 World 的第二天气循环或额外调度器 |
| | 局部天气 → 移动 / 战斗 / 坐骑等**数值**玩法（不新增雨天减速等映射；与既有 Nature「不做对玩家机制影响」一致） |
| | 多级 region 树 / 父区域继承（本效力裁剪掉，见下） |

`on_nature_change` 户外广播仍只跟 **World 单例** 翻转走。对齐 US44：邻房**看不见**彼此的局部贴纸（`look`/谓词按本房合成，无跨房气候可见性）；同时刻意不接受「按房分裂广播」——贴纸房玩家仍可能听到全局「雨停了」而本房 `look`/谓词仍显示局部雨。残留怪异是全局广播 vs 贴纸不同步，不是邻房互见局部天气；贴纸只保证**进房观察与条件求值**一致。

## 回退语义（两级，不可缺省）

```
房间 LocalNature 已声明的面 → World.nature 单例
```

- 房间**未挂**覆盖：全部读数 = `World.nature`（与今日行为位同）。
- 房间挂了覆盖但只覆了部分面：未覆面仍读 `World.nature`；已覆面用贴纸值（静态，不随单例翻转）。
- **不做**「房间 → 父 region → World」三级链：引擎尚无 region 作用域模型；MVP 诉求是少数特色房，不是通用气候树。provenance「回退父级（如华山）」的意图由「最终必回退到确定的 World 单例」满足；若日后加 region，应插入为中间层且不得破坏「无覆盖必落到 World 单例」——本 ADR **不**预建该层。
- 禁止出现「无覆盖也无默认」：`World.nature` 未挂载时行为与今日一致（无户外 Nature 行 / 条件侧按既有缺省），不得因贴纸机制引入新的未定义态。

## 裁剪理由

只做一层房间贴纸、不做 region 继承，是因为：(1) 满足 US42「某些房间与世界默认不同」；(2) 零额外 tick / 广播拓扑；(3) 不触碰 ADR-0009；(4) 实现面可控（加载字段 + 查询合成，模块留给票 `13`，本 ADR 不预先指定文件落点）。

## Considered Options

- **A（采纳）**：房间级静态贴纸 + 查询时合成；`NatureState` 仍 World 单例；回退 `房间 → World`。
- **B**：每 region 一个可推进 `NatureState` + region 树回退——满足「父级华山」字面，但要独立调度/广播边界，且需先发明 region 模型；对本批体量过重。
- **C**：把 `NatureState` 改成「每户外房一份」——直接否定现有单例注释与广播模型，拒。
