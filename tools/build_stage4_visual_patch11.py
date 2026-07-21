#!/usr/bin/env python3
"""Build the eleventh Cure-resurrection presentation test on Patch_v1.8.

TEST10 proved that moving fixed trampolines farther into the mass-Cure block
still did not affect the live HotA/HD log order. TEST11 therefore wraps the two
native calls whose runtime execution is directly observable: the per-target
effect check records the pre-cast log boundary, and the native Cure formatter
returns through a continuation that rotates and refreshes the pointer vector.
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
BUILD_NAME = "Patch_v2.6_VISUAL_TEST11"

base.BUILD_NAME = BUILD_NAME
base.BUILD_SCOPE = "stage4_observable_native_call_log_rotation_test"
base.SUPERSEDES_TEST_BUILD = "Patch_v2.6_VISUAL_TEST10"
base.SUPERSEDED_RESULT_FIELD = "test10_runtime_result"
base.SUPERSEDED_RUNTIME_RESULT = (
    "Mass Cure remained stable but its cast line still appeared after all "
    "revival lines, proving that the hooks at 0x005A1B48 and 0x005A1C00 did "
    "not enter the live HotA/HD display path"
)


SINGLE_CURE_BLOCK_VA = test10.SINGLE_CURE_BLOCK_VA
MASS_CURE_BLOCK_VA = test10.MASS_CURE_BLOCK_VA
MASS_EFFECT_CALL_VA = 0x005A1B97
MASS_LOG_CALL_VA = 0x005A1BF6
MASS_LOG_RETURN_VA = 0x005A1BFB

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
MASS_EFFECT_CALL_EXPECTED = bytes.fromhex("e8 04 68 00 00")
MASS_LOG_CALL_EXPECTED = bytes.fromhex("e8 65 70 00 00")

test4_patch_visual_hooks = test10.test4_patch_visual_hooks
test4_build_visual_payloads = test10.test4_build_visual_payloads


def build_runtime_call_payloads() -> tuple[
    bytes, bytes, int, str, str
]:
    """Fit an observable post-formatter continuation before the resolver."""

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
    ]
    for old, new in replacements:
        if old not in wrapper_source:
            raise RuntimeError(f"TEST4 wrapper sequence missing: {old!r}")
        wrapper_source = wrapper_source.replace(old, new, 1)

    wrapper, _ = assemble(wrapper_source, CURE_WRAPPER_VA)
    if len(wrapper) != 257:
        raise RuntimeError(f"TEST11 Cure wrapper changed size: {len(wrapper)}")

    post_wrapper_va = CURE_WRAPPER_VA + len(wrapper)
    post_wrapper_source = f"""
mass_log_wrapper:
    pop eax
    push {post_wrapper_va + 11:#x}
    jmp {CURE_CAST_LOG_VA:#x}
mass_log_after_native:
    mov ecx, dword ptr [ebx + 0x132fc]
    mov eax, dword ptr [ecx + 0x58]
    add eax, dword ptr [ebp + 0x18]
    mov edx, dword ptr [ecx + 0x5c]
    sub edx, 4
    cmp eax, edx
    jae reorder_done
    push esi
    mov esi, dword ptr [edx]
shift_loop:
    xchg dword ptr [eax], esi
    add eax, 4
    cmp eax, edx
    jbe shift_loop
    pop esi
    push dword ptr [ecx + 0x68]
    call {COMBAT_LOG_REFRESH_VA:#x}
reorder_done:
    jmp {MASS_LOG_RETURN_VA:#x}
"""
    post_wrapper, _ = assemble(post_wrapper_source, post_wrapper_va)
    if len(post_wrapper) != 59:
        raise RuntimeError(
            f"TEST11 post-formatter wrapper changed size: {len(post_wrapper)}"
        )
    if post_wrapper_va + len(post_wrapper) + 4 != RESOLVER_VA:
        raise RuntimeError("TEST11 primary runtime-call payload padding changed")
    return wrapper, post_wrapper, post_wrapper_va, wrapper_source, post_wrapper_source


def build_secondary_cave() -> tuple[bytes, int, int, str, str]:
    """Reuse the safe corpse scan and append the first-effective-call recorder."""

    test9_secondary, _, magic_return_va, helper_source, _ = (
        test10.test9.build_secondary_cave()
    )
    helper = test9_secondary[:155]
    record_wrapper_va = MASS_HELPER_VA + len(helper)
    record_wrapper_source = f"""
mass_effect_record_wrapper:
    push eax
    push edx
    push edi
    lea edi, [ebx + 0x547c]
    xor eax, eax
    push 0x0a
    pop ecx
    repe scasd
    jne record_done
    mov eax, dword ptr [ebx + 0x132fc]
    mov edx, dword ptr [eax + 0x5c]
    sub edx, dword ptr [eax + 0x58]
    mov dword ptr [ebp + 0x18], edx
record_done:
    pop edi
    pop edx
    pop eax
    mov ecx, ebx
    jmp {CURE_EFFECT_CHECK_VA:#x}
"""
    record_wrapper, _ = assemble(record_wrapper_source, record_wrapper_va)
    if len(record_wrapper) != 43:
        raise RuntimeError(
            f"TEST11 effect-record wrapper changed size: {len(record_wrapper)}"
        )
    combined = helper + record_wrapper
    padding = MASS_HELPER_END_VA - (MASS_HELPER_VA + len(combined))
    if padding != 6:
        raise RuntimeError(f"TEST11 secondary padding changed: {padding}")
    combined += b"\x90" * padding
    return (
        combined,
        record_wrapper_va,
        magic_return_va,
        helper_source,
        record_wrapper_source,
    )


def build_visual_payloads_for_test11() -> tuple[
    list[tuple[int, bytes]], dict[str, Any], dict[str, int]
]:
    regions, metadata, addresses = test4_build_visual_payloads()
    metadata = json.loads(json.dumps(metadata))
    addresses = dict(addresses)
    wrapper, post_wrapper, post_wrapper_va, wrapper_source, post_wrapper_source = (
        build_runtime_call_payloads()
    )
    secondary, record_wrapper_va, magic_return_va, helper_source, record_source = (
        build_secondary_cave()
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
                "name": "mass_effect_record_wrapper",
                "va": record_wrapper_va,
                "size": 43,
                "end_exclusive_va": record_wrapper_va + 43,
                "assembly_statement_count": None,
                "assembly": record_source.strip(),
            },
            {
                "name": "mass_log_wrapper",
                "va": post_wrapper_va,
                "size": 59,
                "end_exclusive_va": post_wrapper_va + 59,
                "assembly_statement_count": None,
                "assembly": post_wrapper_source.strip(),
            },
        ]
    )
    metadata["components"] = components
    metadata["test11_final_secondary_payload_hex"] = secondary.hex(" ")
    addresses.update(
        mass_effect_record_wrapper=record_wrapper_va,
        mass_log_wrapper=post_wrapper_va,
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


def patch_visual_hooks(path: Path, stage3_report: dict[str, Any]) -> dict[str, Any]:
    test4_report = test4_patch_visual_hooks(path, stage3_report)
    test4_bytes = path.read_bytes()
    pe = pefile.PE(data=test4_bytes, fast_load=False)

    payload_regions, _, _ = test4_build_visual_payloads()
    test4_primary = next(payload for va, payload in payload_regions if va == PRIMARY_CAVE_VA)
    test4_secondary = next(payload for va, payload in payload_regions if va == MASS_HELPER_VA)
    if len(test4_primary) != PRIMARY_CAVE_LENGTH or len(test4_secondary) != 215:
        raise RuntimeError("TEST4 cave lengths changed unexpectedly")

    single = test10.test9.test8.test7.build_single_block()
    wrapper, post_wrapper, post_wrapper_va, _, _ = build_runtime_call_payloads()
    secondary_prefix, record_wrapper_va, magic_return_va, _, _ = build_secondary_cave()

    primary = bytearray(test4_primary)
    wrapper_offset = CURE_WRAPPER_VA - PRIMARY_CAVE_VA
    resolver_offset = RESOLVER_VA - PRIMARY_CAVE_VA
    primary[wrapper_offset:resolver_offset] = wrapper + post_wrapper + b"\x90" * 4
    primary = bytes(primary)
    secondary = secondary_prefix + test4_secondary[len(secondary_prefix) :]

    effect_hook = relative_branch(MASS_EFFECT_CALL_VA, record_wrapper_va, 0xE8)
    log_hook = relative_branch(MASS_LOG_CALL_VA, post_wrapper_va, 0xE8)
    replacements = {
        SINGLE_CURE_BLOCK_VA: single,
        MASS_EFFECT_CALL_VA: effect_hook,
        MASS_LOG_CALL_VA: log_hook,
        MASS_HELPER_VA: secondary,
        PRIMARY_CAVE_VA: primary,
    }
    expected = {
        SINGLE_CURE_BLOCK_VA: SINGLE_CURE_TEST4,
        MASS_EFFECT_CALL_VA: MASS_EFFECT_CALL_EXPECTED,
        MASS_LOG_CALL_VA: MASS_LOG_CALL_EXPECTED,
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
    final_mass = final[mass_offset : mass_offset + len(MASS_CURE_TEST4)]
    for index, (before, after) in enumerate(zip(MASS_CURE_TEST4, final_mass, strict=True)):
        va = MASS_CURE_BLOCK_VA + index
        in_effect_hook = MASS_EFFECT_CALL_VA <= va < MASS_EFFECT_CALL_VA + 5
        in_log_hook = MASS_LOG_CALL_VA <= va < MASS_LOG_CALL_VA + 5
        if not in_effect_hook and not in_log_hook and before != after:
            raise RuntimeError(f"TEST11 changed an unrelated mass byte at 0x{va:08X}")

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
        (MASS_EFFECT_CALL_VA, effect_hook, record_wrapper_va),
        (MASS_LOG_CALL_VA, log_hook, post_wrapper_va),
    ):
        instruction = test10.test9.test8.decode_instructions(payload, address)[0]
        if instruction.mnemonic != "call" or instruction.operands[0].imm != target:
            raise RuntimeError(f"TEST11 trampoline mismatch at 0x{address:08X}")
        hook_targets[f"0x{address:08X}"] = target

    mass_calls = test10.test9.direct_call_targets(
        test10.test9.test8.decode_instructions(final_mass, MASS_CURE_BLOCK_VA)
    )
    if mass_calls != [record_wrapper_va, CURE_WRAPPER_VA, MASS_HELPER_VA, post_wrapper_va]:
        raise RuntimeError("TEST11 mass call sequence changed")

    helper_calls = test10.test9.direct_call_targets(
        test10.test9.test8.decode_instructions(secondary_prefix, MASS_HELPER_VA)
    )
    if helper_calls != [
        GET_RESURRECTION_TARGET_VA,
        CALC_CURE_POWER_VA,
        SILENT_RESURRECT_ENTRY_VA,
    ]:
        raise RuntimeError("TEST11 secondary helper call sequence changed")
    if CURE_EFFECT_CHECK_VA not in direct_branches(
        secondary_prefix, MASS_HELPER_VA, "jmp"
    ):
        raise RuntimeError("TEST11 effect wrapper does not tail-jump to native check")

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
        raise RuntimeError("TEST11 optimized Cure wrapper call sequence changed")

    post_calls = test10.test9.direct_call_targets(
        test10.test9.test8.decode_instructions(post_wrapper, post_wrapper_va)
    )
    post_jumps = direct_branches(post_wrapper, post_wrapper_va, "jmp")
    if post_calls != [COMBAT_LOG_REFRESH_VA]:
        raise RuntimeError("TEST11 post-formatter refresh call changed")
    if CURE_CAST_LOG_VA not in post_jumps or MASS_LOG_RETURN_VA not in post_jumps:
        raise RuntimeError("TEST11 post-formatter continuation targets changed")

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
            region["label"] = "Stage 4 TEST11 corpse and observable effect-call payload"
            region["patched_hex"] = secondary.hex(" ")
        elif region["va"] == PRIMARY_CAVE_VA and region["length"] == len(primary):
            region["label"] = "Stage 4 TEST11 Cure and observable log-call payload"
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
                "Stage 4 TEST11 accepted single-Cure log-order block",
                SINGLE_CURE_BLOCK_VA,
                single,
                SINGLE_CURE_BASELINE,
            ),
            new_region(
                "Stage 4 TEST11 observable mass effect-call recorder",
                MASS_EFFECT_CALL_VA,
                effect_hook,
                MASS_EFFECT_CALL_EXPECTED,
            ),
            new_region(
                "Stage 4 TEST11 observable mass Cure-log continuation",
                MASS_LOG_CALL_VA,
                log_hook,
                MASS_LOG_CALL_EXPECTED,
            ),
        ]
    )

    rollback = bytearray(final)
    for region in regions:
        start = region["file_offset"]
        rollback[start : start + region["length"]] = bytes.fromhex(region["rollback_hex"])
    if sha256_bytes(bytes(rollback)) != test4_report["input_sha256"]:
        raise RuntimeError(f"Combined TEST11 rollback failed for {path.name}")

    path.write_bytes(final)
    report = dict(test4_report)
    report["test4_intermediate_sha256"] = report["output_sha256"]
    report["output_sha256"] = sha256_bytes(final)
    report["logical_patch_regions"] = regions
    report["exact_contiguous_differences"] = contiguous_differences(bytes(rollback), final)
    report["test10_runtime_result"] = base.SUPERSEDED_RUNTIME_RESULT
    report["test10_mass_crash_fixed"] = True
    report["test10_log_rotation_observed_effective"] = False
    report["combat_log_vector_element_size"] = 4
    report["combat_log_vector_layout_statically_verified"] = True
    report["mass_log_start_recorded_on_first_effective_native_check"] = True
    report["mass_log_rotation_runs_as_native_cure_log_return_continuation"] = True
    report["mass_log_rotation_refreshes_native_log_view"] = True
    report["mass_test4_bytes_changed_only_at_two_native_calls"] = True
    report["mass_helper_jecxz_target_va"] = magic_return_va
    report["mass_helper_jecxz_target_within_payload"] = True
    report["combat_log_string_objects_not_copied_or_duplicated"] = True
    report["ordinary_resurrection_log_path_untouched"] = True
    report["decoded_test11_hook_targets"] = hook_targets
    report["decoded_cure_log_order"] = {
        "single_call_targets": single_calls,
        "mass_call_targets": mass_calls,
        "secondary_helper_call_targets": helper_calls,
        "optimized_wrapper_direct_call_targets": wrapper_calls,
        "post_formatter_call_targets": post_calls,
        "post_formatter_jump_targets": post_jumps,
    }
    report["rollback_reconstructs_input"] = True
    return report


def instructions(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 测试说明

状态：**TEST10 日志顺序修正版；仍是测试包，不替换 `Download/Patch_v2.5.zip`。**

TEST10 已确认群体复活稳定，但群体“施放治愈”仍在全部复活记录之后。静态复核证明日志容器确实是 4 字节指针数组，轮转计算没有元素尺寸错误；问题在于先前选择的固定跳板没有进入 HD/HotA 的实际显示链。

TEST11 改为包装两条可以从实机结果直接证明必然执行的调用：

1. 第一次实际执行群体目标效果检查时记录施法前的日志边界；
2. 原版 `0x005A8C60` 治愈日志函数本身返回到 TEST11 的延续代码；
3. 延续代码轮转本次新增的 4 字节日志指针并调用原生日志刷新，然后回到原 `0x005A1BFB`；
4. TEST4 已通过的群体循环、尸体扫描、复活数量、动画和音效逻辑不变。

## 安装与测试

1. 覆盖到**干净 HotA 1.8.0**；不要叠加 TEST10 或其他补丁。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 优先测试高级水系群体治愈同时复活至少两队尸体：应不崩溃，日志先显示“英雄施放治愈”，再显示各队“起死回生”。
4. 顺带确认单体顺序、复活数量、起身/站立显示和战后永久保留不变。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    executable = report["executables"][0]
    return f"""# Stage 4 TEST11：用可观察原生调用闭合群体日志轮转

状态：**双版本静态构建、调用延续、完整回滚与 ZIP CRC 已验证；等待实机日志顺序门禁。**

## TEST10 实机结论

- 单体顺序继续正确，群体复活机制继续稳定。
- 群体“施放治愈”仍在所有复活记录之后。
- `0x00472770` 的反汇编明确按 `([log+0x5C]-[log+0x58])/4` 读取日志项，确认容器是 4 字节指针数组；既有轮转算法的元素步长正确。
- 因此 TEST8–10 的失败来自运行时没有进入独立记录/尾部跳板，而不是日志对象尺寸判断错误。

## TEST11 路径

- `0x005A1B97` 的原生群体效果检查调用改为记录包装器；受影响兵队表仍全零时，保存当前日志字节边界，再尾跳原 `0x005A83A0`，保持其浮点返回和紧接结算顺序。
- `0x005A1BF6` 的原生治愈日志调用改为延续包装器。包装器不复制参数或字符串：把原返回地址替换为洞内延续地址，尾跳原 `0x005A8C60`；原函数清理参数后，延续代码轮转指针、刷新日志并跳回原 `0x005A1BFB`。
- 群体固定块除这两个 5 字节 `CALL` 外逐字节保持 TEST4；日志容器、字符串对象及普通转世重生日志函数均未修改。
- 尸体辅助函数安全短跳目标仍为 `0x{executable['mass_helper_jecxz_target_va']:08X}`。
- 正式版 `Download/Patch_v2.5.zip` 未改变。

ZIP SHA-256：`{report['zip_sha256']}`
"""


base.build_visual_payloads = build_visual_payloads_for_test11
base.patch_visual_hooks = patch_visual_hooks
base.instructions = instructions
base.research_markdown = research_markdown


if __name__ == "__main__":
    raise SystemExit(base.main())
