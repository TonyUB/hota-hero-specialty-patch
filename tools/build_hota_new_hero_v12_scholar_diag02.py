#!/usr/bin/env python3
"""Build the in-place Coronius Scholar diagnostic from formal V1.14.

DIAG01 appended a sixth PE section and the user reported an early New Scenario
crash before any Scholar record was written.  DIAG02 keeps the same transparent
entry logger and Expert Scholar artwork, but places the logger exclusively in
the verified zero tail (offset 0x800..0xFFF) of V1.14's existing .luck3 section.
No PE section is appended and all existing V1.14 payload bytes are preserved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path
from typing import Any

import capstone
import pefile
from capstone.x86_const import X86_OP_IMM

from build_hota_new_hero_v1 import (
    EXE_NAMES,
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)
from build_hota_new_hero_v104 import contiguous_differences
import build_hota_new_hero_v12_scholar_diag01 as base


BUILD_NAME = "HOTA_NEW_HERO_V1.2_SCHOLAR_DIAG02"
SOURCE_NAME = base.SOURCE_NAME
SOURCE_ZIP_SHA256 = base.SOURCE_ZIP_SHA256
SOURCE_EXE_SHA256 = base.SOURCE_EXE_SHA256
LOG_FILENAME = "hota_scholar_diag02.bin"

LUCK_SECTION_NAME = b".luck3\0\0"
LUCK_SECTION_RVA = 0x002E7000
LUCK_SECTION_VA = base.IMAGE_BASE + LUCK_SECTION_RVA
LUCK_SECTION_SIZE = 0x1000
LUCK_SECTION_RAW_OFFSET = 0x002CC000
LUCK_SECTION_CHARACTERISTICS = 0xE0000020
SOURCE_LUCK_SECTION_SHA256 = "e3be451a919ae0d419320cc2ca000121a5cbc44fcbb3000dddecc74e6d9d671f"
PRESERVED_FORMAL_END = 0x800

LOGGER_VA = LUCK_SECTION_VA + 0x800
ENTRY_WRAPPER_VA = LUCK_SECTION_VA + 0x980
DATA_VA = LUCK_SECTION_VA + 0xD00


def configure_base() -> None:
    base.BUILD_NAME = BUILD_NAME
    base.LOG_FILENAME = LOG_FILENAME
    base.DIAG_SECTION_NAME = LUCK_SECTION_NAME
    base.DIAG_SECTION_RVA = LUCK_SECTION_RVA
    base.DIAG_SECTION_VA = LUCK_SECTION_VA
    base.DIAG_SECTION_SIZE = LUCK_SECTION_SIZE
    base.LOGGER_VA = LOGGER_VA
    base.ENTRY_WRAPPER_VA = ENTRY_WRAPPER_VA
    base.DATA_VA = DATA_VA


configure_base()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def patch_executable(path: Path, payload: bytes, payload_meta: dict[str, Any]) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != SOURCE_EXE_SHA256[path.name]:
        raise RuntimeError(f"unexpected {SOURCE_NAME} source hash for {path.name}")
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != base.IMAGE_BASE or pe.OPTIONAL_HEADER.DllCharacteristics & 0x40:
        raise RuntimeError(f"unexpected image base or ASLR in {path.name}")
    if pe.FILE_HEADER.NumberOfSections != 5 or pe.OPTIONAL_HEADER.SizeOfImage != 0x2E8000:
        raise RuntimeError(f"unexpected V1.14 PE layout in {path.name}")
    section = pe.sections[-1]
    if (
        section.Name != LUCK_SECTION_NAME
        or section.VirtualAddress != LUCK_SECTION_RVA
        or section.PointerToRawData != LUCK_SECTION_RAW_OFFSET
        or section.SizeOfRawData != LUCK_SECTION_SIZE
        or section.Characteristics != LUCK_SECTION_CHARACTERISTICS
    ):
        raise RuntimeError(f"unexpected V1.14 .luck3 layout in {path.name}")
    source_section = original[LUCK_SECTION_RAW_OFFSET:LUCK_SECTION_RAW_OFFSET + LUCK_SECTION_SIZE]
    if sha256_bytes(source_section) != SOURCE_LUCK_SECTION_SHA256:
        raise RuntimeError(f"unexpected V1.14 .luck3 payload in {path.name}")
    if any(source_section[PRESERVED_FORMAL_END:]):
        raise RuntimeError(f"V1.14 .luck3 reserved tail is not zero in {path.name}")
    if len(payload) != LUCK_SECTION_SIZE or any(payload[:PRESERVED_FORMAL_END]):
        raise RuntimeError("DIAG02 payload touches the preserved V1.14 .luck3 prefix")

    imports = base.import_addresses(pe)
    for name, expected in base.IAT.items():
        if imports.get(name) != expected:
            raise RuntimeError(f"unexpected {name} IAT in {path.name}: {imports.get(name)!r}")
    hook_offset = pe.get_offset_from_rva(base.SCHOLAR_ENTRY_VA - base.IMAGE_BASE)
    if original[hook_offset:hook_offset + len(base.SCHOLAR_ENTRY_ORIGINAL)] != base.SCHOLAR_ENTRY_ORIGINAL:
        raise RuntimeError(f"Scholar entry bytes changed in {path.name}")

    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    original_checksum = original[checksum_offset:checksum_offset + 4]
    hook = base.relative_jump(
        base.SCHOLAR_ENTRY_VA,
        ENTRY_WRAPPER_VA,
        len(base.SCHOLAR_ENTRY_ORIGINAL),
    )
    patched = bytearray(original)
    patched[hook_offset:hook_offset + len(hook)] = hook
    tail_start = LUCK_SECTION_RAW_OFFSET + PRESERVED_FORMAL_END
    patched[tail_start:LUCK_SECTION_RAW_OFFSET + LUCK_SECTION_SIZE] = payload[PRESERVED_FORMAL_END:]
    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)

    parsed = pefile.PE(data=final, fast_load=False)
    final_section = final[LUCK_SECTION_RAW_OFFSET:LUCK_SECTION_RAW_OFFSET + LUCK_SECTION_SIZE]
    if parsed.FILE_HEADER.NumberOfSections != 5 or parsed.OPTIONAL_HEADER.SizeOfImage != 0x2E8000:
        raise RuntimeError(f"DIAG02 changed the PE section layout in {path.name}")
    if final_section[:PRESERVED_FORMAL_END] != source_section[:PRESERVED_FORMAL_END]:
        raise RuntimeError(f"DIAG02 changed formal .luck3 bytes in {path.name}")
    if final_section[PRESERVED_FORMAL_END:] != payload[PRESERVED_FORMAL_END:]:
        raise RuntimeError(f"DIAG02 reserved-tail payload mismatch in {path.name}")
    if parsed.verify_checksum() is not True:
        raise RuntimeError(f"DIAG02 PE checksum invalid in {path.name}")

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    instruction = next(decoder.disasm(final[hook_offset:hook_offset + 5], base.SCHOLAR_ENTRY_VA))
    if (
        instruction.mnemonic != "jmp"
        or not instruction.operands
        or instruction.operands[0].type != X86_OP_IMM
        or int(instruction.operands[0].imm) != ENTRY_WRAPPER_VA
    ):
        raise RuntimeError(f"DIAG02 Scholar hook target mismatch in {path.name}")

    restored = bytearray(final)
    restored[hook_offset:hook_offset + len(base.SCHOLAR_ENTRY_ORIGINAL)] = base.SCHOLAR_ENTRY_ORIGINAL
    restored[LUCK_SECTION_RAW_OFFSET:LUCK_SECTION_RAW_OFFSET + LUCK_SECTION_SIZE] = source_section
    restored[checksum_offset:checksum_offset + 4] = original_checksum
    if bytes(restored) != original:
        raise RuntimeError(f"DIAG02 full rollback failed in {path.name}")

    path.write_bytes(final)
    return {
        "name": path.name,
        "source_size": len(original),
        "output_size": len(final),
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "hook": {
            "role": "native Scholar exchange entry",
            "va": f"0x{base.SCHOLAR_ENTRY_VA:08X}",
            "file_offset": f"0x{hook_offset:X}",
            "source_hex": base.SCHOLAR_ENTRY_ORIGINAL.hex(" "),
            "patched_hex": hook.hex(" "),
            "rollback_hex": base.SCHOLAR_ENTRY_ORIGINAL.hex(" "),
            "target_va": f"0x{ENTRY_WRAPPER_VA:08X}",
        },
        "existing_section": {
            "name": ".luck3",
            "rva": f"0x{LUCK_SECTION_RVA:08X}",
            "source_sha256": SOURCE_LUCK_SECTION_SHA256,
            "preserved_prefix": ["0x000", f"0x{PRESERVED_FORMAL_END:03X}"],
            "diagnostic_tail": [f"0x{PRESERVED_FORMAL_END:03X}", "0x1000"],
            "diagnostic_tail_sha256": sha256_bytes(payload[PRESERVED_FORMAL_END:]),
        },
        "payload": payload_meta,
        "contiguous_differences": contiguous_differences(original, final),
        "section_count_preserved": True,
        "file_size_preserved": True,
        "pe_checksum_valid": True,
        "rollback_reconstructs_source": True,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与诊断说明

这是从正式 {SOURCE_NAME} 构建的科洛尼斯学术特第二阶段诊断包，用于修正 DIAG01 在“单人游戏→新建场景”时的提前闪退。

修正：不再新增第六个 PE 节。诊断代码只使用正式 V1.14 既有 .luck3 节中从 0x800 开始、经逐字节验证为空的保留区；正式固定幸运 +3、逐队首次攻击幸运和其他原有代码保持不变。

本包继续把科洛尼斯（壁垒、原屠戮特）的特长图标替换为游戏内“高级学术 / Expert Scholar”的原生第 56 帧，没有使用 Advanced Scholar（中级学术）的第 55 帧。

本阶段仍不改变学术传授效果，只在科洛尼斯参与友方英雄会面时生成 {LOG_FILENAME}，随后完整执行 V1.14 原生逻辑。

安装与测试：
1. 必须覆盖到纯净 HotA 1.8.0，不能叠加 DIAG01。
2. 使用 h3hota HD.exe 启动，先进入“单人游戏→新建场景”，确认不再闪退。
3. 进入地图，让科洛尼斯与一名己方英雄会面并打开交换界面；双方最好都有魔法书。
4. 退出游戏，把根目录生成的 {LOG_FILENAME} 上传给 Codex。
5. 同时确认科洛尼斯显示的是高级学术图标。

如果仍在“新建场景”阶段闪退，即可把根因进一步收敛到图标资源；该阶段尚未执行学术 Hook，不要求存在日志。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--secskill-def", type=Path, required=True)
    parser.add_argument("--secskill32-def", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_zip = args.source_zip.resolve()
    build_root = args.build_root.resolve()
    output_root = args.output_root.resolve()
    if sha256_file(source_zip) != SOURCE_ZIP_SHA256:
        raise RuntimeError(f"formal {SOURCE_NAME} ZIP hash mismatch")

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    payload, payload_meta = base.build_payload()
    executable_reports = [patch_executable(package_root / name, payload, payload_meta) for name in EXE_NAMES]
    icon_report = base.install_icons(
        package_root,
        args.secskill_def.resolve(),
        args.secskill32_def.resolve(),
    )

    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("expected exactly one root installation text file")
    instruction_files[0].write_text(installation_text(), encoding="utf-8")
    instruction_relative = instruction_files[0].relative_to(package_root).as_posix()
    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    if not set(source_hashes).issubset(package_hashes):
        raise RuntimeError("DIAG02 removed formal V1.14 members")
    changed = {
        relative for relative in source_hashes
        if source_hashes[relative] != package_hashes[relative]
    }
    added = set(package_hashes) - set(source_hashes)
    expected_changed = set(EXE_NAMES) | set(base.D32F_RELATIVES) | {instruction_relative}
    if changed != expected_changed or added != {base.LOOSE_ICON_RELATIVE}:
        raise RuntimeError(
            f"unexpected DIAG02 package delta: changed={sorted(changed)} added={sorted(added)}"
        )

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"DIAG02 ZIP CRC failure: {failed}")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("DIAG02 ZIP member set mismatch")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "diagnostic_only": True,
        "gameplay_logic_changed": False,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "withdrawn_predecessor": {
            "name": "HOTA_NEW_HERO_V1.2_SCHOLAR_DIAG01",
            "reason": "user-reported New Scenario crash before any Scholar log; sixth PE section removed",
        },
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "log_filename": LOG_FILENAME,
        "changed_package_files": sorted(changed),
        "added_package_files": sorted(added),
        "source_file_hashes": source_hashes,
        "package_file_hashes": package_hashes,
        "executables": executable_reports,
        "icons": icon_report,
        "static_verification": {
            "formal_v114_source_hashes_verified": True,
            "no_new_pe_section": True,
            "section_count_and_file_size_preserved": True,
            "formal_luck3_prefix_0x000_0x7ff_byte_preserved": True,
            "only_verified_zero_tail_0x800_0xfff_used": True,
            "standard_and_hd_payload_identical": True,
            "expert_scholar_frame_56_preserved_from_diag01": True,
            "full_executable_and_icon_frame_rollbacks_verified": True,
            "zip_crc_and_member_checks_passed": True,
        },
        "runtime_acceptance": {
            "status": "pending New Scenario survival and returned Coronius meeting log",
        },
    }
    (output_root / f"{BUILD_NAME}_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / f"{BUILD_NAME}_README.md").write_text(installation_text(), encoding="utf-8")
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    for item in executable_reports:
        print(f"{item['name']}: {item['output_sha256']}")
    print(f"Runtime log: {LOG_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
