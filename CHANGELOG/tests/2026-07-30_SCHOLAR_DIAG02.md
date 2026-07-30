# 2026-07-30 科洛尼斯学术特 DIAG02

## 目标

修正 `HOTA_NEW_HERO_V1.2_SCHOLAR_DIAG01` 在“单人游戏→新建场景”阶段的提前闪退，同时保持同一原生学术入口诊断与同一套高级学术图标，以单变量验证新增 PE 节是否为根因。

## 构建

- 构建名：`HOTA_NEW_HERO_V1.2_SCHOLAR_DIAG02`
- 正式基线：`HOTA_NEW_HERO_V1.14`
- 基线 ZIP SHA-256：`8077624b88dc83762b77c34cb8645a4907cf2f3bc0538ae0684da713edd4ed85`
- DIAG02 ZIP SHA-256：`24971a44282230e3fef59c87938b3520a4b810c4f3bce4119cb19af1a9b97ce6`
- 运行日志：`hota_scholar_diag02.bin`
- 正式发布：否

## 与 DIAG01 的唯一代码布局差异

DIAG01 新增第六个 `.schdg` 节；DIAG02 完全取消该节，不改变来源 EXE 文件大小、节数量或 `SizeOfImage`。

正式 V1.14 的既有 `.luck3` 节 SHA-256 为：

`e3be451a919ae0d419320cc2ca000121a5cbc44fcbb3000dddecc74e6d9d671f`

其中 `0x000..0x7FF` 包含正式固定幸运 +3、首次攻击幸运和战斗状态代码，DIAG02 逐字节保留；`0x800..0xFFF` 在标准版和 HD 版来源中均经验证为全零，诊断代码只写入该尾部。

```text
学术入口：  0x004A25B0
原始/回滚：55 8B EC 6A FF 68 78 B7 62 00
替换：      E9 CB 53 24 00 90 90 90 90 90
诊断入口：  0x006E7980
继续地址：  0x004A25BA
```

标准版和 HD 版使用相同的 `.luck3` 诊断尾部，SHA-256 为：

`9d435bca3842d51024f7653c139eac4de3e1bd3301adb957e6bfb21ced199bf9`

## 保留内容

- 科洛尼斯 ID `24` 与原生学术函数入口不变；
- 高级学术图标仍为第 56 帧 `skill18c.pcx` / `skl3218c.pcx`；
- `UN44.DEF` / `UN32.DEF` 仍只替换科洛尼斯第 24 帧；
- 标准界面仍增加 `Data/HPS024DR.PCX`；
- 本阶段仍不修改实际法术传授结果。

## 独立验证

- 两个来源 EXE 固定哈希：通过；
- EXE 文件大小保持 `2936832` 字节：通过；
- 节数量保持 `5`、`SizeOfImage` 保持不变：通过；
- `.luck3` 正式前 `0x800` 字节逐字节保留：通过；
- 标准版 / HD 版诊断尾部一致：通过；
- Hook 源字节、目标和原始序言重放：通过；
- PE 校验和与完整 EXE 回滚：通过；
- D32F 单帧隔离、PCX 几何和图标回滚：通过；
- ZIP CRC 与成员集合：通过。

## 启动冒烟

候选包临时覆盖到本地游戏后，`h3hota.exe` 成功建立主窗口，标题为 `Heroes of Might and Magic III: Horn of the Abyss`；随后所有本地文件按覆盖前哈希完整恢复。

## 运行验收

等待用户确认：

1. “单人游戏→新建场景”不再闪退；
2. 科洛尼斯与己方英雄会面后生成 `hota_scholar_diag02.bin`；
3. 高级学术图标显示正常。
