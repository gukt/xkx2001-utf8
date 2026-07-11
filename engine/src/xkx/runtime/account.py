"""AccountService：账号注册 + 密码验证（ADR-0014 决策 7，ADR-0024 决策 3）。

argon2id 密码哈希替换 LPC ``crypt()``（抗 GPU/ASIC 暴力破解）。账号存储为 JSON
文件（每账号一文件，衔接 T5 存档思路）。无状态服务（非 System），密码哈希 +
账号查询纯函数式。

[ADR-0014](../../../docs/adr/ADR-0014-daemon-responsibility-redesign.md) 决策 7
[ADR-0024](../../../docs/adr/ADR-0024-ws-protocol-reconnect-accountservice.md) 决策 3
[spec/layer_h_daemons.py](../spec/layer_h_daemons.py) LOGIN_D check_legal_id/name + random_gift
"""

from __future__ import annotations

import random
import re
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, VerifyMismatchError
from pydantic import BaseModel


class AccountError(Exception):
    """账号错误（注册/验证失败）。"""


# check_legal_id：3-8 小写字母（spec layer_h _check_legal_id）
_ID_PATTERN = re.compile(r"^[a-z]{3,8}$")

# banned_name 列表（spec layer_h _check_legal_name，代词/特殊名字）
_BANNED_NAMES: frozenset[str] = frozenset(
    {"你", "我", "他", "她", "它", "韦小宝", "某人", "您", "谣言", "蒙面人", "金庸"}
)

# 密码最小长度（spec layer_h _new_password：长度 >= 5）
MIN_PASSWORD_LEN = 5


class Account(BaseModel):
    """账号数据（JSON 存储用）。"""

    account_id: str  # 英文名 id（LPC id）
    name: str  # 中文名（LPC name）
    password_hash: str  # argon2id 哈希
    gender: str = "男性"
    # 天赋（random_gift 生成，spec layer_h _random_gift 不变量）
    str_: int = 10
    dex_: int = 10
    int_: int = 10
    con_: int = 10
    end_: int = 60  # end = 100 - str - int - con - dex
    kar: int = 10
    pat: int = 10
    per: int = 40  # per = 60 - kar - pat


def check_legal_id(account_id: str) -> bool:
    """校验英文名：3-8 小写字母（spec _check_legal_id）。"""
    return bool(_ID_PATTERN.match(account_id))


def check_legal_name(name: str) -> bool:
    """校验中文名：1-4 字且不在 banned_name 列表（spec _check_legal_name）。"""
    if not name or not name.strip() or len(name) > 4:
        return False
    return name not in _BANNED_NAMES


def random_gift() -> dict[str, int]:
    """天赋生成（spec _random_gift）。

    50 次 random(4) 分配到 str/int/con/dex（起始 10，上限 30），
    end = 100 - 其余四项。kar+pat+per = 60（kar/pat = 10+random(21)，per = 60-kar-pat）。

    不变量：str+int+con+dex+end == 100，kar+pat+per == 60。
    """
    str_ = int_ = con_ = dex_ = 10
    for _ in range(50):
        r = random.randint(0, 3)
        if r == 0 and str_ < 30:
            str_ += 1
        elif r == 1 and int_ < 30:
            int_ += 1
        elif r == 2 and con_ < 30:
            con_ += 1
        elif r == 3 and dex_ < 30:
            dex_ += 1
    end_ = 100 - str_ - int_ - con_ - dex_
    kar = 10 + random.randint(0, 20)
    pat = 10 + random.randint(0, 20)
    per = 60 - kar - pat
    return {
        "str_": str_,
        "int_": int_,
        "con_": con_,
        "dex_": dex_,
        "end_": end_,
        "kar": kar,
        "pat": pat,
        "per": per,
    }


class AccountService:
    """账号服务（无状态，ADR-0014 决策 7）。

    argon2id 密码哈希。账号存储为 JSON 文件（``storage_dir/<id>.json``）。
    ``storage_dir=None`` 时为纯内存模式（测试用，不持久化）。
    """

    def __init__(
        self,
        storage_dir: Path | None = None,
        *,
        time_cost: int = 2,
    ) -> None:
        self._hasher = PasswordHasher(time_cost=time_cost, memory_cost=8192, parallelism=1)
        self._storage_dir = storage_dir
        if storage_dir is not None:
            storage_dir.mkdir(parents=True, exist_ok=True)
        self._memory: dict[str, Account] = {}  # storage_dir=None 时用

    def hash_password(self, password: str) -> str:
        """argon2id 哈希密码。"""
        return self._hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码（argon2 verify）。错误返回 False（不 raise）。"""
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, Argon2Error):
            return False
        except Exception:
            return False

    def register(
        self,
        account_id: str,
        name: str,
        password: str,
        gender: str = "男性",
    ) -> Account:
        """注册新账号：校验 + 天赋 + argon2 哈希 + 存储。"""
        if not check_legal_id(account_id):
            raise AccountError("英文名必须是 3 到 8 个小写字母")
        if not check_legal_name(name):
            raise AccountError("中文名必须是 1 到 4 个中文字且不与禁用词冲突")
        if len(password) < MIN_PASSWORD_LEN:
            raise AccountError(f"密码长度至少 {MIN_PASSWORD_LEN} 位")
        if self._load(account_id) is not None:
            raise AccountError(f"账号 {account_id} 已存在")
        account = Account(
            account_id=account_id,
            name=name,
            password_hash=self.hash_password(password),
            gender=gender,
            **random_gift(),
        )
        self._save(account)
        return account

    def verify(self, account_id: str, password: str) -> Account | None:
        """验证账号密码（登录用）。成功返回 Account，失败返回 None。"""
        account = self._load(account_id)
        if account is None:
            return None
        if not self.verify_password(password, account.password_hash):
            return None
        return account

    def exists(self, account_id: str) -> bool:
        """账号是否存在。"""
        return self._load(account_id) is not None

    def _save(self, account: Account) -> None:
        if self._storage_dir is None:
            self._memory[account.account_id] = account
            return
        path = self._storage_dir / f"{account.account_id}.json"
        path.write_text(account.model_dump_json(indent=2), encoding="utf-8")

    def _load(self, account_id: str) -> Account | None:
        if self._storage_dir is None:
            return self._memory.get(account_id)
        path = self._storage_dir / f"{account_id}.json"
        if not path.exists():
            return None
        return Account.model_validate_json(path.read_text(encoding="utf-8"))
