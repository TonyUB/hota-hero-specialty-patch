#!/usr/bin/env python3
"""Decode HOTA_NEW_HERO_V1.2_FIRSTATTACK_TEST2 diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import struct
from collections import Counter
from pathlib import Path


MAGIC = 0x314B5441
RECORD = struct.Struct("<24I")


def ptr(value: int) -> str:
    return f"0x{value:08X}" if value else "0"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    data = args.input.read_bytes()
    print(f"file={args.input}")
    print(f"size={len(data)} sha256={hashlib.sha256(data).hexdigest()}")
    if len(data) % RECORD.size:
        raise SystemExit(f"trailing bytes: {len(data) % RECORD.size}")
    rows = [RECORD.unpack_from(data, offset) for offset in range(0, len(data), RECORD.size)]
    bad = [index for index, row in enumerate(rows) if row[0] != MAGIC]
    if bad:
        raise SystemExit(f"bad magic at records: {bad}")
    print(f"records={len(rows)} paths={dict(Counter(row[1] for row in rows))}")
    print("# p30 action: attacker action param target turn side index usedLo usedHi force gate")
    print("# p40 forced/p41 native: stack saved force gate luckyBefore luckyAfter side index luck")
    for index, row in enumerate(rows):
        path = row[1]
        if path == 30:
            print(
                f"{index:03d} p30 attacker={ptr(row[2])} action={row[3]} "
                f"param={row[4]} target={row[5]} turn={row[6]} side={row[7]} "
                f"index={row[8]} used={row[9]:08X}/{row[10]:08X} "
                f"force={row[11]} gate={row[12]:02X}"
            )
        elif path in (40, 41):
            print(
                f"{index:03d} p{path} stack={ptr(row[2])} saved={ptr(row[3])} "
                f"force={row[4]} gate={row[5]:02X} lucky={row[6]}->{row[7]} "
                f"side={row[8]} index={row[9]} luck={row[10]:08X}"
            )
        else:
            print(f"{index:03d} p{path} raw={' '.join(f'{value:08X}' for value in row[2:])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
