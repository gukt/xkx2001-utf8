"""工作区重置后的冒烟测试：包可导入即可。"""

from mud_engine import __version__


def test_package_importable() -> None:
    assert __version__
