#!/usr/bin/env python3
"""Build the first functional V1.1 fixed-Luck test from formal V1.06.

Melodia (hero 29) and Daremyth (hero 43) return final Luck +3 after the
native cursed-ground / Hourglass suppression gate.  All ordinary numeric
modifiers are bypassed for those two heroes; native hard-disable gates remain.
The package also updates their starting skills/spells and Chinese specialty
resources.  It deliberately remains a TEST build until runtime acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
import zlib
from pathlib import Path
from typing import Any

import capstone
import pefile
from capstone.x86_const import X86_OP_IMM

from build_hota_new_hero_v1 import (
    EXE_NAMES,
    LANGUAGE_ARCHIVES,
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)
from build_hota_new_hero_v103 import IMAGE_BASE
from build_hota_new_hero_v104 import assemble, contiguous_differences
from extract_lod import DIRECTORY_OFFSET, ENTRY_SIZE, parse_entries, payload


BUILD_NAME = "HOTA_NEW_HERO_V1.1_LUCK_TEST1"
SOURCE_NAME = "HOTA_NEW_HERO_V1.06"
SOURCE_ZIP_SHA256 = "f1f93628ee6be41056a4301377c50904b3637e8c5da00e5f58d2412685e3b00f"
SOURCE_EXE_SHA256 = {
    "h3hota.exe": "2e64a368d7e5d0cdebc3deaa8bf0beb37649a32f2201ea1c07306cba08b78abf",
    "h3hota HD.exe": "22e86983d225d88240c1c5c51c11e2f20ea5cc4ff69e9341c9c870f42915831e",
}
SOURCE_RESOURCE_SHA256 = {
    "Data/HotA_lng.lod": "0f1b05667c648c4a672e367d47da7f41983ef6a1698939af501bc30a649a2f11",
    "Data/HotA_l_ext.lod": "31fe8b8c6d4370fbd2e2ab814ca3e0f3c1732024b7bca3bdd870f985b8e2e7fc",
    "_HD3_Data/Packs/H3中文-基础资源/HeroSpec.txt":
        "56c114f3601fb05e4d9a231405b41b449c05f904d6066ce7339410f9f401ea95",
}

MELODIA_ID = 29
DAREMYTH_ID = 43
FIXED_LUCK = 3
HOURGLASS_ARTIFACT_ID = 0x55
MIRTH_SPELL_ID = 49

LUCK_POST_GATE_VA = 0x004E39E8
LUCK_POST_GATE_CONTINUE_VA = 0x004E39EE
LUCK_POST_GATE_ORIGINAL = bytes.fromhex("8A 86 D2 00 00 00")
HOURGLASS_SELF_SCAN_VA = 0x004E3964
HOURGLASS_ENEMY_SCAN_VA = 0x004E39A9
HARD_SUPPRESSION_RETURN_VA = 0x004E39DE

LUCK_SECTION_NAME = b".luck3\0\0"
EXPECTED_NEW_SECTION_HEADER_SLOT = bytes.fromhex(
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
    "20 75 6E 77 72 61 70 70"
)
LUCK_SECTION_RVA = 0x002E7000
LUCK_SECTION_VA = IMAGE_BASE + LUCK_SECTION_RVA
LUCK_SECTION_SIZE = 0x1000
LUCK_SECTION_CHARACTERISTICS = 0xE0000020
LUCK_WRAPPER_VA = LUCK_SECTION_VA

MELODIA_RECORD_OFFSET = 0x0027A83C
DAREMYTH_RECORD_OFFSET = 0x0027AD44
MELODIA_RECORD_SOURCE = bytes.fromhex(
    "01 00 00 00 03 00 00 00 03 00 00 00 07 00 00 00 "
    "01 00 00 00 09 00 00 00 01 00 00 00 01 00 00 00 "
    "33 00 00 00 0E 00 00 00 10 00 00 00"
)
DAREMYTH_RECORD_SOURCE = bytes.fromhex(
    "01 00 00 00 04 00 00 00 05 00 00 00 07 00 00 00 "
    "01 00 00 00 18 00 00 00 01 00 00 00 01 00 00 00 "
    "33 00 00 00 1C 00 00 00 1E 00 00 00"
)

LOOSE_HEROSPEC_RELATIVE = "_HD3_Data/Packs/H3中文-基础资源/HeroSpec.txt"
ARCHIVE_OLD_SENTENCE = "英雄施放的幸运魔法总是提高3点幸运。"
LOOSE_OLD_SENTENCE = (
    "使用幸运之神魔法时效果大增，但还要取决于英雄级别与目标级别之差"
    "(目标的级别越低，效果越好)。"
)
SPECIALTY_SENTENCE = "英雄所率领部队的幸运值始终为+3。"
MECHANICS_NOTE = "厄运沙漏等直接禁止幸运生效的效果仍然有效。"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def relative_jump(source_va: int, target_va: int, width: int) -> bytes:
    if width < 5:
        raise ValueError("relative jump needs at least five bytes")
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5)) + b"\x90" * (width - 5)


def build_luck_payload() -> tuple[bytes, dict[str, Any]]:
    source = f"""
    test esi, esi
    je native
    mov eax, dword ptr [esi + 0x1a]
    cmp eax, {MELODIA_ID}
    je forced
    cmp eax, {DAREMYTH_ID}
    jne native
forced:
    mov eax, {FIXED_LUCK}
    pop edi
    pop esi
    mov esp, ebp
    pop ebp
    ret 0x0c
native:
    mov al, byte ptr [esi + 0xd2]
    push {LUCK_POST_GATE_CONTINUE_VA:#x}
    ret
    """
    code = assemble(source, LUCK_WRAPPER_VA)
    if len(code) > 0x100:
        raise RuntimeError("Luck wrapper unexpectedly exceeds its isolated slot")
    result = bytearray(LUCK_SECTION_SIZE)
    result[: len(code)] = code
    return bytes(result), {
        "wrapper_va": LUCK_WRAPPER_VA,
        "wrapper_length": len(code),
        "wrapper_hex": code.hex(" "),
        "assembly": source.strip(),
        "fixed_hero_ids": [MELODIA_ID, DAREMYTH_ID],
        "fixed_luck": FIXED_LUCK,
        "native_continue_va": LUCK_POST_GATE_CONTINUE_VA,
    }


def expected_hero_records() -> tuple[bytes, bytes]:
    melodia = bytearray(MELODIA_RECORD_SOURCE)
    struct.pack_into("<I", melodia, 0x14, 8)  # Basic Luck -> Basic Mysticism
    struct.pack_into("<I", melodia, 0x20, MIRTH_SPELL_ID)
    daremyth = bytearray(DAREMYTH_RECORD_SOURCE)
    struct.pack_into("<I", daremyth, 0x20, MIRTH_SPELL_ID)
    return bytes(melodia), bytes(daremyth)


def patch_executable(path: Path, section_payload: bytes, payload_meta: dict[str, Any]) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_EXE_SHA256[path.name]:
        raise RuntimeError(f"Unexpected {SOURCE_NAME} source hash for {path.name}")
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != IMAGE_BASE or pe.OPTIONAL_HEADER.DllCharacteristics & 0x40:
        raise RuntimeError(f"Unexpected image base or ASLR state in {path.name}")
    if pe.FILE_HEADER.NumberOfSections != 4 or pe.OPTIONAL_HEADER.SizeOfImage != LUCK_SECTION_RVA:
        raise RuntimeError(f"Unexpected source section layout in {path.name}")
    if pe.OPTIONAL_HEADER.FileAlignment != 0x1000 or pe.OPTIONAL_HEADER.SectionAlignment != 0x1000:
        raise RuntimeError(f"Unexpected PE alignment in {path.name}")
    if len(section_payload) != LUCK_SECTION_SIZE:
        raise RuntimeError("Luck section payload size mismatch")

    hook_offset = pe.get_offset_from_rva(LUCK_POST_GATE_VA - IMAGE_BASE)
    if original[hook_offset : hook_offset + len(LUCK_POST_GATE_ORIGINAL)] != LUCK_POST_GATE_ORIGINAL:
        raise RuntimeError(f"Luck post-gate source mismatch in {path.name}")
    if original[MELODIA_RECORD_OFFSET : MELODIA_RECORD_OFFSET + len(MELODIA_RECORD_SOURCE)] != MELODIA_RECORD_SOURCE:
        raise RuntimeError(f"Melodia source record mismatch in {path.name}")
    if original[DAREMYTH_RECORD_OFFSET : DAREMYTH_RECORD_OFFSET + len(DAREMYTH_RECORD_SOURCE)] != DAREMYTH_RECORD_SOURCE:
        raise RuntimeError(f"Daremyth source record mismatch in {path.name}")

    native_guard = original[
        pe.get_offset_from_rva(HOURGLASS_SELF_SCAN_VA - IMAGE_BASE):
        pe.get_offset_from_rva(LUCK_POST_GATE_VA - IMAGE_BASE)
    ]
    if native_guard.count(bytes([HOURGLASS_ARTIFACT_ID])) < 2:
        raise RuntimeError(f"Native Hourglass scans were not found before the hook in {path.name}")
    suppression_offset = pe.get_offset_from_rva(HARD_SUPPRESSION_RETURN_VA - IMAGE_BASE)
    if original[suppression_offset : suppression_offset + 8] != bytes.fromhex("5F 33 C0 5E 8B E5 5D C2"):
        raise RuntimeError(f"Native hard-suppression return mismatch in {path.name}")

    pe_offset = pe.DOS_HEADER.e_lfanew
    section_table_end = (
        pe_offset + 24 + pe.FILE_HEADER.SizeOfOptionalHeader + pe.FILE_HEADER.NumberOfSections * 40
    )
    first_raw = min(section.PointerToRawData for section in pe.sections if section.PointerToRawData)
    if first_raw - section_table_end < 40:
        raise RuntimeError(f"No room for isolated Luck section header in {path.name}")
    if original[section_table_end : section_table_end + 40] != EXPECTED_NEW_SECTION_HEADER_SLOT:
        raise RuntimeError(f"Unexpected fifth section-header slot in {path.name}")
    raw_pointer = align(len(original), pe.OPTIONAL_HEADER.FileAlignment)
    if raw_pointer != len(original):
        raise RuntimeError(f"Unexpected source overlay/alignment in {path.name}")

    patched = bytearray(original)
    patched.extend(section_payload)
    patched[section_table_end : section_table_end + 40] = struct.pack(
        "<8sIIIIIIHHI",
        LUCK_SECTION_NAME,
        LUCK_SECTION_SIZE,
        LUCK_SECTION_RVA,
        LUCK_SECTION_SIZE,
        raw_pointer,
        0,
        0,
        0,
        0,
        LUCK_SECTION_CHARACTERISTICS,
    )
    section_count_offset = pe_offset + 6
    size_of_code_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfCode")
    size_of_image_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfImage")
    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    original_header = {
        "section_count": original[section_count_offset : section_count_offset + 2],
        "size_of_code": original[size_of_code_offset : size_of_code_offset + 4],
        "size_of_image": original[size_of_image_offset : size_of_image_offset + 4],
        "checksum": original[checksum_offset : checksum_offset + 4],
        "new_section_slot": original[section_table_end : section_table_end + 40],
    }
    struct.pack_into("<H", patched, section_count_offset, 5)
    struct.pack_into("<I", patched, size_of_code_offset, pe.OPTIONAL_HEADER.SizeOfCode + LUCK_SECTION_SIZE)
    struct.pack_into("<I", patched, size_of_image_offset, LUCK_SECTION_RVA + LUCK_SECTION_SIZE)

    hook = relative_jump(LUCK_POST_GATE_VA, LUCK_WRAPPER_VA, len(LUCK_POST_GATE_ORIGINAL))
    patched[hook_offset : hook_offset + len(hook)] = hook
    melodia_after, daremyth_after = expected_hero_records()
    patched[MELODIA_RECORD_OFFSET : MELODIA_RECORD_OFFSET + len(melodia_after)] = melodia_after
    patched[DAREMYTH_RECORD_OFFSET : DAREMYTH_RECORD_OFFSET + len(daremyth_after)] = daremyth_after

    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)

    parsed = pefile.PE(data=final, fast_load=False)
    if parsed.FILE_HEADER.NumberOfSections != 5:
        raise RuntimeError(f"Luck section was not registered in {path.name}")
    section = parsed.sections[-1]
    if (
        section.Name != LUCK_SECTION_NAME
        or section.VirtualAddress != LUCK_SECTION_RVA
        or section.PointerToRawData != raw_pointer
        or section.SizeOfRawData != LUCK_SECTION_SIZE
        or section.Characteristics != LUCK_SECTION_CHARACTERISTICS
    ):
        raise RuntimeError(f"Luck section metadata mismatch in {path.name}")
    if final[raw_pointer : raw_pointer + LUCK_SECTION_SIZE] != section_payload:
        raise RuntimeError(f"Luck section payload mismatch in {path.name}")

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    instruction = next(decoder.disasm(final[hook_offset : hook_offset + 5], LUCK_POST_GATE_VA))
    if (
        instruction.mnemonic != "jmp"
        or not instruction.operands
        or instruction.operands[0].type != X86_OP_IMM
        or int(instruction.operands[0].imm) != LUCK_WRAPPER_VA
    ):
        raise RuntimeError(f"Luck hook target mismatch in {path.name}")

    restored = bytearray(final[: len(original)])
    restored[hook_offset : hook_offset + len(LUCK_POST_GATE_ORIGINAL)] = LUCK_POST_GATE_ORIGINAL
    restored[MELODIA_RECORD_OFFSET : MELODIA_RECORD_OFFSET + len(MELODIA_RECORD_SOURCE)] = MELODIA_RECORD_SOURCE
    restored[DAREMYTH_RECORD_OFFSET : DAREMYTH_RECORD_OFFSET + len(DAREMYTH_RECORD_SOURCE)] = DAREMYTH_RECORD_SOURCE
    restored[section_table_end : section_table_end + 40] = original_header["new_section_slot"]
    restored[section_count_offset : section_count_offset + 2] = original_header["section_count"]
    restored[size_of_code_offset : size_of_code_offset + 4] = original_header["size_of_code"]
    restored[size_of_image_offset : size_of_image_offset + 4] = original_header["size_of_image"]
    restored[checksum_offset : checksum_offset + 4] = original_header["checksum"]
    if bytes(restored) != original:
        raise RuntimeError(f"Full executable rollback failed for {path.name}")

    path.write_bytes(final)
    return {
        "name": path.name,
        "source_size": len(original),
        "output_size": len(final),
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "hook": {
            "va": LUCK_POST_GATE_VA,
            "file_offset": hook_offset,
            "source_hex": LUCK_POST_GATE_ORIGINAL.hex(" "),
            "patched_hex": hook.hex(" "),
            "rollback_hex": LUCK_POST_GATE_ORIGINAL.hex(" "),
            "target_va": LUCK_WRAPPER_VA,
        },
        "hero_records": {
            "melodia": {
                "hero_id": MELODIA_ID,
                "file_offset": MELODIA_RECORD_OFFSET,
                "source_hex": MELODIA_RECORD_SOURCE.hex(" "),
                "patched_hex": melodia_after.hex(" "),
                "changes": "Basic Luck (9) -> Basic Mysticism (8); Fortune (51) -> Mirth (49)",
            },
            "daremyth": {
                "hero_id": DAREMYTH_ID,
                "file_offset": DAREMYTH_RECORD_OFFSET,
                "source_hex": DAREMYTH_RECORD_SOURCE.hex(" "),
                "patched_hex": daremyth_after.hex(" "),
                "changes": "skills unchanged; Fortune (51) -> Mirth (49)",
            },
        },
        "new_section": {
            "name": LUCK_SECTION_NAME.rstrip(b"\0").decode("ascii"),
            "rva": LUCK_SECTION_RVA,
            "va": LUCK_SECTION_VA,
            "raw_pointer": raw_pointer,
            "raw_size": LUCK_SECTION_SIZE,
            "characteristics": LUCK_SECTION_CHARACTERISTICS,
            "payload_sha256": sha256_bytes(section_payload),
        },
        "payload": payload_meta,
        "native_hard_suppression_bytes_unchanged": True,
        "rollback_reconstructs_source": True,
        "exact_contiguous_differences_with_common_length": contiguous_differences(original, final[: len(original)]),
        "appended_bytes": len(final) - len(original),
    }


def replace_exact_text(raw: bytes, old: str, new: str, expected_count: int) -> tuple[bytes, dict[str, Any]]:
    text = raw.decode("gb18030")
    actual_count = text.count(old)
    if actual_count != expected_count:
        raise RuntimeError(f"Expected {expected_count} specialty text matches, found {actual_count}")
    updated = text.replace(old, new)
    encoded = updated.encode("gb18030")
    return encoded, {
        "encoding": "gb18030",
        "replacement_count": actual_count,
        "old": old,
        "new": new,
        "source_sha256": sha256_bytes(raw),
        "output_sha256": sha256_bytes(encoded),
    }


def patch_lod(path: Path) -> dict[str, Any]:
    relative = path.relative_to(path.parents[1]).as_posix()
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_RESOURCE_SHA256[relative]:
        raise RuntimeError(f"Unexpected source hash for {relative}")
    entries = parse_entries(original)
    matches = [entry for entry in entries if str(entry["name"]).lower() == "herospec.txt"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one HeroSpec.txt in {relative}")
    entry = matches[0]
    member_source = payload(original, entry)
    member_after, text_report = replace_exact_text(
        member_source, ARCHIVE_OLD_SENTENCE, SPECIALTY_SENTENCE, 2
    )
    compressed = zlib.compress(member_after, 9)
    if len(compressed) >= len(member_after):
        stored = member_after
        compressed_size = 0
    else:
        stored = compressed
        compressed_size = len(compressed)
    output = bytearray(original)
    new_offset = len(output)
    output.extend(stored)
    directory_position = DIRECTORY_OFFSET + int(entry["index"]) * ENTRY_SIZE
    struct.pack_into(
        "<IIII",
        output,
        directory_position + 16,
        new_offset,
        len(member_after),
        int(entry["type"]),
        compressed_size,
    )
    final = bytes(output)
    reparsed = parse_entries(final)
    reparsed_entry = reparsed[int(entry["index"])]
    if payload(final, reparsed_entry) != member_after:
        raise RuntimeError(f"LOD repack verification failed for {relative}")
    path.write_bytes(final)
    return {
        "relative_path": relative,
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "source_size": len(original),
        "output_size": len(final),
        "entry_index": int(entry["index"]),
        "source_member_offset": int(entry["offset"]),
        "output_member_offset": new_offset,
        "source_member_size": int(entry["size"]),
        "output_member_size": len(member_after),
        "output_member_compressed_size": compressed_size,
        "member": text_report,
        "all_other_directory_entries_unchanged": True,
    }


def patch_loose_herospec(path: Path, package_root: Path) -> dict[str, Any]:
    relative = path.relative_to(package_root).as_posix()
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_RESOURCE_SHA256[relative]:
        raise RuntimeError(f"Unexpected source hash for {relative}")
    final, report = replace_exact_text(original, LOOSE_OLD_SENTENCE, SPECIALTY_SENTENCE, 2)
    path.write_bytes(final)
    report["relative_path"] = relative
    return report


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与测试说明

这是从正式 {SOURCE_NAME} 构建的幸运特长功能测试包，暂不替换 GitHub 的正式下载版。

本测试包修改：
1. 马洛迪亚与黛瑞丝所率领部队的幸运值固定为 +3，不受普通正负幸运数值影响。
2. {MECHANICS_NOTE}
3. 马洛迪亚初始技能改为初级智慧术 + 初级神秘术；初始魔法改为振奋。
4. 黛瑞丝初始技能保持初级智慧术 + 初级智力；初始魔法改为振奋。
5. 两人的幸运之神特长标签保留，详细说明更新为“{SPECIALTY_SENTENCE}”

安装：
1. 准备一份已经安装正式 {SOURCE_NAME} 的 HotA 1.8.0 游戏目录。
2. 将本压缩包内全部文件解压到游戏根目录并覆盖同名文件。
3. 使用平时的 h3hota HD.exe 启动。

请重点测试：
1. 分别使用马洛迪亚和黛瑞丝，确认部队幸运显示为 +3，并能正常触发幸运一击。
2. 施加负幸运、携带降幸运宝物、面对大恶魔等普通数值变化后，确认仍为 +3。
3. 任意一方装备厄运沙漏后，确认幸运一击被原生机制禁止；此时界面可能按原生逻辑显示 0。
4. 确认马洛迪亚初始技能为初级智慧术 + 初级神秘术，黛瑞丝技能不变，两人的魔法书均自带振奋而非幸运之神。
5. 分别启动标准 h3hota.exe 与 h3hota HD.exe，确认无闪退。

治愈、复活、治疗量界面、埃尔芙资源及 {SOURCE_NAME} 的其他功能全部继承不变。
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
        raise RuntimeError(f"Formal {SOURCE_NAME} ZIP hash mismatch")

    section_payload, payload_meta = build_luck_payload()
    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_files = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }

    executable_reports = [
        patch_executable(package_root / name, section_payload, payload_meta)
        for name in EXE_NAMES
    ]
    lod_reports = [patch_lod(package_root / relative) for relative in LANGUAGE_ARCHIVES]
    loose_report = patch_loose_herospec(package_root / LOOSE_HEROSPEC_RELATIVE, package_root)

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
    allowed = (
        set(EXE_NAMES)
        | set(LANGUAGE_ARCHIVES)
        | {LOOSE_HEROSPEC_RELATIVE, instruction_files[0].name}
    )
    if changed != allowed:
        raise RuntimeError(f"Unexpected package changes: {sorted(changed ^ allowed)}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Functional test ZIP failed CRC validation")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("Functional test ZIP member set changed")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "functional_test_only": True,
        "formal_release": False,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "source_file_hashes": source_files,
        "package_file_hashes": package_hashes,
        "changed_package_files": sorted(changed),
        "executables": executable_reports,
        "resources": lod_reports + [loose_report],
        "behavior": {
            "hero_ids": [MELODIA_ID, DAREMYTH_ID],
            "ordinary_final_luck": FIXED_LUCK,
            "ordinary_numeric_modifiers_bypassed": True,
            "native_hard_suppression_preserved": True,
            "hourglass_artifact_id": HOURGLASS_ARTIFACT_ID,
            "hourglass_self_scan_va": HOURGLASS_SELF_SCAN_VA,
            "hourglass_enemy_scan_va": HOURGLASS_ENEMY_SCAN_VA,
            "hard_suppression_return_va": HARD_SUPPRESSION_RETURN_VA,
            "hook_after_suppression_va": LUCK_POST_GATE_VA,
        },
        "static_verification": {
            "formal_v106_hashes_verified": True,
            "standard_and_hd_receive_identical_payload": True,
            "native_hard_suppression_precedes_hook": True,
            "hero_records_exact_source_and_output_verified": True,
            "new_section_added_at_exact_image_boundary": True,
            "full_executable_rollback_passed": True,
            "resource_replacement_count_exactly_two_per_source": True,
            "only_expected_package_files_changed": True,
            "zip_crc_and_member_checks_passed": True,
        },
        "runtime_acceptance": {
            "status": "pending user gameplay verification",
            "ordinary_luck": "both specialists display/return +3 despite numeric modifiers",
            "hourglass": "native hard-disable remains effective",
        },
    }
    manifest_path = output_root / f"{BUILD_NAME}_manifest.json"
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_root / f"{BUILD_NAME}_README.md").write_text(installation_text(), encoding="utf-8")
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    for item in executable_reports:
        print(f"{item['name']}: {item['output_sha256']}")
    print(f"Luck payload: {sha256_bytes(section_payload)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
