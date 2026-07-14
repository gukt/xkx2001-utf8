# ADR-0033：内容审核 pipeline MVP（M3-3）

- 状态：已通过（2026-07-14）
- 日期：2026-07-14
- 阶段：M3 Wave 3（M3-3 内容审核 pipeline MVP）
- 关联：[03 §八](../xkx-arch/03-DSL-UGC与Agent协作.md) 分层内容审核 pipeline / [16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) Wave 3 / [ADR-0031](ADR-0031-cpk-format-and-themeregistry-static-loading.md) CPK 格式（M3-3 扫描 CPK 资产）/ [ADR-0038](ADR-0038-kill-criteria-5-round4-rooms-known-ids-quests-manual.md) 雪山派已入库内容（M3-1 选定门派）

## 背景

[16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) M3-3 要求"内容审核 pipeline MVP（自动化预检 + 专家审核）"，对齐 [03 §八](../xkx-arch/03-DSL-UGC与Agent协作.md) 分层内容审核 pipeline（4 层：自动化预检 / 社区众审 / 专家审核 / 平台终审）。M3 范围只做第 1 + 3 层 MVP，社区众审 + 平台终审后置。

**用户决策（2026-07-14）**：M3-4 版权清洗（71 文件改编化 / 标注 / 授权）整体后置--未商业化阶段过早清洗是过度工程（收敛优先于完备）。M3-3 只做**检测**（版权关键词扫描作为预检维度保留），命中标记 `needs_review` 不 block，商业化前清洗时预检已就位。

## 问题

1. **扫描方式**：预检扫描 CPK 资产文本，基于 [layer0 Def](../../engine/src/xkx/dsl/layer0.py) 字段枚举 vs 通用递归？
2. **审核状态位置**：预检结果与 CPK manifest 关联（03 §八"审核状态字段"），内嵌 manifest vs 独立报告？
3. **版权命中 severity**：金庸角色命中是 block（阻止发布）还是 needs_review（待处理）？M3-4 后置后如何标记？
4. **敏感词库**：MVP 是否内置敏感词？合规词库需法务确认，臆造有合规风险。
5. **manifest 写回**：预检后同步 `review_status` 到 manifest.yaml，如何保留注释 / 格式？
6. **专家审核载体**：人工 review 流程如何结构化？

## 决策

### 决策 1：通用递归扫描（不依赖 Def 模型）

[precheck.py](../../engine/src/xkx/content_review/precheck.py) `precheck_cpk` 读 manifest + 资产 YAML，`yaml.safe_load` -> dict/list，`_walk_strings` 递归遍历所有 str 值过词表。**不依赖 [layer0 Def](../../engine/src/xkx/dsl/layer0.py) 字段枚举**（通用，新增字段自动覆盖，Def 字段变更不波及预检）。对比基于 Def 字段枚举（脆弱，新字段需同步预检）。

### 决策 2：4 类词表 + license 校验

[rules.py](../../engine/src/xkx/content_review/rules.py) 内置 4 类词表（对齐 03 §八自动化预检）：

- **VIOLENCE**（过度血腥，`needs_review`）：虐杀 / 肢解 / 凌迟 等--武侠题材杀 / 血是常态，暴力词针对"超出武侠尺度的过度血腥"，需人工判。
- **SENSITIVE**（`info`）：**MVP 空表**，敏感词库后置接入（合规词库需法务确认，不可臆造）。
- **GAMBLING**（`needs_review`）：押注 / 轮盘 / 筹码 等。
- **COPYRIGHT**（版权关键词，`needs_review`）：金庸角色名 + 门派名（精简表，覆盖 LPC 常见衍生）+ `jinyong_role_work` 查出处小说。

license 合规（[precheck._check_license](../../engine/src/xkx/content_review/precheck.py)）：空 license = `block`（必须声明）；非空 = 放行（M3 宽松，外部发布前门3 严格化白名单）。

### 决策 3：manifest review_status 轻量字段 + _review.json 详细（资产/审核元数据分离）

[cpk.py](../../engine/src/xkx/dsl/cpk.py) `CpkManifest` 加 `review_status: ReviewStatus = PENDING`（四态：pending / passed / needs_review / rejected）。详细 findings 落 `<cpk_dir>/_review.json`（[review_status.write_review_report](../../engine/src/xkx/content_review/review_status.py)），manifest 只存状态。

**资产 / 审核元数据分离**：manifest 是资产真相源（只读给引擎），`_review.json` 是审核证据（随审核迭代变化）。避免审核迭代污染资产真相源。对齐 03 §八"预检结果与 CPK manifest 关联（审核状态字段）"--通过 review_status 字段 + `_review.json` 文件名（cpk_id 对应）建立关联。

### 决策 4：版权命中 needs_review 不 block（M3-4 后置）

版权关键词命中 severity = `needs_review`（非 `block`）。`PrecheckReport.passed` = 无 block + license 合规；`needs_review` 不阻塞 passed。`derive_status`：有 block / license 不合规 -> `rejected`；有 needs_review -> `needs_review`；否则 `passed`。

**M3-4 版权清洗后置**：雪山派 CPK 含 4 金庸角色（金轮法王 / 鸠摩智 / 灵智上人 / 达尔巴）+ "雪山派"门派名本身（《侠客行》）命中 `needs_review`，但 `passed=True`（不阻塞，商业化前清洗时预检就位）。M3 阶段不改名（保护 Wave 2 成果 + kill criteria 5 数据）。

### 决策 5：manifest 写回用 yaml 往返（丢注释，正式后置 ruamel）

[review_status.sync_manifest_status](../../engine/src/xkx/content_review/review_status.py) 读 `_review.json` derived_status，若 manifest 状态不同则 `model_dump(mode="json")` + `yaml.safe_dump` 写回。**MVP 会丢失 manifest.yaml 注释**（正式环境后置 ruamel 保注释）。默认预检只落 `_review.json` 不动 manifest（保护格式），`sync_manifest_status` 显式调用（CI / 人工），CLI `--sync-manifest` 选项触发。

### 决策 6：专家审核 checklist MVP（六维矩阵）

[checklist.py](../../engine/src/xkx/content_review/checklist.py) `REVIEW_CHECKLIST` 覆盖 [03 §八] 验证覆盖度六维矩阵（结构 / 数值 / 经济 / 任务逻辑 / 叙事 / 趣味）。预检覆盖可机器化维度（暴力 / 赌博 / 版权 / license），checklist 覆盖人工维度（叙事一致性 / 趣味 / 数值平衡人工校准）。`render_checklist_template` 产出 markdown 模板。**社区众审 / 平台终审后置**（M3 范围外）。

### 决策 7：创作期工具不进 runtime 导入图

`content_review` 模块同 [content_gen](../../engine/src/xkx/content_gen/) 架构定位：仅依赖 stdlib + 已有 pyyaml + pydantic，runtime 不 import 本包（04 §六收敛原则，无新运行时依赖）。CLI `python -m xkx.content_review <cpk_dir>`。

## 后置（M3 范围外）

- **M3-4 版权清洗**（71 文件改编化 / 标注同人非商用 / 授权路径评估）+ provenance 版权链全量回填（门3）--未商业化阶段后置（用户决策 2026-07-14）。
- **社区众审 / 平台终审**实现（03 §八第 2/4 层）。
- **敏感词库接入**（合规词库需法务确认）。
- **ruamel 保注释**写回 manifest（替代 yaml.safe_dump 丢注释）。
- **license 白名单校验**（外部发布前门3 严格化）。
- **71 文件盘点脚本**（[copyright_inventory] 脚本，原 M3-4a 词表盘点后置；M3-3 内置精简金庸词表足够验证版权扫描有效）。

## 验收

- [x] 自动化预检可扫描 CPK 资产（4 类词表命中 + license 校验）
- [x] 雪山派真实预检：4 金庸角色 + 雪山派门派名命中 `needs_review`，`passed=True`（验证预检对真实内容有效）
- [x] 审核状态集成：`review_status` 字段 + `_review.json` 落盘 + manifest 同步
- [x] 状态推导三态（rejected / needs_review / passed）
- [x] 专家审核 checklist MVP（六维矩阵 + 模板）
- [x] 1768 tests 全绿（1744 + 新增 24：test_content_review 20 + test_cpk review_status 4）
- [x] ruff 全过 + test_theme_neutrality 硬门禁不退化

## 关键发现

**雪山派 CPK（M3-1 已入库）含金庸衍生内容**：

- 4 角色：金轮法王（《神雕侠侣》）、鸠摩智（《天龙八部》）、灵智上人（《射雕英雄传》）、达尔巴（《神雕侠侣》）
- 门派名"雪山派"本身（《侠客行》白自在系）

来源：LPC 源 `d/xueshan/` + `kungfu/class/xueshan/`（大轮寺 / 金轮法王系，神雕衍生）。M3-1 选定门派本身就是 M3-4 版权清洗的天然示范对象，但 M3 阶段不清洗（后置）。M3-3 预检标记 `needs_review` 记录待办，商业化前清洗时预检已就位。

## 文件

- 新增 [content_review/](../../engine/src/xkx/content_review/)（rules / precheck / review_status / checklist / __main__）
- 修改 [dsl/cpk.py](../../engine/src/xkx/dsl/cpk.py)（+ ReviewStatus enum + review_status 字段）
- 新增 [tests/test_content_review.py](../../engine/tests/test_content_review.py)（20 测试）
- 扩展 [tests/test_cpk.py](../../engine/tests/test_cpk.py)（+ TestReviewStatus 4 测试）
- [.gitignore](../../engine/.gitignore) 加 `**/_review.json`（运行时产物不入库）
