# ADR-0009：原版侠客行 FluffOS driver 可运行性验证

- 状态：已采纳（阶段 0 任务 2 前置发现）
- 日期：2026-07-11
- 阶段：0 任务 2（FluffOS Linux 编译可行性）
- 关联 dissent：[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 4（规则冲突语义漂移，"靠基线测试断言原 LPC 命中行为"）；[04](../xkx-arch/04-迁移路径与避坑清单.md) §六不做清单"录制运行中 LPC 命令流为 golden trace"

## 背景

[04](../xkx-arch/04-迁移路径与避坑清单.md) §六不做清单原列："录制运行中 LPC 命令流为 golden trace | 旧系统在当前 Linux 不可运行 | 单元级行为规约 + 一次性 golden trace"。该假设认为旧 driver 无法在当前环境运行，因此行为等价验证只能靠从代码提取的单元级行为规约，无法录制运行时 golden trace。

[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 4 明确："规则冲突语义漂移--LPC 靠注册顺序隐式覆盖触发器命中，层1 若优先级/deny-wins 语义未严格对齐，迁移后 533 valid_leave 命中行为会漂移。靠基线测试断言原 LPC 命中行为。"但"基线测试"若无法运行旧系统，只能从代码静态推断命中行为，覆盖面与置信度受限。

## 发现

仓库根目录存在 `driver` 可执行文件（1.1MB）。经验证：

1. **实际是 FluffOS 3.0.20170907**（非 config.xkx 头部注释的 MudOS 0.9.20--该注释是旧模板未更新）。
2. **Mach-O 64-bit x86_64** 二进制，在 arm64 macOS 上通过 Rosetta 2 运行。
3. **libevent 版本不匹配**：driver 链接 `libevent-2.1.6.dylib`，当前 Homebrew 装的是 `2.1.7`。建符号链接 `libevent-2.1.6.dylib -> libevent-2.1.7.dylib` 解决（ABI 兼容）。
4. **成功启动**：`arch -x86_64 ./driver config.xkx` 加载全部 daemon（securityd/virtuald/logind/rankd/commandd/chinesed/emoted/aliasd/fingerd/channeld/natured/weapond/dns_master/ftpd/http），输出 "Accepting connections on 0.0.0.0:8888" + "Initializations complete."
5. **可交互**：`nc 127.0.0.1 8888` 显示完整登录界面（标题画面 + GB 编码 + 登录提示）。

启动日志有少量 `securityd.c` 的 "Unused local variable" warning + "Object cannot be loaded during compilation" 执行时段错误（simul_efun wizardp() 在 securityd 编译完成前被调用），但不阻止 driver 最终完成初始化。这些错误属于编译期加载顺序问题，需后续调查是否影响特定功能路径。

## 决策

1. **修正 04 文档假设**："旧系统在当前 Linux 不可运行"修正为"旧系统（FluffOS 3.0 x86_64 macOS 二进制）可通过 Rosetta 2 在当前 arm64 macOS 运行"。04 §六不做清单"录制运行中 LPC 命令流"项的"理由"列需更新，但该项仍保留在不做清单中（见下文"不做全量 golden trace 录制"）。

2. **阶段 0 任务 2 结论**：现有二进制可运行，无需从源码编译 FluffOS。若未来需要 arm64 原生或 Linux 部署，可从 FluffOS 源码编译（3.0 版本源码公开），但当前不投入。

3. **golden trace 定位为辅助验证手段**，非主线：
   - **主线不变**：单元级行为规约（从代码提取输入输出契约 + hypothesis 属性测试）仍是 greenfield 主门禁，不依赖运行旧系统。原因：golden trace 是行为快照（what），规约是行为契约（why）；greenfield 重写需理解 why 而非复制 what。
   - **辅助**：对 dissent 4 关注的 533 valid_leave 命中行为、combat 七步管线副作用交织时序等"难以从代码静态推断"的路径，可录制旧系统运行时 golden trace 作为基线测试，提升行为等价验证置信度。

4. **不做全量 golden trace 录制**：不录制全量 LPC 命令流（8412 文件不可穷尽），仅在单元规约不足处定点录制。理由：全量录制成本高且复制旧系统而非理解规约，违反 greenfield 原则。

## 运行方法

```bash
# 前置：libevent 符号链接（一次性）
ln -sf libevent-2.1.7.dylib /usr/local/opt/libevent/lib/libevent-2.1.6.dylib

# 启动（Rosetta 2）
cd /path/to/xkx2001-utf8
arch -x86_64 ./driver config.xkx

# 连接（另一终端）
nc 127.0.0.1 8888
```

已知问题：driver 进程 kill -9 后可能处于 UE 状态（不可中断等待 + 正在退出），端口 8888 暂不释放。需等待自行退出或换端口（修改 config.xkx `port number`）。

## 后续

- 阶段 0 任务 2（FluffOS 编译可行性）标记完成：结论"现有二进制可运行，无需编译"
- 阶段 0 任务 1（LPC 规格提取管线）可结合运行时验证：对难以静态判断的路径，运行旧系统录制 golden trace 辅助
- 后置：调查 securityd 编译期加载顺序错误是否影响特定功能路径（可能影响 securityd 相关的权限校验路径录制）

## 结果

- 阶段 0 任务 2 提前完成（现有二进制可运行，无需编译 FluffOS）
- 04 §六不做清单"录制运行中 LPC 命令流"项理由修正，但该项保留（不做全量录制，仅定点辅助）
- 为 dissent 4（规则冲突语义漂移）的"基线测试断言原 LPC 命中行为"提供了运行时验证路径
