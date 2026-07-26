#!/usr/bin/env python3
"""Print HotA.dll instruction context for selected battle-stack fields."""

from __future__ import annotations

import argparse
from pathlib import Path

import capstone
import pefile
from capstone.x86_const import X86_OP_MEM


def parse_int(value: str) -> int:
    return int(value, 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--field", action="append", type=parse_int, required=True)
    parser.add_argument("--before", type=int, default=12)
    parser.add_argument("--after", type=int, default=18)
    args = parser.parse_args()

    pe = pefile.PE(str(args.binary), fast_load=False)
    engine = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    engine.detail = True
    wanted = {value & 0xFFFFFFFF for value in args.field}
    for section in pe.sections:
        if not section.Characteristics & 0x20000000:
            continue
        instructions = list(engine.disasm(
            section.get_data(),
            pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress,
        ))
        hits = []
        for index, instruction in enumerate(instructions):
            if any(
                operand.type == X86_OP_MEM
                and (operand.mem.disp & 0xFFFFFFFF) in wanted
                for operand in instruction.operands
            ):
                hits.append(index)
        for index in hits:
            print(f"--- HIT 0x{instructions[index].address:08X} ---")
            start = max(0, index - args.before)
            end = min(len(instructions), index + args.after + 1)
            for instruction in instructions[start:end]:
                print(
                    f"{instruction.address:08X}  {instruction.bytes.hex(' '):<24} "
                    f"{instruction.mnemonic} {instruction.op_str}".rstrip()
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
