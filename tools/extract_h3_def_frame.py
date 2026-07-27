#!/usr/bin/env python3
"""Extract one or more format-0/1 Heroes III DEF frames as PNG files."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from PIL import Image


HEADER_SIZE = 16
PALETTE_SIZE = 256 * 3
BLOCK_HEADER_SIZE = 16
FRAME_NAME_SIZE = 13


def parse_groups(data: bytes) -> list[dict[str, object]]:
    if len(data) < HEADER_SIZE + PALETTE_SIZE:
        raise ValueError("DEF resource is too short")
    _, full_width, full_height, group_count = struct.unpack_from("<4I", data, 0)
    position = HEADER_SIZE + PALETTE_SIZE
    groups: list[dict[str, object]] = []
    for _ in range(group_count):
        group_id, frame_count, _, _ = struct.unpack_from("<4I", data, position)
        position += BLOCK_HEADER_SIZE
        names = []
        for index in range(frame_count):
            start = position + index * FRAME_NAME_SIZE
            raw = data[start : start + FRAME_NAME_SIZE]
            names.append(raw.split(b"\0", 1)[0].decode("ascii", errors="replace"))
        position += frame_count * FRAME_NAME_SIZE
        offsets = list(struct.unpack_from(f"<{frame_count}I", data, position))
        position += frame_count * 4
        groups.append({
            "id": group_id,
            "names": names,
            "offsets": offsets,
            "full_width": full_width,
            "full_height": full_height,
        })
    return groups


def decode_frame(data: bytes, frame_offset: int, palette: bytes) -> Image.Image:
    (
        _, compression, full_width, full_height,
        width, height, left, top,
    ) = struct.unpack_from("<8I", data, frame_offset)
    pixel_start = frame_offset + 32
    pixels = bytearray([0] * (full_width * full_height))

    if compression == 0:
        source = data[pixel_start : pixel_start + width * height]
        if len(source) != width * height:
            raise ValueError("truncated format-0 frame")
        rows = [source[row * width : (row + 1) * width] for row in range(height)]
    elif compression == 1:
        row_offsets = struct.unpack_from(f"<{height}I", data, pixel_start)
        rows = []
        for row_offset in row_offsets:
            position = pixel_start + row_offset
            row = bytearray()
            while len(row) < width:
                code = data[position]
                run_length = data[position + 1] + 1
                position += 2
                if code == 0xFF:
                    row.extend(data[position : position + run_length])
                    position += run_length
                else:
                    row.extend([code] * run_length)
            if len(row) != width:
                raise ValueError("format-1 row extends beyond the declared width")
            rows.append(bytes(row))
    else:
        raise ValueError(f"unsupported DEF compression format {compression}")

    for row_index, row in enumerate(rows):
        target = (top + row_index) * full_width + left
        pixels[target : target + width] = row

    indexed = Image.frombytes("P", (full_width, full_height), bytes(pixels))
    indexed.putpalette(palette)
    image = indexed.convert("RGBA")
    image.putalpha(Image.frombytes(
        "L",
        (full_width, full_height),
        bytes(0 if value == 0 else 255 for value in pixels),
    ))
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("frames", nargs="+", type=int)
    parser.add_argument("--group", type=int, default=0)
    parser.add_argument("--prefix", default="frame")
    args = parser.parse_args()

    data = args.source.read_bytes()
    palette = data[HEADER_SIZE : HEADER_SIZE + PALETTE_SIZE]
    groups = parse_groups(data)
    if args.group < 0 or args.group >= len(groups):
        raise ValueError("group index is out of range")
    group = groups[args.group]
    names = group["names"]
    offsets = group["offsets"]
    assert isinstance(names, list) and isinstance(offsets, list)
    args.output.mkdir(parents=True, exist_ok=True)
    for frame_index in args.frames:
        if frame_index < 0 or frame_index >= len(offsets):
            raise ValueError(f"frame {frame_index} is out of range")
        destination = args.output / f"{args.prefix}-{frame_index:03d}.png"
        decode_frame(data, int(offsets[frame_index]), palette).save(
            destination, format="PNG", optimize=True
        )
        print(f"{frame_index}: {names[frame_index]} -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
