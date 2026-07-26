#!/usr/bin/env python3
"""Build formal HOTA_NEW_HERO_V1.1 from formal V1.06.

The gameplay executables and HeroSpec resources are byte-identical to the
user-accepted HOTA_NEW_HERO_V1.1_LUCK_TEST1.  Only the formal package name,
installation text, and release metadata differ from the accepted test build.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

import build_hota_new_hero_v11_luck_test1 as test1
from build_hota_new_hero_v1 import (
    EXE_NAMES,
    LANGUAGE_ARCHIVES,
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)


BUILD_NAME = "HOTA_NEW_HERO_V1.1"
ACCEPTED_TEST_NAME = test1.BUILD_NAME
ACCEPTED_TEST_ZIP_SHA256 = "d03fbb00abc4fe6be1105b811c3afd9aa82ed1761f63faed0781df18dc0dcc0f"
ACCEPTED_RUNTIME_HASHES = {
    "h3hota.exe": "2975214a0826067fbf59c03e896142ff14b48a882f8e8d678faa0aa5dff924e8",
    "h3hota HD.exe": "45965c8126c88d92232fcd09593e6c43decc6f50de9d979fb90343426efc1b1f",
    "Data/HotA_lng.lod": "a13335e146c0e7c1c370837f976552d07568c8b76d9af71a5d9ca671fc2b5048",
    "Data/HotA_l_ext.lod": "b09c25b5a8dfb39e288b17bda83a2e934bf92d45b87cba6c3b4255c6d0d7af97",
    test1.LOOSE_HEROSPEC_RELATIVE:
        "238761368de626ef842ef4eee5f5ee27df976a5ed43c94cc08a2c0c51f5c7b6b",
}
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

V1.1 新增幸运特长：
- 马洛迪亚与黛瑞丝所率领部队的幸运值始终为 +3，不受普通正负幸运数值影响。
- 厄运沙漏、诅咒之地等直接禁止幸运生效的原生效果仍然有效。
- 马洛迪亚初始技能改为初级智慧术 + 初级神秘术，魔法书初始自带振奋。
- 黛瑞丝初始技能保持初级智慧术 + 初级智力，魔法书初始自带振奋。
- 两人的幸运之神特长标签保留；其他英雄、全局幸运之神魔法和鹰眼术逻辑保持原版。

完整保留 V1.06：
- 埃尔芙的新英雄立绘、25/25/25 仙灵初始兵力，以及仙灵/妖精伤害 +1、速度 +1；
- 尤兰德、阿斯特拉的单体/群体治愈、永久复活、原生目标限制、治疗动画与音效、复活起身动作；
- 治愈战斗日志顺序、逐队治疗量、魔法书动态范围和存活目标精确悬停数值；
- 阿斯特拉的初级智慧术 + 初级水系魔法；
- 阿德拉及其他未列明英雄的 HotA 1.8.0 原生行为。

当前治愈总量公式：
H = floor(((11L + 29) × (n + 11)) / 12) + 5 × (P - 1) + 10 × max(0, w - 1)

L 为英雄等级（最低 1），P 为当前有效力量（最低 0），n 为目标生物等级（限定 1—7），w 为水系魔法熟练度（无/初级/中级/高级分别为 0/1/2/3）。

V1.1 幸运特长已完成用户实机验收。正式构建同时通过来源哈希、运行路径诊断、原生封锁边界、标准/HD Hook、英雄数据、资源白名单、完整回滚、ZIP CRC、可复现构建和启动门禁。
"""


def manifest_markdown(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 构建、验收与发布记录

- 来源正式版：`{test1.SOURCE_NAME}`
- 来源 ZIP SHA-256：`{test1.SOURCE_ZIP_SHA256}`
- 已验收测试版：`{ACCEPTED_TEST_NAME}`
- 测试版 ZIP SHA-256：`{ACCEPTED_TEST_ZIP_SHA256}`
- 输出 ZIP SHA-256：`{report['zip_sha256']}`
- 标准 EXE SHA-256：`{report['executables'][0]['output_sha256']}`
- HD EXE SHA-256：`{report['executables'][1]['output_sha256']}`
- 幸运负载 SHA-256：`{report['executables'][0]['new_section']['payload_sha256']}`
- 治愈公式：`{FORMULA_EXPRESSION}`

## 正式变更

1. 马洛迪亚（ID 29）与黛瑞丝（ID 43）在原生硬封锁未命中时，所率部队最终幸运值固定为 `+3`。
2. 厄运沙漏、诅咒之地及同类直接禁止幸运生效的原生返回分支保持不变。
3. 马洛迪亚初始技能改为初级智慧术 + 初级神秘术；黛瑞丝初始技能不变；两人初始法术均改为振奋。
4. 两份 HotA LOD 和中文 HD 覆盖资源同步更新两人的特长详细说明。
5. 全局幸运之神魔法、鹰眼术、其他英雄以及 V1.06 的全部治愈/复活内容保持不变。

## 运行路径与边界

诊断日志包含 720 条完整记录，普通战斗入口/封锁后记录各 360 条且全部配对。功能 Hook 位于 `0x004E39E8`，在己/敌双方厄运沙漏扫描与原生返回 0 分支之后。标准版与 HD 版使用相同 `.luck3` 独立节负载。

相较 V1.06，只修改两个 EXE、两份 LOD、中文 HD 覆盖 HeroSpec 和根目录安装说明。正式版的两个 EXE 与三份 HeroSpec 资源均和用户验收通过的测试版逐字节一致。

## 验收

- 用户实机确认：幸运特长已经在游戏内生效，同意发布大版本并在后续小版本继续反馈问题。
- 构建门禁：来源哈希、Hook/英雄记录、原生封锁字节、资源成员边界、完整回滚、变更白名单、ZIP CRC、三次可复现构建和隔离启动均通过。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--accepted-test-zip", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_zip = args.source_zip.resolve()
    accepted_test_zip = args.accepted_test_zip.resolve()
    build_root = args.build_root.resolve()
    output_root = args.output_root.resolve()
    if test1.sha256_file(source_zip) != test1.SOURCE_ZIP_SHA256:
        raise RuntimeError(f"Formal {test1.SOURCE_NAME} ZIP hash mismatch")
    if test1.sha256_file(accepted_test_zip) != ACCEPTED_TEST_ZIP_SHA256:
        raise RuntimeError(f"Accepted {ACCEPTED_TEST_NAME} ZIP hash mismatch")

    accepted_root = build_root / "accepted_test"
    safe_recreate_directory(accepted_root, build_root)
    extract_zip_safely(accepted_test_zip, accepted_root)
    for relative, expected in ACCEPTED_RUNTIME_HASHES.items():
        if test1.sha256_file(accepted_root / relative) != expected:
            raise RuntimeError(f"Accepted runtime/resource hash mismatch: {relative}")

    section_payload, payload_meta = test1.build_luck_payload()
    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_files = {
        path.relative_to(package_root).as_posix(): test1.sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    executable_reports = [
        test1.patch_executable(package_root / name, section_payload, payload_meta)
        for name in EXE_NAMES
    ]
    lod_reports = [test1.patch_lod(package_root / relative) for relative in LANGUAGE_ARCHIVES]
    loose_report = test1.patch_loose_herospec(
        package_root / test1.LOOSE_HEROSPEC_RELATIVE, package_root
    )
    for relative, expected in ACCEPTED_RUNTIME_HASHES.items():
        actual = test1.sha256_file(package_root / relative)
        if actual != expected or (package_root / relative).read_bytes() != (accepted_root / relative).read_bytes():
            raise RuntimeError(f"Formal file differs from accepted test: {relative}")

    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("Expected exactly one root installation text file")
    instruction_files[0].write_text(installation_text(), encoding="utf-8")

    package_files = sorted(item for item in package_root.rglob("*") if item.is_file())
    package_hashes = {
        path.relative_to(package_root).as_posix(): test1.sha256_file(path)
        for path in package_files
    }
    accepted_files = {
        path.relative_to(accepted_root).as_posix(): path
        for path in accepted_root.rglob("*") if path.is_file()
    }
    root_text_relative = instruction_files[0].relative_to(package_root).as_posix()
    if set(accepted_files) != set(package_hashes):
        raise RuntimeError("Formal and accepted-test member sets differ")
    for relative, accepted_path in accepted_files.items():
        if relative == root_text_relative:
            continue
        if (package_root / relative).read_bytes() != accepted_path.read_bytes():
            raise RuntimeError(f"Formal non-instruction file differs from accepted test: {relative}")
    changed = {
        relative for relative, digest in package_hashes.items()
        if source_files.get(relative) != digest
    }
    allowed = (
        set(EXE_NAMES)
        | set(LANGUAGE_ARCHIVES)
        | {test1.LOOSE_HEROSPEC_RELATIVE, instruction_files[0].name}
    )
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
        "source_release": test1.SOURCE_NAME,
        "source_zip_sha256": test1.SOURCE_ZIP_SHA256,
        "accepted_test": ACCEPTED_TEST_NAME,
        "accepted_test_zip_sha256": ACCEPTED_TEST_ZIP_SHA256,
        "accepted_runtime_hashes": ACCEPTED_RUNTIME_HASHES,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": test1.sha256_file(zip_path),
        "formula": FORMULA_EXPRESSION,
        "source_file_hashes": source_files,
        "package_file_hashes": package_hashes,
        "changed_package_files": sorted(changed),
        "executables": executable_reports,
        "resources": lod_reports + [loose_report],
        "runtime_acceptance": {
            "status": "passed by user",
            "accepted_items": [
                "fixed final Luck +3 for Melodia and Daremyth",
                "Melodia Basic Wisdom plus Basic Mysticism",
                "Daremyth native starting skills",
                "both spell books start with Mirth",
                "updated in-game specialty descriptions",
            ],
            "follow_up": "future bug reports will be handled as small-version updates",
        },
        "static_verification": {
            "formal_v106_source_hashes_verified": True,
            "runtime_and_resources_match_accepted_test": True,
            "all_non_instruction_package_files_match_accepted_test": True,
            "standard_and_hd_receive_identical_payload": True,
            "native_hard_suppression_precedes_hook": True,
            "hero_records_exact_source_and_output_verified": True,
            "full_executable_rollback_passed": True,
            "resource_replacement_count_exactly_two_per_source": True,
            "only_expected_package_files_changed": True,
            "zip_crc_and_member_checks_passed": True,
        },
    }
    (output_root / f"{BUILD_NAME}_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / f"{BUILD_NAME}_manifest.md").write_text(
        manifest_markdown(report), encoding="utf-8"
    )
    (output_root / f"{BUILD_NAME}_README.md").write_text(
        installation_text(), encoding="utf-8"
    )
    print(f"Built {zip_path}")
    print(f"ZIP SHA-256: {report['zip_sha256']}")
    for item in executable_reports:
        print(f"{item['name']}: {item['output_sha256']}")
    print("Accepted gameplay/resource files: byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
