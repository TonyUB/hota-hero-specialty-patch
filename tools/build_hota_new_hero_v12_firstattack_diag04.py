#!/usr/bin/env python3
"""Build an action-boundary diagnostic from formal V1.11.

DIAG03 proved the two live HotA.dll attack callbacks and their attacker
argument.  DIAG04 records only verified combat-manager and combat-stack
fields so active attacks, retaliations and repeated callbacks belonging to
one attack command can be separated without changing gameplay.
"""

from __future__ import annotations

from typing import Any

import build_hota_new_hero_v12_firstattack_diag01 as exe_base
import build_hota_new_hero_v12_firstattack_diag03 as diag03


BUILD_NAME = "HOTA_NEW_HERO_V1.2_FIRSTATTACK_DIAG04"
LOG_FILENAME = "hota_luck_firstdiag04.bin"


def build_callback_wrapper(
    *,
    wrapper_va: int,
    path_id: int,
    record_va: int,
    native_tail: str,
) -> tuple[bytes, str]:
    # Both DIAG03 live callbacks use original arg2 (entry ESP+8) as the
    # attacking H3CombatCreature.  The original functions dereference it too.
    source = f"""
    pushfd
    pushad
    cld
    xor eax, eax
    mov edi, {record_va + 4:#x}
    mov ecx, 23
    rep stosd
    mov dword ptr [{record_va + 4:#x}], {path_id}
    mov eax, dword ptr [esp + 0x24]
    mov dword ptr [{record_va + 8:#x}], eax
    mov ebx, dword ptr [esp + 0x2c]
    mov dword ptr [{record_va + 12:#x}], ebx
    mov eax, dword ptr [esp + 0x30]
    mov dword ptr [{record_va + 16:#x}], eax
    mov eax, dword ptr [esp + 0x34]
    mov dword ptr [{record_va + 20:#x}], eax
    mov dword ptr [{record_va + 92:#x}], 0xffffffff
    mov ecx, dword ptr [{exe_base.BATTLE_MANAGER_PTR:#x}]
    test ecx, ecx
    je skip_log
    test ebx, ebx
    je skip_log
    mov eax, dword ptr [ecx + 0x3c]
    mov dword ptr [{record_va + 24:#x}], eax
    mov eax, dword ptr [ecx + 0x40]
    mov dword ptr [{record_va + 28:#x}], eax
    mov eax, dword ptr [ecx + 0x44]
    mov dword ptr [{record_va + 32:#x}], eax
    mov eax, dword ptr [ecx + 0x48]
    mov dword ptr [{record_va + 36:#x}], eax
    mov eax, dword ptr [ecx + 0x132b8]
    mov dword ptr [{record_va + 40:#x}], eax
    mov eax, dword ptr [ecx + 0x132bc]
    mov dword ptr [{record_va + 44:#x}], eax
    mov eax, dword ptr [ecx + 0x132c0]
    mov dword ptr [{record_va + 48:#x}], eax
    mov eax, dword ptr [ecx + 0x132c8]
    mov dword ptr [{record_va + 52:#x}], eax
    mov eax, dword ptr [ecx + 0x13d6c]
    mov dword ptr [{record_va + 56:#x}], eax
    movzx eax, byte ptr [ecx + 0x14030]
    mov dword ptr [{record_va + 60:#x}], eax
    mov eax, dword ptr [ebx]
    mov dword ptr [{record_va + 64:#x}], eax
    mov eax, dword ptr [ebx + 0x34]
    mov dword ptr [{record_va + 68:#x}], eax
    mov eax, dword ptr [ebx + 0x5c]
    mov dword ptr [{record_va + 72:#x}], eax
    mov eax, dword ptr [ebx + 0x70]
    mov dword ptr [{record_va + 76:#x}], eax
    mov eax, dword ptr [ebx + 0xf4]
    mov dword ptr [{record_va + 80:#x}], eax
    mov edx, dword ptr [ebx + 0xf8]
    mov dword ptr [{record_va + 84:#x}], edx
    mov edx, dword ptr [ebx + 0x4ec]
    mov dword ptr [{record_va + 88:#x}], edx
    cmp eax, 1
    ja hero_done
    mov eax, dword ptr [ecx + eax*4 + 0x53cc]
    test eax, eax
    je hero_done
    mov eax, dword ptr [eax + 0x1a]
    mov dword ptr [{record_va + 92:#x}], eax
hero_done:
    mov eax, {exe_base.LOGGER_VA:#x}
    call eax
skip_log:
    popad
    popfd
    {native_tail}
    """
    return exe_base.assemble(source, wrapper_va), source.strip()


def build_cureui_payload(
    source_section: bytes,
    record_va: int,
) -> tuple[bytes, dict[str, Any]]:
    if len(source_section) != diag03.CUREUI_SIZE:
        raise RuntimeError("Unexpected .cureui section size")
    if any(source_section[diag03.PRESERVED_CUREUI_END:]):
        raise RuntimeError("Reserved .cureui diagnostic region is not empty")

    melee_native = f"""
    sub esp, 0x0c
    push ebx
    push ebp
    push esi
    jmp {diag03.HOTA_MELEE_CONTINUE_VA:#x}
    """
    melee_code, melee_source = build_callback_wrapper(
        wrapper_va=diag03.MELEE_WRAPPER_VA,
        path_id=5,
        record_va=record_va,
        native_tail=melee_native,
    )
    second_code, second_source = build_callback_wrapper(
        wrapper_va=diag03.SECOND_WRAPPER_VA,
        path_id=6,
        record_va=record_va,
        native_tail=f"jmp {diag03.SECOND_REPLAY_VA:#x}",
    )
    replay_rva = diag03.SECOND_REPLAY_VA - diag03.HOTA_IMAGE_BASE
    replay_source = f"""
    call base_here
base_here:
    pop eax
    sub eax, {replay_rva + 5:#x}
    mov eax, dword ptr [eax + {diag03.HOTA_GLOBAL_RVA:#x}]
    push ebx
    jmp {diag03.HOTA_SECOND_CONTINUE_VA:#x}
    """
    replay_code = exe_base.assemble(replay_source, diag03.SECOND_REPLAY_VA)

    slots = [
        ("action_callback_1", diag03.MELEE_WRAPPER_VA, diag03.SECOND_WRAPPER_VA,
         melee_code, melee_source),
        ("action_callback_2", diag03.SECOND_WRAPPER_VA, diag03.SECOND_REPLAY_VA,
         second_code, second_source),
        ("aslr_safe_second_replay", diag03.SECOND_REPLAY_VA,
         diag03.CUREUI_VA + diag03.CUREUI_SIZE, replay_code, replay_source.strip()),
    ]
    result = bytearray(source_section)
    components: list[dict[str, Any]] = []
    for name, va, limit, code, source in slots:
        if va + len(code) > limit:
            raise RuntimeError(f"{name} exceeds reserved .cureui slot")
        start = va - diag03.CUREUI_VA
        result[start:start + len(code)] = code
        components.append({
            "name": name,
            "preferred_va": f"0x{va:08X}",
            "length": len(code),
            "limit_preferred_va": f"0x{limit:08X}",
            "assembly": source,
        })
    return bytes(result), {
        "aslr_safe": True,
        "reuses_fixed_exe_logger": f"0x{exe_base.LOGGER_VA:08X}",
        "record_va": f"0x{record_va:08X}",
        "paths": {
            "5": "live HotA callback 1 with action-boundary fields",
            "6": "live HotA callback 2 with action-boundary fields",
        },
        "record_layout_paths_5_6": [
            "magic ATK1", "path", "callback caller return", "attacker",
            "target", "raw arg4", "battle action", "action parameter",
            "action target", "action parameter 2", "current monster side",
            "current monster index", "current active side", "active stack",
            "battle turn", "action-undergoing byte", "attackedAlready",
            "creature id", "stack slot", "native lucky flag", "effective side",
            "side index", "current luck", "side hero id or -1",
        ],
        "components": components,
    }


def installation_text() -> str:
    return f"""{BUILD_NAME} 行动边界诊断说明

DIAG03 已确认真实攻击回调和攻击方参数。本包只记录“当前行动部队、行动类型、攻击方槽位、幸运标志”等字段，用来区分主动攻击、反击，以及双射/环击在同一攻击指令内产生的多次回调。

本包不会强制幸运，也不会改变 V1.11 的伤害、攻击次数、英雄资料或任何既有功能。

安装：覆盖到纯净 HotA 1.8.0 中文版目录，使用 h3hota HD.exe 启动。

请尽量在同一场战斗完成：
1. 先让敌人攻击己方，使己方在自己行动前发生一次反击；
2. 让该己方部队完成第一次主动攻击；
3. 下一回合再主动攻击一次；
4. 再任选一次双射或环击（如测试图方便，两者都测也可以）。

退出游戏后上传根目录生成的 {LOG_FILENAME}。无需截图，也无需等待幸运自然触发。
"""


def main() -> int:
    # Reuse DIAG03's proven PE hooks, ASLR replay, rollback validation,
    # deterministic packaging and standard/HD build path.  Only the diagnostic
    # payload, filename, package name and instructions differ.
    diag03.BUILD_NAME = BUILD_NAME
    diag03.LOG_FILENAME = LOG_FILENAME
    diag03.build_cureui_payload = build_cureui_payload
    diag03.installation_text = installation_text
    return diag03.main()


if __name__ == "__main__":
    raise SystemExit(main())
