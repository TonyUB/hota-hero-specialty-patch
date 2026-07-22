#!/usr/bin/env python3
"""Verify the second V1.04 combat-log candidate and tier/resource fixes."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import pefile

from build_hota_new_hero_v1 import EXE_NAMES, LANGUAGE_ARCHIVES
from build_hota_new_hero_v103 import (
    ASTRA_SKILL_BLOCK_OFFSET,
    ASTRA_SKILLS_AFTER,
    BONUS_CALC_VA,
    CORPSE_CURE_CALC_VA,
    DISPATCH_VA,
    build_formula_payloads,
    locate_astra_hdat_blob,
    total_cure,
)
from build_hota_new_hero_v104_log_test2 import (
    APPEND_HELPER_VA,
    BUILD_NAME,
    CORPSE_CALC_CALL_VA,
    CORPSE_LOG_WRAPPER_VA,
    FLUSH_TRAMPOLINE_VA,
    LIVING_CURE_CALL_VA,
    LIVE_LOG_WRAPPER_VA,
    MASS_FLUSH_CONTINUE_VA,
    MASS_FLUSH_VA,
    MASS_INIT_VA,
    MASS_CORPSE_CALC_CALL_VA,
    LOOSE_HEROSPEC_NEW_ROW,
    LOOSE_HEROSPEC_OLD_ROW,
    LOOSE_HEROSPEC_RELATIVE,
    LOOSE_HEROSPEC_SOURCE_SHA256,
    RECORD_HELPER_VA,
    RES_CAPTURE_VA,
    RES_FLUSH_END_VA,
    SOURCE_HOTA_DAT_SHA256,
    SOURCE_ZIP_SHA256,
    TREATMENT_FORMAT,
    TREATMENT_FORMAT_VA,
    build_log_payloads,
    build_corrected_formula_bonus,
    relative_call,
    relative_jump,
    sha256_file,
    va_to_offset,
)


SPELLBOOK_FORMATTER_CONTEXT_VA = 0x0059BFF0
SPELLBOOK_FORMATTER_CONTEXT_LENGTH = 0x30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--loose-herospec", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--candidate-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reproducible-zip", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = args.source_root.resolve()
    candidate_root = args.candidate_root.resolve()
    candidate_zip = args.candidate_zip.resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if sha256_file(args.source_zip.resolve()) != SOURCE_ZIP_SHA256:
        raise RuntimeError("Source V1.03 ZIP hash mismatch")
    if manifest["build_name"] != BUILD_NAME or manifest["release"] is not False:
        raise RuntimeError("Unexpected build identity")
    if sha256_file(candidate_zip) != manifest["zip_sha256"]:
        raise RuntimeError("Candidate ZIP hash mismatch")
    if args.reproducible_zip and sha256_file(args.reproducible_zip.resolve()) != manifest["zip_sha256"]:
        raise RuntimeError("Independent build is not reproducible")

    payloads = build_log_payloads()
    formula_dispatch, source_formula_bonus, formula_corpse, _ = build_formula_payloads()
    corrected_formula_bonus, _ = build_corrected_formula_bonus()
    expected_new_regions = {
        LIVING_CURE_CALL_VA: relative_call(LIVING_CURE_CALL_VA, LIVE_LOG_WRAPPER_VA),
        CORPSE_CALC_CALL_VA: relative_call(CORPSE_CALC_CALL_VA, CORPSE_LOG_WRAPPER_VA),
        MASS_CORPSE_CALC_CALL_VA: relative_call(MASS_CORPSE_CALC_CALL_VA, CORPSE_LOG_WRAPPER_VA),
        MASS_INIT_VA: payloads["mass_init"],
        MASS_FLUSH_VA: relative_jump(MASS_FLUSH_VA, FLUSH_TRAMPOLINE_VA),
        LIVE_LOG_WRAPPER_VA: payloads["live_wrapper"],
        CORPSE_LOG_WRAPPER_VA: payloads["corpse_wrapper"],
        RECORD_HELPER_VA: payloads["record_helper"],
        APPEND_HELPER_VA: payloads["append_helper"],
        0x0065DCA0: payloads["flush_helper"],
        FLUSH_TRAMPOLINE_VA: payloads["flush_trampoline"],
        TREATMENT_FORMAT_VA: TREATMENT_FORMAT,
        BONUS_CALC_VA: corrected_formula_bonus,
    }
    for name in EXE_NAMES:
        source = (source_root / name).read_bytes()
        candidate_path = candidate_root / name
        candidate = candidate_path.read_bytes()
        source_pe = pefile.PE(data=source, fast_load=False)
        candidate_pe = pefile.PE(data=candidate, fast_load=False)
        source_bonus_offset = va_to_offset(source_pe, BONUS_CALC_VA)
        if source[source_bonus_offset : source_bonus_offset + len(source_formula_bonus)] != source_formula_bonus:
            raise RuntimeError(f"{name}: V1.03 source formula helper mismatch")
        for va, expected in expected_new_regions.items():
            offset = va_to_offset(candidate_pe, va)
            if candidate[offset : offset + len(expected)] != expected:
                raise RuntimeError(f"{name}: payload mismatch at {va:#x}")
        for va, expected in (
            (DISPATCH_VA, formula_dispatch),
            (BONUS_CALC_VA, corrected_formula_bonus),
            (CORPSE_CURE_CALC_VA, formula_corpse),
        ):
            offset = va_to_offset(candidate_pe, va)
            if candidate[offset : offset + len(expected)] != expected:
                raise RuntimeError(f"{name}: V1.03 formula changed at {va:#x}")

        source_capture_start = va_to_offset(source_pe, RES_CAPTURE_VA)
        source_capture_end = va_to_offset(source_pe, MASS_FLUSH_VA)
        candidate_capture_start = va_to_offset(candidate_pe, RES_CAPTURE_VA)
        candidate_capture_end = va_to_offset(candidate_pe, MASS_FLUSH_VA)
        if source[source_capture_start:source_capture_end] != candidate[candidate_capture_start:candidate_capture_end]:
            raise RuntimeError(f"{name}: original resurrection capture body changed")
        source_flush_start = va_to_offset(source_pe, MASS_FLUSH_CONTINUE_VA)
        source_flush_end = va_to_offset(source_pe, RES_FLUSH_END_VA)
        candidate_flush_start = va_to_offset(candidate_pe, MASS_FLUSH_CONTINUE_VA)
        candidate_flush_end = va_to_offset(candidate_pe, RES_FLUSH_END_VA)
        if source[source_flush_start:source_flush_end] != candidate[candidate_flush_start:candidate_flush_end]:
            raise RuntimeError(f"{name}: original resurrection flush body changed")

        source_book = va_to_offset(source_pe, SPELLBOOK_FORMATTER_CONTEXT_VA)
        candidate_book = va_to_offset(candidate_pe, SPELLBOOK_FORMATTER_CONTEXT_VA)
        if source[source_book : source_book + SPELLBOOK_FORMATTER_CONTEXT_LENGTH] != candidate[
            candidate_book : candidate_book + SPELLBOOK_FORMATTER_CONTEXT_LENGTH
        ]:
            raise RuntimeError(f"{name}: spell-book formatter context changed")

        executable_manifest = next(item for item in manifest["executables"] if item["name"] == name)
        if sha256_file(candidate_path) != executable_manifest["output_sha256"]:
            raise RuntimeError(f"{name}: manifest hash mismatch")
        rollback = bytearray(candidate)
        for region in reversed(executable_manifest["logical_patch_regions"]):
            start = int(region["file_offset"])
            rollback[start : start + int(region["length"])] = bytes.fromhex(region["rollback_hex"])
        if bytes(rollback) != source:
            raise RuntimeError(f"{name}: manifest rollback does not reconstruct V1.03")
        print(f"{name}: single/mass/corpse log hooks + rollback=PASS")

    hota_path = candidate_root / "HotA.dat"
    if sha256_file(hota_path) != SOURCE_HOTA_DAT_SHA256:
        raise RuntimeError("HotA.dat changed")
    hota_data = hota_path.read_bytes()
    _, astra_blob_offset, _ = locate_astra_hdat_blob(hota_data)
    skill_offset = astra_blob_offset + ASTRA_SKILL_BLOCK_OFFSET
    if hota_data[skill_offset : skill_offset + len(ASTRA_SKILLS_AFTER)] != ASTRA_SKILLS_AFTER:
        raise RuntimeError("Astra Wisdom/Water skills changed")
    print("HotA.dat and Astra Wisdom/Water skills=PASS")

    for relative in LANGUAGE_ARCHIVES:
        if (candidate_root / relative).read_bytes() != (source_root / relative).read_bytes():
            raise RuntimeError(f"Language archive changed: {relative}")
    print("Both HeroSpec language archives byte-preserved=PASS")

    loose_source = args.loose_herospec.resolve().read_bytes()
    if sha256_file(args.loose_herospec.resolve()) != LOOSE_HEROSPEC_SOURCE_SHA256:
        raise RuntimeError("Loose HeroSpec source hash mismatch")
    loose_candidate = (candidate_root / Path(LOOSE_HEROSPEC_RELATIVE)).read_bytes()
    old_row = LOOSE_HEROSPEC_OLD_ROW.encode("gb18030")
    new_row = LOOSE_HEROSPEC_NEW_ROW.encode("gb18030")
    if loose_source.count(old_row) != 1 or new_row in loose_source:
        raise RuntimeError("Unexpected loose HeroSpec source row")
    if loose_candidate.count(new_row) != 1 or old_row in loose_candidate:
        raise RuntimeError("Loose HeroSpec concise Cure row mismatch")
    if loose_candidate.replace(new_row, old_row, 1) != loose_source:
        raise RuntimeError("Loose HeroSpec rollback mismatch")
    if sha256_file(candidate_root / Path(LOOSE_HEROSPEC_RELATIVE)) != manifest["loose_herospec"]["output_sha256"]:
        raise RuntimeError("Loose HeroSpec manifest hash mismatch")
    print("HD Chinese loose HeroSpec override + rollback=PASS")

    expected_samples = {
        (1, 1, 1, 1): 40,
        (1, 1, 1, 2): 50,
        (1, 1, 7, 1): 60,
        (1, 1, 7, 3): 80,
        (10, 10, 7, 3): 363,
    }
    for arguments, expected in expected_samples.items():
        if total_cure(*arguments) != expected:
            raise RuntimeError(f"Formula sample changed: {arguments}")
    print("F6 Direct mathematical sample matrix + corrected tier source=PASS")

    package_members = sorted(
        path.relative_to(candidate_root).as_posix()
        for path in candidate_root.rglob("*")
        if path.is_file()
    )
    with zipfile.ZipFile(candidate_zip, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Candidate ZIP CRC failure")
        if sorted(archive.namelist()) != package_members:
            raise RuntimeError("Candidate ZIP member mismatch")
    if sorted(manifest["package_file_hashes"]) != package_members:
        raise RuntimeError("Manifest member mismatch")
    for relative, expected_hash in manifest["package_file_hashes"].items():
        if sha256_file(candidate_root / relative) != expected_hash:
            raise RuntimeError(f"Package hash mismatch: {relative}")
    print("ZIP CRC/member/hash verification=PASS")
    if args.reproducible_zip:
        print("Independent reproducible build=PASS")
    print(f"ZIP SHA-256 {manifest['zip_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
