# xkx - 侠客行 MUD 现代化重构引擎

greenfield Python 重写《侠客行》LPC MUD。LPC 是规格源（只读参考，在仓库根目录的 `adm/ cmds/ d/ kungfu/ ...`），本引擎从零按规格实现，行为等价验证。

**当前阶段**：阶段 -1 垂直切片平台验证（2-3 月，★ 最高优先级）。详见 [../PROGRESS.md](../PROGRESS.md) 与 [架构文档](../docs/xkx-arch/README.md)。

## 开发

```bash
# 安装 dev 依赖
pip install -e ".[dev]"

# 跑测试
pytest

# lint / format
ruff check .
ruff format .
```

## 布局

- `src/xkx/`：引擎源码
- `tests/`：测试（pytest + hypothesis）
- [../docs/adr/](../docs/adr/)：实现期决策日志（ADR，仓库级）

> 阶段 -1 遵循"收敛优先"，子目录（combat/dsl/ecs 等）按第一个垂直切片规划后按需建立，不预先铺开。
