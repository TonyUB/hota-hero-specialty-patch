#!/usr/bin/env python3
"""Verify TEST13 reproducibility, rollback metadata, and its TEST12 delta."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pefile
from capstone.x86_const import X86_OP_IMM

import build_stage4_visual_patch13 as test13
from build_diag_patch import contiguous_differences, va_to_offset


ROOT = Path(__file__).resolve().parent.parent
TEST12_NAME = "Patch_v2.6_VISUAL_TEST12"
FORMAL_V25_SHA256 = (
    "cb7cc074219d0934b90b2fd3d06885786adb56f1f1d0d27f757b1bb2df5193e9"
)
ALLOWED_TEST12_DELTA_VAS = (
    (test13.MASS_HELPER_INIT_SITE_VA, test13.MASS_HELPER_INIT_SITE_VA + 7),
    (test13.RESURRECTION_LOG_CALL_VA, test13.RESURRECTION_LOG_CALL_VA + 5),
    (
        test13.NATIVE_CURE_POST_APPEND_HOOK_VA,
        test13.NATIVE_CURE_POST_APPEND_HOOK_VA + 5,
    ),
    (test13.PAYLOAD_CAVE_VA, test13.PAYLOAD_CAVE_END_VA),
)


def files_under(root: Path) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())


def main() -> int:
    first_root = ROOT / "build" / "test13_a" / test13.BUILD_NAME
    second_root = ROOT / "build" / "test13_b" / test13.BUILD_NAME
    test12_root = ROOT / "build" / "logdiag01_ref12" / TEST12_NAME
    first_zip = ROOT / "outputs" / "test13_a" / f"{test13.BUILD_NAME}.zip"
    second_zip = ROOT / "outputs" / "test13_b" / f"{test13.BUILD_NAME}.zip"
    manifest = json.loads(
        (
            ROOT
            / "outputs"
            / "test13_a"
            / f"{test13.BUILD_NAME}_manifest.json"
        ).read_text(encoding="utf-8")
    )

    first_files = files_under(first_root)
    second_files = files_under(second_root)
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

    payload, metadata, codes = test13.build_deferred_payload()
    decode = test13.test12.test10.test9.test8.decode_instructions
    defer_instructions = decode(
        codes["defer_or_append_resurrection_log"], test13.DEFER_WRAPPER_VA
    )
    replay_instructions = decode(
        codes["replay_deferred_resurrection_logs"], test13.POST_CURE_REPLAY_VA
    )
    ret_immediates = [
        instruction.operands[0].imm
        for instruction in defer_instructions
        if instruction.mnemonic == "ret"
        and instruction.operands
        and instruction.operands[0].type == X86_OP_IMM
    ]
    if ret_immediates != [0x0C]:
        raise RuntimeError(f"Deferred native-call stack cleanup changed: {ret_immediates}")
    replay_calls = test13.test12.test10.test9.direct_call_targets(replay_instructions)
    if replay_calls != [test13.SPRINTF_VA, test13.NATIVE_LOG_APPEND_VA]:
        raise RuntimeError(f"Replay call order changed: {replay_calls}")

    for name in ("h3hota.exe", "h3hota HD.exe"):
        test12_bytes = (test12_root / name).read_bytes()
        candidate = (first_root / name).read_bytes()
        if len(test12_bytes) != len(candidate):
            raise RuntimeError(f"PE size changed: {name}")
        pe = pefile.PE(data=test12_bytes, fast_load=False)
        allowed_offsets = [
            (va_to_offset(pe, start), va_to_offset(pe, end - 1) + 1)
            for start, end in ALLOWED_TEST12_DELTA_VAS
        ]
        rdata = next(
            section for section in pe.sections if section.Name.rstrip(b"\0") == b".rdata"
        )
        virtual_size_offset = rdata.get_file_offset() + 8
        allowed_offsets.append((virtual_size_offset, virtual_size_offset + 4))
        differences = contiguous_differences(test12_bytes, candidate)
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

        for baseline_name in ("hota180_clean", "Patch_v1.8"):
            baseline_path = ROOT / "baselines" / baseline_name / name
            baseline = baseline_path.read_bytes()
            baseline_pe = pefile.PE(data=baseline, fast_load=False)
            start = va_to_offset(baseline_pe, test13.PAYLOAD_CAVE_VA)
            end = va_to_offset(baseline_pe, test13.PAYLOAD_CAVE_END_VA - 1) + 1
            if baseline[start:end] != bytes(end - start):
                raise RuntimeError(f"TEST13 cave not zero in {baseline_path}")

        executable = next(
            item for item in manifest["executables"] if item["name"] == name
        )
        required = (
            "rollback_reconstructs_input",
            "logdiag01_rotation_succeeded",
            "logdiag01_native_refresh_preserved_rotation",
            "mass_cure_resurrection_log_deferred",
            "deferred_messages_reformatted_with_native_text_tables",
            "deferred_messages_appended_with_native_log_api",
            "single_cure_path_unchanged",
            "ordinary_resurrection_falls_through_to_native_log_api",
            "test13_cave_rwx",
            "test13_rdata_virtual_size_no_section_overlap",
        )
        for field in required:
            if not executable[field]:
                raise RuntimeError(f"{field} verification failed: {name}")
        if executable["deferred_payload"]["payload_size"] != len(payload):
            raise RuntimeError(f"Deferred payload size changed: {name}")
        if executable["deferred_payload"]["max_deferred_records"] != 14:
            raise RuntimeError(f"Deferred capacity changed: {name}")
        output_pe = pefile.PE(data=candidate, fast_load=False)
        output_rdata = next(
            section
            for section in output_pe.sections
            if section.Name.rstrip(b"\0") == b".rdata"
        )
        if output_rdata.Misc_VirtualSize != output_rdata.SizeOfRawData:
            raise RuntimeError(f"TEST13 .rdata padding is not mapped: {name}")
        print(f"{name}: TEST12 delta ranges={len(differences)}; rollback=PASS")

    formal = ROOT / "OLD" / "Patch_v2.5.zip"
    formal_hash = hashlib.sha256(formal.read_bytes()).hexdigest()
    if formal_hash != FORMAL_V25_SHA256:
        raise RuntimeError("Archived Patch_v2.5.zip changed")
    test_hash = hashlib.sha256(first_zip.read_bytes()).hexdigest()
    print("Reproducible build: PASS")
    print("ZIP CRC: PASS")
    print("Deferred ret 0x0C stack cleanup: PASS")
    print("Native sprintf -> combat-log append order: PASS")
    print("Clean/Patch_v1.8 TEST13 padding: PASS")
    print(f"Formal v2.5 unchanged: {formal_hash}")
    print(f"TEST13 ZIP SHA-256: {test_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
