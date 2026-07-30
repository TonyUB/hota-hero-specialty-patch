#!/usr/bin/env python3
"""Independently verify HOTA_NEW_HERO_V1.2_SCHOLAR_TEST02."""

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
from extract_lod import DIRECTORY_OFFSET, ENTRY_SIZE, parse_entries, payload
import build_hota_new_hero_v12_scholar_diag01 as diag01
import build_hota_new_hero_v12_scholar_diag02 as diag02
import build_hota_new_hero_v12_scholar_test01 as test01
import build_hota_new_hero_v12_scholar_test02 as test02


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def verify_executable(source_path: Path, candidate_path: Path, expected_payload: bytes) -> dict[str, object]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    if sha256_bytes(source) != diag02.SOURCE_EXE_SHA256[source_path.name]:
        raise RuntimeError(f"formal EXE hash mismatch: {source_path.name}")
    if len(candidate) != len(source):
        raise RuntimeError(f"EXE size changed: {candidate_path.name}")
    source_pe = pefile.PE(data=source, fast_load=False)
    candidate_pe = pefile.PE(data=candidate, fast_load=False)
    if candidate_pe.FILE_HEADER.NumberOfSections != source_pe.FILE_HEADER.NumberOfSections:
        raise RuntimeError(f"section count changed: {candidate_path.name}")
    if candidate_pe.OPTIONAL_HEADER.SizeOfImage != source_pe.OPTIONAL_HEADER.SizeOfImage:
        raise RuntimeError(f"SizeOfImage changed: {candidate_path.name}")
    if candidate_pe.verify_checksum() is not True:
        raise RuntimeError(f"candidate checksum invalid: {candidate_path.name}")

    source_section = source[
        diag02.LUCK_SECTION_RAW_OFFSET:
        diag02.LUCK_SECTION_RAW_OFFSET + diag02.LUCK_SECTION_SIZE
    ]
    candidate_section = candidate[
        diag02.LUCK_SECTION_RAW_OFFSET:
        diag02.LUCK_SECTION_RAW_OFFSET + diag02.LUCK_SECTION_SIZE
    ]
    if candidate_section[:diag02.PRESERVED_FORMAL_END] != source_section[:diag02.PRESERVED_FORMAL_END]:
        raise RuntimeError(f"formal .luck3 prefix changed: {candidate_path.name}")
    if candidate_section[diag02.PRESERVED_FORMAL_END:] != expected_payload[diag02.PRESERVED_FORMAL_END:]:
        raise RuntimeError(f"Scholar payload tail mismatch: {candidate_path.name}")

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    entry_offset = source_pe.get_offset_from_rva(diag01.SCHOLAR_ENTRY_VA - diag01.IMAGE_BASE)
    entry_jump = diag01.relative_jump(
        diag01.SCHOLAR_ENTRY_VA,
        diag02.ENTRY_WRAPPER_VA,
        len(diag01.SCHOLAR_ENTRY_ORIGINAL),
    )
    if candidate[entry_offset:entry_offset + len(entry_jump)] != entry_jump:
        raise RuntimeError(f"Scholar entry hook mismatch: {candidate_path.name}")
    for item in test01.FEATURE_PATCHES:
        va = int(item["va"])
        offset = source_pe.get_offset_from_rva(va - diag01.IMAGE_BASE)
        replacement = diag01.relative_jump(va, int(item["wrapper_va"]), len(bytes(item["source"])))
        if candidate[offset:offset + len(replacement)] != replacement:
            raise RuntimeError(f"feature hook mismatch: {item['name']}")
        instruction = next(decoder.disasm(candidate[offset:offset + 5], va))
        if (
            instruction.mnemonic != "jmp"
            or not instruction.operands
            or instruction.operands[0].type != X86_OP_IMM
            or int(instruction.operands[0].imm) != int(item["wrapper_va"])
        ):
            raise RuntimeError(f"feature hook target mismatch: {item['name']}")

    record_start = test02.CORONIUS_RECORD_OFFSET
    record_end = record_start + test02.CORONIUS_RECORD_SIZE
    if sha256_bytes(source[record_start:record_end]) != test02.CORONIUS_RECORD_SHA256:
        raise RuntimeError(f"formal Coronius record mismatch: {source_path.name}")
    field = record_start + test02.STARTING_SPELL_OFFSET
    if struct.unpack_from("<I", source, field)[0] != test02.OLD_STARTING_SPELL:
        raise RuntimeError(f"formal Coronius spell is not Slayer: {source_path.name}")
    if struct.unpack_from("<I", candidate, field)[0] != test02.NEW_STARTING_SPELL:
        raise RuntimeError(f"candidate Coronius spell is not Slow: {candidate_path.name}")
    candidate_record = bytearray(candidate[record_start:record_end])
    struct.pack_into("<I", candidate_record, test02.STARTING_SPELL_OFFSET, test02.OLD_STARTING_SPELL)
    if bytes(candidate_record) != source[record_start:record_end]:
        raise RuntimeError(f"an unrelated Coronius record field changed: {candidate_path.name}")

    checksum_offset = source_pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    restored = bytearray(candidate)
    restored[entry_offset:entry_offset + len(diag01.SCHOLAR_ENTRY_ORIGINAL)] = diag01.SCHOLAR_ENTRY_ORIGINAL
    for item in test01.FEATURE_PATCHES:
        va = int(item["va"])
        offset = source_pe.get_offset_from_rva(va - diag01.IMAGE_BASE)
        original = bytes(item["source"])
        restored[offset:offset + len(original)] = original
    restored[
        diag02.LUCK_SECTION_RAW_OFFSET:
        diag02.LUCK_SECTION_RAW_OFFSET + diag02.LUCK_SECTION_SIZE
    ] = source_section
    struct.pack_into("<I", restored, field, test02.OLD_STARTING_SPELL)
    restored[checksum_offset:checksum_offset + 4] = source[checksum_offset:checksum_offset + 4]
    if bytes(restored) != source:
        raise RuntimeError(f"full EXE rollback failed: {candidate_path.name}")
    return {
        "name": candidate_path.name,
        "source_sha256": sha256_bytes(source),
        "candidate_sha256": sha256_bytes(candidate),
        "starting_spell": {"source": 55, "candidate": 54},
        "payload_tail_sha256": sha256_bytes(expected_payload[diag02.PRESERVED_FORMAL_END:]),
        "checksum_valid": True,
        "full_rollback_verified": True,
    }


def verify_lod(source_path: Path, candidate_path: Path) -> dict[str, object]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    source_entries = parse_entries(source)
    candidate_entries = parse_entries(candidate)
    if len(source_entries) != len(candidate_entries):
        raise RuntimeError(f"LOD member count changed: {candidate_path.name}")
    matches = [entry for entry in source_entries if str(entry["name"]).lower() == "herospec.txt"]
    if len(matches) != 1:
        raise RuntimeError(f"expected one source HeroSpec.txt: {source_path.name}")
    index = int(matches[0]["index"])
    source_member = payload(source, source_entries[index])
    candidate_member = payload(candidate, candidate_entries[index])
    old = test02.OLD_LOD_RECORD.encode("gb18030")
    new = test02.NEW_LOD_RECORD.encode("gb18030")
    if old not in source_member:
        old = test02.OLD_LOD_RECORD.replace("\r\n", "\n").encode("gb18030")
        new = test02.NEW_LOD_RECORD.replace("\r\n", "\n").encode("gb18030")
    if source_member.count(old) != 1 or candidate_member.count(new) != 1 or old in candidate_member:
        raise RuntimeError(f"HeroSpec description mismatch: {candidate_path.name}")
    expected_member = source_member.replace(old, new, 1)
    if candidate_member != expected_member:
        raise RuntimeError(f"unrelated HeroSpec text changed: {candidate_path.name}")
    source_directory = source[
        DIRECTORY_OFFSET:DIRECTORY_OFFSET + len(source_entries) * ENTRY_SIZE
    ]
    candidate_directory = candidate[
        DIRECTORY_OFFSET:DIRECTORY_OFFSET + len(candidate_entries) * ENTRY_SIZE
    ]
    if (
        source_directory[:index * ENTRY_SIZE] + source_directory[(index + 1) * ENTRY_SIZE:]
        != candidate_directory[:index * ENTRY_SIZE] + candidate_directory[(index + 1) * ENTRY_SIZE:]
    ):
        raise RuntimeError(f"an unrelated LOD directory entry changed: {candidate_path.name}")
    return {
        "path": candidate_path.name,
        "source_member_sha256": sha256_bytes(source_member),
        "candidate_member_sha256": sha256_bytes(candidate_member),
        "exact_record_replacement": True,
        "unrelated_directory_entries_preserved": True,
    }


def d32f_frame(data: bytes) -> tuple[int, int, int]:
    if data[:4] != b"D32F" or struct.unpack_from("<I", data, 0x28)[0] != 215:
        raise RuntimeError("unexpected D32F container")
    offsets_position = 0x30 + 215 * 13
    offsets = struct.unpack_from("<215I", data, offsets_position)
    offset = offsets[diag01.CORONIUS_ID]
    header = struct.unpack_from("<8I", data, offset)
    return offset + 32, header[1], header[2]


def verify_icon(
    source_path: Path,
    candidate_path: Path,
    expert_def: Path,
    expected_hash: str,
    expected_name: str,
) -> dict[str, object]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    start, length, size = d32f_frame(source)
    candidate_start, candidate_length, candidate_size = d32f_frame(candidate)
    if (candidate_start, candidate_length, candidate_size) != (start, length, size):
        raise RuntimeError(f"D32F geometry changed: {candidate_path.name}")
    image, _, _, native = diag01.decode_expert_scholar(
        expert_def,
        expected_hash=expected_hash,
        expected_size=size,
        expected_name=expected_name,
    )
    expected_pixels = image.rotate(180).tobytes("raw", "BGRA")
    if candidate[start:start + length] != expected_pixels:
        raise RuntimeError(f"Expert Scholar pixels mismatch: {candidate_path.name}")
    if candidate[:start] != source[:start] or candidate[start + length:] != source[start + length:]:
        raise RuntimeError(f"an unrelated D32F byte changed: {candidate_path.name}")
    return {
        "path": candidate_path.name,
        "frame": diag01.CORONIUS_ID,
        "size": size,
        "native_frame": native["frame_name"],
        "candidate_frame_sha256": sha256_bytes(candidate[start:start + length]),
        "all_other_bytes_preserved": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--candidate-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--secskill-def", type=Path, required=True)
    parser.add_argument("--secskill32-def", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()

    if sha256_file(args.source_zip) != test02.SOURCE_ZIP_SHA256:
        raise RuntimeError("formal source ZIP hash mismatch")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest["build_name"] != test02.BUILD_NAME or not manifest["test_only"]:
        raise RuntimeError("SCHOLAR_TEST02 manifest identity mismatch")
    if sha256_file(args.candidate_zip) != manifest["zip_sha256"]:
        raise RuntimeError("SCHOLAR_TEST02 ZIP hash mismatch")
    with zipfile.ZipFile(args.candidate_zip, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("SCHOLAR_TEST02 ZIP CRC failure")

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
        raise RuntimeError("SCHOLAR_TEST02 changed the formal member set")
    root_texts = [name for name in source_files if "/" not in name and name.lower().endswith(".txt")]
    if len(root_texts) != 1:
        raise RuntimeError("expected one root installation text")
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
        raise RuntimeError(f"unexpected changed-file set: {sorted(changed ^ expected_changed)}")

    test02.configure_feature_build()
    expected_payload, _ = test01.build_payload()
    executables = [
        verify_executable(source_files[name], candidate_files[name], expected_payload)
        for name in EXE_NAMES
    ]
    lods = [
        verify_lod(source_files[name], candidate_files[name])
        for name in test02.LANGUAGE_ARCHIVES
    ]
    old_loose = test02.OLD_LOOSE_RECORD.encode("gb18030")
    new_loose = test02.NEW_LOOSE_RECORD.encode("gb18030")
    loose_source = source_files[test02.LOOSE_HEROSPEC].read_bytes()
    loose_candidate = candidate_files[test02.LOOSE_HEROSPEC].read_bytes()
    if loose_source.count(old_loose) != 1:
        raise RuntimeError("formal loose HeroSpec record mismatch")
    if loose_candidate != loose_source.replace(old_loose, new_loose, 1):
        raise RuntimeError("loose HeroSpec changed beyond Coronius record")

    icons = []
    for relative, expected in diag01.D32F_RELATIVES.items():
        if int(expected["size"]) == 44:
            expert_def, expert_hash, expert_name = (
                args.secskill_def, diag01.SECSKILL_DEF_SHA256, "skill18c.pcx"
            )
        else:
            expert_def, expert_hash, expert_name = (
                args.secskill32_def, diag01.SECSK32_DEF_SHA256, "skl3218c.pcx"
            )
        icons.append(verify_icon(
            source_files[relative], candidate_files[relative],
            expert_def, expert_hash, expert_name,
        ))

    portrait_changes = [
        name for name in changed
        if Path(name).name.upper().startswith(("HPS", "HPL"))
    ]
    if portrait_changes:
        raise RuntimeError(f"hero portrait resource changed: {portrait_changes}")
    install = candidate_files[root_texts[0]].read_text(encoding="utf-8")
    for marker in (test02.BUILD_NAME, "高级学术 / Expert Scholar", "初始魔法由屠戮改为一级魔法“减速”"):
        if marker not in install:
            raise RuntimeError(f"installation text missing marker: {marker}")

    print(json.dumps({
        "verified": True,
        "build_name": test02.BUILD_NAME,
        "candidate_zip_sha256": sha256_file(args.candidate_zip),
        "changed_files": sorted(changed),
        "executables": executables,
        "language_archives": lods,
        "loose_herospec_exact_replacement": True,
        "icons": icons,
        "portrait_resources_untouched": True,
        "member_set_unchanged": True,
        "zip_crc_passed": True,
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
