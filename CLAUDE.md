# CLAUDE.md - 侠客行 MUD 现代化重构 项目指令

> 本文件每个 session 自动加载。它是 agent 在本仓库工作的"操作手册"。
> 开工前必读三件：本文件 + [PROGRESS.md](PROGRESS.md) + [docs/xkx-arch/04-迁移路径与避坑清单.md](docs/xkx-arch/04-迁移路径与避坑清单.md)（当前阶段）。

## 项目一句话

将经典 LPC MUD《侠客行》（8412 LPC 文件、6414 房间、21 门派）从 0 重构为全新 greenfield Python 项目。LPC 是规格源（只读参考），新引擎从零按规格实现，行为等价验证。详见 [架构文档 README](docs/xkx-arch/README.md)。

## 仓库拓扑

- `adm/ cmds/ d/ kungfu/ ...`（仓库根）：**LPC 规格源，只读参考，禁止修改**。新引擎的行为等价基准。
- [engine/](engine/)：**新 greenfield Python 项目**（当前工作区）。`src/xkx/` 包，`tests/` 测试。ADR 在仓库级 [docs/adr/](docs/adr/)。
- [docs/xkx-arch/](docs/xkx-arch/)：架构文档（00-05 + README）。00-04 是实施基线，05 是决策溯源。`_archive/` 是前两轮归档。
- [docs/adr/](docs/adr/)：实现期决策日志（ADR-NNN-xxx，每条一文件）。
- [PROGRESS.md](PROGRESS.md)：活的进度状态，跨 session 交接信源。
- `todo.md` / `README`：遗留的 LPC UTF-8 转码记录，与新项目无关，忽略。

## 六条收缩约束（硬边界，不可违反）

实施中任何引入下列复杂度的设计都是违规，须即时回退：

1. 不考虑分布式架构（验证 UGC 成立前）
2. 运维观测后置（仅 OpenTelemetry+Grafana+Langfuse，无 K8s/Helm）
3. 不考虑分布式网关（单机 1000 在线+100 并发）
4. 纯 Python（暂不考虑 Rust/Go）
5. 内存数据+本地 JSON 定时存档（策略模式，外部玩家测试前必须迁 PG）
6. 3 个开放问题已裁决（见 [02](docs/xkx-arch/02-三个开放架构问题裁决.md)），不得重新打开

完整"不做"清单见 [04 §六](docs/xkx-arch/04-迁移路径与避坑清单.md)。

## 关键架构不变量（从专家复审 dissent 提炼，实施中易踩）

- **tick=1s + compute<100ms + 非均匀 tick**（LPC heart_beat 实测 `set_heart_beat(1)`），不得引入 50ms/20Hz 框架。
- **Command 仅覆盖外部意图**，System tick 派生变更不经 Command；force_me=PrivilegedAction 是保真让步（ROOT 门控+强制审计）。
- **combat 确定性范围=combat-only**，全仿真确定性后置 M3 后。
- **do_attack 七步管线的文本与副作用交织不可分离**，不得"先算后 apply"。
- **PronounContext 必须携带 viewer**（三元组 speaker/viewer/target，`rankd.c` 实证 `this_player()` 依赖）。
- **JSON 存档崩溃安全**：write-temp+os.replace 原子写 + 事件循环外 offload + dirty-flag 分摊，不得重蹈 LPC `save_object` 全量覆盖无原子写的覆辙。
- **存储接口以"持久化边界"抽象**（persist=崩溃恢复级耐久），非"save=权威写"。
- **三层粒度 Theme > Module Pack > UGC CPK**，门派是 wuxia 题材下的 module pack 不是独立题材。
- **themed 治理（天雷/阴间/vote/法院）是平台级 fail-closed Python**，不落入 UGC 可编辑规则层。
- **CombatKernel 从武侠提取、用非武侠验证**（阶段 -1 非武侠微场景硬门禁）。

## 开发规范

- Python >=3.12，包名 `xkx`，代码在 [engine/src/xkx/](engine/src/xkx/)。
- **Python 命令目录**：所有 `python`/`pytest`/`ruff`/`uv` 命令在 [engine/](engine/) 下执行（`cd engine && ...`）。已配 PreToolUse hook 自动补前缀兜底（见 [.claude/hooks/cd_engine.py](.claude/hooks/cd_engine.py)），但写命令时仍应自觉 cd，hook 只是兜底而非依赖。
- 测试：pytest + hypothesis（属性测试，架构明确要求）。
- lint/format：ruff。行长上限 100（`engine/pyproject.toml` 的 `[tool.ruff]`）。E501 无法自动修复、`ruff format` 也不拆字符串字面量，须在写时即控制：
  - 长字符串用括号隐式拼接折行（`s = ("前半" "后半")`），不要指望事后 format 救场。
  - 中文按字符数计（每字算 1 字符），看着短不代表不超；中英文间空格也计入字符。
  - 每写完一组 edit 立即 `ruff check` 自检，不要攒到全部写完再统一查。
- 注释/排版遵循全局 CLAUDE.md（中文回复、中英文之间加空格、类注释不带 @author/@version）。
- 类型：优先类型提示；CapabilityToken/PermissionService 等安全相关模块必须类型完整。
- 提交：只在用户要求时 commit/push；在 master 分支时先开分支。

## 决策日志（ADR）

实施中发现架构假设需偏离 00-04 基线，在 [docs/adr/](docs/adr/) 写一条 ADR（命名 `ADR-NNN-xxx`，编号递增，格式见 [ADR-0001](docs/adr/ADR-0001-python-toolchain-and-skeleton.md)）。必须关联 [05](docs/xkx-arch/05-第三轮专家对抗复审报告.md) 的对应 dissent--那 10 条未消除风险几乎必然会在实施中冒头。

## session 交接

- 开工第一件事：读 [PROGRESS.md](PROGRESS.md)（做到哪）+ 本文件（怎么干）+ [04](docs/xkx-arch/04-迁移路径与避坑清单.md) 当前阶段（kill criteria）。
- 收工前：更新 [PROGRESS.md](PROGRESS.md) 的 Done / In Progress / Blocked / Next Up + 日期。
- 长任务跨 session：在 PROGRESS.md 的 In Progress 写清"当前子任务 + 卡在哪 + 下一步具体动作"。
- **PROGRESS.md 体量纪律**（token 经济学）：Done 单条 ≤2 行（摘要 + ADR 链接 + tests 数），细节进 ADR 不重复。每开新阶段把 Done 归档到 [docs/progress-archive/](docs/progress-archive/) `stage-N-done.md`，主文件只留当前阶段滚动窗口 + 活状态（In Progress/Blocked/Next Up/kill criteria）。目标主文件 < 8KB。
