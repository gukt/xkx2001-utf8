# justfile - 侠客行 MUD 项目 task runner
#
# 设计意图：所有 recipe 自带 `cd engine && uv run`，coding agent 在仓库根
# 直接 `just <recipe>` 即可，无需记忆 cwd / venv / PYTHONPATH。`just`（无参）
# 或 `just --list` 自举发现全部命令。
#
# 约定：
#   - python / pytest / ruff 必须在 engine/ 下跑 -> recipe 内已 cd engine
#   - 统一用 `uv run`（uv 自动管理 .venv + dev 依赖；勿用裸 python/pytest/ruff）
#   - 透传 recipe（python/pytest）用 *args 收集任意参数，引号安全保留
#   - 旧引擎 CLI/tools recipe 已随工作区绿场清空移除；旧实现见 tag
#     archive/engine-pre-m1-rewrite（ADR-0002）

set positional-arguments := true

# 默认：列出所有可用命令
default:
    @just --list

# ── 依赖 ────────────────────────────────────────────────

# 安装/同步全部依赖（含 dev；干净环境一键就绪）
install:
    cd engine && uv sync --all-extras

# ── 测试 ────────────────────────────────────────────────

# 跑全部测试
test:
    cd engine && uv run pytest -ra

# 快速跑：安静 + 首个失败即停（改动后快速自检）
test-quick:
    cd engine && uv run pytest -q -x

# 跑指定测试文件/节点：just test-file tests/test_smoke.py
test-file target:
    cd engine && uv run pytest -ra "{{target}}"

# 按关键字筛选跑：just test-keyword smoke
test-keyword keyword:
    cd engine && uv run pytest -ra -k "{{keyword}}"

# 只收集不跑（快速确认可导入 + 用例数）
count:
    cd engine && uv run pytest --co -q | tail -1

# ── lint / format ───────────────────────────────────────

# ruff lint 检查（不修改）
lint:
    cd engine && uv run ruff check src tests

# ruff lint 自动修复
lint-fix:
    cd engine && uv run ruff check --fix src tests

# ruff format 格式化
format:
    cd engine && uv run ruff format src tests

# ruff format 仅检查不改（门禁用）
format-check:
    cd engine && uv run ruff format --check src tests

# ── 门禁 ────────────────────────────────────────────────

# 提交前本地门禁：lint + 全量测试
gate: lint test

# 快速门禁：lint + test-quick
gate-quick: lint test-quick

# ── 运行 ────────────────────────────────────────────────

# 启动 M1 demo：真实终端 CLI（python -m mud_engine）
run:
    cd engine && uv run python -m mud_engine

# M1 物品命令矩阵（默认场景，不读写存档）：转录 + PASS/FAIL
# 手测步骤见 .scratch/m1-core-engine-skeleton/verify-items-cli.md
verify-items:
    cd engine && uv run python scripts/verify_m1_items.py

# M1 NPC 命令/行为矩阵（默认场景，含 tick 驱动 Chatter；不读写存档）
# 手测步骤见 .scratch/m1-core-engine-skeleton/verify-npc-cli.md
verify-npc:
    cd engine && uv run python scripts/verify_m1_npc.py

# ── 原型（throwaway）────────────────────────────────────

# ECS vs 继承 vs Feature：UGC 组合手感（逻辑原型）
proto-ecs-ugc:
    cd engine && uv run python prototypes/ecs_ugc/tui.py

# ── 逃生口 / 杂项 ───────────────────────────────────────

# 在 engine venv 跑任意 python：just python -c "import mud_engine; print(mud_engine.__version__)"
python *args:
    cd engine && uv run python "$@"

# 在 engine venv 跑任意 pytest 参数：just pytest -k smoke --lf
pytest *args:
    cd engine && uv run pytest "$@"

# 清缓存（.pytest_cache / .ruff_cache / .hypothesis / __pycache__）
clean:
    cd engine && rm -rf .pytest_cache .ruff_cache .hypothesis && find . -type d -name __pycache__ -prune -exec rm -rf {} +
