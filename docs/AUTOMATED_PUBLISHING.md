# Automated edition publishing

Daily **edition JSON** and **Artist haul PNG** publish to `main` without a morning pull request or manual merge. This replaces the manual “commit JSON → commit PNG → open PR → wait for ship” loop. **X posting is not part of this workflow** (no scheduling, queuing, or X API calls).

## Architecture

```
Parent routine (JSON) ──┐
                        ├──► scripts/submit_edition.py (validate + gh api → publish/inbox)
Artist (PNG on disk) ───┘              │
                                       ▼
                         branch publish/inbox (force-push, one commit / day)
                                       │
                         push triggers publish-edition.yml (no parent dispatch)
                                       ▼
              validate → build.py --all → push main → verify production
```

| Piece | Role |
|--------|------|
| `scripts/submit_edition.py` | Runs on the **parent executor** (has the PNG path). Validates, force-pushes inbox via **`gh api`**. |
| `scripts/publish_readiness.py` | Non-destructive check: gh auth + `permissions.push` + optional workflow-on-main. **Fail closed.** |
| `publish/inbox` branch | Short-lived staging ref; **force-pushed** each submit. Never merged via PR. |
| `.github/workflows/publish-edition.yml` | Validates hashes, builds site, pushes `main`, confirms live JSON date + PNG **SHA-256**. Reverts `main` if verification fails. |
| `publish/validate.py` | Strict checks (1200×675 PNG, `x_post.image` path, template fields). |
| `publish/verify_production.py` | HTTP checks against `LOOT_SITE_URL` / production with retries. |

Vercel still deploys on every push to `main` (unchanged). GitHub Actions **Build site** still runs on pushes and PRs.

## Parent routine contract

After the daily routine and Artist render:

| Artefact | Typical path |
|----------|----------------|
| Edition JSON | Wherever the routine writes `YYYY-MM-DD.json` (must match repo schema). |
| Artist PNG | `/workspace/marketing/loot-x/out/YYYY-MM-DD.png` |

The parent **must not** rely on the cloud agent reading that filesystem. It should call `submit_edition.py` from a checkout of this repo (or `PYTHONPATH` pointing at repo root):

```bash
python3 scripts/publish_readiness.py --require-workflow-on-main   # after setup PR merges

python3 scripts/submit_edition.py \
  --edition-date YYYY-MM-DD \
  --json-path /path/to/YYYY-MM-DD.json \
  --png-path /workspace/marketing/loot-x/out/YYYY-MM-DD.png
```

Dry-run (validate only, no GitHub calls):

```bash
python3 scripts/submit_edition.py --edition-date … --json-path … --png-path … --dry-run
```

The script prints `json_sha256` and `png_sha256`. The workflow recomputes hashes from the inbox commit and rejects content that fails strict validation.

## Authentication: existing `gh` vs new credentials

| Approach | When it applies |
|----------|-----------------|
| **Existing `gh auth login` on the parent executor** (preferred) | Parent already uses GitHub CLI for this repo. `submit_edition.py` calls **`gh api` only** — it never prints, exports, or copies tokens. |
| **New credential** | Only if `publish_readiness.py` reports `permissions.push=false` for the active `gh` session. Minimum need: **repository contents write** so the account can force-push `refs/heads/publish/inbox`. Configure via the same `gh auth login` / host you use for other repo writes — **not** a separate env var unless you intentionally run without `gh`. |

**Not required on the parent:** `workflow_dispatch`, Actions write, or Cursor GitHub workflow-mutation tools. The inbox **push** starts the workflow (same pattern as `.github/backfill-views.request` on `main`, but scoped to `publish/inbox`).

**Cloud agents** often have a read-only GitHub integration token (`permissions.push=false`). They must **not** run `submit_edition.py` for real publishes; parent executor only.

### Branch rules

- **`main`**: must allow **GitHub Actions** to push (same as `backfill-views.yml`).
- **`publish/inbox`**: submitter's `gh` identity must be allowed to **force-push** this branch (unprotected branch or ruleset exception).

### What we cannot configure from the repo alone

- Granting push to the parent's `gh` identity (org/repo access).
- Branch protection exceptions.
- Vercel production deploy settings.

## Idempotency and failure behaviour

| Case | Behaviour |
|------|-----------|
| Re-submit same JSON + PNG hashes | Build may run; **no commit** if tree unchanged; workflow succeeds. |
| Validation failure | Workflow **fails before** pushing `main`. Inbox may update; production untouched. |
| Production verify failure after push | Workflow **reverts** the publish commit on `main` and fails loudly (`::error::`). |
| Concurrent submits | `concurrency: publish-edition` queues runs (no cancel). |

Production is **not** treated as live until verification passes (JSON `date` + PNG hash at `/x/YYYY-MM-DD.png`).

Emergency drill without HTTP checks (not for routine use):

```bash
# workflow_dispatch only — set input skip_production_verify=true in GitHub UI
```

## Cutover from manual PNG PRs

**2026-11-10 (manual ship, complete):** Image-only PR #22 was squash-merged to `main` at `17ca210`. Production `/x/2026-11-10.png` is live (HTTP 200, `image/png`, 893 484 bytes, SHA-256 `58eebc7cee7f739317e6b58633e264ab81d48c96a4c18ce356b4d82bcedf0b04`). That edition does **not** need to be republished via this automation.

**After the one-time setup PR merges:**

1. Configure `LOOT_PUBLISH_GITHUB_TOKEN` on the parent executor (see above).
2. Point the daily routine at `scripts/submit_edition.py` for **the next edition onward** (e.g. 2026-11-11+). Each run still sends that day's JSON + Artist PNG together.
3. Watch [Publish edition](https://github.com/Hiccup-za/loot-gaming-roundup/actions/workflows/publish-edition.yml) until production verify succeeds.

Re-submitting 2026-11-10 with unchanged hashes is idempotent (no `main` commit if already present); use only if you intentionally need to rebuild HTML or recover from a partial failure.

## Operator checklist

- [ ] `python3 scripts/publish_readiness.py` exits 0 on the **parent** executor (after setup PR merge, use `--require-workflow-on-main`)
- [ ] Parent `gh` session has `permissions.push=true` on this repo (readiness script checks via API)
- [ ] `publish/inbox` force-push allowed for that identity
- [ ] `github-actions[bot]` can push `main` (backfill already proves this if green)
- [ ] `DATABUDDY_API_KEY` present in GitHub Actions (optional; build succeeds without)
- [ ] Parent routine updated to invoke `scripts/submit_edition.py` after Artist completes
- [ ] No X API / scheduling enabled

## Local validation

```bash
python3 -m publish.validate --edition-date 2026-11-10 --root . --print-hashes
python3 -m unittest discover -s tests -p "test_*.py" -v
```
