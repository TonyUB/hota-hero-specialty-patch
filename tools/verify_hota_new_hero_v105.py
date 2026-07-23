#!/usr/bin/env python3
"""Verify HOTA_NEW_HERO_V1.05 and its reproducible build evidence."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

import pefile

from build_hota_new_hero_v1 import EXE_NAMES, extract_zip_safely
from build_hota_new_hero_v103 import BONUS_CALC_VA, IMAGE_BASE
from build_hota_new_hero_v104 import (
    HOTA_UI_HELPER_VA,
    build_corrected_formula_bonus as build_f6_formula_bonus,
    build_hota_ui_helper as build_f6_ui_helper,
    va_to_offset,
)
from build_hota_new_hero_v105 import (
    BUILD_NAME,
    FORMULA_EXPRESSION,
    SOURCE_EXE_SHA256,
    SOURCE_ZIP_SHA256,
    build_f7_formula_bonus,
    build_f7_ui_helper,
    sha256_file,
    total_cure,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--candidate-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reproducible-zip", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_zip = args.source_zip.resolve()
    candidate_zip = args.candidate_zip.resolve()
    manifest = json.loads(args.manifest.resolve().read_text(encoding="utf-8"))
    if sha256_file(source_zip) != SOURCE_ZIP_SHA256:
        raise RuntimeError("V1.04 source ZIP hash mismatch")
    if manifest["build_name"] != BUILD_NAME or manifest["release"] is not True:
        raise RuntimeError("Manifest build identity mismatch")
    if manifest["formula"]["expression"] != FORMULA_EXPRESSION:
        raise RuntimeError("Manifest formula mismatch")
    if sha256_file(candidate_zip) != manifest["zip_sha256"]:
        raise RuntimeError("Candidate ZIP hash does not match manifest")
    if args.reproducible_zip and sha256_file(args.reproducible_zip.resolve()) != manifest["zip_sha256"]:
        raise RuntimeError("Reproducible ZIP hash mismatch")

    expected_samples = [
        [40, 43, 46, 50, 53, 56, 60],
        [84, 91, 98, 105, 112, 119, 126],
        [76, 80, 84, 88, 93, 97, 101],
        [119, 126, 133, 140, 147, 154, 161],
        [159, 170, 182, 193, 205, 216, 228],
        [314, 334, 355, 376, 397, 417, 438],
        [499, 528, 558, 588, 618, 648, 678],
    ]
    sample_inputs = [(1, 1, 1), (5, 1, 1), (2, 4, 2), (5, 4, 3), (10, 5, 1), (20, 10, 3), (30, 25, 3)]
    actual_samples = [
        [total_cure(level, power, tier, water) for tier in range(1, 8)]
        for level, power, water in sample_inputs
    ]
    if actual_samples != expected_samples:
        raise RuntimeError("F7 reference samples failed")
    for level, power, water in sample_inputs:
        for tier in range(1, 8):
            if total_cure(level, power + 1, tier, water) - total_cure(level, power, tier, water) != 5:
                raise RuntimeError("Per-power +5 invariant failed")
    for level, power in ((1, 1), (5, 4), (20, 10)):
        for tier in range(1, 8):
            base = total_cure(level, power, tier, 1)
            if total_cure(level, power, tier, 0) != base:
                raise RuntimeError("No Water and Basic Water must match")
            if total_cure(level, power, tier, 2) != base + 10:
                raise RuntimeError("Advanced Water +10 invariant failed")
            if total_cure(level, power, tier, 3) != base + 20:
                raise RuntimeError("Expert Water +20 invariant failed")

    f6_formula, _ = build_f6_formula_bonus()
    f7_formula, _ = build_f7_formula_bonus()
    f6_ui, _ = build_f6_ui_helper()
    f7_ui, _ = build_f7_ui_helper()
    f6_ui_region = f6_ui.ljust(len(f7_ui), b"\x00")

    with tempfile.TemporaryDirectory(prefix="hota_v105_verify_") as temp_dir:
        temp = Path(temp_dir)
        source_root = temp / "source"
        candidate_root = temp / "candidate"
        extract_zip_safely(source_zip, source_root)
        extract_zip_safely(candidate_zip, candidate_root)
        source_members = sorted(
            path.relative_to(source_root).as_posix()
            for path in source_root.rglob("*") if path.is_file()
        )
        candidate_members = sorted(
            path.relative_to(candidate_root).as_posix()
            for path in candidate_root.rglob("*") if path.is_file()
        )
        if candidate_members != source_members:
            raise RuntimeError("Candidate member set differs from V1.04")

        changed = []
        for relative in source_members:
            source_path = source_root / Path(relative)
            candidate_path = candidate_root / Path(relative)
            if source_path.read_bytes() != candidate_path.read_bytes():
                changed.append(relative)
        expected_changes = sorted([*EXE_NAMES, "安装说明.txt"])
        if sorted(changed) != expected_changes:
            raise RuntimeError(f"Unexpected changed files: {changed}")

        release_regions = None
        for name in EXE_NAMES:
            source_path = source_root / name
            candidate_path = candidate_root / name
            if sha256_file(source_path) != SOURCE_EXE_SHA256[name]:
                raise RuntimeError(f"{name}: V1.04 source hash mismatch")
            pe_source = pefile.PE(str(source_path), fast_load=False)
            pe_candidate = pefile.PE(str(candidate_path), fast_load=False)
            if pe_source.OPTIONAL_HEADER.ImageBase != IMAGE_BASE or pe_candidate.OPTIONAL_HEADER.ImageBase != IMAGE_BASE:
                raise RuntimeError(f"{name}: image base mismatch")
            source_bytes = source_path.read_bytes()
            candidate_bytes = candidate_path.read_bytes()
            formula_offset = va_to_offset(pe_source, BONUS_CALC_VA)
            helper_offset = va_to_offset(pe_source, HOTA_UI_HELPER_VA)
            if source_bytes[formula_offset : formula_offset + len(f6_formula)] != f6_formula:
                raise RuntimeError(f"{name}: V1.04 gameplay formula mismatch")
            if candidate_bytes[formula_offset : formula_offset + len(f7_formula)] != f7_formula:
                raise RuntimeError(f"{name}: V1.05 gameplay formula mismatch")
            if source_bytes[helper_offset : helper_offset + len(f6_ui_region)] != f6_ui_region:
                raise RuntimeError(f"{name}: V1.04 UI helper mismatch")
            if candidate_bytes[helper_offset : helper_offset + len(f7_ui)] != f7_ui:
                raise RuntimeError(f"{name}: V1.05 UI helper mismatch")

            restored = bytearray(candidate_bytes)
            restored[formula_offset : formula_offset + len(f6_formula)] = f6_formula
            restored[helper_offset : helper_offset + len(f6_ui_region)] = f6_ui_region
            if bytes(restored) != source_bytes:
                raise RuntimeError(f"{name}: non-formula bytes changed or rollback failed")
            if sha256_file(candidate_path) != manifest["package_file_hashes"][name]:
                raise RuntimeError(f"{name}: output hash mismatch")
            current_regions = (
                candidate_bytes[formula_offset : formula_offset + len(f7_formula)],
                candidate_bytes[helper_offset : helper_offset + len(f7_ui)],
            )
            if release_regions is None:
                release_regions = current_regions
            elif current_regions != release_regions:
                raise RuntimeError("Standard and HD executable formula payloads differ")
            pe_source.close()
            pe_candidate.close()

        for relative, digest in manifest["package_file_hashes"].items():
            if sha256_file(candidate_root / Path(relative)) != digest:
                raise RuntimeError(f"Package member hash mismatch: {relative}")
        if manifest["changed_package_files"] != sorted(expected_changes):
            raise RuntimeError("Manifest changed-file set mismatch")

    with zipfile.ZipFile(candidate_zip, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")

    print(f"Verified {candidate_zip.name}")
    print(f"ZIP SHA-256 {manifest['zip_sha256']}")
    print("F7 formula reference table and monotonic increments: PASS")
    print("Standard/HD gameplay and specialty-panel formulas: identical")
    print("V1.04 non-formula payloads and package resources: byte-preserved")
    print("Rollback to V1.04: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
