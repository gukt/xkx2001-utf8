# Workflow 脚本模板

本文件提供一个可直接改编的 JavaScript Workflow 脚本结构。使用时需要根据具体子系统替换：

- `<RESEARCH_DIR>`：实际调研目录，例如 `/home/user/project/.scratch/research/02-combat-system`
- `<BRIEF_PATH>`：`00-brief/brief.md` 路径
- `<SOURCE_FILES>`：子系统相关的 LPC 源码文件清单
- `<ROLES>`：实际启用的角色与对应产出文件

## 脚本结构

```javascript
export const meta = {
  name: '<topic>-research',
  description: '多 Agent 并行调研 <topic> 子系统',
  phases: [
    { title: 'Phase 1: 并行初稿' },
    { title: 'Phase 2: 红队对抗' },
    { title: 'Phase 3: 评审委员会汇总' },
  ],
};

const RESEARCH_DIR = '<RESEARCH_DIR>';
const BRIEF_PATH = `${RESEARCH_DIR}/00-brief/brief.md`;

// Phase 1: 并行初稿
phase('Phase 1: 并行初稿');

const p1Agents = [
  {
    label: '<角色名>',
    prompt: `你是本次调研的 <角色名>。请基于 <SOURCE_FILES> 进行调研。

输出要求：
1. 使用 Write 工具写入文件：${RESEARCH_DIR}/<output-path>.md
2. 内容结构：...
3. 每条结论必须标注证据来源（文件路径 + 函数/对象名）。
4. 先阅读 ${BRIEF_PATH} 了解调研总则。

最终回复只需确认文件已写入，并给出 3-5 句话摘要。`,
  },
  // ... 更多角色
];

await parallel(p1Agents.map(a => () => agent(a.prompt, {
  label: a.label,
  phase: 'Phase 1: 并行初稿',
  effort: 'high',
})));

log('Phase 1 初稿完成');

// Phase 2: 红队对抗
phase('Phase 2: 红队对抗');

const p2Agents = [
  {
    label: '<红队角色名>',
    prompt: `你是红队中的 <角色名>。请阅读 Phase 1 已产出的文件：...

输出要求：
1. 使用 Write 工具写入文件：${RESEARCH_DIR}/04-redteam-review/<output>.md
2. ...
3. 每条质疑必须具体，并引用被质疑的文件与段落。`,
  },
  // ... 更多红队角色
];

await parallel(p2Agents.map(a => () => agent(a.prompt, {
  label: a.label,
  phase: 'Phase 2: 红队对抗',
  effort: 'high',
})));

log('Phase 2 红队对抗完成');

// Phase 3: 评审委员会汇总
phase('Phase 3: 评审委员会汇总');

const synthesisPrompt = `你是本次调研的评审委员会。请阅读 Phase 1 和 Phase 2 的所有产出文件：...

输出要求：
1. 使用 Write 工具写入文件：${RESEARCH_DIR}/05-synthesis/final-report.md
2. 文件结构：执行摘要、范围与方法、现状总览、关键发现、User Stories 汇总、设计建议、未决问题、附录。
3. 统一文风，消除矛盾。
4. 对红队质疑给出裁决。`;

await agent(synthesisPrompt, {
  label: '评审委员会汇总',
  phase: 'Phase 3: 评审委员会汇总',
  effort: 'xhigh',
});

log('Phase 3 评审委员会汇总完成');

return { status: 'completed', researchDir: RESEARCH_DIR };
```

## 关键设计点

1. **让 agent 自己写文件**：每个 agent 的 prompt 明确要求使用 Write 工具写入指定路径。
2. **Phase 1 使用 parallel**：所有初稿角色同时运行。
3. **Phase 2 依赖 Phase 1 文件**：由于 `parallel` 是 barrier，Phase 1 全部完成后才进入 Phase 2。
4. **Phase 3 单 agent 汇总**：由一个高 effort agent 统一审阅并产出最终报告。
5. **失败处理**：Workflow 完成后检查失败 agent，单独重新运行补全。

## 常见角色 prompt 模板

### LPC 源码考古员

```
你是 LPC 源码考古员。请对 <topic> 相关源码做完整盘点。
必须覆盖：<SOURCE_FILES>
输出：${RESEARCH_DIR}/01-raw-findings/source-inventory.md
包含：总体分布、关键文件清单表、关键词索引、待深入文件清单。
每条结论标注证据来源。
```

### 玩法切片策划

```
你是玩法切片策划。请从 <topic> 源码中挑选 4-6 类代表性玩法，做成玩家视角 + 数据流切片。
输出：${RESEARCH_DIR}/01-raw-findings/gameplay-slices.md
同时产出玩家视角 User Stories：${RESEARCH_DIR}/02-user-stories/player-stories.md
```

### 现代任务玩法设计师

```
你是现代任务玩法设计师。请对标当前主流游戏，评估 <topic> 的当代可玩性与过时风险。
输出：${RESEARCH_DIR}/03-engine-insights/modern-design-review.md
```

## 注意事项

- 不要把完整源码清单放进 prompt，只列出关键文件路径。
- 每个 agent 的 prompt 末尾要求"最终回复只需确认文件已写入，并给出 3-5 句话摘要"，避免 agent 在最终回复中重复全文。
- 如果某个 agent 经常 429 失败，可以降低并行度或在 Phase 1 中分批运行。
