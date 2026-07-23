#!/usr/bin/env python3
"""Build a HotA.dll treatment-text formatter diagnostic from formal V1.05.

UIDIAG03 proved that the visible Cure treatment amount is appended outside the
base EXE sprintf path. This build hooks HotA.dll's snprintf-like formatter and
logs only Chinese format strings containing the GBK bytes for "治疗". The hook,
logger and trampoline are position independent so the DLL keeps its normal
ASLR behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path
from typing import Any

import pefile

from build_hota_new_hero_v1 import deterministic_zip, extract_zip_safely, safe_recreate_directory
from build_hota_new_hero_v104 import assemble


BUILD_NAME = "HOTA_NEW_HERO_V1.06_UIDIAG04"
SOURCE_NAME = "HOTA_NEW_HERO_V1.05"
SOURCE_ZIP_SHA256 = "fcadf14fbbb411acef05def01b1b5a705b5cad4e2d473c8068677e9f0ef93d80"
SOURCE_HOTA_DLL_SHA256 = "bfcd3c314da10808b5a2962b1b45a88b31c33984a36834acbe7396073ced3b22"
HOTA_DLL_NAME = "HotA.dll"

HOTA_IMAGE_BASE = 0x10000000
FORMATTER_VA = 0x102051F0
FORMATTER_CONTINUE_VA = 0x102051F6
FORMATTER_ORIGINAL = bytes.fromhex("55 8B EC 8D 45 14")

DIAG_SECTION_NAME = b".uidiag\0"
DIAG_SECTION_SIZE = 0x1000
DIAG_SECTION_CHARACTERISTICS = 0xE0000020  # code + execute/read/write
LOGGER_OFFSET = 0x000
WRAPPER_OFFSET = 0x300
TRAMPOLINE_OFFSET = 0x400
LOG_FILENAME = "hota_cure_uidiag04.bin"
RECORD_MAGIC = 0x314D4648  # HFM1
RECORD_SIZE = 128
FORMAT_COPY_SIZE = 28
ARG_COPY_SIZE = 16

# HotA.dll is ASLR-enabled. The diagnostic code uses only relative transfers
# inside HotA.dll and the fixed-base H3 EXE's kernel32 IAT for file output.
EXE_IAT = {
    "CloseHandle": 0x0063A0C8,
    "CreateFileA": 0x0063A108,
    "WriteFile": 0x0063A114,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def relative_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5))


def filename_store_lines() -> str:
    raw = LOG_FILENAME.encode("ascii") + b"\0"
    raw += b"\0" * (-len(raw) % 4)
    lines = []
    for index in range(0, len(raw), 4):
        value = int.from_bytes(raw[index : index + 4], "little")
        lines.append(f"mov dword ptr [ebp - {0xE0 - index:#x}], {value:#x}")
    return "\n".join(lines)


def build_payload(section_va: int) -> tuple[bytes, dict[str, Any]]:
    logger_va = section_va + LOGGER_OFFSET
    wrapper_va = section_va + WRAPPER_OFFSET
    trampoline_va = section_va + TRAMPOLINE_OFFSET
    data_va = section_va + 0x500

    # Stack-local layout in logger:
    #   [ebp-0xE0] filename (32-byte slot)
    #   [ebp-0xC0] 128-byte record
    #   [ebp-0x3C] file handle
    #   [ebp-0x38] bytes-written
    logger_source = f"""
    push ebp
    mov ebp, esp
    sub esp, 0xe0
    pushfd
    pushad
    {filename_store_lines()}
    lea edi, dword ptr [ebp - 0xc0]
    xor eax, eax
    mov ecx, 32
    rep stosd
    mov ebx, dword ptr [ebp + 0x08]
    lea edi, dword ptr [ebp - 0xc0]
    mov dword ptr [edi], {RECORD_MAGIC:#x}
    mov eax, dword ptr [ebx]
    mov dword ptr [edi + 0x04], eax
    mov eax, dword ptr [ebx + 0x04]
    mov dword ptr [edi + 0x08], eax
    mov eax, dword ptr [ebx + 0x08]
    mov dword ptr [edi + 0x0c], eax
    mov eax, dword ptr [ebx + 0x0c]
    mov dword ptr [edi + 0x10], eax
    mov eax, dword ptr [ebx + 0x10]
    mov dword ptr [edi + 0x14], eax
    mov eax, dword ptr [ebx + 0x14]
    mov dword ptr [edi + 0x18], eax
    mov eax, dword ptr [ebx + 0x18]
    mov dword ptr [edi + 0x1c], eax
    mov eax, dword ptr [ebx + 0x1c]
    mov dword ptr [edi + 0x20], eax
    mov eax, dword ptr [ebx + 0x20]
    mov dword ptr [edi + 0x24], eax
    mov eax, dword ptr [ebx + 0x24]
    mov dword ptr [edi + 0x28], eax
    mov eax, dword ptr [ebx + 0x28]
    mov dword ptr [edi + 0x2c], eax
    mov eax, dword ptr [ebx + 0x2c]
    mov dword ptr [edi + 0x30], eax
    mov esi, dword ptr [ebx + 0x0c]
    lea edi, dword ptr [ebp - 0xc0 + 0x34]
    mov ecx, {FORMAT_COPY_SIZE}
copy_format:
    mov al, byte ptr [esi]
    mov byte ptr [edi], al
    inc esi
    inc edi
    test al, al
    je count_string_args
    loop copy_format
count_string_args:
    mov esi, dword ptr [ebx + 0x0c]
    xor edx, edx
    mov ecx, 64
count_loop:
    cmp byte ptr [esi], 0
    je count_done
    cmp word ptr [esi], 0x7325
    jne count_next
    inc edx
    inc esi
count_next:
    inc esi
    loop count_loop
count_done:
    cmp edx, 1
    jb open_log
    mov esi, dword ptr [ebx + 0x10]
    test esi, esi
    je maybe_second_arg
    cmp esi, 0x10000
    jb maybe_second_arg
    lea edi, dword ptr [ebp - 0xc0 + 0x50]
    mov ecx, {ARG_COPY_SIZE}
copy_arg1:
    mov al, byte ptr [esi]
    mov byte ptr [edi], al
    inc esi
    inc edi
    test al, al
    je maybe_second_arg
    loop copy_arg1
maybe_second_arg:
    cmp edx, 2
    jb open_log
    mov esi, dword ptr [ebx + 0x14]
    test esi, esi
    je open_log
    cmp esi, 0x10000
    jb open_log
    lea edi, dword ptr [ebp - 0xc0 + 0x60]
    mov ecx, {ARG_COPY_SIZE}
copy_arg2:
    mov al, byte ptr [esi]
    mov byte ptr [edi], al
    inc esi
    inc edi
    test al, al
    je open_log
    loop copy_arg2
open_log:
    push 0
    push 0x80
    push 4
    push 0
    push 3
    push 4
    lea eax, dword ptr [ebp - 0xe0]
    push eax
    call dword ptr [{EXE_IAT['CreateFileA']:#x}]
    cmp eax, -1
    je log_done
    mov dword ptr [ebp - 0x3c], eax
    mov dword ptr [ebp - 0x38], 0
    push 0
    lea ecx, dword ptr [ebp - 0x38]
    push ecx
    push {RECORD_SIZE}
    lea ecx, dword ptr [ebp - 0xc0]
    push ecx
    push eax
    call dword ptr [{EXE_IAT['WriteFile']:#x}]
    push dword ptr [ebp - 0x3c]
    call dword ptr [{EXE_IAT['CloseHandle']:#x}]
log_done:
    popad
    popfd
    mov esp, ebp
    pop ebp
    ret 4
    """

    # GBK("治疗") == D6 CE C1 C6. Scan at most 64 bytes and log only matching
    # localized treatment formats, keeping unrelated HotA formatter calls out.
    wrapper_source = f"""
    mov eax, dword ptr [esp + 0x0c]
    test eax, eax
    je native
    mov ecx, 64
scan_format:
    cmp byte ptr [eax], 0
    je native
    cmp word ptr [eax], 0xced6
    jne scan_next
    cmp word ptr [eax + 0x02], 0xc6c1
    je capture
scan_next:
    inc eax
    loop scan_format
    jmp native
capture:
    lea eax, dword ptr [esp]
    push eax
    call {logger_va:#x}
native:
    jmp {trampoline_va:#x}
    """

    trampoline_source = f"""
    push ebp
    mov ebp, esp
    lea eax, dword ptr [ebp + 0x14]
    jmp {FORMATTER_CONTINUE_VA:#x}
    """

    slots = [
        ("stack_local_formatter_logger", logger_va, wrapper_va, logger_source),
        ("gbk_treatment_filter", wrapper_va, trampoline_va, wrapper_source),
        ("formatter_trampoline", trampoline_va, data_va, trampoline_source),
    ]
    payload = bytearray(DIAG_SECTION_SIZE)
    components: list[dict[str, Any]] = []
    for name, va, limit, source in slots:
        code = assemble(source, va)
        if va + len(code) > limit:
            raise RuntimeError(f"{name} exceeds diagnostic slot: {len(code)} bytes")
        start = va - section_va
        payload[start : start + len(code)] = code
        components.append({
            "name": name,
            "va": va,
            "length": len(code),
            "limit_va": limit,
            "assembly": source.strip(),
        })
    return bytes(payload), {
        "filter_mode": "HotA.dll formatter calls whose first 64 format bytes contain GBK 治疗",
        "hooked_function": f"HotA.dll snprintf-like formatter at 0x{FORMATTER_VA:08X}",
        "position_independent": True,
        "section_va_at_preferred_base": section_va,
        "section_size": DIAG_SECTION_SIZE,
        "logger_va_at_preferred_base": logger_va,
        "wrapper_va_at_preferred_base": wrapper_va,
        "trampoline_va_at_preferred_base": trampoline_va,
        "record_size": RECORD_SIZE,
        "record_layout": [
            "magic HFM1",
            "formatter caller return address",
            "destination pointer",
            "maximum destination size",
            "format pointer",
            "variadic arguments 1..8",
            "first 28 format bytes",
            "first 16 bytes pointed to by %s argument 1",
            "first 16 bytes pointed to by %s argument 2 when present",
            "16 reserved bytes",
        ],
        "components": components,
    }


def patch_hota_dll(path: Path) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_HOTA_DLL_SHA256:
        raise RuntimeError("Unexpected formal V1.05 HotA.dll hash")
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != HOTA_IMAGE_BASE:
        raise RuntimeError("Unexpected HotA.dll image base")
    if not (pe.OPTIONAL_HEADER.DllCharacteristics & 0x40):
        raise RuntimeError("Expected HotA.dll ASLR flag is absent")
    if pe.FILE_HEADER.NumberOfSections != 6:
        raise RuntimeError("Unexpected formal HotA.dll section count")
    if pe.OPTIONAL_HEADER.FileAlignment != 0x200 or pe.OPTIONAL_HEADER.SectionAlignment != 0x1000:
        raise RuntimeError("Unexpected HotA.dll PE alignment")
    if pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].VirtualAddress or pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size:
        raise RuntimeError("Unexpected Authenticode overlay in HotA.dll")

    pe_offset = pe.DOS_HEADER.e_lfanew
    section_table_end = (
        pe_offset + 24 + pe.FILE_HEADER.SizeOfOptionalHeader
        + pe.FILE_HEADER.NumberOfSections * 40
    )
    first_raw = min(section.PointerToRawData for section in pe.sections if section.PointerToRawData)
    if first_raw - section_table_end < 40:
        raise RuntimeError("No room for HotA.dll diagnostic section header")
    old_section_slot = original[section_table_end : section_table_end + 40]
    if old_section_slot != bytes(40):
        raise RuntimeError("Unexpected HotA.dll seventh section-header slot")

    raw_pointer = align(len(original), pe.OPTIONAL_HEADER.FileAlignment)
    if raw_pointer != len(original):
        raise RuntimeError("Unexpected unaligned HotA.dll end")
    virtual_end = max(
        align(
            section.VirtualAddress + max(section.Misc_VirtualSize, section.SizeOfRawData),
            pe.OPTIONAL_HEADER.SectionAlignment,
        )
        for section in pe.sections
    )
    section_rva = align(virtual_end, pe.OPTIONAL_HEADER.SectionAlignment)
    if section_rva != pe.OPTIONAL_HEADER.SizeOfImage:
        raise RuntimeError("New HotA.dll section is not at the exact image boundary")
    section_va = HOTA_IMAGE_BASE + section_rva
    wrapper_va = section_va + WRAPPER_OFFSET
    payload, payload_meta = build_payload(section_va)

    hook_offset = pe.get_offset_from_rva(FORMATTER_VA - HOTA_IMAGE_BASE)
    if original[hook_offset : hook_offset + len(FORMATTER_ORIGINAL)] != FORMATTER_ORIGINAL:
        raise RuntimeError("HotA.dll formatter prologue mismatch")

    patched = bytearray(original)
    patched.extend(payload)
    patched[section_table_end : section_table_end + 40] = struct.pack(
        "<8sIIIIIIHHI",
        DIAG_SECTION_NAME,
        DIAG_SECTION_SIZE,
        section_rva,
        DIAG_SECTION_SIZE,
        raw_pointer,
        0,
        0,
        0,
        0,
        DIAG_SECTION_CHARACTERISTICS,
    )

    section_count_offset = pe_offset + 6
    size_of_code_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfCode")
    size_of_image_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfImage")
    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    header_ranges = {
        "section_count": (section_count_offset, 2),
        "size_of_code": (size_of_code_offset, 4),
        "size_of_image": (size_of_image_offset, 4),
        "checksum": (checksum_offset, 4),
        "new_section_header": (section_table_end, 40),
    }
    struct.pack_into("<H", patched, section_count_offset, 7)
    struct.pack_into("<I", patched, size_of_code_offset, pe.OPTIONAL_HEADER.SizeOfCode + DIAG_SECTION_SIZE)
    struct.pack_into("<I", patched, size_of_image_offset, section_rva + DIAG_SECTION_SIZE)
    hook = relative_jump(FORMATTER_VA, wrapper_va) + b"\x90"
    patched[hook_offset : hook_offset + 6] = hook
    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)

    parsed = pefile.PE(data=final, fast_load=False)
    if parsed.FILE_HEADER.NumberOfSections != 7:
        raise RuntimeError("HotA.dll diagnostic section was not registered")
    section = parsed.sections[-1]
    if (
        section.Name != DIAG_SECTION_NAME
        or section.VirtualAddress != section_rva
        or section.PointerToRawData != raw_pointer
        or section.SizeOfRawData != DIAG_SECTION_SIZE
        or section.Characteristics != DIAG_SECTION_CHARACTERISTICS
    ):
        raise RuntimeError("HotA.dll diagnostic section metadata mismatch")
    if final[raw_pointer : raw_pointer + DIAG_SECTION_SIZE] != payload:
        raise RuntimeError("HotA.dll diagnostic payload mismatch")

    restored = bytearray(final[: len(original)])
    restored[hook_offset : hook_offset + 6] = FORMATTER_ORIGINAL
    for start, length in header_ranges.values():
        restored[start : start + length] = original[start : start + length]
    if bytes(restored) != original:
        raise RuntimeError("Exact HotA.dll rollback reconstruction failed")

    path.write_bytes(final)
    return {
        "name": HOTA_DLL_NAME,
        "source_size": len(original),
        "output_size": len(final),
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "hook": {
            "va_at_preferred_base": FORMATTER_VA,
            "file_offset": hook_offset,
            "source_hex": FORMATTER_ORIGINAL.hex(" "),
            "diagnostic_hex": hook.hex(" "),
            "target_va_at_preferred_base": wrapper_va,
        },
        "new_section": {
            "name": DIAG_SECTION_NAME.rstrip(b"\0").decode("ascii"),
            "rva": section_rva,
            "va_at_preferred_base": section_va,
            "raw_pointer": raw_pointer,
            "raw_size": DIAG_SECTION_SIZE,
            "virtual_size": DIAG_SECTION_SIZE,
            "characteristics": DIAG_SECTION_CHARACTERISTICS,
            "payload_sha256": sha256_bytes(payload),
        },
        "payload": payload_meta,
        "rollback_reconstructs_source": True,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与诊断说明

这是从正式 HOTA_NEW_HERO_V1.05 重新构建的 HotA 治疗数值文本诊断包。它会覆盖旧的 UIDIAG03，但不会修改治疗量、复活、界面显示结果或正式补丁资源。

安装：
1. 将压缩包内全部文件解压到 HotA 1.8.0 游戏根目录，覆盖同名文件。
2. 若根目录已有 {LOG_FILENAME}，先把旧文件移走。
3. 使用平时的 h3hota HD.exe 启动。

一次闭合测试（不要点击施法）：
1. 使用尤兰德或阿斯特拉进入战斗，打开治愈术魔法书页面一次，记下显示数字。
2. 选择治愈术，依次悬停普通存活单位、大天使和一个可选己方尸体，各停留一秒。
3. 直接退出游戏，把根目录生成的 {LOG_FILENAME} 上传给 Codex。

本包只在 HotA.dll 的文本格式化入口记录含“治疗”的中文格式串、前八个参数，以及前两个字符串参数的内容。所有调用随后继续执行原生函数；15/17 等当前显示不会被本诊断包改变。
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
        raise RuntimeError(f"Accepted {SOURCE_NAME} ZIP hash mismatch")

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_files = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    dll_report = patch_hota_dll(package_root / HOTA_DLL_NAME)

    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("Expected exactly one root installation text file")
    instruction_files[0].write_text(installation_text(), encoding="utf-8")

    package_files = sorted(item for item in package_root.rglob("*") if item.is_file())
    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path) for path in package_files
    }
    changed = {
        relative for relative, digest in package_hashes.items()
        if source_files.get(relative) != digest
    }
    allowed = {HOTA_DLL_NAME, instruction_files[0].name}
    if changed != allowed:
        raise RuntimeError(f"Unexpected package changes: {sorted(changed)}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Diagnostic ZIP failed CRC validation")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("Diagnostic ZIP member set changed")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "diagnostic_only": True,
        "display_values_changed": False,
        "gameplay_values_changed": False,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "log_filename": LOG_FILENAME,
        "source_file_hashes": source_files,
        "package_file_hashes": package_hashes,
        "changed_package_files": sorted(changed),
        "hota_dll": dll_report,
        "static_verification": {
            "formal_v105_source_hashes_verified": True,
            "new_section_added_at_exact_image_boundary": True,
            "aslr_safe_relative_internal_transfers": True,
            "stack_local_filename_and_record": True,
            "hook_prologue_and_target_verified": True,
            "full_header_hook_size_rollback_passed": True,
            "only_hota_dll_and_installation_text_changed": True,
            "zip_crc_and_member_checks_passed": True,
        },
        "runtime_acceptance": {
            "status": "pending returned HotA formatter log",
            "minimum_test": [
                "open Cure spellbook once",
                "hover one living ordinary friendly target without casting",
                "hover one Archangel without casting",
                "hover one selectable friendly corpse without casting",
            ],
        },
    }
    (output_root / f"{BUILD_NAME}_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / f"{BUILD_NAME}_README.md").write_text(
        installation_text(), encoding="utf-8"
    )
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    print(f"HotA.dll: {dll_report['output_sha256']}")
    print(f"Payload: {dll_report['new_section']['payload_sha256']}")
    print(f"Runtime log: {LOG_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
