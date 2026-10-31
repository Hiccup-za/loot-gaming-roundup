# Loot's Gaming Roundup: page generator

Each daily roundup is built from a **JSON file** (`YYYY-MM-DD.json`). HTML pages are **generated** — do not edit them by hand. All CSS is inline (the theme lives in `brand/theme.css` and is copied into the `CSS` string in `build.py`). Edition pages show a compact **unique-visitor sparkline and total** in the header intro; those numbers are **fetched once at build time** from Databuddy and stored in the JSON (`views_snapshot`). There is no client-side stats fetch on archive pages (or on today's page for now). Fonts (Inter Tight, Inter, JetBrains Mono) come from Google Fonts with system-font fallbacks. The logo, favicons and share image live in `brand/` and are referenced from every page, so keep `brand/` deployed alongside the pages.

## Source of truth and publishing

| File | Role |
|------|------|
| `YYYY-MM-DD.json` | **Source of truth** for each day's stories, optional **X post** (`x_post`), and **views snapshot** |
| `x/YYYY-MM-DD.png` | Optional hosted image for that day's `@LootRoundup` post (not shown on roundup pages). The `x/` directory is kept in git (see `x/.gitkeep`); PNGs are static assets via `vercel.json` `outputDirectory: "."` (no build copy step). |
| `YYYY-MM-DD.html` | Generated edition page |
| `index.html` | Copy of the **latest** edition (home page) |
| `archive.html` | Generated archive: KPI and visitors-per-edition chart from Databuddy `views_snapshot` in JSON, plus one card per edition (newest first) |
| `badges.html` | Generated index of every story/release tag across all editions, with occurrence counts |
| `sitemap.xml` | Generated sitemap for search engines |

On every Vercel deploy, the build command runs `python3 build.py --all`, which rebuilds every edition from JSON, refreshes views snapshots when rules allow, and updates `index.html`, `archive.html`, `badges.html`, and `sitemap.xml`.

GitHub Actions runs the same command on every push and pull request (with `DATABUDDY_API_KEY` from repo secrets when configured).

Clean URLs: `/2026-10-22` serves the same page as `/2026-10-22.html` (see `vercel.json` rewrites).

## Daily steps for Loot (assistant)

1. Copy the previous day's `YYYY-MM-DD.json` to today's filename (e.g. `2026-10-25.json`).
2. Edit the JSON: update `date`, `date_label`, story content, and optionally **`published_at`** (ISO8601, SAST or Z) if the edition went live at a time other than the default **08:00 Africa/Johannesburg** on that date. When you want the X dashboard to show that day's post, add optional **`x_post`** (see JSON schema): `template`, opaque `data` for the image renderer, `text` (≤280 chars on X, each link counts as 23), `image` path like `/x/YYYY-MM-DD.png`, and suggested `time` (HH:MM SAST).
3. Commit the JSON (including `x_post` when used). The public edition feed at `/YYYY-MM-DD.json` is the same file — it is not stripped at build time.
4. After the 1200×675 image is rendered from the template, commit the PNG under **`x/`** (e.g. `x/2026-10-28.png`) in a **separate commit**. It deploys at `https://loot-gaming-roundup.vercel.app/x/YYYY-MM-DD.png`. X images are not linked from roundup HTML and are not listed in `sitemap.xml`.
5. Build with Databuddy credentials available (local export or CI/Vercel):
   ```bash
   export DATABUDDY_API_KEY='…'   # same secret name as Vercel / GitHub
   python3 build.py YYYY-MM-DD.json
   ```
   This writes HTML, **finalises the previous edition's measurement window** (publish-to-publish), fetches or refreshes unique-visitor snapshots per the lock rules, and **writes `views_snapshot` back into the JSON**. It does not remove or rewrite `x_post`.
6. Commit the updated **JSON and generated HTML** (`YYYY-MM-DD.html`, and `index.html` when you built the latest day). Also commit `archive.html`, `badges.html`, and `sitemap.xml` if you ran `--all`.
7. Push to `main` (or open a PR). Vercel runs the full build on every deployment.

Each edition page links to **Past roundups** (`/archive.html`) in the footer and **Archive** / **Badges** in the header nav.

## Files

- `build.py`: the generator (Python 3 standard library only)
- `views_fetch.py`: Databuddy queries for publish-window unique visitors (used by `build.py`)
- `api/views.js`: Vercel serverless route — **reserved for a future live "today" page**; archive and static editions do not call it. It uses the same unique-visitor rules (dated paths, `summary_metrics` total, `visitors` per day)
- `vercel.json`: Vercel build command and clean-URL rewrites
- `.github/workflows/build.yml`: CI build; passes **`DATABUDDY_API_KEY`** from GitHub Actions secrets when set

## Databuddy unique visitors (build time)

- **Website ID:** `d2f227a9-4c59-4917-b672-37f4eb3d81f9`, timezone **Africa/Johannesburg**
- **API:** `POST https://api.databuddy.cc/v1/query` with header **`x-api-key`** from env **`DATABUDDY_API_KEY`**
- **Measurement window:** from this edition's **`published_at`** until the **next** edition's `published_at` (not calendar midnight). If `published_at` is omitted, the build assumes **08:00 Africa/Johannesburg** on the edition `date` (override in JSON when you publish at a different time).
- **Dated paths:** `/YYYY-MM-DD.html` and `/YYYY-MM-DD`. Home (`/`) is **not** included. Unique visitors on `/` overlap the dated URLs, and Databuddy does not give a union of paths, so adding `/` would inflate the edition.
- **Series:** `events_by_date` with the path filter. Each bucket stores **`visitors`** (people in that hour or day), not pageviews. Where both dated URLs have a figure for the same bucket, the snapshot keeps the **higher** one. It does not add them.
- **Total:** `summary_metrics` with the same path filter, reading **`data[0].unique_visitors`**. If that field is missing, the fetch falls back to `top_pages` → `visitors` for that path. The edition total is the **higher** of the two dated URLs (`primary_path` records which one). **Do not sum** hourly or daily `visitors` — the same person in two buckets is counted twice (a checked case summed to 29 against a true unique of 19). Reloading the page does not increase the total.
- **Calendar dates:** `summary_metrics` is bounded by calendar dates that overlap the window, not by the hour. A window that ends at 08:00 still includes that calendar day, so the unique total can include later the same day on that dated URL. The sparkline buckets are clipped to the hour window. The labelled total is the summary figure, not the end of the line.
- **Tracking live from ~15:00 SAST on 22 October 2026** — older portions of a window get an honest `tracking_note`; the build does not invent zero visitors before tracking existed.
- **`views_snapshot.series`** stores **non-cumulative** visitors per **hour** (or per day when the window is longer than 30 days). The header sparkline plots the **cumulative** sum of those buckets so you can see *when* visitors arrived inside the publish window. That running total can be higher than `total_unique_visitors`; the number next to the line is the summary unique count.

Set **`DATABUDDY_API_KEY`** in:

- **Vercel** project environment (Production and Preview) for deploy builds
- **GitHub Actions** repository secret with the **same name** (`DATABUDDY_API_KEY`) for CI

Do **not** commit the key. Without it, builds still succeed; edition pages show a muted **Visitors not recorded** line instead of a sparkline.

Snapshots written before this change store `total_views` and `pageviews`. The build still reads those so the pages render. The labels say unique visitors, and the tooltip says the figure is still a page-view count until the next refresh.

### Snapshot lock

Once a **`views_snapshot`** exists and the edition's **`window_end`** is at or before now, a normal `build.py` run **does not** refetch Databuddy. The open edition's window end is "now" at build time, so an existing snapshot is left as-is. **`--refresh-views`** and **`--backfill-views`** both bypass that lock.

Vercel runs `python3 build.py --all` (see `vercel.json`). That rebuilds HTML from the JSON already in the repo. It does **not** replace page-view snapshots with unique visitors, even when `DATABUDDY_API_KEY` is set.

To refresh every edition, run a build that has the key and one of the flags, then commit the JSON and HTML:

```bash
export DATABUDDY_API_KEY='…'
python3 build.py --all --refresh-views
```

`--backfill-views` does the same fetch. GitHub Actions workflow **Backfill views** (`.github/workflows/backfill-views.yml`) runs `python3 build.py --backfill-views --refresh-views` on **workflow dispatch**, or when `.github/backfill-views.request` is pushed to `main`, and commits the updated snapshots.

### Refresh needed for the numbers on the site

The snapshots committed with the unique-visitor change are still the previous **page-view** totals until that refresh runs. The UI already says unique visitors / visitors. After the refresh, `total_unique_visitors` replaces `total_views` and each bucket's `visitors` replaces `pageviews`. A plain Vercel redeploy is not enough.

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
- `--backfill-views` — fetch unique visitors for all editions (bypasses the snapshot lock)
- `--refresh-views` — refetch even when an edition already has a snapshot (combine with `--all` or `--backfill-views`)

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
    "total_unique_visitors": 19,
    "primary_path": "/2026-10-11.html",
    "series": [
      {"timestamp": "2026-10-11T08:00:00+02:00", "visitors": 5, "tracked": true},
      {"timestamp": "2026-10-11T09:00:00+02:00", "visitors": 8, "tracked": true}
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
  "footer_note": "optional pinned note at the bottom",
  "x_post": {
    "template": "headline",
    "data": {
      "kicker": "Daily gaming news",
      "headline": "Your main headline (required)",
      "dek": "Optional supporting line for the card",
      "tags": ["PS5", "Switch 2", "Indie"]
    },
    "text": "Post copy for @LootRoundup (≤280 chars; each https:// link counts as 23). https://loot-gaming-roundup.vercel.app/YYYY-MM-DD",
    "image": "/x/YYYY-MM-DD.png",
    "time": "09:30"
  }
}
```

**`x_post` (optional)** — consumed by the separate X dashboard repo; not rendered on roundup pages.

| Field | Type | Notes |
|-------|------|--------|
| `template` | string | One of: `headline`, `haul`, `out-this-week`, `games`, `industry`, `stats`, `weekly-wrap` |
| `data` | object | Template-specific fields for the image renderer (opaque to `build.py`) |
| `text` | string | Tweet copy; must fit X's 280-character limit (URLs count as 23 chars each) |
| `image` | string | Site path to the PNG, e.g. `/x/2026-10-28.png` |
| `time` | string | Suggested post time, `HH:MM` in SAST (24-hour) |

**`headline` template `data` fields** (1200×675 card):

| Field | Max length | Required |
|-------|------------|----------|
| `kicker` | 28 chars | no |
| `headline` | 90 chars | yes |
| `dek` | 120 chars | no |
| `tags` | up to 3 strings, each ≤14 chars | no |

See `tests/fixtures/x_post_sample.json` for a minimal example (fixture date only — not a published edition). A missing PNG under `x/` logs a build warning but does not fail CI. Any committed `x/*.png` is served at `/x/<filename>.png` (rewrites only apply to `/YYYY-MM-DD`, not `/x/`).

`published_at` and `views_snapshot` are optional in hand-authored JSON; the build fills or updates `views_snapshot` when `DATABUDDY_API_KEY` is set.

Older snapshots may still have `total_views` and series `pageviews`. The generator reads those when `total_unique_visitors` / `visitors` are absent. New fetches write `total_unique_visitors` and `visitors` only. The series sum is not the edition total.

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
