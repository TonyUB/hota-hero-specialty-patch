# Heroes III HotA 1.8.0 英雄特长补丁工程

本仓库用于维护《英雄无敌 III》Horn of the Abyss 1.8.0 中文版的英雄特长修改。

当前唯一可信的修改基线是 `Patch_v1.8`。本轮接手已完成外层 ZIP 与包内 12 个文件的 SHA-256 核验，结果全部与交接清单一致。

## 当前状态

- 稳定基线：`Patch_v1.8`
- 下一版本命名：诊断版 `Patch_v2.4_diagNN`
- 当前工程目标：Stage 2——乌兰德与阿斯特拉对仍有存活单位的兵队施放 Cure 时，正常治疗后将剩余治疗量交给原生永久复活流程
- 当前阶段：HD 版 Stage 2 的 13 条日志和两张截图已通过；尤兰德/阿斯特拉单体与群体复活数量、跳过条件和原生动画正确
- 明确未完成：尚未明确确认战后永久保留，也没有覆盖原生禁止复活目标，不能宣称 Stage 2 已稳定完成

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

## 当前需要的实机输入

纯净运行时文件和诊断日志已经补齐。现在请按 `docs/STAGE2_TEST.md` 测试功能包，并回传游戏根目录中的 `hota_cure_stage2.log` 与施法前后单位数。

## 工程门禁

1. 纯净 1.8.0 与 `Patch_v1.8` 的全部 EXE 差异已映射。
2. 标准版和 HD 版的 Cure 静态路径及 DLL/patcher 静态覆盖已分析。
3. 第一份构建 `Patch_v2.4_diag01` 已由实机日志证明真实路径。
4. `Patch_v2.4_STAGE2_TEST` 仅处理存活兵队，复用原生 Resurrection 验证器和永久复活函数。
5. 静态签名、PE 合法性、ZIP 哈希或反汇编本身都不能作为游戏内成功证据；仍需验证数量与战后保留。

## 可见性与权利提示

仓库包含第三方游戏二进制和资源，默认保持私有。未经权利审查，不应改为公开仓库或重新分发。
