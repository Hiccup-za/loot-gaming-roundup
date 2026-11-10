#!/usr/bin/env python3
"""Strict validation for automated edition publish (JSON + Artist PNG)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys

import build

EDITION_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXPECTED_PNG_SIZE = (1200, 675)


class PublishValidationError(Exception):
    """One or more publish checks failed."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def png_dimensions(path: str) -> tuple[int, int]:
    with open(path, "rb") as f:
        if f.read(8) != b"\x89PNG\r\n\x1a\n":
            raise PublishValidationError(f"{path}: not a PNG file")
        length = struct.unpack(">I", f.read(4))[0]
        if length != 13 or f.read(4) != b"IHDR":
            raise PublishValidationError(f"{path}: missing IHDR chunk")
        width, height = struct.unpack(">II", f.read(8))
        return width, height


def validate_x_post_strict(data: dict, root: str) -> None:
    errors: list[str] = []

    def err(msg: str) -> None:
        errors.append(msg)

    build.validate_x_post(data, root, warn=err)
    if errors:
        raise PublishValidationError(
            "x_post validation failed:\n  - " + "\n  - ".join(errors)
        )


def validate_edition_bundle(
    root: str,
    edition_date: str,
    *,
    json_path: str | None = None,
    png_path: str | None = None,
    require_x_post: bool = True,
) -> dict[str, str]:
    """Return sha256 hashes for json and png when validation succeeds."""
    if not EDITION_DATE_RE.match(edition_date):
        raise PublishValidationError(f"invalid edition_date: {edition_date}")

    json_path = json_path or os.path.join(root, f"{edition_date}.json")
    png_path = png_path or os.path.join(root, "x", f"{edition_date}.png")

    if not os.path.isfile(json_path):
        raise PublishValidationError(f"missing edition JSON: {json_path}")
    if not os.path.isfile(png_path):
        raise PublishValidationError(f"missing Artist PNG: {png_path}")

    with open(json_path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise PublishValidationError(f"invalid JSON in {json_path}: {e}") from e

    if data.get("date") != edition_date:
        raise PublishValidationError(
            f"JSON date {data.get('date')!r} does not match edition {edition_date}"
        )
    if not isinstance(data.get("date_label"), str) or not data["date_label"].strip():
        raise PublishValidationError("JSON date_label must be a non-empty string")

    if require_x_post and not data.get("x_post"):
        raise PublishValidationError("JSON must include x_post for publish")

    validate_x_post_strict(data, root)

    x_post = data.get("x_post") or {}
    expected_image = f"/x/{edition_date}.png"
    if x_post.get("image") != expected_image:
        raise PublishValidationError(
            f"x_post.image must be {expected_image!r}, got {x_post.get('image')!r}"
        )

    w, h = png_dimensions(png_path)
    if (w, h) != EXPECTED_PNG_SIZE:
        raise PublishValidationError(
            f"PNG must be {EXPECTED_PNG_SIZE[0]}×{EXPECTED_PNG_SIZE[1]}, got {w}×{h}"
        )

    return {
        "json_sha256": sha256_file(json_path),
        "png_sha256": sha256_file(png_path),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--edition-date", required=True)
    ap.add_argument("--root", default=os.getcwd())
    ap.add_argument(
        "--json-path",
        help="override path to edition JSON (default: ROOT/YYYY-MM-DD.json)",
    )
    ap.add_argument(
        "--png-path",
        help="override path to PNG (default: ROOT/x/YYYY-MM-DD.png)",
    )
    ap.add_argument(
        "--print-hashes",
        action="store_true",
        help="print json_sha256 and png_sha256 on success",
    )
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        hashes = validate_edition_bundle(
            root,
            args.edition_date,
            json_path=args.json_path,
            png_path=args.png_path,
        )
    except PublishValidationError as e:
        print(f"publish validation failed: {e}", file=sys.stderr)
        return 1
    if args.print_hashes:
        print(f"json_sha256={hashes['json_sha256']}")
        print(f"png_sha256={hashes['png_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
