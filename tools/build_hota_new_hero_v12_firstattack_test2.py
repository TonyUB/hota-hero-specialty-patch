#!/usr/bin/env python3
"""Build V1.2 FIRSTATTACK TEST2 from the formal V1.11 release.

TEST1 proved the per-stack command qualification and bookkeeping, but wrote
H3CombatCreature::isLucky before HotA's real Luck roll.  HotA subsequently
overwrote that flag.  TEST2 keeps the proven command logic and hooks HotA's
actual Luck function instead, entering its native successful-luck branch for
an eligible first active attack.
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

import build_hota_new_hero_v12_firstattack_diag03 as diag03
import build_hota_new_hero_v12_firstattack_test1 as test1
from build_hota_new_hero_v1 import (
    EXE_NAMES,
    LANGUAGE_ARCHIVES,
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)
from build_hota_new_hero_v104 import assemble, contiguous_differences


BUILD_NAME = "HOTA_NEW_HERO_V1.2_FIRSTATTACK_TEST2"
LOG_FILENAME = "hota_luck_firsttest02.bin"

HOTA_LUCK_ROLL_VA = 0x10133880
HOTA_LUCK_ROLL_ORIGINAL = bytes.fromhex("56 57 8B 7C 24 10")
HOTA_LUCK_NATIVE_CONTINUE_VA = 0x10133886
HOTA_LUCK_SUCCESS_CONTINUE_VA = 0x101338E4
HOTA_LUCK_SUCCESS_WRITE_VA = 0x101338DD
HOTA_LUCK_WRAPPER_VA = diag03.CUREUI_VA + 0x400


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def relative_jump(source_va: int, target_va: int, width: int) -> bytes:
    if width < 5:
        raise ValueError("relative jump needs at least five bytes")
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5)) + b"\x90" * (width - 5)


def build_cureui_payload(
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

    # Entry state is the original HotA function entry.  Replay its six-byte
    # prologue first so both native and forced paths retain the exact original
    # stack frame.  The native success branch at 0x101338DD writes isLucky=1;
    # TEST2 performs that same write, records it, then continues at 0x101338E4
    # so HotA itself emits the normal animation, sound and combat-log message.
    source = f"""
    push esi
    push edi
    mov edi, dword ptr [esp + 0x10]
    cmp dword ptr [{command_force_va:#x}], 1
    jne native_luck
    cmp dword ptr [{current_attacker_va:#x}], edi
    jne native_luck

forced_luck:
    mov eax, dword ptr [edi + 0x70]
    mov dword ptr [edi + 0x70], 1
    pushfd
    pushad
    cld
    xor ecx, ecx
    mov edi, {record_va + 4:#x}
    mov ecx, 23
    xor eax, eax
    rep stosd
    mov ebx, dword ptr [esp]
    mov dword ptr [{record_va + 4:#x}], 40
    mov dword ptr [{record_va + 8:#x}], ebx
    mov eax, dword ptr [{current_attacker_va:#x}]
    mov dword ptr [{record_va + 12:#x}], eax
    mov eax, dword ptr [{command_force_va:#x}]
    mov dword ptr [{record_va + 16:#x}], eax
    mov eax, dword ptr [{gate_mask_va:#x}]
    mov dword ptr [{record_va + 20:#x}], eax
    mov eax, dword ptr [esp + 0x1c]
    mov dword ptr [{record_va + 24:#x}], eax
    mov eax, dword ptr [ebx + 0x70]
    mov dword ptr [{record_va + 28:#x}], eax
    mov eax, dword ptr [ebx + 0xf4]
    mov dword ptr [{record_va + 32:#x}], eax
    mov eax, dword ptr [ebx + 0xf8]
    mov dword ptr [{record_va + 36:#x}], eax
    mov eax, dword ptr [ebx + 0x4ec]
    mov dword ptr [{record_va + 40:#x}], eax
    mov eax, {test1.LOGGER_VA:#x}
    call eax
    popad
    popfd
    jmp {HOTA_LUCK_SUCCESS_CONTINUE_VA:#x}

native_luck:
    pushfd
    pushad
    cld
    mov edi, {record_va + 4:#x}
    mov ecx, 23
    xor eax, eax
    rep stosd
    mov ebx, dword ptr [esp]
    mov dword ptr [{record_va + 4:#x}], 41
    mov dword ptr [{record_va + 8:#x}], ebx
    mov eax, dword ptr [{current_attacker_va:#x}]
    mov dword ptr [{record_va + 12:#x}], eax
    mov eax, dword ptr [{command_force_va:#x}]
    mov dword ptr [{record_va + 16:#x}], eax
    mov eax, dword ptr [{gate_mask_va:#x}]
    mov dword ptr [{record_va + 20:#x}], eax
    mov eax, dword ptr [ebx + 0x70]
    mov dword ptr [{record_va + 24:#x}], eax
    mov dword ptr [{record_va + 28:#x}], eax
    mov eax, dword ptr [ebx + 0xf4]
    mov dword ptr [{record_va + 32:#x}], eax
    mov eax, dword ptr [ebx + 0xf8]
    mov dword ptr [{record_va + 36:#x}], eax
    mov eax, dword ptr [ebx + 0x4ec]
    mov dword ptr [{record_va + 40:#x}], eax
    mov eax, {test1.LOGGER_VA:#x}
    call eax
    popad
    popfd
    jmp {HOTA_LUCK_NATIVE_CONTINUE_VA:#x}
    """
    code = assemble(source, HOTA_LUCK_WRAPPER_VA)
    if HOTA_LUCK_WRAPPER_VA + len(code) > diag03.CUREUI_VA + diag03.CUREUI_SIZE:
        raise RuntimeError("Luck-roll wrapper exceeds reserved .cureui area")
    result = bytearray(source_section)
    start = HOTA_LUCK_WRAPPER_VA - diag03.CUREUI_VA
    result[start:start + len(code)] = code
    return bytes(result), {
        "aslr_safe": True,
        "accepted_cure_ui_prefix_preserved": True,
        "record_va": f"0x{record_va:08X}",
        "components": [{
            "name": "HotA native Luck-roll wrapper",
            "preferred_va": f"0x{HOTA_LUCK_WRAPPER_VA:08X}",
            "length": len(code),
            "native_continue_va": f"0x{HOTA_LUCK_NATIVE_CONTINUE_VA:08X}",
            "forced_success_continue_va": f"0x{HOTA_LUCK_SUCCESS_CONTINUE_VA:08X}",
            "assembly": source.strip(),
        }],
    }


def patch_hota_dll(
    path: Path,
    record_va: int,
    state: dict[str, str],
) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != diag03.SOURCE_HOTA_DLL_SHA256:
        raise RuntimeError("Unexpected formal V1.11 HotA.dll hash")
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != diag03.HOTA_IMAGE_BASE:
        raise RuntimeError("Unexpected HotA.dll image base")
    if not (pe.OPTIONAL_HEADER.DllCharacteristics & 0x40):
        raise RuntimeError("Expected HotA.dll ASLR flag is absent")
    section = pe.sections[-1]
    if (
        section.Name != diag03.CUREUI_NAME
        or section.VirtualAddress != diag03.CUREUI_RVA
        or section.PointerToRawData != diag03.CUREUI_RAW_OFFSET
        or section.SizeOfRawData != diag03.CUREUI_SIZE
        or section.Characteristics != diag03.CUREUI_CHARACTERISTICS
    ):
        raise RuntimeError("Unexpected formal .cureui section layout")
    source_section = original[
        diag03.CUREUI_RAW_OFFSET:diag03.CUREUI_RAW_OFFSET + diag03.CUREUI_SIZE
    ]
    if sha256_bytes(source_section) != diag03.SOURCE_CUREUI_SHA256:
        raise RuntimeError("Unexpected formal .cureui payload")

    hook_offset = pe.get_offset_from_rva(HOTA_LUCK_ROLL_VA - diag03.HOTA_IMAGE_BASE)
    if original[hook_offset:hook_offset + len(HOTA_LUCK_ROLL_ORIGINAL)] != HOTA_LUCK_ROLL_ORIGINAL:
        raise RuntimeError("HotA native Luck-roll entry mismatch")
    replacement = relative_jump(
        HOTA_LUCK_ROLL_VA, HOTA_LUCK_WRAPPER_VA, len(HOTA_LUCK_ROLL_ORIGINAL)
    )
    payload, payload_meta = build_cureui_payload(source_section, record_va, state)
    patched = bytearray(original)
    patched[hook_offset:hook_offset + len(HOTA_LUCK_ROLL_ORIGINAL)] = replacement
    patched[
        diag03.CUREUI_RAW_OFFSET:diag03.CUREUI_RAW_OFFSET + diag03.CUREUI_SIZE
    ] = payload

    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    original_checksum = original[checksum_offset:checksum_offset + 4]
    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    instruction = next(decoder.disasm(final[hook_offset:hook_offset + 5], HOTA_LUCK_ROLL_VA))
    if (
        instruction.mnemonic != "jmp"
        or not instruction.operands
        or instruction.operands[0].type != X86_OP_IMM
        or int(instruction.operands[0].imm) != HOTA_LUCK_WRAPPER_VA
    ):
        raise RuntimeError("HotA native Luck-roll hook target mismatch")

    restored = bytearray(final)
    restored[hook_offset:hook_offset + len(HOTA_LUCK_ROLL_ORIGINAL)] = HOTA_LUCK_ROLL_ORIGINAL
    restored[
        diag03.CUREUI_RAW_OFFSET:diag03.CUREUI_RAW_OFFSET + diag03.CUREUI_SIZE
    ] = source_section
    restored[checksum_offset:checksum_offset + 4] = original_checksum
    if bytes(restored) != original:
        raise RuntimeError("Exact HotA.dll rollback failed")
    if final[
        diag03.CUREUI_RAW_OFFSET:diag03.CUREUI_RAW_OFFSET + diag03.PRESERVED_CUREUI_END
    ] != source_section[:diag03.PRESERVED_CUREUI_END]:
        raise RuntimeError("Accepted Cure UI payload changed")

    path.write_bytes(final)
    return {
        "name": path.name,
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "source_cureui_sha256": diag03.SOURCE_CUREUI_SHA256,
        "output_cureui_sha256": sha256_bytes(payload),
        "accepted_cureui_prefix_preserved": True,
        "hook": {
            "name": "HotA actual Luck-roll entry",
            "preferred_va": f"0x{HOTA_LUCK_ROLL_VA:08X}",
            "file_offset": f"0x{hook_offset:X}",
            "source_hex": HOTA_LUCK_ROLL_ORIGINAL.hex(" "),
            "patched_hex": replacement.hex(" "),
            "target_preferred_va": f"0x{HOTA_LUCK_WRAPPER_VA:08X}",
            "rollback_hex": HOTA_LUCK_ROLL_ORIGINAL.hex(" "),
        },
        "payload": payload_meta,
        "contiguous_differences": contiguous_differences(original, final),
        "rollback_verified": True,
    }


def installation_text() -> str:
    # Reuse the already reviewed TEST1 wording; only the build/log names differ.
    return test1.installation_text()


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
    if sha256_file(source_zip) != test1.SOURCE_ZIP_SHA256:
        raise RuntimeError("Formal V1.11 ZIP hash mismatch")

    # The imported executable/resource builders intentionally use module-level
    # names for deterministic metadata and the embedded log filename.
    test1.BUILD_NAME = BUILD_NAME
    test1.LOG_FILENAME = LOG_FILENAME

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    exe_payload, exe_meta = test1.build_exe_payload()
    record_va = int(exe_meta["record_va"], 16)
    exe_reports = [
        test1.patch_executable(package_root / name, exe_payload, exe_meta)
        for name in EXE_NAMES
    ]
    dll_report = patch_hota_dll(
        package_root / diag03.HOTA_DLL_NAME, record_va, exe_meta["state"]
    )
    resource_reports = [
        test1.patch_lod(package_root / relative, package_root)
        for relative in LANGUAGE_ARCHIVES
    ]
    resource_reports.append(
        test1.patch_loose(package_root / test1.luck_v11.LOOSE_HEROSPEC_RELATIVE, package_root)
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
        | {test1.luck_v11.LOOSE_HEROSPEC_RELATIVE, instruction_files[0].name}
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
        "source_release": test1.SOURCE_NAME,
        "source_zip_sha256": test1.SOURCE_ZIP_SHA256,
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
            "hero_ids": [test1.MELODIA_ID, test1.DAREMYTH_ID],
            "per_stack_first_active_attack_guaranteed_lucky": True,
            "retaliation_does_not_consume_or_inherit": True,
            "same_command_repeated_hits_inherit": True,
            "later_attacks_use_native_luck": True,
            "native_hard_suppression_preserved_by_post_gate_marker": True,
        },
        "test1_failure_addressed": {
            "test1_callback_write_was_overwritten": True,
            "actual_hota_luck_function_preferred_va": f"0x{HOTA_LUCK_ROLL_VA:08X}",
            "forced_path_enters_native_success_branch": True,
            "native_success_write_preferred_va": f"0x{HOTA_LUCK_SUCCESS_WRITE_VA:08X}",
        },
        "static_verification": {
            "firsttest01_action_and_state_chain_reused": True,
            "actual_hota_luck_roll_entry_hooked": True,
            "native_lucky_animation_sound_log_path_reused": True,
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
