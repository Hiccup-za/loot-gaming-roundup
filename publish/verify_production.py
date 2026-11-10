#!/usr/bin/env python3
"""Confirm production serves today's edition JSON and exact Artist PNG hash."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

from publish.validate import PublishValidationError

DEFAULT_SITE_URL = "https://loot-gaming-roundup.vercel.app"
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 12
DEFAULT_RETRY_DELAY = 15


def fetch(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "loot-publish-verify/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise PublishValidationError(f"HTTP {resp.status} for {url}")
        return resp.read()


def verify_production(
    edition_date: str,
    expected_png_sha256: str,
    *,
    site_url: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    retry_delay: int = DEFAULT_RETRY_DELAY,
) -> None:
    site = (site_url or os.environ.get("LOOT_SITE_URL") or DEFAULT_SITE_URL).rstrip(
        "/"
    )
    json_url = f"{site}/{edition_date}.json"
    png_url = f"{site}/x/{edition_date}.png"
    last_err: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            raw_json = fetch(json_url, timeout)
            data = json.loads(raw_json.decode("utf-8"))
            if data.get("date") != edition_date:
                raise PublishValidationError(
                    f"production JSON date is {data.get('date')!r}, expected {edition_date}"
                )
            img = (data.get("x_post") or {}).get("image")
            if img != f"/x/{edition_date}.png":
                raise PublishValidationError(
                    f"production x_post.image is {img!r}, expected /x/{edition_date}.png"
                )

            png_bytes = fetch(png_url, timeout)
            png_hash = hashlib.sha256(png_bytes).hexdigest()
            if png_hash != expected_png_sha256.lower():
                raise PublishValidationError(
                    f"production PNG sha256 mismatch: got {png_hash}, "
                    f"expected {expected_png_sha256}"
                )
            print(f"production verified: {json_url} date OK, {png_url} sha256 OK")
            return
        except (urllib.error.URLError, PublishValidationError, json.JSONDecodeError) as e:
            last_err = e
            if attempt < retries:
                print(
                    f"verify attempt {attempt}/{retries} failed ({e}); "
                    f"retrying in {retry_delay}s…",
                    file=sys.stderr,
                )
                time.sleep(retry_delay)
            continue

    raise PublishValidationError(
        f"production verify failed after {retries} attempts: {last_err}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--edition-date", required=True)
    ap.add_argument("--expected-png-sha256", required=True)
    ap.add_argument("--site-url", default=None)
    ap.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    ap.add_argument("--retry-delay", type=int, default=DEFAULT_RETRY_DELAY)
    args = ap.parse_args(argv)

    # Allow local file check mode for tests via env — production path uses HTTP only.
    try:
        verify_production(
            args.edition_date,
            args.expected_png_sha256,
            site_url=args.site_url,
            retries=args.retries,
            retry_delay=args.retry_delay,
        )
    except PublishValidationError as e:
        print(f"production verification failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
