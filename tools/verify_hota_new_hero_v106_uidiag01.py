#!/usr/bin/env python3
"""Independently verify the isolated Cure UI diagnostic package."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import pefile

from build_hota_new_hero_v1 import EXE_NAMES, extract_zip_safely, safe_recreate_directory
from build_hota_new_hero_v106_uidiag01 import (
    BUILD_NAME,
    DIAG_SECTION_CHARACTERISTICS,
    DIAG_SECTION_NAME,
    DIAG_SECTION_RVA,
    DIAG_SECTION_SIZE,
    EXPECTED_NEW_SECTION_HEADER_SLOT,
    NATIVE_EFFECT_ORIGINAL,
    NATIVE_EFFECT_VA,
    SOURCE_EXE_SHA256,
    SOURCE_ZIP_SHA256,
    WRAPPER_VA,
    build_payload,
    relative_jump,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def verify_executable(source_path: Path, candidate_path: Path, payload: bytes) -> dict[str, object]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    if sha256_bytes(source) != SOURCE_EXE_SHA256[source_path.name]:
        raise RuntimeError(f"Bad formal source hash: {source_path.name}")
    if len(candidate) != len(source) + DIAG_SECTION_SIZE:
        raise RuntimeError(f"Bad diagnostic size: {candidate_path.name}")

    source_pe = pefile.PE(data=source, fast_load=False)
    candidate_pe = pefile.PE(data=candidate, fast_load=False)
    if source_pe.FILE_HEADER.NumberOfSections != 4:
        raise RuntimeError("Formal source section count changed")
    if candidate_pe.FILE_HEADER.NumberOfSections != 5:
        raise RuntimeError("Diagnostic section count is not five")
    section = candidate_pe.sections[-1]
    if (
        section.Name != DIAG_SECTION_NAME
        or section.Misc_VirtualSize != DIAG_SECTION_SIZE
        or section.VirtualAddress != DIAG_SECTION_RVA
        or section.SizeOfRawData != DIAG_SECTION_SIZE
        or section.PointerToRawData != len(source)
        or section.Characteristics != DIAG_SECTION_CHARACTERISTICS
    ):
        raise RuntimeError(f"Bad diagnostic section metadata: {candidate_path.name}")
    if candidate[len(source) :] != payload:
        raise RuntimeError(f"Bad diagnostic payload: {candidate_path.name}")

    entry_offset = source_pe.get_offset_from_rva(NATIVE_EFFECT_VA - source_pe.OPTIONAL_HEADER.ImageBase)
    hook = relative_jump(NATIVE_EFFECT_VA, WRAPPER_VA) + b"\x90"
    if source[entry_offset : entry_offset + 6] != NATIVE_EFFECT_ORIGINAL:
        raise RuntimeError(f"Bad formal hook source: {source_path.name}")
    if candidate[entry_offset : entry_offset + 6] != hook:
        raise RuntimeError(f"Bad diagnostic hook: {candidate_path.name}")

    pe_offset = source_pe.DOS_HEADER.e_lfanew
    section_table_end = (
        pe_offset
        + 24
        + source_pe.FILE_HEADER.SizeOfOptionalHeader
        + source_pe.FILE_HEADER.NumberOfSections * 40
    )
    if source[section_table_end : section_table_end + 40] != EXPECTED_NEW_SECTION_HEADER_SLOT:
        raise RuntimeError(f"Bad formal fifth section slot: {source_path.name}")
    field_ranges = [
        (entry_offset, 6),
        (section_table_end, 40),
        (pe_offset + 6, 2),
        (source_pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfCode"), 4),
        (source_pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfImage"), 4),
        (source_pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum"), 4),
    ]
    allowed = {
        index
        for start, length in field_ranges
        for index in range(start, start + length)
    }
    unexpected = [
        index
        for index, (before, after) in enumerate(zip(source, candidate[: len(source)], strict=True))
        if before != after and index not in allowed
    ]
    if unexpected:
        raise RuntimeError(
            f"Unexpected common-image byte changes in {candidate_path.name}: {unexpected[:8]}"
        )

    restored = bytearray(candidate[: len(source)])
    for start, length in field_ranges:
        restored[start : start + length] = source[start : start + length]
    if bytes(restored) != source:
        raise RuntimeError(f"Exact rollback failed: {candidate_path.name}")
    return {
        "name": candidate_path.name,
        "sha256": sha256_bytes(candidate),
        "size": len(candidate),
        "hook_file_offset": entry_offset,
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
    if sha256_file(source_zip) != SOURCE_ZIP_SHA256:
        raise RuntimeError("Formal V1.05 ZIP hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["build_name"] != BUILD_NAME:
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
    allowed_changes = set(EXE_NAMES) | {root_texts[0]}
    changed = {
        name
        for name in source_files
        if sha256_file(source_files[name]) != sha256_file(candidate_files[name])
    }
    if changed != allowed_changes:
        raise RuntimeError(f"Unexpected package changes: {sorted(changed)}")

    payload, _ = build_payload()
    reports = [
        verify_executable(source_files[name], candidate_files[name], payload)
        for name in EXE_NAMES
    ]
    if candidate_files[EXE_NAMES[0]].read_bytes()[-DIAG_SECTION_SIZE:] != candidate_files[EXE_NAMES[1]].read_bytes()[-DIAG_SECTION_SIZE:]:
        raise RuntimeError("Standard and HD diagnostic payloads differ")
    print(json.dumps({
        "verified": True,
        "candidate_zip_sha256": sha256_file(candidate_zip),
        "changed_files": sorted(changed),
        "executables": reports,
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
