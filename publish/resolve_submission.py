#!/usr/bin/env python3
"""Resolve edition metadata from explicit .publish/submission.json manifest."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

from publish.submission_manifest import (
    MANIFEST_PATH,
    ManifestError,
    parse_manifest,
    validate_manifest_against_files,
    validate_manifest_against_ref,
)
from publish.validate import sha256_file

SHA40 = re.compile(r"^[0-9a-f]{40}$")


def git_show_bytes(commit: str, path: str, *, cwd: str | None = None) -> bytes:
    proc = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        capture_output=True,
        check=False,
        cwd=cwd,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git show {commit}:{path} failed: {proc.stderr.decode()}")
    return proc.stdout


def git_show_object(
    commit: str, path: str, dest: str, *, cwd: str | None = None
) -> None:
    with open(dest, "wb") as f:
        f.write(git_show_bytes(commit, path, cwd=cwd))


def materialize_edition_json(
    commit: str,
    edition_date: str,
    *,
    png_only: bool,
    work_dir: str,
    git_cwd: str,
) -> str:
    json_rel = f"{edition_date}.json"
    dest = os.path.join(work_dir, json_rel)
    if not png_only:
        git_show_object(commit, json_rel, dest, cwd=git_cwd)
        return dest
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
    raise RuntimeError(f"png_only submission but {json_rel} not on main")


def resolve(
    commit: str,
    *,
    ref_name: str | None = None,
    work_dir: str,
) -> dict[str, str]:
    if not SHA40.match(commit):
        raise RuntimeError(f"invalid commit sha: {commit!r}")

    git_cwd = work_dir if os.path.isdir(os.path.join(work_dir, ".git")) else None
    if not git_cwd:
        raise RuntimeError("resolve requires a git work_dir with .git")

    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.join(work_dir, "x"), exist_ok=True)

    manifest_raw = git_show_bytes(commit, MANIFEST_PATH, cwd=git_cwd)
    doc = parse_manifest(manifest_raw)
    validate_manifest_against_ref(doc, ref_name)

    edition_date = doc["edition_date"]
    png_rel = f"x/{edition_date}.png"
    png_only = bool(doc.get("png_only"))

    json_path = materialize_edition_json(
        commit,
        edition_date,
        png_only=png_only,
        work_dir=work_dir,
        git_cwd=git_cwd,
    )
    git_show_object(commit, png_rel, os.path.join(work_dir, png_rel), cwd=git_cwd)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    json_hash = sha256_file(json_path)
    png_hash = sha256_file(os.path.join(work_dir, png_rel))
    validate_manifest_against_files(
        doc,
        json_sha256=json_hash,
        png_sha256=png_hash,
        json_date=data.get("date", ""),
    )

    return {
        "edition_date": edition_date,
        "date_label": data["date_label"],
        "json_sha256": json_hash,
        "png_sha256": png_hash,
        "source_sha": commit,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", required=True)
    ap.add_argument(
        "--ref-name",
        default=None,
        help="push event ref (omit on workflow_dispatch replay)",
    )
    ap.add_argument("--work-dir", default=".")
    ap.add_argument("--github-output", default=None)
    args = ap.parse_args(argv)
    try:
        meta = resolve(args.commit, ref_name=args.ref_name or None, work_dir=args.work_dir)
    except (RuntimeError, ManifestError, json.JSONDecodeError, OSError) as e:
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
