"""Realistic multi-edition main tree + explicit manifest identity."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from datetime import date, timedelta

from publish.resolve_submission import resolve
from publish.submission_manifest import (
    ManifestError,
    MANIFEST_PATH,
    build_manifest,
    parse_manifest,
    validate_manifest_against_ref,
)
from publish.submission_ref import submission_content_id, submission_ref_name
from publish.validate import sha256_file


def _run(cmd: list[str], *, cwd: str, input: bytes | None = None) -> str:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        check=True,
        input=input,
    )
    return proc.stdout.decode() if proc.stdout else ""


def _edition_doc(edition: str, label: str) -> dict:
    return {
        "date": edition,
        "date_label": label,
        "x_post": {
            "template": "haul",
            "data": {},
            "text": "t",
            "image": f"/x/{edition}.png",
            "time": "08:00",
        },
    }


class MultiEditionMainFixture:
    """31 edition JSONs on main (2026-10-11 … 2026-11-10) like production repo shape."""

    def __init__(self) -> None:
        self.repo = tempfile.mkdtemp()
        _run(["git", "init", "-b", "main"], cwd=self.repo)
        _run(["git", "config", "user.email", "t@example.com"], cwd=self.repo)
        _run(["git", "config", "user.name", "t"], cwd=self.repo)
        self.dates = []
        start = date(2026, 10, 11)
        for i in range(31):
            d = start + timedelta(days=i)
            ds = d.isoformat()
            self.dates.append(ds)
            label = f"{d.strftime('%A')} {d.day} {d.strftime('%B %Y')}"
            with open(os.path.join(self.repo, f"{ds}.json"), "w", encoding="utf-8") as f:
                json.dump(_edition_doc(ds, label), f)
            os.makedirs(os.path.join(self.repo, "x"), exist_ok=True)
            with open(os.path.join(self.repo, "x", f"{ds}.png"), "wb") as f:
                f.write(b"\x89PNG\n" + ds.encode() + b"\n")
        _run(["git", "add", "."], cwd=self.repo)
        _run(["git", "commit", "-m", "31 editions on main"], cwd=self.repo)
        self.main_sha = _run(["git", "rev-parse", "HEAD"], cwd=self.repo).strip()

    @property
    def latest(self) -> str:
        return self.dates[-1]

def sha256_file_from_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def make_submission_on_main_tree(
    repo: str,
    main_sha: str,
    edition: str,
    json_bytes: bytes,
    png_bytes: bytes,
    *,
    png_only: bool = False,
) -> tuple[str, str]:
    j_hash = sha256_file_from_bytes(json_bytes)
    p_hash = sha256_file_from_bytes(png_bytes)
    manifest = build_manifest(edition, j_hash, p_hash, png_only=png_only)
    man_blob = _run(["git", "hash-object", "-w", "--stdin"], cwd=repo, input=manifest).strip()
    png_blob = _run(
        ["git", "hash-object", "-w", "--stdin"], cwd=repo, input=png_bytes
    ).strip()
    parent_tree = _run(["git", "rev-parse", f"{main_sha}^{{tree}}"], cwd=repo).strip()
    _run(["git", "read-tree", parent_tree], cwd=repo)
    _run(["git", "checkout-index", "-a", "-f"], cwd=repo)
    os.makedirs(os.path.join(repo, ".publish"), exist_ok=True)
    os.makedirs(os.path.join(repo, "x"), exist_ok=True)
    with open(os.path.join(repo, MANIFEST_PATH), "wb") as f:
        f.write(manifest)
    with open(os.path.join(repo, "x", f"{edition}.png"), "wb") as f:
        f.write(png_bytes)
    if not png_only:
        with open(os.path.join(repo, f"{edition}.json"), "wb") as f:
            f.write(json_bytes)
    _run(["git", "add", "-A"], cwd=repo)
    tree = _run(["git", "write-tree"], cwd=repo).strip()
    sub_sha = _run(
        ["git", "commit-tree", tree, "-p", main_sha, "-m", f"publish submission: {edition}"],
        cwd=repo,
    ).strip()
    ref = submission_ref_name(edition, j_hash, p_hash)
    return sub_sha, ref


class RealisticSubmissionProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = MultiEditionMainFixture()

    def test_latest_edition_on_31_file_main(self):
        edition = self.fx.latest
        with open(os.path.join(self.fx.repo, f"{edition}.json"), "rb") as f:
            jb = f.read()
        with open(os.path.join(self.fx.repo, "x", f"{edition}.png"), "rb") as f:
            pb = f.read()
        sub_sha, ref = make_submission_on_main_tree(
            self.fx.repo, self.fx.main_sha, edition, jb, pb
        )
        meta = resolve(sub_sha, ref_name=ref, work_dir=self.fx.repo)
        self.assertEqual(meta["edition_date"], edition)
        self.assertEqual(meta["edition_date"], "2026-11-10")

    def test_png_only_latest_on_multi_edition_main(self):
        edition = self.fx.latest
        with open(os.path.join(self.fx.repo, f"{edition}.json"), "rb") as f:
            jb = f.read()
        pb = b"\x89PNG\nreplacement haul\n"
        sub_sha, ref = make_submission_on_main_tree(
            self.fx.repo, self.fx.main_sha, edition, jb, pb, png_only=True
        )
        meta = resolve(sub_sha, ref_name=ref, work_dir=self.fx.repo)
        self.assertEqual(meta["edition_date"], edition)
        self.assertEqual(meta["png_sha256"], sha256_file_from_bytes(pb))

    def test_dispatch_replay_no_ref_name(self):
        edition = self.fx.latest
        with open(os.path.join(self.fx.repo, f"{edition}.json"), "rb") as f:
            jb = f.read()
        with open(os.path.join(self.fx.repo, "x", f"{edition}.png"), "rb") as f:
            pb = f.read()
        sub_sha, _ref = make_submission_on_main_tree(
            self.fx.repo, self.fx.main_sha, edition, jb, pb
        )
        meta = resolve(sub_sha, ref_name=None, work_dir=self.fx.repo)
        self.assertEqual(meta["edition_date"], edition)

    def test_unchanged_replay_empty_commit_tree_still_has_manifest(self):
        edition = self.fx.latest
        with open(os.path.join(self.fx.repo, f"{edition}.json"), "rb") as f:
            jb = f.read()
        with open(os.path.join(self.fx.repo, "x", f"{edition}.png"), "rb") as f:
            pb = f.read()
        sub_sha, ref = make_submission_on_main_tree(
            self.fx.repo, self.fx.main_sha, edition, jb, pb
        )
        _run(["git", "commit", "--allow-empty", "-m", "noop"], cwd=self.fx.repo)
        meta = resolve(sub_sha, ref_name=ref, work_dir=self.fx.repo)
        self.assertEqual(meta["edition_date"], edition)

    def test_conflicting_ref_vs_manifest_fails_closed(self):
        edition = self.fx.latest
        with open(os.path.join(self.fx.repo, f"{edition}.json"), "rb") as f:
            jb = f.read()
        with open(os.path.join(self.fx.repo, "x", f"{edition}.png"), "rb") as f:
            pb = f.read()
        sub_sha, ref = make_submission_on_main_tree(
            self.fx.repo, self.fx.main_sha, edition, jb, pb
        )
        bad_ref = ref.replace(edition, "2026-10-11")
        with self.assertRaises(ManifestError):
            resolve(sub_sha, ref_name=bad_ref, work_dir=self.fx.repo)

    def test_conflicting_manifest_content_id(self):
        edition = self.fx.latest
        doc = parse_manifest(
            build_manifest(
                edition,
                "a" * 64,
                "b" * 64,
            )
        )
        self.assertEqual(doc["content_id"], submission_content_id("a" * 64, "b" * 64))
        with self.assertRaises(ManifestError):
            parse_manifest(
                json.dumps(
                    {
                        "manifest_version": 1,
                        "edition_date": edition,
                        "json_sha256": "a" * 64,
                        "png_sha256": "b" * 64,
                        "content_id": "deadbeefdeadbeef",
                        "png_only": False,
                    }
                ).encode()
            )

    def test_ref_validation_helper_mismatch(self):
        edition = self.fx.latest
        doc = parse_manifest(
            build_manifest(edition, "c" * 64, "d" * 64)
        )
        with self.assertRaises(ManifestError):
            validate_manifest_against_ref(
                doc, f"publish/submissions/2026-10-11-{doc['content_id']}"
            )


if __name__ == "__main__":
    unittest.main()
