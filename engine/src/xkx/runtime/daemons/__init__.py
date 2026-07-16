"""daemon 数据对象（ADR-0057）。

各 LPC F_SAVE 单例数据对象的 greenfield 建模，各自一文件：

- ``bboard``：留言板（bboard.c dbase：board_id/notes/wizard_only/poster_family）
- ``job_data``：门派任务/贡献度统计（源码 /clone/obj/job/ 缺失，存档
  data/job_system/job_data.o 可读 LPC .o 文本，数据结构从存档反推，见 ADR-0061）
- ``job_server``：任务奖励统计服务（clone/obj/job_server.c 源码完整可读，
  dbase keys 从源码直接提取，见 ADR-0061）

每个 daemon 实现 ``DaemonSerializable``（``to_dict``/``from_dict``），由
``DaemonStore`` register/save/restore_all。
"""
