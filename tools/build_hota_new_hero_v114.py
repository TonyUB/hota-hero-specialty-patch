#!/usr/bin/env python3
"""Build formal HOTA_NEW_HERO_V1.14 from formal V1.13."""

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


BUILD_NAME = "HOTA_NEW_HERO_V1.14"
SOURCE_NAME = "HOTA_NEW_HERO_V1.13"
SOURCE_ZIP_SHA256 = "ade07aa267b98af897a23ac97917cdc0d375e75171745a56faf6686f66753767"
SOURCE_EXE_SHA256 = {
    "h3hota.exe": "123c686860c5eee2d6df201151a58aaf158d609e602ca85a27f25251d9b2ced1",
    "h3hota HD.exe": "a6bb571cb7336a942fdaa349540c4878d070f2cf9b96ce3a6b5bde9200c4e68d",
}
FORMULA_EXPRESSION = (
    "floor(((11L + 29) * (clamp(n,1,7) + 11)) / 12) "
    "+ 5 * (P - 1) + 10 * max(0, clamp(w,0,3) - 1)"
)

HERO_RECORD_SIZE = 0x5C
MELODIA_ID = 29
DAREMYTH_ID = 43
MELODIA_RECORD_OFFSET = 0x0027A83C
DAREMYTH_RECORD_OFFSET = 0x0027AD44
SECONDARY_SKILL_2_OFFSET = 0x14
STARTING_SPELL_OFFSET = 0x20
MYSTICISM_SKILL_ID = 8
LEADERSHIP_SKILL_ID = 6
MAGIC_ARROW_SPELL_ID = 15
VIEW_AIR_SPELL_ID = 5

MELODIA_V113_RECORD = bytes.fromhex(
    "01 00 00 00 03 00 00 00 03 00 00 00 07 00 00 00 "
    "01 00 00 00 08 00 00 00 01 00 00 00 01 00 00 00 "
    "31 00 00 00 0E 00 00 00 10 00 00 00"
)
DAREMYTH_V113_RECORD = bytes.fromhex(
    "01 00 00 00 04 00 00 00 05 00 00 00 07 00 00 00 "
    "01 00 00 00 18 00 00 00 01 00 00 00 01 00 00 00 "
    "0F 00 00 00 1C 00 00 00 1E 00 00 00"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def contiguous_differences(before: bytes, after: bytes) -> list[dict[str, Any]]:
    if len(before) != len(after):
        raise ValueError("contiguous comparison requires equal lengths")
    result: list[dict[str, Any]] = []
    index = 0
    while index < len(before):
        if before[index] == after[index]:
            index += 1
            continue
        start = index
        while index < len(before) and before[index] != after[index]:
            index += 1
        result.append({
            "offset": start,
            "length": index - start,
            "source_hex": before[start:index].hex(" "),
            "patched_hex": after[start:index].hex(" "),
            "rollback_hex": before[start:index].hex(" "),
        })
    return result


def v114_records() -> tuple[bytes, bytes]:
    melodia = bytearray(MELODIA_V113_RECORD)
    struct.pack_into("<I", melodia, SECONDARY_SKILL_2_OFFSET, LEADERSHIP_SKILL_ID)
    daremyth = bytearray(DAREMYTH_V113_RECORD)
    struct.pack_into("<I", daremyth, STARTING_SPELL_OFFSET, VIEW_AIR_SPELL_ID)
    return bytes(melodia), bytes(daremyth)


def patch_executable(path: Path) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_EXE_SHA256[path.name]:
        raise RuntimeError(f"Unexpected {SOURCE_NAME} source hash for {path.name}")

    melodia_end = MELODIA_RECORD_OFFSET + len(MELODIA_V113_RECORD)
    daremyth_end = DAREMYTH_RECORD_OFFSET + len(DAREMYTH_V113_RECORD)
    if original[MELODIA_RECORD_OFFSET:melodia_end] != MELODIA_V113_RECORD:
        raise RuntimeError(f"Unexpected Melodia V1.13 record in {path.name}")
    if original[DAREMYTH_RECORD_OFFSET:daremyth_end] != DAREMYTH_V113_RECORD:
        raise RuntimeError(f"Unexpected Daremyth V1.13 record in {path.name}")

    melodia_after, daremyth_after = v114_records()
    parsed = pefile.PE(data=original, fast_load=False)
    checksum_offset = parsed.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    source_checksum = original[checksum_offset:checksum_offset + 4]
    patched = bytearray(original)
    patched[MELODIA_RECORD_OFFSET:melodia_end] = melodia_after
    patched[DAREMYTH_RECORD_OFFSET:daremyth_end] = daremyth_after
    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)

    reparsed = pefile.PE(data=final, fast_load=False)
    if reparsed.verify_checksum() is not True:
        raise RuntimeError(f"PE checksum verification failed for {path.name}")
    if final[MELODIA_RECORD_OFFSET:melodia_end] != melodia_after:
        raise RuntimeError(f"Melodia V1.14 record verification failed for {path.name}")
    if final[DAREMYTH_RECORD_OFFSET:daremyth_end] != daremyth_after:
        raise RuntimeError(f"Daremyth V1.14 record verification failed for {path.name}")

    permitted = set(range(
        MELODIA_RECORD_OFFSET + SECONDARY_SKILL_2_OFFSET,
        MELODIA_RECORD_OFFSET + SECONDARY_SKILL_2_OFFSET + 4,
    ))
    permitted.update(range(
        DAREMYTH_RECORD_OFFSET + STARTING_SPELL_OFFSET,
        DAREMYTH_RECORD_OFFSET + STARTING_SPELL_OFFSET + 4,
    ))
    permitted.update(range(checksum_offset, checksum_offset + 4))
    actual = {
        offset for offset, (left, right) in enumerate(zip(original, final))
        if left != right
    }
    if not actual or not actual.issubset(permitted):
        raise RuntimeError(f"Unexpected V1.14 EXE byte differences in {path.name}")

    rollback = bytearray(final)
    rollback[MELODIA_RECORD_OFFSET:melodia_end] = MELODIA_V113_RECORD
    rollback[DAREMYTH_RECORD_OFFSET:daremyth_end] = DAREMYTH_V113_RECORD
    rollback[checksum_offset:checksum_offset + 4] = source_checksum
    if bytes(rollback) != original:
        raise RuntimeError(f"Full V1.14 rollback failed for {path.name}")

    path.write_bytes(final)
    return {
        "name": path.name,
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "source_size": len(original),
        "output_size": len(final),
        "hero_record_size": HERO_RECORD_SIZE,
        "melodia": {
            "hero_id": MELODIA_ID,
            "record_offset": MELODIA_RECORD_OFFSET,
            "field_offset": MELODIA_RECORD_OFFSET + SECONDARY_SKILL_2_OFFSET,
            "source_skill": {"id": MYSTICISM_SKILL_ID, "name": "Mysticism"},
            "output_skill": {"id": LEADERSHIP_SKILL_ID, "name": "Leadership"},
            "source_hex": struct.pack("<I", MYSTICISM_SKILL_ID).hex(" "),
            "patched_hex": struct.pack("<I", LEADERSHIP_SKILL_ID).hex(" "),
            "rollback_hex": struct.pack("<I", MYSTICISM_SKILL_ID).hex(" "),
        },
        "daremyth": {
            "hero_id": DAREMYTH_ID,
            "record_offset": DAREMYTH_RECORD_OFFSET,
            "field_offset": DAREMYTH_RECORD_OFFSET + STARTING_SPELL_OFFSET,
            "source_spell": {"id": MAGIC_ARROW_SPELL_ID, "name": "Magic Arrow"},
            "output_spell": {"id": VIEW_AIR_SPELL_ID, "name": "View Air"},
            "source_hex": struct.pack("<I", MAGIC_ARROW_SPELL_ID).hex(" "),
            "patched_hex": struct.pack("<I", VIEW_AIR_SPELL_ID).hex(" "),
            "rollback_hex": struct.pack("<I", MAGIC_ARROW_SPELL_ID).hex(" "),
        },
        "pe_checksum_offset": checksum_offset,
        "pe_checksum_valid": True,
        "rollback_reconstructs_source": True,
        "contiguous_differences": contiguous_differences(original, final),
    }


def update_installation_text(path: Path) -> dict[str, Any]:
    original = path.read_text(encoding="utf-8")
    replacements = [
        (
            "HOTA_NEW_HERO_V1.13 安装与功能说明",
            "HOTA_NEW_HERO_V1.14 安装与功能说明",
        ),
        (
            "V1.13 小版本说明：\n"
            "- 黛瑞丝的初始二级技能保持初级智慧术 + 初级智力；魔法书初始法术由振奋改为魔法神箭。\n"
            "- 除上述初始法术和版本说明外，全部游戏机制与正式 V1.12 保持一致。",
            "V1.14 平衡性调整：\n"
            "- 马洛迪亚的初始二级技能由初级智慧术 + 初级神秘术改为初级智慧术 + 初级领导术。\n"
            "- 黛瑞丝的初始二级技能保持初级智慧术 + 初级智力；魔法书初始法术由魔法神箭改为观天。\n"
            "- 除上述初始配置和版本说明外，全部游戏机制与正式 V1.13 保持一致。",
        ),
        (
            "- 马洛迪亚：初级智慧术 + 初级神秘术；魔法书初始自带振奋。",
            "- 马洛迪亚：初级智慧术 + 初级领导术；魔法书初始自带振奋。",
        ),
        (
            "- 黛瑞丝：初级智慧术 + 初级智力；魔法书初始自带魔法神箭。",
            "- 黛瑞丝：初级智慧术 + 初级智力；魔法书初始自带观天。",
        ),
    ]
    updated = original
    applied = []
    for old, new in replacements:
        count = updated.count(old)
        if count != 1:
            raise RuntimeError(f"Expected one installation-text match, found {count}: {old!r}")
        updated = updated.replace(old, new, 1)
        applied.append({"old": old, "new": new, "count": count})
    path.write_text(updated, encoding="utf-8")
    return {
        "encoding": "utf-8",
        "source_sha256": sha256_bytes(original.encode("utf-8")),
        "output_sha256": sha256_bytes(updated.encode("utf-8")),
        "replacements": applied,
    }


def manifest_markdown(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 构建与发布记录

- 来源正式版：`{SOURCE_NAME}`
- 来源 ZIP SHA-256：`{SOURCE_ZIP_SHA256}`
- 输出 ZIP SHA-256：`{report['zip_sha256']}`
- 治愈公式：`{FORMULA_EXPRESSION}`

## 正式变更

1. 马洛迪亚的初始二级技能由初级智慧术 + 初级神秘术改为初级智慧术 + 初级领导术，初始法术仍为振奋。
2. 黛瑞丝的初始二级技能仍为初级智慧术 + 初级智力，初始法术由魔法神箭（ID `15`）改为观天（View Air，ID `5`）。
3. 固定幸运 `+3`、逐队每场首次主动攻击必定幸运、原生幸运硬封锁、治愈永久复活和全部其他正式机制逐字节继承 V1.13。

## 文件边界

- 包内仅两个 EXE 的上述两个英雄记录字段与 PE 校验和发生变化。
- 根目录安装说明同步更新到 V1.14。
- `HotA.dll`、`HotA.dat`、两份 LOD、中文 HeroSpec、HD DEF、立绘及其他全部文件与 V1.13 逐字节一致。

## 验证

- 来源 ZIP、两个来源 EXE 与两份完整英雄记录均使用固定哈希/字节校验。
- 只允许马洛迪亚 `record + 0x14`、黛瑞丝 `record + 0x20` 和 PE 校验和字段变化。
- 两个 EXE 的 PE 校验和、完整回滚、ZIP CRC、成员集合和逐文件哈希均已验证。
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
    executable_reports = [patch_executable(package_root / name) for name in EXE_NAMES]

    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("Expected exactly one root installation text file")
    installation_report = update_installation_text(instruction_files[0])
    instruction_relative = instruction_files[0].relative_to(package_root).as_posix()

    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    if set(source_hashes) != set(package_hashes):
        raise RuntimeError("V1.14 package member set differs from V1.13")
    changed = {
        relative for relative in source_hashes
        if source_hashes[relative] != package_hashes[relative]
    }
    expected_changed = set(EXE_NAMES) | {instruction_relative}
    if changed != expected_changed:
        raise RuntimeError(f"Unexpected V1.14 package changes: {sorted(changed ^ expected_changed)}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"V1.14 ZIP CRC failure: {failed}")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("V1.14 ZIP member set mismatch")

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
        "installation_text": installation_report,
        "behavior": {
            "melodia_secondary_skills": ["Basic Wisdom", "Basic Leadership"],
            "melodia_starting_spell": {"id": 49, "name": "Mirth"},
            "daremyth_secondary_skills": ["Basic Wisdom", "Basic Intelligence"],
            "daremyth_starting_spell": {"id": VIEW_AIR_SPELL_ID, "name": "View Air"},
            "uland_and_astra_starting_spell": {"id": 37, "name": "Cure"},
            "all_v113_gameplay_mechanics_preserved": True,
        },
        "static_verification": {
            "source_hashes_verified": True,
            "complete_source_and_output_records_verified": True,
            "only_two_requested_fields_and_pe_checksums_changed_in_exes": True,
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
        instruction_files[0].read_text(encoding="utf-8"), encoding="utf-8"
    )
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    print("Changed package files: " + json.dumps(sorted(changed), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
