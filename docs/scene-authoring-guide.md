# 场景创作：官方轨与内容包轨

> 两条加载轨道，**同一套**场景 YAML 语法。  
> 字段契约见 [创作者契约 v0](creator-contract-v0.md)；表达不到的能力见 [GAP 台账](gap-ledger.md)。  
> 产出自 M3 停机加固票 [`09`](../.scratch/m3-hardening/issues/09-scene-authoring-two-tracks-doc.md)。

本文档**不伴随代码改动**：本窗口**不做**官方场景包化（不会把默认场景改造成带 `manifest.yaml` 的内容包目录）。双轨共存是刻意保留的现状，不是文档里假装已经统一。

## 一句话

学一套场景 YAML（v0 契约）即可写官方场景或外部内容包。差异只有两点：

1. 是否多一份 `manifest.yaml` 包裹包身份；
2. 走哪条 CLI / API 入口加载。

## 双轨对照

| | **官方轨**（无 manifest） | **内容包轨**（有 manifest） |
|---|---|---|
| 场景数据 | 单文件场景 YAML | 包目录内的 `scene.yaml` |
| 包身份 | 无 | 同目录 `manifest.yaml`（`id` / `version` 等） |
| 加载入口 | `load_scene(path)`；CLI **无** `--pack` | `load_pack(dir)`；CLI `--pack <目录>` |
| 校验入口 | （无独立 `--validate`；靠引擎测试 / `just verify-m2` 等） | `--pack <目录> --validate`［可选 `--strict`］ |
| 具体范本 | [`engine/data/m2_mvp_scene.yaml`](../engine/data/m2_mvp_scene.yaml)（官方轻量武侠题材包） | [`.scratch/m3-ugc-loop-creation-surface/example-pack/`](../.scratch/m3-ugc-loop-creation-surface/example-pack/)（非武侠「废弃探测站」） |
| 共用契约 | [创作者契约 v0](creator-contract-v0.md) 的场景 YAML 字段集合 | 同左；另加契约中的 `manifest.yaml` 已知字段 |

## 官方轨

- **范本**：[`engine/data/m2_mvp_scene.yaml`](../engine/data/m2_mvp_scene.yaml)——华山村 / 扬州子集 / 少林 / 野外 / 官道 / 渡口等 MVP 分区，单文件、无 `manifest.yaml`。
- **写法**：直接写 `rooms` / `items` / `npcs` / `player` 等顶层段，字段语义与内容包内的 `scene.yaml` **完全相同**。
- **CLI 现状（诚实记录）**：`python -m mud_engine`（无 `--pack`）当前默认加载的是同轨、同契约的较小文件 [`engine/data/m1_default_scene.yaml`](../engine/data/m1_default_scene.yaml)（经 `scenes.build_world()`）。玩或回归 M2 MVP 武侠场景走 `load_mvp_scene()` / `just verify-m2*`，不是另开一套语法。

## 内容包轨

- **范本**：[`.scratch/m3-ugc-loop-creation-surface/example-pack/`](../.scratch/m3-ugc-loop-creation-surface/example-pack/)
  - [`manifest.yaml`](../.scratch/m3-ugc-loop-creation-surface/example-pack/manifest.yaml)——包身份（`id` / `version` / `creator` / `title`）
  - [`scene.yaml`](../.scratch/m3-ugc-loop-creation-surface/example-pack/scene.yaml)——场景本体（与官方轨同一套字段）
- **CLI**：

```bash
# 加载并进入 REPL（存档落在包目录下 save/）
python -m mud_engine --pack .scratch/m3-ugc-loop-creation-surface/example-pack

# 只校验，不进 REPL
python -m mud_engine --pack .scratch/m3-ugc-loop-creation-surface/example-pack --validate

# 未消费（透传）字段视为失败
python -m mud_engine --pack .scratch/m3-ugc-loop-creation-surface/example-pack --validate --strict
```

`--validate` / `--strict` 必须搭配 `--pack`；不能用来「单独校验」官方轨单文件（官方场景由引擎测试与 verify 脚本覆盖）。细节见创作者契约「机器可检查侧」。

## 创作者怎么选

- **改官方武侠 MVP、或只想交一份场景文件**：写单文件 YAML，对照 `m2_mvp_scene.yaml`，走官方轨。
- **交外部 / 异题材包、需要包身份与 `--validate` 反馈通道**：建目录，放 `manifest.yaml` + `scene.yaml`，对照 `example-pack/`，走内容包轨。

两轨都不要发明私有顶层段当「稳定 API」——透传键不在 v0 冻结范围内；表达不了的玩法先查 [GAP 台账](gap-ledger.md)。

## 本窗口明确不做

- 不把 `m2_mvp_scene.yaml`（或 `m1_default_scene.yaml`）改造成带 `manifest.yaml` 的内容包目录。
- 不合并两条 CLI 入口，也不要求创作者「只学其中一条」。
- 不新增场景字段或加载器行为——本文只说明现状。
