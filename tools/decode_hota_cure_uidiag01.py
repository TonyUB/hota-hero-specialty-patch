#!/usr/bin/env python3
"""Decode 40-byte UID1 records produced by V1.06_UIDIAG01."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


RECORD = struct.Struct("<10I")
MAGIC = 0x31444955


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    return parser.parse_args()


def main() -> int:
    path = parse_args().log.resolve()
    data = path.read_bytes()
    if len(data) % RECORD.size:
        raise RuntimeError(
            f"Truncated diagnostic log: {len(data)} bytes is not divisible by {RECORD.size}"
        )
    records = []
    for index, values in enumerate(RECORD.iter_unpack(data)):
        (
            magic,
            event,
            caller,
            hero_pointer,
            hero_id,
            spell_id,
            target_pointer,
            native_input,
            native_result,
            reserved,
        ) = values
        if magic != MAGIC:
            raise RuntimeError(f"Bad UID1 magic in record {index}: 0x{magic:08X}")
        records.append({
            "index": index,
            "event": event,
            "caller": f"0x{caller:08X}",
            "hero_pointer": f"0x{hero_pointer:08X}",
            "hero_id": hero_id,
            "spell_id": spell_id,
            "target_pointer": f"0x{target_pointer:08X}",
            "native_input": native_input,
            "native_result": native_result,
            "reserved": reserved,
        })
    print(json.dumps({"path": str(path), "record_count": len(records), "records": records}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
