#!/usr/bin/env python3
"""Verify HOTA_NEW_HERO_V1 release invariants."""

from __future__ import annotations

import argparse
import json
import struct
import zipfile
from pathlib import Path

from build_hota_new_hero_v1 import (
    ADELA_CAVE_OFFSET,
    ADELA_HOOK_OFFSET,
    ADELA_NATIVE_CAVE,
    ADELA_NATIVE_HOOK,
    EXE_NAMES,
    HERO_SPEC_ENTRY,
    LANGUAGE_ARCHIVES,
    ORIGINAL_BLESS_TEXT,
    PERMANENT_RESURRECTION_TEXT,
    RELEASE_CURE_TEXT,
    RELEASE_NAME,
    SOURCE_CURE_TEXT,
    SOURCE_ZIP_SHA256,
    sha256_file,
)
from extract_lod import parse_entries, payload


ELF_SPECIALTY_OFFSET = 0x00279A28
ELF_SPEED_HOOK_OFFSET = 0x000E65DC
ELF_SPEED_CAVE_OFFSET = 0x00239D00
ELF_SPEED_HOOK = bytes.fromhex("E9 1F 37 15 00 90 90 90 90 90 90")
ELF_SPEED_CAVE = bytes.fromhex(
    "8B 48 1A 81 F9 9B 00 00 00 0F 84 D8 C8 EA FF "
    "81 F9 8D 00 00 00 0F 84 CC C8 EA FF E9 CA C8 EA FF"
)


def hero_spec_member(archive_path: Path) -> bytes:
    data = archive_path.read_bytes()
    matches = [
        item
        for item in parse_entries(data)
        if str(item["name"]).lower() == HERO_SPEC_ENTRY.lower()
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {HERO_SPEC_ENTRY} in {archive_path}")
    return payload(data, matches[0])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--release-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reproducible-zip", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    release_root = args.release_root.resolve()
    release_zip = args.release_zip.resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    if args.source_zip and sha256_file(args.source_zip.resolve()) != SOURCE_ZIP_SHA256:
        raise RuntimeError("Source v2.6 hash mismatch")
    if manifest["build_name"] != RELEASE_NAME:
        raise RuntimeError("Unexpected release name")
    if sha256_file(release_zip) != manifest["zip_sha256"]:
        raise RuntimeError("Release ZIP hash mismatch")
    if args.reproducible_zip and sha256_file(args.reproducible_zip) != manifest["zip_sha256"]:
        raise RuntimeError("Independent build is not reproducible")

    for name in EXE_NAMES:
        path = release_root / name
        data = path.read_bytes()
        if data[ADELA_HOOK_OFFSET : ADELA_HOOK_OFFSET + len(ADELA_NATIVE_HOOK)] != ADELA_NATIVE_HOOK:
            raise RuntimeError(f"{name}: Adela native epilogue not restored")
        if data[ADELA_CAVE_OFFSET : ADELA_CAVE_OFFSET + len(ADELA_NATIVE_CAVE)] != ADELA_NATIVE_CAVE:
            raise RuntimeError(f"{name}: Adela code cave not cleared")
        if data[ELF_SPEED_HOOK_OFFSET : ELF_SPEED_HOOK_OFFSET + len(ELF_SPEED_HOOK)] != ELF_SPEED_HOOK:
            raise RuntimeError(f"{name}: Elf speed hook changed")
        if data[ELF_SPEED_CAVE_OFFSET : ELF_SPEED_CAVE_OFFSET + len(ELF_SPEED_CAVE)] != ELF_SPEED_CAVE:
            raise RuntimeError(f"{name}: Elf speed helper changed")
        elf_record = struct.unpack_from("<10i", data, ELF_SPECIALTY_OFFSET)
        if elf_record != (4, 118, 0, 0, 1, 0, 0, 0, 0, 0):
            raise RuntimeError(f"{name}: Elf specialty record changed: {elf_record}")
        expected_hash = next(
            item["output_sha256"] for item in manifest["executables"] if item["name"] == name
        )
        if sha256_file(path) != expected_hash:
            raise RuntimeError(f"{name}: manifest hash mismatch")
        print(f"{name}: Adela native + Elf preserved=PASS")

    release_cure = RELEASE_CURE_TEXT.encode("gb18030")
    source_cure = SOURCE_CURE_TEXT.encode("gb18030")
    resurrection = PERMANENT_RESURRECTION_TEXT.encode("gb18030")
    bless = ORIGINAL_BLESS_TEXT.encode("gb18030")
    zero_cost = "施放祝福时不消耗魔法值。".encode("gb18030")
    for relative in LANGUAGE_ARCHIVES:
        member = hero_spec_member(release_root / relative)
        if member.count(release_cure) != 1:
            raise RuntimeError(f"{relative}: full Cure text mismatch")
        if source_cure in member or member.count(resurrection) != 1:
            raise RuntimeError(f"{relative}: Cure text order/duplication mismatch")
        if member.count(bless) != 1 or zero_cost in member:
            raise RuntimeError(f"{relative}: Adela text not restored")
        print(f"{relative}: Cure + Bless text=PASS")

    package_members = sorted(
        path.relative_to(release_root).as_posix()
        for path in release_root.rglob("*")
        if path.is_file()
    )
    with zipfile.ZipFile(release_zip, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Release ZIP CRC failure")
        if sorted(archive.namelist()) != package_members:
            raise RuntimeError("Release ZIP member mismatch")
    if sorted(manifest["package_file_hashes"]) != package_members:
        raise RuntimeError("Manifest member mismatch")
    for relative, expected_hash in manifest["package_file_hashes"].items():
        if sha256_file(release_root / relative) != expected_hash:
            raise RuntimeError(f"Package hash mismatch: {relative}")
    print("ZIP CRC/member/hash verification=PASS")
    if args.reproducible_zip:
        print("Reproducible build=PASS")
    print(f"ZIP SHA-256 {manifest['zip_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
