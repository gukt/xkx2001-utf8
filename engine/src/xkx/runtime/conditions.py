"""condition 系统（阶段 1 T1，ADR-0018）。

ConditionHandler.on_tick 对齐 LPC ``feature/condition.c`` 的 ``update_condition()``，
返回组合结构 ``ConditionTickResult``（纯函数，不 mutate 现场状态），由
ConditionSystem 统一 apply。派生变更审计轨迹（dissent 7）。

Effect 作为独立实体（EffectComp attach 到 effect 实体，``target_id`` 指向被作用
实体），支持一个实体同时承载多个 condition。

T1.4 只定契约 + 框架，具体 condition 类型（蛇毒/醉/失明）按 08 §七"实现到时才补"。
[ADR-0018](../../../docs/adr/ADR-0018-conditionhandler-on-tick-contract.md)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from xkx.combat.result import (
    LEDGER_EFFECT,
    Effect,
    LedgerEntry,
)
from xkx.runtime.components import EffectComp
from xkx.runtime.ecs import World
from xkx.runtime.systems import System

# LPC include/condition.h
CND_CONTINUE = 1
CND_NO_HEAL_UP = 2


@dataclass
class ConditionTickResult:
    """ConditionHandler.on_tick 的返回值（ADR-0018 组合结构，不 mutate 现场状态）。

    - ``effects``: 即时副作用（DoT 扣血/heal 等），按触发顺序
    - ``messages``: 文本（毒发/醉倒等），按触发顺序
    - ``condition_deltas``: ``{effect_id: 新剩余 duration}``（衰减后）
    - ``completed``: 到期移除的 effect_id 列表
    - ``flags``: LPC CND_NO_HEAL_UP 等（跨 System 通信）
    - ``ledger``: messages 与 effects 的交织顺序（对齐 combat ledger，dissent 7）
    """

    effects: list[Effect] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    condition_deltas: dict[str, int] = field(default_factory=dict)
    completed: list[str] = field(default_factory=list)
    flags: int = 0
    ledger: list[LedgerEntry] = field(default_factory=list)


class ConditionHandler:
    """condition 系统核心（ADR-0018），对应 LPC ``feature/condition.c`` 的 ``update_condition()``。

    on_tick 是纯函数：只读 EffectComp 快照 + tick，返回 ConditionTickResult，不
    mutate 现场状态。ConditionSystem.update 调本方法后统一 apply。

    非均匀 tick：只处理 ``next_tick <= tick`` 的 EffectComp（ADR-0018 §3）。
    """

    def on_tick(self, world: World, tick: int) -> ConditionTickResult:
        """遍历到期 EffectComp，返回组合结构（不 mutate world）。"""
        result = ConditionTickResult()
        for effect_eid in world.entities_with(EffectComp):
            eff = world.get(effect_eid, EffectComp)
            if eff is None or eff.next_tick > tick:
                continue
            self._trigger(result, eff)
        return result

    @staticmethod
    def _trigger(result: ConditionTickResult, eff: EffectComp) -> None:
        """触发单个到期 EffectComp，填充 result（不 mutate world）。"""
        # 生成即时副作用 Effect（DoT 扣血 / buff 等），target_id 指向被作用实体
        if eff.amount != 0:
            effect = Effect(
                kind=eff.kind,
                target_id=eff.target_id,
                amount=eff.amount,
                detail=eff.detail,
            )
            result.effects.append(effect)
            result.ledger.append(LedgerEntry(entry_type=LEDGER_EFFECT, effect=effect))
        # 衰减 duration（duration=0 表示永久，不衰减）
        if eff.duration > 0:
            new_duration = eff.duration - 1
            result.condition_deltas[eff.effect_id] = new_duration
            if new_duration <= 0:
                result.completed.append(eff.effect_id)
        # flags 传递（CND_NO_HEAL_UP 等，跨 System 通信）
        if eff.flags & CND_NO_HEAL_UP:
            result.flags |= CND_NO_HEAL_UP


class ConditionSystem(System):
    """condition 系统 ECS System（ADR-0014，tick 驱动）。

    update 调 ConditionHandler.on_tick 得到 ConditionTickResult，统一 apply 到 world
    （apply effects + 衰减 duration + 移除 completed + 更新 next_tick）。
    """

    name = "ConditionSystem"

    def __init__(self) -> None:
        self._handler = ConditionHandler()

    def update(self, world: World, tick: int) -> None:
        result = self._handler.on_tick(world, tick)
        # apply 即时副作用（按账本顺序）
        from xkx.runtime.world import apply_effects

        apply_effects(world, result.effects)
        # 衰减 duration / 移除 completed / 更新 next_tick
        # 物化实体列表，因遍历中可能 remove（swap-remove 不安全于遍历中）
        for effect_eid in list(world.entities_with(EffectComp)):
            eff = world.get(effect_eid, EffectComp)
            if eff is None:
                continue
            if eff.effect_id in result.completed:
                world.remove(effect_eid, EffectComp)
                continue
            if eff.effect_id in result.condition_deltas:
                eff.duration = result.condition_deltas[eff.effect_id]
            if eff.next_tick <= tick:
                eff.next_tick = tick + eff.tick_interval

        # ADR-0022 §4：mutation 后 mark_dirty 供 StorageSystem 周期 persist
        # （整合遗留：EffectComp duration/next_tick 变更 + apply_effects 改 Vitals）
        storage = getattr(world, "storage_system", None)
        if storage is not None:
            for e in result.effects:
                storage.mark_dirty(e.target_id)
            for effect_eid in world.entities_with(EffectComp):
                storage.mark_dirty(effect_eid)
