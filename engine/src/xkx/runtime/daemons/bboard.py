"""bboard 留言板 daemon（ADR-0057）。

对照 LPC ``inherit/misc/bboard.c`` 的 dbase 承载 + F_SAVE 语义：

- ``query_save_file()`` 用 ``board_id`` 作存档路径（L33-37），``do_post`` /
  ``do_discard`` 后调 ``save()``（L117/L250），``setup()`` 调 ``restore()``（L21）。
- dbase key：``board_id`` / ``notes``（mapping 数组）/ ``wizard_only`` /
  ``poster_family``（L146/L179/L180/L182/L190）；本批补 ``capacity``（对照
  ``BOARD_CAPACITY`` 宏，``do_post`` 截断 L110-111 用）+ ``poster_level``（投稿
  等级门槛，``wumiao_b.c:11``，``do_post`` 门控用）。两字段建模补齐让数据结构
  完整，``do_post`` 本身留后续 bboard 子系统批迁移。

本文件是数据建模层（机制层）：``BboardData`` 实现 ``DaemonSerializable``，覆盖
id=9 主路径（save/restore 往返）。完整 do_read/do_post/do_discuss 等命令迁移留
后续 bboard 子系统批。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Note:
    """单条留言（对照 LPC notes[i] mapping：title/author/time/msg）。"""

    title: str = ""
    author: str = ""
    time: int = 0
    msg: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "time": self.time,
            "msg": self.msg,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Note:
        return cls(
            title=d.get("title", ""),
            author=d.get("author", ""),
            time=d.get("time", 0),
            msg=d.get("msg", ""),
        )


@dataclass
class BboardData:
    """bboard 留言板 daemon 数据（对照 bboard.c 物品 dbase）。

    greenfield 无 ItemComp，bboard 作为 DaemonStore 单例承载（ADR-0057 决策 1）。
    存档路径 ``<root>/daemon/bboard_<board_id>.json``（name 由注册方决定）。
    """

    board_id: str = ""
    notes: list[Note] = field(default_factory=list)
    wizard_only: bool = False
    poster_family: str | None = None
    # BOARD_CAPACITY 宏（do_post 截断 L110-111：超出 capacity 删最旧帖）
    capacity: int = 50
    # 投稿等级门槛（wumiao_b.c:11，do_post 门控：cmp_wiz_level 低于此值拒绝投稿）
    poster_level: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "board_id": self.board_id,
            "notes": [n.to_dict() for n in self.notes],
            "wizard_only": self.wizard_only,
            "poster_family": self.poster_family,
            "capacity": self.capacity,
            "poster_level": self.poster_level,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BboardData:
        notes = [Note.from_dict(n) for n in d.get("notes", [])]
        return cls(
            board_id=d.get("board_id", ""),
            notes=notes,
            wizard_only=d.get("wizard_only", False),
            poster_family=d.get("poster_family"),
            # 向后兼容：旧存档无该字段走默认值（capacity=50 / poster_level=None）
            capacity=d.get("capacity", 50),
            poster_level=d.get("poster_level"),
        )
