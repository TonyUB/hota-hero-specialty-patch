#!/usr/bin/env python3
"""Decode 64-byte FMT1 records produced by UIDIAG03."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


RECORD = struct.Struct("<16I")
MAGIC = 0x31544D46


def decode_format(raw: bytes) -> dict[str, str]:
    raw = raw.split(b"\0", 1)[0]
    result = {"hex": raw.hex(" ")}
    for encoding in ("ascii", "gbk"):
        try:
            result[encoding] = raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    path = parser.parse_args().log.resolve()
    data = path.read_bytes()
    if len(data) % RECORD.size:
        raise RuntimeError(
            f"Truncated diagnostic log: {len(data)} bytes is not divisible by {RECORD.size}"
        )
    records = []
    for index, values in enumerate(RECORD.iter_unpack(data)):
        if values[0] != MAGIC:
            raise RuntimeError(f"Bad FMT1 magic in record {index}: 0x{values[0]:08X}")
        format_bytes = struct.pack("<4I", *values[10:14])
        records.append({
            "index": index,
            "caller": f"0x{values[1]:08X}",
            "destination": f"0x{values[2]:08X}",
            "format_pointer": f"0x{values[3]:08X}",
            "arguments": [f"0x{value:08X}" for value in values[4:10]],
            "format": decode_format(format_bytes),
            "reserved": list(values[14:16]),
        })
    print(json.dumps({"path": str(path), "record_count": len(records), "records": records}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
