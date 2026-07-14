"""SchemaValidator 四道校验（S4 / ADR-0008）。

阶段 -1 最小实现：
1. SchemaValidator：pydantic strict 模式 + 未知字段警告（防 neili/max_neili 类静默偏差）
2. CapabilityAuditor：NPC 能力声明检查（attack_skill 是否在 skills 中）
3. ResourceBudgetChecker：数值非负（资源上限 / 奖励经验等）
4. DependencyResolver：引用完整性（room/npc/quest/rule 间的 id 引用）

完整四道校验（jsonschema / CPK manifest / fuel / networkx）后置 M2 / 阶段 0。
"""

from __future__ import annotations

from pydantic import ConfigDict, ValidationError

from xkx.dsl.layer0 import NpcDef, QuestDef, QuestObjective, QuestReward, RoomDef
from xkx.dsl.layer1 import EventRule


class _RoomDefStrict(RoomDef):
    """带 extra='forbid' 的 RoomDef，用于未知字段检测；IR 含 kind 元数据。"""

    kind: str = ""
    model_config = ConfigDict(extra="forbid")


class _NpcDefStrict(NpcDef):
    """带 extra='forbid' 的 NpcDef，用于未知字段检测；IR 含 kind 元数据。"""

    kind: str = ""
    model_config = ConfigDict(extra="forbid")


class _QuestObjectiveStrict(QuestObjective):
    model_config = ConfigDict(extra="forbid")


class _QuestRewardStrict(QuestReward):
    model_config = ConfigDict(extra="forbid")


class _QuestDefStrict(QuestDef):
    """带 extra='forbid' 的 QuestDef，用于未知字段检测；IR 含 kind 元数据。"""

    kind: str = ""
    model_config = ConfigDict(extra="forbid")


class _EventRuleStrict(EventRule):
    """带 extra='forbid' 的 EventRule，用于未知字段检测。"""

    kind: str = ""
    model_config = ConfigDict(extra="forbid")


class SceneValidator:
    """场景 IR 四道校验器（阶段 -1 最小实现）。"""

    def __init__(self, ir: dict) -> None:
        self.ir = ir
        self._room_ids: set[str] = set()
        self._npc_ids: set[str] = set()
        self._quest_ids: set[str] = set()
        self.issues: list[str] = []

    def validate(self) -> list[str]:
        """跑四道校验，返回问题列表（空 = 无问题）。"""
        self.issues = []
        self._collect_ids()
        self._schema_validator()
        self._capability_auditor()
        self._resource_budget_checker()
        self._dependency_resolver()
        return self.issues

    def _collect_ids(self) -> None:
        self._room_ids = {r.get("id") for r in self.ir.get("rooms", []) if r.get("id")}
        self._npc_ids = {n.get("id") for n in self.ir.get("npcs", []) if n.get("id")}
        self._quest_ids = {q.get("id") for q in self.ir.get("quests", []) if q.get("id")}

    def _schema_validator(self) -> None:
        """SchemaValidator：结构校验 + 未知字段警告。"""
        for r in self.ir.get("rooms", []):
            self._validate_strict(_RoomDefStrict, r, "room")
        for n in self.ir.get("npcs", []):
            self._validate_strict(_NpcDefStrict, n, "npc")
        for q in self.ir.get("quests", []):
            self._validate_strict(_QuestDefStrict, q, "quest")
        for rule in self.ir.get("rules", []):
            self._validate_strict(_EventRuleStrict, rule, "rule")

    def _validate_strict(self, model_cls, data: dict, label: str) -> None:
        try:
            model_cls(**data)
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(x) for x in err.get("loc", []))
                self.issues.append(
                    f"[schema] {label} `{data.get('id', '?')}`: {err['msg']} (at {loc})"
                )

    def _capability_auditor(self) -> None:
        """CapabilityAuditor：NPC 能力声明检查（S4 最小）。"""
        for n in self.ir.get("npcs", []):
            skills = n.get("skills", {}) or {}
            attack_skill = n.get("attack_skill", "unarmed")
            if attack_skill != "unarmed" and attack_skill not in skills:
                self.issues.append(
                    f"[capability] npc `{n.get('id')}`: attack_skill `{attack_skill}` "
                    f"不在 skills {list(skills)} 中"
                )

    def _resource_budget_checker(self) -> None:
        """ResourceBudgetChecker：数值非负检查（S4 最小）。"""
        for n in self.ir.get("npcs", []):
            for key in ("max_qi", "max_jing", "max_jingli", "max_neili", "combat_exp"):
                val = n.get(key, 0)
                if val < 0:
                    self.issues.append(f"[resource] npc `{n.get('id')}`: {key}={val} 不可为负")
        for q in self.ir.get("quests", []):
            exp = q.get("reward", {}).get("exp", 0)
            if exp < 0:
                self.issues.append(f"[resource] quest `{q.get('id')}`: reward.exp={exp} 不可为负")

    def _dependency_resolver(self) -> None:
        """DependencyResolver：引用完整性（S4 最小）。"""
        # room.objects / room.exits
        for r in self.ir.get("rooms", []):
            room_id = r.get("id")
            for npc_id in r.get("objects", {}):
                if npc_id not in self._npc_ids:
                    self.issues.append(f"[dependency] room `{room_id}`: 引用未知 npc `{npc_id}`")
            for direction, target_id in r.get("exits", {}).items():
                if target_id not in self._room_ids:
                    self.issues.append(
                        f"[dependency] room `{room_id}`: exit `{direction}` "
                        f"指向未知 room `{target_id}`"
                    )
        # quest giver / objectives npc_id + room_id（M3-1 ADR-0032 决策 3 多步 chain）
        for q in self.ir.get("quests", []):
            qid = q.get("id")
            giver = q.get("giver")
            if giver and giver not in self._npc_ids:
                self.issues.append(f"[dependency] quest `{qid}`: giver `{giver}` 不是已知 npc")
            # objectives list 优先；向后兼容旧 objective 单数
            objs = q.get("objectives") or []
            old = q.get("objective")
            if old and not objs:
                objs = [old]
            for obj in objs:
                npc_id = obj.get("npc_id")
                if npc_id and npc_id not in self._npc_ids:
                    self.issues.append(
                        f"[dependency] quest `{qid}`: objective.npc_id `{npc_id}` 不是已知 npc"
                    )
                room_id = obj.get("room_id")
                if room_id and room_id not in self._room_ids:
                    self.issues.append(
                        f"[dependency] quest `{qid}`: objective.room_id `{room_id}` 不是已知 room"
                    )
        # rule npc_id
        for rule in self.ir.get("rules", []):
            npc_id = rule.get("npc_id")
            if npc_id and npc_id not in self._npc_ids:
                self.issues.append(
                    f"[dependency] rule `{rule.get('id')}`: npc_id `{npc_id}` 不是已知 npc"
                )


def validate(ir: dict) -> list[str]:
    """便捷函数：校验场景 IR，返回问题列表。"""
    return SceneValidator(ir).validate()
