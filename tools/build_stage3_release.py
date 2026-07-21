#!/usr/bin/env python3
"""Promote the runtime-accepted Stage 3 test payload to Patch_v2.5.

The two tested executables are copied byte-for-byte. The only package-content
change is a localized HeroSpec.txt sentence inside HotA_lng.lod describing the
new fully-dead Cure behavior.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import struct
import zlib
import zipfile
from pathlib import Path
from typing import Any

from build_diag_patch import EXE_NAMES, create_zip, safe_recreate_directory, sha256_bytes, sha256_file
from extract_lod import DIRECTORY_OFFSET, ENTRY_SIZE, parse_entries, payload


RELEASE_NAME = "Patch_v2.5"
ACCEPTED_TEST_NAME = "Patch_v2.5_STAGE3_TEST3"
ACCEPTED_TEST_ZIP_SHA256 = "11d3d34175b8b15b5de7f8c5af31e9809762cdb76909910704936e2b43fd8c73"
LANGUAGE_ARCHIVE = "Data/HotA_lng.lod"
HERO_SPEC_ENTRY = "HeroSpec.txt"
OLD_CURE_TEXT = "施放疗伤时，英雄等级每增加(8-n)，效果提高10%，其中n是目标生物的等级。"
NEW_CURE_TEXT = OLD_CURE_TEXT + "此外，疗伤可以复活已经全部阵亡的己方部队。"


def replace_lod_text(archive_path: Path) -> dict[str, Any]:
    original = archive_path.read_bytes()
    entries = parse_entries(original)
    matches = [entry for entry in entries if str(entry["name"]).lower() == HERO_SPEC_ENTRY.lower()]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {HERO_SPEC_ENTRY} entry, found {len(matches)}")
    entry = matches[0]
    member = payload(original, entry)
    old = OLD_CURE_TEXT.encode("gb18030")
    new = NEW_CURE_TEXT.encode("gb18030")
    if member.count(old) != 1:
        raise RuntimeError("Expected Cure specialty sentence was not found exactly once")
    if new in member:
        raise RuntimeError("Cure resurrection sentence is already present")
    updated_member = member.replace(old, new, 1)
    stored = zlib.compress(updated_member, level=9)

    updated_archive = bytearray(original)
    member_offset = len(updated_archive)
    updated_archive.extend(stored)
    directory_position = DIRECTORY_OFFSET + int(entry["index"]) * ENTRY_SIZE
    struct.pack_into(
        "<IIII",
        updated_archive,
        directory_position + 16,
        member_offset,
        len(updated_member),
        int(entry["type"]),
        len(stored),
    )
    archive_path.write_bytes(updated_archive)

    reparsed = parse_entries(bytes(updated_archive))
    replacement = next(
        item for item in reparsed if str(item["name"]).lower() == HERO_SPEC_ENTRY.lower()
    )
    verified_member = payload(bytes(updated_archive), replacement)
    if verified_member != updated_member or verified_member.count(new) != 1:
        raise RuntimeError("Repacked HeroSpec.txt verification failed")

    return {
        "archive": LANGUAGE_ARCHIVE,
        "entry": HERO_SPEC_ENTRY,
        "encoding": "gb18030",
        "old_text": OLD_CURE_TEXT,
        "new_text": NEW_CURE_TEXT,
        "input_archive_sha256": sha256_bytes(original),
        "output_archive_sha256": sha256_bytes(bytes(updated_archive)),
        "input_member_size": len(member),
        "output_member_size": len(updated_member),
        "stored_size": len(stored),
        "other_archive_bytes_preserved": True,
    }


def release_readme(report: dict[str, Any]) -> str:
    return f"""# {RELEASE_NAME} 使用说明

这是 HotA 1.8.0 英雄特长补丁的 Stage 3 正式版。

## 治愈特长

- 尤兰德和阿斯特拉保留原有治愈特长数值。
- 治愈仍会先治疗存活单位，并用剩余治疗量永久复活同一兵队中的阵亡单位。
- 单体治愈可以选择并复活符合原生转世重生规则的己方全灭兵队。
- 高级水系群体治愈会在处理存活兵队后，继续复活符合条件的己方全灭兵队。
- 亡灵等原生禁止目标不会复活；其他英雄不会获得该能力。

## 原生尸体规则

- 同一格存在重叠尸体时，只复活原生规则当前允许的一个兵队。
- 尸体落位被存活兵队占用时不能复活。
- 所有复活均使用永久参数，战斗结束后保留。

## 安装

1. 适用于与项目基线一致的 HotA 1.8.0 中文版。
2. 备份游戏目录中的同名文件。
3. 将 `{RELEASE_NAME}.zip` 解压到游戏根目录并覆盖。

## 校验

```text
{RELEASE_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def markdown_manifest(report: dict[str, Any]) -> str:
    lines = [
        f"# {RELEASE_NAME} 构建与验收清单",
        "",
        "状态：**Stage 3 正式版；全部运行时门禁已通过。**",
        "",
        f"- ZIP SHA-256：`{report['zip_sha256']}`",
        f"- 来源测试版：`{ACCEPTED_TEST_NAME}`",
        f"- 测试版 ZIP SHA-256：`{ACCEPTED_TEST_ZIP_SHA256}`",
        "- 两个 EXE：与实机通过的 TEST3 逐字节一致",
        "- 运行日志：无",
        "",
        "## EXE 哈希",
        "",
        "| 文件 | SHA-256 |",
        "|---|---|",
    ]
    for executable in report["executables"]:
        lines.append(f"| `{executable['name']}` | `{executable['output_sha256']}` |")
    lines.extend(
        [
            "",
            "## 实机验收",
            "",
            "- 尤兰德、阿斯特拉：存活兵队治疗溢出复活通过。",
            "- 尤兰德、阿斯特拉：单体治愈复活全灭尸体通过。",
            "- 两名英雄的高级水系群体治愈复活多个全灭尸体通过。",
            "- 复活单位战后永久保留。",
            "- 重叠尸体只复活一个；尸体格被存活兵队占用时不复活，符合原生落位规则。",
            "- 亡灵只治疗、不复活；非特长英雄单体和群体均不复活尸体。",
            "",
            "## 文本更新",
            "",
            f"`{NEW_CURE_TEXT}`",
            "",
            "## 静态验证",
            "",
            "- 启动导出名 `MainProc\\0` 保持完整。",
            "- 六处挂钩均反汇编到预期入口；两个 EXE 大小不变。",
            "- 所有补丁区均可完整回滚重建可信输入。",
            "- 除 `HotA_lng.lod` 的 HeroSpec.txt 文案外，正式包内容与 TEST3 一致。",
            "- ZIP 成员集合与 CRC 校验通过。",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-root", type=Path, required=True)
    parser.add_argument("--test-zip", type=Path, required=True)
    parser.add_argument("--test-manifest", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    test_root = args.test_root.resolve()
    test_zip = args.test_zip.resolve()
    test_manifest_path = args.test_manifest.resolve()
    build_root = args.build_root.resolve()
    output_root = args.output_root.resolve()
    test_report = json.loads(test_manifest_path.read_text(encoding="utf-8"))

    if test_report.get("build_name") != ACCEPTED_TEST_NAME:
        raise RuntimeError("Unexpected Stage 3 test manifest")
    if sha256_file(test_zip) != ACCEPTED_TEST_ZIP_SHA256:
        raise RuntimeError("Accepted Stage 3 test ZIP hash mismatch")
    for relative, expected_hash in test_report["package_file_hashes"].items():
        if sha256_file(test_root / relative) != expected_hash:
            raise RuntimeError(f"Accepted test package file changed: {relative}")

    package_root = build_root / RELEASE_NAME
    safe_recreate_directory(package_root, build_root)
    shutil.copytree(test_root, package_root, dirs_exist_ok=True, copy_function=shutil.copy2)
    text_update = replace_lod_text(package_root / LANGUAGE_ARCHIVE)

    package_files = sorted(path for path in package_root.rglob("*") if path.is_file())
    test_files = sorted(path for path in test_root.rglob("*") if path.is_file())
    if [path.relative_to(package_root).as_posix() for path in package_files] != [
        path.relative_to(test_root).as_posix() for path in test_files
    ]:
        raise RuntimeError("Release package member set changed")
    for release_path in package_files:
        relative = release_path.relative_to(package_root).as_posix()
        if relative == LANGUAGE_ARCHIVE:
            continue
        if sha256_file(release_path) != test_report["package_file_hashes"][relative]:
            raise RuntimeError(f"Unexpected release content change: {relative}")

    for executable_name in EXE_NAMES:
        if (package_root / executable_name).read_bytes() != (test_root / executable_name).read_bytes():
            raise RuntimeError(f"Accepted executable changed during promotion: {executable_name}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{RELEASE_NAME}.zip"
    create_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"ZIP integrity failure: {bad_member}")
        zip_members = sorted(archive.namelist())
    expected_members = sorted(path.relative_to(package_root).as_posix() for path in package_files)
    if zip_members != expected_members:
        raise RuntimeError("ZIP member set mismatch")

    report = copy.deepcopy(test_report)
    report.update(
        {
            "build_name": RELEASE_NAME,
            "release": True,
            "scope": "stage3_single_and_mass_corpse_release",
            "source_test_build": ACCEPTED_TEST_NAME,
            "source_test_zip_sha256": ACCEPTED_TEST_ZIP_SHA256,
            "package_file_hashes": {
                path.relative_to(package_root).as_posix(): sha256_file(path)
                for path in package_files
            },
            "zip_path": zip_path.name,
            "zip_size": zip_path.stat().st_size,
            "zip_sha256": sha256_file(zip_path),
            "text_update": text_update,
            "runtime_acceptance_required": False,
            "runtime_acceptance": {
                "all_required_tests_passed": True,
                "single_corpse_cure_uland": True,
                "single_corpse_cure_astra": True,
                "mass_corpse_cure_uland": True,
                "mass_corpse_cure_astra": True,
                "living_stack_overflow_resurrection": True,
                "permanent_after_battle": True,
                "undead_negative": True,
                "non_specialist_single_negative": True,
                "non_specialist_mass_negative": True,
                "overlapping_corpses_only_one_resurrected": True,
                "occupied_corpse_not_resurrected": True,
            },
        }
    )
    report["static_verification"]["accepted_test_executables_byte_identical"] = True
    report["static_verification"]["only_language_archive_changed_from_test"] = True
    report["static_verification"]["release_zip_crc_test_passed"] = True

    (output_root / f"{RELEASE_NAME}_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / f"{RELEASE_NAME}_manifest.md").write_text(
        markdown_manifest(report), encoding="utf-8"
    )
    (output_root / f"{RELEASE_NAME}_README.md").write_text(
        release_readme(report), encoding="utf-8"
    )

    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    print(f"HeroSpec: {text_update['output_archive_sha256']}")
    for executable in report["executables"]:
        print(f"{executable['name']}: {executable['output_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
