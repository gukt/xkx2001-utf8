# justfile - 侠客行 MUD 项目 task runner
#
# 设计意图：所有 recipe 自带 `cd engine && uv run`，coding agent 在仓库根
# 直接 `just <recipe>` 即可，无需记忆 cwd / venv / PYTHONPATH。`just`（无参）
# 或 `just --list` 自举发现全部命令。
#
# 约定：
#   - python / pytest / ruff 必须在 engine/ 下跑 -> recipe 内已 cd engine
#   - 统一用 `uv run`（uv 自动管理 .venv + dev 依赖；勿用裸 python/pytest/ruff，
#     .venv 里没装 dev 依赖，直接调会 No module named pytest）
#   - 透传 recipe（run/py/pt/bench 等）用 *args 收集任意参数，引号安全保留

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

# 跑指定测试文件/节点：just test-file tests/combat/test_resolve.py::test_x
test-file target:
    cd engine && uv run pytest -ra "{{target}}"

# 按关键字筛选跑：just test-keyword combat
test-keyword keyword:
    cd engine && uv run pytest -ra -k "{{keyword}}"

# 只收集不跑（快速确认可导入 + 用例数）
count:
    cd engine && uv run pytest --co -q | tail -1

# ── lint / format ───────────────────────────────────────

# ruff lint 检查（不修改）
lint:
    cd engine && uv run ruff check src tests

# ruff lint 自动修复（E501 等无法自动修的不动）
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
# 注：项目当前未 enforce ruff format（85 文件有格式漂移），故 gate 不含 format-check；
# 欲启用格式门禁，先单独跑一次 `just format` 全量格式化消除漂移
gate: lint test

# 快速门禁：lint + test-quick（不全量，改动后快速自检）
gate-quick: lint test-quick

# ── 引擎 CLI / 场景 ─────────────────────────────────────

# 跑引擎 CLI（透传）：just cli --help / just cli scene xueshan_micro
cli *args:
    cd engine && uv run python -m xkx.cli "$@"

# 内容审核 pipeline（M3-3，ADR-0033）
review *args:
    cd engine && uv run python -m xkx.content_review "$@"

# ── tools 脚本 ──────────────────────────────────────────

# 性能 micro-benchmark（ADR-0012）：just bench / just bench --us
bench *args:
    cd engine && uv run python tools/benchmark.py "$@"

# T10 1000+100 集成压测（kill criteria 3，tick p99<100ms）
loadtest *args:
    cd engine && uv run python tools/load_test.py "$@"

# 场景修订量度量（四道可跑通性 + v0->v1 diff）：just measure scenes/xueshan_micro
measure scene:
    cd engine && uv run python tools/measure_revision.py "{{scene}}"

# 门派武器草表 -> 去重分类 ItemDef YAML（ADR-0060 决策 6）：just weapons-load
weapons-load *args:
    cd engine && uv run python tools/weapon_finalize.py "$@"

# 门派护甲草表 -> 去重分类 -> merge 进 items.yaml（ADR-0064 决策 6）：just armor-load
# 草表不存在自动重跑提取；幂等（marker 剥离重追加护甲段，武器段保留）。
armor-load *args:
    cd engine && uv run python tools/armor_finalize.py "$@"

# golden trace 录制（连本地 FluffOS driver，ADR-0009）：just golden-record --login
golden-record *args:
    cd engine && uv run python -m tools.golden_trace.recorder "$@"

# golden trace 三层 diff（L1 概率 / L2 文本 / L3 语义，ADR-0027）
golden-diff *args:
    cd engine && uv run python -m tools.golden_trace.diff "$@"

# 内容生成 v0（M3-1，ADR-0036）
gen-rooms *args:
    cd engine && uv run python tools/content_gen/generate_rooms_v0.py "$@"

# M2/UGC 创作闭环（ADR-0053）：just orchestrate create --intent ... --out ... --bible ...
orchestrate *args:
    cd engine && uv run python -m xkx.orchestrator "$@"

# M2-2 FastAPI + WebSocket 评审工作台：just serve-workbench --output-dir ...
serve-workbench *args:
    cd engine && uv run python -m xkx.workbench "$@"

# 调用点枚举统计（阶段 0 任务 6 抽样校准，ADR-0046）：just scan
scan *args:
    cd engine && uv run python -m tools.sampling.scan_callothers "$@"

# ── 逃生口 / 杂项 ───────────────────────────────────────

# 在 engine venv 跑任意 python：just python -c "import xkx; print(xkx.__file__)"
python *args:
    cd engine && uv run python "$@"

# 在 engine venv 跑任意 pytest 参数：just pytest -m slow --lf
pytest *args:
    cd engine && uv run pytest "$@"

# 清缓存（.pytest_cache / .ruff_cache / .hypothesis / __pycache__）
clean:
    cd engine && rm -rf .pytest_cache .ruff_cache .hypothesis && find . -type d -name __pycache__ -prune -exec rm -rf {} +
