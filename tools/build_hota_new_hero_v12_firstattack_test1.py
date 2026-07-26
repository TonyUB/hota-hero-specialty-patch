#!/usr/bin/env python3
"""Build the first functional V1.2 guaranteed-first-attack test.

For Melodia (29) and Daremyth (43), each friendly combat stack's first active
melee or ranged attack command is guaranteed to use the native lucky-strike
flag.  Retaliations do not consume or inherit the guarantee.  Repeated hits
inside the same active command (double shot, sweep/ring attacks) inherit it.
After the first active command, native Luck calculation is used again.
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

import build_hota_new_hero_v11_luck_test1 as luck_v11
import build_hota_new_hero_v12_firstattack_diag01 as diag01
import build_hota_new_hero_v12_firstattack_diag03 as diag03
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


BUILD_NAME = "HOTA_NEW_HERO_V1.2_FIRSTATTACK_TEST1"
SOURCE_NAME = "HOTA_NEW_HERO_V1.11"
SOURCE_ZIP_SHA256 = "6d262426f4f5cd77ac9dd110dba8d97134d4602993eb284aa2ed2f4a4354bbde"
SOURCE_EXE_SHA256 = {
    "h3hota.exe": "2975214a0826067fbf59c03e896142ff14b48a882f8e8d678faa0aa5dff924e8",
    "h3hota HD.exe": "45965c8126c88d92232fcd09593e6c43decc6f50de9d979fb90343426efc1b1f",
}
SOURCE_RESOURCE_SHA256 = {
    "Data/HotA_lng.lod": "a13335e146c0e7c1c370837f976552d07568c8b76d9af71a5d9ca671fc2b5048",
    "Data/HotA_l_ext.lod": "b09c25b5a8dfb39e288b17bda83a2e934bf92d45b87cba6c3b4255c6d0d7af97",
    luck_v11.LOOSE_HEROSPEC_RELATIVE:
        "238761368de626ef842ef4eee5f5ee27df976a5ed43c94cc08a2c0c51f5c7b6b",
}

MELODIA_ID = 29
DAREMYTH_ID = 43
LOG_FILENAME = "hota_luck_firsttest01.bin"
RECORD_MAGIC = 0x314B5441
RECORD_SIZE = 96

LUCK_SECTION_NAME = diag01.LUCK_SECTION_NAME
LUCK_SECTION_RVA = diag01.LUCK_SECTION_RVA
LUCK_SECTION_VA = diag01.LUCK_SECTION_VA
LUCK_SECTION_SIZE = diag01.LUCK_SECTION_SIZE
LUCK_SECTION_RAW_OFFSET = diag01.LUCK_SECTION_RAW_OFFSET
LUCK_SECTION_CHARACTERISTICS = diag01.LUCK_SECTION_CHARACTERISTICS
SOURCE_LUCK_SECTION_SHA256 = diag01.SOURCE_LUCK_SECTION_SHA256

LUCK_GATE_HOOK_VA = luck_v11.LUCK_POST_GATE_VA
LUCK_GATE_HOOK_BYTES = bytes.fromhex("E9 13 36 20 00 90")
LUCK_GATE_CONTINUE_VA = luck_v11.LUCK_POST_GATE_CONTINUE_VA
BATTLE_MANAGER_PTR = diag01.BATTLE_MANAGER_PTR

BATTLE_RESET_HOOK_VA = 0x00463B71
BATTLE_RESET_ORIGINAL = bytes.fromhex("89 5E 3C 89 86 A8 32 01 00")
BATTLE_RESET_CONTINUE_VA = BATTLE_RESET_HOOK_VA + len(BATTLE_RESET_ORIGINAL)
RANGED_ACTION_HOOK_VA = 0x00478D70
RANGED_ACTION_ORIGINAL = bytes.fromhex("8B 4D 08 C6 86 30 40 01 00 01")
RANGED_ACTION_CONTINUE_VA = RANGED_ACTION_HOOK_VA + len(RANGED_ACTION_ORIGINAL)
MELEE_ACTION_HOOK_VA = 0x00478B94
MELEE_ACTION_ORIGINAL = bytes.fromhex("8B CE C6 86 30 40 01 00 01")
MELEE_ACTION_CONTINUE_VA = MELEE_ACTION_HOOK_VA + len(MELEE_ACTION_ORIGINAL)

LUCK_GATE_WRAPPER_VA = LUCK_SECTION_VA + 0x000
LOGGER_VA = LUCK_SECTION_VA + 0x200
ACTION_HELPER_VA = LUCK_SECTION_VA + 0x300
RESET_WRAPPER_VA = LUCK_SECTION_VA + 0x500
RANGED_WRAPPER_VA = LUCK_SECTION_VA + 0x580
MELEE_WRAPPER_VA = LUCK_SECTION_VA + 0x600
DATA_VA = LUCK_SECTION_VA + 0x800
DATA_LIMIT_VA = LUCK_SECTION_VA + LUCK_SECTION_SIZE

OLD_SPECIALTY_SENTENCE = luck_v11.SPECIALTY_SENTENCE
NEW_SPECIALTY_SENTENCE = (
    "英雄所率领的每支部队在每场战斗中首次主动攻击时必定触发幸运，"
    "之后按正常规则判定。"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def relative_jump(source_va: int, target_va: int, width: int) -> bytes:
    if width < 5:
        raise ValueError("relative jump needs at least five bytes")
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5)) + b"\x90" * (width - 5)


def build_exe_payload() -> tuple[bytes, dict[str, Any]]:
    filename = LOG_FILENAME.encode("ascii") + b"\0"
    filename_va = DATA_VA
    record_va = (filename_va + len(filename) + 3) & ~3
    handle_va = record_va + RECORD_SIZE
    written_va = handle_va + 4
    used_lo_va = written_va + 4
    used_hi_va = used_lo_va + 4
    command_attacker_va = used_hi_va + 4
    command_force_va = command_attacker_va + 4
    gate_mask_va = command_force_va + 4
    if gate_mask_va + 4 > DATA_LIMIT_VA:
        raise RuntimeError("Functional state exceeds .luck3 section")

    gate_source = f"""
    pushfd
    pushad
    test esi, esi
    je gate_done
    mov eax, dword ptr [esi + 0x1a]
    cmp eax, {MELODIA_ID}
    je gate_specialist
    cmp eax, {DAREMYTH_ID}
    jne gate_done
gate_specialist:
    mov ecx, dword ptr [{BATTLE_MANAGER_PTR:#x}]
    test ecx, ecx
    je gate_done
    mov edx, dword ptr [ecx + 0x53cc]
    cmp edx, esi
    jne gate_side_one
    or dword ptr [{gate_mask_va:#x}], 1
    jmp gate_done
gate_side_one:
    mov edx, dword ptr [ecx + 0x53d0]
    cmp edx, esi
    jne gate_done
    or dword ptr [{gate_mask_va:#x}], 2
gate_done:
    popad
    popfd
gate_native:
    mov al, byte ptr [esi + 0xd2]
    push {LUCK_GATE_CONTINUE_VA:#x}
    ret
    """
    logger_source = f"""
    push 0
    push 0x80
    push 4
    push 0
    push 3
    push 4
    push {filename_va:#x}
    call dword ptr [{diag01.IAT['CreateFileA']:#x}]
    cmp eax, -1
    je log_done
    mov dword ptr [{handle_va:#x}], eax
    mov dword ptr [{written_va:#x}], 0
    push 0
    push {written_va:#x}
    push {RECORD_SIZE}
    push {record_va:#x}
    push eax
    call dword ptr [{diag01.IAT['WriteFile']:#x}]
    push dword ptr [{handle_va:#x}]
    call dword ptr [{diag01.IAT['CloseHandle']:#x}]
log_done:
    ret
    """
    action_source = f"""
    pushfd
    pushad
    cld
    xor eax, eax
    mov edi, {record_va + 4:#x}
    mov ecx, 23
    rep stosd
    mov dword ptr [{command_attacker_va:#x}], ebx
    mov dword ptr [{command_force_va:#x}], 0
    mov eax, dword ptr [ebx + 0xf4]
    cmp eax, 1
    ja action_record
    mov edx, 1
    mov ecx, eax
    shl edx, cl
    test dword ptr [{gate_mask_va:#x}], edx
    jz action_record
    mov ecx, dword ptr [ebx + 0xf8]
    cmp ecx, 20
    ja action_record
    imul eax, eax, 21
    add eax, ecx
    mov ecx, eax
    and ecx, 31
    mov edx, 1
    shl edx, cl
    shr eax, 5
    test dword ptr [{used_lo_va:#x} + eax*4], edx
    jnz action_record
    or dword ptr [{used_lo_va:#x} + eax*4], edx
    mov dword ptr [{command_force_va:#x}], 1
action_record:
    mov dword ptr [{record_va + 4:#x}], 30
    mov dword ptr [{record_va + 8:#x}], ebx
    mov eax, dword ptr [esi + 0x3c]
    mov dword ptr [{record_va + 12:#x}], eax
    mov eax, dword ptr [esi + 0x40]
    mov dword ptr [{record_va + 16:#x}], eax
    mov eax, dword ptr [esi + 0x44]
    mov dword ptr [{record_va + 20:#x}], eax
    mov eax, dword ptr [esi + 0x13d6c]
    mov dword ptr [{record_va + 24:#x}], eax
    mov eax, dword ptr [ebx + 0xf4]
    mov dword ptr [{record_va + 28:#x}], eax
    mov eax, dword ptr [ebx + 0xf8]
    mov dword ptr [{record_va + 32:#x}], eax
    mov eax, dword ptr [{used_lo_va:#x}]
    mov dword ptr [{record_va + 36:#x}], eax
    mov eax, dword ptr [{used_hi_va:#x}]
    mov dword ptr [{record_va + 40:#x}], eax
    mov eax, dword ptr [{command_force_va:#x}]
    mov dword ptr [{record_va + 44:#x}], eax
    mov eax, dword ptr [{gate_mask_va:#x}]
    mov dword ptr [{record_va + 48:#x}], eax
    mov eax, {LOGGER_VA:#x}
    call eax
    popad
    popfd
    ret
    """
    reset_source = f"""
    pushfd
    pushad
    xor eax, eax
    mov dword ptr [{used_lo_va:#x}], eax
    mov dword ptr [{used_hi_va:#x}], eax
    mov dword ptr [{command_attacker_va:#x}], eax
    mov dword ptr [{command_force_va:#x}], eax
    mov dword ptr [{gate_mask_va:#x}], eax
    popad
    popfd
    mov dword ptr [esi + 0x3c], ebx
    mov dword ptr [esi + 0x132a8], eax
    jmp {BATTLE_RESET_CONTINUE_VA:#x}
    """
    ranged_source = f"""
    mov eax, {ACTION_HELPER_VA:#x}
    call eax
    mov ecx, dword ptr [ebp + 8]
    mov byte ptr [esi + 0x14030], 1
    jmp {RANGED_ACTION_CONTINUE_VA:#x}
    """
    melee_source = f"""
    mov eax, {ACTION_HELPER_VA:#x}
    call eax
    mov ecx, esi
    mov byte ptr [esi + 0x14030], 1
    jmp {MELEE_ACTION_CONTINUE_VA:#x}
    """

    slots = [
        ("native_luck_gate_marker", LUCK_GATE_WRAPPER_VA, LOGGER_VA, gate_source),
        ("binary_logger", LOGGER_VA, ACTION_HELPER_VA, logger_source),
        ("active_action_helper", ACTION_HELPER_VA, RESET_WRAPPER_VA, action_source),
        ("battle_reset", RESET_WRAPPER_VA, RANGED_WRAPPER_VA, reset_source),
        ("ranged_action_start", RANGED_WRAPPER_VA, MELEE_WRAPPER_VA, ranged_source),
        ("melee_action_start", MELEE_WRAPPER_VA, DATA_VA, melee_source),
    ]
    result = bytearray(LUCK_SECTION_SIZE)
    components = []
    for name, va, limit, source in slots:
        code = assemble(source, va)
        if va + len(code) > limit:
            raise RuntimeError(f"{name} exceeds isolated slot")
        start = va - LUCK_SECTION_VA
        result[start:start + len(code)] = code
        components.append({
            "name": name, "va": f"0x{va:08X}", "length": len(code),
            "limit_va": f"0x{limit:08X}", "assembly": source.strip(),
        })
    filename_offset = filename_va - LUCK_SECTION_VA
    record_offset = record_va - LUCK_SECTION_VA
    result[filename_offset:filename_offset + len(filename)] = filename
    struct.pack_into("<I", result, record_offset, RECORD_MAGIC)
    return bytes(result), {
        "record_va": f"0x{record_va:08X}",
        "record_size": RECORD_SIZE,
        "state": {
            "used_bitmap_low_va": f"0x{used_lo_va:08X}",
            "used_bitmap_high_va": f"0x{used_hi_va:08X}",
            "command_attacker_va": f"0x{command_attacker_va:08X}",
            "command_force_va": f"0x{command_force_va:08X}",
            "native_gate_mask_va": f"0x{gate_mask_va:08X}",
        },
        "components": components,
    }


def patch_executable(path: Path, section_payload: bytes, payload_meta: dict[str, Any]) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_EXE_SHA256[path.name]:
        raise RuntimeError(f"Unexpected formal V1.11 hash for {path.name}")
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != IMAGE_BASE or pe.OPTIONAL_HEADER.DllCharacteristics & 0x40:
        raise RuntimeError(f"Unexpected image base or ASLR state in {path.name}")
    section = pe.sections[-1]
    if (
        section.Name != LUCK_SECTION_NAME
        or section.VirtualAddress != LUCK_SECTION_RVA
        or section.PointerToRawData != LUCK_SECTION_RAW_OFFSET
        or section.SizeOfRawData != LUCK_SECTION_SIZE
        or section.Characteristics != LUCK_SECTION_CHARACTERISTICS
    ):
        raise RuntimeError(f"Unexpected formal .luck3 layout in {path.name}")
    source_section = original[LUCK_SECTION_RAW_OFFSET:LUCK_SECTION_RAW_OFFSET + LUCK_SECTION_SIZE]
    if sha256_bytes(source_section) != SOURCE_LUCK_SECTION_SHA256:
        raise RuntimeError(f"Unexpected formal .luck3 payload in {path.name}")
    luck_hook_offset = pe.get_offset_from_rva(LUCK_GATE_HOOK_VA - IMAGE_BASE)
    if original[luck_hook_offset:luck_hook_offset + len(LUCK_GATE_HOOK_BYTES)] != LUCK_GATE_HOOK_BYTES:
        raise RuntimeError(f"Formal fixed-Luck hook mismatch in {path.name}")

    hooks = [
        (BATTLE_RESET_HOOK_VA, BATTLE_RESET_ORIGINAL, RESET_WRAPPER_VA, "battle reset"),
        (RANGED_ACTION_HOOK_VA, RANGED_ACTION_ORIGINAL, RANGED_WRAPPER_VA, "ranged action"),
        (MELEE_ACTION_HOOK_VA, MELEE_ACTION_ORIGINAL, MELEE_WRAPPER_VA, "melee action"),
    ]
    patched = bytearray(original)
    reports = []
    for va, expected, target, name in hooks:
        offset = pe.get_offset_from_rva(va - IMAGE_BASE)
        if original[offset:offset + len(expected)] != expected:
            raise RuntimeError(f"{name} source mismatch at 0x{va:08X} in {path.name}")
        replacement = relative_jump(va, target, len(expected))
        patched[offset:offset + len(expected)] = replacement
        reports.append({
            "name": name, "va": f"0x{va:08X}", "file_offset": f"0x{offset:X}",
            "source_hex": expected.hex(" "), "patched_hex": replacement.hex(" "),
            "target_va": f"0x{target:08X}", "rollback_hex": expected.hex(" "),
        })
    patched[LUCK_SECTION_RAW_OFFSET:LUCK_SECTION_RAW_OFFSET + LUCK_SECTION_SIZE] = section_payload
    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    original_checksum = original[checksum_offset:checksum_offset + 4]
    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    for report in reports:
        offset = int(report["file_offset"], 16)
        va = int(report["va"], 16)
        instruction = next(decoder.disasm(final[offset:offset + 5], va))
        if (
            instruction.mnemonic != "jmp" or not instruction.operands
            or instruction.operands[0].type != X86_OP_IMM
            or int(instruction.operands[0].imm) != int(report["target_va"], 16)
        ):
            raise RuntimeError(f"Hook target mismatch at {report['va']} in {path.name}")

    restored = bytearray(final)
    for va, expected, _, _ in hooks:
        offset = pe.get_offset_from_rva(va - IMAGE_BASE)
        restored[offset:offset + len(expected)] = expected
    restored[LUCK_SECTION_RAW_OFFSET:LUCK_SECTION_RAW_OFFSET + LUCK_SECTION_SIZE] = source_section
    restored[checksum_offset:checksum_offset + 4] = original_checksum
    if bytes(restored) != original:
        raise RuntimeError(f"Full executable rollback failed for {path.name}")
    path.write_bytes(final)
    return {
        "name": path.name,
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "formal_luck_hook_preserved": True,
        "fixed_plus_three_wrapper_replaced_by_native_gate_marker": True,
        "hooks": reports,
        "payload": payload_meta,
        "contiguous_differences": contiguous_differences(original, final),
        "rollback_verified": True,
    }


def build_dll_payload(
    source_section: bytes,
    record_va: int,
    state: dict[str, str],
) -> tuple[bytes, dict[str, Any]]:
    if len(source_section) != diag03.CUREUI_SIZE:
        raise RuntimeError("Unexpected .cureui size")
    if any(source_section[diag03.PRESERVED_CUREUI_END:]):
        raise RuntimeError("Reserved .cureui region is not empty")
    current_attacker_va = int(state["command_attacker_va"], 16)
    command_force_va = int(state["command_force_va"], 16)
    gate_mask_va = int(state["native_gate_mask_va"], 16)

    def callback_source(path_id: int, native_tail: str) -> tuple[bytes, str]:
        wrapper_va = diag03.MELEE_WRAPPER_VA if path_id == 31 else diag03.SECOND_WRAPPER_VA
        source = f"""
        pushfd
        pushad
        cld
        xor eax, eax
        mov edi, {record_va + 4:#x}
        mov ecx, 23
        rep stosd
        mov ebx, dword ptr [esp + 0x2c]
        mov edx, dword ptr [esp + 0x30]
        mov dword ptr [{record_va + 4:#x}], {path_id}
        mov dword ptr [{record_va + 8:#x}], ebx
        mov dword ptr [{record_va + 12:#x}], edx
        mov eax, dword ptr [{current_attacker_va:#x}]
        mov dword ptr [{record_va + 16:#x}], eax
        mov eax, dword ptr [{command_force_va:#x}]
        mov dword ptr [{record_va + 20:#x}], eax
        mov eax, dword ptr [{gate_mask_va:#x}]
        mov dword ptr [{record_va + 24:#x}], eax
        mov ecx, dword ptr [{BATTLE_MANAGER_PTR:#x}]
        test ecx, ecx
        je callback_done
        test ebx, ebx
        je callback_done
        mov eax, dword ptr [ebx + 0x70]
        mov dword ptr [{record_va + 28:#x}], eax
        cmp dword ptr [{command_force_va:#x}], 1
        jne callback_record
        cmp dword ptr [{current_attacker_va:#x}], ebx
        jne callback_record
        mov dword ptr [ebx + 0x70], 1
callback_record:
        mov eax, dword ptr [ebx + 0x70]
        mov dword ptr [{record_va + 32:#x}], eax
        mov eax, dword ptr [ebx + 0xf4]
        mov dword ptr [{record_va + 36:#x}], eax
        mov eax, dword ptr [ebx + 0xf8]
        mov dword ptr [{record_va + 40:#x}], eax
        mov eax, {LOGGER_VA:#x}
        call eax
callback_done:
        popad
        popfd
        {native_tail}
        """
        return assemble(source, wrapper_va), source.strip()

    melee_code, melee_source = callback_source(
        31,
        f"sub esp, 0x0c\npush ebx\npush ebp\npush esi\njmp {diag03.HOTA_MELEE_CONTINUE_VA:#x}",
    )
    second_code, second_source = callback_source(32, f"jmp {diag03.SECOND_REPLAY_VA:#x}")
    replay_rva = diag03.SECOND_REPLAY_VA - diag03.HOTA_IMAGE_BASE
    replay_source = f"""
    call base_here
base_here:
    pop eax
    sub eax, {replay_rva + 5:#x}
    mov eax, dword ptr [eax + {diag03.HOTA_GLOBAL_RVA:#x}]
    push ebx
    jmp {diag03.HOTA_SECOND_CONTINUE_VA:#x}
    """
    replay_code = assemble(replay_source, diag03.SECOND_REPLAY_VA)
    slots = [
        ("first-attack callback 1", diag03.MELEE_WRAPPER_VA, diag03.SECOND_WRAPPER_VA,
         melee_code, melee_source),
        ("first-attack callback 2", diag03.SECOND_WRAPPER_VA, diag03.SECOND_REPLAY_VA,
         second_code, second_source),
        ("ASLR-safe callback-2 replay", diag03.SECOND_REPLAY_VA,
         diag03.CUREUI_VA + diag03.CUREUI_SIZE, replay_code, replay_source.strip()),
    ]
    result = bytearray(source_section)
    components = []
    for name, va, limit, code, source in slots:
        if va + len(code) > limit:
            raise RuntimeError(f"{name} exceeds .cureui slot")
        start = va - diag03.CUREUI_VA
        result[start:start + len(code)] = code
        components.append({
            "name": name, "preferred_va": f"0x{va:08X}", "length": len(code),
            "limit_preferred_va": f"0x{limit:08X}", "assembly": source,
        })
    return bytes(result), {
        "aslr_safe": True,
        "accepted_cure_ui_prefix_preserved": True,
        "record_va": f"0x{record_va:08X}",
        "components": components,
    }


def replace_exact_text(raw: bytes, old: str, new: str, expected_count: int) -> tuple[bytes, dict[str, Any]]:
    text = raw.decode("gb18030")
    count = text.count(old)
    if count != expected_count:
        raise RuntimeError(f"Expected {expected_count} specialty matches, found {count}")
    final = text.replace(old, new).encode("gb18030")
    return final, {
        "encoding": "gb18030", "replacement_count": count,
        "old": old, "new": new,
        "source_sha256": sha256_bytes(raw), "output_sha256": sha256_bytes(final),
    }


def patch_lod(path: Path, package_root: Path) -> dict[str, Any]:
    relative = path.relative_to(package_root).as_posix()
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_RESOURCE_SHA256[relative]:
        raise RuntimeError(f"Unexpected formal resource hash for {relative}")
    entries = parse_entries(original)
    matches = [entry for entry in entries if str(entry["name"]).lower() == "herospec.txt"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one HeroSpec.txt in {relative}")
    entry = matches[0]
    member_after, text_report = replace_exact_text(
        payload(original, entry), OLD_SPECIALTY_SENTENCE, NEW_SPECIALTY_SENTENCE, 2
    )
    compressed = zlib.compress(member_after, 9)
    stored = member_after if len(compressed) >= len(member_after) else compressed
    compressed_size = 0 if stored is member_after else len(compressed)
    output = bytearray(original)
    new_offset = len(output)
    output.extend(stored)
    directory_position = DIRECTORY_OFFSET + int(entry["index"]) * ENTRY_SIZE
    struct.pack_into(
        "<IIII", output, directory_position + 16, new_offset, len(member_after),
        int(entry["type"]), compressed_size,
    )
    final = bytes(output)
    if payload(final, parse_entries(final)[int(entry["index"])]) != member_after:
        raise RuntimeError(f"LOD repack verification failed for {relative}")
    path.write_bytes(final)
    return {
        "relative_path": relative, "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final), "member": text_report,
        "all_other_directory_entries_unchanged": True,
    }


def patch_loose(path: Path, package_root: Path) -> dict[str, Any]:
    relative = path.relative_to(package_root).as_posix()
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_RESOURCE_SHA256[relative]:
        raise RuntimeError("Unexpected formal loose HeroSpec hash")
    final, report = replace_exact_text(
        original, OLD_SPECIALTY_SENTENCE, NEW_SPECIALTY_SENTENCE, 2
    )
    path.write_bytes(final)
    report["relative_path"] = relative
    return report


def installation_text() -> str:
    return f"""{BUILD_NAME} 功能测试说明

本包从正式 {SOURCE_NAME} 制作，不是正式发布版。

马洛迪亚与黛瑞丝的新特长效果：
{NEW_SPECIALTY_SENTENCE}

具体规则：
1. 每支己方部队分别记录，每场战斗开始时全部重置；
2. 只有主动近战或主动射击会消耗首次资格，反击、等待、防御和施法不会消耗；
3. 双射、环击等同一攻击指令内的全部命中共享必定幸运；
4. 首次主动攻击结束后，该部队恢复原生幸运值与触发概率；
5. 厄运沙漏、诅咒之地等原生“禁止幸运生效”效果仍然有效。

安装：覆盖到纯净 HotA 1.8.0 中文版目录，使用 h3hota HD.exe 启动。

建议测试：
1. 让一支部队先反击，再主动攻击：反击不能消耗资格，首次主动攻击应触发幸运；
2. 同一部队下一次主动攻击应恢复正常概率；
3. 测试射击、双射与环击，确认一次指令的全部命中共享首次幸运；
4. 开启下一场战斗，确认每支部队重新获得首次资格；
5. 如方便，使用厄运沙漏确认原生硬封锁仍有效。

若遇到异常，请上传游戏根目录的 {LOG_FILENAME}；正常通过时只需说明测试结果。
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
        raise RuntimeError("Formal V1.11 ZIP hash mismatch")

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    exe_payload, exe_meta = build_exe_payload()
    record_va = int(exe_meta["record_va"], 16)
    exe_reports = [
        patch_executable(package_root / name, exe_payload, exe_meta) for name in EXE_NAMES
    ]

    old_builder = diag03.build_cureui_payload
    diag03.build_cureui_payload = lambda section, record: build_dll_payload(
        section, record, exe_meta["state"]
    )
    try:
        dll_report = diag03.patch_hota_dll(package_root / diag03.HOTA_DLL_NAME, record_va)
    finally:
        diag03.build_cureui_payload = old_builder

    resource_reports = [
        patch_lod(package_root / relative, package_root) for relative in LANGUAGE_ARCHIVES
    ]
    resource_reports.append(
        patch_loose(package_root / luck_v11.LOOSE_HEROSPEC_RELATIVE, package_root)
    )
    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("Expected exactly one root installation text file")
    instruction_files[0].write_text(installation_text(), encoding="utf-8")

    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    changed = {
        relative for relative, digest in package_hashes.items()
        if source_hashes.get(relative) != digest
    }
    allowed = (
        set(EXE_NAMES) | {diag03.HOTA_DLL_NAME} | set(LANGUAGE_ARCHIVES)
        | {luck_v11.LOOSE_HEROSPEC_RELATIVE, instruction_files[0].name}
    )
    if changed != allowed:
        raise RuntimeError(f"Unexpected package changes: {sorted(changed ^ allowed)}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC validation failed")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("ZIP member set mismatch")
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
        "runtime_log": LOG_FILENAME,
        "changed_package_files": sorted(changed),
        "source_file_hashes": source_hashes,
        "package_file_hashes": package_hashes,
        "executables": exe_reports,
        "hota_dll": dll_report,
        "resources": resource_reports,
        "behavior": {
            "hero_ids": [MELODIA_ID, DAREMYTH_ID],
            "per_stack_first_active_attack_guaranteed_lucky": True,
            "retaliation_does_not_consume_or_inherit": True,
            "same_command_repeated_hits_inherit": True,
            "later_attacks_use_native_luck": True,
            "native_hard_suppression_preserved_by_post_gate_marker": True,
        },
        "static_verification": {
            "diag03_attacker_argument_and_lucky_flag_proof_used": True,
            "diag04_action_6_7_boundary_proof_used": True,
            "battle_reset_hook_rollback_verified": True,
            "formal_fixed_plus_three_replaced_with_native_luck": True,
            "accepted_cure_ui_prefix_preserved": True,
            "standard_and_hd_built_separately": True,
            "all_core_files_rollback_verified": True,
            "only_expected_package_files_changed": True,
            "zip_crc_and_member_checks_passed": True,
        },
    }
    (output_root / f"{BUILD_NAME}_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / f"{BUILD_NAME}_README.txt").write_text(
        installation_text(), encoding="utf-8"
    )
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    print(f"HotA.dll SHA-256: {dll_report['output_sha256']}")
    print("Changed package files: " + json.dumps(sorted(changed), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
