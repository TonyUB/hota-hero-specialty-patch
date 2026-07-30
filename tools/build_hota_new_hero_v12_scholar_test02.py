#!/usr/bin/env python3
"""Build the final visual/configuration Scholar test from formal V1.14."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
import zlib
from pathlib import Path
from typing import Any

import pefile

from build_hota_new_hero_v1 import (
    EXE_NAMES,
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)
from extract_lod import DIRECTORY_OFFSET, ENTRY_SIZE, parse_entries, payload
import build_hota_new_hero_v12_scholar_diag01 as diag01
import build_hota_new_hero_v12_scholar_diag02 as diag02
import build_hota_new_hero_v12_scholar_test01 as test01


BUILD_NAME = "HOTA_NEW_HERO_V1.2_SCHOLAR_TEST02"
SOURCE_NAME = "HOTA_NEW_HERO_V1.14"
SOURCE_ZIP_SHA256 = diag02.SOURCE_ZIP_SHA256
LOG_FILENAME = "hota_scholar_test02.bin"

SOURCE_RESOURCE_SHA256 = {
    "Data/HotA_lng.lod": "c3c02802565122ff746c6d24489787a9611395ca692605b2fbb676ef92ec1d70",
    "Data/HotA_l_ext.lod": "7ed4f3ec8136b5f7d875f8035f7acf963a4145c456b294c17db1975171801912",
    "_HD3_Data/Packs/H3中文-基础资源/HeroSpec.txt":
        "ad31b7594ac28b5fda52cd9796ea13d7ff9fc0c4a913117ae571fa7797902988",
}
LANGUAGE_ARCHIVES = ("Data/HotA_lng.lod", "Data/HotA_l_ext.lod")
LOOSE_HEROSPEC = "_HD3_Data/Packs/H3中文-基础资源/HeroSpec.txt"

CORONIUS_RECORD_OFFSET = 0x0027A670
CORONIUS_RECORD_SIZE = 0x5C
CORONIUS_RECORD_SHA256 = "44e6cbb9b0e9b9a07c7baad0e8501a8e26e70b9851244de40e4c1cf3d8260334"
STARTING_SPELL_OFFSET = 0x20
OLD_STARTING_SPELL = 55  # Slayer
NEW_STARTING_SPELL = 54  # Slow

OLD_LOD_RECORD = (
    '屠戮\t魔法奖励：屠戮\t"{屠戮}\r\n\r\n'
    '施放屠戮时，对1-2级生物效果+20，对3-4级生物效果+16，'
    '对5-6级生物效果+12，对7级生物效果+8。"'
)
NEW_LOD_RECORD = (
    '学术\t辅助技能奖励：学术\t"{学术}\r\n\r\n'
    '学术的效果提升一级；与其他英雄会面时，双方通过智慧术学习魔法的等级上限也提升一级。"'
)
OLD_LOOSE_RECORD = (
    "屠戮成性\t魔法奖励：屠戮成性\t使用屠戮成性魔法时效果大增，"
    "但还要取决于英雄级别与目标级别之差(目标的级别越低，效果越好)。"
)
NEW_LOOSE_RECORD = (
    "学术\t辅助技能奖励：学术\t学术的效果提升一级；与其他英雄会面时，"
    "双方通过智慧术学习魔法的等级上限也提升一级。"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def configure_feature_build() -> None:
    test01.BUILD_NAME = BUILD_NAME
    test01.LOG_FILENAME = LOG_FILENAME


def replace_record(data: bytes, old: str, new: str) -> tuple[bytes, dict[str, Any]]:
    old_bytes = old.encode("gb18030")
    new_bytes = new.encode("gb18030")
    count = data.count(old_bytes)
    if count != 1:
        # Accept LF-only archives while preserving their existing line-ending style.
        old_lf = old.replace("\r\n", "\n").encode("gb18030")
        new_lf = new.replace("\r\n", "\n").encode("gb18030")
        count = data.count(old_lf)
        if count != 1:
            raise RuntimeError(f"specialty record count is {count}, expected exactly one")
        old_bytes, new_bytes = old_lf, new_lf
    result = data.replace(old_bytes, new_bytes, 1)
    if result.count(new_bytes) != 1 or old_bytes in result:
        raise RuntimeError("specialty record replacement verification failed")
    # The source is a legacy Chinese resource.  A strict round trip proves that
    # the replacement did not silently normalize unrelated bytes.
    if data.decode("gb18030").encode("gb18030") != data:
        raise RuntimeError("HeroSpec source does not round-trip through GB18030")
    return result, {
        "source_record_sha256": sha256_bytes(old_bytes),
        "output_record_sha256": sha256_bytes(new_bytes),
        "source_length": len(old_bytes),
        "output_length": len(new_bytes),
        "replacement_count": 1,
    }


def patch_lod(path: Path, package_root: Path) -> dict[str, Any]:
    relative = path.relative_to(package_root).as_posix()
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_RESOURCE_SHA256[relative]:
        raise RuntimeError(f"unexpected formal language archive hash: {relative}")
    entries = parse_entries(original)
    matches = [entry for entry in entries if str(entry["name"]).lower() == "herospec.txt"]
    if len(matches) != 1:
        raise RuntimeError(f"expected one HeroSpec.txt in {relative}")
    entry = matches[0]
    member_before = payload(original, entry)
    member_after, text_report = replace_record(member_before, OLD_LOD_RECORD, NEW_LOD_RECORD)
    compressed = zlib.compress(member_after, 9)
    if len(compressed) < len(member_after):
        stored, compressed_size = compressed, len(compressed)
    else:
        stored, compressed_size = member_after, 0
    output = bytearray(original)
    new_offset = len(output)
    output.extend(stored)
    directory_position = DIRECTORY_OFFSET + int(entry["index"]) * ENTRY_SIZE
    struct.pack_into(
        "<IIII", output, directory_position + 16,
        new_offset, len(member_after), int(entry["type"]), compressed_size,
    )
    final = bytes(output)
    final_entries = parse_entries(final)
    if payload(final, final_entries[int(entry["index"])]) != member_after:
        raise RuntimeError(f"LOD repack verification failed: {relative}")
    original_directory = original[DIRECTORY_OFFSET:DIRECTORY_OFFSET + len(entries) * ENTRY_SIZE]
    final_directory = final[DIRECTORY_OFFSET:DIRECTORY_OFFSET + len(entries) * ENTRY_SIZE]
    before_without_target = (
        original_directory[:int(entry["index"]) * ENTRY_SIZE]
        + original_directory[(int(entry["index"]) + 1) * ENTRY_SIZE:]
    )
    after_without_target = (
        final_directory[:int(entry["index"]) * ENTRY_SIZE]
        + final_directory[(int(entry["index"]) + 1) * ENTRY_SIZE:]
    )
    if before_without_target != after_without_target:
        raise RuntimeError(f"an unrelated LOD directory entry changed: {relative}")
    path.write_bytes(final)
    return {
        "relative_path": relative,
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "member_source_sha256": sha256_bytes(member_before),
        "member_output_sha256": sha256_bytes(member_after),
        "text": text_report,
        "only_target_directory_entry_changed": True,
    }


def patch_loose_herospec(path: Path, package_root: Path) -> dict[str, Any]:
    relative = path.relative_to(package_root).as_posix()
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_RESOURCE_SHA256[relative]:
        raise RuntimeError("unexpected formal loose HeroSpec hash")
    final, report = replace_record(original, OLD_LOOSE_RECORD, NEW_LOOSE_RECORD)
    path.write_bytes(final)
    return {
        "relative_path": relative,
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "text": report,
    }


def patch_starting_spell(path: Path, formal_source: bytes) -> dict[str, Any]:
    stage = path.read_bytes()
    record_before = formal_source[
        CORONIUS_RECORD_OFFSET:CORONIUS_RECORD_OFFSET + CORONIUS_RECORD_SIZE
    ]
    if sha256_bytes(record_before) != CORONIUS_RECORD_SHA256:
        raise RuntimeError(f"unexpected formal Coronius record: {path.name}")
    if stage[
        CORONIUS_RECORD_OFFSET:CORONIUS_RECORD_OFFSET + CORONIUS_RECORD_SIZE
    ] != record_before:
        raise RuntimeError(f"Scholar gameplay stage touched Coronius record: {path.name}")
    field = CORONIUS_RECORD_OFFSET + STARTING_SPELL_OFFSET
    if struct.unpack_from("<I", stage, field)[0] != OLD_STARTING_SPELL:
        raise RuntimeError(f"unexpected Coronius starting spell: {path.name}")
    final = bytearray(stage)
    struct.pack_into("<I", final, field, NEW_STARTING_SPELL)
    pe = pefile.PE(data=bytes(final), fast_load=False)
    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    struct.pack_into("<I", final, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(final), fast_load=False)
    struct.pack_into("<I", final, checksum_offset, checksum_pe.generate_checksum())
    candidate = bytes(final)
    candidate_pe = pefile.PE(data=candidate, fast_load=False)
    if candidate_pe.verify_checksum() is not True:
        raise RuntimeError(f"checksum invalid after starting-spell patch: {path.name}")
    restored = bytearray(candidate)
    struct.pack_into("<I", restored, field, OLD_STARTING_SPELL)
    restored[checksum_offset:checksum_offset + 4] = stage[checksum_offset:checksum_offset + 4]
    if bytes(restored) != stage:
        raise RuntimeError(f"starting-spell rollback failed: {path.name}")
    path.write_bytes(candidate)
    return {
        "hero_id": diag01.CORONIUS_ID,
        "record_file_offset": f"0x{CORONIUS_RECORD_OFFSET:X}",
        "field_file_offset": f"0x{field:X}",
        "source_spell_id": OLD_STARTING_SPELL,
        "output_spell_id": NEW_STARTING_SPELL,
        "output_sha256": sha256_bytes(candidate),
        "rollback_to_gameplay_stage_verified": True,
    }


def install_specialty_icons_only(
    package_root: Path, secskill_def: Path, secskill32_def: Path
) -> dict[str, Any]:
    image44, _, _, source44 = diag01.decode_expert_scholar(
        secskill_def,
        expected_hash=diag01.SECSKILL_DEF_SHA256,
        expected_size=44,
        expected_name="skill18c.pcx",
    )
    image32, _, _, source32 = diag01.decode_expert_scholar(
        secskill32_def,
        expected_hash=diag01.SECSK32_DEF_SHA256,
        expected_size=32,
        expected_name="skl3218c.pcx",
    )
    reports = []
    for relative, expected in diag01.D32F_RELATIVES.items():
        reports.append(diag01.patch_d32f(
            package_root / relative,
            image44 if int(expected["size"]) == 44 else image32,
            expected,
        ))
    forbidden = [
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file()
        and path.name.upper().startswith(("HPS024", "HPL024"))
    ]
    if forbidden:
        raise RuntimeError(f"Coronius portrait resources must remain absent: {forbidden}")
    return {
        "native_expert_scholar_sources": [source44, source32],
        "d32f": reports,
        "coronius_frame": diag01.CORONIUS_ID,
        "portrait_resources_added_or_modified": False,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 收尾测试说明

本包从正式 {SOURCE_NAME} 构建，用于确认科洛尼斯学术特的最终界面与初始配置；学术交换功能沿用已经通过测试的 TEST01 实现。

本次新增：
1. 科洛尼斯的特长图标改为游戏内“高级学术 / Expert Scholar”的原生图标，只修改特长图标，不修改英雄头像；
2. 特长说明改为：{NEW_LOOSE_RECORD.split(chr(9), 2)[2]}
3. 科洛尼斯的初始魔法由屠戮改为一级魔法“减速”。

安装：必须覆盖到纯净 HotA 1.8.0 中文版，不能叠加此前的学术诊断包或测试包。

本轮只需做最小验证：
1. “单人游戏 → 新建场景”能够正常进入；
2. 科洛尼斯头像仍为原头像，特长图标显示为高级学术；
3. 英雄界面中的特长名称与说明正确；
4. 科洛尼斯魔法书初始自带“减速”，不再自带“屠戮”；
5. 与己方英雄会面一次，确认已经通过的学术交换功能没有回归。

运行记录文件为 {LOG_FILENAME}。若上述五项全部通过，只需直接反馈结果；只有交换逻辑异常时才需要上传该文件。
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
    formal_executables = {
        name: (package_root / name).read_bytes() for name in EXE_NAMES
    }

    configure_feature_build()
    feature_payload, payload_meta = test01.build_payload()
    executable_reports = []
    for name in EXE_NAMES:
        feature_report = test01.patch_executable(
            package_root / name, feature_payload, payload_meta
        )
        spell_report = patch_starting_spell(package_root / name, formal_executables[name])
        executable_reports.append({
            **feature_report,
            "output_sha256": spell_report["output_sha256"],
            "starting_spell": spell_report,
        })

    language_reports = [
        patch_lod(package_root / relative, package_root)
        for relative in LANGUAGE_ARCHIVES
    ]
    loose_report = patch_loose_herospec(package_root / LOOSE_HEROSPEC, package_root)
    icon_report = install_specialty_icons_only(
        package_root, args.secskill_def.resolve(), args.secskill32_def.resolve()
    )

    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("expected exactly one root installation text")
    instruction_files[0].write_text(installation_text(), encoding="utf-8")
    instruction_relative = instruction_files[0].relative_to(package_root).as_posix()

    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    if set(source_hashes) != set(package_hashes):
        raise RuntimeError("SCHOLAR_TEST02 changed the formal member set")
    changed = {
        relative for relative in source_hashes
        if source_hashes[relative] != package_hashes[relative]
    }
    expected_changed = (
        set(EXE_NAMES)
        | set(LANGUAGE_ARCHIVES)
        | {LOOSE_HEROSPEC, instruction_relative}
        | set(diag01.D32F_RELATIVES)
    )
    if changed != expected_changed:
        raise RuntimeError(f"unexpected SCHOLAR_TEST02 delta: {sorted(changed ^ expected_changed)}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("SCHOLAR_TEST02 ZIP CRC failure")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("SCHOLAR_TEST02 ZIP member set mismatch")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "test_only": True,
        "formal_release": False,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "log_filename": LOG_FILENAME,
        "changed_package_files": sorted(changed),
        "added_package_files": [],
        "source_file_hashes": source_hashes,
        "package_file_hashes": package_hashes,
        "executables": executable_reports,
        "language_resources": language_reports + [loose_report],
        "specialty_icons": icon_report,
        "runtime_acceptance": {
            "scholar_gameplay": "TEST01 accepted by user",
            "test02_scope": "icon, description, starting Slow, and regression smoke",
        },
        "safety": {
            "portrait_files_untouched": True,
            "only_existing_package_members_changed": True,
            "zip_crc_passed": True,
        },
    }
    (output_root / f"{BUILD_NAME}_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
