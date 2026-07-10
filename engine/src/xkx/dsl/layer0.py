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
from pydantic import BaseModel, Field


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


# S4 ADR-0007：最小任务定义
class QuestReward(BaseModel):
    """任务奖励（S4 最小集：经验 + 标记 + 消息）。"""

    exp: int = 0
    flag: str = ""  # 完成后设置的标记（LPC set_temp("marks/X")）
    message: str = ""  # 完成时给玩家的消息


class QuestObjective(BaseModel):
    """任务目标（S4 最小集：给物品）。"""

    kind: str = "give_item"  # S4 仅支持 give_item；kill_npc/reach_room 后置
    npc_id: str = ""  # give_item 目标 NPC prototype_id
    item_id: str = ""  # give_item 物品 id


class QuestDef(BaseModel):
    """任务定义（S4 ADR-0007）。

    最小垂直切片：ask giver about trigger -> 接任务 -> give item to npc -> 完成 -> reward。
    对照 LPC NPC 任务交互（如 xueshan gelun1.c 的 ask 还愿 + accept_object 酥油罐）。
    """

    id: str
    name: str
    giver: str  # NPC prototype_id（接任务的 NPC）
    trigger: str  # ask 话题
    description: str = ""  # 接任务时显示给玩家的描述
    objective: QuestObjective = Field(default_factory=QuestObjective)
    reward: QuestReward = Field(default_factory=QuestReward)


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
