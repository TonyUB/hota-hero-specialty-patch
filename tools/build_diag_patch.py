#!/usr/bin/env python3
"""Build the diagnostic-only Uland/Astra Cure wrapper on Patch_v1.8.

The payload never calls a resurrection routine. It preserves native Cure behavior,
then appends one fixed-width ASCII record to hota_cure_diag01.log.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import zipfile
from pathlib import Path
from typing import Any

import capstone
import keystone
import pefile
from capstone.x86_const import X86_OP_IMM


BUILD_NAME = "Patch_v2.4_diag01"
EXE_NAMES = ("h3hota.exe", "h3hota HD.exe")
CAVE_VA = 0x00639D80
DATA_VA = 0x00639F20
CAVE_END_EXCLUSIVE_VA = 0x00639FFD
CURE_CORE_VA = 0x00446220
SINGLE_CALL_VA = 0x005A1B05
MASS_CALL_VA = 0x005A1BB4
SINGLE_RETURN_VA = SINGLE_CALL_VA + 5
EXPECTED_CALLS = {
    SINGLE_CALL_VA: bytes.fromhex("E8 16 47 EA FF"),
    MASS_CALL_VA: bytes.fromhex("E8 67 46 EA FF"),
}
IAT = {
    "CloseHandle": 0x0063A0C8,
    "CreateFileA": 0x0063A108,
    "WriteFile": 0x0063A114,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_hash_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s{2}(.+)", line)
        if match is None:
            continue
        digest, name = match.groups()
        result[name.replace("\\", "/")] = digest.lower()
    return result


def verify_baseline(baseline: Path, manifest_path: Path) -> dict[str, str]:
    expected = parse_hash_manifest(manifest_path)
    actual_files = {
        path.relative_to(baseline).as_posix(): path
        for path in baseline.rglob("*")
        if path.is_file()
    }
    if set(actual_files) != set(expected):
        missing = sorted(set(expected) - set(actual_files))
        extra = sorted(set(actual_files) - set(expected))
        raise RuntimeError(f"Baseline file set mismatch; missing={missing}, extra={extra}")
    for relative, expected_hash in expected.items():
        actual_hash = sha256_file(actual_files[relative])
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Baseline hash mismatch: {relative}: {actual_hash} != {expected_hash}"
            )
    return expected


def template_and_offsets() -> tuple[bytes, dict[str, int]]:
    template = (
        b"HOTA_DIAG01 src=S spell=37 hero=00000000 target=00000000 "
        b"alive=00000000 start=00000000 lost=00000000 eax=00000000 "
        b"overflow=00000000 manager=00000000\r\n"
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
        "manager": b"manager=",
    }
    offsets = {name: template.index(marker) + len(marker) for name, marker in markers.items()}
    return template, offsets


def assemble_payload() -> tuple[bytes, dict[str, Any]]:
    template, field_offsets = template_and_offsets()
    filename = b"hota_cure_diag01.log\0"
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
    je diagnostic
    cmp edx, 0xAA
    jne tail_cure
diagnostic:
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
    mov byte ptr [{template_va + field_offsets['source']:#x}], 0x4D
    cmp dword ptr [ebp + 0x04], {SINGLE_RETURN_VA:#x}
    jne source_ready
    mov byte ptr [{template_va + field_offsets['source']:#x}], 0x53
source_ready:
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
    mov eax, dword ptr [ebp - 0x08]
    mov edi, {destination('manager'):#x}
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
            f"Diagnostic code overlaps data: code end 0x{CAVE_VA + len(code):08X}"
        )
    payload_end = hexchars_va + len(hexchars)
    if payload_end > CAVE_END_EXCLUSIVE_VA:
        raise RuntimeError(f"Diagnostic data exceeds cave: end 0x{payload_end:08X}")
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
        "assembly": assembly.strip(),
    }
    return payload, metadata


def va_to_offset(pe: pefile.PE, va: int) -> int:
    return pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)


def import_addresses(pe: pefile.PE) -> dict[str, int]:
    result: dict[str, int] = {}
    for descriptor in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        for symbol in descriptor.imports:
            if symbol.name:
                result[symbol.name.decode("ascii")] = symbol.address
    return result


def relative_call(source_va: int, target_va: int) -> bytes:
    displacement = target_va - (source_va + 5)
    return b"\xE8" + struct.pack("<i", displacement)


def contiguous_differences(before: bytes, after: bytes) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    start: int | None = None
    for index, (left, right) in enumerate(zip(before, after, strict=True)):
        if left != right and start is None:
            start = index
        elif left == right and start is not None:
            ranges.append(
                {
                    "start_offset": start,
                    "end_offset_exclusive": index,
                    "length": index - start,
                    "original_hex": before[start:index].hex(" "),
                    "patched_hex": after[start:index].hex(" "),
                    "rollback_hex": before[start:index].hex(" "),
                }
            )
            start = None
    if start is not None:
        ranges.append(
            {
                "start_offset": start,
                "end_offset_exclusive": len(before),
                "length": len(before) - start,
                "original_hex": before[start:].hex(" "),
                "patched_hex": after[start:].hex(" "),
                "rollback_hex": before[start:].hex(" "),
            }
        )
    return ranges


def patch_executable(path: Path, payload: bytes) -> dict[str, Any]:
    original = path.read_bytes()
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != 0x00400000:
        raise RuntimeError(f"Unexpected image base for {path.name}")
    if pe.OPTIONAL_HEADER.DllCharacteristics & 0x40:
        raise RuntimeError(f"ASLR is enabled unexpectedly for {path.name}")

    imports = import_addresses(pe)
    for name, expected_va in IAT.items():
        if imports.get(name) != expected_va:
            raise RuntimeError(
                f"Unexpected {name} IAT in {path.name}: {imports.get(name)!r}"
            )

    cave_offset = va_to_offset(pe, CAVE_VA)
    cave_end = cave_offset + len(payload)
    if any(original[cave_offset:cave_end]):
        raise RuntimeError(f"Allocated diagnostic cave is not zero-filled in {path.name}")

    patched = bytearray(original)
    logical_regions = []
    for call_va, expected in EXPECTED_CALLS.items():
        offset = va_to_offset(pe, call_va)
        actual = original[offset : offset + len(expected)]
        if actual != expected:
            raise RuntimeError(
                f"Unexpected Cure call bytes at 0x{call_va:08X} in {path.name}: "
                f"{actual.hex(' ')}"
            )
        replacement = relative_call(call_va, CAVE_VA)
        patched[offset : offset + 5] = replacement
        logical_regions.append(
            {
                "label": "single Cure call" if call_va == SINGLE_CALL_VA else "mass Cure call",
                "va": call_va,
                "file_offset": offset,
                "length": 5,
                "original_hex": expected.hex(" "),
                "patched_hex": replacement.hex(" "),
                "rollback_hex": expected.hex(" "),
            }
        )
    patched[cave_offset:cave_end] = payload
    logical_regions.append(
        {
            "label": "diagnostic-only wrapper, logger, and mutable ASCII template",
            "va": CAVE_VA,
            "file_offset": cave_offset,
            "length": len(payload),
            "original_hex": original[cave_offset:cave_end].hex(" "),
            "patched_hex": payload.hex(" "),
            "rollback_hex": original[cave_offset:cave_end].hex(" "),
        }
    )

    patched_bytes = bytes(patched)
    if len(patched_bytes) != len(original):
        raise AssertionError("PE size changed")
    path.write_bytes(patched_bytes)
    pefile.PE(data=patched_bytes, fast_load=False)

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    decoded_calls = []
    for call_va in EXPECTED_CALLS:
        offset = va_to_offset(pe, call_va)
        instruction = next(decoder.disasm(patched_bytes[offset : offset + 5], call_va))
        if (
            instruction.mnemonic != "call"
            or instruction.operands[0].type != X86_OP_IMM
            or instruction.operands[0].imm != CAVE_VA
        ):
            raise RuntimeError(f"Patched call verification failed at 0x{call_va:08X}")
        decoded_calls.append(
            {
                "address": instruction.address,
                "bytes": instruction.bytes.hex(" "),
                "mnemonic": instruction.mnemonic,
                "operands": instruction.op_str,
            }
        )

    forbidden = {
        "GetResurrectionTarget": struct.pack("<I", 0x005A3FD0),
        "ResurrectTarget": struct.pack("<I", 0x005A7870),
    }
    for label, needle in forbidden.items():
        if needle in payload:
            raise RuntimeError(f"Diagnostic payload unexpectedly references {label}")

    rollback = bytearray(patched_bytes)
    for region in logical_regions:
        start = region["file_offset"]
        end = start + region["length"]
        rollback[start:end] = bytes.fromhex(region["rollback_hex"])
    if bytes(rollback) != original:
        raise RuntimeError(f"Rollback reconstruction failed for {path.name}")

    return {
        "name": path.name,
        "input_size": len(original),
        "output_size": len(patched_bytes),
        "input_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(patched_bytes),
        "logical_patch_regions": logical_regions,
        "exact_contiguous_differences": contiguous_differences(original, patched_bytes),
        "decoded_calls": decoded_calls,
        "rollback_reconstructs_input": True,
    }


def safe_recreate_directory(target: Path, allowed_root: Path) -> None:
    resolved_target = target.resolve()
    resolved_root = allowed_root.resolve()
    if resolved_target == resolved_root or resolved_root not in resolved_target.parents:
        raise RuntimeError(f"Refusing to recreate path outside build root: {resolved_target}")
    if resolved_target.exists():
        shutil.rmtree(resolved_target)
    resolved_target.mkdir(parents=True)


def create_zip(package_root: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(
            (item for item in package_root.rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(package_root).as_posix().casefold(),
        ):
            relative = path.relative_to(package_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(2026, 7, 20, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)


def markdown_manifest(report: dict[str, Any]) -> str:
    lines = [
        f"# {BUILD_NAME} 构建清单",
        "",
        "状态：**仅诊断，不含任何复活调用。**",
        "",
        "该版本从唯一可信的 `Patch_v1.8` 构建，保持两个 EXE 大小不变；仅重定向单体/群体 Cure 的两个调用点，并在既有 `.text` 零填充区写入诊断包装器。",
        "",
        f"- ZIP SHA-256：`{report['zip_sha256']}`",
        f"- 包内文件数：{report['package_file_count']}",
        f"- 包装器 VA：`0x{CAVE_VA:08X}`",
        f"- 载荷长度：{report['payload']['payload_size']} 字节",
        f"- 日志文件：`hota_cure_diag01.log`",
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
            "## 逻辑修改区",
            "",
            "两个 EXE 的逻辑修改位置相同；完整原始、修改及回滚字节见 JSON 清单。",
            "",
            "| 位置 | 作用 | 长度 |",
            "|---:|---|---:|",
        ]
    )
    for region in report["executables"][0]["logical_patch_regions"]:
        lines.append(
            f"| `0x{region['va']:08X}` | {region['label']} | {region['length']} |"
        )
    lines.extend(
        [
            "",
            "## 安全边界",
            "",
            "- 包装器对非尤兰德/阿斯特拉、非英雄施法或无存活单位目标直接尾调用原生 Cure。",
            "- 命中目标英雄后仍先完整调用原生 Cure，仅记录返回值；不调用 `GetResurrectionTarget` 或 `ResurrectTarget`。",
            "- 静态检查已确认载荷不含 `0x005A3FD0`、`0x005A7870` 两个复活函数地址。",
            "- PE 大小及其他 10 个包内文件保持不变。运行时是否真正命中仍须由用户实机日志确认。",
            "",
        ]
    )
    return "\n".join(lines)


def test_instructions() -> str:
    return """# Patch_v2.4_diag01 实机测试

这是只记录路径的诊断版，不会复活单位。

1. 备份游戏目录中的现有文件。
2. 将 `Patch_v2.4_diag01.zip` 直接解压到 HotA 1.8.0 游戏根目录并覆盖。
3. 分别测试 `h3hota.exe` 和 `h3hota HD.exe`（若平时只用其中一个，也请至少先测常用版本）。
4. 用尤兰德和阿斯特拉主动对“仍有存活单位、且已有伤亡”的己方兵队施放治愈；最好各测单体和高级水系群体治愈。
5. 再用一名其他英雄施放治愈，确认不会产生该英雄的诊断记录。
6. 退出游戏后，在游戏根目录寻找 `hota_cure_diag01.log`，将它上传到本任务。

每行字段均为十六进制（`spell=37` 和 `src=S/M` 除外）：

```text
HOTA_DIAG01 src=S spell=37 hero=00000019 target=... alive=... start=... lost=... eax=... overflow=... manager=...
```

- `src=S`：单体治愈；`src=M`：群体治愈循环。
- 尤兰德预期 `hero=00000019`；阿斯特拉预期 `hero=000000AA`。
- `eax` 若最高位为 1，表示原生 Cure 返回负值；`overflow` 是其绝对值。
- 若没有生成日志，请告诉我使用的是哪个 EXE、哪位英雄、单体还是群体，以及游戏是否有报错；不要继续测试任何旧版治疗补丁。
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

    executable_reports = [
        patch_executable(package_root / name, payload) for name in EXE_NAMES
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
        "diagnostic_only": True,
        "resurrection_calls_present": False,
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
            "pe_sizes_unchanged": True,
            "other_package_files_unchanged": True,
            "forbidden_resurrection_address_literals_absent": True,
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
