#!/usr/bin/env python3
"""Decode DIAG03 true HotA.dll attack-callback records."""

from __future__ import annotations

import argparse
import csv
import struct
from collections import Counter
from pathlib import Path


MAGIC = 0x314B5441
STRUCT = struct.Struct("<24I")
FIELDS = [
    "magic", "path", "caller", "attacker", "arg1", "arg2", "arg3", "arg4",
    "eax", "ecx", "edx", "ebx", "esi", "edi", "ebp", "arg5", "arg6",
    "arg7", "arg8", "arg9", "arg10", "arg11", "battle_manager", "reserved",
]
HEX_FIELDS = {
    "caller", "attacker", "arg1", "arg2", "arg3", "arg4", "eax", "ecx",
    "edx", "ebx", "esi", "edi", "ebp", "arg5", "arg6", "arg7", "arg8",
    "arg9", "arg10", "arg11", "battle_manager", "reserved",
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
        raise RuntimeError("Input size is not divisible by 96-byte records")
    rows = []
    for index, values in enumerate(STRUCT.iter_unpack(data), start=1):
        if values[0] != MAGIC:
            raise RuntimeError(f"Record {index} has invalid magic 0x{values[0]:08X}")
        row = dict(zip(FIELDS, values))
        row["record"] = index
        rows.append(row)
    output = args.csv or args.input.with_suffix(".csv")
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["record", *FIELDS])
        writer.writeheader()
        for row in rows:
            rendered = dict(row)
            rendered["magic"] = "ATK1"
            for field in HEX_FIELDS:
                rendered[field] = f"0x{int(row[field]):08X}"
            writer.writerow(rendered)
    attack_rows = [row for row in rows if row["path"] in (3, 4)]
    counts = Counter((row["path"], row["attacker"]) for row in attack_rows)
    print(f"records={len(rows)} attacks={len(attack_rows)} csv={output}")
    for key, count in counts.items():
        path, attacker = key
        print(f"path={path} candidate=0x{attacker:08X} count={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
