"""三种对象模型的纯逻辑对照（无 I/O）。

问题：UGC 创作者组合实体 / 热挂能力 / 跨实体查询时，
ECS、继承树、Feature 混入各自的摩擦在哪？

动作面统一：spawn_* / attach_* / query_* / tick / select。
每种模型内部自己决定「怎么表示」与「要记什么 friction」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

# ── 共享动作与观测 ──────────────────────────────────────


@dataclass
class Friction:
    """一次操作的架构代价说明（给人手感，不是性能指标）。"""

    action: str
    model: str
    note: str
    cost: str  # low | medium | high | blocked


@dataclass
class Snapshot:
    model: str
    entities: list[dict[str, Any]]
    selected: int | None
    last_query: list[str]
    friction: list[Friction]
    log: list[str]


class WorldModel(Protocol):
    name: str

    def spawn_guard(self) -> Friction: ...
    def spawn_merchant(self) -> Friction: ...
    def spawn_guard_merchant(self) -> Friction: ...
    def attach_poison(self) -> Friction: ...
    def attach_rideable(self) -> Friction: ...
    def query_sellers(self) -> Friction: ...
    def query_combatants(self) -> Friction: ...
    def query_living(self) -> Friction: ...
    def tick(self) -> Friction: ...
    def select_next(self) -> None: ...
    def snapshot(self) -> Snapshot: ...


def _push(frictions: list[Friction], cap: int = 8) -> None:
    del frictions[:-cap]


# ── 1) ECS ──────────────────────────────────────────────


@dataclass
class _EcsEntity:
    eid: int
    comps: dict[str, dict[str, Any]] = field(default_factory=dict)


class EcsWorld:
    name = "ecs"

    def __init__(self) -> None:
        self._next = 1
        self._ents: dict[int, _EcsEntity] = {}
        self._selected: int | None = None
        self._last_query: list[str] = []
        self._friction: list[Friction] = []
        self._log: list[str] = []

    def _spawn(self, *comp_names: str) -> int:
        eid = self._next
        self._next += 1
        comps: dict[str, dict[str, Any]] = {}
        for name in comp_names:
            comps[name] = _default_comp(name)
        self._ents[eid] = _EcsEntity(eid=eid, comps=comps)
        self._selected = eid
        return eid

    def spawn_guard(self) -> Friction:
        eid = self._spawn("Identity", "Vitals", "Combat", "Room")
        self._ents[eid].comps["Identity"]["name"] = "守卫"
        f = Friction(
            "spawn_guard",
            self.name,
            f"e{eid} = Identity+Vitals+Combat+Room（组合，无新类）",
            "low",
        )
        self._note(f, f"spawn guard e{eid}")
        return f

    def spawn_merchant(self) -> Friction:
        eid = self._spawn("Identity", "Vitals", "Shop", "Room")
        self._ents[eid].comps["Identity"]["name"] = "商人"
        f = Friction(
            "spawn_merchant",
            self.name,
            f"e{eid} = Identity+Vitals+Shop+Room",
            "low",
        )
        self._note(f, f"spawn merchant e{eid}")
        return f

    def spawn_guard_merchant(self) -> Friction:
        eid = self._spawn("Identity", "Vitals", "Combat", "Shop", "Room")
        self._ents[eid].comps["Identity"]["name"] = "守卫商人"
        self._ents[eid].comps["Shop"]["stock"] = ["茶", "饼", "刀"]
        f = Friction(
            "spawn_guard_merchant",
            self.name,
            f"e{eid} 直接叠 Combat+Shop；UGC 声明组件列表即可，无菱形继承",
            "low",
        )
        self._note(f, f"spawn guard+merchant e{eid}")
        return f

    def attach_poison(self) -> Friction:
        if self._selected is None or self._selected not in self._ents:
            return self._blocked("attach_poison", "无选中实体")
        e = self._ents[self._selected]
        if "Vitals" not in e.comps:
            return self._blocked("attach_poison", "无 Vitals，毒无从挂（组件前置条件）")
        e.comps["Poisoned"] = _default_comp("Poisoned")
        f = Friction(
            "attach_poison",
            self.name,
            f"e{e.eid} 热挂 Poisoned 组件；现有 System 下一 tick 自动扫到",
            "low",
        )
        self._note(f, f"attach Poisoned → e{e.eid}")
        return f

    def attach_rideable(self) -> Friction:
        if self._selected is None or self._selected not in self._ents:
            return self._blocked("attach_rideable", "无选中实体")
        e = self._ents[self._selected]
        e.comps["Rideable"] = _default_comp("Rideable")
        f = Friction(
            "attach_rideable",
            self.name,
            "数据侧只需加组件；但引擎还缺 RideSystem——UGC 新能力常要「数据+系统」两半",
            "medium",
        )
        self._note(f, f"attach Rideable → e{e.eid}（尚无 RideSystem）")
        return f

    def query_sellers(self) -> Friction:
        hits = [e for e in self._ents.values() if "Shop" in e.comps]
        self._last_query = [f"e{e.eid}:{e.comps.get('Identity', {}).get('name', '?')}" for e in hits]
        f = Friction(
            "query_sellers",
            self.name,
            f"entities_with(Shop) → {len(hits)}；查询按组件天然索引",
            "low",
        )
        self._note(f, f"query sellers: {self._last_query}")
        return f

    def query_combatants(self) -> Friction:
        hits = [e for e in self._ents.values() if "Combat" in e.comps]
        self._last_query = [f"e{e.eid}" for e in hits]
        f = Friction("query_combatants", self.name, f"entities_with(Combat) → {len(hits)}", "low")
        self._note(f, f"query combatants: {self._last_query}")
        return f

    def query_living(self) -> Friction:
        hits = [e for e in self._ents.values() if "Vitals" in e.comps]
        self._last_query = [f"e{e.eid}" for e in hits]
        f = Friction("query_living", self.name, f"entities_with(Vitals) → {len(hits)}", "low")
        self._note(f, f"query living: {self._last_query}")
        return f

    def tick(self) -> Friction:
        healed, poisoned, fought = 0, 0, 0
        for e in self._ents.values():
            if "Vitals" in e.comps:
                e.comps["Vitals"]["hp"] = min(
                    e.comps["Vitals"]["max_hp"],
                    e.comps["Vitals"]["hp"] + 1,
                )
                healed += 1
            if "Poisoned" in e.comps and "Vitals" in e.comps:
                e.comps["Vitals"]["hp"] = max(0, e.comps["Vitals"]["hp"] - 3)
                e.comps["Poisoned"]["ticks_left"] -= 1
                if e.comps["Poisoned"]["ticks_left"] <= 0:
                    del e.comps["Poisoned"]
                poisoned += 1
            if "Combat" in e.comps:
                e.comps["Combat"]["rage"] += 1
                fought += 1
        f = Friction(
            "tick",
            self.name,
            f"HealSystem({healed}) + PoisonSystem({poisoned}) + CombatSystem({fought})；"
            "行为按组件横切，UGC 不必改基类",
            "low",
        )
        self._note(f, f"tick heal={healed} poison={poisoned} combat={fought}")
        return f

    def select_next(self) -> None:
        ids = sorted(self._ents)
        if not ids:
            self._selected = None
            return
        if self._selected is None or self._selected not in self._ents:
            self._selected = ids[0]
            return
        i = ids.index(self._selected)
        self._selected = ids[(i + 1) % len(ids)]

    def snapshot(self) -> Snapshot:
        ents = []
        for e in sorted(self._ents.values(), key=lambda x: x.eid):
            ents.append(
                {
                    "id": e.eid,
                    "selected": e.eid == self._selected,
                    "kind": "entity",
                    "parts": sorted(e.comps),
                    "state": {k: dict(v) for k, v in e.comps.items()},
                }
            )
        return Snapshot(self.name, ents, self._selected, list(self._last_query), list(self._friction), list(self._log))

    def _note(self, f: Friction, line: str) -> None:
        self._friction.append(f)
        _push(self._friction)
        self._log.append(line)
        _push(self._log, 6)

    def _blocked(self, action: str, why: str) -> Friction:
        f = Friction(action, self.name, why, "blocked")
        self._note(f, f"BLOCKED {action}: {why}")
        return f


# ── 2) 继承树 ───────────────────────────────────────────


class _Obj:
    kind: str = "Object"

    def __init__(self, oid: int, name: str) -> None:
        self.oid = oid
        self.name = name

    def describe_parts(self) -> list[str]:
        return [self.kind]

    def as_state(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind}


class _Living(_Obj):
    kind = "Living"

    def __init__(self, oid: int, name: str) -> None:
        super().__init__(oid, name)
        self.hp = 20
        self.max_hp = 20

    def as_state(self) -> dict[str, Any]:
        return {**super().as_state(), "hp": self.hp, "max_hp": self.max_hp}


class _Guard(_Living):
    kind = "Guard"

    def __init__(self, oid: int, name: str) -> None:
        super().__init__(oid, name)
        self.rage = 0

    def as_state(self) -> dict[str, Any]:
        return {**super().as_state(), "rage": self.rage}


class _Merchant(_Living):
    kind = "Merchant"

    def __init__(self, oid: int, name: str) -> None:
        super().__init__(oid, name)
        self.stock = ["茶", "饼"]

    def as_state(self) -> dict[str, Any]:
        return {**super().as_state(), "stock": list(self.stock)}


class _GuardMerchant(_Guard, _Merchant):  # 菱形：Living 被继承两次
    kind = "GuardMerchant"

    def __init__(self, oid: int, name: str) -> None:
        # 显式拼装——原型刻意暴露「组合能力 = 新子类 + MRO 头疼」
        _Living.__init__(self, oid, name)
        self.rage = 0
        self.stock = ["茶", "饼", "刀"]

    def describe_parts(self) -> list[str]:
        return ["GuardMerchant", "← Guard+Merchant 新子类"]

    def as_state(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "rage": self.rage,
            "stock": list(self.stock),
        }


class _PoisonedGuard(_Guard):
    kind = "PoisonedGuard"

    def __init__(self, oid: int, name: str, ticks: int = 3) -> None:
        super().__init__(oid, name)
        self.poison_ticks = ticks

    def as_state(self) -> dict[str, Any]:
        return {**super().as_state(), "poison_ticks": self.poison_ticks}


class InheritanceWorld:
    name = "inheritance"

    def __init__(self) -> None:
        self._next = 1
        self._ents: dict[int, _Obj] = {}
        self._selected: int | None = None
        self._last_query: list[str] = []
        self._friction: list[Friction] = []
        self._log: list[str] = []
        self._class_count = 5  # Living/Guard/Merchant/GuardMerchant/PoisonedGuard 已写死

    def spawn_guard(self) -> Friction:
        oid = self._alloc(_Guard(self._next, "守卫"))
        f = Friction("spawn_guard", self.name, f"o{oid} = Guard 子类实例", "low")
        self._note(f, f"spawn Guard o{oid}")
        return f

    def spawn_merchant(self) -> Friction:
        oid = self._alloc(_Merchant(self._next, "商人"))
        f = Friction("spawn_merchant", self.name, f"o{oid} = Merchant 子类实例", "low")
        self._note(f, f"spawn Merchant o{oid}")
        return f

    def spawn_guard_merchant(self) -> Friction:
        oid = self._alloc(_GuardMerchant(self._next, "守卫商人"))
        self._class_count = max(self._class_count, 5)
        f = Friction(
            "spawn_guard_merchant",
            self.name,
            f"o{oid} 需要预先写好 GuardMerchant 子类（MRO/菱形）；"
            f"UGC 每多一种组合就可能 +1 类（当前硬编码类数≈{self._class_count}）",
            "high",
        )
        self._note(f, f"spawn GuardMerchant o{oid}（新子类）")
        return f

    def attach_poison(self) -> Friction:
        if self._selected is None or self._selected not in self._ents:
            return self._blocked("attach_poison", "无选中实体")
        obj = self._ents[self._selected]
        if isinstance(obj, _PoisonedGuard):
            obj.poison_ticks = 3
            f = Friction("attach_poison", self.name, "已是 PoisonedGuard，重置 ticks", "medium")
            self._note(f, f"reset poison o{obj.oid}")
            return f
        if type(obj) is _Guard:
            # 运行时换类——继承模型的典型痛：状态要拷、身份变了
            poisoned = _PoisonedGuard(obj.oid, obj.name)
            poisoned.hp = obj.hp
            poisoned.rage = obj.rage
            self._ents[obj.oid] = poisoned
            self._class_count += 1
            f = Friction(
                "attach_poison",
                self.name,
                "Guard→PoisonedGuard 换类/拷状态；Merchant/GuardMerchant 还没有 Poisoned* 子类",
                "high",
            )
            self._note(f, f"reclass Guard→PoisonedGuard o{obj.oid}")
            return f
        return self._blocked(
            "attach_poison",
            f"{obj.kind} 无对应 Poisoned 子类——组合爆炸：要 PoisonedMerchant、PoisonedGuardMerchant…",
        )

    def attach_rideable(self) -> Friction:
        if self._selected is None or self._selected not in self._ents:
            return self._blocked("attach_rideable", "无选中实体")
        obj = self._ents[self._selected]
        return self._blocked(
            "attach_rideable",
            f"要对 {obj.kind} 可骑，得先写 Rideable{obj.kind} 子类（或改基类污染所有 Living）",
        )

    def query_sellers(self) -> Friction:
        hits = [o for o in self._ents.values() if isinstance(o, _Merchant)]
        self._last_query = [f"o{o.oid}:{o.kind}" for o in hits]
        f = Friction(
            "query_sellers",
            self.name,
            f"isinstance(Merchant) → {len(hits)}；靠继承关系，混入非 Merchant 系卖家会漏",
            "medium",
        )
        self._note(f, f"query sellers: {self._last_query}")
        return f

    def query_combatants(self) -> Friction:
        hits = [o for o in self._ents.values() if isinstance(o, _Guard)]
        self._last_query = [f"o{o.oid}:{o.kind}" for o in hits]
        f = Friction(
            "query_combatants",
            self.name,
            "把「能战斗」绑死在 Guard 继承链上；以后战士玩家/野兽要另开分支",
            "medium",
        )
        self._note(f, f"query combatants: {self._last_query}")
        return f

    def query_living(self) -> Friction:
        hits = [o for o in self._ents.values() if isinstance(o, _Living)]
        self._last_query = [f"o{o.oid}:{o.kind}" for o in hits]
        f = Friction("query_living", self.name, f"isinstance(Living) → {len(hits)}", "low")
        self._note(f, f"query living: {self._last_query}")
        return f

    def tick(self) -> Friction:
        healed, poisoned, fought = 0, 0, 0
        for o in self._ents.values():
            if isinstance(o, _Living):
                o.hp = min(o.max_hp, o.hp + 1)
                healed += 1
            if isinstance(o, _PoisonedGuard):
                o.hp = max(0, o.hp - 3)
                o.poison_ticks -= 1
                poisoned += 1
            if isinstance(o, _Guard):
                o.rage += 1
                fought += 1
        f = Friction(
            "tick",
            self.name,
            f"heal={healed} poison={poisoned}(仅 PoisonedGuard) combat={fought}；"
            "新状态=新分支，tick 里 isinstance 链越来越长",
            "high",
        )
        self._note(f, f"tick heal={healed} poison={poisoned} combat={fought}")
        return f

    def select_next(self) -> None:
        ids = sorted(self._ents)
        if not ids:
            self._selected = None
            return
        if self._selected is None or self._selected not in self._ents:
            self._selected = ids[0]
            return
        i = ids.index(self._selected)
        self._selected = ids[(i + 1) % len(ids)]

    def snapshot(self) -> Snapshot:
        ents = []
        for o in sorted(self._ents.values(), key=lambda x: x.oid):
            ents.append(
                {
                    "id": o.oid,
                    "selected": o.oid == self._selected,
                    "kind": o.kind,
                    "parts": o.describe_parts(),
                    "state": o.as_state(),
                }
            )
        return Snapshot(
            self.name, ents, self._selected, list(self._last_query), list(self._friction), list(self._log)
        )

    def _alloc(self, obj: _Obj) -> int:
        oid = self._next
        self._next += 1
        obj.oid = oid
        self._ents[oid] = obj
        self._selected = oid
        return oid

    def _note(self, f: Friction, line: str) -> None:
        self._friction.append(f)
        _push(self._friction)
        self._log.append(line)
        _push(self._log, 6)

    def _blocked(self, action: str, why: str) -> Friction:
        f = Friction(action, self.name, why, "blocked")
        self._note(f, f"BLOCKED {action}: {why}")
        return f


# ── 3) Feature 混入（LPC /feature 风格）─────────────────


@dataclass
class _FeatObj:
    oid: int
    name: str
    base: str
    features: dict[str, dict[str, Any]] = field(default_factory=dict)
    props: dict[str, Any] = field(default_factory=dict)


class FeatureWorld:
    """对象 + 可挂 Feature；接近 LPC 的 /feature 混入，也接近「浅 ECS」。"""

    name = "feature"

    def __init__(self) -> None:
        self._next = 1
        self._ents: dict[int, _FeatObj] = {}
        self._selected: int | None = None
        self._last_query: list[str] = []
        self._friction: list[Friction] = []
        self._log: list[str] = []

    def spawn_guard(self) -> Friction:
        oid = self._spawn("npc", "守卫", {"living": {}, "combat": {"rage": 0}})
        f = Friction(
            "spawn_guard",
            self.name,
            f"o{oid} = npc + living + combat features（组合，像 ECS，但方法仍挂在 feature 模块上）",
            "low",
        )
        self._note(f, f"spawn guard o{oid}")
        return f

    def spawn_merchant(self) -> Friction:
        oid = self._spawn("npc", "商人", {"living": {}, "shop": {"stock": ["茶", "饼"]}})
        f = Friction("spawn_merchant", self.name, f"o{oid} = npc + living + shop", "low")
        self._note(f, f"spawn merchant o{oid}")
        return f

    def spawn_guard_merchant(self) -> Friction:
        oid = self._spawn(
            "npc",
            "守卫商人",
            {"living": {}, "combat": {"rage": 0}, "shop": {"stock": ["茶", "饼", "刀"]}},
        )
        f = Friction(
            "spawn_guard_merchant",
            self.name,
            f"o{oid} 叠 combat+shop，无需新类——与 ECS 同档；差异在「行为放哪」",
            "low",
        )
        self._note(f, f"spawn guard+merchant o{oid}")
        return f

    def attach_poison(self) -> Friction:
        if self._selected is None or self._selected not in self._ents:
            return self._blocked("attach_poison", "无选中实体")
        o = self._ents[self._selected]
        if "living" not in o.features:
            return self._blocked("attach_poison", "无 living feature")
        o.features["poisoned"] = {"ticks_left": 3}
        f = Friction(
            "attach_poison",
            self.name,
            "热挂 poisoned feature；需 feature 模块提供 on_tick——能力与数据同包，UGC 好懂",
            "low",
        )
        self._note(f, f"attach poisoned → o{o.oid}")
        return f

    def attach_rideable(self) -> Friction:
        if self._selected is None or self._selected not in self._ents:
            return self._blocked("attach_rideable", "无选中实体")
        o = self._ents[self._selected]
        o.features["rideable"] = {"speed": 2}
        f = Friction(
            "attach_rideable",
            self.name,
            "挂上 rideable feature 数据；若 UGC 脚本里写了 ride() 钩子即可用——"
            "比纯 ECS「缺 System」少一层引擎改动，但 feature 钩子秩序/冲突要自己管",
            "medium",
        )
        self._note(f, f"attach rideable → o{o.oid}")
        return f

    def query_sellers(self) -> Friction:
        hits = [o for o in self._ents.values() if "shop" in o.features]
        self._last_query = [f"o{o.oid}:{o.name}" for o in hits]
        f = Friction(
            "query_sellers",
            self.name,
            f"has_feature(shop) → {len(hits)}；与 ECS 查询同构，常靠扫全表或自建索引",
            "low",
        )
        self._note(f, f"query sellers: {self._last_query}")
        return f

    def query_combatants(self) -> Friction:
        hits = [o for o in self._ents.values() if "combat" in o.features]
        self._last_query = [f"o{o.oid}" for o in hits]
        f = Friction("query_combatants", self.name, f"has_feature(combat) → {len(hits)}", "low")
        self._note(f, f"query combatants: {self._last_query}")
        return f

    def query_living(self) -> Friction:
        hits = [o for o in self._ents.values() if "living" in o.features]
        self._last_query = [f"o{o.oid}" for o in hits]
        f = Friction("query_living", self.name, f"has_feature(living) → {len(hits)}", "low")
        self._note(f, f"query living: {self._last_query}")
        return f

    def tick(self) -> Friction:
        healed, poisoned, fought = 0, 0, 0
        for o in self._ents.values():
            if "living" in o.features:
                o.props["hp"] = min(o.props["max_hp"], o.props.get("hp", 20) + 1)
                healed += 1
            if "poisoned" in o.features:
                o.props["hp"] = max(0, o.props.get("hp", 20) - 3)
                o.features["poisoned"]["ticks_left"] -= 1
                if o.features["poisoned"]["ticks_left"] <= 0:
                    del o.features["poisoned"]
                poisoned += 1
            if "combat" in o.features:
                o.features["combat"]["rage"] += 1
                fought += 1
        f = Friction(
            "tick",
            self.name,
            f"heal={healed} poison={poisoned} combat={fought}；"
            "每个 feature 自带钩子时像「分布式 System」，顺序/重入是 UGC 坑",
            "medium",
        )
        self._note(f, f"tick heal={healed} poison={poisoned} combat={fought}")
        return f

    def select_next(self) -> None:
        ids = sorted(self._ents)
        if not ids:
            self._selected = None
            return
        if self._selected is None or self._selected not in self._ents:
            self._selected = ids[0]
            return
        i = ids.index(self._selected)
        self._selected = ids[(i + 1) % len(ids)]

    def snapshot(self) -> Snapshot:
        ents = []
        for o in sorted(self._ents.values(), key=lambda x: x.oid):
            ents.append(
                {
                    "id": o.oid,
                    "selected": o.oid == self._selected,
                    "kind": o.base,
                    "parts": [o.base, *sorted(o.features)],
                    "state": {"name": o.name, "props": dict(o.props), "features": {k: dict(v) for k, v in o.features.items()}},
                }
            )
        return Snapshot(
            self.name, ents, self._selected, list(self._last_query), list(self._friction), list(self._log)
        )

    def _spawn(self, base: str, name: str, features: dict[str, dict[str, Any]]) -> int:
        oid = self._next
        self._next += 1
        props: dict[str, Any] = {}
        if "living" in features:
            props["hp"] = 20
            props["max_hp"] = 20
        self._ents[oid] = _FeatObj(oid=oid, name=name, base=base, features=features, props=props)
        self._selected = oid
        return oid

    def _note(self, f: Friction, line: str) -> None:
        self._friction.append(f)
        _push(self._friction)
        self._log.append(line)
        _push(self._log, 6)

    def _blocked(self, action: str, why: str) -> Friction:
        f = Friction(action, self.name, why, "blocked")
        self._note(f, f"BLOCKED {action}: {why}")
        return f


# ── helpers ─────────────────────────────────────────────


def _default_comp(name: str) -> dict[str, Any]:
    if name == "Identity":
        return {"name": "无名"}
    if name == "Vitals":
        return {"hp": 20, "max_hp": 20}
    if name == "Combat":
        return {"rage": 0}
    if name == "Shop":
        return {"stock": ["茶", "饼"]}
    if name == "Room":
        return {"room_id": "yangzhou/guangchang"}
    if name == "Poisoned":
        return {"ticks_left": 3}
    if name == "Rideable":
        return {"speed": 2}
    return {}


def make_worlds() -> dict[str, WorldModel]:
    return {
        "ecs": EcsWorld(),
        "inheritance": InheritanceWorld(),
        "feature": FeatureWorld(),
    }
