#!/usr/bin/env python3
"""Build HOTA_NEW_HERO_V1.02 from the withdrawn V1.01 package.

V1.02 corrects the V1.01 arithmetic interpretation: Uland and Astra use the
requested total-Cure formula directly at every Water Magic mastery. Water Magic
continues to control only the native single-target/mass-target cast behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
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
    HERO_SPEC_ENTRY,
    LANGUAGE_ARCHIVES,
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)
from build_hota_new_hero_v101 import (
    build_formula_payloads as build_v101_formula_payloads,
)
from extract_lod import parse_entries, payload


RELEASE_NAME = "HOTA_NEW_HERO_V1.02"
SOURCE_NAME = "HOTA_NEW_HERO_V1.01"
SOURCE_ZIP_SHA256 = "8962665d3bd4e4f7dc686b9c3cae137262856e698d6e6b25479efd1b2a200d1d"

RELEASE_CURE_TEXT = (
    "治愈术的效果随英雄等级和目标生物等级提升，并可永久复活己方阵亡单位。"
)
RELEASE_CURE_TEXT_EN = (
    "Cure becomes more effective with the hero's level and the target creature's "
    "level, and can permanently resurrect fallen friendly units."
)

IMAGE_BASE = 0x00400000
NATIVE_CURE_SPECIALTY_BONUS_VA = 0x004E6260
CURE_SPECIALTY_CALL_VA = 0x00446326
CORPSE_CURE_CALC_VA = 0x00639D80
DISPATCH_VA = 0x0065DE00
BONUS_CALC_VA = 0x0065DE40

ASTRA_STARTING_SKILLS_OFFSET = 0x0027D07C
ASTRA_STARTING_SKILLS_VA = 0x0067D07C
ASTRA_STARTING_SKILLS = bytes.fromhex(
    "01 00 00 00 07 00 00 00 10 00 00 00"
)
PACKAGE_HOTA_DAT_SHA256 = "5075795db5878b16c14dd7e438c30a68faa3fb27135815c6237d12099d3fe45b"


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


def build_formula_payloads() -> tuple[bytes, bytes, bytes, dict[str, Any]]:
    bonus_source = """
specialist_cure_total:
    push ebp
    mov ebp, esp
    push esi
    mov eax, dword ptr [ebp + 0x0c]
    imul esi, eax, 10
    add esi, 30
    imul eax, eax, 20
    add eax, 60
    mov ecx, dword ptr [ebp + 0x10]
    movsx ecx, word ptr [ecx + 0x55]
    lea edx, [ecx + ecx * 2]
    sub edx, 3
    imul eax, edx
    lea edx, [ecx + ecx * 2]
    add edx, 9
    mov ecx, dword ptr [ebp + 0x08]
    add edx, dword ptr [ecx + 0x78]
    mov ecx, edx
    cdq
    idiv ecx
    add eax, esi
    pop esi
    mov esp, ebp
    pop ebp
    ret 0x0c
"""
    dispatch_source = f"""
cure_specialty_dispatch:
    mov eax, dword ptr [ecx + 0x1a]
    cmp eax, 0x19
    je use_new_formula
    cmp eax, 0xaa
    je use_new_formula
    jmp {NATIVE_CURE_SPECIALTY_BONUS_VA:#x}
use_new_formula:
    push ecx
    push dword ptr [ebp + 0x0c]
    push esi
    call {BONUS_CALC_VA:#x}
    sub eax, edi
    ret 0x0c
"""
    corpse_calc_source = f"""
calc_cure_power:
    push ebp
    mov ebp, esp
    push dword ptr [ebp + 0x14]
    push dword ptr [ebp + 0x10]
    push dword ptr [ebp + 0x08]
    mov eax, {BONUS_CALC_VA:#x}
    call eax
    mov esp, ebp
    pop ebp
    ret 0x10
"""

    bonus = assemble(bonus_source, BONUS_CALC_VA)
    dispatch = assemble(dispatch_source, DISPATCH_VA)
    corpse_calc = assemble(corpse_calc_source, CORPSE_CURE_CALC_VA)
    if DISPATCH_VA + len(dispatch) > BONUS_CALC_VA:
        raise RuntimeError("Formula dispatcher overlaps the bonus calculator")
    _, _, v101_corpse_calc, _ = build_v101_formula_payloads()
    if len(corpse_calc) > len(v101_corpse_calc):
        raise RuntimeError("New corpse Cure calculator exceeds its accepted code region")
    corpse_calc_padded = corpse_calc.ljust(len(v101_corpse_calc), b"\x90")
    metadata = {
        "all_masteries_total_formula": (
            "H = 10P + 30 + floor((20P + 60) * 3(L - 1) / (3L + 16 - n))"
        ),
        "rounding": "positive x86 integer division (floor)",
        "target_tier_relation": "[combatStack+0x78] = 7 - n",
        "mastery_behavior": {
            "numeric_effect": "all Water Magic mastery levels use exact H",
            "targeting_effect": "native Water Magic rules alone choose single-target or mass Cure",
        },
        "living_path_compensation": (
            "dispatcher returns H minus the already-loaded native Cure base; "
            "CureCore then adds that native base and finishes at exactly H"
        ),
        "components": [
            {
                "name": "cure_specialty_dispatch",
                "va": DISPATCH_VA,
                "size": len(dispatch),
                "assembly": dispatch_source.strip(),
            },
            {
                "name": "specialist_cure_total",
                "va": BONUS_CALC_VA,
                "size": len(bonus),
                "assembly": bonus_source.strip(),
            },
            {
                "name": "corpse_cure_total",
                "va": CORPSE_CURE_CALC_VA,
                "size": len(corpse_calc),
                "padded_size": len(corpse_calc_padded),
                "assembly": corpse_calc_source.strip(),
            },
        ],
    }
    return dispatch, bonus, corpse_calc_padded, metadata


def total_cure(power: int, hero_level: int, creature_tier: int) -> int:
    return 10 * power + 30 + ((20 * power + 60) * 3 * (hero_level - 1)) // (
        3 * hero_level + 16 - creature_tier
    )


def patch_executable(
    executable: Path,
    dispatch: bytes,
    bonus: bytes,
    corpse_calc: bytes,
) -> dict[str, Any]:
    original = executable.read_bytes()
    old_dispatch, old_bonus, old_corpse_calc, _ = build_v101_formula_payloads()
    old_call = relative_call(CURE_SPECIALTY_CALL_VA, DISPATCH_VA)
    dispatch_region_length = max(len(old_dispatch), len(dispatch))
    bonus_region_length = max(len(old_bonus), len(bonus))
    expected_dispatch = old_dispatch.ljust(dispatch_region_length, b"\x00")
    expected_bonus = old_bonus.ljust(bonus_region_length, b"\x00")
    replacement_dispatch = dispatch.ljust(dispatch_region_length, b"\x00")
    replacement_bonus = bonus.ljust(bonus_region_length, b"\x00")
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != IMAGE_BASE:
        raise RuntimeError(f"Unexpected image base in {executable.name}")
    if pe.OPTIONAL_HEADER.DllCharacteristics & 0x40:
        raise RuntimeError(f"Unexpected ASLR in {executable.name}")
    if (
        original[
            ASTRA_STARTING_SKILLS_OFFSET :
            ASTRA_STARTING_SKILLS_OFFSET + len(ASTRA_STARTING_SKILLS)
        ]
        != ASTRA_STARTING_SKILLS
    ):
        raise RuntimeError(
            f"Astra starting-skill record changed in {executable.name}"
        )

    context_offset = va_to_offset(pe, CURE_SPECIALTY_CALL_VA - 7)
    expected_context = bytes.fromhex("8B 46 78 57 50 6A 25") + old_call + bytes.fromhex("03 F8")
    if original[context_offset : context_offset + len(expected_context)] != expected_context:
        raise RuntimeError(f"Cure specialty call context changed in {executable.name}")

    call_offset = va_to_offset(pe, CURE_SPECIALTY_CALL_VA)
    calc_offset = va_to_offset(pe, CORPSE_CURE_CALC_VA)
    dispatch_offset = va_to_offset(pe, DISPATCH_VA)
    bonus_offset = va_to_offset(pe, BONUS_CALC_VA)
    if original[call_offset : call_offset + 5] != old_call:
        raise RuntimeError(f"V1.01 Cure specialty call changed in {executable.name}")
    if (
        original[calc_offset : calc_offset + len(old_corpse_calc)]
        != old_corpse_calc
    ):
        raise RuntimeError(f"V1.01 corpse Cure calculator changed in {executable.name}")
    if original[dispatch_offset : dispatch_offset + dispatch_region_length] != expected_dispatch:
        raise RuntimeError(f"V1.01 dispatcher changed in {executable.name}")
    if original[bonus_offset : bonus_offset + bonus_region_length] != expected_bonus:
        raise RuntimeError(f"V1.01 formula calculator changed in {executable.name}")

    formula_end_rva = BONUS_CALC_VA + len(bonus) - IMAGE_BASE
    formula_section = next(
        section
        for section in pe.sections
        if section.VirtualAddress <= DISPATCH_VA - IMAGE_BASE
        < section.VirtualAddress + max(section.Misc_VirtualSize, section.SizeOfRawData)
    )
    if formula_end_rva > formula_section.VirtualAddress + formula_section.Misc_VirtualSize:
        raise RuntimeError(f"Formula cave is not mapped at runtime in {executable.name}")
    if formula_section.Characteristics & 0xE0000000 != 0xE0000000:
        raise RuntimeError(f"Formula cave section is not RWX in {executable.name}")

    new_call = relative_call(CURE_SPECIALTY_CALL_VA, DISPATCH_VA)
    patched = bytearray(original)
    patched[call_offset : call_offset + 5] = new_call
    patched[calc_offset : calc_offset + len(corpse_calc)] = corpse_calc
    patched[dispatch_offset : dispatch_offset + dispatch_region_length] = replacement_dispatch
    patched[bonus_offset : bonus_offset + bonus_region_length] = replacement_bonus
    final = bytes(patched)

    regions = [
        {
            "label": "Full-corpse Cure total calculator",
            "va": CORPSE_CURE_CALC_VA,
            "file_offset": calc_offset,
            "length": len(corpse_calc),
            "source_hex": old_corpse_calc.hex(" "),
            "release_hex": corpse_calc.hex(" "),
            "rollback_hex": old_corpse_calc.hex(" "),
        },
        {
            "label": "Uland/Astra Cure specialty dispatcher",
            "va": DISPATCH_VA,
            "file_offset": dispatch_offset,
            "length": dispatch_region_length,
            "source_hex": expected_dispatch.hex(" "),
            "release_hex": replacement_dispatch.hex(" "),
            "rollback_hex": expected_dispatch.hex(" "),
        },
        {
            "label": "Uland/Astra total Cure formula",
            "va": BONUS_CALC_VA,
            "file_offset": bonus_offset,
            "length": bonus_region_length,
            "source_hex": expected_bonus.hex(" "),
            "release_hex": replacement_bonus.hex(" "),
            "rollback_hex": expected_bonus.hex(" "),
        },
    ]

    rollback = bytearray(final)
    for region in regions:
        start = region["file_offset"]
        rollback[start : start + region["length"]] = bytes.fromhex(
            region["rollback_hex"]
        )
    if bytes(rollback) != original:
        raise RuntimeError(f"Rollback reconstruction failed for {executable.name}")

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    call_instruction = next(decoder.disasm(new_call, CURE_SPECIALTY_CALL_VA))
    if (
        call_instruction.mnemonic != "call"
        or call_instruction.operands[0].type != X86_OP_IMM
        or call_instruction.operands[0].imm != DISPATCH_VA
    ):
        raise RuntimeError(f"Formula call decode failed for {executable.name}")
    pefile.PE(data=final, fast_load=False)
    executable.write_bytes(final)
    return {
        "name": executable.name,
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "logical_patch_regions": regions,
        "exact_contiguous_differences": contiguous_differences(original, final),
        "formula_section": formula_section.Name.rstrip(b"\0").decode("ascii"),
        "formula_section_rwx": True,
        "astra_starting_skills_bytes_preserved": True,
        "rollback_reconstructs_source": True,
    }


def verify_hero_spec(archive_path: Path, archive_relative: str) -> dict[str, Any]:
    archive = archive_path.read_bytes()
    entries = parse_entries(archive)
    matches = [
        item for item in entries if str(item["name"]).lower() == HERO_SPEC_ENTRY.lower()
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {HERO_SPEC_ENTRY} in {archive_relative}")
    member = payload(archive, matches[0])
    release = RELEASE_CURE_TEXT.encode("gb18030")
    if member.count(release) != 1:
        raise RuntimeError(f"Expected concise Cure text once in {archive_relative}")
    return {
        "archive": archive_relative,
        "entry": HERO_SPEC_ENTRY,
        "encoding": "gb18030",
        "archive_sha256": sha256_bytes(archive),
        "cure_text": RELEASE_CURE_TEXT,
        "archive_preserved_byte_for_byte": True,
    }


def installation_text() -> str:
    return f"""{RELEASE_NAME} 安装说明

适用版本：纯净 Heroes III HotA 1.8.0 中文版 + HD Mod。

安装方法：
1. 准备一份无其他平衡修改的纯净 HotA 1.8.0 游戏目录。
2. 将本压缩包内全部文件直接解压到游戏根目录。
3. 覆盖同名文件。
4. 使用 h3hota HD.exe 启动游戏。

英雄修改：
- 埃尔芙：仙灵和妖精杀伤力 +1、速度 +1；初始兵力为 25 / 25 / 25 仙灵。
- 尤兰德、阿斯特拉：{RELEASE_CURE_TEXT}
- 阿斯特拉的初始技能为初级智慧术和初级水系魔法。
- 尤兰德、阿斯特拉的最终治疗量直接使用指定公式；水系等级只决定单体或群体施放，不改变治疗数值。

治愈复活演出：
- 保留原版治愈动画、治愈音效和复活单位的起身动作。
- 不播放转世重生圆圈和转世重生音效。
- 战斗日志先显示治愈施法，再显示各队复活记录。
"""


def release_readme(report: dict[str, Any]) -> str:
    return f"""# {RELEASE_NAME}

适用于 HotA 1.8.0 中文版与 HD Mod。

## 英雄修改

- 埃尔芙：仙灵和妖精杀伤力 +1、速度 +1；初始兵力为 25 / 25 / 25 仙灵。
- 尤兰德、阿斯特拉：{RELEASE_CURE_TEXT}
- 阿斯特拉：初级智慧术 / 初级水系魔法。
- 两名治愈特英雄在所有水系等级下均直接使用同一治疗总量公式；水系等级只决定单体或群体施放。

## 安装

将 `{RELEASE_NAME}.zip` 解压至干净的 HotA 1.8.0 游戏根目录并覆盖同名文件。

## 校验

```text
SHA-256 {report['zip_sha256']}
```
"""


def manifest_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {RELEASE_NAME} 构建与验收记录",
        "",
        f"- 来源正式版：`{SOURCE_NAME}`",
        f"- 来源 ZIP SHA-256：`{SOURCE_ZIP_SHA256}`",
        f"- 输出 ZIP SHA-256：`{report['zip_sha256']}`",
        "- 所有水系等级的最终治疗量均直接采用：`H = 10P + 30 + floor((20P + 60) × 3(L - 1) / (3L + 16 - n))`。",
        "- `P=1、L=1` 时，无论水系等级与目标兵种等级，最终治疗量均为 `40`。",
        "- 水系等级只沿用原版的单体/群体施法范围规则，不再改变这两名英雄的治疗数值。",
        "- 活体治疗、治疗溢出复活和全灭尸体复活统一使用同一个最终总量公式。",
        "- 两个 EXE 的阿斯特拉初始技能记录保持 `01 / 07 / 16`，即初级智慧术 + 初级水系魔法。",
        "- 既有治愈复活动画、音效、永久性、资格限制和战斗日志顺序均原样保留。",
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
        raise RuntimeError("Accepted HOTA_NEW_HERO_V1.01 ZIP hash mismatch")

    package_root = build_root / RELEASE_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_files = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    if source_files.get("HotA.dat") != PACKAGE_HOTA_DAT_SHA256:
        raise RuntimeError("Unexpected source HotA.dat hash")

    dispatch, bonus, corpse_calc, formula_metadata = build_formula_payloads()
    executable_reports = [
        patch_executable(package_root / name, dispatch, bonus, corpse_calc)
        for name in EXE_NAMES
    ]
    text_reports = [
        verify_hero_spec(package_root / relative, relative)
        for relative in LANGUAGE_ARCHIVES
    ]
    instruction_files = [
        path for path in package_root.iterdir() if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("Expected exactly one root installation text file")
    instruction_files[0].write_text(installation_text(), encoding="utf-8")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{RELEASE_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Release ZIP failed CRC validation")
        zip_members = sorted(archive.namelist())
    package_files = sorted(item for item in package_root.rglob("*") if item.is_file())
    package_members = [path.relative_to(package_root).as_posix() for path in package_files]
    if zip_members != sorted(package_members) or sorted(source_files) != sorted(package_members):
        raise RuntimeError("Release package member set changed")

    allowed_changes = set(EXE_NAMES) | {instruction_files[0].name}
    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path) for path in package_files
    }
    actual_changes = {
        relative for relative, digest in package_hashes.items() if source_files[relative] != digest
    }
    if actual_changes != allowed_changes:
        raise RuntimeError(f"Unexpected package changes: {sorted(actual_changes ^ allowed_changes)}")
    if package_hashes["HotA.dat"] != PACKAGE_HOTA_DAT_SHA256:
        raise RuntimeError("HotA.dat changed during build")

    formula_samples = []
    for power, level, tier in ((1, 1, 1), (1, 1, 7), (1, 10, 1), (1, 10, 7), (10, 10, 7)):
        formula_samples.append(
            {
                "power": power,
                "hero_level": level,
                "creature_tier": tier,
                "all_water_masteries": total_cure(power, level, tier),
            }
        )

    report: dict[str, Any] = {
        "schema_version": 1,
        "build_name": RELEASE_NAME,
        "release": True,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "source_file_hashes": source_files,
        "package_file_hashes": package_hashes,
        "changed_package_files": sorted(actual_changes),
        "executables": executable_reports,
        "text_updates": text_reports,
        "formula": formula_metadata,
        "formula_samples": formula_samples,
        "astra_starting_skills": {
            "skills": ["Basic Wisdom", "Basic Water Magic"],
            "exe_file_offset": f"0x{ASTRA_STARTING_SKILLS_OFFSET:08X}",
            "va": f"0x{ASTRA_STARTING_SKILLS_VA:08X}",
            "bytes": ASTRA_STARTING_SKILLS.hex(" "),
            "preserved_in_both_executables": True,
        },
        "runtime_inheritance": {
            "cure_resurrection_logic_from_runtime_accepted_v1": True,
            "cure_visual_and_sound_isolation_unchanged": True,
            "combat_log_ordering_unchanged": True,
            "elf_specialty_logic_unchanged": True,
            "ordinary_resurrection_unchanged": True,
        },
        "static_verification": {
            "both_executable_call_contexts_verified": True,
            "living_and_corpse_paths_finish_at_same_total_formula": True,
            "non_specialists_tail_call_native_bonus": True,
            "v101_formula_regions_matched_before_replacement": True,
            "formula_cave_runtime_mapped_and_rwx": True,
            "both_hero_spec_entries_preserved_and_verified": True,
            "astra_starting_skill_bytes_preserved": True,
            "hota_dat_preserved": True,
            "only_expected_package_files_changed": True,
            "release_zip_crc_test_passed": True,
        },
        "runtime_acceptance": "required for new arithmetic; not claimed by static checks",
    }
    (output_root / f"{RELEASE_NAME}_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / f"{RELEASE_NAME}_manifest.md").write_text(
        manifest_markdown(report), encoding="utf-8"
    )
    (output_root / f"{RELEASE_NAME}_README.md").write_text(
        release_readme(report), encoding="utf-8"
    )

    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    for item in executable_reports:
        print(f"{item['name']}: {item['output_sha256']}")
    for item in text_reports:
        print(f"{item['archive']}: {item['archive_sha256']} (preserved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
