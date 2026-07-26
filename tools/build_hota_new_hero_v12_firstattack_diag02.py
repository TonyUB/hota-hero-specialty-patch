#!/usr/bin/env python3
"""Build the second first-active-attack diagnostic from formal V1.11.

DIAG02 adds a load/path proof to the already-confirmed fixed-Luck wrapper and
records all native attack-roll calls without treating the battle-side pointer
as an H3Hero object.  Gameplay remains identical to formal V1.11.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import build_hota_new_hero_v12_firstattack_diag01 as base


BUILD_NAME = "HOTA_NEW_HERO_V1.2_FIRSTATTACK_DIAG02"
LOG_FILENAME = "hota_luck_firstdiag02.bin"


def build_probe_prefix(record_va: int) -> tuple[bytes, dict[str, object]]:
    source = f"""
    test esi, esi
    je native
    mov eax, dword ptr [esi + 0x1a]
    cmp eax, {base.MELODIA_ID}
    je probe
    cmp eax, {base.DAREMYTH_ID}
    jne native
probe:
    pushfd
    pushad
    cld
    xor eax, eax
    mov edi, {record_va + 4:#x}
    mov ecx, 23
    rep stosd
    mov dword ptr [{record_va + 4:#x}], 0
    mov edx, dword ptr [ebp + 0x04]
    mov dword ptr [{record_va + 8:#x}], edx
    mov dword ptr [{record_va + 12:#x}], esi
    mov edx, dword ptr [ebp + 0x08]
    mov dword ptr [{record_va + 16:#x}], edx
    mov edx, dword ptr [ebp + 0x0c]
    mov dword ptr [{record_va + 20:#x}], edx
    mov dword ptr [{record_va + 24:#x}], esi
    mov edx, dword ptr [esi + 0x1a]
    mov dword ptr [{record_va + 28:#x}], edx
    mov eax, {base.LOGGER_VA:#x}
    call eax
    popad
    popfd
forced:
    mov eax, 3
    pop edi
    pop esi
    mov esp, ebp
    pop ebp
    ret 0x0c
native:
    mov al, byte ptr [esi + 0xd2]
    push {0x004E39EE:#x}
    ret
    """
    code = base.assemble(source, base.LUCK_SECTION_VA)
    if len(code) > base.PRESERVED_FORMAL_REGION_END:
        raise RuntimeError("Fixed-Luck proof wrapper exceeds reserved prefix")
    prefix = bytearray(base.PRESERVED_FORMAL_REGION_END)
    prefix[:len(code)] = code
    return bytes(prefix), {
        "va": f"0x{base.LUCK_SECTION_VA:08X}",
        "length": len(code),
        "assembly": source.strip(),
        "semantics": "V1.11 fixed Luck +3 plus behavior-transparent path-0 proof record",
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 诊断测试说明

本包修正 DIAG01 未生成文件的问题：
1. 在已经确认生效的固定幸运 +3 路径增加路径 0“加载证明”。
2. 攻击投骰路径不再把参战方指针误当成英雄对象，也不提前按英雄编号过滤。
3. 所有伤害、幸运结果、硬封锁、英雄数据和资源仍与正式 V1.11 一致。

安装：将压缩包全部内容覆盖到纯净 HotA 1.8.0 中文版目录，使用 h3hota HD.exe 启动。

最小测试：
1. 使用马洛迪亚或黛瑞丝进入战斗。
2. 完成一次主动近战攻击、一次主动远程攻击，并让己方部队反击一次。
3. 如方便，再测试一次二连击或多目标攻击。
4. 退出游戏后上传游戏根目录的 {LOG_FILENAME}。

本包不是功能测试版，第一次攻击不会被强制改成幸运；它只证明并区分真实运行入口。
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
    if base.sha256_file(source_zip) != base.SOURCE_ZIP_SHA256:
        raise RuntimeError(f"Formal {base.SOURCE_NAME} ZIP hash mismatch")

    original_log_filename = base.LOG_FILENAME
    base.LOG_FILENAME = LOG_FILENAME
    try:
        region, region_meta = base.build_diagnostic_region(filter_specialists=False)
    finally:
        base.LOG_FILENAME = original_log_filename
    record_va = int(str(region_meta["record_va"]), 16)
    prefix, prefix_meta = build_probe_prefix(record_va)
    region_meta["fixed_luck_probe"] = prefix_meta
    region_meta["attack_filter"] = "all native roll calls; no battle-side pointer dereference"

    package_root = build_root / BUILD_NAME
    base.safe_recreate_directory(package_root, build_root)
    base.extract_zip_safely(source_zip, package_root)
    source_hashes = {
        path.relative_to(package_root).as_posix(): base.sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    exe_reports = [
        base.patch_executable(
            package_root / name,
            region,
            region_meta,
            formal_prefix=prefix,
        )
        for name in base.EXE_NAMES
    ]
    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("Expected exactly one root installation text file")
    instruction_files[0].write_text(installation_text(), encoding="utf-8")
    package_hashes = {
        path.relative_to(package_root).as_posix(): base.sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    changed = sorted(
        relative for relative in source_hashes
        if source_hashes[relative] != package_hashes[relative]
    )
    expected_changed = sorted([
        *base.EXE_NAMES,
        instruction_files[0].relative_to(package_root).as_posix(),
    ])
    if changed != expected_changed:
        raise RuntimeError(f"Unexpected changed package files: {changed}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    base.deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"ZIP CRC failure: {failed}")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("ZIP member set mismatch")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "formal_release": False,
        "diagnostic_only": True,
        "source_release": base.SOURCE_NAME,
        "source_zip_sha256": base.SOURCE_ZIP_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": base.sha256_file(zip_path),
        "runtime_log": LOG_FILENAME,
        "record_magic": "ATK1",
        "record_size": base.RECORD_SIZE,
        "changed_package_files": changed,
        "source_file_hashes": source_hashes,
        "package_file_hashes": package_hashes,
        "executables": exe_reports,
        "diagnostic_change_from_diag01": {
            "path_0_proves_fixed_luck_wrapper_execution": True,
            "removed_invalid_hero_id_filter_from_attack_paths": True,
            "battle_side_pointer_is_recorded_but_not_dereferenced": True,
        },
        "static_verification": {
            "formal_v111_hashes_verified": True,
            "fixed_luck_plus_3_semantics_preserved": True,
            "only_existing_luck_section_used": True,
            "both_native_roll_hooks_verified": True,
            "standard_and_hd_built_separately": True,
            "full_executable_rollback_verified": True,
            "zip_crc_and_member_checks_passed": True,
            "gameplay_resources_byte_identical_to_v111": True,
        },
    }
    (output_root / f"{BUILD_NAME}_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / f"{BUILD_NAME}_README.txt").write_text(
        installation_text(), encoding="utf-8"
    )
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    print("Changed package files: " + json.dumps(changed, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
