"""pilot 共享桩：新引擎缺失的 LPC 等价行为占位。

ADR-0048 决策 2：评审团发现多个 pending/logic 样本共用这些缺口 API，
pilot 前一次性补建最小可用桩，避免每样本重复建。

桩为"最小等价行为占位"，具体接口与实现按 pilot 实测时首个依赖样本
（xue.c:main）的需求补全。本文件先记录待建清单，实测时填函数。

注意：这是测量用桩，不是 src/xkx 正式实现。落一次性目录（ADR-0048 决策 8）。

待建桩清单（调研 + 评审团核实）：
- SKILL_D->valid_learn / type / query_skill_name  （xue.c / tieyanling.c / songshan-jian.c 等依赖）
- recognize_apprentice / prevent_learn             （xue.c / tieyanling.c 拜师请教链）
- is_spouse_of                                      （xue.c 配偶婚次惩罚）
- receive_damage                                    （xue.c / tieyanling.c 教官 jing 扣耗）
"""

from __future__ import annotations

# TODO(pilot): 首个依赖样本（xue.c:main）实测时，在此补建上述桩函数。
