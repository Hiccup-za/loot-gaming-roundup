"""GitHub REST via the ``gh`` CLI (uses gh's stored credentials; never reads token)."""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any


class GhCliError(RuntimeError):
    def __init__(self, returncode: int, stderr: str, stdout: str = "") -> None:
        msg = stderr.strip() or stdout.strip() or f"gh exited {returncode}"
        super().__init__(msg)
        self.returncode = returncode


def require_gh() -> str:
    path = shutil.which("gh")
    if not path:
        raise GhCliError(127, "gh CLI not found on PATH")
    return path


def gh_api(
    method: str,
    endpoint: str,
    payload: dict[str, Any] | None = None,
    *,
    hostname: str = "",
) -> Any:
    """Call ``gh api``. Endpoint is like ``repos/OWNER/REPO/...`` (no leading slash)."""
    require_gh()
    cmd = ["gh", "api", endpoint, "-X", method]
    if hostname:
        cmd.extend(["--hostname", hostname])
    if payload is not None:
        cmd.extend(["--input", "-"])
        proc = subprocess.run(
            cmd,
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            check=False,
        )
    else:
        proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise GhCliError(
            proc.returncode,
            proc.stderr.decode("utf-8", errors="replace"),
            proc.stdout.decode("utf-8", errors="replace"),
        )
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout.decode("utf-8"))


def gh_auth_ok() -> bool:
    require_gh()
    proc = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def gh_workflow_run(
    workflow_file: str,
    repo: str,
    *,
    ref: str = "main",
    inputs: dict[str, str] | None = None,
) -> None:
    """Re-trigger publish-edition.yml (idempotent recovery). Needs Actions write on gh token."""
    require_gh()
    cmd = ["gh", "workflow", "run", workflow_file, "--repo", repo, "--ref", ref]
    if inputs:
        for key, value in inputs.items():
            cmd.extend(["-f", f"{key}={value}"])
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise GhCliError(
            proc.returncode,
            proc.stderr.decode("utf-8", errors="replace"),
            proc.stdout.decode("utf-8", errors="replace"),
        )
