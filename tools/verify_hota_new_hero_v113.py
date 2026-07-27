#!/usr/bin/env python3
"""Independently verify formal HOTA_NEW_HERO_V1.13."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

import pefile

import build_hota_new_hero_v113 as release
from build_hota_new_hero_v1 import EXE_NAMES, extract_zip_safely, safe_recreate_directory


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
        raise RuntimeError("Formal V1.12 ZIP hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidate_sha = sha256_file(candidate_zip)
    if manifest.get("build_name") != release.BUILD_NAME or not manifest.get("formal_release"):
        raise RuntimeError("V1.13 manifest identity mismatch")
    if manifest.get("source_zip_sha256") != source_sha:
        raise RuntimeError("V1.13 manifest source hash mismatch")
    if manifest.get("zip_sha256") != candidate_sha:
        raise RuntimeError("V1.13 ZIP hash differs from manifest")
    if manifest.get("formula") != release.FORMULA_EXPRESSION:
        raise RuntimeError("V1.13 Cure formula mismatch")

    with zipfile.ZipFile(source_zip, "r") as archive:
        source_members = sorted(archive.namelist())
    with zipfile.ZipFile(candidate_zip, "r") as archive:
        candidate_members = sorted(archive.namelist())
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"V1.13 ZIP CRC failure: {failed}")
    if source_members != candidate_members:
        raise RuntimeError("V1.13 ZIP member set differs from V1.12")

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
        raise RuntimeError("V1.13 extracted member set differs from V1.12")

    root_texts = [
        relative for relative in candidate_files
        if "/" not in relative and relative.lower().endswith(".txt")
    ]
    if len(root_texts) != 1:
        raise RuntimeError("Expected exactly one root installation text")
    changed = {
        relative for relative in source_files
        if source_files[relative].read_bytes() != candidate_files[relative].read_bytes()
    }
    expected_changed = set(EXE_NAMES) | {root_texts[0]}
    if changed != expected_changed:
        raise RuntimeError(f"Unexpected V1.13 changed-file set: {sorted(changed)}")

    expected_record = release.daremyth_v113_record()
    for name in EXE_NAMES:
        source = source_files[name].read_bytes()
        candidate = candidate_files[name].read_bytes()
        if hashlib.sha256(source).hexdigest() != release.SOURCE_EXE_SHA256[name]:
            raise RuntimeError(f"Unexpected V1.12 source EXE hash for {name}")
        start = release.DAREMYTH_RECORD_OFFSET
        end = start + len(release.DAREMYTH_V112_RECORD)
        if source[start:end] != release.DAREMYTH_V112_RECORD:
            raise RuntimeError(f"Unexpected V1.12 Daremyth record for {name}")
        if candidate[start:end] != expected_record:
            raise RuntimeError(f"Unexpected V1.13 Daremyth record for {name}")
        if struct.unpack_from("<I", candidate, start + release.STARTING_SPELL_OFFSET)[0] != release.MAGIC_ARROW_SPELL_ID:
            raise RuntimeError(f"Daremyth does not start with Magic Arrow in {name}")
        for offset in (0x0C, 0x10, 0x14, 0x18, 0x1C):
            if candidate[start + offset:start + offset + 4] != source[start + offset:start + offset + 4]:
                raise RuntimeError(f"Daremyth skill/spellbook field changed at +0x{offset:X} in {name}")
        parsed = pefile.PE(data=candidate, fast_load=False)
        if parsed.verify_checksum() is not True:
            raise RuntimeError(f"Invalid PE checksum for {name}")
        checksum_offset = parsed.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
        permitted = set(range(start + release.STARTING_SPELL_OFFSET, start + release.STARTING_SPELL_OFFSET + 4))
        permitted.update(range(checksum_offset, checksum_offset + 4))
        actual = {index for index, (left, right) in enumerate(zip(source, candidate)) if left != right}
        if not actual or not actual.issubset(permitted):
            raise RuntimeError(f"Unexpected EXE byte differences for {name}")
        rollback = bytearray(candidate)
        rollback[start:end] = release.DAREMYTH_V112_RECORD
        rollback[checksum_offset:checksum_offset + 4] = source[checksum_offset:checksum_offset + 4]
        if bytes(rollback) != source:
            raise RuntimeError(f"Independent rollback failed for {name}")

    install_text = candidate_files[root_texts[0]].read_text(encoding="utf-8")
    required = [
        release.BUILD_NAME,
        "黛瑞丝的初始二级技能保持初级智慧术 + 初级智力",
        "魔法书初始法术由振奋改为魔法神箭",
        "魔法书初始自带魔法神箭",
        "正式 V1.12 保持一致",
    ]
    missing = [value for value in required if value not in install_text]
    if missing:
        raise RuntimeError(f"V1.13 installation text is incomplete: {missing}")

    source_hashes = {name: sha256_file(path) for name, path in source_files.items()}
    candidate_hashes = {name: sha256_file(path) for name, path in candidate_files.items()}
    if manifest.get("source_file_hashes") != source_hashes:
        raise RuntimeError("V1.13 manifest source hashes mismatch")
    if manifest.get("package_file_hashes") != candidate_hashes:
        raise RuntimeError("V1.13 manifest output hashes mismatch")
    if manifest.get("changed_package_files") != sorted(changed):
        raise RuntimeError("V1.13 manifest changed-file list mismatch")

    print(json.dumps({
        "verified": True,
        "formal_release": release.BUILD_NAME,
        "source_zip_sha256": source_sha,
        "candidate_zip_sha256": candidate_sha,
        "candidate_zip_size": candidate_zip.stat().st_size,
        "changed_files": sorted(changed),
        "daremyth_starting_spell": "Magic Arrow (15)",
        "secondary_skills_and_spellbook_flag_unchanged": True,
        "pe_checksums_valid": True,
        "full_rollback_verified": True,
        "zip_crc_passed": True,
        "manifest_hashes_match": True,
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
