#!/usr/bin/env python3
"""Validate and deterministically package referenced VLC skin assets as .vlt."""

from __future__ import annotations

import argparse
import gzip
import io
import os
from pathlib import Path
import tarfile

from validate_skin import print_result, validate_skin


def package_skin(source: Path, output: Path, dtd: Path | None = None, strict: bool = False) -> None:
    result = validate_skin(source, dtd)
    print_result(result)
    if not result.ok or (strict and result.warnings):
        raise ValueError("skin validation failed; archive was not created")
    # Redistributed font/design licenses travel with the skin even though VLC
    # has no XML reference for plain-text license documents.
    for name in ('ATTRIBUTION.txt', 'assets/OFL-Inter.txt'):
        notice = result.source / name
        if notice.is_file() and notice.resolve().is_relative_to(result.source):
            result.files.add(notice.resolve())
    output = output.resolve()
    if output.suffix.lower() != ".vlt":
        raise ValueError("output must have the .vlt extension")
    if output in result.files:
        raise ValueError("output would overwrite a source asset")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as compressed:
                with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                    for asset in sorted(result.files, key=lambda p: p.relative_to(result.source).as_posix()):
                        contents = asset.read_bytes()
                        member = tarfile.TarInfo(asset.relative_to(result.source).as_posix())
                        member.size = len(contents)
                        member.mode = 0o644
                        member.mtime = 0
                        member.uid = member.gid = 0
                        member.uname = member.gname = ""
                        archive.addfile(member, io.BytesIO(contents))
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(f"Created {output} ({output.stat().st_size:,} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="skin directory or its theme.xml")
    parser.add_argument("output", type=Path, help="destination .vlt")
    parser.add_argument("--dtd", type=Path, help="use a particular skin.dtd")
    parser.add_argument("--strict", action="store_true", help="also fail on validation warnings")
    args = parser.parse_args()
    try:
        package_skin(args.source, args.output, args.dtd, args.strict)
    except (ValueError, OSError, tarfile.TarError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
