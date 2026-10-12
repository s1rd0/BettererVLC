#!/usr/bin/env python3
"""Convert original Figma PNG exports into VLC bitmap controls and slider sprites."""
from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from skin_constants import SEEK_FRAMES, VOLUME_FRAMES

ROOT = Path(__file__).resolve().parents[1]
BG = '#1b1b1b'
ACCENT = '#d37918'
BUTTONS = {
    'prev': (30, 28), 'next': (30, 28), 'play': (54, 28), 'pause': (54, 28),
    'stop': (30, 28), 'menu': (28, 28), 'sidebar': (28, 28), 'folder': (28, 28),
    'minimize': (36, 24), 'maximize': (36, 24), 'fullscreen': (36, 24), 'close': (36, 24),
    'audio': (30, 32), 'subtitles': (30, 32), 'settings': (30, 32), 'playlist': (30, 32),
    'mute': (24, 28), 'unmute': (24, 28), 'home': (30, 32), 'video': (30, 32),
    'library': (30, 32), 'stream': (30, 32), 'lists': (30, 32), 'recent': (30, 32),
    'add': (30, 32), 'shuffle': (24, 28), 'repeat': (24, 28),
    'load': (24, 28), 'save': (24, 28), 'delete': (24, 28),
}


def main() -> None:
    original_dir = ROOT / 'design-assets/exported'
    destination = ROOT / 'skin/assets'
    original_dir.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    payload = ROOT / 'build/figma-exported-assets.json'
    if payload.is_file():
        exports = json.loads(payload.read_text(encoding='utf-8'))
    else:
        exports = json.loads((original_dir / 'nodes.json').read_text(encoding='utf-8'))
    images = {}
    provenance = []
    for asset in exports:
        data = (base64.b64decode(asset['base64'], validate=True) if 'base64' in asset
                else (original_dir / f"{asset['name']}.png").read_bytes())
        image = Image.open(BytesIO(data)).convert('RGBA')
        image.load()
        expected = (round(asset['width']), round(asset['height']))
        # Figma includes the volume wedge's half-pixel stroke outside its frame.
        if image.size != expected and not (asset['name'].startswith('volume') and image.size == (89, 28)):
            raise ValueError(f"Wrong export dimensions: {asset['name']}")
        (original_dir / f"{asset['name']}.png").write_bytes(data)
        images[asset['name']] = image
        provenance.append({k: asset[k] for k in ('name', 'id', 'width', 'height')})
    (original_dir / 'nodes.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')

    for name, size in BUTTONS.items():
        icon = images[name]
        if icon.width > size[0] or icon.height > size[1]:
            raise ValueError(f'{name} does not fit its native button rectangle')
        rail = name in {'home', 'video', 'library', 'stream', 'lists', 'recent', 'add'}
        for state in ('up', 'over', 'down'):
            output = Image.new('RGBA', size, '#191919' if rail else BG)
            if state != 'up':
                ImageDraw.Draw(output).rounded_rectangle((0, 0, size[0]-1, size[1]-1), radius=4,
                                                         fill='#303030' if state == 'over' else '#373737')
            output.alpha_composite(icon, ((size[0]-icon.width)//2, (size[1]-icon.height)//2))
            if state != 'up' and name in {'play', 'pause'}:
                ImageDraw.Draw(output).rounded_rectangle((0, 0, size[0]-1, size[1]-1), radius=6,
                                                         outline='#e89a3e' if name == 'play' else '#969696')
            output.save(destination / f'{name}-{state}.png')
        if name in {'shuffle', 'repeat'}:
            for state in ('up', 'over', 'down'):
                output = Image.open(destination / f'{name}-{state}.png').convert('RGBA')
                ImageDraw.Draw(output).rounded_rectangle((0, 0, size[0]-1, size[1]-1), radius=4, outline=ACCENT)
                output.save(destination / f'{name}-on-{state}.png')

    for name, color in {'bg': BG, 'field': '#2c2a27', 'topbar': BG, 'sidebar-bg': '#0e0e0e',
                        'rail-bg': '#191919', 'seek-bg': '#090909'}.items():
        Image.new('RGB', (1, 1), color).save(destination / f'{name}.png')
    images['title-logo'].save(destination / 'title-logo.png')
    # Keep the small source cone at its original resolution. The 192px canvas
    # also provides a square fallback area for native cover art without blur.
    idle = Image.new('RGBA', (192, 192))
    cone = images['title-logo']
    idle.alpha_composite(cone, ((192-cone.width)//2, (192-cone.height)//2))
    idle.save(destination / 'idle-logo.png')
    knob = Image.new('RGBA', (8, 24))
    ImageDraw.Draw(knob).rounded_rectangle((0, 0, 7, 23), radius=4, fill=ACCENT)
    knob.save(destination / 'seek.png')
    Image.new('RGBA', (1, 1)).save(destination / 'vol-knob.png')

    width, height, steps = 606, 28, SEEK_FRAMES
    track = Image.new('RGBA', (width, height * steps), BG)
    for step in range(steps):
        tile = Image.new('RGBA', (width, height), BG)
        draw = ImageDraw.Draw(tile)
        draw.rounded_rectangle((0, 0, width-1, height-1), radius=6, fill='#090909')
        end = round((width - 4) * step / (steps - 1))
        if end > 0:
            draw.rounded_rectangle((2, 2, end+1, height-3), radius=4, fill='#371f06')
        track.alpha_composite(tile, (0, step * height))
    track.save(destination / 'seek-track.png')

    # The original exported zero-volume wedge remains the base at every value.
    # Its interior is filled dynamically, corresponding to the prototype's
    # clipped volume-fill layer. Native VLC's slider spans 0 to 200 percent.
    original = images['volume0']
    steps = VOLUME_FRAMES
    volume = Image.new('RGBA', (89, 28 * steps), BG)
    for step in range(steps):
        tile = Image.new('RGBA', (89, 28), BG)
        tile.alpha_composite(original)
        pixels = tile.load()
        source = original.load()
        end = round(86 * step / (steps-1))
        for x in range(2, min(end+2, 86)):
            for y in range(2, 26):
                r, g, b, alpha = source[x, y]
                if alpha == 255 and 7 <= r <= 12 and r == g == b:
                    t = x / 86
                    pixels[x, y] = (round(142+(211-142)*t), round(170+(121-170)*t), 24, 255)
        volume.alpha_composite(tile, (0, step * 28))
    volume.save(destination / 'vol-track.png')
    print(f'Prepared {len(exports)} original Figma exports and VLC bitmap controls in {destination}')


if __name__ == '__main__':
    main()
