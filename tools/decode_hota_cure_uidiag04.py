#!/usr/bin/env python3
"""Decode 128-byte HFM1 records produced by UIDIAG04."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


RECORD = struct.Struct("<32I")
MAGIC = 0x314D4648


def decode_text(raw: bytes) -> dict[str, str]:
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
            raise RuntimeError(f"Bad HFM1 magic in record {index}: 0x{values[0]:08X}")
        raw = struct.pack("<32I", *values)
        records.append({
            "index": index,
            "caller": f"0x{values[1]:08X}",
            "destination": f"0x{values[2]:08X}",
            "maximum_size": values[3],
            "format_pointer": f"0x{values[4]:08X}",
            "arguments": [f"0x{value:08X}" for value in values[5:13]],
            "format": decode_text(raw[52:80]),
            "argument_1_text": decode_text(raw[80:96]),
            "argument_2_text": decode_text(raw[96:112]),
            "reserved_hex": raw[112:128].hex(" "),
        })
    print(json.dumps({
        "path": str(path),
        "record_count": len(records),
        "records": records,
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
