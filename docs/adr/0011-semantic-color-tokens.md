---
Status: accepted
---

# 内容着色用语义色 token，禁止 ANSI / LPC 色宏进 YAML

Pre-M4 引擎房间保真 grill（2026-07-22）拍板：房间风景、`long` 等创作者可见文本的着色，以**语义色 token** 为权威写法；引擎可校验允许色名，由客户端（终端 CLI→ANSI、Web→CSS 等）渲染最终样式。YAML 与服务端权威输出**禁止**嵌入原始 ANSI 转义序列，也**禁止** LPC 色宏名（如 `HIG`/`HIR`/`NOR`）。Token 语法定为 `<c:name>…</c>`；本波允许色名仅 `red`/`green`/`yellow`/`blue`/`magenta`/`cyan`/`white`（无 `black`、无背景/闪烁/粗体 token、不支持嵌套）。闭合 `</c>` 即复原，不另设 `NOR` token。官方 CLI：TTY（或 `--color`）时将七色映为亮色 ANSI；管道/测试默认剥 token 出纯文本。动机：题材包需可被多客户端消费，ANSI 绑死 Telnet/终端且难校验、难迁移；服务端定义色词汇表，不负责最终像素。由 [.scratch/pre-m4-engine-room-fidelity/](../../.scratch/pre-m4-engine-room-fidelity/) 落地。

## Considered Options

- **A（采纳）**：语义 token + 客户端渲染；YAML/服务端不含 ANSI / LPC 色宏。
- **B**：服务端直接出 ANSI——CLI 简单，Web 与多客户端要剥码，内容格式绑死终端。
- **C**：本波不做色——与已定硬门闩冲突。
