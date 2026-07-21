#!/usr/bin/env python3
"""Generate reproducible PE inventories and static candidate-address evidence.

This tool intentionally does not patch binaries. Historical addresses are treated as
search anchors only; its output is static evidence, never proof of runtime execution.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import capstone
import pefile
from capstone.x86_const import X86_OP_IMM


CANDIDATE_VAS: tuple[tuple[str, int], ...] = (
    ("H3CombatCreature::ApplySpell (historical)", 0x00444610),
    ("Cure core (historical candidate)", 0x00446220),
    ("Cure injection point (historical candidate)", 0x0044632D),
    ("H3Hero::CalculateSpellCost (historical)", 0x004E54B0),
    ("H3CombatManager::CastSpell (historical)", 0x005A0140),
    ("H3CombatManager::GetResurrectionTarget (historical)", 0x005A3FD0),
    ("H3CombatManager::ResurrectTarget (historical)", 0x005A7870),
    ("Existing patch/code-cave risk area", 0x00639D00),
    ("Historical crash address", 0x0069124C),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_ascii(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.rstrip(b"\0").decode("ascii", errors="replace")


def section_for_rva(pe: pefile.PE, rva: int) -> pefile.SectionStructure | None:
    for section in pe.sections:
        start = section.VirtualAddress
        end = start + max(section.Misc_VirtualSize, section.SizeOfRawData)
        if start <= rva < end:
            return section
    return None


def section_for_offset(pe: pefile.PE, offset: int) -> pefile.SectionStructure | None:
    for section in pe.sections:
        start = section.PointerToRawData
        end = start + section.SizeOfRawData
        if start <= offset < end:
            return section
    return None


def offset_mapping(pe: pefile.PE, offset: int) -> dict[str, Any]:
    section = section_for_offset(pe, offset)
    if section is None:
        return {"file_offset": offset, "section": None, "rva": None, "va": None}
    rva = section.VirtualAddress + offset - section.PointerToRawData
    return {
        "file_offset": offset,
        "section": decode_ascii(section.Name),
        "rva": rva,
        "va": pe.OPTIONAL_HEADER.ImageBase + rva,
    }


def disassemble_at(pe: pefile.PE, va: int, byte_count: int = 96) -> dict[str, Any]:
    image_base = pe.OPTIONAL_HEADER.ImageBase
    rva = va - image_base
    section = section_for_rva(pe, rva)
    if rva < 0 or section is None:
        return {
            "present": False,
            "va": va,
            "rva": rva,
            "reason": "address is not mapped by a PE section",
        }

    try:
        file_offset = pe.get_offset_from_rva(rva)
    except pefile.PEFormatError as exc:
        return {
            "present": False,
            "va": va,
            "rva": rva,
            "reason": str(exc),
        }

    data = pe.__data__[file_offset : file_offset + byte_count]
    engine = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    instructions = [
        {
            "address": instruction.address,
            "size": instruction.size,
            "bytes": instruction.bytes.hex(" "),
            "mnemonic": instruction.mnemonic,
            "operands": instruction.op_str,
        }
        for instruction in engine.disasm(data, va)
    ]
    return {
        "present": True,
        "va": va,
        "rva": rva,
        "file_offset": file_offset,
        "section": decode_ascii(section.Name),
        "sample_size": len(data),
        "sample_sha256": sha256_bytes(data),
        "sample_hex": data.hex(" "),
        "instructions": instructions,
    }


def direct_xrefs(pe: pefile.PE) -> dict[int, list[dict[str, Any]]]:
    targets = {va for _, va in CANDIDATE_VAS}
    references: dict[int, list[dict[str, Any]]] = {target: [] for target in targets}
    engine = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    engine.detail = True
    engine.skipdata = True

    for section in pe.sections:
        if not section.Characteristics & 0x20000000:  # IMAGE_SCN_MEM_EXECUTE
            continue
        section_va = pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress
        for instruction in engine.disasm(section.get_data(), section_va):
            if instruction.id == 0:
                continue
            if instruction.mnemonic != "call" and not instruction.mnemonic.startswith("j"):
                continue
            if not instruction.operands or instruction.operands[0].type != X86_OP_IMM:
                continue
            target = instruction.operands[0].imm
            if target not in targets:
                continue
            references[target].append(
                {
                    "address": instruction.address,
                    "mnemonic": instruction.mnemonic,
                    "operands": instruction.op_str,
                    "bytes": instruction.bytes.hex(" "),
                }
            )
    return references


def file_version(pe: pefile.PE) -> dict[str, Any] | None:
    if not getattr(pe, "VS_FIXEDFILEINFO", None):
        return None
    info = pe.VS_FIXEDFILEINFO[0]
    return {
        "file_version": (
            f"{info.FileVersionMS >> 16}.{info.FileVersionMS & 0xFFFF}."
            f"{info.FileVersionLS >> 16}.{info.FileVersionLS & 0xFFFF}"
        ),
        "product_version": (
            f"{info.ProductVersionMS >> 16}.{info.ProductVersionMS & 0xFFFF}."
            f"{info.ProductVersionLS >> 16}.{info.ProductVersionLS & 0xFFFF}"
        ),
        "file_flags": info.FileFlags,
        "file_type": info.FileType,
    }


def inventory(path: Path) -> tuple[pefile.PE, dict[str, Any]]:
    pe = pefile.PE(str(path), fast_load=False)
    timestamp = dt.datetime.fromtimestamp(
        pe.FILE_HEADER.TimeDateStamp, tz=dt.timezone.utc
    ).isoformat()

    sections = []
    for section in pe.sections:
        data = section.get_data()
        sections.append(
            {
                "name": decode_ascii(section.Name),
                "rva": section.VirtualAddress,
                "virtual_size": section.Misc_VirtualSize,
                "raw_offset": section.PointerToRawData,
                "raw_size": section.SizeOfRawData,
                "characteristics": f"0x{section.Characteristics:08X}",
                "entropy": round(section.get_entropy(), 6),
                "sha256": sha256_bytes(data),
            }
        )

    imports: list[dict[str, Any]] = []
    for descriptor in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        symbols = []
        for imported in descriptor.imports:
            symbols.append(
                {
                    "name": decode_ascii(imported.name) if imported.name else None,
                    "ordinal": imported.ordinal,
                    "address": imported.address,
                }
            )
        imports.append({"dll": decode_ascii(descriptor.dll), "symbols": symbols})

    xrefs = direct_xrefs(pe)
    candidates = []
    for label, va in CANDIDATE_VAS:
        evidence = disassemble_at(pe, va)
        evidence["label"] = label
        evidence["direct_xrefs"] = xrefs[va]
        candidates.append(evidence)

    result = {
        "path": path.as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "machine": f"0x{pe.FILE_HEADER.Machine:04X}",
        "timestamp_utc": timestamp,
        "image_base": pe.OPTIONAL_HEADER.ImageBase,
        "entrypoint_rva": pe.OPTIONAL_HEADER.AddressOfEntryPoint,
        "entrypoint_va": pe.OPTIONAL_HEADER.ImageBase
        + pe.OPTIONAL_HEADER.AddressOfEntryPoint,
        "size_of_image": pe.OPTIONAL_HEADER.SizeOfImage,
        "checksum": f"0x{pe.OPTIONAL_HEADER.CheckSum:08X}",
        "calculated_checksum": f"0x{pe.generate_checksum():08X}",
        "overlay_offset": pe.get_overlay_data_start_offset(),
        "version": file_version(pe),
        "sections": sections,
        "imports": imports,
        "candidates": candidates,
    }
    return pe, result


def contiguous_differences(left: bytes, right: bytes) -> tuple[int, list[tuple[int, int]]]:
    ranges: list[tuple[int, int]] = []
    differing_bytes = 0
    start: int | None = None
    maximum = max(len(left), len(right))
    for index in range(maximum):
        different = index >= len(left) or index >= len(right) or left[index] != right[index]
        if different:
            differing_bytes += 1
            if start is None:
                start = index
        elif start is not None:
            ranges.append((start, index))
            start = None
    if start is not None:
        ranges.append((start, maximum))
    return differing_bytes, ranges


def compare_files(
    left_path: Path,
    right_path: Path,
    left_pe: pefile.PE,
    right_pe: pefile.PE,
) -> dict[str, Any]:
    left = left_path.read_bytes()
    right = right_path.read_bytes()
    differing_bytes, ranges = contiguous_differences(left, right)
    details = []
    for start, end in ranges:
        details.append(
            {
                "start_offset": start,
                "end_offset_exclusive": end,
                "length": end - start,
                "left_mapping": offset_mapping(left_pe, start),
                "right_mapping": offset_mapping(right_pe, start),
                "left_hex": left[start:end].hex(" "),
                "right_hex": right[start:end].hex(" "),
            }
        )
    return {
        "left": left_path.as_posix(),
        "right": right_path.as_posix(),
        "same_size": len(left) == len(right),
        "left_size": len(left),
        "right_size": len(right),
        "differing_bytes": differing_bytes,
        "range_count": len(ranges),
        "ranges": details,
    }


def hex_value(value: int | None) -> str:
    return "—" if value is None else f"0x{value:08X}"


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Patch_v1.8 PE 静态清单",
        "",
        "> 证据等级：静态候选。此报告不能证明 HotA 1.8.0 运行时执行这些地址。",
        "",
        "## 输入",
        "",
        "| 文件 | 大小 | SHA-256 | ImageBase | EntryPoint |",
        "|---|---:|---|---:|---:|",
    ]
    for binary in report["binaries"]:
        lines.append(
            f"| `{Path(binary['path']).name}` | {binary['size']} | `{binary['sha256']}` "
            f"| `{hex_value(binary['image_base'])}` | `{hex_value(binary['entrypoint_va'])}` |"
        )

    comparison = report["comparison"]
    lines.extend(
        [
            "",
            "## 标准版与 HD 版差异",
            "",
            f"两个文件大小{'相同' if comparison['same_size'] else '不同'}；共有 "
            f"**{comparison['differing_bytes']}** 个不同字节，分布在 "
            f"**{comparison['range_count']}** 个连续区间。",
            "",
            "| 文件偏移 | 长度 | 节区 | VA | 标准版字节 | HD 版字节 |",
            "|---:|---:|---|---:|---|---|",
        ]
    )
    for item in comparison["ranges"]:
        mapping = item["left_mapping"]
        lines.append(
            f"| `{hex_value(item['start_offset'])}` | {item['length']} | "
            f"`{mapping['section'] or 'overlay'}` | `{hex_value(mapping['va'])}` | "
            f"`{item['left_hex']}` | `{item['right_hex']}` |"
        )

    for binary in report["binaries"]:
        name = Path(binary["path"]).name
        lines.extend(
            [
                "",
                f"## {name}",
                "",
                f"- PE 时间戳（UTC）：`{binary['timestamp_utc']}`",
                f"- SizeOfImage：`{hex_value(binary['size_of_image'])}`",
                f"- Header checksum：`{binary['checksum']}`",
                f"- Calculated checksum：`{binary['calculated_checksum']}`",
                f"- Overlay offset：`{hex_value(binary['overlay_offset'])}`",
                "",
                "### 节区",
                "",
                "| 名称 | RVA | VirtualSize | RawOffset | RawSize | Entropy | SHA-256 |",
                "|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for section in binary["sections"]:
            lines.append(
                f"| `{section['name']}` | `{hex_value(section['rva'])}` | "
                f"`{hex_value(section['virtual_size'])}` | `{hex_value(section['raw_offset'])}` | "
                f"`{hex_value(section['raw_size'])}` | {section['entropy']:.6f} | "
                f"`{section['sha256']}` |"
            )

        lines.extend(["", "### 导入模块", ""])
        lines.append(
            ", ".join(f"`{entry['dll']}`" for entry in binary["imports"]) or "无"
        )

        lines.extend(["", "### 历史候选地址", ""])
        for candidate in binary["candidates"]:
            lines.append(f"#### {candidate['label']} — `{hex_value(candidate['va'])}`")
            lines.append("")
            if not candidate["present"]:
                lines.append(f"未映射：{candidate['reason']}")
                lines.append("")
                continue
            lines.append(
                f"节区 `{candidate['section']}`，RVA `{hex_value(candidate['rva'])}`，"
                f"文件偏移 `{hex_value(candidate['file_offset'])}`。"
            )
            xref_text = ", ".join(
                f"`{hex_value(reference['address'])}` ({reference['mnemonic']})"
                for reference in candidate["direct_xrefs"]
            )
            lines.append(
                f"静态直接引用：{xref_text if xref_text else '未发现；可能经跳转表或间接调用到达'}。"
            )
            lines.extend(["", "```asm"])
            for instruction in candidate["instructions"][:12]:
                lines.append(
                    f"{instruction['address']:08X}  {instruction['bytes']:<24} "
                    f"{instruction['mnemonic']} {instruction['operands']}".rstrip()
                )
            lines.extend(["```", ""])

    lines.extend(
        [
            "## 当前结论边界",
            "",
            "- 本报告只能说明磁盘文件在这些地址存在何种字节和静态指令。",
            "- 没有纯净 HotA 1.8.0 EXE 时，不能判断这些字节属于官方版本还是 Patch_v1.8 修改。",
            "- 没有 HotA/HD DLL、patcher 和动态命中证据时，不能判断游戏运行时是否执行、覆盖或绕开这些代码。",
            "- 在诊断日志经实机确认前，不得基于本报告注入复活逻辑。",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path, help="standard h3hota.exe")
    parser.add_argument("right", type=Path, help="h3hota HD.exe")
    parser.add_argument("--json", dest="json_path", type=Path, required=True)
    parser.add_argument("--markdown", dest="markdown_path", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    left_pe, left_inventory = inventory(args.left)
    right_pe, right_inventory = inventory(args.right)
    report = {
        "schema_version": 1,
        "evidence_level": "static_candidate_only",
        "tool_versions": {
            "pefile": pefile.__version__,
            "capstone": capstone.__version__,
        },
        "binaries": [left_inventory, right_inventory],
        "comparison": compare_files(args.left, args.right, left_pe, right_pe),
    }

    args.json_path.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_path.parent.mkdir(parents=True, exist_ok=True)
    args.json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.markdown_path.write_text(markdown_report(report), encoding="utf-8")
    print(f"Wrote {args.json_path}")
    print(f"Wrote {args.markdown_path}")
    print(
        f"Compared {report['comparison']['differing_bytes']} differing bytes across "
        f"{report['comparison']['range_count']} ranges"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
