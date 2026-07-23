---
Status: resolved
---

# 03 — A4 房间风景 details 升级（K2 + U + S1 + N1）

**What to build:** `details` 键模型升级为「无空格英文 id → `{text, aliases}`」（K2）；创作者仍在 `long`/`details.*.text` 里手写纯文本 `石狮(shi shi)`（U），不引入 `<d:…>` 等标签；引擎按分隔符归一（N1：`shi shi`=`shi_shi`=`shi-shi`=`shishi` 同一骨架）匹配 `look 石狮`/`look shi shi`/`look ss`/`look shi_shi`/`look shi-shi`/`look shishi`；新增文本扫描辅助，仅当 `名(id)` 能解析到本房已登记的某条 details 时才判定命中（S1 安全阀，未登记则当纯文本，供客户端高亮/可点判定用，不误伤纯文本括号）；`details.*.text` 内嵌套的风景（如「石球」）可被 `look` 到，前提是它在同一房间 `details` 里被扁平登记（不是 text 内联子树）。旧「键→纯字符串」写法提供兼容/迁移路径。

对应 spec：`.scratch/polishing/spec.md` §A4（User Stories 10–15；Implementation Decisions「A4」）；权威规格见 [CONTEXT.md](../../../CONTEXT.md)「房间风景」词条。

**Blocked by:** None — 可立即开始。

- [x] `components.py`：`RoomDetails` 从 `dict[str, str]` 升级为 `dict[str, DetailEntry]`；`DetailEntry` 含 `text: str` + `aliases: tuple[str, ...]`。
- [x] `scene_loader.py`：`details` 段解析支持新形状 `{ <id>: { text, aliases? } }`；旧写法 `{ <键>: <纯字符串> }` 自动转换为 `{text: 值, aliases: [键]}`（双轨兼容，选定方案：自动转换而非强制迁移官方范本——落地时如与本决策冲突可在实现票 Comments 里记录变更理由）。
- [x] `look` 匹配逻辑扩展：键或任一 alias 精确匹配（不做中文分词），且做 N1 分隔符归一（空格/`_`/`-`/全粘连视为同一骨架）；look id 大小写不敏感。
- [x] 新增文本扫描辅助函数：扫描 `long`/`details.*.text` 里 `名(id)` 形态，仅当 `id`（经 N1 归一）命中本房已注册 details 时返回「可 look」判定，供未来客户端/CLI 高亮消费；未登记形态原样返回纯文本判定。
- [x] 嵌套 look：`details.*.text` 内的 `名(id)` 同样走 S1 扫描；目标必须在同一房间 `details` 扁平登记才可 `look` 到。
- [x] `test_room_details.py` 扩展：新形状加载、别名归一矩阵（六种拼写变体命中同一条）、S1 扫描高亮判定（登记/未登记两种输入）、嵌套 look、旧写法兼容加载。
- [x] S2 契约测试：新字段解析进组件而非落进 `extension_data`（`assert "details" not in extras` 模式，参考 `test_room_details.py::TestRoomDetailsLoad`）。
- [x] `just test` 全绿。

## Comments

**实现摘要（2026-07-23）**

- **字段名（钉死）**
  - `DetailEntry.text: str`
  - `DetailEntry.aliases: tuple[str, ...]`
  - `RoomDetails.entries: dict[str, DetailEntry]`（主键推荐无空格英文 id）
- **加载**：解析实际在 `capabilities._parse_room_details`（房间能力注册表，非 `scene_loader` 直写）。旧「键→纯字符串」→ `DetailEntry(text=值, aliases=(键,))`；K2 形状要求主键匹配 `^[A-Za-z][A-Za-z0-9_]*$`。官方范本未强制迁移，双轨兼容。
- **N1 / look**：`mud_engine.room_details.normalize_detail_token` / `resolve_detail`；look id `casefold`；`parsing._parse_look` 目标改为 `" ".join(args)` 以支持空格拼音别名。
- **S1 扫描签名（钉死，供客户端）**

```python
@dataclass(frozen=True)
class DetailMention:
    display: str
    raw_id: str
    start: int
    end: int
    lookable: bool
    detail_key: str | None

def scan_detail_mentions(text: str, details: RoomDetails) -> list[DetailMention]: ...
def resolve_detail(details: RoomDetails, token: str) -> DetailEntry | None: ...
def normalize_detail_token(token: str) -> str: ...
```

  扫描先找 `(id)`，再以已登记键/别名最长后缀回推 `display`；未登记则启发式短名（连续汉字取末两字）。**不**从 long 自动登记 aliases。
