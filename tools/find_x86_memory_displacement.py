#!/usr/bin/env python3
"""Find x86 instructions that reference a selected memory displacement in a PE."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import capstone
import pefile
from capstone.x86 import X86_OP_MEM


def number(value: str) -> int:
    return int(value, 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip", type=Path)
    parser.add_argument("displacement", type=number)
    parser.add_argument("--member", required=True)
    args = parser.parse_args()

    with zipfile.ZipFile(args.zip) as archive:
        data = archive.read(args.member)
    pe = pefile.PE(data=data, fast_load=False)
    image_base = int(pe.OPTIONAL_HEADER.ImageBase)
    engine = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    engine.detail = True
    engine.skipdata = True

    matches: list[tuple[int, str, str, str]] = []
    for section in pe.sections:
        if not (int(section.Characteristics) & 0x20000000):
            continue
        start = int(section.PointerToRawData)
        size = min(int(section.SizeOfRawData), len(data) - start)
        va = image_base + int(section.VirtualAddress)
        for instruction in engine.disasm(data[start:start + size], va):
            if instruction.id == 0:
                continue
            if any(
                operand.type == X86_OP_MEM
                and operand.mem.disp == args.displacement
                for operand in instruction.operands
            ):
                matches.append(
                    (
                        instruction.address,
                        instruction.bytes.hex(" "),
                        instruction.mnemonic,
                        instruction.op_str,
                    )
                )

    print(
        f"member={args.member} imageBase=0x{image_base:08X} "
        f"disp=0x{args.displacement:X} matches={len(matches)}"
    )
    for address, raw, mnemonic, operands in matches:
        print(f"0x{address:08X}  {raw:<28} {mnemonic:<8} {operands}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
