#!/usr/bin/env python3
"""Disassemble a selected preferred-VA region from a PE in a release ZIP."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import capstone
import pefile


def parse_int(value: str) -> int:
    return int(value, 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip", type=Path)
    parser.add_argument("va", type=parse_int)
    parser.add_argument("size", type=parse_int)
    parser.add_argument("--member", default="HotA.dll")
    args = parser.parse_args()

    with zipfile.ZipFile(args.zip) as archive:
        data = archive.read(args.member)
    pe = pefile.PE(data=data, fast_load=False)
    image_base = int(pe.OPTIONAL_HEADER.ImageBase)
    offset = pe.get_offset_from_rva(args.va - image_base)
    block = data[offset:offset + args.size]

    engine = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for instruction in engine.disasm(block, args.va):
        raw = instruction.bytes.hex(" ").ljust(26)
        print(
            f"0x{instruction.address:08X}  {raw}  "
            f"{instruction.mnemonic:<8} {instruction.op_str}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
