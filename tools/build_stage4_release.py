#!/usr/bin/env python3
"""Promote the runtime-accepted TEST13 payload to formal Patch_v2.6.

The tested executables are copied byte-for-byte.  Only the two localized HotA
archives are repacked so HeroSpec.txt keeps the original Cure scaling sentence
and adds the concise permanent-resurrection sentence requested for the release.
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

from build_diag_patch import (
    EXE_NAMES,
    create_zip,
    safe_recreate_directory,
    sha256_bytes,
    sha256_file,
)
from extract_lod import DIRECTORY_OFFSET, ENTRY_SIZE, parse_entries, payload


RELEASE_NAME = "Patch_v2.6"
ACCEPTED_TEST_NAME = "Patch_v2.6_VISUAL_TEST13"
ACCEPTED_TEST_ZIP_SHA256 = (
    "2a4a8c6cd3177452680c5542ea9fa0ee7a8a3afe881e4f51d2322bc7410896cb"
)
LANGUAGE_ARCHIVES = ("Data/HotA_lng.lod", "Data/HotA_l_ext.lod")
HERO_SPEC_ENTRY = "HeroSpec.txt"
ORIGINAL_CURE_TEXT = (
    "施放疗伤时，英雄等级每增加(8-n)，效果提高10%，其中n是目标生物的等级。"
)
CONCISE_RESURRECTION_TEXT = "治愈魔法可以永久复活友方单位。"
RELEASE_CURE_TEXT = ORIGINAL_CURE_TEXT + CONCISE_RESURRECTION_TEXT


def replace_lod_text(archive_path: Path, archive_relative: str) -> dict[str, Any]:
    original = archive_path.read_bytes()
    entries = parse_entries(original)
    matches = [
        entry
        for entry in entries
        if str(entry["name"]).lower() == HERO_SPEC_ENTRY.lower()
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one {HERO_SPEC_ENTRY} entry in {archive_relative}, found {len(matches)}"
        )
    entry = matches[0]
    member = payload(original, entry)
    old = ORIGINAL_CURE_TEXT.encode("gb18030")
    new = RELEASE_CURE_TEXT.encode("gb18030")
    if member.count(old) != 1:
        raise RuntimeError(
            f"Expected original Cure sentence exactly once in {archive_relative}"
        )
    if CONCISE_RESURRECTION_TEXT.encode("gb18030") in member:
        raise RuntimeError(f"Concise Cure sentence already present in {archive_relative}")
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
        item
        for item in reparsed
        if str(item["name"]).lower() == HERO_SPEC_ENTRY.lower()
    )
    verified_member = payload(bytes(updated_archive), replacement)
    if verified_member != updated_member or verified_member.count(new) != 1:
        raise RuntimeError(f"Repacked HeroSpec verification failed: {archive_relative}")

    return {
        "archive": archive_relative,
        "entry": HERO_SPEC_ENTRY,
        "encoding": "gb18030",
        "old_text": ORIGINAL_CURE_TEXT,
        "added_text": CONCISE_RESURRECTION_TEXT,
        "new_text": RELEASE_CURE_TEXT,
        "input_archive_sha256": sha256_bytes(original),
        "output_archive_sha256": sha256_bytes(bytes(updated_archive)),
        "input_member_size": len(member),
        "output_member_size": len(updated_member),
        "stored_size": len(stored),
        "other_archive_bytes_preserved": True,
    }


def release_readme(report: dict[str, Any]) -> str:
    return f"""# {RELEASE_NAME} 使用说明

这是 HotA 1.8.0 新英雄特长补丁的正式版。

## 尤兰德 / 阿斯特拉

**特长说明：** {CONCISE_RESURRECTION_TEXT}

- 保留原版治愈特长的等级增幅。
- 治愈先恢复生命，剩余治疗量永久复活同一兵队的阵亡单位。
- 单体治愈可以选择符合原生规则的友方尸体；高级水系群体治愈可以复活多个合法友方尸体。
- 亡灵等原生禁止目标不会复活；非特长英雄不获得该能力。

## 演出与战斗日志

- 仅保留原版治愈动画、治愈音效和复活单位的起身动作。
- 不播放转世重生圆圈和转世重生音效。
- 单体与群体日志均先显示“施放治愈”，再显示各队复活记录。
- 普通转世重生的动画、音效和日志保持原版。

## 原生尸体规则

- 同一格存在重叠尸体时，只复活原生规则当前允许的一个兵队。
- 尸体格被存活兵队占用时不能复活。
- 复活单位战斗结束后永久保留。

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
        "状态：**Stage 4 正式版；全部功能、演出与日志顺序实机门禁已通过。**",
        "",
        f"- ZIP SHA-256：`{report['zip_sha256']}`",
        f"- 来源测试版：`{ACCEPTED_TEST_NAME}`",
        f"- 测试版 ZIP SHA-256：`{ACCEPTED_TEST_ZIP_SHA256}`",
        "- 两个 EXE：与实机通过的 TEST13 逐字节一致",
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
            "- 尤兰德、阿斯特拉：存活兵队治疗溢出、单体尸体与高级水系群体尸体复活均通过。",
            "- 复活数量、战后永久保留、亡灵/非特长英雄负例均通过。",
            "- 重叠尸体只复活一个；尸体格被存活兵队占用时不复活。",
            "- 治愈动画/音效、逐队起身与最终站立姿势通过；转世重生圆圈/音效仅对治愈复活隐藏。",
            "- 普通转世重生保持原版。",
            "- 单体和群体日志均已确认先显示治愈施法，再显示复活记录。",
            "",
            "## 特长文本",
            "",
            f"新增简化句：`{CONCISE_RESURRECTION_TEXT}`",
            "",
            "## 静态验证",
            "",
            "- TEST13 标准版与 HD 版执行文件逐字节保留。",
            "- 延迟日志分支 `RET 0x0C`、原生格式化和日志追加调用约定保持。",
            "- 两个语言 LOD 的 `HeroSpec.txt` 均完成重打包及解包复核。",
            "- 除两个语言 LOD 的特长文案外，正式包内容与 TEST13 一致。",
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
        raise RuntimeError("Unexpected TEST13 manifest")
    if sha256_file(test_zip) != ACCEPTED_TEST_ZIP_SHA256:
        raise RuntimeError("Accepted TEST13 ZIP hash mismatch")
    for relative, expected_hash in test_report["package_file_hashes"].items():
        if sha256_file(test_root / relative) != expected_hash:
            raise RuntimeError(f"Accepted TEST13 package file changed: {relative}")

    package_root = build_root / RELEASE_NAME
    safe_recreate_directory(package_root, build_root)
    shutil.copytree(
        test_root, package_root, dirs_exist_ok=True, copy_function=shutil.copy2
    )
    text_updates = [
        replace_lod_text(package_root / relative, relative)
        for relative in LANGUAGE_ARCHIVES
    ]

    package_files = sorted(path for path in package_root.rglob("*") if path.is_file())
    test_files = sorted(path for path in test_root.rglob("*") if path.is_file())
    package_members = [path.relative_to(package_root).as_posix() for path in package_files]
    test_members = [path.relative_to(test_root).as_posix() for path in test_files]
    if package_members != test_members:
        raise RuntimeError("Release package member set changed")
    for release_path in package_files:
        relative = release_path.relative_to(package_root).as_posix()
        if relative in LANGUAGE_ARCHIVES:
            continue
        if sha256_file(release_path) != test_report["package_file_hashes"][relative]:
            raise RuntimeError(f"Unexpected release content change: {relative}")

    for executable_name in EXE_NAMES:
        if (package_root / executable_name).read_bytes() != (
            test_root / executable_name
        ).read_bytes():
            raise RuntimeError(
                f"Accepted TEST13 executable changed during promotion: {executable_name}"
            )

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{RELEASE_NAME}.zip"
    create_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"ZIP integrity failure: {bad_member}")
        zip_members = sorted(archive.namelist())
    expected_members = sorted(package_members)
    if zip_members != expected_members:
        raise RuntimeError("ZIP member set mismatch")

    report = copy.deepcopy(test_report)
    report.update(
        {
            "build_name": RELEASE_NAME,
            "release": True,
            "scope": "stage4_formal_cure_resurrection_presentation_and_log_release",
            "source_test_build": ACCEPTED_TEST_NAME,
            "source_test_zip_sha256": ACCEPTED_TEST_ZIP_SHA256,
            "package_file_hashes": {
                path.relative_to(package_root).as_posix(): sha256_file(path)
                for path in package_files
            },
            "zip_path": zip_path.name,
            "zip_size": zip_path.stat().st_size,
            "zip_sha256": sha256_file(zip_path),
            "text_updates": text_updates,
            "runtime_acceptance_required": False,
            "runtime_acceptance": {
                "all_required_tests_passed": True,
                "single_and_mass_cure_resurrection": True,
                "living_and_fully_dead_friendly_stacks": True,
                "permanent_after_battle": True,
                "undead_and_non_specialist_negative_cases": True,
                "overlapping_and_occupied_corpse_rules": True,
                "cure_animation_and_sound_preserved": True,
                "resurrection_circle_and_sound_suppressed_for_cure_only": True,
                "stand_up_and_final_idle_pose": True,
                "ordinary_resurrection_unchanged": True,
                "single_cure_log_order": True,
                "mass_cure_log_order": True,
            },
        }
    )
    report["static_verification"]["accepted_test13_executables_byte_identical"] = True
    report["static_verification"]["only_language_archives_changed_from_test"] = True
    report["static_verification"]["both_hero_spec_entries_repacked_and_verified"] = True
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
    for update in text_updates:
        print(f"{update['archive']}: {update['output_archive_sha256']}")
    for executable in report["executables"]:
        print(f"{executable['name']}: {executable['output_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
