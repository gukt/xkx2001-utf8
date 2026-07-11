"""CombatSystem：tick 驱动的战斗派生变更处理器（ADR-0023 决策 2）。

职责承重决策（ADR-0023）：
- **tick 驱动**：每 tick 遍历有敌对关系的实体，调 ``resolve_attack`` -> ``apply_effects``。
- **快照边界**：调 ``resolve_attack`` 前从组件构建 ``CombatContext`` 快照，
  ``resolve_attack`` 只读快照不 mutate 现场，``apply_effects`` 按账本顺序写回。
- **input log 记录**：战斗期间的攻击输入按序记录到 input log（确定性重放用）。
- **确定性重放入口**：提供 ``replay`` 转发到 ``replay.replay``（纯函数，不依赖 ECS）。
- **不套 Command 模式**：tick mutation 不走 Command 管线（System tick 派生变更不经
  Command，CLAUDE.md 不变量 + ADR-0020）。

combat-only 确定性边界（ADR-0023 决策 1）：只有 ``resolve_attack`` + ``apply_effects``
链路在确定性范围内；heal/exp/condition 等 System 的 tick mutation 不在此范围。

文件边界：CombatSystem 作为 ``combat/system.py`` 独立实现，不接入 ``runtime/world.py``
的 System 注册（留给后续整合）。接口对齐 ``runtime.systems.System.update(world, tick)``
（鸭子类型），但不继承 ``System`` 类（避免 combat -> runtime 依赖，combat 包自包含）。
"""

from __future__ import annotations

from xkx.combat.context import CombatantSnapshot, CombatContext
from xkx.combat.replay import CombatSnapshot, InputEntry
from xkx.combat.replay import replay as replay_fn
from xkx.combat.resolve_attack import resolve_attack
from xkx.combat.result import (
    KIND_DAMAGE,
    KIND_EXP,
    KIND_JINGLI,
    KIND_POTENTIAL,
    KIND_SKILL_IMPROVE,
    KIND_WOUND,
    LEDGER_EFFECT,
    LEDGER_MESSAGE,
    LEDGER_SUBRESULT,
    CombatRoundResult,
    Effect,
)
from xkx.combat.rng import DeterministicRNG


class CombatSystem:
    """tick 驱动的战斗 System（ADR-0023 决策 2）。

    独立实现（不继承 ``runtime.systems.System``，避免 combat -> runtime 依赖）。
    接口对齐 ``System.update(world, tick)``（鸭子类型），后续整合时接入 world.py。

    用法（单 tick）：
        sys = CombatSystem()
        results = sys.tick(snapshot, seed)
        # results: list[CombatRoundResult]，按顺序 apply_effects 到 ECS

    重放（确定性）：
        results = sys.replay(snapshot, seed, input_log)
        # 同 snapshot + seed + input_log -> 同输出
    """

    name: str = "CombatSystem"

    def __init__(self) -> None:
        # input log：本 tick 内的攻击输入按序记录（确定性重放用）
        self._input_log: list[InputEntry] = []

    def record_input(self, entry: InputEntry) -> None:
        """记录一条战斗输入到 input log（ADR-0023 决策 2）。"""
        self._input_log.append(entry)

    def tick(self, snapshot: CombatSnapshot, seed: int) -> list[CombatRoundResult]:
        """单 tick 战斗驱动：构建 CombatContext -> resolve_attack -> 返回结果。

        本 tick 的攻击输入从 ``snapshot`` 的敌对关系派生（每对敌对实体一次攻击），
        同时记录到 input log 供重放。调用方拿到结果后按顺序 ``apply_effects`` 到 ECS。

        不套 Command（CLAUDE.md 不变量）：tick mutation 通过 Effect 账本记录，
        不经 Command 管线。
        """
        self._input_log.clear()
        results: list[CombatRoundResult] = []
        seen_pairs: set[tuple[int, int]] = set()
        seq = 0
        for attacker_id, attacker in snapshot.combatants.items():
            # 敌对关系由快照外维护（T6 最小：遍历所有 combatant 对，按 seq 顺序）
            # 实际敌对关系从 CombatState.enemies 取，T6 快照简化为 combatants dict
            for victim_id, victim in snapshot.combatants.items():
                if attacker_id == victim_id:
                    continue
                pair = (attacker_id, victim_id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                # T6 最小：每对 combatant 一次攻击（attacker -> victim）
                # 实际 fight() 语义（主动性判定）后置 T8
                entry = InputEntry(
                    attacker_id=attacker_id,
                    victim_id=victim_id,
                    attack_type=0,
                    seq=seq,
                )
                self.record_input(entry)
                ctx = CombatContext(
                    attacker=attacker.model_copy(),
                    victim=victim.model_copy(),
                    seed=seed + seq,
                    limbs=snapshot.limbs,
                )
                results.append(resolve_attack(ctx))
                seq += 1
        return results

    def replay(
        self,
        snapshot: CombatSnapshot,
        seed: int,
        input_log: list[InputEntry],
    ) -> list[CombatRoundResult]:
        """确定性重放入口（ADR-0023 决策 2/3）。

        转发到 ``replay.replay`` 纯函数。同 snapshot + seed + input_log -> 同输出。
        不依赖运行时 ECS。
        """
        return replay_fn(snapshot, seed, input_log)

    @staticmethod
    def apply_effects(
        snapshot: CombatantSnapshot,
        effects: list[Effect],
    ) -> CombatantSnapshot:
        """按账本顺序把 Effect apply 到快照副本（模拟 receive_damage/wound clamp）。

        用于确定性重放后的状态推进（不依赖 ECS）。三层资源不变量 apply 后保持。
        """
        s = snapshot.model_copy()
        for e in effects:
            if e.target_id != s.entity_id:
                continue
            if e.kind == KIND_DAMAGE:
                s.qi = max(0, s.qi - e.amount)
            elif e.kind == KIND_WOUND:
                s.eff_qi = max(0, s.eff_qi - e.amount)
                s.qi = min(s.qi, s.eff_qi)
            elif e.kind == KIND_EXP:
                s.combat_exp += e.amount
            elif e.kind == KIND_POTENTIAL:
                s.potential = min(s.max_potential, s.potential + e.amount)
            elif e.kind == KIND_JINGLI:
                s.jingli = max(0, min(s.max_jingli, s.jingli + e.amount))
            elif e.kind == KIND_SKILL_IMPROVE and e.detail:
                s.skills[e.detail] = s.skills.get(e.detail, 0) + e.amount
        return s

    @staticmethod
    def flatten_messages(result: CombatRoundResult) -> list[str]:
        """展开 CombatRoundResult 的消息（含 riposte 子回合嵌入）。

        子回合的 messages 整体嵌入父回合的嵌入位置（保持交织顺序）。
        调用方用此方法拿到完整的消息序列用于下发。
        """
        messages: list[str] = []
        for entry in result.ledger:
            if entry.entry_type == LEDGER_MESSAGE:
                messages.append(entry.text)
            elif entry.entry_type == LEDGER_SUBRESULT and entry.sub_result is not None:
                messages.extend(CombatSystem.flatten_messages(entry.sub_result))
        return messages

    @staticmethod
    def flatten_effects(result: CombatRoundResult) -> list[Effect]:
        """展开 CombatRoundResult 的副作用（含 riposte 子回合嵌入）。

        子回合的 effects 整体嵌入父回合的嵌入位置（保持交织顺序）。
        调用方用此方法拿到完整的 effect 序列用于 apply。
        """
        effects: list[Effect] = []
        for entry in result.ledger:
            if entry.entry_type == LEDGER_EFFECT and entry.effect is not None:
                effects.append(entry.effect)
            elif entry.entry_type == LEDGER_SUBRESULT and entry.sub_result is not None:
                effects.extend(CombatSystem.flatten_effects(entry.sub_result))
        return effects


def make_rng(seed: int) -> DeterministicRNG:
    """构造 DeterministicRNG（供外部测试/重放用）。"""
    return DeterministicRNG(seed)
