"""层0：YAML 声明式数据（房间/NPC/任务定义）。

吸收 LPC ``set()`` 调用：
- 房间（``d/city/chaguan.c``）：``set("short"/"long"/"exits"/"objects")``
- NPC（``d/city/npc/bing.c``）：``set_name`` + ``set`` 属性 + ``set_skill``
- 任务（S4 ADR-0007）：从 LPC NPC 任务交互抽象的最小 DSL

约 60% 的 LPC 内容是纯数据可直接转层0（03 §一）。编译到 JSON IR 见 ``ir.py``。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class RoomDef(BaseModel):
    """房间定义（映射 LPC ``inherit ROOM`` + ``set(...)``）。"""

    id: str  # 房间标识，如 "city/chaguan"
    short: str
    long: str
    exits: dict[str, str] = Field(default_factory=dict)  # 方向 -> 目标房间 id
    objects: dict[str, int] = Field(default_factory=dict)  # npc_id -> 数量
    items: list[str] = Field(default_factory=list)  # S5a：房间地面物品 id（玩家可 take）
    outdoors: bool = False
    no_fight: bool = False


class ApprenticeConditions(BaseModel):
    """拜师入门条件（M3-1 ADR-0032 决策 1，声明式）。

    对照 LPC attempt_apprentice 钩子入门检查（如 gongcang.c:64-84）。引擎
    求值（bai 命令），非层1 谓词：ADR-0016 护栏不引入 attr_gt/le/ge，
    combat_exp >= N 阈值无法用层1 谓词表达，且入门条件有领域语义，用结构化
    字段更清晰（ADR-0032 决策 1「复用层1 谓词」实施期细化为独立条件模型）。

    求值规则（bai 命令按序检查，首项不满足即拒绝）：
    1. reject_gender：玩家性别 == 此值 -> 拒绝（对照 gongcang 拒女徒）
    2. allow_families + other_family_max_combat_exp：玩家已有门派且不在
       allow_families + combat_exp >= other_family_max_combat_exp -> 拒绝
       （对照 gongcang「外派高手」检查；allow_families 空=不限门派）
    3. min_combat_exp：玩家 combat_exp < 此值 -> 拒绝
    4. min_skills：任一技能等级 < 阈值 -> 拒绝
    5. require_flags：玩家缺任一标记 -> 拒绝（darba 打赢设标记解锁拜师）
    全部通过 -> recruit。
    """

    min_combat_exp: int = 0
    reject_gender: str = ""
    allow_families: list[str] = Field(default_factory=list)
    other_family_max_combat_exp: int = 0
    min_skills: dict[str, int] = Field(default_factory=dict)
    require_flags: list[str] = Field(default_factory=list)


class KneelDef(BaseModel):
    """剃度动作配置（M3-1 ADR-0032 决策 1，对照 gongcang.c:114 do_kneel）。

    kneel 命令在房间内有 apprentice_config.kneel 的师傅 NPC 时触发剃度：
    检查 require_flag（pending 标记）-> 设 class（TitleComp.char_class）->
    清除标记 -> 输出 message。gongcang 专属行为通过声明式配置驱动，非硬编码。
    """

    set_class: str = ""  # 剃度后设的职业（LPC set("class","lama")）
    require_flag: str = ""  # 需要的 pending 标记（LPC pending/join_lama，空=不需要）
    clear_flag: str = ""  # 剃度后清除的标记（默认=require_flag，空=不清除）
    message: str = ""  # 剃度文本（LPC message_vision）


class ApprenticeDef(BaseModel):
    """师傅收徒配置（M3-1 ADR-0032 决策 1，对照 LPC create_family + attempt_apprentice）。

    NpcDef.apprentice 非空表示该 NPC 是师傅（可收徒）。师傅自己的 family
    信息（family_name/generation/title）对应 LPC create_family，拜师时
    recruit 写入玩家 FamilyComp（generation = 师傅 generation + 1）。
    """

    family_name: str  # 师傅门派（LPC create_family 第 1 参）
    generation: int  # 师傅辈分（LPC create_family 第 2 参，如 gongcang=12）
    title: str  # 师傅称号（LPC create_family 第 3 参，如「弟子」/「喇嘛」/「法王」）
    conditions: ApprenticeConditions = Field(default_factory=ApprenticeConditions)
    kneel: KneelDef | None = None  # 剃度配置（gongcang 专属，None=无剃度）
    success_message: str = ""  # 收徒成功消息（对照 gongcang「好吧，我就收下你了...」）


class NpcDef(BaseModel):
    """NPC 定义（映射 LPC ``inherit NPC`` + ``set_name`` / ``set`` / ``set_skill``）。"""

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    gender: str = "男性"
    age: int = 20
    attitude: str = "friendly"  # friendly | heroism | aggressive

    # 四维属性（LPC str/dex/int/con）
    str_: int = 20
    dex_: int = 20
    int_: int = 20
    con_: int = 20

    # 三层资源上限
    max_qi: int = 100
    max_jing: int = 100
    max_jingli: int = 100
    max_neili: int = 0

    # 战斗
    combat_exp: int = 0
    skills: dict[str, int] = Field(default_factory=dict)
    apply_attack: int = 0
    apply_dodge: int = 0
    apply_parry: int = 0
    apply_damage: int = 0
    apply_armor: int = 0
    weapon: str | None = None
    # 本回合招式技能 id + 武器显示名（题材数据声明，内核不解释，见 ADR-0003）
    attack_skill: str = "unarmed"
    weapon_label: str = "拳头"

    # 战斗喊话（LPC chat_msg_combat）
    chat_chance_combat: int = 0
    chat_msg_combat: list[str] = Field(default_factory=list)

    # 对话（LPC set("inquiry")）；S4 ADR-0006：topic -> reply 静态字符串
    inquiry: dict[str, str] = Field(default_factory=dict)

    # M3-1 ADR-0032 决策 1：拜师配置（None=该 NPC 不收徒）
    apprentice: ApprenticeDef | None = None


# S4 ADR-0007：最小任务定义
class QuestReward(BaseModel):
    """任务奖励（S4 最小集 + M3-1 ADR-0032 决策 3 time_gate）。

    ``time_gate > 0``：任务可重复，发奖后记 ``claimed_at``，冷却期内（tick 差
    < time_gate）ask 拒绝再接（对照 jiamu lama_wage 工资冷却，jiamu.c:51-56）。
    ``time_gate == 0``（默认）：一次性任务（S4 行为，向后兼容）。
    """

    exp: int = 0
    flag: str = ""  # 完成后设置的标记（LPC set_temp("marks/X")）
    message: str = ""  # 完成时给玩家的消息
    time_gate: int = 0  # M3-1：可重复任务冷却 tick 数（0=一次性）


class QuestObjective(BaseModel):
    """任务目标（S4 give_item + M3-1 ADR-0032 决策 3 扩 kill_npc/reach_room/fight_win）。

    kind 取值：
    - ``give_item``（S4）：给指定 NPC 指定物品。匹配 npc_id + item_id
    - ``kill_npc``（M3-1）：击杀指定 NPC。匹配 npc_id（对照 fsgelun kill corpse）
    - ``reach_room``（M3-1）：到达指定房间。匹配 room_id
    - ``fight_win``（M3-1）：切磋击败指定 NPC（不杀死）。匹配 npc_id，
      NPC qi 降到 win_threshold% 判赢（对照 darba fight + checking，darba.c:109）
    """

    kind: str = "give_item"
    npc_id: str = ""  # give_item/kill_npc/fight_win 目标 NPC prototype_id
    item_id: str = ""  # give_item 物品 id
    room_id: str = ""  # reach_room 目标房间 id
    win_threshold: int = 50  # fight_win 判赢阈值（NPC qi*100/max_qi <= 此值）


class QuestDef(BaseModel):
    """任务定义（S4 ADR-0007 + M3-1 ADR-0032 决策 3 多步 chain）。

    S4 单 objective -> M3-1 扩为 ``objectives`` list（多步 chain，按序完成）。
    向后兼容：``objective`` 单数字段保留，model_validator 合并到 objectives[0]，
    旧 YAML（如 xueshan_micro/quests.yaml）不破坏。QuestLog.current_step
    跟踪当前步骤，全部完成才 reward。对照 LPC 多步任务（fsgelun kill->give
    corpse 多步 + darba fight->flag->unlock 拜师）。
    """

    id: str
    name: str
    giver: str  # NPC prototype_id（接任务的 NPC）
    trigger: str  # ask 话题
    description: str = ""  # 接任务时显示给玩家的描述
    objective: QuestObjective | None = None  # S4 单 objective（兼容，合并到 objectives）
    objectives: list[QuestObjective] = Field(default_factory=list)  # M3-1 多步 chain
    reward: QuestReward = Field(default_factory=QuestReward)

    @model_validator(mode="after")
    def _merge_objective(self) -> QuestDef:
        """S4 ``objective`` 单数合并到 ``objectives`` list（向后兼容旧 YAML）。"""
        if self.objective is not None and not self.objectives:
            self.objectives = [self.objective]
        if not self.objectives:
            self.objectives = [QuestObjective()]  # 兜底默认 give_item
        return self


class ItemDef(BaseModel):
    """物品定义（S5a）：映射 LPC ``inherit ITEM`` + ``set_name``。

    对照 d/xueshan/obj/suyouguan.c ``set_name("酥油罐", ({"suyou guan",...}))``。
    """

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)


class SkillDef(BaseModel):
    """武学数据定义（M3-1 ADR-0032 决策 5，CPK 资产）。

    dsl 层声明，runtime 边界编译到 ``combat.context.SkillData``（招式载体）。
    本字段集是 M3-1 练功 stub（``valid_learn``/``practice_skill`` 简化 bool，
    rich LPC 条件记 GAP 后置）。combat 招式字段（action/dodge/parry/damage/
    force/damage_type/query_action 招式表）后置内容生产扩展时再加。
    """

    skill_id: str  # 武学 id（注册表 key，对照 LPC SKILL_D(skill)）
    skill_type: str = ""  # LPC type()：martial/knowledge/dodge 等
    valid_learn: bool = True  # LPC valid_learn(me) 简化布尔（能否向 NPC 学习）
    practice_skill: bool = True  # LPC practice_skill(me) 简化布尔（能否自行练习）
    valid_enable: list[str] = Field(default_factory=list)  # 可 enable 种类（空=不限）


def load_rooms(path: Path | str) -> list[RoomDef]:
    """从 YAML 加载房间列表（顶层为房间 dict 的 list）。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [RoomDef(**r) for r in (data or [])]


def load_npcs(path: Path | str) -> list[NpcDef]:
    """从 YAML 加载 NPC 列表（顶层为 NPC dict 的 list）。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [NpcDef(**n) for n in (data or [])]


def load_quests(path: Path | str) -> list[QuestDef]:
    """从 YAML 加载任务列表（S4 ADR-0007）。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [QuestDef(**q) for q in (data or [])]


def load_items(path: Path | str) -> list[ItemDef]:
    """从 YAML 加载物品列表（S5a）。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [ItemDef(**i) for i in (data or [])]


def load_skills(path: Path | str) -> list[SkillDef]:
    """从 YAML 加载武学数据列表（M3-1 ADR-0032 决策 5，CPK 资产）。

    skills.yaml 顶层为 SkillDef dict 的 list。runtime 边界编译到 SkillData。
    """
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [SkillDef(**s) for s in (data or [])]
