#!/usr/bin/env python3
"""Independently verify HOTA_NEW_HERO_V1.2_SCHOLAR_DIAG03."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from build_hota_new_hero_v1 import EXE_NAMES, extract_zip_safely, safe_recreate_directory
import build_hota_new_hero_v12_scholar_diag01 as diag01
import build_hota_new_hero_v12_scholar_diag03 as diag03
from verify_hota_new_hero_v12_scholar_diag02 import verify_executable


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--candidate-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()

    diag03.configure_logger()
    if sha256(args.source_zip) != diag03.SOURCE_ZIP_SHA256:
        raise RuntimeError("formal V1.14 source ZIP hash mismatch")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest["build_name"] != diag03.BUILD_NAME or not manifest["diagnostic_only"]:
        raise RuntimeError("DIAG03 manifest identity mismatch")
    if sha256(args.candidate_zip) != manifest["zip_sha256"]:
        raise RuntimeError("DIAG03 ZIP hash mismatch")
    with zipfile.ZipFile(args.candidate_zip, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("DIAG03 ZIP CRC failure")

    safe_recreate_directory(args.work_root, args.work_root.parent)
    source_root = args.work_root / "source"
    candidate_root = args.work_root / "candidate"
    source_root.mkdir()
    candidate_root.mkdir()
    extract_zip_safely(args.source_zip, source_root)
    extract_zip_safely(args.candidate_zip, candidate_root)
    source_files = files(source_root)
    candidate_files = files(candidate_root)
    if set(source_files) != set(candidate_files):
        raise RuntimeError("DIAG03 changed the formal V1.14 member set")

    root_texts = [name for name in source_files if "/" not in name and name.lower().endswith(".txt")]
    if len(root_texts) != 1:
        raise RuntimeError("expected one root installation text")
    changed = {
        name for name in source_files
        if sha256(source_files[name]) != sha256(candidate_files[name])
    }
    expected_changed = set(EXE_NAMES) | {root_texts[0]}
    if changed != expected_changed:
        raise RuntimeError(f"unexpected DIAG03 changed files: {sorted(changed)}")

    # This is the central isolation claim: every non-EXE/non-text member,
    # including all DEF and PCX resources, must be byte-identical to V1.14.
    preserved = set(source_files) - expected_changed
    for name in preserved:
        if source_files[name].read_bytes() != candidate_files[name].read_bytes():
            raise RuntimeError(f"DIAG03 resource changed unexpectedly: {name}")

    payload, _ = diag01.build_payload()
    executables = [
        verify_executable(source_files[name], candidate_files[name], payload)
        for name in EXE_NAMES
    ]
    if len({item["diagnostic_tail_sha256"] for item in executables}) != 1:
        raise RuntimeError("standard and HD DIAG03 tails differ")

    install = candidate_files[root_texts[0]].read_text(encoding="utf-8")
    for marker in (
        diag03.BUILD_NAME,
        diag03.LOG_FILENAME,
        "完全撤销所有新英雄头像、特长图标、DEF 和 PCX 修改",
        "不会显示新的高级学术特长图标",
    ):
        if marker not in install:
            raise RuntimeError(f"DIAG03 installation text missing marker: {marker}")

    print(json.dumps({
        "verified": True,
        "build_name": diag03.BUILD_NAME,
        "candidate_zip_sha256": sha256(args.candidate_zip),
        "changed_files": sorted(changed),
        "added_files": [],
        "preserved_non_exe_members": len(preserved),
        "all_graphic_resources_byte_preserved": True,
        "executables": executables,
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
