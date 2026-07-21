#!/usr/bin/env python3
"""Build a one-run combat-log diagnostic on the TEST12 behavior.

The package keeps TEST12 gameplay/presentation behavior and appends fixed-size
binary records at the mass-wrapper, corpse-helper, Cure-only resurrection, and
native Cure-log post-append paths. Three snapshots around pointer rotation and
native refresh distinguish an unexecuted hook from a lost counter or a later
display rebuild.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

import pefile

import build_stage4_visual_patch12 as test12
from build_diag_patch import IAT, contiguous_differences, sha256_bytes, va_to_offset
from build_stage3_patch import assemble, relative_branch


base = test12.base
BUILD_NAME = "Patch_v2.6_VISUAL_LOGDIAG01"
LOG_FILENAME = "hota_cure_logdiag01.bin"

base.BUILD_NAME = BUILD_NAME
base.BUILD_SCOPE = "stage4_single_run_native_log_order_binary_diagnostic"
base.SUPERSEDES_TEST_BUILD = "Patch_v2.6_VISUAL_TEST12"
base.SUPERSEDED_RESULT_FIELD = "test12_runtime_result"
base.SUPERSEDED_RUNTIME_RESULT = (
    "Mass Cure remained stable but the Cure cast line still appeared after "
    "all revival lines, so the next build records live execution and vector state"
)


WRAPPER_INIT_SITE_VA = 0x00639DD9
MASS_HELPER_INIT_SITE_VA = 0x00639C29
COUNTED_RESURRECTION_SITE_VA = 0x00639CCB
NATIVE_CURE_POST_APPEND_HOOK_VA = test12.NATIVE_CURE_POST_APPEND_HOOK_VA
STATE_VA = test12.MASS_RESURRECTION_STATE_VA

DIAG_CAVE_VA = 0x0065DA00
DIAG_CAVE_END_VA = 0x0065E000
DIAG_EVENT_VA = 0x0065DA00
DIAG_WRAPPER_INIT_VA = 0x0065DB00
DIAG_HELPER_INIT_VA = 0x0065DB60
DIAG_COUNTED_VA = 0x0065DBC0
DIAG_POST_APPEND_VA = 0x0065DC40
DIAG_DATA_VA = 0x0065DF00

EVENT_WRAPPER_INIT = 1
EVENT_HELPER_INIT = 2
EVENT_RESURRECTION = 3
EVENT_POST_ENTER = 4
EVENT_AFTER_ROTATE = 5
EVENT_AFTER_REFRESH = 6
RECORD_MAGIC = 0x31474448  # little-endian bytes: HDG1
RECORD_SIZE = 24

EXPECTED_WRAPPER_INIT = bytes.fromhex("80 0d fc 9f 63 00 80")
EXPECTED_HELPER_INIT = EXPECTED_WRAPPER_INIT
EXPECTED_COUNTED = bytes.fromhex(
    "80 3d fc 9f 63 00 80 72 06 fe 05 fc 9f 63 00"
)


def build_diag_payload() -> tuple[bytes, dict[str, Any], dict[str, bytes]]:
    filename = LOG_FILENAME.encode("ascii") + b"\0"
    filename_va = DIAG_DATA_VA
    record_va = filename_va + len(filename)
    handle_va = record_va + RECORD_SIZE
    written_va = handle_va + 4
    data_end_va = written_va + 4

    event_source = f"""
diag_event:
    pushfd
    pushad
    mov eax, dword ptr [esp + 0x28]
    mov dword ptr [{record_va + 4:#x}], eax
    mov eax, dword ptr [esp + 0x2c]
    mov dword ptr [{record_va + 8:#x}], eax
    mov eax, dword ptr [esp + 0x30]
    mov dword ptr [{record_va + 12:#x}], eax
    mov eax, dword ptr [esp + 0x34]
    mov dword ptr [{record_va + 16:#x}], eax
    mov eax, dword ptr [esp + 0x38]
    mov dword ptr [{record_va + 20:#x}], eax
    push 0
    push 0x80
    push 4
    push 0
    push 3
    push 4
    push {filename_va:#x}
    call dword ptr [{IAT['CreateFileA']:#x}]
    cmp eax, -1
    je diag_done
    mov dword ptr [{handle_va:#x}], eax
    mov dword ptr [{written_va:#x}], 0
    push 0
    push {written_va:#x}
    push {RECORD_SIZE}
    push {record_va:#x}
    push eax
    call dword ptr [{IAT['WriteFile']:#x}]
    push dword ptr [{handle_va:#x}]
    call dword ptr [{IAT['CloseHandle']:#x}]
diag_done:
    popad
    popfd
    ret 0x14
"""
    wrapper_source = f"""
diag_wrapper_init:
    pushfd
    pushad
    or byte ptr [{STATE_VA:#x}], 0x80
    movzx eax, byte ptr [{STATE_VA:#x}]
    mov edx, dword ptr [esp + 0x28]
    push 0
    push ecx
    push eax
    push edx
    push {EVENT_WRAPPER_INIT}
    call {DIAG_EVENT_VA:#x}
    popad
    popfd
    ret
"""
    helper_source = f"""
diag_helper_init:
    pushfd
    pushad
    or byte ptr [{STATE_VA:#x}], 0x80
    movzx eax, byte ptr [{STATE_VA:#x}]
    mov edx, dword ptr [ebp - 0x14]
    push dword ptr [ebp + 0x14]
    push ebx
    push edx
    push eax
    push {EVENT_HELPER_INIT}
    call {DIAG_EVENT_VA:#x}
    popad
    popfd
    ret
"""
    counted_source = f"""
diag_counted_resurrection:
    pushfd
    pushad
    cmp byte ptr [{STATE_VA:#x}], 0x80
    jb count_ready
    inc byte ptr [{STATE_VA:#x}]
count_ready:
    movzx eax, byte ptr [{STATE_VA:#x}]
    mov edx, dword ptr [esp + 0x2c]
    mov esi, dword ptr [esp + 0x30]
    mov edi, dword ptr [esp + 0x28]
    push edi
    push esi
    push edx
    push eax
    push {EVENT_RESURRECTION}
    call {DIAG_EVENT_VA:#x}
    popad
    popfd
    ret
"""
    post_source = f"""
diag_native_cure_post_append:
    push ebx
    push esi
    push edi
    xor eax, eax
    xchg byte ptr [{STATE_VA:#x}], al
    mov ebx, eax
    mov ecx, dword ptr [ebp - 0x20]
    mov ecx, dword ptr [ecx + 0x132fc]
    mov esi, dword ptr [ecx + 0x58]
    mov edi, dword ptr [ecx + 0x5c]
    xor edx, edx
    cmp edi, esi
    jbe enter_ready
    mov edx, dword ptr [edi - 4]
enter_ready:
    push edx
    push edi
    push esi
    push ebx
    push {EVENT_POST_ENTER}
    call {DIAG_EVENT_VA:#x}
    test bl, 0x80
    jz replay_displaced
    and ebx, 0x7f
    jz replay_displaced
    mov edx, edi
    sub edx, 4
    mov eax, ebx
    neg eax
    lea eax, [edx + eax * 4]
    mov edi, eax
    mov ecx, dword ptr [edx]
rotate_pointer:
    xchg dword ptr [eax], ecx
    add eax, 4
    cmp eax, edx
    jbe rotate_pointer
    push dword ptr [edx]
    push dword ptr [edi]
    push edi
    push ebx
    push {EVENT_AFTER_ROTATE}
    call {DIAG_EVENT_VA:#x}
    mov eax, dword ptr [ebp - 0x20]
    mov ecx, dword ptr [eax + 0x132fc]
    push dword ptr [ecx + 0x68]
    call {test12.COMBAT_LOG_REFRESH_VA:#x}
    mov eax, dword ptr [ebp - 0x20]
    mov ecx, dword ptr [eax + 0x132fc]
    mov edx, dword ptr [ecx + 0x5c]
    sub edx, 4
    push dword ptr [edx]
    push dword ptr [edi]
    push edi
    push ebx
    push {EVENT_AFTER_REFRESH}
    call {DIAG_EVENT_VA:#x}
replay_displaced:
    pop edi
    pop esi
    pop ebx
    mov ecx, dword ptr [ebp - 0x18]
    test ecx, ecx
    ret
"""

    slots = [
        ("diag_event", DIAG_EVENT_VA, DIAG_WRAPPER_INIT_VA, event_source),
        ("diag_wrapper_init", DIAG_WRAPPER_INIT_VA, DIAG_HELPER_INIT_VA, wrapper_source),
        ("diag_helper_init", DIAG_HELPER_INIT_VA, DIAG_COUNTED_VA, helper_source),
        ("diag_counted_resurrection", DIAG_COUNTED_VA, DIAG_POST_APPEND_VA, counted_source),
        ("diag_native_cure_post_append", DIAG_POST_APPEND_VA, DIAG_DATA_VA, post_source),
    ]
    payload = bytearray(data_end_va - DIAG_CAVE_VA)
    components = []
    codes: dict[str, bytes] = {}
    for name, va, slot_end, source in slots:
        code, statement_count = assemble(source, va)
        if va + len(code) > slot_end:
            raise RuntimeError(f"{name} exceeds its diagnostic slot")
        payload[va - DIAG_CAVE_VA : va - DIAG_CAVE_VA + len(code)] = code
        codes[name] = code
        components.append(
            {
                "name": name,
                "va": va,
                "size": len(code),
                "slot_end_exclusive_va": slot_end,
                "assembly_statement_count": statement_count,
                "assembly": source.strip(),
            }
        )

    data = filename + struct.pack("<6I", RECORD_MAGIC, 0, 0, 0, 0, 0) + b"\0" * 8
    payload[DIAG_DATA_VA - DIAG_CAVE_VA : data_end_va - DIAG_CAVE_VA] = data
    if DIAG_CAVE_VA + len(payload) > DIAG_CAVE_END_VA:
        raise RuntimeError("Diagnostic payload exceeds validated .rdata padding")
    metadata = {
        "payload_size": len(payload),
        "payload_end_exclusive_va": DIAG_CAVE_VA + len(payload),
        "filename": LOG_FILENAME,
        "filename_va": filename_va,
        "record_va": record_va,
        "record_size": RECORD_SIZE,
        "record_magic": RECORD_MAGIC,
        "handle_va": handle_va,
        "written_va": written_va,
        "components": components,
    }
    return bytes(payload), metadata, codes


def patch_visual_hooks(path: Path, stage3_report: dict[str, Any]) -> dict[str, Any]:
    test12_report = test12.patch_visual_hooks_test12(path, stage3_report)
    test12_bytes = path.read_bytes()
    pe = pefile.PE(data=test12_bytes, fast_load=False)
    payload, metadata, _ = build_diag_payload()

    wrapper_hook = relative_branch(
        WRAPPER_INIT_SITE_VA, DIAG_WRAPPER_INIT_VA, 0xE8
    ) + b"\x90\x90"
    helper_hook = relative_branch(
        MASS_HELPER_INIT_SITE_VA, DIAG_HELPER_INIT_VA, 0xE8
    ) + b"\x90\x90"
    counted_hook = relative_branch(
        COUNTED_RESURRECTION_SITE_VA, DIAG_COUNTED_VA, 0xE8
    ) + b"\x90" * 10
    post_hook = relative_branch(
        NATIVE_CURE_POST_APPEND_HOOK_VA, DIAG_POST_APPEND_VA, 0xE8
    )
    test12_post_va = test12.build_runtime_payloads()[2]
    expected_post_hook = relative_branch(
        NATIVE_CURE_POST_APPEND_HOOK_VA, test12_post_va, 0xE8
    )

    expected = {
        WRAPPER_INIT_SITE_VA: EXPECTED_WRAPPER_INIT,
        MASS_HELPER_INIT_SITE_VA: EXPECTED_HELPER_INIT,
        COUNTED_RESURRECTION_SITE_VA: EXPECTED_COUNTED,
        NATIVE_CURE_POST_APPEND_HOOK_VA: expected_post_hook,
        DIAG_CAVE_VA: bytes(len(payload)),
    }
    replacements = {
        WRAPPER_INIT_SITE_VA: wrapper_hook,
        MASS_HELPER_INIT_SITE_VA: helper_hook,
        COUNTED_RESURRECTION_SITE_VA: counted_hook,
        NATIVE_CURE_POST_APPEND_HOOK_VA: post_hook,
        DIAG_CAVE_VA: payload,
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
        <= DIAG_CAVE_VA - pe.OPTIONAL_HEADER.ImageBase
        < section.VirtualAddress + max(section.Misc_VirtualSize, section.SizeOfRawData)
    )
    if cave_section.Name.rstrip(b"\0") != b".rdata":
        raise RuntimeError("Diagnostic cave moved out of .rdata")
    if cave_section.Characteristics & 0xE0000000 != 0xE0000000:
        raise RuntimeError("Diagnostic cave section is not read/write/execute")
    if cave_section.Misc_VirtualSize >= cave_section.SizeOfRawData:
        raise RuntimeError("Expected .rdata raw-alignment padding is unavailable")
    if (
        cave_section.VirtualAddress + cave_section.SizeOfRawData
        > next(
            section.VirtualAddress
            for section in pe.sections
            if section.VirtualAddress > cave_section.VirtualAddress
        )
    ):
        raise RuntimeError("Expanding .rdata VirtualSize would overlap the next section")
    virtual_size_offset = cave_section.get_file_offset() + 8
    virtual_size_before = struct.pack("<I", cave_section.Misc_VirtualSize)
    virtual_size_after = struct.pack("<I", cave_section.SizeOfRawData)
    if (
        test12_bytes[virtual_size_offset : virtual_size_offset + 4]
        != virtual_size_before
    ):
        raise RuntimeError("Unexpected .rdata VirtualSize header bytes")
    absolute_refs = []
    for offset in range(0, len(test12_bytes) - 3):
        value = struct.unpack_from("<I", test12_bytes, offset)[0]
        if DIAG_CAVE_VA <= value < DIAG_CAVE_END_VA:
            absolute_refs.append(offset)
    if absolute_refs:
        raise RuntimeError(f"Unexpected references into diagnostic padding: {absolute_refs[:8]}")

    patched = bytearray(test12_bytes)
    for va, replacement in replacements.items():
        offset = va_to_offset(pe, va)
        patched[offset : offset + len(replacement)] = replacement
    patched[virtual_size_offset : virtual_size_offset + 4] = virtual_size_after
    final = bytes(patched)

    for va, target in (
        (WRAPPER_INIT_SITE_VA, DIAG_WRAPPER_INIT_VA),
        (MASS_HELPER_INIT_SITE_VA, DIAG_HELPER_INIT_VA),
        (COUNTED_RESURRECTION_SITE_VA, DIAG_COUNTED_VA),
        (NATIVE_CURE_POST_APPEND_HOOK_VA, DIAG_POST_APPEND_VA),
    ):
        offset = va_to_offset(pe, va)
        instruction = test12.test10.test9.test8.decode_instructions(
            final[offset : offset + 5], va
        )[0]
        if instruction.mnemonic != "call" or instruction.operands[0].imm != target:
            raise RuntimeError(f"Diagnostic call target changed at 0x{va:08X}")

    event_calls = test12.test10.test9.direct_call_targets(
        test12.test10.test9.test8.decode_instructions(
            payload, DIAG_CAVE_VA
        )
    )
    if event_calls.count(DIAG_EVENT_VA) != 6:
        raise RuntimeError("Diagnostic event call count changed")
    if event_calls.count(test12.COMBAT_LOG_REFRESH_VA) != 1:
        raise RuntimeError("Diagnostic native refresh call count changed")

    regions = json.loads(json.dumps(test12_report["logical_patch_regions"]))
    primary_offset = va_to_offset(pe, test12.PRIMARY_CAVE_VA)
    secondary_offset = va_to_offset(pe, test12.MASS_HELPER_VA)
    for region in regions:
        if region["va"] == test12.PRIMARY_CAVE_VA:
            region["label"] = "Stage 4 LOGDIAG01 instrumented Cure payload"
            region["patched_hex"] = final[
                primary_offset : primary_offset + region["length"]
            ].hex(" ")
        elif region["va"] == test12.MASS_HELPER_VA:
            region["label"] = "Stage 4 LOGDIAG01 instrumented corpse/count payload"
            region["patched_hex"] = final[
                secondary_offset : secondary_offset + region["length"]
            ].hex(" ")
        elif region["va"] == NATIVE_CURE_POST_APPEND_HOOK_VA:
            region["label"] = "Stage 4 LOGDIAG01 native post-append hook"
            region["patched_hex"] = post_hook.hex(" ")
    regions.append(
        {
            "label": "Stage 4 LOGDIAG01 binary logger in validated .rdata padding",
            "va": DIAG_CAVE_VA,
            "file_offset": va_to_offset(pe, DIAG_CAVE_VA),
            "length": len(payload),
            "original_hex": bytes(len(payload)).hex(" "),
            "patched_hex": payload.hex(" "),
            "rollback_hex": bytes(len(payload)).hex(" "),
        }
    )
    regions.append(
        {
            "label": "Stage 4 LOGDIAG01 map complete .rdata raw padding",
            "va": 0,
            "file_offset": virtual_size_offset,
            "length": 4,
            "original_hex": virtual_size_before.hex(" "),
            "patched_hex": virtual_size_after.hex(" "),
            "rollback_hex": virtual_size_before.hex(" "),
            "section_header_field": ".rdata.Misc_VirtualSize",
        }
    )

    rollback = bytearray(final)
    for region in regions:
        start = region["file_offset"]
        rollback[start : start + region["length"]] = bytes.fromhex(
            region["rollback_hex"]
        )
    if sha256_bytes(bytes(rollback)) != test12_report["input_sha256"]:
        raise RuntimeError(f"Combined LOGDIAG01 rollback failed for {path.name}")

    path.write_bytes(final)
    report = dict(test12_report)
    report["test12_intermediate_sha256"] = report["output_sha256"]
    report["output_sha256"] = sha256_bytes(final)
    report["logical_patch_regions"] = regions
    report["exact_contiguous_differences"] = contiguous_differences(
        bytes(rollback), final
    )
    report["test11_runtime_result"] = (
        "Mass Cure stable; TEST11 still displayed the Cure cast line last"
    )
    report["test12_runtime_result"] = base.SUPERSEDED_RUNTIME_RESULT
    report["diagnostic_only_addition"] = True
    report["diagnostic_log_filename"] = LOG_FILENAME
    report["diagnostic_record_size"] = RECORD_SIZE
    report["diagnostic_record_magic"] = RECORD_MAGIC
    report["diagnostic_event_ids"] = {
        "wrapper_init": EVENT_WRAPPER_INIT,
        "corpse_helper_init": EVENT_HELPER_INIT,
        "resurrection_entry": EVENT_RESURRECTION,
        "native_post_enter": EVENT_POST_ENTER,
        "after_rotation": EVENT_AFTER_ROTATE,
        "after_refresh": EVENT_AFTER_REFRESH,
    }
    report["diagnostic_payload"] = metadata
    report["diagnostic_cave_section"] = ".rdata"
    report["diagnostic_cave_rwx"] = True
    report["diagnostic_rdata_virtual_size_before"] = cave_section.Misc_VirtualSize
    report["diagnostic_rdata_virtual_size_after"] = cave_section.SizeOfRawData
    report["diagnostic_rdata_virtual_size_no_section_overlap"] = True
    report["diagnostic_cave_preexisting_absolute_references"] = 0
    report["diagnostic_call_sites_same_size"] = True
    report["test12_gameplay_and_visual_paths_preserved"] = True
    report["rollback_reconstructs_input"] = True
    return report


def instructions(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 一次性日志诊断说明

状态：**仅用于定位群体治愈日志顺序；不替换正式版，也不是新的功能候选版。**

本包保持 TEST12 的复活、动画、音效和日志轮转逻辑，只增加二进制诊断记录。一次群体治愈即可确认：

1. 群体治愈包装器和尸体扫描是否实际执行；
2. 每次治愈专用复活是否被准确计数；
3. 原生治愈日志真实追加后的 Hook 是否进入；
4. 指针轮转是否成功；
5. 调用原生日志刷新后，向量是否又被改回。

## 测试步骤

1. 覆盖到**干净 HotA 1.8.0**，不要叠加 TEST12 或其他补丁。
2. 删除游戏根目录旧的 `{LOG_FILENAME}`。
3. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
4. 用阿斯特拉或尤兰德施放一次高级水系群体治愈，最好同时复活两队以上。
5. 截图战斗日志，然后退出游戏。
6. 上传游戏根目录生成的 `{LOG_FILENAME}`。这是固定记录格式的二进制文件，不要用文本编辑器另存。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    return f"""# Stage 4 LOGDIAG01：一次测试闭合群体日志显示链

状态：**标准版与 HD 版静态构建、完整回滚与可复现性已验证；等待一份实机二进制日志。**

- 日志文件：`{LOG_FILENAME}`；每条 `{RECORD_SIZE}` 字节，小端序六个 DWORD。
- 事件 1/2/3 分别证明群体包装器、尸体辅助函数和每次治愈专用复活计数实际执行。
- 事件 4 保存原生治愈日志追加后的状态字节、向量首尾地址及最后指针。
- 事件 5 保存轮转后的插入位置和值；事件 6 保存调用 `0x00472770` 刷新后的同一位置和值。
- 诊断载荷位于两个 EXE 共同的 RWX `.rdata` 原始对齐填充 `0x0065DA00` 起；补丁前为全零且没有绝对引用。
- 正式版 `Download/Patch_v2.5.zip` 未改变。

ZIP SHA-256：`{report['zip_sha256']}`
"""


base.build_visual_payloads = test12.build_visual_payloads_for_test12
base.patch_visual_hooks = patch_visual_hooks
base.instructions = instructions
base.research_markdown = research_markdown


if __name__ == "__main__":
    raise SystemExit(base.main())
