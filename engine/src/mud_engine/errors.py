"""引擎公共错误类型（叶子模块，无下游依赖）。

把加载期错误放在独立模块，避免 ``capabilities``（能力注册）与 ``scene_loader``
（场景加载）为共享 ``SceneLoadError`` 而互相 import 形成循环，也避免错误类型
挂在能力注册表模块上造成心智错位。``PackManifestError`` 同理：内容包清单校验
与场景内容校验是两个独立阶段，错误类型与 ``SceneLoadError`` 平级、不互相挂靠。
"""

from __future__ import annotations


class SceneLoadError(Exception):
    """场景数据加载/校验失败：消息带文件路径与出错的数据键定位。"""


class PackManifestError(Exception):
    """内容包 manifest 加载/校验失败：消息带包路径与出错的字段名定位。"""


__all__ = ["SceneLoadError", "PackManifestError"]
