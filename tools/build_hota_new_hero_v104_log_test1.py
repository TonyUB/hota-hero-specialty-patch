#!/usr/bin/env python3
"""Build the V1.04 combat-log candidate from accepted V1.03.

This candidate leaves Cure arithmetic, the spell book, resurrection messages,
and all data archives unchanged.  It adds one localized ``creature: +H`` line
for every Uland/Astra stack that reaches Cure settlement.  Single-target Cure
appends the line immediately; mass Cure buffers the lines until the native Cure
cast line has been appended, then replays the already-accepted resurrection
messages.
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
import keystone
import pefile
from capstone.x86_const import X86_OP_IMM

from build_hota_new_hero_v1 import (
    EXE_NAMES,
    LANGUAGE_ARCHIVES,
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)
from build_hota_new_hero_v103 import (
    ASTRA_SKILLS_AFTER,
    BONUS_CALC_VA,
    CORPSE_CURE_CALC_VA,
    CURE_SPECIALTY_CALL_VA,
    DISPATCH_VA,
    IMAGE_BASE,
    RELEASE_CURE_TEXT,
    build_formula_payloads,
    locate_astra_hdat_blob,
    total_cure,
)


BUILD_NAME = "HOTA_NEW_HERO_V1.04_LOG_TEST1"
SOURCE_NAME = "HOTA_NEW_HERO_V1.03"
SOURCE_ZIP_SHA256 = "11b16774cf8167fa1f4d6e288167bc1298ccd6fb22e84ce588f178253ed8e7b9"
SOURCE_HOTA_DAT_SHA256 = "bcabc72b9511b3d6787ba23f8bc3b1fd2df729080ec4fc1e64a5ea070d240517"

NATIVE_CURE_CORE_VA = 0x00446220
SPECIALIST_WRAPPER_VA = 0x00639DD0
LIVING_CURE_CALL_VA = 0x00639E28
CORPSE_CALC_CALL_VA = 0x00639EA5
MASS_INIT_VA = 0x0065DA00
RES_CAPTURE_VA = 0x0065DA20
MASS_FLUSH_VA = 0x0065DAA0
MASS_FLUSH_CONTINUE_VA = 0x0065DAA5
RES_FLUSH_END_VA = 0x0065DB3C

LIVE_LOG_WRAPPER_VA = 0x0065DB40
CORPSE_LOG_WRAPPER_VA = 0x0065DB90
RECORD_HELPER_VA = 0x0065DBD0
APPEND_HELPER_VA = 0x0065DC30
FLUSH_HELPER_VA = 0x0065DCA0
FLUSH_TRAMPOLINE_VA = 0x0065DCE0

RES_COUNT_VA = 0x0065DD00
TREATMENT_COUNT_VA = 0x0065DD7C
TREATMENT_RECORDS_VA = 0x0065DD80
TREATMENT_FORMAT_VA = 0x0065DDF0
TREATMENT_FORMAT = b"%s: +%d\0"
MASS_SCOPE_FLAG_VA = 0x00639FFC

CREATURE_TABLE_POINTER_VA = 0x006747B0
TEXT_BUFFER_VA = 0x00697428
SPRINTF_VA = 0x006179DE
LOG_APPEND_VA = 0x004729D0
MAX_TREATMENT_RECORDS = 14

SOURCE_EXE_SHA256 = {
    "h3hota.exe": "a85c4db22c3afe06d3c09c15e832a3f4dbb3de61b873541e1985ac208eabee9f",
    "h3hota HD.exe": "dce0882d870fa75f14d05891b261b8bfd978facdba2f12d005b9cc4d9299b6dd",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def assemble(source: str, address: int) -> bytes:
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoded, _ = engine.asm(source, addr=address)
    return bytes(encoded)


def relative_call(source_va: int, target_va: int) -> bytes:
    return b"\xE8" + struct.pack("<i", target_va - (source_va + 5))


def relative_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + struct.pack("<i", target_va - (source_va + 5))


def va_to_offset(pe: pefile.PE, va: int) -> int:
    return pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)


def contiguous_differences(before: bytes, after: bytes) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    start: int | None = None
    for index, (left, right) in enumerate(zip(before, after)):
        if left != right and start is None:
            start = index
        if left == right and start is not None:
            differences.append(
                {
                    "file_offset": start,
                    "length": index - start,
                    "source_hex": before[start:index].hex(" "),
                    "release_hex": after[start:index].hex(" "),
                    "rollback_hex": before[start:index].hex(" "),
                }
            )
            start = None
    if start is not None:
        differences.append(
            {
                "file_offset": start,
                "length": len(before) - start,
                "source_hex": before[start:].hex(" "),
                "release_hex": after[start:].hex(" "),
                "rollback_hex": before[start:].hex(" "),
            }
        )
    return differences


def build_log_payloads() -> dict[str, bytes]:
    mass_init = assemble(
        f"""
        mov byte ptr [{RES_COUNT_VA:#x}], 0
        mov byte ptr [{TREATMENT_COUNT_VA:#x}], 0
        or byte ptr [{MASS_SCOPE_FLAG_VA:#x}], 0x80
        ret
        """,
        MASS_INIT_VA,
    )
    live_wrapper = assemble(
        f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        mov esi, ecx
        push dword ptr [ebp + 0x10]
        push dword ptr [ebp + 0x0c]
        push dword ptr [ebp + 0x08]
        mov ecx, esi
        call {NATIVE_CURE_CORE_VA:#x}
        mov edi, eax
        push dword ptr [ebp + 0x10]
        push dword ptr [ebp + 0x0c]
        push dword ptr [ebp + 0x08]
        push esi
        call {CORPSE_CURE_CALC_VA:#x}
        push ebx
        push eax
        push esi
        call {RECORD_HELPER_VA:#x}
        mov eax, edi
        pop edi
        pop esi
        pop ebx
        mov esp, ebp
        pop ebp
        ret 0x0c
        """,
        LIVE_LOG_WRAPPER_VA,
    )
    corpse_wrapper = assemble(
        f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        push dword ptr [ebp + 0x14]
        push dword ptr [ebp + 0x10]
        push dword ptr [ebp + 0x0c]
        push dword ptr [ebp + 0x08]
        call {CORPSE_CURE_CALC_VA:#x}
        mov edi, eax
        push ebx
        push edi
        push dword ptr [ebp + 0x08]
        call {RECORD_HELPER_VA:#x}
        mov eax, edi
        pop edi
        pop esi
        pop ebx
        mov esp, ebp
        pop ebp
        ret 0x10
        """,
        CORPSE_LOG_WRAPPER_VA,
    )
    record_helper = assemble(
        f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        mov eax, dword ptr [{MASS_SCOPE_FLAG_VA:#x}]
        test al, 0x80
        jz immediate
        movzx eax, byte ptr [{TREATMENT_COUNT_VA:#x}]
        cmp eax, {MAX_TREATMENT_RECORDS}
        jae done
        mov edx, dword ptr [ebp + 0x08]
        mov edx, dword ptr [edx + 0x34]
        mov dword ptr [{TREATMENT_RECORDS_VA:#x} + eax * 8], edx
        mov edx, dword ptr [ebp + 0x0c]
        mov dword ptr [{TREATMENT_RECORDS_VA + 4:#x} + eax * 8], edx
        inc byte ptr [{TREATMENT_COUNT_VA:#x}]
        jmp done
    immediate:
        push dword ptr [ebp + 0x0c]
        mov eax, dword ptr [ebp + 0x08]
        push dword ptr [eax + 0x34]
        push dword ptr [ebp + 0x10]
        call {APPEND_HELPER_VA:#x}
    done:
        pop esi
        pop ebx
        mov esp, ebp
        pop ebp
        ret 0x0c
        """,
        RECORD_HELPER_VA,
    )
    append_helper = assemble(
        f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        mov eax, dword ptr [ebp + 0x0c]
        imul eax, eax, 0x74
        mov edx, dword ptr [{CREATURE_TABLE_POINTER_VA:#x}]
        mov edx, dword ptr [edx + eax + 0x14]
        push dword ptr [ebp + 0x10]
        push edx
        push {TREATMENT_FORMAT_VA:#x}
        push {TEXT_BUFFER_VA:#x}
        mov eax, {SPRINTF_VA:#x}
        call eax
        add esp, 0x10
        mov eax, dword ptr [ebp + 0x08]
        mov ecx, dword ptr [eax + 0x132fc]
        push 0
        push 1
        push {TEXT_BUFFER_VA:#x}
        mov eax, {LOG_APPEND_VA:#x}
        call eax
        pop edi
        pop esi
        pop ebx
        mov esp, ebp
        pop ebp
        ret 0x0c
        """,
        APPEND_HELPER_VA,
    )
    flush_helper = assemble(
        f"""
        push eax
        push ebx
        push esi
        movzx ebx, byte ptr [{TREATMENT_COUNT_VA:#x}]
        mov byte ptr [{TREATMENT_COUNT_VA:#x}], 0
        test ebx, ebx
        jz done
        mov esi, {TREATMENT_RECORDS_VA:#x}
    loop_records:
        push dword ptr [esi + 4]
        push dword ptr [esi]
        push dword ptr [ebp - 0x20]
        call {APPEND_HELPER_VA:#x}
        add esi, 8
        dec ebx
        jnz loop_records
    done:
        pop esi
        pop ebx
        pop eax
        ret
        """,
        FLUSH_HELPER_VA,
    )
    flush_trampoline = assemble(
        f"""
        call {FLUSH_HELPER_VA:#x}
        push ebx
        push esi
        push edi
        xor eax, eax
        jmp {MASS_FLUSH_CONTINUE_VA:#x}
        """,
        FLUSH_TRAMPOLINE_VA,
    )
    expected_lengths = {
        "mass_init": 22,
        "live_wrapper": 60,
        "corpse_wrapper": 46,
        "record_helper": 82,
        "append_helper": 80,
        "flush_helper": 49,
        "flush_trampoline": 15,
    }
    payloads = {
        "mass_init": mass_init,
        "live_wrapper": live_wrapper,
        "corpse_wrapper": corpse_wrapper,
        "record_helper": record_helper,
        "append_helper": append_helper,
        "flush_helper": flush_helper,
        "flush_trampoline": flush_trampoline,
        "format": TREATMENT_FORMAT,
    }
    for name, expected in expected_lengths.items():
        if len(payloads[name]) != expected:
            raise RuntimeError(f"Unexpected {name} length {len(payloads[name])} != {expected}")
    return payloads


def decode_relative_target(code: bytes, address: int, mnemonic: str) -> int:
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    instruction = next(decoder.disasm(code, address))
    if (
        instruction.mnemonic != mnemonic
        or not instruction.operands
        or instruction.operands[0].type != X86_OP_IMM
    ):
        raise RuntimeError(f"Could not decode {mnemonic} at {address:#x}")
    return int(instruction.operands[0].imm)


def patch_executable(executable: Path, payloads: dict[str, bytes]) -> dict[str, Any]:
    original = executable.read_bytes()
    if sha256_bytes(original) != SOURCE_EXE_SHA256[executable.name]:
        raise RuntimeError(f"Unexpected V1.03 source hash for {executable.name}")
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != IMAGE_BASE:
        raise RuntimeError(f"Unexpected image base in {executable.name}")
    if pe.OPTIONAL_HEADER.DllCharacteristics & 0x40:
        raise RuntimeError(f"Unexpected ASLR in {executable.name}")

    formula_dispatch, formula_bonus, formula_corpse, _ = build_formula_payloads()
    preserved_regions = {
        "formula_dispatch": (DISPATCH_VA, formula_dispatch),
        "formula_bonus": (BONUS_CALC_VA, formula_bonus),
        "corpse_formula": (CORPSE_CURE_CALC_VA, formula_corpse),
        "res_capture": (
            RES_CAPTURE_VA,
            original[va_to_offset(pe, RES_CAPTURE_VA) : va_to_offset(pe, MASS_FLUSH_VA)],
        ),
        "res_flush_body": (
            MASS_FLUSH_CONTINUE_VA,
            original[va_to_offset(pe, MASS_FLUSH_CONTINUE_VA) : va_to_offset(pe, RES_FLUSH_END_VA)],
        ),
    }
    for label, (va, expected) in preserved_regions.items():
        offset = va_to_offset(pe, va)
        if original[offset : offset + len(expected)] != expected:
            raise RuntimeError(f"{label} source mismatch in {executable.name}")

    source_mass_init = bytes.fromhex(
        "C6 05 00 DD 65 00 00 80 0D FC 9F 63 00 80 C3"
    ) + b"\x00" * 7
    source_flush_entry = bytes.fromhex("53 56 57 31 C0")
    expected_sites = {
        "living_call": (LIVING_CURE_CALL_VA, relative_call(LIVING_CURE_CALL_VA, NATIVE_CURE_CORE_VA)),
        "corpse_call": (CORPSE_CALC_CALL_VA, relative_call(CORPSE_CALC_CALL_VA, CORPSE_CURE_CALC_VA)),
        "mass_init": (MASS_INIT_VA, source_mass_init),
        "flush_entry": (MASS_FLUSH_VA, source_flush_entry),
    }
    for label, (va, expected) in expected_sites.items():
        offset = va_to_offset(pe, va)
        if original[offset : offset + len(expected)] != expected:
            raise RuntimeError(f"{label} source mismatch in {executable.name}")

    cave_payloads = {
        LIVE_LOG_WRAPPER_VA: payloads["live_wrapper"],
        CORPSE_LOG_WRAPPER_VA: payloads["corpse_wrapper"],
        RECORD_HELPER_VA: payloads["record_helper"],
        APPEND_HELPER_VA: payloads["append_helper"],
        FLUSH_HELPER_VA: payloads["flush_helper"],
        FLUSH_TRAMPOLINE_VA: payloads["flush_trampoline"],
        TREATMENT_FORMAT_VA: payloads["format"],
    }
    for va, replacement in cave_payloads.items():
        offset = va_to_offset(pe, va)
        if original[offset : offset + len(replacement)] != b"\x00" * len(replacement):
            raise RuntimeError(f"Code/data cave at {va:#x} is not zero in {executable.name}")
    treatment_state_offset = va_to_offset(pe, TREATMENT_COUNT_VA)
    if original[treatment_state_offset : treatment_state_offset + 0x74] != b"\x00" * 0x74:
        raise RuntimeError(f"Treatment state cave changed in {executable.name}")

    section = next(
        item
        for item in pe.sections
        if item.VirtualAddress <= LIVE_LOG_WRAPPER_VA - IMAGE_BASE
        < item.VirtualAddress + max(item.Misc_VirtualSize, item.SizeOfRawData)
    )
    mapped_end = section.VirtualAddress + section.Misc_VirtualSize + IMAGE_BASE
    if TREATMENT_FORMAT_VA + len(TREATMENT_FORMAT) > mapped_end:
        raise RuntimeError(f"Log cave is not mapped in {executable.name}")
    if section.Characteristics & 0xE0000000 != 0xE0000000:
        raise RuntimeError(f"Log cave section is not RWX in {executable.name}")

    replacements = [
        ("Living Cure settlement logger call", LIVING_CURE_CALL_VA, relative_call(LIVING_CURE_CALL_VA, LIVE_LOG_WRAPPER_VA)),
        ("Full-corpse Cure logger call", CORPSE_CALC_CALL_VA, relative_call(CORPSE_CALC_CALL_VA, CORPSE_LOG_WRAPPER_VA)),
        ("Mass Cure log-buffer initialization", MASS_INIT_VA, payloads["mass_init"]),
        ("Post-Cure treatment flush trampoline", MASS_FLUSH_VA, relative_jump(MASS_FLUSH_VA, FLUSH_TRAMPOLINE_VA)),
        ("Living Cure treatment wrapper", LIVE_LOG_WRAPPER_VA, payloads["live_wrapper"]),
        ("Full-corpse treatment wrapper", CORPSE_LOG_WRAPPER_VA, payloads["corpse_wrapper"]),
        ("Single/mass treatment recorder", RECORD_HELPER_VA, payloads["record_helper"]),
        ("Localized treatment-line appender", APPEND_HELPER_VA, payloads["append_helper"]),
        ("Mass treatment-line flush", FLUSH_HELPER_VA, payloads["flush_helper"]),
        ("Original resurrection-flush continuation", FLUSH_TRAMPOLINE_VA, payloads["flush_trampoline"]),
        ("Treatment log format", TREATMENT_FORMAT_VA, payloads["format"]),
    ]
    patched = bytearray(original)
    regions: list[dict[str, Any]] = []
    for label, va, replacement in replacements:
        offset = va_to_offset(pe, va)
        source = original[offset : offset + len(replacement)]
        patched[offset : offset + len(replacement)] = replacement
        regions.append(
            {
                "label": label,
                "va": va,
                "file_offset": offset,
                "length": len(replacement),
                "source_hex": source.hex(" "),
                "release_hex": replacement.hex(" "),
                "rollback_hex": source.hex(" "),
            }
        )
    final = bytes(patched)

    rollback = bytearray(final)
    for region in reversed(regions):
        start = int(region["file_offset"])
        rollback[start : start + int(region["length"])] = bytes.fromhex(region["rollback_hex"])
    if bytes(rollback) != original:
        raise RuntimeError(f"Rollback reconstruction failed for {executable.name}")
    if decode_relative_target(relative_call(LIVING_CURE_CALL_VA, LIVE_LOG_WRAPPER_VA), LIVING_CURE_CALL_VA, "call") != LIVE_LOG_WRAPPER_VA:
        raise RuntimeError("Living wrapper call decode failed")
    if decode_relative_target(relative_call(CORPSE_CALC_CALL_VA, CORPSE_LOG_WRAPPER_VA), CORPSE_CALC_CALL_VA, "call") != CORPSE_LOG_WRAPPER_VA:
        raise RuntimeError("Corpse wrapper call decode failed")
    if decode_relative_target(relative_jump(MASS_FLUSH_VA, FLUSH_TRAMPOLINE_VA), MASS_FLUSH_VA, "jmp") != FLUSH_TRAMPOLINE_VA:
        raise RuntimeError("Flush trampoline jump decode failed")
    pefile.PE(data=final, fast_load=False)
    executable.write_bytes(final)
    return {
        "name": executable.name,
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "logical_patch_regions": regions,
        "exact_contiguous_differences": contiguous_differences(original, final),
        "log_section": section.Name.rstrip(b"\0").decode("ascii"),
        "log_section_rwx": True,
        "rollback_reconstructs_source": True,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 测试说明

适用版本：纯净 Heroes III HotA 1.8.0 中文版 + HD Mod。

安装方法：
1. 准备一份无其他平衡修改的纯净 HotA 1.8.0 游戏目录。
2. 将本压缩包内全部文件直接解压到游戏根目录。
3. 覆盖同名文件。
4. 使用 h3hota HD.exe 启动游戏。

本次测试目标：
- 不修改魔法书显示值。
- 单体治愈：在施法提示后显示目标兵种的治愈值。
- 群体治愈：在施法提示后逐队显示所有有效受疗单位的治愈值。
- 原版复活提示保持原有文案与规则，并排在治愈值之后。
- 日志治愈值格式为“兵种名: +数值”，兵种名沿用当前游戏语言资源。

既有内容保持不变：
- 尤兰德、阿斯特拉：{RELEASE_CURE_TEXT}
- 当前治疗公式、永久复活机制、治愈动画/音效、复活起身动作与复活提示不变。
- 阿斯特拉仍为初级智慧术 + 初级水系魔法。

注意：这是运行时测试候选版，需实机确认启动、单体治愈、群体治愈、纯尸体复活及日志顺序后，方可发布正式 V1.04。
"""


def manifest_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {BUILD_NAME} 构建与静态验收记录",
        "",
        f"- 来源正式版：`{SOURCE_NAME}`",
        f"- 来源 ZIP SHA-256：`{SOURCE_ZIP_SHA256}`",
        f"- 输出 ZIP SHA-256：`{report['zip_sha256']}`",
        "- 魔法书路径未修改。",
        "- 日志顺序：治愈施放提示 → 每个有效单位的治愈值 → 原版复活提示。",
        "- 单体目标立即追加治愈值；群体目标最多缓存 14 队，并在原版治愈施法提示落盘后统一追加。",
        "- 治愈值使用 V1.03 已有 F6 Direct 总量；公式、HotA.dat 与两个 HeroSpec 语言档案逐字节保留。",
        "- 纯静态检查不能证明运行时稳定，本候选版仍需实机验收。",
        "",
        "## EXE 哈希",
        "",
        "| 文件 | SHA-256 |",
        "|---|---|",
    ]
    for executable in report["executables"]:
        lines.append(f"| `{executable['name']}` | `{executable['output_sha256']}` |")
    lines.append("")
    return "\n".join(lines)


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
        raise RuntimeError("Accepted HOTA_NEW_HERO_V1.03 ZIP hash mismatch")

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_files = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    if source_files.get("HotA.dat") != SOURCE_HOTA_DAT_SHA256:
        raise RuntimeError("Unexpected source HotA.dat hash")

    payloads = build_log_payloads()
    executable_reports = [patch_executable(package_root / name, payloads) for name in EXE_NAMES]
    instruction_files = [
        path for path in package_root.iterdir() if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("Expected exactly one root installation text file")
    instruction_files[0].write_text(installation_text(), encoding="utf-8")

    package_files = sorted(item for item in package_root.rglob("*") if item.is_file())
    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path) for path in package_files
    }
    actual_changes = {
        relative for relative, digest in package_hashes.items() if source_files[relative] != digest
    }
    allowed_changes = set(EXE_NAMES) | {instruction_files[0].name}
    if actual_changes != allowed_changes:
        raise RuntimeError(f"Unexpected package changes: {sorted(actual_changes ^ allowed_changes)}")
    if package_hashes["HotA.dat"] != SOURCE_HOTA_DAT_SHA256:
        raise RuntimeError("HotA.dat must be byte-preserved")
    for relative in LANGUAGE_ARCHIVES:
        if package_hashes[relative] != source_files[relative]:
            raise RuntimeError(f"Language archive changed: {relative}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Candidate ZIP failed CRC validation")
        zip_members = sorted(archive.namelist())
    package_members = [path.relative_to(package_root).as_posix() for path in package_files]
    if zip_members != sorted(package_members) or sorted(source_files) != sorted(package_members):
        raise RuntimeError("Candidate package member set changed")

    _, astra_blob_offset, _ = locate_astra_hdat_blob((package_root / "HotA.dat").read_bytes())
    astra_skills = (package_root / "HotA.dat").read_bytes()[
        astra_blob_offset + 0x0C : astra_blob_offset + 0x0C + len(ASTRA_SKILLS_AFTER)
    ]
    if astra_skills != ASTRA_SKILLS_AFTER:
        raise RuntimeError("Astra Basic Wisdom + Basic Water Magic was not preserved")

    report: dict[str, Any] = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "release": False,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "source_file_hashes": source_files,
        "package_file_hashes": package_hashes,
        "changed_package_files": sorted(actual_changes),
        "executables": executable_reports,
        "log_contract": {
            "format": "%s: +%d",
            "creature_name_source": "localized singular creature-name pointer (+0x14)",
            "single_order": ["native Cure cast line", "target Cure total", "native resurrection line(s)"],
            "mass_order": ["native Cure cast line", "all buffered Cure totals", "deferred native resurrection line(s)"],
            "maximum_buffered_stacks": MAX_TREATMENT_RECORDS,
            "magic_book_unchanged": True,
            "native_resurrection_wording_unchanged": True,
        },
        "formula_preserved": {
            "expression": "floor((11L + 10P + 19) * (clamp(n,1,7) + 11) / 12) + 10 * max(0, clamp(w,0,3) - 1)",
            "sample_P1_L1_n1_w1": total_cure(1, 1, 1, 1),
            "sample_P1_L1_n7_w3": total_cure(1, 1, 7, 3),
        },
        "runtime_inheritance": {
            "v103_formula_byte_preserved": True,
            "hota_dat_byte_preserved": True,
            "language_archives_byte_preserved": True,
            "resurrection_capture_body_byte_preserved": True,
            "resurrection_flush_body_after_entry_byte_preserved": True,
        },
        "static_verification": {
            "both_executable_source_hashes_verified": True,
            "all_patch_contexts_verified": True,
            "cave_zero_state_verified": True,
            "cave_runtime_mapped_and_rwx": True,
            "relative_targets_disassembled": True,
            "rollback_reconstructs_sources": True,
            "only_expected_package_files_changed": True,
            "zip_crc_and_member_checks_passed": True,
        },
        "runtime_acceptance": "required; no startup or battle-runtime success is claimed by static checks",
    }
    (output_root / f"{BUILD_NAME}_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / f"{BUILD_NAME}_manifest.md").write_text(
        manifest_markdown(report), encoding="utf-8"
    )
    (output_root / f"{BUILD_NAME}_README.md").write_text(
        installation_text(), encoding="utf-8"
    )

    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    for item in executable_reports:
        print(f"{item['name']}: {item['output_sha256']}")
    print("HotA.dat and both language archives: byte-preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
