#!/usr/bin/env python3
"""Parent-side entry point: validate artefacts and queue automated publish.

Reads edition JSON and Artist PNG from the parent routine's paths, validates,
uploads a single commit to ``publish/inbox`` on GitHub via the **``gh`` CLI**
(``gh api`` — credentials stay inside gh; this script never reads or prints tokens).
A push to ``publish/inbox`` starts ``publish-edition.yml`` on GitHub Actions.
No pull request and **no workflow_dispatch** from the parent.

Prerequisite: parent executor has normal ``gh auth login`` with permission to
**push** this repository (see ``scripts/publish_readiness.py``).

  LOOT_PUBLISH_REPO_OWNER (optional, default Hiccup-za)
  LOOT_PUBLISH_REPO       (optional, default loot-gaming-roundup)

Typical paths after the daily routine + Artist:

  JSON: /workspace/.../loot-gaming-roundup/YYYY-MM-DD.json  (or routine output dir)
  PNG:  /workspace/marketing/loot-x/out/YYYY-MM-DD.png
"""
from __future__ import annotations

import argparse
import os
import sys

# Repo root on path for publish.* imports when run as scripts/submit_edition.py
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from publish.github_client import GitHubAPIError, client_from_env
from publish.validate import PublishValidationError, validate_edition_bundle

INBOX_REF = "heads/publish/inbox"


def upload_inbox(
    client,
    edition_date: str,
    json_bytes: bytes,
    png_bytes: bytes,
    *,
    dry_run: bool,
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
    message = f"publish inbox: {edition_date} edition JSON + Artist PNG"
    commit_sha = client.create_commit(message, tree_sha, [main_sha])
    if dry_run:
        print(f"dry-run: would update {INBOX_REF} to {commit_sha}")
        return commit_sha
    try:
        client.update_ref(INBOX_REF, commit_sha, force=True)
    except GitHubAPIError as e:
        if e.status not in (404, 422):
            raise
        client.create_ref(INBOX_REF, commit_sha)
    print(f"updated {INBOX_REF} → {commit_sha}")
    return commit_sha


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--edition-date", required=True, help="YYYY-MM-DD")
    ap.add_argument(
        "--json-path",
        required=True,
        help="path to edition JSON source file",
    )
    ap.add_argument(
        "--png-path",
        required=True,
        help="Artist output, e.g. /workspace/marketing/loot-x/out/YYYY-MM-DD.png",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and show hashes only; do not call GitHub",
    )
    args = ap.parse_args(argv)

    json_path = os.path.abspath(args.json_path)
    png_path = os.path.abspath(args.png_path)

    # Validate in a temp layout so paths match publish conventions.
    import tempfile
    import shutil

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

    with open(json_path, "rb") as f:
        json_bytes = f.read()
    with open(png_path, "rb") as f:
        png_bytes = f.read()

    if args.dry_run:
        print("dry-run: skipping GitHub inbox upload")
        return 0

    from publish.gh_cli import gh_auth_ok

    if not gh_auth_ok():
        print(
            "submit failed: gh is not authenticated. "
            "Run scripts/publish_readiness.py on the parent executor.",
            file=sys.stderr,
        )
        return 1

    try:
        client = client_from_env()
        commit_sha = upload_inbox(
            client,
            args.edition_date,
            json_bytes,
            png_bytes,
            dry_run=False,
        )
    except (RuntimeError, GitHubAPIError) as e:
        print(f"submit failed: {e}", file=sys.stderr)
        return 1

    print(
        f"pushed publish/inbox → {commit_sha} for {args.edition_date}; "
        f"GitHub Actions publish workflow should start from the push. "
        f"Track: https://github.com/{client.owner}/{client.repo}/actions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
