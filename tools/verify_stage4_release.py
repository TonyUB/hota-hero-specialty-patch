#!/usr/bin/env python3
"""Verify formal Patch_v2.6 reproducibility and TEST13 byte preservation."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from build_diag_patch import EXE_NAMES, sha256_file
from build_stage4_release import (
    ACCEPTED_TEST_ZIP_SHA256,
    CONCISE_RESURRECTION_TEXT,
    HERO_SPEC_ENTRY,
    LANGUAGE_ARCHIVES,
    RELEASE_CURE_TEXT,
    RELEASE_NAME,
)
from extract_lod import parse_entries, payload


ROOT = Path(__file__).resolve().parent.parent
OLD_FORMAL_V25_SHA256 = (
    "cb7cc074219d0934b90b2fd3d06885786adb56f1f1d0d27f757b1bb2df5193e9"
)


def files_under(root: Path) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())


def main() -> int:
    first_root = ROOT / "build" / "release26_a" / RELEASE_NAME
    second_root = ROOT / "build" / "release26_b" / RELEASE_NAME
    test_root = ROOT / "build" / "test13_a" / "Patch_v2.6_VISUAL_TEST13"
    first_zip = ROOT / "outputs" / "release26_a" / f"{RELEASE_NAME}.zip"
    second_zip = ROOT / "outputs" / "release26_b" / f"{RELEASE_NAME}.zip"
    manifest = json.loads(
        (
            ROOT / "outputs" / "release26_a" / f"{RELEASE_NAME}_manifest.json"
        ).read_text(encoding="utf-8")
    )

    first_files = files_under(first_root)
    second_files = files_under(second_root)
    test_files = files_under(test_root)
    if first_files != second_files or first_files != test_files:
        raise RuntimeError("Release/test package member sets differ")
    for relative in first_files:
        first = (first_root / relative).read_bytes()
        second = (second_root / relative).read_bytes()
        if first != second:
            raise RuntimeError(f"Reproducible release mismatch: {relative}")
        test = (test_root / relative).read_bytes()
        if relative.as_posix() not in LANGUAGE_ARCHIVES and first != test:
            raise RuntimeError(f"Unexpected release delta from TEST13: {relative}")

    if first_zip.read_bytes() != second_zip.read_bytes():
        raise RuntimeError("Reproducible release ZIP bytes differ")
    with zipfile.ZipFile(first_zip) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"ZIP CRC failure: {bad_member}")
        if sorted(archive.namelist()) != sorted(path.as_posix() for path in first_files):
            raise RuntimeError("ZIP member set differs from release package")

    concise = CONCISE_RESURRECTION_TEXT.encode("gb18030")
    full = RELEASE_CURE_TEXT.encode("gb18030")
    for relative in LANGUAGE_ARCHIVES:
        archive_bytes = (first_root / relative).read_bytes()
        entry = next(
            item
            for item in parse_entries(archive_bytes)
            if str(item["name"]).lower() == HERO_SPEC_ENTRY.lower()
        )
        member = payload(archive_bytes, entry)
        if member.count(full) != 1 or member.count(concise) != 1:
            raise RuntimeError(f"Concise HeroSpec sentence mismatch: {relative}")
        print(f"{relative}: HeroSpec concise text=PASS")

    for executable in EXE_NAMES:
        if (first_root / executable).read_bytes() != (test_root / executable).read_bytes():
            raise RuntimeError(f"Accepted TEST13 executable changed: {executable}")
    if any(path.name.startswith("hota_cure_") for path in first_root.rglob("*")):
        raise RuntimeError("Runtime diagnostic file was packaged")

    if manifest["source_test_zip_sha256"] != ACCEPTED_TEST_ZIP_SHA256:
        raise RuntimeError("Accepted TEST13 hash changed in manifest")
    if manifest.get("runtime_acceptance_required"):
        raise RuntimeError("Formal release still requires runtime acceptance")
    if not all(manifest["runtime_acceptance"].values()):
        raise RuntimeError("Not every runtime acceptance gate is marked passed")
    for relative, expected_hash in manifest["package_file_hashes"].items():
        if sha256_file(first_root / relative) != expected_hash:
            raise RuntimeError(f"Manifest package hash mismatch: {relative}")

    old_formal = ROOT / "OLD" / "Patch_v2.5.zip"
    old_hash = hashlib.sha256(old_formal.read_bytes()).hexdigest()
    if old_hash != OLD_FORMAL_V25_SHA256:
        raise RuntimeError("Existing formal Patch_v2.5.zip changed before archival")
    release_hash = hashlib.sha256(first_zip.read_bytes()).hexdigest()
    print("Reproducible formal build: PASS")
    print("TEST13 executable byte identity: PASS")
    print("Only two language archives changed from TEST13: PASS")
    print("ZIP members and CRC: PASS")
    print(f"Existing v2.5 before archival: {old_hash}")
    print(f"Patch_v2.6 ZIP SHA-256: {release_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
