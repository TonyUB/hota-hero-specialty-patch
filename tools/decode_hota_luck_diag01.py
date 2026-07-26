#!/usr/bin/env python3
"""Decode hota_luck_diag01.bin produced by V1.1_LUCKDIAG01."""

from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path


MAGIC = 0x314B434C
RECORD = struct.Struct("<10I")
HERO_NAMES = {29: "Melodia", 43: "Daremyth"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = args.log.read_bytes()
    if len(data) % RECORD.size:
        raise RuntimeError(f"truncated log: {len(data)} is not a multiple of {RECORD.size}")
    records = []
    for index in range(0, len(data), RECORD.size):
        values = RECORD.unpack_from(data, index)
        if values[0] != MAGIC:
            raise RuntimeError(f"bad record magic at file offset {index:#x}")
        _, stage, caller, hero_ptr, hero_id, enemy_ptr, cursed, clamp, flags, reserved = values
        records.append({
            "index": index // RECORD.size,
            "stage": stage,
            "stage_name": {1: "function entry", 2: "passed native suppression gate"}.get(stage, "unknown"),
            "caller": f"0x{caller:08X}",
            "hero_pointer": f"0x{hero_ptr:08X}",
            "hero_id": hero_id,
            "hero_name": HERO_NAMES.get(hero_id, "unknown"),
            "enemy_hero_pointer": f"0x{enemy_ptr:08X}",
            "is_cursed_ground": cursed,
            "clamp_requested": clamp,
            "hero_flags_0x105": f"0x{flags:08X}",
            "reserved": reserved,
        })
    stage_counts = Counter(item["stage"] for item in records)
    hero_counts = Counter(item["hero_id"] for item in records)
    report = {
        "file": args.log.as_posix(),
        "size": len(data),
        "record_size": RECORD.size,
        "record_count": len(records),
        "stage_counts": {str(key): value for key, value in sorted(stage_counts.items())},
        "hero_counts": {str(key): value for key, value in sorted(hero_counts.items())},
        "interpretation": {
            "ordinary_path": "a stage-1 call should normally be followed by stage 2",
            "native_suppression": "a stage-1 call without stage 2 was stopped before numeric luck calculation",
        },
        "records": records,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
