# HOTA_NEW_HERO_V1.03 构建与验收记录

- 来源正式版：`HOTA_NEW_HERO_V1.02`
- 来源 ZIP SHA-256：`8ed7849fb7251ed44124bf86328f23952e6e6341cc664872beb1b62cdd31375a`
- 输出 ZIP SHA-256：`11b16774cf8167fa1f4d6e288167bc1298ccd6fb22e84ce588f178253ed8e7b9`
- F6 Direct：`H = floor(((11L + 10P + 19) × (clamp(n,1,7) + 11)) / 12) + 10 × max(0, clamp(w,0,3) - 1)`。
- `P=1、L=1`、无/初级水系时，1级兵为 `40`，7级兵为 `60`。
- 水系数值加成为无/初级 `+0`、中级 `+10`、高级 `+20`，在兵种倍率取整后相加；原版单体/群体范围规则保持不变。
- 活体治疗、治疗溢出复活和全灭尸体复活统一使用同一个最终总量公式。
- `HotA.dat` 的 `Heroes\hero170.str` 仅把第二技能类型从幸运术 ID `9` 改为水系魔法 ID `16`；初级等级、智慧术、魔法书和初始治愈术不变。
- 输出 `HotA.dat` SHA-256：`bcabc72b9511b3d6787ba23f8bc3b1fd2df729080ec4fc1e64a5ea070d240517`。
- 既有治愈复活动画、音效、永久性、资格限制和战斗日志顺序均原样保留。

## EXE 哈希

| 文件 | SHA-256 |
|---|---|
| `h3hota.exe` | `a85c4db22c3afe06d3c09c15e832a3f4dbb3de61b873541e1985ac208eabee9f` |
| `h3hota HD.exe` | `dce0882d870fa75f14d05891b261b8bfd978facdba2f12d005b9cc4d9299b6dd` |
