#!/usr/bin/env python3
"""Build TEST13: defer mass-Cure resurrection log appends until Cure is logged.

LOGDIAG01 proved that TEST12 rotates the native combat-log vector correctly and
that the vector remains correct after the native refresh.  The visible order is
therefore maintained by a second layer that observes append chronology.  TEST13
changes that chronology without changing resurrection state: Cure-triggered
mass-resurrection messages are recorded at their original call site, the native
Cure message is appended normally, and the saved messages are then formatted
and appended through the original combat-log API.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

import pefile

import build_stage4_visual_patch12 as test12
from build_diag_patch import contiguous_differences, sha256_bytes, va_to_offset
from build_stage3_patch import assemble, relative_branch


base = test12.base
BUILD_NAME = "Patch_v2.6_VISUAL_TEST13"

base.BUILD_NAME = BUILD_NAME
base.BUILD_SCOPE = "stage4_mass_cure_deferred_resurrection_log_append_test"
base.SUPERSEDES_TEST_BUILD = "Patch_v2.6_VISUAL_LOGDIAG01"
base.SUPERSEDED_RESULT_FIELD = "logdiag01_runtime_result"
base.SUPERSEDED_RUNTIME_RESULT = (
    "LOGDIAG01 recorded four Cure-only resurrection entries, a successful Cure "
    "pointer rotation, and an unchanged vector after native refresh; the visible "
    "order is therefore rebuilt from append chronology by a second display layer"
)


STATE_VA = test12.MASS_RESURRECTION_STATE_VA
MASS_HELPER_INIT_SITE_VA = 0x00639C29
RESURRECTION_LOG_CALL_VA = 0x005A7A3F
NATIVE_CURE_POST_APPEND_HOOK_VA = test12.NATIVE_CURE_POST_APPEND_HOOK_VA

NATIVE_LOG_APPEND_VA = 0x004729D0
SPRINTF_VA = 0x006179DE
CREATURE_TABLE_PTR_VA = 0x006747B0
GAME_PTR_VA = 0x006A5DC4
RESURRECTION_TEXT_BUFFER_VA = 0x00697428

PAYLOAD_CAVE_VA = 0x0065DA00
PAYLOAD_CAVE_END_VA = 0x0065E000
MASS_INIT_VA = 0x0065DA00
DEFER_WRAPPER_VA = 0x0065DA20
POST_CURE_REPLAY_VA = 0x0065DAA0
DATA_VA = 0x0065DD00
DEFERRED_COUNT_VA = DATA_VA
DEFERRED_RECORDS_VA = DATA_VA + 4
MAX_DEFERRED_RECORDS = 14
DEFERRED_RECORD_SIZE = 8

EXPECTED_MASS_HELPER_INIT = bytes.fromhex("80 0d fc 9f 63 00 80")
EXPECTED_RESURRECTION_LOG_CALL = relative_branch(
    RESURRECTION_LOG_CALL_VA, NATIVE_LOG_APPEND_VA, 0xE8
)
NATIVE_CURE_POST_APPEND_EXPECTED = bytes.fromhex("8b 4d e8 85 c9")


def build_deferred_payload() -> tuple[bytes, dict[str, Any], dict[str, bytes]]:
    """Assemble the initialization, defer wrapper, and post-Cure replay code."""

    mass_init_source = f"""
mass_deferred_log_init:
    mov byte ptr [{DEFERRED_COUNT_VA:#x}], 0
    or byte ptr [{STATE_VA:#x}], 0x80
    ret
"""
    defer_source = f"""
defer_or_append_resurrection_log:
    cmp byte ptr [{STATE_VA:#x}], 0x80
    jb append_now
    movzx eax, byte ptr [{DEFERRED_COUNT_VA:#x}]
    cmp eax, {MAX_DEFERRED_RECORDS}
    jae append_now
    mov edx, dword ptr [esi + 0x34]
    mov dword ptr [{DEFERRED_RECORDS_VA:#x} + eax * 8], edx
    mov edx, dword ptr [esi + 0x4c]
    sub edx, dword ptr [ebp + 0x08]
    mov dword ptr [{DEFERRED_RECORDS_VA + 4:#x} + eax * 8], edx
    inc byte ptr [{DEFERRED_COUNT_VA:#x}]
    xor eax, eax
    ret 0x0c
append_now:
    jmp {NATIVE_LOG_APPEND_VA:#x}
"""
    replay_source = f"""
replay_deferred_resurrection_logs:
    push ebx
    push esi
    push edi
    xor eax, eax
    xchg byte ptr [{STATE_VA:#x}], al
    test al, 0x80
    jz clear_stale_count
    xor eax, eax
    xchg byte ptr [{DEFERRED_COUNT_VA:#x}], al
    movzx ebx, al
    test ebx, ebx
    jz replay_displaced
    mov edi, {DEFERRED_RECORDS_VA:#x}
replay_next:
    mov esi, dword ptr [edi]
    imul esi, esi, 0x74
    mov edx, dword ptr [edi + 4]
    mov eax, dword ptr [{CREATURE_TABLE_PTR_VA:#x}]
    cmp edx, 1
    je singular_message
    mov eax, dword ptr [eax + esi + 0x18]
    mov ecx, dword ptr [{GAME_PTR_VA:#x}]
    mov ecx, dword ptr [ecx + 0x20]
    mov ecx, dword ptr [ecx + 0x1d4]
    jmp format_message
singular_message:
    mov eax, dword ptr [eax + esi + 0x14]
    mov ecx, dword ptr [{GAME_PTR_VA:#x}]
    mov ecx, dword ptr [ecx + 0x20]
    mov ecx, dword ptr [ecx + 0x1d8]
format_message:
    push eax
    push edx
    push ecx
    push {RESURRECTION_TEXT_BUFFER_VA:#x}
    call {SPRINTF_VA:#x}
    add esp, 0x10
    mov eax, dword ptr [ebp - 0x20]
    mov ecx, dword ptr [eax + 0x132fc]
    push 0
    push 1
    push {RESURRECTION_TEXT_BUFFER_VA:#x}
    call {NATIVE_LOG_APPEND_VA:#x}
    add edi, {DEFERRED_RECORD_SIZE}
    dec ebx
    jnz replay_next
    jmp replay_displaced
clear_stale_count:
    mov byte ptr [{DEFERRED_COUNT_VA:#x}], 0
replay_displaced:
    pop edi
    pop esi
    pop ebx
    mov ecx, dword ptr [ebp - 0x18]
    test ecx, ecx
    ret
"""

    sources = {
        "mass_deferred_log_init": mass_init_source,
        "defer_or_append_resurrection_log": defer_source,
        "replay_deferred_resurrection_logs": replay_source,
    }
    placements = {
        "mass_deferred_log_init": MASS_INIT_VA,
        "defer_or_append_resurrection_log": DEFER_WRAPPER_VA,
        "replay_deferred_resurrection_logs": POST_CURE_REPLAY_VA,
    }
    codes = {
        name: assemble(source, placements[name])[0]
        for name, source in sources.items()
    }
    ordered = sorted((placements[name], name, code) for name, code in codes.items())
    for (va, name, code), (next_va, next_name, _) in zip(ordered, ordered[1:]):
        if va + len(code) > next_va:
            raise RuntimeError(f"{name} overlaps {next_name}")
    code_end = max(va + len(code) for va, _, code in ordered)
    if code_end > DATA_VA:
        raise RuntimeError("TEST13 code overlaps deferred-record storage")
    data_end = DEFERRED_RECORDS_VA + MAX_DEFERRED_RECORDS * DEFERRED_RECORD_SIZE
    if data_end > PAYLOAD_CAVE_END_VA:
        raise RuntimeError("TEST13 deferred records exceed validated padding")

    payload = bytearray(data_end - PAYLOAD_CAVE_VA)
    for va, _, code in ordered:
        offset = va - PAYLOAD_CAVE_VA
        payload[offset : offset + len(code)] = code

    metadata = {
        "payload_va": PAYLOAD_CAVE_VA,
        "payload_size": len(payload),
        "payload_end_exclusive_va": PAYLOAD_CAVE_VA + len(payload),
        "deferred_count_va": DEFERRED_COUNT_VA,
        "deferred_records_va": DEFERRED_RECORDS_VA,
        "deferred_record_size": DEFERRED_RECORD_SIZE,
        "max_deferred_records": MAX_DEFERRED_RECORDS,
        "components": [
            {
                "name": name,
                "va": va,
                "size": len(codes[name]),
                "end_exclusive_va": va + len(codes[name]),
                "assembly": sources[name].strip(),
            }
            for name, va in placements.items()
        ],
    }
    return bytes(payload), metadata, codes


def patch_visual_hooks(path: Path, stage3_report: dict[str, Any]) -> dict[str, Any]:
    """Build TEST12 first, then replace pointer rotation with append deferral."""

    test12_report = test12.patch_visual_hooks_test12(path, stage3_report)
    test12_bytes = path.read_bytes()
    pe = pefile.PE(data=test12_bytes, fast_load=False)
    payload, metadata, codes = build_deferred_payload()

    mass_init_hook = relative_branch(
        MASS_HELPER_INIT_SITE_VA, MASS_INIT_VA, 0xE8
    ) + b"\x90\x90"
    defer_hook = relative_branch(
        RESURRECTION_LOG_CALL_VA, DEFER_WRAPPER_VA, 0xE8
    )
    replay_hook = relative_branch(
        NATIVE_CURE_POST_APPEND_HOOK_VA, POST_CURE_REPLAY_VA, 0xE8
    )
    test12_post_va = test12.build_runtime_payloads()[2]
    expected_test12_post_hook = relative_branch(
        NATIVE_CURE_POST_APPEND_HOOK_VA, test12_post_va, 0xE8
    )

    expected = {
        MASS_HELPER_INIT_SITE_VA: EXPECTED_MASS_HELPER_INIT,
        RESURRECTION_LOG_CALL_VA: EXPECTED_RESURRECTION_LOG_CALL,
        NATIVE_CURE_POST_APPEND_HOOK_VA: expected_test12_post_hook,
        PAYLOAD_CAVE_VA: bytes(len(payload)),
    }
    replacements = {
        MASS_HELPER_INIT_SITE_VA: mass_init_hook,
        RESURRECTION_LOG_CALL_VA: defer_hook,
        NATIVE_CURE_POST_APPEND_HOOK_VA: replay_hook,
        PAYLOAD_CAVE_VA: payload,
    }
    for va, expected_bytes in expected.items():
        offset = va_to_offset(pe, va)
        actual = test12_bytes[offset : offset + len(expected_bytes)]
        if actual != expected_bytes:
            raise RuntimeError(f"Unexpected TEST12 bytes at 0x{va:08X}")

    cave_section = next(
        section
        for section in pe.sections
        if section.VirtualAddress
        <= PAYLOAD_CAVE_VA - pe.OPTIONAL_HEADER.ImageBase
        < section.VirtualAddress + max(section.Misc_VirtualSize, section.SizeOfRawData)
    )
    if cave_section.Name.rstrip(b"\0") != b".rdata":
        raise RuntimeError("TEST13 cave moved out of .rdata")
    if cave_section.Characteristics & 0xE0000000 != 0xE0000000:
        raise RuntimeError("TEST13 cave section is not read/write/execute")
    if cave_section.Misc_VirtualSize >= cave_section.SizeOfRawData:
        raise RuntimeError("Expected .rdata raw-alignment padding is unavailable")
    next_section_va = next(
        section.VirtualAddress
        for section in pe.sections
        if section.VirtualAddress > cave_section.VirtualAddress
    )
    if cave_section.VirtualAddress + cave_section.SizeOfRawData > next_section_va:
        raise RuntimeError("Expanding .rdata VirtualSize would overlap the next section")
    virtual_size_offset = cave_section.get_file_offset() + 8
    virtual_size_before = struct.pack("<I", cave_section.Misc_VirtualSize)
    virtual_size_after = struct.pack("<I", cave_section.SizeOfRawData)
    if test12_bytes[virtual_size_offset : virtual_size_offset + 4] != virtual_size_before:
        raise RuntimeError("Unexpected .rdata VirtualSize header bytes")

    absolute_refs = []
    for offset in range(0, len(test12_bytes) - 3):
        value = struct.unpack_from("<I", test12_bytes, offset)[0]
        if PAYLOAD_CAVE_VA <= value < PAYLOAD_CAVE_END_VA:
            absolute_refs.append(offset)
    if absolute_refs:
        raise RuntimeError(f"Unexpected references into TEST13 padding: {absolute_refs[:8]}")

    patched = bytearray(test12_bytes)
    for va, replacement in replacements.items():
        offset = va_to_offset(pe, va)
        patched[offset : offset + len(replacement)] = replacement
    patched[virtual_size_offset : virtual_size_offset + 4] = virtual_size_after
    final = bytes(patched)

    decode = test12.test10.test9.test8.decode_instructions
    direct_calls = test12.test10.test9.direct_call_targets
    for va, target in (
        (MASS_HELPER_INIT_SITE_VA, MASS_INIT_VA),
        (RESURRECTION_LOG_CALL_VA, DEFER_WRAPPER_VA),
        (NATIVE_CURE_POST_APPEND_HOOK_VA, POST_CURE_REPLAY_VA),
    ):
        offset = va_to_offset(pe, va)
        instruction = decode(final[offset : offset + 5], va)[0]
        if instruction.mnemonic != "call" or instruction.operands[0].imm != target:
            raise RuntimeError(f"TEST13 call target changed at 0x{va:08X}")

    replay_calls = direct_calls(
        decode(codes["replay_deferred_resurrection_logs"], POST_CURE_REPLAY_VA)
    )
    if replay_calls != [SPRINTF_VA, NATIVE_LOG_APPEND_VA]:
        raise RuntimeError(f"TEST13 replay call sequence changed: {replay_calls}")
    defer_jumps = test12.direct_branches(
        codes["defer_or_append_resurrection_log"], DEFER_WRAPPER_VA, "jmp"
    )
    if defer_jumps != [NATIVE_LOG_APPEND_VA]:
        raise RuntimeError(f"TEST13 native fallback changed: {defer_jumps}")

    regions = json.loads(json.dumps(test12_report["logical_patch_regions"]))
    helper_offset = va_to_offset(pe, test12.MASS_HELPER_VA)
    for region in regions:
        start = region["va"]
        end = start + region["length"]
        if start <= MASS_HELPER_INIT_SITE_VA < end:
            region["label"] = "Stage 4 TEST13 counted Cure-resurrection and deferred-log init payload"
            region_offset = va_to_offset(pe, start)
            region["patched_hex"] = final[
                region_offset : region_offset + region["length"]
            ].hex(" ")
    regions = [
        region
        for region in regions
        if not (
            region["va"] == NATIVE_CURE_POST_APPEND_HOOK_VA
            and region["length"] == 5
        )
    ]

    def new_region(
        label: str, va: int, patched_bytes: bytes, rollback_bytes: bytes
    ) -> dict[str, Any]:
        return {
            "label": label,
            "va": va,
            "file_offset": va_to_offset(pe, va),
            "length": len(patched_bytes),
            "original_hex": rollback_bytes.hex(" "),
            "patched_hex": patched_bytes.hex(" "),
            "rollback_hex": rollback_bytes.hex(" "),
        }

    regions.extend(
        [
            new_region(
                "Stage 4 TEST13 defer native Resurrection log append",
                RESURRECTION_LOG_CALL_VA,
                defer_hook,
                EXPECTED_RESURRECTION_LOG_CALL,
            ),
            new_region(
                "Stage 4 TEST13 post-Cure deferred log replay hook",
                NATIVE_CURE_POST_APPEND_HOOK_VA,
                replay_hook,
                NATIVE_CURE_POST_APPEND_EXPECTED,
            ),
            new_region(
                "Stage 4 TEST13 deferred-log payload in validated .rdata padding",
                PAYLOAD_CAVE_VA,
                payload,
                bytes(len(payload)),
            ),
            {
                "label": "Stage 4 TEST13 map complete .rdata raw padding",
                "va": 0,
                "file_offset": virtual_size_offset,
                "length": 4,
                "original_hex": virtual_size_before.hex(" "),
                "patched_hex": virtual_size_after.hex(" "),
                "rollback_hex": virtual_size_before.hex(" "),
                "section_header_field": ".rdata.Misc_VirtualSize",
            },
        ]
    )

    rollback = bytearray(final)
    for region in regions:
        start = region["file_offset"]
        rollback[start : start + region["length"]] = bytes.fromhex(
            region["rollback_hex"]
        )
    if sha256_bytes(bytes(rollback)) != test12_report["input_sha256"]:
        raise RuntimeError(f"Combined TEST13 rollback failed for {path.name}")

    path.write_bytes(final)
    report = dict(test12_report)
    report["test12_intermediate_sha256"] = report["output_sha256"]
    report["output_sha256"] = sha256_bytes(final)
    report["logical_patch_regions"] = regions
    report["exact_contiguous_differences"] = contiguous_differences(
        bytes(rollback), final
    )
    report["logdiag01_runtime_result"] = base.SUPERSEDED_RUNTIME_RESULT
    report["logdiag01_record_count"] = 21
    report["logdiag01_resurrection_entry_count"] = 4
    report["logdiag01_rotation_succeeded"] = True
    report["logdiag01_native_refresh_preserved_rotation"] = True
    report["visible_log_uses_append_chronology"] = True
    report["mass_cure_resurrection_log_deferred"] = True
    report["deferred_messages_reformatted_with_native_text_tables"] = True
    report["deferred_messages_appended_with_native_log_api"] = True
    report["single_cure_path_unchanged"] = True
    report["ordinary_resurrection_falls_through_to_native_log_api"] = True
    report["deferred_payload"] = metadata
    report["decoded_test13_call_order"] = {
        "post_cure_replay_direct_calls": replay_calls,
        "defer_fallback_jump_targets": defer_jumps,
    }
    report["test13_cave_section"] = ".rdata"
    report["test13_cave_rwx"] = True
    report["test13_rdata_virtual_size_before"] = cave_section.Misc_VirtualSize
    report["test13_rdata_virtual_size_after"] = cave_section.SizeOfRawData
    report["test13_rdata_virtual_size_no_section_overlap"] = True
    report["rollback_reconstructs_input"] = True
    return report


def instructions(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 测试说明

状态：**LOGDIAG01 定位后的群体战斗日志时序修正版；仍是测试包，不替换 `Download/Patch_v2.5.zip`。**

LOGDIAG01 已证明 TEST12 的日志指针轮转和原生刷新都正确，但屏幕仍按实际追加先后重新生成显示缓存。TEST13 因此不再移动已写入的指针：群体治愈触发复活时，暂存每队的兵种与复活数量；原版“英雄施放治愈”正常写入后，再用原版文本和原生日志接口依次补写“起死回生”记录。

本版保持不变：

- 单体治愈现有的“先治愈、后复活”顺序；
- TEST4 已通过的复活数量、永久保留、亡灵排除、重叠尸体和占格尸体规则；
- 仅保留治愈动画、原版治愈音效与复活起身动作；
- 普通转世重生仍立即调用原生日志接口，动画、音效和日志均不变。

## 安装与一次测试

1. 覆盖到**干净 HotA 1.8.0**，不要叠加 LOGDIAG01 或其他测试补丁。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 用高级水系群体治愈一次复活两队或更多部队。
4. 应先显示“英雄施放治愈”，随后按原顺序显示各队“起死回生了”。同时确认不崩溃、数量正确、起身与音效不变。
5. 不需要再次生成诊断文件，也不必重复测试单体。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    return f"""# Stage 4 TEST13：按真实追加时序重放群体复活日志

状态：**标准版与 HD 版静态构建、调用约定、完整回滚、可复现性和 ZIP CRC 已验证；等待一次实机群体日志顺序门禁。**

## LOGDIAG01 实机结论

- 用户日志共 21 条定长记录，其中 4 条为治愈专属复活入口。
- 原生治愈日志追加后的状态为 `0x84`：群体标记有效且准确携带 4 次复活。
- TEST12 轮转后，插入位置确实保存治愈日志指针。
- 调用 `0x00472770` 后该位置和值没有变化。
- 因此屏幕顺序不是原生指针向量或刷新函数改回，而是 HotA/HD 的另一层显示缓存按日志追加调用的先后顺序维护。

## TEST13 设计

- 在原生转世重生日志调用点 `0x005A7A3F` 使用同长度 `CALL`。仅当 TEST12 的群体治愈状态高位有效时，记录兵种 ID 与本次复活数量并以 `RET 0x0C` 模拟原生日志调用的栈清理；单体治愈和普通转世重生直接尾跳原生 `0x004729D0`。
- 原生治愈日志仍在 `0x005A9547` 正常追加。紧接其后的同长度 Hook 不再轮转指针，而是读取暂存记录，复用原版兵种名单复数表、原版中文/英文格式串及 `sprintf`，再调用原生 `0x004729D0` 逐条追加。
- 每次群体尸体扫描入口清空暂存计数；最多保存 {MAX_DEFERRED_RECORDS} 条，每条 8 字节。代码和数据位于两个 EXE 共同、补丁前全零且无旧引用的 RWX `.rdata` 对齐填充中。
- 没有修改复活资格、数量、永久性、动画、音效或兵队状态；只改变治愈专属群体复活消息真正进入日志器的时点。

正式版 `Download/Patch_v2.5.zip` 保持不变。

ZIP SHA-256：`{report['zip_sha256']}`
"""


base.build_visual_payloads = test12.build_visual_payloads_for_test12
base.patch_visual_hooks = patch_visual_hooks
base.instructions = instructions
base.research_markdown = research_markdown


if __name__ == "__main__":
    raise SystemExit(base.main())
