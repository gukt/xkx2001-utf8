Type: grilling
Status: resolved

## Question

上一轮方案定的"六条收缩约束"(见 [docs/archive/xkx-arch/README.md](../../../docs/archive/xkx-arch/README.md)):

1. 不考虑分布式架构(验证 UGC 成立前)
2. 运维观测后置
3. 不考虑分布式网关(单机 1000 在线 + 100 并发)
4. 纯 Python(暂不考虑 Rust/Go)
5. 内存数据 + 本地 JSON 定时存档
6. (原第 6 条是"三个开放架构问题已裁决",随旧目标一并作废)

这些约束是为"全量复刻"目标定的,新目标(核心引擎 + UGC + 轻量题材包 MVP)下是否延续?还是要重新评估承载/技术栈假设?

## Answer

逐条重新评估(不盲目继承),结果:五条**全部延续**——它们本质是"先单机跑通、别过早复杂化"的通用工程判断,与"复刻不复刻"无关,新目标下依然成立:

1. 不考虑分布式架构(验证 UGC 成立前)——成立
2. 运维观测后置(仅基础 OpenTelemetry + Grafana,不上 K8s/Helm)——成立
3. 不考虑分布式网关,单机承载——成立,且具体数字维持原值:**1000 在线 + 100 并发**(不重新定数字,不推迟到 ticket 06)
4. 纯 Python(暂不考虑 Rust/Go)——成立
5. 内存数据 + 本地 JSON 定时存档(不上 PG/Redis)——成立

注意:约束 3 的"1000 在线 + 100 并发"是 MVP 阶段的单机承载上限,不代表 [06-scaling-commercialization-support-points](06-scaling-commercialization-support-points.md) 里"未来承载目标"的规模——06 讨论的是更远期、可能超出单机的目标,两者不是同一个数字。
