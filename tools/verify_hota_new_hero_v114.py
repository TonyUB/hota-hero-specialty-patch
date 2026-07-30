#!/usr/bin/env python3
"""Independently verify formal HOTA_NEW_HERO_V1.14."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

import pefile

import build_hota_new_hero_v114 as release
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
    candidate_sha = sha256_file(candidate_zip)
    if source_sha != release.SOURCE_ZIP_SHA256:
        raise RuntimeError("Formal V1.13 ZIP hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("build_name") != release.BUILD_NAME or not manifest.get("formal_release"):
        raise RuntimeError("V1.14 manifest identity mismatch")
    if manifest.get("source_zip_sha256") != source_sha:
        raise RuntimeError("V1.14 manifest source hash mismatch")
    if manifest.get("zip_sha256") != candidate_sha:
        raise RuntimeError("V1.14 ZIP differs from manifest")
    if manifest.get("formula") != release.FORMULA_EXPRESSION:
        raise RuntimeError("V1.14 Cure formula mismatch")

    with zipfile.ZipFile(source_zip) as archive:
        source_members = sorted(archive.namelist())
    with zipfile.ZipFile(candidate_zip) as archive:
        candidate_members = sorted(archive.namelist())
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"V1.14 ZIP CRC failure: {failed}")
    if source_members != candidate_members:
        raise RuntimeError("V1.14 ZIP member set differs from V1.13")

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
        raise RuntimeError("V1.14 extracted member set differs from V1.13")

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
        raise RuntimeError(f"Unexpected V1.14 changed-file set: {sorted(changed)}")

    melodia_after, daremyth_after = release.v114_records()
    for name in EXE_NAMES:
        source = source_files[name].read_bytes()
        candidate = candidate_files[name].read_bytes()
        if hashlib.sha256(source).hexdigest() != release.SOURCE_EXE_SHA256[name]:
            raise RuntimeError(f"Unexpected V1.13 source EXE hash for {name}")

        ms = release.MELODIA_RECORD_OFFSET
        me = ms + len(release.MELODIA_V113_RECORD)
        ds = release.DAREMYTH_RECORD_OFFSET
        de = ds + len(release.DAREMYTH_V113_RECORD)
        if source[ms:me] != release.MELODIA_V113_RECORD:
            raise RuntimeError(f"Unexpected V1.13 Melodia record for {name}")
        if source[ds:de] != release.DAREMYTH_V113_RECORD:
            raise RuntimeError(f"Unexpected V1.13 Daremyth record for {name}")
        if candidate[ms:me] != melodia_after:
            raise RuntimeError(f"Unexpected V1.14 Melodia record for {name}")
        if candidate[ds:de] != daremyth_after:
            raise RuntimeError(f"Unexpected V1.14 Daremyth record for {name}")
        if struct.unpack_from("<I", candidate, ms + release.SECONDARY_SKILL_2_OFFSET)[0] != release.LEADERSHIP_SKILL_ID:
            raise RuntimeError(f"Melodia does not start with Basic Leadership in {name}")
        if struct.unpack_from("<I", candidate, ds + release.STARTING_SPELL_OFFSET)[0] != release.VIEW_AIR_SPELL_ID:
            raise RuntimeError(f"Daremyth does not start with View Air in {name}")

        parsed = pefile.PE(data=candidate, fast_load=False)
        if parsed.verify_checksum() is not True:
            raise RuntimeError(f"Invalid PE checksum for {name}")
        checksum_offset = parsed.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
        permitted = set(range(
            ms + release.SECONDARY_SKILL_2_OFFSET,
            ms + release.SECONDARY_SKILL_2_OFFSET + 4,
        ))
        permitted.update(range(
            ds + release.STARTING_SPELL_OFFSET,
            ds + release.STARTING_SPELL_OFFSET + 4,
        ))
        permitted.update(range(checksum_offset, checksum_offset + 4))
        actual = {
            offset for offset, (left, right) in enumerate(zip(source, candidate))
            if left != right
        }
        if not actual or not actual.issubset(permitted):
            raise RuntimeError(f"Unexpected EXE byte differences for {name}")

        rollback = bytearray(candidate)
        rollback[ms:me] = release.MELODIA_V113_RECORD
        rollback[ds:de] = release.DAREMYTH_V113_RECORD
        rollback[checksum_offset:checksum_offset + 4] = source[checksum_offset:checksum_offset + 4]
        if bytes(rollback) != source:
            raise RuntimeError(f"Independent rollback failed for {name}")

    install_text = candidate_files[root_texts[0]].read_text(encoding="utf-8")
    required = [
        release.BUILD_NAME,
        "马洛迪亚的初始二级技能由初级智慧术 + 初级神秘术改为初级智慧术 + 初级领导术",
        "魔法书初始法术由魔法神箭改为观天",
        "马洛迪亚：初级智慧术 + 初级领导术；魔法书初始自带振奋",
        "黛瑞丝：初级智慧术 + 初级智力；魔法书初始自带观天",
        "正式 V1.13 保持一致",
    ]
    missing = [value for value in required if value not in install_text]
    if missing:
        raise RuntimeError(f"V1.14 installation text is incomplete: {missing}")

    source_hashes = {name: sha256_file(path) for name, path in source_files.items()}
    candidate_hashes = {name: sha256_file(path) for name, path in candidate_files.items()}
    if manifest.get("source_file_hashes") != source_hashes:
        raise RuntimeError("V1.14 manifest source hashes mismatch")
    if manifest.get("package_file_hashes") != candidate_hashes:
        raise RuntimeError("V1.14 manifest output hashes mismatch")
    if manifest.get("changed_package_files") != sorted(changed):
        raise RuntimeError("V1.14 manifest changed-file list mismatch")

    print(json.dumps({
        "verified": True,
        "formal_release": release.BUILD_NAME,
        "source_zip_sha256": source_sha,
        "candidate_zip_sha256": candidate_sha,
        "changed_files": sorted(changed),
        "melodia_secondary_skill_2": "Basic Leadership (6)",
        "daremyth_starting_spell": "View Air (5)",
        "pe_checksums_valid": True,
        "full_rollback_verified": True,
        "zip_crc_passed": True,
        "manifest_hashes_match": True,
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
