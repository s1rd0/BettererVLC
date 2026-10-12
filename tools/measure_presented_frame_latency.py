#!/usr/bin/env python3
"""Measure seek-to-presentation latency on our synthetic AVI through LibVLC.

Uses the documented video display callback, which runs on the playback clock,
instead of treating position readback as evidence of a displayed new frame.
No GUI, microphone or system audio capture. The video output is a memory sink,
so these results do not measure the physical monitor or the Skins2/D3D window.
"""
from __future__ import annotations

import argparse
import ctypes as C
import json
import os
from pathlib import Path
import threading
import time


WIDTH, HEIGHT, PITCH = 320, 180, 1280
LOCK = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p))
UNLOCK = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p))
DISPLAY = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p)


def measure(vlc_dir: Path, media: Path, root: Path, caching: int, output: str) -> dict:
    with os.add_dll_directory(str(vlc_dir)):
        vlc = C.CDLL(str(vlc_dir / 'libvlc.dll'))
        signatures = {
            'libvlc_new': ([C.c_int, C.POINTER(C.c_char_p)], C.c_void_p),
            'libvlc_media_new_path': ([C.c_void_p, C.c_char_p], C.c_void_p),
            'libvlc_media_player_new_from_media': ([C.c_void_p], C.c_void_p),
            'libvlc_media_player_play': ([C.c_void_p], C.c_int),
            'libvlc_media_player_set_position': ([C.c_void_p, C.c_float], None),
            'libvlc_media_player_stop': ([C.c_void_p], None),
            'libvlc_media_player_release': ([C.c_void_p], None),
            'libvlc_media_release': ([C.c_void_p], None),
            'libvlc_release': ([C.c_void_p], None),
            'libvlc_audio_set_volume': ([C.c_void_p, C.c_int], C.c_int),
            'libvlc_video_set_callbacks': ([C.c_void_p, LOCK, UNLOCK, DISPLAY, C.c_void_p], None),
            'libvlc_video_set_format': ([C.c_void_p, C.c_char_p, C.c_uint, C.c_uint, C.c_uint], None),
        }
        for name, (arguments, returns) in signatures.items():
            function = getattr(vlc, name)
            function.argtypes, function.restype = arguments, returns
        args = [b'--ignore-config', b'--no-plugins-cache', b'--no-media-library',
                b'--quiet', b'--no-video-title-show',
                f'--config={root / "build/presentation-test-vlcrc"}'.encode(),
                f'--file-caching={caching}'.encode(), f'--aout={output}'.encode()]
        native_args = (C.c_char_p * len(args))(*args)
        instance = vlc.libvlc_new(len(args), native_args)
        if not instance:
            raise RuntimeError('LibVLC initialization failed')
        native_media = vlc.libvlc_media_new_path(instance, str(media).encode('utf-8'))
        player = vlc.libvlc_media_player_new_from_media(native_media)
        if not player:
            vlc.libvlc_media_release(native_media)
            vlc.libvlc_release(instance)
            raise RuntimeError('Could not create test media player')
        buffers = [C.create_string_buffer(PITCH * HEIGHT + 31) for _ in range(4)]
        addresses = [(C.addressof(buffer) + 31) & ~31 for buffer in buffers]
        next_buffer = 0
        decoded = {}
        condition = threading.Condition()
        presented = []

        @LOCK
        def lock(opaque, planes):
            nonlocal next_buffer
            index = next_buffer % len(buffers)
            next_buffer += 1
            planes[0] = addresses[index]
            return index + 1

        @UNLOCK
        def unlock(opaque, picture, planes):
            pixels = C.string_at(addresses[int(picture) - 1], PITCH * HEIGHT)
            first, last = WIDTH, -1
            # Only the moving orange dot: excludes labels and bottom timeline.
            for y in range(58, 123, 3):
                row = y * PITCH
                for x in range(WIDTH):
                    offset = row + x * 4
                    blue, green, red = pixels[offset:offset + 3]
                    if red > 180 and 80 < green < 200 and blue < 110:
                        first, last = min(first, x), max(last, x)
            decoded[int(picture)] = (round(((first + last)/2 - 24) * 99/272)/10
                                      if last >= first else None)

        @DISPLAY
        def display(opaque, picture):
            timestamp = time.perf_counter()
            seconds = decoded.get(int(picture))
            if seconds is not None:
                with condition:
                    presented.append((timestamp, seconds))
                    condition.notify_all()

        samples = []
        try:
            vlc.libvlc_video_set_callbacks(player, lock, unlock, display, None)
            vlc.libvlc_video_set_format(player, b'RV32', WIDTH, HEIGHT, PITCH)
            if vlc.libvlc_media_player_play(player) != 0:
                raise RuntimeError('Test playback failed')
            began = time.perf_counter()
            with condition:
                while not any(seconds >= .8 for _, seconds in presented):
                    remaining = 8 - (time.perf_counter() - began)
                    if remaining <= 0:
                        raise RuntimeError('No presented test frames')
                    condition.wait(min(.1, remaining))
            vlc.libvlc_audio_set_volume(player, 20)
            for target in (6, 1, 5):
                began = time.perf_counter()
                vlc.libvlc_media_player_set_position(player, target / 10)
                with condition:
                    while True:
                        arrived = [(at, sec) for at, sec in presented
                                   if at >= began and abs(sec - target) <= .2]
                        if arrived:
                            at, sec = arrived[0]
                            samples.append({'seek_seconds': target, 'presented_seconds': sec,
                                            'presentation_ms': round((at - began)*1000, 2)})
                            break
                        remaining = 6 - (time.perf_counter() - began)
                        if remaining <= 0:
                            raise RuntimeError(f'No presented frame after seek to {target}s')
                        condition.wait(min(.1, remaining))
                time.sleep(.2)
            return {'file_caching_ms': caching, 'audio_output': output,
                    'video_output': 'LibVLC clock-driven memory display callback',
                    'synthetic_media': str(media.relative_to(root)), 'samples': samples,
                    'limitation': 'Not physical display latency, Skins2 mouse latency, audible volume latency, or latency on user media.'}
        finally:
            vlc.libvlc_media_player_stop(player)
            vlc.libvlc_media_player_release(player)
            vlc.libvlc_media_release(native_media)
            vlc.libvlc_release(instance)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vlc-dir', type=Path, default=Path(r'C:\Program Files\VideoLAN\VLC'))
    parser.add_argument('--caching', type=int, default=1000)
    parser.add_argument('--aout', choices=('mmdevice', 'directsound'), default='mmdevice')
    parser.add_argument('--report', type=Path, default=root/'build/presented-frame-latency.json')
    args = parser.parse_args()
    result = measure(args.vlc_dir, root/'build/test-media.avi', root, args.caching, args.aout)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
