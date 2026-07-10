"""DSL 子系统：四层 -> JSON IR（唯一真相源）。

S1 实现：层0（RoomDef/NpcDef YAML 声明式数据）+ 层1（EventRule 事件规则）。
层2（Ink 对话树）/ 层3（RestrictedPython 沙箱）后置。

层1 是唯一规则表示层（02 Q2 裁决），薄求值子模块不命名"引擎"、不建独立框架。
"""
