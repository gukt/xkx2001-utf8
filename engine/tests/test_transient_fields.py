"""12 号票测试：组件字段三态--瞬时字段（运行时可变、不进存档）。

覆盖 12 号票 acceptance：
- #1 components.py 三态标注：``transient_field()`` 标注瞬时字段（见 components.py
  模块 docstring 三态说明：启动固定 / 运行时可变进存档 / 瞬时运行时可变不进存档）。
- #2 save.py 按三态过滤：瞬时字段不进存档。正确 codec 省略它时自然不进；codec
  误带它时 save.py 在序列化 chokepoint 强制剔除 + 记警告。
- #3 挂一个瞬时字段的组件，存档后该字段不出现、恢复后回到默认值（不是运行时
  改过的值）。
- #4 现有组件的存档行为不变：本文件末尾单独验证 Identity payload 不被过滤增删，
  全量 round-trip 由 test_save.py 覆盖。

测试在公开 seam 上观测：``save_world`` 写出的 entity JSON 文件 + ``restore_world``
恢复出的世界状态。不直接测 save.py 私有函数。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import pytest

from openmud import save
from openmud.components import Identity, transient_field
from openmud.save import restore_world, save_world
from openmud.world import World


# ── 测试用组件：演示瞬时字段 ──────────────────────────────────
# 不进正式包，仅用于验证 tri-state 过滤机制。``label`` 是"运行时可变进存档"字段
# （重启后保留），``tick_count`` 是"瞬时"字段（运行时累加、重启回到默认 0）--
# 模拟未来 Nature 的 current_day_phase（B 块第一个真实用例）。
@dataclass
class RuntimeCache:
    label: str
    tick_count: int = transient_field(0)  # 瞬时（运行时可变、不进存档）


def _ser_cache(c: RuntimeCache) -> dict:
    return {"label": c.label}  # tick_count 不进存档


def _des_cache(d: dict) -> RuntimeCache:
    return RuntimeCache(label=d["label"])  # tick_count 取默认 0


@pytest.fixture
def cache_codec():
    """注册 RuntimeCache 的正确 codec，用完恢复（不污染其他测试）。"""
    codec = (_ser_cache, _des_cache)
    save._CODECS[RuntimeCache] = codec
    save._CODECS_BY_NAME[RuntimeCache.__name__] = codec
    yield
    save._CODECS.pop(RuntimeCache, None)
    save._CODECS_BY_NAME.pop(RuntimeCache.__name__, None)


def _ser_cache_leaky(c: RuntimeCache) -> dict:
    # 故意把瞬时字段也塞进 payload，用来验证 save.py 的序列化 chokepoint 会剔除它。
    return {"label": c.label, "tick_count": c.tick_count}


@pytest.fixture
def cache_codec_leaky():
    """注册一个会误带瞬时字段的 codec，验证 save.py chokepoint 兜底剔除。"""
    codec = (_ser_cache_leaky, _des_cache)
    save._CODECS[RuntimeCache] = codec
    save._CODECS_BY_NAME[RuntimeCache.__name__] = codec
    yield
    save._CODECS.pop(RuntimeCache, None)
    save._CODECS_BY_NAME.pop(RuntimeCache.__name__, None)


def _build_world_with_cache(*, tick_count: int) -> tuple[World, int, int]:
    """建一个最小世界：一个玩家（带 Identity，可被 save_world 标记）+ 一个挂
    RuntimeCache 的实体（tick_count 设为非默认值）。返回 (world, player_id, cache_id)。"""
    world = World()
    player = world.create_entity()
    world.add_component(player, Identity(name="玩家"))
    cache_entity = world.create_entity()
    world.add_component(cache_entity, RuntimeCache(label="cache", tick_count=tick_count))
    return world, player, cache_entity


def _cache_record(tmp_path, cache_id: int) -> dict:
    """读存档里 cache 实体的 JSON 记录。"""
    snapshot_dir = (tmp_path / "current").resolve()
    text = (snapshot_dir / f"entity_{cache_id}.json").read_text(encoding="utf-8")
    return json.loads(text)


class TestTransientFieldNotSaved:
    """12 号票 acceptance #2/#3：瞬时字段不进存档、恢复后回到默认值。"""

    class WhenCodecCorrectlyOmitsTransientField:
        def test_transient_field_absent_from_saved_entity_json(self, tmp_path, cache_codec) -> None:
            world, player, cache_id = _build_world_with_cache(tick_count=42)
            save_world(world, player, tmp_path)

            payload = _cache_record(tmp_path, cache_id)["components"]["RuntimeCache"]
            assert "tick_count" not in payload  # 瞬时字段不进存档
            assert payload["label"] == "cache"  # 运行时可变进存档字段保留

        def test_transient_field_returns_to_default_after_restore(
            self, tmp_path, cache_codec
        ) -> None:
            world, player, cache_id = _build_world_with_cache(tick_count=42)
            save_world(world, player, tmp_path)

            restored = restore_world(tmp_path)
            assert restored is not None
            world2, _player2 = restored
            cache = world2.get_component(cache_id, RuntimeCache)
            assert cache is not None
            assert cache.label == "cache"  # 持久字段恢复
            assert cache.tick_count == 0  # 瞬时字段回到默认，不是运行时改过的 42

    class WhenCodecLeaksTransientField:
        def test_save_strips_leaked_transient_field_and_warns(
            self, tmp_path, cache_codec_leaky, caplog
        ) -> None:
            world, player, cache_id = _build_world_with_cache(tick_count=42)
            with caplog.at_level(logging.WARNING):
                save_world(world, player, tmp_path)

            payload = _cache_record(tmp_path, cache_id)["components"]["RuntimeCache"]
            # chokepoint 兜底：即使 codec 误带，瞬时字段仍不进存档。
            assert "tick_count" not in payload
            assert payload["label"] == "cache"
            # codec 误带被记为警告（surfacing 编码 bug，不静默吞）。
            assert any(
                "瞬时" in r.message or "transient" in r.message.lower() for r in caplog.records
            )


class TestNoRegressionOnExistingComponents:
    """12 号票 acceptance #4：三态过滤对无瞬时字段的现有组件是 no-op，存档行为不变。

    全量 round-trip 一致性由 test_save.py 覆盖；这里在 save seam 上直接断言一个
    现有组件（Identity）的 payload 不被过滤增删任何字段。
    """

    def test_identity_payload_unchanged_by_filter(self, tmp_path) -> None:
        world = World()
        player = world.create_entity()
        world.add_component(player, Identity(name="玩家", aliases=("玩家", "旅人")))
        save_world(world, player, tmp_path)

        snapshot_dir = (tmp_path / "current").resolve()
        record = json.loads((snapshot_dir / f"entity_{player}.json").read_text(encoding="utf-8"))
        # Identity 无瞬时字段：过滤后 payload 与 codec 原样输出一致，无增删。
        assert record["components"]["Identity"] == {
            "name": "玩家",
            "aliases": ["玩家", "旅人"],
        }
