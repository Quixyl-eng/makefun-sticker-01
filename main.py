#!/usr/bin/env python3
"""Emit the make.fun sticker image to the judge output path.

The sticker ships next to this file as entry.png. The judge always
names the output entry.png; the format itself is told apart by the
first bytes (PNG or JPEG). This program validates those bytes with
the Python 3.13 standard library only — the sandbox installs nothing
— then copies them unchanged to MAKEFUN_OUTPUT_DIR/entry.png,
defaulting to /output/entry.png. Both harness runs must write the
same bytes: the copy is deterministic and does not redraw the image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import zlib
from pathlib import Path

MAX_BYTES = 1_048_576
MAX_EDGE = 1024
ENTRY_NAME = "entry.png"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"


class EntryError(Exception):
    """The shipped sticker does not meet the contest gate."""


def detect_format(data: bytes) -> str:
    if data.startswith(PNG_MAGIC):
        return "png"
    if data.startswith(JPEG_SOI):
        return "jpeg"
    raise EntryError("entry is neither a PNG nor a JPEG (magic bytes)")


def _png_chunk(data: bytes, offset: int) -> tuple[str, bytes, int]:
    if offset + 12 > len(data):
        raise EntryError("truncated PNG chunk header")
    length = struct.unpack(">I", data[offset : offset + 4])[0]
    kind = data[offset + 4 : offset + 8].decode("latin-1")
    start = offset + 8
    end = start + length
    if end + 4 > len(data):
        raise EntryError(f"truncated PNG chunk {kind}")
    payload = data[start:end]
    stored_crc = struct.unpack(">I", data[end : end + 4])[0]
    actual_crc = zlib.crc32(data[offset + 4 : end]) & 0xFFFFFFFF
    if stored_crc != actual_crc:
        raise EntryError(f"PNG chunk {kind} has a bad CRC")
    return kind, payload, end + 4


def png_info(data: bytes) -> dict[str, int | str]:
    if len(data) < 33 or not data.startswith(PNG_MAGIC):
        raise EntryError("invalid PNG header")
    kind, payload, cursor = _png_chunk(data, 8)
    if kind != "IHDR" or len(payload) != 13:
        raise EntryError("PNG does not start with a valid IHDR")
    width, height, bit_depth, color_type, _comp, _filt, _inter = struct.unpack(
        ">IIBBBBB", payload
    )
    saw_idata = False
    saw_iend = False
    while cursor < len(data):
        kind, payload, cursor = _png_chunk(data, cursor)
        if kind == "IDAT":
            saw_idata = True
        elif kind == "IEND":
            saw_iend = True
            break
    if not saw_idata:
        raise EntryError("PNG has no IDAT image data")
    if not saw_iend:
        raise EntryError("PNG is missing the IEND end marker")
    if cursor != len(data):
        raise EntryError("trailing bytes after PNG IEND")
    return {
        "format": "png",
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
    }


def jpeg_info(data: bytes) -> dict[str, int | str]:
    if not data.startswith(JPEG_SOI):
        raise EntryError("invalid JPEG start marker")
    if JPEG_EOI not in data:
        raise EntryError("JPEG is missing the end-of-image marker")
    pos = 2
    width = height = 0
    precision = 0
    while pos < len(data) - 1:
        if data[pos] != 0xFF:
            raise EntryError("JPEG segment is not byte-aligned")
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        if pos >= len(data):
            break
        marker = data[pos]
        pos += 1
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            if marker == 0xD9:
                break
            continue
        if pos + 2 > len(data):
            raise EntryError("truncated JPEG segment length")
        length = struct.unpack(">H", data[pos : pos + 2])[0]
        if length < 2 or pos + length > len(data):
            raise EntryError("invalid JPEG segment length")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if length < 7:
                raise EntryError("truncated JPEG SOF segment")
            precision, height, width = struct.unpack(">BHH", data[pos + 2 : pos + 7])
            return {
                "format": "jpeg",
                "width": width,
                "height": height,
                "precision": precision,
            }
        pos += length
    if width == 0 or height == 0:
        raise EntryError("JPEG has no SOF dimensions")
    return {
        "format": "jpeg",
        "width": width,
        "height": height,
        "precision": precision,
    }


def inspect(data: bytes) -> dict[str, int | str]:
    kind = detect_format(data)
    return png_info(data) if kind == "png" else jpeg_info(data)


def validate(data: bytes) -> dict[str, int | str]:
    if not data:
        raise EntryError("entry image is empty")
    if len(data) > MAX_BYTES:
        raise EntryError(f"entry is {len(data)} bytes, over the {MAX_BYTES} limit")
    info = inspect(data)
    width = int(info["width"])
    height = int(info["height"])
    if width < 1 or height < 1:
        raise EntryError("entry has non-positive dimensions")
    if width > MAX_EDGE or height > MAX_EDGE:
        raise EntryError(f"entry is {width}x{height}, over the {MAX_EDGE}x{MAX_EDGE} limit")
    info["bytes"] = len(data)
    info["sha256"] = payload_digest(data)
    return info


def payload_digest(data: bytes) -> str:
    """Return the SHA-256 hex digest of the raw sticker bytes."""
    return hashlib.sha256(data).hexdigest()


def default_source() -> Path:
    return Path(__file__).resolve().parent / ENTRY_NAME


def default_output_dir() -> Path:
    return Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))


def emit(source: Path, output_dir: Path) -> tuple[Path, dict[str, int | str]]:
    if not source.is_file():
        raise EntryError(f"source image not found: {source}")
    data = source.read_bytes()
    info = validate(data)
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / ENTRY_NAME
    dest.write_bytes(data)
    return dest, info


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the shipped sticker and copy it to the judge output path.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="path to the shipped entry.png (default: next to this file)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="directory for entry.png (default: $MAKEFUN_OUTPUT_DIR or /output)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the source image and print a short report, without writing output",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print format, dimensions and byte size after a successful run",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the validation report as a single JSON object",
    )
    return parser


def format_report(info: dict[str, int | str], dest: Path | None = None) -> str:
    parts = [
        f"format={info['format']}",
        f"size={info['width']}x{info['height']}",
        f"bytes={info['bytes']}",
    ]
    if "sha256" in info:
        parts.append(f"sha256={info['sha256']}")
    if dest is not None:
        parts.append(f"wrote={dest}")
    return " ".join(parts)


def format_json(info: dict[str, int | str], dest: Path | None = None) -> str:
    payload = dict(info)
    if dest is not None:
        payload["wrote"] = str(dest)
    payload["crc_checked"] = info.get("format") == "png"
    return json.dumps(payload, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = args.source if args.source is not None else default_source()
    output_dir = args.output_dir if args.output_dir is not None else default_output_dir()
    try:
        if args.check:
            if not source.is_file():
                raise EntryError(f"source image not found: {source}")
            info = validate(source.read_bytes())
            print(format_json(info) if args.json else format_report(info))
            return 0
        dest, info = emit(source, output_dir)
        if args.verbose or args.json:
            print(format_json(info, dest) if args.json else format_report(info, dest))
        return 0
    except EntryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
