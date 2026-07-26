#!/usr/bin/env python3
"""Independently verify HOTA_NEW_HERO_V1.1_LUCKDIAG01."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

import pefile

from build_hota_new_hero_v1 import EXE_NAMES, extract_zip_safely, safe_recreate_directory
import build_hota_new_hero_v11_luckdiag01 as diag


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--candidate-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    return parser.parse_args()


def verify_exe(source: Path, candidate: Path, expected_payload: bytes) -> dict[str, object]:
    source_data = source.read_bytes()
    candidate_data = candidate.read_bytes()
    if hashlib.sha256(source_data).hexdigest() != diag.SOURCE_EXE_SHA256[source.name]:
        raise RuntimeError(f"source EXE hash mismatch: {source.name}")
    if len(candidate_data) != len(source_data) + diag.DIAG_SECTION_SIZE:
        raise RuntimeError(f"candidate size mismatch: {candidate.name}")
    source_pe = pefile.PE(data=source_data, fast_load=False)
    candidate_pe = pefile.PE(data=candidate_data, fast_load=False)
    if source_pe.FILE_HEADER.NumberOfSections != 4 or candidate_pe.FILE_HEADER.NumberOfSections != 5:
        raise RuntimeError(f"section count mismatch: {candidate.name}")
    section = candidate_pe.sections[-1]
    if section.Name != diag.DIAG_SECTION_NAME or section.VirtualAddress != diag.DIAG_SECTION_RVA:
        raise RuntimeError(f"diagnostic section identity mismatch: {candidate.name}")
    raw = int(section.PointerToRawData)
    payload = candidate_data[raw : raw + diag.DIAG_SECTION_SIZE]
    if payload != expected_payload:
        raise RuntimeError(f"diagnostic payload mismatch: {candidate.name}")

    entry_offset = source_pe.get_offset_from_rva(diag.LUCK_ENTRY_VA - diag.IMAGE_BASE)
    post_offset = source_pe.get_offset_from_rva(diag.LUCK_POST_GATE_VA - diag.IMAGE_BASE)
    expected_entry = diag.relative_jump(diag.LUCK_ENTRY_VA, diag.ENTRY_WRAPPER_VA, len(diag.LUCK_ENTRY_ORIGINAL))
    expected_post = diag.relative_jump(diag.LUCK_POST_GATE_VA, diag.POST_GATE_WRAPPER_VA, len(diag.LUCK_POST_GATE_ORIGINAL))
    if candidate_data[entry_offset : entry_offset + len(expected_entry)] != expected_entry:
        raise RuntimeError(f"entry hook mismatch: {candidate.name}")
    if candidate_data[post_offset : post_offset + len(expected_post)] != expected_post:
        raise RuntimeError(f"post-gate hook mismatch: {candidate.name}")

    for va in (0x004E3964, 0x004E39A9):
        offset = source_pe.get_offset_from_rva(va - diag.IMAGE_BASE)
        if source_data[offset : offset + 3] not in (bytes.fromhex("83 39 55"), bytes.fromhex("83 3A 55")):
            raise RuntimeError(f"native Hourglass scan mismatch at {va:#x}: {source.name}")
        if candidate_data[offset : offset + 3] != source_data[offset : offset + 3]:
            raise RuntimeError(f"native Hourglass scan changed at {va:#x}: {candidate.name}")
    zero_return_offset = source_pe.get_offset_from_rva(0x004E39DE - diag.IMAGE_BASE)
    if candidate_data[zero_return_offset : zero_return_offset + 8] != source_data[zero_return_offset : zero_return_offset + 8]:
        raise RuntimeError(f"native suppression return changed: {candidate.name}")

    restored = bytearray(candidate_data[: len(source_data)])
    restored[entry_offset : entry_offset + len(diag.LUCK_ENTRY_ORIGINAL)] = diag.LUCK_ENTRY_ORIGINAL
    restored[post_offset : post_offset + len(diag.LUCK_POST_GATE_ORIGINAL)] = diag.LUCK_POST_GATE_ORIGINAL
    pe_offset = source_pe.DOS_HEADER.e_lfanew
    section_table_end = pe_offset + 24 + source_pe.FILE_HEADER.SizeOfOptionalHeader + 4 * 40
    restored[section_table_end : section_table_end + 40] = source_data[section_table_end : section_table_end + 40]
    for field, width in (("SizeOfCode", 4), ("SizeOfImage", 4), ("CheckSum", 4)):
        offset = source_pe.OPTIONAL_HEADER.get_field_absolute_offset(field)
        restored[offset : offset + width] = source_data[offset : offset + width]
    section_count_offset = pe_offset + 6
    restored[section_count_offset : section_count_offset + 2] = source_data[section_count_offset : section_count_offset + 2]
    if bytes(restored) != source_data:
        raise RuntimeError(f"independent rollback failed: {candidate.name}")
    return {
        "name": candidate.name,
        "source_sha256": hashlib.sha256(source_data).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate_data).hexdigest(),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "rollback_verified": True,
        "hourglass_scans_preserved": True,
    }


def main() -> int:
    args = parse_args()
    if sha256(args.source_zip) != diag.SOURCE_ZIP_SHA256:
        raise RuntimeError("formal V1.06 source ZIP hash mismatch")
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
    if set(source_files) != set(candidate_files):
        raise RuntimeError("candidate member set differs from formal V1.06")
    root_texts = [name for name in source_files if "/" not in name and name.lower().endswith(".txt")]
    if len(root_texts) != 1:
        raise RuntimeError("expected one root installation text")
    changed = {
        name for name in source_files
        if sha256(source_files[name]) != sha256(candidate_files[name])
    }
    allowed = set(EXE_NAMES) | {root_texts[0]}
    if changed != allowed:
        raise RuntimeError(f"unexpected package changes: {sorted(changed)}")

    expected_payload, _ = diag.build_payload()
    exe_reports = [
        verify_exe(source_files[name], candidate_files[name], expected_payload)
        for name in EXE_NAMES
    ]
    if len({item["payload_sha256"] for item in exe_reports}) != 1:
        raise RuntimeError("standard and HD diagnostic payloads differ")
    install_text = candidate_files[root_texts[0]].read_text(encoding="utf-8")
    for marker in (diag.BUILD_NAME, diag.LOG_FILENAME, "stage 1", "stage 2", "厄运沙漏"):
        if marker not in install_text:
            raise RuntimeError(f"installation text missing marker: {marker}")
    print(json.dumps({
        "verified": True,
        "build_name": diag.BUILD_NAME,
        "candidate_zip_sha256": sha256(args.candidate_zip),
        "changed_files": sorted(changed),
        "executables": exe_reports,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
