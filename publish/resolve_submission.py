#!/usr/bin/env python3
"""Resolve edition metadata from a publish submission commit tree (not diff names)."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

from publish.submission_ref import SUBMISSION_BRANCH_RE
from publish.validate import sha256_file

EDITION_JSON = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\.json$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def git_show_object(
    commit: str, path: str, dest: str, *, cwd: str | None = None
) -> None:
    proc = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        capture_output=True,
        check=False,
        cwd=cwd,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git show {commit}:{path} failed: {proc.stderr.decode()}")
    with open(dest, "wb") as f:
        f.write(proc.stdout)


def ls_tree_paths(commit: str, *, cwd: str | None = None) -> list[str]:
    """All blob paths in the commit tree (not the parent diff)."""
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", commit],
        capture_output=True,
        check=True,
        text=True,
        cwd=cwd,
    )
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


def edition_date_from_ref(ref_name: str | None) -> str | None:
    if not ref_name:
        return None
    m = SUBMISSION_BRANCH_RE.match(ref_name)
    return m.group("date") if m else None


def detect_edition_date(paths: list[str], ref_name: str | None) -> str:
    for path in paths:
        m = EDITION_JSON.match(path)
        if m:
            return m.group("date")
    from_ref = edition_date_from_ref(ref_name)
    if from_ref:
        for path in paths:
            if path == f"x/{from_ref}.png":
                return from_ref
    raise RuntimeError(
        f"cannot determine edition date from tree {paths!r} ref={ref_name!r}"
    )


def materialize_json(
    commit: str, edition_date: str, paths: list[str], work_dir: str, *, git_cwd: str
) -> str:
    json_rel = f"{edition_date}.json"
    dest = os.path.join(work_dir, json_rel)
    if json_rel in paths:
        git_show_object(commit, json_rel, dest, cwd=git_cwd)
        return dest
    # PNG-only submission tree: edition JSON already on main.
    for ref in ("origin/main", "main"):
        proc = subprocess.run(
            ["git", "show", f"{ref}:{json_rel}"],
            capture_output=True,
            check=False,
            cwd=git_cwd,
        )
        if proc.returncode == 0:
            with open(dest, "wb") as f:
                f.write(proc.stdout)
            return dest
    raise RuntimeError(
        f"{json_rel} not in submission {commit} and not found on main"
    )


def resolve(
    commit: str,
    *,
    ref_name: str | None = None,
    work_dir: str,
) -> dict[str, str]:
    if not SHA40.match(commit):
        raise RuntimeError(f"invalid commit sha: {commit!r}")

    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.join(work_dir, "x"), exist_ok=True)

    git_cwd = work_dir if os.path.isdir(os.path.join(work_dir, ".git")) else None
    paths = ls_tree_paths(commit, cwd=git_cwd)
    edition_date = detect_edition_date(paths, ref_name)

    png_rel = f"x/{edition_date}.png"
    if png_rel not in paths:
        raise RuntimeError(f"missing {png_rel} in submission tree")

    if not git_cwd:
        raise RuntimeError("resolve requires a git work_dir with .git for materialize")
    json_path = materialize_json(commit, edition_date, paths, work_dir, git_cwd=git_cwd)
    git_show_object(commit, png_rel, os.path.join(work_dir, png_rel), cwd=git_cwd)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("date") != edition_date:
        raise RuntimeError("JSON date field mismatch")

    return {
        "edition_date": edition_date,
        "date_label": data["date_label"],
        "json_sha256": sha256_file(json_path),
        "png_sha256": sha256_file(os.path.join(work_dir, png_rel)),
        "source_sha": commit,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--ref-name", default=None, help="e.g. publish/submissions/2026-11-11-abc")
    ap.add_argument("--work-dir", default=".")
    ap.add_argument("--github-output", default=None)
    args = ap.parse_args(argv)
    try:
        meta = resolve(args.commit, ref_name=args.ref_name, work_dir=args.work_dir)
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
