# Loot's Gaming Roundup: page generator

Each daily roundup is built from a **JSON file** (`YYYY-MM-DD.json`). HTML pages are **generated** — do not edit them by hand. All CSS is inline (the theme lives in `brand/theme.css` and is copied into the `CSS` string in `build.py`). Edition pages show a compact **views sparkline and total** in the header intro; those numbers are **fetched once at build time** from Databuddy and stored in the JSON (`views_snapshot`). There is no client-side stats fetch on archive pages (or on today's page for now). Fonts (Inter Tight, Inter, JetBrains Mono) come from Google Fonts with system-font fallbacks. The logo, favicons and share image live in `brand/` and are referenced from every page, so keep `brand/` deployed alongside the pages.

## Source of truth and publishing

| File | Role |
|------|------|
| `YYYY-MM-DD.json` | **Source of truth** for each day's stories and **views snapshot** |
| `YYYY-MM-DD.html` | Generated edition page |
| `index.html` | Copy of the **latest** edition (home page) |
| `archive.html` | Generated list of every past edition |
| `sitemap.xml` | Generated sitemap for search engines |

On every Vercel deploy, the build command runs `python3 build.py --all`, which rebuilds every edition from JSON, refreshes views snapshots when rules allow, and updates `index.html`, `archive.html`, and `sitemap.xml`.

GitHub Actions runs the same command on every push and pull request (with `DATABUDDY_API_KEY` from repo secrets when configured).

Clean URLs: `/2026-10-22` serves the same page as `/2026-10-22.html` (see `vercel.json` rewrites).

## Daily steps for Loot (assistant)

1. Copy the previous day's `YYYY-MM-DD.json` to today's filename (e.g. `2026-10-25.json`).
2. Edit the JSON: update `date`, `date_label`, story content, and optionally **`published_at`** (ISO8601, SAST or Z) if the edition went live at a time other than the default **08:00 Africa/Johannesburg** on that date.
3. Commit the JSON.
4. Build with Databuddy credentials available (local export or CI/Vercel):
   ```bash
   export DATABUDDY_API_KEY='…'   # same secret name as Vercel / GitHub
   python3 build.py YYYY-MM-DD.json
   ```
   This writes HTML, **finalises the previous edition's views window** (publish-to-publish), fetches or refreshes snapshots per the lock rules, and **writes `views_snapshot` back into the JSON**.
5. Commit the updated **JSON and generated HTML** (`YYYY-MM-DD.html`, and `index.html` when you built the latest day). Also commit `archive.html` / `sitemap.xml` if you ran `--all`.
6. Push to `main` (or open a PR). Vercel runs the full build on every deployment.

Each edition page links to **Past roundups** (`/archive.html`) in the footer and **Archive** in the header nav.

## Files

- `build.py`: the generator (Python 3 standard library only)
- `views_fetch.py`: Databuddy queries for publish-window page views (used by `build.py`)
- `api/views.js`: Vercel serverless route — **reserved for a future live "today" page**; archive and static editions do not call it
- `vercel.json`: Vercel build command and clean-URL rewrites
- `.github/workflows/build.yml`: CI build; passes **`DATABUDDY_API_KEY`** from GitHub Actions secrets when set

## Databuddy page views (build time)

- **Website ID:** `d2f227a9-4c59-4917-b672-37f4eb3d81f9`, timezone **Africa/Johannesburg**
- **API:** `POST https://api.databuddy.cc/v1/query` with header **`x-api-key`** from env **`DATABUDDY_API_KEY`**
- **Measurement window:** from this edition's **`published_at`** until the **next** edition's `published_at` (not calendar midnight). If `published_at` is omitted, the build assumes **08:00 Africa/Johannesburg** on the edition `date` (override in JSON when you publish at a different time).
- **Paths merged:** `/YYYY-MM-DD.html`, `/YYYY-MM-DD`, and **`/`** (home page while that edition was live)
- **Tracking live from ~15:00 SAST on 22 October 2026** — older portions of a window get an honest `tracking_note`; the build does not invent zero views before tracking existed.
- **`views_snapshot.series`** stores **non-cumulative** pageviews per **hour** (or per day when the window is longer than 30 days). The header sparkline plots the **cumulative** sum across those buckets so you can see *when* views landed inside the publish window, not just the total.

Set **`DATABUDDY_API_KEY`** in:

- **Vercel** project environment (Production and Preview) for deploy builds
- **GitHub Actions** repository secret with the **same name** (`DATABUDDY_API_KEY`) for CI

Do **not** commit the key. Without it, builds still succeed; edition pages show a muted **Views not recorded** line instead of a sparkline.

### Snapshot lock

Once an edition's **`window_end`** is in the past and a **`views_snapshot`** exists, a normal `build.py` run **does not** refetch Databuddy unless you pass **`--refresh-views`** or **`--backfill-views`**. The latest (still-open) window may still be updated on each build when a key is present.

One-off backfill for all editions in the repo:

```bash
export DATABUDDY_API_KEY='…'
python3 build.py --backfill-views
```

Then commit updated JSON files and regenerated HTML.

## Making a single edition (local)

```bash
python3 build.py 2026-10-11.json
```

Writes `2026-10-11.html`. If that file is the latest date, also updates `index.html`. Refreshes `archive.html` and `sitemap.xml`.

Rebuild **everything**:

```bash
python3 build.py --all
```

Options:

- `-o path.html` — custom output (skips index/archive/sitemap side effects)
- `--no-index` — skip updating `index.html` when building one edition
- `--backfill-views` — fetch views for all editions (bypasses snapshot lock)
- `--refresh-views` — refetch even when a closed edition already has a snapshot (combine with `--all` or `--backfill-views`)

## JSON schema

```json
{
  "date": "2026-10-11",
  "date_label": "Sunday 11 October 2026",
  "published_at": "2026-10-11T08:00:00+02:00",
  "views_snapshot": {
    "window_start": "2026-10-11T08:00:00+02:00",
    "window_end": "2026-10-12T08:00:00+02:00",
    "granularity": "hourly",
    "total_views": 42,
    "series": [
      {"timestamp": "2026-10-11T08:00:00+02:00", "pageviews": 5, "tracked": true},
      {"timestamp": "2026-10-11T09:00:00+02:00", "pageviews": 37, "tracked": true}
    ],
    "fetched_at": "2026-10-13T10:00:00+02:00",
    "tracking_note": "optional string when tracking started mid-window"
  },
  "your_games": [ STORY, ... ],
  "industry":   [ STORY, ... ],
  "releases_link": "https://...",
  "releases": [
    {"date": "13 Oct", "title": "...", "note": "optional one-liner", "tags": ["PS5","PC"]}
  ],
  "footer_note": "optional pinned note at the bottom"
}
```

`published_at` and `views_snapshot` are optional in hand-authored JSON; the build fills or updates `views_snapshot` when `DATABUDDY_API_KEY` is set.

STORY = `{"title": "...", "tags": ["PS5"], "body": "...", "links": [{"label": "Source", "url": "https://..."}]}`

If a section is empty or missing, it's left off the page.

## Tag chip colours

- `PS5` / `PlayStation` / `PS Plus`: blue
- `Switch` / `Switch 2` / `Nintendo` / `Pokémon`: red
- `Xbox`: green
- `PC`: grey
- Any other tag (a game or franchise name): neutral outline

See `brand/theme.md` for the full palette, fonts and layout notes.

## Checking a build visually

```bash
google-chrome --headless=new --no-sandbox --hide-scrollbars --force-device-scale-factor=2 \
  --window-size=390,7100 --screenshot=preview-mobile.png file://$PWD/index.html
google-chrome --headless=new --no-sandbox --hide-scrollbars \
  --window-size=1280,6100 --screenshot=preview-desktop.png file://$PWD/index.html
```

If the page is longer than the window, the bottom gets cut off. Raise the window height when that happens.

## Header

The masthead is a sticky bar (`header.masthead` > `.bar`) holding the logo, the one-line title and the section nav, which scrolls sideways on phones. The kicker, date and optional views sparkline sit in `.intro` just under it and scroll away. Sections have `scroll-margin-top` so the jump links land below the bar. Keep `brand/theme.css` and the `CSS` string in `build.py` identical.

## Responsive layout

- Under 1000px: one 760px column (phones and tablets).
- 1000px and up: a 1200px container with the story feed (`main.feed`) on the left and a sticky "Out this week" sidebar (`aside.side`, 300px) on the right. Story text is capped at 38em (about 70 characters a line). The sidebar scrolls on its own if it's taller than the window.
- 1440px and up: a 1280px container, a 360px sidebar and slightly larger headings and spacing.
