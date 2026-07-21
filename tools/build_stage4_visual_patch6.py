#!/usr/bin/env python3
"""Build the sixth Cure-resurrection presentation test on Patch_v1.8.

TEST5 moved the full mass-Cure message routine before the affected-stack table
was initialized. The stock mass path passes a null explicit target and relies
on that table, so HotA 1.8 could dereference invalid target state. TEST6 uses a
two-phase mass path: validate and mark targets, append the Cure cast message,
then apply Cure/resurrection. The single-target TEST5 ordering remains valid.
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
BUILD_NAME = "Patch_v2.6_VISUAL_TEST6"

base.BUILD_NAME = BUILD_NAME
base.BUILD_SCOPE = "stage4_safe_two_phase_mass_cure_log_order_test"
base.SUPERSEDES_TEST_BUILD = "Patch_v2.6_VISUAL_TEST5"
base.SUPERSEDED_RESULT_FIELD = "test5_runtime_result"
base.SUPERSEDED_RUNTIME_RESULT = (
    "Single Cure passed, but mass Cure crashed at HotA.dll+0x38060 because "
    "the full mass message routine ran before its affected-stack table existed"
)


SINGLE_CURE_BLOCK_VA = 0x005A1AFA
MASS_CURE_BLOCK_VA = 0x005A1B30
MASS_CURE_FALLTHROUGH_VA = 0x005A1BFB
MASS_HELPER_VA = 0x00639C29
MASS_HELPER_END_VA = 0x00639CF5
SILENT_RESURRECT_ENTRY_VA = 0x00639CF5
CURE_CAST_LOG_VA = 0x005A8C60
CURE_EFFECT_CHECK_VA = 0x005A83A0
GET_RESURRECTION_TARGET_VA = 0x005A3FD0
CALC_CURE_POWER_VA = 0x00639D80
CURE_WRAPPER_VA = 0x00639DD0

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
        raise RuntimeError("TEST6 single-Cure block changed size")
    return code


def build_mass_blocks() -> tuple[bytes, bytes, int]:
    prefix_source = f"""
        lea edi, [ebx + 0x547c]
        push 0x0a
        pop ecx
        xor eax, eax
        rep stosd
        mov edx, dword ptr [ebx + 0x132c0]
        mov dword ptr [ebp + 0x14], eax
        mov eax, dword ptr [ebx + edx * 4 + 0x54bc]
        test eax, eax
        jle mass_dead_premark
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
    mass_dead_premark:
        xor eax, eax
        call {MASS_HELPER_VA:#x}
        mov ecx, dword ptr [ebp + 0x10]
        push 0
        push 0x25
        push ecx
        mov ecx, ebx
        call {CURE_CAST_LOG_VA:#x}
        push 1
        pop eax
        call {MASS_HELPER_VA:#x}
        jmp {MASS_CURE_FALLTHROUGH_VA:#x}
    """
    prefix, _ = assemble(prefix_source, MASS_CURE_BLOCK_VA)
    fragment_va = MASS_CURE_BLOCK_VA + len(prefix)
    fragment_source = f"""
    living_apply_fragment:
        push dword ptr [ebp - 0x14]
        push dword ptr [ebp + 0x1c]
        push esi
        mov ecx, edi
        call {CURE_WRAPPER_VA:#x}
        ret
    """
    fragment, _ = assemble(fragment_source, fragment_va)
    mass_code = prefix + fragment
    if len(mass_code) > len(MASS_CURE_TEST4):
        raise RuntimeError("TEST6 mass-Cure block exceeds its fixed-size range")
    mass_code += b"\x90" * (len(MASS_CURE_TEST4) - len(mass_code))

    helper_source = f"""
    two_phase_mass_helper:
        push edi
        mov dword ptr [ebp + 0x18], eax
        and dword ptr [ebp + 0x14], 0
    stack_loop:
        mov edx, dword ptr [ebx + 0x132c0]
        mov eax, dword ptr [ebp + 0x14]
        cmp eax, dword ptr [ebx + edx * 4 + 0x54bc]
        jge helper_done
        imul eax, edx, 0x15
        add eax, dword ptr [ebp + 0x14]
        imul eax, eax, 0x548
        lea edi, [ebx + eax + 0x54cc]
        cmp dword ptr [edi + 0x4c], 0
        je dead_stack
    living_stack:
        cmp dword ptr [ebp + 0x18], 0
        je stack_next
        imul eax, edx, 0x14
        add eax, dword ptr [ebp + 0x14]
        cmp byte ptr [ebx + eax + 0x547c], 0
        je stack_next
        call {fragment_va:#x}
        jmp stack_next
    dead_stack:
        mov eax, dword ptr [ebp - 0x14]
        test eax, eax
        jz stack_next
        mov eax, dword ptr [eax + 0x1a]
        cmp eax, 0x19
        je dead_specialist
        cmp eax, 0xaa
        jne stack_next
    dead_specialist:
        cmp dword ptr [edi + 0x60], 0
        jle stack_next
        push 0
        push dword ptr [edi + 0x38]
        push edx
        mov ecx, ebx
        call {GET_RESURRECTION_TARGET_VA:#x}
        cmp eax, edi
        jne stack_next
        cmp dword ptr [ebp + 0x18], 0
        jne dead_apply
        jmp mark_affected
    dead_apply:
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
    mark_affected:
        mov eax, dword ptr [ebx + 0x132c0]
        imul eax, eax, 0x14
        add eax, dword ptr [ebp + 0x14]
        mov byte ptr [ebx + eax + 0x547c], 1
    stack_next:
        inc dword ptr [ebp + 0x14]
        jmp stack_loop
    helper_done:
        pop edi
        ret
    """
    helper, _ = assemble(helper_source, MASS_HELPER_VA)
    if len(helper) > len(MASS_HELPER_TEST4):
        raise RuntimeError("TEST6 two-phase helper exceeds the validated cave")
    helper += b"\x90" * (len(MASS_HELPER_TEST4) - len(helper))
    if MASS_HELPER_VA + len(helper) != MASS_HELPER_END_VA:
        raise RuntimeError("TEST6 helper must end at the silent-resurrection entry")
    return mass_code, helper, fragment_va


test4_patch_visual_hooks = base.patch_visual_hooks


def decode_instructions(code: bytes, address: int) -> list[Any]:
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    return list(decoder.disasm(code, address))


def direct_call_targets(instructions: list[Any]) -> list[int]:
    targets: list[int] = []
    for instruction in instructions:
        if (
            instruction.mnemonic == "call"
            and instruction.operands
            and instruction.operands[0].type == X86_OP_IMM
        ):
            targets.append(instruction.operands[0].imm)
    return targets


def patch_visual_hooks(path: Path, stage3_report: dict[str, Any]) -> dict[str, Any]:
    test4_report = test4_patch_visual_hooks(path, stage3_report)
    test4_bytes = path.read_bytes()
    pe = pefile.PE(data=test4_bytes, fast_load=False)
    mass_code, helper_code, fragment_va = build_mass_blocks()
    replacements = {
        SINGLE_CURE_BLOCK_VA: build_single_block(),
        MASS_CURE_BLOCK_VA: mass_code,
        MASS_HELPER_VA: helper_code,
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
            raise RuntimeError(f"TEST6 replacement length mismatch at 0x{address:08X}")
        patched[offset : offset + len(replacement)] = replacement
        regions.append(
            {
                "label": f"Stage 4 TEST6 block at 0x{address:08X}",
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

    single_instructions = decode_instructions(
        replacements[SINGLE_CURE_BLOCK_VA], SINGLE_CURE_BLOCK_VA
    )
    single_targets = direct_call_targets(single_instructions)
    if single_targets.index(CURE_CAST_LOG_VA) > single_targets.index(CURE_WRAPPER_VA):
        raise RuntimeError("Single Cure cast log does not precede CureCore")

    mass_instructions = decode_instructions(replacements[MASS_CURE_BLOCK_VA], MASS_CURE_BLOCK_VA)
    mass_targets = direct_call_targets(mass_instructions)
    helper_positions = [i for i, target in enumerate(mass_targets) if target == MASS_HELPER_VA]
    if len(helper_positions) != 2:
        raise RuntimeError("TEST6 mass block must call its helper exactly twice")
    log_position = mass_targets.index(CURE_CAST_LOG_VA)
    wrapper_position = mass_targets.index(CURE_WRAPPER_VA)
    if not helper_positions[0] < log_position < helper_positions[1] < wrapper_position:
        raise RuntimeError("TEST6 two-phase mass call ordering verification failed")

    helper_instructions = decode_instructions(replacements[MASS_HELPER_VA], MASS_HELPER_VA)
    helper_targets = direct_call_targets(helper_instructions)
    for target in (
        fragment_va,
        GET_RESURRECTION_TARGET_VA,
        CALC_CURE_POWER_VA,
        SILENT_RESURRECT_ENTRY_VA,
    ):
        if target not in helper_targets:
            raise RuntimeError(f"TEST6 helper is missing call target 0x{target:08X}")

    final = bytes(patched)
    replacement_ranges = tuple(
        (address, address + len(payload)) for address, payload in replacements.items()
    )

    def overlaps_replacement(region: dict[str, Any]) -> bool:
        start = region["va"]
        end = start + region["length"]
        return any(start < block_end and end > block_start for block_start, block_end in replacement_ranges)

    nonoverlapping_test4_regions = [
        region
        for region in test4_report["logical_patch_regions"]
        if not overlaps_replacement(region)
    ]
    all_regions = nonoverlapping_test4_regions + regions
    rollback = bytearray(final)
    for region in all_regions:
        start = region["file_offset"]
        rollback[start : start + region["length"]] = bytes.fromhex(region["rollback_hex"])
    if sha256_bytes(bytes(rollback)) != test4_report["input_sha256"]:
        raise RuntimeError(f"Combined TEST6 rollback failed for {path.name}")

    path.write_bytes(final)
    report = dict(test4_report)
    report["test4_intermediate_sha256"] = report["output_sha256"]
    report["output_sha256"] = sha256_bytes(final)
    report["logical_patch_regions"] = all_regions
    report["exact_contiguous_differences"] = contiguous_differences(bytes(rollback), final)
    report["cure_cast_log_moved_before_effects"] = True
    report["mass_affected_table_initialized_before_cast_log"] = True
    report["mass_dead_targets_premarked_with_native_validation"] = True
    report["mass_cure_two_phase_apply"] = True
    report["ordinary_resurrection_log_path_untouched"] = True
    report["mass_living_apply_fragment_va"] = fragment_va
    report["decoded_cure_log_order"] = {
        "single_call_targets": single_targets,
        "mass_call_targets": mass_targets,
        "helper_call_targets": helper_targets,
        "mass_premark_before_log_before_apply": True,
    }
    report["rollback_reconstructs_input"] = True
    return report


def instructions(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 测试说明

状态：**TEST5 群体崩溃修正版，不替换 `Download/Patch_v2.5.zip`。**

TEST5 单体治愈正常，但群体治愈在 `HotA.dll+0x38060` 崩溃。原因是群体施法日志使用空显式目标，必须等受影响兵队表建立后才能调用；TEST5 把完整日志函数移到了该表初始化之前。

TEST6 改为两阶段群体处理：

1. 先执行原版资格检查，并使用原生尸体解析预先标记所有合法目标；
2. 在目标表完整后写入“英雄施放治愈”；
3. 再对已标记活体执行治愈，并对合法尸体执行永久复活。

因此预期仍是先显示施法日志，再显示各队“起死回生”，同时不再向 HotA 提供未初始化的群体目标状态。

## 安装

1. 覆盖到干净 HotA 1.8.0，不要叠加 TEST5 或其他旧补丁。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 先启动 `h3hota HD.exe` 到主菜单，再进行战斗测试。

## 必测

1. 高级水系群体治愈同时复活至少两队全灭尸体：不崩溃；先显示施放治愈，再显示各队起死回生。
2. 群体治愈同时包含受伤存活兵队和全灭尸体：治疗与复活数量正确，日志顺序正确。
3. 单体治愈复活全灭尸体：保持 TEST5 已通过结果。
4. 治愈动画/音效、逐队起身、最终站立状态、战后永久保留、亡灵/重叠/占格规则保持 TEST4 结果。
5. 普通转世重生的日志、圆圈、音效和起身动作保持原版。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    return f"""# Stage 4 TEST6：安全的两阶段群体治愈日志

状态：**静态构建与回滚验证完成，等待实机门禁。**

## TEST5 崩溃证据

- 单体治愈正常；群体治愈崩溃。
- 异常：`EXCEPTION_ACCESS_VIOLATION`，读取 `0x5866AAE7`。
- 地址：`HotA.dll+0x38060`。
- TEST5 在清空/建立 `[battle+0x547C]` 受影响兵队表之前，以空显式目标调用完整群体日志函数 `0x005A8C60`。

## TEST6 设计

- 第一阶段只复用原版 `0x005A83A0` 资格检查并标记活体；尸体继续通过原生 `GetResurrectionTarget` 验证后标记。
- 目标表完整后调用原版 `0x005A8C60`，其参数与原群体路径一致。
- 第二阶段仅对已标记活体调用 Cure 包装器，对已标记且再次通过原生解析的尸体计算治愈量并调用永久复活。
- 继续使用 TEST4 的静音起身入口、动画/音效隔离和 `temporary=0`。
- 普通转世重生和全局日志器不修改。

## 静态门禁

- 构建输入必须精确匹配 TEST4 的单体块、群体块和原群体尸体辅助函数。
- 群体调用序列必须为：资格检查 → 预标记辅助函数 → 施法日志 → 应用辅助函数 → Cure 包装器。
- 新辅助函数必须精确结束在 `0x00639CF5`，不得覆盖 TEST4 静音复活入口。
- 标准版/HD 版分别执行完整回滚、PE 尺寸、`MainProc`、非 EXE 哈希和 ZIP CRC 检查。

ZIP SHA-256：`{report['zip_sha256']}`
"""


base.patch_visual_hooks = patch_visual_hooks
base.instructions = instructions
base.research_markdown = research_markdown


if __name__ == "__main__":
    raise SystemExit(base.main())
