#!/usr/bin/env python3
"""Independently verify Scholar TEST04."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pefile

import build_hota_new_hero_v12_scholar_diag01 as diag01
import build_hota_new_hero_v12_scholar_test02 as test02
import build_hota_new_hero_v12_scholar_test03 as test03
import build_hota_new_hero_v12_scholar_test04 as test04
import verify_hota_new_hero_v12_scholar_test02 as verify02


_BASE_VERIFY_EXECUTABLE = verify02.verify_executable

# 0x004E6260 loads hero_id, indexes the 40-byte table, then gates the original
# spell-specialty calculation on `cmp dword ptr [record], 3`.
NATIVE_SPECIALTY_FUNCTION_OFFSET = 0x000E6260
NATIVE_SPECIALTY_GATE_SIGNATURE = bytes.fromhex(
    "55 8B EC 83 EC 08 8B 51 1A 56 8B 35 80 9C 67 00 "
    "33 C0 8D 14 92 8D 14 D6 83 3A 03 0F 85"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_executable(
    source_path: Path, candidate_path: Path, expected_payload: bytes
) -> dict[str, object]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    if len(candidate) != len(source):
        raise RuntimeError(f"EXE size changed: {candidate_path.name}")
    if source[
        NATIVE_SPECIALTY_FUNCTION_OFFSET:
        NATIVE_SPECIALTY_FUNCTION_OFFSET + len(NATIVE_SPECIALTY_GATE_SIGNATURE)
    ] != NATIVE_SPECIALTY_GATE_SIGNATURE:
        raise RuntimeError(f"native specialty gate signature mismatch: {source_path.name}")

    pointer = struct.unpack_from(
        "<I", source, test04.SPECIALTY_TABLE_POINTER_OFFSET
    )[0]
    if pointer != test04.SPECIALTY_TABLE_POINTER_VA:
        raise RuntimeError(f"specialty-table pointer mismatch: {source_path.name}")
    start = test04.CORONIUS_SPECIALTY_RECORD_OFFSET
    end = start + test04.SPECIALTY_RECORD_SIZE
    source_record = source[start:end]
    candidate_record = candidate[start:end]
    if sha256_bytes(source_record) != test04.CORONIUS_SPECIALTY_RECORD_SHA256:
        raise RuntimeError(f"formal specialty record mismatch: {source_path.name}")
    expected_record = bytearray(source_record)
    struct.pack_into("<i", expected_record, 0, test04.DISABLED_SPECIALTY_TYPE)
    if candidate_record != bytes(expected_record):
        raise RuntimeError(f"candidate specialty record mismatch: {candidate_path.name}")
    if struct.unpack_from("<i", candidate_record, 0)[0] == test04.NATIVE_SPELL_SPECIALTY_TYPE:
        raise RuntimeError(f"native Slayer gate remains enabled: {candidate_path.name}")

    candidate_pe = pefile.PE(data=candidate, fast_load=False)
    if candidate_pe.verify_checksum() is not True:
        raise RuntimeError(f"candidate checksum invalid: {candidate_path.name}")
    checksum_offset = candidate_pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")

    # Restore only TEST04's native-table change, recompute the stage checksum,
    # and let TEST02's independent verifier prove every inherited hook, payload,
    # starting-spell byte and complete rollback to formal V1.14.
    stage = bytearray(candidate)
    struct.pack_into("<i", stage, start, test04.NATIVE_SPELL_SPECIALTY_TYPE)
    struct.pack_into("<I", stage, checksum_offset, 0)
    stage_pe = pefile.PE(data=bytes(stage), fast_load=False)
    struct.pack_into("<I", stage, checksum_offset, stage_pe.generate_checksum())
    stage_bytes = bytes(stage)

    differences = {
        index for index, (left, right) in enumerate(zip(candidate, stage_bytes))
        if left != right
    }
    allowed = set(range(start, start + 4)) | set(range(checksum_offset, checksum_offset + 4))
    if not differences or not differences.issubset(allowed):
        raise RuntimeError(f"native-specialty isolation failed: {candidate_path.name}")

    temporary = candidate_path.with_name(candidate_path.name + ".test04_stage.tmp")
    temporary.write_bytes(stage_bytes)
    try:
        report = _BASE_VERIFY_EXECUTABLE(source_path, temporary, expected_payload)
    finally:
        temporary.unlink(missing_ok=True)

    report["name"] = candidate_path.name
    report["candidate_sha256"] = sha256_bytes(candidate)
    report["native_specialty"] = {
        "function_va": "0x004E6260",
        "gate": "record.type == 3",
        "source_record_type": test04.NATIVE_SPELL_SPECIALTY_TYPE,
        "candidate_record_type": test04.DISABLED_SPECIALTY_TYPE,
        "source_spell_id": test04.NATIVE_SLAYER_SPELL_ID,
        "native_slayer_path_bypassed": True,
        "record_file_offset": f"0x{start:X}",
        "all_other_record_bytes_preserved": True,
        "isolated_delta_verified": True,
    }
    report["full_rollback_verified"] = True
    return report


def verify_icon(
    source_path: Path,
    candidate_path: Path,
    expert_def: Path,
    expected_hash: str,
    _expected_name: str,
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
        raise RuntimeError(f"D32F frame metadata mismatch: {candidate_path.name}")
    if candidate[metadata_end:start + length] != rendered[
        test03.D32F_FRAME_METADATA_SIZE:
    ]:
        raise RuntimeError(f"Expert Scholar visible pixels mismatch: {candidate_path.name}")
    if candidate[:start] != source[:start] or candidate[start + length:] != source[start + length:]:
        raise RuntimeError(f"an unrelated D32F byte changed: {candidate_path.name}")
    return {
        "path": candidate_path.name,
        "frame": diag01.CORONIUS_ID,
        "size": size,
        "native_frame_index": test04.EXPERT_SCHOLAR_FRAME,
        "native_frame": native["frame_name"],
        "metadata_prefix_hex": candidate[start:metadata_end].hex(" "),
        "metadata_prefix_preserved": True,
        "visible_pixels_sha256": sha256_bytes(candidate[metadata_end:start + length]),
        "all_other_bytes_preserved": True,
    }


def main() -> int:
    test02.BUILD_NAME = test04.BUILD_NAME
    test02.LOG_FILENAME = test04.LOG_FILENAME
    test02.installation_text = test04.installation_text
    verify02.verify_executable = verify_executable
    verify02.verify_icon = verify_icon
    return verify02.main()


if __name__ == "__main__":
    raise SystemExit(main())
