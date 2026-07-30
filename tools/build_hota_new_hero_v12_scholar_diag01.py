#!/usr/bin/env python3
"""Build the Coronius Scholar-entry diagnostic from formal V1.14.

The executable hook is behavior-transparent: it records the two H3Hero pointers
at the native Scholar exchange entry (0x004A25B0), then replays the exact
overwritten prologue and lets the original function run unchanged.  The package
also installs the native Expert Scholar artwork for Coronius so the requested
visual can be checked independently from the pending gameplay hook.
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
from PIL import Image
from capstone.x86_const import X86_OP_IMM

from build_hota_new_hero_v1 import (
    EXE_NAMES,
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)
from build_hota_new_hero_v103 import IMAGE_BASE
from build_hota_new_hero_v104 import assemble, contiguous_differences


BUILD_NAME = "HOTA_NEW_HERO_V1.2_SCHOLAR_DIAG01"
SOURCE_NAME = "HOTA_NEW_HERO_V1.14"
SOURCE_ZIP_SHA256 = "8077624b88dc83762b77c34cb8645a4907cf2f3bc0538ae0684da713edd4ed85"
SOURCE_EXE_SHA256 = {
    "h3hota.exe": "eccb8163cdda269318d8da52d4889a4d4e0ed5388e88994ddbb578f5777cfee6",
    "h3hota HD.exe": "f0f1615ca0700cdf7a5f79917b4d43794c7c99731c279867c1a54857a0cbf42e",
}

CORONIUS_ID = 24
SCHOLAR_SKILL_ID = 18
WISDOM_SKILL_ID = 7
EXPERT_SCHOLAR_FRAME = SCHOLAR_SKILL_ID * 3 + 2
SECSKILL_DEF_SHA256 = "298f31e75e045fcb1195d870efbed8d7f5ecb81bab18e0ffc89ccc6a81c91aee"
SECSK32_DEF_SHA256 = "e56aeeaa81e36d08aaeb86b296ef9903b7f3100ecd81e11c6df8922937afd213"

SCHOLAR_ENTRY_VA = 0x004A25B0
SCHOLAR_CONTINUE_VA = 0x004A25BA
SCHOLAR_ENTRY_ORIGINAL = bytes.fromhex("55 8B EC 6A FF 68 78 B7 62 00")

DIAG_SECTION_NAME = b".schdg\0\0"
DIAG_SECTION_RVA = 0x002E8000
DIAG_SECTION_VA = IMAGE_BASE + DIAG_SECTION_RVA
DIAG_SECTION_SIZE = 0x1000
DIAG_SECTION_CHARACTERISTICS = 0xE0000020
EXPECTED_SOURCE_SECTION_COUNT = 5
EXPECTED_SOURCE_SIZE_OF_IMAGE = DIAG_SECTION_RVA

LOGGER_VA = DIAG_SECTION_VA + 0x000
ENTRY_WRAPPER_VA = DIAG_SECTION_VA + 0x180
DATA_VA = DIAG_SECTION_VA + 0x500
LOG_FILENAME = "hota_scholar_diag01.bin"
RECORD_MAGIC = 0x31484353  # SCH1
RECORD_DWORDS = 18
RECORD_SIZE = RECORD_DWORDS * 4

IAT = {
    "CloseHandle": 0x0063A0C8,
    "CreateFileA": 0x0063A108,
    "WriteFile": 0x0063A114,
}

D32F_RELATIVES = {
    "_HD3_Data/Compability/#hota15/UN32.DEF": {
        "source_sha256": "17799a6988f9f37f08fca54e43de22ea6374409a0a477fa778bbde575a65768b",
        "size": 32,
    },
    "_HD3_Data/Compability/#hota15/UN44.DEF": {
        "source_sha256": "bba48ccbe9ab2dd3a2a822edaa267d47778fe82a33fb79bbca81aa112a40dcb7",
        "size": 44,
    },
}
LOOSE_ICON_RELATIVE = "Data/HPS024DR.PCX"


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
    if written_va + 4 > DIAG_SECTION_VA + DIAG_SECTION_SIZE:
        raise RuntimeError("diagnostic data exceeds isolated section")

    logger_source = f"""
    push 0
    push 0x80
    push 4
    push 0
    push 3
    push 4
    push {filename_va:#x}
    call dword ptr [{IAT['CreateFileA']:#x}]
    cmp eax, -1
    je logger_done
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
logger_done:
    ret
    """

    wrapper_source = f"""
    pushfd
    pushad
    test ecx, ecx
    je entry_native
    test edx, edx
    je entry_native
    mov eax, dword ptr [ecx + 0x1a]
    cmp eax, {CORONIUS_ID}
    je entry_log
    mov eax, dword ptr [edx + 0x1a]
    cmp eax, {CORONIUS_ID}
    jne entry_native
entry_log:
    mov eax, dword ptr [esp + 0x24]
    mov dword ptr [{record_va + 8:#x}], eax
    mov dword ptr [{record_va + 12:#x}], ecx
    mov eax, dword ptr [ecx + 0x1a]
    mov dword ptr [{record_va + 16:#x}], eax
    movsx eax, byte ptr [ecx + 0xdb]
    mov dword ptr [{record_va + 20:#x}], eax
    movsx eax, byte ptr [ecx + 0xd0]
    mov dword ptr [{record_va + 24:#x}], eax
    xor eax, eax
    xor esi, esi
count_h1:
    cmp byte ptr [ecx + esi + 0x3ea], 0
    je count_h1_next
    inc eax
count_h1_next:
    inc esi
    cmp esi, 0x46
    jl count_h1
    mov dword ptr [{record_va + 28:#x}], eax
    mov dword ptr [{record_va + 32:#x}], edx
    mov eax, dword ptr [edx + 0x1a]
    mov dword ptr [{record_va + 36:#x}], eax
    movsx eax, byte ptr [edx + 0xdb]
    mov dword ptr [{record_va + 40:#x}], eax
    movsx eax, byte ptr [edx + 0xd0]
    mov dword ptr [{record_va + 44:#x}], eax
    xor eax, eax
    xor esi, esi
count_h2:
    cmp byte ptr [edx + esi + 0x3ea], 0
    je count_h2_next
    inc eax
count_h2_next:
    inc esi
    cmp esi, 0x46
    jl count_h2
    mov dword ptr [{record_va + 48:#x}], eax
    movsx eax, byte ptr [ecx + 0xdb]
    movsx ebx, byte ptr [edx + 0xdb]
    cmp eax, ebx
    jge native_raw_ready
    mov eax, ebx
native_raw_ready:
    mov dword ptr [{record_va + 52:#x}], eax
    xor edi, edi
    mov ebx, dword ptr [ecx + 0x1a]
    cmp ebx, {CORONIUS_ID}
    jne specialist_h1_done
    or edi, 1
specialist_h1_done:
    mov ebx, dword ptr [edx + 0x1a]
    cmp ebx, {CORONIUS_ID}
    jne specialist_h2_done
    or edi, 2
specialist_h2_done:
    mov dword ptr [{record_va + 68:#x}], edi
    movsx eax, byte ptr [ecx + 0xdb]
    test eax, eax
    jle cap_h1_zero
    inc eax
    test edi, 1
    je cap_h1_ready
    inc eax
    jmp cap_h1_ready
cap_h1_zero:
    xor eax, eax
cap_h1_ready:
    movsx ebx, byte ptr [edx + 0xdb]
    test ebx, ebx
    jle cap_h2_zero
    inc ebx
    test edi, 2
    je cap_h2_ready
    inc ebx
    jmp cap_h2_ready
cap_h2_zero:
    xor ebx, ebx
cap_h2_ready:
    cmp eax, ebx
    jge meeting_cap_ready
    mov eax, ebx
meeting_cap_ready:
    cmp eax, 5
    jle meeting_cap_clamped
    mov eax, 5
meeting_cap_clamped:
    mov dword ptr [{record_va + 56:#x}], eax
    movsx ebx, byte ptr [ecx + 0xd0]
    add ebx, 3
    cmp ebx, 5
    jle h1_wisdom_clamped
    mov ebx, 5
h1_wisdom_clamped:
    cmp ebx, eax
    jle h1_effective_ready
    mov ebx, eax
h1_effective_ready:
    mov dword ptr [{record_va + 60:#x}], ebx
    movsx ebx, byte ptr [edx + 0xd0]
    add ebx, 3
    cmp ebx, 5
    jle h2_wisdom_clamped
    mov ebx, 5
h2_wisdom_clamped:
    cmp ebx, eax
    jle h2_effective_ready
    mov ebx, eax
h2_effective_ready:
    mov dword ptr [{record_va + 64:#x}], ebx
    mov eax, {LOGGER_VA:#x}
    call eax
entry_native:
    popad
    popfd
    push ebp
    mov ebp, esp
    push -1
    push 0x62b778
    push {SCHOLAR_CONTINUE_VA:#x}
    ret
    """

    payload = bytearray(DIAG_SECTION_SIZE)
    components: list[dict[str, Any]] = []
    for name, va, limit, source in (
        ("logger", LOGGER_VA, ENTRY_WRAPPER_VA, logger_source),
        ("entry_wrapper", ENTRY_WRAPPER_VA, DATA_VA, wrapper_source),
    ):
        code = assemble(source, va)
        if va + len(code) > limit:
            raise RuntimeError(f"{name} exceeds isolated slot")
        start = va - DIAG_SECTION_VA
        payload[start:start + len(code)] = code
        components.append({
            "name": name,
            "va": f"0x{va:08X}",
            "length": len(code),
            "limit_va": f"0x{limit:08X}",
            "assembly": source.strip(),
        })

    payload[filename_va - DIAG_SECTION_VA:filename_va - DIAG_SECTION_VA + len(filename)] = filename
    struct.pack_into("<II", payload, record_va - DIAG_SECTION_VA, RECORD_MAGIC, 1)
    return bytes(payload), {
        "section_va": f"0x{DIAG_SECTION_VA:08X}",
        "section_size": DIAG_SECTION_SIZE,
        "filename_va": f"0x{filename_va:08X}",
        "record_va": f"0x{record_va:08X}",
        "record_size": RECORD_SIZE,
        "record_layout": [
            "magic SCH1", "schema version", "native caller return address",
            "hero1 pointer", "hero1 id", "hero1 Scholar mastery", "hero1 Wisdom mastery",
            "hero1 learned-spell count", "hero2 pointer", "hero2 id",
            "hero2 Scholar mastery", "hero2 Wisdom mastery", "hero2 learned-spell count",
            "native maximum raw Scholar mastery", "planned specialist meeting spell cap",
            "planned hero1 effective receive cap", "planned hero2 effective receive cap",
            "specialist flags (bit0=hero1, bit1=hero2)",
        ],
        "components": components,
    }


def patch_executable(path: Path, payload: bytes, payload_meta: dict[str, Any]) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_EXE_SHA256[path.name]:
        raise RuntimeError(f"unexpected {SOURCE_NAME} source hash for {path.name}")
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != IMAGE_BASE or pe.OPTIONAL_HEADER.DllCharacteristics & 0x40:
        raise RuntimeError(f"unexpected image base or ASLR in {path.name}")
    if pe.FILE_HEADER.NumberOfSections != EXPECTED_SOURCE_SECTION_COUNT:
        raise RuntimeError(f"unexpected source section count in {path.name}")
    if pe.OPTIONAL_HEADER.SizeOfImage != EXPECTED_SOURCE_SIZE_OF_IMAGE:
        raise RuntimeError(f"unexpected source SizeOfImage in {path.name}")
    if len(payload) != DIAG_SECTION_SIZE:
        raise RuntimeError("isolated payload size mismatch")

    imports = import_addresses(pe)
    for name, expected in IAT.items():
        if imports.get(name) != expected:
            raise RuntimeError(f"unexpected {name} IAT in {path.name}: {imports.get(name)!r}")

    hook_offset = pe.get_offset_from_rva(SCHOLAR_ENTRY_VA - IMAGE_BASE)
    if original[hook_offset:hook_offset + len(SCHOLAR_ENTRY_ORIGINAL)] != SCHOLAR_ENTRY_ORIGINAL:
        raise RuntimeError(f"Scholar entry bytes changed in {path.name}")

    pe_offset = pe.DOS_HEADER.e_lfanew
    section_table_end = pe_offset + 24 + pe.FILE_HEADER.SizeOfOptionalHeader + pe.FILE_HEADER.NumberOfSections * 40
    first_raw = min(section.PointerToRawData for section in pe.sections if section.PointerToRawData)
    if first_raw - section_table_end < 40:
        raise RuntimeError(f"no room for sixth section header in {path.name}")
    raw_pointer = align(len(original), pe.OPTIONAL_HEADER.FileAlignment)
    if raw_pointer != len(original):
        raise RuntimeError(f"unexpected overlay or file alignment in {path.name}")
    last = max(pe.sections, key=lambda section: section.VirtualAddress)
    last_end = align(
        last.VirtualAddress + max(last.Misc_VirtualSize, last.SizeOfRawData),
        pe.OPTIONAL_HEADER.SectionAlignment,
    )
    if last_end != DIAG_SECTION_RVA:
        raise RuntimeError(f"sixth section is not at exact image boundary in {path.name}")

    section_count_offset = pe_offset + 6
    size_of_code_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfCode")
    size_of_image_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfImage")
    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    original_header = {
        "section_header_slot": original[section_table_end:section_table_end + 40],
        "section_count": original[section_count_offset:section_count_offset + 2],
        "size_of_code": original[size_of_code_offset:size_of_code_offset + 4],
        "size_of_image": original[size_of_image_offset:size_of_image_offset + 4],
        "checksum": original[checksum_offset:checksum_offset + 4],
    }

    patched = bytearray(original)
    patched.extend(payload)
    patched[section_table_end:section_table_end + 40] = struct.pack(
        "<8sIIIIIIHHI",
        DIAG_SECTION_NAME,
        DIAG_SECTION_SIZE,
        DIAG_SECTION_RVA,
        DIAG_SECTION_SIZE,
        raw_pointer,
        0, 0, 0, 0,
        DIAG_SECTION_CHARACTERISTICS,
    )
    struct.pack_into("<H", patched, section_count_offset, EXPECTED_SOURCE_SECTION_COUNT + 1)
    struct.pack_into("<I", patched, size_of_code_offset, pe.OPTIONAL_HEADER.SizeOfCode + DIAG_SECTION_SIZE)
    struct.pack_into("<I", patched, size_of_image_offset, DIAG_SECTION_RVA + DIAG_SECTION_SIZE)
    hook = relative_jump(SCHOLAR_ENTRY_VA, ENTRY_WRAPPER_VA, len(SCHOLAR_ENTRY_ORIGINAL))
    patched[hook_offset:hook_offset + len(hook)] = hook
    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)

    parsed = pefile.PE(data=final, fast_load=False)
    if parsed.FILE_HEADER.NumberOfSections != EXPECTED_SOURCE_SECTION_COUNT + 1:
        raise RuntimeError(f"diagnostic section registration failed in {path.name}")
    section = parsed.sections[-1]
    if (
        section.Name != DIAG_SECTION_NAME
        or section.VirtualAddress != DIAG_SECTION_RVA
        or section.PointerToRawData != raw_pointer
        or section.SizeOfRawData != DIAG_SECTION_SIZE
        or section.Characteristics != DIAG_SECTION_CHARACTERISTICS
    ):
        raise RuntimeError(f"diagnostic section metadata mismatch in {path.name}")
    if final[raw_pointer:raw_pointer + DIAG_SECTION_SIZE] != payload:
        raise RuntimeError(f"diagnostic payload mismatch in {path.name}")
    if parsed.verify_checksum() is not True:
        raise RuntimeError(f"PE checksum invalid in {path.name}")

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    instruction = next(decoder.disasm(final[hook_offset:hook_offset + 5], SCHOLAR_ENTRY_VA))
    if (
        instruction.mnemonic != "jmp"
        or not instruction.operands
        or instruction.operands[0].type != X86_OP_IMM
        or int(instruction.operands[0].imm) != ENTRY_WRAPPER_VA
    ):
        raise RuntimeError(f"Scholar hook target mismatch in {path.name}")

    restored = bytearray(final[:len(original)])
    restored[hook_offset:hook_offset + len(SCHOLAR_ENTRY_ORIGINAL)] = SCHOLAR_ENTRY_ORIGINAL
    restored[section_table_end:section_table_end + 40] = original_header["section_header_slot"]
    restored[section_count_offset:section_count_offset + 2] = original_header["section_count"]
    restored[size_of_code_offset:size_of_code_offset + 4] = original_header["size_of_code"]
    restored[size_of_image_offset:size_of_image_offset + 4] = original_header["size_of_image"]
    restored[checksum_offset:checksum_offset + 4] = original_header["checksum"]
    if bytes(restored) != original:
        raise RuntimeError(f"full executable rollback failed in {path.name}")

    path.write_bytes(final)
    return {
        "name": path.name,
        "source_size": len(original),
        "output_size": len(final),
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "hook": {
            "role": "native Scholar exchange entry",
            "va": f"0x{SCHOLAR_ENTRY_VA:08X}",
            "file_offset": f"0x{hook_offset:X}",
            "source_hex": SCHOLAR_ENTRY_ORIGINAL.hex(" "),
            "patched_hex": hook.hex(" "),
            "rollback_hex": SCHOLAR_ENTRY_ORIGINAL.hex(" "),
            "target_va": f"0x{ENTRY_WRAPPER_VA:08X}",
        },
        "new_section": {
            "name": DIAG_SECTION_NAME.rstrip(b"\0").decode("ascii"),
            "rva": f"0x{DIAG_SECTION_RVA:08X}",
            "raw_pointer": f"0x{raw_pointer:X}",
            "raw_size": DIAG_SECTION_SIZE,
            "payload_sha256": sha256_bytes(payload),
        },
        "payload": payload_meta,
        "common_length_differences": contiguous_differences(original, final[:len(original)]),
        "appended_bytes": len(final) - len(original),
        "pe_checksum_valid": True,
        "rollback_reconstructs_source": True,
    }


def decode_expert_scholar(
    source: Path,
    *,
    expected_hash: str,
    expected_size: int,
    expected_name: str,
) -> tuple[Image.Image, bytes, bytes, dict[str, Any]]:
    data = source.read_bytes()
    if sha256_bytes(data) != expected_hash:
        raise RuntimeError(f"unexpected clean secondary-skill DEF hash: {source}")
    if len(data) < 784:
        raise RuntimeError("Secskill.def is truncated")
    palette = data[16:784]
    _, full_width, full_height, group_count = struct.unpack_from("<4I", data, 0)
    if (full_width, full_height, group_count) != (expected_size, expected_size, 1):
        raise RuntimeError(f"unexpected secondary-skill DEF header: {source}")
    group_position = 784
    _, frame_count, _, _ = struct.unpack_from("<4I", data, group_position)
    names_position = group_position + 16
    names = [
        data[names_position + index * 13:names_position + (index + 1) * 13]
        .split(b"\0", 1)[0].decode("ascii")
        for index in range(frame_count)
    ]
    offsets_position = names_position + frame_count * 13
    offsets = struct.unpack_from(f"<{frame_count}I", data, offsets_position)
    if EXPERT_SCHOLAR_FRAME >= frame_count or names[EXPERT_SCHOLAR_FRAME].lower() != expected_name.lower():
        raise RuntimeError("Expert Scholar frame identity mismatch")
    offset = offsets[EXPERT_SCHOLAR_FRAME]
    _, compression, frame_full_width, frame_full_height, width, height, left, top = struct.unpack_from(
        "<8I", data, offset
    )
    if (frame_full_width, frame_full_height) != (expected_size, expected_size) or compression not in (0, 1):
        raise RuntimeError("unexpected Expert Scholar frame format")
    pixel_start = offset + 32
    pixels = bytearray([0] * (frame_full_width * frame_full_height))
    if compression == 0:
        rows = [
            data[pixel_start + row * width:pixel_start + (row + 1) * width]
            for row in range(height)
        ]
    else:
        row_offsets = struct.unpack_from(f"<{height}I", data, pixel_start)
        rows = []
        for row_offset in row_offsets:
            position = pixel_start + row_offset
            row = bytearray()
            while len(row) < width:
                code = data[position]
                run = data[position + 1] + 1
                position += 2
                if code == 0xFF:
                    row.extend(data[position:position + run])
                    position += run
                else:
                    row.extend([code] * run)
            if len(row) != width:
                raise RuntimeError("Expert Scholar row exceeds declared width")
            rows.append(bytes(row))
    for row_index, row in enumerate(rows):
        target = (top + row_index) * frame_full_width + left
        pixels[target:target + width] = row
    indexed = Image.frombytes("P", (expected_size, expected_size), bytes(pixels))
    indexed.putpalette(palette)
    rgba = indexed.convert("RGBA")
    rgba.putalpha(Image.frombytes(
        "L",
        (expected_size, expected_size),
        bytes(0 if value == 0 else 255 for value in pixels),
    ))
    return rgba, bytes(pixels), palette, {
        "source_sha256": sha256_bytes(data),
        "frame_index": EXPERT_SCHOLAR_FRAME,
        "frame_name": names[EXPERT_SCHOLAR_FRAME],
        "compression": compression,
        "size": [expected_size, expected_size],
    }


def patch_d32f(path: Path, image: Image.Image, expected: dict[str, Any]) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != expected["source_sha256"]:
        raise RuntimeError(f"unexpected D32F source hash: {path}")
    if original[:4] != b"D32F" or struct.unpack_from("<I", original, 0x28)[0] != 215:
        raise RuntimeError(f"unexpected D32F identity: {path}")
    frame_count = 215
    offsets_position = 0x30 + frame_count * 13
    offsets = struct.unpack_from(f"<{frame_count}I", original, offsets_position)
    frame_offset = offsets[CORONIUS_ID]
    header = struct.unpack_from("<8I", original, frame_offset)
    data_size = header[1]
    target_size = int(expected["size"])
    if header[0] != 0x20 or header[2:6] != (target_size, target_size, target_size, target_size):
        raise RuntimeError(f"unexpected Coronius D32F frame geometry: {path}")
    if data_size != target_size * target_size * 4:
        raise RuntimeError(f"unexpected Coronius D32F pixel size: {path}")
    resized = image if target_size == 44 else image.resize((target_size, target_size), Image.Resampling.LANCZOS)
    stored = resized.rotate(180).tobytes("raw", "BGRA")
    start = frame_offset + 32
    end = start + data_size
    patched = bytearray(original)
    patched[start:end] = stored
    final = bytes(patched)
    if len(final) != len(original) or final[:start] != original[:start] or final[end:] != original[end:]:
        raise RuntimeError(f"D32F frame isolation failed: {path}")
    rollback = bytearray(final)
    rollback[start:end] = original[start:end]
    if bytes(rollback) != original:
        raise RuntimeError(f"D32F rollback failed: {path}")
    path.write_bytes(final)
    return {
        "path": path.as_posix(),
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "frame_index": CORONIUS_ID,
        "frame_offset": f"0x{frame_offset:X}",
        "pixel_offset": f"0x{start:X}",
        "pixel_length": data_size,
        "orientation": "stored 180 degrees for D32F runtime orientation",
        "source_hex_sha256": sha256_bytes(original[start:end]),
        "patched_hex_sha256": sha256_bytes(final[start:end]),
        "rollback_hex_sha256": sha256_bytes(original[start:end]),
        "all_other_bytes_preserved": True,
        "rollback_verified": True,
    }


def install_icons(package_root: Path, secskill_def: Path, secskill32_def: Path) -> dict[str, Any]:
    image44, _, _, source_meta44 = decode_expert_scholar(
        secskill_def,
        expected_hash=SECSKILL_DEF_SHA256,
        expected_size=44,
        expected_name="skill18c.pcx",
    )
    image32, indexed32, palette32, source_meta32 = decode_expert_scholar(
        secskill32_def,
        expected_hash=SECSK32_DEF_SHA256,
        expected_size=32,
        expected_name="skl3218c.pcx",
    )
    d32f_reports = []
    for relative, expected in D32F_RELATIVES.items():
        source_image = image44 if int(expected["size"]) == 44 else image32
        d32f_reports.append(patch_d32f(package_root / Path(relative), source_image, expected))
    # HPS specialty PCX slots are 48x32 and are not alpha sprites.  Use the
    # native SECSK32 dark-brown palette entry for the eight-pixel side gutters
    # instead of transparent/cyan palette index 0.
    hps_background_index = 217
    if tuple(palette32[hps_background_index * 3:hps_background_index * 3 + 3]) != (41, 24, 16):
        raise RuntimeError("unexpected SECSK32 dark-brown palette entry")
    hps_pixels = bytearray([hps_background_index] * (48 * 32))
    for row in range(32):
        hps_pixels[row * 48 + 8:row * 48 + 40] = indexed32[row * 32:(row + 1) * 32]
    pcx = struct.pack("<III", 48 * 32, 48, 32) + bytes(hps_pixels) + palette32
    if len(pcx) != 2316:
        raise RuntimeError("Heroes III PCX length mismatch")
    loose = package_root / Path(LOOSE_ICON_RELATIVE)
    loose.parent.mkdir(parents=True, exist_ok=True)
    loose.write_bytes(pcx)
    return {
        "native_sources": [source_meta44, source_meta32],
        "loose_icon": {
            "relative": LOOSE_ICON_RELATIVE,
            "sha256": sha256_bytes(pcx),
            "size": len(pcx),
            "format": "Heroes III indexed PCX resource",
            "background_palette_index": hps_background_index,
        },
        "d32f": d32f_reports,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与诊断说明

这是从正式 {SOURCE_NAME} 构建的科洛尼斯学术特第一阶段诊断包。

本包已经把科洛尼斯（壁垒、原屠戮特）的特长图标替换为游戏内“高级学术 / Expert Scholar”的原生图标；没有使用英文 Advanced Scholar（中级学术）图标。

本阶段尚未启用“学术传授上限 +1、双方智慧术学习上限 +1”的实际效果。两个 EXE 只在科洛尼斯参与友方英雄会面时记录原生学术交换入口，然后完整执行 V1.14 原有逻辑；其他正式机制保持不变。

安装：
1. 准备一份纯净 HotA 1.8.0 中文版 + HD Mod，或已安装正式 {SOURCE_NAME} 的目录。
2. 将压缩包内全部文件解压到游戏根目录并覆盖同名文件。
3. 使用平时的 h3hota HD.exe 启动。

最小测试：
1. 删除游戏根目录旧的 {LOG_FILENAME}（如存在）。
2. 使用科洛尼斯与一名己方英雄在冒险地图上会面并打开英雄交换界面；双方最好都有魔法书。
3. 关闭交换界面并退出游戏。
4. 把游戏根目录生成的 {LOG_FILENAME} 上传给 Codex。
5. 顺便确认科洛尼斯的特长图标显示为高级学术图标；诊断版特长文字与实际传授效果仍保持原版，属于预期现象。

诊断文件只包含英雄 ID、学术/智慧术等级、已学法术数量、计划采用的等级上限和本地运行地址，不包含个人信息。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--secskill-def", type=Path, required=True)
    parser.add_argument("--secskill32-def", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_zip = args.source_zip.resolve()
    secskill_def = args.secskill_def.resolve()
    secskill32_def = args.secskill32_def.resolve()
    build_root = args.build_root.resolve()
    output_root = args.output_root.resolve()
    if sha256_file(source_zip) != SOURCE_ZIP_SHA256:
        raise RuntimeError(f"formal {SOURCE_NAME} ZIP hash mismatch")

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }

    payload, payload_meta = build_payload()
    executable_reports = [patch_executable(package_root / name, payload, payload_meta) for name in EXE_NAMES]
    icon_report = install_icons(package_root, secskill_def, secskill32_def)

    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("expected exactly one root installation text file")
    instruction_files[0].write_text(installation_text(), encoding="utf-8")
    instruction_relative = instruction_files[0].relative_to(package_root).as_posix()

    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    if not set(source_hashes).issubset(package_hashes):
        raise RuntimeError("diagnostic package removed formal V1.14 members")
    changed = {
        relative for relative in source_hashes
        if source_hashes[relative] != package_hashes[relative]
    }
    added = set(package_hashes) - set(source_hashes)
    expected_changed = set(EXE_NAMES) | set(D32F_RELATIVES) | {instruction_relative}
    if changed != expected_changed or added != {LOOSE_ICON_RELATIVE}:
        raise RuntimeError(
            f"unexpected package delta: changed={sorted(changed)} added={sorted(added)}"
        )

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"diagnostic ZIP CRC failure: {failed}")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("diagnostic ZIP member set mismatch")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "diagnostic_only": True,
        "gameplay_logic_changed": False,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "log_filename": LOG_FILENAME,
        "changed_package_files": sorted(changed),
        "added_package_files": sorted(added),
        "source_file_hashes": source_hashes,
        "package_file_hashes": package_hashes,
        "executables": executable_reports,
        "icons": icon_report,
        "planned_behavior_after_runtime_confirmation": {
            "hero_id": CORONIUS_ID,
            "replaced_specialty": "Slayer",
            "scholar_caps": {"Basic": 3, "Advanced": 4, "Expert": 5},
            "wisdom_receive_cap_bonus_for_both_heroes": 1,
            "absolute_spell_level_cap": 5,
        },
        "static_verification": {
            "formal_v114_source_hashes_verified": True,
            "native_scholar_entry_identical_in_standard_and_hd": True,
            "native_fields_observed": {
                "Scholar": "+0xDB",
                "Wisdom": "+0xD0",
                "learned_spells": "+0x3EA (70 bytes)",
            },
            "diagnostic_wrapper_replays_exact_prologue": True,
            "isolated_sixth_section_at_image_boundary": True,
            "both_executables_receive_identical_payload": True,
            "expert_scholar_frame_name_verified": "skill18c.pcx",
            "advanced_scholar_frame_not_used": True,
            "d32f_other_frames_byte_preserved": True,
            "full_executable_and_icon_frame_rollbacks_verified": True,
            "zip_crc_and_member_checks_passed": True,
        },
        "runtime_acceptance": {
            "status": "pending returned Coronius hero-meeting log",
            "expected": "one or more SCH1 records after Coronius meets a friendly hero",
        },
    }
    (output_root / f"{BUILD_NAME}_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / f"{BUILD_NAME}_README.md").write_text(installation_text(), encoding="utf-8")
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    for item in executable_reports:
        print(f"{item['name']}: {item['output_sha256']}")
    print(f"Runtime log: {LOG_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
