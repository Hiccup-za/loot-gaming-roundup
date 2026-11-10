#!/usr/bin/env python3
"""Resolve edition metadata from a publish submission commit (push event)."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

from publish.validate import sha256_file

EDITION_JSON = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\.json$")


def git_show_object(commit: str, path: str, dest: str) -> None:
    proc = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git show {commit}:{path} failed: {proc.stderr.decode()}")
    with open(dest, "wb") as f:
        f.write(proc.stdout)


def list_commit_paths(commit: str) -> list[str]:
    proc = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", commit],
        capture_output=True,
        check=True,
        text=True,
    )
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


def resolve(commit: str, *, work_dir: str) -> dict[str, str]:
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.join(work_dir, "x"), exist_ok=True)

    edition_date = ""
    for path in list_commit_paths(commit):
        m = EDITION_JSON.match(path)
        if m:
            edition_date = m.group("date")
            break
    if not edition_date:
        raise RuntimeError(f"no YYYY-MM-DD.json in submission commit {commit}")

    json_rel = f"{edition_date}.json"
    png_rel = f"x/{edition_date}.png"
    git_show_object(commit, json_rel, os.path.join(work_dir, json_rel))
    git_show_object(commit, png_rel, os.path.join(work_dir, png_rel))

    with open(os.path.join(work_dir, json_rel), encoding="utf-8") as f:
        data = json.load(f)
    if data.get("date") != edition_date:
        raise RuntimeError("submission JSON date field mismatch")

    return {
        "edition_date": edition_date,
        "date_label": data["date_label"],
        "json_sha256": sha256_file(os.path.join(work_dir, json_rel)),
        "png_sha256": sha256_file(os.path.join(work_dir, png_rel)),
        "source_sha": commit,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--work-dir", default=".")
    ap.add_argument("--github-output", default=None)
    args = ap.parse_args(argv)
    try:
        meta = resolve(args.commit, work_dir=args.work_dir)
    except (RuntimeError, json.JSONDecodeError, OSError) as e:
        print(f"resolve failed: {e}", file=sys.stderr)
        return 1
    out = args.github_output
    if out:
        with open(out, "a", encoding="utf-8") as f:
            for k, v in meta.items():
                f.write(f"{k}={v}\n")
    else:
        for k, v in meta.items():
            print(f"{k}={v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
