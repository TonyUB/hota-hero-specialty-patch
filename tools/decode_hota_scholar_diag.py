#!/usr/bin/env python3
"""Decode hota_scholar_diag01.bin records."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


MAGIC = 0x31484353
RECORD_DWORDS = 18
RECORD_SIZE = RECORD_DWORDS * 4
FIELDS = [
    "magic", "schema_version", "caller_return", "hero1_pointer", "hero1_id",
    "hero1_scholar", "hero1_wisdom", "hero1_known_spells", "hero2_pointer",
    "hero2_id", "hero2_scholar", "hero2_wisdom", "hero2_known_spells",
    "native_max_raw_scholar", "planned_meeting_spell_cap",
    "planned_hero1_receive_cap", "planned_hero2_receive_cap", "specialist_flags",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    data = args.log.read_bytes()
    if not data or len(data) % RECORD_SIZE:
        raise RuntimeError(f"log size {len(data)} is not a non-zero multiple of {RECORD_SIZE}")
    records = []
    for offset in range(0, len(data), RECORD_SIZE):
        values = struct.unpack_from(f"<{RECORD_DWORDS}I", data, offset)
        record = dict(zip(FIELDS, values))
        if record["magic"] != MAGIC or record["schema_version"] != 1:
            raise RuntimeError(f"invalid SCH1 record at offset 0x{offset:X}")
        for field in ("caller_return", "hero1_pointer", "hero2_pointer"):
            record[field] = f"0x{int(record[field]):08X}"
        flags = int(record["specialist_flags"])
        record["specialist_position"] = [
            label for bit, label in ((1, "hero1"), (2, "hero2")) if flags & bit
        ]
        record["runtime_path_valid"] = (
            int(record["hero1_id"]) == 24 or int(record["hero2_id"]) == 24
        )
        records.append(record)
    print(json.dumps({
        "log": str(args.log.resolve()),
        "record_size": RECORD_SIZE,
        "record_count": len(records),
        "records": records,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
