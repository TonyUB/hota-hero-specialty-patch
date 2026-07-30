#!/usr/bin/env python3
"""Verify Scholar TEST03, including the preserved D32F metadata prefix."""

from __future__ import annotations

import hashlib
from pathlib import Path

import build_hota_new_hero_v12_scholar_diag01 as diag01
import build_hota_new_hero_v12_scholar_test02 as test02
import build_hota_new_hero_v12_scholar_test03 as test03
import verify_hota_new_hero_v12_scholar_test02 as verify02


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_icon(
    source_path: Path,
    candidate_path: Path,
    expert_def: Path,
    expected_hash: str,
    expected_name: str,
) -> dict[str, object]:
    source = source_path.read_bytes()
    candidate = candidate_path.read_bytes()
    start, length, size = verify02.d32f_frame(source)
    candidate_start, candidate_length, candidate_size = verify02.d32f_frame(candidate)
    if (candidate_start, candidate_length, candidate_size) != (start, length, size):
        raise RuntimeError(f"D32F geometry changed: {candidate_path.name}")
    image, _, _, native = diag01.decode_expert_scholar(
        expert_def,
        expected_hash=expected_hash,
        expected_size=size,
        expected_name=expected_name,
    )
    rendered = image.rotate(180).tobytes("raw", "BGRA")
    metadata_end = start + test03.D32F_FRAME_METADATA_SIZE
    if candidate[start:metadata_end] != test03.D32F_FRAME_METADATA:
        raise RuntimeError(f"D32F frame metadata mismatch: {candidate_path.name}")
    if candidate[metadata_end:start + length] != rendered[test03.D32F_FRAME_METADATA_SIZE:]:
        raise RuntimeError(f"Expert Scholar visible pixels mismatch: {candidate_path.name}")
    if candidate[:start] != source[:start] or candidate[start + length:] != source[start + length:]:
        raise RuntimeError(f"an unrelated D32F byte changed: {candidate_path.name}")
    return {
        "path": candidate_path.name,
        "frame": diag01.CORONIUS_ID,
        "size": size,
        "native_frame": native["frame_name"],
        "metadata_prefix_hex": candidate[start:metadata_end].hex(" "),
        "metadata_prefix_preserved": True,
        "visible_pixels_sha256": sha256_bytes(candidate[metadata_end:start + length]),
        "all_other_bytes_preserved": True,
    }


def main() -> int:
    test02.BUILD_NAME = test03.BUILD_NAME
    test02.LOG_FILENAME = test03.LOG_FILENAME
    test02.installation_text = test03.installation_text
    verify02.verify_icon = verify_icon
    return verify02.main()


if __name__ == "__main__":
    raise SystemExit(main())
