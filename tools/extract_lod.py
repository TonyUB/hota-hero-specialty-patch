#!/usr/bin/env python3
"""List or safely extract Heroes III LOD archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path


DIRECTORY_OFFSET = 0x5C
ENTRY_SIZE = 32


def parse_entries(data: bytes) -> list[dict[str, int | str]]:
    if len(data) < DIRECTORY_OFFSET or data[:4] != b"LOD\0":
        raise ValueError("not a supported LOD archive")
    count = struct.unpack_from("<I", data, 8)[0]
    directory_end = DIRECTORY_OFFSET + count * ENTRY_SIZE
    if directory_end > len(data):
        raise ValueError("LOD directory extends past end of file")

    entries = []
    for index in range(count):
        position = DIRECTORY_OFFSET + index * ENTRY_SIZE
        raw_name, offset, size, file_type, compressed_size = struct.unpack_from(
            "<16sIIII", data, position
        )
        name = raw_name.split(b"\0", 1)[0].decode("ascii", errors="replace")
        stored_size = compressed_size or size
        if offset + stored_size > len(data):
            raise ValueError(f"entry {name!r} extends past end of file")
        entries.append(
            {
                "index": index,
                "name": name,
                "offset": offset,
                "size": size,
                "type": file_type,
                "compressed_size": compressed_size,
            }
        )
    return entries


def payload(data: bytes, entry: dict[str, int | str]) -> bytes:
    offset = int(entry["offset"])
    size = int(entry["size"])
    compressed_size = int(entry["compressed_size"])
    stored = data[offset : offset + (compressed_size or size)]
    if not compressed_size:
        return stored
    try:
        unpacked = zlib.decompress(stored)
    except zlib.error:
        unpacked = zlib.decompress(stored, -zlib.MAX_WBITS)
    if len(unpacked) != size:
        raise ValueError(
            f"decompressed size mismatch for {entry['name']}: {len(unpacked)} != {size}"
        )
    return unpacked


def safe_target(root: Path, name: str) -> Path:
    target = (root / name).resolve()
    resolved_root = root.resolve()
    if target != resolved_root and resolved_root not in target.parents:
        raise ValueError(f"unsafe LOD entry path: {name!r}")
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--extract", type=Path)
    parser.add_argument("--json", action="store_true", help="print listing as JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = args.archive.read_bytes()
    entries = parse_entries(data)
    listing = {
        "archive": args.archive.as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "entries": entries,
    }
    if args.json:
        print(json.dumps(listing, ensure_ascii=False, indent=2))
    else:
        print(f"{args.archive}: {len(entries)} entries")
        for entry in entries:
            print(
                f"{int(entry['index']):4d} {int(entry['size']):9d} "
                f"{int(entry['compressed_size']):9d} {entry['name']}"
            )

    if args.extract:
        args.extract.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            target = safe_target(args.extract, str(entry["name"]))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload(data, entry))
        print(f"Extracted {len(entries)} entries to {args.extract}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
