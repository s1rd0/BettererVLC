#!/usr/bin/env python3
"""Check effective Skins2 slider bindings using the installed VLC 3.x XML reader.

This regression uses libvlccore's real xml_ReaderCreate/reader callbacks, then
replays the relevant SkinParser state transitions. It catches a VLC 3.x bug:
its Skins2 XMLParser never synthesizes an end callback for an empty Playtree,
so later Sliders unexpectedly bind to playtree.slider. No GUI is launched.

Sources: modules/gui/skins2/parser/{xmlparser,skin_parser}.cpp and
include/{vlc_xml,vlc_common}.h in VideoLAN's 3.0.x branch.
"""

from __future__ import annotations

import argparse
import ctypes as C
import json
import os
from pathlib import Path
import re
import tarfile


class CommonMembers(C.Structure):
    _fields_ = [("object_type", C.c_void_p), ("header", C.c_void_p),
                ("flags", C.c_int), ("force", C.c_bool),
                ("libvlc", C.c_void_p), ("parent", C.c_void_p)]


class XMLReader(C.Structure):
    # VLC 3.x ABI, from include/vlc_xml.h and VLC_COMMON_MEMBERS.
    _fields_ = [("obj", CommonMembers), ("sys", C.c_void_p),
                ("stream", C.c_void_p), ("module", C.c_void_p),
                ("next_node", C.c_void_p), ("next_attr", C.c_void_p),
                ("use_dtd", C.c_void_p), ("is_empty", C.c_void_p)]


class NativeReader:
    def __init__(self, directory: Path):
        self.directory_handle = os.add_dll_directory(str(directory))
        self.library = C.CDLL(str(directory / "libvlccore.dll"))
        lib = self.library
        lib.libvlc_InternalCreate.restype = C.c_void_p
        lib.libvlc_InternalInit.argtypes = [C.c_void_p, C.c_int, C.POINTER(C.c_char_p)]
        lib.libvlc_InternalInit.restype = C.c_int
        lib.vlc_stream_MemoryNew.argtypes = [C.c_void_p, C.c_void_p, C.c_size_t, C.c_bool]
        lib.vlc_stream_MemoryNew.restype = C.c_void_p
        lib.xml_ReaderCreate.argtypes = [C.c_void_p, C.c_void_p]
        lib.xml_ReaderCreate.restype = C.POINTER(XMLReader)
        for name in ("xml_ReaderDelete", "vlc_stream_Delete",
                     "libvlc_InternalCleanup", "libvlc_InternalDestroy"):
            getattr(lib, name).argtypes = [C.c_void_p]
            getattr(lib, name).restype = None
        self.instance = lib.libvlc_InternalCreate()
        if not self.instance:
            raise RuntimeError("could not create native VLC core")
        arguments = (C.c_char_p * 4)(b"native-xml-binding-check", b"--ignore-config",
                                    b"--no-plugins-cache", b"--no-media-library")
        if lib.libvlc_InternalInit(self.instance, 4, arguments) != 0:
            lib.libvlc_InternalDestroy(self.instance)
            self.instance = None
            raise RuntimeError("could not initialize native VLC core")

    def close(self):
        if self.instance:
            self.library.libvlc_InternalCleanup(self.instance)
            self.library.libvlc_InternalDestroy(self.instance)
            self.instance = None
        self.directory_handle.close()

    def effective_bindings(self, xml: bytes) -> list[dict[str, str]]:
        # DTD validation is performed separately by validate_skin.py. Omit its
        # declaration here so this parser regression requires no catalog/file IO.
        xml = re.sub(rb"<!DOCTYPE\s+[^>]+>", b"", xml, count=1)
        buffer = C.create_string_buffer(xml)
        stream = self.library.vlc_stream_MemoryNew(self.instance, buffer, len(xml), True)
        if not stream:
            raise RuntimeError("could not create native VLC memory stream")
        reader = self.library.xml_ReaderCreate(self.instance, stream)
        if not reader:
            self.library.vlc_stream_Delete(stream)
            raise RuntimeError("could not create native VLC XML reader")
        next_node = C.CFUNCTYPE(C.c_int, C.c_void_p, C.POINTER(C.c_char_p))(reader.contents.next_node)
        next_attr = C.CFUNCTYPE(C.c_char_p, C.c_void_p, C.POINTER(C.c_char_p))(reader.contents.next_attr)
        current_tree = ""
        layout = ""
        bindings = []
        try:
            while True:
                name = C.c_char_p()
                kind = next_node(reader, C.byref(name))
                if kind < 0:
                    raise ValueError("native VLC XML reader rejected XML")
                if kind == 0:
                    break
                tag = name.value.decode("utf-8")
                if kind == 1:  # XML_READER_STARTELEM
                    attributes = {}
                    while True:
                        value = C.c_char_p()
                        key = next_attr(reader, C.byref(value))
                        if key is None:
                            break
                        attributes[key.decode("utf-8")] = value.value.decode("utf-8")
                    if tag == "Layout":
                        layout = attributes.get("id", "none")
                    elif tag in {"Playtree", "Playlist"}:
                        current_tree = attributes.get("id", "none")
                    elif tag == "Slider":
                        requested = attributes.get("value", "none")
                        bindings.append({"id": attributes.get("id", "none"),
                                         "layout": layout, "requested": requested,
                                         "effective": "playtree.slider" if current_tree else requested})
                elif kind == 2 and tag in {"Playtree", "Playlist"}:
                    current_tree = ""  # SkinParser::handleEndElement
        finally:
            self.library.xml_ReaderDelete(reader)
            self.library.vlc_stream_Delete(stream)
        return bindings


def expected_bindings() -> dict[str, str]:
    return {f"{prefix}.{kind}": value
            for prefix in ("library", "player", "fullscreen")
            for kind, value in (("seek", "time"), ("volume", "volume"))}


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vlc-dir", type=Path,
                        default=Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "VideoLAN/VLC")
    args = parser.parse_args()
    native = NativeReader(args.vlc_dir.resolve())
    try:
        source = (root / "skin/theme.xml").read_bytes()
        with tarfile.open(root / "dist/VLC-Redesign.vlt", "r:gz") as archive:
            packaged = archive.extractfile("theme.xml").read()
        expected = expected_bindings()
        positive = native.effective_bindings(source)
        packed = native.effective_bindings(packaged)
        for label, bindings in (("source", positive), ("archive", packed)):
            actual = {entry["id"]: entry["effective"] for entry in bindings}
            if actual != expected or len(bindings) != 6:
                raise AssertionError(f"{label}: expected six independent bindings, got {actual}")
        old_xml, mutations = re.subn(rb"<(Playtree|Playlist)(\s[^>]*?)>\s*</\1>",
                                     rb"<\1\2 />", source)
        if mutations < 1:
            raise AssertionError("positive XML has no explicitly closed tree for negative regression")
        negative = native.effective_bindings(old_xml)
        if len(negative) != 6 or not all(entry["effective"] == "playtree.slider" for entry in negative):
            raise AssertionError(f"old self-closing tree did not reproduce six aliased bindings: {negative}")
        report = {"parser": "installed VLC 3.x libvlccore + libxml_plugin (native C API)",
                  "positive_source": positive, "positive_archive": packed,
                  "old_self_closing_tree_negative": negative,
                  "passed": True}
        output = root / "build/slider-binding-regression.json"
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("PASS: native VLC reader confirms six independent time/volume bindings in source and archive.")
        print("PASS: old self-closing Playtree reproduces all six incorrectly bound to playtree.slider.")
        print(f"Report: {output}")
    finally:
        native.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
