# HOTA_NEW_HERO_V1.04 构建与静态验收记录

- 来源正式版：`HOTA_NEW_HERO_V1.03`
- 来源 ZIP SHA-256：`11b16774cf8167fa1f4d6e288167bc1298ccd6fb22e84ce588f178253ed8e7b9`
- 输出 ZIP SHA-256：`60a2744a00e4759d4115c3e51c1aa434ae93d6324949349a923ab50931b0e7ad`
- 魔法书路径未修改。
- 日志顺序：治愈施放提示 → 每个有效单位的治愈值 → 原版复活提示。
- 单体目标立即追加治愈值；群体活体与尸体入口均记录，最多缓存 14 队，并在原版治愈施法提示落盘后统一追加。
- F6 Direct 数学公式不变；目标等级改为 `clamp(*(stack+0x78)+1,1,7)`，对应 H3CreatureInformation 的 0–6 级字段。
- 两个 LOD 内 HeroSpec 逐字节保留；HD 中文 loose HeroSpec 与 HotA.dat 的阿斯特拉结构化说明均更新为新文案。
- 新增 HotA.dll 的定点分发器，仅对英雄 ID 25/170 的治愈特长详情表启用 F6 Direct 数值。
- TEST2 与 UI TEST3 的实机验收全部通过；正式版沿用通过验收的运行字节。

## EXE 哈希

| 文件 | SHA-256 |
|---|---|
| `h3hota.exe` | `aa7933be741576df85dc421c9fc6cef14a213df67c4a191d011e8f9692da96e0` |
| `h3hota HD.exe` | `91ffc17974091e0f7c1f3ac5fd95bd3259167f3621eecaee64b6da68062e318c` |
| `HotA.dll` | `bfcd3c314da10808b5a2962b1b45a88b31c33984a36834acbe7396073ced3b22` |
