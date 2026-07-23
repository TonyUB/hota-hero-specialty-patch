#!/usr/bin/env python3
"""Build an unfiltered native-effect path diagnostic from formal V1.05."""

from __future__ import annotations

from typing import Any

import build_hota_new_hero_v106_uidiag01 as base
from build_hota_new_hero_v104 import assemble


BUILD_NAME = "HOTA_NEW_HERO_V1.06_UIDIAG02"
LOG_FILENAME = "hota_cure_uidiag02.bin"


def build_payload() -> tuple[bytes, dict[str, Any]]:
    filename = LOG_FILENAME.encode("ascii") + b"\0"
    filename_va = base.DATA_VA
    record_va = base.align(filename_va + len(filename), 4)
    handle_va = record_va + base.RECORD_SIZE
    written_va = handle_va + 4
    data_end_va = written_va + 4

    logger_source = f"""
    push ebp
    mov ebp, esp
    pushfd
    pushad
    mov eax, dword ptr [ebp + 0x08]
    mov dword ptr [{record_va + 4:#x}], eax
    mov eax, dword ptr [ebp + 0x0c]
    mov dword ptr [{record_va + 8:#x}], eax
    mov eax, dword ptr [ebp + 0x10]
    mov dword ptr [{record_va + 12:#x}], eax
    mov eax, dword ptr [ebp + 0x14]
    mov dword ptr [{record_va + 16:#x}], eax
    mov eax, dword ptr [ebp + 0x18]
    mov dword ptr [{record_va + 20:#x}], eax
    mov eax, dword ptr [ebp + 0x1c]
    mov dword ptr [{record_va + 24:#x}], eax
    mov eax, dword ptr [ebp + 0x20]
    mov dword ptr [{record_va + 28:#x}], eax
    mov eax, dword ptr [ebp + 0x24]
    mov dword ptr [{record_va + 32:#x}], eax
    mov eax, dword ptr [ebp + 0x28]
    mov dword ptr [{record_va + 36:#x}], eax
    push 0
    push 0x80
    push 4
    push 0
    push 3
    push 4
    push {filename_va:#x}
    call dword ptr [{base.IAT['CreateFileA']:#x}]
    cmp eax, -1
    je log_done
    mov dword ptr [{handle_va:#x}], eax
    mov dword ptr [{written_va:#x}], 0
    push 0
    push {written_va:#x}
    push {base.RECORD_SIZE}
    push {record_va:#x}
    push eax
    call dword ptr [{base.IAT['WriteFile']:#x}]
    push dword ptr [{handle_va:#x}]
    call dword ptr [{base.IAT['CloseHandle']:#x}]
log_done:
    popad
    popfd
    mov esp, ebp
    pop ebp
    ret 0x24
    """

    wrapper_source = f"""
    push ebp
    mov ebp, esp
    sub esp, 0x08
    push ebx
    push esi
    push edi
    mov esi, ecx
    mov ebx, dword ptr [ebp + 0x0c]
    mov edi, dword ptr [ebp + 0x10]
    push edi
    push ebx
    push dword ptr [ebp + 0x08]
    mov ecx, esi
    mov eax, {base.TRAMPOLINE_VA:#x}
    call eax
    mov dword ptr [ebp - 0x04], eax
    mov eax, 1
    test edi, edi
    je event_ready
    mov eax, 2
event_ready:
    xor edx, edx
    test esi, esi
    je object_ready
    mov edx, dword ptr [esi + 0x1a]
object_ready:
    push 0
    push dword ptr [ebp - 0x04]
    push ebx
    push edi
    push dword ptr [ebp + 0x08]
    push edx
    push esi
    push dword ptr [ebp + 0x04]
    push eax
    mov eax, {base.LOGGER_VA:#x}
    call eax
    mov eax, dword ptr [ebp - 0x04]
    pop edi
    pop esi
    pop ebx
    mov esp, ebp
    pop ebp
    ret 0x0c
    """

    trampoline_source = f"""
    push ebp
    mov ebp, esp
    sub esp, 8
    mov eax, {base.NATIVE_EFFECT_CONTINUE_VA:#x}
    jmp eax
    """

    slots = [
        ("logger", base.LOGGER_VA, base.WRAPPER_VA, logger_source),
        ("unfiltered_wrapper", base.WRAPPER_VA, base.TRAMPOLINE_VA, wrapper_source),
        ("trampoline", base.TRAMPOLINE_VA, base.DATA_VA, trampoline_source),
    ]
    payload = bytearray(base.DIAG_SECTION_SIZE)
    components = []
    for name, va, limit, source in slots:
        code = assemble(source, va)
        if va + len(code) > limit:
            raise RuntimeError(f"{name} exceeds its isolated diagnostic slot")
        start = va - base.DIAG_SECTION_VA
        payload[start : start + len(code)] = code
        components.append({
            "name": name,
            "va": va,
            "length": len(code),
            "limit_va": limit,
            "assembly": source.strip(),
        })
    if data_end_va > base.DIAG_SECTION_VA + base.DIAG_SECTION_SIZE:
        raise RuntimeError("Diagnostic data exceeds isolated PE section")
    payload[filename_va - base.DIAG_SECTION_VA : filename_va - base.DIAG_SECTION_VA + len(filename)] = filename
    payload[record_va - base.DIAG_SECTION_VA : record_va - base.DIAG_SECTION_VA + 4] = base.struct.pack(
        "<I", base.RECORD_MAGIC
    )
    return bytes(payload), {
        "filter_mode": "unfiltered native-effect calls; filter offline",
        "section_va": base.DIAG_SECTION_VA,
        "section_size": base.DIAG_SECTION_SIZE,
        "filename_va": filename_va,
        "record_va": record_va,
        "record_size": base.RECORD_SIZE,
        "record_layout": [
            "magic UID1",
            "event (1=null target, 2=non-null target)",
            "native caller return address",
            "object pointer passed in ECX",
            "raw dword at object+0x1A (zero if object is null)",
            "raw first stack argument",
            "target pointer",
            "raw second stack argument",
            "native result",
            "reserved",
        ],
        "handle_va": handle_va,
        "written_va": written_va,
        "components": components,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与诊断说明

这是从正式 HOTA_NEW_HERO_V1.05 重新构建的无筛选只读路径诊断包。它会覆盖上一版 UIDIAG01，但不会修正或改写任何治疗数值。

安装：
1. 将压缩包内全部文件解压到 HotA 1.8.0 游戏根目录，覆盖同名文件。
2. 若根目录已有 {LOG_FILENAME}，先把旧文件移走。
3. 使用平时的 h3hota HD.exe 启动。

最小测试（不要点击施法）：
1. 使用尤兰德或阿斯特拉进入战斗，打开魔法书中的治愈术页面一次。
2. 选择治愈术，依次悬停一个存活己方单位和一个可选己方尸体，只观察底部提示。
3. 直接退出游戏，把根目录生成的 {LOG_FILENAME} 上传给 Codex。

本版取消入口内的英雄和法术筛选，记录经过原生通用法术效果计算器的全部调用，再由 Codex 根据调用者、原始参数和对象字段离线识别真实路径。原生计算结果会被原样返回；实际治疗/复活、战斗日志、动画、音效和正式 V1.05 的资源均不改变。
"""


def main() -> int:
    base.BUILD_NAME = BUILD_NAME
    base.LOG_FILENAME = LOG_FILENAME
    base.build_payload = build_payload
    base.installation_text = installation_text
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
