# Automated edition publishing

Daily **edition JSON** and **Artist haul PNG** publish to `main` without a morning pull request or manual merge. This replaces the manual “commit JSON → commit PNG → open PR → wait for ship” loop. **X posting is not part of this workflow** (no scheduling, queuing, or X API calls).

## Architecture

```
Parent routine (JSON) ──┐
                        ├──► scripts/submit_edition.py (validate + GitHub API)
Artist (PNG on disk) ───┘              │
                                       ▼
                         branch publish/inbox (one commit / day)
                                       │
                         workflow_dispatch publish-edition.yml
                                       ▼
              validate → build.py --all → push main → verify production
```

| Piece | Role |
|--------|------|
| `scripts/submit_edition.py` | Runs on the **parent executor** (has the PNG path). Validates, uploads inbox commit, triggers workflow. |
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
export LOOT_PUBLISH_GITHUB_TOKEN='…'   # fine-grained PAT — see below

python3 scripts/submit_edition.py \
  --edition-date 2026-11-10 \
  --json-path /path/to/2026-11-10.json \
  --png-path /workspace/marketing/loot-x/out/2026-11-10.png
```

Dry-run (validate only):

```bash
python3 scripts/submit_edition.py --edition-date … --json-path … --png-path … --dry-run
```

The script prints `json_sha256` and `png_sha256`; the workflow requires these to match the inbox commit (tamper detection).

## One-time authentication setup (operator)

Create a **fine-grained personal access token** (or machine user) for the parent executor:

| Permission | Access |
|------------|--------|
| Repository access | `Hiccup-za/loot-gaming-roundup` only |
| Contents | Read and write |
| Actions | Read and write |
| Metadata | Read |

Store as **`LOOT_PUBLISH_GITHUB_TOKEN`** in the parent executor secrets (not in this repo).

### Branch rules

- **`main`**: must already allow **GitHub Actions** to push (same as existing `backfill-views.yml`). If `main` requires PR reviews for all pushes, automated publish will fail until an exception is added for `github-actions[bot]`.
- **`publish/inbox`**: allow the PAT holder to **force-push** this branch only (or leave the branch unprotected). The submit script force-updates inbox each day.

### What we cannot configure from the repo alone

- Minting the PAT (Christopher / org admin).
- Branch protection exceptions on `main` / `publish/inbox`.
- Vercel project settings (production deploy on `main` is assumed).

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

**PR #22** (`x/2026-11-10.png` only) becomes **redundant** after the first successful automated publish for `2026-11-10` with the same PNG bytes. Close #22 without merging once publish verifies.

**Suggested cutover (after this setup PR merges):**

1. Merge the one-time **automated publishing** setup PR (not the image-only PR).
2. Configure `LOOT_PUBLISH_GITHUB_TOKEN` on the parent executor.
3. Run submit for today using Artist PNG + edition JSON (JSON may already be on `main`; submit still sends both):

   ```bash
   python3 scripts/submit_edition.py \
     --edition-date 2026-11-10 \
     --json-path ./2026-11-10.json \
     --png-path /workspace/marketing/loot-x/out/2026-11-10.png
   ```

4. Watch [Publish edition](https://github.com/Hiccup-za/loot-gaming-roundup/actions/workflows/publish-edition.yml) until verify succeeds.
5. Close PR #22.

## Operator checklist

- [ ] Fine-grained PAT created and stored on parent as `LOOT_PUBLISH_GITHUB_TOKEN`
- [ ] `publish/inbox` force-push allowed for PAT
- [ ] `github-actions[bot]` can push `main` (backfill already proves this if green)
- [ ] `DATABUDDY_API_KEY` present in GitHub Actions (optional; build succeeds without)
- [ ] Parent routine updated to invoke `scripts/submit_edition.py` after Artist completes
- [ ] No X API / scheduling enabled

## Local validation

```bash
python3 -m publish.validate --edition-date 2026-11-10 --root . --print-hashes
python3 -m unittest discover -s tests -p "test_*.py" -v
```
