#!/usr/bin/env python3
"""Build the eighth Cure-resurrection presentation test on Patch_v1.8.

TEST5-TEST7 reassembled the complete mass-Cure loop. Runtime crash addresses
inside that rewritten loop prove that HotA/HD hooks depend on its original
instruction layout, not only its apparent semantics. TEST8 restores TEST4's
accepted loop byte-for-byte from 0x005A1B36 through 0x005A1BFA. Two fixed-size
trampolines only record the pre-cast log offset at the original entry and rotate
the completed log pointer range immediately after the original cast formatter.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import capstone
import pefile
from capstone.x86_const import X86_OP_IMM

import build_stage4_visual_patch7 as test7
from build_diag_patch import contiguous_differences, sha256_bytes, va_to_offset
from build_stage3_patch import assemble, relative_branch


base = test7.base
BUILD_NAME = "Patch_v2.6_VISUAL_TEST8"

base.BUILD_NAME = BUILD_NAME
base.BUILD_SCOPE = "stage4_test4_layout_preserving_cure_log_rotation_test"
base.SUPERSEDES_TEST_BUILD = "Patch_v2.6_VISUAL_TEST7"
base.SUPERSEDED_RESULT_FIELD = "test7_runtime_result"
base.SUPERSEDED_RUNTIME_RESULT = (
    "Single Cure log order passed, but mass Cure crashed at 0x005A1B78 before "
    "the corpse helper, cast formatter, or log-rotation helper ran; TEST7's "
    "reassembled loop changed address-sensitive HotA/HD runtime behavior"
)


SINGLE_CURE_BLOCK_VA = test7.SINGLE_CURE_BLOCK_VA
MASS_CURE_BLOCK_VA = test7.MASS_CURE_BLOCK_VA
MASS_CURE_PRESERVED_START_VA = 0x005A1B36
MASS_CURE_PRESERVED_END_VA = 0x005A1BFB
MASS_CURE_FALLTHROUGH_VA = test7.MASS_CURE_FALLTHROUGH_VA
MASS_HELPER_VA = test7.MASS_HELPER_VA
MASS_HELPER_END_VA = test7.MASS_HELPER_END_VA
SILENT_RESURRECT_ENTRY_VA = test7.SILENT_RESURRECT_ENTRY_VA

PRIMARY_CAVE_VA = 0x00639D80
PRIMARY_CAVE_LENGTH = 636
CURE_WRAPPER_VA = test7.CURE_WRAPPER_VA
RESOLVER_VA = 0x00639F10

CURE_CORE_VA = 0x00446220
CURE_CAST_LOG_VA = test7.CURE_CAST_LOG_VA
CURE_EFFECT_CHECK_VA = test7.CURE_EFFECT_CHECK_VA
GET_RESURRECTION_TARGET_VA = test7.GET_RESURRECTION_TARGET_VA
CALC_CURE_POWER_VA = test7.CALC_CURE_POWER_VA
COMBAT_LOG_REFRESH_VA = test7.COMBAT_LOG_REFRESH_VA


SINGLE_CURE_TEST4 = test7.SINGLE_CURE_TEST4
SINGLE_CURE_BASELINE = test7.SINGLE_CURE_BASELINE
MASS_CURE_TEST4 = test7.MASS_CURE_TEST4
MASS_CURE_BASELINE = test7.MASS_CURE_BASELINE
MASS_FALLTHROUGH_EXPECTED = bytes.fromhex("8b55f06a00")


# Capture TEST4's builders before installing TEST8's overrides on the shared
# build_stage4_visual_patch3 module object.
test4_patch_visual_hooks = test7.test4_patch_visual_hooks
test4_build_visual_payloads = base.build_visual_payloads


def build_optimized_wrapper_and_record_helper() -> tuple[bytes, bytes, int, str, str]:
    """Shrink only internal calls so a 22-byte entry trampoline fits safely."""

    _, metadata, _ = test4_build_visual_payloads()
    wrapper_source = next(
        component["assembly"]
        for component in metadata["components"]
        if component["name"] == "cure_wrapper"
    )
    replacements = [
        (
            "    mov eax, 0x446220\n    call eax",
            "    call 0x446220",
        ),
        (
            "    mov eax, 0x5a3fd0\n    call eax",
            "    call 0x5a3fd0",
        ),
        (
            "    mov edx, 0x639cf5\n    call edx",
            "    call 0x639cf5",
        ),
        (
            "    mov eax, 0x5a3fd0\n    call eax",
            "    call 0x5a3fd0",
        ),
        (
            "    mov edx, 0x639d80\n    call edx",
            "    call 0x639d80",
        ),
    ]
    for old, new in replacements:
        if old not in wrapper_source:
            raise RuntimeError(f"TEST4 wrapper sequence missing: {old!r}")
        wrapper_source = wrapper_source.replace(old, new, 1)

    wrapper, _ = assemble(wrapper_source, CURE_WRAPPER_VA)
    if len(wrapper) != 297 or CURE_WRAPPER_VA + len(wrapper) != 0x00639EF9:
        raise RuntimeError("Optimized Cure wrapper layout changed")

    record_va = CURE_WRAPPER_VA + len(wrapper)
    record_source = """
record_mass_log_start:
    mov eax, dword ptr [ebx + 0x132fc]
    mov ecx, dword ptr [eax + 0x5c]
    sub ecx, dword ptr [eax + 0x58]
    mov dword ptr [ebp + 0x18], ecx
    lea edi, [ebx + 0x547c]
    ret
"""
    record, _ = assemble(record_source, record_va)
    if len(record) != 22 or record_va + len(record) != 0x00639F0F:
        raise RuntimeError("Mass-log entry helper no longer fits before resolver")
    if record_va + len(record) + 1 != RESOLVER_VA:
        raise RuntimeError("Mass-log entry helper must leave one padding byte")
    return wrapper, record, record_va, wrapper_source, record_source


def build_secondary_cave() -> tuple[bytes, int, str, str]:
    """Build compact TEST4 corpse scan plus post-formatter pointer rotation."""

    helper_source = f"""
mass_corpse_helper:
    mov ecx, dword ptr [ebp - 0x14]
    jecxz helper_magic_return
    mov eax, dword ptr [ecx + 0x1a]
    cmp al, 0x19
    je specialist
    cmp al, 0xaa
    jne helper_magic_return
specialist:
    push edi
    and dword ptr [ebp + 0x14], 0
stack_loop:
    mov edx, dword ptr [ebx + 0x132c0]
    mov eax, dword ptr [ebp + 0x14]
    cmp eax, dword ptr [ebx + edx * 4 + 0x54bc]
    jge helper_pop
    imul ecx, edx, 0x15
    add ecx, eax
    imul ecx, ecx, 0x548
    lea edi, [ebx + ecx + 0x54cc]
    cmp dword ptr [edi + 0x4c], 0
    jne stack_next
    cmp dword ptr [edi + 0x60], 0
    jle stack_next
    push 0
    push dword ptr [edi + 0x38]
    push edx
    mov ecx, ebx
    call {GET_RESURRECTION_TARGET_VA:#x}
    cmp eax, edi
    jne stack_next
    push dword ptr [ebp - 0x14]
    push dword ptr [ebp + 0x1c]
    push esi
    push edi
    call {CALC_CURE_POWER_VA:#x}
    test eax, eax
    jle stack_next
    push 0
    push eax
    push edi
    mov ecx, ebx
    call {SILENT_RESURRECT_ENTRY_VA:#x}
    mov eax, dword ptr [ebx + 0x132c0]
    imul eax, eax, 0x14
    add eax, dword ptr [ebp + 0x14]
    mov byte ptr [ebx + eax + 0x547c], 1
stack_next:
    inc dword ptr [ebp + 0x14]
    jmp stack_loop
helper_pop:
    pop edi
helper_magic_return:
    mov ecx, dword ptr [ebp + 0x10]
    pop eax
    push 0
    push eax
    ret
"""
    helper, _ = assemble(helper_source, MASS_HELPER_VA)
    if len(helper) != 148:
        raise RuntimeError(f"Compact corpse helper changed size: {len(helper)}")

    reorder_va = MASS_HELPER_VA + len(helper)
    reorder_source = f"""
reorder_new_log_entries_and_replay:
    mov ecx, dword ptr [ebx + 0x132fc]
    mov esi, dword ptr [ecx + 0x58]
    add esi, dword ptr [ebp + 0x18]
    mov edi, dword ptr [ecx + 0x5c]
    sub edi, 4
    cmp esi, edi
    jae reorder_done
    mov edx, dword ptr [edi]
shift_loop:
    mov eax, dword ptr [edi - 4]
    mov dword ptr [edi], eax
    sub edi, 4
    cmp edi, esi
    ja shift_loop
    mov dword ptr [esi], edx
    push dword ptr [ecx + 0x68]
    call {COMBAT_LOG_REFRESH_VA:#x}
reorder_done:
    mov edx, dword ptr [ebp - 0x10]
    pop eax
    push 0
    push eax
    ret
"""
    reorder, _ = assemble(reorder_source, reorder_va)
    if len(reorder) != 54:
        raise RuntimeError(f"Log-rotation tail changed size: {len(reorder)}")
    combined = helper + reorder
    if MASS_HELPER_VA + len(combined) != 0x00639CF3:
        raise RuntimeError("TEST8 secondary helpers changed address layout")
    combined += b"\x90" * (MASS_HELPER_END_VA - MASS_HELPER_VA - len(combined))
    if len(combined) != MASS_HELPER_END_VA - MASS_HELPER_VA:
        raise RuntimeError("TEST8 secondary cave must preserve 0x639CF5 boundary")
    return combined, reorder_va, helper_source, reorder_source


def build_visual_payloads_for_test8() -> tuple[list[tuple[int, bytes]], dict[str, Any], dict[str, int]]:
    """Return TEST4 intermediate bytes with metadata describing TEST8's final caves."""

    regions, metadata, addresses = test4_build_visual_payloads()
    metadata = json.loads(json.dumps(metadata))
    addresses = dict(addresses)
    wrapper, record, record_va, wrapper_source, record_source = (
        build_optimized_wrapper_and_record_helper()
    )
    secondary, reorder_va, helper_source, reorder_source = build_secondary_cave()

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
                size=148,
                end_exclusive_va=MASS_HELPER_VA + 148,
                assembly=helper_source.strip(),
            )
        components.append(component)
    components.extend(
        [
            {
                "name": "mass_log_reorder_tail",
                "va": reorder_va,
                "size": 54,
                "end_exclusive_va": reorder_va + 54,
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
        ]
    )
    metadata["components"] = components
    metadata["test8_final_secondary_payload_hex"] = secondary.hex(" ")
    addresses.update(
        mass_log_reorder_tail=reorder_va,
        mass_log_record_start=record_va,
    )
    return regions, metadata, addresses


def decode_instructions(code: bytes, address: int) -> list[Any]:
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    return list(decoder.disasm(code, address))


def direct_call_targets(instructions: list[Any]) -> list[int]:
    return [
        instruction.operands[0].imm
        for instruction in instructions
        if instruction.mnemonic == "call"
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

    single = test7.build_single_block()
    secondary_prefix, reorder_va, _, _ = build_secondary_cave()
    wrapper, record, record_va, _, _ = build_optimized_wrapper_and_record_helper()
    primary = bytearray(test4_primary)
    wrapper_offset = CURE_WRAPPER_VA - PRIMARY_CAVE_VA
    resolver_offset = RESOLVER_VA - PRIMARY_CAVE_VA
    primary[wrapper_offset:resolver_offset] = wrapper + record + b"\x90"
    primary = bytes(primary)
    secondary = secondary_prefix + test4_secondary[len(secondary_prefix) :]

    record_hook = relative_branch(MASS_CURE_BLOCK_VA, record_va, 0xE8) + b"\x90"
    reorder_hook = relative_branch(MASS_CURE_FALLTHROUGH_VA, reorder_va, 0xE8)
    replacements = {
        SINGLE_CURE_BLOCK_VA: single,
        MASS_CURE_BLOCK_VA: record_hook,
        MASS_CURE_FALLTHROUGH_VA: reorder_hook,
        MASS_HELPER_VA: secondary,
        PRIMARY_CAVE_VA: primary,
    }
    expected = {
        SINGLE_CURE_BLOCK_VA: SINGLE_CURE_TEST4,
        MASS_CURE_BLOCK_VA: MASS_CURE_TEST4[:6],
        MASS_CURE_FALLTHROUGH_VA: MASS_FALLTHROUGH_EXPECTED,
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

    preserved_offset = va_to_offset(pe, MASS_CURE_PRESERVED_START_VA)
    preserved_length = MASS_CURE_PRESERVED_END_VA - MASS_CURE_PRESERVED_START_VA
    test4_mass_offset = va_to_offset(pe, MASS_CURE_BLOCK_VA)
    expected_preserved = test4_bytes[
        test4_mass_offset + 6 : test4_mass_offset + 6 + preserved_length
    ]
    if final[preserved_offset : preserved_offset + preserved_length] != expected_preserved:
        raise RuntimeError("TEST8 moved or changed the accepted TEST4 mass loop")

    # The silent entry and every helper after the Stage 3 resolver remain at
    # the exact TEST4 addresses and bytes.
    silent_offset = va_to_offset(pe, SILENT_RESURRECT_ENTRY_VA)
    if final[silent_offset : silent_offset + 11] != test4_bytes[silent_offset : silent_offset + 11]:
        raise RuntimeError("TEST4 silent-resurrection entry changed")
    resolver_file_offset = va_to_offset(pe, RESOLVER_VA)
    primary_end_offset = va_to_offset(pe, PRIMARY_CAVE_VA) + PRIMARY_CAVE_LENGTH
    if final[resolver_file_offset:primary_end_offset] != test4_bytes[
        resolver_file_offset:primary_end_offset
    ]:
        raise RuntimeError("Stage 3 resolver/validation/effect helpers changed")

    hook_targets = {}
    for address, payload, target in (
        (MASS_CURE_BLOCK_VA, record_hook, record_va),
        (MASS_CURE_FALLTHROUGH_VA, reorder_hook, reorder_va),
    ):
        instruction = decode_instructions(payload, address)[0]
        if instruction.mnemonic != "call" or instruction.operands[0].imm != target:
            raise RuntimeError(f"TEST8 trampoline target mismatch at 0x{address:08X}")
        hook_targets[f"0x{address:08X}"] = target

    mass_calls = direct_call_targets(
        decode_instructions(
            final[test4_mass_offset : test4_mass_offset + len(MASS_CURE_TEST4)],
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
        raise RuntimeError("TEST8 accepted mass-loop call sequence changed")

    helper_calls = direct_call_targets(
        decode_instructions(secondary_prefix, MASS_HELPER_VA)
    )
    if helper_calls != [
        GET_RESURRECTION_TARGET_VA,
        CALC_CURE_POWER_VA,
        SILENT_RESURRECT_ENTRY_VA,
        COMBAT_LOG_REFRESH_VA,
    ]:
        raise RuntimeError("TEST8 secondary helper call sequence changed")

    wrapper_calls = direct_call_targets(
        decode_instructions(wrapper, CURE_WRAPPER_VA)
    )
    if wrapper_calls != [
        CURE_CORE_VA,
        GET_RESURRECTION_TARGET_VA,
        SILENT_RESURRECT_ENTRY_VA,
        GET_RESURRECTION_TARGET_VA,
        CALC_CURE_POWER_VA,
    ]:
        raise RuntimeError("Optimized wrapper direct-call sequence changed")

    single_calls = direct_call_targets(decode_instructions(single, SINGLE_CURE_BLOCK_VA))
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
            region["label"] = "Stage 4 TEST8 compact corpse/log helper payload"
            region["patched_hex"] = secondary.hex(" ")
        elif region["va"] == PRIMARY_CAVE_VA and region["length"] == len(primary):
            region["label"] = "Stage 4 TEST8 Cure wrapper and log-entry payload"
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
                "Stage 4 TEST8 accepted single-Cure log-order block",
                SINGLE_CURE_BLOCK_VA,
                single,
                SINGLE_CURE_BASELINE,
            ),
            new_region(
                "Stage 4 TEST8 mass-log entry trampoline",
                MASS_CURE_BLOCK_VA,
                record_hook,
                MASS_CURE_BASELINE[:6],
            ),
            new_region(
                "Stage 4 TEST8 post-formatter log-rotation trampoline",
                MASS_CURE_FALLTHROUGH_VA,
                reorder_hook,
                MASS_FALLTHROUGH_EXPECTED,
            ),
        ]
    )

    rollback = bytearray(final)
    for region in regions:
        start = region["file_offset"]
        rollback[start : start + region["length"]] = bytes.fromhex(region["rollback_hex"])
    if sha256_bytes(bytes(rollback)) != test4_report["input_sha256"]:
        raise RuntimeError(f"Combined TEST8 rollback failed for {path.name}")

    path.write_bytes(final)
    report = dict(test4_report)
    report["test4_intermediate_sha256"] = report["output_sha256"]
    report["output_sha256"] = sha256_bytes(final)
    report["logical_patch_regions"] = regions
    report["exact_contiguous_differences"] = contiguous_differences(bytes(rollback), final)
    report["test7_crash_eip"] = "0x005A1B78"
    report["test7_crashed_before_new_helpers"] = True
    report["mass_test4_loop_bytes_preserved_va_range"] = "0x005A1B36-0x005A1BFA"
    report["mass_test4_loop_bytes_preserved_sha256"] = sha256(expected_preserved).hexdigest()
    report["mass_entry_hook_length"] = len(record_hook)
    report["mass_post_formatter_hook_length"] = len(reorder_hook)
    report["mass_log_offset_saved_before_settlement"] = True
    report["mass_cast_log_runs_at_original_test4_address_and_timing"] = True
    report["mass_new_log_pointer_range_rotated_after_formatter"] = True
    report["combat_log_string_objects_not_copied_or_duplicated"] = True
    report["ordinary_resurrection_log_path_untouched"] = True
    report["decoded_test8_hook_targets"] = hook_targets
    report["decoded_cure_log_order"] = {
        "single_call_targets": single_calls,
        "mass_call_targets_before_post_formatter_trampoline": mass_calls,
        "secondary_helper_call_targets": helper_calls,
        "optimized_wrapper_direct_call_targets": wrapper_calls,
        "mass_post_formatter_reorder_target": reorder_va,
    }
    report["rollback_reconstructs_input"] = True
    return report


def instructions(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 测试说明

状态：**TEST7 群体崩溃修正版；仍是测试包，不替换 `Download/Patch_v2.5.zip`。**

TEST7 的单体治愈日志顺序已经通过，但群体治愈仍在 `0x005A1B78` 崩溃。该地址处于群体目标索引计算阶段；当时尚未进入尸体扫描、施法记录或日志轮转。由此确认，TEST5–TEST7 对整段群体循环的重编译改变了 HotA/HD Hook 依赖的原始指令地址。

TEST8 改回已通过全部功能门禁的 TEST4 原始群体布局：

1. `0x005A1B36–0x005A1BFA` 与 TEST4 逐字节一致；
2. 入口只用一个 6 字节固定跳板记录施法前日志长度，并重放原来的第一条指令；
3. 原版 `0x005A8C60` 仍在原地址、原时点写入“英雄施放治愈”；
4. 施法记录返回后，用一个 5 字节固定跳板轮转本次新增日志指针，再重放被替换的两条原指令；
5. 不复制、不释放、不重建日志字符串。

## 安装

1. 覆盖到**干净 HotA 1.8.0**；不要叠加 TEST4、TEST5、TEST6、TEST7 或其他补丁。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 先启动 `h3hota HD.exe` 到主菜单，再进入战斗。

## 优先测试

1. 高级水系群体治愈同时复活至少两队尸体：确认不崩溃，数量、起身、站立姿势和战后永久保留均正常。
2. 打开战斗日志：应先显示“英雄施放治愈”，随后显示各队“起死回生”。
3. 群体治愈同时包含受伤存活兵队和全灭尸体，确认治疗与复活都正常。
4. 单体治愈复活尸体应继续保持已经通过的“先治愈、后复活”日志顺序。
5. 亡灵、重叠尸体、被占格尸体、普通转世重生，以及治愈/复活动画和音效隔离规则均应保持 TEST4 结果。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    executable = report["executables"][0]
    return f"""# Stage 4 TEST8：保持 TEST4 群体循环原始地址布局

状态：**静态构建、双版本逐字节布局、完整回滚与 ZIP CRC 已验证；等待实机门禁。**

## TEST7 崩溃证据

- 单体治愈正常，日志顺序已达到“先治愈、后复活”。
- 群体治愈异常 EIP 为 `0x005A1B78`，读取随机地址 `0xF6715754`。
- 此处仍在计算当前群体目标栈地址，位于 TEST7 新增的尸体扫描、原版施法格式化器和日志轮转函数之前。
- 因此崩溃不是日志指针轮转本身造成，而是整段群体循环重编译后改变了 HotA/HD 地址敏感 Hook 的运行条件。

## TEST8 设计

- 从唯一可信 `Patch_v1.8` 重建，并先生成已通过实机的 TEST4 中间态。
- 仅把群体入口 `0x005A1B30–0x005A1B35` 改为 6 字节 `CALL + NOP`；辅助函数记录日志向量的字节长度并重放原 `LEA EDI,[EBX+0x547C]`。
- `0x005A1B36–0x005A1BFA` 的哈希固定为 `{executable['mass_test4_loop_bytes_preserved_sha256']}`，与 TEST4 完全一致。
- 仅把原施法格式化器后的 `0x005A1BFB–0x005A1BFF` 改为 5 字节 `CALL`；尾辅助函数轮转指针后重放 `MOV EDX,[EBP-0x10]` 与 `PUSH 0`，再返回 `0x005A1C00`。
- 尸体扫描仍沿用 TEST4 的原生资格校验、永久复活、起身动画和音效隔离语义；只用 `JECXZ` 与短比较压缩等价代码以容纳日志尾函数。
- Cure 包装器只把五处 `MOV reg,imm32; CALL reg` 压缩为等价的相对 `CALL`，为入口记录辅助函数腾出空间；Stage 3 解析器、验证器和效果门完整保留原地址及原字节。

## 静态门禁

- 标准版与 HD 版独立核对 TEST4 中间字节、两个固定跳板目标、原群体循环哈希、辅助调用顺序和回滚。
- `0x00639CF5` 静音永久复活入口及 `0x00639F10` 后的 Stage 3 辅助函数未移动。
- 原生普通转世重生日志路径、全局日志追加函数和字符串所有权未 Hook。
- 正式版 `Download/Patch_v2.5.zip` 未改变。

ZIP SHA-256：`{report['zip_sha256']}`
"""


base.build_visual_payloads = build_visual_payloads_for_test8
base.patch_visual_hooks = patch_visual_hooks
base.instructions = instructions
base.research_markdown = research_markdown


if __name__ == "__main__":
    raise SystemExit(base.main())
