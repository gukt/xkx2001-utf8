"""运行时子系统接线：fresh load 与 restore 共用的单一入口。

把 nature / AI / 渡口 / 交战 / 门禁 / 昏迷苏醒的 ``attach_*`` 序列收拢到一处，
避免 ``load_scene`` 与 ``__main__`` restore 路径各自维护一份清单而静默漂移。
本模块刻意不放进 ``world.py``（子系统模块会反向 import World，会循环）。
"""

from __future__ import annotations

from pathlib import Path

from mud_engine.ai import attach_ai_system
from mud_engine.combat_system import attach_combat_system
from mud_engine.death_flow import attach_unconscious_recovery
from mud_engine.entity_gate import attach_entry_guards
from mud_engine.ferry import attach_ferries
from mud_engine.nature import attach_nature
from mud_engine.world import World


def wire_runtime(world: World, scene_path: Path) -> None:
    """按固定顺序挂载不进存档的运行时子系统（幂等）。

    每次显式从 ``scene_path`` 重读 nature 配置，不依赖 ``extension_data`` 里
    是否还留着 fresh load 时的透传段。

    ``read_nature_config`` 延迟导入，避免与 ``scene_loader``（调用本函数）循环。
    """
    from mud_engine.scene_loader import read_nature_config

    attach_nature(world, config_from_yaml=read_nature_config(scene_path))
    attach_ai_system(world)
    attach_ferries(world)
    attach_combat_system(world)  # 内部已 attach_power_model
    attach_entry_guards(world)
    attach_unconscious_recovery(world)


__all__ = ["wire_runtime"]
