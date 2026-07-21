#!/usr/bin/env python3
"""Build the tenth Cure-resurrection presentation test on Patch_v1.8.

TEST9 kept mass Cure stable but proved that the runtime does not execute the
log-length hook placed in the table-initialization prefix. TEST10 moves the
record hook to the mandatory stack-count read at 0x005A1B48 and moves the
rotation hook to the post-formatter argument-preparation instruction at
0x005A1C00. Both trampolines replay the exact displaced instructions.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pefile

import build_stage4_visual_patch9 as test9
from build_diag_patch import contiguous_differences, sha256_bytes, va_to_offset
from build_stage3_patch import assemble, relative_branch


base = test9.base
BUILD_NAME = "Patch_v2.6_VISUAL_TEST10"

base.BUILD_NAME = BUILD_NAME
base.BUILD_SCOPE = "stage4_mandatory_runtime_log_rotation_test"
base.SUPERSEDES_TEST_BUILD = "Patch_v2.6_VISUAL_TEST9"
base.SUPERSEDED_RESULT_FIELD = "test9_runtime_result"
base.SUPERSEDED_RUNTIME_RESULT = (
    "Single Cure remained correct and mass Cure no longer crashed, but the "
    "Cure cast line still appeared after every revival line; the hook in the "
    "mass table-initialization prefix was bypassed by the HotA/HD runtime path"
)


SINGLE_CURE_BLOCK_VA = test9.SINGLE_CURE_BLOCK_VA
MASS_CURE_BLOCK_VA = test9.MASS_CURE_BLOCK_VA
MASS_LOG_RECORD_HOOK_VA = 0x005A1B48
MASS_LOG_RECORD_RETURN_VA = 0x005A1B4F
MASS_LOG_REORDER_HOOK_VA = 0x005A1C00
MASS_LOG_REORDER_RETURN_VA = 0x005A1C05

MASS_HELPER_VA = test9.MASS_HELPER_VA
MASS_HELPER_END_VA = test9.MASS_HELPER_END_VA
SILENT_RESURRECT_ENTRY_VA = test9.SILENT_RESURRECT_ENTRY_VA
PRIMARY_CAVE_VA = test9.PRIMARY_CAVE_VA
PRIMARY_CAVE_LENGTH = test9.PRIMARY_CAVE_LENGTH
CURE_WRAPPER_VA = test9.CURE_WRAPPER_VA
RESOLVER_VA = test9.RESOLVER_VA

CURE_CORE_VA = test9.CURE_CORE_VA
CURE_CAST_LOG_VA = test9.CURE_CAST_LOG_VA
CURE_EFFECT_CHECK_VA = test9.CURE_EFFECT_CHECK_VA
GET_RESURRECTION_TARGET_VA = test9.GET_RESURRECTION_TARGET_VA
CALC_CURE_POWER_VA = test9.CALC_CURE_POWER_VA
COMBAT_LOG_REFRESH_VA = test9.COMBAT_LOG_REFRESH_VA

SINGLE_CURE_TEST4 = test9.SINGLE_CURE_TEST4
SINGLE_CURE_BASELINE = test9.SINGLE_CURE_BASELINE
MASS_CURE_TEST4 = test9.MASS_CURE_TEST4
MASS_LOG_RECORD_EXPECTED = bytes.fromhex("8b 84 93 bc 54 00 00")
MASS_LOG_REORDER_EXPECTED = bytes.fromhex("8b cb 8b 42 08")

test4_patch_visual_hooks = test9.test4_patch_visual_hooks
test4_build_visual_payloads = test9.test4_build_visual_payloads


def build_wrapper_record_and_replay() -> tuple[
    bytes, bytes, bytes, int, int, str, str, str
]:
    """Fit the wrapper, record helper, and replay tail before the resolver."""

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
    ]
    for old, new in replacements:
        if old not in wrapper_source:
            raise RuntimeError(f"TEST4 wrapper sequence missing: {old!r}")
        wrapper_source = wrapper_source.replace(old, new, 1)

    wrapper, _ = assemble(wrapper_source, CURE_WRAPPER_VA)
    if len(wrapper) != 285:
        raise RuntimeError(f"TEST10 Cure wrapper changed size: {len(wrapper)}")

    record_va = CURE_WRAPPER_VA + len(wrapper)
    record_source = """
record_mass_log_start:
    mov ecx, dword ptr [ebx + 0x132fc]
    mov eax, dword ptr [ecx + 0x5c]
    sub eax, dword ptr [ecx + 0x58]
    mov dword ptr [ebp + 0x18], eax
    mov eax, dword ptr [ebx + edx * 4 + 0x54bc]
    ret
"""
    record, _ = assemble(record_source, record_va)
    if len(record) != 23 or record_va + len(record) != 0x00639F04:
        raise RuntimeError("TEST10 record helper layout changed")

    replay_va = record_va + len(record)
    replay_source = """
post_log_replay:
    mov edx, dword ptr [ebp - 0x10]
    mov ecx, ebx
    mov eax, dword ptr [edx + 8]
    ret
"""
    replay, _ = assemble(replay_source, replay_va)
    if len(replay) != 9 or replay_va + len(replay) != 0x00639F0D:
        raise RuntimeError("TEST10 post-log replay layout changed")
    if replay_va + len(replay) + 3 != RESOLVER_VA:
        raise RuntimeError("TEST10 primary helpers must leave three padding bytes")
    return (
        wrapper,
        record,
        replay,
        record_va,
        replay_va,
        wrapper_source,
        record_source,
        replay_source,
    )


def build_secondary_cave(replay_va: int) -> tuple[bytes, int, int, str, str]:
    """Reuse TEST9's safe corpse scan and jump to the primary replay tail."""

    test9_secondary, _, magic_return_va, helper_source, _ = test9.build_secondary_cave()
    helper = test9_secondary[:155]
    reorder_va = MASS_HELPER_VA + len(helper)
    reorder_source = f"""
reorder_new_log_entries:
    mov ecx, dword ptr [ebx + 0x132fc]
    mov esi, dword ptr [ecx + 0x58]
    add esi, dword ptr [ebp + 0x18]
    mov edi, dword ptr [ecx + 0x5c]
    sub edi, 4
    cmp esi, edi
    jae reorder_done
    mov edx, dword ptr [edi]
shift_loop:
    xchg dword ptr [esi], edx
    add esi, 4
    cmp esi, edi
    jbe shift_loop
    push dword ptr [ecx + 0x68]
    call {COMBAT_LOG_REFRESH_VA:#x}
reorder_done:
    jmp {replay_va:#x}
"""
    reorder, _ = assemble(reorder_source, reorder_va)
    if len(reorder) != 46:
        raise RuntimeError(f"TEST10 log-rotation helper changed size: {len(reorder)}")
    combined = helper + reorder
    padding = MASS_HELPER_END_VA - (MASS_HELPER_VA + len(combined))
    if padding != 3:
        raise RuntimeError(f"TEST10 secondary padding changed: {padding}")
    combined += b"\x90" * padding
    return combined, reorder_va, magic_return_va, helper_source, reorder_source


def build_visual_payloads_for_test10() -> tuple[
    list[tuple[int, bytes]], dict[str, Any], dict[str, int]
]:
    """Return TEST4 cave bytes while describing TEST10's final cave payloads."""

    regions, metadata, addresses = test4_build_visual_payloads()
    metadata = json.loads(json.dumps(metadata))
    addresses = dict(addresses)
    (
        wrapper,
        record,
        replay,
        record_va,
        replay_va,
        wrapper_source,
        record_source,
        replay_source,
    ) = build_wrapper_record_and_replay()
    secondary, reorder_va, magic_return_va, helper_source, reorder_source = (
        build_secondary_cave(replay_va)
    )

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
                size=155,
                end_exclusive_va=MASS_HELPER_VA + 155,
                assembly=helper_source.strip(),
            )
        components.append(component)
    components.extend(
        [
            {
                "name": "mass_log_reorder_tail",
                "va": reorder_va,
                "size": 46,
                "end_exclusive_va": reorder_va + 46,
                "assembly_statement_count": None,
                "assembly": reorder_source.strip(),
            },
            {
                "name": "mass_log_record_start",
                "va": record_va,
                "size": len(record),
                "end_exclusive_va": record_va + len(record),
                "assembly_statement_count": None,
                "assembly": record_source.strip(),
            },
            {
                "name": "post_log_replay",
                "va": replay_va,
                "size": len(replay),
                "end_exclusive_va": replay_va + len(replay),
                "assembly_statement_count": None,
                "assembly": replay_source.strip(),
            },
        ]
    )
    metadata["components"] = components
    metadata["test10_final_secondary_payload_hex"] = secondary.hex(" ")
    addresses.update(
        mass_log_reorder_tail=reorder_va,
        mass_log_record_start=record_va,
        post_log_replay=replay_va,
        mass_helper_magic_return=magic_return_va,
    )
    return regions, metadata, addresses


def patch_visual_hooks(path: Path, stage3_report: dict[str, Any]) -> dict[str, Any]:
    test4_report = test4_patch_visual_hooks(path, stage3_report)
    test4_bytes = path.read_bytes()
    pe = pefile.PE(data=test4_bytes, fast_load=False)

    payload_regions, _, _ = test4_build_visual_payloads()
    test4_primary = next(payload for va, payload in payload_regions if va == PRIMARY_CAVE_VA)
    test4_secondary = next(payload for va, payload in payload_regions if va == MASS_HELPER_VA)
    if len(test4_primary) != PRIMARY_CAVE_LENGTH or len(test4_secondary) != 215:
        raise RuntimeError("TEST4 cave lengths changed unexpectedly")

    single = test9.test8.test7.build_single_block()
    (
        wrapper,
        record,
        replay,
        record_va,
        replay_va,
        _,
        _,
        _,
    ) = build_wrapper_record_and_replay()
    secondary_prefix, reorder_va, magic_return_va, _, _ = build_secondary_cave(
        replay_va
    )

    primary = bytearray(test4_primary)
    wrapper_offset = CURE_WRAPPER_VA - PRIMARY_CAVE_VA
    resolver_offset = RESOLVER_VA - PRIMARY_CAVE_VA
    primary[wrapper_offset:resolver_offset] = wrapper + record + replay + b"\x90" * 3
    primary = bytes(primary)
    secondary = secondary_prefix + test4_secondary[len(secondary_prefix) :]

    record_hook = (
        relative_branch(MASS_LOG_RECORD_HOOK_VA, record_va, 0xE8) + b"\x90\x90"
    )
    reorder_hook = relative_branch(MASS_LOG_REORDER_HOOK_VA, reorder_va, 0xE8)
    replacements = {
        SINGLE_CURE_BLOCK_VA: single,
        MASS_LOG_RECORD_HOOK_VA: record_hook,
        MASS_LOG_REORDER_HOOK_VA: reorder_hook,
        MASS_HELPER_VA: secondary,
        PRIMARY_CAVE_VA: primary,
    }
    expected = {
        SINGLE_CURE_BLOCK_VA: SINGLE_CURE_TEST4,
        MASS_LOG_RECORD_HOOK_VA: MASS_LOG_RECORD_EXPECTED,
        MASS_LOG_REORDER_HOOK_VA: MASS_LOG_REORDER_EXPECTED,
        MASS_HELPER_VA: test4_secondary,
        PRIMARY_CAVE_VA: test4_primary,
    }
    for address, expected_bytes in expected.items():
        offset = va_to_offset(pe, address)
        actual = test4_bytes[offset : offset + len(expected_bytes)]
        if actual != expected_bytes:
            raise RuntimeError(f"Unexpected TEST4 bytes at 0x{address:08X}")

    patched = bytearray(test4_bytes)
    for address, replacement in replacements.items():
        offset = va_to_offset(pe, address)
        patched[offset : offset + len(replacement)] = replacement
    final = bytes(patched)

    mass_offset = va_to_offset(pe, MASS_CURE_BLOCK_VA)
    pre_record_length = MASS_LOG_RECORD_HOOK_VA - MASS_CURE_BLOCK_VA
    if final[mass_offset : mass_offset + pre_record_length] != test4_bytes[
        mass_offset : mass_offset + pre_record_length
    ]:
        raise RuntimeError("TEST10 changed TEST4 mass bytes before 0x005A1B48")
    after_record_offset = va_to_offset(pe, MASS_LOG_RECORD_RETURN_VA)
    after_record_length = MASS_LOG_REORDER_HOOK_VA - MASS_LOG_RECORD_RETURN_VA
    if final[after_record_offset : after_record_offset + after_record_length] != test4_bytes[
        after_record_offset : after_record_offset + after_record_length
    ]:
        raise RuntimeError("TEST10 changed TEST4 mass bytes between its two hooks")

    silent_offset = va_to_offset(pe, SILENT_RESURRECT_ENTRY_VA)
    if final[silent_offset : silent_offset + 11] != test4_bytes[silent_offset : silent_offset + 11]:
        raise RuntimeError("TEST4 silent-resurrection entry changed")
    resolver_offset = va_to_offset(pe, RESOLVER_VA)
    primary_end_offset = va_to_offset(pe, PRIMARY_CAVE_VA) + PRIMARY_CAVE_LENGTH
    if final[resolver_offset:primary_end_offset] != test4_bytes[
        resolver_offset:primary_end_offset
    ]:
        raise RuntimeError("Stage 3 resolver/validation/effect helpers changed")

    hook_targets = {}
    for address, payload, target in (
        (MASS_LOG_RECORD_HOOK_VA, record_hook, record_va),
        (MASS_LOG_REORDER_HOOK_VA, reorder_hook, reorder_va),
    ):
        instruction = test9.test8.decode_instructions(payload, address)[0]
        if instruction.mnemonic != "call" or instruction.operands[0].imm != target:
            raise RuntimeError(f"TEST10 trampoline mismatch at 0x{address:08X}")
        hook_targets[f"0x{address:08X}"] = target

    mass_calls = test9.direct_call_targets(
        test9.test8.decode_instructions(
            final[mass_offset : mass_offset + len(MASS_CURE_TEST4)],
            MASS_CURE_BLOCK_VA,
        )
    )
    if mass_calls != [
        record_va,
        CURE_EFFECT_CHECK_VA,
        CURE_WRAPPER_VA,
        MASS_HELPER_VA,
        CURE_CAST_LOG_VA,
    ]:
        raise RuntimeError("TEST10 mass call sequence changed")

    reorder_offset = va_to_offset(pe, MASS_LOG_REORDER_HOOK_VA)
    reorder_instruction = test9.test8.decode_instructions(
        final[reorder_offset : reorder_offset + 5], MASS_LOG_REORDER_HOOK_VA
    )[0]
    if reorder_instruction.operands[0].imm != reorder_va:
        raise RuntimeError("TEST10 post-formatter rotation hook changed")

    helper_calls = test9.direct_call_targets(
        test9.test8.decode_instructions(secondary_prefix, MASS_HELPER_VA)
    )
    if helper_calls != [
        GET_RESURRECTION_TARGET_VA,
        CALC_CURE_POWER_VA,
        SILENT_RESURRECT_ENTRY_VA,
        COMBAT_LOG_REFRESH_VA,
    ]:
        raise RuntimeError("TEST10 secondary helper call sequence changed")

    wrapper_calls = test9.direct_call_targets(
        test9.test8.decode_instructions(wrapper, CURE_WRAPPER_VA)
    )
    if wrapper_calls != [
        CURE_CORE_VA,
        GET_RESURRECTION_TARGET_VA,
        SILENT_RESURRECT_ENTRY_VA,
        GET_RESURRECTION_TARGET_VA,
        CALC_CURE_POWER_VA,
        SILENT_RESURRECT_ENTRY_VA,
    ]:
        raise RuntimeError("TEST10 optimized wrapper call sequence changed")

    single_calls = test9.direct_call_targets(
        test9.test8.decode_instructions(single, SINGLE_CURE_BLOCK_VA)
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
            region["label"] = "Stage 4 TEST10 mandatory-path corpse/log helper payload"
            region["patched_hex"] = secondary.hex(" ")
        elif region["va"] == PRIMARY_CAVE_VA and region["length"] == len(primary):
            region["label"] = "Stage 4 TEST10 wrapper, record, and replay payload"
            region["patched_hex"] = primary.hex(" ")

    def new_region(label: str, va: int, payload: bytes, rollback_bytes: bytes) -> dict[str, Any]:
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
                "Stage 4 TEST10 accepted single-Cure log-order block",
                SINGLE_CURE_BLOCK_VA,
                single,
                SINGLE_CURE_BASELINE,
            ),
            new_region(
                "Stage 4 TEST10 mandatory stack-count log record hook",
                MASS_LOG_RECORD_HOOK_VA,
                record_hook,
                MASS_LOG_RECORD_EXPECTED,
            ),
            new_region(
                "Stage 4 TEST10 mandatory post-formatter log rotation hook",
                MASS_LOG_REORDER_HOOK_VA,
                reorder_hook,
                MASS_LOG_REORDER_EXPECTED,
            ),
        ]
    )

    rollback = bytearray(final)
    for region in regions:
        start = region["file_offset"]
        rollback[start : start + region["length"]] = bytes.fromhex(region["rollback_hex"])
    if sha256_bytes(bytes(rollback)) != test4_report["input_sha256"]:
        raise RuntimeError(f"Combined TEST10 rollback failed for {path.name}")

    path.write_bytes(final)
    report = dict(test4_report)
    report["test4_intermediate_sha256"] = report["output_sha256"]
    report["output_sha256"] = sha256_bytes(final)
    report["logical_patch_regions"] = regions
    report["exact_contiguous_differences"] = contiguous_differences(bytes(rollback), final)
    report["test9_runtime_result"] = base.SUPERSEDED_RUNTIME_RESULT
    report["test9_mass_crash_fixed"] = True
    report["test9_log_rotation_observed_effective"] = False
    report["mass_test4_bytes_preserved_before_record_sha256"] = sha256(
        test4_bytes[mass_offset : mass_offset + pre_record_length]
    ).hexdigest()
    report["mass_test4_bytes_preserved_between_hooks_sha256"] = sha256(
        test4_bytes[after_record_offset : after_record_offset + after_record_length]
    ).hexdigest()
    report["mass_log_record_hook_va"] = MASS_LOG_RECORD_HOOK_VA
    report["mass_log_record_hook_replays_original_stack_count_read"] = True
    report["mass_log_rotation_hook_va"] = MASS_LOG_REORDER_HOOK_VA
    report["mass_log_rotation_hook_replays_displaced_argument_setup"] = True
    report["mass_log_rotation_uses_forward_pointer_swaps"] = True
    report["mass_helper_jecxz_target_va"] = magic_return_va
    report["mass_helper_jecxz_target_within_payload"] = True
    report["mass_cast_log_runs_at_original_test4_address_and_timing"] = True
    report["combat_log_string_objects_not_copied_or_duplicated"] = True
    report["ordinary_resurrection_log_path_untouched"] = True
    report["decoded_test10_hook_targets"] = hook_targets
    report["decoded_cure_log_order"] = {
        "single_call_targets": single_calls,
        "mass_call_targets_before_post_formatter_hook": mass_calls,
        "secondary_helper_call_targets": helper_calls,
        "optimized_wrapper_direct_call_targets": wrapper_calls,
        "mass_post_formatter_reorder_target": reorder_va,
        "post_log_replay_target": replay_va,
    }
    report["rollback_reconstructs_input"] = True
    return report


def instructions(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 测试说明

状态：**TEST9 日志顺序修正版；仍是测试包，不替换 `Download/Patch_v2.5.zip`。**

TEST9 已确认单体顺序正确、群体复活稳定，但群体日志仍把“施放治愈”放在所有“起死回生”之后。TEST10 不改变复活、动画或音效，只把日志挂钩移到群体施法实际运行路径中的两条必经指令：

1. 在 `0x005A1B48` 读取群体堆栈数量时记录本次施法前的日志末尾；随后重放原读取指令。
2. 原版治愈施法记录写入后，在 `0x005A1C00` 进入后续参数准备时轮转本次新增的日志指针；随后重放原来的寄存器与参数准备指令。
3. 群体逐队结算顺序、尸体扫描、永久复活、起身动画、治愈音效与复活特效/音效隔离全部保持 TEST4/TEST9 路径。

## 安装与测试

1. 覆盖到**干净 HotA 1.8.0**；不要叠加 TEST9 或其他补丁。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 优先测试高级水系群体治愈同时复活至少两队尸体：应不崩溃，且日志先显示“英雄施放治愈”，再显示各队“起死回生”。
4. 顺带确认单体仍保持同样顺序，复活数量、站立显示及战后保留不变。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    executable = report["executables"][0]
    return f"""# Stage 4 TEST10：把日志挂钩移到群体施法必经运行指令

状态：**双版本静态构建、地址/指令重放、完整回滚与 ZIP CRC 已验证；等待实机日志顺序门禁。**

## TEST9 实机结论

- 单体日志已是“先治愈、后复活”。
- 群体复活不再崩溃，实际机制、动画和音效均正常。
- 群体“施放治愈”仍在全部复活记录之后，说明 `0x005A1B36` 所在初始化前缀没有进入 HotA/HD 的实际显示路径。

## TEST10 改动

- `0x005A1B30–0x005A1B47` 保持 TEST4 原字节；记录跳板移到必经数量读取 `0x005A1B48`，7 字节覆盖后由辅助函数重放 `MOV EAX,[EBX+EDX*4+0x54BC]`。
- `0x005A1B4F–0x005A1BFF` 保持 TEST4 原字节，包括原版 `0x005A8C60` 施法记录调用。
- 轮转跳板移到紧随施法记录之后的 `0x005A1C00`；辅助函数完成轮转后重放 `MOV ECX,EBX / MOV EAX,[EDX+8]`，并返回 `0x005A1C05`。
- 两个跳板均为同长度替换，不移动 TEST4 已验证的群体循环、复活处理或原版日志调用地址。

## 静态门禁

- 群体前段保留哈希：`{executable['mass_test4_bytes_preserved_before_record_sha256']}`
- 两挂钩之间保留哈希：`{executable['mass_test4_bytes_preserved_between_hooks_sha256']}`
- 记录挂钩：`0x{executable['mass_log_record_hook_va']:08X}`
- 轮转挂钩：`0x{executable['mass_log_rotation_hook_va']:08X}`
- 尸体辅助函数安全短跳目标：`0x{executable['mass_helper_jecxz_target_va']:08X}`
- 未复制、释放或重建任何日志字符串对象；仅轮转本次新增范围内的指针。
- 正式版 `Download/Patch_v2.5.zip` 未改变。

ZIP SHA-256：`{report['zip_sha256']}`
"""


base.build_visual_payloads = build_visual_payloads_for_test10
base.patch_visual_hooks = patch_visual_hooks
base.instructions = instructions
base.research_markdown = research_markdown


if __name__ == "__main__":
    raise SystemExit(base.main())
