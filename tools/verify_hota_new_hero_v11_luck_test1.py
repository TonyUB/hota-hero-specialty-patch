#!/usr/bin/env python3
"""Independent static verifier for HOTA_NEW_HERO_V1.1_LUCK_TEST1."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

import capstone
import pefile
from capstone.x86_const import X86_OP_IMM

from build_hota_new_hero_v1 import EXE_NAMES, extract_zip_safely, safe_recreate_directory
from build_hota_new_hero_v11_luck_test1 import (
    ARCHIVE_OLD_SENTENCE,
    BUILD_NAME,
    DAREMYTH_RECORD_OFFSET,
    DAREMYTH_RECORD_SOURCE,
    EXPECTED_NEW_SECTION_HEADER_SLOT,
    HARD_SUPPRESSION_RETURN_VA,
    HOURGLASS_ARTIFACT_ID,
    HOURGLASS_ENEMY_SCAN_VA,
    HOURGLASS_SELF_SCAN_VA,
    IMAGE_BASE,
    LOOSE_HEROSPEC_RELATIVE,
    LOOSE_OLD_SENTENCE,
    LUCK_POST_GATE_ORIGINAL,
    LUCK_POST_GATE_VA,
    LUCK_SECTION_CHARACTERISTICS,
    LUCK_SECTION_NAME,
    LUCK_SECTION_RVA,
    LUCK_SECTION_SIZE,
    LUCK_WRAPPER_VA,
    MELODIA_RECORD_OFFSET,
    MELODIA_RECORD_SOURCE,
    SOURCE_EXE_SHA256,
    SOURCE_NAME,
    SOURCE_ZIP_SHA256,
    SPECIALTY_SENTENCE,
    build_luck_payload,
    expected_hero_records,
    relative_jump,
)
from extract_lod import parse_entries, payload


ALLOWED_CHANGED = {
    "h3hota.exe",
    "h3hota HD.exe",
    "Data/HotA_lng.lod",
    "Data/HotA_l_ext.lod",
    LOOSE_HEROSPEC_RELATIVE,
    "安装说明.txt",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def zip_members(path: Path) -> list[str]:
    with zipfile.ZipFile(path, "r") as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"CRC failure in {path.name}: {failed}")
        return sorted(archive.namelist())


def verify_executable(source_path: Path, candidate_path: Path) -> dict[str, str | int | bool]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    if sha256_bytes(source) != SOURCE_EXE_SHA256[source_path.name]:
        raise RuntimeError(f"Unexpected source hash for {source_path.name}")
    if len(candidate) != len(source) + LUCK_SECTION_SIZE:
        raise RuntimeError(f"Unexpected output size for {source_path.name}")

    source_pe = pefile.PE(data=source, fast_load=False)
    candidate_pe = pefile.PE(data=candidate, fast_load=False)
    if source_pe.FILE_HEADER.NumberOfSections != 4 or candidate_pe.FILE_HEADER.NumberOfSections != 5:
        raise RuntimeError(f"Section count mismatch for {source_path.name}")
    section = candidate_pe.sections[-1]
    if (
        section.Name != LUCK_SECTION_NAME
        or section.VirtualAddress != LUCK_SECTION_RVA
        or section.SizeOfRawData != LUCK_SECTION_SIZE
        or section.Characteristics != LUCK_SECTION_CHARACTERISTICS
        or section.PointerToRawData != len(source)
    ):
        raise RuntimeError(f"Isolated Luck section mismatch for {source_path.name}")

    expected_payload, _ = build_luck_payload()
    actual_payload = candidate[
        section.PointerToRawData : section.PointerToRawData + LUCK_SECTION_SIZE
    ]
    if actual_payload != expected_payload:
        raise RuntimeError(f"Luck payload mismatch for {source_path.name}")

    hook_offset = source_pe.get_offset_from_rva(LUCK_POST_GATE_VA - IMAGE_BASE)
    if source[hook_offset : hook_offset + 6] != LUCK_POST_GATE_ORIGINAL:
        raise RuntimeError(f"Source Hook bytes mismatch for {source_path.name}")
    hook = relative_jump(LUCK_POST_GATE_VA, LUCK_WRAPPER_VA, 6)
    if candidate[hook_offset : hook_offset + 6] != hook:
        raise RuntimeError(f"Candidate Hook bytes mismatch for {source_path.name}")
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    instruction = next(decoder.disasm(candidate[hook_offset : hook_offset + 5], LUCK_POST_GATE_VA))
    if (
        instruction.mnemonic != "jmp"
        or instruction.operands[0].type != X86_OP_IMM
        or int(instruction.operands[0].imm) != LUCK_WRAPPER_VA
    ):
        raise RuntimeError(f"Candidate Hook target mismatch for {source_path.name}")

    melodia_after, daremyth_after = expected_hero_records()
    if source[MELODIA_RECORD_OFFSET : MELODIA_RECORD_OFFSET + len(MELODIA_RECORD_SOURCE)] != MELODIA_RECORD_SOURCE:
        raise RuntimeError(f"Melodia source record mismatch for {source_path.name}")
    if candidate[MELODIA_RECORD_OFFSET : MELODIA_RECORD_OFFSET + len(melodia_after)] != melodia_after:
        raise RuntimeError(f"Melodia output record mismatch for {source_path.name}")
    if source[DAREMYTH_RECORD_OFFSET : DAREMYTH_RECORD_OFFSET + len(DAREMYTH_RECORD_SOURCE)] != DAREMYTH_RECORD_SOURCE:
        raise RuntimeError(f"Daremyth source record mismatch for {source_path.name}")
    if candidate[DAREMYTH_RECORD_OFFSET : DAREMYTH_RECORD_OFFSET + len(daremyth_after)] != daremyth_after:
        raise RuntimeError(f"Daremyth output record mismatch for {source_path.name}")

    guard_start = source_pe.get_offset_from_rva(HOURGLASS_SELF_SCAN_VA - IMAGE_BASE)
    guard_end = source_pe.get_offset_from_rva(LUCK_POST_GATE_VA - IMAGE_BASE)
    if source[guard_start:guard_end] != candidate[guard_start:guard_end]:
        raise RuntimeError(f"Native hard-suppression code changed for {source_path.name}")
    if source[guard_start:guard_end].count(bytes([HOURGLASS_ARTIFACT_ID])) < 2:
        raise RuntimeError(f"Hourglass IDs missing from native gate in {source_path.name}")
    hard_return = source_pe.get_offset_from_rva(HARD_SUPPRESSION_RETURN_VA - IMAGE_BASE)
    if candidate[hard_return : hard_return + 8] != bytes.fromhex("5F 33 C0 5E 8B E5 5D C2"):
        raise RuntimeError(f"Hard-suppression zero return changed for {source_path.name}")
    for address in (HOURGLASS_SELF_SCAN_VA, HOURGLASS_ENEMY_SCAN_VA):
        if address >= LUCK_POST_GATE_VA:
            raise RuntimeError("Hook was placed before a native Hourglass scan")

    pe_offset = source_pe.DOS_HEADER.e_lfanew
    section_table_end = (
        pe_offset
        + 24
        + source_pe.FILE_HEADER.SizeOfOptionalHeader
        + source_pe.FILE_HEADER.NumberOfSections * 40
    )
    section_count_offset = pe_offset + 6
    size_of_code_offset = source_pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfCode")
    size_of_image_offset = source_pe.OPTIONAL_HEADER.get_field_absolute_offset("SizeOfImage")
    checksum_offset = source_pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    if source[section_table_end : section_table_end + 40] != EXPECTED_NEW_SECTION_HEADER_SLOT:
        raise RuntimeError(f"Unexpected source section slot for {source_path.name}")

    restored = bytearray(candidate[: len(source)])
    restored[hook_offset : hook_offset + 6] = LUCK_POST_GATE_ORIGINAL
    restored[MELODIA_RECORD_OFFSET : MELODIA_RECORD_OFFSET + len(MELODIA_RECORD_SOURCE)] = MELODIA_RECORD_SOURCE
    restored[DAREMYTH_RECORD_OFFSET : DAREMYTH_RECORD_OFFSET + len(DAREMYTH_RECORD_SOURCE)] = DAREMYTH_RECORD_SOURCE
    restored[section_table_end : section_table_end + 40] = source[section_table_end : section_table_end + 40]
    restored[section_count_offset : section_count_offset + 2] = source[section_count_offset : section_count_offset + 2]
    restored[size_of_code_offset : size_of_code_offset + 4] = source[size_of_code_offset : size_of_code_offset + 4]
    restored[size_of_image_offset : size_of_image_offset + 4] = source[size_of_image_offset : size_of_image_offset + 4]
    restored[checksum_offset : checksum_offset + 4] = source[checksum_offset : checksum_offset + 4]
    if bytes(restored) != source:
        raise RuntimeError(f"Independent rollback failed for {source_path.name}")

    return {
        "source_sha256": sha256_bytes(source),
        "candidate_sha256": sha256_bytes(candidate),
        "candidate_size": len(candidate),
        "payload_sha256": sha256_bytes(actual_payload),
        "rollback_passed": True,
        "native_hard_suppression_unchanged": True,
    }


def entry_map(data: bytes) -> dict[str, dict[str, int | str]]:
    return {str(entry["name"]).lower(): entry for entry in parse_entries(data)}


def verify_lod(source_path: Path, candidate_path: Path) -> dict[str, int | str | bool]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    source_entries = entry_map(source)
    candidate_entries = entry_map(candidate)
    if set(source_entries) != set(candidate_entries):
        raise RuntimeError(f"LOD member set changed in {candidate_path.name}")
    for name, source_entry in source_entries.items():
        candidate_entry = candidate_entries[name]
        if name == "herospec.txt":
            continue
        if source_entry != candidate_entry or payload(source, source_entry) != payload(candidate, candidate_entry):
            raise RuntimeError(f"Unexpected LOD member change: {candidate_path.name}/{name}")
    source_member = payload(source, source_entries["herospec.txt"])
    candidate_member = payload(candidate, candidate_entries["herospec.txt"])
    source_text = source_member.decode("gb18030")
    candidate_text = candidate_member.decode("gb18030")
    if source_text.count(ARCHIVE_OLD_SENTENCE) != 2:
        raise RuntimeError(f"Unexpected source HeroSpec state in {source_path.name}")
    expected = source_text.replace(ARCHIVE_OLD_SENTENCE, SPECIALTY_SENTENCE)
    if candidate_text != expected or candidate_text.count(SPECIALTY_SENTENCE) != 2:
        raise RuntimeError(f"Unexpected HeroSpec output in {candidate_path.name}")
    return {
        "source_sha256": sha256_bytes(source),
        "candidate_sha256": sha256_bytes(candidate),
        "source_member_sha256": sha256_bytes(source_member),
        "candidate_member_sha256": sha256_bytes(candidate_member),
        "replacement_count": 2,
        "other_members_unchanged": True,
    }


def verify_loose(source_path: Path, candidate_path: Path) -> dict[str, str | int]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    source_text = source.decode("gb18030")
    candidate_text = candidate.decode("gb18030")
    if source_text.count(LOOSE_OLD_SENTENCE) != 2:
        raise RuntimeError("Unexpected loose HeroSpec source state")
    if candidate_text != source_text.replace(LOOSE_OLD_SENTENCE, SPECIALTY_SENTENCE):
        raise RuntimeError("Unexpected loose HeroSpec output state")
    return {
        "source_sha256": sha256_bytes(source),
        "candidate_sha256": sha256_bytes(candidate),
        "replacement_count": 2,
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
        raise RuntimeError(f"Formal {SOURCE_NAME} ZIP hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("build_name") != BUILD_NAME:
        raise RuntimeError("Manifest build name mismatch")
    if manifest.get("zip_sha256") != sha256_file(candidate_zip):
        raise RuntimeError("Manifest candidate ZIP hash mismatch")
    if zip_members(source_zip) != zip_members(candidate_zip):
        raise RuntimeError("Candidate ZIP member list differs from formal source")

    safe_recreate_directory(work_root, work_root.parent)
    source_root = work_root / "source"
    candidate_root = work_root / "candidate"
    source_root.mkdir()
    candidate_root.mkdir()
    extract_zip_safely(source_zip, source_root)
    extract_zip_safely(candidate_zip, candidate_root)
    source_files = {
        path.relative_to(source_root).as_posix(): sha256_file(path)
        for path in source_root.rglob("*") if path.is_file()
    }
    candidate_files = {
        path.relative_to(candidate_root).as_posix(): sha256_file(path)
        for path in candidate_root.rglob("*") if path.is_file()
    }
    changed = {name for name in source_files if source_files[name] != candidate_files[name]}
    if changed != ALLOWED_CHANGED:
        raise RuntimeError(f"Unexpected changed-file set: {sorted(changed)}")

    executable_reports = {
        name: verify_executable(source_root / name, candidate_root / name)
        for name in EXE_NAMES
    }
    payload_hashes = {report["payload_sha256"] for report in executable_reports.values()}
    if len(payload_hashes) != 1:
        raise RuntimeError("Standard and HD payloads differ")
    lod_reports = {
        relative: verify_lod(source_root / relative, candidate_root / relative)
        for relative in ("Data/HotA_lng.lod", "Data/HotA_l_ext.lod")
    }
    loose_report = verify_loose(
        source_root / LOOSE_HEROSPEC_RELATIVE,
        candidate_root / LOOSE_HEROSPEC_RELATIVE,
    )
    if manifest.get("changed_package_files") != sorted(changed):
        raise RuntimeError("Manifest changed-file list mismatch")
    if manifest.get("package_file_hashes") != candidate_files:
        raise RuntimeError("Manifest package hashes mismatch")

    report = {
        "build_name": BUILD_NAME,
        "candidate_zip_sha256": sha256_file(candidate_zip),
        "changed_files": sorted(changed),
        "executables": executable_reports,
        "lods": lod_reports,
        "loose_herospec": loose_report,
        "result": "PASS",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
