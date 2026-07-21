#!/usr/bin/env python3
"""Verify TEST11 reproducibility and its allowed binary delta from TEST4."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pefile

from build_diag_patch import contiguous_differences, va_to_offset


ROOT = Path(__file__).resolve().parent.parent
BUILD_NAME = "Patch_v2.6_VISUAL_TEST11"
TEST4_NAME = "Patch_v2.6_VISUAL_TEST4"
FORMAL_V25_SHA256 = (
    "cb7cc074219d0934b90b2fd3d06885786adb56f1f1d0d27f757b1bb2df5193e9"
)
ALLOWED_TEST4_DELTA_VAS = (
    (0x005A1AFA, 0x005A1AFA + 53),
    (0x005A1B97, 0x005A1B9C),
    (0x005A1BF6, 0x005A1BFB),
    (0x00639C29, 0x00639CF5),
    (0x00639DD0, 0x00639F10),
)


def main() -> int:
    first_root = ROOT / "build" / "test11_a" / BUILD_NAME
    second_root = ROOT / "build" / "test11_b" / BUILD_NAME
    test4_root = ROOT / "build" / "test10_ref4" / TEST4_NAME
    first_zip = ROOT / "outputs" / "test11_a" / f"{BUILD_NAME}.zip"
    second_zip = ROOT / "outputs" / "test11_b" / f"{BUILD_NAME}.zip"
    manifest_path = ROOT / "outputs" / "test11_a" / f"{BUILD_NAME}_manifest.json"
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

    for name in ("h3hota.exe", "h3hota HD.exe"):
        test4 = (test4_root / name).read_bytes()
        test11 = (first_root / name).read_bytes()
        if len(test4) != len(test11):
            raise RuntimeError(f"PE size changed: {name}")
        pe = pefile.PE(data=test4, fast_load=False)
        allowed_offsets = tuple(
            (va_to_offset(pe, start), va_to_offset(pe, end - 1) + 1)
            for start, end in ALLOWED_TEST4_DELTA_VAS
        )
        differences = contiguous_differences(test4, test11)
        for difference in differences:
            start = difference["start_offset"]
            end = difference["end_offset_exclusive"]
            if not any(
                allowed_start <= start and end <= allowed_end
                for allowed_start, allowed_end in allowed_offsets
            ):
                raise RuntimeError(
                    f"Unexpected TEST4 delta in {name}: 0x{start:X}-0x{end:X}"
                )
        executable = next(
            item for item in manifest["executables"] if item["name"] == name
        )
        required = (
            "rollback_reconstructs_input",
            "combat_log_vector_layout_statically_verified",
            "mass_log_start_recorded_on_first_effective_native_check",
            "mass_log_rotation_runs_as_native_cure_log_return_continuation",
            "mass_log_rotation_refreshes_native_log_view",
            "mass_test4_bytes_changed_only_at_two_native_calls",
        )
        for field in required:
            if not executable[field]:
                raise RuntimeError(f"{field} verification failed: {name}")
        print(f"{name}: TEST4 delta ranges={len(differences)}; rollback=PASS")

    formal = ROOT / "Download" / "Patch_v2.5.zip"
    formal_hash = hashlib.sha256(formal.read_bytes()).hexdigest()
    if formal_hash != FORMAL_V25_SHA256:
        raise RuntimeError("Formal Patch_v2.5.zip changed")
    test11_hash = hashlib.sha256(first_zip.read_bytes()).hexdigest()
    print("Reproducible build: PASS")
    print("ZIP CRC: PASS")
    print(f"Formal v2.5 unchanged: {formal_hash}")
    print(f"TEST11 ZIP SHA-256: {test11_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
