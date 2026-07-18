Type: grilling
Status: resolved

## Question

UGC/DSL 创作层的 MVP 设计,要不要直接继承旧方案的"DSL 四层 + Agent 协作创作"设计(见 [docs/archive/xkx-arch/03-DSL-UGC与Agent协作.md](../../../docs/archive/xkx-arch/03-DSL-UGC与Agent协作.md)),还是完全从零重新设计?

## Answer

不直接沿用旧方案的四层结构。基于新目的地(题材无关引擎 + 轻量题材包 MVP)重新设计,但旧方案与 [01-关键修正与避坑清单.md](../../../docs/archive/xkx-arch/_archive/01-关键修正与避坑清单.md) 中 UGC 相关的教训(例如"§23 UGC 脚本用受限 Python 非 WASM"、"§H WASM 定位为无状态计算单元"、"§21 inquiry 是交易状态机非对话树")作为重要参考输入,不能忽略这些已经用真实代码验证过的坑。
