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

## 纯净 HotA 1.8.0 运行时

用户另于 2026-07-20 提供同一套未修改安装目录中的运行文件。可提交的 8 个文件已全部通过 `tools/verify_clean_baseline.ps1` 核验；详细哈希见 `baselines/hota180_clean_SHA256.txt`。

`HotA_Settings.ini` 的导入哈希为 `94b91d9c3f8f7211199f6997831cb7c3e1f209fbc6fdc7d178dd9aeb23d8a29e`，但文件包含本机用户目录路径，因此只在本地保留，仓库以 `.gitignore` 排除。
