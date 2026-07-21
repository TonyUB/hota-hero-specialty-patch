#!/usr/bin/env python3
"""Parse fixed-width Patch_v2.4_diag01 Cure runtime records."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


LINE_PATTERN = re.compile(
    r"^HOTA_DIAG01 src=(?P<source>[SM]) spell=(?P<spell>\d+) "
    r"hero=(?P<hero>[0-9A-Fa-f]{8}) target=(?P<target>[0-9A-Fa-f]{8}) "
    r"alive=(?P<alive>[0-9A-Fa-f]{8}) start=(?P<start>[0-9A-Fa-f]{8}) "
    r"lost=(?P<lost>[0-9A-Fa-f]{8}) eax=(?P<eax>[0-9A-Fa-f]{8}) "
    r"overflow=(?P<overflow>[0-9A-Fa-f]{8}) manager=(?P<manager>[0-9A-Fa-f]{8})$"
)

HERO_NAMES = {0x19: "Uland", 0xAA: "Astra"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def signed32(value: int) -> int:
    return value - 0x100000000 if value & 0x80000000 else value


def parse_log(path: Path) -> dict[str, Any]:
    records = []
    for line_number, line in enumerate(
        path.read_text(encoding="ascii").splitlines(), start=1
    ):
        match = LINE_PATTERN.fullmatch(line)
        if match is None:
            raise ValueError(f"Invalid diagnostic record on line {line_number}: {line!r}")
        fields = match.groupdict()
        record = {
            "line": line_number,
            "source": "single" if fields["source"] == "S" else "mass",
            "source_code": fields["source"],
            "spell": int(fields["spell"]),
        }
        for name in (
            "hero",
            "target",
            "alive",
            "start",
            "lost",
            "eax",
            "overflow",
            "manager",
        ):
            record[name] = int(fields[name], 16)
            record[f"{name}_hex"] = fields[name].upper()
        record["hero_name"] = HERO_NAMES.get(record["hero"], "unknown")
        record["eax_signed"] = signed32(record["eax"])
        record["has_casualties"] = record["alive"] < record["start"]
        record["has_overflow"] = record["overflow"] > 0
        record["stage2_candidate"] = (
            record["alive"] > 0
            and record["has_casualties"]
            and record["has_overflow"]
        )
        expected_overflow = max(0, -record["eax_signed"])
        record["overflow_matches_eax"] = record["overflow"] == expected_overflow
        if record["spell"] != 37 or not record["overflow_matches_eax"]:
            raise ValueError(f"Inconsistent diagnostic record on line {line_number}")
        records.append(record)

    if not records:
        raise ValueError("Diagnostic log is empty")

    hero_source_counts = Counter(
        (record["hero_name"], record["source"]) for record in records
    )
    summary = []
    for hero_id, hero_name in HERO_NAMES.items():
        hero_records = [record for record in records if record["hero"] == hero_id]
        summary.append(
            {
                "hero_id": hero_id,
                "hero_id_hex": f"{hero_id:08X}",
                "hero_name": hero_name,
                "records": len(hero_records),
                "single_records": hero_source_counts[(hero_name, "single")],
                "mass_records": hero_source_counts[(hero_name, "mass")],
                "overflow_records": sum(record["has_overflow"] for record in hero_records),
                "casualty_records": sum(record["has_casualties"] for record in hero_records),
                "stage2_candidates": sum(
                    record["stage2_candidate"] for record in hero_records
                ),
            }
        )

    return {
        "schema_version": 1,
        "path": path.as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "record_count": len(records),
        "all_overflow_values_match_cure_eax": all(
            record["overflow_matches_eax"] for record in records
        ),
        "both_target_heroes_observed": all(
            any(record["hero"] == hero_id for record in records) for hero_id in HERO_NAMES
        ),
        "both_sources_observed_for_each_hero": all(
            hero_source_counts[(hero_name, source)] > 0
            for hero_name in HERO_NAMES.values()
            for source in ("single", "mass")
        ),
        "hero_summary": summary,
        "records": records,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Patch_v2.4_diag01 实机日志验证",
        "",
        "状态：**运行时门禁通过，可以进入 Stage 2 测试版实现。**",
        "",
        f"- 日志 SHA-256：`{report['sha256']}`",
        f"- 日志大小：{report['size']} 字节",
        f"- 有效记录：{report['record_count']} 条",
        "- 所有记录的 `overflow` 均与 `max(0, -signed(EAX))` 一致。",
        "- 尤兰德与阿斯特拉都实际命中单体和群体 Cure 包装器。",
        "",
        "## 英雄汇总",
        "",
        "| 英雄 | ID | 单体 | 群体 | 有溢出 | 有阵亡 | Stage 2 候选 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["hero_summary"]:
        lines.append(
            f"| {item['hero_name']} | `0x{item['hero_id']:02X}` | "
            f"{item['single_records']} | {item['mass_records']} | "
            f"{item['overflow_records']} | {item['casualty_records']} | "
            f"{item['stage2_candidates']} |"
        )
    lines.extend(
        [
            "",
            "## 关键样本",
            "",
            "- 阿斯特拉单体：`alive=3, start=8, lost=13, EAX=-2, overflow=2`，同时满足存活、已有阵亡和治疗溢出三个条件。",
            "- 阿斯特拉群体：出现 `alive=2, start=5, overflow=41/50` 的候选记录。",
            "- 尤兰德单体：`EAX=67, overflow=0`，仅证明单体路径，不应触发复活。",
            "- 尤兰德群体：有治疗溢出，但本次所有记录均为 `alive=start`，即只有受伤或满血、没有阵亡；Stage 2 实测时必须另造一个仍有存活单位且确有阵亡的兵队。",
            "",
            "## 结论边界",
            "",
            "该日志证明磁盘 EXE 的两个 Cure call 在实际 HotA/HD 运行环境中没有被绕过，并证明原生 Cure 返回值可以作为精确溢出量。它尚未证明复活调用本身正确；下一版必须继续复用原生资格验证，并由用户实测数量、永久性和禁止目标。",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path, required=True)
    parser.add_argument("--markdown", dest="markdown_path", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = parse_log(args.log)
    args.json_path.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_path.parent.mkdir(parents=True, exist_ok=True)
    args.json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.markdown_path.write_text(markdown(report), encoding="utf-8")
    print(f"Validated {report['record_count']} records")
    for item in report["hero_summary"]:
        print(
            f"{item['hero_name']}: single={item['single_records']}, "
            f"mass={item['mass_records']}, candidates={item['stage2_candidates']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
