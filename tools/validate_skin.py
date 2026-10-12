#!/usr/bin/env python3
"""Validate a VLC Skins2 source directory before packaging it as a .vlt.

Requires Pillow and lxml. This checks the installed VLC 2.0 DTD, assets,
references and useful geometry constraints; it does not replace a VLC smoke test.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from xml.parsers import expat

from lxml import etree
from PIL import Image, ImageFont


BUILTIN_ACTIONS = {"none"} | {
    f"dialogs.{name}()" for name in (
        "changeSkin", "fileSimple", "file", "directory", "disc", "net",
        "playlist", "messages", "prefs", "fileInfo", "streamingWizard",
        "popup", "audioPopup", "videoPopup", "miscPopup",
    )
} | {
    f"vlc.{name}()" for name in (
        "fullscreen", "play", "pause", "stop", "faster", "slower", "mute",
        "volumeUp", "volumeDown", "minimize", "onTop", "snapshot",
        "toggleRecord", "nextFrame", "quit",
    )
} | {
    f"playlist.{name}()" for name in (
        "load", "save", "add", "next", "previous", "del", "sort",
    )
} | {"playtree.del()", "playtree.sort()", "equalizer.enable()", "equalizer.disable()"} | {
    f"playlist.set{mode}({value})"
    for mode in ("Random", "Loop", "Repeat") for value in ("true", "false")
} | {
    f"dvd.{name}()" for name in (
        "nextTitle", "previousTitle", "nextChapter", "previousChapter", "rootMenu",
    )
}
BOOL_VARS = {"true", "false", "dvd.isActive", "equalizer.isEnabled"} | {
    f"vlc.{name}" for name in (
        "isPlaying", "isStopped", "isPaused", "isSeekable", "canRecord",
        "isRecording", "isFullscreen", "hasVout", "hasAudio", "isMute", "isOnTop",
    )
} | {f"{prefix}.is{mode}" for prefix in ("playlist", "playtree") for mode in ("Random", "Loop", "Repeat")}
PERCENT_VARS = {"time", "volume", "playtree.slider", "equalizer.preamp"} | {
    f"equalizer.band({i})" for i in range(10)
}
BITMAP_ATTRS = {
    "Image": ("image",), "Button": ("up", "down", "over"),
    "Checkbox": ("up1", "down1", "over1", "up2", "down2", "over2"),
    "Slider": ("up", "down", "over", "background"),
    "SliderBackground": ("image",), "RadialSlider": ("sequence",),
    "Playlist": ("bgimage",), "Playtree": ("bgimage", "itemimage", "openimage", "closedimage"),
}


@dataclass
class ValidationResult:
    source: Path
    dtd: Path
    files: set[Path] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def default_dtd() -> Path:
    installed = Path(r"C:\Program Files\VideoLAN\VLC\skins\skin.dtd")
    return installed if installed.is_file() else Path(__file__).resolve().parents[1] / "docs" / "skin.dtd"


def safe_asset(source: Path, name: str) -> Path:
    """VLC archive paths are portable, relative and contained in the theme root."""
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    if not name or "\\" in name or posix.is_absolute() or windows.drive or ".." in posix.parts:
        raise ValueError(f"unsafe asset path {name!r}; use a relative path with forward slashes")
    candidate = (source / name).resolve()
    if not candidate.is_relative_to(source.resolve()):
        raise ValueError(f"asset path escapes source directory: {name!r}")
    if not candidate.is_file():
        raise ValueError(f"missing asset: {name}")
    return candidate


def validate_skin(source: Path | str, dtd_path: Path | str | None = None) -> ValidationResult:
    source = Path(source).resolve()
    if source.is_file():
        if source.name != "theme.xml":
            raise ValueError("source XML must be named theme.xml")
        source = source.parent
    result = ValidationResult(source, Path(dtd_path).resolve() if dtd_path else default_dtd())
    if not result.dtd.is_file():
        result.errors.append(f"DTD not found: {result.dtd}")
        return result
    try:
        dtd = etree.DTD(str(result.dtd))
    except (OSError, etree.DTDParseError) as exc:
        result.errors.append(f"could not read DTD: {exc}")
        return result

    elements: list[etree._Element] = []
    visited: set[Path] = set()

    def read_xml(path: Path, depth: int = 0) -> None:
        if depth > 4:
            result.errors.append(f"Include exceeds VLC recursion limit: {path.name}")
            return
        if path in visited:
            result.errors.append(f"repeated or cyclic Include: {path.name}")
            return
        visited.add(path)
        result.files.add(path)
        try:
            parser = etree.XMLParser(load_dtd=False, resolve_entities=False, no_network=True)
            document = etree.parse(str(path), parser)
            # VLC 3.0's pull parser skips end callbacks for self-closing tags.
            # Playlist/tree context would then override following slider values.
            lexical = expat.ParserCreate()

            def check_closing_tag(name: str, attributes: dict[str, str]) -> None:
                if name in {"Playtree", "Playlist"}:
                    opening = lexical.GetInputContext() or b""
                    if re.match(rb'''<(?:[^<>"']|"[^"]*"|'[^']*')*/\s*>''', opening):
                        result.errors.append(f"{path.name}: {name} (line {lexical.CurrentLineNumber}) "
                                             f"requires an explicit </{name}> closing tag for VLC 3.0 slider bindings")

            lexical.StartElementHandler = check_closing_tag
            lexical.Parse(path.read_bytes(), True)
        except (OSError, etree.XMLSyntaxError, expat.ExpatError) as exc:
            result.errors.append(f"XML: {exc}")
            return
        if not dtd.validate(document):
            result.errors.extend(f"DTD: {entry.message} (line {entry.line})" for entry in dtd.error_log)
        root = document.getroot()
        if root.get("version") != "2.0":
            result.errors.append(f"{path.name}: VLC Skins2 requires Theme version=2.0")
        for element in root.iter():
            if not isinstance(element.tag, str):
                continue
            elements.append(element)
            name = element.get("file")
            if name is not None:
                try:
                    asset = safe_asset(source, name)
                    result.files.add(asset)
                    if element.tag == "Include":
                        read_xml(asset, depth + 1)
                except ValueError as exc:
                    result.errors.append(str(exc))

    read_xml(source / "theme.xml")
    ids: dict[str, etree._Element] = {}
    bitmaps: dict[str, tuple[int, int]] = {}
    fonts = {"defaultfont"}

    def label(element: etree._Element) -> str:
        return f"{element.tag} {element.get('id', '(unnamed)')} (line {element.sourceline})"

    def integer(element: etree._Element, name: str, default: int = 0, minimum: int | None = None) -> int:
        raw = element.get(name, str(default))
        try:
            value = int(raw)
            if minimum is not None and value < minimum:
                raise ValueError
            return value
        except ValueError:
            result.errors.append(f"{label(element)}: {name} must be an integer" + (f" >= {minimum}" if minimum is not None else ""))
            return default

    for element in elements:
        identity = element.get("id")
        if identity and identity != "none":
            if identity in ids:
                result.errors.append(f"duplicate id: {identity}")
            ids[identity] = element
        if element.tag in {"Font", "BitmapFont"} and identity:
            fonts.add(identity)
        if element.tag == "Font":
            try:
                font_path = safe_asset(source, element.get("file", ""))
                ImageFont.truetype(str(font_path), integer(element, "size", 12, 1))
            except (ValueError, OSError) as exc:
                result.errors.append(f"{label(element)}: invalid font: {exc}")
        if element.tag in {"Bitmap", "BitmapFont"}:
            try:
                asset = safe_asset(source, element.get("file", ""))
                with Image.open(asset) as image:
                    image.load()
                    width, height = image.size
                frames = integer(element, "nbframes", 1, 1)
                if height % frames:
                    result.errors.append(f"{label(element)}: image height {height} is not divisible by nbframes={frames}")
                if identity:
                    bitmaps[identity] = (width, height // frames)
                for child in element.findall("SubBitmap"):
                    x, y = integer(child, "x"), integer(child, "y")
                    w, h = integer(child, "width", 0, 1), integer(child, "height", 0, 1)
                    n = integer(child, "nbframes", 1, 1)
                    if x < 0 or y < 0 or x + w > width or y + h > height:
                        result.errors.append(f"{label(child)}: rectangle is outside bitmap {width}x{height}")
                    if h % n:
                        result.errors.append(f"{label(child)}: height is not divisible by nbframes={n}")
                    bitmaps[child.get("id", "")] = (w, h // n)
            except (ValueError, OSError) as exc:
                result.errors.append(f"{label(element)}: invalid image: {exc}")

    windows = {key for key, element in ids.items() if element.tag == "Window"}
    layouts = {key for key, element in ids.items() if element.tag == "Layout"}
    popups = {key for key, element in ids.items() if element.tag == "PopupMenu"}
    for element in elements:
        for attr in BITMAP_ATTRS.get(element.tag, ()):
            reference = element.get(attr)
            if reference and reference != "none" and reference not in bitmaps:
                result.errors.append(f"{label(element)}: unknown bitmap {attr}={reference}")
        for attr in ("font", "tooltipfont"):
            reference = element.get(attr)
            if reference and reference not in fonts:
                result.errors.append(f"{label(element)}: unknown font {reference}")
        states = BITMAP_ATTRS.get(element.tag, ()) if element.tag in {"Button", "Checkbox", "Slider"} else ()
        sizes = {bitmaps[element.get(attr)] for attr in states if element.get(attr) in bitmaps and attr != "background"}
        if len(sizes) > 1:
            result.errors.append(f"{label(element)}: state bitmaps have different frame dimensions: {sorted(sizes)}")
        if element.tag == "SliderBackground" and element.get("image") in bitmaps:
            width, height = bitmaps[element.get("image")]
            nx, ny = integer(element, "nbhoriz", 1, 1), integer(element, "nbvert", 1, 1)
            px, py = integer(element, "padhoriz", 0, 0), integer(element, "padvert", 0, 0)
            if (width + px) % nx or (height + py) % ny:
                result.errors.append(f"{label(element)}: sprite dimensions/padding do not divide into {nx}x{ny} frames")
        if element.tag == "RadialSlider" and element.get("sequence") in bitmaps:
            n = integer(element, "nbimages", 1, 1)
            if bitmaps[element.get("sequence")][1] % n:
                result.errors.append(f"{label(element)}: sequence height does not divide by nbimages")
        for attr in ("action", "action1", "action2"):
            for action in filter(None, (x.strip() for x in element.get(attr, "").split(";"))):
                if action in BUILTIN_ACTIONS:
                    continue
                if element.tag == "Image" and attr == "action" and action in {"move", "resizeE", "resizeS", "resizeSE"}:
                    continue
                match = re.fullmatch(r"(.+)\.(show|hide|maximize|unmaximize)\(\)", action)
                if match:
                    targets = windows | popups if match[2] == "show" else windows
                    if match[1] not in targets:
                        result.errors.append(f"{label(element)}: unknown action target {match[1]}")
                    continue
                match = re.fullmatch(r"(.+)\.setLayout\((.+)\)", action)
                if match:
                    window, layout = match.groups()
                    if window not in windows or layout not in layouts:
                        result.errors.append(f"{label(element)}: unknown window/layout in {action}")
                    elif ids[layout].getparent() is not ids[window]:
                        result.errors.append(f"{label(element)}: layout {layout} belongs to another window")
                    continue
                result.warnings.append(f"{label(element)}: action not recognized for VLC 3.0: {action}")
        for attr in ("visible", "state", "focus"):
            expression = element.get(attr)
            if expression is None:
                continue
            tokens = re.findall(r"[\w.-]+(?:\(\))?", expression)
            for token in tokens:
                if token in BOOL_VARS or token in {"and", "or", "not"}:
                    continue
                match = re.fullmatch(r"(.+)\.(isVisible|isMaximized|isActive)(?:\(\))?", token)
                if match and match[1] in (layouts if match[2] == "isActive" else windows):
                    continue
                result.warnings.append(f"{label(element)}: boolean variable not recognized: {token}")
        if element.tag in {"Slider", "RadialSlider"}:
            value = element.get("value", "none")
            nested_tree = element.getparent() is not None and element.getparent().tag == "Playtree"
            if value not in PERCENT_VARS and not nested_tree:
                result.errors.append(f"{label(element)}: unknown percentage variable {value}")
        if element.tag in {"Slider", "Anchor"}:
            points = element.get("points", "(0,0)" if element.tag == "Anchor" else "")
            pair = r"\(\s*-?\d+\s*,\s*-?\d+\s*\)"
            if not re.fullmatch(rf"\s*{pair}(?:\s*,\s*{pair})*\s*", points):
                result.errors.append(f"{label(element)}: invalid points; expected (x,y),(x,y)")
        if element.tag == "Playlist":
            result.warnings.append(f"{label(element)}: Playlist is deprecated; prefer Playtree")

    # Geometry warnings are informational: a control can intentionally straddle
    # an edge, and VLC also supports percentage coordinates and position presets.
    def geometry(element: etree._Element, box: tuple[int, int], offset: tuple[int, int] = (0, 0)) -> None:
        if element.tag in {"Group", "Panel"}:
            try:
                x, y = int(element.get("x", "0")), int(element.get("y", "0"))
                if element.tag == "Panel":
                    box = (int(element.get("width", "0")), int(element.get("height", "0")))
                    offset = (0, 0)
                else:
                    offset = (offset[0] + x, offset[1] + y)
            except ValueError:
                return
        elif element.tag in {"Image", "Button", "Checkbox", "Text", "Video", "Playtree", "Playlist"}:
            try:
                x = int(element.get("x", "0")) + offset[0]
                y = int(element.get("y", "0")) + offset[1]
                key = element.get({"Button": "up", "Checkbox": "up1", "Image": "image"}.get(element.tag, ""), "")
                bw, bh = bitmaps.get(key, (0, 0))
                w, h = int(element.get("width", str(bw))), int(element.get("height", str(bh)))
                if element.tag == "Image":
                    w, h = (w if w > 0 else bw), (h if h > 0 else bh)
                if element.tag == "Text":
                    font = ids.get(element.get("font", ""))
                    h = int(font.get("size", "12")) if font is not None else 12
                # Zero-sized Panels are legitimate anchor containers in the
                # shipped VLC skin, not clipping bounds.
                outside = x < 0 or y < 0 or (box[0] > 0 and x + w > box[0]) or (box[1] > 0 and y + h > box[1])
                if element.get("position", "-1") == "-1" and w > 0 and h > 0 and outside:
                    result.warnings.append(f"{label(element)}: rectangle ({x},{y},{w},{h}) exceeds {box[0]}x{box[1]} container")
            except ValueError:
                pass
        for child in element:
            if isinstance(child.tag, str):
                geometry(child, box, offset)

    for element in elements:
        if element.tag == "Layout":
            width, height = integer(element, "width", 0, 1), integer(element, "height", 0, 1)
            for axis, initial in (("width", width), ("height", height)):
                minimum = integer(element, f"min{axis}", -1)
                maximum = integer(element, f"max{axis}", -1)
                if (minimum > 0 and initial < minimum) or (maximum > 0 and initial > maximum) or (minimum > 0 and maximum > 0 and minimum > maximum):
                    result.errors.append(f"{label(element)}: initial {axis} and resize limits disagree")
            geometry(element, (width, height))
    return result


def print_result(result: ValidationResult) -> None:
    print(f"DTD: {result.dtd}")
    for message in result.errors:
        print(f"ERROR: {message}")
    for message in result.warnings:
        print(f"WARNING: {message}")
    print(f"{'PASS' if result.ok else 'FAIL'}: {len(result.files)} source/assets; {len(result.errors)} errors; {len(result.warnings)} warnings")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="skin directory or its theme.xml")
    parser.add_argument("--dtd", type=Path, help="use a particular skin.dtd")
    parser.add_argument("--strict", action="store_true", help="also fail on warnings")
    args = parser.parse_args()
    try:
        result = validate_skin(args.source, args.dtd)
    except ValueError as exc:
        parser.error(str(exc))
    print_result(result)
    return 0 if result.ok and not (args.strict and result.warnings) else 1


if __name__ == "__main__":
    raise SystemExit(main())
