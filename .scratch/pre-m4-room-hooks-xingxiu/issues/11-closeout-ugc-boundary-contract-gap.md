---
Status: resolved
---

# 11 — 收口：UGC 边界回归 + 十类整合 + 契约/GAP/CONTEXT/PROGRESS

**What to build:** 票 `02`–`10` 落地后做收口：复核 UGC 边界的机器可检查化（`01` 已随字段落地，本票只复核不补代码）——内容包轨道声明钩子字段的 `--validate`/`--strict`/非严格加载路径判定一致失败；核对 `xingxiu_mechanics.yaml` 十类机关全部各有至少一条可玩验收路径且端到端跑通（S3），与官方扬州 `m2_mvp_scene` 的加载/测试互不干扰；`docs/creator-contract-v0.md` 新增一节明确「钩子引用字段为官方轨专属、不在创作者契约的加法承诺范围内、UGC 内容包引用即失败」；`docs/gap-ledger.md` 新增一行说明「运行时改世界」机关目前只能靠官方可信房间钩子表达，纯声明式 YAML 独立表达不到，且明示不做整区星宿移植、不等价 LPC 行为；同时修订既有「剧情门」行措辞使其与本批钩子边界一致（不产生矛盾表述）；核对 `CONTEXT.md` 房间钩子/`xingxiu_mechanics`/窄 `ctx`/房间自由状态相关词条与最终实现一致（小出入直接回写，大偏差先短 grill）；更新 `PROGRESS.md`（Done 增补、Next Up 改为 M4 评估、明确不自动开 M4）；本 effort README/issues Status 收口为关闭态。

对应 spec：US47–51；Testing 全量回归 + S3。

**Blocked by:** `02`、`03`、`04`、`05`、`06`、`07`、`08`、`09`、`10`（十类机关全部落地或已按治理止损线明文重估/止损）。

- [x] 复核内容包轨道声明钩子字段的加载/`--validate`/`--strict` 一致失败判定（信任边界，非「加法只警告」的一般规则）。
- [x] `xingxiu_mechanics.yaml` 十类机关全部至少一条可玩验收路径核对通过；端到端命令序列跑通（S3）。
- [x] 与官方扬州 `m2_mvp_scene` 的加载/测试互不干扰（两个场景文件独立，互不修改对方内容）。
- [x] `docs/creator-contract-v0.md` 新增一节：钩子引用字段官方轨专属说明，UGC 引用即失败。
- [x] `docs/gap-ledger.md`：新增「运行时改世界机关」行（已支持，官方可信钩子；UGC 仍禁；不做整区星宿移植、不等价 LPC 行为）；核对既有「剧情门」行措辞与本批边界一致，不自相矛盾。
- [x] `CONTEXT.md`：核对房间钩子/`xingxiu_mechanics`/窄 `ctx`/房间自由状态/`ON_BEFORE_LEAVE_ROOM` 等词条与实现一致；小出入直接回写，大偏差先短 grill 不静默发明。
- [x] `PROGRESS.md`：Done 增补本 effort 收口；Next Up 改为「M4 评估」；明确不自动开 M4；滑动窗口溢出移入 `.scratch/progress-archive.md`。
- [x] 本 effort README / issues Status 收口为关闭态；`docs/adr/0012` 结论不变，不新开 ADR。
- [x] 若 `02`–`10` 中有任何票按治理止损线重估/止损（工作量超预估 3 倍），本票在 Comments + `PROGRESS.md` Blocked 明文记录缩 scope 的机关及理由，不静默降级验收标准。
- [x] `just test` 全量回归绿。

## Comments

2026-07-22 Wave 7 收口：

- **UGC 复核**（不补代码）：`TestUgcRejectsHooksS2` 已覆盖 `load_pack` / `--validate` / `--validate --strict` 对内容包 `hooks` 一致失败；与「未消费字段只警告」路径分离。
- **十类 S3**：既有 `test_xingxiu_mechanics_02`–`10` 可玩路径 + 本票 `test_xingxiu_mechanics_closeout` 清单（九类 `RoomHookBinding` + `random_of` 落地出口 + `silk_rope` SkillBehavior；`m2_mvp_scene` 无 hooks、无星宿房键）。
- **契约**：`creator-contract-v0.md` 新增「官方轨专属：房间钩子引用」节——`hooks` 不在加法承诺内；UGC 引用即失败。
- **GAP**：新增「运行时改世界机关」已支持行；「剧情门」行改写为与钩子边界一致（契约止于声明式三件套）。
- **CONTEXT**：回写房间钩子 / 窄 ctx / `RoomFreeState` / `ON_BEFORE_LEAVE_ROOM` / `xingxiu_mechanics`；effort 标已关闭。
- **止损**：`02`–`10` 无治理止损缩 scope；Blocked 空。
- **ADR-0012** 结论不变，不新开 ADR；**不自动开 M4**。
- **code-review fix**：首 commit 勾选 PROGRESS 时文件尚未回写——本 fix 补 `PROGRESS.md`（Done Wave 7 / Next Up=M4 评估）+ Wave 2 移入 `progress-archive`；closeout 测 docstring 标明 e2e 仍靠 `02`–`10`。
