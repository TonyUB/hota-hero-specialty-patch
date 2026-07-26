#!/usr/bin/env python3
"""Independently verify formal HOTA_NEW_HERO_V1.1."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import build_hota_new_hero_v11 as release
import build_hota_new_hero_v11_luck_test1 as test1
from build_hota_new_hero_v1 import EXE_NAMES, extract_zip_safely, safe_recreate_directory
from verify_hota_new_hero_v11_luck_test1 import (
    ALLOWED_CHANGED,
    sha256_file,
    verify_executable,
    verify_lod,
    verify_loose,
    zip_members,
)


def files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*") if path.is_file()
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--accepted-test-zip", type=Path, required=True)
    parser.add_argument("--candidate-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_zip = args.source_zip.resolve()
    accepted_zip = args.accepted_test_zip.resolve()
    candidate_zip = args.candidate_zip.resolve()
    manifest_path = args.manifest.resolve()
    work_root = args.work_root.resolve()
    if sha256_file(source_zip) != test1.SOURCE_ZIP_SHA256:
        raise RuntimeError("Formal V1.06 ZIP hash mismatch")
    if sha256_file(accepted_zip) != release.ACCEPTED_TEST_ZIP_SHA256:
        raise RuntimeError("Accepted LUCK_TEST1 ZIP hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("build_name") != release.BUILD_NAME or not manifest.get("formal_release"):
        raise RuntimeError("Formal manifest identity mismatch")
    if manifest.get("zip_sha256") != sha256_file(candidate_zip):
        raise RuntimeError("Formal ZIP hash differs from manifest")
    if manifest.get("accepted_test_zip_sha256") != release.ACCEPTED_TEST_ZIP_SHA256:
        raise RuntimeError("Accepted test identity mismatch")
    if zip_members(source_zip) != zip_members(candidate_zip):
        raise RuntimeError("Formal member set differs from V1.06")
    with zipfile.ZipFile(candidate_zip, "r") as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"Formal ZIP CRC failure: {failed}")

    safe_recreate_directory(work_root, work_root.parent)
    roots = {
        "source": work_root / "source",
        "accepted": work_root / "accepted",
        "candidate": work_root / "candidate",
    }
    for root in roots.values():
        root.mkdir()
    extract_zip_safely(source_zip, roots["source"])
    extract_zip_safely(accepted_zip, roots["accepted"])
    extract_zip_safely(candidate_zip, roots["candidate"])
    source_files = files(roots["source"])
    accepted_files = files(roots["accepted"])
    candidate_files = files(roots["candidate"])
    if set(source_files) != set(accepted_files) or set(source_files) != set(candidate_files):
        raise RuntimeError("Source, accepted test, and formal member sets differ")

    changed = {
        name for name in source_files
        if sha256_file(source_files[name]) != sha256_file(candidate_files[name])
    }
    if changed != ALLOWED_CHANGED:
        raise RuntimeError(f"Unexpected formal changed-file set: {sorted(changed)}")
    runtime_resources = set(release.ACCEPTED_RUNTIME_HASHES)
    for relative in runtime_resources:
        accepted = accepted_files[relative].read_bytes()
        candidate = candidate_files[relative].read_bytes()
        if candidate != accepted:
            raise RuntimeError(f"Formal file differs from user-accepted test: {relative}")
        if sha256_file(candidate_files[relative]) != release.ACCEPTED_RUNTIME_HASHES[relative]:
            raise RuntimeError(f"Formal accepted hash mismatch: {relative}")

    executable_reports = {
        name: verify_executable(source_files[name], candidate_files[name])
        for name in EXE_NAMES
    }
    lod_reports = {
        relative: verify_lod(source_files[relative], candidate_files[relative])
        for relative in ("Data/HotA_lng.lod", "Data/HotA_l_ext.lod")
    }
    loose_report = verify_loose(
        source_files[test1.LOOSE_HEROSPEC_RELATIVE],
        candidate_files[test1.LOOSE_HEROSPEC_RELATIVE],
    )
    root_texts = [name for name in candidate_files if "/" not in name and name.lower().endswith(".txt")]
    if len(root_texts) != 1:
        raise RuntimeError("Expected exactly one root installation text")
    for relative in candidate_files:
        if relative == root_texts[0]:
            continue
        if candidate_files[relative].read_bytes() != accepted_files[relative].read_bytes():
            raise RuntimeError(f"Formal non-instruction file differs from accepted test: {relative}")
    install_text = candidate_files[root_texts[0]].read_text(encoding="utf-8")
    required_text = [
        release.BUILD_NAME,
        "马洛迪亚",
        "黛瑞丝",
        "初级神秘术",
        "振奋",
        "厄运沙漏",
        "V1.06",
    ]
    if any(value not in install_text for value in required_text):
        raise RuntimeError("Formal installation text is incomplete")
    candidate_hashes = {
        name: sha256_file(path) for name, path in candidate_files.items()
    }
    if manifest.get("package_file_hashes") != candidate_hashes:
        raise RuntimeError("Formal manifest package hashes mismatch")
    if manifest.get("changed_package_files") != sorted(changed):
        raise RuntimeError("Formal manifest changed-file list mismatch")

    print(json.dumps({
        "verified": True,
        "formal_release": release.BUILD_NAME,
        "candidate_zip_sha256": sha256_file(candidate_zip),
        "changed_files": sorted(changed),
        "accepted_gameplay_and_resources_byte_identical": True,
        "all_non_instruction_files_match_accepted_test": True,
        "executables": executable_reports,
        "lods": lod_reports,
        "loose_herospec": loose_report,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
