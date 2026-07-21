# Heroes III HotA 1.8.0 英雄特长补丁工程

本仓库用于维护《英雄无敌 III》Horn of the Abyss 1.8.0 中文版的英雄特长修改。

当前唯一可信的修改基线是 `Patch_v1.8`。本轮接手已完成外层 ZIP 与包内 12 个文件的 SHA-256 核验，结果全部与交接清单一致。

## 当前状态

- 稳定基线：`Patch_v1.8`
- 当前正式输出：`Patch_v2.4`
- 已完成目标：乌兰德与阿斯特拉对仍有存活单位的兵队施放 Cure 时，正常治疗后将剩余治疗量交给原生永久复活流程
- 实机验收：HD 版单体与群体数量正确，复活单位战后保留；亡灵负例只治疗、不复活
- 明确未包含：全灭尸体目标、高级水系群体 Cure 的尸体扫描

## 仓库内容

- `AGENTS.md`：不可违反的工程规则和当前里程碑
- `docs/HOTA_Codex_交接文档.md`：完整交接文档
- `docs/PROJECT_STATUS.md`：接手后的当前理解、边界和下一步
- `docs/INGEST_REPORT.md`：附件导入与哈希核验记录
- `baselines/Patch_v1.8/`：已核验的 12 文件稳定基线
- `baselines/Patch_v1.8_SHA256.txt`：原始校验清单
- `baselines/hota180_clean/`：用户提供的纯净 HotA 1.8.0 运行时基线（本机设置文件除外）
- `baselines/hota180_clean_SHA256.txt`：纯净运行时哈希
- `tools/verify_baseline.ps1`：可重复执行的基线核验脚本
- `analysis/`：差异映射、反汇编、运行时证据和调用图工作区
- `build/`：内部构建工作区
- `output/`：最小化发布包输出目录

## 核验基线

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\verify_baseline.ps1
```

已验证的原始 `Patch_v1.8.zip` SHA-256：

```text
13520ef74a9decd28fdcbe21ecf630d046ea04561570a9b16bbddd3b8f76ea52
```

仓库保存的是该 ZIP 解包后的 12 个文件；脚本逐项核验文件内容。重新压缩会改变 ZIP 容器哈希，不能用重打包文件冒充原始基线。

## 当前实机状态

Stage 2 的诊断、功能、永久性与原生禁止目标门禁均已通过。正式版不再生成 `hota_cure_stage2.log`；若安装正式包，建议先用常用的 HD 启动方式做一次单体与群体冒烟测试。

## 工程门禁

1. 纯净 1.8.0 与 `Patch_v1.8` 的全部 EXE 差异已映射。
2. 标准版和 HD 版的 Cure 静态路径及 DLL/patcher 静态覆盖已分析。
3. 第一份构建 `Patch_v2.4_diag01` 已由实机日志证明真实路径。
4. `Patch_v2.4_STAGE2_TEST` 的 13 条正向/跳过日志、数量截图、战后永久性和亡灵负例均已通过。
5. 正式 `Patch_v2.4` 保留测试版关键资格校验与永久复活机器码序列，移除了运行日志和诊断数据。
6. 正式 ZIP SHA-256：`43708d91e192bd7b42eb6f15b21414ecfcda72c1232dd5df277a2b049c35ffde`。

## 可见性与权利提示

仓库包含第三方游戏二进制和资源，默认保持私有。未经权利审查，不应改为公开仓库或重新分发。
