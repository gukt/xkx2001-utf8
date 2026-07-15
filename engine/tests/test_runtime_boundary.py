"""runtime 导入边界测试：不依赖创作期/工作台包（M2-2）。"""

from __future__ import annotations

import sys


class _BlockWorkbench:
    """临时让 xkx.workbench / fastapi import 失败，验证 runtime 不依赖它们。"""

    def __init__(self) -> None:
        self.blocked = {"xkx.workbench", "fastapi", "uvicorn"}
        self._original = dict(sys.modules)

    def find_spec(self, name: str, path=None, target=None):  # type: ignore[no-untyped-def]
        if any(name == b or name.startswith(b + ".") for b in self.blocked):
            raise ModuleNotFoundError(f"blocked {name}")
        return None

    def __enter__(self) -> _BlockWorkbench:
        sys.meta_path.insert(0, self)
        # 清掉已导入的 workbench 相关模块，让测试重新 import runtime
        for name in list(sys.modules):
            if any(name == b or name.startswith(b + ".") for b in self.blocked):
                del sys.modules[name]
        return self

    def __exit__(self, *args: object) -> None:
        sys.meta_path.remove(self)
        # 恢复被删的模块（fastapi 若原本有则恢复不了，但测试后进程会退出）
        for name, mod in self._original.items():
            if name not in sys.modules:
                sys.modules[name] = mod


def test_runtime_imports_without_workbench() -> None:
    """runtime 关键模块可在无 fastapi/uvicorn/workbench 时导入。"""
    with _BlockWorkbench():
        from xkx.runtime import commands, components, world

        assert commands is not None
        assert components is not None
        assert world is not None
