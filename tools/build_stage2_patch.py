#!/usr/bin/env python3
"""Build the live-stack Cure overflow resurrection test on Patch_v1.8."""

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


BUILD_NAME = "Patch_v2.4_STAGE2_TEST"
DATA_VA = 0x00639F50
GET_RESURRECTION_TARGET_VA = 0x005A3FD0
RESURRECT_TARGET_VA = 0x005A7870
SINGLE_RETURN_VA = 0x005A1B0A


def template_and_offsets() -> tuple[bytes, dict[str, int]]:
    template = (
        b"HOTA_STAGE2 src=S hero=00000000 target=00000000 alive=00000000 "
        b"start=00000000 lost=00000000 eax=00000000 overflow=00000000 "
        b"revived=N\r\n"
    )
    markers = {
        "source": b"src=",
        "hero": b"hero=",
        "target": b"target=",
        "alive": b"alive=",
        "start": b"start=",
        "lost": b"lost=",
        "eax": b"eax=",
        "overflow": b"overflow=",
        "revived": b"revived=",
    }
    offsets = {name: template.index(marker) + len(marker) for name, marker in markers.items()}
    return template, offsets


def assemble_payload() -> tuple[bytes, dict[str, Any]]:
    template, field_offsets = template_and_offsets()
    filename = b"hota_cure_stage2.log\0"
    hexchars = b"0123456789ABCDEF"
    template_va = DATA_VA
    filename_va = template_va + len(template)
    hexchars_va = filename_va + len(filename)
    data = template + filename + hexchars

    def destination(field: str) -> int:
        return template_va + field_offsets[field]

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
    mov dword ptr [ebp - 0x0C], edx
    mov eax, dword ptr [ecx + 0x4C]
    mov dword ptr [ebp - 0x10], eax
    mov eax, dword ptr [ecx + 0x60]
    mov dword ptr [ebp - 0x14], eax
    mov eax, dword ptr [ecx + 0x58]
    mov dword ptr [ebp - 0x18], eax
    mov byte ptr [{destination('source'):#x}], 0x4D
    cmp dword ptr [ebp + 0x04], {SINGLE_RETURN_VA:#x}
    jne source_ready
    mov byte ptr [{destination('source'):#x}], 0x53
source_ready:
    mov byte ptr [{destination('revived'):#x}], 0x4E
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
    jle write_log
    mov eax, dword ptr [ebp - 0x10]
    cmp eax, dword ptr [ebp - 0x14]
    jge write_log

    mov eax, dword ptr [ebp - 0x04]
    push 0
    push dword ptr [eax + 0x38]
    mov ecx, dword ptr [ebp - 0x08]
    push dword ptr [ecx + 0x132C0]
    mov eax, {GET_RESURRECTION_TARGET_VA:#x}
    call eax
    test eax, eax
    je write_log
    cmp eax, dword ptr [ebp - 0x04]
    jne write_log

    push 0
    push dword ptr [ebp - 0x20]
    push eax
    mov ecx, dword ptr [ebp - 0x08]
    mov edx, {RESURRECT_TARGET_VA:#x}
    call edx
    mov byte ptr [{destination('revived'):#x}], 0x59

write_log:
    mov eax, dword ptr [ebp - 0x0C]
    mov edi, {destination('hero'):#x}
    call hex8
    mov eax, dword ptr [ebp - 0x04]
    mov edi, {destination('target'):#x}
    call hex8
    mov eax, dword ptr [ebp - 0x10]
    mov edi, {destination('alive'):#x}
    call hex8
    mov eax, dword ptr [ebp - 0x14]
    mov edi, {destination('start'):#x}
    call hex8
    mov eax, dword ptr [ebp - 0x18]
    mov edi, {destination('lost'):#x}
    call hex8
    mov eax, dword ptr [ebp - 0x1C]
    mov edi, {destination('eax'):#x}
    call hex8
    mov eax, dword ptr [ebp - 0x20]
    mov edi, {destination('overflow'):#x}
    call hex8

    push 0
    push 0x80
    push 4
    push 0
    push 3
    push 4
    push {filename_va:#x}
    call dword ptr [{IAT['CreateFileA']:#x}]
    cmp eax, -1
    je log_finished
    mov dword ptr [ebp - 0x24], eax
    lea ecx, dword ptr [ebp - 0x28]
    mov dword ptr [ecx], 0
    push 0
    push ecx
    push {len(template)}
    push {template_va:#x}
    push eax
    call dword ptr [{IAT['WriteFile']:#x}]
    push dword ptr [ebp - 0x24]
    call dword ptr [{IAT['CloseHandle']:#x}]
log_finished:
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

hex8:
    mov ecx, 8
hex8_loop:
    mov edx, eax
    shr edx, 28
    mov dl, byte ptr [edx + {hexchars_va:#x}]
    mov byte ptr [edi], dl
    shl eax, 4
    inc edi
    dec ecx
    jne hex8_loop
    ret
"""
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoded, count = engine.asm(assembly, addr=CAVE_VA)
    code = bytes(encoded)
    if CAVE_VA + len(code) > DATA_VA:
        raise RuntimeError(
            f"Stage 2 code overlaps data: code end 0x{CAVE_VA + len(code):08X}"
        )
    payload_end = hexchars_va + len(hexchars)
    if payload_end > CAVE_END_EXCLUSIVE_VA:
        raise RuntimeError(f"Stage 2 data exceeds cave: end 0x{payload_end:08X}")

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

    payload = code + bytes(DATA_VA - CAVE_VA - len(code)) + data
    metadata = {
        "assembly_statement_count": count,
        "code_size": len(code),
        "payload_size": len(payload),
        "payload_end_exclusive_va": CAVE_VA + len(payload),
        "template_va": template_va,
        "template_length": len(template),
        "template_ascii": template.decode("ascii").rstrip("\r\n"),
        "filename_va": filename_va,
        "hexchars_va": hexchars_va,
        "field_vas": {name: template_va + offset for name, offset in field_offsets.items()},
        "validator_sequence_hex": validator_sequence.hex(" "),
        "permanent_resurrection_sequence_hex": permanent_resurrection_sequence.hex(" "),
        "assembly": assembly.strip(),
    }
    return payload, metadata


def markdown_manifest(report: dict[str, Any]) -> str:
    lines = [
        f"# {BUILD_NAME} 构建清单",
        "",
        "状态：**Stage 2 实机测试版，仅处理仍有存活单位的兵队。**",
        "",
        "该版本从唯一可信的 `Patch_v1.8` 构建：先完整执行原生 Cure；仅当治疗量溢出、目标确有阵亡且通过原生 Resurrection 资格验证时，调用原生永久复活函数。",
        "",
        f"- ZIP SHA-256：`{report['zip_sha256']}`",
        f"- 包内文件数：{report['package_file_count']}",
        f"- 包装器 VA：`0x{CAVE_VA:08X}`",
        f"- 载荷长度：{report['payload']['payload_size']} 字节",
        "- 运行日志：`hota_cure_stage2.log`",
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
            "## 功能顺序",
            "",
            "1. 非尤兰德/阿斯特拉、非英雄施法或无存活单位目标直接尾调用原生 Cure。",
            "2. 目标英雄先执行原生 Cure，保留清除负面状态、治疗和原生特长缩放。",
            "3. 只使用原生 Cure 返回的负值绝对值作为溢出量。",
            "4. `numberAlive < numberAtStart` 时，按当前格子与施法方调用 `GetResurrectionTarget(..., context=0)`。",
            "5. 验证返回指针与当前 Cure 目标完全一致。",
            "6. 调用 `ResurrectTarget(target, overflow, temporary=0)`，不直接写兵队字段。",
            "",
            "## 静态安全验证",
            "",
            "- 两个 EXE 的单体/群体 Cure call 均反汇编为包装器目标。",
            "- 机器码包含原生资格验证调用及 `push 0` 的永久复活调用序列。",
            "- `EAX/ECX/EDX/EFLAGS`、非易失寄存器和原始 `ret 0x0C` 栈约定均恢复。",
            "- 两个 EXE 大小不变，其他 10 个包内文件不变，完整回滚可重建输入。",
            "- ZIP CRC 与 12 文件结构已验证。静态检查不能替代游戏内数量与战后永久性测试。",
            "",
        ]
    )
    return "\n".join(lines)


def test_instructions() -> str:
    return """# Patch_v2.4_STAGE2_TEST 实机测试

这是功能测试版，只处理“仍有至少一个单位存活、同时已有阵亡”的兵队；不处理全灭尸体，也不让群体治愈扫描尸体。

1. 备份游戏目录，将 ZIP 直接解压到 HotA 1.8.0 根目录并覆盖。
2. 删除旧的 `hota_cure_stage2.log`，避免混入上一次结果。
3. 分别用尤兰德和阿斯特拉制造一个 `存活数 < 开战数` 的己方兵队，再施放单体治愈。
4. 分别测试高级水系群体治愈；至少保证其中一队仍存活且确有阵亡。
5. 观察正常治疗先发生，剩余治疗量是否增加单位；战斗结束后确认新增单位仍然保留。
6. 验证只有受伤但没有阵亡的满编兵队不会超过开战数量，其他英雄行为不变。
7. 若能选择不允许复活的目标，确认仍遵守原生 Resurrection 限制。
8. 上传 `hota_cure_stage2.log`，并说明每次施法前后单位数、是否战后保留、使用的 EXE。

日志示例：

```text
HOTA_STAGE2 src=S hero=00000019 target=... alive=... start=... lost=... eax=... overflow=... revived=Y
```

- `revived=Y` 表示已通过原生资格验证并调用永久复活函数。
- `revived=N` 表示无溢出、没有阵亡或原生资格验证拒绝。
- 作弊码可用于快速构造测试场景，不影响该调用路径本身。
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
            payload_label="Stage 2 live-stack Cure overflow resurrection wrapper and logger",
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
        "static_verification": {
            "both_calls_decode_to_wrapper": True,
            "native_validator_sequence_present": True,
            "native_resurrect_target_sequence_present": True,
            "temporary_argument_is_zero": True,
            "pe_sizes_unchanged": True,
            "other_package_files_unchanged": True,
            "rollback_reconstruction_passed": True,
            "zip_crc_test_passed": True,
        },
    }
    json_path = output_root / f"{BUILD_NAME}_manifest.json"
    markdown_path = output_root / f"{BUILD_NAME}_manifest.md"
    test_path = output_root / f"{BUILD_NAME}_TEST.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(markdown_manifest(report), encoding="utf-8")
    test_path.write_text(test_instructions(), encoding="utf-8")
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    for executable in executable_reports:
        print(f"{executable['name']}: {executable['output_sha256']}")
    print(
        f"Payload: {payload_metadata['code_size']} code bytes, "
        f"{payload_metadata['payload_size']} total bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
