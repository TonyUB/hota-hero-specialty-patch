#!/usr/bin/env python3
"""Build the seventh Cure-resurrection presentation test on Patch_v1.8.

TEST6 split each mass-Cure target's validation from its application. HotA 1.8
keeps hidden per-target state across those two operations, so the split crashed
immediately after the native effect check returned. TEST7 restores the accepted
TEST4 target-by-target settlement order exactly at the semantic level. It records
the combat-log vector length before settlement and, only after the stock Cure
formatter appends its final cast line, rotates that last pointer in front of the
new effect lines and refreshes the existing log view.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

import capstone
import pefile
from capstone.x86_const import X86_OP_IMM

import build_stage4_visual_patch4 as test4
from build_diag_patch import contiguous_differences, sha256_bytes, va_to_offset
from build_stage3_patch import assemble


base = test4.base
BUILD_NAME = "Patch_v2.6_VISUAL_TEST7"

base.BUILD_NAME = BUILD_NAME
base.BUILD_SCOPE = "stage4_post_settlement_cure_log_pointer_rotation_test"
base.SUPERSEDES_TEST_BUILD = "Patch_v2.6_VISUAL_TEST6"
base.SUPERSEDED_RESULT_FIELD = "test6_runtime_result"
base.SUPERSEDED_RUNTIME_RESULT = (
    "Mass Cure still crashed: the return address 0x005A1B82 shows that HotA "
    "requires each native effect check to be followed immediately by its "
    "target settlement; TEST6's two-phase split violated that hidden state"
)


SINGLE_CURE_BLOCK_VA = 0x005A1AFA
MASS_CURE_BLOCK_VA = 0x005A1B30
MASS_CURE_FALLTHROUGH_VA = 0x005A1BFB
COMMON_POST_SPELL_VA = 0x005A2368
MASS_HELPER_VA = 0x00639C29
MASS_HELPER_END_VA = 0x00639CF5
SILENT_RESURRECT_ENTRY_VA = 0x00639CF5

CURE_CAST_LOG_VA = 0x005A8C60
CURE_EFFECT_CHECK_VA = 0x005A83A0
CURE_WRAPPER_VA = 0x00639DD0
GET_RESURRECTION_TARGET_VA = 0x005A3FD0
CALC_CURE_POWER_VA = 0x00639D80
COMBAT_LOG_REFRESH_VA = 0x00472770


SINGLE_CURE_TEST4 = bytes.fromhex(
    "8b55ec8b451c5250568bcfe8c68209008b4df06a006a64578b51088bcb52"
    "e8a348efff8b4510576a25508bcbe835710000e938080000"
)
MASS_CURE_TEST4 = bytes.fromhex(
    "8dbb7c540000b90a00000033c0f3ab8b93c03201008945148b8493bc54000085c00f8e950000008b4d148d04d5000000002bc28d0c4103c18d0cc5000000002bc88d0c498d04c88dbcc3cc5400008b84c35457000085c075478b4d10516a016a0057526a258bcbe804680000dc1d38ac6300dfe0f6c44175278b55ec8b451c5250568bcfe8178209008b83c03201008b55148d0c808d048ac684187c540000018b93c03201008b4514408b8c93bc5400008945143bc10f8c6bffffffe8388009006a25518bcbe865700000"
)
MASS_HELPER_TEST4 = bytes.fromhex(
    "5589e583ec105356578b45008b40ec8945fc85c00f84a40000008b401a83f819740b3daa0000000f85910000008b83c03201008945f88b8c83bc540000894df0c745f4000000008b45f43b45f07d6f8b55f86bd21501c269d2480500008dbc13cc540000837f4c00754f837f60007e496a00ff7738ff75f889d9b8d03f5a00ffd039f87534ff75fc8b5500ff721c5657b8809d6300ffd085c07e1e6a00505789d9baf59c6300ffd28b45f86bc0140345f4c684037c54000001ff45f4eb895f5e5b89ec5d8b4d10586a0050c3"
)
SILENT_RESURRECT_ENTRY_TEST4 = bytes.fromhex("fe057f9d6300e970dbf6ff")
MASS_FALLTHROUGH_EXPECTED = bytes.fromhex(
    "8b55f06a008bcb8b4208508d837c54000050e8be4e0000e951070000"
)
COMMON_POST_SPELL_REINITIALIZATION_EXPECTED = bytes.fromhex(
    "8dbbd45400008d93bc540000c745140200000083ceff"
)

SINGLE_CURE_BASELINE = bytes.fromhex(
    "8b55ec8b451c5250568bcfe81647eaff8b4df06a006a64578b51088bcb52"
    "e8a348efff8b4510576a25508bcbe835710000e938080000"
)
MASS_CURE_BASELINE = bytes.fromhex(
    "8dbb7c540000b90a00000033c0f3ab8b93c03201008945148b8493bc54000085c00f8e950000008b4d148d04d5000000002bc28d0c4103c18d0cc5000000002bc88d0c498d04c88dbcc3cc5400008b84c35457000085c075478b4d10516a016a0057526a258bcbe804680000dc1d38ac6300dfe0f6c44175278b55ec8b451c5250568bcfe86746eaff8b83c03201008b55148d0c808d048ac684187c540000018b93c03201008b4514408b8c93bc5400008945143bc10f8c6bffffff8b4d106a006a25518bcbe865700000"
)

EXPECTED_HASHES = {
    SINGLE_CURE_BLOCK_VA: "b39e193620a41d686a424040e7676f62892075eedf4a8ed9f51048615ccb8dc6",
    MASS_CURE_BLOCK_VA: "2ddb96d78b0d95de9ed7b876f6052e978e6c34c1c88a4f9965145878a9428c87",
    MASS_HELPER_VA: "2eb5c3cbd1b5ca4669bb93cad2171bd73a5c4caa8ae067eb874943f885a9a88e",
}


def build_single_block() -> bytes:
    """Keep TEST5's already runtime-accepted single-target ordering."""

    source = f"""
        mov eax, dword ptr [ebp + 0x10]
        push edi
        push 0x25
        push eax
        mov ecx, ebx
        call {CURE_CAST_LOG_VA:#x}
        mov edx, dword ptr [ebp - 0x14]
        mov eax, dword ptr [ebp + 0x1c]
        push edx
        push eax
        push esi
        mov ecx, edi
        call {CURE_WRAPPER_VA:#x}
        mov ecx, dword ptr [ebp - 0x10]
        push 0
        push 0x64
        push edi
        mov edx, dword ptr [ecx + 8]
        mov ecx, ebx
        push edx
        call 0x004963c0
        jmp 0x005a2368
    """
    code, _ = assemble(source, SINGLE_CURE_BLOCK_VA)
    if len(code) != len(SINGLE_CURE_TEST4):
        raise RuntimeError("TEST7 single-Cure block changed size")
    return code


def build_secondary_cave() -> tuple[bytes, int]:
    """Fit the corpse scan and post-settlement log rotation before 0x639CF5."""

    helper_source = f"""
    mass_corpse_helper:
        mov eax, dword ptr [ebp - 0x14]
        test eax, eax
        jz helper_magic_return
        mov eax, dword ptr [eax + 0x1a]
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
    reorder_va = MASS_HELPER_VA + len(helper)

    reorder_source = f"""
    reorder_new_log_entries:
        mov ecx, dword ptr [ebx + 0x132fc]
        mov esi, dword ptr [ecx + 0x58]
        mov eax, dword ptr [ebp + 0x18]
        lea esi, [esi + eax * 4]
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
        ret
    """
    reorder, _ = assemble(reorder_source, reorder_va)
    combined = helper + reorder
    if len(helper) != 154:
        raise RuntimeError(f"TEST7 compact corpse helper changed size: {len(helper)}")
    if len(reorder) != 50:
        raise RuntimeError(f"TEST7 log-rotation helper changed size: {len(reorder)}")
    if reorder_va != 0x00639CC3:
        raise RuntimeError(f"Unexpected TEST7 log-rotation address: 0x{reorder_va:08X}")
    if MASS_HELPER_VA + len(combined) != MASS_HELPER_END_VA:
        raise RuntimeError("TEST7 helpers must end exactly at the silent-resurrection entry")
    return combined, reorder_va


def build_mass_block(reorder_va: int) -> bytes:
    """Preserve immediate check -> apply ordering, then rotate completed logs."""

    source = f"""
        mov eax, dword ptr [ebx + 0x132fc]
        mov ecx, dword ptr [eax + 0x58]
        mov eax, dword ptr [eax + 0x5c]
        sub eax, ecx
        sar eax, 2
        mov dword ptr [ebp + 0x18], eax
        lea edi, [ebx + 0x547c]
        push 0x0a
        pop ecx
        xor eax, eax
        rep stosd
        mov edx, dword ptr [ebx + 0x132c0]
        mov dword ptr [ebp + 0x14], eax
        mov eax, dword ptr [ebx + edx * 4 + 0x54bc]
        test eax, eax
        jle mass_done
    mass_loop:
        imul eax, edx, 0x15
        add eax, dword ptr [ebp + 0x14]
        imul eax, eax, 0x548
        lea edi, [ebx + eax + 0x54cc]
        mov eax, dword ptr [ebx + eax + 0x5754]
        test eax, eax
        jne mass_next
        mov ecx, dword ptr [ebp + 0x10]
        push ecx
        push 1
        push 0
        push edi
        push edx
        push 0x25
        mov ecx, ebx
        call {CURE_EFFECT_CHECK_VA:#x}
        fcomp qword ptr [0x0063ac38]
        fnstsw ax
        test ah, 0x41
        jne mass_next
        push dword ptr [ebp - 0x14]
        push dword ptr [ebp + 0x1c]
        push esi
        mov ecx, edi
        call {CURE_WRAPPER_VA:#x}
        mov eax, dword ptr [ebx + 0x132c0]
        mov edx, dword ptr [ebp + 0x14]
        lea ecx, [eax + eax * 4]
        lea eax, [edx + ecx * 4]
        mov byte ptr [eax + ebx + 0x547c], 1
    mass_next:
        mov edx, dword ptr [ebx + 0x132c0]
        mov eax, dword ptr [ebp + 0x14]
        inc eax
        mov ecx, dword ptr [ebx + edx * 4 + 0x54bc]
        mov dword ptr [ebp + 0x14], eax
        cmp eax, ecx
        jl mass_loop
    mass_done:
        call {MASS_HELPER_VA:#x}
        push 0x25
        push ecx
        mov ecx, ebx
        call {CURE_CAST_LOG_VA:#x}
        call {reorder_va:#x}
    """
    code, _ = assemble(source, MASS_CURE_BLOCK_VA)
    if len(code) > len(MASS_CURE_TEST4):
        raise RuntimeError("TEST7 mass-Cure block exceeds its fixed-size range")
    code += b"\x90" * (len(MASS_CURE_TEST4) - len(code))
    return code


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


test4_patch_visual_hooks = base.patch_visual_hooks


def patch_visual_hooks(path: Path, stage3_report: dict[str, Any]) -> dict[str, Any]:
    test4_report = test4_patch_visual_hooks(path, stage3_report)
    test4_bytes = path.read_bytes()
    pe = pefile.PE(data=test4_bytes, fast_load=False)

    cave_code, reorder_va = build_secondary_cave()
    replacements = {
        SINGLE_CURE_BLOCK_VA: build_single_block(),
        MASS_CURE_BLOCK_VA: build_mass_block(reorder_va),
        MASS_HELPER_VA: cave_code,
    }
    expected = {
        SINGLE_CURE_BLOCK_VA: SINGLE_CURE_TEST4,
        MASS_CURE_BLOCK_VA: MASS_CURE_TEST4,
        MASS_HELPER_VA: MASS_HELPER_TEST4,
    }
    baselines = {
        SINGLE_CURE_BLOCK_VA: SINGLE_CURE_BASELINE,
        MASS_CURE_BLOCK_VA: MASS_CURE_BASELINE,
        MASS_HELPER_VA: bytes(len(MASS_HELPER_TEST4)),
    }

    patched = bytearray(test4_bytes)
    regions: list[dict[str, Any]] = []
    for address, expected_bytes in expected.items():
        offset = va_to_offset(pe, address)
        actual = test4_bytes[offset : offset + len(expected_bytes)]
        if actual != expected_bytes:
            raise RuntimeError(
                f"Unexpected post-TEST4 bytes at 0x{address:08X}: {actual.hex(' ')}"
            )
        if sha256(actual).hexdigest() != EXPECTED_HASHES[address]:
            raise RuntimeError(f"Post-TEST4 block hash mismatch at 0x{address:08X}")
        replacement = replacements[address]
        if len(replacement) != len(expected_bytes):
            raise RuntimeError(f"TEST7 replacement length mismatch at 0x{address:08X}")
        patched[offset : offset + len(replacement)] = replacement
        regions.append(
            {
                "label": f"Stage 4 TEST7 block at 0x{address:08X}",
                "va": address,
                "file_offset": offset,
                "length": len(replacement),
                "original_hex": baselines[address].hex(" "),
                "patched_hex": replacement.hex(" "),
                "rollback_hex": baselines[address].hex(" "),
                "test4_intermediate_hex": expected_bytes.hex(" "),
            }
        )

    silent_offset = va_to_offset(pe, SILENT_RESURRECT_ENTRY_VA)
    silent_actual = test4_bytes[
        silent_offset : silent_offset + len(SILENT_RESURRECT_ENTRY_TEST4)
    ]
    if silent_actual != SILENT_RESURRECT_ENTRY_TEST4:
        raise RuntimeError("TEST4 silent-resurrection entry changed unexpectedly")
    regions.append(
        {
            "label": "Preserved TEST4 silent-resurrection entry",
            "va": SILENT_RESURRECT_ENTRY_VA,
            "file_offset": silent_offset,
            "length": len(SILENT_RESURRECT_ENTRY_TEST4),
            "original_hex": bytes(len(SILENT_RESURRECT_ENTRY_TEST4)).hex(" "),
            "patched_hex": SILENT_RESURRECT_ENTRY_TEST4.hex(" "),
            "rollback_hex": bytes(len(SILENT_RESURRECT_ENTRY_TEST4)).hex(" "),
        }
    )

    fallthrough_offset = va_to_offset(pe, MASS_CURE_FALLTHROUGH_VA)
    if test4_bytes[
        fallthrough_offset : fallthrough_offset + len(MASS_FALLTHROUGH_EXPECTED)
    ] != MASS_FALLTHROUGH_EXPECTED:
        raise RuntimeError("Mass-Cure fallthrough changed unexpectedly")
    common_offset = va_to_offset(pe, COMMON_POST_SPELL_VA)
    if test4_bytes[
        common_offset
        : common_offset + len(COMMON_POST_SPELL_REINITIALIZATION_EXPECTED)
    ] != COMMON_POST_SPELL_REINITIALIZATION_EXPECTED:
        raise RuntimeError("Post-spell EDI/ESI reinitialization changed unexpectedly")

    single_calls = direct_call_targets(
        decode_instructions(replacements[SINGLE_CURE_BLOCK_VA], SINGLE_CURE_BLOCK_VA)
    )
    if single_calls.index(CURE_CAST_LOG_VA) > single_calls.index(CURE_WRAPPER_VA):
        raise RuntimeError("Single Cure cast log no longer precedes its application")

    mass_calls = direct_call_targets(
        decode_instructions(replacements[MASS_CURE_BLOCK_VA], MASS_CURE_BLOCK_VA)
    )
    expected_mass_calls = [
        CURE_EFFECT_CHECK_VA,
        CURE_WRAPPER_VA,
        MASS_HELPER_VA,
        CURE_CAST_LOG_VA,
        reorder_va,
    ]
    if mass_calls != expected_mass_calls:
        raise RuntimeError(
            "TEST7 mass call order changed: "
            + ", ".join(f"0x{target:08X}" for target in mass_calls)
        )

    helper_instructions = decode_instructions(
        replacements[MASS_HELPER_VA], MASS_HELPER_VA
    )
    helper_calls = direct_call_targets(helper_instructions)
    if helper_calls != [
        GET_RESURRECTION_TARGET_VA,
        CALC_CURE_POWER_VA,
        SILENT_RESURRECT_ENTRY_VA,
        COMBAT_LOG_REFRESH_VA,
    ]:
        raise RuntimeError("TEST7 helper call sequence changed")

    final = bytes(patched)
    replacement_ranges = tuple(
        (address, address + len(payload)) for address, payload in replacements.items()
    )

    def overlaps_replacement(region: dict[str, Any]) -> bool:
        start = region["va"]
        end = start + region["length"]
        return any(
            start < block_end and end > block_start
            for block_start, block_end in replacement_ranges
        )

    nonoverlapping_test4_regions = [
        region
        for region in test4_report["logical_patch_regions"]
        if not overlaps_replacement(region)
    ]
    all_regions = nonoverlapping_test4_regions + regions
    rollback = bytearray(final)
    for region in all_regions:
        start = region["file_offset"]
        rollback[start : start + region["length"]] = bytes.fromhex(
            region["rollback_hex"]
        )
    if sha256_bytes(bytes(rollback)) != test4_report["input_sha256"]:
        raise RuntimeError(f"Combined TEST7 rollback failed for {path.name}")

    path.write_bytes(final)
    report = dict(test4_report)
    report["test4_intermediate_sha256"] = report["output_sha256"]
    report["output_sha256"] = sha256_bytes(final)
    report["logical_patch_regions"] = all_regions
    report["exact_contiguous_differences"] = contiguous_differences(
        bytes(rollback), final
    )
    report["mass_native_check_immediately_precedes_application"] = True
    report["mass_cure_two_phase_apply"] = False
    report["mass_log_count_saved_before_settlement"] = True
    report["mass_cast_log_runs_at_original_post_settlement_timing"] = True
    report["mass_new_log_pointer_range_rotated_after_settlement"] = True
    report["combat_log_string_objects_not_copied_or_duplicated"] = True
    report["mass_log_rotation_clobbered_registers_dead_until_reinitialized"] = True
    report["ordinary_resurrection_log_path_untouched"] = True
    report["mass_log_rotation_helper_va"] = reorder_va
    report["decoded_cure_log_order"] = {
        "single_call_targets": single_calls,
        "mass_call_targets": mass_calls,
        "helper_call_targets": helper_calls,
        "mass_check_then_apply_before_cast_log_then_rotate": True,
    }
    report["rollback_reconstructs_input"] = True
    return report


def instructions(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 测试说明

状态：**TEST6 群体崩溃修正版；仍是测试包，不替换 `Download/Patch_v2.5.zip`。**

TEST6 把群体治愈拆成“先检查全部目标、再统一结算”，但 HotA 1.8.0 的效果检查会保存只供紧接着的本目标结算使用的内部状态。新崩溃报告的返回地址 `0x005A1B82` 正位于该检查之后，证明两阶段拆分不可用。

TEST7 完全恢复 TEST4 已通过实机验证的逐队顺序：

1. 每个存活目标仍是“原生效果检查 → 立即治疗/溢出复活”；
2. 尸体仍按原来的原生尸体解析与永久复活顺序处理；
3. 全部结算完成后，原版函数在原来的时点写入“英雄施放治愈”；
4. 最后只轮转本次新增日志的指针，把施法行移到各效果行之前，再用原生日志刷新函数重绘。

没有提前调用群体日志函数，没有拆开检查与结算，也没有复制、释放或重建任何日志字符串。

## 安装

1. 覆盖到干净 HotA 1.8.0；不要叠加 TEST5、TEST6 或其他旧补丁。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 先启动 `h3hota HD.exe` 到主菜单，再进入战斗。

## 优先测试

1. 高级水系群体治愈同时复活至少两队尸体：确认不崩溃，数量、起身、站立姿势和战后永久保留均与 TEST4 一致。
2. 打开战斗日志：应先显示“英雄施放治愈”，随后显示各队“起死回生”。
3. 群体治愈同时包含受伤存活兵队和全灭尸体，确认治疗/复活均正常。
4. 单体治愈复活尸体应继续保持 TEST5 已通过的日志顺序。
5. 亡灵、重叠尸体、被占格尸体、普通转世重生，以及治愈/复活动画和音效隔离规则均应保持 TEST4 结果。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    return f"""# Stage 4 TEST7：结算后轮转战斗日志指针

状态：**静态构建、双版本调用顺序与完整回滚验证已完成，等待实机门禁。**

## TEST6 崩溃证据

- 群体治愈仍然崩溃，异常读取随机地址 `0xD1D7356B`。
- Call stack V2 的直接返回地址为 `0x005A1B82`，即 TEST6 调用原生 `0x005A83A0` 效果检查后的下一条指令。
- 结论：受影响兵队表完整并不足以保证安全；HotA 还要求每队检查后立即执行该队结算。TEST6 的两阶段设计已撤回。

## TEST7 设计

- 群体存活兵队恢复逐队“效果检查 → Cure 包装器 → 受影响标记”的连续顺序。
- 随后运行已通过 TEST4 门禁的尸体扫描与静音永久复活入口。
- 原版 `0x005A8C60` 仍在全部效果结算后调用，参数和运行时点不提前。
- 结算前保存 `[battle+0x132FC]` 日志向量的元素数量，而不是保存可能因扩容失效的裸指针。
- 原版施法行追加完成后，将日志向量中本次新增范围的最后一个指针轮转到范围首位；每个字符串对象仍恰好保留一个所有权指针。
- 最后以日志对象现有的显示索引调用原生 `0x00472770` 刷新界面。

## 静态门禁

- 标准版与 HD 版均从唯一可信 `Patch_v1.8` 独立重建。
- 群体直接调用序列固定为：`0x005A83A0 → 0x00639DD0 → 0x00639C29 → 0x005A8C60 → 0x00639CC3`。
- 辅助调用序列固定为：原生尸体解析 → 治愈量计算 → TEST4 静音永久复活入口 → 原生日志刷新。
- 第二代码洞仍精确结束于 `0x00639CF5`，不覆盖 TEST4 静音复活入口。
- 原生普通转世重生日志函数和全局日志追加函数均未 Hook。
- 每个 EXE 均完成原字节哈希、PE 尺寸、完整回滚、非 EXE 哈希与 ZIP CRC 检查。

ZIP SHA-256：`{report['zip_sha256']}`
"""


base.patch_visual_hooks = patch_visual_hooks
base.instructions = instructions
base.research_markdown = research_markdown


if __name__ == "__main__":
    raise SystemExit(base.main())
