#!/usr/bin/env python3
"""Inventory HotA/HD runtime DLLs and search for EXE patching evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import struct
from pathlib import Path
from typing import Any

import pefile

from analyze_pe import decode_ascii, file_version, hex_value, sha256_file


CANDIDATE_VAS: tuple[tuple[str, int], ...] = (
    ("CureCore", 0x00446220),
    ("Cure single call", 0x005A1B05),
    ("Cure mass call", 0x005A1BB4),
    ("GetResurrectionTarget", 0x005A3FD0),
    ("ResurrectTarget", 0x005A7870),
    ("Patch cave start", 0x00639D00),
    ("Adela cave start", 0x00639D40),
)

SIGNATURE_VAS: tuple[tuple[str, int, int], ...] = (
    ("CureCore prologue", 0x00446220, 32),
    ("Cure single call context", 0x005A1AFA, 32),
    ("Cure mass call context", 0x005A1BA9, 32),
    ("GetResurrectionTarget prologue", 0x005A3FD0, 32),
    ("ResurrectTarget prologue", 0x005A7870, 32),
)

PATCHING_APIS = {
    "createfilea",
    "createfilew",
    "flushinstructioncache",
    "getmodulehandlea",
    "getmodulehandlew",
    "getprocaddress",
    "loadlibrarya",
    "loadlibraryw",
    "mapviewoffile",
    "ntprotectvirtualmemory",
    "openprocess",
    "outputdebugstringa",
    "outputdebugstringw",
    "readprocessmemory",
    "virtualalloc",
    "virtualallocex",
    "virtualprotect",
    "virtualprotectex",
    "writefile",
    "writeprocessmemory",
}

STRING_KEYWORDS = (
    "h3hota",
    "hota",
    "patch",
    "hook",
    "cure",
    "resur",
    "spell",
    "virtualprotect",
    "writeprocessmemory",
    "outputdebugstring",
    ".ini",
    ".log",
)


def occurrences(data: bytes, needle: bytes) -> list[int]:
    result = []
    start = 0
    while True:
        index = data.find(needle, start)
        if index < 0:
            return result
        result.append(index)
        start = index + 1


def relevant_strings(data: bytes) -> tuple[int, list[dict[str, Any]]]:
    found: list[tuple[int, str, str]] = []
    total = 0
    for match in re.finditer(rb"[\x20-\x7E]{5,}", data):
        total += 1
        value = match.group().decode("ascii", errors="replace")
        if any(keyword in value.lower() for keyword in STRING_KEYWORDS):
            found.append((match.start(), "ascii", value))
    for match in re.finditer(rb"(?:[\x20-\x7E]\x00){5,}", data):
        total += 1
        value = match.group().decode("utf-16le", errors="replace")
        if any(keyword in value.lower() for keyword in STRING_KEYWORDS):
            found.append((match.start(), "utf16le", value))

    unique = []
    seen: set[tuple[int, str, str]] = set()
    for offset, encoding, value in sorted(found):
        key = (offset, encoding, value)
        if key in seen:
            continue
        seen.add(key)
        unique.append({"offset": offset, "encoding": encoding, "value": value})
    return total, unique


def reference_signatures(reference_exe: Path) -> dict[str, bytes]:
    data = reference_exe.read_bytes()
    pe = pefile.PE(str(reference_exe), fast_load=False)
    signatures = {}
    for label, va, size in SIGNATURE_VAS:
        rva = va - pe.OPTIONAL_HEADER.ImageBase
        offset = pe.get_offset_from_rva(rva)
        signatures[label] = data[offset : offset + size]
    return signatures


def inventory(path: Path, signatures: dict[str, bytes]) -> dict[str, Any]:
    data = path.read_bytes()
    pe = pefile.PE(str(path), fast_load=False)
    imports = []
    patching_imports = []
    for descriptor in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        dll = decode_ascii(descriptor.dll)
        symbols = []
        for imported in descriptor.imports:
            name = decode_ascii(imported.name) if imported.name else None
            symbols.append(
                {
                    "name": name,
                    "ordinal": imported.ordinal,
                    "iat_va": imported.address,
                }
            )
            if name and name.lower() in PATCHING_APIS:
                patching_imports.append(
                    {"dll": dll, "name": name, "iat_va": imported.address}
                )
        imports.append({"dll": dll, "symbols": symbols})

    exports = []
    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            exports.append(
                {
                    "name": decode_ascii(symbol.name) if symbol.name else None,
                    "ordinal": symbol.ordinal,
                    "rva": symbol.address,
                    "va": pe.OPTIONAL_HEADER.ImageBase + symbol.address,
                }
            )

    literal_hits = []
    for label, va in CANDIDATE_VAS:
        hits = occurrences(data, struct.pack("<I", va))
        if hits:
            literal_hits.append({"label": label, "va": va, "file_offsets": hits})

    signature_hits = []
    for label, signature in signatures.items():
        hits = occurrences(data, signature)
        if hits:
            signature_hits.append(
                {"label": label, "length": len(signature), "file_offsets": hits}
            )

    string_count, strings = relevant_strings(data)
    timestamp = dt.datetime.fromtimestamp(
        pe.FILE_HEADER.TimeDateStamp, tz=dt.timezone.utc
    ).isoformat()
    return {
        "path": path.as_posix(),
        "size": len(data),
        "sha256": sha256_file(path),
        "machine": f"0x{pe.FILE_HEADER.Machine:04X}",
        "timestamp_utc": timestamp,
        "image_base": pe.OPTIONAL_HEADER.ImageBase,
        "entrypoint_va": pe.OPTIONAL_HEADER.ImageBase
        + pe.OPTIONAL_HEADER.AddressOfEntryPoint,
        "version": file_version(pe),
        "sections": [
            {
                "name": decode_ascii(section.Name),
                "rva": section.VirtualAddress,
                "virtual_size": section.Misc_VirtualSize,
                "raw_offset": section.PointerToRawData,
                "raw_size": section.SizeOfRawData,
                "characteristics": f"0x{section.Characteristics:08X}",
                "entropy": round(section.get_entropy(), 6),
            }
            for section in pe.sections
        ],
        "imports": imports,
        "patching_related_imports": patching_imports,
        "exports": exports,
        "candidate_address_literal_hits": literal_hits,
        "reference_signature_hits": signature_hits,
        "string_count": string_count,
        "relevant_strings": strings,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# HotA 1.8.0 运行时模块静态清单",
        "",
        "> 该报告只搜索导入、导出、字符串、地址字面量和 EXE 字节签名。未命中不等于运行时不会计算地址或动态覆盖代码。",
        "",
        "| 模块 | 大小 | SHA-256 | ImageBase | EntryPoint | 导出 |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for module in report["modules"]:
        lines.append(
            f"| `{Path(module['path']).name}` | {module['size']} | `{module['sha256']}` | "
            f"`{hex_value(module['image_base'])}` | `{hex_value(module['entrypoint_va'])}` | "
            f"{len(module['exports'])} |"
        )

    for module in report["modules"]:
        name = Path(module["path"]).name
        lines.extend(["", f"## {name}", ""])
        if module["version"]:
            lines.append(f"版本：`{module['version']['file_version']}`")
            lines.append("")

        lines.append("### 可能用于内存修改/诊断的导入")
        lines.append("")
        if module["patching_related_imports"]:
            for imported in module["patching_related_imports"]:
                lines.append(
                    f"- `{imported['dll']}!{imported['name']}`，IAT `{hex_value(imported['iat_va'])}`"
                )
        else:
            lines.append("未发现预设列表中的直接导入。")

        lines.extend(["", "### 候选 EXE 地址字面量", ""])
        if module["candidate_address_literal_hits"]:
            for hit in module["candidate_address_literal_hits"]:
                offsets = ", ".join(hex_value(value) for value in hit["file_offsets"])
                lines.append(f"- {hit['label']} `{hex_value(hit['va'])}`：{offsets}")
        else:
            lines.append("未发现。")

        lines.extend(["", "### 32 字节 EXE 签名", ""])
        if module["reference_signature_hits"]:
            for hit in module["reference_signature_hits"]:
                offsets = ", ".join(hex_value(value) for value in hit["file_offsets"])
                lines.append(f"- {hit['label']}：{offsets}")
        else:
            lines.append("未发现。")

        lines.extend(["", "### 相关字符串", ""])
        if module["relevant_strings"]:
            for item in module["relevant_strings"][:100]:
                value = item["value"].replace("`", "\\`")
                lines.append(
                    f"- `{hex_value(item['offset'])}` ({item['encoding']}): `{value}`"
                )
            if len(module["relevant_strings"]) > 100:
                lines.append(
                    f"- 其余 {len(module['relevant_strings']) - 100} 条见 JSON。"
                )
        else:
            lines.append("未发现关键词字符串。")

    lines.extend(
        [
            "",
            "## 证据边界",
            "",
            "- DLL 可以通过基址加 RVA、模式扫描、加密/压缩表或 patcher 脚本间接定位 EXE，因此没有地址字面量或完整签名并不能排除覆盖。",
            "- 最终判断仍需要启动后的内存字节、断点命中或诊断包装器日志。",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-exe", type=Path, required=True)
    parser.add_argument("--module", dest="modules", type=Path, action="append", required=True)
    parser.add_argument("--json", dest="json_path", type=Path, required=True)
    parser.add_argument("--markdown", dest="markdown_path", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    signatures = reference_signatures(args.reference_exe)
    report = {
        "schema_version": 1,
        "reference_exe": args.reference_exe.as_posix(),
        "reference_exe_sha256": sha256_file(args.reference_exe),
        "modules": [inventory(path, signatures) for path in args.modules],
    }
    args.json_path.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_path.parent.mkdir(parents=True, exist_ok=True)
    args.json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.markdown_path.write_text(markdown(report), encoding="utf-8")
    print(f"Analyzed {len(report['modules'])} runtime modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
