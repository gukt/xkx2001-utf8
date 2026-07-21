# M2 MVP 场景房间键清单（Wave 4 协调）

> 22/23 共用 `yangzhou_*`；25 连接扬州东门 ↔ 少林山门；华山 ↔ 扬州留给 26。
> 场景文件：`engine/data/m2_mvp_scene.yaml`（单文件，随票累加）。

## 华山村（21）`huashan_*`

| 键 | 用途 |
|---|---|
| `huashan_birth` | 出生点 / 村口 |
| `huashan_guide` | 教程向导 |
| `huashan_training` | 教学木桩 + `NoDeathZone` |

## 扬州枢纽+城门（22）`yangzhou_*`

| 键 | 用途 |
|---|---|
| `yangzhou_guangchang` | 中央广场（枢纽） |
| `yangzhou_beidajie` | 北大街 |
| `yangzhou_nandajie` | 南大街 |
| `yangzhou_dongdajie` | 东大街 |
| `yangzhou_xidajie` | 西大街 |
| `yangzhou_beimen` | 北门 |
| `yangzhou_nanmen` | 南门 |
| `yangzhou_dongmen` | 东门（预留 east → 官道，25 接） |
| `yangzhou_ximen` | 西门（`count:2` 同名官兵） |

## 扬州商业+马厩（23）`yangzhou_*`（不与 22 冲突）

| 键 | 用途 | 挂接 |
|---|---|---|
| `yangzhou_kedian` | 客栈 | 北大街 |
| `yangzhou_qianzhuang` | 钱庄 | 东大街 |
| `yangzhou_datiepu` | 打铁铺 | 西大街 |
| `yangzhou_biaoju` | 镖局 | 南大街 |
| `yangzhou_wumiao` | 武庙 | 广场 |
| `yangzhou_chaguan` | 茶馆 | 东大街 |
| `yangzhou_stable` | 马厩 | 西门内侧 / 西大街 |

## 少林寺（24）`shaolin_*`

| 键 | 用途 |
|---|---|
| `shaolin_shanmen` | 山门（`EntryGuard`；预留 west → 官道，25 接） |
| `shaolin_guangchang` | 广场 |
| `shaolin_damoyuan` | 达摩院 |
| `shaolin_cangjingge` | 藏经阁 |
| `shaolin_wuchang` | 武场（学技能） |

## 野外 / 官道 / 渡口（25）

| 键 | 用途 |
|---|---|
| `road_yz_east` | 扬州东门外官道（接 `yangzhou_dongmen`） |
| `wild_edge` | 野外边缘（高 `Terrain.cost`） |
| `wild_forest` | 野外遭遇区（aggro 山贼） |
| `wild_thicket` | 野外深处 |
| `ferry_west` | 西岸渡口 |
| `ferry_east` | 东岸渡口 |
| `road_shaolin` | 少林方向官道（接 `shaolin_shanmen`） |
