#!/usr/bin/env python3
"""Decode hota_luck_firstdiag01.bin into CSV and a compact text summary."""

from __future__ import annotations

import argparse
import csv
import struct
from collections import Counter
from pathlib import Path


MAGIC = 0x314B5441
FIELDS = [
    "magic", "path", "caller", "attacker", "arg1", "arg2", "hero", "hero_id",
    "effective_side", "raw_side", "stack_slot", "creature_id", "luck", "lucky_before",
    "attacker_84", "attacker_288", "battle", "ebx", "ecx", "edi", "ebp",
    "battle_132b8", "battle_132bc", "battle_132c0",
]
STRUCT = struct.Struct("<" + "I" * len(FIELDS))
HEX_FIELDS = {
    "caller", "attacker", "arg1", "arg2", "hero", "battle", "ebx", "ecx",
    "edi", "ebp", "battle_132b8", "battle_132bc", "battle_132c0",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--csv", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = args.input.read_bytes()
    if len(data) % STRUCT.size:
        raise RuntimeError(f"File size {len(data)} is not divisible by record size {STRUCT.size}")
    rows = []
    for index, values in enumerate(STRUCT.iter_unpack(data), start=1):
        row = dict(zip(FIELDS, values))
        if row["magic"] != MAGIC:
            raise RuntimeError(f"Record {index} has unexpected magic 0x{row['magic']:08X}")
        row["record"] = index
        rows.append(row)
    output = args.csv or args.input.with_suffix(".csv")
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["record", *FIELDS])
        writer.writeheader()
        for row in rows:
            rendered = dict(row)
            rendered["magic"] = "ATK1"
            for name in HEX_FIELDS:
                rendered[name] = f"0x{int(row[name]):08X}"
            writer.writerow(rendered)
    counts = Counter((row["path"], row["caller"], row["hero_id"]) for row in rows)
    print(f"records={len(rows)} record_size={STRUCT.size} csv={output}")
    for (path, caller, hero_id), count in sorted(counts.items()):
        print(f"path={path} caller=0x{caller:08X} hero={hero_id} count={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
