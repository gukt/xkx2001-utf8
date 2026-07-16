"""job_data daemon（ADR-0061）。

门派任务/贡献度统计。源码 ``/clone/obj/job/`` 目录缺失（job_data.c 等
源码全部缺失），存档 ``data/job_system/job_data.o`` 是 UTF-8 编码的
LPC .o 文本格式，数据结构从存档完整反推（ADR-0061 决策 1 数据结构级），
API 契约从调用方 ``d/wizard/center.c`` 反推（决策 1 API 契约级），
算法级逻辑接受推断权衡（决策 1 算法级不可逐行验证）。

12 类 dbase key（从存档反推）：

- ``ASSESS_NUM``（int）：评估基数
- ``assess_<fac>``（int × 11）：门派评估基数
- ``strategy_<fac>``（mapping × 11）：门派策略（6 策略权重）
- ``luck_<fac>`` / ``luck_<fac>rate``（int × 11）：门派运气值/率
- ``money_<fac>``（int × 11）：门派金钱系数
- ``power_<fac>``（mapping × 11）：门派势力（5 区域）
- ``job_datas``（array）：活跃任务数组
- ``family_job_data``（array × 11）：门派贡献度数组
- ``family_assess``（array）：门派评估（存档为空）
- ``assess_player_data``（array）：玩家评估数组
- ``START_JOB_SYSTEM``（int）：任务系统开关

门派缩写对照（11 门派）：``wd``=武当派 / ``xx``=星宿派 / ``hs``=华山派 /
``th``=桃花岛 / ``gb``=丐帮 / ``em``=峨嵋派 / ``bt``=白驼山 /
``qz``=全真教 / ``xs``=雪山派 / ``dl``=大理段家 / ``sl``=少林派。

[ADR-0061](../../../docs/adr/ADR-0061-job-data-binary-source-equivalence.md)
[ADR-0057](../../../docs/adr/ADR-0057-daemon-store-per-object-save.md)
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

# 11 门派缩写 -> 中文名对照（存档 assess_<fac> / strategy_<fac> 等的 <fac>）
FAMILY_ABBR: dict[str, str] = {
    "wd": "武当派",
    "xx": "星宿派",
    "hs": "华山派",
    "th": "桃花岛",
    "gb": "丐帮",
    "em": "峨嵋派",
    "bt": "白驼山",
    "qz": "全真教",
    "xs": "雪山派",
    "dl": "大理段家",
    "sl": "少林派",
}

# 门派开关参数 -> 门派中文名（对照 center.c L215-225 switch 的 11 case）
MENPAI_OPTIONS: list[tuple[str, str]] = [
    ("-wudang", "武当派"),
    ("-xingxiu", "星宿派"),
    ("-huashan", "华山派"),
    ("-taohua", "桃花岛"),
    ("-gaibang", "丐帮"),
    ("-emei", "峨嵋派"),
    ("-baituo", "白驼山"),
    ("-quanzhen", "全真教"),
    ("-xueshan", "雪山派"),
    ("-dali", "大理段家"),
    ("-shaolin", "少林派"),
]

# 6 策略名（存档 strategy_<fac> mapping 的 key）
STRATEGIES: list[str] = [
    "support_pker",
    "business",
    "protect",
    "plunder",
    "oppose_pker",
    "generally",
]

# 5 区域名（存档 power_<fac> mapping 的 key）
AREAS: list[str] = ["南疆", "东北", "西域", "江南", "中原"]

# center.c L11 版权头（ANSI 颜色码移除为纯文本）
COPYRIGHT = (
    "游戏主动性任务察看器1.0版     Server 2001年7月     \n"
)


# ──────────────────────── LPC .o 解析辅助 ────────────────────────


def _lpc_value_to_python(s: str) -> Any:
    """把 LPC .o 值文本转为 Python 对象（int / str / dict / list）。

    LPC .o 格式：mapping ``(["key":value,...])``、array ``({elem,...})``。
    方法：先提取字符串占位，再把 LPC 括号语法替换为 Python 语法，
    最后 ``ast.literal_eval`` 解析。字符串提取避免值中的 ``])``/``({``
    等字符干扰替换。

    ADR-0061 决策 1 数据结构级：存档往返测试用此函数解析存档。
    """
    s = s.strip()
    # 纯 int（含负数）
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    # LPC mapping / array（以 ( 开头）
    if s.startswith("("):
        # 提取所有 "..." 字符串为占位符，避免特殊字符干扰替换
        strings: list[str] = []

        def _save(m: re.Match[str]) -> str:
            strings.append(m.group(0))
            return f"\x00{len(strings) - 1}\x00"

        s = re.sub(r'"[^"]*"', _save, s)
        # LPC -> Python 语法替换（顺序无关：({ 和 ([ 不重叠）
        s = s.replace("({", "[").replace("})", "]")
        s = s.replace("([", "{").replace("])", "}")
        # 恢复字符串
        def _restore(m: re.Match[str]) -> str:
            return strings[int(m.group(1))]

        s = re.sub(r"\x00(\d+)\x00", _restore, s)
        return ast.literal_eval(s)
    # 纯字符串
    if s.startswith('"'):
        return ast.literal_eval(s)
    return s


# ──────────────────────── ActiveJob ────────────────────────


@dataclass
class ActiveJob:
    """单条活跃任务（对照存档 job_datas 数组每条 mapping）。

    字段对照存档 key：job_command_mode / job_player / job_master_place /
    job_area / job_master / job_strategy / job_master_cname / job_askjob /
    job_master_prompt_time / job_menpai。反对 PK 类任务另有
    job_oppose_pker_place / job_oppose_pker_place_chinses /
    job_oppose_pker_mode / job_oppose_pker_time。

    注意：存档中不同任务含字段不一致（条目 2 无 job_command_mode /
    job_askjob / job_master_prompt_time），用默认值兜底。
    """

    job_player: str = ""
    job_master: str = ""
    job_master_place: str = ""
    job_master_cname: str = ""
    job_area: str = ""
    job_strategy: str = ""
    job_menpai: str = ""
    job_command_mode: str = ""
    job_askjob: int = 0
    job_master_prompt_time: int = 0
    # 反对 PK 类任务字段（仅部分任务有，对照存档条目 2）
    # LPC 原文拼写为 chinses（非"中文"），保留原拼写
    job_oppose_pker_place: str = ""
    job_oppose_pker_place_chinses: str = ""
    job_oppose_pker_mode: str = ""
    job_oppose_pker_time: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_player": self.job_player,
            "job_master": self.job_master,
            "job_master_place": self.job_master_place,
            "job_master_cname": self.job_master_cname,
            "job_area": self.job_area,
            "job_strategy": self.job_strategy,
            "job_menpai": self.job_menpai,
            "job_command_mode": self.job_command_mode,
            "job_askjob": self.job_askjob,
            "job_master_prompt_time": self.job_master_prompt_time,
            "job_oppose_pker_place": self.job_oppose_pker_place,
            "job_oppose_pker_place_chinses": (
                self.job_oppose_pker_place_chinses
            ),
            "job_oppose_pker_mode": self.job_oppose_pker_mode,
            "job_oppose_pker_time": self.job_oppose_pker_time,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ActiveJob:
        return cls(
            job_player=d.get("job_player", ""),
            job_master=d.get("job_master", ""),
            job_master_place=d.get("job_master_place", ""),
            job_master_cname=d.get("job_master_cname", ""),
            job_area=d.get("job_area", ""),
            job_strategy=d.get("job_strategy", ""),
            job_menpai=d.get("job_menpai", ""),
            job_command_mode=d.get("job_command_mode", ""),
            job_askjob=d.get("job_askjob", 0),
            job_master_prompt_time=d.get("job_master_prompt_time", 0),
            job_oppose_pker_place=d.get("job_oppose_pker_place", ""),
            job_oppose_pker_place_chinses=d.get(
                "job_oppose_pker_place_chinses", ""
            ),
            job_oppose_pker_mode=d.get("job_oppose_pker_mode", ""),
            job_oppose_pker_time=d.get("job_oppose_pker_time", 0),
        )


# ──────────────────────── JobData ────────────────────────


@dataclass
class JobData:
    """job_data daemon 数据（ADR-0061 决策 1 数据结构级）。

    字段从存档 ``data/job_system/job_data.o`` 反推（12 类 dbase key）。
    存档格式为 LPC .o 文本（UTF-8），数据结构级往返可验证。
    API 契约从 ``d/wizard/center.c`` 调用方反推。
    算法级逻辑（choose_of_player 排序、贡献度计算）为推断实现，
    不可逐行验证（ADR-0061 决策 1 算法级）。

    DaemonStore 管理下数据已在内存（ADR-0057 内存权威），restore 为
    no-op，save 由调用方调 ``daemon_store.save("job_data")``。
    """

    # 1. ASSESS_NUM：评估基数（存档 ASSESS_NUM 10000）
    assess_num: int = 10000
    # 2. assess_<fac>：11 门派评估基数（存档 assess_wd 7000, ...）
    assess: dict[str, int] = field(default_factory=dict)
    # 3. strategy_<fac>：11 门派策略（6 策略权重）
    strategy: dict[str, dict[str, int]] = field(default_factory=dict)
    # 4. luck_<fac>：11 门派运气值（存档 luck_wd 3, ...）
    luck: dict[str, int] = field(default_factory=dict)
    # 5. luck_<fac>rate：11 门派运气率（存档 luck_wdrate 30, ...）
    luck_rate: dict[str, int] = field(default_factory=dict)
    # 6. money_<fac>：11 门派金钱系数（存档 money_wd 5, ...）
    money: dict[str, int] = field(default_factory=dict)
    # 7. power_<fac>：11 门派势力（5 区域，存档 power_wd (["南疆":5,...])）
    power: dict[str, dict[str, int]] = field(default_factory=dict)
    # 8. job_datas：活跃任务数组
    job_datas: list[ActiveJob] = field(default_factory=list)
    # 9. family_job_data：11 门派贡献度数组
    # 每条含多个 player_id:contribute 值对 + job_contribute + family_name
    family_job_data: list[dict[str, Any]] = field(default_factory=list)
    # 10. family_assess：门派评估（存档为空数组 ({})）
    family_assess: list[dict[str, Any]] = field(default_factory=list)
    # 11. assess_player_data：玩家评估数组
    assess_player_data: list[dict[str, Any]] = field(default_factory=list)
    # 12. START_JOB_SYSTEM：任务系统开关（存档 START_JOB_SYSTEM 1）
    start_job_system: int = 1

    # ──── DaemonSerializable ────

    def to_dict(self) -> dict[str, Any]:
        return {
            "assess_num": self.assess_num,
            "assess": self.assess,
            "strategy": self.strategy,
            "luck": self.luck,
            "luck_rate": self.luck_rate,
            "money": self.money,
            "power": self.power,
            "job_datas": [j.to_dict() for j in self.job_datas],
            "family_job_data": self.family_job_data,
            "family_assess": self.family_assess,
            "assess_player_data": self.assess_player_data,
            "start_job_system": self.start_job_system,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> JobData:
        return cls(
            assess_num=d.get("assess_num", 10000),
            assess=d.get("assess", {}),
            strategy=d.get("strategy", {}),
            luck=d.get("luck", {}),
            luck_rate=d.get("luck_rate", {}),
            money=d.get("money", {}),
            power=d.get("power", {}),
            job_datas=[
                ActiveJob.from_dict(j) for j in d.get("job_datas", [])
            ],
            family_job_data=d.get("family_job_data", []),
            family_assess=d.get("family_assess", []),
            assess_player_data=d.get("assess_player_data", []),
            start_job_system=d.get("start_job_system", 1),
        )

    # ──── LPC .o 存档解析 ────

    @classmethod
    def from_lpc_o(cls, text: str) -> JobData:
        """从 LPC .o 存档文本解析为 JobData（ADR-0061 决策 1 数据结构级）。

        存档格式为逐行 key-value，value 可以是 int / LPC mapping /
        LPC array of mappings。用 ``_lpc_value_to_python`` 解析值。
        """
        data = cls()
        for line in text.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            key, val_str = parts
            val = _lpc_value_to_python(val_str)

            if key == "ASSESS_NUM":
                data.assess_num = val
            elif key == "START_JOB_SYSTEM":
                data.start_job_system = val
            elif key == "job_datas":
                data.job_datas = [ActiveJob.from_dict(m) for m in val]
            elif key == "family_job_data":
                data.family_job_data = val
            elif key == "family_assess":
                data.family_assess = val
            elif key == "assess_player_data":
                data.assess_player_data = val
            elif key.startswith("assess_"):
                data.assess[key[7:]] = val
            elif key.startswith("strategy_"):
                data.strategy[key[9:]] = val
            elif key.startswith("luck_") and key.endswith("rate"):
                data.luck_rate[key[5:-4]] = val
            elif key.startswith("luck_"):
                data.luck[key[5:]] = val
            elif key.startswith("money_"):
                data.money[key[6:]] = val
            elif key.startswith("power_"):
                data.power[key[6:]] = val
        return data

    # ──── API 契约（从 center.c 调用方反推） ────

    def restore(self) -> None:
        """从存档恢复 dbase（对照 center.c L161/L235/L639/L666/L702/L810）。

        DaemonStore 管理下数据已在内存（ADR-0057 内存权威），
        restore_all 在启动时一次性加载，此处为 no-op 保留接口兼容。
        """
        # DaemonStore 管理下无需操作
        return

    def save(self) -> None:
        """保存 dbase 到存档（对照 center.c L714）。

        DaemonStore 管理下由调用方调 ``daemon_store.save("job_data")``
        （ADR-0057 决策 1 per-object save），此处为 no-op 保留接口兼容。
        """
        return

    def reset(self) -> None:
        """重置所有任务数据（对照 center.c L704，player_name=="all" 时调）。"""
        self.job_datas = []
        self.family_job_data = []
        self.family_assess = []
        self.assess_player_data = []
        self.start_job_system = 0

    def query_familys_job_data(self) -> list[dict[str, Any]]:
        """返回所有门派任务数据数组（对照 center.c L163）。"""
        return self.family_job_data

    def query_family_job_data(self, family: str) -> dict[str, Any]:
        """返回单门派任务数据（对照 center.c L171）。

        从 family_job_data 中找 family_name 匹配的条目。
        未找到返回空 dict（对照 center.c L172-177 undefinedp 分支）。
        """
        for item in self.family_job_data:
            if item.get("family_name") == family:
                return item
        return {}

    def query_family_jobdata(self, family: str) -> str:
        """门派任务完成统计文本（对照 center.c L239）。

        **推断实现**（ADR-0061 决策 1 算法级不可逐行验证）：文本拼接
        逻辑只能从调用方反推位置（do_check_menpai_job 中
        ``msg += job_data.query_family_jobdata(family)``），具体文本
        内容（哪些字段如何拼接）为推断。
        """
        item = self.query_family_job_data(family)
        contribute = item.get("job_contribute", 0)
        return f"{family}当前的贡献度为{contribute}\t"

    def choose_of_player(
        self, family: str, kind: str
    ) -> list[str]:
        """贡献度 top/bottom 玩家名列表（对照 center.c L240/L255）。

        **推断实现**（ADR-0061 决策 1 算法级不可逐行验证）：排序逻辑
        只能从存档数据推断（family_job_data 中每门派有 job_contribute
        总值和各玩家贡献值），排序细节（相同值如何处理、top/bottom
        取几个）为推断。kind="good" 按贡献值降序，kind="bad" 升序。
        """
        item = self.query_family_job_data(family)
        if not item:
            return []
        # 提取玩家贡献值（排除 job_contribute 和 family_name）
        players = {
            k: v
            for k, v in item.items()
            if k not in ("job_contribute", "family_name")
            and isinstance(v, int)
        }
        if not players:
            return []
        if kind == "good":
            sorted_players = sorted(
                players.items(), key=lambda x: x[1], reverse=True
            )
        else:
            sorted_players = sorted(players.items(), key=lambda x: x[1])
        return [name for name, _ in sorted_players]

    def query_job_start(self) -> bool:
        """任务系统是否开启（对照 center.c L644/L671）。"""
        return self.start_job_system == 1

    def set_job_start(self) -> None:
        """开启任务系统（对照 center.c L647）。"""
        self.start_job_system = 1

    def set_close_start(self) -> None:
        """关闭任务系统（对照 center.c L674）。"""
        self.start_job_system = 0

    def query_job_data(self) -> list[dict[str, Any]]:
        """活跃任务数组（对照 center.c L709/L811）。

        返回 list[dict]（每条含 job_player 等字段），供 get_mapping
        按 job_player 查找。
        """
        return [j.to_dict() for j in self.job_datas]

    def detract_job_data(self, player: str) -> None:
        """删除玩家任务（对照 center.c L711）。"""
        self.job_datas = [
            j for j in self.job_datas if j.job_player != player
        ]

    def query_list(self, key: str) -> list[str]:
        """任务列表查询（对照 center.c L840/L843/L846 do_check_do_job）。

        **推断实现**（ADR-0061 决策 1 算法级不可逐行验证）：query_list
        从 job_datas 中按 key 提取玩家列表。key 可为 "ask_job" /
        "finish_job" / "oppose_pker"。源码缺失，逻辑为推断：
        ask_job = job_askjob==1 的任务，oppose_pker = 有反对 PK
        字段的任务，finish_job = 其余。
        """
        if key == "ask_job":
            return [
                j.job_player
                for j in self.job_datas
                if j.job_askjob == 1
            ]
        if key == "oppose_pker":
            return [
                j.job_player
                for j in self.job_datas
                if j.job_oppose_pker_place
            ]
        if key == "finish_job":
            return [
                j.job_player
                for j in self.job_datas
                if j.job_askjob == 0
            ]
        return []
