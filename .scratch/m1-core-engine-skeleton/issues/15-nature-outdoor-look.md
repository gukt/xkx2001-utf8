# 15 - 户外房间文案动态拼接（B3）

**What to build:** `Description` 加 `outdoors` 字段；`look` 渲染时户外房间追加当前时辰（及天气，若已有）desc_msg，室内房间不追加。玩家在户外能感知世界随时辰演化。

**Blocked by:** 14 - 需要 Nature 谓词/desc_msg 查询。

**Status:** ready-for-agent

- [ ] `Description` 组件有 `outdoors: bool` 字段（默认 false）
- [ ] 场景 YAML 房间可声明 `outdoors: true`
- [ ] `look` 户外房间消息含当前时辰 desc_msg
- [ ] `look` 室内房间不追加 Nature 文案
- [ ] 推进相位后户外 `look` 文案随之变化
- [ ] 现有测试全绿（不回归）
