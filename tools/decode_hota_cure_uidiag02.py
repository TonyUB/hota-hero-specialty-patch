#!/usr/bin/env python3
"""Decode 40-byte unfiltered UID1 records produced by UIDIAG02."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


RECORD = struct.Struct("<10I")
MAGIC = 0x31444955


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
        (
            magic,
            event,
            caller,
            object_pointer,
            object_field_1a,
            argument_1,
            argument_3,
            argument_2,
            native_result,
            reserved,
        ) = values
        if magic != MAGIC:
            raise RuntimeError(f"Bad UID1 magic in record {index}: 0x{magic:08X}")
        records.append({
            "index": index,
            "event": event,
            "caller": f"0x{caller:08X}",
            "object_pointer": f"0x{object_pointer:08X}",
            "object_field_1a": object_field_1a,
            "argument_1": argument_1,
            "argument_2": argument_2,
            "argument_3": f"0x{argument_3:08X}",
            "native_result": native_result,
            "reserved": reserved,
        })
    print(json.dumps({"path": str(path), "record_count": len(records), "records": records}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
