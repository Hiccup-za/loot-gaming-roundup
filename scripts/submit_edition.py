#!/usr/bin/env python3
"""Parent-side entry point: validate artefacts and queue automated publish.

Creates an **immutable** ref ``publish/submissions/{date}-{contentId}`` (no force-push
overwrite). A push starts ``publish-edition.yml`` on GitHub Actions.

Uses the **``gh`` CLI** only (``gh api``); never prints or exports tokens.

Prerequisite: ``python3 scripts/publish_readiness.py`` exits 0 on the parent executor.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import os
import shutil
import sys
import tempfile

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from publish.github_client import GitHubAPIError, client_from_env
from publish.submission_ref import submission_ref_head, submission_ref_name
from publish.validate import PublishValidationError, validate_edition_bundle


def create_submission_commit(
    client,
    edition_date: str,
    json_bytes: bytes,
    png_bytes: bytes,
) -> str:
    main_sha = client.ref_sha("heads/main")
    main_commit = client._request("GET", f"/git/commits/{main_sha}")
    base_tree = main_commit["tree"]["sha"]

    json_blob = client.create_blob(json_bytes, binary=False)
    png_blob = client.create_blob(png_bytes, binary=True)
    tree_sha = client.create_tree(
        base_tree,
        [
            {
                "path": f"{edition_date}.json",
                "mode": "100644",
                "type": "blob",
                "sha": json_blob,
            },
            {
                "path": f"x/{edition_date}.png",
                "mode": "100644",
                "type": "blob",
                "sha": png_blob,
            },
        ],
    )
    message = f"publish submission: {edition_date}"
    return client.create_commit(message, tree_sha, [main_sha])


def file_hashes_match_commit(client, commit_sha: str, edition_date: str, hashes: dict[str, str]) -> bool:
    """Compare JSON/PNG blob hashes at commit paths to expected content hashes."""
    commit = client._request("GET", f"/git/commits/{commit_sha}")
    tree_sha = commit["tree"]["sha"]
    tree = client._request("GET", f"/git/trees/{tree_sha}?recursive=1")
    paths = {e["path"]: e["sha"] for e in tree.get("tree", []) if e["type"] == "blob"}
    needed = {f"{edition_date}.json", f"x/{edition_date}.png"}
    if not needed.issubset(paths):
        return False
    for path, blob_sha in paths.items():
        if path not in needed:
            continue
        blob = client._request("GET", f"/git/blobs/{blob_sha}")
        raw = base64.b64decode(blob["content"])
        digest = hashlib.sha256(raw).hexdigest()
        if path.endswith(".json") and digest != hashes["json_sha256"]:
            return False
        if path.endswith(".png") and digest != hashes["png_sha256"]:
            return False
    return True


def upload_submission(
    client,
    edition_date: str,
    json_bytes: bytes,
    png_bytes: bytes,
    hashes: dict[str, str],
    *,
    dry_run: bool,
) -> tuple[str, str]:
    ref_name = submission_ref_name(edition_date, hashes["json_sha256"], hashes["png_sha256"])
    head = submission_ref_head(ref_name)
    commit_sha = create_submission_commit(client, edition_date, json_bytes, png_bytes)
    if dry_run:
        print(f"dry-run: would create ref {ref_name} → {commit_sha}")
        return commit_sha, ref_name

    try:
        client.create_ref(head, commit_sha)
        print(f"created {ref_name} → {commit_sha}")
        return commit_sha, ref_name
    except GitHubAPIError as e:
        if e.status != 422:
            raise
        existing_sha = client.ref_sha(head)
        if file_hashes_match_commit(client, existing_sha, edition_date, hashes):
            print(f"idempotent: {ref_name} already exists with same content ({existing_sha})")
            return existing_sha, ref_name
        raise RuntimeError(
            f"ref {ref_name} exists but content differs; use new artefacts or inspect {existing_sha}"
        ) from e


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--edition-date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--json-path", required=True)
    ap.add_argument("--png-path", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    json_path = os.path.abspath(args.json_path)
    png_path = os.path.abspath(args.png_path)

    with tempfile.TemporaryDirectory() as tmp:
        shutil.copyfile(json_path, os.path.join(tmp, f"{args.edition_date}.json"))
        os.makedirs(os.path.join(tmp, "x"), exist_ok=True)
        shutil.copyfile(png_path, os.path.join(tmp, "x", f"{args.edition_date}.png"))
        try:
            hashes = validate_edition_bundle(tmp, args.edition_date)
        except PublishValidationError as e:
            print(f"validation failed: {e}", file=sys.stderr)
            return 1

    print(f"json_sha256={hashes['json_sha256']}")
    print(f"png_sha256={hashes['png_sha256']}")
    print(f"submission_ref={submission_ref_name(args.edition_date, hashes['json_sha256'], hashes['png_sha256'])}")

    with open(json_path, "rb") as f:
        json_bytes = f.read()
    with open(png_path, "rb") as f:
        png_bytes = f.read()

    if args.dry_run:
        print("dry-run: skipping GitHub upload")
        return 0

    from publish.gh_cli import gh_auth_ok

    if not gh_auth_ok():
        print("submit failed: gh not authenticated; run publish_readiness.py", file=sys.stderr)
        return 1

    try:
        client = client_from_env()
        commit_sha, ref_name = upload_submission(
            client,
            args.edition_date,
            json_bytes,
            png_bytes,
            hashes,
            dry_run=False,
        )
    except (RuntimeError, GitHubAPIError) as e:
        print(f"submit failed: {e}", file=sys.stderr)
        return 1

    print(
        f"queued {ref_name} ({commit_sha}). "
        f"Actions: https://github.com/{client.owner}/{client.repo}/actions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
