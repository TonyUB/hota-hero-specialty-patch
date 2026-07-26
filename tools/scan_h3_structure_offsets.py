#!/usr/bin/env python3
"""Find x86 instructions referencing selected structure displacements."""

from __future__ import annotations

import argparse
import struct
import zipfile
from pathlib import Path

import capstone
import pefile


def parse_int(value: str) -> int:
    return int(value, 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip", type=Path)
    parser.add_argument("member")
    parser.add_argument("offset", nargs="+", type=parse_int)
    args = parser.parse_args()

    with zipfile.ZipFile(args.zip) as archive:
        data = archive.read(args.member)
    pe = pefile.PE(data=data, fast_load=False)
    image_base = int(pe.OPTIONAL_HEADER.ImageBase)
    engine = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    engine.detail = True

    wanted = set(args.offset)
    for displacement in sorted(wanted):
        needle = struct.pack("<I", displacement)
        cursor = 0
        while True:
            index = data.find(needle, cursor)
            if index < 0:
                break
            try:
                rva = pe.get_rva_from_offset(index)
            except pefile.PEFormatError:
                cursor = index + 1
                continue
            context = data[max(0, index - 8):index + 12].hex(" ")
            print(
                f"RAW 0x{image_base + rva:08X} file+0x{index:X} "
                f"disp=0x{displacement:X} {context}"
            )
            cursor = index + 1

    print("DISASSEMBLED_REFERENCES")
    for section in pe.sections:
        if not (section.Characteristics & 0x20000000):
            continue
        start = image_base + int(section.VirtualAddress)
        block = section.get_data()
        for instruction in engine.disasm(block, start):
            matches = []
            for operand in instruction.operands:
                if operand.type != capstone.x86.X86_OP_MEM:
                    continue
                displacement = operand.mem.disp & 0xFFFFFFFF
                if displacement in wanted:
                    matches.append(displacement)
            if matches:
                raw = instruction.bytes.hex(" ").ljust(26)
                joined = ",".join(f"0x{item:X}" for item in matches)
                print(
                    f"0x{instruction.address:08X} {raw} "
                    f"{instruction.mnemonic:<8} {instruction.op_str:<36} ; {joined}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
