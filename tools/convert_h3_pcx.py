#!/usr/bin/env python3
"""Convert a standard or Heroes III raw PCX resource to PNG."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from PIL import Image, UnidentifiedImageError


def load_image(path: Path) -> Image.Image:
    try:
        with Image.open(path) as image:
            return image.convert("RGB")
    except UnidentifiedImageError:
        data = path.read_bytes()
        if len(data) < 12:
            raise ValueError(f"{path} is too short to be a Heroes III PCX resource")

        pixel_count, width, height = struct.unpack_from("<III", data)
        if pixel_count != width * height:
            raise ValueError(f"{path} has an invalid Heroes III PCX header")

        pixel_end = 12 + pixel_count
        palette_end = pixel_end + 256 * 3
        if len(data) < palette_end:
            raise ValueError(f"{path} has incomplete pixel or palette data")

        image = Image.frombytes("P", (width, height), data[12:pixel_end])
        image.putpalette(data[pixel_end:palette_end])
        return image.convert("RGB")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    args.destination.parent.mkdir(parents=True, exist_ok=True)
    load_image(args.source).save(args.destination, format="PNG", optimize=True)


if __name__ == "__main__":
    main()
