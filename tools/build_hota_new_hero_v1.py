#!/usr/bin/env python3
"""Build HOTA_NEW_HERO_V1 from the accepted Patch_v2.6 release.

The accepted Cure/Elf runtime payload is preserved byte-for-byte except for the
two exact Adela zero-cost-Bless edits, which are restored to clean HotA 1.8.0
bytes.  The localized HeroSpec entries and installation text are then updated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import zipfile
import zlib
from pathlib import Path
from typing import Any

from extract_lod import DIRECTORY_OFFSET, ENTRY_SIZE, parse_entries, payload


RELEASE_NAME = "HOTA_NEW_HERO_V1"
SOURCE_NAME = "Patch_v2.6"
SOURCE_ZIP_SHA256 = "afb90c1a02e25eb8face09908b66150eb05f21e4a457144ffaccaaf0b6eb5557"
EXE_NAMES = ("h3hota.exe", "h3hota HD.exe")
LANGUAGE_ARCHIVES = ("Data/HotA_lng.lod", "Data/HotA_l_ext.lod")
HERO_SPEC_ENTRY = "HeroSpec.txt"

ADELA_HOOK_OFFSET = 0x000E5597
ADELA_CAVE_OFFSET = 0x00239D40
ADELA_PATCHED_HOOK = bytes.fromhex("E9 A4 47 15 00")
ADELA_NATIVE_HOOK = bytes.fromhex("8B C6 5E 5B 5D")
ADELA_PATCHED_CAVE = bytes.fromhex(
    "83 7B 1A 09 75 08 83 7D 08 29 75 02 31 F6 "
    "8B C6 5E 5B 5D E9 44 B8 EA FF"
)
ADELA_NATIVE_CAVE = bytes(len(ADELA_PATCHED_CAVE))

ORIGINAL_CURE_TEXT = (
    "施放疗伤时，英雄等级每增加(8-n)，效果提高10%，其中n是目标生物的等级。"
)
PERMANENT_RESURRECTION_TEXT = "治愈魔法可以永久复活友方单位。"
SOURCE_CURE_TEXT = ORIGINAL_CURE_TEXT + PERMANENT_RESURRECTION_TEXT
RELEASE_CURE_TEXT = PERMANENT_RESURRECTION_TEXT + ORIGINAL_CURE_TEXT
ADELA_ZERO_COST_LINE = "施放祝福时不消耗魔法值。\n\n"
ORIGINAL_BLESS_TEXT = (
    "施放祝福时，英雄等级每增加n，效果提高10%，其中n是目标生物的等级。"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def safe_recreate_directory(path: Path, parent: Path) -> None:
    resolved = path.resolve()
    resolved_parent = parent.resolve()
    if resolved == resolved_parent or resolved_parent not in resolved.parents:
        raise RuntimeError(f"Unsafe build directory: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def extract_zip_safely(source_zip: Path, target: Path) -> None:
    resolved_target = target.resolve()
    with zipfile.ZipFile(source_zip, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Source ZIP failed CRC validation")
        for info in archive.infolist():
            destination = (resolved_target / info.filename).resolve()
            if resolved_target not in destination.parents and destination != resolved_target:
                raise RuntimeError(f"Unsafe ZIP member: {info.filename}")
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)


def patch_adela(executable: Path) -> dict[str, Any]:
    original = executable.read_bytes()
    updated = bytearray(original)
    changes = (
        ("native function epilogue", ADELA_HOOK_OFFSET, ADELA_PATCHED_HOOK, ADELA_NATIVE_HOOK),
        ("retired zero-cost code cave", ADELA_CAVE_OFFSET, ADELA_PATCHED_CAVE, ADELA_NATIVE_CAVE),
    )
    reports: list[dict[str, Any]] = []
    for label, offset, expected, replacement in changes:
        actual = bytes(updated[offset : offset + len(expected)])
        if actual != expected:
            raise RuntimeError(
                f"{executable.name}: unexpected {label} bytes at 0x{offset:08X}: "
                f"{actual.hex(' ')}"
            )
        updated[offset : offset + len(expected)] = replacement
        reports.append(
            {
                "label": label,
                "file_offset": f"0x{offset:08X}",
                "va": f"0x{offset + 0x00400000:08X}",
                "source_bytes": expected.hex(" "),
                "release_bytes": replacement.hex(" "),
                "rollback_bytes": expected.hex(" "),
            }
        )
    executable.write_bytes(updated)
    return {
        "name": executable.name,
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(bytes(updated)),
        "changed_byte_count": sum(len(item[2]) for item in changes),
        "changes": reports,
    }


def update_hero_spec(archive_path: Path, archive_relative: str) -> dict[str, Any]:
    original_archive = archive_path.read_bytes()
    entries = parse_entries(original_archive)
    matches = [
        item for item in entries if str(item["name"]).lower() == HERO_SPEC_ENTRY.lower()
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {HERO_SPEC_ENTRY} in {archive_relative}")
    entry = matches[0]
    member = payload(original_archive, entry)
    source_cure = SOURCE_CURE_TEXT.encode("gb18030")
    release_cure = RELEASE_CURE_TEXT.encode("gb18030")
    adela_line = ADELA_ZERO_COST_LINE.encode("gb18030")
    original_bless = ORIGINAL_BLESS_TEXT.encode("gb18030")
    if member.count(source_cure) != 1:
        raise RuntimeError(f"Expected current Cure text once in {archive_relative}")
    if member.count(adela_line) != 1:
        raise RuntimeError(f"Expected Adela zero-cost line once in {archive_relative}")
    if member.count(original_bless) != 1:
        raise RuntimeError(f"Expected original Bless text once in {archive_relative}")
    updated_member = member.replace(source_cure, release_cure, 1).replace(adela_line, b"", 1)
    if updated_member.count(release_cure) != 1 or adela_line in updated_member:
        raise RuntimeError(f"HeroSpec replacement failed in {archive_relative}")

    stored = zlib.compress(updated_member, level=9)
    updated_archive = bytearray(original_archive)
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

    verified_entry = next(
        item
        for item in parse_entries(bytes(updated_archive))
        if str(item["name"]).lower() == HERO_SPEC_ENTRY.lower()
    )
    verified = payload(bytes(updated_archive), verified_entry)
    if verified != updated_member:
        raise RuntimeError(f"Repacked HeroSpec verification failed in {archive_relative}")
    return {
        "archive": archive_relative,
        "entry": HERO_SPEC_ENTRY,
        "encoding": "gb18030",
        "source_archive_sha256": sha256_bytes(original_archive),
        "output_archive_sha256": sha256_bytes(bytes(updated_archive)),
        "cure_text_before": SOURCE_CURE_TEXT,
        "cure_text_after": RELEASE_CURE_TEXT,
        "removed_adela_text": ADELA_ZERO_COST_LINE.rstrip(),
        "original_bless_text_preserved": ORIGINAL_BLESS_TEXT,
        "other_archive_bytes_preserved": True,
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

治愈复活演出：
- 保留原版治愈动画、治愈音效和复活单位的起身动作。
- 不播放转世重生圆圈和转世重生音效。
- 战斗日志先显示治愈施法，再显示各队复活记录。
"""


def deterministic_zip(package_root: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in package_root.rglob("*") if item.is_file()):
            relative = path.relative_to(package_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def release_readme(report: dict[str, Any]) -> str:
    return f"""# {RELEASE_NAME}

适用于 HotA 1.8.0 中文版与 HD Mod。

## 英雄修改

- 埃尔芙：仙灵和妖精杀伤力 +1、速度 +1；初始兵力为 25 / 25 / 25 仙灵。
- 尤兰德、阿斯特拉：{RELEASE_CURE_TEXT}

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
        "- 治愈复活、动画、音效与日志顺序逻辑逐字节继承自已实机通过的 v2.6。",
        "- 阿德拉零耗魔入口和代码洞均恢复为纯净 HotA 1.8.0 字节。",
        "- 两个语言 LOD 均恢复祝福原文，并按“新增治愈句 + 原始等级增幅句”排列。",
        "- 除两个 EXE、两个语言 LOD 和安装说明外，包内文件与 v2.6 相同。",
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
        raise RuntimeError("Accepted Patch_v2.6 ZIP hash mismatch")

    package_root = build_root / RELEASE_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_files = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }

    executable_reports = [patch_adela(package_root / name) for name in EXE_NAMES]
    text_reports = [
        update_hero_spec(package_root / relative, relative)
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

    allowed_changes = set(EXE_NAMES) | set(LANGUAGE_ARCHIVES) | {instruction_files[0].name}
    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path) for path in package_files
    }
    actual_changes = {
        relative for relative, digest in package_hashes.items() if source_files[relative] != digest
    }
    if actual_changes != allowed_changes:
        raise RuntimeError(f"Unexpected package changes: {sorted(actual_changes ^ allowed_changes)}")

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
        "runtime_inheritance": {
            "cure_resurrection_logic_from_runtime_accepted_v2_6": True,
            "elf_specialty_logic_unchanged": True,
            "ordinary_resurrection_unchanged": True,
        },
        "static_verification": {
            "adela_native_hook_bytes_restored": True,
            "adela_code_cave_cleared": True,
            "both_hero_spec_entries_repacked_and_verified": True,
            "only_expected_package_files_changed": True,
            "release_zip_crc_test_passed": True,
        },
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
        print(f"{item['archive']}: {item['output_archive_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
