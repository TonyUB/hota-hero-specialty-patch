#!/usr/bin/env python3
"""Build the third Cure-resurrection visual test on Patch_v1.8.

TEST2 removed the Resurrection effect object. HotA 1.8.0 has an additional
battle-render hook that dereferences that object without a null check while a
revived creature plays its stand-up frames. TEST3 therefore keeps the valid
effect object, advances its public frame counter beyond the effect's frame
range for Cure-triggered resurrection only, skips the Resurrection sound call,
and preserves the native creature stand-up/redraw loop.
"""

from __future__ import annotations

import argparse
import json
import shutil
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
BUILD_NAME = "Patch_v2.6_VISUAL_TEST3"
BUILD_SCOPE = "stage4_valid_effect_hidden_frame_soundless_standup_test"
SUPERSEDES_TEST_BUILD = "Patch_v2.6_VISUAL_TEST2"
SUPERSEDED_RESULT_FIELD = "test2_failure"
SUPERSEDED_RUNTIME_RESULT = "HotA.dll+0x64AFF null resurrection-effect dereference"
EXTRA_STANDUP_COMPLETION_FRAME = False

VISUAL_TAIL_GATE_VA = 0x00639D20
SILENT_FLAG_VA = 0x00639D3F
FRAME_COUNTER_GATE_VA = 0x00639D58
PUBLIC_CLEANUP_GATE_VA = 0x00639D70
SILENT_RESURRECT_ENTRY_VA = 0x00639CF5

VISUAL_TAIL_HOOK_VA = 0x005A7AF5
SOUNDLESS_STANDUP_ENTRY_VA = 0x005A7B12
FRAME_COUNTER_HOOK_VA = 0x005A7B22
PUBLIC_CLEANUP_HOOK_VA = 0x005A7B6D

VISUAL_TAIL_EXPECTED = bytes.fromhex("8B 00 8D 0C 7F")
FRAME_COUNTER_EXPECTED = bytes.fromhex("89 BB F0 32 01 00")
PUBLIC_CLEANUP_EXPECTED = bytes.fromhex("8B 8E 84 00 00 00")


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

    completion_frame_statement = (
        "    inc eax\n" if EXTRA_STANDUP_COMPLETION_FRAME else ""
    )
    tail_source = f"""
cure_visual_tail_gate:
    cmp byte ptr [{SILENT_FLAG_VA:#x}], 0
    jne cure_soundless_standup
normal_resurrection_tail:
    mov eax, dword ptr [eax]
    lea ecx, [edi + edi * 2]
    ret
cure_soundless_standup:
    pop edx
    mov eax, dword ptr [ebp + 0x10]
{completion_frame_statement}    mov byte ptr [esi + 0x20], 1
    mov dword ptr [ebp + 0x0c], eax
    jmp {SOUNDLESS_STANDUP_ENTRY_VA:#x}
"""
    tail_code, tail_count = assemble(tail_source, VISUAL_TAIL_GATE_VA)
    tail_end_va = VISUAL_TAIL_GATE_VA + len(tail_code)
    if tail_end_va > 0x00639D40:
        raise RuntimeError("Visual tail gate exceeds the validated low cave")
    if VISUAL_TAIL_GATE_VA <= SILENT_FLAG_VA < tail_end_va:
        raise RuntimeError("Visual tail gate overlaps its runtime flag")
    low_payload = bytearray(0x00639D40 - VISUAL_TAIL_GATE_VA)
    low_payload[: len(tail_code)] = tail_code
    flag_placed = False
    if VISUAL_TAIL_GATE_VA <= SILENT_FLAG_VA < 0x00639D40:
        low_payload[SILENT_FLAG_VA - VISUAL_TAIL_GATE_VA] = 0
        flag_placed = True

    frame_source = f"""
cure_frame_counter_gate:
    cmp byte ptr [{SILENT_FLAG_VA:#x}], 0
    je normal_resurrection_frame
cure_hidden_resurrection_frame:
    mov dword ptr [ebx + 0x132f0], ebp
    ret
normal_resurrection_frame:
    mov dword ptr [ebx + 0x132f0], edi
    ret
"""
    frame_code, frame_count = assemble(frame_source, FRAME_COUNTER_GATE_VA)
    if FRAME_COUNTER_GATE_VA + len(frame_code) > PUBLIC_CLEANUP_GATE_VA:
        raise RuntimeError("Frame counter gate overlaps public cleanup gate")

    cleanup_source = f"""
public_cleanup_gate:
    mov byte ptr [{SILENT_FLAG_VA:#x}], 0
    mov ecx, dword ptr [esi + 0x84]
    ret
"""
    cleanup_code, cleanup_count = assemble(
        cleanup_source, PUBLIC_CLEANUP_GATE_VA
    )
    if PUBLIC_CLEANUP_GATE_VA + len(cleanup_code) > 0x00639D80:
        raise RuntimeError("Public cleanup gate exceeds the validated high cave")
    frame_end_va = FRAME_COUNTER_GATE_VA + len(frame_code)
    cleanup_end_va = PUBLIC_CLEANUP_GATE_VA + len(cleanup_code)
    if (
        FRAME_COUNTER_GATE_VA <= SILENT_FLAG_VA < frame_end_va
        or PUBLIC_CLEANUP_GATE_VA <= SILENT_FLAG_VA < cleanup_end_va
    ):
        raise RuntimeError("High visual helper overlaps its runtime flag")
    high_payload = bytearray(0x00639D80 - FRAME_COUNTER_GATE_VA)
    high_payload[: len(frame_code)] = frame_code
    cleanup_offset = PUBLIC_CLEANUP_GATE_VA - FRAME_COUNTER_GATE_VA
    high_payload[cleanup_offset : cleanup_offset + len(cleanup_code)] = cleanup_code
    if FRAME_COUNTER_GATE_VA <= SILENT_FLAG_VA < 0x00639D80:
        high_payload[SILENT_FLAG_VA - FRAME_COUNTER_GATE_VA] = 0
        flag_placed = True
    if not flag_placed:
        raise RuntimeError("Runtime flag lies outside the validated visual caves")

    payload_regions = extended_stage3_regions + [
        (VISUAL_TAIL_GATE_VA, bytes(low_payload)),
        (FRAME_COUNTER_GATE_VA, bytes(high_payload)),
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
                "va": VISUAL_TAIL_GATE_VA,
                "size": len(low_payload),
                "end_exclusive_va": 0x00639D40,
                "cave_end_exclusive_va": 0x00639D40,
                "free_bytes": 0,
            },
            {
                "va": FRAME_COUNTER_GATE_VA,
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
                "name": "cure_visual_tail_gate",
                "va": VISUAL_TAIL_GATE_VA,
                "size": len(tail_code),
                "end_exclusive_va": VISUAL_TAIL_GATE_VA + len(tail_code),
                "assembly_statement_count": tail_count,
                "assembly": tail_source.strip(),
                "flag_va": SILENT_FLAG_VA,
            },
            {
                "name": "cure_frame_counter_gate",
                "va": FRAME_COUNTER_GATE_VA,
                "size": len(frame_code),
                "end_exclusive_va": FRAME_COUNTER_GATE_VA + len(frame_code),
                "assembly_statement_count": frame_count,
                "assembly": frame_source.strip(),
            },
            {
                "name": "public_cleanup_gate",
                "va": PUBLIC_CLEANUP_GATE_VA,
                "size": len(cleanup_code),
                "end_exclusive_va": PUBLIC_CLEANUP_GATE_VA + len(cleanup_code),
                "assembly_statement_count": cleanup_count,
                "assembly": cleanup_source.strip(),
            },
        ]
    )
    addresses = dict(addresses)
    addresses.update(
        {
            "silent_resurrect_entry": SILENT_RESURRECT_ENTRY_VA,
            "cure_visual_tail_gate": VISUAL_TAIL_GATE_VA,
            "cure_frame_counter_gate": FRAME_COUNTER_GATE_VA,
            "public_cleanup_gate": PUBLIC_CLEANUP_GATE_VA,
            "silent_resurrection_flag": SILENT_FLAG_VA,
        }
    )
    return payload_regions, metadata, addresses


def patch_visual_hooks(path: Path, stage3_report: dict[str, Any]) -> dict[str, Any]:
    original = path.read_bytes()
    pe = pefile.PE(data=original, fast_load=False)
    replacements = {
        VISUAL_TAIL_HOOK_VA: relative_branch(
            VISUAL_TAIL_HOOK_VA, VISUAL_TAIL_GATE_VA, 0xE8
        ),
        FRAME_COUNTER_HOOK_VA: relative_branch(
            FRAME_COUNTER_HOOK_VA, FRAME_COUNTER_GATE_VA, 0xE8
        )
        + b"\x90",
        PUBLIC_CLEANUP_HOOK_VA: relative_branch(
            PUBLIC_CLEANUP_HOOK_VA, PUBLIC_CLEANUP_GATE_VA, 0xE8
        )
        + b"\x90",
    }
    expected = {
        VISUAL_TAIL_HOOK_VA: VISUAL_TAIL_EXPECTED,
        FRAME_COUNTER_HOOK_VA: FRAME_COUNTER_EXPECTED,
        PUBLIC_CLEANUP_HOOK_VA: PUBLIC_CLEANUP_EXPECTED,
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
                "label": f"Stage 4 TEST3 visual hook at 0x{address:08X}",
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
        VISUAL_TAIL_HOOK_VA: VISUAL_TAIL_GATE_VA,
        FRAME_COUNTER_HOOK_VA: FRAME_COUNTER_GATE_VA,
        PUBLIC_CLEANUP_HOOK_VA: PUBLIC_CLEANUP_GATE_VA,
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

状态：**第三轮动画测试版，不替换 `Download/Patch_v2.5.zip`。**

TEST2 的崩溃已定位到 `HotA.dll+0x64AFF`：测试版清空复活圆圈对象后，HotA 的额外绘制代码仍在兵种起身刷新期间直接读取该对象。本版改为：

- 保留合法的复活特效对象，避免 HotA 空指针崩溃；
- 治愈触发复活时，把圆圈的公开帧序号置于有效范围之外，使圆圈不绘制；
- 跳过复活法术音效，只保留原版治愈术音效；
- 完整执行每支部队的原生起身动作和逐帧刷新；
- 普通转世重生仍使用原版圆圈、复活音效和起身动作。

## 安装

1. 覆盖到干净 HotA 1.8.0，不要叠加 TEST1、TEST2 或 v2.5。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 先启动 `h3hota HD.exe` 到主菜单，再进行战斗测试。

## 必测

1. 尤兰德、阿斯特拉单体治愈复活全灭尸体：不崩溃；有治愈术演出/音效和兵种起身动作；无灰棕圆圈、无复活音效。
2. 高级水系群体治愈同时复活至少两队尸体：每队都立即起身，不依赖鼠标移入刷新；无灰棕圆圈、无复活音效。
3. 普通转世重生：原版圆圈、复活音效、起身动作全部保留。
4. 战斗结束后确认复活数量永久保留；亡灵、重叠尸体与被占格尸体规则不变。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    return f"""# Stage 4 TEST3：保留合法对象，隐藏圆圈并静音复活声

状态：**静态构建完成，等待实机门禁。**

## TEST2 崩溃根因

- 崩溃地址：`HotA.dll+0x64AFF`，读取地址 `0x00000028`。
- 对应干净 HotA 1.8.0 指令：`cmp dword ptr [ecx + 0x28], 0`。
- `ecx` 来自主战场对象的复活特效指针；TEST2 用效果 ID `-1` 令该指针为空。
- HotA 的额外绘制钩子没有执行与原版 EXE 相同的空指针检查，因此在起身逐帧刷新时崩溃。

## TEST3 边界

1. 不再改写 `0x005A7A50` 的复活效果 ID，原生对象始终有效。
2. 治愈专用路径在 `0x005A7AF5` 跳过 `0x005A7AFE–0x005A7B0D` 的复活音效设置/调用，但保留兵种起身状态和帧数。
3. 在 `0x005A7B22` 的每个起身帧，把复活特效公开帧序号设为当前函数的正数栈帧地址；它必然远大于动画帧数，HotA 绘制钩子会按自身的范围比较跳过圆圈绘制，但仍能安全读取合法对象。
4. 普通转世重生使用原指令写入真实帧序号，视觉和声音不变。
5. 公共收尾入口清除作用域标记，因此正常动画与自动结算/无动画分支都不会泄漏状态。

## 静态保证

- 仍从唯一可信 `Patch_v1.8` 重建，并继续调用原生 `ResurrectTarget(..., temporary=0)`。
- 未手工写入单位数量、生命、永久死亡或尸体占格字段。
- 标准版与 HD 版独立核对原字节、Hook 目标、回滚、非 EXE 哈希和 ZIP CRC。
- 是否达到“仅有治愈术演出/音效 + 兵种起身动作”必须由实机确认。

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
        "scope": BUILD_SCOPE,
        "source_baseline": "Patch_v1.8",
        "preserves_stage3_gameplay": True,
        "cure_resurrection_effect_object_preserved": True,
        "cure_resurrection_effect_ring_suppressed": True,
        "native_creature_standup_animation_preserved": True,
        "native_resurrection_sound_suppressed_for_cure": True,
        "original_cure_sound_path_untouched": True,
        "native_resurrection_log_preserved": True,
        "ordinary_resurrection_visuals_and_sound_preserved": True,
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
            "valid_resurrection_effect_object_preserved": True,
            "effect_frame_suppression_hook_verified": True,
            "resurrection_sound_bypass_hook_verified": True,
            "public_cleanup_flag_reset_verified": True,
            "native_resurrection_state_path_preserved": True,
            "native_standup_loop_preserved": True,
            "ordinary_resurrection_replays_original_instructions": True,
            "temporary_argument_is_zero": True,
            "direct_stack_state_writes_absent": True,
            "pe_sizes_unchanged": True,
            "other_package_files_unchanged": True,
            "rollback_reconstruction_passed": True,
            "zip_crc_test_passed": True,
            "startup_export_name_preserved": True,
        },
        "runtime_acceptance_required": True,
        "supersedes_test_build": SUPERSEDES_TEST_BUILD,
        SUPERSEDED_RESULT_FIELD: SUPERSEDED_RUNTIME_RESULT,
    }
    if EXTRA_STANDUP_COMPLETION_FRAME:
        report["cure_standup_completion_frame_added"] = True

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
