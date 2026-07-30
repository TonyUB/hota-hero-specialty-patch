#!/usr/bin/env python3
"""Build the first functional Coronius Scholar-specialty test from V1.14."""

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
import build_hota_new_hero_v12_scholar_diag01 as diag01
import build_hota_new_hero_v12_scholar_diag02 as diag02


BUILD_NAME = "HOTA_NEW_HERO_V1.2_SCHOLAR_TEST01"
SOURCE_NAME = diag02.SOURCE_NAME
SOURCE_ZIP_SHA256 = diag02.SOURCE_ZIP_SHA256
LOG_FILENAME = "hota_scholar_test01.bin"

ACTIVE_VA = diag02.LUCK_SECTION_VA + 0xEF0
WRAPPER_SCHOLAR_H2_VA = diag02.LUCK_SECTION_VA + 0xD80
WRAPPER_SCHOLAR_H1_VA = diag02.LUCK_SECTION_VA + 0xDC0
WRAPPER_WISDOM_EDI_VA = diag02.LUCK_SECTION_VA + 0xE00
WRAPPER_WISDOM_EBX_VA = diag02.LUCK_SECTION_VA + 0xE40

FEATURE_PATCHES = (
    {
        "name": "hero2 Scholar contribution and specialist-active flag",
        "va": 0x004A25CB,
        "continue_va": 0x004A25D1,
        "wrapper_va": WRAPPER_SCHOLAR_H2_VA,
        "source": bytes.fromhex("8A 82 DB 00 00 00"),
    },
    {
        "name": "hero1 Scholar contribution",
        "va": 0x004A25DC,
        "continue_va": 0x004A25E2,
        "wrapper_va": WRAPPER_SCHOLAR_H1_VA,
        "source": bytes.fromhex("8A 8F DB 00 00 00"),
    },
    {
        "name": "ordered hero EDI Wisdom receive cap",
        "va": 0x004A2657,
        "continue_va": 0x004A2661,
        "wrapper_va": WRAPPER_WISDOM_EDI_VA,
        "source": bytes.fromhex("0F BE 87 D0 00 00 00 83 C0 02"),
    },
    {
        "name": "ordered hero EBX Wisdom receive cap",
        "va": 0x004A267C,
        "continue_va": 0x004A2686,
        "wrapper_va": WRAPPER_WISDOM_EBX_VA,
        "source": bytes.fromhex("0F BE 83 D0 00 00 00 83 C0 02"),
    },
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def configure_logger() -> None:
    diag01.BUILD_NAME = BUILD_NAME
    diag01.LOG_FILENAME = LOG_FILENAME


def feature_sources() -> tuple[tuple[str, int, int, str], ...]:
    return (
        (
            "scholar_h2",
            WRAPPER_SCHOLAR_H2_VA,
            WRAPPER_SCHOLAR_H1_VA,
            f"""
            mov byte ptr [{ACTIVE_VA:#x}], 0
            cmp dword ptr [ecx + 0x1a], {diag01.CORONIUS_ID}
            je meeting_specialist
            cmp dword ptr [edx + 0x1a], {diag01.CORONIUS_ID}
            jne meeting_flag_ready
meeting_specialist:
            mov byte ptr [{ACTIVE_VA:#x}], 1
meeting_flag_ready:
            mov al, byte ptr [edx + 0xdb]
            cmp dword ptr [edx + 0x1a], {diag01.CORONIUS_ID}
            jne scholar_h2_ready
            test al, al
            jle scholar_h2_ready
            inc al
scholar_h2_ready:
            push {FEATURE_PATCHES[0]['continue_va']:#x}
            ret
            """,
        ),
        (
            "scholar_h1",
            WRAPPER_SCHOLAR_H1_VA,
            WRAPPER_WISDOM_EDI_VA,
            f"""
            mov cl, byte ptr [edi + 0xdb]
            cmp dword ptr [edi + 0x1a], {diag01.CORONIUS_ID}
            jne scholar_h1_ready
            test cl, cl
            jle scholar_h1_ready
            inc cl
scholar_h1_ready:
            push {FEATURE_PATCHES[1]['continue_va']:#x}
            ret
            """,
        ),
        (
            "wisdom_edi",
            WRAPPER_WISDOM_EDI_VA,
            WRAPPER_WISDOM_EBX_VA,
            f"""
            movsx eax, byte ptr [edi + 0xd0]
            add eax, 2
            cmp byte ptr [{ACTIVE_VA:#x}], 0
            je wisdom_edi_ready
            inc eax
wisdom_edi_ready:
            push {FEATURE_PATCHES[2]['continue_va']:#x}
            ret
            """,
        ),
        (
            "wisdom_ebx",
            WRAPPER_WISDOM_EBX_VA,
            ACTIVE_VA,
            f"""
            movsx eax, byte ptr [ebx + 0xd0]
            add eax, 2
            cmp byte ptr [{ACTIVE_VA:#x}], 0
            je wisdom_ebx_ready
            inc eax
wisdom_ebx_ready:
            push {FEATURE_PATCHES[3]['continue_va']:#x}
            ret
            """,
        ),
    )


def build_payload() -> tuple[bytes, dict[str, Any]]:
    configure_logger()
    base_payload, base_meta = diag01.build_payload()
    payload = bytearray(base_payload)
    components: list[dict[str, Any]] = []
    for name, va, limit, source in feature_sources():
        code = diag01.assemble(source, va)
        if va + len(code) > limit:
            raise RuntimeError(f"{name} exceeds its isolated .luck3 slot")
        start = va - diag02.LUCK_SECTION_VA
        payload[start:start + len(code)] = code
        components.append({
            "name": name,
            "va": f"0x{va:08X}",
            "length": len(code),
            "limit_va": f"0x{limit:08X}",
            "assembly": source.strip(),
        })
    payload[ACTIVE_VA - diag02.LUCK_SECTION_VA] = 0
    meta = dict(base_meta)
    meta["diagnostic_components"] = base_meta["components"]
    meta["feature_components"] = components
    meta["specialist_active_va"] = f"0x{ACTIVE_VA:08X}"
    return bytes(payload), meta


def patch_executable(path: Path, payload: bytes, payload_meta: dict[str, Any]) -> dict[str, Any]:
    source = path.read_bytes()
    if sha256_bytes(source) != diag02.SOURCE_EXE_SHA256[path.name]:
        raise RuntimeError(f"unexpected formal source hash for {path.name}")

    base_report = diag02.patch_executable(path, payload, payload_meta)
    stage = path.read_bytes()
    pe = pefile.PE(data=stage, fast_load=False)
    patched = bytearray(stage)
    patch_reports: list[dict[str, Any]] = []
    for item in FEATURE_PATCHES:
        offset = pe.get_offset_from_rva(int(item["va"]) - diag01.IMAGE_BASE)
        source_bytes = bytes(item["source"])
        if source[offset:offset + len(source_bytes)] != source_bytes:
            raise RuntimeError(f"formal feature source mismatch: {item['name']}")
        if stage[offset:offset + len(source_bytes)] != source_bytes:
            raise RuntimeError(f"diagnostic stage unexpectedly touched feature site: {item['name']}")
        replacement = diag01.relative_jump(
            int(item["va"]), int(item["wrapper_va"]), len(source_bytes)
        )
        patched[offset:offset + len(replacement)] = replacement
        patch_reports.append({
            "name": item["name"],
            "va": f"0x{int(item['va']):08X}",
            "file_offset": f"0x{offset:X}",
            "source_hex": source_bytes.hex(" "),
            "patched_hex": replacement.hex(" "),
            "wrapper_va": f"0x{int(item['wrapper_va']):08X}",
            "continue_va": f"0x{int(item['continue_va']):08X}",
        })

    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    struct.pack_into("<I", patched, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(patched), fast_load=False)
    struct.pack_into("<I", patched, checksum_offset, checksum_pe.generate_checksum())
    final = bytes(patched)
    final_pe = pefile.PE(data=final, fast_load=False)
    if final_pe.verify_checksum() is not True:
        raise RuntimeError(f"functional test checksum invalid: {path.name}")

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    for item in FEATURE_PATCHES:
        offset = final_pe.get_offset_from_rva(int(item["va"]) - diag01.IMAGE_BASE)
        instruction = next(decoder.disasm(final[offset:offset + 5], int(item["va"])))
        if (
            instruction.mnemonic != "jmp"
            or not instruction.operands
            or instruction.operands[0].type != X86_OP_IMM
            or int(instruction.operands[0].imm) != int(item["wrapper_va"])
        ):
            raise RuntimeError(f"functional hook target mismatch: {item['name']}")

    # Reconstruct formal V1.14 from the final candidate, including its original
    # checksum, to prove that the feature and diagnostic edits are isolated.
    source_pe = pefile.PE(data=source, fast_load=False)
    restored = bytearray(final)
    entry_offset = source_pe.get_offset_from_rva(diag01.SCHOLAR_ENTRY_VA - diag01.IMAGE_BASE)
    restored[entry_offset:entry_offset + len(diag01.SCHOLAR_ENTRY_ORIGINAL)] = (
        diag01.SCHOLAR_ENTRY_ORIGINAL
    )
    for item in FEATURE_PATCHES:
        offset = source_pe.get_offset_from_rva(int(item["va"]) - diag01.IMAGE_BASE)
        source_bytes = bytes(item["source"])
        restored[offset:offset + len(source_bytes)] = source_bytes
    restored[
        diag02.LUCK_SECTION_RAW_OFFSET:
        diag02.LUCK_SECTION_RAW_OFFSET + diag02.LUCK_SECTION_SIZE
    ] = source[
        diag02.LUCK_SECTION_RAW_OFFSET:
        diag02.LUCK_SECTION_RAW_OFFSET + diag02.LUCK_SECTION_SIZE
    ]
    restored[checksum_offset:checksum_offset + 4] = source[checksum_offset:checksum_offset + 4]
    if bytes(restored) != source:
        raise RuntimeError(f"functional test full rollback failed: {path.name}")

    path.write_bytes(final)
    return {
        **base_report,
        "output_sha256": sha256_bytes(final),
        "feature_patches": patch_reports,
        "contiguous_differences": contiguous_differences(source, final),
        "pe_checksum_valid": True,
        "rollback_reconstructs_source": True,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与测试说明

这是从正式 {SOURCE_NAME} 构建的科洛尼斯学术特首个功能测试包。

当前实际效果：
1. 科洛尼斯的学术术贡献提高一级：初级可传授 1—3 级魔法，中级可传授 1—4 级魔法，高级可传授 1—5 级魔法。
2. 科洛尼斯参与友方英雄会面时，双方英雄可接收的魔法等级均在各自智慧术原上限基础上提高一级，最高仍为 5 级。
3. 原生魔法书条件、法术禁用规则、已学法术过滤、双向传授、提示和交换界面流程全部保留。
4. 没有科洛尼斯参与的英雄会面完全使用原版规则。

本测试包保留 {LOG_FILENAME} 运行记录。DIAG03 已确认旧图形资源修改会引起新建场景闪退，因此本包暂不替换科洛尼斯图标；图标将在功能验证后单独修复。

安装：必须覆盖到纯净 HotA 1.8.0，不能叠加任何学术诊断包。

建议测试：
1. 先确认“单人游戏 → 新建场景”可以正常进入。
2. 科洛尼斯（初级学术、初级智慧）与没有学术/智慧的友方英雄会面。
3. 确保双方魔法书中存在至少一个对方未学会的 3 级可传授魔法；初级学术在原版只能传授至 2 级，而本测试包应出现原生学术提示并完成 3 级魔法学习。
4. 再测试非科洛尼斯的两名英雄，确认规则没有变化。
5. 退出后上传 {LOG_FILENAME}，并说明双方实际交换了哪些等级的魔法。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
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

    payload, payload_meta = build_payload()
    executable_reports = [
        patch_executable(package_root / name, payload, payload_meta)
        for name in EXE_NAMES
    ]

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
    if set(source_hashes) != set(package_hashes):
        raise RuntimeError("SCHOLAR_TEST01 changed the formal member set")
    changed = {
        relative for relative in source_hashes
        if source_hashes[relative] != package_hashes[relative]
    }
    expected_changed = set(EXE_NAMES) | {instruction_relative}
    if changed != expected_changed:
        raise RuntimeError(f"unexpected SCHOLAR_TEST01 delta: {sorted(changed)}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("SCHOLAR_TEST01 ZIP CRC failure")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("SCHOLAR_TEST01 ZIP member set mismatch")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "diagnostic_only": False,
        "test_only": True,
        "gameplay_logic_changed": True,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "validated_runtime_input": {
            "diag03_sha256": "6a8bbd069f62d8e135970dbe5987e439cd5012672e0547b2ce7ae53d7533ce9d",
            "record_count": 1,
            "coronius_position": "hero1",
            "native_cap": 1,
            "planned_meeting_cap": 3,
            "planned_receive_caps": [3, 3],
        },
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "log_filename": LOG_FILENAME,
        "changed_package_files": sorted(changed),
        "added_package_files": [],
        "source_file_hashes": source_hashes,
        "package_file_hashes": package_hashes,
        "executables": executable_reports,
        "static_verification": {
            "all_non_exe_resources_byte_preserved_except_install_text": True,
            "native_four_calculation_sites_only": True,
            "non_specialist_meeting_path_preserves_raw_values": True,
            "no_temporary_hero_skill_mutation": True,
            "formal_luck3_prefix_preserved": True,
            "file_size_section_count_and_size_of_image_preserved": True,
            "full_rollback_verified": True,
            "zip_crc_and_member_checks_passed": True,
        },
        "runtime_acceptance": {
            "status": "pending eligible 2nd/3rd-level transfer and non-specialist control",
        },
    }
    (output_root / f"{BUILD_NAME}_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / f"{BUILD_NAME}_README.md").write_text(
        installation_text(), encoding="utf-8"
    )
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    for item in executable_reports:
        print(f"{item['name']}: {item['output_sha256']}")
    print(f"Runtime log: {LOG_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
