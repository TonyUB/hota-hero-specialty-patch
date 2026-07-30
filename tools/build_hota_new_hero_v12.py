#!/usr/bin/env python3
"""Build formal HOTA_NEW_HERO_V1.2 with the accepted Scholar specialty."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
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
from build_hota_new_hero_v104 import contiguous_differences
import build_hota_new_hero_v12_scholar_diag01 as diag01
import build_hota_new_hero_v12_scholar_diag02 as diag02
import build_hota_new_hero_v12_scholar_test01 as test01
import build_hota_new_hero_v12_scholar_test02 as test02
import build_hota_new_hero_v12_scholar_test04 as test04


BUILD_NAME = "HOTA_NEW_HERO_V1.2"
SOURCE_NAME = "HOTA_NEW_HERO_V1.14"
SOURCE_ZIP_SHA256 = diag02.SOURCE_ZIP_SHA256
SOURCE_EXE_SHA256 = diag02.SOURCE_EXE_SHA256
FORMULA_EXPRESSION = (
    "floor(((11L + 29) * (clamp(n,1,7) + 11)) / 12) "
    "+ 5 * (P - 1) + 10 * max(0, clamp(w,0,3) - 1)"
)
SOURCE_INSTALLATION_SHA256 = (
    "b292d1908dea251767aa567e84f6702714fa58cd1133ffdf10cb7c31ab33e3c1"
)

CORONIUS_ID = diag01.CORONIUS_ID
CORONIUS_RECORD_OFFSET = test02.CORONIUS_RECORD_OFFSET
CORONIUS_RECORD_SIZE = test02.CORONIUS_RECORD_SIZE
CORONIUS_RECORD_SHA256 = test02.CORONIUS_RECORD_SHA256
STARTING_SPELL_OFFSET = test02.STARTING_SPELL_OFFSET
SLAYER_SPELL_ID = test02.OLD_STARTING_SPELL


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def build_feature_components() -> tuple[list[dict[str, Any]], dict[int, bytes]]:
    reports: list[dict[str, Any]] = []
    components: dict[int, bytes] = {}
    for name, va, limit, source in test01.feature_sources():
        code = diag01.assemble(source, va)
        if va < diag02.LUCK_SECTION_VA + diag02.PRESERVED_FORMAL_END:
            raise RuntimeError(f"formal Scholar component overlaps the preserved prefix: {name}")
        if va + len(code) > limit:
            raise RuntimeError(f"formal Scholar component exceeds its slot: {name}")
        components[va] = code
        reports.append({
            "name": name,
            "va": f"0x{va:08X}",
            "length": len(code),
            "slot_end_va": f"0x{limit:08X}",
            "sha256": sha256_bytes(code),
            "assembly": source.strip(),
        })
    return reports, components


def patch_executable(path: Path) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_EXE_SHA256[path.name]:
        raise RuntimeError(f"unexpected {SOURCE_NAME} source hash: {path.name}")
    parsed = pefile.PE(data=original, fast_load=False)

    section_start = diag02.LUCK_SECTION_RAW_OFFSET
    section_end = section_start + diag02.LUCK_SECTION_SIZE
    source_section = original[section_start:section_end]
    if any(source_section[diag02.PRESERVED_FORMAL_END:]):
        raise RuntimeError(f"formal .luck3 tail is not empty: {path.name}")
    entry_offset = parsed.get_offset_from_rva(
        diag01.SCHOLAR_ENTRY_VA - diag01.IMAGE_BASE
    )
    if original[
        entry_offset:entry_offset + len(diag01.SCHOLAR_ENTRY_ORIGINAL)
    ] != diag01.SCHOLAR_ENTRY_ORIGINAL:
        raise RuntimeError(f"formal Scholar entry differs: {path.name}")

    record_start = CORONIUS_RECORD_OFFSET
    record_end = record_start + CORONIUS_RECORD_SIZE
    record = original[record_start:record_end]
    if sha256_bytes(record) != CORONIUS_RECORD_SHA256:
        raise RuntimeError(f"unexpected formal Coronius record: {path.name}")
    spell_field = record_start + STARTING_SPELL_OFFSET
    if struct.unpack_from("<I", original, spell_field)[0] != SLAYER_SPELL_ID:
        raise RuntimeError(f"formal Coronius does not start with Slayer: {path.name}")

    pointer = struct.unpack_from(
        "<I", original, test04.SPECIALTY_TABLE_POINTER_OFFSET
    )[0]
    if pointer != test04.SPECIALTY_TABLE_POINTER_VA:
        raise RuntimeError(f"unexpected specialty-table pointer: {path.name}")
    specialty_start = test04.CORONIUS_SPECIALTY_RECORD_OFFSET
    specialty_end = specialty_start + test04.SPECIALTY_RECORD_SIZE
    specialty_record = original[specialty_start:specialty_end]
    if sha256_bytes(specialty_record) != test04.CORONIUS_SPECIALTY_RECORD_SHA256:
        raise RuntimeError(f"unexpected Coronius specialty record: {path.name}")

    component_reports, components = build_feature_components()
    patched = bytearray(original)
    for va, code in components.items():
        raw = section_start + (va - diag02.LUCK_SECTION_VA)
        if any(original[raw:raw + len(code)]):
            raise RuntimeError(f"formal Scholar component slot is not empty: 0x{va:08X}")
        patched[raw:raw + len(code)] = code
    patched[
        section_start + (test01.ACTIVE_VA - diag02.LUCK_SECTION_VA)
    ] = 0

    hook_reports: list[dict[str, Any]] = []
    for item in test01.FEATURE_PATCHES:
        va = int(item["va"])
        source_bytes = bytes(item["source"])
        offset = parsed.get_offset_from_rva(va - diag01.IMAGE_BASE)
        if original[offset:offset + len(source_bytes)] != source_bytes:
            raise RuntimeError(f"formal Scholar hook source mismatch: {item['name']}")
        replacement = diag01.relative_jump(
            va, int(item["wrapper_va"]), len(source_bytes)
        )
        patched[offset:offset + len(replacement)] = replacement
        hook_reports.append({
            "name": item["name"],
            "va": f"0x{va:08X}",
            "file_offset": f"0x{offset:X}",
            "source_hex": source_bytes.hex(" "),
            "patched_hex": replacement.hex(" "),
            "rollback_hex": source_bytes.hex(" "),
            "wrapper_va": f"0x{int(item['wrapper_va']):08X}",
            "continue_va": f"0x{int(item['continue_va']):08X}",
        })

    struct.pack_into(
        "<i", patched, specialty_start, test04.DISABLED_SPECIALTY_TYPE
    )
    checksum_offset = parsed.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)
    if pefile.PE(data=final, fast_load=False).verify_checksum() is not True:
        raise RuntimeError(f"formal V1.2 checksum invalid: {path.name}")

    if final[
        entry_offset:entry_offset + len(diag01.SCHOLAR_ENTRY_ORIGINAL)
    ] != diag01.SCHOLAR_ENTRY_ORIGINAL:
        raise RuntimeError(f"formal release contains diagnostic entry hook: {path.name}")
    if b"hota_scholar_" in final or b"SCH1" in final:
        raise RuntimeError(f"formal release contains Scholar diagnostic strings: {path.name}")
    if final[record_start:record_end] != record:
        raise RuntimeError(f"formal release changed Coronius hero record: {path.name}")
    expected_specialty = bytearray(specialty_record)
    struct.pack_into("<i", expected_specialty, 0, test04.DISABLED_SPECIALTY_TYPE)
    if final[specialty_start:specialty_end] != bytes(expected_specialty):
        raise RuntimeError(f"formal specialty-table isolation failed: {path.name}")
    if final[
        section_start:section_start + diag02.PRESERVED_FORMAL_END
    ] != original[
        section_start:section_start + diag02.PRESERVED_FORMAL_END
    ]:
        raise RuntimeError(f"formal .luck3 prefix changed: {path.name}")

    permitted = set(range(checksum_offset, checksum_offset + 4))
    permitted.update(range(specialty_start, specialty_start + 4))
    for va, code in components.items():
        raw = section_start + (va - diag02.LUCK_SECTION_VA)
        permitted.update(range(raw, raw + len(code)))
    for item in test01.FEATURE_PATCHES:
        offset = parsed.get_offset_from_rva(int(item["va"]) - diag01.IMAGE_BASE)
        permitted.update(range(offset, offset + len(bytes(item["source"]))))
    actual = {
        index for index, (left, right) in enumerate(zip(original, final))
        if left != right
    }
    if not actual or not actual.issubset(permitted):
        raise RuntimeError(f"formal V1.2 changed an unapproved EXE byte: {path.name}")

    restored = bytearray(final)
    restored[section_start:section_end] = source_section
    for item in test01.FEATURE_PATCHES:
        offset = parsed.get_offset_from_rva(int(item["va"]) - diag01.IMAGE_BASE)
        source_bytes = bytes(item["source"])
        restored[offset:offset + len(source_bytes)] = source_bytes
    restored[specialty_start:specialty_end] = specialty_record
    restored[checksum_offset:checksum_offset + 4] = original[
        checksum_offset:checksum_offset + 4
    ]
    if bytes(restored) != original:
        raise RuntimeError(f"formal V1.2 full rollback failed: {path.name}")

    path.write_bytes(final)
    return {
        "name": path.name,
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "source_size": len(original),
        "output_size": len(final),
        "scholar_components": component_reports,
        "scholar_hooks": hook_reports,
        "coronius": {
            "hero_id": CORONIUS_ID,
            "hero_record_file_offset": f"0x{record_start:X}",
            "hero_record_unchanged": True,
            "starting_spell": {"id": SLAYER_SPELL_ID, "name": "Slayer"},
            "native_specialty_record_file_offset": f"0x{specialty_start:X}",
            "native_specialty_source_type": test04.NATIVE_SPELL_SPECIALTY_TYPE,
            "native_specialty_output_type": test04.DISABLED_SPECIALTY_TYPE,
            "native_slayer_bonus_bypassed": True,
        },
        "diagnostic_entry_hook_absent": True,
        "diagnostic_strings_absent": True,
        "formal_luck3_prefix_preserved": True,
        "pe_checksum_offset": f"0x{checksum_offset:X}",
        "pe_checksum_valid": True,
        "rollback_reconstructs_source": True,
        "contiguous_differences": contiguous_differences(original, final),
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与功能说明

适用版本：纯净 Heroes III HotA 1.8.0 中文版 + HD Mod。

安装方法：
1. 准备一份无其他平衡修改的纯净 HotA 1.8.0 游戏目录。
2. 将本压缩包内全部文件直接解压到游戏根目录。
3. 覆盖同名文件。
4. 使用 h3hota HD.exe 启动游戏。

V1.2 大版本新增：
- 将壁垒英雄克洛尼斯的原“屠戮”特长替换为“学术”特长；初始魔法仍为屠戮。
- 学术的效果提升一级：初级学术可互相学习 1—3 级魔法，中级可学习 1—4 级，高级可学习 1—5 级。
- 克洛尼斯与其他英雄会面时，双方通过智慧术学习魔法的等级上限也提升一级，最高不超过 5 级。
- 原屠戮特长的分级加成与实际增幅均已停用；屠戮作为初始法术保留，但只按普通法术规则生效。
- 特长图标使用游戏原生“高级学术”图标。

克洛尼斯初始配置：
- 初级智慧术 + 初级学术；魔法书初始自带屠戮。

完整保留的既有功能：
- 埃尔芙的新英雄立绘、25/25/25 仙灵初始兵力，以及仙灵/妖精伤害 +1、速度 +1；
- 马洛迪亚与黛瑞丝的固定幸运 +3、每支部队每场首次主动攻击必定幸运，以及原生幸运硬封锁；
- 马洛迪亚的初级智慧术 + 初级领导术与初始振奋；
- 黛瑞丝的初级智慧术 + 初级智力与初始观天；
- 尤兰德、阿斯特拉的单体/群体治愈、永久复活、原生目标限制、治疗动画与音效、复活起身动作；
- 治愈战斗日志顺序、逐队治疗量、魔法书动态范围和存活目标精确悬停数值；
- 阿斯特拉的初级智慧术 + 初级水系魔法；
- 阿德拉及其他未列明英雄的 HotA 1.8.0 原生行为。

当前治愈总量公式：
H = floor(((11L + 29) × (n + 11)) / 12) + 5 × (P - 1) + 10 × max(0, w - 1)

L 为英雄等级（最低 1），P 为当前有效力量（最低 0），n 为目标生物等级（限定 1—7），w 为水系魔法熟练度（无/初级/中级/高级分别为 0/1/2/3）。
"""


def update_installation_text(path: Path) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_INSTALLATION_SHA256:
        raise RuntimeError("unexpected V1.14 installation text hash")
    updated = installation_text().encode("utf-8")
    path.write_bytes(updated)
    return {
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(updated),
        "encoding": "utf-8",
        "complete_replacement": True,
    }


def manifest_markdown(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 构建与发布记录

- 来源正式版：`{SOURCE_NAME}`
- 来源 ZIP SHA-256：`{SOURCE_ZIP_SHA256}`
- 输出 ZIP SHA-256：`{report['zip_sha256']}`
- 治愈公式：`{FORMULA_EXPRESSION}`

## 正式变更

1. 克洛尼斯的原屠戮特长替换为学术特长：自身学术贡献提升一级；参与会面时，双方智慧术接收上限也提升一级，最高为 5。
2. 克洛尼斯仍以初级智慧术 + 初级学术开局，魔法书初始自带屠戮。
3. 原生屠戮特长类型从 `3` 改为 `-1`，旧动态加成栏与实际分级增幅均不可达。
4. 使用原生第 59 帧 `skill19c / skl3219c` 作为高级学术特长图标。

## 正式化边界

- 不保留测试版的学术入口诊断 Hook、日志文件名或 `SCH1` 记录器。
- `.luck3` 前 `0x800` 字节及既有幸运系统逐字节保留，只在已验证尾部槽位写入四个学术计算包装器。
- 克洛尼斯完整英雄记录不变，因此初始屠戮保持正式 V1.14 原值。
- 三份 HeroSpec、两份 D32F 特长图标容器与根目录安装说明同步更新。

## 验证

- 两份 EXE 独立验证四个 Hook、代码槽、原生屠戮类型门槛、PE 校验和和完整回滚。
- 正确的高级学术 DEF 帧、D32F 元数据前缀和所有非目标帧逐字节验证。
- ZIP CRC、成员集合、逐文件哈希和第二次可重复构建验证通过。
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

    executable_reports = [patch_executable(package_root / name) for name in EXE_NAMES]
    language_reports = [
        test02.patch_lod(package_root / relative, package_root)
        for relative in test02.LANGUAGE_ARCHIVES
    ]
    language_reports.append(
        test02.patch_loose_herospec(package_root / test02.LOOSE_HEROSPEC, package_root)
    )
    icon_report = test04.install_specialty_icons_only(
        package_root,
        args.secskill_def.resolve(),
        args.secskill32_def.resolve(),
    )

    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("expected exactly one root installation text")
    installation_report = update_installation_text(instruction_files[0])
    instruction_relative = instruction_files[0].relative_to(package_root).as_posix()

    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    if set(source_hashes) != set(package_hashes):
        raise RuntimeError("V1.2 changed the formal package member set")
    changed = {
        relative for relative in source_hashes
        if source_hashes[relative] != package_hashes[relative]
    }
    expected_changed = (
        set(EXE_NAMES)
        | set(test02.LANGUAGE_ARCHIVES)
        | {test02.LOOSE_HEROSPEC, instruction_relative}
        | set(diag01.D32F_RELATIVES)
    )
    if changed != expected_changed:
        raise RuntimeError(f"unexpected formal V1.2 delta: {sorted(changed ^ expected_changed)}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("formal V1.2 ZIP CRC failure")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("formal V1.2 ZIP member set mismatch")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "formal_release": True,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "formula": FORMULA_EXPRESSION,
        "changed_package_files": sorted(changed),
        "source_file_hashes": source_hashes,
        "package_file_hashes": package_hashes,
        "executables": executable_reports,
        "language_resources": language_reports,
        "specialty_icons": icon_report,
        "installation_text": installation_report,
        "behavior": {
            "coronius_secondary_skills": ["Basic Wisdom", "Basic Scholar"],
            "coronius_starting_spell": {"id": SLAYER_SPELL_ID, "name": "Slayer"},
            "coronius_native_slayer_specialty_disabled": True,
            "scholar_contribution_bonus": 1,
            "meeting_wisdom_cap_bonus": 1,
            "native_spell_level_cap": 5,
            "all_v114_gameplay_preserved": True,
        },
        "formalization": {
            "diagnostic_entry_hook_absent": True,
            "diagnostic_strings_absent": True,
            "test_log_writer_removed": True,
        },
        "static_verification": {
            "source_hashes_verified": True,
            "approved_executable_bytes_only": True,
            "full_executable_rollback_verified": True,
            "zip_crc_and_member_checks_passed": True,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
