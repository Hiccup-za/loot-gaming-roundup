"""GitHub git/data API for inbox uploads — prefers ``gh api`` credentials."""
from __future__ import annotations

import base64
import os
from typing import Any

from publish.gh_cli import GhCliError, gh_api


class GitHubAPIError(RuntimeError):
    def __init__(self, status: int, message: str, body: str = "") -> None:
        super().__init__(
            f"GitHub API {status}: {message}" + (f" — {body}" if body else "")
        )
        self.status = status
        self.body = body


def _api_error(exc: GhCliError) -> GitHubAPIError:
    body = exc.args[0] if exc.args else ""
    status = 0
    if "HTTP 404" in body:
        status = 404
    elif "HTTP 403" in body:
        status = 403
    elif "HTTP 422" in body:
        status = 422
    return GitHubAPIError(status, body)


class GitHubClient:
    def __init__(self, owner: str, repo: str) -> None:
        self.owner = owner
        self.repo = repo
        self._prefix = f"repos/{owner}/{repo}"

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        endpoint = path if path.startswith("repos/") else f"{self._prefix}{path}"
        try:
            return gh_api(method, endpoint, payload)
        except GhCliError as e:
            raise _api_error(e) from e

    def ref_sha(self, ref: str) -> str:
        data = self._request("GET", f"/git/ref/{ref}")
        return data["object"]["sha"]

    def create_blob(self, content: bytes, *, binary: bool) -> str:
        if binary:
            encoded = base64.b64encode(content).decode("ascii")
            data = self._request(
                "POST",
                "/git/blobs",
                {"content": encoded, "encoding": "base64"},
            )
        else:
            data = self._request(
                "POST",
                "/git/blobs",
                {"content": content.decode("utf-8"), "encoding": "utf-8"},
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
        self._request("PATCH", f"/git/refs/{ref}", {"sha": sha, "force": force})

    def create_ref(self, ref: str, sha: str) -> None:
        self._request("POST", "/git/refs", {"ref": f"refs/{ref}", "sha": sha})


def client_from_env() -> GitHubClient:
    owner = os.environ.get("LOOT_PUBLISH_REPO_OWNER", "Hiccup-za")
    repo = os.environ.get("LOOT_PUBLISH_REPO", "loot-gaming-roundup")
    return GitHubClient(owner, repo)
