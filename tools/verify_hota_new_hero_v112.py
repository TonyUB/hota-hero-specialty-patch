#!/usr/bin/env python3
"""Independently verify formal HOTA_NEW_HERO_V1.12."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import tempfile
import zipfile
from pathlib import Path

import pefile

import build_hota_new_hero_v112 as v112
from build_hota_new_hero_v1 import extract_zip_safely
from extract_lod import parse_entries, payload


EXPECTED_CHANGED = {
    "h3hota.exe",
    "h3hota HD.exe",
    "HotA.dll",
    "Data/HotA_lng.lod",
    "Data/HotA_l_ext.lod",
    v112.test1.luck_v11.LOOSE_HEROSPEC_RELATIVE,
    "安装说明.txt",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def relative_target(data: bytes, offset: int, va: int) -> int:
    if data[offset] != 0xE9:
        raise RuntimeError(f"Expected rel32 jump at 0x{va:08X}")
    return va + 5 + struct.unpack_from("<i", data, offset + 1)[0]


def find_herospec(raw: bytes) -> bytes:
    entries = parse_entries(raw)
    matches = [entry for entry in entries if str(entry["name"]).lower() == "herospec.txt"]
    if len(matches) != 1:
        raise RuntimeError("Expected one HeroSpec.txt")
    return payload(raw, matches[0])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    source_zip = args.source_zip.resolve()
    output_zip = args.zip.resolve()
    manifest_path = args.manifest.resolve()
    if sha256_file(source_zip) != v112.SOURCE_ZIP_SHA256:
        raise RuntimeError("V1.11 source ZIP hash mismatch")
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if report["build_name"] != v112.BUILD_NAME or not report["formal_release"]:
        raise RuntimeError("V1.12 manifest identity mismatch")
    if report["zip_sha256"] != sha256_file(output_zip):
        raise RuntimeError("V1.12 ZIP hash differs from manifest")
    if report["formula"] != v112.FORMULA_EXPRESSION:
        raise RuntimeError("Cure formula mismatch")
    if report["specialty_text"]["zh-CN"] != v112.SPECIALTY_ZH:
        raise RuntimeError("Chinese specialty text mismatch")

    with zipfile.ZipFile(output_zip, "r") as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"V1.12 ZIP CRC failure: {failed}")
        output_members = sorted(archive.namelist())
    with zipfile.ZipFile(source_zip, "r") as archive:
        source_members = sorted(archive.namelist())
    if output_members != source_members:
        raise RuntimeError("V1.12 member set differs from V1.11")

    with tempfile.TemporaryDirectory(prefix="hota_v112_verify_") as temporary:
        root = Path(temporary)
        source_root = root / "source"
        output_root = root / "output"
        source_root.mkdir()
        output_root.mkdir()
        extract_zip_safely(source_zip, source_root)
        extract_zip_safely(output_zip, output_root)
        source_hashes = {
            path.relative_to(source_root).as_posix(): sha256_file(path)
            for path in sorted(item for item in source_root.rglob("*") if item.is_file())
        }
        output_hashes = {
            path.relative_to(output_root).as_posix(): sha256_file(path)
            for path in sorted(item for item in output_root.rglob("*") if item.is_file())
        }
        changed = {
            relative for relative in source_hashes
            if source_hashes[relative] != output_hashes[relative]
        }
        if changed != EXPECTED_CHANGED:
            raise RuntimeError(f"Unexpected V1.12 changed files: {sorted(changed ^ EXPECTED_CHANGED)}")

        fixed_pattern = bytes.fromhex("B8 03 00 00 00 5F 5E 89 EC 5D C2 0C 00")
        for name in v112.EXE_NAMES:
            data = (output_root / name).read_bytes()
            pe = pefile.PE(data=data, fast_load=False)
            checks = [
                (v112.test1.LUCK_GATE_HOOK_VA, v112.test1.LUCK_GATE_WRAPPER_VA),
                (v112.test1.BATTLE_RESET_HOOK_VA, v112.test1.RESET_WRAPPER_VA),
                (v112.test1.RANGED_ACTION_HOOK_VA, v112.test1.RANGED_WRAPPER_VA),
                (v112.test1.MELEE_ACTION_HOOK_VA, v112.test1.MELEE_WRAPPER_VA),
            ]
            for va, expected in checks:
                offset = pe.get_offset_from_rva(va - v112.test1.IMAGE_BASE)
                if relative_target(data, offset, va) != expected:
                    raise RuntimeError(f"Unexpected hook target in {name} at 0x{va:08X}")
            section = pe.sections[-1]
            luck = data[
                section.PointerToRawData:section.PointerToRawData + section.SizeOfRawData
            ]
            if fixed_pattern not in luck[:0x200]:
                raise RuntimeError(f"Fixed +3 return path missing in {name}")
            if any(luck[0x200:0x300]):
                raise RuntimeError(f"Diagnostic logger slot is not empty in {name}")
            if b"hota_luck_first" in data:
                raise RuntimeError(f"Diagnostic filename remains in {name}")

        dll = (output_root / v112.test2.diag03.HOTA_DLL_NAME).read_bytes()
        dll_pe = pefile.PE(data=dll, fast_load=False)
        dll_hook_offset = dll_pe.get_offset_from_rva(
            v112.test2.HOTA_LUCK_ROLL_VA - v112.test2.diag03.HOTA_IMAGE_BASE
        )
        if relative_target(dll, dll_hook_offset, v112.test2.HOTA_LUCK_ROLL_VA) != v112.test2.HOTA_LUCK_WRAPPER_VA:
            raise RuntimeError("HotA Luck-roll hook target mismatch")
        if b"hota_luck_first" in dll:
            raise RuntimeError("Diagnostic filename remains in HotA.dll")
        source_dll = (source_root / v112.test2.diag03.HOTA_DLL_NAME).read_bytes()
        if dll[
            v112.test2.diag03.CUREUI_RAW_OFFSET:
            v112.test2.diag03.CUREUI_RAW_OFFSET + v112.test2.diag03.PRESERVED_CUREUI_END
        ] != source_dll[
            v112.test2.diag03.CUREUI_RAW_OFFSET:
            v112.test2.diag03.CUREUI_RAW_OFFSET + v112.test2.diag03.PRESERVED_CUREUI_END
        ]:
            raise RuntimeError("Accepted Cure UI prefix changed")

        for relative in v112.LANGUAGE_ARCHIVES:
            text = find_herospec((output_root / relative).read_bytes()).decode("gb18030")
            if text.count(v112.SPECIALTY_ZH) != 2:
                raise RuntimeError(f"Combined specialty text mismatch in {relative}")
        loose = (
            output_root / v112.test1.luck_v11.LOOSE_HEROSPEC_RELATIVE
        ).read_text(encoding="gb18030")
        if loose.count(v112.SPECIALTY_ZH) != 2:
            raise RuntimeError("Combined specialty text mismatch in loose HeroSpec")
        install = (output_root / "安装说明.txt").read_text(encoding="utf-8")
        for required in (v112.BUILD_NAME, v112.SPECIALTY_ZH, "厄运沙漏", "首次主动攻击"):
            if required not in install:
                raise RuntimeError(f"Installation text missing: {required}")

        if report["source_file_hashes"] != source_hashes:
            raise RuntimeError("Manifest source hashes mismatch")
        if report["package_file_hashes"] != output_hashes:
            raise RuntimeError("Manifest output hashes mismatch")
        if set(report["changed_package_files"]) != changed:
            raise RuntimeError("Manifest changed-file list mismatch")

    print("V1.12 independent verification passed")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    print("Changed files: " + json.dumps(sorted(EXPECTED_CHANGED), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
