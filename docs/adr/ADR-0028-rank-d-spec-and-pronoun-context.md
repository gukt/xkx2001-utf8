# ADR-0028：RANK_D 规格提取 + PronounContext 三元组完整求值

- 状态：草案（阶段 2 Wave 2 前置，2.5 TitleSystem 前置 ADR）
- 日期：2026-07-12
- 阶段：阶段 2 Wave 2（2.5 TitleSystem 称谓）
- 关联：[04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 2（M2-5）/ §七避坑 5（PronounContext viewer，System tick 无说话者回退）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 6（previous_object/PronounContext viewer 缺失）+ §二专家 3 承重论断 2（RANK_D query_close 是观察者相对的二元关系函数，依赖 this_player()）+ §三 Q3 force_me 收敛 / [15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.5 任务卡 + §五 ADR 表 + §七 dissent 映射 + §八规格补充（层 H 第二梯队 rankd PKS 称号）/ [ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md)（ActionContext 三元组 actor/source/viewer/target + PronounContext viewer 不变量）/ [ADR-0021](ADR-0021-previous-object-explicit-mapping.md)（previous_object 显式化，B 类 PronounContext viewer）/ [ADR-0025](ADR-0025-query-index-layer.md)（query() 语义 + 后置 key 激活策略，2.5 激活 title/nickname/shen）/ [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)（TitleComp 可序列化）/ [ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 决策 3（rankd -> PronounContext 三元组）/ [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（13 组件，TitleComp 新增第 14）/ [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py)（RANK_D 规格部分提取）/ [spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py)（PronounContext viewer 不变量 + visible 三级）/ [runtime/pronoun.py](../../engine/src/xkx/runtime/pronoun.py)（PronounService 现状，viewer/target 显式传参框架）/ [adm/daemons/rankd.c](../../adm/daemons/rankd.c)（RANK_D 7 函数 LPC 规格源）/ [feature/name.c](../../feature/name.c)（short() 状态修饰）/ [adm/simul_efun/message.c](../../adm/simul_efun/message.c)（message_vision 4 变量代词）/ [adm/simul_efun/gender.c](../../adm/simul_efun/gender.c)（gender_self/gender_pronoun）

## 背景

[15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.5 任务卡：实现 RANK_D 7 函数称谓求值，对照 [层 H](../xkx-arch/08-阶段-0-实施计划.md) rankd.c 规格 + PronounContext 三元组。验收：rankd.c 7 函数行为等价；PronounContext 三元组求值与 LPC `this_player()` 依赖一致。

**LPC 规格源**（只读参考，本 ADR 完整提取）：

- [adm/daemons/rankd.c](../../adm/daemons/rankd.c) 7 函数（`rankd.c:1-651`）：
  - `query_rank(ob)`（行 8-320）：按 gender/class/shen/PKS/wizhood 求等级称谓串（如"【大侠】"/"【土匪】"/"【天后】"）
  - `query_respect(ob)`（行 322-404）：尊敬称谓（如"壮士"/"姑娘"/"大师"）
  - `query_rude(ob)`（行 406-461）：粗鄙称谓（如"臭贼"/"贼尼"/"老匹夫"）
  - `query_self(ob)`（行 463-513）：自称（如"在下"/"小女子"/"贫僧"）
  - `query_self_rude(ob)`（行 515-569）：傲慢自称（如"老子"/"老娘"/"本王"）
  - `query_close(ob)`（行 570-613）：亲近称谓（如"弟弟"/"妹妹"/"哥哥"），**依赖 `this_player()->query("age")` 判定辈分**
  - `query_self_close(ob)`（行 615-651）：亲近自称（如"愚兄我"/"小妹我"），**依赖 `this_player()->query("age")` + `this_player()->query("gender")`**
- [feature/name.c](../../feature/name.c) `short(raw)`（行 99-147）：状态修饰（打坐/鬼气/断线/输入中/发呆/昏迷），`name(raw)` / `id(str)` / `set_name` / `set_color`
- [adm/simul_efun/message.c](../../adm/simul_efun/message.c) `message_vision(msg, me, you)`（行 6-33）：4 变量代词替换（`$N`/`$n`/`$P`/`$p`），分发 me/you/room 三视角
- [adm/simul_efun/gender.c](../../adm/simul_efun/gender.c) `gender_self(sex)` / `gender_pronoun(sex)`：性别代词（self="你"，pronoun=他/她/它）

**专家 3 承重论断 2**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 3）：

> RANK_D 的 query_close/query_self_close 是观察者相对的二元关系函数，依赖 `this_player()`--代词求值不是单实体属性而是 (speaker, viewer, target) 关系。PronounContext 必须携带 viewer。

`rankd.c` 实证：`query_close`/`query_self_close` 中 `this_player()->query("age")` 取**观察者**年龄与 target 年龄比较决定辈分（"弟弟" vs "哥哥"）。greenfield 无全局 `this_player()`（[ADR-0021](ADR-0021-previous-object-explicit-mapping.md) 显式化），viewer 必须显式传参。

**dissent 6 的承重张力**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 6 条 + [15](../xkx-arch/15-阶段2-子系统实施计划.md) §七 dissent 6）：

> previous_object/PronounContext viewer 缺失。阶段 1 T4 已做 viewer/target 显式传参框架（[ADR-0021](ADR-0021-previous-object-explicit-mapping.md) B 类），2.5 完整求值。

**force_me 边界**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 6 条 + §三 Q3 收敛）：

> force_me=PrivilegedAction 是保真让步，边界在 force_me 处妥协。RANK_D 求值不走 force_me，是 System/工具层无状态服务。

本 ADR 落地裁决：**RANK_D 7 函数提取为无状态纯函数**（`rank_service.py`，签名 `(world, viewer, target) -> str`），不走 Command 管线不经 force_me；**PronounContext 三元组完整求值**（speaker/viewer/target -> 10 变量占位符），viewer 从 ActionContext/SystemContext 取；**TitleComp 新增第 14 组件**（玩家称号 + 门派职位 + PKS 称号），可序列化（ADR-0022）；**short() 状态修饰在 TitleSystem 落地**（ADR-0025 后置 2.5 的项在此补）。

**CLAUDE.md 不变量**：

- PronounContext 必须携带 viewer（三元组 speaker/viewer/target，`rankd.c` 实证 `this_player()` 依赖）。
- Command 仅覆盖外部意图（称谓求值是 System/工具层无状态服务，非 Command）。
- CombatKernel 从武侠提取、用非武侠验证（称谓系统无武侠语义，门派职位是 module pack 资产）。
- 新组件可序列化（TitleComp 须可序列化，ADR-0022）。
- 三层粒度 Theme > Module Pack > UGC CPK（门派职位是 module pack，非独立题材）。
- tick=1s + compute<100ms（称谓求值是 O(1) 字典查表，非热路径；预计算+缓存后置性能优化）。

## 决策

### 1. RANK_D 7 函数规格提取（对照 adm/daemons/rankd.c，完整签名 + 不变量）

读 [rankd.c](../../adm/daemons/rankd.c) 全文提取 7 函数。**前 5 函数是单实体属性**（签名 `(ob) -> str`，从 ob 取 gender/class/shen/age/family 等求值），**后 2 函数是观察者相对的二元关系**（`query_close`/`query_self_close`，依赖 `this_player()` 即 viewer）。greenfield 统一为 `(world, viewer, target) -> str` 签名（viewer 对前 5 函数无语义但保持接口一致；System tick 无 viewer 路径见决策 4 回退）。

| LPC 函数 | 行号 | greenfield 接口 | viewer 依赖 | 求值输入（从 target 取） |
|---|---|---|---|---|
| `query_rank(ob)` | 8-320 | `query_rank(world, target) -> str` | 无（单实体） | gender/class/shen/PKS/MKS/wizhood/is_ghost/family/skill(buddhism/lamaism/mahayana/taoism/pixie-jian)/dali/rank |
| `query_respect(ob)` | 322-404 | `query_respect(world, target) -> str` | 无（age 从 target 取） | rank_info/respect（覆盖）/gender/class/age（-SKILL_D("beauty")->reduce_age）/dali/rank/skill(pixie-jian) |
| `query_rude(ob)` | 406-461 | `query_rude(world, target) -> str` | 无 | rank_info/rude（覆盖）/gender/class/age/dali/rank |
| `query_self(ob)` | 463-513 | `query_self(world, target) -> str` | 无 | rank_info/self（覆盖）/gender/class/age/dali/rank |
| `query_self_rude(ob)` | 515-569 | `query_self_rude(world, target) -> str` | 无 | rank_info/self_rude（覆盖）/gender/class/age/dali/rank |
| `query_close(ob)` | 570-613 | `query_close(world, viewer, target) -> str` | **是**（viewer age/gender vs target） | ob.gender/ob.age 或 ob.mud_age + viewer.age/viewer.mud_age；eunach 分支 random(5) |
| `query_self_close(ob)` | 615-651 | `query_self_close(world, viewer, target) -> str` | **是**（viewer gender + age vs target） | viewer.gender + (viewer.mud_age 或 viewer.age) vs (target.mud_age 或 target.age) |

**不变量（从 rankd.c 提取）**：

- **rank_info 覆盖优先**（行 327/411/468/520）：`rank_info/respect`、`rank_info/rude`、`rank_info/self`、`rank_info/self_rude` 四键若 `stringp` 则直接返回，跳过按 gender/class 求值。greenfield 映射 TitleComp.rank_info 字典。
- **age 修正**（行 330/414/471/523）：`age = ob->query("age") - SKILL_D("beauty")->reduce_age(ob)`。beauty 技能减龄，greenfield 映射 `Skills.levels["beauty"]` 经 reduce_age 公式修正（公式后置 2.3 Attribute/Skill，2.5 先接 0）。
- **query_close 辈分判定**（行 574-612）：`a1 = viewer.mud_age || viewer.age`，`a2 = target.mud_age || target.age`；`a1 >= a2` -> viewer 年长（target 是"弟弟"/"妹妹"），否则 viewer 年幼（target 是"哥哥"/"姐姐"）。无 mud_age 时回退 age。
- **query_close 无性分支**（行 597-605）：`class == "eunach"` 时 `random(5)==1` 返回异性称谓（"妹妹"/"姐姐"），否则同性（"弟弟"/"哥哥"）。**含 random，非确定性**（属称谓系统非 combat，不需 DeterministicRNG，用系统 RNG）。
- **query_self_close gender 取自 viewer**（行 630/635）：自称性别跟随说话者（viewer），非 target。这是 viewer 依赖的第二个实证。
- **query_rank PKS 称号**（行 80-82/190-192）：`PKS > 100 && PKS > MKS` -> "土匪"/"土匪婆"。PKS/MKS 是 dbase key（[dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py) POSTPONED_KEYS 未含，本 ADR 新增激活见决策 5）。
- **query_rank 无 this_player() 依赖**：前 5 函数全部从 ob 自身属性求值，无 viewer 依赖。只有 query_close/query_self_close 依赖 viewer（专家 3 承重论断 2 精确范围）。
- **wizhood 优先于一切**（query_rank 行 60-78/170-188）：巫师等级（admin/arch/wizard/...）直接返回对应仙界称谓，跳过 class/shen 分支。greenfield 映射 CapabilityToken.status（WizLevel）。
- **is_ghost 最先**（query_rank 行 19-20）：`is_ghost()` 返回"【鬼魂】"，跳过所有后续分支。greenfield 映射 Marks.flags 含 "ghost" 或 TitleComp.is_ghost。
- **gender 二分支**（query_rank 行 58-319）：`case "女性"` 与 `default`（含男性/无性），女性有独立 class 分支表。

**副作用**：7 函数均为**纯查询无副作用**（无 set/set_temp/tell_object/log_file）。唯一例外是 query_close/query_self_close 的 `random(5)`（无性分支，返回值随机但无状态变更）。

**this_player() 依赖精确范围**（回应专家 3 承重论断 2）：

- query_close（行 574/578/581/586）：`this_player()->query("mud_age")` / `this_player()->query("age")` / `previous_object()->query("age")`（this_player 不存在时回退 previous_object）。
- query_self_close（行 620/624/627/630/633/635）：同上 + `this_player()->query("gender")`。
- **LPC 回退路径**（行 584-588/631-636）：`this_player()` 不存在时用 `previous_object()`。greenfield 无此回退（无全局 this_player/previous_object），viewer 必须显式传参，System tick 无 viewer 路径见决策 4 回退。

**补全层 H 规格提取遗漏**（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §八规格补充建议）：

[spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) 层 H 规格提取覆盖 LOGIN_D/CHAR_D/SECURITY_D/NATURE_D/CHINESE_D，**RANK_D 7 函数未提取**（文件头注释行 4-5 仅列 daemon 名，无 FunctionSpec）。本 ADR 决策 7 产出 RANK_D 7 函数的完整 FunctionSpec（补入 layer_h_daemons.py），含签名/前置/后置/不变量/副作用/this_player 依赖标注。

### 2. PronounContext 三元组完整求值（10 变量占位符）

**10 变量占位符**（[00](../xkx-arch/00-愿景约束与总纲.md) §渲染下沉 + [_archive/01-v2](../xkx-arch/_archive/01-v2-关键修正与避坑清单.md) §P1）：

代词体系是 10 变量（`$N/$n/$P/$p/$C/$c/$R/$r/$S/$s`），其中 4 个是基础代词（[message.c](../../adm/simul_efun/message.c) `message_vision` 实证），6 个由 RANK_D 7 函数求值（v2 扩展设计，服务端预求值下发 PronounContext payload）。

| 占位符 | 大小写 | 语义 | LPC 求值来源 | PronounContext 字段 |
|---|---|---|---|---|
| `$N` | 大写 N | speaker（me）name | `me->name()`（[message.c:14](../../adm/simul_efun/message.c)） | `name_me` |
| `$n` | 小写 n | target（you）name | `you->name()`（[message.c:26](../../adm/simul_efun/message.c)） | `name_you` |
| `$P` | 大写 P | speaker 性别代词（self="你"） | `gender_self(my_gender)`（[message.c:13](../../adm/simul_efun/message.c)） | `pronoun_me` |
| `$p` | 小写 p | target 性别代词（他/她/它） | `gender_pronoun(your_gender)`（[message.c:25](../../adm/simul_efun/message.c)） | `pronoun_you` |
| `$C` | 大写 C | speaker 对 target 的**尊敬称谓** | `RANK_D->query_close(target)`（viewer=speaker） | `close` |
| `$c` | 小写 c | target 对 speaker 的**尊敬称谓** | `RANK_D->query_close(speaker)`（viewer=target，角色互换） | `close_rev` |
| `$R` | 大写 R | speaker 对 target 的**尊敬称谓** | `RANK_D->query_respect(target)` | `respect` |
| `$r` | 小写 r | target 对 speaker 的**尊敬称谓** | `RANK_D->query_respect(speaker)` | `respect_rev` |
| `$S` | 大写 S | speaker 的**自称** | `RANK_D->query_self(speaker)` | `self` |
| `$s` | 小写 s | speaker 的**傲慢自称** | `RANK_D->query_self_rude(speaker)` | `self_rude` |

> 10 变量中 6 个由 RANK_D 求值（`$C/$c/$R/$r/$S/$s`），对应 RANK_D 的 query_close/query_respect/query_self/query_self_rude 4 函数（query_rank/query_rude 未进 10 变量，是 short()/look 场景的等级称谓，非 message_vision 代词）。大小写约定：大写=speaker 视角对 target，小写=target 视角对 speaker（角色互换，viewer 翻转）。

**PronounContext 结构**（[ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 决策 3 + [_archive/01-v2](../xkx-arch/_archive/01-v2-关键修正与避坑清单.md) §P1 行 133）：

```python
@dataclass(frozen=True, slots=True)
class PronounContext:
    """10 变量代词上下文（服务端预求值，下发前端做纯字符串替换）。

    [00] §渲染下沉：服务端求值 PronounContext，前端只做 $X -> context[X] 替换。
    RANK_D 7 函数是业务逻辑求值（依赖年龄/性别/职业/门派/官职/武功/善恶/鬼魂），
    非纯渲染函数（[_archive/01-v2] §P1）。
    """
    # 基础代词（message_vision 4 变量）
    name_me: str          # $N：speaker name
    name_you: str         # $n：target name
    pronoun_me: str       # $P：speaker 性别 self 代词（"你"）
    pronoun_you: str      # $p：target 性别 pronoun（他/她/它）
    # RANK_D 求值代词（6 变量）
    close: str            # $C：speaker 看 target 的亲近称谓（query_close，viewer=speaker）
    close_rev: str        # $c：target 看 speaker 的亲近称谓（query_close，viewer=target）
    respect: str          # $R：speaker 看 target 的尊敬称谓（query_respect）
    respect_rev: str      # $r：target 看 speaker 的尊敬称谓（query_respect，角色互换）
    self: str             # $S：speaker 自称（query_self）
    self_rude: str        # $s：speaker 傲慢自称（query_self_rude）
```

**三元组 speaker/viewer/target 语义**（[ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 决策 2 + [ADR-0021](ADR-0021-previous-object-explicit-mapping.md) B 类）：

- **speaker**（说话者）：事件的发起者，对应 ActionContext.actor。代词 $N/$P/$S/$s 的主体。命令路径下 speaker == actor。
- **viewer**（观察者）：代词求值的观察者，对应 ActionContext.viewer。`query_close`/`query_self_close` 的辈分判定依赖 viewer 年龄。玩家命令路径下 viewer == actor == speaker；PrivilegedAction 路径下 viewer == actor（被代执行者）。
- **target**（被谈论对象）：事件的承受者，对应 ActionContext.target。代词 $n/$p/$C/$c/$R/$r 的主体。kill 的被攻击者、give 的接受者。

**$C/$c 角色互换的 viewer 翻转**（核心求值规则）：

- `$C`（speaker 看 target 亲近称谓）：`query_close(world, viewer=speaker, target=target)` -> speaker 年龄 vs target 年龄 -> "弟弟"/"哥哥"等。
- `$c`（target 看 speaker 亲近称谓）：`query_close(world, viewer=target, target=speaker)` -> target 年龄 vs speaker 年龄 -> 角色互换。
- 这证明了 viewer 是**求值参数非实体属性**：同一对 (speaker, target)，$C 和 $c 的 viewer 不同（前者 speaker，后者 target），产出不同结果。

**PronounService 扩展**（[pronoun.py](../../engine/src/xkx/runtime/pronoun.py) 现状仅 rank_relation + visible）：

现有 PronounService 阶段 1 最小实现（`rank_relation` + `visible`），2.5 扩展为完整 7 函数 + PronounContext 构造：

```python
class PronounService:
    @staticmethod
    def query_rank(world, target) -> str: ...
    @staticmethod
    def query_respect(world, target) -> str: ...
    @staticmethod
    def query_rude(world, target) -> str: ...
    @staticmethod
    def query_self(world, target) -> str: ...
    @staticmethod
    def query_self_rude(world, target) -> str: ...
    @staticmethod
    def query_close(world, viewer, target) -> str: ...
    @staticmethod
    def query_self_close(world, viewer, target) -> str: ...

    @staticmethod
    def build_context(world, speaker, target) -> PronounContext:
        """构造 10 变量 PronounContext（speaker/target 二元，viewer 内部翻转）。

        $C/$c 角色互换：query_close(viewer=speaker, target=target) +
        query_close(viewer=target, target=speaker)。
        """
        ...

    @staticmethod
    def render(template: str, ctx: PronounContext) -> str:
        """$X -> ctx 字段纯字符串替换（前端渲染等价，服务端也可用）。

        对齐 message_vision 的 replace_string 语义，但扩展到 10 变量。
        """
        ...
```

**可见性不变量**（[spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) `_visible`）：`visible(viewer, target)` 三级判定（巫师等级 > invisibility > 鬼魂）阶段 1 最小实现仅判 Identity 存在，2.5 补 invisibility + ghost（若 2.6 阴间先行则衔接 is_ghost 标记）。PronounContext 求值前先过 visible 门控：viewer 看不到 target 时，$n/$p/$C/$c 退化为基础代词（避免泄露隐身目标信息）。

### 3. TitleComp 组件（玩家称号 + 门派职位 + PKS 称号）

新增第 14 组件 TitleComp（[ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) 13 组件之后），承载 rankd.c 求值所需的全部 dbase key，可序列化（ADR-0022）。

```python
@dataclass
class TitleComp:
    """称谓组件（阶段 2.5，ADR-0028）。

    承载 RANK_D 7 函数求值所需的 dbase key：title/nickname/shen（玩家称号）+
    rank_info 四键（rankd 覆盖优先）+ PKS/MKS（PKS 称号）+ class/dali/rank
    （门派职位/官职）+ is_ghost（鬼魂状态）。

    对照 LPC set("title"/"nickname"/"shen"/"rank_info/*"/"PKS"/"MKS"/"class")
    dbase key（[dbase_map.py] POSTPONED_KEYS，2.5 激活）。
    """
    # 玩家称号（LPC set("title")/set("nickname")/set("shen")）
    title: str = ""           # LPC "title"：头衔（如"普通百姓"/"华山派弟子"）
    nickname: str = ""        # LPC "nickname"：绰号（如「老顽童」）
    shen: int = 0             # LPC "shen"：道德值（正=侠，负=魔，rankd 按阈值分级）

    # rank_info 覆盖（LPC set("rank_info/respect|rude|self|self_rude")）
    # rankd.c 行 327/411/468/520：stringp 时直接返回，跳过 gender/class 求值
    rank_info_respect: str | None = None
    rank_info_rude: str | None = None
    rank_info_self: str | None = None
    rank_info_self_rude: str | None = None

    # PKS 称号（LPC "PKS"/"MKS"，09 §五法院系统）
    pks: int = 0              # 玩家击杀数（PKS>100 且 PKS>MKS -> "土匪"/"土匪婆"）
    mks: int = 0              # 怪物击杀数（对照用）

    # 门派职位/官职（LPC "class"/"dali/rank"/"rank"）
    char_class: str = ""      # LPC "class"：职业（bonze/taoist/beggar/eunach/swordsman/...）
    dali_rank: int = 0        # LPC "dali/rank"：大理官职（1-5，5=王爷/王妃）
    family_rank: int = 0      # LPC "rank"：丐帮袋数（rankd 行 28/130-145/280-295）

    # 鬼魂状态（LPC is_ghost()，rankd 行 19 最先判定）
    is_ghost: bool = False
```

**字段命名避坑**：`class` 是 Python 保留字，字段名用 `char_class`（对照 [components.py](../../engine/src/xkx/runtime/components.py) `Attributes.str_` 同样避 Python 保留字模式）。dbase key `"class"` 仍映射到 `TitleComp.char_class`（DBASE_KEY_MAP 条目）。

**可序列化**（ADR-0022）：字段全基本类型（str/int/bool/None），`serialization.py` 按 `dataclasses.fields` 提取，无需额外适配。存档含 TitleComp 后，rankd 求值在崩溃恢复后可重现（无随机性依赖，query_close 的 random(5) 是运行时随机非持久态）。

**门派职位是 module pack 资产**（CLAUDE.md 三层粒度）：TitleComp 承载**数据**（family_rank/dali_rank/char_class），但"丐帮 9 袋 = 神丐"的**映射规则**是武侠题材包资产（rankd.c 行 130-145 的 if-else 分支），不进核心引擎。greenfield 分离：TitleComp（核心引擎数据组件）+ rank_service 求值函数（核心引擎纯函数，但 class 分支表数据从题材包加载）。详见决策 6 主题无关性。

**不新增 dbase key 到 POSTPONED_KEYS 之外**：title/nickname/shen 已在 POSTPONED_KEYS（[dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py) 行 107），PKS/MKS/class/rank/dali/rank 未在 POSTPONED_KEYS（层 H 规格未覆盖），本 ADR 决策 5 新增激活。

### 4. System tick 无 viewer 回退（04 §七避坑 5）

[04](../xkx-arch/04-迁移路径与避坑清单.md) §七避坑 5："PronounContext 必须携带 viewer（`rankd.c` 实证 `this_player()` 依赖），单机下 `this_player()` 映射 `ActionContext.actor` 需在 System tick 无'当前说话者'时定义回退。"

LPC `rankd.c` 的回退路径（行 584-588/631-636）：`this_player()` 不存在时用 `previous_object()`。greenfield 无全局 this_player/previous_object，需显式定义 System tick 路径的 viewer 回退。

**三类调用路径的 viewer 取值**：

| 路径 | speaker | viewer | target | 场景 |
|---|---|---|---|---|
| Command 路径 | ActionContext.actor | ActionContext.viewer（== actor 玩家路径） | ActionContext.target | 玩家命令（say/emote/give）触发的代词求值 |
| PrivilegedAction 路径 | ActionContext.actor（被代执行者） | ActionContext.viewer（== actor） | ActionContext.target | force_me 代执行（[ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 决策 4） |
| System tick 路径 | SystemContext.actor | **SystemContext.actor**（回退=speaker 自身） | SystemContext.target | heart_beat/combat do_attack/heal 触发的消息（如战斗招式文本 `$N一招...攻向$n`） |

**System tick 回退规则**：System tick 路径无"当前说话者"（无 ActionContext），viewer 回退为 speaker 自身（`viewer == speaker`）。语义：System 产生的消息（如 combat 招式文本）speaker 是行动者，viewer 也是行动者自身（行动者看自己 vs target 的辈分关系）。这与 LPC `previous_object()` 回退不等价（LPC 回退到调用者对象，greenfield 回退到 speaker 自身），但语义合理：System 消息的"观察者"就是消息主体自身。

**不变量**：

- PronounContext 求值必须从 ActionContext/SystemContext 取 viewer，不得从全局 `this_player()` 取（[ADR-0021](ADR-0021-previous-object-explicit-mapping.md) B 类，greenfield 无全局 this_player）。
- System tick 路径 viewer == speaker（回退规则），PronounService.build_context(world, speaker, target) 内部对 $C/$c 仍翻转 viewer（$C viewer=speaker，$c viewer=target），不因 System 路径而退化。
- combat 招式文本（CombatState.action_message 如 `"$N一招「试探」，攻向$n$l"`）的 $N/$n 由 PronounContext 求值，viewer = attacker（speaker）。$l 是部位占位符（非代词，combat 管线求值，[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)）。

**性能**（[00](../xkx-arch/00-愿景约束与总纲.md) §渲染下沉 + [_archive/01-v2](../xkx-arch/_archive/01-v2-关键修正与避坑清单.md) §P1 性能疑虑）：RANK_D 7 函数是 O(1) 字典查表 + if-else 分支，单次求值 <0.1ms。combat 每 tick 多条消息（招式 + 伤害 + miss），每条消息 build_context 一次。1000 实体 * 10 消息/tick = 10000 次求值/tick，<1ms 总耗时，非热路径（CombatSystem 占 92%，[ADR-0025](ADR-0025-query-index-layer.md) 决策 3 性能分析）。预计算+缓存后置（若 profiler 显示瓶颈，缓存 PronounContext per (speaker, target) 对，dirty flag 在 TitleComp 变更时失效）。

### 5. 后置 key 激活（title/nickname/shen + PKS/MKS/class/rank，对齐 ADR-0025 §5）

对照 [ADR-0025](ADR-0025-query-index-layer.md) 决策 5 后置 key 激活策略，2.5 激活以下 key 到 DBASE_KEY_MAP（从 POSTPONED_KEYS 移除）：

| key | 映射目标 | 激活时机 | rankd 用途 |
|---|---|---|---|
| `title` | TitleComp.title | 2.5 | short() 称号前缀（[name.c:132](../../feature/name.c)） |
| `nickname` | TitleComp.nickname | 2.5 | short() 绰号前缀（[name.c:129](../../feature/name.c)） |
| `shen` | TitleComp.shen | 2.5 | query_rank 善恶分级（行 147-166/297-316） |
| `PKS` | TitleComp.pks | 2.5（新增） | query_rank PKS 称号（行 80/190） |
| `MKS` | TitleComp.mks | 2.5（新增） | query_rank PKS>MKS 判定（行 81/191） |
| `class` | TitleComp.char_class | 2.5（新增） | query_rank/query_respect 等的 class 分支 |
| `rank` | TitleComp.family_rank | 2.5（新增） | 丐帮袋数（行 28/130-145/280-295） |

**路径前缀新增**：

| 前缀 | 映射目标 | 用途 |
|---|---|---|
| `rank_info` | TitleComp（四字段分发） | rankd 覆盖优先（respect/rude/self/self_rude） |
| `dali` | TitleComp.dali_rank（`dali/rank`） | 大理官职（行 40-41/115-120/263-270/343-352） |

**激活协议**（[ADR-0025](ADR-0025-query-index-layer.md) 决策 5）：2.5 实现时在 DBASE_KEY_MAP 加条目，`validate_dbase_map` 启动期校验 TitleComp 字段存在。`rank_info/respect` 等路径前缀需扩展 `resolve_dbase_key` 支持 TitleComp 四字段分发（PATH_PREFIX_MAP 加 `rank_info` -> TitleComp 分发逻辑）。

**未激活的后置 key**（2.5 不动，后置 2.6/M3）：

- `vendetta`/`vendetta_mark`/`pking`/`pktime`（法院系统，2.6，[09](../xkx-arch/09-灵魂系统盘点.md) §五）
- `mud_age`/`age_modify`/`month`/`birthday`（时间系统，2.5 用 Attributes.age，完整 mud_age 后置 M3 时间系统）
- `death_count`/`death_times`/`my_killer`（死亡轮回，2.2）

### 6. short() 状态修饰落地（ADR-0025 后置 2.5 的项）

[ADR-0025](ADR-0025-query-index-layer.md) §简化台账第 6 项：`short()` 状态修饰（打坐/鬼气/断线/昏迷）后置 2.5 TitleSystem。本 ADR 落地。

对照 [feature/name.c](../../feature/name.c) `short(raw)`（行 99-147）提取状态修饰规则：

**short() 完整格式**（[name.c:99-147](../../feature/name.c)）：

```
short = colorname || name(raw)            # 基础名（colorname 优先）
short = short_key || name(id)             # LPC "short" key 覆盖（行 106-107）
# 非角色对象（!is_character）直接返回 short
# raw=0 时状态修饰：
if pending/exercise:   return name + "正坐在地下修炼内力。"    # 行 112-113
if pending/respirate:  return name + "正坐在地下吐纳炼精。"    # 行 114-115
if pending/jingzuo:    return name + "正在蒲团上盘膝静坐。"    # 行 116-117
# apply/short 掩码（行 120-121，后置，无 apply 机制）
# title/nickname 前缀（行 129-133）：
if nickname: short = "「{nickname}」" + short
if title:    short = "{title}" + (" " if no nick else "") + short
# raw=0 时尾部状态标记（行 136-144）：
if is_ghost:      short = "(鬼气) " + short
if netdead:       short += " <断线中>"
if in_input:      short += " <输入文字中>"
if in_edit:       short += " <编辑档案中>"
if interactive && idle>120: short += " <发呆中>"
if !living:       short += disable_type                  # 昏迷/ disable
```

**greenfield short() 实现**（扩展 [query.py](../../engine/src/xkx/runtime/query.py) `short(identity)` 为 `short(world, eid, *, raw=False)`）：

| LPC 状态 | greenfield 数据源 | 实现时机 |
|---|---|---|
| `pending/exercise`/`respirate`/`jingzuo` | Marks.flags 含 "pending/exercise" 等 | 2.5（Marks 已有） |
| `is_ghost` | TitleComp.is_ghost | 2.5 |
| `netdead` | Marks.flags 含 "netdead"（[dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py) POSTPONED_KEYS 行 114） | 2.5 |
| `in_input`/`in_edit` | 连接状态（T7 WS 服务器，后置） | M3（消息/编辑系统） |
| `idle > 120` | 连接 idle 时间（T7 WS） | M3 |
| `!living`/`disable_type` | Marks.flags 含 "disabled" + disable_type | 2.5（condition 系统，2.2 衔接） |
| `title`/`nickname` 前缀 | TitleComp.title/nickname | 2.5 |
| `colorname`/`apply/short` | colorname 后置（无 ANSI 颜色内核化），apply 后置 | M3 |

**raw 参数语义**（[name.c:78-90](../../feature/name.c) `name(raw)` + 行 99 `short(raw)`）：`raw=1` 跳过所有状态修饰和 apply 掩码，返回基础名。greenfield `short(world, eid, raw=True)` 仅返回 `name(id)` 格式（对齐 [ADR-0025](ADR-0025-query-index-layer.md) 决策 4 基础格式），`raw=False` 加状态修饰。

**不变量**：

- `short(raw=True)` 必须无副作用无状态依赖（纯函数，用于 look 命令目标匹配等）。
- `short(raw=False)` 的状态修饰顺序严格对齐 [name.c](../../feature/name.c)：打坐/吐纳/静坐（提前 return）-> title/nick 前缀 -> 鬼气前缀 -> 断线/输入/发呆/昏迷尾部标记。
- 战斗中 `!living`（disable_type）的 short 修饰与 combat 管线交织（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) 副作用账本），short() 调用时机在 combat 文本产出之前。

### 7. RANK_D 7 函数 FunctionSpec 补入层 H 规格

补全 [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) 遗漏的 RANK_D 7 函数 FunctionSpec（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §八规格补充建议）。每函数含：

- **签名**：`query_rank(ob)` / `query_respect(ob)` / `query_rude(ob)` / `query_self(ob)` / `query_self_rude(ob)` / `query_close(ob)` / `query_self_close(ob)`，返回 `string`。
- **前置条件**：`objectp(ob)`（target 有效）；query_close/query_self_close 额外 `objectp(this_player()) || objectp(previous_object())`（viewer 回退路径）。
- **后置条件**：返回称谓字符串（非空）；rank_info 覆盖优先；is_ghost 最先（query_rank）；wizhood 优先于 class/shen（query_rank）。
- **不变量**：
  - query_close/query_self_close 是观察者相对的二元关系函数（专家 3 承重论断 2），依赖 `this_player()->query("age")`。
  - rank_info 四键覆盖优先（行 327/411/468/520）。
  - query_rank PKS>100 且 PKS>MKS -> "土匪"/"土匪婆"（行 80-82/190-192）。
  - age 经 `SKILL_D("beauty")->reduce_age(ob)` 修正（行 330/414/471/523）。
- **副作用**：7 函数均无状态变更副作用（纯查询）。query_close 无性分支 `random(5)` 是返回值随机非状态变更。
- **this_player() 依赖标注**：query_close（行 574/578/581/586）、query_self_close（行 620/624/627/630/633/635）显式标注 `this_player()` 依赖 + `previous_object()` 回退。
- **random_specs**：query_close 无性分支 `random(5)==1`（系统 RNG，非 DeterministicRNG，称谓系统非 combat）。

**规格补入位置**：[spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py) 文件头注释行 4-5 补 RANK_D 7 函数描述 + LAYER_SPEC.function_specs 补 7 个 FunctionSpec。本 ADR 不写完整 FunctionSpec 代码（编码阶段产出），只定规格契约。

## 简化台账（与 LPC rankd.c / name.c 的差异）

| # | LPC 语义 | greenfield 实现 | 后置时机 | 关联 |
|---|---|---|---|---|
| 1 | `SKILL_D("beauty")->reduce_age(ob)` | 2.5 接 0（不减龄），2.3 接真实公式 | 2.3 Attribute/Skill | [rankd.c:330](../../adm/daemons/rankd.c) |
| 2 | `wizhood(ob)` 巫师称谓表（9 级 * 2 性别 = 18 项） | 完整实现（query_rank 行 60-78/170-188） | 本任务 | [rankd.c:60](../../adm/daemons/rankd.c) |
| 3 | `query_rank` class 分支表（bonze/taoist/beggar/eunach/...） | 完整实现（数据从题材包加载，决策 6） | 本任务 | [rankd.c:85-318](../../adm/daemons/rankd.c) |
| 4 | `query_rank` shen 阈值分级（1000000/100000/10000/1000/-100...） | 完整实现 | 本任务 | [rankd.c:147-166/297-316](../../adm/daemons/rankd.c) |
| 5 | `query_close` 无性分支 `random(5)` | 完整实现（系统 RNG，非 DeterministicRNG） | 本任务 | [rankd.c:600-604](../../adm/daemons/rankd.c) |
| 6 | `previous_object()` 回退（this_player 不存在时） | 不实现（greenfield 无 previous_object，System tick 回退 speaker 自身，决策 4） | 砍掉 | [rankd.c:586/633](../../adm/daemons/rankd.c) |
| 7 | `short()` colorname / `apply/short` 掩码 | 不实现（无 ANSI 颜色内核化，无 apply 机制） | M3 | [name.c:103/120](../../feature/name.c) |
| 8 | `short()` `in_input`/`in_edit`/`idle>120` 状态 | 后置（依赖连接状态，T7 WS） | M3 | [name.c:139-142](../../feature/name.c) |
| 9 | `message_vision` 3 视角分发（me/you/room） | 后置（消息系统，2.5 只产 PronounContext payload） | M3 消息系统 | [message.c:24-32](../../adm/simul_efun/message.c) |
| 10 | emote 7 视角（myself/others/target/...） | 不实现（后置 M3 emote 系统） | M3 | [_archive/01-v2](../xkx-arch/_archive/01-v2-关键修正与避坑清单.md) §P2 |
| 11 | `rank_info` 四键 `set("rank_info/respect", ...)` 动态编辑 | TitleComp 字段承载，编辑器后置 | M3（动态编辑） | [rankd.c:327](../../adm/daemons/rankd.c) |
| 12 | 频道称谓过滤（chblk 等场景的称谓替换） | 不实现 | M3 频道系统 | [15](../xkx-arch/15-阶段2-子系统实施计划.md) §不做 |
| 13 | `set_color` ANSI 颜色 | 不实现（渲染下沉前端，[00] §渲染下沉） | 砍掉 | [name.c:18-42](../../feature/name.c) |
| 14 | `intermud_name`（跨服名 `name(id@mud)`） | 不实现（intermud 砍，[ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 决策 4） | 砍掉 | [name.c:92-97](../../feature/name.c) |

> 简化台账与 [ADR-0002](ADR-0002-resolve-attack-extraction.md) / [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) / [ADR-0025](ADR-0025-query-index-layer.md) §简化台账模式一致。砍掉项 = greenfield 不实现（LPC 特有机制或后置 M3）；后置项 = 对应子系统实现时补。

## 代码结构

### 新建 `engine/src/xkx/runtime/title.py`

```python
# RANK_D 7 函数（无状态纯函数，对齐 rankd.c）
def query_rank(world, target) -> str: ...
def query_respect(world, target) -> str: ...
def query_rude(world, target) -> str: ...
def query_self(world, target) -> str: ...
def query_self_rude(world, target) -> str: ...
def query_close(world, viewer, target) -> str: ...
def query_self_close(world, viewer, target) -> str: ...

# short() 状态修饰（扩展 query.py.short）
def short(world, eid, *, raw: bool = False) -> str: ...
```

### 扩展 `engine/src/xkx/runtime/pronoun.py`

- `PronounContext` frozen dataclass（10 字段，决策 2）。
- `PronounService` 扩展 7 函数 + `build_context(world, speaker, target)` + `render(template, ctx)`。
- 现有 `rank_relation` / `visible` 保留（阶段 1 最小实现，2.5 补完整）。

### 扩展 `engine/src/xkx/runtime/components.py`

- 新增 `TitleComp`（第 14 组件，决策 3）。
- `serialization.py` 自动覆盖（dataclass 字段提取，ADR-0022）。

### 扩展 `engine/src/xkx/runtime/dbase_map.py`

- DBASE_KEY_MAP 新增 7 条：`title`/`nickname`/`shen`/`PKS`/`MKS`/`class`/`rank` -> TitleComp 字段。
- PATH_PREFIX_MAP 新增 2 条：`rank_info` -> TitleComp 四字段分发，`dali` -> TitleComp.dali_rank。
- POSTPONED_KEYS 移除 `title`/`shen`（nickname 未在 POSTPONED_KEYS，新增激活）。

### 扩展 `engine/src/xkx/spec/layer_h_daemons.py`

- 补 RANK_D 7 函数 FunctionSpec（决策 7）。
- 文件头注释补 RANK_D 描述。
- LAYER_SPEC.function_specs 补 7 个 spec。

### 测试 `engine/tests/test_title.py`

- RANK_D 7 函数行为等价（对照 rankd.c 典型 case：男/女 * bonze/taoist/beggar/eunach * 各 shen 阈值 * 各 age 段）。
- PronounContext 10 变量求值（$C/$c 角色互换 viewer 翻转）。
- TitleComp 序列化往返（ADR-0022）。
- short() 状态修饰（打坐/鬼气/断线/昏迷/raw 参数）。
- PKS 称号（PKS>100 且 PKS>MKS -> "土匪"/"土匪婆"）。
- hypothesis 属性测试：rank_info 覆盖优先不变量 + query_close 辈分判定（viewer age vs target age 边界）+ is_ghost 最先（query_rank 短路）。
- 现有 1101 tests 不回归。

## 简化台账（汇总）

见上方"简化台账（与 LPC rankd.c / name.c 的差异）"表 14 项。

## 验收标准（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.5）

- [ ] RANK_D 7 函数行为等价（对照 rankd.c 典型 case，含 gender/class/shen/PKS/age/wizhood/ghost 全分支）
- [ ] PronounContext 三元组求值与 LPC `this_player()` 依赖一致（$C/$c 角色互换 viewer 翻转）
- [ ] 10 变量占位符完整求值（$N/$n/$P/$p/$C/$c/$R/$r/$S/$s）
- [ ] TitleComp 组件可序列化（ADR-0022 往返）
- [ ] short() 状态修饰（打坐/鬼气/断线/昏迷 + title/nickname 前缀 + raw 参数）
- [ ] PKS 称号（PKS>100 且 PKS>MKS -> "土匪"/"土匪婆"）
- [ ] 后置 key 激活（title/nickname/shen/PKS/MKS/class/rank + rank_info/dali 路径前缀）
- [ ] System tick 无 viewer 回退（viewer == speaker，决策 4）
- [ ] RANK_D 7 函数 FunctionSpec 补入 layer_h_daemons.py
- [ ] hypothesis 属性测试（rank_info 覆盖 + query_close 辈分 + is_ghost 短路）
- [ ] 现有 1101 tests 不回归
- [ ] ruff 全过（行长 100，中文按字符数计）
- [ ] test_theme_neutrality 硬门禁持续通过（称谓求值纯函数无武侠烙印，class 分支表数据从题材包加载）

## 关联 dissent

| dissent | 本 ADR 应对 |
|---|---|
| **6（previous_object/PronounContext viewer 缺失）**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 6 条 + [15](../xkx-arch/15-阶段2-子系统实施计划.md) §七） | PronounContext 三元组完整求值（决策 2），viewer 从 ActionContext/SystemContext 显式取，query_close/query_self_close 签名 `(world, viewer, target)`；System tick 无 viewer 回退 speaker 自身（决策 4，04 §七避坑 5） |
| **force_me 边界侵蚀**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 6 条 + §三 Q3 收敛） | RANK_D 求值不走 force_me，是 System/工具层无状态纯函数（决策 1），不经 8 段管线；称谓求值非 Command（CLAUDE.md "Command 仅覆盖外部意图"） |
| **层1 原语蠕变**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 3 条） | 称谓求值不落入层1 DSL（决策 1），是 Python 纯函数 rank_service；rank_info 覆盖是数据非规则，class 分支表是题材包数据非层1 谓词 |
| **专家 3 承重论断 2**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §二专家 3） | RANK_D query_close/query_self_close 是观察者相对的二元关系函数，精确标注 viewer 依赖范围（仅后 2 函数，前 5 函数无 viewer 依赖）；$C/$c 角色互换 viewer 翻转实证（决策 2） |
| **8（存储语义，新组件可序列化）**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 8 条） | TitleComp 字段全基本类型，serialization.py 自动覆盖（决策 3），崩溃恢复后 rankd 求值可重现 |

## 不做（范围边界）

- **不实现代码**（本 ADR 是设计文档，编码是第二波 2.5 agent 的任务）。
- **不做完整 emote 7 视角系统**（后置 M3，[15](../xkx-arch/15-阶段2-子系统实施计划.md) §不做）：2.5 只产 PronounContext payload，emote 7 视角变体（myself/others/target/...）后置 M3 emote 系统。
- **不做动态称谓编辑器**（后置 M3）：rank_info 四键由 TitleComp 承载，但玩家/巫师动态编辑界面后置。
- **不做频道称谓过滤**（后置 M3 频道系统）：chblk 等场景的称谓替换后置。
- **不重新设计 ActionContext 三元组**（[ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 已定）：2.5 只完整求值 PronounContext，不改 ActionContext 结构。
- **不实现 colorname / apply/short 掩码**（砍掉，[name.c:103/120](../../feature/name.c)）：无 ANSI 颜色内核化（渲染下沉前端，[00](../xkx-arch/00-愿景约束与总纲.md) §渲染下沉），无 apply 机制（LPC 特有）。
- **不实现 message_vision 3 视角分发**（后置 M3 消息系统）：2.5 只产 PronounContext payload，消息分发后置。
- **不实现 intermud_name**（砍掉，[ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 决策 4）：intermud 砍。
- **不实现 beauty reduce_age 真实公式**（后置 2.3）：2.5 接 0，2.3 Attribute/Skill 接真实公式。
- **不实现 in_input/in_edit/idle 状态修饰**（后置 M3）：依赖连接状态（T7 WS），2.5 只做 Marks/TitleComp 可承接的状态。
- **不修改 LPC 源**（只读规格）。
- **不预计算+缓存 PronounContext**（后置性能优化）：O(1) 查表非热路径，profiler 显示瓶颈再缓存。

## 开放问题（需 lead 裁决）

1. **TitleComp 与 Attributes.family 的边界**：`Attributes.family`（[components.py:33](../../engine/src/xkx/runtime/components.py)）已承载门派名（LPC `family/family_name`），但 rankd.c 行 24-35 按 `family/family_name` 分派技能（buddhism/lamaism/mahayana）。TitleComp 是否承载 family，还是 rank_service 从 Attributes.family 读？**建议**：rank_service 从 Attributes.family 读（family 是 Attributes 既有字段，TitleComp 不重复），TitleComp 只承载 rankd.c 求值所需的 title/nickname/shen/rank_info/PKS/MKS/class/rank/dali/is_ghost。需 lead 确认。

2. **class 分支表数据归属**：rankd.c 的 class -> 称谓映射表（bonze/taoist/beggar/eunach 等，行 85-318）是武侠题材数据还是核心引擎？按 CLAUDE.md 三层粒度，门派职位是 module pack，但 class（职业）跨越武侠（bonze 喇嘛）与通用（scholar/officer）。**裁决（2026-07-12 lead）**：class 分支表数据从题材包加载（决策选项 A），核心引擎 rank_service 不硬编码"bonze"等武侠字面量，符合 test_theme_neutrality 硬门禁。核心引擎只提供查表框架（`CLASS_TITLE_TABLE: dict[str, dict[str, str]]` 由题材包注册填充），rank_service 按 `char_class` 查表。代价：核心引擎无法独立测试 class 称谓，测试用注入的测试用表（非武侠 class 如 scholar/officer 或占位）。

3. **query_close random(5) 的确定性**：无性分支 `random(5)==1` 返回异性称谓，用系统 RNG。combat 文本若含 $C（如 emote 场景），此随机性会使文本不可重放。**建议**：2.5 用系统 RNG（称谓系统非 combat，不进 DeterministicRNG），若 M3 全仿真确定性扩展到称谓时再收口。需 lead 确认是否接受此非确定性。

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 6（previous_object/PronounContext viewer 缺失）+ §二专家 3 承重论断 2（RANK_D query_close 观察者相对二元关系）+ §三 Q3 force_me 收敛
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 2 M2-5（TitleSystem）+ §七避坑 5（PronounContext viewer，System tick 回退）
- [15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.5 任务卡 + §五 ADR 表 + §七 dissent 6 映射 + §八规格补充（rankd PKS 称号）
- [ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 决策 2（ActionContext 三元组 actor/source/viewer/target + PronounContext viewer 不变量）
- [ADR-0021](ADR-0021-previous-object-explicit-mapping.md) B 类（PronounContext viewer 显式传参，155 处映射）
- [ADR-0025](ADR-0025-query-index-layer.md) 决策 5（后置 key 激活策略，2.5 激活 title/nickname/shen）+ §简化台账第 6 项（short 状态修饰后置 2.5）
- [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)（TitleComp 可序列化）
- [ADR-0014](ADR-0014-daemon-responsibility-redesign.md) 决策 3（rankd -> PronounContext 三元组，viewer 不变量实证）
- [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（13 组件，TitleComp 新增第 14）
- [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)（combat 招式文本 $N/$n 与 PronounContext 衔接）
- [spec/layer_h_daemons.py](../../engine/src/xkx/spec/layer_h_daemons.py)（RANK_D 规格补入，决策 7）
- [spec/layer_i_character.py](../../engine/src/xkx/spec/layer_i_character.py) `_visible`（viewer/target 语义，PronounContext 不变量实证）
- [runtime/pronoun.py](../../engine/src/xkx/runtime/pronoun.py)（PronounService 现状，2.5 扩展）
- [runtime/action_context.py](../../engine/src/xkx/runtime/action_context.py)（ActionContext.viewer 字段）
- [runtime/components.py](../../engine/src/xkx/runtime/components.py)（TitleComp 新增）
- [runtime/dbase_map.py](../../engine/src/xkx/runtime/dbase_map.py)（后置 key 激活，决策 5）
- [adm/daemons/rankd.c](../../adm/daemons/rankd.c)（RANK_D 7 函数 LPC 规格源）
- [feature/name.c](../../feature/name.c)（short() 状态修饰 LPC 规格源）
- [adm/simul_efun/message.c](../../adm/simul_efun/message.c)（message_vision 4 变量代词）
- [adm/simul_efun/gender.c](../../adm/simul_efun/gender.c)（gender_self/gender_pronoun）
- [09](../xkx-arch/09-灵魂系统盘点.md) §五（法院系统 PKS/killer 四区域，TitleComp.pks/mks 来源）

*最后更新：2026-07-12*
