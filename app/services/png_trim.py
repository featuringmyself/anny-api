"""Trim trailing empty rows from dark-theme conversation screenshots."""

from __future__ import annotations

import struct
import zlib

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _decode_rgba_rows(png: bytes) -> tuple[int, int, int, list[bytes]]:
    if png[:8] != _PNG_SIG:
        raise ValueError("not a PNG")
    pos = 8
    width = height = color_type = None
    idat = b""
    while pos < len(png):
        length = struct.unpack(">I", png[pos : pos + 4])[0]
        ctype = png[pos + 4 : pos + 8]
        chunk = png[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            width, height = struct.unpack(">II", chunk[:8])
            color_type = chunk[9]
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
    if width is None or height is None or color_type is None:
        raise ValueError("invalid PNG")
    if color_type == 2:
        bpp = 3
    elif color_type == 6:
        bpp = 4
    else:
        raise ValueError(f"unsupported PNG color type {color_type}")

    raw = zlib.decompress(idat)
    stride = width * bpp
    rows: list[bytes] = []
    i = 0
    prev = bytearray(stride)
    for _ in range(height):
        filt = raw[i]
        i += 1
        row = bytearray(raw[i : i + stride])
        i += stride
        if filt == 1:
            for x in range(bpp, stride):
                row[x] = (row[x] + row[x - bpp]) & 255
        elif filt == 2:
            for x in range(stride):
                row[x] = (row[x] + prev[x]) & 255
        elif filt == 3:
            for x in range(stride):
                left = row[x - bpp] if x >= bpp else 0
                row[x] = (row[x] + ((left + prev[x]) // 2)) & 255
        elif filt == 4:
            for x in range(stride):
                a = row[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else b if pb <= pc else c
                row[x] = (row[x] + pr) & 255
        elif filt != 0:
            raise ValueError(f"unsupported PNG filter {filt}")
        rows.append(bytes(row))
        prev = row
    return width, height, bpp, rows


def _encode_png(width: int, height: int, bpp: int, rows: list[bytes]) -> bytes:
    color_type = 2 if bpp == 3 else 6
    raw = b"".join(b"\x00" + row for row in rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return (
        _PNG_SIG
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def _row_max_rgb(row: bytes, bpp: int) -> int:
    mx = 0
    for i in range(0, len(row), bpp):
        mx = max(mx, row[i], row[i + 1], row[i + 2])
    return mx


def trim_trailing_black(
    png: bytes,
    *,
    threshold: int = 22,
    pad_px: int = 8,
) -> bytes:
    """
    Crop trailing near-black rows only.

    Safe for dark ChatGPT themes: does not try to detect composer chrome
    (that wrongly eats product cards / dark gaps). Composer must be removed
    at capture time by hiding it in the DOM.
    """
    width, height, bpp, rows = _decode_rgba_rows(png)
    y = height - 1
    while y >= 0 and _row_max_rgb(rows[y], bpp) <= threshold:
        y -= 1
    if y < 0:
        return png
    new_h = min(height, y + 1 + pad_px)
    if new_h >= height:
        return png
    return _encode_png(width, new_h, bpp, rows[:new_h])
