---
Status: ready-for-agent
---

# 11 — 收口：UGC 边界回归 + 十类整合 + 契约/GAP/CONTEXT/PROGRESS

**What to build:** 票 `02`–`10` 落地后做收口：复核 UGC 边界的机器可检查化（`01` 已随字段落地，本票只复核不补代码）——内容包轨道声明钩子字段的 `--validate`/`--strict`/非严格加载路径判定一致失败；核对 `xingxiu_mechanics.yaml` 十类机关全部各有至少一条可玩验收路径且端到端跑通（S3），与官方扬州 `m2_mvp_scene` 的加载/测试互不干扰；`docs/creator-contract-v0.md` 新增一节明确「钩子引用字段为官方轨专属、不在创作者契约的加法承诺范围内、UGC 内容包引用即失败」；`docs/gap-ledger.md` 新增一行说明「运行时改世界」机关目前只能靠官方可信房间钩子表达，纯声明式 YAML 独立表达不到，且明示不做整区星宿移植、不等价 LPC 行为；同时修订既有「剧情门」行措辞使其与本批钩子边界一致（不产生矛盾表述）；核对 `CONTEXT.md` 房间钩子/`xingxiu_mechanics`/窄 `ctx`/房间自由状态相关词条与最终实现一致（小出入直接回写，大偏差先短 grill）；更新 `PROGRESS.md`（Done 增补、Next Up 改为 M4 评估、明确不自动开 M4）；本 effort README/issues Status 收口为关闭态。

对应 spec：US47–51；Testing 全量回归 + S3。

**Blocked by:** `02`、`03`、`04`、`05`、`06`、`07`、`08`、`09`、`10`（十类机关全部落地或已按治理止损线明文重估/止损）。

- [ ] 复核内容包轨道声明钩子字段的加载/`--validate`/`--strict` 一致失败判定（信任边界，非「加法只警告」的一般规则）。
- [ ] `xingxiu_mechanics.yaml` 十类机关全部至少一条可玩验收路径核对通过；端到端命令序列跑通（S3）。
- [ ] 与官方扬州 `m2_mvp_scene` 的加载/测试互不干扰（两个场景文件独立，互不修改对方内容）。
- [ ] `docs/creator-contract-v0.md` 新增一节：钩子引用字段官方轨专属说明，UGC 引用即失败。
- [ ] `docs/gap-ledger.md`：新增「运行时改世界机关」行（已支持，官方可信钩子；UGC 仍禁；不做整区星宿移植、不等价 LPC 行为）；核对既有「剧情门」行措辞与本批边界一致，不自相矛盾。
- [ ] `CONTEXT.md`：核对房间钩子/`xingxiu_mechanics`/窄 `ctx`/房间自由状态/`ON_BEFORE_LEAVE_ROOM` 等词条与实现一致；小出入直接回写，大偏差先短 grill 不静默发明。
- [ ] `PROGRESS.md`：Done 增补本 effort 收口；Next Up 改为「M4 评估」；明确不自动开 M4；滑动窗口溢出移入 `.scratch/progress-archive.md`。
- [ ] 本 effort README / issues Status 收口为关闭态；`docs/adr/0012` 结论不变，不新开 ADR。
- [ ] 若 `02`–`10` 中有任何票按治理止损线重估/止损（工作量超预估 3 倍），本票在 Comments + `PROGRESS.md` Blocked 明文记录缩 scope 的机关及理由，不静默降级验收标准。
- [ ] `just test` 全量回归绿。

## Comments

