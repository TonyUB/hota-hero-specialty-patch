#!/usr/bin/env python3
"""Build a behavior-transparent first-active-attack diagnostic from V1.11.

The diagnostic keeps the accepted V1.11 gameplay intact.  It records the two
native lucky-strike roll paths for Melodia (29) and Daremyth (43), so a runtime
test can distinguish active melee, active ranged, retaliation and repeated
checks inside one attack command before the guaranteed-first-attack feature is
implemented.
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
from build_hota_new_hero_v104 import assemble, contiguous_differences


BUILD_NAME = "HOTA_NEW_HERO_V1.2_FIRSTATTACK_DIAG01"
SOURCE_NAME = "HOTA_NEW_HERO_V1.11"
SOURCE_ZIP_SHA256 = "6d262426f4f5cd77ac9dd110dba8d97134d4602993eb284aa2ed2f4a4354bbde"
SOURCE_EXE_SHA256 = {
    "h3hota.exe": "2975214a0826067fbf59c03e896142ff14b48a882f8e8d678faa0aa5dff924e8",
    "h3hota HD.exe": "45965c8126c88d92232fcd09593e6c43decc6f50de9d979fb90343426efc1b1f",
}

MELODIA_ID = 29
DAREMYTH_ID = 43
BATTLE_MANAGER_PTR = 0x00699420

MELEE_ROLL_HOOK_VA = 0x0043F648
MELEE_ROLL_CONTINUE_VA = 0x0043F64E
MELEE_ROLL_ORIGINAL = bytes.fromhex("8B 86 EC 04 00 00")
SECOND_ROLL_HOOK_VA = 0x0044152A
SECOND_ROLL_CONTINUE_VA = 0x00441530
SECOND_ROLL_ORIGINAL = bytes.fromhex("8B 86 EC 04 00 00")

LUCK_SECTION_NAME = b".luck3\0\0"
LUCK_SECTION_RVA = 0x002E7000
LUCK_SECTION_VA = IMAGE_BASE + LUCK_SECTION_RVA
LUCK_SECTION_SIZE = 0x1000
LUCK_SECTION_RAW_OFFSET = 0x002CC000
LUCK_SECTION_CHARACTERISTICS = 0xE0000020
SOURCE_LUCK_SECTION_SHA256 = "6c01569ef7b605f30a1c7c1c3060e620f4a3e22276094ce66e4ae3c0a87dbbfd"
PRESERVED_FORMAL_REGION_END = 0x200

LOGGER_VA = LUCK_SECTION_VA + 0x200
MELEE_WRAPPER_VA = LUCK_SECTION_VA + 0x380
SECOND_WRAPPER_VA = LUCK_SECTION_VA + 0x600
DATA_VA = LUCK_SECTION_VA + 0x900
DATA_LIMIT_VA = LUCK_SECTION_VA + 0x1000

LOG_FILENAME = "hota_luck_firstdiag01.bin"
RECORD_MAGIC = 0x314B5441  # little-endian ASCII: ATK1
RECORD_DWORDS = 24
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


def build_diagnostic_region(*, filter_specialists: bool = True) -> tuple[bytes, dict[str, Any]]:
    filename = LOG_FILENAME.encode("ascii") + b"\0"
    filename_va = DATA_VA
    record_va = (filename_va + len(filename) + 3) & ~3
    handle_va = record_va + RECORD_SIZE
    written_va = handle_va + 4
    if written_va + 4 > DATA_LIMIT_VA:
        raise RuntimeError("Diagnostic data exceeds reserved .luck3 space")

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
    ret
    """

    def wrapper_source(path_id: int, continue_va: int, include_arg2: bool) -> str:
        arg2 = "mov edx, dword ptr [ebp + 0x0c]" if include_arg2 else "xor edx, edx"
        if filter_specialists:
            hero_filter = f"""
            mov edx, dword ptr [edx + 0x1a]
            mov dword ptr [{record_va + 28:#x}], edx
            cmp edx, {MELODIA_ID}
            je specialist
            cmp edx, {DAREMYTH_ID}
            jne skip_log
            """
        else:
            hero_filter = f"""
            mov dword ptr [{record_va + 28:#x}], 0xffffffff
            """
        return f"""
        pushfd
        pushad
        mov dword ptr [{record_va + 4:#x}], {path_id}
        mov edx, dword ptr [ebp + 0x04]
        mov dword ptr [{record_va + 8:#x}], edx
        mov dword ptr [{record_va + 12:#x}], esi
        mov edx, dword ptr [ebp + 0x08]
        mov dword ptr [{record_va + 16:#x}], edx
        {arg2}
        mov dword ptr [{record_va + 20:#x}], edx
        mov edx, eax
        mov dword ptr [{record_va + 32:#x}], edx
        mov ecx, dword ptr [{BATTLE_MANAGER_PTR:#x}]
        test ecx, ecx
        je skip_log
        mov dword ptr [{record_va + 64:#x}], ecx
        mov edx, dword ptr [ecx + eax*4 + 0x53cc]
        test edx, edx
        je skip_log
        mov dword ptr [{record_va + 24:#x}], edx
        {hero_filter}
specialist:
        mov edx, dword ptr [esi + 0xf4]
        mov dword ptr [{record_va + 36:#x}], edx
        mov edx, dword ptr [esi + 0xf8]
        mov dword ptr [{record_va + 40:#x}], edx
        mov edx, dword ptr [esi + 0x34]
        mov dword ptr [{record_va + 44:#x}], edx
        mov edx, dword ptr [esi + 0x4ec]
        mov dword ptr [{record_va + 48:#x}], edx
        mov edx, dword ptr [esi + 0x70]
        mov dword ptr [{record_va + 52:#x}], edx
        mov edx, dword ptr [esi + 0x84]
        mov dword ptr [{record_va + 56:#x}], edx
        mov edx, dword ptr [esi + 0x288]
        mov dword ptr [{record_va + 60:#x}], edx
        mov dword ptr [{record_va + 68:#x}], ebx
        mov dword ptr [{record_va + 72:#x}], ecx
        mov dword ptr [{record_va + 76:#x}], edi
        mov dword ptr [{record_va + 80:#x}], ebp
        mov edx, dword ptr [ecx + 0x132b8]
        mov dword ptr [{record_va + 84:#x}], edx
        mov edx, dword ptr [ecx + 0x132bc]
        mov dword ptr [{record_va + 88:#x}], edx
        mov edx, dword ptr [ecx + 0x132c0]
        mov dword ptr [{record_va + 92:#x}], edx
        mov eax, {LOGGER_VA:#x}
        call eax
skip_log:
        popad
        popfd
        mov eax, dword ptr [esi + 0x4ec]
        push {continue_va:#x}
        ret
        """

    slots = [
        ("logger", LOGGER_VA, MELEE_WRAPPER_VA, logger_source),
        ("melee_roll_wrapper", MELEE_WRAPPER_VA, SECOND_WRAPPER_VA,
         wrapper_source(1, MELEE_ROLL_CONTINUE_VA, False)),
        ("second_roll_wrapper", SECOND_WRAPPER_VA, DATA_VA,
         wrapper_source(2, SECOND_ROLL_CONTINUE_VA, True)),
    ]
    region = bytearray(LUCK_SECTION_SIZE - PRESERVED_FORMAL_REGION_END)
    components: list[dict[str, Any]] = []
    for name, va, limit, source in slots:
        code = assemble(source, va)
        if va + len(code) > limit:
            raise RuntimeError(f"{name} exceeds reserved slot")
        start = va - (LUCK_SECTION_VA + PRESERVED_FORMAL_REGION_END)
        region[start:start + len(code)] = code
        components.append({
            "name": name,
            "va": f"0x{va:08X}",
            "length": len(code),
            "limit_va": f"0x{limit:08X}",
            "assembly": source.strip(),
        })
    data_base = LUCK_SECTION_VA + PRESERVED_FORMAL_REGION_END
    filename_offset = filename_va - data_base
    record_offset = record_va - data_base
    region[filename_offset:filename_offset + len(filename)] = filename
    struct.pack_into("<I", region, record_offset, RECORD_MAGIC)
    return bytes(region), {
        "preserved_formal_region": [
            f"0x{LUCK_SECTION_VA:08X}",
            f"0x{LUCK_SECTION_VA + PRESERVED_FORMAL_REGION_END:08X}",
        ],
        "filename_va": f"0x{filename_va:08X}",
        "record_va": f"0x{record_va:08X}",
        "record_size": RECORD_SIZE,
        "record_layout": [
            "magic ATK1", "path (1=0x43F620 family, 2=0x441330 family)",
            "native caller return address", "attacker stack pointer", "arg1", "arg2",
            "acting hero pointer", "acting hero id", "effective side", "raw side",
            "stack slot", "creature id", "current luck", "native lucky flag before roll",
            "attacker field +0x84", "attacker field +0x288", "battle manager pointer",
            "original EBX", "original ECX", "original EDI", "original EBP",
            "battle +0x132B8", "battle +0x132BC", "battle +0x132C0",
        ],
        "components": components,
    }


def patch_executable(
    path: Path,
    region: bytes,
    region_meta: dict[str, Any],
    *,
    formal_prefix: bytes | None = None,
) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_EXE_SHA256[path.name]:
        raise RuntimeError(f"Unexpected {SOURCE_NAME} hash for {path.name}")
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != IMAGE_BASE or pe.OPTIONAL_HEADER.DllCharacteristics & 0x40:
        raise RuntimeError(f"Unexpected image base or ASLR state in {path.name}")
    if pe.FILE_HEADER.NumberOfSections != 5:
        raise RuntimeError(f"Unexpected section count in {path.name}")
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
    if any(source_section[PRESERVED_FORMAL_REGION_END:]):
        raise RuntimeError(f"Reserved .luck3 space is not empty in {path.name}")
    if len(region) != LUCK_SECTION_SIZE - PRESERVED_FORMAL_REGION_END:
        raise RuntimeError("Diagnostic region length mismatch")

    imports = import_addresses(pe)
    for name, expected in IAT.items():
        if imports.get(name) != expected:
            raise RuntimeError(f"Unexpected {name} IAT in {path.name}: {imports.get(name)!r}")

    hooks = [
        (MELEE_ROLL_HOOK_VA, MELEE_ROLL_ORIGINAL, MELEE_WRAPPER_VA),
        (SECOND_ROLL_HOOK_VA, SECOND_ROLL_ORIGINAL, SECOND_WRAPPER_VA),
    ]
    patched = bytearray(original)
    hook_reports: list[dict[str, Any]] = []
    for va, expected, wrapper_va in hooks:
        offset = pe.get_offset_from_rva(va - IMAGE_BASE)
        if original[offset:offset + len(expected)] != expected:
            raise RuntimeError(f"Hook source mismatch at 0x{va:08X} in {path.name}")
        replacement = relative_jump(va, wrapper_va, len(expected))
        patched[offset:offset + len(expected)] = replacement
        hook_reports.append({
            "va": f"0x{va:08X}", "file_offset": f"0x{offset:X}",
            "source_hex": expected.hex(" "), "patched_hex": replacement.hex(" "),
            "wrapper_va": f"0x{wrapper_va:08X}", "rollback_hex": expected.hex(" "),
        })
    region_start = LUCK_SECTION_RAW_OFFSET + PRESERVED_FORMAL_REGION_END
    if formal_prefix is not None:
        if len(formal_prefix) != PRESERVED_FORMAL_REGION_END:
            raise RuntimeError("Replacement formal prefix length mismatch")
        patched[
            LUCK_SECTION_RAW_OFFSET:
            LUCK_SECTION_RAW_OFFSET + PRESERVED_FORMAL_REGION_END
        ] = formal_prefix
    patched[region_start:region_start + len(region)] = region

    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    original_checksum = original[checksum_offset:checksum_offset + 4]
    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)

    parsed = pefile.PE(data=final, fast_load=False)
    parsed_section = parsed.sections[-1]
    final_section = final[
        parsed_section.PointerToRawData:
        parsed_section.PointerToRawData + parsed_section.SizeOfRawData
    ]
    expected_prefix = (
        source_section[:PRESERVED_FORMAL_REGION_END]
        if formal_prefix is None else formal_prefix
    )
    if final_section[:PRESERVED_FORMAL_REGION_END] != expected_prefix:
        raise RuntimeError(f"Fixed-Luck prefix mismatch in {path.name}")
    if final_section[PRESERVED_FORMAL_REGION_END:] != region:
        raise RuntimeError(f"Diagnostic region mismatch in {path.name}")

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    for report in hook_reports:
        offset = int(report["file_offset"], 16)
        va = int(report["va"], 16)
        instruction = next(decoder.disasm(final[offset:offset + 5], va))
        if (
            instruction.mnemonic != "jmp"
            or not instruction.operands
            or instruction.operands[0].type != X86_OP_IMM
            or int(instruction.operands[0].imm) != int(report["wrapper_va"], 16)
        ):
            raise RuntimeError(f"Hook target mismatch at {report['va']} in {path.name}")

    restored = bytearray(final)
    for va, expected, _ in hooks:
        offset = pe.get_offset_from_rva(va - IMAGE_BASE)
        restored[offset:offset + len(expected)] = expected
    restored[
        LUCK_SECTION_RAW_OFFSET:
        LUCK_SECTION_RAW_OFFSET + LUCK_SECTION_SIZE
    ] = source_section
    restored[checksum_offset:checksum_offset + 4] = original_checksum
    if bytes(restored) != original:
        raise RuntimeError(f"Full rollback failed for {path.name}")

    path.write_bytes(final)
    return {
        "name": path.name,
        "source_size": len(original),
        "output_size": len(final),
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "formal_luck_region_sha256": sha256_bytes(final_section[:PRESERVED_FORMAL_REGION_END]),
        "formal_luck_region_byte_preserved": formal_prefix is None,
        "diagnostic_region_sha256": sha256_bytes(region),
        "hooks": hook_reports,
        "contiguous_differences": contiguous_differences(original, final),
        "rollback_verified": True,
        "payload": region_meta,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 诊断测试说明

用途：确认“每支部队第一次主动攻击必定触发幸运”应挂接的真实运行入口。
本包不会改变 V1.11 的战斗效果、伤害、幸运结果、资源或英雄数据；只会为马洛迪亚与黛瑞丝记录幸运投骰路径。

安装：
1. 准备一份纯净 HotA 1.8.0 中文版 + HD Mod。
2. 将压缩包内全部文件解压到游戏根目录并覆盖。
3. 使用 h3hota HD.exe 启动。

最小测试：
1. 使用马洛迪亚或黛瑞丝进入战斗。
2. 至少完成一次主动近战攻击、一次主动远程攻击，并让己方部队发生一次反击。
3. 如方便，再测试一次二连击或多目标攻击；不要求幸运实际触发。
4. 退出游戏后，把游戏根目录生成的 {LOG_FILENAME} 上传给 Codex。

诊断文件只包含整数地址、英雄/兵种/队列字段和调用路径，不包含个人信息。
正式 V1.11 的固定幸运 +3 与厄运沙漏/诅咒之地硬封锁行为保持不变。
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

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }

    region, region_meta = build_diagnostic_region()
    exe_reports = [patch_executable(package_root / name, region, region_meta) for name in EXE_NAMES]
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
    changed = sorted(
        relative for relative in source_hashes
        if source_hashes[relative] != package_hashes[relative]
    )
    expected_changed = sorted([*EXE_NAMES, instruction_files[0].relative_to(package_root).as_posix()])
    if changed != expected_changed:
        raise RuntimeError(f"Unexpected changed package files: {changed}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"ZIP CRC failure: {failed}")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("ZIP member set mismatch")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "formal_release": False,
        "diagnostic_only": True,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "runtime_log": LOG_FILENAME,
        "record_magic": "ATK1",
        "record_size": RECORD_SIZE,
        "changed_package_files": changed,
        "source_file_hashes": source_hashes,
        "package_file_hashes": package_hashes,
        "executables": exe_reports,
        "static_verification": {
            "formal_v111_hashes_verified": True,
            "formal_fixed_luck_wrapper_preserved": True,
            "only_reserved_luck_section_space_used": True,
            "both_native_roll_hooks_verified": True,
            "standard_and_hd_built_separately": True,
            "full_executable_rollback_verified": True,
            "zip_crc_and_member_checks_passed": True,
            "gameplay_resources_byte_identical_to_v111": True,
        },
    }
    manifest_path = output_root / f"{BUILD_NAME}_manifest.json"
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_root / f"{BUILD_NAME}_README.txt").write_text(installation_text(), encoding="utf-8")
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    print("Changed package files: " + json.dumps(changed, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
