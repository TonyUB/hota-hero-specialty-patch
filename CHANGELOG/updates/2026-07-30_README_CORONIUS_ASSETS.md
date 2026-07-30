# README 克洛尼斯素材更新（2026-07-30）

## 更新内容

- 为中英文 README 的克洛尼斯条目增加英雄头像、学术特长图标、魔法书图标和初始法术“屠戮”图标。
- 全部图标统一为 72 像素显示高度，并沿用现有英雄条目的排版与间距。
- 英雄头像取自游戏资源 `HPL024DR.PCX`。
- 学术特长图标取自 `Secskill.def` 的高级学术帧 `skill19c.pcx`，不是高级土系魔法图标。
- 屠戮图标取自 `spells.def` 的 `Sp54Slay.pcx`。

## 对应文件

- `assets/portraits/coronius.png`：58×64，SHA-256 `46bbd6ce687d746cf4e843230f33ada2ddf41959d246bbb13f04073ad7b04151`
- `assets/specialties/coronius.png`：44×44，SHA-256 `bd58a1047f3547db997e39d94a60ad2aca9f3846f27c5f2d135f1d4172b9a2e2`
- `assets/spells/slayer.png`：78×65，SHA-256 `d4e00a2f8cb0fc0293bab55b6ce9814227092d682f3352f05e7bf6bf2633b1f3`

## 经验总结

- 二级技能图标必须按 `Secskill.def` 的实际帧名核验，不能仅凭相邻帧序号或视觉印象推断。
- D32F/DEF 帧替换时应保留原帧元数据，只替换解码后的像素数据，避免图标方向、调色板或载入行为异常。
