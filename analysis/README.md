# Analysis workspace

当前证据与里程碑：

- [x] `baseline_diff.md` / `clean_patch_diff.md`：纯净 HotA 1.8.0、可信 `Patch_v1.8` 和回滚字节已经完成映射。
- [x] `existing_patch_map.json`：现有 Patch_v1.8 修改与代码洞占用已经登记。
- [x] `cure_runtime_path.md`：单体/群体 Cure、CureCore、原生尸体解析和永久复活接口已经定位。
- [x] `diag01_runtime_validation.md`：实机日志确认两个 Cure 调用点确实执行。
- [x] `stage2_release_acceptance.md`：活体治疗溢出复活、亡灵负例和战后永久性已经通过实机门禁。
- [ ] `stage3_corpse_research.md`：静态实现及测试构建已经完成；单体尸体目标、群体尸体扫描、负例和战后永久性等待实机验证。

辅助产物：

- `pe_inventory.md` / `pe_inventory.json`：两个基线 EXE 的可复现 PE、反汇编和静态直接引用清单。
- `runtime_modules.md` / `runtime_modules.json`：EXE、HotA DLL、HD DLL 与 patcher 的运行模块覆盖分析。
- `../tools/analyze_pe.py`：生成 PE 静态清单。
- `../tools/extract_lod.py`：安全列出/解包 H3 LOD。
- `../tools/build_stage3_patch.py`：从唯一可信 `Patch_v1.8` 构建 Stage 3 测试包。

静态成果不能替代实机结果。`Patch_v2.5_STAGE3_TEST` 在用户完成运行时门禁前不得进入 `Download/`。
