#!/usr/bin/env python3
"""Build the true HotA.dll attack-callback diagnostic from formal V1.11."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path
from typing import Any

import pefile

import build_hota_new_hero_v12_firstattack_diag01 as exe_base
from build_hota_new_hero_v12_firstattack_diag02 import build_probe_prefix


BUILD_NAME = "HOTA_NEW_HERO_V1.2_FIRSTATTACK_DIAG03"
LOG_FILENAME = "hota_luck_firstdiag03.bin"
HOTA_DLL_NAME = "HotA.dll"
SOURCE_HOTA_DLL_SHA256 = "2b642ae18c3b4dcc074092c45f725a81d4c21e27868cb5a0c67c9df6e05ed2b9"

HOTA_IMAGE_BASE = 0x10000000
CUREUI_NAME = b".cureui\0"
CUREUI_RVA = 0x04692000
CUREUI_VA = HOTA_IMAGE_BASE + CUREUI_RVA
CUREUI_SIZE = 0x1000
CUREUI_RAW_OFFSET = 0x00265E00
CUREUI_CHARACTERISTICS = 0xE0000020
SOURCE_CUREUI_SHA256 = "5d435b6306dc58aeec95f01d3e2930911af32db20bbecf0c732e772048556b36"
PRESERVED_CUREUI_END = 0x400

HOTA_MELEE_CALLBACK_VA = 0x101392F0
HOTA_MELEE_ORIGINAL = bytes.fromhex("83 EC 0C 53 55 56")
HOTA_MELEE_CONTINUE_VA = HOTA_MELEE_CALLBACK_VA + len(HOTA_MELEE_ORIGINAL)
HOTA_SECOND_CALLBACK_VA = 0x10129560
HOTA_SECOND_ORIGINAL = bytes.fromhex("A1 04 54 63 10 53")
HOTA_SECOND_CONTINUE_VA = HOTA_SECOND_CALLBACK_VA + len(HOTA_SECOND_ORIGINAL)
HOTA_GLOBAL_RVA = 0x00635404

MELEE_WRAPPER_VA = CUREUI_VA + 0x400
SECOND_WRAPPER_VA = CUREUI_VA + 0x700
SECOND_REPLAY_VA = CUREUI_VA + 0xA00


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def relative_jump(source_va: int, target_va: int, width: int) -> bytes:
    if width < 5:
        raise ValueError("relative jump needs at least five bytes")
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5)) + b"\x90" * (width - 5)


def relocated_push_ret(target_va: int) -> bytes:
    # The original A1 operand at callback+1 has a PE HIGHLOW relocation. Reuse
    # that relocation for the absolute wrapper VA instead of placing an E9
    # displacement under a relocation entry.
    return b"\x68" + struct.pack("<I", target_va) + b"\xC3"


def build_callback_wrapper(
    *,
    wrapper_va: int,
    path_id: int,
    attacker_entry_offset: int,
    record_va: int,
    native_tail: str,
) -> tuple[bytes, str]:
    # After pushfd/pushad, original entry ESP is current ESP + 0x24.
    source = f"""
    pushfd
    pushad
    mov dword ptr [{record_va + 4:#x}], {path_id}
    mov eax, dword ptr [esp + 0x24]
    mov dword ptr [{record_va + 8:#x}], eax
    mov eax, dword ptr [esp + {0x24 + attacker_entry_offset:#x}]
    mov dword ptr [{record_va + 12:#x}], eax
    mov edx, dword ptr [esp + 0x28]
    mov dword ptr [{record_va + 16:#x}], edx
    mov edx, dword ptr [esp + 0x2c]
    mov dword ptr [{record_va + 20:#x}], edx
    mov edx, dword ptr [esp + 0x30]
    mov dword ptr [{record_va + 24:#x}], edx
    mov edx, dword ptr [esp + 0x34]
    mov dword ptr [{record_va + 28:#x}], edx
    mov edx, dword ptr [esp + 0x1c]
    mov dword ptr [{record_va + 32:#x}], edx
    mov edx, dword ptr [esp + 0x18]
    mov dword ptr [{record_va + 36:#x}], edx
    mov edx, dword ptr [esp + 0x14]
    mov dword ptr [{record_va + 40:#x}], edx
    mov edx, dword ptr [esp + 0x10]
    mov dword ptr [{record_va + 44:#x}], edx
    mov edx, dword ptr [esp + 0x04]
    mov dword ptr [{record_va + 48:#x}], edx
    mov edx, dword ptr [esp]
    mov dword ptr [{record_va + 52:#x}], edx
    mov edx, dword ptr [esp + 0x08]
    mov dword ptr [{record_va + 56:#x}], edx
    mov edx, dword ptr [esp + 0x38]
    mov dword ptr [{record_va + 60:#x}], edx
    mov edx, dword ptr [esp + 0x3c]
    mov dword ptr [{record_va + 64:#x}], edx
    mov edx, dword ptr [esp + 0x40]
    mov dword ptr [{record_va + 68:#x}], edx
    mov edx, dword ptr [esp + 0x44]
    mov dword ptr [{record_va + 72:#x}], edx
    mov edx, dword ptr [esp + 0x48]
    mov dword ptr [{record_va + 76:#x}], edx
    mov edx, dword ptr [esp + 0x4c]
    mov dword ptr [{record_va + 80:#x}], edx
    mov edx, dword ptr [esp + 0x50]
    mov dword ptr [{record_va + 84:#x}], edx
    mov ecx, dword ptr [{exe_base.BATTLE_MANAGER_PTR:#x}]
    xor edx, edx
    mov dword ptr [{record_va + 88:#x}], ecx
    mov dword ptr [{record_va + 92:#x}], edx
    test ecx, ecx
    je skip_log
    mov eax, {exe_base.LOGGER_VA:#x}
    call eax
skip_log:
    popad
    popfd
    {native_tail}
    """
    return exe_base.assemble(source, wrapper_va), source.strip()


def build_cureui_payload(source_section: bytes, record_va: int) -> tuple[bytes, dict[str, Any]]:
    if len(source_section) != CUREUI_SIZE:
        raise RuntimeError("Unexpected .cureui section size")
    if any(source_section[PRESERVED_CUREUI_END:]):
        raise RuntimeError("Reserved .cureui diagnostic region is not empty")

    melee_native = f"""
    sub esp, 0x0c
    push ebx
    push ebp
    push esi
    jmp {HOTA_MELEE_CONTINUE_VA:#x}
    """
    melee_code, melee_source = build_callback_wrapper(
        wrapper_va=MELEE_WRAPPER_VA,
        path_id=3,
        attacker_entry_offset=0x08,
        record_va=record_va,
        native_tail=melee_native,
    )
    second_native = f"""
    jmp {SECOND_REPLAY_VA:#x}
    """
    second_code, second_source = build_callback_wrapper(
        wrapper_va=SECOND_WRAPPER_VA,
        path_id=4,
        attacker_entry_offset=0x10,
        record_va=record_va,
        native_tail=second_native,
    )
    replay_rva = SECOND_REPLAY_VA - HOTA_IMAGE_BASE
    replay_source = f"""
    call base_here
base_here:
    pop eax
    sub eax, {replay_rva + 5:#x}
    mov eax, dword ptr [eax + {HOTA_GLOBAL_RVA:#x}]
    push ebx
    jmp {HOTA_SECOND_CONTINUE_VA:#x}
    """
    replay_code = exe_base.assemble(replay_source, SECOND_REPLAY_VA)

    slots = [
        ("hota_43f620_callback", MELEE_WRAPPER_VA, SECOND_WRAPPER_VA, melee_code, melee_source),
        ("hota_441330_callback", SECOND_WRAPPER_VA, SECOND_REPLAY_VA, second_code, second_source),
        ("aslr_safe_second_replay", SECOND_REPLAY_VA, CUREUI_VA + CUREUI_SIZE,
         replay_code, replay_source.strip()),
    ]
    result = bytearray(source_section)
    components: list[dict[str, Any]] = []
    for name, va, limit, code, source in slots:
        if va + len(code) > limit:
            raise RuntimeError(f"{name} exceeds reserved .cureui slot")
        start = va - CUREUI_VA
        result[start:start + len(code)] = code
        components.append({
            "name": name,
            "preferred_va": f"0x{va:08X}",
            "length": len(code),
            "limit_preferred_va": f"0x{limit:08X}",
            "assembly": source,
        })
    return bytes(result), {
        "aslr_safe": True,
        "reuses_fixed_exe_logger": f"0x{exe_base.LOGGER_VA:08X}",
        "record_va": f"0x{record_va:08X}",
        "paths": {
            "3": "HotA replacement callback for native 0x0043F620",
            "4": "HotA replacement callback for native 0x00441330",
        },
        "record_layout_paths_3_4": [
            "magic ATK1", "path", "callback caller return", "attacker stack",
            "raw arg1", "raw arg2", "raw arg3", "raw arg4",
            "entry EAX", "entry ECX", "entry EDX", "entry EBX", "entry ESI",
            "entry EDI", "entry EBP", "raw arg5", "raw arg6", "raw arg7",
            "raw arg8", "raw arg9", "raw arg10", "raw arg11",
            "battle-manager pointer", "reserved zero",
        ],
        "components": components,
    }


def patch_hota_dll(path: Path, record_va: int) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_HOTA_DLL_SHA256:
        raise RuntimeError("Unexpected formal V1.11 HotA.dll hash")
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != HOTA_IMAGE_BASE:
        raise RuntimeError("Unexpected HotA.dll image base")
    if not (pe.OPTIONAL_HEADER.DllCharacteristics & 0x40):
        raise RuntimeError("Expected HotA.dll ASLR flag is absent")
    section = pe.sections[-1]
    if (
        section.Name != CUREUI_NAME
        or section.VirtualAddress != CUREUI_RVA
        or section.PointerToRawData != CUREUI_RAW_OFFSET
        or section.SizeOfRawData != CUREUI_SIZE
        or section.Characteristics != CUREUI_CHARACTERISTICS
    ):
        raise RuntimeError("Unexpected formal .cureui section layout")
    source_section = original[CUREUI_RAW_OFFSET:CUREUI_RAW_OFFSET + CUREUI_SIZE]
    if sha256_bytes(source_section) != SOURCE_CUREUI_SHA256:
        raise RuntimeError("Unexpected formal .cureui payload")

    relocation_rvas = {
        entry.rva
        for block in pe.DIRECTORY_ENTRY_BASERELOC
        for entry in block.entries
        if entry.type == pefile.RELOCATION_TYPE["IMAGE_REL_BASED_HIGHLOW"]
    }
    second_operand_rva = HOTA_SECOND_CALLBACK_VA - HOTA_IMAGE_BASE + 1
    if second_operand_rva not in relocation_rvas:
        raise RuntimeError("Expected callback-2 HIGHLOW relocation is absent")

    hooks = [
        (HOTA_MELEE_CALLBACK_VA, HOTA_MELEE_ORIGINAL, MELEE_WRAPPER_VA, "rel32"),
        (HOTA_SECOND_CALLBACK_VA, HOTA_SECOND_ORIGINAL, SECOND_WRAPPER_VA,
         "relocated_push_ret"),
    ]
    patched = bytearray(original)
    hook_reports: list[dict[str, Any]] = []
    for va, expected, wrapper, hook_kind in hooks:
        offset = pe.get_offset_from_rva(va - HOTA_IMAGE_BASE)
        if original[offset:offset + len(expected)] != expected:
            raise RuntimeError(f"HotA callback source mismatch at 0x{va:08X}")
        replacement = (
            relative_jump(va, wrapper, len(expected))
            if hook_kind == "rel32"
            else relocated_push_ret(wrapper)
        )
        patched[offset:offset + len(expected)] = replacement
        hook_reports.append({
            "preferred_va": f"0x{va:08X}",
            "file_offset": f"0x{offset:X}",
            "source_hex": expected.hex(" "),
            "patched_hex": replacement.hex(" "),
            "wrapper_preferred_va": f"0x{wrapper:08X}",
            "hook_kind": hook_kind,
            "rollback_hex": expected.hex(" "),
        })
    payload, payload_meta = build_cureui_payload(source_section, record_va)
    patched[CUREUI_RAW_OFFSET:CUREUI_RAW_OFFSET + CUREUI_SIZE] = payload

    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    original_checksum = original[checksum_offset:checksum_offset + 4]
    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)

    parsed = pefile.PE(data=final, fast_load=False)
    final_section = final[CUREUI_RAW_OFFSET:CUREUI_RAW_OFFSET + CUREUI_SIZE]
    if final_section[:PRESERVED_CUREUI_END] != source_section[:PRESERVED_CUREUI_END]:
        raise RuntimeError("Accepted Cure UI payload changed")
    if final_section != payload:
        raise RuntimeError("DIAG03 .cureui payload mismatch")

    restored = bytearray(final)
    for va, expected, _, _ in hooks:
        offset = pe.get_offset_from_rva(va - HOTA_IMAGE_BASE)
        restored[offset:offset + len(expected)] = expected
    restored[CUREUI_RAW_OFFSET:CUREUI_RAW_OFFSET + CUREUI_SIZE] = source_section
    restored[checksum_offset:checksum_offset + 4] = original_checksum
    if bytes(restored) != original:
        raise RuntimeError("Exact HotA.dll rollback failed")

    path.write_bytes(final)
    return {
        "name": HOTA_DLL_NAME,
        "source_size": len(original),
        "output_size": len(final),
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "source_cureui_sha256": SOURCE_CUREUI_SHA256,
        "output_cureui_sha256": sha256_bytes(final_section),
        "accepted_cureui_prefix_preserved": True,
        "callback_2_existing_highlow_relocation_reused": True,
        "hooks": hook_reports,
        "payload": payload_meta,
        "rollback_verified": True,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 真实攻击回调诊断说明

DIAG02 已证明 HotA 1.8.0 在启动时整体替换了 EXE 的两段原生攻击函数。本包直接记录 HotA.dll 的两个真实替代回调，不改变伤害、幸运结果、攻击次数或正式 V1.11 的任何功能。

安装：覆盖到纯净 HotA 1.8.0 中文版目录，使用 h3hota HD.exe 启动。

请按顺序测试：
1. 普通主动近战攻击；
2. 反击；
3. 主动射击；
4. 双射；
5. 环击。

随后退出游戏并上传根目录生成的 {LOG_FILENAME}。
本包仍是诊断版，尚未强制第一次攻击触发幸运。
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
    if sha256_file(source_zip) != exe_base.SOURCE_ZIP_SHA256:
        raise RuntimeError("Formal V1.11 ZIP hash mismatch")

    old_filename = exe_base.LOG_FILENAME
    exe_base.LOG_FILENAME = LOG_FILENAME
    try:
        exe_region, exe_meta = exe_base.build_diagnostic_region(filter_specialists=False)
    finally:
        exe_base.LOG_FILENAME = old_filename
    record_va = int(str(exe_meta["record_va"]), 16)
    probe_prefix, probe_meta = build_probe_prefix(record_va)
    exe_meta["fixed_luck_probe"] = probe_meta

    package_root = build_root / BUILD_NAME
    exe_base.safe_recreate_directory(package_root, build_root)
    exe_base.extract_zip_safely(source_zip, package_root)
    source_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    exe_reports = [
        exe_base.patch_executable(
            package_root / name,
            exe_region,
            exe_meta,
            formal_prefix=probe_prefix,
        )
        for name in exe_base.EXE_NAMES
    ]
    dll_report = patch_hota_dll(package_root / HOTA_DLL_NAME, record_va)
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
    expected_changed = sorted([
        *exe_base.EXE_NAMES,
        HOTA_DLL_NAME,
        instruction_files[0].relative_to(package_root).as_posix(),
    ])
    if changed != expected_changed:
        raise RuntimeError(f"Unexpected changed package files: {changed}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    exe_base.deterministic_zip(package_root, zip_path)
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
        "source_release": exe_base.SOURCE_NAME,
        "source_zip_sha256": exe_base.SOURCE_ZIP_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "runtime_log": LOG_FILENAME,
        "record_magic": "ATK1",
        "record_size": exe_base.RECORD_SIZE,
        "runtime_evidence": {
            "hota_runtime_base_observed": "0x65A20000",
            "native_43f620_callback_runtime": "0x65B592F0",
            "native_441330_callback_runtime": "0x65B49560",
            "preferred_callbacks": [
                f"0x{HOTA_MELEE_CALLBACK_VA:08X}",
                f"0x{HOTA_SECOND_CALLBACK_VA:08X}",
            ],
        },
        "changed_package_files": changed,
        "source_file_hashes": source_hashes,
        "package_file_hashes": package_hashes,
        "executables": exe_reports,
        "hota_dll": dll_report,
        "static_verification": {
            "formal_v111_hashes_verified": True,
            "accepted_cure_ui_prefix_preserved": True,
            "only_existing_zero_cureui_space_used": True,
            "aslr_safe_relative_dll_hooks": True,
            "aslr_safe_second_callback_replay": True,
            "standard_and_hd_built_separately": True,
            "full_executable_and_dll_rollback_verified": True,
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
    print("Changed package files: " + json.dumps(changed, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
