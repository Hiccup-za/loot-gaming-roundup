# Automated edition publishing

Daily **edition JSON** and **Artist haul PNG** publish to `main` without a morning pull request or manual merge. **X posting is not part of this workflow** (no scheduling, queuing, or X API calls).

## Architecture

```
Parent routine (JSON) ──┐
                        ├──► scripts/submit_edition.py (validate + gh api)
Artist (PNG on disk) ───┘              │
                                       ▼
              immutable ref publish/submissions/{date}-{contentId}
                                       │
                         push triggers publish-edition.yml
                                       ▼
         validate → build.py --all → ff-pull main → push → verify production
```

| Piece | Role |
|--------|------|
| `scripts/submit_edition.py` | Parent executor: validates, creates **immutable** submission ref (no force-push overwrite). |
| `scripts/publish_readiness.py` | Non-destructive: `gh` auth + `permissions.push`. **Fail closed.** |
| `publish/submissions/...` | One ref per unique JSON+PNG content; retries reuse same ref idempotently. |
| `.github/workflows/publish-edition.yml` | Build, push `main` with **ff-only pull**, verify `/`, `/{date}`, JSON, PNG hash. **Never auto-reverts `main`.** |
| `publish/verify_production.py` | ~10 min bounded wait; distinguishes **deploy pending** vs **content error**. |

## Parent invocation (exact)

```bash
cd /path/to/loot-gaming-roundup   # or PYTHONPATH=/path/to/loot-gaming-roundup

python3 scripts/publish_readiness.py --require-workflow-on-main   # once after setup PR merges

python3 scripts/submit_edition.py \
  --edition-date YYYY-MM-DD \
  --json-path /path/to/YYYY-MM-DD.json \
  --png-path /workspace/marketing/loot-x/out/YYYY-MM-DD.png
```

Dry-run (validate only):

```bash
python3 scripts/submit_edition.py --edition-date YYYY-MM-DD --json-path … --png-path … --dry-run
```

Artefact paths:

| Artefact | Typical path |
|----------|----------------|
| Edition JSON | Written by the daily routine |
| Artist PNG | `/workspace/marketing/loot-x/out/YYYY-MM-DD.png` |

## Authentication

**Use existing `gh auth login` on the parent executor** (`Hiccup-za` with `permissions.push=true`). `submit_edition.py` uses **`gh api`** for submission refs and **`gh workflow run`** only for **idempotent replay** (optional **Actions: write** on the same `gh` session).

A **new credential is only required** if `publish_readiness.py` reports `permissions.push=false`. Minimum capability: **repository contents write** (create refs under `publish/submissions/*`). Configure through the same `gh login` used for other repo writes — not a separate PAT product unless `gh` is unavailable.

Cloud agents typically have read-only GitHub integration; they must **not** run real submits.

### Branch rules

- **`main`**: GitHub Actions must push (same as `backfill-views.yml`). Publish pulls `main` with `--ff-only` before committing to avoid clobbering concurrent writers; failed verify **does not** `git revert HEAD` (would risk unrelated commits).
- **`publish/submissions/*`**: Parent creates new refs; no force-push required.

## Idempotency and failure behaviour

| Case | Behaviour |
|------|-----------|
| Same JSON+PNG resubmit | Same ref reused; `submit_edition.py` **re-triggers** workflow (`gh workflow run` + `submission_sha`); **production verify always runs** even if `main` no-op. |
| Different content same day | New `contentId` → new submission ref; concurrency **per ref** queues runs. |
| Validation failure | Fails **before** `main` push. |
| Verify **pending deploy** (stale `/`, slow Vercel) | Workflow **fails** with warning; **`main` publish commit kept**; recorded `publish_sha` in logs. |
| Verify **content error** (wrong PNG hash, bad JSON) | Workflow fails; **no automatic revert** — revert the recorded `publish_sha` manually if needed. |

Production checks: JSON `date`/`date_label`, PNG SHA-256, **`/` and `/{date}` HTML** show `date_label`, valid PNG content-type.

## Cutover (2026-11-10)

Manual ship via PR #22 (`17ca210`) — production PNG verified. Automation starts **2026-11-11+** after setup PR **#23** merges.

## Operator checklist

- [ ] `publish_readiness.py` exits 0 on parent (`--require-workflow-on-main` after #23)
- [ ] Parent `gh`: `permissions.push=true`
- [ ] `github-actions[bot]` can push `main`
- [ ] Parent routine calls `submit_edition.py` after Artist
- [ ] No X API automation

## Status

**Not operational end-to-end** until PR #23 merges and a submission workflow run completes with production verify OK on the parent executor.

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
