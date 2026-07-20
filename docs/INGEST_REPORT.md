# 附件导入与核验报告

导入日期：2026-07-20

## 原始附件

| 附件 | 大小（字节） | 观测到的 SHA-256 | 结果 |
|---|---:|---|---|
| `HOTA_Codex_交接包.zip` | 22,922 | `8167b786d6fd03e9fc25c15c082fde340d65287a4f6bd625476c1ecc8c1eaec8` | 已读取并解包 |
| `Patch_v1.8.zip` | 21,080,361 | `13520ef74a9decd28fdcbe21ecf630d046ea04561570a9b16bbddd3b8f76ea52` | 与交接清单一致 |

## 基线内容核验

`Patch_v1.8.zip` 的 12 个包内文件全部与 `baselines/Patch_v1.8_SHA256.txt` 一致：

- `Data/HPL005EL.PCX`
- `Data/HPS005EL.PCX`
- `Data/HotA_l_ext.lod`
- `Data/HotA_lng.lod`
- `HotA.dat`
- `_HD3_Data/Compability/#hota15/Files.ini`
- `_HD3_Data/Compability/#hota15/Pack.ini`
- `_HD3_Data/Compability/#hota15/UN32.DEF`
- `_HD3_Data/Compability/#hota15/UN44.DEF`
- `h3hota HD.exe`
- `h3hota.exe`
- `安装说明.txt`

仓库保存解包后的交接文档和稳定基线内容，便于 Git 审计与直接分析。原始 ZIP 容器哈希记录在本报告中；不得将重新压缩产生的不同 ZIP 哈希标记为原始可信基线。
