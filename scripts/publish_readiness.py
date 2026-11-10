#!/usr/bin/env python3
"""Non-destructive publish readiness check using existing ``gh`` authentication.

Uses ``gh auth status`` and read-only GitHub API calls. Never prints, exports, or
copies tokens. Exits 0 only when the parent executor can push the publish inbox ref.

Does **not** modify repository content.
"""
from __future__ import annotations

import argparse
import sys

_REPO_ROOT = __import__("os").path.dirname(
    __import__("os").path.dirname(__import__("os").path.abspath(__file__))
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from publish.gh_cli import GhCliError, gh_api, gh_auth_ok, require_gh

DEFAULT_OWNER = "Hiccup-za"
DEFAULT_REPO = "loot-gaming-roundup"
WORKFLOW_NAME = "publish-edition.yml"


def check(*, owner: str, repo: str, require_workflow_on_main: bool) -> int:
    errors: list[str] = []
    notes: list[str] = []

    try:
        require_gh()
    except GhCliError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    if not gh_auth_ok():
        errors.append("gh is not authenticated (run `gh auth login` on the parent executor)")
    else:
        notes.append("gh auth: OK (credentials present; token not inspected)")

    prefix = f"repos/{owner}/{repo}"
    try:
        meta = gh_api("GET", prefix)
    except GhCliError as e:
        errors.append(f"cannot read repository metadata: {e}")
        meta = {}

    perms = meta.get("permissions") or {}
    if perms.get("push") is not True:
        errors.append(
            "GitHub token used by gh does not have push permission on this repository "
            f"(permissions.push={perms.get('push')!r}). "
            "Inbox upload requires contents write / git push to refs/heads/publish/inbox."
        )
    else:
        notes.append("repo permissions.push: true")

    try:
        gh_api("GET", f"{prefix}/git/ref/heads/main")
        notes.append("read ref heads/main: OK")
    except GhCliError as e:
        errors.append(f"cannot read main ref: {e}")

    notes.append(
        "submit path: create immutable ref publish/submissions/{date}-{contentId} (no force-push)"
    )

    if require_workflow_on_main:
        try:
            wf = gh_api(
                "GET",
                f"{prefix}/actions/workflows/{WORKFLOW_NAME}",
            )
            if wf.get("state") != "active":
                errors.append(f"{WORKFLOW_NAME} exists but state={wf.get('state')!r}")
            else:
                notes.append(f"workflow {WORKFLOW_NAME} on default branch: active")
        except GhCliError:
            errors.append(
                f"{WORKFLOW_NAME} not found on the repository default branch "
                "(merge setup PR #23 first)"
            )

    notes.append(
        "trigger path: push to publish/submissions/* (no workflow_dispatch / Actions write on parent)"
    )

    for line in notes:
        print(line)

    if errors:
        print("\nReadiness: NOT READY (fail closed)", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "\nIf gh cannot push, a separate credential with repository contents write "
            "would be required — gh does not expose that token for export; use `gh auth login` "
            "with an account that can push this repo, or configure git credentials the same way "
            "other repo commits are made from the parent environment.",
            file=sys.stderr,
        )
        return 1

    print("\nReadiness: OK for submit_edition.py (validate + submission ref create)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--owner", default=DEFAULT_OWNER)
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument(
        "--require-workflow-on-main",
        action="store_true",
        help="also require publish-edition.yml on default branch (post–setup PR merge)",
    )
    args = ap.parse_args(argv)
    return check(
        owner=args.owner,
        repo=args.repo,
        require_workflow_on_main=args.require_workflow_on_main,
    )


if __name__ == "__main__":
    raise SystemExit(main())
