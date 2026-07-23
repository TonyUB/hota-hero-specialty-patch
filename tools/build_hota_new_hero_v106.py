#!/usr/bin/env python3
"""Build formal HOTA_NEW_HERO_V1.06 from formal V1.05.

The runtime HotA.dll payload is byte-identical to the user-accepted
HOTA_NEW_HERO_V1.06_UI_TEST2. Only formal naming, installation text and release
metadata differ from the test package.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

import build_hota_new_hero_v106_ui_test2 as test2
from build_hota_new_hero_v1 import deterministic_zip, extract_zip_safely, safe_recreate_directory


BUILD_NAME = "HOTA_NEW_HERO_V1.06"
ACCEPTED_TEST_NAME = "HOTA_NEW_HERO_V1.06_UI_TEST2"
ACCEPTED_TEST_ZIP_SHA256 = "bd9e7ef9c990c0d8a9232b187b586371afc8b25c8b78027cc8c914ee1adf8f83"
ACCEPTED_HOTA_DLL_SHA256 = "2b642ae18c3b4dcc074092c45f725a81d4c21e27868cb5a0c67c9df6e05ed2b9"
FORMULA_EXPRESSION = (
    "floor(((11L + 29) * (clamp(n,1,7) + 11)) / 12) "
    "+ 5 * (P - 1) + 10 * max(0, clamp(w,0,3) - 1)"
)


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与功能说明

适用版本：纯净 Heroes III HotA 1.8.0 中文版 + HD Mod。

安装方法：
1. 准备一份无其他平衡修改的纯净 HotA 1.8.0 游戏目录。
2. 将本压缩包内全部文件直接解压到游戏根目录。
3. 覆盖同名文件。
4. 使用 h3hota HD.exe 启动游戏。

V1.06 更新：
- 尤兰德、阿斯特拉把治愈术指向存活友方兵队时，底部“治疗点数”按目标实际兵种等级和正式 F7 公式显示。
- 两名英雄的魔法书治愈说明显示当前1—7级生物的治疗量范围；例如 L=1、P=1、无/初级水系时显示40-60。
- 普通英雄继续显示 HotA 1.8.0 原版治愈数值。
- 尸体悬停仍只显示“治愈”；实际永久复活效果保持不变。

当前治愈总量公式：
H = floor(((11L + 29) × (n + 11)) / 12) + 5 × (P - 1) + 10 × max(0, w - 1)

L 为英雄等级（最低1），P 为当前有效力量（最低0），n 为目标生物等级（限定1—7），w 为水系魔法熟练度（无/初级/中级/高级分别为0/1/2/3）。全部使用整数运算；主乘积除以12后向下取整，再增加力量项与水系项。

完整保留：
- 埃尔芙的新英雄立绘、25/25/25仙灵初始兵力，以及仙灵/妖精伤害+1、速度+1；
- 尤兰德、阿斯特拉的单体/群体治愈、永久复活、原生目标限制、治疗动画与音效、复活起身动作；
- 战斗日志顺序与逐队“兵种名获得数值点治疗。”提示；
- 阿斯特拉的初级智慧术 + 初级水系魔法；
- 阿德拉及其他未列明英雄的 HotA 1.8.0 原生行为。

本版的活体悬停精确值、魔法书动态范围及继承功能已经完成用户实机验收。构建同时通过来源哈希、F7 双计算器、ASLR 安全、新节边界、Hook、回滚、ZIP CRC、可复现构建和启动门禁。
"""


def manifest_markdown(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 构建、验收与发布记录

- 来源正式版：`{test2.SOURCE_NAME}`
- 来源 ZIP SHA-256：`{test2.SOURCE_ZIP_SHA256}`
- 已验收测试版：`{ACCEPTED_TEST_NAME}`
- 测试版 ZIP SHA-256：`{ACCEPTED_TEST_ZIP_SHA256}`
- 输出 ZIP SHA-256：`{report['zip_sha256']}`
- `HotA.dll` SHA-256：`{report['hota_dll']['output_sha256']}`
- 公式：`{FORMULA_EXPRESSION}`

## 正式变更

1. 尤兰德/阿斯特拉的存活目标悬停治疗点数改用目标实际等级的 F7 总量。
2. 两名英雄的魔法书以当前本地化句式显示1—7级目标的动态范围。
3. 普通英雄、尸体悬停、实际治疗/复活、战斗日志、动画、音效和所有其他资源保持正式 V1.05 行为。

## 文件边界

相较 V1.05，包内只有 `HotA.dll` 与根目录安装说明变化；两个 EXE 与其 F7 计算器逐字节保持不变。正式 `HotA.dll` 与用户验收通过的 UI_TEST2 完全相同。

## 验收

- 用户实机确认：魔法书范围、存活目标分级悬停值及全部相关功能均正确。
- 静态/构建门禁：来源哈希、F7 计算器、HotA Hook、新节/ASLR、完整回滚、变更白名单、ZIP CRC、二次可复现构建和标准启动均通过。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_zip = args.source_zip.resolve()
    build_root = args.build_root.resolve()
    output_root = args.output_root.resolve()
    if test2.sha256_file(source_zip) != test2.SOURCE_ZIP_SHA256:
        raise RuntimeError(f"Accepted {test2.SOURCE_NAME} ZIP hash mismatch")

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_files = {
        path.relative_to(package_root).as_posix(): test2.sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    exe_hashes = test2.validate_formula_helpers(package_root)
    dll_report = test2.patch_hota_dll(package_root / test2.HOTA_DLL_NAME)
    if dll_report["output_sha256"] != ACCEPTED_HOTA_DLL_SHA256:
        raise RuntimeError("Formal runtime HotA.dll differs from accepted UI_TEST2")

    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("Expected exactly one root installation text file")
    instruction_files[0].write_text(installation_text(), encoding="utf-8")

    package_files = sorted(item for item in package_root.rglob("*") if item.is_file())
    package_hashes = {
        path.relative_to(package_root).as_posix(): test2.sha256_file(path)
        for path in package_files
    }
    changed = {
        relative for relative, digest in package_hashes.items()
        if source_files.get(relative) != digest
    }
    allowed = {test2.HOTA_DLL_NAME, instruction_files[0].name}
    if changed != allowed:
        raise RuntimeError(f"Unexpected package changes: {sorted(changed)}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Formal ZIP failed CRC validation")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("Formal ZIP member set changed")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "formal_release": True,
        "source_release": test2.SOURCE_NAME,
        "source_zip_sha256": test2.SOURCE_ZIP_SHA256,
        "accepted_test": ACCEPTED_TEST_NAME,
        "accepted_test_zip_sha256": ACCEPTED_TEST_ZIP_SHA256,
        "accepted_hota_dll_sha256": ACCEPTED_HOTA_DLL_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": test2.sha256_file(zip_path),
        "formula": FORMULA_EXPRESSION,
        "source_file_hashes": source_files,
        "package_file_hashes": package_hashes,
        "changed_package_files": sorted(changed),
        "formal_exe_hashes_and_f7_helpers_verified": exe_hashes,
        "hota_dll": dll_report,
        "runtime_acceptance": {
            "status": "passed by user",
            "accepted_items": [
                "localized Cure spell-book dynamic tier-1..tier-7 range",
                "living-target exact F7 hover values",
                "ordinary hero native Cure UI",
                "inherited treatment, permanent resurrection, logs, visuals and audio",
            ],
            "corpse_hover": "intentionally unchanged; Cure text only",
        },
        "static_verification": {
            "formal_v105_source_hashes_verified": True,
            "formal_f7_total_and_ui_helpers_verified_in_both_exes": True,
            "runtime_hota_dll_matches_accepted_test": True,
            "new_section_added_at_exact_image_boundary": True,
            "aslr_safe_relative_hota_internal_transfers": True,
            "hook_sources_and_targets_verified": True,
            "full_header_hooks_size_rollback_passed": True,
            "only_hota_dll_and_installation_text_changed": True,
            "zip_crc_and_member_checks_passed": True,
        },
    }
    manifest_json = output_root / f"{BUILD_NAME}_manifest.json"
    manifest_md = output_root / f"{BUILD_NAME}_manifest.md"
    readme = output_root / f"{BUILD_NAME}_README.md"
    manifest_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest_md.write_text(manifest_markdown(report), encoding="utf-8")
    readme.write_text(installation_text(), encoding="utf-8")
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    print(f"HotA.dll: {dll_report['output_sha256']}")
    print(f"Accepted runtime payload: {dll_report['output_sha256'] == ACCEPTED_HOTA_DLL_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
