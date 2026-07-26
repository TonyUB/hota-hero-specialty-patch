#!/usr/bin/env python3
"""Build formal documentation-only HOTA_NEW_HERO_V1.11 from formal V1.1."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from build_hota_new_hero_v1 import (
    deterministic_zip,
    extract_zip_safely,
    safe_recreate_directory,
)


BUILD_NAME = "HOTA_NEW_HERO_V1.11"
SOURCE_NAME = "HOTA_NEW_HERO_V1.1"
SOURCE_ZIP_SHA256 = "4ea5e0549f591cb3b43fce2af621b0806ce7d6608c1f82eaa30525c1ec516883"
FORMULA_EXPRESSION = (
    "floor(((11L + 29) * (clamp(n,1,7) + 11)) / 12) "
    "+ 5 * (P - 1) + 10 * max(0, clamp(w,0,3) - 1)"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def installation_text() -> str:
    return f"""{BUILD_NAME} 安装与功能说明

适用版本：纯净 Heroes III HotA 1.8.0 中文版 + HD Mod。

安装方法：
1. 准备一份无其他平衡修改的纯净 HotA 1.8.0 游戏目录。
2. 将本压缩包内全部文件直接解压到游戏根目录。
3. 覆盖同名文件。
4. 使用 h3hota HD.exe 启动游戏。

V1.11 小版本说明：
- 调整 GitHub 门帘的幸运特长说明：两名英雄的特长效果只保留固定幸运 +3，厄运沙漏、诅咒之地等原生封锁改为分组共用的额外说明。
- 两名幸运英雄共用一条创作方向；尤兰德与阿斯特拉也改为共用一条创作方向。
- 游戏内特长文本、英雄数据、执行文件、DLL、LOD 和全部实际游戏机制与 V1.1 逐字节相同。

V1.1 幸运特长：
- 马洛迪亚与黛瑞丝所率领部队的幸运值始终为 +3，不受普通正负幸运数值影响。
- 厄运沙漏、诅咒之地等直接禁止幸运生效的原生效果仍然有效。
- 马洛迪亚初始技能为初级智慧术 + 初级神秘术；黛瑞丝保持初级智慧术 + 初级智力；两人的魔法书均初始自带振奋。

完整保留的其他功能：
- 埃尔芙的新英雄立绘、25/25/25 仙灵初始兵力，以及仙灵/妖精伤害 +1、速度 +1；
- 尤兰德、阿斯特拉的单体/群体治愈、永久复活、原生目标限制、治疗动画与音效、复活起身动作；
- 治愈战斗日志顺序、逐队治疗量、魔法书动态范围和存活目标精确悬停数值；
- 阿斯特拉的初级智慧术 + 初级水系魔法；
- 阿德拉及其他未列明英雄的 HotA 1.8.0 原生行为。

当前治愈总量公式：
H = floor(((11L + 29) × (n + 11)) / 12) + 5 × (P - 1) + 10 × max(0, w - 1)

L 为英雄等级（最低 1），P 为当前有效力量（最低 0），n 为目标生物等级（限定 1—7），w 为水系魔法熟练度（无/初级/中级/高级分别为 0/1/2/3）。

V1.11 除根目录安装说明外，包内全部文件与已验收的正式 V1.1 逐字节一致。
"""


def manifest_markdown(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 构建与发布记录

- 来源正式版：`{SOURCE_NAME}`
- 来源 ZIP SHA-256：`{SOURCE_ZIP_SHA256}`
- 输出 ZIP SHA-256：`{report['zip_sha256']}`
- 治愈公式：`{FORMULA_EXPRESSION}`

## 正式变更

1. GitHub 门帘中，马洛迪亚和黛瑞丝各自的特长效果只保留固定幸运 `+3`。
2. 厄运沙漏、诅咒之地等原生硬封锁说明移到两名幸运英雄共用的“额外说明”。
3. 两名幸运英雄共用一条创作方向；两名治愈英雄同样改为共用一条创作方向。
4. 中英文内容同步，下载链接更新到 V1.11。

## 文件边界

V1.11 是说明与发布结构小版本。补丁包内除根目录 `安装说明.txt` 外，两个 EXE、`HotA.dll`、`HotA.dat`、两份 LOD、中文 HeroSpec、立绘、HD DEF 和其他所有文件均与正式 V1.1 逐字节一致。

## 验证

- 来源 ZIP 哈希和成员集合已验证。
- 除安装说明外的全部包内文件逐一比较并确认与 V1.1 相同。
- ZIP CRC、逐文件清单和可复现构建通过。
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
    if sha256_file(source_zip) != SOURCE_ZIP_SHA256:
        raise RuntimeError(f"Formal {SOURCE_NAME} ZIP hash mismatch")

    package_root = build_root / BUILD_NAME
    safe_recreate_directory(package_root, build_root)
    extract_zip_safely(source_zip, package_root)
    source_files = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in sorted(item for item in package_root.rglob("*") if item.is_file())
    }
    instruction_files = [
        path for path in package_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    ]
    if len(instruction_files) != 1:
        raise RuntimeError("Expected exactly one root installation text file")
    instruction_relative = instruction_files[0].relative_to(package_root).as_posix()
    instruction_files[0].write_text(installation_text(), encoding="utf-8")

    package_files = sorted(item for item in package_root.rglob("*") if item.is_file())
    package_hashes = {
        path.relative_to(package_root).as_posix(): sha256_file(path)
        for path in package_files
    }
    if set(source_files) != set(package_hashes):
        raise RuntimeError("V1.11 package member set differs from V1.1")
    changed = {
        relative for relative in source_files
        if source_files[relative] != package_hashes[relative]
    }
    if changed != {instruction_relative}:
        raise RuntimeError(f"Unexpected V1.11 package changes: {sorted(changed)}")

    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = output_root / f"{BUILD_NAME}.zip"
    deterministic_zip(package_root, zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"V1.11 ZIP CRC failure: {failed}")
        if sorted(archive.namelist()) != sorted(package_hashes):
            raise RuntimeError("V1.11 ZIP member set changed")

    report = {
        "schema_version": 1,
        "build_name": BUILD_NAME,
        "formal_release": True,
        "documentation_only": True,
        "source_release": SOURCE_NAME,
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "zip_path": zip_path.name,
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "formula": FORMULA_EXPRESSION,
        "source_file_hashes": source_files,
        "package_file_hashes": package_hashes,
        "changed_package_files": sorted(changed),
        "gameplay_files_byte_identical_to_source": True,
        "readme_layout": {
            "luck_specialty_effect": "fixed Luck +3 only",
            "luck_additional_note": "shared by Melodia and Daremyth",
            "luck_creative_direction": "shared by Melodia and Daremyth",
            "cure_creative_direction": "shared by Uland and Astra",
            "languages": ["zh-CN", "en"],
        },
        "static_verification": {
            "formal_v11_source_hash_verified": True,
            "member_set_unchanged": True,
            "only_root_installation_text_changed": True,
            "all_gameplay_and_resource_files_match_v11": True,
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
    print(f"Changed package files: {sorted(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
