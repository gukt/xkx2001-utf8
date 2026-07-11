"""AccountService 测试（ADR-0014 决策 7，ADR-0024 决策 3）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from xkx.runtime.account import (
    Account,
    AccountError,
    AccountService,
    check_legal_id,
    check_legal_name,
    random_gift,
)

# ---------------------------------------------------------------------------
# check_legal_id / check_legal_name
# ---------------------------------------------------------------------------


class TestCheckLegalId:
    def test_valid_ids(self) -> None:
        for aid in ("abc", "player", "test123".replace("123", ""), "abcdefgh"):
            assert check_legal_id(aid), f"{aid} 应合法"

    def test_too_short(self) -> None:
        assert not check_legal_id("ab")
        assert not check_legal_id("")

    def test_too_long(self) -> None:
        assert not check_legal_id("abcdefghi")  # 9 字符

    def test_uppercase_rejected(self) -> None:
        assert not check_legal_id("Abc")
        assert not check_legal_id("ABC")

    def test_non_letter_rejected(self) -> None:
        assert not check_legal_id("ab1")
        assert not check_legal_id("a_c")
        assert not check_legal_id("ab c")


class TestCheckLegalName:
    def test_valid_names(self) -> None:
        for name in ("张三", "李四", "令狐冲", "欧阳克"):
            assert check_legal_name(name), f"{name} 应合法"

    def test_empty(self) -> None:
        assert not check_legal_name("")
        assert not check_legal_name(" ")

    def test_too_long(self) -> None:
        assert not check_legal_name("五个字的名字")

    def test_banned_names(self) -> None:
        banned = ["你", "我", "他", "她", "它", "韦小宝", "某人", "您", "谣言", "蒙面人", "金庸"]
        for name in banned:
            assert not check_legal_name(name), f"{name} 应被禁"


# ---------------------------------------------------------------------------
# random_gift 不变量
# ---------------------------------------------------------------------------


class TestRandomGift:
    def test_sum_invariants(self) -> None:
        """str+int+con+dex+end == 100，kar+pat+per == 60。"""
        for _ in range(100):
            gift = random_gift()
            assert gift["str_"] + gift["int_"] + gift["con_"] + gift["dex_"] + gift["end_"] == 100
            assert gift["kar"] + gift["pat"] + gift["per"] == 60

    def test_attribute_bounds(self) -> None:
        """str/int/con/dex 在 [10, 30]，end >= 0。"""
        for _ in range(100):
            gift = random_gift()
            for k in ("str_", "int_", "con_", "dex_"):
                assert 10 <= gift[k] <= 30
            assert gift["end_"] >= 0

    def test_kar_pat_bounds(self) -> None:
        """kar/pat 在 [10, 30]，per = 60-kar-pat。"""
        for _ in range(100):
            gift = random_gift()
            assert 10 <= gift["kar"] <= 30
            assert 10 <= gift["pat"] <= 30
            assert gift["per"] == 60 - gift["kar"] - gift["pat"]


# ---------------------------------------------------------------------------
# AccountService 注册与验证
# ---------------------------------------------------------------------------


class TestAccountServiceRegister:
    def test_register_success(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        account = svc.register("alice", "爱丽丝", "secret1")
        assert account.account_id == "alice"
        assert account.name == "爱丽丝"
        assert account.password_hash != "secret1"  # 哈希后
        assert svc.exists("alice")

    def test_register_persists_to_file(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        svc.register("bob", "鲍勃", "passwd1")
        path = tmp_path / "bob.json"
        assert path.exists()

    def test_register_memory_mode(self) -> None:
        """storage_dir=None 内存模式。"""
        svc = AccountService()
        account = svc.register("carol", "卡罗尔", "pw1234")
        assert svc.exists("carol")
        assert svc.verify("carol", "pw1234") == account or svc.verify("carol", "pw1234") is not None

    def test_register_duplicate_raises(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        svc.register("alice", "爱丽丝", "secret1")
        with pytest.raises(AccountError, match="已存在"):
            svc.register("alice", "另一个", "passwd1")

    def test_register_invalid_id_raises(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        with pytest.raises(AccountError, match="英文名"):
            svc.register("AB", "爱丽丝", "secret1")

    def test_register_invalid_name_raises(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        with pytest.raises(AccountError, match="中文名"):
            svc.register("alice", "韦小宝", "secret1")

    def test_register_short_password_raises(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        with pytest.raises(AccountError, match="密码"):
            svc.register("alice", "爱丽丝", "1234")


class TestAccountServiceVerify:
    def test_verify_correct_password(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        svc.register("alice", "爱丽丝", "secret1")
        account = svc.verify("alice", "secret1")
        assert account is not None
        assert account.account_id == "alice"

    def test_verify_wrong_password(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        svc.register("alice", "爱丽丝", "secret1")
        assert svc.verify("alice", "wrong") is None

    def test_verify_nonexistent_account(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        assert svc.verify("nobody", "pw") is None

    def test_verify_after_reload(self, tmp_path: Path) -> None:
        """重新构造 AccountService（读存档）后仍可验证。"""
        svc1 = AccountService(tmp_path)
        svc1.register("alice", "爱丽丝", "secret1")
        svc2 = AccountService(tmp_path)  # 重新加载
        assert svc2.verify("alice", "secret1") is not None


class TestPasswordHashing:
    def test_hash_password_returns_argon2_hash(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        h = svc.hash_password("secret1")
        assert h.startswith("$argon2")

    def test_verify_password_correct(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        h = svc.hash_password("secret1")
        assert svc.verify_password("secret1", h) is True

    def test_verify_password_wrong(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        h = svc.hash_password("secret1")
        assert svc.verify_password("wrong", h) is False

    def test_password_hash_not_equal_to_plain(self, tmp_path: Path) -> None:
        svc = AccountService(tmp_path)
        h = svc.hash_password("secret1")
        assert h != "secret1"
        assert "secret1" not in h


# ---------------------------------------------------------------------------
# Account 模型
# ---------------------------------------------------------------------------


def test_account_model_roundtrip() -> None:
    """Account JSON 序列化往返。"""
    account = Account(
        account_id="alice",
        name="爱丽丝",
        password_hash="$argon2id$fake",
        str_=20,
        dex_=20,
        int_=15,
        con_=15,
        end_=30,
    )
    restored = Account.model_validate_json(account.model_dump_json())
    assert restored == account
    assert restored.str_ == 20
