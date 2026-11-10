"""Explicit submission identity (authoritative for push and workflow_dispatch replay)."""
from __future__ import annotations

import json
from typing import Any

from publish.submission_ref import (
    submission_content_id,
    submission_ref_name,
    SUBMISSION_BRANCH_RE,
)

MANIFEST_PATH = ".publish/submission.json"
MANIFEST_VERSION = 1


class ManifestError(RuntimeError):
    pass


def build_manifest(
    edition_date: str,
    json_sha256: str,
    png_sha256: str,
    *,
    png_only: bool = False,
) -> bytes:
    cid = submission_content_id(json_sha256, png_sha256)
    doc = {
        "manifest_version": MANIFEST_VERSION,
        "edition_date": edition_date,
        "json_sha256": json_sha256,
        "png_sha256": png_sha256,
        "content_id": cid,
        "png_only": png_only,
    }
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def parse_manifest(raw: bytes) -> dict[str, Any]:
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ManifestError(f"invalid manifest JSON: {e}") from e
    if doc.get("manifest_version") != MANIFEST_VERSION:
        raise ManifestError(f"unsupported manifest_version: {doc.get('manifest_version')!r}")
    for key in ("edition_date", "json_sha256", "png_sha256", "content_id"):
        if not isinstance(doc.get(key), str) or not doc[key]:
            raise ManifestError(f"manifest missing or invalid {key}")
    expected_cid = submission_content_id(doc["json_sha256"], doc["png_sha256"])
    if doc["content_id"] != expected_cid:
        raise ManifestError(
            f"manifest content_id {doc['content_id']!r} != derived {expected_cid!r}"
        )
    return doc


def validate_manifest_against_ref(doc: dict[str, Any], ref_name: str | None) -> None:
    if not ref_name:
        return
    m = SUBMISSION_BRANCH_RE.match(ref_name)
    if not m:
        raise ManifestError(f"ref {ref_name!r} is not a publish/submissions branch")
    ref_date, ref_id = m.group("date"), m.group("id")
    if doc["edition_date"] != ref_date:
        raise ManifestError(
            f"manifest edition_date {doc['edition_date']!r} != ref date {ref_date!r}"
        )
    if doc["content_id"] != ref_id:
        raise ManifestError(
            f"manifest content_id {doc['content_id']!r} != ref id {ref_id!r}"
        )
    expected_ref = submission_ref_name(
        doc["edition_date"], doc["json_sha256"], doc["png_sha256"]
    )
    if ref_name != expected_ref:
        raise ManifestError(f"ref {ref_name!r} != expected {expected_ref!r}")


def validate_manifest_against_files(
    doc: dict[str, Any],
    *,
    json_sha256: str,
    png_sha256: str,
    json_date: str,
) -> None:
    if json_sha256 != doc["json_sha256"]:
        raise ManifestError("materialized JSON sha256 != manifest")
    if png_sha256 != doc["png_sha256"]:
        raise ManifestError("materialized PNG sha256 != manifest")
    if json_date != doc["edition_date"]:
        raise ManifestError("edition JSON date field != manifest edition_date")
