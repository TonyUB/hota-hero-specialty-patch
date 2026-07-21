#!/usr/bin/env python3
"""Build the fifth Cure-resurrection presentation test on Patch_v1.8.

TEST4 passed all gameplay, animation, and sound gates. Its only remaining
presentation issue is combat-log ordering: native ResurrectTarget appends each
revival line while CureCore is still running, whereas the stock Cure branch
appends the hero cast line only after CureCore returns. TEST5 reorders the
existing fixed-size Cure blocks so their unchanged cast-log call runs before
the Cure calculations. No global logger, Resurrection path, or code cave is
changed.
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
BUILD_NAME = "Patch_v2.6_VISUAL_TEST5"

base.BUILD_NAME = BUILD_NAME
base.BUILD_SCOPE = "stage4_cure_cast_log_before_resurrection_lines_test"
base.SUPERSEDES_TEST_BUILD = "Patch_v2.6_VISUAL_TEST4"
base.SUPERSEDED_RESULT_FIELD = "test4_runtime_result"
base.SUPERSEDED_RUNTIME_RESULT = (
    "All gameplay, animation, sound, overlap, and occupancy gates passed; "
    "only native Cure combat-log ordering remained cosmetic"
)


SINGLE_CURE_BLOCK_VA = 0x005A1AFA
MASS_CURE_BLOCK_VA = 0x005A1B30
CURE_CAST_LOG_VA = 0x005A8C60
CURE_WRAPPER_VA = 0x00639DD0
MASS_CORPSE_HELPER_VA = 0x00639C29

# Exact post-TEST4 bytes. These are checked before reordering so TEST5 cannot
# silently build on any other executable state.
SINGLE_CURE_EXPECTED = bytes.fromhex(
    "8b55ec8b451c5250568bcfe8c68209008b4df06a006a64578b51088bcb52"
    "e8a348efff8b4510576a25508bcbe835710000e938080000"
)
MASS_CURE_EXPECTED = bytes.fromhex(
    "8dbb7c540000b90a00000033c0f3ab8b93c03201008945148b8493bc54000085c00f8e950000008b4d148d04d5000000002bc28d0c4103c18d0cc5000000002bc88d0c498d04c88dbcc3cc5400008b84c35457000085c075478b4d10516a016a0057526a258bcbe804680000dc1d38ac6300dfe0f6c44175278b55ec8b451c5250568bcfe8178209008b83c03201008b55148d0c808d048ac684187c540000018b93c03201008b4514408b8c93bc5400008945143bc10f8c6bffffffe8388009006a25518bcbe865700000"
)

SINGLE_CURE_EXPECTED_SHA256 = (
    "b39e193620a41d686a424040e7676f62892075eedf4a8ed9f51048615ccb8dc6"
)
MASS_CURE_EXPECTED_SHA256 = (
    "2ddb96d78b0d95de9ed7b876f6052e978e6c34c1c88a4f9965145878a9428c87"
)
SINGLE_CURE_BASELINE = bytes.fromhex(
    "8b55ec8b451c5250568bcfe81647eaff8b4df06a006a64578b51088bcb52"
    "e8a348efff8b4510576a25508bcbe835710000e938080000"
)
MASS_CURE_BASELINE = bytes.fromhex(
    "8dbb7c540000b90a00000033c0f3ab8b93c03201008945148b8493bc54000085c00f8e950000008b4d148d04d5000000002bc28d0c4103c18d0cc5000000002bc88d0c498d04c88dbcc3cc5400008b84c35457000085c075478b4d10516a016a0057526a258bcbe804680000dc1d38ac6300dfe0f6c44175278b55ec8b451c5250568bcfe86746eaff8b83c03201008b55148d0c808d048ac684187c540000018b93c03201008b4514408b8c93bc5400008945143bc10f8c6bffffff8b4d106a006a25518bcbe865700000"
)


def reordered_cure_blocks() -> dict[int, bytes]:
    for side in range(2):
        for slot in range(20):
            original_index = (((side * 7) * 3) + slot) * 0x548
            simplified_index = (side * 0x15 + slot) * 0x548
            if original_index != simplified_index:
                raise RuntimeError("Mass-Cure stack-index algebra mismatch")
    single_source = f"""
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
    mass_source = f"""
        mov ecx, dword ptr [ebp + 0x10]
        push 0
        push 0x25
        push ecx
        mov ecx, ebx
        call {CURE_CAST_LOG_VA:#x}
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
        call 0x005a83a0
        fcomp qword ptr [0x0063ac38]
        fnstsw ax
        test ah, 0x41
        jne mass_next
        mov edx, dword ptr [ebp - 0x14]
        mov eax, dword ptr [ebp + 0x1c]
        push edx
        push eax
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
        call {MASS_CORPSE_HELPER_VA:#x}
        add esp, 4
    """
    single, _ = assemble(single_source, SINGLE_CURE_BLOCK_VA)
    mass, _ = assemble(mass_source, MASS_CURE_BLOCK_VA)
    if len(single) != len(SINGLE_CURE_EXPECTED):
        raise RuntimeError("Reordered single-Cure block changed size")
    if len(mass) > len(MASS_CURE_EXPECTED):
        raise RuntimeError("Reordered mass-Cure block exceeds its fixed-size range")
    mass += b"\x90" * (len(MASS_CURE_EXPECTED) - len(mass))
    return {SINGLE_CURE_BLOCK_VA: single, MASS_CURE_BLOCK_VA: mass}


test4_patch_visual_hooks = base.patch_visual_hooks


def patch_visual_hooks(path: Path, stage3_report: dict[str, Any]) -> dict[str, Any]:
    test4_report = test4_patch_visual_hooks(path, stage3_report)
    test4_bytes = path.read_bytes()
    pe = pefile.PE(data=test4_bytes, fast_load=False)
    expected = {
        SINGLE_CURE_BLOCK_VA: SINGLE_CURE_EXPECTED,
        MASS_CURE_BLOCK_VA: MASS_CURE_EXPECTED,
    }
    expected_hashes = {
        SINGLE_CURE_BLOCK_VA: SINGLE_CURE_EXPECTED_SHA256,
        MASS_CURE_BLOCK_VA: MASS_CURE_EXPECTED_SHA256,
    }
    baseline_blocks = {
        SINGLE_CURE_BLOCK_VA: SINGLE_CURE_BASELINE,
        MASS_CURE_BLOCK_VA: MASS_CURE_BASELINE,
    }
    replacements = reordered_cure_blocks()

    patched = bytearray(test4_bytes)
    log_order_regions: list[dict[str, Any]] = []
    decoded_order: list[dict[str, Any]] = []
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True

    for address, expected_bytes in expected.items():
        offset = va_to_offset(pe, address)
        actual = test4_bytes[offset : offset + len(expected_bytes)]
        if actual != expected_bytes:
            raise RuntimeError(
                f"Unexpected post-TEST4 Cure bytes at 0x{address:08X}: "
                f"{actual.hex(' ')}"
            )
        if sha256(actual).hexdigest() != expected_hashes[address]:
            raise RuntimeError(f"Post-TEST4 Cure block hash mismatch at 0x{address:08X}")
        replacement = replacements[address]
        patched[offset : offset + len(replacement)] = replacement

        calls: list[dict[str, Any]] = []
        for instruction in decoder.disasm(replacement, address):
            if (
                instruction.mnemonic == "call"
                and instruction.operands
                and instruction.operands[0].type == X86_OP_IMM
            ):
                calls.append(
                    {
                        "address": instruction.address,
                        "target": instruction.operands[0].imm,
                        "bytes": instruction.bytes.hex(" "),
                    }
                )
        targets = [item["target"] for item in calls]
        if CURE_CAST_LOG_VA not in targets or CURE_WRAPPER_VA not in targets:
            raise RuntimeError(f"Required Cure calls missing at 0x{address:08X}")
        if targets.index(CURE_CAST_LOG_VA) > targets.index(CURE_WRAPPER_VA):
            raise RuntimeError(f"Cure log still follows CureCore at 0x{address:08X}")
        if address == MASS_CURE_BLOCK_VA:
            if MASS_CORPSE_HELPER_VA not in targets:
                raise RuntimeError("Mass-Cure corpse helper call is missing")
            if targets.index(CURE_CAST_LOG_VA) > targets.index(MASS_CORPSE_HELPER_VA):
                raise RuntimeError("Cure log still follows the mass corpse scan")
        decoded_order.append(
            {
                "block_va": address,
                "call_sequence": calls,
                "cast_log_precedes_cure_wrapper": True,
            }
        )
        log_order_regions.append(
            {
                "label": f"Stage 4 TEST5 Cure log-order block at 0x{address:08X}",
                "va": address,
                "file_offset": offset,
                "length": len(replacement),
                "original_hex": baseline_blocks[address].hex(" "),
                "patched_hex": replacement.hex(" "),
                "rollback_hex": baseline_blocks[address].hex(" "),
                "test4_intermediate_hex": expected_bytes.hex(" "),
            }
        )

    final = bytes(patched)
    rollback = bytearray(final)
    cure_ranges = (
        (SINGLE_CURE_BLOCK_VA, SINGLE_CURE_BLOCK_VA + len(SINGLE_CURE_EXPECTED)),
        (MASS_CURE_BLOCK_VA, MASS_CURE_BLOCK_VA + len(MASS_CURE_EXPECTED)),
    )

    def overlaps_cure_block(region: dict[str, Any]) -> bool:
        start = region["va"]
        end = start + region["length"]
        return any(start < block_end and end > block_start for block_start, block_end in cure_ranges)

    nonoverlapping_test4_regions = [
        region
        for region in test4_report["logical_patch_regions"]
        if not overlaps_cure_block(region)
    ]
    all_regions = nonoverlapping_test4_regions + log_order_regions
    for region in all_regions:
        start = region["file_offset"]
        rollback[start : start + region["length"]] = bytes.fromhex(
            region["rollback_hex"]
        )
    if sha256_bytes(bytes(rollback)) != test4_report["input_sha256"]:
        raise RuntimeError(f"Combined TEST5 rollback failed for {path.name}")

    path.write_bytes(final)
    report = dict(test4_report)
    report["test4_intermediate_sha256"] = report["output_sha256"]
    report["output_sha256"] = sha256_bytes(final)
    report["logical_patch_regions"] = all_regions
    report["exact_contiguous_differences"] = contiguous_differences(
        bytes(rollback), final
    )
    report["decoded_cure_log_order"] = decoded_order
    report["cure_cast_log_moved_before_effects"] = True
    report["mass_stack_index_algebra_verified"] = True
    report["ordinary_resurrection_log_path_untouched"] = True
    report["rollback_reconstructs_input"] = True
    return report


def instructions(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 测试说明

状态：**战斗日志顺序测试版，不替换 `Download/Patch_v2.5.zip`。**

TEST4 的功能、动画、音效、重叠尸体与占位尸体测试已经全部通过。本版只修正战斗日志顺序：原版 Cure 分支会等全部治疗结算结束后才写入“英雄施放治愈”，因此治愈专属复活产生的“起死回生”信息会显示在前面。

TEST5 将 Cure 分支原有的施法日志调用等价前移，预期顺序为：

1. `阿斯特拉施放治愈。`（或尤兰德）
2. 各部队的 `起死回生了！`

数值、目标判定、永久复活、治愈动画/音效、起身动画与普通转世重生均不改变。

## 安装

1. 覆盖到干净 HotA 1.8.0，不要叠加任何旧补丁或测试版。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 先启动 `h3hota HD.exe` 到主菜单，再进行战斗测试。

## 必测

1. 阿斯特拉或尤兰德单体治愈复活一队全灭尸体：先显示施放治愈，再显示该队起死回生。
2. 高级水系群体治愈同时复活至少两队尸体：先显示一次施放治愈，再依次显示各队起死回生。
3. 对仍存活的受伤部队施放单体与群体治愈：治疗、动画、音效和日志均正常。
4. 普通转世重生的日志、动画与音效保持原版。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    return f"""# Stage 4 TEST5：治愈施法日志前移

状态：**静态构建与回滚验证完成，等待实机日志顺序门禁。**

## 根因

- 原生复活函数 `0x005A7870` 在每队复活结算过程中直接追加“起死回生”日志。
- 单体 Cure 在 `0x005A1B26`、群体 Cure 在 `0x005A1BF6` 调用 `0x005A8C60` 追加“英雄施放治愈”。
- 因为后者位于 CureCore 或群体循环之后，显示顺序自然成为“复活在前，施法在后”。

## 修改

- 在单体 Cure 固定长度块 `0x005A1AFA–0x005A1B2F` 内重排原有指令。
- 在群体 Cure 固定长度块 `0x005A1B30–0x005A1BFA` 内重排原有指令。
- 两个块的长度、入口和出口均不变；`0x005A8C60` 的原有参数不变，只是先于 CureCore 调用。
- 不新增代码洞，不缓存或改写字符串，不修改全局日志器，也不修改普通转世重生的日志路径。
- 构建器要求输入先精确匹配 TEST4 的两个 Cure 块，并验证单体/群体中施法日志调用均位于治愈专属包装器之前。

ZIP SHA-256：`{report['zip_sha256']}`
"""


base.patch_visual_hooks = patch_visual_hooks
base.instructions = instructions
base.research_markdown = research_markdown


if __name__ == "__main__":
    raise SystemExit(base.main())
