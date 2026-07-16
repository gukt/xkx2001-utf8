"""job_server daemon（ADR-0061 决策 2 顺带迁移数据层）。

对照 LPC ``clone/obj/job_server.c``（718 行，源码完整可读）。系统 1：
F_SAVE 单例，``query_save_file = /data/npc/job_server``。每个 ``_func``
方法 ``restore()`` + 改 dbase + ``save()``。

dbase keys 从源码直接提取（非反推）：

- ``exp_limit/<job>``（mapping）：per-job exp 限制
- ``pot_limit/<job>``（mapping）：per-job pot 限制
- ``stat/<job>``（mapping of arrays）：per-job per-user 统计
- ``exp_hist/<job>``（array of arrays）：per-job exp 直方图
- ``pot_hist/<job>``（array of arrays）：per-job pot 直方图
- ``job_data/<job>_<data>``（KV）：per-job 自定义数据

命令层留后续 job_server 子系统批（调用方 ``ftb_zhu.c`` / ``zhike.c``
门派任务触发逻辑较重）。

[ADR-0061](../../../docs/adr/ADR-0061-job-data-binary-source-equivalence.md) 决策 2
[ADR-0057](../../../docs/adr/ADR-0057-daemon-store-per-object-save.md)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 直方图 bin 数（对照 job_server.c L626/L639 allocate(10)）
HIST_BINS = 10


@dataclass
class JobServerData:
    """job_server daemon 数据（对照 job_server.c dbase）。

    系统 1：源码完整可读（718 行），dbase keys 从源码直接提取。
    DaemonStore 管理下数据已在内存（ADR-0057），``restore`` 为
    no-op，``save`` 由调用方调 ``daemon_store.save("job_server")``。

    ``stat[job][player_id]`` 为 6 元素列表（对照 job_server.c L604）：
    ``[count, total_time, pot_reward, pot_rate, exp_reward, exp_rate]``。

    ``exp_hist[job]`` / ``pot_hist[job]`` 为 10 bin 数组（对照
    job_server.c L626/L639），每 bin 为 3 元素列表：
    ``[count, total_reward, total_time]``。
    """

    # set("exp_limit/"+job_name, limit)（job_server.c L543）
    exp_limit: dict[str, int] = field(default_factory=dict)
    # set("pot_limit/"+job_name, limit)（job_server.c L549）
    pot_limit: dict[str, int] = field(default_factory=dict)
    # set("stat/"+job_name, stat)（job_server.c L603-619）
    # stat[job][player_id] = [count, time, pot_reward, pot_rate, exp_reward, exp_rate]
    stat: dict[str, dict[str, list[int]]] = field(default_factory=dict)
    # set("exp_hist/"+job_name, hist)（job_server.c L624-628）
    # hist[job][i] = [count, total_reward, total_time]
    exp_hist: dict[str, list[list[int]]] = field(default_factory=dict)
    # set("pot_hist/"+job_name, hist)（job_server.c L637-641）
    pot_hist: dict[str, list[list[int]]] = field(default_factory=dict)
    # set("job_data/"+job_name+"_"+data_name, value)（job_server.c L675）
    job_data: dict[str, Any] = field(default_factory=dict)

    # ──── DaemonSerializable ────

    def to_dict(self) -> dict[str, Any]:
        return {
            "exp_limit": self.exp_limit,
            "pot_limit": self.pot_limit,
            "stat": self.stat,
            "exp_hist": self.exp_hist,
            "pot_hist": self.pot_hist,
            "job_data": self.job_data,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> JobServerData:
        return cls(
            exp_limit=d.get("exp_limit", {}),
            pot_limit=d.get("pot_limit", {}),
            stat=d.get("stat", {}),
            exp_hist=d.get("exp_hist", {}),
            pot_hist=d.get("pot_hist", {}),
            job_data=d.get("job_data", {}),
        )

    # ──── API（从 job_server.c 源码直接提取） ────

    def restore(self) -> None:
        """从存档恢复 dbase（对照 job_server.c 各 _func 方法 restore()）。

        DaemonStore 管理下数据已在内存（ADR-0057），此处为 no-op。
        """
        return

    def save(self) -> None:
        """保存 dbase 到存档（对照 job_server.c 各 _func 方法 save()）。

        DaemonStore 管理下由调用方调 ``daemon_store.save("job_server")``。
        """
        return

    def set_exp_limit(self, job_name: str, limit: int) -> None:
        """设置 per-job exp 限制（对照 job_server.c L541-545 set_exp_limit_func）。"""
        self.exp_limit[job_name] = limit

    def get_exp_limit(self, job_name: str) -> int:
        """取 per-job exp 限制（对照 job_server.c L553-556 get_exp_limit_func）。"""
        return self.exp_limit.get(job_name, 0)

    def set_pot_limit(self, job_name: str, limit: int) -> None:
        """设置 per-job pot 限制（对照 job_server.c L547-551 set_pot_limit_func）。"""
        self.pot_limit[job_name] = limit

    def get_pot_limit(self, job_name: str) -> int:
        """取 per-job pot 限制（对照 job_server.c L558-561 get_pot_limit_func）。"""
        return self.pot_limit.get(job_name, 0)

    def set_job_data(
        self, job_name: str, data_name: str, value: Any
    ) -> None:
        """设置 per-job 自定义数据（对照 job_server.c L673-677）。"""
        self.job_data[f"{job_name}_{data_name}"] = value

    def get_job_data(
        self, job_name: str, data_name: str
    ) -> Any:
        """取 per-job 自定义数据（对照 job_server.c L679-682）。"""
        return self.job_data.get(f"{job_name}_{data_name}")

    def get_job_hist(self, job_name: str) -> list[Any]:
        """取 per-job 直方图（对照 job_server.c L688-696 get_job_hist_func）。

        返回 ``[exp_hist, pot_hist]``。
        """
        return [
            self.exp_hist.get(job_name),
            self.pot_hist.get(job_name),
        ]

    def get_job_stat(self, job_name: str) -> dict[str, list[int]]:
        """取 per-job per-user 统计（对照 job_server.c L684-686 get_job_stat_func）。"""
        return self.stat.get(job_name, {})

    def clear(self, job_name: str) -> None:
        """清除 job 的直方图和统计（对照 job_server.c L654-671 clear_func）。

        直方图重置为 10 bin 零值（对照 L665-667），统计删除。
        exp_limit / pot_limit 保留（对照 L662-663 注释掉的 delete）。
        """
        zero_bin = [[0, 0, 0] for _ in range(HIST_BINS)]
        if job_name in self.exp_hist:
            self.exp_hist[job_name] = [list(b) for b in zero_bin]
        if job_name in self.pot_hist:
            self.pot_hist[job_name] = [list(b) for b in zero_bin]
        self.stat.pop(job_name, None)

    def init_hist(self, job_name: str) -> None:
        """初始化 per-job 直方图（对照 job_server.c L624-628 / L637-641）。

        若直方图不存在则创建 10 bin 零值数组。
        """
        zero_bin = [[0, 0, 0] for _ in range(HIST_BINS)]
        if job_name not in self.exp_hist:
            self.exp_hist[job_name] = [list(b) for b in zero_bin]
        if job_name not in self.pot_hist:
            self.pot_hist[job_name] = [list(b) for b in zero_bin]
