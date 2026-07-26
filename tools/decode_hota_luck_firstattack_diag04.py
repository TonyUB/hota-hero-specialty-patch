#!/usr/bin/env python3
"""Decode DIAG04 action-boundary records."""

from __future__ import annotations

import argparse
import csv
import struct
from collections import Counter
from pathlib import Path


MAGIC = 0x314B5441
STRUCT = struct.Struct("<24I")
FIELDS = [
    "magic", "path", "caller", "attacker", "target", "arg4", "action",
    "action_parameter", "action_target", "action_parameter2",
    "current_mon_side", "current_mon_index", "current_active_side",
    "active_stack", "turn", "action_undergoing", "attacked_already",
    "creature_id", "slot_index", "is_lucky", "side", "side_index", "luck",
    "hero_id",
]
HEX_FIELDS = {"caller", "attacker", "target", "active_stack"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()
    data = args.input.read_bytes()
    if len(data) % STRUCT.size:
        raise RuntimeError("Input size is not divisible by 96-byte records")
    rows = []
    for index, values in enumerate(STRUCT.iter_unpack(data), start=1):
        if values[0] != MAGIC:
            raise RuntimeError(f"Record {index} has invalid magic 0x{values[0]:08X}")
        row = dict(zip(FIELDS, values))
        row["record"] = index
        row["active_equals_attacker"] = int(row["active_stack"] == row["attacker"])
        rows.append(row)
    output = args.csv or args.input.with_suffix(".csv")
    fieldnames = ["record", *FIELDS, "active_equals_attacker"]
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            rendered = dict(row)
            rendered["magic"] = "ATK1"
            for field in HEX_FIELDS:
                rendered[field] = f"0x{int(row[field]):08X}"
            writer.writerow(rendered)
    attacks = [row for row in rows if row["path"] in (5, 6)]
    print(f"records={len(rows)} action_records={len(attacks)} csv={output}")
    for key, count in Counter(
        (row["path"], row["active_equals_attacker"], row["action"])
        for row in attacks
    ).items():
        path, active, action = key
        print(f"path={path} active_eq_attacker={active} action={action} count={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
