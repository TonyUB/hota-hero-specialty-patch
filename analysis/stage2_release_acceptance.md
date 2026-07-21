# Patch_v2.4 Stage 2 发布验收

状态：**Stage 2 功能门禁全部通过，正式无日志构建已完成。**

## 实机证据

| 门禁 | 证据 | 结果 |
|---|---|---|
| Cure 真实路径 | `hota_cure_diag01.log`，15 条记录 | 尤兰德/阿斯特拉单体与群体均命中 |
| 复活决策 | `hota_cure_stage2.log`，SHA-256 `6a659d1718328adf470d0906cc1b0fa894b40dd92526c036fd015b0b95a62b01` | 8 个候选全部 `Y`，5 个非候选全部 `N` |
| 数量与动画 | 两张战斗截图 | 单体/群体数量与生命值换算一致，动画来自原生复活函数 |
| 永久性 | 用户战后观察 | 复活单位战斗结束后保留 |
| 原生禁止目标 | `hota_cure_stage2_undead.log`，SHA-256 `bea4906dd421055b92d380d883436414faa59a36095e0f54f69858530e9d201d` | 亡灵满足基础候选条件但 `revived=N`，只治疗、不复活 |

亡灵记录为：

```text
HOTA_STAGE2 src=S hero=00000019 target=092464A4 alive=00000017 start=0000001C lost=00000005 eax=FFFFFFF6 overflow=0000000A revived=N
```

其中 `alive=23 < start=28`，且 `overflow=10`，所以它不是“没有伤亡”或“没有治疗溢出”的普通跳过；`revived=N` 直接证明原生 `GetResurrectionTarget` 拒绝该目标。

## 正式构建

```text
Patch_v2.4.zip
SHA-256 43708d91e192bd7b42eb6f15b21414ecfcda72c1232dd5df277a2b049c35ffde

h3hota.exe
SHA-256 6b08f448bdac4b4dba7ad4c772df6e8b53aab455efdf9f0244869041a17007a2

h3hota HD.exe
SHA-256 706617a5c80e780211bb89fb260e82598b075bc3d774e2bc13d32c7280c35098
```

- 正式包装器 206 字节，不包含日志模板、日志文件名或 Windows 文件 I/O 地址。
- 两个 EXE 的修改位置和修改字节集合一致，大小均保持不变。
- 资格校验及 `ResurrectTarget(target, overflow, temporary=0)` 的关键机器码序列与实机测试版完全一致。
- 其他 10 个包内文件与 `Patch_v1.8` 基线逐字节一致。
- 连续两次构建 ZIP 哈希一致，12 个成员及 CRC 验证通过，清单中的回滚字节可完整重建输入。

## 验证范围说明

功能实机证据来自 `h3hota HD.exe`。标准 `h3hota.exe` 已完成独立输入哈希、PE、调用点、输出差异和回滚验证，且其补丁字节与 HD 版完全一致，但尚未单独进行实机冒烟测试。

Stage 2 仍不包含全灭尸体目标或高级水系群体 Cure 的尸体扫描；这两项必须作为后续独立里程碑设计和验证。
