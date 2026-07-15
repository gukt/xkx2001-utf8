# pilot 样本 id=1：cmds/skill/xue.c:main 导航

> AI 铺路交付：人工测此样本时的规格导航 + 桩依赖 + 后置分支 + effort_record 模板。
> 守 ADR-0048 红线：迁移代码 + 测试 + effort 工时必须人工，AI 不代劳。

## 元数据

| 项 | 值 |
|---|---|
| id | 1 |
| file | cmds/skill/xue.c |
| func | main（L16-151） |
| subsystem | cmds |
| status / func_kind / tier | pending / logic / high |
| call_count | 53 |
| role | high-tier 变异源（最复杂） |

## 关键发现：新引擎已有简化版 learn()

[engine/src/xkx/runtime/commands.py:1446-1516](../../../../src/xkx/runtime/commands.py) 已实现 `learn()` 主流程
（is_busy/is_fighting/potential/apprentice/query_skill/gain/improve_skill/combat_exp 门控/jing 消耗）。

**pilot 测的是"补 8 项后置分支到行为等价"，非从零写。**

## 三态对照表（依赖能力）

| 能力 | 状态 | 引擎位置 |
|---|---|---|
| is_busy | 已有 | runtime/skill.py:69 |
| is_fighting | 已有 | runtime/commands.py:1470 |
| query/add/set/add_temp | 已有 | runtime/query.py |
| query_skill / improve_skill | 已有 | runtime/query.py:490 / runtime/skill.py:78 |
| query_int | 已有 | runtime/commands.py:1488 |
| is_apprentice_of | 已有 | runtime/commands.py:1160 |
| SKILL_D.type | 已有 | combat/context.py:63 |
| SKILL_D.valid_learn | 部分 | combat/context.py:64（bool，无 me 逻辑） |
| present / environment | 部分 | runtime/query.py:467,473 |
| receive_damage | 部分 | 仅 combat apply；runtime 直接 vitals.jing-= -> 桩 |
| is_spouse_of | 无 | 桩 stubs.py |
| recognize_apprentice | 无 | 桩 stubs.py |
| prevent_learn | 无 | 桩 stubs.py |
| query_skill_name | 无 | 桩 stubs.py |
| to_chinese | 无 | 桩 stubs.py |
| married_times / spouse/title | 无 | dbase 无映射（后置） |
| userp | 无 | - |

## 6 桩依赖（stubs.py 已建）

| 桩 | xue.c 调用位置 | 说明 |
|---|---|---|
| is_spouse_of(me, ob) | L53,80,91,93 | 双向配偶校验（桩默认 False） |
| recognize_apprentice(me) | L53 | ob 侧付费认可（桩默认 False） |
| prevent_learn(me, skill) | L74 | 师傅侧门控（桩默认 False=可教） |
| query_skill_name(skill, level) | L124 | 招式名（桩默认 None） |
| to_chinese(skill) | L102,107 | 技能中文名（桩默认 skill_id） |
| receive_damage(entity, vital, amount) | L110,148 | 通用 vital 扣减 clamp（桩已实现） |

## 8 项后置分支（待人工补全到行为等价）

1. 峨嵋减速 L58-68（峨嵋派+非女+query_int<20+random(25) -> slow_factor=2）
2. spouse 检查 L80-88（is_spouse_of + married_times 惩罚 + combat_exp<10000 门控）
3. recognize_apprentice 付费 L50-56
4. prevent_learn L74（师傅拒绝教）
5. query_skill_name L124（招式名文本分支）
6. to_chinese L102,107（技能中文名）
7. teacher jing 消耗 L109-115（ob->receive_damage("jing", ...)）
8. env/no_teach L104-105（师傅不教）

## effort_record 模板（人工填 effort 后转 effort_records.jsonl）

reusable_api / missing_api 已填，effort 字段待人工计时填。

```json
{
  "file": "cmds/skill/xue.c", "func": "main", "subsystem": "cmds",
  "status": "pending", "func_kind": "logic", "tier": "high", "call_count": 53,
  "corrected_status": "", "corrected_kind": "", "misclassified": false, "misclass_reason": "",
  "effort": {"read_spec": 0, "write_code": 0, "write_test": 0, "debug": 0},
  "reusable_api": ["is_busy","is_fighting","query/add/set/add_temp","query_skill","improve_skill","query_int","is_apprentice_of","name","SKILL_D.type","SKILL_D.valid_learn(bool)"],
  "missing_api": ["is_spouse_of(stub)","recognize_apprentice(stub)","prevent_learn(stub)","query_skill_name(stub)","to_chinese(stub)","receive_damage(stub)","married_times","spouse/title","userp"],
  "notes": "已有 learn()（commands.py:1446-1516）覆盖主流程。测补 8 项后置分支。6 桩已建 stubs.py。effort 待人工计时填。"
}
```

## 迁移代码落点

- 迁移代码：`samples/xue_c_main.py`（人工写，补 8 后置分支）
- 测试：`samples/test_xue_c_main.py`（人工写，3 处 RNG + spouse + linji-zhuang 特例）
- 工时记录：测完把上面 JSON 的 effort 填真实值，追加到 `effort_records.jsonl`

## 估时锚点

ADR-0048 调研 high-tier 锚点 120-190 min（xue.c:main 高位估 190）。
子步骤粗估：读规格 15-25 / 补桩 25-40 / 写后置分支 35-55 / 写测试 25-40 / 调试 15-30 = 115-190 min。
