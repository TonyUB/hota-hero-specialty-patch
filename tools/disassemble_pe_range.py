#!/usr/bin/env python3
"""Disassemble an exact virtual-address range from a 32-bit PE image."""

from __future__ import annotations

import argparse
from pathlib import Path

import capstone
import pefile


def number(value: str) -> int:
    return int(value, 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--start", type=number, required=True)
    parser.add_argument("--end", type=number, required=True)
    args = parser.parse_args()
    if args.end <= args.start:
        raise ValueError("end must be greater than start")

    data = args.binary.read_bytes()
    pe = pefile.PE(data=data, fast_load=False)
    image_base = int(pe.OPTIONAL_HEADER.ImageBase)
    offset = pe.get_offset_from_rva(args.start - image_base)
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = False
    consumed = 0
    for instruction in decoder.disasm(data[offset:offset + args.end - args.start], args.start):
        if instruction.address >= args.end:
            break
        consumed = instruction.address + instruction.size - args.start
        print(
            f"0x{instruction.address:08X}  {instruction.bytes.hex(' '):<28} "
            f"{instruction.mnemonic:<8} {instruction.op_str}"
        )
    if consumed != args.end - args.start:
        print(f"# decoded {consumed:#x} of {(args.end - args.start):#x} requested bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
