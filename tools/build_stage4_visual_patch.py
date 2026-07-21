#!/usr/bin/env python3
"""Build a Cure-resurrection visual-isolation test on Patch_v1.8.

The accepted Stage 3 gameplay path is retained. Cure-triggered calls still enter
the native permanent ResurrectTarget routine, but a scoped flag bypasses only
its animation block. The native resurrection combat log and Cure's own outer
animation path are left intact.
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


BUILD_NAME = "Patch_v2.6_VISUAL_TEST1"

# Two clean zero ranges between existing Patch_v1.8 cave bodies. Both ranges
# are zero in the clean 1.8.0 executables and Patch_v1.8, and have no static
# direct/absolute references before this build.
AUTO_SKIP_CLEANUP_VA = 0x00639D20
SILENT_RESURRECT_ENTRY_VA = 0x00639D30
VISUAL_GATE_VA = 0x00639D58
SILENT_FLAG_VA = 0x00639D7F

AUTORESOLVE_SKIP_BRANCH_VA = 0x005A799B
AUTORESOLVE_SKIP_ORIGINAL_TARGET_VA = 0x005A7B6D
RESURRECTION_VISUAL_ENTRY_VA = 0x005A7A44
RESURRECTION_VISUAL_CONTINUE_VA = 0x005A7A4A

AUTORESOLVE_SKIP_EXPECTED = bytes.fromhex("0F 85 CC 01 00 00")
RESURRECTION_VISUAL_ENTRY_EXPECTED = bytes.fromhex("8B 0D A8 7F 68 00")


def near_jcc32(source_va: int, target_va: int, condition_opcode: int) -> bytes:
    displacement = target_va - (source_va + 6)
    return bytes((0x0F, condition_opcode)) + struct.pack("<i", displacement)


def build_visual_payloads() -> tuple[list[tuple[int, bytes]], dict[str, Any], dict[str, int]]:
    stage3_regions, metadata, addresses = assemble_payload(
        resurrect_entry_va=SILENT_RESURRECT_ENTRY_VA
    )

    cleanup_source = f"""
autoresolve_flag_cleanup:
    mov byte ptr [{SILENT_FLAG_VA:#x}], 0
    jmp {AUTORESOLVE_SKIP_ORIGINAL_TARGET_VA:#x}
"""
    cleanup_code, cleanup_count = assemble(cleanup_source, AUTO_SKIP_CLEANUP_VA)
    if AUTO_SKIP_CLEANUP_VA + len(cleanup_code) > SILENT_RESURRECT_ENTRY_VA:
        raise RuntimeError("Autoresolve cleanup overlaps silent resurrection entry")

    helper_source = f"""
silent_resurrect_entry:
    mov byte ptr [{SILENT_FLAG_VA:#x}], 1
    jmp {RESURRECT_TARGET_VA:#x}
"""
    helper_code, helper_count = assemble(helper_source, SILENT_RESURRECT_ENTRY_VA)
    if SILENT_RESURRECT_ENTRY_VA + len(helper_code) > 0x00639D40:
        raise RuntimeError("Silent resurrection entry overlaps existing cave at 0x00639D40")

    low_payload_end = SILENT_RESURRECT_ENTRY_VA + len(helper_code)
    low_payload = bytearray(low_payload_end - AUTO_SKIP_CLEANUP_VA)
    low_payload[: len(cleanup_code)] = cleanup_code
    helper_offset = SILENT_RESURRECT_ENTRY_VA - AUTO_SKIP_CLEANUP_VA
    low_payload[helper_offset : helper_offset + len(helper_code)] = helper_code

    gate_source = f"""
cure_resurrection_visual_gate:
    cmp byte ptr [{SILENT_FLAG_VA:#x}], 0
    jne cure_silent_visual
    mov ecx, dword ptr [0x00687FA8]
    jmp {RESURRECTION_VISUAL_CONTINUE_VA:#x}
cure_silent_visual:
    mov byte ptr [{SILENT_FLAG_VA:#x}], 0
    jmp {AUTORESOLVE_SKIP_ORIGINAL_TARGET_VA:#x}
"""
    gate_code, gate_count = assemble(gate_source, VISUAL_GATE_VA)
    if VISUAL_GATE_VA + len(gate_code) > SILENT_FLAG_VA:
        raise RuntimeError("Visual gate overlaps its runtime flag")
    high_payload = bytearray(0x00639D80 - VISUAL_GATE_VA)
    high_payload[: len(gate_code)] = gate_code
    high_payload[SILENT_FLAG_VA - VISUAL_GATE_VA] = 0

    payload_regions = stage3_regions + [
        (AUTO_SKIP_CLEANUP_VA, bytes(low_payload)),
        (VISUAL_GATE_VA, bytes(high_payload)),
    ]
    metadata = json.loads(json.dumps(metadata))
    metadata["payload_size"] += len(low_payload) + len(high_payload)
    metadata["regions"].extend(
        [
            {
                "va": AUTO_SKIP_CLEANUP_VA,
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
    metadata["total_free_bytes"] += (0x00639D40 - low_payload_end)
    metadata["components"].extend(
        [
            {
                "name": "autoresolve_flag_cleanup",
                "va": AUTO_SKIP_CLEANUP_VA,
                "size": len(cleanup_code),
                "end_exclusive_va": AUTO_SKIP_CLEANUP_VA + len(cleanup_code),
                "assembly_statement_count": cleanup_count,
                "assembly": cleanup_source.strip(),
            },
            {
                "name": "silent_resurrect_entry",
                "va": SILENT_RESURRECT_ENTRY_VA,
                "size": len(helper_code),
                "end_exclusive_va": SILENT_RESURRECT_ENTRY_VA + len(helper_code),
                "assembly_statement_count": helper_count,
                "assembly": helper_source.strip(),
            },
            {
                "name": "cure_resurrection_visual_gate",
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
            "autoresolve_flag_cleanup": AUTO_SKIP_CLEANUP_VA,
            "silent_resurrect_entry": SILENT_RESURRECT_ENTRY_VA,
            "cure_resurrection_visual_gate": VISUAL_GATE_VA,
            "silent_resurrection_flag": SILENT_FLAG_VA,
        }
    )
    return payload_regions, metadata, addresses


def patch_visual_hooks(path: Path, stage3_report: dict[str, Any]) -> dict[str, Any]:
    original = path.read_bytes()
    pe = pefile.PE(data=original, fast_load=False)
    replacements = {
        AUTORESOLVE_SKIP_BRANCH_VA: near_jcc32(
            AUTORESOLVE_SKIP_BRANCH_VA, AUTO_SKIP_CLEANUP_VA, 0x85
        ),
        RESURRECTION_VISUAL_ENTRY_VA: relative_branch(
            RESURRECTION_VISUAL_ENTRY_VA, VISUAL_GATE_VA, 0xE9
        )
        + b"\x90",
    }
    expected = {
        AUTORESOLVE_SKIP_BRANCH_VA: AUTORESOLVE_SKIP_EXPECTED,
        RESURRECTION_VISUAL_ENTRY_VA: RESURRECTION_VISUAL_ENTRY_EXPECTED,
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
                "label": f"Stage 4 visual isolation hook at 0x{address:08X}",
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
    decoded_visual_hooks = []
    expected_targets = {
        AUTORESOLVE_SKIP_BRANCH_VA: AUTO_SKIP_CLEANUP_VA,
        RESURRECTION_VISUAL_ENTRY_VA: VISUAL_GATE_VA,
    }
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
    baseline_hash = stage3_report["input_sha256"]
    if sha256_bytes(bytes(rollback)) != baseline_hash:
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

状态：**动画隔离测试版，不替换 `Download/Patch_v2.5.zip` 正式版。**

## 本次唯一目标

- 尤兰德、阿斯特拉通过治愈触发复活时，保留治愈术自身动画。
- 不再播放转世重生的单位动画；“起死回生”战斗记录仍保留。
- 复活数值、原生资格限制、尸体落位、永久保留和 v2.5 的其他功能均不改变。
- 英雄正常施放转世重生时仍播放原版转世重生动画。

## 安装

1. 必须覆盖到干净 HotA 1.8.0；不要叠加其他测试补丁。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 先启动 `h3hota HD.exe` 到主菜单，确认没有启动故障后再测试。

## 必测

1. 尤兰德单体治愈复活“仍有存活单位”的兵队：只看到治愈动画，数量正确。
2. 尤兰德单体治愈复活“已经全灭”的尸体：只看到治愈动画，数量正确。
3. 阿斯特拉重复上述两项。
4. 两名英雄高级水系群体治愈：多个兵队复活时不逐队播放转世重生动画，治愈动画仍正常。
5. 用任意英雄正常施放转世重生：原版转世重生动画必须仍然存在。
6. 战斗结束后确认复活单位永久保留；亡灵、重叠尸体、被占格尸体规则与 v2.5 相同。

如果观察到“治愈动画也消失”“正常转世重生动画消失”或复活数量变化，请立即停止测试并告诉我具体施法场景。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    return f"""# Stage 4：治愈复活动画隔离

状态：**静态实现完成，等待实机动画门禁。**

## 边界定位

- `ResurrectTarget` 在 `0x005A7870–0x005A7991` 完成生命、永久性、尸体落位与朝向等状态处理。
- `0x005A79A1–0x005A7A43` 生成并写入原生“起死回生”战斗记录。
- `0x005A7A44` 开始加载复活动画资源，后续设置动画状态并等待播放。
- 原版在自动结算/不播放动画路径会由 `0x005A799B` 直接跳到 `0x005A7B6D`，静态上证明 `0x005A7A44–0x005A7B6C` 可以作为视觉演出块隔离，而不跳过前面的复活状态写入。

## 实现

- v2.5 的三个治愈专用复活调用改走 `0x{SILENT_RESURRECT_ENTRY_VA:08X}`，只在进入原生 `ResurrectTarget` 前设置一次作用域标记。
- `0x{RESURRECTION_VISUAL_ENTRY_VA:08X}` 的门仅在该标记存在时跳过复活动画块；普通转世重生重放原指令，保持原样。
- 自动结算原本就会跳过动画；`0x{AUTORESOLVE_SKIP_BRANCH_VA:08X}` 只改到清理标记的等价跳板，防止标记残留。
- 临时参数仍为 `0`；没有手工写 `numberAlive`、`healthLost` 或 `numberForeverDead`。

## 静态验证

- 从唯一可信 `Patch_v1.8` 基线重新构建，没有在 v2.5 二进制上叠补丁。
- 标准版与 HD 版独立核验全部原字节、PE 大小、启动字符串和完整回滚。
- 新代码洞在干净 1.8.0 与 Patch_v1.8 中均为零，邻接边界是两个已知 Patch_v1.8 代码洞；静态扫描没有旧引用。
- ZIP 成员、CRC 与非 EXE 文件哈希通过。
- 静态分析不能证明最终动画组合，必须由游戏实测确认。

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
        "scope": "stage4_cure_resurrection_visual_isolation_test",
        "source_baseline": "Patch_v1.8",
        "preserves_stage3_gameplay": True,
        "cure_resurrection_animation_suppressed": True,
        "native_resurrection_log_preserved": True,
        "ordinary_resurrection_animation_preserved": True,
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
            "visual_entry_hook_verified": True,
            "autoresolve_flag_cleanup_verified": True,
            "native_resurrection_state_path_preserved": True,
            "native_resurrection_log_path_preserved": True,
            "ordinary_resurrection_zero_flag_path_replays_original": True,
            "temporary_argument_is_zero": True,
            "direct_stack_state_writes_absent": True,
            "pe_sizes_unchanged": True,
            "other_package_files_unchanged": True,
            "rollback_reconstruction_passed": True,
            "zip_crc_test_passed": True,
            "startup_export_name_preserved": True,
        },
        "runtime_acceptance_required": True,
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
