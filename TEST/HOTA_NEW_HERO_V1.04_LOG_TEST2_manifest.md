# HOTA_NEW_HERO_V1.04_LOG_TEST2 构建与静态验收记录

- 来源正式版：`HOTA_NEW_HERO_V1.03`
- 来源 ZIP SHA-256：`11b16774cf8167fa1f4d6e288167bc1298ccd6fb22e84ce588f178253ed8e7b9`
- 输出 ZIP SHA-256：`a1350b5cd8733b6dd69ade9de0689611319339cb39389dfe50cc4865ecc9cb82`
- 魔法书路径未修改。
- 日志顺序：治愈施放提示 → 每个有效单位的治愈值 → 原版复活提示。
- 单体目标立即追加治愈值；群体活体与尸体入口均记录，最多缓存 14 队，并在原版治愈施法提示落盘后统一追加。
- F6 Direct 数学公式不变；目标等级改为 `clamp(*(stack+0x78)+1,1,7)`，对应 H3CreatureInformation 的 0–6 级字段。
- HotA.dat 与两个 LOD 内 HeroSpec 逐字节保留；新增 HD 中文资源包的 loose HeroSpec 覆盖文件，以修正运行时仍显示原版说明的问题。
- 纯静态检查不能证明运行时稳定，本候选版仍需实机验收。

## EXE 哈希

| 文件 | SHA-256 |
|---|---|
| `h3hota.exe` | `e44ceb0b5157f8e6109dd53631cce774405513f68b8249ff9c3e2636e78902e7` |
| `h3hota HD.exe` | `5ba365935ef13a507b15893dfe898387abeb15ea538db3c217d92ec6046857dc` |
