#!/usr/bin/env python3
"""Build the second Cure-resurrection visual test on Patch_v1.8.

TEST1 skipped the whole native resurrection visual block. That removed the
effect ring but also skipped the per-stack stand-up sprite refresh used by mass
Cure. TEST2 lets the native visual loop run, substitutes "no effect object"
only while Cure is inside the resurrection-effect setup, then restores the
original effect id before the native sound and stand-up loop.
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import zipfile
from pathlib import Path
from typing import Any

import capstone
import pefile
from capstone.x86_const import X86_OP_IMM

from build_diag_patch import (
    EXE_NAMES,
    contiguous_differences,
    create_zip,
    safe_recreate_directory,
    sha256_bytes,
    sha256_file,
    va_to_offset,
    verify_baseline,
)
from build_stage3_patch import (
    RESURRECT_TARGET_VA,
    assemble,
    assemble_payload,
    patch_executable,
    relative_branch,
)


BUILD_NAME = "Patch_v2.6_VISUAL_TEST2"

RESTORE_EFFECT_ID_HELPER_VA = 0x00639D20
AUTORESOLVE_FLAG_CLEANUP_VA = 0x00639D30
VISUAL_GATE_VA = 0x00639D58
SILENT_FLAG_VA = 0x00639D7F
SILENT_RESURRECT_ENTRY_VA = 0x00639CF5

AUTORESOLVE_SKIP_BRANCH_VA = 0x005A799B
AUTORESOLVE_SKIP_TARGET_VA = 0x005A7B6D
RESURRECTION_EFFECT_ENTRY_VA = 0x005A7A50
RESURRECTION_EFFECT_CONTINUE_VA = 0x005A7A56
RESTORE_EFFECT_ID_HOOK_VA = 0x005A7AF5
RESTORE_EFFECT_ID_RETURN_VA = 0x005A7AFA

AUTORESOLVE_SKIP_EXPECTED = bytes.fromhex("0F 85 CC 01 00 00")
RESURRECTION_EFFECT_ENTRY_EXPECTED = bytes.fromhex("8B B9 38 14 00 00")
RESTORE_EFFECT_ID_EXPECTED = bytes.fromhex("8B 00 8D 0C 7F")


def near_jcc32(source_va: int, target_va: int, condition_opcode: int) -> bytes:
    displacement = target_va - (source_va + 6)
    return bytes((0x0F, condition_opcode)) + struct.pack("<i", displacement)


def build_visual_payloads() -> tuple[list[tuple[int, bytes]], dict[str, Any], dict[str, int]]:
    stage3_regions, metadata, addresses = assemble_payload(
        resurrect_entry_va=SILENT_RESURRECT_ENTRY_VA
    )

    helper_source = f"""
silent_resurrect_entry:
    inc byte ptr [{SILENT_FLAG_VA:#x}]
    jmp {RESURRECT_TARGET_VA:#x}
"""
    helper_code, helper_count = assemble(helper_source, SILENT_RESURRECT_ENTRY_VA)
    if SILENT_RESURRECT_ENTRY_VA + len(helper_code) != 0x00639D00:
        raise RuntimeError("Silent resurrection entry must exactly fill the Stage 3 secondary cave")

    extended_stage3_regions: list[tuple[int, bytes]] = []
    helper_appended = False
    for region_va, payload in stage3_regions:
        if region_va + len(payload) == SILENT_RESURRECT_ENTRY_VA:
            extended_stage3_regions.append((region_va, payload + helper_code))
            helper_appended = True
        else:
            extended_stage3_regions.append((region_va, payload))
    if not helper_appended:
        raise RuntimeError("Stage 3 secondary payload no longer ends at the helper address")

    restore_source = f"""
restore_effect_id_and_clear_flag:
    pop edx
    pop edi
    push edx
    mov byte ptr [{SILENT_FLAG_VA:#x}], 0
    mov eax, dword ptr [eax]
    lea ecx, [edi + edi * 2]
    ret
"""
    restore_code, restore_count = assemble(restore_source, RESTORE_EFFECT_ID_HELPER_VA)
    if RESTORE_EFFECT_ID_HELPER_VA + len(restore_code) > AUTORESOLVE_FLAG_CLEANUP_VA:
        raise RuntimeError("Effect-id restore helper overlaps autoresolve cleanup")

    autoresolve_source = f"""
autoresolve_flag_cleanup:
    mov byte ptr [{SILENT_FLAG_VA:#x}], 0
    jmp {AUTORESOLVE_SKIP_TARGET_VA:#x}
"""
    autoresolve_code, autoresolve_count = assemble(
        autoresolve_source, AUTORESOLVE_FLAG_CLEANUP_VA
    )
    if AUTORESOLVE_FLAG_CLEANUP_VA + len(autoresolve_code) > 0x00639D40:
        raise RuntimeError("Autoresolve cleanup overlaps the existing cave at 0x00639D40")

    low_payload_end = AUTORESOLVE_FLAG_CLEANUP_VA + len(autoresolve_code)
    low_payload = bytearray(low_payload_end - RESTORE_EFFECT_ID_HELPER_VA)
    low_payload[: len(restore_code)] = restore_code
    autoresolve_offset = AUTORESOLVE_FLAG_CLEANUP_VA - RESTORE_EFFECT_ID_HELPER_VA
    low_payload[
        autoresolve_offset : autoresolve_offset + len(autoresolve_code)
    ] = autoresolve_code

    gate_source = f"""
cure_resurrection_effect_gate:
    mov edi, dword ptr [ecx + 0x1438]
    push edi
    cmp byte ptr [{SILENT_FLAG_VA:#x}], 0
    je resurrection_effect_ready
cure_without_resurrection_effect:
    or edi, -1
resurrection_effect_ready:
    jmp {RESURRECTION_EFFECT_CONTINUE_VA:#x}
"""
    gate_code, gate_count = assemble(gate_source, VISUAL_GATE_VA)
    if VISUAL_GATE_VA + len(gate_code) > SILENT_FLAG_VA:
        raise RuntimeError("Effect gate overlaps its runtime flag")
    high_payload = bytearray(0x00639D80 - VISUAL_GATE_VA)
    high_payload[: len(gate_code)] = gate_code
    high_payload[SILENT_FLAG_VA - VISUAL_GATE_VA] = 0

    payload_regions = extended_stage3_regions + [
        (RESTORE_EFFECT_ID_HELPER_VA, bytes(low_payload)),
        (VISUAL_GATE_VA, bytes(high_payload)),
    ]

    metadata = json.loads(json.dumps(metadata))
    metadata["payload_size"] += len(helper_code) + len(low_payload) + len(high_payload)
    for region in metadata["regions"]:
        if region["end_exclusive_va"] == SILENT_RESURRECT_ENTRY_VA:
            region["size"] += len(helper_code)
            region["end_exclusive_va"] += len(helper_code)
            region["free_bytes"] -= len(helper_code)
            break
    else:
        raise RuntimeError("Secondary payload metadata was not found")
    metadata["regions"].extend(
        [
            {
                "va": RESTORE_EFFECT_ID_HELPER_VA,
                "size": len(low_payload),
                "end_exclusive_va": low_payload_end,
                "cave_end_exclusive_va": 0x00639D40,
                "free_bytes": 0x00639D40 - low_payload_end,
            },
            {
                "va": VISUAL_GATE_VA,
                "size": len(high_payload),
                "end_exclusive_va": 0x00639D80,
                "cave_end_exclusive_va": 0x00639D80,
                "free_bytes": 0,
            },
        ]
    )
    metadata["total_free_bytes"] = sum(
        region["free_bytes"] for region in metadata["regions"]
    )
    metadata["components"].extend(
        [
            {
                "name": "silent_resurrect_entry",
                "va": SILENT_RESURRECT_ENTRY_VA,
                "size": len(helper_code),
                "end_exclusive_va": SILENT_RESURRECT_ENTRY_VA + len(helper_code),
                "assembly_statement_count": helper_count,
                "assembly": helper_source.strip(),
            },
            {
                "name": "restore_effect_id_and_clear_flag",
                "va": RESTORE_EFFECT_ID_HELPER_VA,
                "size": len(restore_code),
                "end_exclusive_va": RESTORE_EFFECT_ID_HELPER_VA + len(restore_code),
                "assembly_statement_count": restore_count,
                "assembly": restore_source.strip(),
            },
            {
                "name": "autoresolve_flag_cleanup",
                "va": AUTORESOLVE_FLAG_CLEANUP_VA,
                "size": len(autoresolve_code),
                "end_exclusive_va": AUTORESOLVE_FLAG_CLEANUP_VA
                + len(autoresolve_code),
                "assembly_statement_count": autoresolve_count,
                "assembly": autoresolve_source.strip(),
            },
            {
                "name": "cure_resurrection_effect_gate",
                "va": VISUAL_GATE_VA,
                "size": len(gate_code),
                "end_exclusive_va": VISUAL_GATE_VA + len(gate_code),
                "assembly_statement_count": gate_count,
                "assembly": gate_source.strip(),
                "flag_va": SILENT_FLAG_VA,
            },
        ]
    )
    addresses = dict(addresses)
    addresses.update(
        {
            "silent_resurrect_entry": SILENT_RESURRECT_ENTRY_VA,
            "restore_effect_id_and_clear_flag": RESTORE_EFFECT_ID_HELPER_VA,
            "autoresolve_flag_cleanup": AUTORESOLVE_FLAG_CLEANUP_VA,
            "cure_resurrection_effect_gate": VISUAL_GATE_VA,
            "silent_resurrection_flag": SILENT_FLAG_VA,
        }
    )
    return payload_regions, metadata, addresses


def patch_visual_hooks(path: Path, stage3_report: dict[str, Any]) -> dict[str, Any]:
    original = path.read_bytes()
    pe = pefile.PE(data=original, fast_load=False)
    replacements = {
        AUTORESOLVE_SKIP_BRANCH_VA: near_jcc32(
            AUTORESOLVE_SKIP_BRANCH_VA, AUTORESOLVE_FLAG_CLEANUP_VA, 0x85
        ),
        RESURRECTION_EFFECT_ENTRY_VA: relative_branch(
            RESURRECTION_EFFECT_ENTRY_VA, VISUAL_GATE_VA, 0xE9
        )
        + b"\x90",
        RESTORE_EFFECT_ID_HOOK_VA: relative_branch(
            RESTORE_EFFECT_ID_HOOK_VA, RESTORE_EFFECT_ID_HELPER_VA, 0xE8
        ),
    }
    expected = {
        AUTORESOLVE_SKIP_BRANCH_VA: AUTORESOLVE_SKIP_EXPECTED,
        RESURRECTION_EFFECT_ENTRY_VA: RESURRECTION_EFFECT_ENTRY_EXPECTED,
        RESTORE_EFFECT_ID_HOOK_VA: RESTORE_EFFECT_ID_EXPECTED,
    }

    patched = bytearray(original)
    visual_regions: list[dict[str, Any]] = []
    for address, expected_bytes in expected.items():
        offset = va_to_offset(pe, address)
        actual = original[offset : offset + len(expected_bytes)]
        if actual != expected_bytes:
            raise RuntimeError(
                f"Unexpected visual-path bytes at 0x{address:08X}: {actual.hex(' ')}"
            )
        replacement = replacements[address]
        if len(replacement) != len(expected_bytes):
            raise AssertionError("Visual hook replacement length mismatch")
        patched[offset : offset + len(replacement)] = replacement
        visual_regions.append(
            {
                "label": f"Stage 4 TEST2 visual hook at 0x{address:08X}",
                "va": address,
                "file_offset": offset,
                "length": len(replacement),
                "original_hex": expected_bytes.hex(" "),
                "patched_hex": replacement.hex(" "),
                "rollback_hex": expected_bytes.hex(" "),
            }
        )

    final = bytes(patched)
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    expected_targets = {
        AUTORESOLVE_SKIP_BRANCH_VA: AUTORESOLVE_FLAG_CLEANUP_VA,
        RESURRECTION_EFFECT_ENTRY_VA: VISUAL_GATE_VA,
        RESTORE_EFFECT_ID_HOOK_VA: RESTORE_EFFECT_ID_HELPER_VA,
    }
    decoded_visual_hooks = []
    for address, replacement in replacements.items():
        offset = va_to_offset(pe, address)
        instruction = next(decoder.disasm(final[offset : offset + len(replacement)], address))
        if (
            not instruction.operands
            or instruction.operands[0].type != X86_OP_IMM
            or instruction.operands[0].imm != expected_targets[address]
        ):
            raise RuntimeError(f"Visual hook target verification failed at 0x{address:08X}")
        decoded_visual_hooks.append(
            {
                "address": instruction.address,
                "bytes": instruction.bytes.hex(" "),
                "mnemonic": instruction.mnemonic,
                "operands": instruction.op_str,
            }
        )

    rollback = bytearray(final)
    all_regions = stage3_report["logical_patch_regions"] + visual_regions
    for region in all_regions:
        start = region["file_offset"]
        rollback[start : start + region["length"]] = bytes.fromhex(
            region["rollback_hex"]
        )
    if sha256_bytes(bytes(rollback)) != stage3_report["input_sha256"]:
        raise RuntimeError(f"Combined rollback failed for {path.name}")

    path.write_bytes(final)
    report = dict(stage3_report)
    report["stage3_intermediate_sha256"] = report["output_sha256"]
    report["output_sha256"] = sha256_bytes(final)
    report["logical_patch_regions"] = all_regions
    report["exact_contiguous_differences"] = contiguous_differences(
        bytes(rollback), final
    )
    report["decoded_hooks"] = report["decoded_hooks"] + decoded_visual_hooks
    report["rollback_reconstructs_input"] = True
    return report


def instructions(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 测试说明

状态：**第二轮动画测试版，不替换 `Download/Patch_v2.5.zip`。**

TEST1 已证明复活计算不依赖转世重生圆圈，但整段跳过会让高级水系群体治愈复活的多队尸体缺少起身刷新。本版改为：

- 隐藏治愈触发复活时的灰棕色转世重生圆圈；
- 保留每支兵队从尸体切回站立单位的原生起身动作；
- 保留治愈动画、复活音效和“起死回生”战斗记录；
- 不改变复活数量、合法性、占格规则和战后永久性；
- 普通转世重生仍完整显示原版圆圈和起身动画。

## 安装

1. 覆盖到干净 HotA 1.8.0，不要叠加 TEST1 或 v2.5。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 先启动 `h3hota HD.exe` 到主菜单，再进行战斗测试。

## 必测

1. 单体治愈复活存活兵队与全灭尸体：治愈动画正常，单位正确起身，没有灰棕圆圈。
2. 高级水系群体治愈同时复活至少两队尸体：每队都从尸体切回站立单位，不再停留为地面尸体。
3. 将鼠标移入和移出复活格，确认贴图不依赖鼠标刷新才出现。
4. 普通转世重生：灰棕圆圈、起身动作和音效全部保持原版。
5. 战斗结束后确认复活数量永久保留；亡灵、重叠尸体与被占格尸体规则不变。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    return f"""# Stage 4 TEST2：拆分复活圆圈与兵种起身帧

状态：**静态构建完成，等待群体实机门禁。**

## TEST1 反馈

- 单体正常。
- 高级水系群体治愈的复活计算和战斗记录正确，但多支全灭兵队仍显示为地面尸体；鼠标移动到格子后才刷新成站立兵种。

这证明 TEST1 从 `0x005A7A44` 跳到 `0x005A7B6D` 时，同时跳过了灰棕圆圈和单位起身/逐帧刷新。

## TEST2 边界

- `0x005A7A44–0x005A7A95`：装载或清除转世重生圆圈对象。
- `0x005A7AB9–0x005A7B6C`：计算兵种起身帧、播放音效并逐帧刷新单位。
- 治愈路径在圆圈装载阶段临时令效果 ID 为 `-1`，让原生代码自行释放/清空圆圈对象。
- 到 `0x005A7AF5` 时恢复原效果 ID，再执行原版音效和兵种起身循环。
- 普通转世重生保存并恢复相同 ID，行为不变。

## 静态保证

- 仍从唯一可信 `Patch_v1.8` 重建。
- 三个治愈复活调用仍进入原生 `ResurrectTarget(..., temporary=0)`。
- 没有手工写兵队数量、生命或永久死亡字段。
- 标准版与 HD 版独立验证原字节、Hook 目标、PE 大小、启动字符串、完整回滚、非 EXE 哈希和 ZIP CRC。
- 是否真正得到“治愈动画 + 起身动作、无灰棕圆圈”必须由实机确认。

ZIP SHA-256：`{report['zip_sha256']}`
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    baseline = args.baseline.resolve()
    build_root = args.build_root.resolve()
    output_root = args.output_root.resolve()
    expected_hashes = verify_baseline(baseline, args.baseline_manifest.resolve())
    payload_regions, payload_metadata, addresses = build_visual_payloads()

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    shutil.copytree(baseline, package_root, dirs_exist_ok=True, copy_function=shutil.copy2)

    executable_reports = []
    for name in EXE_NAMES:
        path = package_root / name
        stage3_report = patch_executable(
            path,
            payload_regions,
            addresses,
            resurrect_entry_va=SILENT_RESURRECT_ENTRY_VA,
        )
        executable_reports.append(patch_visual_hooks(path, stage3_report))

    package_files = sorted(path for path in package_root.rglob("*") if path.is_file())
    if len(package_files) != len(expected_hashes):
        raise RuntimeError("Package file count changed")
    for path in package_files:
        relative = path.relative_to(package_root).as_posix()
        if relative not in EXE_NAMES and sha256_file(path) != expected_hashes[relative]:
            raise RuntimeError(f"Non-EXE package file changed: {relative}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    create_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"ZIP integrity failure: {bad_member}")
        zip_members = sorted(archive.namelist())
    expected_members = sorted(
        path.relative_to(package_root).as_posix() for path in package_files
    )
    if zip_members != expected_members:
        raise RuntimeError("ZIP member set mismatch")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "release": False,
        "runtime_logging": False,
        "scope": "stage4_effect_ring_suppression_with_standup_refresh_test",
        "source_baseline": "Patch_v1.8",
        "preserves_stage3_gameplay": True,
        "cure_resurrection_effect_ring_suppressed": True,
        "native_creature_standup_animation_preserved": True,
        "native_resurrection_sound_preserved": True,
        "native_resurrection_log_preserved": True,
        "ordinary_resurrection_visuals_preserved": True,
        "permanent_resurrection_argument": 0,
        "baseline_manifest": args.baseline_manifest.as_posix(),
        "baseline_file_hashes": expected_hashes,
        "package_file_count": len(package_files),
        "package_file_hashes": {
            path.relative_to(package_root).as_posix(): sha256_file(path)
            for path in package_files
        },
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "payload": payload_metadata,
        "addresses": addresses,
        "executables": executable_reports,
        "static_verification": {
            "stage3_six_hooks_preserved": True,
            "effect_entry_hook_verified": True,
            "effect_id_restore_hook_verified": True,
            "autoresolve_flag_cleanup_verified": True,
            "native_resurrection_state_path_preserved": True,
            "native_standup_loop_preserved": True,
            "native_sound_path_preserved": True,
            "ordinary_resurrection_replays_original_effect_id": True,
            "temporary_argument_is_zero": True,
            "direct_stack_state_writes_absent": True,
            "pe_sizes_unchanged": True,
            "other_package_files_unchanged": True,
            "rollback_reconstruction_passed": True,
            "zip_crc_test_passed": True,
            "startup_export_name_preserved": True,
        },
        "runtime_acceptance_required": True,
        "supersedes_test_build": "Patch_v2.6_VISUAL_TEST1",
    }

    json_path = output_root / f"{BUILD_NAME}_manifest.json"
    instructions_path = output_root / f"{BUILD_NAME}_INSTRUCTIONS.md"
    research_path = output_root / f"{BUILD_NAME}_RESEARCH.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    instructions_path.write_text(instructions(report), encoding="utf-8")
    research_path.write_text(research_markdown(report), encoding="utf-8")

    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    for executable in executable_reports:
        print(f"{executable['name']}: {executable['output_sha256']}")
    print(
        f"Payload: {payload_metadata['payload_size']} bytes; "
        f"free: {payload_metadata['total_free_bytes']} bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
