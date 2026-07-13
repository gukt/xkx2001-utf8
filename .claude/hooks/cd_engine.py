#!/usr/bin/env python3
"""PreToolUse hook：为 Python/uv/pytest/ruff 命令自动补 cd engine 前缀。

背景：harness 把仓库根设为 cwd，但 Python 项目在 engine/ 子目录（uv 管理，
pyproject.toml 在 engine/ 下）。裸跑 pytest/ruff/uv 会找不到配置或用错环境。

触发条件：命令以 python/python3/pytest/ruff/uv 开头，且
- 不含 `cd engine`（已手动 cd 则不重复补）
- 不含 `engine/` 路径访问（说明已用仓库根相对路径，cd 会双重前缀，应放行）

策略 A：改写 tool input 注入 `cd engine &&`，无感兜底，不阻塞流程。
"""
import json
import re
import sys

_NEEDS_ENGINE = re.compile(r"^\s*(python3?|pytest|ruff|uv)(?:\s|$)")
_HAS_CD_ENGINE = re.compile(r"\bcd\s+engine\b")
_HAS_ENGINE_PATH = re.compile(r"\bengine/")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # 解析失败不阻塞

    cmd = (data.get("tool_input") or {}).get("command", "")
    if not cmd:
        return

    if not _NEEDS_ENGINE.match(cmd):
        return
    if _HAS_CD_ENGINE.search(cmd):
        return
    if _HAS_ENGINE_PATH.search(cmd):
        return

    new_cmd = "cd engine && " + cmd.lstrip()
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "modifiedToolInput": {"command": new_cmd},
        }
    }))


if __name__ == "__main__":
    main()
