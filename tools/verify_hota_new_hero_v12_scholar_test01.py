#!/usr/bin/env python3
"""Independently verify HOTA_NEW_HERO_V1.2_SCHOLAR_TEST01."""

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
import build_hota_new_hero_v12_scholar_diag01 as diag01
import build_hota_new_hero_v12_scholar_diag02 as diag02
import build_hota_new_hero_v12_scholar_test01 as test01


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def reference_caps(
    hero1_id: int,
    hero1_scholar: int,
    hero1_wisdom: int,
    hero2_id: int,
    hero2_scholar: int,
    hero2_wisdom: int,
) -> tuple[int, int, int]:
    active = hero1_id == diag01.CORONIUS_ID or hero2_id == diag01.CORONIUS_ID
    contribution1 = hero1_scholar + (1 if hero1_id == diag01.CORONIUS_ID and hero1_scholar > 0 else 0)
    contribution2 = hero2_scholar + (1 if hero2_id == diag01.CORONIUS_ID and hero2_scholar > 0 else 0)
    raw = max(contribution1, contribution2)
    meeting = min(5, raw + 1) if raw > 0 else 0
    receive1 = min(meeting, hero1_wisdom + 2 + (1 if active else 0)) if meeting else 0
    receive2 = min(meeting, hero2_wisdom + 2 + (1 if active else 0)) if meeting else 0
    return meeting, receive1, receive2


def verify_executable(source_path: Path, candidate_path: Path, payload: bytes) -> dict[str, object]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    if hashlib.sha256(source).hexdigest() != diag02.SOURCE_EXE_SHA256[source_path.name]:
        raise RuntimeError(f"source EXE hash mismatch: {source_path.name}")
    if len(candidate) != len(source):
        raise RuntimeError(f"candidate EXE size changed: {candidate_path.name}")
    source_pe = pefile.PE(data=source, fast_load=False)
    candidate_pe = pefile.PE(data=candidate, fast_load=False)
    if source_pe.FILE_HEADER.NumberOfSections != 5 or candidate_pe.FILE_HEADER.NumberOfSections != 5:
        raise RuntimeError(f"section count changed: {candidate_path.name}")
    if candidate_pe.OPTIONAL_HEADER.SizeOfImage != source_pe.OPTIONAL_HEADER.SizeOfImage:
        raise RuntimeError(f"SizeOfImage changed: {candidate_path.name}")

    source_section = source[
        diag02.LUCK_SECTION_RAW_OFFSET:
        diag02.LUCK_SECTION_RAW_OFFSET + diag02.LUCK_SECTION_SIZE
    ]
    candidate_section = candidate[
        diag02.LUCK_SECTION_RAW_OFFSET:
        diag02.LUCK_SECTION_RAW_OFFSET + diag02.LUCK_SECTION_SIZE
    ]
    if hashlib.sha256(source_section).hexdigest() != diag02.SOURCE_LUCK_SECTION_SHA256:
        raise RuntimeError(f"source .luck3 mismatch: {source_path.name}")
    if candidate_section[:diag02.PRESERVED_FORMAL_END] != source_section[:diag02.PRESERVED_FORMAL_END]:
        raise RuntimeError(f"formal .luck3 prefix changed: {candidate_path.name}")
    if candidate_section[diag02.PRESERVED_FORMAL_END:] != payload[diag02.PRESERVED_FORMAL_END:]:
        raise RuntimeError(f"functional payload mismatch: {candidate_path.name}")

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    entry_offset = source_pe.get_offset_from_rva(diag01.SCHOLAR_ENTRY_VA - diag01.IMAGE_BASE)
    entry_jump = diag01.relative_jump(
        diag01.SCHOLAR_ENTRY_VA,
        diag02.ENTRY_WRAPPER_VA,
        len(diag01.SCHOLAR_ENTRY_ORIGINAL),
    )
    if source[entry_offset:entry_offset + len(diag01.SCHOLAR_ENTRY_ORIGINAL)] != diag01.SCHOLAR_ENTRY_ORIGINAL:
        raise RuntimeError(f"source Scholar entry mismatch: {source_path.name}")
    if candidate[entry_offset:entry_offset + len(entry_jump)] != entry_jump:
        raise RuntimeError(f"candidate diagnostic entry mismatch: {candidate_path.name}")

    hooks: list[dict[str, str]] = []
    for item in test01.FEATURE_PATCHES:
        va = int(item["va"])
        wrapper_va = int(item["wrapper_va"])
        source_bytes = bytes(item["source"])
        offset = source_pe.get_offset_from_rva(va - diag01.IMAGE_BASE)
        expected = diag01.relative_jump(va, wrapper_va, len(source_bytes))
        if source[offset:offset + len(source_bytes)] != source_bytes:
            raise RuntimeError(f"source feature bytes mismatch: {item['name']}")
        if candidate[offset:offset + len(expected)] != expected:
            raise RuntimeError(f"candidate feature bytes mismatch: {item['name']}")
        instruction = next(decoder.disasm(candidate[offset:offset + 5], va))
        if (
            instruction.mnemonic != "jmp"
            or not instruction.operands
            or instruction.operands[0].type != X86_OP_IMM
            or int(instruction.operands[0].imm) != wrapper_va
        ):
            raise RuntimeError(f"feature target mismatch: {item['name']}")
        hooks.append({
            "name": str(item["name"]),
            "va": f"0x{va:08X}",
            "target": f"0x{wrapper_va:08X}",
        })

    if candidate_pe.verify_checksum() is not True:
        raise RuntimeError(f"candidate checksum invalid: {candidate_path.name}")
    checksum_offset = source_pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    restored = bytearray(candidate)
    restored[entry_offset:entry_offset + len(diag01.SCHOLAR_ENTRY_ORIGINAL)] = diag01.SCHOLAR_ENTRY_ORIGINAL
    for item in test01.FEATURE_PATCHES:
        va = int(item["va"])
        source_bytes = bytes(item["source"])
        offset = source_pe.get_offset_from_rva(va - diag01.IMAGE_BASE)
        restored[offset:offset + len(source_bytes)] = source_bytes
    restored[
        diag02.LUCK_SECTION_RAW_OFFSET:
        diag02.LUCK_SECTION_RAW_OFFSET + diag02.LUCK_SECTION_SIZE
    ] = source_section
    restored[checksum_offset:checksum_offset + 4] = source[checksum_offset:checksum_offset + 4]
    if bytes(restored) != source:
        raise RuntimeError(f"independent full rollback failed: {candidate_path.name}")

    return {
        "name": candidate_path.name,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
        "size": len(candidate),
        "section_count": 5,
        "formal_luck3_prefix_preserved": True,
        "payload_tail_sha256": hashlib.sha256(payload[diag02.PRESERVED_FORMAL_END:]).hexdigest(),
        "feature_hooks": hooks,
        "rollback_verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--candidate-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()

    if sha256(args.source_zip) != test01.SOURCE_ZIP_SHA256:
        raise RuntimeError("formal V1.14 source ZIP hash mismatch")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest["build_name"] != test01.BUILD_NAME or not manifest["test_only"]:
        raise RuntimeError("SCHOLAR_TEST01 manifest identity mismatch")
    if sha256(args.candidate_zip) != manifest["zip_sha256"]:
        raise RuntimeError("SCHOLAR_TEST01 ZIP hash mismatch")
    with zipfile.ZipFile(args.candidate_zip, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("SCHOLAR_TEST01 ZIP CRC failure")

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
        raise RuntimeError("SCHOLAR_TEST01 changed formal member set")
    root_texts = [name for name in source_files if "/" not in name and name.lower().endswith(".txt")]
    if len(root_texts) != 1:
        raise RuntimeError("expected one root installation text")
    changed = {
        name for name in source_files
        if sha256(source_files[name]) != sha256(candidate_files[name])
    }
    expected_changed = set(EXE_NAMES) | {root_texts[0]}
    if changed != expected_changed:
        raise RuntimeError(f"unexpected SCHOLAR_TEST01 files: {sorted(changed)}")
    for name in set(source_files) - expected_changed:
        if source_files[name].read_bytes() != candidate_files[name].read_bytes():
            raise RuntimeError(f"non-EXE resource changed: {name}")

    payload, _ = test01.build_payload()
    executables = [
        verify_executable(source_files[name], candidate_files[name], payload)
        for name in EXE_NAMES
    ]
    if len({item["payload_tail_sha256"] for item in executables}) != 1:
        raise RuntimeError("standard and HD payloads differ")

    vectors = {
        "returned_diag03_case": reference_caps(24, 1, 1, 17, 0, 0),
        "coronius_advanced": reference_caps(24, 2, 2, 17, 0, 0),
        "coronius_expert": reference_caps(24, 3, 3, 17, 0, 0),
        "non_specialist_control": reference_caps(23, 1, 1, 17, 0, 0),
        "specialist_basic_vs_other_expert": reference_caps(24, 1, 1, 17, 3, 3),
    }
    expected_vectors = {
        "returned_diag03_case": (3, 3, 3),
        "coronius_advanced": (4, 4, 3),
        "coronius_expert": (5, 5, 3),
        "non_specialist_control": (2, 2, 2),
        "specialist_basic_vs_other_expert": (4, 4, 4),
    }
    if vectors != expected_vectors:
        raise RuntimeError(f"reference specialty vectors failed: {vectors}")

    install = candidate_files[root_texts[0]].read_text(encoding="utf-8")
    for marker in (test01.BUILD_NAME, test01.LOG_FILENAME, "初级可传授 1—3 级魔法", "没有科洛尼斯参与"):
        if marker not in install:
            raise RuntimeError(f"installation text missing marker: {marker}")

    print(json.dumps({
        "verified": True,
        "build_name": test01.BUILD_NAME,
        "candidate_zip_sha256": sha256(args.candidate_zip),
        "changed_files": sorted(changed),
        "all_graphic_resources_byte_preserved": True,
        "executables": executables,
        "reference_vectors": {name: list(value) for name, value in vectors.items()},
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
