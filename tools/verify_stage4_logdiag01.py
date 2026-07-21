#!/usr/bin/env python3
"""Verify LOGDIAG01 reproducibility and its delta from TEST12."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pefile

import build_stage4_logdiag01 as diag
import analyze_stage4_logdiag01 as analyzer
from build_diag_patch import contiguous_differences, va_to_offset


ROOT = Path(__file__).resolve().parent.parent
TEST12_NAME = "Patch_v2.6_VISUAL_TEST12"
FORMAL_V25_SHA256 = (
    "cb7cc074219d0934b90b2fd3d06885786adb56f1f1d0d27f757b1bb2df5193e9"
)
ALLOWED_TEST12_DELTA_VAS = (
    (diag.NATIVE_CURE_POST_APPEND_HOOK_VA, diag.NATIVE_CURE_POST_APPEND_HOOK_VA + 5),
    (diag.MASS_HELPER_INIT_SITE_VA, diag.MASS_HELPER_INIT_SITE_VA + 7),
    (diag.COUNTED_RESURRECTION_SITE_VA, diag.COUNTED_RESURRECTION_SITE_VA + 15),
    (diag.WRAPPER_INIT_SITE_VA, diag.WRAPPER_INIT_SITE_VA + 7),
    (diag.DIAG_CAVE_VA, diag.DIAG_CAVE_END_VA),
)


def main() -> int:
    synthetic = b"".join(
        analyzer.RECORD.pack(analyzer.MAGIC, event, a, b, c, d)
        for event, a, b, c, d in (
            (1, 0x005A1BB9, 0x80, 0x10000000, 0),
            (3, 0x81, 0x10000010, 100, 0x00639EA0),
            (3, 0x82, 0x10000020, 200, 0x00639EA0),
            (3, 0x83, 0x10000030, 300, 0x00639EA0),
            (4, 0x83, 0x20000000, 0x20000020, 0x30000000),
            (5, 3, 0x20000010, 0x30000000, 0x30000010),
            (6, 3, 0x20000010, 0x30000000, 0x30000010),
        )
    )
    synthetic_report = analyzer.parse_bytes(synthetic)
    if "另一层显示缓存" not in synthetic_report["diagnosis"][-1]:
        raise RuntimeError("Diagnostic parser synthetic verdict changed")

    first_root = ROOT / "build" / "logdiag01_a" / diag.BUILD_NAME
    second_root = ROOT / "build" / "logdiag01_b" / diag.BUILD_NAME
    test12_root = ROOT / "build" / "logdiag01_ref12" / TEST12_NAME
    first_zip = ROOT / "outputs" / "logdiag01_a" / f"{diag.BUILD_NAME}.zip"
    second_zip = ROOT / "outputs" / "logdiag01_b" / f"{diag.BUILD_NAME}.zip"
    manifest_path = (
        ROOT / "outputs" / "logdiag01_a" / f"{diag.BUILD_NAME}_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    first_files = sorted(
        path.relative_to(first_root)
        for path in first_root.rglob("*")
        if path.is_file()
    )
    second_files = sorted(
        path.relative_to(second_root)
        for path in second_root.rglob("*")
        if path.is_file()
    )
    if first_files != second_files:
        raise RuntimeError("Reproducible builds have different member sets")
    for relative in first_files:
        if (first_root / relative).read_bytes() != (second_root / relative).read_bytes():
            raise RuntimeError(f"Reproducible build mismatch: {relative}")
    if first_zip.read_bytes() != second_zip.read_bytes():
        raise RuntimeError("Reproducible ZIP bytes differ")
    with zipfile.ZipFile(first_zip) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"ZIP CRC failure: {bad_member}")

    payload, _, _ = diag.build_diag_payload()
    for name in ("h3hota.exe", "h3hota HD.exe"):
        test12_bytes = (test12_root / name).read_bytes()
        diagnostic = (first_root / name).read_bytes()
        if len(test12_bytes) != len(diagnostic):
            raise RuntimeError(f"PE size changed: {name}")
        pe = pefile.PE(data=test12_bytes, fast_load=False)
        allowed_offsets = list(
            (va_to_offset(pe, start), va_to_offset(pe, end - 1) + 1)
            for start, end in ALLOWED_TEST12_DELTA_VAS
        )
        rdata = next(
            section for section in pe.sections if section.Name.rstrip(b"\0") == b".rdata"
        )
        virtual_size_offset = rdata.get_file_offset() + 8
        allowed_offsets.append((virtual_size_offset, virtual_size_offset + 4))
        differences = contiguous_differences(test12_bytes, diagnostic)
        for difference in differences:
            start = difference["start_offset"]
            end = difference["end_offset_exclusive"]
            if not any(
                allowed_start <= start and end <= allowed_end
                for allowed_start, allowed_end in allowed_offsets
            ):
                raise RuntimeError(
                    f"Unexpected TEST12 delta in {name}: 0x{start:X}-0x{end:X}"
                )

        clean_path = ROOT / "baselines" / "hota180_clean" / name
        patched_path = ROOT / "baselines" / "Patch_v1.8" / name
        for candidate in (clean_path, patched_path):
            candidate_bytes = candidate.read_bytes()
            candidate_pe = pefile.PE(data=candidate_bytes, fast_load=False)
            start = va_to_offset(candidate_pe, diag.DIAG_CAVE_VA)
            end = va_to_offset(candidate_pe, diag.DIAG_CAVE_END_VA - 1) + 1
            if candidate_bytes[start:end] != bytes(end - start):
                raise RuntimeError(f"Diagnostic cave not zero in {candidate}")

        executable = next(
            item for item in manifest["executables"] if item["name"] == name
        )
        required = (
            "rollback_reconstructs_input",
            "diagnostic_only_addition",
            "diagnostic_cave_rwx",
            "diagnostic_rdata_virtual_size_no_section_overlap",
            "diagnostic_call_sites_same_size",
            "test12_gameplay_and_visual_paths_preserved",
        )
        for field in required:
            if not executable[field]:
                raise RuntimeError(f"{field} verification failed: {name}")
        if executable["diagnostic_log_filename"] != diag.LOG_FILENAME:
            raise RuntimeError(f"Diagnostic filename changed: {name}")
        if executable["diagnostic_payload"]["payload_size"] != len(payload):
            raise RuntimeError(f"Diagnostic payload size changed: {name}")
        output_pe = pefile.PE(data=diagnostic, fast_load=False)
        output_rdata = next(
            section
            for section in output_pe.sections
            if section.Name.rstrip(b"\0") == b".rdata"
        )
        if output_rdata.Misc_VirtualSize != output_rdata.SizeOfRawData:
            raise RuntimeError(f"Diagnostic .rdata padding is not mapped: {name}")
        print(f"{name}: TEST12 delta ranges={len(differences)}; rollback=PASS")

    formal = ROOT / "OLD" / "Patch_v2.5.zip"
    formal_hash = hashlib.sha256(formal.read_bytes()).hexdigest()
    if formal_hash != FORMAL_V25_SHA256:
        raise RuntimeError("Archived Patch_v2.5.zip changed")
    diagnostic_hash = hashlib.sha256(first_zip.read_bytes()).hexdigest()
    print("Reproducible build: PASS")
    print("ZIP CRC: PASS")
    print("Clean/Patch_v1.8 diagnostic padding: PASS")
    print("Diagnostic parser synthetic case: PASS")
    print(f"Formal v2.5 unchanged: {formal_hash}")
    print(f"LOGDIAG01 ZIP SHA-256: {diagnostic_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
