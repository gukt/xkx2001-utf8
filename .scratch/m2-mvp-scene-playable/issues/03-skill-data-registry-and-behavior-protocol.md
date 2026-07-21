# 03 — 技能数据地基：SkillData 全局注册表 + skills: YAML 顶层段 + SkillBehavior 协议

**What to build:** 落地 spec Implementation Decisions「A3/B1」定义的技能三层组织里的前两层：`SkillData`（全局注册表 `SKILLS: dict[str, SkillData]`，不是挂在 entity 上的组件——与 `capabilities.CAPABILITIES` 是同一种"自描述规格列表"模式,但本身是**全局字典**而非"逐实体挂载"，更接近未来 07 号票 `FactionDefinition`/`FACTIONS` 会复用的同一种"顶层声明式全局注册表"写法，建议本票把"解析一个顶层段为全局字典 + 校验已知字段 + SceneLoadError 定位"这段逻辑写得足够通用，方便 07 号票直接复用同一模式，不强制共享一个 helper 函数，重复两次是可接受的）；每条技能含技能类型（如 `martial`，不强制枚举）、等级需求、招式列表（每招 `force`/`dodge`/`damage_type`/可选固定 `damage`/`lvl` 门槏/展示文案）；`skills:` 新顶层段加入 `scene_loader._TOP_LEVEL_KNOWN_SECTIONS`；`SkillBehavior` 是 `Protocol`（`hit_ob(ctx, damage) -> int|str|None` / `hit_by(ctx) -> None` / `post_action(ctx) -> None`），`register_skill_behavior(skill_id, behavior)` 按技能 id 注册（与 `commands.register` 同构）。本票**只建数据地基**，不接入真实战斗结算（02 号票的 `resolve_attack` 占位调用点，16 号票才真正接入）、不接入角色组件（05 号票的 `SkillLevels` 只存"学会了哪些技能+等级/经验"，招式内容永远查本票的 `SKILLS`，不复制）。

**Blocked by:** None — 全局注册表 + YAML 顶层段解析，不依赖房间/NPC 能力注册表（01 号票是"逐实体挂载"模式，与本票"全局字典"模式是两回事），可与 01/02/04 并行开工。

**Status:** resolved

- [x] `SkillData`（技能类型/等级需求/招式列表）与招式项（`force`/`dodge`/`damage_type`/可选固定 `damage`/`lvl` 门槏/展示文案）的数据形状落地；`SKILLS: dict[str, SkillData]` 全局注册表。
- [x] `skills:` 顶层段 YAML 解析：加入 `_TOP_LEVEL_KNOWN_SECTIONS`，解析失败（缺字段/类型错）抛 `SceneLoadError` 带定位信息（与 `scene_loader.py` 现有报错风格一致：文件路径 + 出错条目键）。
- [x] 场景加载完成后 `SKILLS` 被正确填充（`load_scene` 调用点/时机由实现阶段决定，建议贴近 `attach_nature`/`attach_ai_system` 的调用位置）。
- [x] `SkillBehavior` 是 `@runtime_checkable` 或至少类型可检查的 Protocol（三个钩子方法签名明确）；`register_skill_behavior`/一个按 id 查询的读取函数（供 16 号票消费）。
- [x] 引用校验：招式声明的字段类型错误（如 `force` 非数字）在加载期报错，不是运行时静默失败（对齐 M1 "加载期数据校验" 边界）。
- [x] 多个场景文件重新 `load_scene` 时 `SKILLS` 全局状态如何处理（覆盖/清空重建）有明确、测试锁定的行为——避免"两次加载互相污染"的隐性 bug（测试建议：连续加载两份不同 `skills:` 内容的场景，断言第二次加载后 `SKILLS` 只含第二份内容）。
- [x] 至少 2 条技能数据样例（供后续票直接引用，如"罗汉拳基础招式"）写入测试夹具，不需要是最终少林题材内容（24 号票会替换/追加真正的题材数据）。
- [x] 现有测试全绿不回归。
