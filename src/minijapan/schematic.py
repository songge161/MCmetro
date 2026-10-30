"""Sponge v2 export, with deterministic gzip and Minecraft 1.20.1 block states."""

from __future__ import annotations

import gzip
import struct
from pathlib import Path


class Blocks:
    def __init__(self, width, height, length):
        if any(not 1 <= size <= 512 for size in (width, height, length)):
            raise ValueError("样板尺寸每轴须在 1..512 内")
        if width * height * length > 16_000_000:
            raise ValueError("样板体积不能超过 1600 万格")
        self.width, self.height, self.length = width, height, length
        self.palette = {"minecraft:air": 0}
        self.data = bytearray(width * height * length)

    def index(self, x, y, z):
        if not (0 <= x < self.width and 0 <= y < self.height and 0 <= z < self.length):
            raise ValueError(f"方块越界：{x}, {y}, {z}")
        return x + z * self.width + y * self.width * self.length

    def set(self, x, y, z, state):
        if state not in self.palette:
            if len(self.palette) >= 128:
                raise ValueError("首版样板最多支持 128 个方块状态")
            self.palette[state] = len(self.palette)
        self.data[self.index(x, y, z)] = self.palette[state]

    def get(self, x, y, z):
        return self.data[self.index(x, y, z)]


def _string(value):
    encoded = value.encode("utf-8")
    return struct.pack(">H", len(encoded)) + encoded


def _tag(kind, name, payload):
    return bytes([kind]) + _string(name) + payload


def write_schematic(blocks, path):
    integers = {"Version": 2, "DataVersion": 3465, "PaletteMax": len(blocks.palette)}
    body = b"".join(_tag(3, name, struct.pack(">i", value)) for name, value in integers.items())
    for name, value in (
        ("Width", blocks.width),
        ("Height", blocks.height),
        ("Length", blocks.length),
    ):
        body += _tag(2, name, struct.pack(">H", value))
    body += _tag(11, "Offset", struct.pack(">iiii", 3, 0, 0, 0))
    palette = (
        b"".join(_tag(3, name, struct.pack(">i", value)) for name, value in blocks.palette.items())
        + b"\0"
    )
    body += _tag(10, "Palette", palette)
    body += _tag(7, "BlockData", struct.pack(">i", len(blocks.data)) + blocks.data)
    body += _tag(9, "BlockEntities", struct.pack(">Bi", 10, 0))
    body += _tag(9, "Entities", struct.pack(">Bi", 10, 0))
    root = _tag(10, "Schematic", body + b"\0")
    Path(path).write_bytes(gzip.compress(root, mtime=0))
