#!/usr/bin/env python3
"""Build formal HOTA_NEW_HERO_V1.05 from accepted V1.04.

V1.05 changes only the Cure total used by Uland and Astra, plus the matching
specialty-detail calculator embedded in both fixed-base executable variants.
All resurrection, visual, sound, logging, text-resource, HotA.dat, and HotA.dll
payloads are inherited byte-for-byte from V1.04.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import pefile

from build_hota_new_hero_v1 import (
    EXE_NAMES,
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)
from build_hota_new_hero_v103 import BONUS_CALC_VA, IMAGE_BASE
from build_hota_new_hero_v104 import (
    HOTA_CURE_SPELL_ID,
    HOTA_HERO_PRIMARY_VA,
    HOTA_NATIVE_SPECIALTY_VA,
    HOTA_SPECIAL_TERRAIN_VA,
    HOTA_SPELL_EXPERTISE_VA,
    HOTA_UI_HELPER_VA,
    assemble,
    build_corrected_formula_bonus as build_f6_formula_bonus,
    build_hota_ui_helper as build_f6_ui_helper,
    contiguous_differences,
    va_to_offset,
)


BUILD_NAME = "HOTA_NEW_HERO_V1.05"
SOURCE_NAME = "HOTA_NEW_HERO_V1.04"
SOURCE_ZIP_SHA256 = "60a2744a00e4759d4115c3e51c1aa434ae93d6324949349a923ab50931b0e7ad"

SOURCE_EXE_SHA256 = {
    "h3hota.exe": "aa7933be741576df85dc421c9fc6cef14a213df67c4a191d011e8f9692da96e0",
    "h3hota HD.exe": "91ffc17974091e0f7c1f3ac5fd95bd3259167f3621eecaee64b6da68062e318c",
}

FORMULA_EXPRESSION = (
    "floor(((11L + 29) * (clamp(n,1,7) + 11)) / 12) "
    "+ 5 * (P - 1) + 10 * max(0, clamp(w,0,3) - 1)"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def total_cure(level: int, power: int, tier: int, water: int) -> int:
    """Return the F7 NativePower Cure total using integer arithmetic only."""

    level = max(int(level), 1)
    power = max(int(power), 0)
    tier = min(max(int(tier), 1), 7)
    water = min(max(int(water), 0), 3)
    return (
        ((11 * level + 29) * (tier + 11)) // 12
        + 5 * (power - 1)
        + 10 * max(0, water - 1)
    )


def build_f7_formula_bonus() -> tuple[bytes, dict[str, Any]]:
    """Build the gameplay calculator in the accepted 80-byte helper region."""

    f6_payload, _ = build_f6_formula_bonus()
    source = """
        push ebp
        mov ebp, esp
        push esi
        mov eax, dword ptr [ebp + 0x10]
        movsx eax, word ptr [eax + 0x55]
        imul eax, eax, 0x0b
        add eax, 0x1d
        mov edx, dword ptr [ebp + 0x08]
        mov esi, dword ptr [edx + 0x78]
        inc esi
        cmp esi, 1
        jge tier_min_ok
        mov esi, 1
    tier_min_ok:
        cmp esi, 7
        jle tier_max_ok
        mov esi, 7
    tier_max_ok:
        add esi, 0x0b
        imul eax, esi
        cdq
        mov ecx, 0x0c
        idiv ecx
        mov ecx, dword ptr [ebp + 0x0c]
        dec ecx
        imul ecx, ecx, 5
        add eax, ecx
        add eax, dword ptr [ebp + 0x14]
        pop esi
        mov esp, ebp
        pop ebp
        ret 0x10
    """
    payload = assemble(source, BONUS_CALC_VA)
    if len(payload) > len(f6_payload):
        raise RuntimeError("F7 gameplay helper exceeds the accepted 80-byte region")
    padded = payload.ljust(len(f6_payload), b"\x90")
    return padded, {
        "assembly": source.strip(),
        "source_size": len(f6_payload),
        "payload_size": len(payload),
        "padded_size": len(padded),
        "hero_level_source": "signed word at hero+0x55; live heroes are level >= 1",
        "spell_power_source": "effective Cure power argument; runtime domain is non-negative",
        "target_tier_source": "combatStack.info.level at +0x78 (0..6), converted with +1",
        "water_bonus_source": "existing dispatcher argument: 10 * max(0, clamp(w,0,3) - 1)",
    }


def build_f7_ui_helper() -> tuple[bytes, str]:
    """Build the HotA specialty-panel dispatcher using the same F7 formula."""

    source = f"""
    mov eax, dword ptr [ecx + 0x1a]
    cmp eax, 0x19
    je specialist
    cmp eax, 0xaa
    je specialist
native:
    mov eax, {HOTA_NATIVE_SPECIALTY_VA:#x}
    jmp eax
specialist:
    cmp dword ptr [esp + 0x04], {HOTA_CURE_SPELL_ID}
    jne native
    push ebp
    mov ebp, esp
    sub esp, 0x08
    push ebx
    push esi
    push edi
    mov esi, ecx
    push 2
    mov eax, {HOTA_HERO_PRIMARY_VA:#x}
    call eax
    mov dword ptr [ebp - 0x04], eax
    movsx eax, word ptr [esi + 0x55]
    imul eax, eax, 11
    add eax, 29
    mov edi, dword ptr [ebp + 0x0c]
    inc edi
    cmp edi, 1
    jge tier_min_ok
    mov edi, 1
tier_min_ok:
    cmp edi, 7
    jle tier_max_ok
    mov edi, 7
tier_max_ok:
    add edi, 11
    imul eax, edi
    cdq
    mov ebx, 12
    idiv ebx
    mov edi, eax
    mov ecx, dword ptr [ebp - 0x04]
    dec ecx
    imul ecx, ecx, 5
    add edi, ecx
    mov ecx, esi
    mov eax, {HOTA_SPECIAL_TERRAIN_VA:#x}
    call eax
    push eax
    push {HOTA_CURE_SPELL_ID}
    mov ecx, esi
    mov eax, {HOTA_SPELL_EXPERTISE_VA:#x}
    call eax
    cmp eax, 1
    jle water_ready
    sub eax, 1
    cmp eax, 2
    jle water_capped
    mov eax, 2
water_capped:
    imul eax, eax, 10
    add edi, eax
water_ready:
    mov eax, edi
    cmp dword ptr [ebp + 0x10], 100
    je percentage
    sub eax, dword ptr [ebp + 0x10]
    jmp finished
percentage:
    mov ecx, dword ptr [ebp - 0x04]
    lea ecx, [ecx + ecx * 4 + 30]
    sub eax, ecx
    imul eax, eax, 100
    cdq
    idiv ecx
finished:
    pop edi
    pop esi
    pop ebx
    mov esp, ebp
    pop ebp
    ret 0x0c
    """
    return assemble(source, HOTA_UI_HELPER_VA), source.strip()


def patch_executable(path: Path) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_EXE_SHA256[path.name]:
        raise RuntimeError(f"Unexpected {SOURCE_NAME} source hash for {path.name}")
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != IMAGE_BASE:
        raise RuntimeError(f"Unexpected image base in {path.name}")
    if pe.OPTIONAL_HEADER.DllCharacteristics & 0x40:
        raise RuntimeError(f"Unexpected ASLR in {path.name}")

    f6_formula, _ = build_f6_formula_bonus()
    f7_formula, formula_metadata = build_f7_formula_bonus()
    f6_ui, _ = build_f6_ui_helper()
    f7_ui, ui_source = build_f7_ui_helper()
    f6_ui_region = f6_ui.ljust(len(f7_ui), b"\x00")

    replacements = [
        ("F7 NativePower gameplay Cure calculator", BONUS_CALC_VA, f6_formula, f7_formula),
        ("F7 NativePower specialty-panel calculator", HOTA_UI_HELPER_VA, f6_ui_region, f7_ui),
    ]
    patched = bytearray(original)
    regions: list[dict[str, Any]] = []
    for label, va, expected, replacement in replacements:
        offset = va_to_offset(pe, va)
        if original[offset : offset + len(expected)] != expected:
            raise RuntimeError(f"{label} source mismatch in {path.name}")
        patched[offset : offset + len(replacement)] = replacement
        regions.append({
            "label": label,
            "va": va,
            "file_offset": offset,
            "length": len(replacement),
            "source_hex": expected.hex(" "),
            "release_hex": replacement.hex(" "),
            "rollback_hex": expected.hex(" "),
        })

    section = next(
        item for item in pe.sections
        if item.VirtualAddress <= HOTA_UI_HELPER_VA - IMAGE_BASE
        < item.VirtualAddress + max(item.Misc_VirtualSize, item.SizeOfRawData)
    )
    mapped_end = IMAGE_BASE + section.VirtualAddress + max(
        section.Misc_VirtualSize, section.SizeOfRawData
    )
    if HOTA_UI_HELPER_VA + len(f7_ui) > mapped_end:
        raise RuntimeError(f"F7 UI helper is not fully mapped in {path.name}")
    if section.Characteristics & 0xE0000000 != 0xE0000000:
        raise RuntimeError(f"F7 helper section is not RWX in {path.name}")

    final = bytes(patched)
    rollback = bytearray(final)
    for region in reversed(regions):
        start = int(region["file_offset"])
        rollback[start : start + int(region["length"])] = bytes.fromhex(region["rollback_hex"])
    if bytes(rollback) != original:
        raise RuntimeError(f"Rollback reconstruction failed for {path.name}")
    pefile.PE(data=final, fast_load=False)
    path.write_bytes(final)
    return {
        "name": path.name,
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "logical_patch_regions": regions,
        "exact_contiguous_differences": contiguous_differences(original, final),
        "formula_metadata": formula_metadata,
        "ui_helper_assembly": ui_source,
        "helper_section": section.Name.rstrip(b"\0").decode("ascii"),
        "helper_section_rwx": True,
        "rollback_reconstructs_source": True,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与功能说明

适用版本：纯净 Heroes III HotA 1.8.0 中文版 + HD Mod。

安装方法：
1. 准备一份无其他平衡修改的纯净 HotA 1.8.0 游戏目录。
2. 将本压缩包内全部文件直接解压到游戏根目录。
3. 覆盖同名文件。
4. 使用 h3hota HD.exe 启动游戏。

本版更新：
- 尤兰德、阿斯特拉的治愈总量改用 F7 NativePower 公式：
  H = floor(((11L + 29) × (n + 11)) / 12) + 5 × (P - 1) + 10 × max(0, w - 1)
- L 为英雄等级（最低 1），P 为当前有效力量（最低 0），n 为目标生物等级（限定 1–7），w 为水系魔法熟练度（无/初级/中级/高级分别为 0/1/2/3）。
- 全部运算使用整数；主乘积先除以 12 并向下取整，再叠加力量项与水系项。
- 同步更新两套启动 EXE 的实际治疗/复活数值和英雄特长详情表。
- 参考值：L=1、P=1、无/初级水系时，1–7级生物的治疗量依次为 40/43/46/50/53/56/60。

保持不变：
- 单体/群体施法范围、永久复活、目标资格、治愈动画与音效、复活起身动作及提示顺序。
- 战斗日志继续逐队显示“兵种名获得数值点治疗。”，并在其后显示原版复活提示。
- 魔法书显示值不修改。
- 阿斯特拉仍为初级智慧术 + 初级水系魔法。
- HotA.dll、HotA.dat、双语言 LOD、HeroSpec.txt 与其余资源均逐字节继承 V1.04。

本包已完成双入口静态一致性、精确字节回滚、公式样例、ZIP CRC 和可复现构建检查；V1.05 新数值仍建议在新开地图中做一次实机冒烟测试。
"""


def manifest_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {BUILD_NAME} 构建与静态验收记录",
        "",
        f"- 来源正式版：`{SOURCE_NAME}`",
        f"- 来源 ZIP SHA-256：`{SOURCE_ZIP_SHA256}`",
        f"- 输出 ZIP SHA-256：`{report['zip_sha256']}`",
        f"- 公式：`{FORMULA_EXPRESSION}`",
        "- 仅两套 EXE 的实际治疗计算器、特长详情计算器及根目录安装说明发生变化。",
        "- V1.04 的复活、动画、音效、日志、HotA.dll、HotA.dat 与资源文件逐字节保留。",
        "",
        "| 文件 | SHA-256 |",
        "|---|---|",
    ]
    for item in report["executables"]:
        lines.append(f"| `{item['name']}` | `{item['output_sha256']}` |")
    lines.extend(["", "运行时状态：V1.05 新公式尚待用户实机冒烟；其余继承功能已在 V1.04 通过。", ""])
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
        raise RuntimeError(f"Accepted {SOURCE_NAME} ZIP hash mismatch")

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_files = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }

    executable_reports = [patch_executable(package_root / name) for name in EXE_NAMES]
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
    actual_changes = {
        relative for relative, digest in package_hashes.items()
        if source_files.get(relative) != digest
    }
    allowed_changes = set(EXE_NAMES) | {instruction_files[0].name}
    if actual_changes != allowed_changes:
        raise RuntimeError(f"Unexpected package changes: {sorted(actual_changes ^ allowed_changes)}")
    for relative, digest in source_files.items():
        if relative not in allowed_changes and package_hashes.get(relative) != digest:
            raise RuntimeError(f"Inherited V1.04 file changed: {relative}")

    samples = [
        {"L": 1, "P": 1, "w": 1, "tiers_1_to_7": [total_cure(1, 1, n, 1) for n in range(1, 8)]},
        {"L": 5, "P": 1, "w": 1, "tiers_1_to_7": [total_cure(5, 1, n, 1) for n in range(1, 8)]},
        {"L": 2, "P": 4, "w": 2, "tiers_1_to_7": [total_cure(2, 4, n, 2) for n in range(1, 8)]},
        {"L": 5, "P": 4, "w": 3, "tiers_1_to_7": [total_cure(5, 4, n, 3) for n in range(1, 8)]},
        {"L": 10, "P": 5, "w": 1, "tiers_1_to_7": [total_cure(10, 5, n, 1) for n in range(1, 8)]},
        {"L": 20, "P": 10, "w": 3, "tiers_1_to_7": [total_cure(20, 10, n, 3) for n in range(1, 8)]},
        {"L": 30, "P": 25, "w": 3, "tiers_1_to_7": [total_cure(30, 25, n, 3) for n in range(1, 8)]},
    ]
    expected_samples = [
        [40, 43, 46, 50, 53, 56, 60],
        [84, 91, 98, 105, 112, 119, 126],
        [76, 80, 84, 88, 93, 97, 101],
        [119, 126, 133, 140, 147, 154, 161],
        [159, 170, 182, 193, 205, 216, 228],
        [314, 334, 355, 376, 397, 417, 438],
        [499, 528, 558, 588, 618, 648, 678],
    ]
    if [item["tiers_1_to_7"] for item in samples] != expected_samples:
        raise RuntimeError("F7 formula sample table mismatch")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Candidate ZIP failed CRC validation")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("Candidate ZIP member set changed")

    report: dict[str, Any] = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
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
        "formula": {
            "name": "F7 NativePower",
            "expression": FORMULA_EXPRESSION,
            "integer_arithmetic": True,
            "samples": samples,
            "per_power_increment": 5,
            "advanced_water_increment_over_basic": 10,
            "expert_water_increment_over_basic": 20,
        },
        "byte_preserved_from_v104": [
            relative for relative in sorted(package_hashes) if relative not in actual_changes
        ],
        "static_verification": {
            "both_executable_source_hashes_verified": True,
            "f6_source_payloads_verified": True,
            "f7_gameplay_and_ui_formulas_assembled": True,
            "both_executables_receive_identical_logical_payloads": True,
            "helper_runtime_mapped_and_rwx": True,
            "rollback_reconstructs_v104_sources": True,
            "only_expected_package_files_changed": True,
            "formula_samples_match_f7_instruction": True,
            "zip_crc_and_member_checks_passed": True,
        },
        "runtime_acceptance": {
            "status": "pending V1.05 smoke test",
            "inherited_from_v104": [
                "single and mass Cure",
                "living and fully-dead friendly stacks",
                "per-stack treatment totals and log order",
                "permanent resurrection behavior",
                "Cure-only audio and resurrection stand-up animation",
                "Astra Basic Wisdom + Basic Water Magic",
            ],
        },
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
    print("F7 formula samples: PASS")
    print("Inherited V1.04 non-formula payloads: byte-preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
