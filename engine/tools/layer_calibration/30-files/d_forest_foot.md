# d_forest_foot 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/d/forest/foot.c
- basename: d_forest_foot
- 总语义单元数: 6
- 各层计数: 层0=5  层1=1  层2=0  层3=0
- 层3 项: 无

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set("short","山脚") | 层0 | 纯数据声明 |
| create() set("long", @LONG@) | 层0 | 纯数据声明 |
| create() set("exits", mapping) | 层0 | 纯数据声明，east/up 出口 |
| create() set("item_desc", lian) | 层0 | 纯数据声明，铁链描述（已断） |
| create() set("outdoors","city")+set("cost",1)+setup() | 层0 | 纯数据声明；无 replace_program 但也无其他自定义钩子（仅 valid_leave） |
| valid_leave(me,dir) dir==up 分支 | 层1 | condition->deny 形态：NOT(is_wizard) -> deny。单条件单动作，无副作用无状态机，形态完全符合层1。当前谓词集无 is_wizard 叶子，需扩展（对应 LPC wizardp()） |

## 备注

- 本文件是层1 的最简形态：单条件->deny，无副作用。唯一缺口是谓词集缺 `is_wizard`（wizardp 权限判断）。
- `wizardp(me)` 是管理员权限判断，非角色属性，建议作为层1 叶子谓词 `is_wizard` 独立扩展（与 family_eq/has_flag 同级），而非塞进 has_flag。多处房间用 wizardp 做权限门禁（如 bwdh/kantai valid_leave 的 up 分支也用 wizardp）。
- 其他方向无自定义规则，走默认放行。
- `item_desc` lian 描述"铁链已断"是纯静态文案，暗示原本可能有 climb 铁链的交互但已被移除，本文件无对应命令钩子。
