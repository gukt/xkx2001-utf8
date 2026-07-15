"""daemon 数据对象（ADR-0057）。

各 LPC F_SAVE 单例数据对象的 greenfield 建模，各自一文件：

- ``bboard``：留言板（bboard.c dbase：board_id/notes/wizard_only/poster_family）
- ``job_data``：门派任务/贡献度统计（二进制 .sav 无法提取，留 Protocol 占位）

每个 daemon 实现 ``DaemonSerializable``（``to_dict``/``from_dict``），由
``DaemonStore`` register/save/restore_all。
"""
