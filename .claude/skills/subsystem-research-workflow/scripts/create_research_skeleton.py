#!/usr/bin/env python3
"""创建子系统调研目录骨架。

用法：
    python create_research_skeleton.py <topic-name> [--root <research-root>]

示例：
    python create_research_skeleton.py combat-system
    python create_research_skeleton.py social-system --root /path/to/.scratch/research
"""

import argparse
import re
from pathlib import Path


DEFAULT_ROOT = Path(".scratch/research")

BRIEF_TEMPLATE = """# {topic_title} 调研总则

> 本次调研属于 `.scratch/research/` 下研究主题。目标是为新引擎提供基于当前仓库一手源码的设计输入，同时引入现代游戏设计、玩家心理、商业化与 UGC 扩展视角进行批判性审视。

## 1. 调研目标

1. **忠实还原原始细节**：基于当前仓库一手源码，细致梳理 {topic_title} 的实现方式、数据结构、调用链与状态流转。
2. **提取设计灵感与风险警示**：从现代游戏设计、玩家心理、商业化与 UGC 创作角度，输出对新引擎可参考的方向、应避免的过时模式以及需警惕的设计陷阱。
3. **不输出 engine 接口草案**：本次调研止步于设计输入层，具体的 engine 抽象与接口设计留待后续任务单独决策。

## 2. 范围边界

### 2.1 纳入范围

- 待 Grilling 阶段确认后填写。

### 2.2 不纳入范围

- 不做行为等价验证。
- 不把 engine 侧现有实现当作正确形态反向脑补。
- 不依赖旧文档结论。
- 不输出可直接落地的 engine 代码或接口契约。

## 3. 调研团队与职责

见 `.claude/skills/subsystem-research-workflow/references/team-roles.md`。

## 4. 调研方法

### 4.1 多 Agent 并行 Workflow

- **Phase 1：并行初稿**：各角色同步阅读源码并产出指定章节初稿。
- **Phase 2：红队对抗**：横向对比验证员交叉检查，评审委员会组织质询，各角色回应并修订。
- **Phase 3：评审委员会汇总**：统一文风、消除矛盾、标注未决问题，生成最终报告。

### 4.2 资料来源优先级

1. 当前仓库根目录下源码。
2. 必要时查阅旧文档，仅作二手参考。
3. engine 侧现有实现仅作事后对照。

## 5. 输出目录结构

```
.scratch/research/{topic_dir}/
├── 00-brief/               # 本总则
├── 01-raw-findings/        # 一手源码清单、调用链、数据结构
├── 02-user-stories/        # 三层 User Stories
├── 03-engine-insights/     # 设计灵感、可选方向、风险警示
├── 04-redteam-review/      # 红队对抗记录
└── 05-synthesis/           # 评审委员会最终汇总
```

## 6. 关键约束

- **基于一手资料**：所有结论必须能从当前仓库源码中找到证据。
- **全局与细节兼顾**：既要有宏观脉络，也要有代表性实例细节。
- **现代视角批判**：对过时、不符合当代玩家习惯或商业化潜力的设计显式标注。
- **User Stories 完整**：覆盖所有可触达路径。
"""


def to_title(topic: str) -> str:
    """将 kebab-case 主题名转为可读标题。"""
    return " ".join(word.capitalize() for word in topic.replace("_", "-").split("-"))


def find_next_index(root: Path) -> int:
    """根据已有主题目录确定下一个序号。"""
    if not root.exists():
        return 1
    indices = []
    for item in root.iterdir():
        if item.is_dir():
            match = re.match(r"^(\d+)-", item.name)
            if match:
                indices.append(int(match.group(1)))
    return max(indices, default=0) + 1


def create_skeleton(topic: str, root: Path) -> Path:
    """创建调研目录骨架并返回目录路径。"""
    next_index = find_next_index(root)
    topic_dir = root / f"{next_index:02d}-{topic}"
    topic_dir.mkdir(parents=True, exist_ok=False)

    subdirs = [
        "00-brief",
        "01-raw-findings",
        "02-user-stories",
        "03-engine-insights",
        "04-redteam-review",
        "05-synthesis",
    ]
    for subdir in subdirs:
        (topic_dir / subdir).mkdir(parents=True, exist_ok=False)

    brief_path = topic_dir / "00-brief" / "brief.md"
    brief_content = BRIEF_TEMPLATE.format(
        topic_title=to_title(topic),
        topic_dir=topic_dir.name,
    )
    brief_path.write_text(brief_content, encoding="utf-8")

    return topic_dir


def main():
    parser = argparse.ArgumentParser(description="创建子系统调研目录骨架")
    parser.add_argument("topic", help="主题名，例如 combat-system")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"研究根目录，默认 {DEFAULT_ROOT}",
    )
    args = parser.parse_args()

    topic = args.topic.strip().lower().replace(" ", "-")
    topic_dir = create_skeleton(topic, args.root)
    print(f"Created: {topic_dir}")
    print(f"Brief:   {topic_dir / '00-brief' / 'brief.md'}")


if __name__ == "__main__":
    main()
