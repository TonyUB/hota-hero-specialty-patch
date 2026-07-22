# Analysis workspace

当前证据与里程碑：

- [x] `baseline_diff.md` / `clean_patch_diff.md`：纯净 HotA 1.8.0、可信 `Patch_v1.8` 和回滚字节已经完成映射。
- [x] `existing_patch_map.json`：现有 Patch_v1.8 修改与代码洞占用已经登记。
- [x] `cure_runtime_path.md`：单体/群体 Cure、CureCore、原生尸体解析和永久复活接口已经定位。
- [x] `diag01_runtime_validation.md`：实机日志确认两个 Cure 调用点确实执行。
- [x] `stage2_release_acceptance.md`：活体治疗溢出复活、亡灵负例和战后永久性已经通过实机门禁。
- [x] `stage3_corpse_research.md`：`TEST3` 已通过单体、群体、负例、永久性、重叠尸体和占格冲突的全部实机门禁。
- [x] `stage4_visual_isolation.md` / `stage4_logdiag01_runtime_validation.md`：治愈演出隔离、起身状态、音效及单体/群体日志顺序均已通过；该运行逻辑由 `HOTA_NEW_HERO_V1.02` 继续继承。
- [x] `stage4_release_acceptance.md`：TEST13 到正式 v2.6 的逐字节执行文件保留、双语言 LOD 文案、旧版归档与正式包哈希已经闭合。
- [x] `stage3_test2_runtime_results.md`：九组截图结果和剩余单体故障边界已记录。

辅助产物：

- `pe_inventory.md` / `pe_inventory.json`：两个基线 EXE 的可复现 PE、反汇编和静态直接引用清单。
- `runtime_modules.md` / `runtime_modules.json`：EXE、HotA DLL、HD DLL 与 patcher 的运行模块覆盖分析。
- `../tools/analyze_pe.py`：生成 PE 静态清单。
- `../tools/extract_lod.py`：安全列出/解包 H3 LOD。
- `../tools/build_hota_new_hero_v1.py`：从已验收 v2.6 正式包可复现构建历史 V1。
- `../tools/build_hota_new_hero_v101.py`：历史 V1.01 构建器；保留了错误的水系数值差，仅用于追溯。
- `../tools/build_hota_new_hero_v102.py`：从 V1.01 可复现构建当前 V1.02，使所有水系等级直接得到同一公式总量，并记录公式代码、回滚字节和逐文件哈希。

Stage 4 运行时门禁已全部通过。当前正式版 `HOTA_NEW_HERO_V1.02` 继承该治愈运行逻辑，保持阿德拉原始耗魔，并让两位治愈特英雄在所有水系熟练度下直接使用同一总量公式和简化说明。
