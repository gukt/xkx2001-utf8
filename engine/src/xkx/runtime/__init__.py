"""运行时子系统：最小 ECS + 组件 + 场景加载。

S1：dict 存储 ECS（SparseSet 后置，01 子系统3）。加载层0 IR -> 构建实体。
命令管线（go/kill）见 ``commands.py``（S1-5）。
"""
