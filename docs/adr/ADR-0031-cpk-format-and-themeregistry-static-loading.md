# ADR-0031：CPK 格式固化 + ThemeRegistry 静态加载（M3 Wave 1 前置）

- 状态：待评审（2026-07-13）
- 日期：2026-07-13
- 阶段：M3 Wave 1 前置（M3-2 CPK 格式化 + StdLib CPK 骨架）
- 关联 dissent：[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 5（themed 治理，门派内容是题材包资产）/ dissent 10（平台特性范围过载，只做 StdLib CPK 骨架）/ dissent 3（层1 原语蠕变护栏，CPK capabilities 衔接层1 词汇表）

## 背景

[03 §四](../xkx-arch/03-DSL-UGC与Agent协作.md) 定义 CPK（内容包）= manifest + 资产集合，是 UGC 平台的内容单元；[03 §五](../xkx-arch/03-DSL-UGC与Agent协作.md) 定义 ThemeRegistry 三层粒度（核心 / 题材包 / UGC）+ 启动时静态加载。[04 §三 M3](../xkx-arch/04-迁移路径与避坑清单.md) 要求"官方 StdLib CPK：武侠内容以 CPK 形式入库（门派灵魂归属武侠题材包资产）"。

[ADR-0030](ADR-0030-family-content-pack-boundary-race-extraction.md) 已完成门派内容包边界切割（RaceProfile + FamilyBonus 声明式载体 + ThemeConfig 房间路径外提 + test_theme_neutrality 收官硬门禁），核心引擎无武侠烙印。本 ADR 是 ADR-0030 的下游：把"已切割的题材包资产"以 CPK 格式入库，并建立 ThemeRegistry 静态加载机制，让武侠内容作为 wuxia 题材 StdLib CPK 注册到引擎。

[03 §十落地顺序](../xkx-arch/03-DSL-UGC与Agent协作.md) 第 7 步"CPK 格式固化 + 创作者经济字段预留"是 M3 前置；硬约束 4"provenance 后移：开发期用简单版本号，门3 前才强制回填"。

## 问题：现有场景无 CPK 格式 + 无 ThemeRegistry

### 1. 场景散落无 manifest

[engine/scenes/](../../engine/scenes/) 下 5 个微场景（xueshan_micro / zhongnan_micro / wuxia_micro / academy_micro / age_of_sail_micro）是裸 YAML 目录（rooms.yaml / npcs.yaml / rules.yaml / quests.yaml / items.yaml），无 manifest，无 CPK 元数据（cpk_id / theme / pack_type / version / dependencies / entry_points）。

### 2. cli.py 硬编码加载单场景

[cli.py:32](../../engine/src/xkx/cli.py#L32) `SCENE_DIR = .../scenes/xueshan_micro` 硬编码加载单个微场景，无 CPK 加载器，无题材归属，无多 CPK 注册。

### 3. 无 ThemeRegistry

[03 §五](../xkx-arch/03-DSL-UGC与Agent协作.md) 要求 ThemeRegistry = 启动时静态注册表（`theme_id -> ThemeDescriptor`），每题材注册 component_schemas / condition_predicates / action_verbs / default_assets / themed_governance_policies。当前引擎无此机制，ADR-0030 的 RaceProfile / FamilyBonus / ThemeConfig 载体虽就绪但无题材包注册入口（测试用直接构造，生产无注入路径）；ADR-0028 决策 6 class 分支表同理（[title.py](../../engine/src/xkx/runtime/title.py) `set_class_tables` 可注入，但无题材包加载入口）。

### 4. compile_scene 无 manifest 元数据

[ir.py:37](../../engine/src/xkx/dsl/ir.py#L37) `compile_scene` 产出裸 IR dict（schema_version + rooms/npcs/quests/items），无 CPK manifest 关联，IR 与 CPK 脱节。

## 决策

### 决策 1：CpkManifest 数据模型（对齐 03 §四，M3 简化）

新建 [engine/src/xkx/dsl/cpk.py](../../engine/src/xkx/dsl/cpk.py)，pydantic v2 模型对齐 [03 §四](../xkx-arch/03-DSL-UGC与Agent协作.md) manifest 结构，M3 范围简化（provenance / market / resource_quota 后置）：

| 字段 | 类型 | M3 状态 | 对照 03 §四 |
|---|---|---|---|
| `cpk_id` | `str` | 必填 | `cpk_id: wuxia_shaolin_v3` |
| `schema_version` | `int` | 必填（=1） | `schema_version: 1` |
| `theme` | `str` | 必填 | `theme: wuxia` |
| `pack_type` | `Literal["module_pack","ugc"]` | 必填（M3 全 module_pack） | `pack_type: module_pack` |
| `version` | `str` | 必填（SemVer 开发期） | `version: 3.1.0` |
| `license` | `str` | 必填 | `license: CC-BY-SA-4.0` |
| `author` | `str` | 必填（开发期简单署名） | provenance.author 简化 |
| `dependencies` | `list[CpkDependency]` | 必填（M3 微场景空） | `dependencies: [...]` |
| `capabilities_required` | `list[str]` | 必填（module_pack 可空） | `capabilities_required: [...]` |
| `entry_points` | `dict[str,str]` | 必填（main_scene） | `entry_points: {main_scene: ...}` |
| `market` | `MarketFields` | Day1 预留（不实现功能） | `market: {title/tags/...}` |
| `provenance` | `Provenance \| None` | M3 None（后置门3） | 全量 provenance 后置 |
| `resource_quota` | `ResourceQuota \| None` | M3 None（UGC 后置） | UGC 沙箱配额后置 |

**module_pack vs ugc 区别**（[03 §五](../xkx-arch/03-DSL-UGC与Agent协作.md) 三层粒度）：

- `module_pack`（受信任开发者，StdLib 级）：进程级无沙箱 Python，`capabilities_required` / `resource_quota` 不强制（信任）。M3 全部 CPK 是 module_pack（官方 StdLib）。
- `ugc`（创作者，沙箱）：RestrictedPython 受限，`capabilities_required` / `resource_quota` 强制。后置 Wave 3 / M3 后。

**Provenance 简化**（[03 §四](../xkx-arch/03-DSL-UGC与Agent协作.md) 硬约束 4 + 用户决策 5）：M3 开发期只用 `version` + `author` 简单署名；全量 provenance（`content_hash` blake3 / `parents` / `prompt_hash` / `legacy_authors`）后置门3（首次对外发布前强制回填）。M3 是内部 demo，不触发门3。

**Market Day1 预留**（[03 §四](../xkx-arch/03-DSL-UGC与Agent协作.md) + [§八](../xkx-arch/03-DSL-UGC与Agent协作.md)）：`MarketFields`（title / description / tags / author_id / revenue_share / price）字段存在但 M3 不实现浏览 / 搜索 / 安装 / 评分 / 分账功能（后置 M3 后）。

### 决策 2：CPK 目录格式（扁平，最小改动）

5 微场景保持现有 [engine/scenes/](../../engine/scenes/) 目录结构，每个加 `manifest.yaml`：

```text
engine/scenes/xueshan_micro/
  manifest.yaml       # 新增：CpkManifest
  rooms.yaml          # 现有层0
  npcs.yaml           # 现有层0
  quests.yaml         # 现有层0（xueshan 有）
  items.yaml          # 现有层0（xueshan 有）
  rules.yaml          # 现有层1
```

**否决替代方案**（标准化 `cpks/<theme>/<cpk_id>/manifest.yaml + assets/`）：代价是移动 5 微场景 + 改所有测试路径 + 改 cli.py / measure_revision.py，违反收敛优先于完备。扁平加 manifest 最小改动，CPK 格式与目录解耦（manifest 内 `theme` 字段声明归属，不靠目录路径）。

### 决策 3：ThemeRegistry 静态加载（03 §五）

新建 [engine/src/xkx/runtime/theme_registry.py](../../engine/src/xkx/runtime/theme_registry.py)，启动时静态注册表：

**ThemeDescriptor**（题材包描述符）：

| 字段 | 类型 | 对照 03 §五 |
|---|---|---|
| `theme_id` | `str` | `wuxia` / `default`（非武侠测试） |
| `race_profile` | `RaceProfile` | ADR-0030 人类种族基础 |
| `family_bonuses` | `list[FamilyBonus]` | ADR-0030 门派加成（M3 填 1-2，全量后置） |
| `theme_config` | `ThemeConfig` | ADR-0030 房间路径（wuxia / default） |
| `class_tables` | `dict` | ADR-0028 class 分支表（set_class_tables 注入） |
| `condition_predicates` | `set[str]` | 层1 谓词词汇表（ADR-0016 已扩充 8 类） |
| `action_verbs` | `set[str]` | 层1 动词词汇表 |
| `governance_policies` | `dict` | ADR-0029 themed 治理（平台级 fail-closed，复用） |

**ThemeRegistry**：`dict[str, ThemeDescriptor]`，启动时静态加载，无运行时 unload / 版本协商 / 隔离（[04 §六](../xkx-arch/04-迁移路径与避坑清单.md) 不做清单"题材包运行时热插拔"）。

**M3 注册 2 题材**：

- `wuxia`：武侠旗舰题材（xueshan / zhongnan / wuxia_micro 3 CPK），`ThemeConfig.wuxia()` + 武当派 FamilyBonus（ADR-0030 标准）+ 武侠 class 表
- `default`：非武侠测试题材（academy / age_of_sail 2 CPK），`ThemeConfig.default()` + 海盗帮派 FamilyBonus（ADR-0030 非武侠边界验证）+ 非武侠 class 表

> 第二题材真实存在且需不停服切换时才议运行时热插拔（[04 §六](../xkx-arch/04-迁移路径与避坑清单.md)）。M3 静态加载 2 题材（wuxia 旗舰 + default 测试），不实现热插拔。

### 决策 4：CPK 加载器（manifest -> IR -> 注册）

新建 [engine/src/xkx/dsl/cpk_loader.py](../../engine/src/xkx/dsl/cpk_loader.py)：

```python
def load_cpk(path: Path) -> tuple[CpkManifest, dict]:
    """读 manifest.yaml + 资产 YAML -> (manifest, IR)。

    复用 layer0.load_rooms/load_npcs/load_quests/load_items + layer1.load_rules
    + ir.compile_scene。manifest 校验（schema + 依赖 + entry_points 引用完整性）。
    """
```

**加载流程**：

1. 读 `manifest.yaml` -> `CpkManifest`（pydantic 校验）
2. 读资产 YAML -> 层0 / 层1 Def
3. `compile_scene` -> IR（复用现有 [ir.py](../../engine/src/xkx/dsl/ir.py)）
4. manifest 校验：`entry_points.main_scene` 在 IR rooms 中 / `dependencies` 引用已注册 CPK（M3 线性无依赖）/ `theme` 已在 ThemeRegistry 注册
5. 注册到 ThemeRegistry（按 `manifest.theme` 归属题材）

**四道校验衔接**（[ADR-0008](ADR-0008-schema-validator-four-checks.md) SchemaValidator 最小版已有 [validator.py](../../engine/src/xkx/dsl/validator.py)）：M3 扩展 manifest 级校验（cpk_id 唯一 / theme 已注册 / entry_points 引用完整 / dependencies 已加载），UGC 沙箱级校验（CapabilityAuditor / ResourceBudgetChecker / DependencyResolver networkx）后置 Wave 3。

### 决策 5：5 微场景重整为 StdLib CPK

每个微场景加 `manifest.yaml`，声明 `pack_type: module_pack` + `theme` + `entry_points`：

| 微场景 | theme | cpk_id | entry_points.main_scene | 用途 |
|---|---|---|---|---|
| xueshan_micro | wuxia | wuxia_xueshan_micro | xueshan/dshanlu | M3 旗舰武侠（Wave 2 扩展完整内容） |
| zhongnan_micro | wuxia | wuxia_zhongnan_micro | zhongnan/gate | 武侠微场景（S2-S4f） |
| wuxia_micro | wuxia | wuxia_micro | （现有首房间） | 武侠微场景 |
| academy_micro | default | academy_micro | （现有首房间） | 非武侠主题无关性验证 |
| age_of_sail_micro | default | age_of_sail_micro | （现有首房间） | 非武侠主题无关性验证（大航海） |

> M3-2 只重整格式（加 manifest + 接入 ThemeRegistry），不扩内容。xueshan 完整内容扩展是 Wave 2（M3-11 门派核心循环）。

### 决策 6：cli.py 改读 ThemeRegistry + CPK 加载器

[cli.py](../../engine/src/xkx/cli.py) 从硬编码 `SCENE_DIR` 改为：

1. 启动时 `ThemeRegistry` 静态加载 wuxia + default 题材
2. `load_cpk(scenes/xueshan_micro)` -> (manifest, IR)
3. `build_world(ir, theme_config=registry["wuxia"].theme_config)`

向后兼容：保留 `load_game(scene="xueshan_micro")` 参数，默认 wuxia 旗舰。

### 决策 7：范围边界（M3 只 StdLib CPK 骨架）

**M3 做**：

- CpkManifest 数据模型（module_pack，provenance / market / resource_quota 后置）
- ThemeRegistry 静态加载（wuxia + default 2 题材）
- CPK 加载器（manifest -> IR，线性依赖）
- 5 微场景重整格式

**M3 不做**（后置）：

- UGC CPK 沙箱（RestrictedPython）-> Wave 3 / M3 后
- 内容审核 pipeline MVP -> Wave 3（M3-3，独立 ADR）
- CPK 内容寻址 blake3 + 不可变快照 -> 门3（与 provenance 同期）
- CPK 依赖图 networkx 拓扑排序 + 环检测 -> UGC 后置（M3 线性无依赖）
- 内容市场浏览 / 搜索 / 安装 / 评分 / 分账 -> M3 后（market 字段 Day1 预留）
- 多题材运行时热插拔 -> 第二题材真实存在且需不停服切换后（[04 §六](../xkx-arch/04-迁移路径与避坑清单.md)）
- 全量 provenance 回填 -> 门3（首次对外发布前）
- 版权清洗 71 文件 -> Wave 3（M3-4，独立 ADR）

## 开放问题（待用户裁决）

1. **CPK 目录格式**：扁平（`scenes/xueshan_micro/manifest.yaml` + 现有 yaml，最小改动）vs 标准化（`cpks/wuxia/xueshan/manifest.yaml + assets/`）？**倾向**：扁平（收敛，CPK 格式与目录解耦）。

2. **ThemeRegistry 注册粒度**：M3 注册 wuxia + default 2 题材，还是只 wuxia（default 用 `ThemeConfig.default()` 不注册为题材）？**倾向**：注册 2 题材（default 作为非武侠测试题材，承载 academy / age_of_sail + 非武侠 FamilyBonus，主题无关性验证完整）。

3. **CPK 依赖解析深度**：M3 线性无依赖（微场景独立）vs networkx 拓扑排序？**倾向**：M3 最小（线性，dependencies 空校验），networkx 后置 UGC（[03 §三](../xkx-arch/03-DSL-UGC与Agent协作.md) DependencyResolver）。

4. **manifest schema_version**：复用 `IR_SCHEMA_VERSION=1` vs 独立 `CPK_MANIFEST_SCHEMA_VERSION`？**倾向**：独立 `CPK_MANIFEST_SCHEMA_VERSION=1`（CPK manifest 与 IR 是两层，独立演进）。

5. **class_tables 注入**：[ADR-0028](ADR-0028-rank-d-spec-and-pronoun-context.md) 决策 6 class 分支表当前测试用 `set_class_tables` 注入，M3 是否在 `ThemeDescriptor.class_tables` 落地武侠表？**倾向**：M3 落地（wuxia 题材注册武侠 `CLASS_TITLE_TABLE`，default 注册非武侠表），完成 ADR-0028 题材包注入闭环。

## 不做（范围边界）

见决策 7。

## kill criteria

- **CPK 格式过度设计**（引入 UGC 沙箱 / 内容寻址 / networkx 依赖图等 M3 后置能力）-> 暂停，回退到 StdLib CPK 骨架（dissent 10 平台特性范围过载）。
- **ThemeRegistry 滑向运行时热插拔**（引入 unload / version / isolation）-> 暂停，回退静态加载（[04 §六](../xkx-arch/04-迁移路径与避坑清单.md) 不做清单）。
- **主题无关性回归**（5 微场景重整后 test_theme_neutrality 不通过）-> 暂停，先修主题无关性（[ADR-0030](ADR-0030-family-content-pack-boundary-race-extraction.md) 硬门禁）。

## 验收标准（对应 04 §三 M3 官方 StdLib CPK）

- [ ] CpkManifest pydantic 模型对齐 03 §四（M3 简化：provenance / market / resource_quota 后置）
- [ ] ThemeRegistry 静态加载 wuxia + default 2 题材（ThemeDescriptor 8 字段）
- [ ] CPK 加载器 `load_cpk`（manifest -> IR，复用 compile_scene）
- [ ] 5 微场景各加 `manifest.yaml`（pack_type=module_pack + theme + entry_points）
- [ ] cli.py 改读 ThemeRegistry + load_cpk（向后兼容 load_game 参数）
- [ ] test_theme_neutrality 硬门禁持续通过（5 微场景重整不引入武侠烙印）
- [ ] test_load_test CI 门禁不退化（tick p99 < 100ms）
- [ ] 全量 tests 绿 + ruff 全过
- [ ] CPK manifest 可序列化（[ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)，Day1 预留 market 字段往返）

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 5（themed 治理，门派内容是题材包资产，CPK 是题材包资产载体）
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 10（平台特性范围过载，M3 只做 StdLib CPK 骨架，UGC 沙箱 / 市场后置）
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 3（层1 原语蠕变护栏，CPK capabilities_required 衔接层1 谓词 / 动词词汇表）
- [03](../xkx-arch/03-DSL-UGC与Agent协作.md) §四（CPK manifest 结构）/ §五（ThemeRegistry 三层粒度 + 静态加载）/ §十落地顺序第 7 步
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三 M3（官方 StdLib CPK）/ §六不做清单（题材包运行时热插拔）
- [ADR-0030](ADR-0030-family-content-pack-boundary-race-extraction.md)（门派切割：RaceProfile / FamilyBonus / ThemeConfig 载体就绪，本 ADR 下游入库）
- [ADR-0028](ADR-0028-rank-d-spec-and-pronoun-context.md) 决策 6（class 分支表注入，ThemeDescriptor.class_tables 落地）
- [ADR-0029](ADR-0029-world-governance-system.md)（themed 治理平台级 fail-closed，ThemeDescriptor.governance_policies 复用）
- [ADR-0008](ADR-0008-schema-validator-four-checks.md)（SchemaValidator 最小版，CPK manifest 校验衔接）
- [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)（CPK manifest 可序列化）
