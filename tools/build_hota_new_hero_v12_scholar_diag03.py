#!/usr/bin/env python3
"""Build the runtime-only Coronius Scholar diagnostic from formal V1.14.

DIAG03 is a single-variable isolation build.  It keeps every DEF/PCX resource
from formal V1.14 byte-for-byte and only installs the behavior-transparent
Scholar entry logger in the verified zero tail of the existing .luck3 section.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from build_hota_new_hero_v1 import (
    EXE_NAMES,
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)
import build_hota_new_hero_v12_scholar_diag01 as diag01
import build_hota_new_hero_v12_scholar_diag02 as diag02


BUILD_NAME = "HOTA_NEW_HERO_V1.2_SCHOLAR_DIAG03"
SOURCE_NAME = diag02.SOURCE_NAME
SOURCE_ZIP_SHA256 = diag02.SOURCE_ZIP_SHA256
LOG_FILENAME = "hota_scholar_diag03.bin"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure_logger() -> None:
    # DIAG02 owns the verified in-place PE layout.  Only the diagnostic identity
    # and output filename change; all addresses and the native continuation stay
    # identical so the executable delta remains independently reversible.
    diag01.BUILD_NAME = BUILD_NAME
    diag01.LOG_FILENAME = LOG_FILENAME


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与诊断说明

这是从正式 {SOURCE_NAME} 构建的科洛尼斯学术特第三阶段诊断包。

DIAG02 仍会在“单人游戏 → 新建场景”阶段闪退，而且没有生成学术诊断文件。该时间点尚未执行学术术会面 Hook，因此 DIAG03 完全撤销所有新英雄头像、特长图标、DEF 和 PCX 修改，只保留行为透明的学术术入口记录器。

本包不会改变学术术传授效果。科洛尼斯与友方英雄会面时，仅记录双方英雄数据到 {LOG_FILENAME}，随后完整执行正式 V1.14 的原生逻辑。

安装与测试：
1. 必须覆盖到纯净 HotA 1.8.0，不能叠加 DIAG01 或 DIAG02。
2. 使用 h3hota HD.exe 启动，先测试“单人游戏 → 新建场景”。
3. 若能进入地图，让科洛尼斯与一名友方英雄会面并打开交换界面；双方最好都有魔法书。
4. 退出游戏并上传根目录生成的 {LOG_FILENAME}。

本诊断包不会显示新的高级学术特长图标；图标将在运行路径确认稳定后单独处理。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logger()
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

    payload, payload_meta = diag01.build_payload()
    executable_reports = [
        diag02.patch_executable(package_root / name, payload, payload_meta)
        for name in EXE_NAMES
    ]

    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("expected exactly one root installation text file")
    instruction_files[0].write_text(installation_text(), encoding="utf-8")
    instruction_relative = instruction_files[0].relative_to(package_root).as_posix()

    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    if set(source_hashes) != set(package_hashes):
        raise RuntimeError("DIAG03 changed the formal V1.14 member set")
    changed = {
        relative for relative in source_hashes
        if source_hashes[relative] != package_hashes[relative]
    }
    expected_changed = set(EXE_NAMES) | {instruction_relative}
    if changed != expected_changed:
        raise RuntimeError(f"unexpected DIAG03 package delta: {sorted(changed)}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"DIAG03 ZIP CRC failure: {failed}")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("DIAG03 ZIP member set mismatch")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "diagnostic_only": True,
        "gameplay_logic_changed": False,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "withdrawn_predecessors": [
            {
                "name": "HOTA_NEW_HERO_V1.2_SCHOLAR_DIAG01",
                "reason": "new sixth PE section; user-reported New Scenario crash",
            },
            {
                "name": "HOTA_NEW_HERO_V1.2_SCHOLAR_DIAG02",
                "reason": "New Scenario crash persisted; all icon-resource deltas removed in DIAG03",
            },
        ],
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "log_filename": LOG_FILENAME,
        "changed_package_files": sorted(changed),
        "added_package_files": [],
        "source_file_hashes": source_hashes,
        "package_file_hashes": package_hashes,
        "executables": executable_reports,
        "static_verification": {
            "formal_v114_source_hashes_verified": True,
            "no_new_pe_section": True,
            "section_count_and_file_size_preserved": True,
            "formal_luck3_prefix_0x000_0x7ff_byte_preserved": True,
            "only_verified_zero_tail_0x800_0xfff_used": True,
            "all_formal_graphic_resources_byte_preserved": True,
            "package_member_set_unchanged": True,
            "full_executable_rollback_verified": True,
            "zip_crc_and_member_checks_passed": True,
        },
        "runtime_acceptance": {
            "status": "pending New Scenario survival and returned Coronius meeting log",
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
    print(f"Runtime log: {LOG_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
