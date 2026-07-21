#!/usr/bin/env python3
"""Build the twelfth Cure-resurrection presentation test on Patch_v1.8.

TEST11 proved that wrapping the mass block's native effect and Cure-log calls
still did not enter HotA/HD's live ordering path. TEST12 hooks inside the native
Cure logger, immediately after its real combat-log append. A mass-scoped byte
counts only Cure-triggered resurrection calls, so the newly appended Cure line
can be rotated backward by the exact number of revival lines.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pefile
from capstone.x86_const import X86_OP_IMM

import build_stage4_visual_patch10 as test10
from build_diag_patch import contiguous_differences, sha256_bytes, va_to_offset
from build_stage3_patch import assemble, relative_branch


base = test10.base
BUILD_NAME = "Patch_v2.6_VISUAL_TEST12"

base.BUILD_NAME = BUILD_NAME
base.BUILD_SCOPE = "stage4_native_cure_logger_post_append_rotation_test"
base.SUPERSEDES_TEST_BUILD = "Patch_v2.6_VISUAL_TEST11"
base.SUPERSEDED_RESULT_FIELD = "test11_runtime_result"
base.SUPERSEDED_RUNTIME_RESULT = (
    "Mass Cure remained stable but its cast line still appeared after all "
    "revival lines, proving that wrapping the calls at 0x005A1B97 and "
    "0x005A1BF6 did not enter the live HotA/HD ordering path"
)


SINGLE_CURE_BLOCK_VA = test10.SINGLE_CURE_BLOCK_VA
MASS_CURE_BLOCK_VA = test10.MASS_CURE_BLOCK_VA
MASS_WRAPPER_RETURN_VA = 0x005A1BB9
NATIVE_CURE_POST_APPEND_HOOK_VA = 0x005A954C
NATIVE_CURE_POST_APPEND_RETURN_VA = 0x005A9551
MASS_RESURRECTION_STATE_VA = 0x00639FFC

MASS_HELPER_VA = test10.MASS_HELPER_VA
MASS_HELPER_END_VA = test10.MASS_HELPER_END_VA
SILENT_RESURRECT_ENTRY_VA = test10.SILENT_RESURRECT_ENTRY_VA
PRIMARY_CAVE_VA = test10.PRIMARY_CAVE_VA
PRIMARY_CAVE_LENGTH = test10.PRIMARY_CAVE_LENGTH
CURE_WRAPPER_VA = test10.CURE_WRAPPER_VA
RESOLVER_VA = test10.RESOLVER_VA

CURE_CORE_VA = test10.CURE_CORE_VA
CURE_CAST_LOG_VA = test10.CURE_CAST_LOG_VA
CURE_EFFECT_CHECK_VA = test10.CURE_EFFECT_CHECK_VA
GET_RESURRECTION_TARGET_VA = test10.GET_RESURRECTION_TARGET_VA
CALC_CURE_POWER_VA = test10.CALC_CURE_POWER_VA
COMBAT_LOG_REFRESH_VA = test10.COMBAT_LOG_REFRESH_VA

SINGLE_CURE_TEST4 = test10.SINGLE_CURE_TEST4
SINGLE_CURE_BASELINE = test10.SINGLE_CURE_BASELINE
MASS_CURE_TEST4 = test10.MASS_CURE_TEST4
NATIVE_CURE_POST_APPEND_EXPECTED = bytes.fromhex("8b 4d e8 85 c9")
SILENT_RESURRECT_ENTRY_TEST4 = bytes.fromhex("fe 05 7f 9d 63 00 e9 70 db f6 ff")

test4_patch_visual_hooks = test10.test4_patch_visual_hooks
test4_build_visual_payloads = test10.test4_build_visual_payloads


def build_runtime_payloads() -> tuple[bytes, bytes, int, str, str]:
    """Build the mass-aware Cure wrapper and native-logger continuation."""

    _, metadata, _ = test4_build_visual_payloads()
    wrapper_source = next(
        component["assembly"]
        for component in metadata["components"]
        if component["name"] == "cure_wrapper"
    )
    replacements = [
        ("    mov eax, 0x446220\n    call eax", "    call 0x446220"),
        ("    mov eax, 0x5a3fd0\n    call eax", "    call 0x5a3fd0"),
        ("    mov edx, 0x639cf5\n    call edx", "    call 0x639cf5"),
        ("    mov eax, 0x5a3fd0\n    call eax", "    call 0x5a3fd0"),
        ("    mov edx, 0x639d80\n    call edx", "    call 0x639d80"),
        ("    mov edx, 0x639cf5\n    call edx", "    call 0x639cf5"),
        (
            "    xor edx, edx\n"
            "    test eax, eax\n"
            "    jns live_overflow_ready\n"
            "    mov edx, eax\n"
            "    neg edx\n"
            "live_overflow_ready:\n"
            "    mov dword ptr [ebp - 0x20], edx\n"
            "    cmp dword ptr [ebp - 0x20], 0\n"
            "    jle live_finish",
            "    test eax, eax\n"
            "    jns live_finish\n"
            "    mov edx, eax\n"
            "    neg edx\n"
            "    mov dword ptr [ebp - 0x20], edx",
        ),
        ("    mov eax, 0x446220\n    jmp eax", "    jmp 0x446220"),
        ("    sub esp, 0x34", "    sub esp, 0x20"),
        (
            "    pushfd\n"
            "    pop dword ptr [ebp - 0x2C]\n"
            "    mov dword ptr [ebp - 0x1C], eax\n"
            "    mov dword ptr [ebp - 0x30], ecx\n"
            "    mov dword ptr [ebp - 0x34], edx",
            "    mov dword ptr [ebp - 0x1C], eax",
        ),
        (
            "    mov eax, dword ptr [ebp - 0x1C]\n"
            "    mov ecx, dword ptr [ebp - 0x30]\n"
            "    mov edx, dword ptr [ebp - 0x34]\n"
            "    pop edi\n"
            "    pop esi\n"
            "    pop ebx\n"
            "    push dword ptr [ebp - 0x2C]\n"
            "    popfd",
            "    mov eax, dword ptr [ebp - 0x1C]\n"
            "    pop edi\n"
            "    pop esi\n"
            "    pop ebx",
        ),
        ("    mov dword ptr [ebp - 0x04], ecx", "    mov esi, ecx"),
        ("    mov ecx, dword ptr [ebp - 0x04]", "    mov ecx, esi"),
        ("    mov eax, dword ptr [ebp - 0x04]", "    mov eax, esi"),
        ("    cmp eax, dword ptr [ebp - 0x04]", "    cmp eax, esi"),
        (
            "cure_wrapper:\n",
            "cure_wrapper:\n"
            f"    cmp dword ptr [esp], {MASS_WRAPPER_RETURN_VA:#x}\n"
            "    jne wrapper_state_ready\n"
            f"    or byte ptr [{MASS_RESURRECTION_STATE_VA:#x}], 0x80\n"
            "wrapper_state_ready:\n",
        ),
        ("    sub esp, 0x20", "    sub esp, 0x0c"),
        ("    mov dword ptr [ebp - 0x08], ebx\n", ""),
        ("    mov dword ptr [ebp - 0x10], eax", "    mov dword ptr [ebp - 0x04], eax"),
        ("    mov dword ptr [ebp - 0x14], eax", "    mov dword ptr [ebp - 0x08], eax"),
        ("    mov dword ptr [ebp - 0x1C], eax", "    mov edi, eax"),
        ("    mov dword ptr [ebp - 0x20], edx", "    mov dword ptr [ebp - 0x0c], edx"),
        ("    mov eax, dword ptr [ebp - 0x10]", "    mov eax, dword ptr [ebp - 0x04]"),
        ("    cmp eax, dword ptr [ebp - 0x14]", "    cmp eax, dword ptr [ebp - 0x08]"),
        (
            "    mov eax, esi\n"
            "    push 0\n"
            "    push dword ptr [eax + 0x38]\n"
            "    mov ecx, dword ptr [ebp - 0x08]\n"
            "    push dword ptr [ecx + 0x132C0]",
            "    push 0\n"
            "    push dword ptr [esi + 0x38]\n"
            "    push dword ptr [ebx + 0x132C0]\n"
            "    mov ecx, ebx",
        ),
        (
            "    push dword ptr [ebp - 0x20]\n"
            "    push eax\n"
            "    mov ecx, dword ptr [ebp - 0x08]",
            "    push dword ptr [ebp - 0x0c]\n"
            "    push eax\n"
            "    mov ecx, ebx",
        ),
        ("    mov eax, dword ptr [ebp - 0x1C]", "    mov eax, edi"),
        (
            "    sub esp, 0x08\n"
            "    push ebx\n"
            "    push esi\n"
            "    push edi\n"
            "    mov dword ptr [ebp - 0x04], ecx\n"
            "    mov dword ptr [ebp - 0x08], ebx",
            "    push ebx\n"
            "    push esi\n"
            "    mov esi, ecx",
        ),
        ("    cmp dword ptr [ecx + 0x60], 0", "    cmp dword ptr [esi + 0x60], 0"),
        (
            "    push dword ptr [ecx + 0x38]\n"
            "    mov eax, dword ptr [ebp - 0x08]\n"
            "    push dword ptr [eax + 0x132C0]\n"
            "    mov ecx, eax",
            "    push dword ptr [esi + 0x38]\n"
            "    push dword ptr [ebx + 0x132C0]\n"
            "    mov ecx, ebx",
        ),
        ("    cmp eax, dword ptr [ebp - 0x04]", "    cmp eax, esi"),
        (
            "    push dword ptr [ebp - 0x04]\n"
            "    mov ecx, dword ptr [ebp - 0x08]",
            "    push esi\n"
            "    mov ecx, ebx",
        ),
        (
            "    pop edi\n"
            "    pop esi\n"
            "    pop ebx\n"
            "    mov esp, ebp\n"
            "    pop ebp\n"
            "    ret 0x0C\n\n"
            "tail_cure:",
            "    pop esi\n"
            "    pop ebx\n"
            "    mov esp, ebp\n"
            "    pop ebp\n"
            "    ret 0x0C\n\n"
            "tail_cure:",
        ),
    ]
    for old, new in replacements:
        if old not in wrapper_source:
            raise RuntimeError(f"TEST4 wrapper sequence missing: {old!r}")
        wrapper_source = wrapper_source.replace(old, new, 1)

    wrapper, _ = assemble(wrapper_source, CURE_WRAPPER_VA)
    if len(wrapper) != 248:
        raise RuntimeError(f"TEST12 Cure wrapper changed size: {len(wrapper)}")

    post_append_va = CURE_WRAPPER_VA + len(wrapper)
    post_append_source = f"""
native_cure_post_append:
    xor eax, eax
    xchg byte ptr [{MASS_RESURRECTION_STATE_VA:#x}], al
    test al, 0x80
    jz replay_displaced
    and eax, 0x7f
    jz replay_displaced
    mov ecx, dword ptr [ebp - 0x20]
    mov ecx, dword ptr [ecx + 0x132fc]
    mov edx, dword ptr [ecx + 0x5c]
    sub edx, 4
    neg eax
    lea eax, [edx + eax * 4]
    push ecx
    mov ecx, dword ptr [edx]
rotate_pointer:
    xchg dword ptr [eax], ecx
    add eax, 4
    cmp eax, edx
    jbe rotate_pointer
    pop ecx
    push dword ptr [ecx + 0x68]
    call {COMBAT_LOG_REFRESH_VA:#x}
replay_displaced:
    mov ecx, dword ptr [ebp - 0x18]
    test ecx, ecx
    ret
"""
    post_append, _ = assemble(post_append_source, post_append_va)
    if len(post_append) != 64:
        raise RuntimeError(f"TEST12 post-append helper changed size: {len(post_append)}")
    if post_append_va + len(post_append) > RESOLVER_VA:
        raise RuntimeError("TEST12 primary runtime payload overlaps the resolver")
    return wrapper, post_append, post_append_va, wrapper_source, post_append_source


def build_secondary_cave() -> tuple[bytes, int, int, str, str, str]:
    """Add mass-state initialization and count Cure resurrection calls."""

    _, _, _, helper_source, _ = test10.test9.build_secondary_cave()
    helper_source = helper_source.replace(
        "mass_corpse_helper:\n",
        "mass_corpse_helper:\n"
        f"    or byte ptr [{MASS_RESURRECTION_STATE_VA:#x}], 0x80\n",
        1,
    )
    helper, _ = assemble(helper_source, MASS_HELPER_VA)
    if len(helper) != 162:
        raise RuntimeError(f"TEST12 corpse helper changed size: {len(helper)}")

    counted_resurrect_va = MASS_HELPER_VA + len(helper)
    counted_resurrect_source = f"""
counted_silent_resurrection:
    cmp byte ptr [{MASS_RESURRECTION_STATE_VA:#x}], 0x80
    jb only_visual_flag
    inc byte ptr [{MASS_RESURRECTION_STATE_VA:#x}]
only_visual_flag:
    inc byte ptr [0x00639d7f]
    jmp 0x005a7870
"""
    counted_resurrect, _ = assemble(counted_resurrect_source, counted_resurrect_va)
    if len(counted_resurrect) != 26:
        raise RuntimeError(
            f"TEST12 counted resurrection helper changed size: {len(counted_resurrect)}"
        )
    combined = helper + counted_resurrect
    padding = MASS_HELPER_END_VA - (MASS_HELPER_VA + len(combined))
    if padding != 16:
        raise RuntimeError(f"TEST12 secondary padding changed: {padding}")
    combined += b"\x90" * padding

    silent_entry_source = f"""
silent_resurrect_entry:
    jmp {counted_resurrect_va:#x}
"""
    silent_entry, _ = assemble(silent_entry_source, SILENT_RESURRECT_ENTRY_VA)
    silent_entry += b"\x90" * (11 - len(silent_entry))
    if len(silent_entry) != 11:
        raise RuntimeError("TEST12 silent entry size changed")
    combined += silent_entry

    magic_return_va = MASS_HELPER_VA + 14
    return (
        combined,
        counted_resurrect_va,
        magic_return_va,
        helper_source,
        counted_resurrect_source,
        silent_entry_source,
    )


def build_visual_payloads_for_test12() -> tuple[
    list[tuple[int, bytes]], dict[str, Any], dict[str, int]
]:
    regions, metadata, addresses = test4_build_visual_payloads()
    metadata = json.loads(json.dumps(metadata))
    addresses = dict(addresses)
    wrapper, post_append, post_append_va, wrapper_source, post_append_source = (
        build_runtime_payloads()
    )
    (
        secondary,
        counted_resurrect_va,
        magic_return_va,
        helper_source,
        counted_resurrect_source,
        silent_entry_source,
    ) = build_secondary_cave()

    components = []
    for component in metadata["components"]:
        if component["name"] == "cure_wrapper":
            component.update(
                size=len(wrapper),
                end_exclusive_va=CURE_WRAPPER_VA + len(wrapper),
                assembly=wrapper_source.strip(),
            )
        elif component["name"] == "mass_corpse_hook":
            component.update(
                size=162,
                end_exclusive_va=MASS_HELPER_VA + 162,
                assembly=helper_source.strip(),
            )
        elif component["name"] == "silent_resurrect_entry":
            component.update(
                assembly=silent_entry_source.strip(),
                counted_helper_va=counted_resurrect_va,
            )
        components.append(component)
    components.extend(
        [
            {
                "name": "counted_silent_resurrection",
                "va": counted_resurrect_va,
                "size": 26,
                "end_exclusive_va": counted_resurrect_va + 26,
                "assembly_statement_count": None,
                "assembly": counted_resurrect_source.strip(),
            },
            {
                "name": "native_cure_post_append",
                "va": post_append_va,
                "size": 64,
                "end_exclusive_va": post_append_va + 64,
                "assembly_statement_count": None,
                "assembly": post_append_source.strip(),
                "state_va": MASS_RESURRECTION_STATE_VA,
            },
        ]
    )
    metadata["components"] = components
    metadata["test12_final_secondary_payload_hex"] = secondary.hex(" ")
    metadata["runtime_state_byte_va"] = MASS_RESURRECTION_STATE_VA
    addresses.update(
        counted_silent_resurrection=counted_resurrect_va,
        native_cure_post_append=post_append_va,
        mass_resurrection_state=MASS_RESURRECTION_STATE_VA,
        mass_helper_magic_return=magic_return_va,
    )
    return regions, metadata, addresses


def direct_branches(code: bytes, address: int, mnemonic: str) -> list[int]:
    return [
        instruction.operands[0].imm
        for instruction in test10.test9.test8.decode_instructions(code, address)
        if instruction.mnemonic == mnemonic
        and instruction.operands
        and instruction.operands[0].type == X86_OP_IMM
    ]


def patch_visual_hooks_test12(
    path: Path, stage3_report: dict[str, Any]
) -> dict[str, Any]:
    """Patch only the accepted single block, caves, and native logger epilogue."""

    test4_report = test4_patch_visual_hooks(path, stage3_report)
    test4_bytes = path.read_bytes()
    pe = pefile.PE(data=test4_bytes, fast_load=False)

    payload_regions, _, _ = test4_build_visual_payloads()
    test4_primary = next(
        payload for va, payload in payload_regions if va == PRIMARY_CAVE_VA
    )
    test4_secondary = next(
        payload for va, payload in payload_regions if va == MASS_HELPER_VA
    )
    if len(test4_primary) != PRIMARY_CAVE_LENGTH or len(test4_secondary) != 215:
        raise RuntimeError("TEST4 cave lengths changed unexpectedly")

    single = test10.test9.test8.test7.build_single_block()
    wrapper, post_append, post_append_va, _, _ = build_runtime_payloads()
    (
        secondary,
        counted_resurrect_va,
        magic_return_va,
        _,
        _,
        _,
    ) = build_secondary_cave()

    primary = bytearray(test4_primary)
    wrapper_offset = CURE_WRAPPER_VA - PRIMARY_CAVE_VA
    resolver_offset = RESOLVER_VA - PRIMARY_CAVE_VA
    runtime_payload = wrapper + post_append
    padding = resolver_offset - wrapper_offset - len(runtime_payload)
    if padding != 8:
        raise RuntimeError(f"TEST12 primary padding changed: {padding}")
    primary[wrapper_offset:resolver_offset] = runtime_payload + b"\x90" * padding
    primary = bytes(primary)

    logger_hook = relative_branch(
        NATIVE_CURE_POST_APPEND_HOOK_VA, post_append_va, 0xE8
    )
    replacements = {
        SINGLE_CURE_BLOCK_VA: single,
        NATIVE_CURE_POST_APPEND_HOOK_VA: logger_hook,
        MASS_HELPER_VA: secondary,
        PRIMARY_CAVE_VA: primary,
    }
    expected = {
        SINGLE_CURE_BLOCK_VA: SINGLE_CURE_TEST4,
        NATIVE_CURE_POST_APPEND_HOOK_VA: NATIVE_CURE_POST_APPEND_EXPECTED,
        MASS_HELPER_VA: test4_secondary,
        PRIMARY_CAVE_VA: test4_primary,
    }
    for address, expected_bytes in expected.items():
        offset = va_to_offset(pe, address)
        actual = test4_bytes[offset : offset + len(expected_bytes)]
        if actual != expected_bytes:
            raise RuntimeError(f"Unexpected TEST4 bytes at 0x{address:08X}")

    state_offset = va_to_offset(pe, MASS_RESURRECTION_STATE_VA)
    if test4_bytes[state_offset] != 0:
        raise RuntimeError("TEST12 runtime state byte is not initially zero")
    if test4_bytes[state_offset + 1] == 0:
        raise RuntimeError("TEST12 runtime state byte crossed its semantic boundary")

    patched = bytearray(test4_bytes)
    for address, replacement in replacements.items():
        offset = va_to_offset(pe, address)
        patched[offset : offset + len(replacement)] = replacement
    final = bytes(patched)

    mass_offset = va_to_offset(pe, MASS_CURE_BLOCK_VA)
    final_mass = final[mass_offset : mass_offset + len(MASS_CURE_TEST4)]
    if final_mass != MASS_CURE_TEST4:
        raise RuntimeError("TEST12 changed the accepted TEST4 mass-Cure block")

    resolver_offset = va_to_offset(pe, RESOLVER_VA)
    primary_end_offset = va_to_offset(pe, PRIMARY_CAVE_VA) + PRIMARY_CAVE_LENGTH
    if final[resolver_offset:primary_end_offset] != test4_bytes[
        resolver_offset:primary_end_offset
    ]:
        raise RuntimeError("Stage 3 resolver/validation/effect helpers changed")

    hook_instruction = test10.test9.test8.decode_instructions(
        logger_hook, NATIVE_CURE_POST_APPEND_HOOK_VA
    )[0]
    if (
        hook_instruction.mnemonic != "call"
        or hook_instruction.operands[0].imm != post_append_va
    ):
        raise RuntimeError("TEST12 native Cure logger hook target changed")

    mass_calls = test10.test9.direct_call_targets(
        test10.test9.test8.decode_instructions(final_mass, MASS_CURE_BLOCK_VA)
    )
    if mass_calls != [
        CURE_EFFECT_CHECK_VA,
        CURE_WRAPPER_VA,
        MASS_HELPER_VA,
        CURE_CAST_LOG_VA,
    ]:
        raise RuntimeError("TEST12 did not preserve the TEST4 mass call sequence")

    helper_calls = test10.test9.direct_call_targets(
        test10.test9.test8.decode_instructions(secondary, MASS_HELPER_VA)
    )
    if helper_calls != [
        GET_RESURRECTION_TARGET_VA,
        CALC_CURE_POWER_VA,
        SILENT_RESURRECT_ENTRY_VA,
    ]:
        raise RuntimeError("TEST12 secondary helper call sequence changed")

    wrapper_calls = test10.test9.direct_call_targets(
        test10.test9.test8.decode_instructions(wrapper, CURE_WRAPPER_VA)
    )
    if wrapper_calls != [
        CURE_CORE_VA,
        GET_RESURRECTION_TARGET_VA,
        SILENT_RESURRECT_ENTRY_VA,
        GET_RESURRECTION_TARGET_VA,
        CALC_CURE_POWER_VA,
        SILENT_RESURRECT_ENTRY_VA,
    ]:
        raise RuntimeError("TEST12 optimized Cure wrapper call sequence changed")

    post_calls = test10.test9.direct_call_targets(
        test10.test9.test8.decode_instructions(post_append, post_append_va)
    )
    if post_calls != [COMBAT_LOG_REFRESH_VA]:
        raise RuntimeError("TEST12 native log refresh call changed")

    silent_entry = secondary[
        SILENT_RESURRECT_ENTRY_VA - MASS_HELPER_VA :
        SILENT_RESURRECT_ENTRY_VA - MASS_HELPER_VA + 11
    ]
    silent_jumps = direct_branches(
        silent_entry, SILENT_RESURRECT_ENTRY_VA, "jmp"
    )
    counted_offset = counted_resurrect_va - MASS_HELPER_VA
    counted_helper = secondary[counted_offset : counted_offset + 26]
    counted_jumps = direct_branches(
        counted_helper, counted_resurrect_va, "jmp"
    )
    if silent_jumps != [counted_resurrect_va] or counted_jumps != [0x005A7870]:
        raise RuntimeError("TEST12 counted silent-resurrection path changed")

    single_calls = test10.test9.direct_call_targets(
        test10.test9.test8.decode_instructions(single, SINGLE_CURE_BLOCK_VA)
    )
    if single_calls.index(CURE_CAST_LOG_VA) > single_calls.index(CURE_WRAPPER_VA):
        raise RuntimeError("Accepted single-Cure log ordering changed")

    regions = json.loads(json.dumps(test4_report["logical_patch_regions"]))

    def overlaps_single(region: dict[str, Any]) -> bool:
        start = region["va"]
        end = start + region["length"]
        return start < SINGLE_CURE_BLOCK_VA + len(single) and end > SINGLE_CURE_BLOCK_VA

    regions = [region for region in regions if not overlaps_single(region)]
    for region in regions:
        if region["va"] == MASS_HELPER_VA and region["length"] == len(secondary):
            region["label"] = "Stage 4 TEST12 counted Cure-resurrection payload"
            region["patched_hex"] = secondary.hex(" ")
        elif region["va"] == PRIMARY_CAVE_VA and region["length"] == len(primary):
            region["label"] = "Stage 4 TEST12 Cure and native-log payload"
            region["patched_hex"] = primary.hex(" ")

    def new_region(
        label: str, va: int, payload: bytes, rollback_bytes: bytes
    ) -> dict[str, Any]:
        return {
            "label": label,
            "va": va,
            "file_offset": va_to_offset(pe, va),
            "length": len(payload),
            "original_hex": rollback_bytes.hex(" "),
            "patched_hex": payload.hex(" "),
            "rollback_hex": rollback_bytes.hex(" "),
        }

    regions.extend(
        [
            new_region(
                "Stage 4 TEST12 accepted single-Cure log-order block",
                SINGLE_CURE_BLOCK_VA,
                single,
                SINGLE_CURE_BASELINE,
            ),
            new_region(
                "Stage 4 TEST12 native Cure logger post-append hook",
                NATIVE_CURE_POST_APPEND_HOOK_VA,
                logger_hook,
                NATIVE_CURE_POST_APPEND_EXPECTED,
            ),
        ]
    )

    rollback = bytearray(final)
    for region in regions:
        start = region["file_offset"]
        rollback[start : start + region["length"]] = bytes.fromhex(
            region["rollback_hex"]
        )
    if sha256_bytes(bytes(rollback)) != test4_report["input_sha256"]:
        raise RuntimeError(f"Combined TEST12 rollback failed for {path.name}")

    path.write_bytes(final)
    report = dict(test4_report)
    report["test4_intermediate_sha256"] = report["output_sha256"]
    report["output_sha256"] = sha256_bytes(final)
    report["logical_patch_regions"] = regions
    report["exact_contiguous_differences"] = contiguous_differences(
        bytes(rollback), final
    )
    report["test11_runtime_result"] = base.SUPERSEDED_RUNTIME_RESULT
    report["test11_log_rotation_observed_effective"] = False
    report["combat_log_vector_element_size"] = 4
    report["combat_log_vector_layout_statically_verified"] = True
    report["mass_state_initialized_by_wrapper_and_corpse_helper"] = True
    report["cure_resurrection_calls_counted_exactly"] = True
    report["native_cure_logger_post_append_hooked"] = True
    report["native_cure_logger_displaced_instructions_replayed"] = True
    report["mass_log_rotation_uses_exact_resurrection_count"] = True
    report["mass_log_rotation_refreshes_native_log_view"] = True
    report["mass_test4_block_byte_identical"] = True
    report["mass_helper_jecxz_target_va"] = magic_return_va
    report["mass_helper_jecxz_target_within_payload"] = True
    report["runtime_state_byte_va"] = MASS_RESURRECTION_STATE_VA
    report["runtime_state_byte_initial_value"] = 0
    report["runtime_state_boundary_byte_preserved"] = True
    report["ordinary_resurrection_entry_untouched"] = True
    report["decoded_test12_hook_target"] = post_append_va
    report["decoded_cure_log_order"] = {
        "single_call_targets": single_calls,
        "mass_call_targets": mass_calls,
        "secondary_helper_call_targets": helper_calls,
        "optimized_wrapper_direct_call_targets": wrapper_calls,
        "post_append_call_targets": post_calls,
        "silent_entry_jump_targets": silent_jumps,
        "counted_helper_jump_targets": counted_jumps,
    }
    report["rollback_reconstructs_input"] = True
    return report


def instructions_test12(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 测试说明

状态：**TEST11 日志顺序修正版；仍是测试包，不替换 `Download/Patch_v2.5.zip`。**

TEST11 的群体复活、动画和音效均保持稳定，但“英雄施放治愈”仍显示在全部复活记录之后。TEST12 不再修改群体循环外围的日志调用，而是进入原版治愈日志函数内部：原版把“施放治愈”真正追加到战斗日志之后，立即按本次治愈实际触发的复活队数把该记录前移。

本版保持不变：

- TEST4 已通过的单体/群体复活数量、永久保留、亡灵排除、重叠/占格尸体规则；
- 仅保留治愈术动画、原版治愈音效及每队复活的起身动作；
- 不显示转世重生圆圈，不播放转世重生音效；
- 单体治愈现有的“先治愈、后复活”顺序；
- 普通转世重生的动画、音效和日志路径。

## 安装与测试

1. 覆盖到**干净 HotA 1.8.0**，不要叠加 TEST11 或其他补丁。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 重点测试高级水系群体治愈一次复活两队或更多部队：应不崩溃，日志先显示“英雄施放治愈”，随后显示每队“起死回生了”。
4. 顺带确认单体顺序、复活数量、起身/站立显示、音效和战后永久保留均不变。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown_test12(report: dict[str, Any]) -> str:
    executable = report["executables"][0]
    return f"""# Stage 4 TEST12：在原生治愈日志追加后按复活次数轮转

状态：**标准版与 HD 版静态构建、完整回滚、可复现性和 ZIP CRC 已验证；等待实机日志顺序门禁。**

## TEST11 实机结论

- 单体顺序正确，群体复活机制稳定，但群体“施放治愈”仍在所有复活记录之后。
- 因此 HotA/HD 运行时没有采用 TEST11 在群体块 `0x005A1B97` / `0x005A1BF6` 设置的外围延续路径。

## TEST12 路径

- 群体治愈包装器和尸体辅助函数把单字节状态标记为本次群体施法；每次治愈专用静默复活成功进入原生 `0x005A7870` 前，低 7 位准确累计一次。
- 原版治愈日志函数 `0x005A8C60` 在 `0x005A9547` 调用原生 `0x004729D0`，这一步正是屏幕上“施放治愈”的实际追加。TEST12 在紧接其后的 `0x005A954C` 用同长度 `CALL` 进入洞内助手。
- 助手原子取出并清零本次状态，把最后一个治愈日志指针向前轮转“实际复活次数”个位置，再调用原生日志刷新 `0x00472770`，最后重放被替换的 `mov ecx,[ebp-0x18] / test ecx,ecx`。
- 群体固定块逐字节保持 TEST4；单体顺序、复活结算、视觉/音效隔离和普通转世重生路径均不变。
- 运行时状态字节为 `0x{executable['runtime_state_byte_va']:08X}`，尸体辅助函数安全短跳目标为 `0x{executable['mass_helper_jecxz_target_va']:08X}`。
- 正式版 `Download/Patch_v2.5.zip` 未改变。

ZIP SHA-256：`{report['zip_sha256']}`
"""


base.build_visual_payloads = build_visual_payloads_for_test12
base.patch_visual_hooks = patch_visual_hooks_test12
base.instructions = instructions_test12
base.research_markdown = research_markdown_test12


if __name__ == "__main__":
    raise SystemExit(base.main())
