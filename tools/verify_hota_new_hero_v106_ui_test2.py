#!/usr/bin/env python3
"""Independently verify HOTA_NEW_HERO_V1.06_UI_TEST2."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import pefile

from build_hota_new_hero_v1 import extract_zip_safely, safe_recreate_directory
import build_hota_new_hero_v106_ui_test2 as test2


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def verify_dll(source_path: Path, candidate_path: Path) -> dict[str, object]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    if sha256_bytes(source) != test2.SOURCE_HOTA_DLL_SHA256:
        raise RuntimeError("Bad formal HotA.dll source hash")
    if len(candidate) != len(source) + test2.SECTION_SIZE:
        raise RuntimeError("Bad UI-test HotA.dll size")
    source_pe = pefile.PE(data=source, fast_load=False)
    candidate_pe = pefile.PE(data=candidate, fast_load=False)
    if source_pe.FILE_HEADER.NumberOfSections != 6 or candidate_pe.FILE_HEADER.NumberOfSections != 7:
        raise RuntimeError("Unexpected source/candidate section count")
    section_rva = source_pe.OPTIONAL_HEADER.SizeOfImage
    section_va = source_pe.OPTIONAL_HEADER.ImageBase + section_rva
    payload, _ = test2.build_payload(section_va)
    section = candidate_pe.sections[-1]
    if (
        section.Name != test2.DIAG_SECTION_NAME
        or section.Misc_VirtualSize != test2.SECTION_SIZE
        or section.VirtualAddress != section_rva
        or section.SizeOfRawData != test2.SECTION_SIZE
        or section.PointerToRawData != len(source)
        or section.Characteristics != test2.SECTION_CHARACTERISTICS
    ):
        raise RuntimeError("Bad HotA.dll UI section metadata")
    if candidate[len(source) :] != payload:
        raise RuntimeError("Bad HotA.dll UI payload")

    hover_offset = source_pe.get_offset_from_rva(test2.HOVER_PATCH_VA - source_pe.OPTIONAL_HEADER.ImageBase)
    book_offset = source_pe.get_offset_from_rva(test2.BOOK_PATCH_VA - source_pe.OPTIONAL_HEADER.ImageBase)
    expected_hover = (
        test2.relative_call(test2.HOVER_PATCH_VA, section_va + test2.HOVER_HELPER_OFFSET)
        + bytes.fromhex("89 C6")
    ).ljust(len(test2.HOVER_ORIGINAL), b"\x90")
    expected_book = test2.relative_jump(
        test2.BOOK_PATCH_VA,
        section_va + test2.BOOK_HELPER_OFFSET,
    )
    if source[hover_offset : hover_offset + len(test2.HOVER_ORIGINAL)] != test2.HOVER_ORIGINAL:
        raise RuntimeError("Bad formal hover source")
    if candidate[hover_offset : hover_offset + len(expected_hover)] != expected_hover:
        raise RuntimeError("Bad living-hover hook")
    if source[book_offset : book_offset + len(test2.BOOK_ORIGINAL)] != test2.BOOK_ORIGINAL:
        raise RuntimeError("Bad formal book source")
    if candidate[book_offset : book_offset + len(expected_book)] != expected_book:
        raise RuntimeError("Bad spell-book hook")

    pe_offset = source_pe.DOS_HEADER.e_lfanew
    section_table_end = (
        pe_offset + 24 + source_pe.FILE_HEADER.SizeOfOptionalHeader
        + source_pe.FILE_HEADER.NumberOfSections * 40
    )
    field_ranges = [
        (hover_offset, len(test2.HOVER_ORIGINAL)),
        (book_offset, len(test2.BOOK_ORIGINAL)),
        (section_table_end, 40),
        (pe_offset + 6, 2),
        (source_pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfCode"), 4),
        (source_pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfImage"), 4),
        (source_pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum"), 4),
    ]
    allowed = {
        index for start, length in field_ranges for index in range(start, start + length)
    }
    unexpected = [
        index
        for index, (before, after) in enumerate(zip(source, candidate[: len(source)], strict=True))
        if before != after and index not in allowed
    ]
    if unexpected:
        raise RuntimeError(f"Unexpected common-image changes: {unexpected[:8]}")
    restored = bytearray(candidate[: len(source)])
    for start, length in field_ranges:
        restored[start : start + length] = source[start : start + length]
    if bytes(restored) != source:
        raise RuntimeError("Exact HotA.dll rollback failed")
    return {
        "sha256": sha256_bytes(candidate),
        "size": len(candidate),
        "payload_sha256": sha256_bytes(payload),
        "rollback_exact": True,
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
    if sha256_file(source_zip) != test2.SOURCE_ZIP_SHA256:
        raise RuntimeError("Formal V1.05 ZIP hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["build_name"] != test2.BUILD_NAME:
        raise RuntimeError("Manifest build name mismatch")
    if manifest["zip_sha256"] != sha256_file(candidate_zip):
        raise RuntimeError("Candidate ZIP hash does not match manifest")
    with zipfile.ZipFile(candidate_zip, "r") as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"Candidate ZIP CRC failure: {bad_member}")

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
        raise RuntimeError("Candidate member set differs from formal V1.05")

    root_texts = [name for name in source_files if "/" not in name and name.lower().endswith(".txt")]
    if len(root_texts) != 1:
        raise RuntimeError("Expected one root installation text")
    changed = {
        name for name in source_files
        if sha256_file(source_files[name]) != sha256_file(candidate_files[name])
    }
    allowed = {test2.HOTA_DLL_NAME, root_texts[0]}
    if changed != allowed:
        raise RuntimeError(f"Unexpected package changes: {sorted(changed)}")

    test2.validate_formula_helpers(candidate_root)
    dll_report = verify_dll(
        source_files[test2.HOTA_DLL_NAME],
        candidate_files[test2.HOTA_DLL_NAME],
    )
    print(json.dumps({
        "verified": True,
        "candidate_zip_sha256": sha256_file(candidate_zip),
        "changed_files": sorted(changed),
        "hota_dll": dll_report,
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
