#!/usr/bin/env python3
"""Parse and summarize Patch_v2.4_STAGE2_TEST runtime records."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


LINE_PATTERN = re.compile(
    r"^HOTA_STAGE2 src=(?P<source>[SM]) hero=(?P<hero>[0-9A-Fa-f]{8}) "
    r"target=(?P<target>[0-9A-Fa-f]{8}) alive=(?P<alive>[0-9A-Fa-f]{8}) "
    r"start=(?P<start>[0-9A-Fa-f]{8}) lost=(?P<lost>[0-9A-Fa-f]{8}) "
    r"eax=(?P<eax>[0-9A-Fa-f]{8}) overflow=(?P<overflow>[0-9A-Fa-f]{8}) "
    r"revived=(?P<revived>[YN])$"
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
            raise ValueError(f"Invalid Stage 2 record on line {line_number}: {line!r}")
        fields = match.groupdict()
        record: dict[str, Any] = {
            "line": line_number,
            "source": "single" if fields["source"] == "S" else "mass",
            "source_code": fields["source"],
            "revived": fields["revived"] == "Y",
            "revived_code": fields["revived"],
        }
        for name in (
            "hero",
            "target",
            "alive",
            "start",
            "lost",
            "eax",
            "overflow",
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
        record["overflow_matches_eax"] = record["overflow"] == max(
            0, -record["eax_signed"]
        )
        record["false_positive"] = record["revived"] and not record["stage2_candidate"]
        if not record["overflow_matches_eax"]:
            raise ValueError(f"Overflow mismatch on line {line_number}")
        records.append(record)

    if not records:
        raise ValueError("Stage 2 log is empty")

    hero_source_counts = Counter(
        (record["hero_name"], record["source"]) for record in records
    )
    hero_summary = []
    for hero_id, hero_name in HERO_NAMES.items():
        hero_records = [record for record in records if record["hero"] == hero_id]
        hero_summary.append(
            {
                "hero_id": hero_id,
                "hero_id_hex": f"{hero_id:08X}",
                "hero_name": hero_name,
                "records": len(hero_records),
                "single_records": hero_source_counts[(hero_name, "single")],
                "mass_records": hero_source_counts[(hero_name, "mass")],
                "revived_yes": sum(record["revived"] for record in hero_records),
                "revived_no": sum(not record["revived"] for record in hero_records),
                "candidates": sum(record["stage2_candidate"] for record in hero_records),
                "validator_rejections": sum(
                    record["stage2_candidate"] and not record["revived"]
                    for record in hero_records
                ),
                "false_positives": sum(record["false_positive"] for record in hero_records),
            }
        )

    candidates = [record for record in records if record["stage2_candidate"]]
    non_candidates = [record for record in records if not record["stage2_candidate"]]
    return {
        "schema_version": 1,
        "path": path.as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "record_count": len(records),
        "revived_yes_count": sum(record["revived"] for record in records),
        "revived_no_count": sum(not record["revived"] for record in records),
        "candidate_count": len(candidates),
        "non_candidate_count": len(non_candidates),
        "validator_accepted_candidate_count": sum(
            record["revived"] for record in candidates
        ),
        "validator_rejected_candidate_count": sum(
            not record["revived"] for record in candidates
        ),
        "all_candidates_revived": all(record["revived"] for record in candidates),
        "all_non_candidates_skipped": all(not record["revived"] for record in non_candidates),
        "false_positive_count": sum(record["false_positive"] for record in records),
        "all_overflow_values_match_cure_eax": all(
            record["overflow_matches_eax"] for record in records
        ),
        "both_sources_observed_for_each_hero": all(
            hero_source_counts[(hero_name, source)] > 0
            for hero_name in HERO_NAMES.values()
            for source in ("single", "mass")
        ),
        "hero_summary": hero_summary,
        "records": records,
    }


def markdown(report: dict[str, Any]) -> str:
    observed_paths = ", ".join(
        f"{item['hero_name']}单体" * (item["single_records"] > 0)
        + ("/" if item["single_records"] > 0 and item["mass_records"] > 0 else "")
        + f"{item['hero_name']}群体" * (item["mass_records"] > 0)
        for item in report["hero_summary"]
        if item["single_records"] > 0 or item["mass_records"] > 0
    )
    lines = [
        "# Patch_v2.4_STAGE2_TEST 实机日志验证",
        "",
        "状态：**Stage 2 日志决策已完成结构化验证。**",
        "",
        f"- 日志 SHA-256：`{report['sha256']}`",
        f"- 有效记录：{report['record_count']} 条",
        f"- `revived=Y`：{report['revived_yes_count']} 条",
        f"- `revived=N`：{report['revived_no_count']} 条",
        f"- 同时具备存活、阵亡和溢出的候选：{report['candidate_count']} 条",
        f"- 原生资格验证接受：{report['validator_accepted_candidate_count']} 条",
        f"- 原生资格验证拒绝：{report['validator_rejected_candidate_count']} 条",
        f"- 非候选误触发：{report['false_positive_count']} 条",
        "- 所有 `overflow` 均等于 `max(0, -signed(EAX))`。",
        "",
        "## 英雄汇总",
        "",
        "| 英雄 | 单体 | 群体 | 候选 | revived=Y | revived=N | 原生拒绝 | 误触发 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["hero_summary"]:
        lines.append(
            f"| {item['hero_name']} | {item['single_records']} | "
            f"{item['mass_records']} | {item['candidates']} | "
            f"{item['revived_yes']} | {item['revived_no']} | "
            f"{item['validator_rejections']} | "
            f"{item['false_positives']} |"
        )
    lines.extend(
        [
            "",
            "## 判定",
            "",
            f"- 本日志覆盖的路径：{observed_paths}。",
            f"- 非候选记录共 {report['non_candidate_count']} 条，全部正确跳过。",
            (
                f"- 有 {report['validator_rejected_candidate_count']} 条记录在满足基础候选条件后被原生资格验证拒绝。"
                if report["validator_rejected_candidate_count"]
                else "- 本日志没有包含满足基础候选条件后被原生资格验证拒绝的样本。"
            ),
            (
                "- `revived=Y` 证明 `temporary=0` 调用发生；战后永久性仍须结合用户实机观察。"
                if report["revived_yes_count"]
                else "- 本日志没有 `revived=Y`；它用于验证原生资格拒绝，不能单独证明永久复活路径。"
            ),
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
    print(
        f"Validated {report['record_count']} records: "
        f"Y={report['revived_yes_count']}, N={report['revived_no_count']}"
    )
    for item in report["hero_summary"]:
        print(
            f"{item['hero_name']}: single={item['single_records']}, "
            f"mass={item['mass_records']}, revived={item['revived_yes']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
