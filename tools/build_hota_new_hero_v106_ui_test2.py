#!/usr/bin/env python3
"""Build V1.06 UI_TEST2 from formal V1.05.

The build corrects the two HotA.dll UI paths proven by UIDIAG04:

* living-target Cure hover uses the accepted F7 total for the actual stack;
* Cure spell-book text shows the current tier-1..tier-7 F7 range.

Gameplay, corpse targeting, resurrection, battle logs, visuals and audio are
inherited byte-for-byte from formal V1.05.
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

from build_hota_new_hero_v1 import EXE_NAMES, deterministic_zip, extract_zip_safely, safe_recreate_directory
from build_hota_new_hero_v104 import assemble, va_to_offset
from build_hota_new_hero_v105 import build_f7_formula_bonus, build_f7_ui_helper


BUILD_NAME = "HOTA_NEW_HERO_V1.06_UI_TEST2"
SOURCE_NAME = "HOTA_NEW_HERO_V1.05"
SOURCE_ZIP_SHA256 = "fcadf14fbbb411acef05def01b1b5a705b5cad4e2d473c8068677e9f0ef93d80"
SOURCE_HOTA_DLL_SHA256 = "bfcd3c314da10808b5a2962b1b45a88b31c33984a36834acbe7396073ced3b22"
SOURCE_EXE_SHA256 = {
    "h3hota.exe": "2e64a368d7e5d0cdebc3deaa8bf0beb37649a32f2201ea1c07306cba08b78abf",
    "h3hota HD.exe": "22e86983d225d88240c1c5c51c11e2f20ea5cc4ff69e9341c9c870f42915831e",
}

HOTA_DLL_NAME = "HotA.dll"
HOTA_IMAGE_BASE = 0x10000000
DIAG_SECTION_NAME = b".cureui\0"
SECTION_SIZE = 0x1000
SECTION_CHARACTERISTICS = 0xE0000020

HOVER_PATCH_VA = 0x1006DA00
HOVER_ORIGINAL = bytes.fromhex("56 FF 73 78 BA 60 62 4E 00 8B C8 55 FF D2 03 F0")
BOOK_PATCH_VA = 0x1013D8D1
BOOK_ORIGINAL = bytes.fromhex("E9 23 01 00 00")

HOVER_HELPER_OFFSET = 0x000
BOOK_HELPER_OFFSET = 0x200
HOTA_FORMATTER_VA = 0x102051F0
BOOK_NATIVE_COMMON_VA = 0x1013D9F9
BOOK_AFTER_CLEANUP_VA = 0x1013DA0F

NATIVE_SPECIALTY_VA = 0x004E6260
SPECIAL_TERRAIN_VA = 0x004E5210
SPELL_EXPERTISE_VA = 0x004E52F0
FORMULA_TOTAL_VA = 0x0065DE40
FORMULA_UI_VA = 0x0065DF00
CURE_SPELL_ID = 37


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def relative_call(source_va: int, target_va: int) -> bytes:
    return b"\xE8" + struct.pack("<i", target_va - (source_va + 5))


def relative_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5))


def validate_formula_helpers(package_root: Path) -> dict[str, str]:
    expected_total, _ = build_f7_formula_bonus()
    expected_ui, _ = build_f7_ui_helper()
    hashes: dict[str, str] = {}
    for name in EXE_NAMES:
        path = package_root / name
        data = path.read_bytes()
        if sha256_bytes(data) != SOURCE_EXE_SHA256[name]:
            raise RuntimeError(f"Unexpected formal V1.05 source hash for {name}")
        pe = pefile.PE(data=data, fast_load=False)
        total_offset = va_to_offset(pe, FORMULA_TOTAL_VA)
        ui_offset = va_to_offset(pe, FORMULA_UI_VA)
        if data[total_offset : total_offset + len(expected_total)] != expected_total:
            raise RuntimeError(f"F7 total helper mismatch in {name}")
        if data[ui_offset : ui_offset + len(expected_ui)] != expected_ui:
            raise RuntimeError(f"F7 UI helper mismatch in {name}")
        hashes[name] = sha256_bytes(data)
    return hashes


def build_payload(section_va: int) -> tuple[bytes, dict[str, Any]]:
    hover_helper_va = section_va + HOVER_HELPER_OFFSET
    book_helper_va = section_va + BOOK_HELPER_OFFSET

    # Entry registers at HOVER_PATCH_VA:
    #   EAX = current hero, EBX = actual combat stack, EBP = spell id,
    #   ESI = native base effect, [caller ESP+0x20] = effective spell power.
    # The helper returns the final preview total in EAX for every path.
    hover_source = f"""
    push ebp
    mov ebp, esp
    sub esp, 0x10
    push ebx
    push esi
    push edi
    mov edi, eax
    mov dword ptr [ebp - 0x04], esi
    mov eax, dword ptr [ebp]
    mov dword ptr [ebp - 0x08], eax
    mov eax, dword ptr [ebp + 0x28]
    mov dword ptr [ebp - 0x0c], eax
    mov eax, dword ptr [edi + 0x1a]
    cmp eax, 0x19
    je maybe_specialist
    cmp eax, 0xaa
    jne native
maybe_specialist:
    cmp dword ptr [ebp - 0x08], {CURE_SPELL_ID}
    jne native
    mov ecx, edi
    mov eax, {SPECIAL_TERRAIN_VA:#x}
    call eax
    push eax
    push {CURE_SPELL_ID}
    mov ecx, edi
    mov eax, {SPELL_EXPERTISE_VA:#x}
    call eax
    cmp eax, 1
    jle water_zero
    sub eax, 1
    cmp eax, 2
    jle water_capped
    mov eax, 2
water_capped:
    imul eax, eax, 10
    jmp water_ready
water_zero:
    xor eax, eax
water_ready:
    mov dword ptr [ebp - 0x10], eax
    push eax
    push edi
    push dword ptr [ebp - 0x0c]
    push ebx
    mov eax, {FORMULA_TOTAL_VA:#x}
    call eax
    jmp finished
native:
    push dword ptr [ebp - 0x04]
    push dword ptr [ebx + 0x78]
    push dword ptr [ebp - 0x08]
    mov ecx, edi
    mov eax, {NATIVE_SPECIALTY_VA:#x}
    call eax
    add eax, dword ptr [ebp - 0x04]
finished:
    pop edi
    pop esi
    pop ebx
    mov esp, ebp
    pop ebp
    ret
    """

    # Entry is a JMP from the Cure-only spell-book branch. Stack contains the
    # localized Cure format pointer followed by the already-computed native
    # value. Non-specialists jump straight back to the original common path.
    # Specialists discard those two items, calculate n=1 and n=7 through the
    # accepted V1.05 UI helper, expand the first localized %d into %d-%d, then
    # reproduce the skipped post-format state update before returning.
    book_source = f"""
    mov eax, dword ptr [ebx + 0x1a]
    cmp eax, 0x19
    je specialist
    cmp eax, 0xaa
    jne native
specialist:
    pop eax
    add esp, 4
    push ebp
    mov ebp, esp
    sub esp, 0x1a0
    push ebx
    push esi
    push edi
    mov dword ptr [ebp - 0x04], eax
    push 0
    push 0
    push {CURE_SPELL_ID}
    mov ecx, ebx
    mov eax, {FORMULA_UI_VA:#x}
    call eax
    mov dword ptr [ebp - 0x08], eax
    push 0
    push 6
    push {CURE_SPELL_ID}
    mov ecx, ebx
    mov eax, {FORMULA_UI_VA:#x}
    call eax
    mov dword ptr [ebp - 0x0c], eax
    mov esi, dword ptr [ebp - 0x04]
    lea edi, dword ptr [ebp - 0x1a0]
    mov ecx, 0x170
    xor edx, edx
copy_format:
    cmp ecx, 6
    jb format_done
    mov al, byte ptr [esi]
    test al, al
    je format_done
    test edx, edx
    jne copy_one
    cmp al, 0x25
    jne copy_one
    cmp byte ptr [esi + 1], 0x64
    jne copy_one
    mov byte ptr [edi], 0x25
    mov byte ptr [edi + 1], 0x64
    mov byte ptr [edi + 2], 0x2d
    mov byte ptr [edi + 3], 0x25
    mov byte ptr [edi + 4], 0x64
    add esi, 2
    add edi, 5
    sub ecx, 5
    mov edx, 1
    jmp copy_format
copy_one:
    mov byte ptr [edi], al
    inc esi
    inc edi
    dec ecx
    jmp copy_format
format_done:
    mov byte ptr [edi], 0
    test edx, edx
    je single_value
    push dword ptr [ebp - 0x0c]
    push dword ptr [ebp - 0x08]
    lea eax, dword ptr [ebp - 0x1a0]
    push eax
    push 0x300
    push 0x697428
    call {HOTA_FORMATTER_VA:#x}
    add esp, 0x14
    jmp formatted
single_value:
    push dword ptr [ebp - 0x08]
    lea eax, dword ptr [ebp - 0x1a0]
    push eax
    push 0x300
    push 0x697428
    call {HOTA_FORMATTER_VA:#x}
    add esp, 0x10
formatted:
    pop edi
    pop esi
    pop ebx
    mov esp, ebp
    pop ebp
    add dword ptr [edi + 0x10], -0x0c
    jmp {BOOK_AFTER_CLEANUP_VA:#x}
native:
    jmp {BOOK_NATIVE_COMMON_VA:#x}
    """

    payload = bytearray(SECTION_SIZE)
    components: list[dict[str, Any]] = []
    for name, va, limit, source in [
        ("living_target_f7_preview", hover_helper_va, book_helper_va, hover_source),
        ("localized_spellbook_f7_range", book_helper_va, section_va + 0x600, book_source),
    ]:
        code = assemble(source, va)
        if va + len(code) > limit:
            raise RuntimeError(f"{name} exceeds assigned section slot: {len(code)} bytes")
        start = va - section_va
        payload[start : start + len(code)] = code
        components.append({
            "name": name,
            "va_at_preferred_base": va,
            "length": len(code),
            "limit_va_at_preferred_base": limit,
            "assembly": source.strip(),
        })
    return bytes(payload), {
        "position_independent_inside_hota_dll": True,
        "section_va_at_preferred_base": section_va,
        "hover_helper_va_at_preferred_base": hover_helper_va,
        "book_helper_va_at_preferred_base": book_helper_va,
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
        raise RuntimeError("Unexpected HotA.dll Authenticode overlay")

    hover_offset = pe.get_offset_from_rva(HOVER_PATCH_VA - HOTA_IMAGE_BASE)
    book_offset = pe.get_offset_from_rva(BOOK_PATCH_VA - HOTA_IMAGE_BASE)
    if original[hover_offset : hover_offset + len(HOVER_ORIGINAL)] != HOVER_ORIGINAL:
        raise RuntimeError("Living hover source block mismatch")
    if original[book_offset : book_offset + len(BOOK_ORIGINAL)] != BOOK_ORIGINAL:
        raise RuntimeError("Spell-book Cure branch source jump mismatch")

    pe_offset = pe.DOS_HEADER.e_lfanew
    section_table_end = (
        pe_offset + 24 + pe.FILE_HEADER.SizeOfOptionalHeader
        + pe.FILE_HEADER.NumberOfSections * 40
    )
    first_raw = min(section.PointerToRawData for section in pe.sections if section.PointerToRawData)
    if first_raw - section_table_end < 40:
        raise RuntimeError("No room for HotA.dll UI section header")
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
        raise RuntimeError("New UI section is not at the exact image boundary")
    section_va = HOTA_IMAGE_BASE + section_rva
    hover_helper_va = section_va + HOVER_HELPER_OFFSET
    book_helper_va = section_va + BOOK_HELPER_OFFSET
    payload, payload_meta = build_payload(section_va)

    hover_patch = (
        relative_call(HOVER_PATCH_VA, hover_helper_va)
        + bytes.fromhex("89 C6")
    ).ljust(len(HOVER_ORIGINAL), b"\x90")
    book_patch = relative_jump(BOOK_PATCH_VA, book_helper_va)

    patched = bytearray(original)
    patched[hover_offset : hover_offset + len(hover_patch)] = hover_patch
    patched[book_offset : book_offset + len(book_patch)] = book_patch
    patched.extend(payload)
    patched[section_table_end : section_table_end + 40] = struct.pack(
        "<8sIIIIIIHHI",
        DIAG_SECTION_NAME,
        SECTION_SIZE,
        section_rva,
        SECTION_SIZE,
        raw_pointer,
        0,
        0,
        0,
        0,
        SECTION_CHARACTERISTICS,
    )

    section_count_offset = pe_offset + 6
    size_of_code_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfCode")
    size_of_image_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfImage")
    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    header_ranges = [
        (section_count_offset, 2),
        (size_of_code_offset, 4),
        (size_of_image_offset, 4),
        (checksum_offset, 4),
        (section_table_end, 40),
    ]
    struct.pack_into("<H", patched, section_count_offset, 7)
    struct.pack_into("<I", patched, size_of_code_offset, pe.OPTIONAL_HEADER.SizeOfCode + SECTION_SIZE)
    struct.pack_into("<I", patched, size_of_image_offset, section_rva + SECTION_SIZE)
    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)

    parsed = pefile.PE(data=final, fast_load=False)
    if parsed.FILE_HEADER.NumberOfSections != 7:
        raise RuntimeError("HotA.dll UI section was not registered")
    section = parsed.sections[-1]
    if (
        section.Name != DIAG_SECTION_NAME
        or section.VirtualAddress != section_rva
        or section.PointerToRawData != raw_pointer
        or section.SizeOfRawData != SECTION_SIZE
        or section.Characteristics != SECTION_CHARACTERISTICS
    ):
        raise RuntimeError("HotA.dll UI section metadata mismatch")
    if final[raw_pointer : raw_pointer + SECTION_SIZE] != payload:
        raise RuntimeError("HotA.dll UI payload mismatch")

    restored = bytearray(final[: len(original)])
    restored[hover_offset : hover_offset + len(HOVER_ORIGINAL)] = HOVER_ORIGINAL
    restored[book_offset : book_offset + len(BOOK_ORIGINAL)] = BOOK_ORIGINAL
    for start, length in header_ranges:
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
        "hover_patch": {
            "va_at_preferred_base": HOVER_PATCH_VA,
            "file_offset": hover_offset,
            "source_hex": HOVER_ORIGINAL.hex(" "),
            "test_hex": hover_patch.hex(" "),
            "helper_va_at_preferred_base": hover_helper_va,
        },
        "book_patch": {
            "va_at_preferred_base": BOOK_PATCH_VA,
            "file_offset": book_offset,
            "source_hex": BOOK_ORIGINAL.hex(" "),
            "test_hex": book_patch.hex(" "),
            "helper_va_at_preferred_base": book_helper_va,
        },
        "new_section": {
            "name": DIAG_SECTION_NAME.rstrip(b"\0").decode("ascii"),
            "rva": section_rva,
            "va_at_preferred_base": section_va,
            "raw_pointer": raw_pointer,
            "size": SECTION_SIZE,
            "characteristics": SECTION_CHARACTERISTICS,
            "payload_sha256": sha256_bytes(payload),
        },
        "payload": payload_meta,
        "rollback_reconstructs_source": True,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与测试说明

这是从正式 HOTA_NEW_HERO_V1.05 重新构建的治愈界面测试包，不是正式版本。

安装：
1. 将压缩包内全部文件解压到 HotA 1.8.0 游戏根目录，覆盖同名文件。
2. 使用平时的 h3hota HD.exe 启动。

本轮只验证两个已经由 UIDIAG04 精确定位的 HotA 界面入口：
- 尤兰德/阿斯特拉将治愈术悬停在存活友方兵队上时，底部治疗点数按正式 V1.05 F7 公式和目标实际等级显示；
- 两名英雄的魔法书治愈说明显示当前1—7级生物的治疗量范围，例如初始 L=1、P=1、初级水系时显示40-60。

最小测试：
1. 打开治愈术魔法书，确认初始范围为40-60。
2. 将治愈术依次悬停在1级兵、3级兵和7级兵上；初始条件下应分别显示40、46、60。
3. 悬停尸体时仍只显示“治愈”；本测试包不触碰尸体目标提示，以免干扰已经稳定的永久复活路径。
4. 不需要实际施法；若愿意，可额外施放一次确认治疗/复活和战斗日志没有回归。

普通英雄仍显示原版治愈数值。实际治疗、永久复活、群体循环、战斗日志、动画和音效均继承正式 V1.05，不在本轮修改范围内。
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
    exe_hashes = validate_formula_helpers(package_root)
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
            raise RuntimeError("UI test ZIP failed CRC validation")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("UI test ZIP member set changed")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "test_only": True,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "source_file_hashes": source_files,
        "package_file_hashes": package_hashes,
        "changed_package_files": sorted(changed),
        "formal_exe_hashes_and_f7_helpers_verified": exe_hashes,
        "hota_dll": dll_report,
        "behavior_scope": {
            "living_specialist_cure_hover": "exact F7 target total",
            "specialist_cure_spellbook": "localized tier-1..tier-7 F7 range",
            "corpse_hover": "unchanged; still Cure text only",
            "normal_heroes": "native behavior",
            "gameplay_and_logs": "byte-inherited from formal V1.05",
        },
        "static_verification": {
            "formal_v105_source_hashes_verified": True,
            "formal_f7_total_and_ui_helpers_verified_in_both_exes": True,
            "new_section_added_at_exact_image_boundary": True,
            "aslr_safe_relative_hota_internal_transfers": True,
            "hook_sources_and_targets_verified": True,
            "full_header_hooks_size_rollback_passed": True,
            "only_hota_dll_and_installation_text_changed": True,
            "zip_crc_and_member_checks_passed": True,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
