#!/usr/bin/env python3
"""Build a UI-region sprintf diagnostic from formal V1.05."""

from __future__ import annotations

from typing import Any

import build_hota_new_hero_v106_uidiag01 as base
from build_hota_new_hero_v104 import assemble


BUILD_NAME = "HOTA_NEW_HERO_V1.06_UIDIAG03"
LOG_FILENAME = "hota_cure_uidiag03.bin"
SPRINTF_VA = 0x006179DE
SPRINTF_CONTINUE_VA = 0x006179E4
SPRINTF_ORIGINAL = bytes.fromhex("55 8B EC 83 EC 20")
UI_CALLER_MIN = 0x00590000
UI_CALLER_MAX_EXCLUSIVE = 0x005B0000
RECORD_MAGIC = 0x31544D46  # FMT1
RECORD_SIZE = 64
FORMAT_COPY_SIZE = 16
MAX_RECORDS = 2048
LOGGER_VA = base.DIAG_SECTION_VA + 0x000
WRAPPER_VA = base.DIAG_SECTION_VA + 0x200
TRAMPOLINE_VA = base.DIAG_SECTION_VA + 0x300
DATA_VA = base.DIAG_SECTION_VA + 0x400


def build_payload() -> tuple[bytes, dict[str, Any]]:
    filename = LOG_FILENAME.encode("ascii") + b"\0"
    filename_va = DATA_VA
    record_va = base.align(filename_va + len(filename), 4)
    count_va = record_va + RECORD_SIZE
    handle_va = count_va + 4
    written_va = handle_va + 4
    data_end_va = written_va + 4

    logger_source = f"""
    push ebp
    mov ebp, esp
    pushfd
    pushad
    mov eax, dword ptr [{count_va:#x}]
    cmp eax, {MAX_RECORDS}
    jae log_done
    inc eax
    mov dword ptr [{count_va:#x}], eax
    mov esi, dword ptr [ebp + 0x08]
    mov eax, dword ptr [esi]
    mov dword ptr [{record_va + 4:#x}], eax
    mov eax, dword ptr [esi + 0x04]
    mov dword ptr [{record_va + 8:#x}], eax
    mov eax, dword ptr [esi + 0x08]
    mov dword ptr [{record_va + 12:#x}], eax
    mov eax, dword ptr [esi + 0x0c]
    mov dword ptr [{record_va + 16:#x}], eax
    mov eax, dword ptr [esi + 0x10]
    mov dword ptr [{record_va + 20:#x}], eax
    mov eax, dword ptr [esi + 0x14]
    mov dword ptr [{record_va + 24:#x}], eax
    mov eax, dword ptr [esi + 0x18]
    mov dword ptr [{record_va + 28:#x}], eax
    mov eax, dword ptr [esi + 0x1c]
    mov dword ptr [{record_va + 32:#x}], eax
    mov eax, dword ptr [esi + 0x20]
    mov dword ptr [{record_va + 36:#x}], eax
    mov dword ptr [{record_va + 40:#x}], 0
    mov dword ptr [{record_va + 44:#x}], 0
    mov dword ptr [{record_va + 48:#x}], 0
    mov dword ptr [{record_va + 52:#x}], 0
    mov dword ptr [{record_va + 56:#x}], 0
    mov dword ptr [{record_va + 60:#x}], 0
    mov esi, dword ptr [ebp + 0x08]
    mov esi, dword ptr [esi + 0x08]
    test esi, esi
    je format_ready
    mov edi, {record_va + 40:#x}
    mov ecx, {FORMAT_COPY_SIZE}
copy_format:
    mov al, byte ptr [esi]
    mov byte ptr [edi], al
    inc esi
    inc edi
    test al, al
    je format_ready
    loop copy_format
format_ready:
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
    push {RECORD_SIZE}
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
    ret 4
    """

    wrapper_source = f"""
    mov eax, dword ptr [esp]
    cmp eax, {UI_CALLER_MIN:#x}
    jb native
    cmp eax, {UI_CALLER_MAX_EXCLUSIVE:#x}
    jae native
    lea eax, dword ptr [esp]
    push eax
    mov eax, {LOGGER_VA:#x}
    call eax
native:
    mov eax, {TRAMPOLINE_VA:#x}
    jmp eax
    """

    trampoline_source = f"""
    push ebp
    mov ebp, esp
    sub esp, 0x20
    mov eax, {SPRINTF_CONTINUE_VA:#x}
    jmp eax
    """

    slots = [
        ("bounded_sprintf_logger", LOGGER_VA, WRAPPER_VA, logger_source),
        ("ui_caller_filter", WRAPPER_VA, TRAMPOLINE_VA, wrapper_source),
        ("sprintf_trampoline", TRAMPOLINE_VA, DATA_VA, trampoline_source),
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
        "<I", RECORD_MAGIC
    )
    return bytes(payload), {
        "filter_mode": "sprintf callers in 0x00590000..0x005AFFFF; filter offline",
        "hooked_function": "sprintf-like formatter at 0x006179DE",
        "section_va": base.DIAG_SECTION_VA,
        "section_size": base.DIAG_SECTION_SIZE,
        "filename_va": filename_va,
        "record_va": record_va,
        "record_size": RECORD_SIZE,
        "maximum_records": MAX_RECORDS,
        "record_layout": [
            "magic FMT1",
            "formatter caller return address",
            "destination pointer",
            "format pointer",
            "variadic arguments 1..6",
            "first 16 format bytes, copied only until NUL",
            "two reserved dwords",
        ],
        "count_va": count_va,
        "handle_va": handle_va,
        "written_va": written_va,
        "components": components,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与诊断说明

这是从正式 HOTA_NEW_HERO_V1.05 重新构建的 UI 格式化路径诊断包。它会覆盖 UIDIAG02，不修改治疗、复活或任何界面返回值。

安装：
1. 将压缩包内全部文件解压到 HotA 1.8.0 游戏根目录，覆盖同名文件。
2. 若根目录已有 {LOG_FILENAME}，先把旧文件移走。
3. 使用平时的 h3hota HD.exe 启动。

一次闭合测试（不要点击施法）：
1. 使用尤兰德或阿斯特拉进入战斗，打开治愈术魔法书页面一次并记下显示数字。
2. 选择治愈术，依次悬停普通存活单位、大天使和一个可选己方尸体，各停留一秒。
3. 直接退出游戏，把根目录生成的 {LOG_FILENAME} 上传给 Codex。

本包只记录 EXE 内 UI 区域调用格式化函数时的调用者、格式指针、前六个参数及最多 16 字节格式串，最多 2048 条。所有调用最终都从原生序言跳板继续，格式化结果和游戏逻辑保持原样。
"""


def main() -> int:
    base.BUILD_NAME = BUILD_NAME
    base.LOG_FILENAME = LOG_FILENAME
    base.NATIVE_EFFECT_VA = SPRINTF_VA
    base.NATIVE_EFFECT_CONTINUE_VA = SPRINTF_CONTINUE_VA
    base.NATIVE_EFFECT_ORIGINAL = SPRINTF_ORIGINAL
    base.LOGGER_VA = LOGGER_VA
    base.WRAPPER_VA = WRAPPER_VA
    base.TRAMPOLINE_VA = TRAMPOLINE_VA
    base.DATA_VA = DATA_VA
    base.build_payload = build_payload
    base.installation_text = installation_text
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
