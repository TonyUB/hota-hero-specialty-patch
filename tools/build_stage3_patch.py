#!/usr/bin/env python3
"""Build the Stage 3 Cure corpse-resurrection test patch.

The patch extends the accepted Stage 2 Cure overflow wrapper without writing
combat-stack state directly. Corpse lookup, eligibility, placement, animation,
and permanent resurrection remain owned by the native engine routines.
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import zipfile
from pathlib import Path
from typing import Any

import capstone
import keystone
import pefile
from capstone.x86_const import X86_OP_IMM

from build_diag_patch import (
    CAVE_END_EXCLUSIVE_VA,
    CAVE_VA,
    EXE_NAMES,
    IAT,
    contiguous_differences,
    create_zip,
    import_addresses,
    safe_recreate_directory,
    sha256_bytes,
    sha256_file,
    va_to_offset,
    verify_baseline,
)


BUILD_NAME = "Patch_v2.5_STAGE3_TEST3"

MAINPROC_STRING_VA = 0x00639C20
MAINPROC_STRING = b"MainProc\x00"

# 0x00639C28 is the terminating NUL for the runtime GetProcAddress name
# "MainProc". The original Stage 3 test incorrectly started there and made
# startup resolve a longer, invalid export name. Payload may begin only after it.
SECOND_CAVE_VA = 0x00639C29
SECOND_CAVE_END_EXCLUSIVE_VA = 0x00639D00

CURE_CORE_VA = 0x00446220
HERO_SPELL_BONUS_VA = 0x004E6260
CELL_LIVING_TARGET_VA = 0x004E7230
GET_RESURRECTION_TARGET_VA = 0x005A3FD0
RESURRECT_TARGET_VA = 0x005A7870

SINGLE_CURE_CALL_VA = 0x005A1B05
MASS_CURE_CALL_VA = 0x005A1BB4
MASS_AFTER_LIVING_LOOP_VA = 0x005A1BEC
MASS_AFTER_LIVING_LOOP_RETURN_VA = 0x005A1BF1
CAST_CURE_EFFECT_GATE_VA = 0x005A05E1
CAST_CURE_EFFECT_ORIGINAL_CONTINUE_VA = 0x005A05E8
CAST_CURE_EFFECT_BYPASS_VA = 0x005A0628
CAST_CURE_EFFECT_NO_TARGET_VA = 0x005A062B
TARGET_RESOLVER_SWITCH_VA = 0x005A3C77
TARGET_RESOLVER_ORIGINAL_CONTINUE_VA = 0x005A3C7D
TARGET_VALIDATION_GATE_VA = 0x005A3D26
TARGET_VALIDATION_ORIGINAL_CONTINUE_VA = 0x005A3D2B
TARGET_VALIDATION_SUCCESS_VA = 0x005A3D45

PATCH_V18_EXPECTED = {
    SINGLE_CURE_CALL_VA: bytes.fromhex("E8 16 47 EA FF"),
    MASS_CURE_CALL_VA: bytes.fromhex("E8 67 46 EA FF"),
    MASS_AFTER_LIVING_LOOP_VA: bytes.fromhex("8B 4D 10 6A 00"),
    CAST_CURE_EFFECT_GATE_VA: bytes.fromhex("85 FF 74 46 8B 55 10"),
    TARGET_RESOLVER_SWITCH_VA: bytes.fromhex("8B 55 08 83 EA 26"),
    TARGET_VALIDATION_GATE_VA: bytes.fromhex("8B 4D FC 57 53"),
}


def align(value: int, alignment: int = 0x10) -> int:
    return (value + alignment - 1) & -alignment


def assemble(source: str, address: int) -> tuple[bytes, int]:
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoded, count = engine.asm(source, addr=address)
    return bytes(encoded), count


def relative_branch(source_va: int, target_va: int, opcode: int) -> bytes:
    displacement = target_va - (source_va + 5)
    return bytes([opcode]) + struct.pack("<i", displacement)


def assemble_payload() -> tuple[list[tuple[int, bytes]], dict[str, Any], dict[str, int]]:
    components: list[tuple[str, int, bytes, int, str]] = []

    calc_va = CAVE_VA
    calc_source = f"""
calc_cure_power:
    push ebp
    mov ebp, esp
    push esi
    mov eax, dword ptr [0x00687FA8]
    mov ecx, dword ptr [eax + 0x13D8]
    imul ecx, dword ptr [ebp + 0x10]
    mov edx, dword ptr [ebp + 0x0C]
    mov esi, dword ptr [eax + edx * 4 + 0x13DC]
    add esi, ecx
    mov ecx, dword ptr [ebp + 0x14]
    test ecx, ecx
    jz calc_done
    push esi
    mov eax, dword ptr [ebp + 0x08]
    push dword ptr [eax + 0x78]
    push 0x25
    mov eax, {HERO_SPELL_BONUS_VA:#x}
    call eax
    add esi, eax
calc_done:
    mov eax, esi
    pop esi
    mov esp, ebp
    pop ebp
    ret 0x10
"""
    calc_code, calc_count = assemble(calc_source, calc_va)
    components.append(("calc_cure_power", calc_va, calc_code, calc_count, calc_source))

    wrapper_va = align(calc_va + len(calc_code))
    wrapper_source = f"""
cure_wrapper:
    mov eax, dword ptr [esp + 0x0C]
    test eax, eax
    jz tail_cure
    mov edx, dword ptr [eax + 0x1A]
    cmp edx, 0x19
    je specialist
    cmp edx, 0xAA
    jne tail_cure
specialist:
    cmp dword ptr [ecx + 0x4C], 0
    jle dead_stack

live_stack:
    push ebp
    mov ebp, esp
    sub esp, 0x34
    push ebx
    push esi
    push edi
    mov dword ptr [ebp - 0x04], ecx
    mov dword ptr [ebp - 0x08], ebx
    mov eax, dword ptr [ecx + 0x4C]
    mov dword ptr [ebp - 0x10], eax
    mov eax, dword ptr [ecx + 0x60]
    mov dword ptr [ebp - 0x14], eax

    push dword ptr [ebp + 0x10]
    push dword ptr [ebp + 0x0C]
    push dword ptr [ebp + 0x08]
    mov ecx, dword ptr [ebp - 0x04]
    mov eax, {CURE_CORE_VA:#x}
    call eax
    pushfd
    pop dword ptr [ebp - 0x2C]
    mov dword ptr [ebp - 0x1C], eax
    mov dword ptr [ebp - 0x30], ecx
    mov dword ptr [ebp - 0x34], edx

    xor edx, edx
    test eax, eax
    jns live_overflow_ready
    mov edx, eax
    neg edx
live_overflow_ready:
    mov dword ptr [ebp - 0x20], edx
    cmp dword ptr [ebp - 0x20], 0
    jle live_finish
    mov eax, dword ptr [ebp - 0x10]
    cmp eax, dword ptr [ebp - 0x14]
    jge live_finish

    mov eax, dword ptr [ebp - 0x04]
    push 0
    push dword ptr [eax + 0x38]
    mov ecx, dword ptr [ebp - 0x08]
    push dword ptr [ecx + 0x132C0]
    mov eax, {GET_RESURRECTION_TARGET_VA:#x}
    call eax
    test eax, eax
    je live_finish
    cmp eax, dword ptr [ebp - 0x04]
    jne live_finish

    push 0
    push dword ptr [ebp - 0x20]
    push eax
    mov ecx, dword ptr [ebp - 0x08]
    mov edx, {RESURRECT_TARGET_VA:#x}
    call edx

live_finish:
    mov eax, dword ptr [ebp - 0x1C]
    mov ecx, dword ptr [ebp - 0x30]
    mov edx, dword ptr [ebp - 0x34]
    pop edi
    pop esi
    pop ebx
    push dword ptr [ebp - 0x2C]
    popfd
    mov esp, ebp
    pop ebp
    ret 0x0C

dead_stack:
    push ebp
    mov ebp, esp
    sub esp, 0x08
    push ebx
    push esi
    push edi
    mov dword ptr [ebp - 0x04], ecx
    mov dword ptr [ebp - 0x08], ebx
    cmp dword ptr [ecx + 0x60], 0
    jle dead_finish

    push 0
    push dword ptr [ecx + 0x38]
    mov eax, dword ptr [ebp - 0x08]
    push dword ptr [eax + 0x132C0]
    mov ecx, eax
    mov eax, {GET_RESURRECTION_TARGET_VA:#x}
    call eax
    test eax, eax
    je dead_finish
    cmp eax, dword ptr [ebp - 0x04]
    jne dead_finish

    push dword ptr [ebp + 0x10]
    push dword ptr [ebp + 0x0C]
    push dword ptr [ebp + 0x08]
    push eax
    mov edx, {calc_va:#x}
    call edx
    test eax, eax
    jle dead_finish

    push 0
    push eax
    push dword ptr [ebp - 0x04]
    mov ecx, dword ptr [ebp - 0x08]
    mov edx, {RESURRECT_TARGET_VA:#x}
    call edx

dead_finish:
    xor eax, eax
    pop edi
    pop esi
    pop ebx
    mov esp, ebp
    pop ebp
    ret 0x0C

tail_cure:
    mov eax, {CURE_CORE_VA:#x}
    jmp eax
"""
    wrapper_code, wrapper_count = assemble(wrapper_source, wrapper_va)
    components.append(("cure_wrapper", wrapper_va, wrapper_code, wrapper_count, wrapper_source))

    resolver_va = align(wrapper_va + len(wrapper_code))
    resolver_source = f"""
target_resolver_gate:
    mov edx, dword ptr [ebp + 0x08]
    cmp edx, 0x25
    jne resolver_original

    push ecx
    mov eax, dword ptr [ebp + 0x10]
    lea edx, [eax * 8]
    sub edx, eax
    shl edx, 4
    lea ecx, [edx + ecx + 0x1C4]
    mov eax, {CELL_LIVING_TARGET_VA:#x}
    call eax
    test eax, eax
    jnz resolver_return_living
    pop ecx

    cmp dword ptr [ebp + 0x18], 0
    jne resolver_zero
    mov edx, dword ptr [ebp + 0x0C]
    cmp edx, dword ptr [ecx + 0x132C0]
    jne resolver_zero
    mov eax, dword ptr [ecx + edx * 4 + 0x53CC]
    test eax, eax
    jz resolver_zero
    mov eax, dword ptr [eax + 0x1A]
    cmp eax, 0x19
    je resolver_corpse
    cmp eax, 0xAA
    jne resolver_zero

resolver_corpse:
    push dword ptr [ebp + 0x18]
    push dword ptr [ebp + 0x10]
    push dword ptr [ebp + 0x0C]
    mov eax, {GET_RESURRECTION_TARGET_VA:#x}
    call eax
    pop ebp
    ret 0x14

resolver_return_living:
    add esp, 4
    pop ebp
    ret 0x14

resolver_zero:
    xor eax, eax
    pop ebp
    ret 0x14

resolver_original:
    sub edx, 0x26
    jmp {TARGET_RESOLVER_ORIGINAL_CONTINUE_VA:#x}
"""
    resolver_code, resolver_count = assemble(resolver_source, resolver_va)
    components.append(("target_resolver_gate", resolver_va, resolver_code, resolver_count, resolver_source))

    validation_va = align(resolver_va + len(resolver_code))
    validation_source = f"""
target_validation_gate:
    cmp esi, 0x25
    jne validation_original
    cmp dword ptr [eax + 0x4C], 0
    jne validation_original
    jmp {TARGET_VALIDATION_SUCCESS_VA:#x}
validation_original:
    mov ecx, dword ptr [ebp - 0x04]
    push edi
    push ebx
    jmp {TARGET_VALIDATION_ORIGINAL_CONTINUE_VA:#x}
"""
    validation_code, validation_count = assemble(validation_source, validation_va)
    components.append(("target_validation_gate", validation_va, validation_code, validation_count, validation_source))

    effect_gate_va = align(validation_va + len(validation_code))
    effect_gate_source = f"""
single_corpse_effect_gate:
    test edi, edi
    jz {CAST_CURE_EFFECT_NO_TARGET_VA:#x}
    cmp dword ptr [ebp + 0x08], 0x25
    jne effect_original
    cmp dword ptr [edi + 0x4C], 0
    jne effect_original
    mov eax, dword ptr [ebp - 0x14]
    test eax, eax
    jz effect_original
    cmp byte ptr [eax + 0x1A], 0x19
    je effect_validate_corpse
    cmp byte ptr [eax + 0x1A], 0xAA
    jne effect_original

effect_validate_corpse:
    push 0
    push dword ptr [edi + 0x38]
    push dword ptr [ebx + 0x132C0]
    mov ecx, ebx
    mov eax, {GET_RESURRECTION_TARGET_VA:#x}
    call eax
    cmp eax, edi
    jne effect_original
    jmp {CAST_CURE_EFFECT_BYPASS_VA:#x}

effect_original:
    mov edx, dword ptr [ebp + 0x10]
    jmp {CAST_CURE_EFFECT_ORIGINAL_CONTINUE_VA:#x}
"""
    effect_gate_code, effect_gate_count = assemble(effect_gate_source, effect_gate_va)
    components.append(
        (
            "single_corpse_effect_gate",
            effect_gate_va,
            effect_gate_code,
            effect_gate_count,
            effect_gate_source,
        )
    )

    mass_va = SECOND_CAVE_VA
    mass_source = f"""
mass_corpse_hook:
    push ebp
    mov ebp, esp
    sub esp, 0x10
    push ebx
    push esi
    push edi

    mov eax, dword ptr [ebp]
    mov eax, dword ptr [eax - 0x14]
    mov dword ptr [ebp - 0x04], eax
    test eax, eax
    jz mass_finish
    mov eax, dword ptr [eax + 0x1A]
    cmp eax, 0x19
    je mass_specialist
    cmp eax, 0xAA
    jne mass_finish

mass_specialist:
    mov eax, dword ptr [ebx + 0x132C0]
    mov dword ptr [ebp - 0x08], eax
    mov ecx, dword ptr [ebx + eax * 4 + 0x54BC]
    mov dword ptr [ebp - 0x10], ecx
    mov dword ptr [ebp - 0x0C], 0

mass_loop:
    mov eax, dword ptr [ebp - 0x0C]
    cmp eax, dword ptr [ebp - 0x10]
    jge mass_finish
    mov edx, dword ptr [ebp - 0x08]
    imul edx, edx, 0x15
    add edx, eax
    imul edx, edx, 0x548
    lea edi, [ebx + edx + 0x54CC]
    cmp dword ptr [edi + 0x4C], 0
    jne mass_next
    cmp dword ptr [edi + 0x60], 0
    jle mass_next

    push 0
    push dword ptr [edi + 0x38]
    push dword ptr [ebp - 0x08]
    mov ecx, ebx
    mov eax, {GET_RESURRECTION_TARGET_VA:#x}
    call eax
    cmp eax, edi
    jne mass_next

    push dword ptr [ebp - 0x04]
    mov edx, dword ptr [ebp]
    push dword ptr [edx + 0x1C]
    push esi
    push edi
    mov eax, {calc_va:#x}
    call eax
    test eax, eax
    jle mass_next

    push 0
    push eax
    push edi
    mov ecx, ebx
    mov edx, {RESURRECT_TARGET_VA:#x}
    call edx

    mov eax, dword ptr [ebp - 0x08]
    imul eax, eax, 0x14
    add eax, dword ptr [ebp - 0x0C]
    mov byte ptr [ebx + eax + 0x547C], 1

mass_next:
    inc dword ptr [ebp - 0x0C]
    jmp mass_loop

mass_finish:
    pop edi
    pop esi
    pop ebx
    mov esp, ebp
    pop ebp
    mov ecx, dword ptr [ebp + 0x10]
    pop eax
    push 0
    push eax
    ret
"""
    mass_code, mass_count = assemble(mass_source, mass_va)
    components.append(("mass_corpse_hook", mass_va, mass_code, mass_count, mass_source))

    primary_components = components[:-1]
    primary_end = effect_gate_va + len(effect_gate_code)
    if primary_end > CAVE_END_EXCLUSIVE_VA:
        layout = ", ".join(
            f"{name}=0x{address:08X}+{len(code)}"
            for name, address, code, _count, _source in primary_components
        )
        raise RuntimeError(
            f"Stage 3 primary payload exceeds cave: 0x{primary_end:08X} > "
            f"0x{CAVE_END_EXCLUSIVE_VA:08X}; {layout}"
        )
    secondary_end = mass_va + len(mass_code)
    if secondary_end > SECOND_CAVE_END_EXCLUSIVE_VA:
        raise RuntimeError(
            f"Stage 3 mass hook exceeds second cave: 0x{secondary_end:08X} > "
            f"0x{SECOND_CAVE_END_EXCLUSIVE_VA:08X}"
        )

    primary_payload = bytearray(primary_end - CAVE_VA)
    component_reports = []
    for name, address, code, count, source in primary_components:
        start = address - CAVE_VA
        primary_payload[start : start + len(code)] = code
        component_reports.append(
            {
                "name": name,
                "va": address,
                "size": len(code),
                "end_exclusive_va": address + len(code),
                "assembly_statement_count": count,
                "assembly": source.strip(),
            }
        )
    component_reports.append(
        {
            "name": "mass_corpse_hook",
            "va": mass_va,
            "size": len(mass_code),
            "end_exclusive_va": secondary_end,
            "assembly_statement_count": mass_count,
            "assembly": mass_source.strip(),
        }
    )

    addresses = {
        "calc_cure_power": calc_va,
        "cure_wrapper": wrapper_va,
        "target_resolver_gate": resolver_va,
        "target_validation_gate": validation_va,
        "single_corpse_effect_gate": effect_gate_va,
        "mass_corpse_hook": mass_va,
    }
    metadata = {
        "payload_size": len(primary_payload) + len(mass_code),
        "regions": [
            {
                "va": CAVE_VA,
                "size": len(primary_payload),
                "end_exclusive_va": primary_end,
                "cave_end_exclusive_va": CAVE_END_EXCLUSIVE_VA,
                "free_bytes": CAVE_END_EXCLUSIVE_VA - primary_end,
            },
            {
                "va": SECOND_CAVE_VA,
                "size": len(mass_code),
                "end_exclusive_va": secondary_end,
                "cave_end_exclusive_va": SECOND_CAVE_END_EXCLUSIVE_VA,
                "free_bytes": SECOND_CAVE_END_EXCLUSIVE_VA - secondary_end,
            },
        ],
        "total_free_bytes": (CAVE_END_EXCLUSIVE_VA - primary_end)
        + (SECOND_CAVE_END_EXCLUSIVE_VA - secondary_end),
        "components": component_reports,
    }
    return [
        (CAVE_VA, bytes(primary_payload)),
        (SECOND_CAVE_VA, mass_code),
    ], metadata, addresses


def patch_executable(
    path: Path, payload_regions: list[tuple[int, bytes]], addresses: dict[str, int]
) -> dict[str, Any]:
    original = path.read_bytes()
    pe = pefile.PE(data=original, fast_load=False)
    if pe.OPTIONAL_HEADER.ImageBase != 0x00400000:
        raise RuntimeError(f"Unexpected image base for {path.name}")
    if pe.OPTIONAL_HEADER.DllCharacteristics & 0x40:
        raise RuntimeError(f"ASLR is enabled unexpectedly for {path.name}")
    imports = import_addresses(pe)
    for name, expected_va in IAT.items():
        if imports.get(name) != expected_va:
            raise RuntimeError(
                f"Unexpected {name} IAT in {path.name}: {imports.get(name)!r}"
            )

    mainproc_offset = va_to_offset(pe, MAINPROC_STRING_VA)
    mainproc_actual = original[
        mainproc_offset : mainproc_offset + len(MAINPROC_STRING)
    ]
    if mainproc_actual != MAINPROC_STRING:
        raise RuntimeError(
            f"Startup export name guard failed in {path.name}: "
            f"expected {MAINPROC_STRING!r}, got {mainproc_actual!r}"
        )

    for region_va, payload in payload_regions:
        cave_offset = va_to_offset(pe, region_va)
        cave_end = cave_offset + len(payload)
        if any(original[cave_offset:cave_end]):
            raise RuntimeError(
                f"Allocated cave at 0x{region_va:08X} is not zero-filled in {path.name}"
            )

    replacements = {
        SINGLE_CURE_CALL_VA: relative_branch(
            SINGLE_CURE_CALL_VA, addresses["cure_wrapper"], 0xE8
        ),
        MASS_CURE_CALL_VA: relative_branch(
            MASS_CURE_CALL_VA, addresses["cure_wrapper"], 0xE8
        ),
        MASS_AFTER_LIVING_LOOP_VA: relative_branch(
            MASS_AFTER_LIVING_LOOP_VA, addresses["mass_corpse_hook"], 0xE8
        ),
        CAST_CURE_EFFECT_GATE_VA: relative_branch(
            CAST_CURE_EFFECT_GATE_VA, addresses["single_corpse_effect_gate"], 0xE9
        )
        + b"\x90\x90",
        TARGET_RESOLVER_SWITCH_VA: relative_branch(
            TARGET_RESOLVER_SWITCH_VA, addresses["target_resolver_gate"], 0xE9
        )
        + b"\x90",
        TARGET_VALIDATION_GATE_VA: relative_branch(
            TARGET_VALIDATION_GATE_VA, addresses["target_validation_gate"], 0xE9
        ),
    }

    patched = bytearray(original)
    logical_regions: list[dict[str, Any]] = []
    for address, expected in PATCH_V18_EXPECTED.items():
        offset = va_to_offset(pe, address)
        actual = original[offset : offset + len(expected)]
        if actual != expected:
            raise RuntimeError(
                f"Unexpected bytes at 0x{address:08X} in {path.name}: "
                f"{actual.hex(' ')}"
            )
        replacement = replacements[address]
        if len(replacement) != len(expected):
            raise AssertionError(f"Replacement length mismatch at 0x{address:08X}")
        patched[offset : offset + len(replacement)] = replacement
        logical_regions.append(
            {
                "label": f"Stage 3 hook at 0x{address:08X}",
                "va": address,
                "file_offset": offset,
                "length": len(expected),
                "original_hex": expected.hex(" "),
                "patched_hex": replacement.hex(" "),
                "rollback_hex": expected.hex(" "),
            }
        )

    for region_va, payload in payload_regions:
        cave_offset = va_to_offset(pe, region_va)
        cave_end = cave_offset + len(payload)
        patched[cave_offset:cave_end] = payload
        logical_regions.append(
            {
                "label": "Stage 3 Cure corpse-resurrection payload",
                "va": region_va,
                "file_offset": cave_offset,
                "length": len(payload),
                "original_hex": original[cave_offset:cave_end].hex(" "),
                "patched_hex": payload.hex(" "),
                "rollback_hex": original[cave_offset:cave_end].hex(" "),
            }
        )

    patched_bytes = bytes(patched)
    if len(patched_bytes) != len(original):
        raise AssertionError("PE size changed")
    if (
        patched_bytes[mainproc_offset : mainproc_offset + len(MAINPROC_STRING)]
        != MAINPROC_STRING
    ):
        raise RuntimeError(f"Startup export name was corrupted in {path.name}")
    pefile.PE(data=patched_bytes, fast_load=False)

    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    decoded_hooks = []
    for address, replacement in replacements.items():
        offset = va_to_offset(pe, address)
        instruction = next(decoder.disasm(patched_bytes[offset : offset + 5], address))
        expected_target = {
            SINGLE_CURE_CALL_VA: addresses["cure_wrapper"],
            MASS_CURE_CALL_VA: addresses["cure_wrapper"],
            MASS_AFTER_LIVING_LOOP_VA: addresses["mass_corpse_hook"],
            CAST_CURE_EFFECT_GATE_VA: addresses["single_corpse_effect_gate"],
            TARGET_RESOLVER_SWITCH_VA: addresses["target_resolver_gate"],
            TARGET_VALIDATION_GATE_VA: addresses["target_validation_gate"],
        }[address]
        if (
            instruction.operands[0].type != X86_OP_IMM
            or instruction.operands[0].imm != expected_target
        ):
            raise RuntimeError(f"Hook target verification failed at 0x{address:08X}")
        decoded_hooks.append(
            {
                "address": instruction.address,
                "bytes": instruction.bytes.hex(" "),
                "mnemonic": instruction.mnemonic,
                "operands": instruction.op_str,
            }
        )

    required_literals = {
        "CureCore": CURE_CORE_VA,
        "hero spell bonus": HERO_SPELL_BONUS_VA,
        "living target lookup": CELL_LIVING_TARGET_VA,
        "GetResurrectionTarget": GET_RESURRECTION_TARGET_VA,
        "ResurrectTarget": RESURRECT_TARGET_VA,
    }
    combined_payload = b"".join(payload for _va, payload in payload_regions)
    for label, address in required_literals.items():
        if struct.pack("<I", address) not in combined_payload:
            raise RuntimeError(f"Payload does not reference {label} at 0x{address:08X}")

    rollback = bytearray(patched_bytes)
    for region in logical_regions:
        start = region["file_offset"]
        end = start + region["length"]
        rollback[start:end] = bytes.fromhex(region["rollback_hex"])
    if bytes(rollback) != original:
        raise RuntimeError(f"Rollback reconstruction failed for {path.name}")

    path.write_bytes(patched_bytes)
    return {
        "name": path.name,
        "input_size": len(original),
        "output_size": len(patched_bytes),
        "input_sha256": sha256_bytes(original),
        "output_sha256": sha256_bytes(patched_bytes),
        "logical_patch_regions": logical_regions,
        "exact_contiguous_differences": contiguous_differences(original, patched_bytes),
        "decoded_hooks": decoded_hooks,
        "startup_export_name_va": MAINPROC_STRING_VA,
        "startup_export_name_hex": MAINPROC_STRING.hex(" "),
        "startup_export_name_preserved": True,
        "rollback_reconstructs_input": True,
    }


def instructions(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 测试说明

状态：**Stage 3 实机测试版，不替换 `Download/Patch_v2.4.zip` 稳定版。**

本包继续包含启动字符串保护，并修复 `TEST2` 中单体尸体在正式结算前被 Cure 活体效果校验判定为“抵抗魔法”的问题。

## 新增范围

- 尤兰德、阿斯特拉的单体治愈可以选择符合原生转世重生规则的己方尸体。
- 对全灭兵队使用完整治愈量进行永久复活，不先调用只适用于活体的 CureCore。
- 高级水系群体治愈完成原有活体结算后，再扫描己方全灭兵队并逐队尝试永久复活。
- 活体治疗溢出复活继续保留 Stage 2 已通过的逻辑。
- 尸体解析、亡灵等禁用规则、占格冲突、数量上限、动画与永久性都调用原生接口。
- 单体结算只在尤兰德/阿斯特拉、治愈、全灭目标且原生转世重生资格再次确认时，跳过不适用于尸体的 Cure 活体效果检查。

## 安装

1. 备份当前游戏目录中的同名文件。
2. 将 `{BUILD_NAME}.zip` 解压到 HotA 1.8.0 游戏根目录并覆盖。
3. 第一次只启动 `h3hota HD.exe` 并确认可以到达主菜单；成功后再进行下列玩法测试。

## 必测项目

1. 尤兰德单体：让一个可被转世重生的己方兵队完全阵亡，确认治愈光标可以选中尸体，并记录复活数量。
2. 阿斯特拉单体：重复上一项。
3. 尤兰德高级水系群体：同场保留受伤活体，并准备至少两个可复活的己方全灭兵队；确认活体仍正常治疗、尸体也复活。
4. 阿斯特拉高级水系群体：重复上一项。
5. 亡灵负例：完全阵亡的亡灵尸体不应被单体治愈选中，也不应被群体治愈复活。
6. 非特长英雄负例：普通英雄的治愈不能选择尸体，群体治愈不扫描尸体。
7. 战斗结束后确认新增单位永久保留。

如果尸体上叠有其他活体或多个尸体，请另行说明；原生占格规则可能只允许当前最上层、可合法落位的尸体复活。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Stage 3 尸体复活研究与测试构建",
        "",
        "状态：**静态实现完成，等待实机门禁。**",
        "",
        "## 原因定位",
        "",
        "治愈 `0x25` 在 `0x005A3C60` 的目标解析中固定走活体格解析；原生复活法术 `0x26/0x28` 才会调用 `0x005A3FD0` 读取尸体格记录。因此 Stage 2 的溢出复活可以处理仍存活兵队，但治愈无法选中全灭尸体。",
        "",
        "`0x005A3FD0` 已经完整处理尸体格、所属阵营、原兵队槽位、双格占位和 `0x005A83A0` 原生复活资格校验；无需自行重建尸体表。",
        "",
        "## 测试实现",
        "",
        "- `0x005A3C77`：治愈先保留活体解析；仅英雄施法且当前英雄为尤兰德/阿斯特拉时，活体为空才回退到原生尸体解析。",
        "- `0x005A3D26`：仅对上述已由原生复活解析确认的治愈尸体跳过不适用于尸体的 Cure 二次校验。",
        "- `0x005A05E1`：正式单体结算时再次确认英雄、治愈、全灭状态及原生复活资格，再跳过会把尸体显示为‘抵抗魔法’的 Cure 活体效果检查。",
        "- `0x005A1B05/0x005A1BB4`：保留 Stage 2 活体溢出复活；全灭目标不进入 CureCore。",
        "- `0x005A1BEC`：高级水系群体治愈的活体循环结束后，按当前阵营兵队槽位扫描 `numberAlive == 0` 的目标，并逐个再次调用原生尸体解析。",
        "- 全灭目标的治愈量复刻 CureCore 的原生数值公式，并调用英雄原生法术特长增幅函数；最终只调用 `ResurrectTarget(..., temporary=0)`。",
        "",
        "## 静态验证",
        "",
        f"- 载荷：{report['payload']['payload_size']} 字节；两个代码洞合计剩余 {report['payload']['total_free_bytes']} 字节。",
        "- 两个 EXE 的六个挂钩点均核验原字节并反汇编确认目标。",
        "- 两个 EXE 大小不变；其他包内文件哈希不变。",
        "- 每个补丁区都通过完整回滚重建；ZIP 成员与 CRC 通过。",
        "- 启动导出名 `MainProc\\0` 在写入前后均逐字节校验，第二代码洞从终止符之后的 `0x00639C29` 开始。",
        "- 当前尚未证明尸体光标、群体枚举、占格冲突和战后永久性在实机环境中的最终行为。",
        "",
        "## 输出哈希",
        "",
        f"- ZIP：`{report['zip_sha256']}`",
    ]
    for executable in report["executables"]:
        lines.append(f"- `{executable['name']}`：`{executable['output_sha256']}`")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    baseline = args.baseline.resolve()
    build_root = args.build_root.resolve()
    output_root = args.output_root.resolve()
    expected_hashes = verify_baseline(baseline, args.baseline_manifest.resolve())
    payload_regions, payload_metadata, addresses = assemble_payload()

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    shutil.copytree(baseline, package_root, dirs_exist_ok=True, copy_function=shutil.copy2)

    executable_reports = [
        patch_executable(package_root / name, payload_regions, addresses)
        for name in EXE_NAMES
    ]
    package_files = sorted(path for path in package_root.rglob("*") if path.is_file())
    if len(package_files) != len(expected_hashes):
        raise RuntimeError("Package file count changed")
    for path in package_files:
        relative = path.relative_to(package_root).as_posix()
        if relative not in EXE_NAMES and sha256_file(path) != expected_hashes[relative]:
            raise RuntimeError(f"Non-EXE package file changed: {relative}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    create_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"ZIP integrity failure: {bad_member}")
        zip_members = sorted(archive.namelist())
    expected_members = sorted(
        path.relative_to(package_root).as_posix() for path in package_files
    )
    if zip_members != expected_members:
        raise RuntimeError("ZIP member set mismatch")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "release": False,
        "runtime_logging": False,
        "scope": "stage3_single_and_mass_corpse_test",
        "fully_dead_corpse_support": True,
        "mass_cure_corpse_scan": True,
        "native_resurrection_validation": True,
        "permanent_resurrection_argument": 0,
        "baseline_manifest": args.baseline_manifest.as_posix(),
        "baseline_file_hashes": expected_hashes,
        "package_file_count": len(package_files),
        "package_file_hashes": {
            path.relative_to(package_root).as_posix(): sha256_file(path)
            for path in package_files
        },
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "payload": payload_metadata,
        "addresses": addresses,
        "executables": executable_reports,
        "static_verification": {
            "six_hook_sites_verified": True,
            "single_corpse_runtime_effect_gate_fixed": True,
            "native_target_lookup_reused": True,
            "native_resurrection_validator_reused": True,
            "native_resurrect_target_reused": True,
            "temporary_argument_is_zero": True,
            "direct_stack_state_writes_absent": True,
            "pe_sizes_unchanged": True,
            "other_package_files_unchanged": True,
            "rollback_reconstruction_passed": True,
            "zip_crc_test_passed": True,
            "startup_export_name_preserved": True,
        },
        "runtime_acceptance_required": True,
    }

    json_path = output_root / f"{BUILD_NAME}_manifest.json"
    instructions_path = output_root / f"{BUILD_NAME}_INSTRUCTIONS.md"
    research_path = output_root / f"{BUILD_NAME}_RESEARCH.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    instructions_path.write_text(instructions(report), encoding="utf-8")
    research_path.write_text(research_markdown(report), encoding="utf-8")

    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    for executable in executable_reports:
        print(f"{executable['name']}: {executable['output_sha256']}")
    print(
        f"Payload: {payload_metadata['payload_size']} bytes; "
        f"free: {payload_metadata['total_free_bytes']} bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
