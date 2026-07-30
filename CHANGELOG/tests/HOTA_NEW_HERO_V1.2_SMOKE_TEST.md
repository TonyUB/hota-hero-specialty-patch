# HOTA_NEW_HERO_V1.2 正式启动门槛

## 范围

使用正式构建目录临时覆盖测试游戏根目录中的两个 EXE 与两份 D32F 特长图标容器，启动标准 `h3hota.exe`，等待 12 秒并检测真实主窗口，随后恢复全部原文件。

## 结果

- 正式 `h3hota.exe` SHA-256：`f536332e37bc5d1fb503c65189223bd84ac9a96d662c147493aea29ade83535e`；
- 建立主窗口：是；
- 窗口标题：`Heroes of Might and Magic III: Horn of the Abyss`；
- 临时覆盖的两个 EXE、`UN32.DEF` 与 `UN44.DEF`：全部恢复；
- 结果：通过。

TEST04 已由用户使用实际游戏流程确认功能与界面；正式版相对 TEST04 只移除诊断写入并将完整英雄记录恢复为 V1.14 原值（初始屠戮）。
