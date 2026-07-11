# inherit_char_char 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/inherit/char/char.c
- basename: inherit_char_char
- 引擎侧/内容侧: 引擎侧（角色基类，heart_beat 七步管线核心）
- 总语义单元数: 6
- 各层计数: 层0=1  层1=0  层2=0  层3=5
- 层3 项: 5 项（见下表理由）

## 语义单元标注

| 语义单元 | 层 | 引擎侧/内容侧 | 理由 |
|---|---|---|---|
| inherit 声明（17 个 feature 模块聚合） | 层0 | 引擎侧 | 纯声明：角色基类组合 F_ACTION/F_ATTACK/F_DAMAGE/... 等 feature |
| create() seteuid(0) | 层3 | 引擎侧 | 生命周期初始化，允许 LOGIN_D 导出 uid，过程逻辑 |
| is_character() 返回 1 | 层3 | 引擎侧 | 引擎平台类型标识接口，属 ECS System 层 |
| setup() | 层3 | 引擎侧 | create->运行阶段转换点：seteuid+set_heart_beat(1)+tick初始化+enable_player+CHAR_D->setup_char，多步副作用交织 |
| heart_beat() 七步管线 | 层3 | 引擎侧 | 核心循环：频道清理/属性封顶/濒死/昏迷/战斗/chat/tick衰减，七步顺序不可重排，chat 可 destruct，tick=5+random(10) 非均匀 |
| visible(ob) | 层3 | 引擎侧 | wizard 等级比较 + invisibility + ghost/astral_vision 多分支，过程逻辑 |

## 备注

- heart_beat 是 NPC AI 的核心驱动循环（已有规格见 layer_g_npc_ai.py），七步管线是架构不变量。
- CLAUDE.md 架构不变量：tick=1s + compute<100ms + 非均匀 tick（LPC heart_beat 实测 set_heart_beat(1)）。
- 七步顺序不可重排：channel -> attr_cap -> mortal -> unconscious -> combat -> chat -> tick_decay。
- 步骤 6 chat() 可能 destruct(this_object())，后续代码必须检查 this_object() 存在性。
- 步骤 7 tick 衰减：tick=5+random(10) 的非均匀周期降频执行 update_condition/heal_up，节省 CPU。
- inherit 声明本身是层0，但所继承的 17 个 feature 模块的逻辑分别在各自文件中标注（feature/attack.c、feature/damage.c 等）。
- 新引擎预期：heart_beat 演变为 ECS System 的 tick 驱动 System，Python 原生实现，语义上属层3。
