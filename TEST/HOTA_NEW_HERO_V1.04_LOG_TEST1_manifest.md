# HOTA_NEW_HERO_V1.04_LOG_TEST1 构建与静态验收记录

- 来源正式版：`HOTA_NEW_HERO_V1.03`
- 来源 ZIP SHA-256：`11b16774cf8167fa1f4d6e288167bc1298ccd6fb22e84ce588f178253ed8e7b9`
- 输出 ZIP SHA-256：`55a0ccbd23fcc6cfd9af4134d29d49f7073e821ea1460136e4a830da89c0cf82`
- 魔法书路径未修改。
- 日志顺序：治愈施放提示 → 每个有效单位的治愈值 → 原版复活提示。
- 单体目标立即追加治愈值；群体目标最多缓存 14 队，并在原版治愈施法提示落盘后统一追加。
- 治愈值使用 V1.03 已有 F6 Direct 总量；公式、HotA.dat 与两个 HeroSpec 语言档案逐字节保留。
- 纯静态检查不能证明运行时稳定，本候选版仍需实机验收。

## EXE 哈希

| 文件 | SHA-256 |
|---|---|
| `h3hota.exe` | `cb5b7d82494bb7a4a3012049e812e392cea212aefc8cf81e0c0ad7389100ccce` |
| `h3hota HD.exe` | `e8eec29e09a46d21ebcd38b583c38dca90af7bd3dad89d59dc1658256cab6077` |
