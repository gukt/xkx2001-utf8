"""LPC 原版侠客行 do_attack 七步 combat golden trace 录制客户端。

用途：连接本地 FluffOS 3.0 driver（127.0.0.1:8888），录制层 E 战斗的
文本流基线，供阶段 2.4 文本体验流行为为等价 diff 使用（dissent 4 基线测试）。

关键编码事实（实测探明，见 README.md "编码"节）：
- driver 输出为 **UTF-8**（选 BIG5=n 后），telnet IAC 协商字节须先过滤再 UTF-8 decode。
- driver 中文输入须用 **GBK** 编码：LPC `check_legal_name` 用 `strlen` 按字节判定，
  要求中文名字节长 2-8 且为偶数。UTF-8 中文 3 字节/字无法满足偶数约束，
  GBK 中文 2 字节/字方可（1-4 中文字）。
- 英文名须纯字母 a-z，长度 3-8。
- 密码 ASCII，长度 >=5。
- 电子邮件须 id@address 格式（空字符串会被拒）。

边界：定点辅助录制 combat 文本流，不录全量命令流（ADR-0009）。
不修改 LPC 源（仓库根 adm/ cmds/ d/ kungfu/ 只读）。
不重启 driver（单进程共享，多连接会干扰概率采样）。

用法：
    cd engine && .venv/bin/python -m tools.golden_trace.recorder --login
    cd engine && .venv/bin/python -m tools.golden_trace.recorder --sample
详见 README.md。
"""

from __future__ import annotations

import contextlib
import json
import re
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# 编码/协议常量
# ---------------------------------------------------------------------------

DRIVER_HOST = "127.0.0.1"
DRIVER_PORT = 8888
DRIVER_ENCODING_OUT = "utf-8"  # driver 输出编码（实测）
CN_INPUT_ENCODING = "gbk"  # 中文名/中文命令输入编码（LPC strlen 按字节判定）
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
DEFAULT_TIMEOUT = 8.0
LONG_TIMEOUT = 15.0


def strip_iac(data: bytes) -> bytes:
    """过滤 telnet IAC 协商字节（0xff 开头），否则 decode 失败。

    处理：IAC IAC(0xff 0xff -> 字面 0xff)、WILL/WONT/DO/DONT(0xfb-0xfe + option)、
    SB...SE(0xfa ... 0xff 0xf0)。
    """
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0xFF and i + 1 < n:
            cmd = data[i + 1]
            if cmd == 0xFF:  # 转义的字面 0xff
                out.append(0xFF)
                i += 2
            elif cmd in (0xFB, 0xFC, 0xFD, 0xFE):  # WILL/WONT/DO/DONT + 1 option
                i += 3
            elif cmd == 0xFA:  # SB ... IAC SE 子协商
                j = i + 2
                while j < n - 1:
                    if data[j] == 0xFF and data[j + 1] == 0xF0:
                        j += 2
                        break
                    j += 1
                i = j if j < n else n
            else:  # 其他两字节命令
                i += 2
        else:
            out.append(b)
            i += 1
    return bytes(out)


def strip_ansi(text: str) -> str:
    """去除 ANSI 颜色码 \\x1b[...m，返回纯文本（保留换行）。"""
    return ANSI_RE.sub("", text).replace("\r", "")


# ---------------------------------------------------------------------------
# 会话日志
# ---------------------------------------------------------------------------


@dataclass
class SessionLog:
    """录制会话日志：每条 (方向, 时间戳, 原始文本含 ANSI, 纯文本)。

    保留含 ANSI 版本（diff 时按需剥离），同时存纯文本便于检索。
    """

    entries: list[dict] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def record(self, direction: str, text: str) -> None:
        self.entries.append(
            {
                "dir": direction,  # "recv" / "send"
                "ts": time.time() - self.started_at,
                "raw": text,  # 含 ANSI
                "clean": strip_ansi(text),
            }
        )

    def dump(self, path: Path) -> None:
        with path.open("w", encoding="utf-8") as f:
            f.write("# golden trace session log\n")
            f.write("# started: " + time.ctime(self.started_at) + "\n")
            f.write(f"# entries: {len(self.entries)}\n\n")
            for e in self.entries:
                tag = ">> SEND" if e["dir"] == "send" else "<< RECV"
                f.write(f"----- [{e['ts']:7.2f}s] {tag} -----\n")
                f.write(e["raw"])
                if not e["raw"].endswith("\n"):
                    f.write("\n")
                f.write("\n")


# ---------------------------------------------------------------------------
# DriverClient
# ---------------------------------------------------------------------------


class DriverClient:
    """FluffOS driver telnet 交互客户端（串行单连接）。

    生命周期：connect -> login -> command* / sample_combat* -> close。
    登录状态机见 `login()` 文档。
    """

    def __init__(
        self,
        host: str = DRIVER_HOST,
        port: int = DRIVER_PORT,
        log: SessionLog | None = None,
    ):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.log = log or SessionLog()
        self.in_game = False

    # -- 底层 ----------------------------------------------------------

    def connect(self, timeout: float = DEFAULT_TIMEOUT) -> str:
        """建立 TCP 连接，读首屏标题画面。返回首屏文本。"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect((self.host, self.port))
        txt, _ = self._read_until(["BIG5", "Do you want"], timeout=timeout)
        self.log.record("recv", txt)
        return txt

    def _read_until(
        self,
        markers: list[str],
        timeout: float = DEFAULT_TIMEOUT,
    ) -> tuple[str, str | None]:
        """读直到任一 marker（纯文本，已去 ANSI）出现或超时。

        返回 (full_text 含 ANSI, matched_marker)。markers 为空时读到超时返回全部。
        """
        assert self.sock is not None
        buf = ""
        deadline = time.time() + timeout
        self.sock.settimeout(0.5)
        while time.time() < deadline:
            try:
                d = self.sock.recv(4096)
                if d:
                    buf += strip_iac(d).decode(DRIVER_ENCODING_OUT, errors="replace")
                    if markers:
                        c = strip_ansi(buf)
                        for m in markers:
                            if m in c:
                                return buf, m
                else:
                    break
            except TimeoutError:
                if not markers:
                    # 无 marker 模式：读到静默即返回
                    return buf, None
                continue
            except OSError:
                break
        return buf, None

    def _send(self, text: str, gbk: bool = False) -> None:
        """发送一行。gbk=True 时用 GBK 编码（中文输入），否则 ASCII。"""
        assert self.sock is not None
        enc = CN_INPUT_ENCODING if gbk else "ascii"
        data = text.encode(enc) + b"\n"
        self.sock.sendall(data)
        self.log.record("send", text + "\n")

    # -- 登录状态机 ----------------------------------------------------

    def login(
        self,
        account: str,
        cn_name: str,
        password: str,
        email: str = "trace@xkx.local",
        accept_gift: bool = True,
        gender: str = "m",
    ) -> str:
        """走完整登录状态机进游戏。

        步骤（实测探明，对应 adm/daemons/logind.c）：
            1. BIG5? -> n（选 GB/UTF-8 输出）
            2. 英文名（纯字母 3-8）-> account
            3. "确定吗" -> y
            4. 中文名（GBK 编码，1-4 中文字）-> cn_name
            5. 密码（ASCII >=5）-> password
            6. 密码确认 -> password
            7. 天赋 -> y（接受）或 n（重随机，改问"同意"）
            8. 电子邮件地址（须 id@address 格式）-> email
            9. 性别 m/f -> gender
           10. 进游戏（出生地默认，无选择提示，直接 enter_world）

        返回进游戏后的首屏文本（look 输出）。
        """
        self._send("n")
        txt, _ = self._read_until(["您的英文名字"])
        self.log.record("recv", txt)

        self._send(account)
        txt, m = self._read_until(["确定吗", "您的英文名字"])
        self.log.record("recv", txt)
        if m != "确定吗":
            tail = strip_ansi(txt)[-200:]
            raise LoginError(f"英文名 {account!r} 被拒（须纯字母 3-8 字符）: {tail}")

        self._send("y")
        txt, _ = self._read_until(["中文名字"])
        self.log.record("recv", txt)

        self._send(cn_name, gbk=True)
        txt, m = self._read_until(["密码", "对不起", "中文名字"])
        self.log.record("recv", txt)
        if "对不起" in strip_ansi(txt):
            raise LoginError(
                f"中文名 {cn_name!r} 被拒（须 GBK 1-4 中文字）: {strip_ansi(txt)[-200:]}"
            )

        self._send(password)
        txt, m = self._read_until(["再输入", "密码的长度", "密码"])
        self.log.record("recv", txt)
        if "密码的长度" in strip_ansi(txt):
            raise LoginError(f"密码过短（须 >=5 字元）: {strip_ansi(txt)[-200:]}")

        self._send(password)
        txt, _ = self._read_until(["天赋"])
        self.log.record("recv", txt)

        # 步骤 7：天赋。第一次问"接受"，发 n 改问"同意"；循环直到 y
        loop = 0
        while loop < 10:
            loop += 1
            c = strip_ansi(txt)
            if "接受" in c or "同意" in c:
                if accept_gift:
                    self._send("y")
                    break
                self._send("n")
                txt, _ = self._read_until(["接受", "同意"])
                self.log.record("recv", txt)
            else:
                break

        # 步骤 8：电子邮件
        txt, _ = self._read_until(["电子邮件", "电子", "邮箱"])
        self.log.record("recv", txt)
        self._send(email)
        txt, _ = self._read_until(["男性", "女性", "电子邮件"])
        self.log.record("recv", txt)
        if "电子邮件" in strip_ansi(txt) and "男性" not in strip_ansi(txt):
            # email 格式不对，重发默认
            self._send("trace@xkx.local")
            txt, _ = self._read_until(["男性", "女性"])
            self.log.record("recv", txt)

        # 步骤 9：性别
        self._send(gender)
        # 进游戏（enter_world），读首屏
        txt, _ = self._read_until(
            [">", "□", "【", "您现在"], timeout=LONG_TIMEOUT
        )
        self.log.record("recv", txt)
        self.in_game = True
        return txt

    # -- 游戏内命令 ----------------------------------------------------

    def command(
        self,
        cmd: str,
        wait_markers: list[str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> str:
        """发一条游戏命令，读响应。

        cmd 为纯 ASCII 命令（look/go north/kill npc 等）。中文命令须用
        `command_cn()`。wait_markers 可指定等待关键词，否则读到静默返回。
        """
        self._send(cmd)
        if wait_markers:
            txt, _ = self._read_until(wait_markers, timeout=timeout)
        else:
            txt, _ = self._read_until([], timeout=timeout)
        self.log.record("recv", txt)
        return txt

    def command_cn(self, cmd: str, timeout: float = DEFAULT_TIMEOUT) -> str:
        """发含中文的命令（GBK 编码输入）。"""
        self._send(cmd, gbk=True)
        txt, _ = self._read_until([], timeout=timeout)
        self.log.record("recv", txt)
        return txt

    # -- combat 采样 ---------------------------------------------------

    def sample_combat(
        self,
        npc: str,
        rounds: int = 30,
        round_timeout: float = 3.0,
    ) -> str:
        """反复 kill 同一 NPC 采样 combat 文本流。

        策略：kill <npc> 触发战斗，combat 每回合自动输出文本（fight_ob 持续）。
        持续读响应 rounds 个"回合"（以观察到攻击/被攻击文本计数），直到战斗结束
        （NPC 死亡或玩家死亡或 flee）。

        返回累积的 combat 文本流。
        """
        self._send(f"kill {npc}")
        self.log.record("send", f"kill {npc}\n")
        accumulated = ""
        attacks_seen = 0
        deadline = time.time() + rounds * round_timeout + 10
        while time.time() < deadline and attacks_seen < rounds * 2:
            txt, _ = self._read_until([], timeout=round_timeout)
            if txt:
                accumulated += txt
                self.log.record("recv", txt)
                c = strip_ansi(txt)
                # 统计回合：攻击动作行通常含"你"或 NPC 名 + 武学招式
                attacks_seen += c.count("你使出") + c.count("使出一招")
                # 死亡/逃跑终止
                if "死了" in c or "你被击败" in c or "你已经死了" in c:
                    break
                if "什么" in c and npc in c and "没有" in c:
                    break  # NPC 不存在
            else:
                # 静默：可能战斗结束，发 look 探测
                break
        return accumulated

    # -- 收尾 ----------------------------------------------------------

    def close(self) -> None:
        if self.sock is not None:
            with contextlib.suppress(OSError):
                self._send("quit")
            with contextlib.suppress(OSError):
                self.sock.close()
            self.sock = None


class LoginError(RuntimeError):
    """登录状态机失败。"""


# ---------------------------------------------------------------------------
# 概率统计
# ---------------------------------------------------------------------------

# 攻击结果消息模式（LPC combatd.c damage_msg / combat 消息）
# 这些是层 E 七步的观测点，对照 layer_e_combat.py 的 RandomSpec 概率模型。
RESULT_PATTERNS = {
    # (key, 正则, 对应 LPC 概率公式) -- 模式基于实测 combat 文本校准
    # 实测文本：命中后有"结果在...造成"/"结果一击命中"/"结果你..."伤害描述；
    # 闪避为"身子一侧，闪了开去"/"及时避开"；未命中为"偏了几寸"。
    "dodge": (re.compile(r"闪了开去|及时避开"), "闪避概率 = dp/(ap+dp)"),
    "parry": (re.compile(r"招架|格挡|架开"), "招架概率 = pp/(ap+pp)"),
    "hit": (re.compile(r"结果在.*?造成|结果一击命中|结果你\w"), "命中 = 1 - dodge - parry"),
    "miss": (re.compile(r"偏了几寸|没有击中|落空"), "未命中（稀有）"),
    "wound": (
        re.compile(r"瘀伤|瘀青|肿了|内伤| wounded"),
        "wound: 空手kill 1/4, 武器kill 1/2, 空手非kill 1/7, 武器非kill 1/4",
    ),
    "dodge_exp": (re.compile(r"获得了.*经验.*闪避"), "闪避后获经验: (jingli_ratio*100+int)>50"),
    "crit": (re.compile(r"致命|暴击"), "暴击（伤害随机化上界）"),
}
# 伤害数值提取："-123 点气" / "造成 45 点伤害"
DAMAGE_RE = re.compile(r"(?:减(?:少|少)|损失|造成|击中.*?)(\d+)\s*(?:点)?(?:气|伤害|气血)")
QI_CHANGE_RE = re.compile(r"(\d+)\s*点?\s*气")


def analyze_combat(text: str) -> dict:
    """分析 combat 文本流，返回概率统计 + 伤害分布。

    对照层 E 31 处 random 概率模型，标注每个观测值对应公式。
    """
    clean = strip_ansi(text)
    stats: dict = {
        "totals": {},
        "probabilities": {},
        "damage_values": [],
        "damage_stats": {},
        "lpc_formula_map": {},
    }
    for key, (pat, formula) in RESULT_PATTERNS.items():
        n = len(pat.findall(clean))
        stats["totals"][key] = n
        stats["lpc_formula_map"][key] = formula

    # 概率：命中/闪避/招架 三者互斥（七步 3/4 步顺序判定）
    dodge = stats["totals"]["dodge"]
    parry = stats["totals"]["parry"]
    hit = stats["totals"]["hit"]
    decided = dodge + parry + hit
    if decided > 0:
        stats["probabilities"] = {
            "dodge_p": round(dodge / decided, 4),
            "parry_p": round(parry / decided, 4),
            "hit_p": round(hit / decided, 4),
            "n_decided": decided,
        }
    # 伤害分布
    damages = [int(m) for m in DAMAGE_RE.findall(clean)]
    stats["damage_values"] = damages
    if damages:
        stats["damage_stats"] = {
            "n": len(damages),
            "min": min(damages),
            "max": max(damages),
            "mean": round(sum(damages) / len(damages), 2),
        }
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

BASELINE_DIR = Path(__file__).parent / "baseline"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or "--help" in argv or "-h" in argv:
        print(__doc__)
        print(
            "\n子命令:\n"
            "  --login        跑完整登录流程，保存 login_session.txt\n"
            "  --sample       登录后采样 combat，保存 combat_*.txt + combat_stats.json\n"
            "  --explore      登录后 look/go 探索（找 NPC 用）\n"
            "环境变量:\n"
            "  XKX_ACCOUNT  英文名（默认 goldtrc）\n"
            "  XKX_CN_NAME  中文名（默认 金录基）\n"
            "  XKX_PASSWORD 密码（默认 pass123）\n"
            "  XKX_NPC      采样 NPC id（默认 rabbit）\n"
            "  XKX_ROUNDS   采样回合数（默认 30）\n"
        )
        return 0

    import os

    account = os.environ.get("XKX_ACCOUNT", "goldtrc")
    cn_name = os.environ.get("XKX_CN_NAME", "金录基")
    password = os.environ.get("XKX_PASSWORD", "pass123")
    npc = os.environ.get("XKX_NPC", "rabbit")
    rounds = int(os.environ.get("XKX_ROUNDS", "30"))

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    client = DriverClient()
    try:
        client.connect()
        first = client.login(account, cn_name, password)
        print("[login] in_game, first screen bytes:", len(first))

        if "--login" in argv:
            client.log.dump(BASELINE_DIR / "login_session.txt")
            print(f"[login] saved {BASELINE_DIR / 'login_session.txt'}")
            # 进游戏后 look 一次
            look_txt = client.command("look")
            client.log.dump(BASELINE_DIR / "login_session.txt")
            print(f"[login] look output bytes: {len(look_txt)}")

        if "--explore" in argv:
            look_txt = client.command("look")
            print(strip_ansi(look_txt)[:2000])
            # 试几个方向
            for d in ("north", "south", "east", "west"):
                t = client.command(f"go {d}")
                print(f"\n=== go {d} ===")
                print(strip_ansi(t)[:800])

        if "--sample" in argv:
            # 先 look 看当前房间 NPC
            look_txt = client.command("look")
            (BASELINE_DIR / "look_before.txt").write_text(
                strip_ansi(look_txt), encoding="utf-8"
            )
            combat = client.sample_combat(npc, rounds=rounds)
            out = BASELINE_DIR / f"combat_{npc}.txt"
            out.write_text(combat, encoding="utf-8")
            print(f"[sample] saved {out}, bytes={len(combat)}")
            # 统计
            stats = analyze_combat(combat)
            stats_path = BASELINE_DIR / "combat_stats.json"
            stats_path.write_text(
                json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"[sample] saved {stats_path}")
            print("[sample] summary:", stats["probabilities"], stats["damage_stats"])
            # meta
            meta = {
                "driver": "FluffOS 3.0 (MudOS v22b25 兼容)",
                "host": f"{DRIVER_HOST}:{DRIVER_PORT}",
                "encoding_out": DRIVER_ENCODING_OUT,
                "encoding_cn_input": CN_INPUT_ENCODING,
                "account": account,
                "cn_name": cn_name,
                "npc": npc,
                "rounds_requested": rounds,
                "login_steps": 10,
                "login_step9": "性别选择 m/f（天赋 y 后是电子邮件，再是性别，然后进游戏）",
                "repro_cmds": [
                    f"XKX_ACCOUNT={account} XKX_CN_NAME='{cn_name}' "
                    f"XKX_PASSWORD={password} XKX_NPC={npc} "
                    f".venv/bin/python -m tools.golden_trace.recorder --sample",
                ],
                "notes": [
                    "driver 单进程共享，须串行单连接",
                    "不得 kill -9 driver（UE 状态端口 8888 不释放）",
                    "ANSI 颜色码保留在 raw，clean 字段已剥离",
                    "随机性：LPC random() 每次采样结果不同，概率需多次采样取分布",
                ],
            }
            (BASELINE_DIR / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
