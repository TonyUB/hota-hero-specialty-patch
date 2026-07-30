#!/usr/bin/env python3
"""Build Scholar TEST04 with the correct icon and native Slayer disabled."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any

import pefile

import build_hota_new_hero_v12_scholar_diag01 as diag01
import build_hota_new_hero_v12_scholar_test02 as test02
import build_hota_new_hero_v12_scholar_test03 as test03


BUILD_NAME = "HOTA_NEW_HERO_V1.2_SCHOLAR_TEST04"
LOG_FILENAME = "hota_scholar_test04.bin"

# Secskill.def names the skills with one-based numbers.  Scholar is secondary
# skill ID 18 in the executable, but its DEF frames are named skill19a/b/c.
EXPERT_SCHOLAR_FRAME = 59
EXPERT_SCHOLAR_44_NAME = "skill19c.pcx"
EXPERT_SCHOLAR_32_NAME = "skl3219c.pcx"

# h3hota.exe stores a pointer to a 40-byte-per-hero specialty table at
# 0x00679C80.  In formal V1.14 it points to 0x00678420, whose raw offset is
# 0x00278420 in both standard and HD executables.
SPECIALTY_TABLE_POINTER_OFFSET = 0x00279C80
SPECIALTY_TABLE_POINTER_VA = 0x00678420
SPECIALTY_TABLE_OFFSET = 0x00278420
SPECIALTY_RECORD_SIZE = 40
CORONIUS_SPECIALTY_RECORD_OFFSET = (
    SPECIALTY_TABLE_OFFSET + diag01.CORONIUS_ID * SPECIALTY_RECORD_SIZE
)
CORONIUS_SPECIALTY_RECORD_SHA256 = (
    "ca7678be2828557c4c2315ac02537b5c3e60af3ef5edde23db99b9ef01fa4a03"
)
NATIVE_SPELL_SPECIALTY_TYPE = 3
DISABLED_SPECIALTY_TYPE = -1
NATIVE_SLAYER_SPELL_ID = 55

_BASE_PATCH_STARTING_SPELL = test02.patch_starting_spell


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_correct_expert_scholar(
    path: Path, *, expected_hash: str, expected_size: int, expected_name: str
):
    previous_frame = diag01.EXPERT_SCHOLAR_FRAME
    diag01.EXPERT_SCHOLAR_FRAME = EXPERT_SCHOLAR_FRAME
    try:
        return diag01.decode_expert_scholar(
            path,
            expected_hash=expected_hash,
            expected_size=expected_size,
            expected_name=expected_name,
        )
    finally:
        diag01.EXPERT_SCHOLAR_FRAME = previous_frame


def install_specialty_icons_only(
    package_root: Path, secskill_def: Path, secskill32_def: Path
) -> dict[str, Any]:
    image44, _, _, source44 = decode_correct_expert_scholar(
        secskill_def,
        expected_hash=diag01.SECSKILL_DEF_SHA256,
        expected_size=44,
        expected_name=EXPERT_SCHOLAR_44_NAME,
    )
    image32, _, _, source32 = decode_correct_expert_scholar(
        secskill32_def,
        expected_hash=diag01.SECSK32_DEF_SHA256,
        expected_size=32,
        expected_name=EXPERT_SCHOLAR_32_NAME,
    )
    reports = []
    for relative, expected in diag01.D32F_RELATIVES.items():
        reports.append(test03.patch_d32f_preserving_metadata(
            package_root / relative,
            image44 if int(expected["size"]) == 44 else image32,
            expected,
        ))
    forbidden = [
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*")
        if path.is_file()
        and path.name.upper().startswith(("HPS024", "HPL024"))
    ]
    if forbidden:
        raise RuntimeError(f"Coronius portrait resources must remain absent: {forbidden}")
    return {
        "native_expert_scholar_sources": [source44, source32],
        "d32f": reports,
        "coronius_frame": diag01.CORONIUS_ID,
        "source_frame": EXPERT_SCHOLAR_FRAME,
        "source_frame_names": [EXPERT_SCHOLAR_44_NAME, EXPERT_SCHOLAR_32_NAME],
        "per_frame_metadata_preserved": True,
        "portrait_resources_added_or_modified": False,
    }


def patch_starting_spell_and_disable_slayer(
    path: Path, formal_source: bytes
) -> dict[str, Any]:
    report = _BASE_PATCH_STARTING_SPELL(path, formal_source)
    stage = path.read_bytes()

    pointer = struct.unpack_from("<I", formal_source, SPECIALTY_TABLE_POINTER_OFFSET)[0]
    if pointer != SPECIALTY_TABLE_POINTER_VA:
        raise RuntimeError(f"unexpected specialty-table pointer: {path.name}")

    start = CORONIUS_SPECIALTY_RECORD_OFFSET
    end = start + SPECIALTY_RECORD_SIZE
    source_record = formal_source[start:end]
    stage_record = stage[start:end]
    if sha256_bytes(source_record) != CORONIUS_SPECIALTY_RECORD_SHA256:
        raise RuntimeError(f"unexpected formal Coronius specialty record: {path.name}")
    if stage_record != source_record:
        raise RuntimeError(f"earlier Scholar stage touched specialty table: {path.name}")
    if struct.unpack_from("<i", source_record, 0)[0] != NATIVE_SPELL_SPECIALTY_TYPE:
        raise RuntimeError(f"formal Coronius specialty is not type 3: {path.name}")
    if struct.unpack_from("<I", source_record, 4)[0] != NATIVE_SLAYER_SPELL_ID:
        raise RuntimeError(f"formal Coronius specialty is not Slayer: {path.name}")

    final = bytearray(stage)
    struct.pack_into("<i", final, start, DISABLED_SPECIALTY_TYPE)
    pe = pefile.PE(data=bytes(final), fast_load=False)
    checksum_offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    struct.pack_into("<I", final, checksum_offset, 0)
    checksum_pe = pefile.PE(data=bytes(final), fast_load=False)
    struct.pack_into("<I", final, checksum_offset, checksum_pe.generate_checksum())
    candidate = bytes(final)
    if pefile.PE(data=candidate, fast_load=False).verify_checksum() is not True:
        raise RuntimeError(f"checksum invalid after native-specialty patch: {path.name}")

    expected_record = bytearray(source_record)
    struct.pack_into("<i", expected_record, 0, DISABLED_SPECIALTY_TYPE)
    if candidate[start:end] != bytes(expected_record):
        raise RuntimeError(f"native-specialty record isolation failed: {path.name}")

    restored = bytearray(candidate)
    struct.pack_into("<i", restored, start, NATIVE_SPELL_SPECIALTY_TYPE)
    restored[checksum_offset:checksum_offset + 4] = stage[
        checksum_offset:checksum_offset + 4
    ]
    if bytes(restored) != stage:
        raise RuntimeError(f"native-specialty rollback failed: {path.name}")

    path.write_bytes(candidate)
    report["output_sha256"] = sha256_bytes(candidate)
    report["native_specialty"] = {
        "table_pointer_va": f"0x{pointer:08X}",
        "record_file_offset": f"0x{start:X}",
        "record_size": SPECIALTY_RECORD_SIZE,
        "source_type": NATIVE_SPELL_SPECIALTY_TYPE,
        "output_type": DISABLED_SPECIALTY_TYPE,
        "ignored_source_spell_id": NATIVE_SLAYER_SPELL_ID,
        "patched_field_source_hex": "03 00 00 00",
        "patched_field_output_hex": "ff ff ff ff",
        "all_other_record_bytes_preserved": True,
        "rollback_to_slow_stage_verified": True,
    }
    return report


def installation_text() -> str:
    return f"""{BUILD_NAME} 修正测试说明

本包从正式 {test02.SOURCE_NAME} 构建，继承已经通过测试的科洛尼斯学术交换功能、特长说明和初始“减速”。

TEST04 修正：
1. 特长图标改用游戏原生第 59 帧 `skill19c / skl3219c`，即“高级学术 / Expert Scholar”，不再误用高级土系魔法图标；
2. 保留 UN32/UN44 每帧开头 8 字节运行时元数据，只替换后续可见图像；
3. 将科洛尼斯原生特长表类型从法术特长 `3` 改为游戏已有的禁用类型 `-1`，切断原“屠戮”动态加成栏与实际法术增幅；
4. 特长说明仍为：{test02.NEW_LOOSE_RECORD.split(chr(9), 2)[2]}
5. 初始魔法由屠戮改为一级魔法“减速”，与 TEST03 的已确认配置一致。

安装：必须覆盖到纯净 HotA 1.8.0 中文版，不能叠加 TEST02、TEST03 或其他学术测试包。

最小验证：
1. “单人游戏 → 新建场景”正常进入；
2. 科洛尼斯特长图标为高级学术，不是高级土系魔法；
3. 特长窗口不再显示原屠戮的 `1-2级 +20 / 3-4级 +16 / 5-6级 +12 / 7级 +8`；
4. 科洛尼斯释放屠戮时不再获得上述原特长增幅；
5. 初始魔法为减速，学术交换功能无回归。

运行记录文件为 {LOG_FILENAME}。若学术交换正常，本轮无需上传日志，只需反馈以上五项结果。
"""


def main() -> int:
    test02.BUILD_NAME = BUILD_NAME
    test02.LOG_FILENAME = LOG_FILENAME
    test02.install_specialty_icons_only = install_specialty_icons_only
    test02.patch_starting_spell = patch_starting_spell_and_disable_slayer
    test02.installation_text = installation_text
    return test02.main()


if __name__ == "__main__":
    raise SystemExit(main())
