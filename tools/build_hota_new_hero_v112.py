#!/usr/bin/env python3
"""Build formal HOTA_NEW_HERO_V1.12 from formal V1.11.

Melodia and Daremyth retain the accepted fixed Luck +3 specialty from V1.11.
In addition, each friendly stack is guaranteed to trigger native Luck on its
first active attack command in every battle.  The formal payload contains no
diagnostic file writer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path
from typing import Any

import build_hota_new_hero_v12_firstattack_test1 as test1
import build_hota_new_hero_v12_firstattack_test2 as test2
from build_hota_new_hero_v1 import (
    EXE_NAMES,
    LANGUAGE_ARCHIVES,
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)
from build_hota_new_hero_v104 import assemble


BUILD_NAME = "HOTA_NEW_HERO_V1.12"
SOURCE_NAME = "HOTA_NEW_HERO_V1.11"
SOURCE_ZIP_SHA256 = test1.SOURCE_ZIP_SHA256
FORMULA_EXPRESSION = (
    "floor(((11L + 29) * (clamp(n,1,7) + 11)) / 12) "
    "+ 5 * (P - 1) + 10 * max(0, clamp(w,0,3) - 1)"
)
SPECIALTY_ZH = (
    "英雄所率领部队的幸运值始终为+3，且每支部队在每场战斗中首次主动攻击时必定触发幸运。"
)
SPECIALTY_EN = (
    "The Luck of all troops under the hero's command is always +3, and each "
    "troop is guaranteed to trigger Luck on its first active attack in every battle."
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def build_formal_exe_payload() -> tuple[bytes, dict[str, Any]]:
    # Reuse the tested action/reset wrapper layout so all addresses remain
    # identical to TEST2, then replace diagnostic-only components.
    payload, meta = test1.build_exe_payload()
    result = bytearray(payload)
    state = meta["state"]
    used_lo_va = int(state["used_bitmap_low_va"], 16)
    command_attacker_va = int(state["command_attacker_va"], 16)
    command_force_va = int(state["command_force_va"], 16)
    gate_mask_va = int(state["native_gate_mask_va"], 16)

    gate_source = f"""
    pushfd
    pushad
    test esi, esi
    je gate_mark_done
    mov eax, dword ptr [esi + 0x1a]
    cmp eax, {test1.MELODIA_ID}
    je gate_mark_specialist
    cmp eax, {test1.DAREMYTH_ID}
    jne gate_mark_done
gate_mark_specialist:
    mov ecx, dword ptr [{test1.BATTLE_MANAGER_PTR:#x}]
    test ecx, ecx
    je gate_mark_done
    mov edx, dword ptr [ecx + 0x53cc]
    cmp edx, esi
    jne gate_mark_side_one
    or dword ptr [{gate_mask_va:#x}], 1
    jmp gate_mark_done
gate_mark_side_one:
    mov edx, dword ptr [ecx + 0x53d0]
    cmp edx, esi
    jne gate_mark_done
    or dword ptr [{gate_mask_va:#x}], 2
gate_mark_done:
    popad
    popfd
    test esi, esi
    je gate_native
    mov eax, dword ptr [esi + 0x1a]
    cmp eax, {test1.MELODIA_ID}
    je gate_fixed
    cmp eax, {test1.DAREMYTH_ID}
    jne gate_native
gate_fixed:
    mov eax, 3
    pop edi
    pop esi
    mov esp, ebp
    pop ebp
    ret 0x0c
gate_native:
    mov al, byte ptr [esi + 0xd2]
    push {test1.LUCK_GATE_CONTINUE_VA:#x}
    ret
    """
    action_source = f"""
    pushfd
    pushad
    mov dword ptr [{command_attacker_va:#x}], ebx
    mov dword ptr [{command_force_va:#x}], 0
    mov eax, dword ptr [ebx + 0xf4]
    cmp eax, 1
    ja action_done
    mov edx, 1
    mov ecx, eax
    shl edx, cl
    test dword ptr [{gate_mask_va:#x}], edx
    jz action_done
    mov ecx, dword ptr [ebx + 0xf8]
    cmp ecx, 20
    ja action_done
    imul eax, eax, 21
    add eax, ecx
    mov ecx, eax
    and ecx, 31
    mov edx, 1
    shl edx, cl
    shr eax, 5
    test dword ptr [{used_lo_va:#x} + eax*4], edx
    jnz action_done
    or dword ptr [{used_lo_va:#x} + eax*4], edx
    mov dword ptr [{command_force_va:#x}], 1
action_done:
    popad
    popfd
    ret
    """
    gate_code = assemble(gate_source, test1.LUCK_GATE_WRAPPER_VA)
    action_code = assemble(action_source, test1.ACTION_HELPER_VA)
    if len(gate_code) > test1.LOGGER_VA - test1.LUCK_GATE_WRAPPER_VA:
        raise RuntimeError("Formal fixed-Luck gate wrapper exceeds its slot")
    if len(action_code) > test1.RESET_WRAPPER_VA - test1.ACTION_HELPER_VA:
        raise RuntimeError("Formal action helper exceeds its slot")

    gate_start = test1.LUCK_GATE_WRAPPER_VA - test1.LUCK_SECTION_VA
    logger_start = test1.LOGGER_VA - test1.LUCK_SECTION_VA
    action_start = test1.ACTION_HELPER_VA - test1.LUCK_SECTION_VA
    reset_start = test1.RESET_WRAPPER_VA - test1.LUCK_SECTION_VA
    data_start = test1.DATA_VA - test1.LUCK_SECTION_VA
    result[gate_start:logger_start] = b"\0" * (logger_start - gate_start)
    result[gate_start:gate_start + len(gate_code)] = gate_code
    result[logger_start:action_start] = b"\0" * (action_start - logger_start)
    result[action_start:reset_start] = b"\0" * (reset_start - action_start)
    result[action_start:action_start + len(action_code)] = action_code
    result[data_start:] = b"\0" * (len(result) - data_start)

    kept = {
        "battle_reset", "ranged_action_start", "melee_action_start"
    }
    components = [
        component for component in meta["components"] if component["name"] in kept
    ]
    components[0:0] = [
        {
            "name": "fixed_luck_plus_three_and_native_gate_marker",
            "va": f"0x{test1.LUCK_GATE_WRAPPER_VA:08X}",
            "length": len(gate_code),
            "limit_va": f"0x{test1.LOGGER_VA:08X}",
            "assembly": gate_source.strip(),
        },
        {
            "name": "active_action_helper_without_diagnostics",
            "va": f"0x{test1.ACTION_HELPER_VA:08X}",
            "length": len(action_code),
            "limit_va": f"0x{test1.RESET_WRAPPER_VA:08X}",
            "assembly": action_source.strip(),
        },
    ]
    meta["components"] = components
    meta["formal_no_runtime_log_writer"] = True
    meta["fixed_luck_plus_three_preserved"] = True
    return bytes(result), meta


def patch_executable(path: Path, payload: bytes, meta: dict[str, Any]) -> dict[str, Any]:
    report = test1.patch_executable(path, payload, meta)
    report["fixed_plus_three_wrapper_replaced_by_native_gate_marker"] = False
    report["fixed_plus_three_and_native_gate_marker_combined"] = True
    report["formal_no_runtime_diagnostics"] = True
    return report


def build_formal_cureui_payload(
    source_section: bytes,
    record_va: int,
    state: dict[str, str],
) -> tuple[bytes, dict[str, Any]]:
    del record_va
    if len(source_section) != test2.diag03.CUREUI_SIZE:
        raise RuntimeError("Unexpected .cureui size")
    if any(source_section[test2.diag03.PRESERVED_CUREUI_END:]):
        raise RuntimeError("Reserved .cureui region is not empty")
    current_attacker_va = int(state["command_attacker_va"], 16)
    command_force_va = int(state["command_force_va"], 16)
    source = f"""
    push esi
    push edi
    mov edi, dword ptr [esp + 0x10]
    cmp dword ptr [{command_force_va:#x}], 1
    jne native_luck
    cmp dword ptr [{current_attacker_va:#x}], edi
    jne native_luck
    mov dword ptr [edi + 0x70], 1
    jmp {test2.HOTA_LUCK_SUCCESS_CONTINUE_VA:#x}
native_luck:
    jmp {test2.HOTA_LUCK_NATIVE_CONTINUE_VA:#x}
    """
    code = assemble(source, test2.HOTA_LUCK_WRAPPER_VA)
    if test2.HOTA_LUCK_WRAPPER_VA + len(code) > (
        test2.diag03.CUREUI_VA + test2.diag03.CUREUI_SIZE
    ):
        raise RuntimeError("Formal Luck-roll wrapper exceeds reserved .cureui")
    result = bytearray(source_section)
    start = test2.HOTA_LUCK_WRAPPER_VA - test2.diag03.CUREUI_VA
    result[start:start + len(code)] = code
    return bytes(result), {
        "aslr_safe": True,
        "accepted_cure_ui_prefix_preserved": True,
        "formal_no_runtime_log_writer": True,
        "components": [{
            "name": "formal HotA native Luck-roll wrapper",
            "preferred_va": f"0x{test2.HOTA_LUCK_WRAPPER_VA:08X}",
            "length": len(code),
            "native_continue_va": f"0x{test2.HOTA_LUCK_NATIVE_CONTINUE_VA:08X}",
            "forced_success_continue_va": f"0x{test2.HOTA_LUCK_SUCCESS_CONTINUE_VA:08X}",
            "assembly": source.strip(),
        }],
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与功能说明

适用版本：纯净 Heroes III HotA 1.8.0 中文版 + HD Mod。

安装方法：
1. 准备一份无其他平衡修改的纯净 HotA 1.8.0 游戏目录。
2. 将本压缩包内全部文件直接解压到游戏根目录。
3. 覆盖同名文件。
4. 使用 h3hota HD.exe 启动游戏。

V1.12 小版本说明：
- 马洛迪亚与黛瑞丝所率领部队的幸运值始终为 +3。
- 两位英雄所率领的每支部队，在每场战斗中首次主动攻击时必定触发幸运；之后按 +3 幸运的原生概率判定。
- 反击、等待、防御和施法不消耗首次攻击资格；双射、环击等同一攻击指令内的全部命中共享该次必定幸运。
- 厄运沙漏、诅咒之地等直接禁止幸运生效的原生效果仍然有效。
- 游戏内特长描述更新为：{SPECIALTY_ZH}

幸运英雄初始配置：
- 马洛迪亚：初级智慧术 + 初级神秘术；魔法书初始自带振奋。
- 黛瑞丝：初级智慧术 + 初级智力；魔法书初始自带振奋。

完整保留的其他功能：
- 埃尔芙的新英雄立绘、25/25/25 仙灵初始兵力，以及仙灵/妖精伤害 +1、速度 +1；
- 尤兰德、阿斯特拉的单体/群体治愈、永久复活、原生目标限制、治疗动画与音效、复活起身动作；
- 治愈战斗日志顺序、逐队治疗量、魔法书动态范围和存活目标精确悬停数值；
- 阿斯特拉的初级智慧术 + 初级水系魔法；
- 阿德拉及其他未列明英雄的 HotA 1.8.0 原生行为。

当前治愈总量公式：
H = floor(((11L + 29) × (n + 11)) / 12) + 5 × (P - 1) + 10 × max(0, w - 1)

L 为英雄等级（最低 1），P 为当前有效力量（最低 0），n 为目标生物等级（限定 1—7），w 为水系魔法熟练度（无/初级/中级/高级分别为 0/1/2/3）。
"""


def manifest_markdown(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 构建与发布记录

- 来源正式版：`{SOURCE_NAME}`
- 来源 ZIP SHA-256：`{SOURCE_ZIP_SHA256}`
- 输出 ZIP SHA-256：`{report['zip_sha256']}`
- 治愈公式：`{FORMULA_EXPRESSION}`

## 正式变更

1. 马洛迪亚和黛瑞丝继续保持最终幸运固定 `+3`。
2. 两位英雄所率领的每支部队，每场战斗首次主动攻击必定进入 HotA 原生幸运成功分支；之后按常驻 `+3` 的原生概率判定。
3. 反击不消耗也不继承资格；双射、环击等同一主动攻击指令内的全部命中共享资格。
4. 厄运沙漏、诅咒之地等原生硬封锁继续优先于两项特长效果。
5. 中英文门帘、游戏内 HeroSpec、安装说明与下载信息同步更新。

## 运行路径

- 固定幸运与硬封锁后门禁：EXE `0x004E39E8 -> 0x006E7000`。
- 战斗资格重置：EXE `0x00463B71 -> 0x006E7500`。
- 主动射击入口：EXE `0x00478D70 -> 0x006E7580`。
- 主动近战入口：EXE `0x00478B94 -> 0x006E7600`。
- HotA 实际幸运函数：首选 VA `0x10133880 -> 0x14692400`；强制成功后继续 `0x101338E4`。

## 文件边界与验证

- 相对 V1.11 只修改两个 EXE、`HotA.dll`、两份 LOD、中文 HeroSpec 和根目录安装说明。
- 正式负载移除了 TEST2 的二进制诊断文件写入，只保留已验收的游戏机制。
- 标准/HD 独立构建、来源哈希、变更白名单、完整回滚、ZIP CRC、可复现构建、运行时钩子和双启动门禁均已验证。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_zip = args.source_zip.resolve()
    build_root = args.build_root.resolve()
    output_root = args.output_root.resolve()
    if sha256_file(source_zip) != SOURCE_ZIP_SHA256:
        raise RuntimeError("Formal V1.11 ZIP hash mismatch")

    test1.BUILD_NAME = BUILD_NAME
    test1.NEW_SPECIALTY_SENTENCE = SPECIALTY_ZH
    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }

    exe_payload, exe_meta = build_formal_exe_payload()
    record_va = int(exe_meta["record_va"], 16)
    exe_reports = [
        patch_executable(package_root / name, exe_payload, exe_meta)
        for name in EXE_NAMES
    ]
    original_dll_builder = test2.build_cureui_payload
    test2.build_cureui_payload = build_formal_cureui_payload
    try:
        dll_report = test2.patch_hota_dll(
            package_root / test2.diag03.HOTA_DLL_NAME, record_va, exe_meta["state"]
        )
    finally:
        test2.build_cureui_payload = original_dll_builder
    resource_reports = [
        test1.patch_lod(package_root / relative, package_root)
        for relative in LANGUAGE_ARCHIVES
    ]
    resource_reports.append(
        test1.patch_loose(package_root / test1.luck_v11.LOOSE_HEROSPEC_RELATIVE, package_root)
    )
    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("Expected exactly one root installation text file")
    instruction_files[0].write_text(installation_text(), encoding="utf-8")

    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    changed = {
        relative for relative, digest in package_hashes.items()
        if source_hashes.get(relative) != digest
    }
    allowed = (
        set(EXE_NAMES) | {test2.diag03.HOTA_DLL_NAME} | set(LANGUAGE_ARCHIVES)
        | {test1.luck_v11.LOOSE_HEROSPEC_RELATIVE, instruction_files[0].name}
    )
    if changed != allowed:
        raise RuntimeError(f"Unexpected V1.12 package changes: {sorted(changed ^ allowed)}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"V1.12 ZIP CRC failure: {failed}")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("V1.12 ZIP member set mismatch")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "formal_release": True,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "accepted_functional_test": "HOTA_NEW_HERO_V1.2_FIRSTATTACK_TEST2",
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "formula": FORMULA_EXPRESSION,
        "specialty_text": {"zh-CN": SPECIALTY_ZH, "en": SPECIALTY_EN},
        "changed_package_files": sorted(changed),
        "source_file_hashes": source_hashes,
        "package_file_hashes": package_hashes,
        "executables": exe_reports,
        "hota_dll": dll_report,
        "resources": resource_reports,
        "behavior": {
            "hero_ids": [test1.MELODIA_ID, test1.DAREMYTH_ID],
            "fixed_luck_plus_three": True,
            "per_stack_first_active_attack_guaranteed_lucky": True,
            "retaliation_does_not_consume_or_inherit": True,
            "same_command_repeated_hits_inherit": True,
            "later_attacks_use_native_fixed_plus_three_luck": True,
            "native_hard_suppression_preserved": True,
            "runtime_diagnostic_writer_removed": True,
        },
        "static_verification": {
            "formal_v111_source_hash_verified": True,
            "accepted_test2_execution_path_reused": True,
            "fixed_plus_three_wrapper_restored": True,
            "actual_hota_luck_roll_entry_hooked": True,
            "native_lucky_animation_sound_log_path_reused": True,
            "accepted_cure_ui_prefix_preserved": True,
            "standard_and_hd_built_separately": True,
            "all_core_files_rollback_verified": True,
            "only_expected_package_files_changed": True,
            "zip_crc_and_member_checks_passed": True,
        },
    }
    (output_root / f"{BUILD_NAME}_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / f"{BUILD_NAME}_manifest.md").write_text(
        manifest_markdown(report), encoding="utf-8"
    )
    (output_root / f"{BUILD_NAME}_README.md").write_text(
        installation_text(), encoding="utf-8"
    )
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    print(f"HotA.dll SHA-256: {dll_report['output_sha256']}")
    print("Changed package files: " + json.dumps(sorted(changed), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
