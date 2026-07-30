#!/usr/bin/env python3
"""Independently verify formal HOTA_NEW_HERO_V1.2."""

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
import build_hota_new_hero_v12 as release
import build_hota_new_hero_v12_scholar_diag01 as diag01
import build_hota_new_hero_v12_scholar_diag02 as diag02
import build_hota_new_hero_v12_scholar_test01 as test01
import build_hota_new_hero_v12_scholar_test02 as test02
import build_hota_new_hero_v12_scholar_test03 as test03
import build_hota_new_hero_v12_scholar_test04 as test04
import verify_hota_new_hero_v12_scholar_test02 as verify02


NATIVE_SPECIALTY_FUNCTION_OFFSET = 0x000E6260
NATIVE_SPECIALTY_GATE_SIGNATURE = bytes.fromhex(
    "55 8B EC 83 EC 08 8B 51 1A 56 8B 35 80 9C 67 00 "
    "33 C0 8D 14 92 8D 14 D6 83 3A 03 0F 85"
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


def verify_executable(source_path: Path, candidate_path: Path) -> dict[str, object]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    if sha256_bytes(source) != release.SOURCE_EXE_SHA256[source_path.name]:
        raise RuntimeError(f"formal V1.14 EXE hash mismatch: {source_path.name}")
    if len(candidate) != len(source):
        raise RuntimeError(f"formal V1.2 EXE size changed: {candidate_path.name}")
    source_pe = pefile.PE(data=source, fast_load=False)
    candidate_pe = pefile.PE(data=candidate, fast_load=False)
    if candidate_pe.verify_checksum() is not True:
        raise RuntimeError(f"formal V1.2 checksum invalid: {candidate_path.name}")
    if candidate_pe.FILE_HEADER.NumberOfSections != source_pe.FILE_HEADER.NumberOfSections:
        raise RuntimeError(f"formal V1.2 section count changed: {candidate_path.name}")
    if candidate_pe.OPTIONAL_HEADER.SizeOfImage != source_pe.OPTIONAL_HEADER.SizeOfImage:
        raise RuntimeError(f"formal V1.2 SizeOfImage changed: {candidate_path.name}")

    if source[
        NATIVE_SPECIALTY_FUNCTION_OFFSET:
        NATIVE_SPECIALTY_FUNCTION_OFFSET + len(NATIVE_SPECIALTY_GATE_SIGNATURE)
    ] != NATIVE_SPECIALTY_GATE_SIGNATURE:
        raise RuntimeError(f"native specialty gate signature mismatch: {source_path.name}")

    record_start = release.CORONIUS_RECORD_OFFSET
    record_end = record_start + release.CORONIUS_RECORD_SIZE
    if sha256_bytes(source[record_start:record_end]) != release.CORONIUS_RECORD_SHA256:
        raise RuntimeError(f"formal Coronius record mismatch: {source_path.name}")
    if candidate[record_start:record_end] != source[record_start:record_end]:
        raise RuntimeError(f"formal V1.2 changed Coronius hero record: {candidate_path.name}")
    spell_field = record_start + release.STARTING_SPELL_OFFSET
    if struct.unpack_from("<I", candidate, spell_field)[0] != release.SLAYER_SPELL_ID:
        raise RuntimeError(f"formal V1.2 Coronius does not start with Slayer: {candidate_path.name}")

    specialty_start = test04.CORONIUS_SPECIALTY_RECORD_OFFSET
    specialty_end = specialty_start + test04.SPECIALTY_RECORD_SIZE
    source_specialty = source[specialty_start:specialty_end]
    expected_specialty = bytearray(source_specialty)
    struct.pack_into("<i", expected_specialty, 0, test04.DISABLED_SPECIALTY_TYPE)
    if candidate[specialty_start:specialty_end] != bytes(expected_specialty):
        raise RuntimeError(f"formal V1.2 specialty record mismatch: {candidate_path.name}")

    section_start = diag02.LUCK_SECTION_RAW_OFFSET
    section_end = section_start + diag02.LUCK_SECTION_SIZE
    source_section = source[section_start:section_end]
    candidate_section = candidate[section_start:section_end]
    if candidate_section[:diag02.PRESERVED_FORMAL_END] != source_section[:diag02.PRESERVED_FORMAL_END]:
        raise RuntimeError(f"formal .luck3 prefix changed: {candidate_path.name}")

    component_reports, components = release.build_feature_components()
    for va, code in components.items():
        raw = section_start + (va - diag02.LUCK_SECTION_VA)
        if candidate[raw:raw + len(code)] != code:
            raise RuntimeError(f"formal Scholar component mismatch: 0x{va:08X}")
    active_raw = section_start + (test01.ACTIVE_VA - diag02.LUCK_SECTION_VA)
    if candidate[active_raw] != 0:
        raise RuntimeError(f"formal Scholar active flag is not initialized: {candidate_path.name}")

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    for item in test01.FEATURE_PATCHES:
        va = int(item["va"])
        offset = source_pe.get_offset_from_rva(va - diag01.IMAGE_BASE)
        expected = diag01.relative_jump(
            va, int(item["wrapper_va"]), len(bytes(item["source"]))
        )
        if candidate[offset:offset + len(expected)] != expected:
            raise RuntimeError(f"formal Scholar hook mismatch: {item['name']}")
        instruction = next(decoder.disasm(candidate[offset:offset + 5], va))
        if (
            instruction.mnemonic != "jmp"
            or not instruction.operands
            or instruction.operands[0].type != X86_OP_IMM
            or int(instruction.operands[0].imm) != int(item["wrapper_va"])
        ):
            raise RuntimeError(f"formal Scholar hook target mismatch: {item['name']}")

    entry_offset = source_pe.get_offset_from_rva(
        diag01.SCHOLAR_ENTRY_VA - diag01.IMAGE_BASE
    )
    if candidate[
        entry_offset:entry_offset + len(diag01.SCHOLAR_ENTRY_ORIGINAL)
    ] != diag01.SCHOLAR_ENTRY_ORIGINAL:
        raise RuntimeError(f"formal V1.2 retains diagnostic entry hook: {candidate_path.name}")
    if b"hota_scholar_" in candidate or b"SCH1" in candidate:
        raise RuntimeError(f"formal V1.2 retains diagnostic strings: {candidate_path.name}")

    checksum_offset = source_pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    restored = bytearray(candidate)
    restored[section_start:section_end] = source_section
    for item in test01.FEATURE_PATCHES:
        offset = source_pe.get_offset_from_rva(int(item["va"]) - diag01.IMAGE_BASE)
        source_bytes = bytes(item["source"])
        restored[offset:offset + len(source_bytes)] = source_bytes
    restored[specialty_start:specialty_end] = source_specialty
    restored[checksum_offset:checksum_offset + 4] = source[
        checksum_offset:checksum_offset + 4
    ]
    if bytes(restored) != source:
        raise RuntimeError(f"formal V1.2 full EXE rollback failed: {candidate_path.name}")

    return {
        "name": candidate_path.name,
        "source_sha256": sha256_bytes(source),
        "candidate_sha256": sha256_bytes(candidate),
        "coronius_starting_spell": {"id": release.SLAYER_SPELL_ID, "name": "Slayer"},
        "coronius_hero_record_unchanged": True,
        "native_specialty_type": test04.DISABLED_SPECIALTY_TYPE,
        "native_slayer_bonus_bypassed": True,
        "scholar_components": component_reports,
        "diagnostic_entry_hook_absent": True,
        "diagnostic_strings_absent": True,
        "checksum_valid": True,
        "full_rollback_verified": True,
    }


def verify_icon(
    source_path: Path,
    candidate_path: Path,
    expert_def: Path,
    expected_hash: str,
) -> dict[str, object]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    start, length, size = verify02.d32f_frame(source)
    candidate_start, candidate_length, candidate_size = verify02.d32f_frame(candidate)
    if (candidate_start, candidate_length, candidate_size) != (start, length, size):
        raise RuntimeError(f"D32F geometry changed: {candidate_path.name}")
    expected_name = (
        test04.EXPERT_SCHOLAR_44_NAME
        if size == 44 else test04.EXPERT_SCHOLAR_32_NAME
    )
    image, _, _, native = test04.decode_correct_expert_scholar(
        expert_def,
        expected_hash=expected_hash,
        expected_size=size,
        expected_name=expected_name,
    )
    rendered = image.rotate(180).tobytes("raw", "BGRA")
    metadata_end = start + test03.D32F_FRAME_METADATA_SIZE
    if candidate[start:metadata_end] != test03.D32F_FRAME_METADATA:
        raise RuntimeError(f"D32F metadata mismatch: {candidate_path.name}")
    if candidate[metadata_end:start + length] != rendered[
        test03.D32F_FRAME_METADATA_SIZE:
    ]:
        raise RuntimeError(f"formal Expert Scholar pixels mismatch: {candidate_path.name}")
    if candidate[:start] != source[:start] or candidate[start + length:] != source[start + length:]:
        raise RuntimeError(f"an unrelated D32F byte changed: {candidate_path.name}")
    return {
        "path": candidate_path.name,
        "hero_frame": diag01.CORONIUS_ID,
        "size": size,
        "native_frame_index": test04.EXPERT_SCHOLAR_FRAME,
        "native_frame": native["frame_name"],
        "metadata_preserved": True,
        "all_other_bytes_preserved": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--candidate-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--secskill-def", type=Path, required=True)
    parser.add_argument("--secskill32-def", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if sha256_file(args.source_zip) != release.SOURCE_ZIP_SHA256:
        raise RuntimeError("formal V1.14 source ZIP hash mismatch")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("build_name") != release.BUILD_NAME or not manifest.get("formal_release"):
        raise RuntimeError("formal V1.2 manifest identity mismatch")
    if sha256_file(args.candidate_zip) != manifest.get("zip_sha256"):
        raise RuntimeError("formal V1.2 ZIP hash mismatch")
    if manifest.get("formula") != release.FORMULA_EXPRESSION:
        raise RuntimeError("formal V1.2 Cure formula mismatch")
    with zipfile.ZipFile(args.candidate_zip, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("formal V1.2 ZIP CRC failure")

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
        raise RuntimeError("formal V1.2 changed the source member set")

    root_texts = [
        name for name in source_files
        if "/" not in name and name.lower().endswith(".txt")
    ]
    if len(root_texts) != 1:
        raise RuntimeError("expected exactly one root installation text")
    expected_changed = (
        set(EXE_NAMES)
        | set(test02.LANGUAGE_ARCHIVES)
        | {test02.LOOSE_HEROSPEC, root_texts[0]}
        | set(diag01.D32F_RELATIVES)
    )
    changed = {
        name for name in source_files
        if sha256_file(source_files[name]) != sha256_file(candidate_files[name])
    }
    if changed != expected_changed:
        raise RuntimeError(f"unexpected formal V1.2 changed-file set: {sorted(changed)}")

    executables = [
        verify_executable(source_files[name], candidate_files[name])
        for name in EXE_NAMES
    ]
    lods = [
        verify02.verify_lod(source_files[name], candidate_files[name])
        for name in test02.LANGUAGE_ARCHIVES
    ]
    old_loose = test02.OLD_LOOSE_RECORD.encode("gb18030")
    new_loose = test02.NEW_LOOSE_RECORD.encode("gb18030")
    loose_source = source_files[test02.LOOSE_HEROSPEC].read_bytes()
    loose_candidate = candidate_files[test02.LOOSE_HEROSPEC].read_bytes()
    if loose_candidate != loose_source.replace(old_loose, new_loose, 1):
        raise RuntimeError("formal loose HeroSpec changed beyond Coronius record")

    icons = []
    for relative, expected in diag01.D32F_RELATIVES.items():
        if int(expected["size"]) == 44:
            expert_def, expert_hash = args.secskill_def, diag01.SECSKILL_DEF_SHA256
        else:
            expert_def, expert_hash = args.secskill32_def, diag01.SECSK32_DEF_SHA256
        icons.append(verify_icon(
            source_files[relative], candidate_files[relative], expert_def, expert_hash
        ))

    install = candidate_files[root_texts[0]].read_text(encoding="utf-8")
    for marker in (
        release.BUILD_NAME,
        "初级智慧术 + 初级学术；魔法书初始自带屠戮",
        "原屠戮特长的分级加成与实际增幅均已停用",
    ):
        if marker not in install:
            raise RuntimeError(f"formal installation text missing marker: {marker}")

    print(json.dumps({
        "verified": True,
        "build_name": release.BUILD_NAME,
        "candidate_zip_sha256": sha256_file(args.candidate_zip),
        "changed_files": sorted(changed),
        "executables": executables,
        "language_archives": lods,
        "loose_herospec_exact_replacement": True,
        "icons": icons,
        "installation_text_verified": True,
        "member_set_unchanged": True,
        "zip_crc_passed": True,
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
