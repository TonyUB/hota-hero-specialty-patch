# Analysis workspace

当前证据与里程碑：

- [x] `baseline_diff.md` / `clean_patch_diff.md`：纯净 HotA 1.8.0、可信 `Patch_v1.8` 和回滚字节已经完成映射。
- [x] `existing_patch_map.json`：现有 Patch_v1.8 修改与代码洞占用已经登记。
- [x] `cure_runtime_path.md`：单体/群体 Cure、CureCore、原生尸体解析和永久复活接口已经定位。
- [x] `diag01_runtime_validation.md`：实机日志确认两个 Cure 调用点确实执行。
- [x] `stage2_release_acceptance.md`：活体治疗溢出复活、亡灵负例和战后永久性已经通过实机门禁。
- [x] `stage3_corpse_research.md`：`TEST3` 已通过单体、群体、负例、永久性、重叠尸体和占格冲突的全部实机门禁；正式版为 `Download/Patch_v2.5.zip`。
- [x] `stage3_test2_runtime_results.md`：九组截图结果和剩余单体故障边界已记录。

辅助产物：

- `pe_inventory.md` / `pe_inventory.json`：两个基线 EXE 的可复现 PE、反汇编和静态直接引用清单。
- `runtime_modules.md` / `runtime_modules.json`：EXE、HotA DLL、HD DLL 与 patcher 的运行模块覆盖分析。
- `../tools/analyze_pe.py`：生成 PE 静态清单。
- `../tools/extract_lod.py`：安全列出/解包 H3 LOD。
- `../tools/build_stage3_patch.py`：从唯一可信 `Patch_v1.8` 构建 Stage 3 测试包。

Stage 3 运行时门禁已全部通过。正式版 `Patch_v2.5` 的两个 EXE 与 TEST3 逐字节一致；仅在中文语言资源中追加了已验收功能的一句特长说明。
