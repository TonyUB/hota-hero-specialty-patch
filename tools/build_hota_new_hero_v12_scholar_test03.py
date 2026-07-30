#!/usr/bin/env python3
"""Build Scholar TEST03 with the D32F per-frame metadata preserved."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any

from PIL import Image

import build_hota_new_hero_v12_scholar_diag01 as diag01
import build_hota_new_hero_v12_scholar_test02 as test02


BUILD_NAME = "HOTA_NEW_HERO_V1.2_SCHOLAR_TEST03"
LOG_FILENAME = "hota_scholar_test03.bin"
D32F_FRAME_METADATA = bytes.fromhex("08 00 00 00 00 00 00 00")
D32F_FRAME_METADATA_SIZE = len(D32F_FRAME_METADATA)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch_d32f_preserving_metadata(
    path: Path, image: Image.Image, expected: dict[str, Any]
) -> dict[str, Any]:
    original = path.read_bytes()
    if sha256_bytes(original) != expected["source_sha256"]:
        raise RuntimeError(f"unexpected D32F source hash: {path}")
    if original[:4] != b"D32F" or struct.unpack_from("<I", original, 0x28)[0] != 215:
        raise RuntimeError(f"unexpected D32F identity: {path}")

    frame_count = 215
    offsets_position = 0x30 + frame_count * 13
    offsets = struct.unpack_from(f"<{frame_count}I", original, offsets_position)
    frame_offset = offsets[diag01.CORONIUS_ID]
    header = struct.unpack_from("<8I", original, frame_offset)
    data_size = header[1]
    target_size = int(expected["size"])
    if header[0] != 0x20 or header[2:6] != (
        target_size, target_size, target_size, target_size
    ):
        raise RuntimeError(f"unexpected Coronius D32F frame geometry: {path}")
    if data_size != target_size * target_size * 4:
        raise RuntimeError(f"unexpected Coronius D32F data size: {path}")

    start = frame_offset + 32
    end = start + data_size
    if original[start:start + D32F_FRAME_METADATA_SIZE] != D32F_FRAME_METADATA:
        raise RuntimeError(f"unexpected D32F frame metadata: {path}")
    # All 215 frames in both formal containers carry the same hidden prefix.
    # It is inside the nominal BGRA-sized data block but is not visible pixels.
    for index, offset in enumerate(offsets):
        if original[offset + 32:offset + 32 + D32F_FRAME_METADATA_SIZE] != D32F_FRAME_METADATA:
            raise RuntimeError(f"D32F frame {index} metadata differs: {path}")

    resized = image if target_size == 44 else image.resize(
        (target_size, target_size), Image.Resampling.LANCZOS
    )
    rendered = resized.rotate(180).tobytes("raw", "BGRA")
    if len(rendered) != data_size:
        raise RuntimeError(f"rendered D32F length mismatch: {path}")
    replacement = D32F_FRAME_METADATA + rendered[D32F_FRAME_METADATA_SIZE:]

    patched = bytearray(original)
    patched[start:end] = replacement
    final = bytes(patched)
    if final[start:start + D32F_FRAME_METADATA_SIZE] != D32F_FRAME_METADATA:
        raise RuntimeError(f"D32F metadata was not preserved: {path}")
    if (
        final[:start] != original[:start]
        or final[end:] != original[end:]
        or final[start + D32F_FRAME_METADATA_SIZE:end]
           != rendered[D32F_FRAME_METADATA_SIZE:]
    ):
        raise RuntimeError(f"D32F visible-frame isolation failed: {path}")
    restored = bytearray(final)
    restored[start:end] = original[start:end]
    if bytes(restored) != original:
        raise RuntimeError(f"D32F full rollback failed: {path}")

    path.write_bytes(final)
    return {
        "path": path.as_posix(),
        "source_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(final),
        "frame_index": diag01.CORONIUS_ID,
        "frame_offset": f"0x{frame_offset:X}",
        "data_offset": f"0x{start:X}",
        "data_length": data_size,
        "metadata_prefix_hex": D32F_FRAME_METADATA.hex(" "),
        "metadata_prefix_preserved": True,
        "visible_data_offset": f"0x{start + D32F_FRAME_METADATA_SIZE:X}",
        "visible_data_length": data_size - D32F_FRAME_METADATA_SIZE,
        "all_other_bytes_preserved": True,
        "rollback_verified": True,
    }


def install_specialty_icons_only(
    package_root: Path, secskill_def: Path, secskill32_def: Path
) -> dict[str, Any]:
    image44, _, _, source44 = diag01.decode_expert_scholar(
        secskill_def,
        expected_hash=diag01.SECSKILL_DEF_SHA256,
        expected_size=44,
        expected_name="skill18c.pcx",
    )
    image32, _, _, source32 = diag01.decode_expert_scholar(
        secskill32_def,
        expected_hash=diag01.SECSK32_DEF_SHA256,
        expected_size=32,
        expected_name="skl3218c.pcx",
    )
    reports = []
    for relative, expected in diag01.D32F_RELATIVES.items():
        reports.append(patch_d32f_preserving_metadata(
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
        "per_frame_metadata_preserved": True,
        "portrait_resources_added_or_modified": False,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} D32F 修复测试说明

本包从正式 {test02.SOURCE_NAME} 构建，继承已经通过验证的科洛尼斯学术交换功能、特长说明和初始“减速”。

TEST02 闪退根因：UN32/UN44 的每帧数据块前 8 字节是运行时元数据 `08 00 00 00 00 00 00 00`，并非可见 BGRA 像素。TEST02 覆盖了这 8 字节，导致“单人游戏 → 新建场景”加载阶段闪退。

TEST03 修正：
1. 完整保留上述 8 字节元数据；
2. 只替换其后的“高级学术 / Expert Scholar”可见图像数据；
3. 科洛尼斯英雄头像资源保持不变；
4. 特长说明仍为：{test02.NEW_LOOSE_RECORD.split(chr(9), 2)[2]}
5. 初始魔法由屠戮改为一级魔法“减速”。

安装：必须覆盖到纯净 HotA 1.8.0 中文版，不能叠加 TEST02 或其他学术测试包。

最小验证：
1. “单人游戏 → 新建场景”能够正常进入；
2. 科洛尼斯头像不变，特长图标为高级学术且方向正确；
3. 特长名称、说明和初始“减速”正确；
4. 与己方英雄会面一次，确认学术交换功能无回归。

运行记录文件为 {LOG_FILENAME}。如果四项全部通过，只需反馈结果；交换异常时再上传该文件。
"""


def main() -> int:
    # Reuse TEST02's isolated gameplay/text/spell builder while replacing only
    # its invalid D32F writer and build identity.
    test02.BUILD_NAME = BUILD_NAME
    test02.LOG_FILENAME = LOG_FILENAME
    test02.install_specialty_icons_only = install_specialty_icons_only
    test02.installation_text = installation_text
    return test02.main()


if __name__ == "__main__":
    raise SystemExit(main())
