"""job_data daemon 单测（ADR-0061）。

数据结构级（决策 1 必做）：存档往返测试 -- 解析 job_data.o（LPC .o 文本）
为 JobData -> to_dict -> from_dict -> 断言字段一致。覆盖全部 12 类 dbase key。

API 契约级（决策 1 必做）：从 center.c 调用方反推 12 方法签名/返回类型，
构造测试用例验证方法行为。

DaemonStore 注册：JobData register/save/restore_all 往返一致。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xkx.runtime.daemon_store import DaemonStore
from xkx.runtime.daemons.job_data import (
    FAMILY_ABBR,
    ActiveJob,
    JobData,
)

# 存档路径（仓库根 data/job_system/job_data.o）
JOB_DATA_O = (
    Path(__file__).parent.parent.parent
    / "data"
    / "job_system"
    / "job_data.o"
)


def _load_archive() -> str:
    """读取存档文本。"""
    return JOB_DATA_O.read_text(encoding="utf-8")


# ──────────────────────── 存档往返（数据结构级） ────────────────────────


def test_parse_archive_basic_fields() -> None:
    """解析存档：ASSESS_NUM / START_JOB_SYSTEM。"""
    data = JobData.from_lpc_o(_load_archive())
    assert data.assess_num == 10000
    assert data.start_job_system == 1


def test_parse_archive_assess_11_families() -> None:
    """解析存档：11 门派评估基数（assess_<fac>）。"""
    data = JobData.from_lpc_o(_load_archive())
    assert len(data.assess) == 11
    assert data.assess["wd"] == 7000
    assert data.assess["xx"] == 5000
    assert data.assess["hs"] == 8000
    assert data.assess["gb"] == 8000
    assert data.assess["sl"] == 5000
    # 全部 11 门派缩写都有
    for abbr in FAMILY_ABBR:
        assert abbr in data.assess


def test_parse_archive_strategy_11_families() -> None:
    """解析存档：11 门派策略（strategy_<fac>，6 策略权重）。"""
    data = JobData.from_lpc_o(_load_archive())
    assert len(data.strategy) == 11
    strat_wd = data.strategy["wd"]
    assert strat_wd["protect"] == 30
    assert strat_wd["oppose_pker"] == 30
    assert strat_wd["generally"] == 40
    assert strat_wd["support_pker"] == 0
    # 6 策略 key 都在
    for abbr in FAMILY_ABBR:
        s = data.strategy[abbr]
        assert "support_pker" in s
        assert "generally" in s


def test_parse_archive_luck_and_rate() -> None:
    """解析存档：11 门派运气值/率（luck_<fac> / luck_<fac>rate）。"""
    data = JobData.from_lpc_o(_load_archive())
    assert len(data.luck) == 11
    assert len(data.luck_rate) == 11
    assert data.luck["wd"] == 3
    assert data.luck_rate["wd"] == 30
    assert data.luck["th"] == 4
    assert data.luck_rate["th"] == 15


def test_parse_archive_money() -> None:
    """解析存档：11 门派金钱系数（money_<fac>）。"""
    data = JobData.from_lpc_o(_load_archive())
    assert len(data.money) == 11
    assert data.money["wd"] == 5
    assert data.money["xx"] == 15


def test_parse_archive_power_11_families() -> None:
    """解析存档：11 门派势力（power_<fac>，5 区域）。"""
    data = JobData.from_lpc_o(_load_archive())
    assert len(data.power) == 11
    pwr_wd = data.power["wd"]
    assert pwr_wd["南疆"] == 5
    assert pwr_wd["中原"] == 20
    assert pwr_wd["西域"] == 0
    # 5 区域 key 都在
    for abbr in FAMILY_ABBR:
        p = data.power[abbr]
        assert "南疆" in p
        assert "中原" in p


def test_parse_archive_job_datas() -> None:
    """解析存档：活跃任务数组（job_datas）。"""
    data = JobData.from_lpc_o(_load_archive())
    assert len(data.job_datas) == 9
    # 条目 1：全真教 oppose_pker 任务
    j0 = data.job_datas[0]
    assert j0.job_player == "wandao"
    assert j0.job_menpai == "全真教"
    assert j0.job_strategy == "oppose_pker"
    assert j0.job_command_mode == "传话"
    assert j0.job_askjob == 1
    # 条目 2：少林派 protect 任务（有 oppose_pker 字段）
    j1 = data.job_datas[1]
    assert j1.job_player == "dsda"
    assert j1.job_menpai == "少林派"
    assert j1.job_strategy == "protect"
    assert j1.job_oppose_pker_place == "/d/wudang/taizipo"
    assert j1.job_oppose_pker_mode == "npc"
    # 条目 2 无 job_command_mode（默认空串）
    assert j1.job_command_mode == ""


def test_parse_archive_family_job_data() -> None:
    """解析存档：门派贡献度数组（family_job_data，11 门派）。"""
    data = JobData.from_lpc_o(_load_archive())
    assert len(data.family_job_data) == 11
    wd = data.family_job_data[0]
    assert wd["family_name"] == "武当派"
    assert wd["job_contribute"] == 4470
    # 玩家贡献值对存在
    assert wd["shanxi"] == 73
    assert wd["axesky"] == 567


def test_parse_archive_family_assess_empty() -> None:
    """解析存档：门派评估为空数组。"""
    data = JobData.from_lpc_o(_load_archive())
    assert data.family_assess == []


def test_parse_archive_assess_player_data() -> None:
    """解析存档：玩家评估数组（assess_player_data）。"""
    data = JobData.from_lpc_o(_load_archive())
    assert len(data.assess_player_data) == 8
    apd0 = data.assess_player_data[0]
    assert apd0["family"] == "丐帮"
    assert apd0["ltt"] == "bad"


def test_roundtrip_to_dict_from_dict() -> None:
    """数据结构级往返：from_lpc_o -> to_dict -> from_dict 断言字段一致。"""
    original = JobData.from_lpc_o(_load_archive())
    d = original.to_dict()
    restored = JobData.from_dict(d)

    # 12 类 dbase key 逐字段断言
    assert restored.assess_num == original.assess_num
    assert restored.assess == original.assess
    assert restored.strategy == original.strategy
    assert restored.luck == original.luck
    assert restored.luck_rate == original.luck_rate
    assert restored.money == original.money
    assert restored.power == original.power
    assert restored.start_job_system == original.start_job_system

    # job_datas 往返
    assert len(restored.job_datas) == len(original.job_datas)
    for orig, rest in zip(original.job_datas, restored.job_datas, strict=True):
        assert rest.job_player == orig.job_player
        assert rest.job_menpai == orig.job_menpai
        assert rest.job_strategy == orig.job_strategy
        assert rest.job_oppose_pker_place == orig.job_oppose_pker_place

    # family_job_data / family_assess / assess_player_data 往返
    assert restored.family_job_data == original.family_job_data
    assert restored.family_assess == original.family_assess
    assert restored.assess_player_data == original.assess_player_data


def test_roundtrip_idempotent() -> None:
    """二次 to_dict -> from_dict 幂等。"""
    data = JobData.from_lpc_o(_load_archive())
    d1 = data.to_dict()
    r1 = JobData.from_dict(d1)
    d2 = r1.to_dict()
    r2 = JobData.from_dict(d2)
    assert d1 == d2
    assert r1.to_dict() == r2.to_dict()


def test_daemon_store_roundtrip(tmp_path: Any) -> None:
    """DaemonStore register/save/restore_all 往返一致。"""
    store = DaemonStore(str(tmp_path))
    original = JobData.from_lpc_o(_load_archive())
    store.register("job_data", original)
    store.save("job_data")

    # 验证存档文件生成
    target = tmp_path / "daemon" / "job_data.json"
    assert target.exists()
    with open(target, encoding="utf-8") as f:
        state = json.load(f)
    assert state["assess_num"] == 10000
    assert state["start_job_system"] == 1

    # 新 store 模拟冷重启：restore_all 需要已知 type 才能定位 from_dict
    store2 = DaemonStore(str(tmp_path))
    store2.register("job_data", JobData())
    store2.restore_all()
    restored = store2.get("job_data")
    assert restored is not None
    assert isinstance(restored, JobData)
    assert restored.assess_num == original.assess_num
    assert restored.assess == original.assess
    assert len(restored.job_datas) == len(original.job_datas)
    assert len(restored.family_job_data) == len(original.family_job_data)


# ──────────────────────── API 契约测试 ────────────────────────


def _sample_job_data() -> JobData:
    """构造测试用 JobData（含 2 门派 + 2 活跃任务）。"""
    return JobData(
        assess_num=10000,
        assess={"wd": 7000, "xx": 5000},
        strategy={
            "wd": {"protect": 30, "generally": 40},
            "xx": {"plunder": 30, "generally": 40},
        },
        luck={"wd": 3, "xx": 2},
        luck_rate={"wd": 30, "xx": 20},
        money={"wd": 5, "xx": 15},
        power={
            "wd": {"南疆": 5, "中原": 20},
            "xx": {"西域": 30, "中原": 0},
        },
        job_datas=[
            ActiveJob(
                job_player="player1",
                job_menpai="武当派",
                job_strategy="oppose_pker",
                job_askjob=1,
            ),
            ActiveJob(
                job_player="player2",
                job_menpai="星宿派",
                job_strategy="protect",
                job_oppose_pker_place="/d/test",
                job_oppose_pker_mode="npc",
            ),
        ],
        family_job_data=[
            {
                "family_name": "武当派",
                "job_contribute": 1000,
                "alice": 500,
                "bob": 300,
                "charlie": 200,
            },
            {
                "family_name": "星宿派",
                "job_contribute": 800,
                "dave": 800,
            },
        ],
        start_job_system=1,
    )


def test_restore_is_noop() -> None:
    """restore() 是 no-op（DaemonStore 内存权威）。"""
    data = _sample_job_data()
    original_assess = data.assess.copy()
    data.restore()
    assert data.assess == original_assess


def test_save_is_noop() -> None:
    """save() 是 no-op（由 DaemonStore.save 负责）。"""
    data = _sample_job_data()
    data.save()
    # 不 raise 即通过


def test_reset_clears_data() -> None:
    """reset() 清空任务数据（对照 center.c L704）。"""
    data = _sample_job_data()
    assert len(data.job_datas) > 0
    data.reset()
    assert data.job_datas == []
    assert data.family_job_data == []
    assert data.family_assess == []
    assert data.assess_player_data == []
    assert data.start_job_system == 0


def test_query_familys_job_data() -> None:
    """query_familys_job_data() 返回所有门派数据（对照 center.c L163）。"""
    data = _sample_job_data()
    result = data.query_familys_job_data()
    assert len(result) == 2
    assert result[0]["family_name"] == "武当派"


def test_query_family_job_data_found() -> None:
    """query_family_job_data(family) 返回单门派数据（对照 center.c L171）。"""
    data = _sample_job_data()
    wd = data.query_family_job_data("武当派")
    assert wd["job_contribute"] == 1000
    assert wd["family_name"] == "武当派"


def test_query_family_job_data_not_found() -> None:
    """query_family_job_data 未找到返回空 dict（对照 center.c L172-177）。"""
    data = _sample_job_data()
    result = data.query_family_job_data("不存在的门派")
    assert result == {}


def test_query_family_jobdata_text() -> None:
    """query_family_jobdata(family) 返回统计文本（对照 center.c L239）。

    推断实现（ADR-0061 决策 1 算法级不可逐行验证）。
    """
    data = _sample_job_data()
    text = data.query_family_jobdata("武当派")
    assert "武当派" in text
    assert "1000" in text


def test_choose_of_player_good() -> None:
    """choose_of_player(family,"good") 返回贡献值降序列表（对照 L240）。

    推断实现（ADR-0061 决策 1 算法级不可逐行验证）。
    """
    data = _sample_job_data()
    good = data.choose_of_player("武当派", "good")
    assert good[0] == "alice"
    assert good[1] == "bob"
    assert good[2] == "charlie"


def test_choose_of_player_bad() -> None:
    """choose_of_player(family,"bad") 返回贡献值升序列表（对照 L255）。

    推断实现（ADR-0061 决策 1 算法级不可逐行验证）。
    """
    data = _sample_job_data()
    bad = data.choose_of_player("武当派", "bad")
    assert bad[0] == "charlie"
    assert bad[1] == "bob"
    assert bad[2] == "alice"


def test_choose_of_player_empty_family() -> None:
    """choose_of_player 未找到门派返回空列表。"""
    data = _sample_job_data()
    result = data.choose_of_player("不存在的门派", "good")
    assert result == []


def test_query_job_start() -> None:
    """query_job_start() 返回任务系统开关（对照 center.c L644/L671）。"""
    data = _sample_job_data()
    assert data.query_job_start() is True
    data.start_job_system = 0
    assert data.query_job_start() is False


def test_set_job_start_and_close() -> None:
    """set_job_start / set_close_start 开关任务系统（对照 L647/L674）。"""
    data = _sample_job_data()
    data.set_close_start()
    assert data.query_job_start() is False
    data.set_job_start()
    assert data.query_job_start() is True


def test_query_job_data() -> None:
    """query_job_data() 返回活跃任务 list[dict]（对照 L709/L811）。"""
    data = _sample_job_data()
    result = data.query_job_data()
    assert len(result) == 2
    assert result[0]["job_player"] == "player1"
    assert result[1]["job_player"] == "player2"


def test_detract_job_data() -> None:
    """detract_job_data(player) 删除玩家任务（对照 L711）。"""
    data = _sample_job_data()
    assert len(data.job_datas) == 2
    data.detract_job_data("player1")
    assert len(data.job_datas) == 1
    assert data.job_datas[0].job_player == "player2"


def test_query_list_ask_job() -> None:
    """query_list("ask_job") 返回已得到任务的玩家（对照 L843）。

    推断实现（ADR-0061 决策 1 算法级不可逐行验证）。
    """
    data = _sample_job_data()
    result = data.query_list("ask_job")
    assert "player1" in result  # job_askjob == 1


def test_query_list_oppose_pker() -> None:
    """query_list("oppose_pker") 返回正在执行任务的玩家（对照 L846）。

    推断实现（ADR-0061 决策 1 算法级不可逐行验证）。
    """
    data = _sample_job_data()
    result = data.query_list("oppose_pker")
    assert "player2" in result  # 有 oppose_pker_place


def test_query_list_finish_job() -> None:
    """query_list("finish_job") 返回已完成任务的玩家（对照 L840）。

    推断实现（ADR-0061 决策 1 算法级不可逐行验证）。
    """
    data = _sample_job_data()
    # player2 的 job_askjob=0（默认），应为 finish_job
    result = data.query_list("finish_job")
    assert "player2" in result


def test_query_list_unknown_key() -> None:
    """query_list 未知 key 返回空列表。"""
    data = _sample_job_data()
    assert data.query_list("unknown") == []


# ──────────────────────── ActiveJob 往返 ────────────────────────


def test_active_job_roundtrip() -> None:
    """ActiveJob to_dict/from_dict 往返一致。"""
    job = ActiveJob(
        job_player="test",
        job_master="master",
        job_master_place="/d/test",
        job_master_cname="测试掌门",
        job_area="中原",
        job_strategy="protect",
        job_menpai="武当派",
        job_command_mode="传话",
        job_askjob=1,
        job_master_prompt_time=992767486,
        job_oppose_pker_place="/d/wudang/taizipo",
        job_oppose_pker_place_chinses="湖北武当山",
        job_oppose_pker_mode="npc",
        job_oppose_pker_time=992961751,
    )
    d = job.to_dict()
    restored = ActiveJob.from_dict(d)
    assert restored.job_player == job.job_player
    assert restored.job_master == job.job_master
    assert restored.job_strategy == job.job_strategy
    assert restored.job_oppose_pker_place == job.job_oppose_pker_place
    assert restored.job_master_prompt_time == job.job_master_prompt_time
