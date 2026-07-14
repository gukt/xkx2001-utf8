"""内容审核词表（M3-3，ADR-0033 决策 1）。

对齐 [03 §八](../../../../docs/xkx-arch/03-DSL-UGC与Agent协作.md) 分层内容审核
pipeline 的自动化预检 4 类：暴力 / 敏感词 / 赌博 / 版权关键词。

**检测 ≠ 清洗**（M3 范围收缩，用户决策 2026-07-14）：版权清洗（M3-4 改编化 /
标注 / 授权）整体后置（未商业化阶段过早清洗是过度工程）。M3-3 只做**检测**--
版权关键词命中标记 ``needs_review``（不 block，不强制改），商业化前清洗时预检
已就位。

**severity 三级**：

- ``block``：严重违规，阻止发布（如 license 不合规，[precheck](precheck.py) 单独
  校验，不在本词表）。
- ``needs_review``：需人工审核（版权 / 暴力 / 赌博命中）。
- ``info``：提示（敏感词待人工判）。

**武侠题材注意**：战斗 / 杀 / 血是武侠常态，暴力词针对"超出武侠常态的过度血腥
描写"，非通用战斗词，需人工判定超题材尺度。

**金庸角色词表**：内置主要角色 + 门派（精简，覆盖 LPC 常见衍生）。M3-4 全量
盘点后置（71 文件清单 [copyright_inventory] 脚本后置）；本表 MVP 内置足以验证
版权扫描有效（雪山派 4 金庸角色命中）。

[ADR-0033](../../../../docs/adr/ADR-0033-content-review-pipeline-mvp.md) 决策 1 /
[03 §八](../../../../docs/xkx-arch/03-DSL-UGC与Agent协作.md)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    """违规严重级别（03 §八 内容分级）。"""

    BLOCK = "block"  # 严重违规，阻止发布
    NEEDS_REVIEW = "needs_review"  # 需人工审核
    INFO = "info"  # 提示


class Category(StrEnum):
    """预检维度（03 §八 自动化预检 4 类 + license）。"""

    VIOLENCE = "violence"
    SENSITIVE = "sensitive"
    GAMBLING = "gambling"
    COPYRIGHT = "copyright"
    LICENSE = "license"


@dataclass(frozen=True)
class Term:
    """词表条目。

    Attributes:
        rule_id: 规则唯一标识（如 ``copyright_jinyong_role``）。
        category: 维度（暴力 / 敏感词 / 赌博 / 版权）。
        severity: 命中后的严重级别。
        terms: 触发词列表（命中任一即报告 Finding）。
        rationale: 命中说明（人工 review 判定依据）。
    """

    rule_id: str
    category: Category
    severity: Severity
    terms: tuple[str, ...]
    rationale: str


# ── 暴力词（过度血腥，超出武侠常态）────────────────────────────────────────────
VIOLENCE_TERMS: list[Term] = [
    Term(
        rule_id="violence_excessive_gore",
        category=Category.VIOLENCE,
        severity=Severity.NEEDS_REVIEW,
        terms=(
            "虐杀", "肢解", "开膛", "凌迟", "碎尸", "剥皮", "活剐",
            "剖腹", "抽肠", "挖眼", "炮烙",
        ),
        rationale=(
            "过度血腥暴力描写（武侠常态战斗 / 杀 / 血不计），"
            "需人工判定是否超题材尺度。"
        ),
    ),
]

# ── 敏感词（MVP 空表，后置接入合规词库）──────────────────────────────────────────
SENSITIVE_TERMS: list[Term] = [
    Term(
        rule_id="sensitive_placeholder",
        category=Category.SENSITIVE,
        severity=Severity.INFO,
        terms=(),
        rationale=(
            "敏感词库后置接入（合规词库需法务确认，不可臆造），"
            "结构预留，MVP 不内置具体词。"
        ),
    ),
]

# ── 赌博词（赌博玩法判定）────────────────────────────────────────────────────────
GAMBLING_TERMS: list[Term] = [
    Term(
        rule_id="gambling_mechanics",
        category=Category.GAMBLING,
        severity=Severity.NEEDS_REVIEW,
        terms=(
            "押注", "下注", "庄家", "抽头", "轮盘", "筹码", "赌资",
            "赌场", "聚赌", "设局抽水", "押大小", "摇骰子",
        ),
        rationale="赌博相关内容，需判定是否构成赌博玩法（合规风险）。",
    ),
]

# ── 金庸角色 / 门派词表（版权关键词）────────────────────────────────────────────
# (name, work) 紧凑表示 -> 展开为 Term。覆盖 LPC 常见衍生，精简非穷举。
_JINYONG_ROLES: tuple[tuple[str, str], ...] = (
    # 射雕英雄传
    ("郭靖", "射雕英雄传"), ("黄蓉", "射雕英雄传"), ("黄药师", "射雕英雄传"),
    ("洪七公", "射雕英雄传"), ("欧阳锋", "射雕英雄传"), ("周伯通", "射雕英雄传"),
    ("王重阳", "射雕英雄传"), ("梅超风", "射雕英雄传"), ("陈玄风", "射雕英雄传"),
    ("杨康", "射雕英雄传"), ("穆念慈", "射雕英雄传"), ("裘千仞", "射雕英雄传"),
    ("柯镇恶", "射雕英雄传"), ("灵智上人", "射雕英雄传"), ("沙通天", "射雕英雄传"),
    ("彭连虎", "射雕英雄传"), ("梁子翁", "射雕英雄传"), ("欧阳克", "射雕英雄传"),
    ("丘处机", "射雕英雄传"), ("马钰", "射雕英雄传"),
    # 神雕侠侣
    ("杨过", "神雕侠侣"), ("小龙女", "神雕侠侣"), ("李莫愁", "神雕侠侣"),
    ("郭襄", "神雕侠侣"), ("郭芙", "神雕侠侣"), ("金轮法王", "神雕侠侣"),
    ("达尔巴", "神雕侠侣"), ("霍都", "神雕侠侣"), ("公孙止", "神雕侠侣"),
    ("裘千尺", "神雕侠侣"), ("陆无双", "神雕侠侣"), ("程英", "神雕侠侣"),
    ("耶律齐", "神雕侠侣"), ("赵志敬", "神雕侠侣"), ("尹志平", "神雕侠侣"),
    ("武三通", "神雕侠侣"), ("武敦儒", "神雕侠侣"), ("武修文", "神雕侠侣"),
    # 倚天屠龙记
    ("张无忌", "倚天屠龙记"), ("赵敏", "倚天屠龙记"), ("周芷若", "倚天屠龙记"),
    ("殷离", "倚天屠龙记"), ("小昭", "倚天屠龙记"), ("张翠山", "倚天屠龙记"),
    ("张三丰", "倚天屠龙记"), ("谢逊", "倚天屠龙记"), ("成昆", "倚天屠龙记"),
    ("灭绝师太", "倚天屠龙记"), ("韦一笑", "倚天屠龙记"), ("杨逍", "倚天屠龙记"),
    ("范遥", "倚天屠龙记"), ("宋远桥", "倚天屠龙记"), ("殷梨亭", "倚天屠龙记"),
    ("宋青书", "倚天屠龙记"), ("殷天正", "倚天屠龙记"), ("纪晓芙", "倚天屠龙记"),
    ("何太冲", "倚天屠龙记"), ("鹿杖客", "倚天屠龙记"), ("鹤笔翁", "倚天屠龙记"),
    # 天龙八部
    ("萧峰", "天龙八部"), ("乔峰", "天龙八部"), ("段誉", "天龙八部"),
    ("虚竹", "天龙八部"), ("鸠摩智", "天龙八部"), ("慕容复", "天龙八部"),
    ("王语嫣", "天龙八部"), ("段正淳", "天龙八部"), ("阿朱", "天龙八部"),
    ("阿紫", "天龙八部"), ("阿碧", "天龙八部"), ("游坦之", "天龙八部"),
    ("丁春秋", "天龙八部"), ("无崖子", "天龙八部"), ("天山童姥", "天龙八部"),
    ("李秋水", "天龙八部"), ("木婉清", "天龙八部"), ("钟灵", "天龙八部"),
    ("康敏", "天龙八部"), ("包不同", "天龙八部"), ("风波恶", "天龙八部"),
    ("段延庆", "天龙八部"), ("叶二娘", "天龙八部"), ("云中鹤", "天龙八部"),
    # 笑傲江湖
    ("令狐冲", "笑傲江湖"), ("岳不群", "笑傲江湖"), ("宁中则", "笑傲江湖"),
    ("岳灵珊", "笑傲江湖"), ("林平之", "笑傲江湖"), ("左冷禅", "笑傲江湖"),
    ("东方不败", "笑傲江湖"), ("任我行", "笑傲江湖"), ("任盈盈", "笑傲江湖"),
    ("向问天", "笑傲江湖"), ("风清扬", "笑傲江湖"), ("田伯光", "笑傲江湖"),
    ("仪琳", "笑傲江湖"), ("莫大", "笑傲江湖"), ("刘正风", "笑傲江湖"),
    ("曲洋", "笑傲江湖"), ("余沧海", "笑傲江湖"), ("方证", "笑傲江湖"),
    ("冲虚", "笑傲江湖"), ("蓝凤凰", "笑傲江湖"), ("桃谷六仙", "笑傲江湖"),
    # 鹿鼎记
    ("韦小宝", "鹿鼎记"), ("陈近南", "鹿鼎记"), ("鳌拜", "鹿鼎记"),
    ("吴三桂", "鹿鼎记"), ("海大富", "鹿鼎记"), ("洪安通", "鹿鼎记"),
    # 侠客行
    ("石破天", "侠客行"), ("石中玉", "侠客行"), ("白自在", "侠客行"),
    ("白万剑", "侠客行"), ("白阿绣", "侠客行"), ("谢烟客", "侠客行"),
    ("贝海石", "侠客行"), ("丁不三", "侠客行"), ("丁不四", "侠客行"),
    ("丁珰", "侠客行"),
    # 碧血剑
    ("袁承志", "碧血剑"), ("温青青", "碧血剑"), ("何铁手", "碧血剑"),
    ("夏雪宜", "碧血剑"), ("穆人清", "碧血剑"), ("归辛树", "碧血剑"),
    # 书剑恩仇录
    ("陈家洛", "书剑恩仇录"), ("霍青桐", "书剑恩仇录"), ("香香公主", "书剑恩仇录"),
    ("文泰来", "书剑恩仇录"), ("骆冰", "书剑恩仇录"), ("余鱼同", "书剑恩仇录"),
    # 雪山飞狐 / 飞狐外传 / 连城诀
    ("胡斐", "雪山飞狐"), ("胡一刀", "雪山飞狐"), ("苗人凤", "雪山飞狐"),
    ("苗若兰", "雪山飞狐"), ("田归农", "雪山飞狐"), ("程灵素", "飞狐外传"),
    ("袁紫衣", "飞狐外传"), ("狄云", "连城诀"), ("戚芳", "连城诀"),
    ("血刀老祖", "连城诀"),
)

_JINYONG_FAMILIES: tuple[tuple[str, str], ...] = (
    ("华山派", "笑傲江湖"), ("桃花岛", "射雕英雄传"), ("丐帮", "射雕英雄传"),
    ("星宿派", "天龙八部"), ("日月神教", "笑傲江湖"), ("明教", "倚天屠龙记"),
    ("全真教", "射雕英雄传"), ("古墓派", "神雕侠侣"), ("雪山派", "侠客行"),
    ("侠客岛", "侠客行"), ("大理段氏", "天龙八部"), ("逍遥派", "天龙八部"),
    ("峨眉派", "倚天屠龙记"), ("武当派", "倚天屠龙记"), ("少林派", "多部"),
    ("昆仑派", "倚天屠龙记"), ("崆峒派", "倚天屠龙记"), ("铁掌帮", "射雕英雄传"),
    ("神龙教", "鹿鼎记"), ("红花会", "书剑恩仇录"),
)


def _copyright_terms() -> list[Term]:
    """金庸角色 / 门派 -> Term（版权关键词，needs_review，M3 不清洗）。"""
    terms: list[Term] = []
    role_names = tuple(name for name, _ in _JINYONG_ROLES)
    terms.append(
        Term(
            rule_id="copyright_jinyong_role",
            category=Category.COPYRIGHT,
            severity=Severity.NEEDS_REVIEW,
            terms=role_names,
            rationale=(
                "金庸衍生角色名命中，商业化前需改编化（改名）或标注同人非商用"
                "（M3-4 后置；M3 不清洗，标记待处理）。"
            ),
        )
    )
    family_names = tuple(name for name, _ in _JINYONG_FAMILIES)
    terms.append(
        Term(
            rule_id="copyright_jinyong_family",
            category=Category.COPYRIGHT,
            severity=Severity.NEEDS_REVIEW,
            terms=family_names,
            rationale=(
                "金庸衍生门派名命中，商业化前需门派虚构化或标注"
                "（M3-4 后置；M3 不清洗，标记待处理）。"
            ),
        )
    )
    return terms


COPYRIGHT_TERMS: list[Term] = _copyright_terms()

#: 全部词表（预检扫描用）。license 合规校验在 [precheck](precheck.py) 单独做。
ALL_TERMS: list[Term] = (
    VIOLENCE_TERMS + SENSITIVE_TERMS + GAMBLING_TERMS + COPYRIGHT_TERMS
)


def jinyong_role_work(name: str) -> str | None:
    """查金庸角色出处小说（供 Finding context 标注版权归属）。"""
    for role_name, work in _JINYONG_ROLES:
        if role_name == name:
            return work
    for fam_name, work in _JINYONG_FAMILIES:
        if fam_name == name:
            return work
    return None


__all__ = [
    "Severity",
    "Category",
    "Term",
    "VIOLENCE_TERMS",
    "SENSITIVE_TERMS",
    "GAMBLING_TERMS",
    "COPYRIGHT_TERMS",
    "ALL_TERMS",
    "jinyong_role_work",
]
