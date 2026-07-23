#!/usr/bin/env python3
"""Build a behavior-transparent Cure UI path diagnostic from formal V1.05.

The build adds one isolated PE section to each fixed-base executable and hooks
the entry of the native general spell-effect calculator. Only Cure calls made
by Uland or Astra are logged. The wrapper calls the original function through
a trampoline and returns its exact result; it never writes existing Cure,
resurrection, presentation, or treatment-log state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path
from typing import Any

import capstone
import pefile
from capstone.x86_const import X86_OP_IMM

from build_hota_new_hero_v1 import (
    EXE_NAMES,
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)
from build_hota_new_hero_v103 import IMAGE_BASE
from build_hota_new_hero_v104 import HOTA_CURE_SPELL_ID, assemble, contiguous_differences


BUILD_NAME = "HOTA_NEW_HERO_V1.06_UIDIAG01"
SOURCE_NAME = "HOTA_NEW_HERO_V1.05"
SOURCE_ZIP_SHA256 = "fcadf14fbbb411acef05def01b1b5a705b5cad4e2d473c8068677e9f0ef93d80"
SOURCE_EXE_SHA256 = {
    "h3hota.exe": "2e64a368d7e5d0cdebc3deaa8bf0beb37649a32f2201ea1c07306cba08b78abf",
    "h3hota HD.exe": "22e86983d225d88240c1c5c51c11e2f20ea5cc4ff69e9341c9c870f42915831e",
}

NATIVE_EFFECT_VA = 0x004E59D0
NATIVE_EFFECT_CONTINUE_VA = 0x004E59D6
NATIVE_EFFECT_ORIGINAL = bytes.fromhex("55 8B EC 83 EC 08")

DIAG_SECTION_NAME = b".uidiag\0"
EXPECTED_NEW_SECTION_HEADER_SLOT = bytes.fromhex(
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
    "20 75 6E 77 72 61 70 70"
)
DIAG_SECTION_RVA = 0x002E7000
DIAG_SECTION_VA = IMAGE_BASE + DIAG_SECTION_RVA
DIAG_SECTION_SIZE = 0x1000
DIAG_SECTION_CHARACTERISTICS = 0xE0000020  # code + execute/read/write

LOGGER_VA = DIAG_SECTION_VA + 0x000
WRAPPER_VA = DIAG_SECTION_VA + 0x100
TRAMPOLINE_VA = DIAG_SECTION_VA + 0x200
DATA_VA = DIAG_SECTION_VA + 0x300
LOG_FILENAME = "hota_cure_uidiag01.bin"
RECORD_MAGIC = 0x31444955  # little-endian bytes: UID1
RECORD_DWORDS = 10
RECORD_SIZE = RECORD_DWORDS * 4

IAT = {
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


def import_addresses(pe: pefile.PE) -> dict[str, int]:
    result: dict[str, int] = {}
    for descriptor in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        for symbol in descriptor.imports:
            if symbol.name:
                result[symbol.name.decode("ascii")] = int(symbol.address)
    return result


def build_payload() -> tuple[bytes, dict[str, Any]]:
    filename = LOG_FILENAME.encode("ascii") + b"\0"
    filename_va = DATA_VA
    record_va = align(filename_va + len(filename), 4)
    handle_va = record_va + RECORD_SIZE
    written_va = handle_va + 4
    data_end_va = written_va + 4

    logger_source = f"""
    push ebp
    mov ebp, esp
    pushfd
    pushad
    mov eax, dword ptr [ebp + 0x08]
    mov dword ptr [{record_va + 4:#x}], eax
    mov eax, dword ptr [ebp + 0x0c]
    mov dword ptr [{record_va + 8:#x}], eax
    mov eax, dword ptr [ebp + 0x10]
    mov dword ptr [{record_va + 12:#x}], eax
    mov eax, dword ptr [ebp + 0x14]
    mov dword ptr [{record_va + 16:#x}], eax
    mov eax, dword ptr [ebp + 0x18]
    mov dword ptr [{record_va + 20:#x}], eax
    mov eax, dword ptr [ebp + 0x1c]
    mov dword ptr [{record_va + 24:#x}], eax
    mov eax, dword ptr [ebp + 0x20]
    mov dword ptr [{record_va + 28:#x}], eax
    mov eax, dword ptr [ebp + 0x24]
    mov dword ptr [{record_va + 32:#x}], eax
    mov eax, dword ptr [ebp + 0x28]
    mov dword ptr [{record_va + 36:#x}], eax
    push 0
    push 0x80
    push 4
    push 0
    push 3
    push 4
    push {filename_va:#x}
    call dword ptr [{IAT['CreateFileA']:#x}]
    cmp eax, -1
    je log_done
    mov dword ptr [{handle_va:#x}], eax
    mov dword ptr [{written_va:#x}], 0
    push 0
    push {written_va:#x}
    push {RECORD_SIZE}
    push {record_va:#x}
    push eax
    call dword ptr [{IAT['WriteFile']:#x}]
    push dword ptr [{handle_va:#x}]
    call dword ptr [{IAT['CloseHandle']:#x}]
log_done:
    popad
    popfd
    mov esp, ebp
    pop ebp
    ret 0x24
    """

    wrapper_source = f"""
    test ecx, ecx
    je native
    mov eax, dword ptr [ecx + 0x1a]
    cmp eax, 0x19
    je maybe_cure
    cmp eax, 0xaa
    jne native
maybe_cure:
    cmp dword ptr [esp + 0x04], {HOTA_CURE_SPELL_ID}
    jne native
    push ebp
    mov ebp, esp
    sub esp, 0x08
    push ebx
    push esi
    push edi
    mov esi, ecx
    mov ebx, dword ptr [ebp + 0x0c]
    mov edi, dword ptr [ebp + 0x10]
    push edi
    push ebx
    push dword ptr [ebp + 0x08]
    mov ecx, esi
    mov eax, {TRAMPOLINE_VA:#x}
    call eax
    mov dword ptr [ebp - 0x04], eax
    mov eax, 1
    test edi, edi
    je event_ready
    mov eax, 2
event_ready:
    push 0
    push dword ptr [ebp - 0x04]
    push ebx
    push edi
    push dword ptr [ebp + 0x08]
    mov edx, dword ptr [esi + 0x1a]
    push edx
    push esi
    push dword ptr [ebp + 0x04]
    push eax
    mov eax, {LOGGER_VA:#x}
    call eax
    mov eax, dword ptr [ebp - 0x04]
    pop edi
    pop esi
    pop ebx
    mov esp, ebp
    pop ebp
    ret 0x0c
native:
    mov eax, {TRAMPOLINE_VA:#x}
    jmp eax
    """

    trampoline_source = f"""
    push ebp
    mov ebp, esp
    sub esp, 8
    mov eax, {NATIVE_EFFECT_CONTINUE_VA:#x}
    jmp eax
    """

    slots = [
        ("logger", LOGGER_VA, WRAPPER_VA, logger_source),
        ("wrapper", WRAPPER_VA, TRAMPOLINE_VA, wrapper_source),
        ("trampoline", TRAMPOLINE_VA, DATA_VA, trampoline_source),
    ]
    payload = bytearray(DIAG_SECTION_SIZE)
    components = []
    for name, va, limit, source in slots:
        code = assemble(source, va)
        if va + len(code) > limit:
            raise RuntimeError(f"{name} exceeds its isolated diagnostic slot")
        start = va - DIAG_SECTION_VA
        payload[start : start + len(code)] = code
        components.append({
            "name": name,
            "va": va,
            "length": len(code),
            "limit_va": limit,
            "assembly": source.strip(),
        })
    if data_end_va > DIAG_SECTION_VA + DIAG_SECTION_SIZE:
        raise RuntimeError("Diagnostic data exceeds isolated PE section")
    payload[filename_va - DIAG_SECTION_VA : filename_va - DIAG_SECTION_VA + len(filename)] = filename
    payload[record_va - DIAG_SECTION_VA : record_va - DIAG_SECTION_VA + 4] = struct.pack(
        "<I", RECORD_MAGIC
    )
    return bytes(payload), {
        "section_va": DIAG_SECTION_VA,
        "section_size": DIAG_SECTION_SIZE,
        "filename_va": filename_va,
        "record_va": record_va,
        "record_size": RECORD_SIZE,
        "record_layout": [
            "magic UID1",
            "event (1=null target, 2=non-null target)",
            "native caller return address",
            "hero pointer",
            "hero id",
            "spell id",
            "target pointer",
            "native base input",
            "native result",
            "reserved",
        ],
        "handle_va": handle_va,
        "written_va": written_va,
        "components": components,
    }


def patch_executable(path: Path, payload: bytes, payload_meta: dict[str, Any]) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_EXE_SHA256[path.name]:
        raise RuntimeError(f"Unexpected {SOURCE_NAME} source hash for {path.name}")
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != IMAGE_BASE:
        raise RuntimeError(f"Unexpected image base in {path.name}")
    if pe.OPTIONAL_HEADER.DllCharacteristics & 0x40:
        raise RuntimeError(f"Unexpected ASLR in {path.name}")
    if pe.FILE_HEADER.NumberOfSections != 4:
        raise RuntimeError(f"Unexpected source section count in {path.name}")
    if pe.OPTIONAL_HEADER.SizeOfImage != DIAG_SECTION_RVA:
        raise RuntimeError(f"Unexpected source SizeOfImage in {path.name}")
    if len(payload) != DIAG_SECTION_SIZE:
        raise RuntimeError("Diagnostic payload must occupy exactly one raw section")

    imports = import_addresses(pe)
    for name, expected in IAT.items():
        if imports.get(name) != expected:
            raise RuntimeError(f"Unexpected {name} IAT in {path.name}: {imports.get(name)!r}")

    entry_offset = pe.get_offset_from_rva(NATIVE_EFFECT_VA - IMAGE_BASE)
    if original[entry_offset : entry_offset + len(NATIVE_EFFECT_ORIGINAL)] != NATIVE_EFFECT_ORIGINAL:
        raise RuntimeError(f"Native effect prologue mismatch in {path.name}")

    pe_offset = pe.DOS_HEADER.e_lfanew
    section_table_end = (
        pe_offset + 24 + pe.FILE_HEADER.SizeOfOptionalHeader
        + pe.FILE_HEADER.NumberOfSections * 40
    )
    first_raw = min(section.PointerToRawData for section in pe.sections if section.PointerToRawData)
    if first_raw - section_table_end < 40:
        raise RuntimeError(f"No room for isolated diagnostic section header in {path.name}")
    if (
        original[section_table_end : section_table_end + 40]
        != EXPECTED_NEW_SECTION_HEADER_SLOT
    ):
        raise RuntimeError(f"Unexpected fifth section-header slot in {path.name}")

    raw_pointer = align(len(original), pe.OPTIONAL_HEADER.FileAlignment)
    if raw_pointer != len(original):
        raise RuntimeError(f"Unexpected source overlay/alignment in {path.name}")
    if pe.OPTIONAL_HEADER.FileAlignment != 0x1000 or pe.OPTIONAL_HEADER.SectionAlignment != 0x1000:
        raise RuntimeError(f"Unexpected PE alignment in {path.name}")

    last = max(pe.sections, key=lambda section: section.VirtualAddress)
    last_virtual_end = align(
        last.VirtualAddress + max(last.Misc_VirtualSize, last.SizeOfRawData),
        pe.OPTIONAL_HEADER.SectionAlignment,
    )
    if last_virtual_end != DIAG_SECTION_RVA:
        raise RuntimeError(f"New section RVA is not the exact image boundary in {path.name}")

    patched = bytearray(original)
    patched.extend(payload)
    section_header = struct.pack(
        "<8sIIIIIIHHI",
        DIAG_SECTION_NAME,
        DIAG_SECTION_SIZE,
        DIAG_SECTION_RVA,
        DIAG_SECTION_SIZE,
        raw_pointer,
        0,
        0,
        0,
        0,
        DIAG_SECTION_CHARACTERISTICS,
    )
    patched[section_table_end : section_table_end + 40] = section_header

    section_count_offset = pe_offset + 6
    size_of_code_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfCode")
    size_of_image_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfImage")
    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    original_header_fields = {
        "section_count": original[section_count_offset : section_count_offset + 2],
        "size_of_code": original[size_of_code_offset : size_of_code_offset + 4],
        "size_of_image": original[size_of_image_offset : size_of_image_offset + 4],
        "checksum": original[checksum_offset : checksum_offset + 4],
        "new_section_header_slot": original[section_table_end : section_table_end + 40],
    }
    struct.pack_into("<H", patched, section_count_offset, pe.FILE_HEADER.NumberOfSections + 1)
    struct.pack_into("<I", patched, size_of_code_offset, pe.OPTIONAL_HEADER.SizeOfCode + DIAG_SECTION_SIZE)
    struct.pack_into("<I", patched, size_of_image_offset, DIAG_SECTION_RVA + DIAG_SECTION_SIZE)

    hook = relative_jump(NATIVE_EFFECT_VA, WRAPPER_VA) + b"\x90"
    patched[entry_offset : entry_offset + len(hook)] = hook
    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)
    parsed = pefile.PE(data=final, fast_load=False)
    if parsed.FILE_HEADER.NumberOfSections != 5:
        raise RuntimeError(f"Diagnostic section was not registered in {path.name}")
    section = parsed.sections[-1]
    if (
        section.Name != DIAG_SECTION_NAME
        or section.VirtualAddress != DIAG_SECTION_RVA
        or section.PointerToRawData != raw_pointer
        or section.SizeOfRawData != DIAG_SECTION_SIZE
        or section.Characteristics != DIAG_SECTION_CHARACTERISTICS
    ):
        raise RuntimeError(f"Diagnostic section metadata mismatch in {path.name}")
    if final[raw_pointer : raw_pointer + DIAG_SECTION_SIZE] != payload:
        raise RuntimeError(f"Diagnostic section payload mismatch in {path.name}")

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    instruction = next(decoder.disasm(final[entry_offset : entry_offset + 5], NATIVE_EFFECT_VA))
    if (
        instruction.mnemonic != "jmp"
        or not instruction.operands
        or instruction.operands[0].type != X86_OP_IMM
        or int(instruction.operands[0].imm) != WRAPPER_VA
    ):
        raise RuntimeError(f"Native effect hook target mismatch in {path.name}")

    restored = bytearray(final[: len(original)])
    restored[entry_offset : entry_offset + len(NATIVE_EFFECT_ORIGINAL)] = NATIVE_EFFECT_ORIGINAL
    restored[section_table_end : section_table_end + 40] = original_header_fields["new_section_header_slot"]
    restored[section_count_offset : section_count_offset + 2] = original_header_fields["section_count"]
    restored[size_of_code_offset : size_of_code_offset + 4] = original_header_fields["size_of_code"]
    restored[size_of_image_offset : size_of_image_offset + 4] = original_header_fields["size_of_image"]
    restored[checksum_offset : checksum_offset + 4] = original_header_fields["checksum"]
    if bytes(restored) != original:
        raise RuntimeError(f"Full rollback reconstruction failed for {path.name}")

    path.write_bytes(final)
    return {
        "name": path.name,
        "source_size": len(original),
        "output_size": len(final),
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "hook": {
            "va": NATIVE_EFFECT_VA,
            "file_offset": entry_offset,
            "source_hex": NATIVE_EFFECT_ORIGINAL.hex(" "),
            "diagnostic_hex": hook.hex(" "),
            "rollback_hex": NATIVE_EFFECT_ORIGINAL.hex(" "),
            "target_va": WRAPPER_VA,
        },
        "new_section": {
            "name": DIAG_SECTION_NAME.rstrip(b"\0").decode("ascii"),
            "rva": DIAG_SECTION_RVA,
            "va": DIAG_SECTION_VA,
            "raw_pointer": raw_pointer,
            "raw_size": DIAG_SECTION_SIZE,
            "virtual_size": DIAG_SECTION_SIZE,
            "characteristics": DIAG_SECTION_CHARACTERISTICS,
            "payload_sha256": sha256_bytes(payload),
        },
        "header_offsets": {
            "section_table_new_entry": section_table_end,
            "number_of_sections": section_count_offset,
            "size_of_code": size_of_code_offset,
            "size_of_image": size_of_image_offset,
            "checksum": checksum_offset,
        },
        "payload": payload_meta,
        "exact_contiguous_differences_with_common_length": contiguous_differences(
            original, final[: len(original)]
        ),
        "appended_bytes": len(final) - len(original),
        "rollback_reconstructs_source": True,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与诊断说明

这是从正式 HOTA_NEW_HERO_V1.05 重新构建的只读路径诊断包。安装本包会覆盖并移除已撤回 UI_TEST1 的错误 EXE。

安装：
1. 将压缩包内全部文件解压到 HotA 1.8.0 游戏根目录，覆盖同名文件。
2. 使用平时的 h3hota HD.exe 启动。

最小测试（不要真正点击施法）：
1. 使用尤兰德或阿斯特拉进入战斗并打开魔法书，查看一次治愈术数值。
2. 选择治愈术，把鼠标依次移到一个存活己方单位和一个可选己方尸体上，只观察底部提示，不要点击施法。
3. 退出游戏，把游戏根目录新生成的 {LOG_FILENAME} 上传给 Codex。

诊断包不会修正显示值，也不会修改原生函数返回值。它只记录两名英雄的治愈通用效果计算调用者、英雄、目标指针、输入值和原生返回值。实际治疗/复活、日志、动画、音效和正式 V1.05 的全部资源保持不变。
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

    payload, payload_meta = build_payload()
    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_files = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    executable_reports = [
        patch_executable(package_root / name, payload, payload_meta) for name in EXE_NAMES
    ]

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
    allowed = set(EXE_NAMES) | {instruction_files[0].name}
    if changed != allowed:
        raise RuntimeError(f"Unexpected package changes: {sorted(changed ^ allowed)}")
    for relative, digest in source_files.items():
        if relative not in allowed and package_hashes.get(relative) != digest:
            raise RuntimeError(f"Inherited V1.05 file changed: {relative}")

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
        "payload": payload_meta,
        "executables": executable_reports,
        "static_verification": {
            "v105_source_hashes_verified": True,
            "new_section_added_at_exact_image_boundary": True,
            "no_existing_zero_region_or_runtime_state_used": True,
            "hook_prologue_and_target_verified": True,
            "wrapper_filter_mode": payload_meta.get("filter_mode", "Uland/Astra Cure only"),
            "wrapped_calls_return_exact_native_result": True,
            "both_executables_receive_identical_payload": True,
            "full_header_hook_size_rollback_passed": True,
            "only_expected_package_files_changed": True,
            "zip_crc_and_member_checks_passed": True,
        },
        "runtime_acceptance": {
            "status": "pending returned UI path log",
            "minimum_test": [
                "open Cure spellbook once",
                "hover one living friendly target without casting",
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
    for item in executable_reports:
        print(f"{item['name']}: {item['output_sha256']}")
    print(f"Isolated section payload: {sha256_bytes(payload)}")
    print(f"Runtime log: {LOG_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
