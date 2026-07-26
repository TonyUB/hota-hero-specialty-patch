# Analysis workspace

当前证据与里程碑：

- [x] `baseline_diff.md` / `clean_patch_diff.md`：纯净 HotA 1.8.0、可信 `Patch_v1.8` 和回滚字节已经完成映射。
- [x] `existing_patch_map.json`：现有 Patch_v1.8 修改与代码洞占用已经登记。
- [x] `cure_runtime_path.md`：单体/群体 Cure、CureCore、原生尸体解析和永久复活接口已经定位。
- [x] `diag01_runtime_validation.md`：实机日志确认两个 Cure 调用点确实执行。
- [x] `stage2_release_acceptance.md`：活体治疗溢出复活、亡灵负例和战后永久性已经通过实机门禁。
- [x] `stage3_corpse_research.md`：`TEST3` 已通过单体、群体、负例、永久性、重叠尸体和占格冲突的全部实机门禁。
- [x] `stage4_visual_isolation.md` / `stage4_logdiag01_runtime_validation.md`：治愈演出隔离、起身状态、音效及单体/群体日志顺序均已通过；该运行逻辑由 `HOTA_NEW_HERO_V1.03` 继续继承。
- [x] `stage4_release_acceptance.md`：TEST13 到正式 v2.6 的逐字节执行文件保留、双语言 LOD 文案、旧版归档与正式包哈希已经闭合。
- [x] `stage3_test2_runtime_results.md`：九组截图结果和剩余单体故障边界已记录。
- [x] `hymn_exclusive_spell_research.md`：壁垒/塔楼幸运特长英雄的“颂歌”专属魔法方案已保存；当前仅研究，不进入 V1.05。
- [x] `HOTA_NEW_HERO_V1.1_LUCKDIAG01` / `LUCK_TEST1`：马洛迪亚和黛瑞丝的实际幸运读取路径、原生硬封锁边界、固定幸运 +3、初始技能与振奋法术均已通过诊断、实机和正式发布门禁。

辅助产物：

- `pe_inventory.md` / `pe_inventory.json`：两个基线 EXE 的可复现 PE、反汇编和静态直接引用清单。
- `runtime_modules.md` / `runtime_modules.json`：EXE、HotA DLL、HD DLL 与 patcher 的运行模块覆盖分析。
- `../tools/analyze_pe.py`：生成 PE 静态清单。
- `../tools/extract_lod.py`：安全列出/解包 H3 LOD。
- `../tools/build_hota_new_hero_v1.py`：从已验收 v2.6 正式包可复现构建历史 V1。
- `../tools/build_hota_new_hero_v101.py`：历史 V1.01 构建器；保留了错误的水系数值差，仅用于追溯。
- `../tools/build_hota_new_hero_v102.py`：历史 V1.02 构建器；用于追溯上一版治疗公式。
- `../tools/build_hota_new_hero_v103.py`：从 V1.02 可复现构建当前 V1.03，写入 F6 Direct 治疗公式，并在 `HotA.dat` 中把阿斯特拉的初级幸运术改为初级水系魔法。
- `../tools/verify_hota_new_hero_v103.py`：校验双 EXE 公式、活体/尸体路径、阿斯特拉初始技能、LOD 文案、ZIP 成员与可复现哈希。
- `../tools/build_hota_new_hero_v104.py` / `verify_hota_new_hero_v104.py`：构建并校验逐队中文治疗日志、零基兵种等级修正与特长详情同步。
- `../tools/build_hota_new_hero_v105.py` / `verify_hota_new_hero_v105.py`：从已验收 V1.04 只替换 F7 NativePower 的实际治疗计算器和特长详情计算器，校验标准/HD 一致、公式样例、逐文件继承、完整回滚与可复现 ZIP。

Stage 4、逐队治疗日志及 V1.06 治愈界面运行时门禁均已通过。当前正式版 `HOTA_NEW_HERO_V1.11` 是基于 V1.1 的说明与排版小版本；除根目录安装说明外，全部游戏文件与 V1.1 逐字节一致。它继承全部治疗/复活逻辑、阿德拉原始耗魔、阿斯特拉初级智慧术 + 初级水系魔法、F7 NativePower 公式，以及已实机验收的马洛迪亚/黛瑞丝固定幸运 +3 特长；厄运沙漏等原生硬封锁保持有效。
