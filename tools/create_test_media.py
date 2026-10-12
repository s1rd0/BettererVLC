#!/usr/bin/env python3
"""Create a deterministic 10-second MJPEG/PCM AVI for local VLC playback checks.

Requires Pillow, uses only synthetic pictures and sound, and needs no ffmpeg.
The orange moving dot, frame counter and quiet 440 Hz tone make playback,
seeking and volume changes visible/audible when testing a Skins2 theme.
"""

from __future__ import annotations

import argparse
import io
import math
from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT = 320, 180
FPS, DURATION, SAMPLE_RATE = 10, 10, 16_000
FRAME_COUNT = FPS * DURATION
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS


def chunk(identifier: bytes, payload: bytes) -> bytes:
    return identifier + struct.pack("<I", len(payload)) + payload + (b"\0" if len(payload) % 2 else b"")


def list_chunk(identifier: bytes, payload: bytes) -> bytes:
    return chunk(b"LIST", identifier + payload)


def stream_header(kind: bytes, handler: bytes, scale: int, rate: int,
                  length: int, buffer_size: int, sample_size: int,
                  rectangle: tuple[int, int, int, int] = (0, 0, 0, 0)) -> bytes:
    return struct.pack("<4s4sIHH8I4h", kind, handler, 0, 0, 0, 0,
                       scale, rate, 0, length, buffer_size, 0xFFFFFFFF,
                       sample_size, *rectangle)


def generate_frames(root: Path) -> list[bytes]:
    font_path = root / "skin" / "assets" / "Inter-Regular.ttf"
    if font_path.exists():
        title_font = ImageFont.truetype(str(font_path), 13)
        detail_font = ImageFont.truetype(str(font_path), 11)
    else:
        title_font = ImageFont.load_default(size=13)
        detail_font = ImageFont.load_default(size=11)
    background = Image.new("RGB", (WIDTH, HEIGHT))
    background.putdata([(11 + x * 8 // WIDTH, 13 + y * 8 // HEIGHT, 19 + y * 12 // HEIGHT)
                        for y in range(HEIGHT) for x in range(WIDTH)])
    frames = []
    for number in range(FRAME_COUNT):
        image = background.copy()
        draw = ImageDraw.Draw(image)
        phase = number / (FRAME_COUNT - 1)
        x = int(24 + phase * (WIDTH - 48))
        y = int(90 + 19 * math.sin(number / FPS * math.pi))
        draw.text((20, 17), "VLC Redesign • playback test", font=title_font,
                  fill=(242, 242, 245))
        draw.text((20, 39), "Synthetic local video + 440 Hz audio", font=detail_font,
                  fill=(143, 145, 159))
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill=(255, 144, 67))
        draw.rounded_rectangle((20, 136, WIDTH - 20, 140), radius=2,
                               fill=(55, 56, 65))
        draw.rounded_rectangle((20, 136, 22 + int(phase * (WIDTH - 42)), 140),
                               radius=2, fill=(255, 144, 67))
        draw.text((20, 151), f"{number / FPS:04.1f}s / 10.0s    frame {number + 1:03d}/100",
                  font=detail_font, fill=(179, 180, 190))
        encoded = io.BytesIO()
        image.save(encoded, format="JPEG", quality=82, optimize=False,
                   progressive=False, subsampling=0)
        frames.append(encoded.getvalue())
    return frames


def generate_audio() -> bytes:
    samples = []
    for number in range(SAMPLE_RATE * DURATION):
        seconds = number / SAMPLE_RATE
        # Short ramps prevent clicks at the start/end of the quiet test tone.
        envelope = min(1.0, seconds / 0.05, (DURATION - seconds) / 0.05)
        samples.append(round(2800 * envelope * math.sin(2 * math.pi * 440 * seconds)))
    return struct.pack(f"<{len(samples)}h", *samples)


def create_avi(output: Path, root: Path) -> None:
    frames = generate_frames(root)
    audio = generate_audio()
    audio_block_size = SAMPLES_PER_FRAME * 2
    max_frame_size = max(map(len, frames))

    main_header = struct.pack("<14I", 1_000_000 // FPS,
                              max_frame_size * FPS + SAMPLE_RATE * 2,
                              0, 0x110, FRAME_COUNT, 0, 2,
                              max(max_frame_size, audio_block_size),
                              WIDTH, HEIGHT, 0, 0, 0, 0)
    bitmap_header = struct.pack("<IiiHH4sIiiII", 40, WIDTH, HEIGHT, 1, 24,
                                b"MJPG", WIDTH * HEIGHT * 3, 0, 0, 0, 0)
    video_stream = list_chunk(b"strl", chunk(b"strh", stream_header(
        b"vids", b"MJPG", 1, FPS, FRAME_COUNT, max_frame_size, 0,
        (0, 0, WIDTH, HEIGHT))) + chunk(b"strf", bitmap_header))
    pcm_header = struct.pack("<HHIIHH", 1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16)
    audio_stream = list_chunk(b"strl", chunk(b"strh", stream_header(
        b"auds", b"\0\0\0\0", 2, SAMPLE_RATE * 2, SAMPLE_RATE * DURATION,
        audio_block_size, 2)) + chunk(b"strf", pcm_header))
    headers = list_chunk(b"hdrl", chunk(b"avih", main_header) + video_stream + audio_stream)

    movie = bytearray()
    index = bytearray()
    for number, frame in enumerate(frames):
        audio_block = audio[number * audio_block_size:(number + 1) * audio_block_size]
        for identifier, payload in ((b"00dc", frame), (b"01wb", audio_block)):
            offset = len(movie) + 4  # offsets relative to the movi list's type field
            movie.extend(chunk(identifier, payload))
            index.extend(struct.pack("<4sIII", identifier, 0x10, offset, len(payload)))
    contents = b"AVI " + headers + list_chunk(b"movi", bytes(movie)) + chunk(b"idx1", bytes(index))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"RIFF" + struct.pack("<I", len(contents)) + contents)
    print(f"Created {output.resolve()} ({output.stat().st_size:,} bytes): "
          f"10 s, 320×180, 10 fps MJPEG; mono 16 kHz signed 16-bit PCM audio.")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path,
                        default=root / "build" / "test-media.avi")
    args = parser.parse_args()
    create_avi(args.output.resolve(), root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
