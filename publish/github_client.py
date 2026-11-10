"""Minimal GitHub REST client for edition submit (stdlib only)."""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from typing import Any


class GitHubAPIError(RuntimeError):
    def __init__(self, status: int, message: str, body: str = "") -> None:
        super().__init__(f"GitHub API {status}: {message}" + (f" — {body}" if body else ""))
        self.status = status
        self.body = body


class GitHubClient:
    def __init__(self, token: str, owner: str, repo: str) -> None:
        self.token = token
        self.owner = owner
        self.repo = repo
        self.api = f"https://api.github.com/repos/{owner}/{repo}"

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        accept: str = "application/vnd.github+json",
    ) -> Any:
        url = path if path.startswith("http") else f"{self.api}{path}"
        data = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "loot-submit-edition/1.0",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise GitHubAPIError(e.code, e.reason, body) from e

    def ref_sha(self, ref: str) -> str:
        # ref: heads/main or heads/publish/inbox
        data = self._request("GET", f"/git/ref/{ref}")
        return data["object"]["sha"]

    def create_blob(self, content: bytes, *, binary: bool) -> str:
        if binary:
            encoded = base64.b64encode(content).decode("ascii")
        else:
            encoded = content.decode("utf-8")
        data = self._request(
            "POST",
            "/git/blobs",
            {"content": encoded, "encoding": "base64" if binary else "utf-8"},
        )
        return data["sha"]

    def create_tree(self, base_tree: str, entries: list[dict[str, str]]) -> str:
        data = self._request(
            "POST",
            "/git/trees",
            {"base_tree": base_tree, "tree": entries},
        )
        return data["sha"]

    def create_commit(self, message: str, tree: str, parents: list[str]) -> str:
        data = self._request(
            "POST",
            "/git/commits",
            {"message": message, "tree": tree, "parents": parents},
        )
        return data["sha"]

    def update_ref(self, ref: str, sha: str, *, force: bool = False) -> None:
        self._request(
            "PATCH",
            f"/git/refs/{ref}",
            {"sha": sha, "force": force},
        )

    def create_ref(self, ref: str, sha: str) -> None:
        try:
            self._request("POST", "/git/refs", {"ref": f"refs/{ref}", "sha": sha})
        except GitHubAPIError as e:
            if e.status != 422:
                raise

    def dispatch_workflow(
        self,
        workflow_file: str,
        ref: str,
        inputs: dict[str, str],
    ) -> None:
        self._request(
            "POST",
            f"/actions/workflows/{workflow_file}/dispatches",
            {"ref": ref, "inputs": inputs},
        )


def client_from_env() -> GitHubClient:
    token = os.environ.get("LOOT_PUBLISH_GITHUB_TOKEN") or os.environ.get(
        "GITHUB_TOKEN"
    )
    if not token:
        raise RuntimeError(
            "Set LOOT_PUBLISH_GITHUB_TOKEN (fine-grained PAT) or GITHUB_TOKEN"
        )
    owner = os.environ.get("LOOT_PUBLISH_REPO_OWNER", "Hiccup-za")
    repo = os.environ.get("LOOT_PUBLISH_REPO", "loot-gaming-roundup")
    return GitHubClient(token, owner, repo)
