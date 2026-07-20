# 纯净 HotA 1.8.0 运行时基线

用户于 2026-07-20 明确说明，这些文件直接来自未经过任何修改的 `HOMM3 HotA1.80 汉化正式版1.2`。

包含：

```text
h3hota.exe
h3hota HD.exe
HotA.dll
HD_HOTA.dll
HW_HOTA.dll
patcher_x86.dll
patcher_x86.ini
HotA_Setup.ini
HotA_Settings.ini (local-only; excluded from Git because it contains a machine-specific user path)
```

导入时的大小、版本信息和 SHA-256 已记录；可信哈希见 `../hota180_clean_SHA256.txt`。任何分析或构建都必须先重新核验这些文件，不得静默替换。`HotA_Settings.ini` 的哈希只作为注释保留，文件本身不提交，以免把用户目录路径发布到仓库。

两个 EXE 均为 2,932,736 字节、FileVersion `3.2`、ProductVersion `HotA`。运行时 DLL/patcher 仅用于静态覆盖分析和后续诊断，不随最终补丁包重新分发，除非技术上确实需要且经过单独确认。
