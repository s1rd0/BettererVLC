#!/usr/bin/env python3
"""Generate the live VLC Skins2 XML for the exported VLC Redesign assets."""

from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
from skin_constants import SEEK_FRAMES, VOLUME_FRAMES


BASE_WIDTH, BASE_HEIGHT = 1280, 720
TOP, BOTTOM = 40, 54
GRAY = "#8F8F8F"
ORANGE = "#D37918"
ANCHOR_BOTTOM = {"lefttop": "leftbottom", "rightbottom": "leftbottom"}
ANCHOR_RIGHT_BOTTOM = {"lefttop": "rightbottom", "rightbottom": "rightbottom"}
ANCHOR_RIGHT_TOP = {"lefttop": "righttop", "rightbottom": "righttop"}
STATES = ("up", "over", "down")
BUTTONS = (
    "prev", "play", "pause", "next", "menu", "sidebar", "folder", "minimize",
    "maximize", "fullscreen", "close", "audio", "subtitles", "settings", "playlist",
    "mute", "unmute", "home", "video", "library", "stream", "lists", "recent", "add",
    "shuffle", "shuffle-on", "repeat", "repeat-on", "load", "save", "delete",
)
IMAGES = (
    "bg", "field", "topbar", "sidebar-bg", "rail-bg", "idle-logo", "title-logo",
    "seek", "seek-track", "vol-knob", "vol-track",
)


def node(parent: ET.Element, tag: str, **attributes: object) -> ET.Element:
    return ET.SubElement(parent, tag, {key: str(value) for key, value in attributes.items()})


def picture(parent: ET.Element, identity: str, image: str, x: int, y: int, **extra: object) -> ET.Element:
    return node(parent, "Image", id=identity, image=image, x=x, y=y, **extra)


def button(parent: ET.Element, identity: str, asset: str, x: int, y: int,
           action: str, tooltip: str, **extra: object) -> ET.Element:
    return node(parent, "Button", id=identity, x=x, y=y,
                up=f"{asset}-up", over=f"{asset}-over", down=f"{asset}-down",
                action=action, tooltiptext=tooltip, **extra)


def checkbox(parent: ET.Element, identity: str, off: str, on: str, x: int, y: int,
             state: str, action1: str, action2: str, tooltip1: str, tooltip2: str,
             **extra: object) -> ET.Element:
    return node(parent, "Checkbox", id=identity, x=x, y=y, state=state,
                up1=f"{off}-up", over1=f"{off}-over", down1=f"{off}-down",
                up2=f"{on}-up", over2=f"{on}-over", down2=f"{on}-down",
                action1=action1, action2=action2,
                tooltiptext1=tooltip1, tooltiptext2=tooltip2, **extra)


def text(parent: ET.Element, identity: str, value: str, x: int, y: int, width: int,
         font: str = "ui12", **extra: object) -> ET.Element:
    return node(parent, "Text", id=identity, text=value, font=font, x=x, y=y,
                width=width, color=GRAY, scrolling="none", focus="false", **extra)


def popup(theme: ET.Element) -> None:
    menu = node(theme, "PopupMenu", id="mainMenu")
    for label, action in (
        ("Open file…", "dialogs.fileSimple()"),
        ("Open folder…", "dialogs.directory()"),
        ("Open disc…", "dialogs.disc()"),
        ("Open network stream…", "dialogs.net()"),
        (None, None),
        ("Play", "vlc.play()"), ("Pause", "vlc.pause()"), ("Stop", "vlc.stop()"),
        ("Previous", "playlist.previous()"), ("Next", "playlist.next()"),
        (None, None),
        ("Show playlist", "main.setLayout(library)"),
        ("Player view", "main.setLayout(player)"),
        ("Load playlist…", "playlist.load()"), ("Save playlist…", "playlist.save()"),
        (None, None),
        ("Media information…", "dialogs.fileInfo()"),
        ("Preferences…", "dialogs.prefs()"),
        ("VLC context menu", "dialogs.popup()"),
        ("Change skin…", "dialogs.changeSkin()"),
        (None, None), ("Quit", "vlc.quit()"),
    ):
        node(menu, "MenuSeparator") if label is None else node(menu, "MenuItem", label=label, action=action)


def titlebar(layout: ET.Element, prefix: str, width: int) -> None:
    for maximized in (False, True):
        picture(layout, f"{prefix}.titlebar.{int(maximized)}", "topbar", 0, 0,
                width=width, height=TOP, resize="scale", rightbottom="righttop",
                action="move", action2="main.unmaximize()" if maximized else "main.maximize()",
                visible="main.isMaximized" if maximized else "not main.isMaximized")
    picture(layout, f"{prefix}.brand", "title-logo", 13, 8)
    button(layout, f"{prefix}.menu", "menu", 51, 6, "mainMenu.show()", "Media and playback menu")
    checkbox(layout, f"{prefix}.sidebar", "sidebar", "sidebar", 89, 6,
             "library.isActive", "main.setLayout(library)", "main.setLayout(player)",
             "Show playlist", "Hide playlist")
    button(layout, f"{prefix}.folder", "folder", 141, 6,
           "dialogs.fileSimple()", "Open media file")
    text(layout, f"{prefix}.section", "Videos", 173, 13, 90, "ui14")
    text(layout, f"{prefix}.idle-title", "VLC Media Player", 310, 13, width - 620,
         "ui14", rightbottom="righttop", alignment="center", visible="vlc.isStopped")
    text(layout, f"{prefix}.media-title", "$N", 310, 13, width - 620,
         "ui14", rightbottom="righttop", alignment="center", visible="not vlc.isStopped")
    button(layout, f"{prefix}.minimize", "minimize", width - 150, 8,
           "vlc.minimize()", "Minimize", **ANCHOR_RIGHT_TOP)
    checkbox(layout, f"{prefix}.maximize", "maximize", "maximize", width - 114, 8,
             "main.isMaximized", "main.maximize()", "main.unmaximize()",
             "Maximize", "Restore window", **ANCHOR_RIGHT_TOP)
    button(layout, f"{prefix}.fullscreen", "fullscreen", width - 78, 8,
           "vlc.fullscreen()", "Toggle fullscreen", **ANCHOR_RIGHT_TOP)
    button(layout, f"{prefix}.close", "close", width - 42, 8,
           "vlc.quit()", "Close VLC", **ANCHOR_RIGHT_TOP)


def transport(layout: ET.Element, prefix: str, width: int, height: int,
              bar_height: int = BOTTOM) -> None:
    y = height - bar_height
    picture(layout, f"{prefix}.transport-bg", "bg", 0, y,
            width=width, height=bar_height, resize="scale",
            lefttop="leftbottom", rightbottom="rightbottom", action="move")
    button(layout, f"{prefix}.previous", "prev", 20, y + 15,
           "playlist.previous()", "Previous item", **ANCHOR_BOTTOM)
    checkbox(layout, f"{prefix}.play-pause", "play", "pause", 58, y + 13,
             "vlc.isPlaying", "vlc.play()", "vlc.pause()", "Play", "Pause", **ANCHOR_BOTTOM)
    button(layout, f"{prefix}.next", "next", 120, y + 15,
           "playlist.next()", "Next item", **ANCHOR_BOTTOM)
    text(layout, f"{prefix}.elapsed", "$T", 170, y + 21, 78, "ui15", **ANCHOR_BOTTOM)
    # VLC scales the curve and sprite using max(point)+1 as their natural
    # dimensions. Keep height=15, not the sprite's 28, so y=14 stays centered.
    seeker = node(layout, "Slider", id=f"{prefix}.seek", x=254, y=y + 13,
                  width=width - 677, height=15, points="(4,14),(602,14)",
                  value="time", up="seek", thickness=16, tooltiptext="$T / $D",
                  lefttop="leftbottom", rightbottom="rightbottom")
    node(seeker, "SliderBackground", id=f"{prefix}.seek-background", image="seek-track", nbvert=SEEK_FRAMES)
    text(layout, f"{prefix}.duration", "$D", width - 420, y + 21, 78, "ui15",
         **ANCHOR_RIGHT_BOTTOM)
    checkbox(layout, f"{prefix}.mute", "unmute", "mute", width - 324, y + 13,
             "vlc.isMute", "vlc.mute()", "vlc.mute()", "Mute", "Unmute",
             **ANCHOR_RIGHT_BOTTOM)
    volume = node(layout, "Slider", id=f"{prefix}.volume", x=width - 292, y=y + 13,
                  points="(3,14),(85,14)", value="volume", up="vol-knob",
                  tooltiptext="Volume: $V%", thickness=16, **ANCHOR_RIGHT_BOTTOM)
    node(volume, "SliderBackground", id=f"{prefix}.volume-background", image="vol-track", nbvert=VOLUME_FRAMES)
    for asset, distance, action, tooltip in (
        ("audio", 184, "dialogs.audioPopup()", "Audio tracks and audio settings"),
        ("subtitles", 142, "dialogs.videoPopup()", "Subtitles and video settings"),
        ("settings", 100, "dialogs.prefs()", "Preferences"),
        ("playlist", 50, "main.setLayout(library)", "Show playlist"),
    ):
        if prefix == "fullscreen" and asset == "playlist":
            action = "vlc.fullscreen();main.setLayout(library)"
        button(layout, f"{prefix}.{asset}", asset, width - distance, y + 11,
               action, tooltip, **ANCHOR_RIGHT_BOTTOM)


def library_sidebar(layout: ET.Element, prefix: str, height: int) -> None:
    picture(layout, f"{prefix}.sidebar-bg", "sidebar-bg", 50, TOP,
            width=377, height=height - TOP - BOTTOM, resize="scale", rightbottom="leftbottom")
    picture(layout, f"{prefix}.rail-bg", "rail-bg", 0, TOP,
            width=50, height=height - TOP - BOTTOM, resize="scale", rightbottom="leftbottom")
    for index, (asset, action, tooltip) in enumerate((
        ("home", "main.setLayout(player)", "Player view"),
        ("video", "dialogs.fileSimple()", "Open video or audio"),
        ("library", "dialogs.directory()", "Open a media folder"),
        ("stream", "dialogs.net()", "Open a network stream"),
        ("lists", "playlist.load()", "Load a playlist"),
        ("recent", "dialogs.playlist()", "Open VLC playlist and media library"),
    )):
        button(layout, f"{prefix}.nav.{asset}", asset, 10, 62 + index * 42, action, tooltip)
    button(layout, f"{prefix}.nav.add", "add", 10, height - 128,
           "playlist.add()", "Add files to playlist", **ANCHOR_BOTTOM)
    text(layout, f"{prefix}.playlist-title", "Playlist", 70, 68, 240, "ui20")
    text(layout, f"{prefix}.playlist-help", "Drop files here", 70, 108, 220)
    checkbox(layout, f"{prefix}.shuffle", "shuffle", "shuffle-on", 326, 92,
             "playlist.isRandom", "playlist.setRandom(true)", "playlist.setRandom(false)",
             "Enable shuffle", "Disable shuffle")
    checkbox(layout, f"{prefix}.repeat", "repeat", "repeat-on", 358, 92,
             "playlist.isLoop", "playlist.setLoop(true)", "playlist.setLoop(false)",
             "Repeat playlist", "Disable repeat")
    button(layout, f"{prefix}.add-files", "add", 70, 127, "playlist.add()", "Add files")
    text(layout, f"{prefix}.add-label", "Add files", 110, 135, 190, "ui14")
    for asset, x, action, tooltip in (
        ("load", 326, "playlist.load()", "Load playlist"),
        ("save", 358, "playlist.save()", "Save playlist"),
        ("delete", 390, "playlist.del()", "Remove selected items"),
    ):
        button(layout, f"{prefix}.{asset}", asset, x, 128, action, tooltip)
    node(layout, "Playtree", id=f"{prefix}.live-playlist", x=70, y=165,
         width=337, height=height - 239, font="ui14", flat="true",
         fgcolor="#A6A6A6", playcolor=ORANGE, selcolor="#2C2A27",
         bgcolor1="#0E0E0E", bgcolor2="#0E0E0E", rightbottom="leftbottom",
         help="Double-click an item to play; use the mouse wheel to scroll")


def build_theme(source: Path, width: int = BASE_WIDTH, height: int = BASE_HEIGHT) -> Path:
    if width < 1000 or height < 600:
        raise ValueError("main layout must be at least 1000x600")
    # VLC builds Theme before Font objects. The implicit defaultfont is the
    # built-in FreeSans font resolved on demand; a custom tooltip font is not
    # registered yet at this point in the native builder.
    theme = ET.Element("Theme", version="2.0", magnet="15")
    node(theme, "ThemeInfo", name="VLC Redesign", author="Juxtopposed; VLC Skins2 adaptation",
         webpage="https://www.figma.com/community/file/1691465999134370980/vlc-redesign")
    for size in (12, 14, 15, 20):
        node(theme, "Font", id=f"ui{size}", file="assets/Inter-Regular.ttf", size=size)
    for asset in IMAGES:
        node(theme, "Bitmap", id=asset, file=f"assets/{asset}.png", alphacolor="#FF00FF")
    for asset in BUTTONS:
        for state in STATES:
            identity = f"{asset}-{state}"
            node(theme, "Bitmap", id=identity, file=f"assets/{identity}.png", alphacolor="#FF00FF")
    popup(theme)
    main = node(theme, "Window", id="main", position="Center", dragdrop="true", playondrop="true")
    # Skins2 selects each layout while building it, so the last one is the
    # initial layout when there is no previously saved window configuration.
    for identity, sidebar in (("library", True), ("player", False)):
        layout = node(main, "Layout", id=identity, width=width, height=height,
                      minwidth=1000, minheight=600, maxwidth=7680, maxheight=4320)
        picture(layout, f"{identity}.background", "bg", 0, 0,
                width=width, height=height, resize="scale", rightbottom="rightbottom")
        left = 447 if sidebar else 10
        right_margin = 20 if sidebar else 10
        video_width = width - left - right_margin
        picture(layout, f"{identity}.field", "field", left, TOP,
                width=video_width, height=height - TOP - BOTTOM, resize="scale", rightbottom="rightbottom")
        picture(layout, f"{identity}.idle-art", "idle-logo",
                left + (video_width - 192) // 2, TOP + (height - TOP - BOTTOM - 192) // 2,
                width=192, height=192, resize="scale2", art="true", visible="not vlc.hasVout",
                xkeepratio="true", ykeepratio="true")
        node(layout, "Video", id=f"{identity}.video", x=left, y=TOP,
             width=video_width, height=height - TOP - BOTTOM, autoresize="false",
             visible="vlc.hasVout", rightbottom="rightbottom")
        if sidebar:
            library_sidebar(layout, identity, height)
        titlebar(layout, identity, width)
        transport(layout, identity, width, height)
        picture(layout, f"{identity}.resize-east", "bg", width - 4, TOP,
                width=4, height=height - TOP - BOTTOM, resize="scale", action="resizeE",
                lefttop="righttop", rightbottom="rightbottom")
        picture(layout, f"{identity}.resize-south", "bg", 0, height - 4,
                width=width, height=4, resize="scale", action="resizeS",
                lefttop="leftbottom", rightbottom="rightbottom")
        picture(layout, f"{identity}.resize-corner", "bg", width - 12, height - 12,
                width=12, height=12, resize="scale", action="resizeSE", **ANCHOR_RIGHT_BOTTOM)
    controller = node(theme, "Window", id="fullscreenController", position="South", ymargin="3%")
    fullscreen = node(controller, "Layout", id="fullscreen-controls", width=1000, height=64,
                      minwidth=1000, maxwidth=1000, minheight=64, maxheight=64)
    transport(fullscreen, "fullscreen", 1000, 64, bar_height=64)
    source.mkdir(parents=True, exist_ok=True)
    ET.indent(theme, space="  ")
    output = source / "theme.xml"
    # VLC's pull reader does not emit an end event for self-closing tags. A
    # self-closing Playtree leaves parser context active and redirects every
    # following Slider to playtree.slider, overriding its time/volume binding.
    data = ET.tostring(theme, encoding="unicode", short_empty_elements=False)
    output.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                      '<!DOCTYPE Theme PUBLIC "-//VideoLAN//DTD VLC Skins V2.0//EN" "skin.dtd">\n'
                      + data + "\n", encoding="utf-8", newline="\n")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "skin",
                        help="directory in which to write theme.xml (default: repository skin/)")
    parser.add_argument("--width", type=int, default=BASE_WIDTH)
    parser.add_argument("--height", type=int, default=BASE_HEIGHT)
    args = parser.parse_args()
    try:
        output = build_theme(args.source, args.width, args.height)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    print(f"Created {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
