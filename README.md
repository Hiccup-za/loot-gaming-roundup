# Loot's Gaming Roundup: page generator

Each daily roundup is built from a **JSON file** (`YYYY-MM-DD.json`). HTML pages are **generated** — do not edit them by hand. All CSS is inline (the theme lives in `brand/theme.css` and is copied into the `CSS` string in `build.py`). Edition pages load a small inline script that fetches readership stats from `/api/views` (no build-time numbers). Fonts (Inter Tight, Inter, JetBrains Mono) come from Google Fonts with system-font fallbacks. The logo, favicons and share image live in `brand/` and are referenced from every page, so keep `brand/` deployed alongside the pages.

## Source of truth and publishing

| File | Role |
|------|------|
| `YYYY-MM-DD.json` | **Source of truth** for each day's stories |
| `YYYY-MM-DD.html` | Generated edition page |
| `index.html` | Copy of the **latest** edition (home page) |
| `archive.html` | Generated list of every past edition |
| `sitemap.xml` | Generated sitemap for search engines |

**Production never serves stale HTML.** On every Vercel deploy, the build command runs `python3 build.py --all`, which rebuilds every edition from JSON, refreshes `index.html`, `archive.html`, and `sitemap.xml`. You can commit **only the JSON** for a new day; the deploy step generates matching HTML.

GitHub Actions runs the same `python3 build.py --all` on every push and pull request so broken JSON or generator errors are caught early. Committed HTML may lag JSON in the repo; **Vercel always rebuilds on deploy**, so production stays in sync.

Clean URLs: `/2026-10-22` serves the same page as `/2026-10-22.html` (see `vercel.json` rewrites).

## Daily steps for Loot (assistant)

1. Copy the previous day's `YYYY-MM-DD.json` to today's filename (e.g. `2026-10-23.json`).
2. Edit the JSON: update `date`, `date_label`, and the story content.
3. Commit `YYYY-MM-DD.json` (you do **not** have to commit HTML — Vercel regenerates it on deploy).
4. **Optional:** run `python3 build.py --all` locally and commit the generated HTML, `archive.html`, and `sitemap.xml` if you want the repo to mirror production without waiting for deploy.
5. Push to `main` (or open a PR); Vercel runs the full build on every deployment.
Each edition page links to **Past roundups** (`/archive.html`) in the footer and **Archive** in the header nav.

## Files

- `build.py`: the generator (Python 3 standard library only)
- `api/views.js`: Vercel serverless route — queries Databuddy for daily page views (not run at build time)
- `vercel.json`: Vercel build command and clean-URL rewrites
- `.github/workflows/build.yml`: CI build and drift check

## Databuddy page views (Vercel)

Edition pages show a **daily views** line chart loaded in the browser via `GET /api/views?date=YYYY-MM-DD`. The route merges hits on both `/YYYY-MM-DD.html` and `/YYYY-MM-DD`, caches responses for about ten minutes, and never exposes credentials to the client.

Set **`DATABUDDY_API_KEY`** in the Vercel project environment (Production and Preview). Do **not** commit the key or add it to the repo. Without the key, the API returns `503` and edition pages show “Views unavailable” without breaking the rest of the page.

View tracking for this site began on **22 October 2026**; older editions show an honest note rather than zero-filled days before tracking existed.

## Making a single edition (local)

```bash
python3 build.py 2026-10-11.json
```

Writes `2026-10-11.html`. If that file is the latest date, also updates `index.html`. Always refreshes `archive.html` and `sitemap.xml`.

Rebuild **everything**:

```bash
python3 build.py --all
```

Options: `-o path.html` writes to a custom path (skips index/archive/sitemap side effects). `--no-index` skips updating `index.html` when building one edition.

## JSON schema

```json
{
  "date": "2026-10-11",
  "date_label": "Sunday 11 October 2026",
  "your_games": [ STORY, ... ],
  "industry":   [ STORY, ... ],
  "releases_link": "https://...",
  "releases": [
    {"date": "13 Oct", "title": "...", "note": "optional one-liner", "tags": ["PS5","PC"]}
  ],
  "footer_note": "optional pinned note at the bottom"
}
```

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

The masthead is a sticky bar (`header.masthead` > `.bar`) holding the logo, the one-line title and the section nav, which scrolls sideways on phones. The kicker and date sit in `.intro` just under it and scroll away. Sections have `scroll-margin-top` so the jump links land below the bar. Keep `brand/theme.css` and the `CSS` string in `build.py` identical.

## Responsive layout

- Under 1000px: one 760px column (phones and tablets).
- 1000px and up: a 1200px container with the story feed (`main.feed`) on the left and a sticky "Out this week" sidebar (`aside.side`, 300px) on the right. Story text is capped at 38em (about 70 characters a line). The sidebar scrolls on its own if it's taller than the window.
- 1440px and up: a 1280px container, a 360px sidebar and slightly larger headings and spacing.
