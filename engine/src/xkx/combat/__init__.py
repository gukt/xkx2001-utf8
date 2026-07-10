"""战斗子系统：resolve_attack 纯函数 + seeded RNG + 副作用账本.

从 LPC ``adm/daemons/combatd.c`` 的 ``do_attack`` 七步管线提取（见 ADR-0002）。
combat 确定性范围 = combat-only（全仿真确定性后置 M3 后，见 04 §六）。
副作用按"文本与状态交织真实顺序"记入 ``CombatRoundResult.effects`` 账本，
显式否定"先纯计算后批量 apply"（01 子系统5 / 05 §五 dissent）。
"""
