#!/usr/bin/env python3
"""Confirm production serves edition JSON, PNG, and rendered HTML for home + edition routes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum

from publish.validate import PublishValidationError

DEFAULT_SITE_URL = "https://loot-gaming-roundup.vercel.app"
DEFAULT_TIMEOUT = 45
DEFAULT_RETRIES = 25
DEFAULT_RETRY_DELAY = 24  # ~10 minutes total bounded wait

DATE_LABEL_IN_HTML = re.compile(
    r'<div class="date">([^<]+)</div>',
    re.IGNORECASE,
)


class VerifyStatus(Enum):
    OK = "ok"
    PENDING_DEPLOY = "pending_deploy"
    CONTENT_ERROR = "content_error"


@dataclass
class VerifyResult:
    status: VerifyStatus
    detail: str


def fetch(url: str, timeout: int) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "loot-publish-verify/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read(), resp.headers.get("Content-Type", "")


def html_date_labels(html: str) -> list[str]:
    return [m.group(1).strip() for m in DATE_LABEL_IN_HTML.finditer(html)]


def verify_production(
    edition_date: str,
    expected_date_label: str,
    expected_png_sha256: str,
    *,
    site_url: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    retry_delay: int = DEFAULT_RETRY_DELAY,
) -> VerifyResult:
    site = (site_url or os.environ.get("LOOT_SITE_URL") or DEFAULT_SITE_URL).rstrip(
        "/"
    )
    edition_paths = (f"/{edition_date}", f"/{edition_date}.html")
    json_url = f"{site}/{edition_date}.json"
    png_url = f"{site}/x/{edition_date}.png"
    home_url = f"{site}/"
    expected_png = expected_png_sha256.lower()
    last_pending: str | None = None

    for attempt in range(1, retries + 1):
        pending_reasons: list[str] = []
        hard_errors: list[str] = []

        try:
            _, raw_json, _ = fetch(json_url, timeout)
            data = json.loads(raw_json.decode("utf-8"))
            if data.get("date") != edition_date:
                hard_errors.append(
                    f"JSON date is {data.get('date')!r}, expected {edition_date}"
                )
            if data.get("date_label") != expected_date_label:
                hard_errors.append(
                    f"JSON date_label mismatch (production vs expected bundle)"
                )
            img = (data.get("x_post") or {}).get("image")
            if img != f"/x/{edition_date}.png":
                hard_errors.append(f"x_post.image is {img!r}")

            _, png_bytes, png_ct = fetch(png_url, timeout)
            if "image" not in png_ct.lower():
                pending_reasons.append(f"PNG content-type {png_ct!r}")
            png_hash = hashlib.sha256(png_bytes).hexdigest()
            if png_hash != expected_png:
                # Wrong hash with HTTP 200 is a content error, not deploy lag.
                hard_errors.append(
                    f"PNG sha256 {png_hash} != expected {expected_png}"
                )

            _, home_html, _ = fetch(home_url, timeout)
            home_labels = html_date_labels(home_html.decode("utf-8", errors="replace"))
            if expected_date_label not in home_labels:
                pending_reasons.append(
                    f"home page date not yet {expected_date_label!r} (saw {home_labels[:2]})"
                )

            edition_ok = False
            for path in edition_paths:
                _, ed_html, _ = fetch(f"{site}{path}", timeout)
                labels = html_date_labels(ed_html.decode("utf-8", errors="replace"))
                if expected_date_label in labels:
                    edition_ok = True
                    break
            if not edition_ok:
                pending_reasons.append(
                    f"edition routes missing date label {expected_date_label!r}"
                )

            if hard_errors:
                return VerifyResult(
                    VerifyStatus.CONTENT_ERROR,
                    "; ".join(hard_errors),
                )

            if not pending_reasons:
                return VerifyResult(
                    VerifyStatus.OK,
                    f"verified JSON, PNG, /, and {edition_paths}",
                )

            last_pending = "; ".join(pending_reasons)
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            last_pending = str(e)

        if attempt < retries:
            print(
                f"verify attempt {attempt}/{retries}: deploy may still be pending ({last_pending}); "
                f"retrying in {retry_delay}s…",
                file=sys.stderr,
            )
            time.sleep(retry_delay)

    return VerifyResult(
        VerifyStatus.PENDING_DEPLOY,
        f"timed out after ~{retries * retry_delay}s waiting for deploy: {last_pending}",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--edition-date", required=True)
    ap.add_argument("--expected-date-label", required=True)
    ap.add_argument("--expected-png-sha256", required=True)
    ap.add_argument("--site-url", default=None)
    ap.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    ap.add_argument("--retry-delay", type=int, default=DEFAULT_RETRY_DELAY)
    args = ap.parse_args(argv)

    result = verify_production(
        args.edition_date,
        args.expected_date_label,
        args.expected_png_sha256,
        site_url=args.site_url,
        retries=args.retries,
        retry_delay=args.retry_delay,
    )
    if result.status == VerifyStatus.OK:
        print(result.detail)
        return 0
    if result.status == VerifyStatus.PENDING_DEPLOY:
        print(f"production verify pending: {result.detail}", file=sys.stderr)
        print(
            "::warning::Publish commit on main is not reverted automatically. "
            "Re-run verification or wait for Vercel and check production manually.",
            file=sys.stderr,
        )
        return 2
    print(f"production content error: {result.detail}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
