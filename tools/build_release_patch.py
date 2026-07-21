#!/usr/bin/env python3
"""Build the accepted Stage 2 Cure overflow resurrection release.

This is the logger-free counterpart of Patch_v2.4_STAGE2_TEST.  It preserves
the tested native Cure -> native eligibility check -> permanent resurrection
sequence while removing all runtime file I/O and mutable diagnostic data.
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import zipfile
from pathlib import Path
from typing import Any

import keystone

from build_diag_patch import (
    CAVE_END_EXCLUSIVE_VA,
    CAVE_VA,
    CURE_CORE_VA,
    EXE_NAMES,
    IAT,
    create_zip,
    patch_executable,
    safe_recreate_directory,
    sha256_file,
    verify_baseline,
)


BUILD_NAME = "Patch_v2.4"
GET_RESURRECTION_TARGET_VA = 0x005A3FD0
RESURRECT_TARGET_VA = 0x005A7870


def assemble_payload() -> tuple[bytes, dict[str, Any]]:
    """Assemble the logger-free version of the Stage 2 wrapper.

    The local-variable offsets intentionally match the accepted test build.
    This keeps the two critical native call sequences byte-for-byte identical
    while allowing the logging branch and its data block to disappear.
    """

    assembly = f"""
wrapper:
    mov eax, dword ptr [esp + 0x0C]
    test eax, eax
    jz tail_cure
    mov edx, dword ptr [eax + 0x1A]
    cmp edx, 0x19
    je stage2
    cmp edx, 0xAA
    jne tail_cure
stage2:
    cmp dword ptr [ecx + 0x4C], 0
    jle tail_cure
    push ebp
    mov ebp, esp
    sub esp, 0x34
    push ebx
    push esi
    push edi
    mov dword ptr [ebp - 0x04], ecx
    mov dword ptr [ebp - 0x08], ebx
    mov eax, dword ptr [ecx + 0x4C]
    mov dword ptr [ebp - 0x10], eax
    mov eax, dword ptr [ecx + 0x60]
    mov dword ptr [ebp - 0x14], eax

    push dword ptr [ebp + 0x10]
    push dword ptr [ebp + 0x0C]
    push dword ptr [ebp + 0x08]
    mov ecx, dword ptr [ebp - 0x04]
    mov eax, {CURE_CORE_VA:#x}
    call eax
    pushfd
    pop dword ptr [ebp - 0x2C]
    mov dword ptr [ebp - 0x1C], eax
    mov dword ptr [ebp - 0x30], ecx
    mov dword ptr [ebp - 0x34], edx

    xor edx, edx
    test eax, eax
    jns overflow_ready
    mov edx, eax
    neg edx
overflow_ready:
    mov dword ptr [ebp - 0x20], edx
    cmp dword ptr [ebp - 0x20], 0
    jle finish
    mov eax, dword ptr [ebp - 0x10]
    cmp eax, dword ptr [ebp - 0x14]
    jge finish

    mov eax, dword ptr [ebp - 0x04]
    push 0
    push dword ptr [eax + 0x38]
    mov ecx, dword ptr [ebp - 0x08]
    push dword ptr [ecx + 0x132C0]
    mov eax, {GET_RESURRECTION_TARGET_VA:#x}
    call eax
    test eax, eax
    je finish
    cmp eax, dword ptr [ebp - 0x04]
    jne finish

    push 0
    push dword ptr [ebp - 0x20]
    push eax
    mov ecx, dword ptr [ebp - 0x08]
    mov edx, {RESURRECT_TARGET_VA:#x}
    call edx

finish:
    mov eax, dword ptr [ebp - 0x1C]
    mov ecx, dword ptr [ebp - 0x30]
    mov edx, dword ptr [ebp - 0x34]
    pop edi
    pop esi
    pop ebx
    push dword ptr [ebp - 0x2C]
    popfd
    mov esp, ebp
    pop ebp
    ret 0x0C

tail_cure:
    mov eax, {CURE_CORE_VA:#x}
    jmp eax
"""
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoded, count = engine.asm(assembly, addr=CAVE_VA)
    code = bytes(encoded)
    if CAVE_VA + len(code) > CAVE_END_EXCLUSIVE_VA:
        raise RuntimeError(
            f"Release code exceeds cave: end 0x{CAVE_VA + len(code):08X}"
        )

    validator_sequence = bytes.fromhex(
        "6A 00 FF 70 38 8B 4D F8 FF B1 C0 32 01 00 B8 D0 3F 5A 00 FF D0"
    )
    permanent_resurrection_sequence = bytes.fromhex(
        "6A 00 FF 75 E0 50 8B 4D F8 BA 70 78 5A 00 FF D2"
    )
    if validator_sequence not in code:
        raise RuntimeError("Native resurrection target validation sequence not found")
    if permanent_resurrection_sequence not in code:
        raise RuntimeError("Permanent native resurrection call sequence not found")

    forbidden_logging_literals = {
        name: struct.pack("<I", address) for name, address in IAT.items()
    }
    for name, literal in forbidden_logging_literals.items():
        if literal in code:
            raise RuntimeError(f"Release payload unexpectedly references {name}")
    if b"hota_cure_stage2.log" in code or b"HOTA_STAGE2" in code:
        raise RuntimeError("Release payload unexpectedly contains diagnostic data")

    metadata = {
        "assembly_statement_count": count,
        "code_size": len(code),
        "payload_size": len(code),
        "payload_end_exclusive_va": CAVE_VA + len(code),
        "runtime_logging": False,
        "critical_sequences_match_accepted_test_build": True,
        "validator_sequence_hex": validator_sequence.hex(" "),
        "permanent_resurrection_sequence_hex": permanent_resurrection_sequence.hex(" "),
        "assembly": assembly.strip(),
    }
    return code, metadata


def markdown_manifest(report: dict[str, Any]) -> str:
    lines = [
        f"# {BUILD_NAME} 构建清单",
        "",
        "状态：**Stage 2 正式版；仅处理仍有存活单位的兵队。**",
        "",
        "该版本从唯一可信的 `Patch_v1.8` 构建。功能路径与实机通过的测试版一致，已移除运行日志和诊断数据。",
        "",
        f"- ZIP SHA-256：`{report['zip_sha256']}`",
        f"- 包内文件数：{report['package_file_count']}",
        f"- 包装器 VA：`0x{CAVE_VA:08X}`",
        f"- 载荷长度：{report['payload']['payload_size']} 字节",
        "- 运行日志：无",
        "",
        "## EXE 输出哈希",
        "",
        "| 文件 | 输入 SHA-256 | 输出 SHA-256 | 精确差异区间数 |",
        "|---|---|---|---:|",
    ]
    for executable in report["executables"]:
        lines.append(
            f"| `{executable['name']}` | `{executable['input_sha256']}` | "
            f"`{executable['output_sha256']}` | "
            f"{len(executable['exact_contiguous_differences'])} |"
        )
    lines.extend(
        [
            "",
            "## 功能边界",
            "",
            "1. 仅拦截尤兰德和阿斯特拉的英雄 Cure；其他路径尾调用原生 Cure。",
            "2. 先完整执行原生 Cure，再使用其实际治疗溢出量。",
            "3. 仅当目标仍存活且存在阵亡时请求复活。",
            "4. 复用 `GetResurrectionTarget(..., context=0)`；亡灵等不合格目标由原生规则拒绝。",
            "5. 复用 `ResurrectTarget(target, overflow, temporary=0)`，复活永久保留。",
            "6. 不直接写兵队字段，不处理全灭尸体，不让群体 Cure 扫描尸体。",
            "",
            "## 验证",
            "",
            "- HD 版测试日志：8 个有效候选全部复活，5 个非候选全部跳过。",
            "- 数量截图：尤兰德单体/群体、阿斯特拉单体/群体均与原生生命值换算一致。",
            "- 用户确认复活单位战后保留。",
            "- 亡灵负例满足阵亡与溢出条件但被原生资格校验拒绝，只治疗、不复活。",
            "- 正式版关键资格校验与永久复活机器码序列和测试版完全一致。",
            "- 两个 EXE 大小不变；其他 10 个包内文件不变；回滚重建、ZIP 成员与 CRC 均通过。",
            "",
        ]
    )
    return "\n".join(lines)


def release_readme(report: dict[str, Any]) -> str:
    return f"""# Patch_v2.4 使用说明

这是 HotA 1.8.0 英雄特长补丁的 Stage 2 正式版。

## 新功能

- 尤兰德和阿斯特拉对仍有单位存活、同时已有阵亡的己方兵队施放治愈时，先正常治疗并解除负面状态，再用剩余治疗量复活同一兵队。
- 复活调用使用原生 `temporary=0` 路径，战后永久保留。
- 亡灵等不允许被转世重生的目标仍只会获得治愈，不会复活。
- 单体和高级水系群体治愈均适用；群体治愈会对每个符合条件的存活兵队分别结算。

## 安装

1. 适用于与项目基线一致的 HotA 1.8.0 中文版。
2. 备份游戏目录中的同名文件。
3. 将 `Patch_v2.4.zip` 解压到游戏根目录并覆盖。

## 当前边界

- 不支持对已经全灭的尸体格直接施放治愈。
- 高级水系群体治愈不会额外扫描全灭尸体。
- 群体施法复活多个兵队时，每个兵队会播放一次原生转世重生动画。
- 正式版不生成 `hota_cure_stage2.log`。

## 校验

```text
Patch_v2.4.zip
SHA-256 {report['zip_sha256']}
```
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
    payload, payload_metadata = assemble_payload()

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    shutil.copytree(baseline, package_root, dirs_exist_ok=True, copy_function=shutil.copy2)

    required_literals = {
        "GetResurrectionTarget": struct.pack("<I", GET_RESURRECTION_TARGET_VA),
        "ResurrectTarget": struct.pack("<I", RESURRECT_TARGET_VA),
    }
    executable_reports = [
        patch_executable(
            package_root / name,
            payload,
            payload_label="Stage 2 logger-free Cure overflow resurrection wrapper",
            forbidden_address_literals={},
            required_address_literals=required_literals,
        )
        for name in EXE_NAMES
    ]

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
        "release": True,
        "runtime_logging": False,
        "scope": "live_stack_only",
        "fully_dead_corpse_support": False,
        "mass_cure_corpse_scan": False,
        "native_resurrection_validation": True,
        "permanent_resurrection_argument": 0,
        "baseline_manifest": args.baseline_manifest.as_posix(),
        "baseline_file_hashes": expected_hashes,
        "package_file_count": len(package_files),
        "package_file_hashes": {
            path.relative_to(package_root).as_posix(): sha256_file(path)
            for path in package_files
        },
        "zip_path": zip_path.as_posix(),
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "payload": payload_metadata,
        "executables": executable_reports,
        "runtime_acceptance": {
            "environment": "h3hota HD.exe",
            "accepted_candidates": 8,
            "correctly_skipped_non_candidates": 5,
            "native_validator_rejections": 1,
            "permanent_after_battle_confirmed_by_user": True,
        },
        "static_verification": {
            "both_calls_decode_to_wrapper": True,
            "native_validator_sequence_present": True,
            "native_resurrect_target_sequence_present": True,
            "critical_sequences_match_accepted_test_build": True,
            "temporary_argument_is_zero": True,
            "runtime_logging_absent": True,
            "pe_sizes_unchanged": True,
            "other_package_files_unchanged": True,
            "rollback_reconstruction_passed": True,
            "zip_crc_test_passed": True,
        },
    }
    json_path = output_root / f"{BUILD_NAME}_manifest.json"
    markdown_path = output_root / f"{BUILD_NAME}_manifest.md"
    readme_path = output_root / f"{BUILD_NAME}_README.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(markdown_manifest(report), encoding="utf-8")
    readme_path.write_text(release_readme(report), encoding="utf-8")
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    for executable in executable_reports:
        print(f"{executable['name']}: {executable['output_sha256']}")
    print(f"Payload: {payload_metadata['code_size']} code bytes; no runtime logger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
