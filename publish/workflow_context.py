"""Validate workflow inputs from GitHub Actions context."""
from __future__ import annotations

import argparse
import re
import sys

SHA40 = re.compile(r"^[0-9a-f]{40}$")


def validate_submission_sha(raw: str) -> str:
    value = (raw or "").strip().lower()
    if not SHA40.match(value):
        raise ValueError(f"submission_sha must be 40-char lowercase hex, got {raw!r}")
    return value


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--github-output")
    args = ap.parse_args(argv)
    try:
        sha = validate_submission_sha(args.raw)
    except ValueError as e:
        print(f"invalid submission sha: {e}", file=sys.stderr)
        return 1
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as f:
            f.write(f"submission_sha={sha}\n")
    else:
        print(sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
