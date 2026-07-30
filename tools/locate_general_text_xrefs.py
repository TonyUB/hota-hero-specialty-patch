#!/usr/bin/env python3
"""Locate x86 code that reads selected H3 GENRLTXT entries.

The executable stores a pointer to the loaded general-text table at a known
absolute address.  This helper finds a load of that pointer followed by an
indexed entry read in the same basic instruction window.  It is intentionally
only a static locator: every result remains a candidate until runtime logging
confirms the path in HotA 1.8.0.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import capstone
import pefile
from capstone.x86_const import X86_OP_MEM, X86_OP_REG


def number(value: str) -> int:
    return int(value, 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--table-pointer", type=number, default=0x006A5DC4)
    parser.add_argument("--indices", type=number, nargs="+", required=True)
    parser.add_argument("--window", type=int, default=16)
    args = parser.parse_args()

    data = args.binary.read_bytes()
    pe = pefile.PE(data=data, fast_load=False)
    engine = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    engine.detail = True
    engine.skipdata = True
    wanted = {index * 4: index for index in args.indices}

    matches: list[tuple[int, int, list[capstone.CsInsn]]] = []
    for section in pe.sections:
        if not int(section.Characteristics) & 0x20000000:
            continue
        start = int(section.PointerToRawData)
        size = min(int(section.SizeOfRawData), len(data) - start)
        va = int(pe.OPTIONAL_HEADER.ImageBase) + int(section.VirtualAddress)
        instructions = [
            item for item in engine.disasm(data[start : start + size], va)
            if item.id != 0
        ]
        for position, instruction in enumerate(instructions):
            if len(instruction.operands) < 2:
                continue
            destination, source = instruction.operands[:2]
            if destination.type != X86_OP_REG or source.type != X86_OP_MEM:
                continue
            memory = source.mem
            if memory.base or memory.index or memory.disp != args.table_pointer:
                continue
            register = destination.reg
            following = instructions[position : position + args.window]
            for candidate in following[1:]:
                for operand in candidate.operands:
                    if operand.type != X86_OP_MEM:
                        continue
                    memory = operand.mem
                    if memory.base == register and memory.index == 0 and memory.disp in wanted:
                        matches.append((instruction.address, wanted[memory.disp], following))
                        break
                else:
                    continue
                break

    print(
        f"binary={args.binary} tablePointer=0x{args.table_pointer:08X} "
        f"indices={args.indices} matches={len(matches)}"
    )
    for load_address, index, instructions in matches:
        print(f"\nLOAD 0x{load_address:08X} -> GENRLTXT[{index}]")
        for instruction in instructions:
            print(
                f"0x{instruction.address:08X}  {instruction.bytes.hex(' '):<24} "
                f"{instruction.mnemonic:<8} {instruction.op_str}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
