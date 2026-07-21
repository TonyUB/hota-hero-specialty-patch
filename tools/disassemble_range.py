#!/usr/bin/env python3
"""Disassemble an explicit VA range from a 32-bit PE image."""

from __future__ import annotations

import argparse
from pathlib import Path

import capstone
import pefile
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM


def parse_int(value: str) -> int:
    return int(value, 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("start_va", type=parse_int)
    parser.add_argument("end_va", type=parse_int)
    parser.add_argument(
        "--xrefs",
        action="store_true",
        help="scan executable sections for immediate or absolute-memory references",
    )
    args = parser.parse_args()

    if args.end_va <= args.start_va:
        parser.error("end_va must be greater than start_va")

    pe = pefile.PE(str(args.binary), fast_load=False)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    start_rva = args.start_va - image_base
    end_rva = args.end_va - image_base
    start_offset = pe.get_offset_from_rva(start_rva)
    end_offset = pe.get_offset_from_rva(end_rva)
    data = pe.__data__[start_offset:end_offset]

    engine = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    engine.detail = True
    for instruction in engine.disasm(data, args.start_va):
        print(
            f"{instruction.address:08X}  {instruction.bytes.hex(' '):<24} "
            f"{instruction.mnemonic} {instruction.op_str}".rstrip()
        )

    if args.xrefs:
        print("XREFS")
        engine.skipdata = True
        for section in pe.sections:
            if not section.Characteristics & 0x20000000:
                continue
            section_va = image_base + section.VirtualAddress
            for instruction in engine.disasm(section.get_data(), section_va):
                if instruction.id == 0:
                    continue
                targets: list[int] = []
                for operand in instruction.operands:
                    if operand.type == X86_OP_IMM:
                        targets.append(operand.imm)
                    elif (
                        operand.type == X86_OP_MEM
                        and operand.mem.base == 0
                        and operand.mem.index == 0
                    ):
                        targets.append(operand.mem.disp)
                if any(args.start_va <= target < args.end_va for target in targets):
                    print(
                        f"{instruction.address:08X}  {instruction.bytes.hex(' '):<24} "
                        f"{instruction.mnemonic} {instruction.op_str}".rstrip()
                    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
