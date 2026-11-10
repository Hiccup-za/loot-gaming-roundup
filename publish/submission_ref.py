"""Immutable publish submission ref names and idempotency helpers."""
from __future__ import annotations

import hashlib
import re

EDITION_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SUBMISSION_BRANCH_RE = re.compile(
    r"^publish/submissions/(?P<date>\d{4}-\d{2}-\d{2})-(?P<id>[0-9a-f]{16})$"
)


def submission_content_id(json_sha256: str, png_sha256: str) -> str:
    digest = hashlib.sha256(f"{json_sha256}:{png_sha256}".encode()).hexdigest()
    return digest[:16]


def submission_ref_name(edition_date: str, json_sha256: str, png_sha256: str) -> str:
    if not EDITION_DATE_RE.match(edition_date):
        raise ValueError(f"invalid edition date: {edition_date}")
    sid = submission_content_id(json_sha256, png_sha256)
    return f"publish/submissions/{edition_date}-{sid}"


def submission_ref_head(ref_name: str) -> str:
    return f"heads/{ref_name}"
