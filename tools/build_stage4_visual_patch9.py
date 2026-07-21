#!/usr/bin/env python3
"""Build the ninth Cure-resurrection presentation test on Patch_v1.8.

TEST8 proved that keeping TEST4's mass-Cure instruction addresses prevents the
runtime crash, but its pre-cast log-length hook at 0x005A1B30 did not affect the
observed log order. TEST9 restores that entry instruction and moves the same
fixed-length hook to 0x005A1B36, the mandatory table-clear count instruction.
All following instruction addresses remain unchanged. It also fixes TEST8's
out-of-range JECXZ encoding and uses a smaller forward swap rotation.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import capstone
import pefile
from capstone.x86_const import X86_OP_IMM

import build_stage4_visual_patch8 as test8
from build_diag_patch import contiguous_differences, sha256_bytes, va_to_offset
from build_stage3_patch import assemble, relative_branch


base = test8.base
BUILD_NAME = "Patch_v2.6_VISUAL_TEST9"

base.BUILD_NAME = BUILD_NAME
base.BUILD_SCOPE = "stage4_mandatory_mass_init_log_rotation_test"
base.SUPERSEDES_TEST_BUILD = "Patch_v2.6_VISUAL_TEST8"
base.SUPERSEDED_RESULT_FIELD = "test8_runtime_result"
base.SUPERSEDED_RUNTIME_RESULT = (
    "Mass Cure no longer crashed and all resurrection behavior remained valid, "
    "but the Cure cast line still appeared after the revival lines; the entry "
    "record hook at 0x005A1B30 did not produce an effective rotation start"
)


SINGLE_CURE_BLOCK_VA = test8.SINGLE_CURE_BLOCK_VA
MASS_CURE_BLOCK_VA = test8.MASS_CURE_BLOCK_VA
MASS_LOG_RECORD_HOOK_VA = 0x005A1B36
MASS_CURE_AFTER_RECORD_VA = 0x005A1B3B
MASS_CURE_END_VA = 0x005A1BFB
MASS_CURE_FALLTHROUGH_VA = test8.MASS_CURE_FALLTHROUGH_VA

MASS_HELPER_VA = test8.MASS_HELPER_VA
MASS_HELPER_END_VA = test8.MASS_HELPER_END_VA
SILENT_RESURRECT_ENTRY_VA = test8.SILENT_RESURRECT_ENTRY_VA
PRIMARY_CAVE_VA = test8.PRIMARY_CAVE_VA
PRIMARY_CAVE_LENGTH = test8.PRIMARY_CAVE_LENGTH
CURE_WRAPPER_VA = test8.CURE_WRAPPER_VA
RESOLVER_VA = test8.RESOLVER_VA

CURE_CORE_VA = test8.CURE_CORE_VA
CURE_CAST_LOG_VA = test8.CURE_CAST_LOG_VA
CURE_EFFECT_CHECK_VA = test8.CURE_EFFECT_CHECK_VA
GET_RESURRECTION_TARGET_VA = test8.GET_RESURRECTION_TARGET_VA
CALC_CURE_POWER_VA = test8.CALC_CURE_POWER_VA
COMBAT_LOG_REFRESH_VA = test8.COMBAT_LOG_REFRESH_VA

SINGLE_CURE_TEST4 = test8.SINGLE_CURE_TEST4
SINGLE_CURE_BASELINE = test8.SINGLE_CURE_BASELINE
MASS_CURE_TEST4 = test8.MASS_CURE_TEST4
MASS_CURE_BASELINE = test8.MASS_CURE_BASELINE
MASS_LOG_RECORD_EXPECTED = bytes.fromhex("b9 0a 00 00 00")
MASS_FALLTHROUGH_EXPECTED = test8.MASS_FALLTHROUGH_EXPECTED

test4_patch_visual_hooks = test8.test4_patch_visual_hooks
test4_build_visual_payloads = test8.test4_build_visual_payloads


def build_wrapper_and_record_helper() -> tuple[bytes, bytes, int, str, str]:
    wrapper, _, record_va, wrapper_source, _ = (
        test8.build_optimized_wrapper_and_record_helper()
    )
    record_source = """
record_mass_log_start:
    mov eax, dword ptr [ebx + 0x132fc]
    mov ecx, dword ptr [eax + 0x5c]
    sub ecx, dword ptr [eax + 0x58]
    mov dword ptr [ebp + 0x18], ecx
    mov ecx, 0x0a
    ret
"""
    record, _ = assemble(record_source, record_va)
    if len(wrapper) != 297 or len(record) != 21:
        raise RuntimeError("TEST9 primary helper size changed")
    if record_va + len(record) != 0x00639F0E:
        raise RuntimeError("TEST9 record helper must leave two padding bytes")
    return wrapper, record, record_va, wrapper_source, record_source


def build_secondary_cave() -> tuple[bytes, int, int, str, str]:
    helper_source = f"""
mass_corpse_helper:
    mov ecx, dword ptr [ebp - 0x14]
    jecxz helper_magic_return
    jmp hero_check
helper_magic_return:
    mov ecx, dword ptr [ebp + 0x10]
    pop eax
    push 0
    push eax
    ret
hero_check:
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
    jmp helper_magic_return
"""
    helper, _ = assemble(helper_source, MASS_HELPER_VA)
    if len(helper) != 155:
        raise RuntimeError(f"TEST9 corpse helper changed size: {len(helper)}")

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
    xchg dword ptr [esi], edx
    add esi, 4
    cmp esi, edi
    jbe shift_loop
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
    if len(reorder) != 49:
        raise RuntimeError(f"TEST9 log-rotation helper changed size: {len(reorder)}")
    combined = helper + reorder
    if MASS_HELPER_VA + len(combined) != MASS_HELPER_END_VA:
        raise RuntimeError("TEST9 secondary helpers must exactly end at 0x639CF5")

    instructions = test8.decode_instructions(helper, MASS_HELPER_VA)
    jecxz = next(instruction for instruction in instructions if instruction.mnemonic == "jecxz")
    expected_magic_return = MASS_HELPER_VA + 7
    if jecxz.operands[0].imm != expected_magic_return:
        raise RuntimeError(
            f"JECXZ target escaped helper: 0x{jecxz.operands[0].imm:08X}"
        )
    return combined, reorder_va, expected_magic_return, helper_source, reorder_source


def build_visual_payloads_for_test9() -> tuple[list[tuple[int, bytes]], dict[str, Any], dict[str, int]]:
    regions, metadata, addresses = test4_build_visual_payloads()
    metadata = json.loads(json.dumps(metadata))
    addresses = dict(addresses)
    wrapper, record, record_va, wrapper_source, record_source = (
        build_wrapper_and_record_helper()
    )
    secondary, reorder_va, magic_return_va, helper_source, reorder_source = (
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
                "name": "mass_log_reorder_tail",
                "va": reorder_va,
                "size": 49,
                "end_exclusive_va": reorder_va + 49,
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
    metadata["test9_final_secondary_payload_hex"] = secondary.hex(" ")
    addresses.update(
        mass_log_reorder_tail=reorder_va,
        mass_log_record_start=record_va,
        mass_helper_magic_return=magic_return_va,
    )
    return regions, metadata, addresses


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

    single = test8.test7.build_single_block()
    secondary_prefix, reorder_va, magic_return_va, _, _ = build_secondary_cave()
    wrapper, record, record_va, _, _ = build_wrapper_and_record_helper()

    primary = bytearray(test4_primary)
    wrapper_offset = CURE_WRAPPER_VA - PRIMARY_CAVE_VA
    resolver_offset = RESOLVER_VA - PRIMARY_CAVE_VA
    primary[wrapper_offset:resolver_offset] = wrapper + record + b"\x90\x90"
    primary = bytes(primary)
    secondary = secondary_prefix + test4_secondary[len(secondary_prefix) :]

    record_hook = relative_branch(MASS_LOG_RECORD_HOOK_VA, record_va, 0xE8)
    reorder_hook = relative_branch(MASS_CURE_FALLTHROUGH_VA, reorder_va, 0xE8)
    replacements = {
        SINGLE_CURE_BLOCK_VA: single,
        MASS_LOG_RECORD_HOOK_VA: record_hook,
        MASS_CURE_FALLTHROUGH_VA: reorder_hook,
        MASS_HELPER_VA: secondary,
        PRIMARY_CAVE_VA: primary,
    }
    expected = {
        SINGLE_CURE_BLOCK_VA: SINGLE_CURE_TEST4,
        MASS_LOG_RECORD_HOOK_VA: MASS_LOG_RECORD_EXPECTED,
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

    mass_offset = va_to_offset(pe, MASS_CURE_BLOCK_VA)
    entry_expected = MASS_CURE_TEST4[:6]
    if final[mass_offset : mass_offset + 6] != entry_expected:
        raise RuntimeError("TEST9 must restore TEST4 bytes at 0x005A1B30")
    after_record_offset = va_to_offset(pe, MASS_CURE_AFTER_RECORD_VA)
    after_record_length = MASS_CURE_END_VA - MASS_CURE_AFTER_RECORD_VA
    test4_after_record = test4_bytes[
        after_record_offset : after_record_offset + after_record_length
    ]
    if final[after_record_offset : after_record_offset + after_record_length] != test4_after_record:
        raise RuntimeError("TEST9 changed TEST4 mass bytes after the fixed hook")

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
        (MASS_LOG_RECORD_HOOK_VA, record_hook, record_va),
        (MASS_CURE_FALLTHROUGH_VA, reorder_hook, reorder_va),
    ):
        instruction = test8.decode_instructions(payload, address)[0]
        if instruction.mnemonic != "call" or instruction.operands[0].imm != target:
            raise RuntimeError(f"TEST9 trampoline target mismatch at 0x{address:08X}")
        hook_targets[f"0x{address:08X}"] = target

    mass_calls = direct_call_targets(
        test8.decode_instructions(
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
        raise RuntimeError("TEST9 mass call sequence changed")

    helper_calls = direct_call_targets(
        test8.decode_instructions(secondary_prefix, MASS_HELPER_VA)
    )
    if helper_calls != [
        GET_RESURRECTION_TARGET_VA,
        CALC_CURE_POWER_VA,
        SILENT_RESURRECT_ENTRY_VA,
        COMBAT_LOG_REFRESH_VA,
    ]:
        raise RuntimeError("TEST9 secondary helper call sequence changed")

    wrapper_calls = direct_call_targets(test8.decode_instructions(wrapper, CURE_WRAPPER_VA))
    if wrapper_calls != [
        CURE_CORE_VA,
        GET_RESURRECTION_TARGET_VA,
        SILENT_RESURRECT_ENTRY_VA,
        GET_RESURRECTION_TARGET_VA,
        CALC_CURE_POWER_VA,
    ]:
        raise RuntimeError("TEST9 optimized wrapper call sequence changed")

    single_calls = direct_call_targets(test8.decode_instructions(single, SINGLE_CURE_BLOCK_VA))
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
            region["label"] = "Stage 4 TEST9 compact corpse/log helper payload"
            region["patched_hex"] = secondary.hex(" ")
        elif region["va"] == PRIMARY_CAVE_VA and region["length"] == len(primary):
            region["label"] = "Stage 4 TEST9 Cure wrapper and mandatory-init log payload"
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
                "Stage 4 TEST9 accepted single-Cure log-order block",
                SINGLE_CURE_BLOCK_VA,
                single,
                SINGLE_CURE_BASELINE,
            ),
            new_region(
                "Stage 4 TEST9 mandatory mass-table-init log record hook",
                MASS_LOG_RECORD_HOOK_VA,
                record_hook,
                MASS_LOG_RECORD_EXPECTED,
            ),
            new_region(
                "Stage 4 TEST9 post-formatter log-rotation trampoline",
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
        raise RuntimeError(f"Combined TEST9 rollback failed for {path.name}")

    path.write_bytes(final)
    report = dict(test4_report)
    report["test4_intermediate_sha256"] = report["output_sha256"]
    report["output_sha256"] = sha256_bytes(final)
    report["logical_patch_regions"] = regions
    report["exact_contiguous_differences"] = contiguous_differences(bytes(rollback), final)
    report["test8_runtime_result"] = base.SUPERSEDED_RUNTIME_RESULT
    report["test8_mass_crash_fixed"] = True
    report["test8_log_rotation_observed_effective"] = False
    report["mass_test4_entry_restored_sha256"] = sha256(entry_expected).hexdigest()
    report["mass_test4_bytes_preserved_after_record_hook_sha256"] = sha256(
        test4_after_record
    ).hexdigest()
    report["mass_log_record_hook_va"] = MASS_LOG_RECORD_HOOK_VA
    report["mass_log_record_hook_replays_original_ecx_count"] = True
    report["mass_log_rotation_uses_forward_pointer_swaps"] = True
    report["mass_helper_jecxz_target_va"] = magic_return_va
    report["mass_helper_jecxz_target_within_payload"] = True
    report["mass_cast_log_runs_at_original_test4_address_and_timing"] = True
    report["combat_log_string_objects_not_copied_or_duplicated"] = True
    report["ordinary_resurrection_log_path_untouched"] = True
    report["decoded_test9_hook_targets"] = hook_targets
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

状态：**TEST8 日志顺序修正版；仍是测试包，不替换 `Download/Patch_v2.5.zip`。**

TEST8 已确认群体治愈复活不再崩溃，但战斗日志仍是“先起死回生、后施放治愈”。这说明 TEST8 放在群体入口 `0x005A1B30` 的施法前日志长度记录没有形成有效的轮转起点。

TEST9 只调整日志辅助逻辑：

1. `0x005A1B30–0x005A1B35` 恢复为 TEST4 原始指令；
2. 把 5 字节记录跳板移到必经的群体表清空计数指令 `0x005A1B36`，辅助函数记录日志长度后重放原来的 `MOV ECX,10`；
3. `0x005A1B3B–0x005A1BFA` 继续与 TEST4 逐字节一致，所有后续地址不移动；
4. 施法记录返回后仍只轮转本次新增的日志指针，不复制、释放或重建字符串；
5. 同时修正 TEST8 尸体辅助函数中越出代码洞的 `JECXZ` 短跳目标，空英雄指针分支现在落在代码洞内部的安全返回块。

## 安装

1. 覆盖到**干净 HotA 1.8.0**；不要叠加 TEST8 或其他补丁。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 先启动 `h3hota HD.exe` 到主菜单，再进入战斗。

## 本轮只需测试

1. 高级水系群体治愈同时复活至少两队尸体，确认不崩溃。
2. 查看战斗日志：应先显示“英雄施放治愈”，随后显示各队“起死回生”。
3. 顺带确认复活数量、起身/站立显示和战后永久保留未变化。
4. 单体治愈无需重复完整门禁，只需确认仍是“先治愈、后复活”。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    executable = report["executables"][0]
    return f"""# Stage 4 TEST9：把日志起点记录移到群体表清空必经指令

状态：**静态构建、双版本地址/短跳目标、完整回滚与 ZIP CRC 已验证；等待实机日志顺序门禁。**

## TEST8 实机结论

- 群体治愈复活不再崩溃，证明恢复 TEST4 的群体指令地址布局是正确方向。
- 单体日志顺序继续正确。
- 群体日志顺序仍未改变，说明 `0x005A1B30` 的入口记录跳板在 HotA/HD 实际路径中没有形成有效起点；尾部轮转因此直接跳过。

## TEST9 改动

- 恢复 `0x005A1B30` 的 TEST4 原始 `LEA EDI,[EBX+0x547C]`。
- 在必经的 `0x005A1B36` 用同长度 5 字节 `CALL` 记录 `[log+0x5C]-[log+0x58]`，辅助函数随后重放原 `MOV ECX,10`；返回地址仍为 `0x005A1B3B`。
- `0x005A1B3B–0x005A1BFA` 保持 TEST4 原字节，哈希为 `{executable['mass_test4_bytes_preserved_after_record_hook_sha256']}`。
- 尾部以 `XCHG` 从前向后交换指针，实现“最后的治愈施法行移到本次新增范围首位”；字符串对象及所有权不变。
- TEST8 的 `JECXZ` 被 Keystone 错误截断为洞外地址 `0x00639BB5`。TEST9 将安全返回块移到近距离，静态解码目标固定为 `0x{executable['mass_helper_jecxz_target_va']:08X}`，随后再进入原尸体扫描。

## 保持不变

- TEST4 已通过的复活数量、永久性、亡灵/重叠/占位规则、起身动画、治愈音效和复活圆圈/音效隔离。
- 单体治愈已通过的日志前移路径。
- 原版 `0x005A8C60` 群体施法记录的地址、参数和运行时点。
- `0x00639CF5` 静音复活入口、`0x00639F10` 后的 Stage 3 辅助函数及普通转世重生路径。
- 正式版 `Download/Patch_v2.5.zip`。

ZIP SHA-256：`{report['zip_sha256']}`
"""


base.build_visual_payloads = build_visual_payloads_for_test9
base.patch_visual_hooks = patch_visual_hooks
base.instructions = instructions
base.research_markdown = research_markdown


if __name__ == "__main__":
    raise SystemExit(base.main())
