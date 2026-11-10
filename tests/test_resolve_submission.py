"""resolve_submission uses commit trees, not name-only diffs."""
import json
import os
import subprocess
import tempfile
import unittest

from publish.resolve_submission import ls_tree_paths, resolve


class ResolveSubmissionTests(unittest.TestCase):
    def _run(self, *args: str, cwd: str) -> subprocess.CompletedProcess:
        return subprocess.run(args, cwd=cwd, capture_output=True, check=True)

    def _init_repo(self) -> str:
        tmp = tempfile.mkdtemp()
        self._run("git", "init", "-b", "main", cwd=tmp)
        self._run("git", "config", "user.email", "t@example.com", cwd=tmp)
        self._run("git", "config", "user.name", "t", cwd=tmp)
        return tmp

    def test_unchanged_replay_commit_empty_name_only_diff(self):
        """Commit identical to parent: name-only is empty; ls-tree still resolves."""
        repo = self._init_repo()
        edition = "2099-07-01"
        label = "Tuesday 1 July 2099"
        with open(os.path.join(repo, f"{edition}.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "date": edition,
                    "date_label": label,
                    "x_post": {
                        "template": "haul",
                        "data": {},
                        "text": "t",
                        "image": f"/x/{edition}.png",
                        "time": "08:00",
                    },
                },
                f,
            )
        os.makedirs(os.path.join(repo, "x"), exist_ok=True)
        with open(os.path.join(repo, "x", f"{edition}.png"), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"x" * 100)
        self._run("git", "add", ".", cwd=repo)
        self._run("git", "commit", "-m", "main edition", cwd=repo)
        main_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        # Submission commit with same tree as parent (replay / no file diff).
        self._run("git", "commit", "--allow-empty", "-m", "replay", cwd=repo)
        submission_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        self.assertNotEqual(submission_sha, main_sha)
        # git show --name-only would be empty; tree still has edition files.
        ref = f"publish/submissions/{edition}-deadbeefcafebabe"
        paths = ls_tree_paths(submission_sha, cwd=repo)
        self.assertIn(f"{edition}.json", paths)
        meta = resolve(submission_sha, ref_name=ref, work_dir=repo)
        self.assertEqual(meta["edition_date"], edition)
        self.assertEqual(meta["date_label"], label)

    def test_png_only_tree_uses_ref_name_for_date(self):
        repo = self._init_repo()
        edition = "2099-07-02"
        label = "Wednesday 2 July 2099"
        with open(os.path.join(repo, f"{edition}.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "date": edition,
                    "date_label": label,
                    "x_post": {
                        "template": "haul",
                        "data": {},
                        "text": "t",
                        "image": f"/x/{edition}.png",
                        "time": "08:00",
                    },
                },
                f,
            )
        os.makedirs(os.path.join(repo, "x"), exist_ok=True)
        with open(os.path.join(repo, "x", f"{edition}.png"), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"y" * 100)
        self._run("git", "add", ".", cwd=repo)
        self._run("git", "commit", "-m", "main", cwd=repo)
        main_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()

        png_path = os.path.join(repo, "x", f"{edition}.png")
        with open(png_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"z" * 120)
        blob = subprocess.check_output(
            ["git", "hash-object", "-w", png_path], cwd=repo, text=True
        ).strip()
        x_tree = subprocess.check_output(
            ["git", "mktree"],
            cwd=repo,
            input=f"100644 blob {blob}\t{edition}.png\n".encode(),
        ).decode().strip()
        tree_sha = subprocess.check_output(
            ["git", "mktree"],
            cwd=repo,
            input=f"040000 tree {x_tree}\tx\n".encode(),
        ).decode().strip()
        submission_sha = subprocess.check_output(
            ["git", "commit-tree", tree_sha, "-p", main_sha, "-m", "png only"],
            cwd=repo,
            text=True,
        ).strip()

        paths = ls_tree_paths(submission_sha, cwd=repo)
        self.assertNotIn(f"{edition}.json", paths)
        self.assertIn(f"x/{edition}.png", paths)

        meta = resolve(
            submission_sha,
            ref_name=f"publish/submissions/{edition}-aabbccddeeff1122",
            work_dir=repo,
        )
        self.assertEqual(meta["edition_date"], edition)


if __name__ == "__main__":
    unittest.main()
