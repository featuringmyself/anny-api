"""png_trim: only strip trailing near-black, never mid-content dark rows."""

from pathlib import Path

from app.services.png_trim import trim_trailing_black


def _png_size(data: bytes) -> tuple[int, int]:
    import struct

    return struct.unpack(">II", data[16:24])


def test_trim_trailing_black_on_known_capture():
    src = Path("tmp/xbox/20261009104505_chatgpt.png")
    if not src.exists():
        return  # artifact not present in CI
    original = src.read_bytes()
    _, h0 = _png_size(original)
    trimmed = trim_trailing_black(original, pad_px=8)
    w1, h1 = _png_size(trimmed)
    assert w1 == _png_size(original)[0]
    # Known capture has ~336px pure-black tail; keep composer (DOM hide owns that).
    assert h1 < h0
    assert h0 - h1 >= 300
    assert h1 >= 800  # must not eat the conversation / product cards


def test_trim_is_noop_without_black_tail():
    # 1x1 black PNG still decodes; all-black trims to pad — use tiny non-black.
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    # 2x2 white RGB
    raw = b"".join(b"\x00" + bytes([255, 255, 255] * 2) for _ in range(2))
    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    assert trim_trailing_black(png) == png
