#!/usr/bin/env python3
"""Independently verify HOTA_NEW_HERO_V1.2_SCHOLAR_DIAG01."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

import pefile

from build_hota_new_hero_v1 import EXE_NAMES, extract_zip_safely, safe_recreate_directory
import build_hota_new_hero_v12_scholar_diag01 as diag


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def verify_executable(source: Path, candidate: Path, expected_payload: bytes) -> dict[str, object]:
    before = source.read_bytes()
    after = candidate.read_bytes()
    if hashlib.sha256(before).hexdigest() != diag.SOURCE_EXE_SHA256[source.name]:
        raise RuntimeError(f"source EXE hash mismatch: {source.name}")
    if len(after) != len(before) + diag.DIAG_SECTION_SIZE:
        raise RuntimeError(f"candidate EXE size mismatch: {candidate.name}")
    source_pe = pefile.PE(data=before, fast_load=False)
    candidate_pe = pefile.PE(data=after, fast_load=False)
    if source_pe.FILE_HEADER.NumberOfSections != 5 or candidate_pe.FILE_HEADER.NumberOfSections != 6:
        raise RuntimeError(f"section count mismatch: {candidate.name}")
    section = candidate_pe.sections[-1]
    if (
        section.Name != diag.DIAG_SECTION_NAME
        or section.VirtualAddress != diag.DIAG_SECTION_RVA
        or section.SizeOfRawData != diag.DIAG_SECTION_SIZE
    ):
        raise RuntimeError(f"diagnostic section mismatch: {candidate.name}")
    raw = int(section.PointerToRawData)
    if after[raw:raw + diag.DIAG_SECTION_SIZE] != expected_payload:
        raise RuntimeError(f"diagnostic payload mismatch: {candidate.name}")
    hook_offset = source_pe.get_offset_from_rva(diag.SCHOLAR_ENTRY_VA - diag.IMAGE_BASE)
    expected_hook = diag.relative_jump(
        diag.SCHOLAR_ENTRY_VA,
        diag.ENTRY_WRAPPER_VA,
        len(diag.SCHOLAR_ENTRY_ORIGINAL),
    )
    if before[hook_offset:hook_offset + len(diag.SCHOLAR_ENTRY_ORIGINAL)] != diag.SCHOLAR_ENTRY_ORIGINAL:
        raise RuntimeError(f"source Scholar entry mismatch: {source.name}")
    if after[hook_offset:hook_offset + len(expected_hook)] != expected_hook:
        raise RuntimeError(f"candidate Scholar hook mismatch: {candidate.name}")

    pe_offset = source_pe.DOS_HEADER.e_lfanew
    section_header_offset = (
        pe_offset + 24 + source_pe.FILE_HEADER.SizeOfOptionalHeader
        + source_pe.FILE_HEADER.NumberOfSections * 40
    )
    restored = bytearray(after[:len(before)])
    restored[hook_offset:hook_offset + len(diag.SCHOLAR_ENTRY_ORIGINAL)] = diag.SCHOLAR_ENTRY_ORIGINAL
    restored[section_header_offset:section_header_offset + 40] = before[section_header_offset:section_header_offset + 40]
    section_count_offset = pe_offset + 6
    restored[section_count_offset:section_count_offset + 2] = before[section_count_offset:section_count_offset + 2]
    for field in ("SizeOfCode", "SizeOfImage", "CheckSum"):
        offset = source_pe.OPTIONAL_HEADER.get_field_absolute_offset(field)
        restored[offset:offset + 4] = before[offset:offset + 4]
    if bytes(restored) != before:
        raise RuntimeError(f"independent executable rollback failed: {candidate.name}")
    if candidate_pe.verify_checksum() is not True:
        raise RuntimeError(f"candidate checksum invalid: {candidate.name}")
    return {
        "name": candidate.name,
        "source_sha256": hashlib.sha256(before).hexdigest(),
        "candidate_sha256": hashlib.sha256(after).hexdigest(),
        "payload_sha256": hashlib.sha256(expected_payload).hexdigest(),
        "rollback_verified": True,
    }


def d32f_frame_range(data: bytes, index: int) -> tuple[int, int]:
    if data[:4] != b"D32F" or struct.unpack_from("<I", data, 0x28)[0] != 215:
        raise RuntimeError("invalid D32F container")
    offsets = struct.unpack_from("<215I", data, 0x30 + 215 * 13)
    frame_offset = offsets[index]
    header = struct.unpack_from("<8I", data, frame_offset)
    return frame_offset + 32, frame_offset + 32 + header[1]


def verify_d32f(source: Path, candidate: Path, expected_hash: str) -> dict[str, object]:
    before = source.read_bytes()
    after = candidate.read_bytes()
    if hashlib.sha256(before).hexdigest() != expected_hash or len(before) != len(after):
        raise RuntimeError(f"D32F baseline mismatch: {candidate}")
    start, end = d32f_frame_range(before, diag.CORONIUS_ID)
    if before[:start] != after[:start] or before[end:] != after[end:] or before[start:end] == after[start:end]:
        raise RuntimeError(f"D32F Coronius-frame isolation mismatch: {candidate}")
    rollback = bytearray(after)
    rollback[start:end] = before[start:end]
    if bytes(rollback) != before:
        raise RuntimeError(f"D32F rollback mismatch: {candidate}")
    return {
        "relative": candidate.name,
        "source_sha256": hashlib.sha256(before).hexdigest(),
        "candidate_sha256": hashlib.sha256(after).hexdigest(),
        "changed_pixel_offset": start,
        "changed_pixel_length": end - start,
        "all_other_bytes_preserved": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--candidate-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()
    if sha256(args.source_zip) != diag.SOURCE_ZIP_SHA256:
        raise RuntimeError("formal V1.14 source ZIP hash mismatch")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest["build_name"] != diag.BUILD_NAME or not manifest["diagnostic_only"]:
        raise RuntimeError("manifest identity mismatch")
    if sha256(args.candidate_zip) != manifest["zip_sha256"]:
        raise RuntimeError("candidate ZIP hash mismatch")
    with zipfile.ZipFile(args.candidate_zip, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("candidate ZIP CRC failure")

    safe_recreate_directory(args.work_root, args.work_root.parent)
    source_root = args.work_root / "source"
    candidate_root = args.work_root / "candidate"
    source_root.mkdir()
    candidate_root.mkdir()
    extract_zip_safely(args.source_zip, source_root)
    extract_zip_safely(args.candidate_zip, candidate_root)
    source_files = files(source_root)
    candidate_files = files(candidate_root)
    if set(candidate_files) - set(source_files) != {diag.LOOSE_ICON_RELATIVE}:
        raise RuntimeError("unexpected candidate added-member set")
    if not set(source_files).issubset(candidate_files):
        raise RuntimeError("candidate removed formal V1.14 members")
    changed = {
        name for name in source_files if sha256(source_files[name]) != sha256(candidate_files[name])
    }
    root_texts = [name for name in source_files if "/" not in name and name.lower().endswith(".txt")]
    if len(root_texts) != 1:
        raise RuntimeError("expected exactly one root installation text")
    expected_changed = set(EXE_NAMES) | set(diag.D32F_RELATIVES) | {root_texts[0]}
    if changed != expected_changed:
        raise RuntimeError(f"unexpected changed files: {sorted(changed)}")

    payload, _ = diag.build_payload()
    exes = [verify_executable(source_files[name], candidate_files[name], payload) for name in EXE_NAMES]
    if len({item["payload_sha256"] for item in exes}) != 1:
        raise RuntimeError("standard and HD payloads differ")
    d32f = [
        verify_d32f(
            source_files[relative],
            candidate_files[relative],
            str(expected["source_sha256"]),
        )
        for relative, expected in diag.D32F_RELATIVES.items()
    ]
    icon = candidate_files[diag.LOOSE_ICON_RELATIVE].read_bytes()
    if len(icon) != 2316 or struct.unpack_from("<III", icon, 0) != (48 * 32, 48, 32):
        raise RuntimeError("loose Coronius PCX geometry mismatch")
    install = candidate_files[root_texts[0]].read_text(encoding="utf-8")
    for marker in (diag.BUILD_NAME, diag.LOG_FILENAME, "高级学术 / Expert Scholar", "Advanced Scholar"):
        if marker not in install:
            raise RuntimeError(f"installation text missing marker: {marker}")
    print(json.dumps({
        "verified": True,
        "build_name": diag.BUILD_NAME,
        "candidate_zip_sha256": sha256(args.candidate_zip),
        "changed_files": sorted(changed),
        "added_files": [diag.LOOSE_ICON_RELATIVE],
        "executables": exes,
        "d32f": d32f,
        "loose_icon_sha256": hashlib.sha256(icon).hexdigest(),
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
