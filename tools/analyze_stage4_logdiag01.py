#!/usr/bin/env python3
"""Parse Patch_v2.6_VISUAL_LOGDIAG01 fixed-size binary records."""

from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any


MAGIC = 0x31474448
RECORD = struct.Struct("<6I")
EVENT_NAMES = {
    1: "wrapper_init",
    2: "corpse_helper_init",
    3: "resurrection_entry",
    4: "native_post_enter",
    5: "after_rotation",
    6: "after_refresh",
}


def parse_bytes(data: bytes, source: str = "<memory>") -> dict[str, Any]:
    if not data:
        raise ValueError("Diagnostic file is empty")
    if len(data) % RECORD.size:
        raise ValueError(
            f"Diagnostic size {len(data)} is not a multiple of {RECORD.size}"
        )
    records = []
    for index, values in enumerate(RECORD.iter_unpack(data)):
        magic, event, a, b, c, d = values
        if magic != MAGIC:
            raise ValueError(f"Bad record magic at index {index}: 0x{magic:08X}")
        if event not in EVENT_NAMES:
            raise ValueError(f"Unknown event {event} at index {index}")
        records.append(
            {
                "index": index,
                "event": event,
                "event_name": EVENT_NAMES[event],
                "a": a,
                "b": b,
                "c": c,
                "d": d,
                "hex": {
                    "a": f"0x{a:08X}",
                    "b": f"0x{b:08X}",
                    "c": f"0x{c:08X}",
                    "d": f"0x{d:08X}",
                },
            }
        )

    counts = Counter(record["event_name"] for record in records)
    enter = next((record for record in reversed(records) if record["event"] == 4), None)
    rotated = next((record for record in reversed(records) if record["event"] == 5), None)
    refreshed = next((record for record in reversed(records) if record["event"] == 6), None)
    resurrection_events = [record for record in records if record["event"] == 3]

    diagnosis: list[str] = []
    if enter is None:
        if counts["wrapper_init"] or counts["corpse_helper_init"]:
            diagnosis.append(
                "群体/复活诊断路径已执行，但原生治愈日志追加后的 Hook 没有进入。"
            )
        else:
            diagnosis.append("没有命中群体包装器；需先核对安装目录或日志写入权限。")
    else:
        state = enter["a"]
        counted = state & 0x7F
        active = bool(state & 0x80)
        diagnosis.append(
            f"原生追加后 Hook 已执行；active={active}，携带复活计数={counted}，"
            f"实际复活事件={len(resurrection_events)}。"
        )
        if not active or counted != len(resurrection_events):
            diagnosis.append("状态字节或复活计数传递不一致，应修正计数作用域。")
        elif rotated is None:
            diagnosis.append("计数存在但未生成轮转后快照，应检查轮转分支。")
        else:
            cure_pointer = enter["d"]
            rotation_ok = rotated["c"] == cure_pointer
            diagnosis.append(
                "轮转后的插入位置保存了治愈记录指针。"
                if rotation_ok
                else "轮转后的插入位置不是追加前的治愈记录指针。"
            )
            if refreshed is None:
                diagnosis.append("缺少原生刷新后的快照。")
            elif refreshed["c"] != cure_pointer:
                diagnosis.append("原生刷新调用把已轮转的向量重新改写了。")
            elif refreshed["d"] == cure_pointer:
                diagnosis.append("刷新后治愈指针重新回到向量末尾。")
            else:
                diagnosis.append(
                    "轮转和原生刷新后向量仍正确；屏幕顺序来自随后重建的另一层显示缓存。"
                )

    return {
        "path": source,
        "size": len(data),
        "record_size": RECORD.size,
        "record_count": len(records),
        "event_counts": dict(sorted(counts.items())),
        "diagnosis": diagnosis,
        "records": records,
    }


def parse(path: Path) -> dict[str, Any]:
    return parse_bytes(path.read_bytes(), str(path))


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# LOGDIAG01 分析",
        "",
        f"记录数：{report['record_count']}；文件大小：{report['size']} 字节。",
        "",
        "## 结论",
        "",
    ]
    lines.extend(f"- {item}" for item in report["diagnosis"])
    lines.extend(["", "## 事件计数", ""])
    lines.extend(
        f"- `{name}`：{count}" for name, count in report["event_counts"].items()
    )
    lines.extend(["", "## 原始记录", ""])
    for record in report["records"]:
        values = record["hex"]
        lines.append(
            f"- #{record['index']} `{record['event_name']}` "
            f"a={values['a']} b={values['b']} c={values['c']} d={values['d']}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    report = parse(args.log)
    if args.json:
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    rendered = markdown(report)
    if args.markdown:
        args.markdown.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
