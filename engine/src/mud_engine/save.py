"""存档与崩溃恢复：全量 per-entity JSON 存档 + 原子发布 + 容错恢复（05 号票）。

持久化边界是"崩溃恢复级耐久"（见 M1 spec「存档与崩溃恢复」）：内存态权威，
存档是周期快照，进程重启后恢复到最近一次成功**发布**的快照；不承诺每次变更
立即持久化，两次快照间崩溃会丢变更（有意取舍，不是缺陷）。

存档布局（``<save_root>``）::

    snapshots/<seq>/entity_<id>.json   每个实体一份独立 JSON（人类可读，05 验收 #6）
    current -> snapshots/<seq>/         symlink，restore 始终读这里

整体原子性（05 验收 #4 "写入中途崩溃不破坏上一次已成功写入的存档"）：
save 先写一个全新的 staging 快照目录（``snapshots/<新 seq>/``），全部 entity
文件写完 + fsync 后，用 ``os.replace`` 原子替换 ``current`` symlink。``current``
永远指向一个完整快照；写入中途崩溃只会留下一个孤儿 staging 目录，不影响上一次
已发布的快照。单文件也走 tmp+fsync+replace 三步，保证单个 entity 文件写入中断
不留半截（参考旧引擎"原子写三步"，思路参考、代码从零）。

容错恢复（05 验收 #5 "单个条目损坏跳过+不拒绝启动"）：restore 扫描 ``current``
指向的快照目录，逐个读 entity 文件；单个文件损坏（JSON 解析失败 / 结构不合法 /
组件反序列化失败 / 重复 id）只跳过该条目记 warning，其余条目正常恢复，进程不崩。

存档粒度按 entity（每实体一份独立记录，spec「存档与崩溃恢复」），为后续脏标记
式增量存档留扩展空间--M1 先做全量（写所有实体文件），未来只写 dirty 实体即可。
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path

from mud_engine.capabilities import (
    CAPABILITIES,
    NPC_CAPABILITIES,
    ROOM_CAPABILITIES,
    CapabilitySpec,
)
from mud_engine.components import (
    TRANSIENT,
    BlockExits,
    Door,
    Doors,
    DoorState,
    Exit,
    Exits,
    HiddenExit,
    HiddenExits,
    Identity,
    ItemSpawnMeta,
    ItemTemplateKey,
    MoreBuffer,
    NpcSpawnMeta,
    PlayerSession,
    Position,
    QuestProgress,
    ReadingSession,
)
from mud_engine.world import EntityId, World

logger = logging.getLogger(__name__)


class _RestoreSkip(Exception):
    """恢复单个 entity 条目时的可跳过错误（被 restore 容错层 catch 记 warning）。"""


# ── 组件序列化注册表 ──────────────────────────────────────
# 每个组件类型登记一对 (to_dict, from_dict)。组件类本身保持纯数据定义（不塞
# 序列化逻辑），序列化集中在 save.py 一处，便于新增组件时只改这里。
# Exit / Door / DoorState 是 Exits / Doors 的内部结构，由各自 codec 内部处理。

_Codec = tuple[Callable[[object], dict], Callable[[dict], object]]


def _ser_identity(c: Identity) -> dict:
    return {"name": c.name, "aliases": list(c.aliases)}


def _des_identity(d: dict) -> Identity:
    return Identity(name=d["name"], aliases=tuple(d.get("aliases", [])))


def _ser_position(c: Position) -> dict:
    return {"room": c.room}


def _des_position(d: dict) -> Position:
    return Position(room=d["room"])


def _ser_exits(c: Exits) -> dict:
    return {
        "by_direction": {
            direction: {"target": exit_.target, "aliases": list(exit_.aliases)}
            for direction, exit_ in c.by_direction.items()
        }
    }


def _des_exits(d: dict) -> Exits:
    exits = Exits()
    for direction, payload in d.get("by_direction", {}).items():
        exits.by_direction[str(direction)] = Exit(
            target=payload["target"], aliases=tuple(payload.get("aliases", []))
        )
    return exits


def _ser_doors(c: Doors) -> dict:
    return {
        "by_direction": {
            direction: {
                "state": door.state.value,
                "key_item_id": door.key_item_id,
                "consume_key": door.consume_key,
            }
            for direction, door in c.by_direction.items()
        }
    }


def _des_doors(d: dict) -> Doors:
    doors = Doors()
    for direction, payload in d.get("by_direction", {}).items():
        doors.by_direction[str(direction)] = Door(
            state=DoorState(payload["state"]),
            key_item_id=payload.get("key_item_id"),
            consume_key=bool(payload.get("consume_key", False)),
        )
    return doors


def _ser_hidden_exits(c: HiddenExits) -> dict:
    return {
        "by_direction": {
            direction: {"target": exit_.target, "aliases": list(exit_.aliases)}
            for direction, exit_ in c.by_direction.items()
        }
    }


def _des_hidden_exits(d: dict) -> HiddenExits:
    hidden = HiddenExits()
    for direction, payload in d.get("by_direction", {}).items():
        hidden.by_direction[str(direction)] = HiddenExit(
            target=payload["target"],
            aliases=tuple(payload.get("aliases", [])),
        )
    return hidden


def _ser_block_exits(c: BlockExits) -> dict:
    return {"by_direction": dict(c.by_direction)}


def _des_block_exits(d: dict) -> BlockExits:
    raw = d.get("by_direction") or {}
    return BlockExits(by_direction={str(k): str(v) for k, v in dict(raw).items()})


def _ser_npc_spawn_meta(c: NpcSpawnMeta) -> dict:
    return {
        "template_key": c.template_key,
        "startroom": c.startroom,
        "desired_count": c.desired_count,
        "respawn": c.respawn,
    }


def _des_npc_spawn_meta(d: dict) -> NpcSpawnMeta:
    return NpcSpawnMeta(
        template_key=str(d["template_key"]),
        startroom=d["startroom"],
        desired_count=int(d.get("desired_count", 1)),
        respawn=bool(d.get("respawn", False)),
    )


def _ser_item_spawn_meta(c: ItemSpawnMeta) -> dict:
    return {
        "template_key": c.template_key,
        "startroom": c.startroom,
        "desired_count": c.desired_count,
        "respawn": c.respawn,
    }


def _des_item_spawn_meta(d: dict) -> ItemSpawnMeta:
    return ItemSpawnMeta(
        template_key=str(d["template_key"]),
        startroom=d["startroom"],
        desired_count=int(d.get("desired_count", 1)),
        respawn=bool(d.get("respawn", False)),
    )


def _ser_item_template_key(c: ItemTemplateKey) -> dict:
    return {"key": c.key}


def _des_item_template_key(d: dict) -> ItemTemplateKey:
    return ItemTemplateKey(key=str(d["key"]))


def _ser_player_session(c: PlayerSession) -> dict:
    return {"subscriptions": sorted(c.subscriptions)}


def _des_player_session(d: dict) -> PlayerSession:
    raw = d.get("subscriptions")
    if isinstance(raw, (list, tuple)):
        return PlayerSession(subscriptions=frozenset(str(x) for x in raw))
    return PlayerSession()


def _ser_quest_progress(c: QuestProgress) -> dict:
    return {"quests": dict(c.quests), "flags": dict(c.flags)}


def _des_quest_progress(d: dict) -> QuestProgress:
    quests_raw = d.get("quests") or {}
    flags_raw = d.get("flags") or {}
    return QuestProgress(
        quests={str(k): str(v) for k, v in dict(quests_raw).items()},
        flags={str(k): bool(v) for k, v in dict(flags_raw).items()},
    )


def _ser_reading_session(c: ReadingSession) -> dict:
    return {"book_id": c.book_id, "room": c.room}


def _des_reading_session(d: dict) -> ReadingSession:
    return ReadingSession(book_id=str(d["book_id"]), room=int(d["room"]))


def _ser_more_buffer(_c: MoreBuffer) -> dict:
    return {}


def _des_more_buffer(_d: dict) -> MoreBuffer:
    return MoreBuffer()


def _codecs_from_specs(specs: list[CapabilitySpec]) -> dict[type, _Codec]:
    return {spec.component_type: (spec.to_dict, spec.from_dict) for spec in specs}


# 物品 / 房间 / NPC 能力 codec 来自各自注册表（M1-31 / M2-01）；固有组件仍在此声明。
# Description 走 ROOM_CAPABILITIES；Inquiry/Behaviors/AIController/Vitals/…/Unconscious/Dead
# 走 NPC_CAPABILITIES（含仅 codec、无 YAML 的运行时 marker）。
_CODECS: dict[type, _Codec] = {}
_CODECS.update(_codecs_from_specs(CAPABILITIES))
_CODECS.update(_codecs_from_specs(ROOM_CAPABILITIES))
_CODECS.update(_codecs_from_specs(NPC_CAPABILITIES))
_CODECS.update(
    {
        Identity: (_ser_identity, _des_identity),
        Position: (_ser_position, _des_position),
        Exits: (_ser_exits, _des_exits),
        Doors: (_ser_doors, _des_doors),
        HiddenExits: (_ser_hidden_exits, _des_hidden_exits),
        BlockExits: (_ser_block_exits, _des_block_exits),
        NpcSpawnMeta: (_ser_npc_spawn_meta, _des_npc_spawn_meta),
        ItemSpawnMeta: (_ser_item_spawn_meta, _des_item_spawn_meta),
        ItemTemplateKey: (_ser_item_template_key, _des_item_template_key),
        PlayerSession: (_ser_player_session, _des_player_session),
        QuestProgress: (_ser_quest_progress, _des_quest_progress),
        ReadingSession: (_ser_reading_session, _des_reading_session),
        MoreBuffer: (_ser_more_buffer, _des_more_buffer),
    }
)

# 按组件类名索引（存档文件用类名作 key，反序列化时按名查 codec）。
_CODECS_BY_NAME: dict[str, _Codec] = {ctype.__name__: codec for ctype, codec in _CODECS.items()}


def has_save(save_root: Path | str) -> bool:
    """save_root 下是否存在已发布的存档（``current`` symlink 存在）。"""
    current = Path(save_root) / "current"
    return current.is_symlink()


def save_world(
    world: World,
    player_id: EntityId,
    save_root: Path | str,
    *,
    on_entity_saved: Callable[[EntityId], None] | None = None,
) -> None:
    """全量存档：每个实体写一份 JSON 到新 staging 快照目录，写完后原子发布。

    ``on_entity_saved`` 是每写完一个实体文件后调用的钩子--合法用途是观测存档
    进度，测试也借它在中途 raise 来模拟"进程被杀"（05 验收 #4）。它在发布
    *之前*调用，故 raise 会让本次存档不发布，``current`` 仍指向上一次成功快照。
    """
    root = Path(save_root)
    snapshots_dir = root / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = snapshots_dir / f"{_next_seq(snapshots_dir):06d}"
    snapshot_dir.mkdir(parents=True, exist_ok=False)

    for entity_id in sorted(world.all_entities()):
        record = _serialize_entity(world, entity_id, player_id)
        _write_json_atomic(snapshot_dir / f"entity_{entity_id}.json", record)
        if on_entity_saved is not None:
            on_entity_saved(entity_id)

    # 场景路径 meta：restore 后重读题材包 nature 配置（不写死默认场景）。
    if world.scene_path is not None:
        _write_json_atomic(
            snapshot_dir / "world_meta.json",
            {"scene_path": str(world.scene_path)},
        )

    _fsync_dir(snapshot_dir)
    _publish(root, snapshot_dir)
    _cleanup_old_snapshots(snapshots_dir, snapshot_dir)


def restore_world(save_root: Path | str) -> tuple[World, EntityId] | None:
    """从存档恢复，返回 ``(world, player_id)``；无存档或恢复后无玩家则返回 None。

    无存档（``current`` 不存在）或 ``current`` 指向的快照里玩家条目也损坏/缺失时
    返回 None--让上层回退到 fresh scene，进程仍能启动（05 验收 #5 "不拒绝启动"）。
    其余单个 entity 条目损坏只跳过并记 warning，不影响整体恢复。
    """
    root = Path(save_root)
    current = root / "current"
    if not current.is_symlink():
        return None
    snapshot_dir = current.resolve()
    if not snapshot_dir.is_dir():
        # current 是断链 symlink（指向的快照目录已删）--视为无存档。
        logger.warning("存档 %s 的 current 指向不存在的快照，视为无存档", root)
        return None

    world = World()
    player_id: EntityId | None = None
    for entry in sorted(snapshot_dir.iterdir()):
        if not entry.name.startswith("entity_") or not entry.name.endswith(".json"):
            continue
        try:
            record = _read_entity(entry)
            entity_id = _restore_entity(world, record)
        except _RestoreSkip as exc:
            logger.warning("跳过损坏的存档条目 %s：%s", entry.name, exc)
            continue
        if record.get("is_player"):
            player_id = entity_id

    meta_path = snapshot_dir / "world_meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            raw_scene = meta.get("scene_path") if isinstance(meta, dict) else None
            if isinstance(raw_scene, str) and raw_scene:
                world.scene_path = Path(raw_scene)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("跳过损坏的 world_meta.json：%s", exc)

    if player_id is None:
        logger.warning("存档 %s 缺少可用的玩家实体，回退到 fresh scene", snapshot_dir)
        return None
    world.primary_player_id = player_id
    return world, player_id


def _transient_field_names(component_type: type) -> frozenset[str]:
    """该组件类型上被标为"瞬时"（运行时可变、不进存档）的字段名（12 号票）。

    通过 ``transient_field()`` 写入的 dataclass field metadata（``TRANSIENT`` key）
    识别。非 dataclass 类型无瞬时字段（返回空）。
    """
    if not dataclasses.is_dataclass(component_type):
        return frozenset()
    return frozenset(
        f.name for f in dataclasses.fields(component_type) if f.metadata.get(TRANSIENT) is True
    )


def _strip_transient(component_type: type, payload: dict) -> dict:
    """三态过滤 chokepoint：从序列化 payload 里剔除瞬时字段（12 号票）。

    瞬时字段（``transient_field()`` 标注）一律不进存档。codec 本应省略它们；若
    codec 误带，这里兜底剔除并记警告（surfacing 编码 bug，不静默吞，但也不让一个
    codec 失误破坏整次存档）。无瞬时字段的组件是 no-op 快路径，不改 payload。
    """
    transient = _transient_field_names(component_type)
    if not transient:
        return payload
    leaked = transient & payload.keys()
    if leaked:
        logger.warning(
            "组件 %s 的瞬时字段 %s 被 codec 误带入存档，已剔除",
            component_type.__name__,
            sorted(leaked),
        )
    return {k: v for k, v in payload.items() if k not in transient}


def _serialize_entity(world: World, entity_id: EntityId, player_id: EntityId) -> dict:
    """把一个实体序列化成存档记录（id + 各组件 dict + 玩家标记）。"""
    components: dict[str, dict] = {}
    for component_type, component in world.components_of(entity_id):
        codec = _CODECS.get(component_type)
        if codec is None:
            raise TypeError(
                f"无法序列化 entity {entity_id} 的组件 {component_type.__name__}：未注册 codec"
            )
        serialize, _ = codec
        payload = serialize(component)
        payload = _strip_transient(component_type, payload)  # 三态过滤：瞬时字段不进存档
        components[component_type.__name__] = payload
    record: dict = {"id": entity_id, "components": components}
    if entity_id == player_id:
        record["is_player"] = True
    return record


def _read_entity(path: Path) -> dict:
    """读单个 entity 文件并做基本结构校验；损坏抛 _RestoreSkip 供容错层跳过。"""
    try:
        with path.open(encoding="utf-8") as f:
            record = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise _RestoreSkip(f"读取/解析失败：{exc}") from exc
    if not isinstance(record, dict) or "id" not in record or "components" not in record:
        raise _RestoreSkip("缺少 id 或 components 字段")
    return record


def _restore_entity(world: World, record: dict) -> EntityId:
    """按记录重建实体并挂回全部组件；任何可跳过错误抛 _RestoreSkip。"""
    entity_id = record["id"]
    if not isinstance(entity_id, int):
        raise _RestoreSkip(f"id 不是整数：{entity_id!r}")
    try:
        world.create_entity_with_id(entity_id)
    except ValueError as exc:
        raise _RestoreSkip(f"id {entity_id} 重复：{exc}") from exc

    components = record["components"]
    if not isinstance(components, dict):
        raise _RestoreSkip("components 不是映射")
    for name, payload in components.items():
        codec = _CODECS_BY_NAME.get(name)
        if codec is None:
            raise _RestoreSkip(f"未知组件类型 {name}")
        _, deserialize = codec
        try:
            component = deserialize(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise _RestoreSkip(f"组件 {name} 反序列化失败：{exc}") from exc
        world.add_component(entity_id, component)
    return entity_id


def _write_json_atomic(path: Path, obj: dict) -> None:
    """原子写单个 JSON 文件：tmp + fsync + os.replace 三步。

    写 tmp 中途崩溃只损坏 tmp，已发布的 target 不受影响；``os.replace`` POSIX
    原子替换。``ensure_ascii=False`` + ``indent=2`` 让存档人类可读（05 验收 #6）。
    """
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _next_seq(snapshots_dir: Path) -> int:
    """下一个快照序号：扫描已有快照目录取 max+1（跳过非数字名）。"""
    max_seq = 0
    for entry in snapshots_dir.iterdir():
        try:
            max_seq = max(max_seq, int(entry.name))
        except ValueError:
            continue
    return max_seq + 1


def _publish(root: Path, snapshot_dir: Path) -> None:
    """原子发布快照：建临时 symlink，``os.replace`` 替换 ``current``。

    symlink target 用相对路径（``snapshots/<seq>``，相对于 ``current`` 所在的
    ``root`` 解析），整个 ``save_root`` 移动后 symlink 仍有效。
    """
    current = root / "current"
    tmp_link = root / f"current.tmp.{os.getpid()}"
    if tmp_link.is_symlink() or tmp_link.exists():
        tmp_link.unlink()
    os.symlink(snapshot_dir.relative_to(root), tmp_link)
    _fsync_dir(root)
    os.replace(tmp_link, current)
    _fsync_dir(root)


def _cleanup_old_snapshots(snapshots_dir: Path, keep: Path) -> None:
    """发布后删掉非当前快照，避免目录累积（非原子，崩了也无害--多留几份而已）。"""
    for entry in snapshots_dir.iterdir():
        if entry != keep:
            shutil.rmtree(entry, ignore_errors=True)


def _fsync_dir(path: Path) -> None:
    """fsync 一个目录（刷目录元数据，保证新增/替换的条目可持久化）。"""
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


__all__ = ["has_save", "restore_world", "save_world"]
