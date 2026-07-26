#!/usr/bin/env python3
"""Independently verify formal documentation-only HOTA_NEW_HERO_V1.11."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import build_hota_new_hero_v111 as release
from build_hota_new_hero_v1 import extract_zip_safely, safe_recreate_directory


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*") if path.is_file()
    }


def members(path: Path) -> list[str]:
    with zipfile.ZipFile(path, "r") as archive:
        return sorted(archive.namelist())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--candidate-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_zip = args.source_zip.resolve()
    candidate_zip = args.candidate_zip.resolve()
    manifest_path = args.manifest.resolve()
    work_root = args.work_root.resolve()

    source_sha = sha256_file(source_zip)
    if source_sha != release.SOURCE_ZIP_SHA256:
        raise RuntimeError("Formal V1.1 ZIP hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidate_sha = sha256_file(candidate_zip)
    if manifest.get("build_name") != release.BUILD_NAME:
        raise RuntimeError("V1.11 manifest identity mismatch")
    if not manifest.get("formal_release") or not manifest.get("documentation_only"):
        raise RuntimeError("V1.11 manifest release type mismatch")
    if manifest.get("source_zip_sha256") != source_sha:
        raise RuntimeError("V1.11 manifest source hash mismatch")
    if manifest.get("zip_sha256") != candidate_sha:
        raise RuntimeError("V1.11 ZIP hash differs from manifest")
    if manifest.get("formula") != release.FORMULA_EXPRESSION:
        raise RuntimeError("V1.11 manifest Cure formula mismatch")
    if members(source_zip) != members(candidate_zip):
        raise RuntimeError("V1.11 ZIP member set differs from V1.1")

    with zipfile.ZipFile(candidate_zip, "r") as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"V1.11 ZIP CRC failure: {failed}")

    safe_recreate_directory(work_root, work_root.parent)
    source_root = work_root / "source"
    candidate_root = work_root / "candidate"
    source_root.mkdir()
    candidate_root.mkdir()
    extract_zip_safely(source_zip, source_root)
    extract_zip_safely(candidate_zip, candidate_root)
    source_files = files(source_root)
    candidate_files = files(candidate_root)
    if set(source_files) != set(candidate_files):
        raise RuntimeError("V1.11 extracted member set differs from V1.1")

    changed = {
        relative for relative in source_files
        if source_files[relative].read_bytes() != candidate_files[relative].read_bytes()
    }
    root_texts = [
        relative for relative in candidate_files
        if "/" not in relative and relative.lower().endswith(".txt")
    ]
    if len(root_texts) != 1:
        raise RuntimeError("Expected exactly one root installation text")
    if changed != {root_texts[0]}:
        raise RuntimeError(f"Unexpected V1.11 changed-file set: {sorted(changed)}")

    install_text = candidate_files[root_texts[0]].read_text(encoding="utf-8")
    required_text = [
        release.BUILD_NAME,
        release.SOURCE_NAME,
        "共用一条创作方向",
        "额外说明",
        "厄运沙漏",
        "诅咒之地",
        "全部文件与已验收的正式 V1.1 逐字节一致",
    ]
    missing = [value for value in required_text if value not in install_text]
    if missing:
        raise RuntimeError(f"V1.11 installation text is incomplete: {missing}")

    source_hashes = {name: sha256_file(path) for name, path in source_files.items()}
    candidate_hashes = {name: sha256_file(path) for name, path in candidate_files.items()}
    if manifest.get("source_file_hashes") != source_hashes:
        raise RuntimeError("V1.11 manifest source file hashes mismatch")
    if manifest.get("package_file_hashes") != candidate_hashes:
        raise RuntimeError("V1.11 manifest package file hashes mismatch")
    if manifest.get("changed_package_files") != sorted(changed):
        raise RuntimeError("V1.11 manifest changed-file list mismatch")
    if not manifest.get("gameplay_files_byte_identical_to_source"):
        raise RuntimeError("V1.11 manifest gameplay identity flag missing")

    print(json.dumps({
        "verified": True,
        "formal_release": release.BUILD_NAME,
        "source_zip_sha256": source_sha,
        "candidate_zip_sha256": candidate_sha,
        "candidate_zip_size": candidate_zip.stat().st_size,
        "changed_files": sorted(changed),
        "all_non_instruction_files_match_v11": True,
        "zip_crc_passed": True,
        "manifest_hashes_match": True,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
