# Loot's Gaming Roundup: page generator

Each daily roundup is a single HTML file. All CSS is inline (the theme lives in `brand/theme.css` and is copied into the `CSS` string in `build.py`) and there's no JavaScript. Fonts (Inter Tight, Inter, JetBrains Mono) come from Google Fonts with system-font fallbacks. The logo, favicons and share image live in `brand/` and are referenced from every page, so keep `brand/` deployed alongside the pages. It's built from a JSON file by `build.py`, so every day's page has the same design.

## Files
- `build.py`: the generator (needs only the Python 3 standard library)
- `YYYY-MM-DD.json`: the stories for one day (example: `2026-10-11.json`)
- `YYYY-MM-DD.html`: the page built for that day
- `index.html`: a copy of the latest day's page
- `preview-mobile-top.png`, `preview-mobile-scrolled.png` (390px at 2x), `preview-1024.png`, `preview-1440.png`, `preview-1440-scrolled.png`, `preview-1920.png`: viewport screenshots of the latest build

## Making a new roundup
1. Copy yesterday's JSON to `YYYY-MM-DD.json` and replace the content.
2. Run `python3 build.py YYYY-MM-DD.json`.
   This writes `YYYY-MM-DD.html` and updates `index.html`.
   Options: `-o path.html` writes to a custom path (and leaves `index.html` alone). `--no-index` builds the page without updating `index.html`.

## JSON schema
```json
{
  "date": "2026-10-11",                       // used for the output filename
  "date_label": "Sunday 11 October 2026",     // shown in the header
  "your_games": [ STORY, ... ],               // "Your games" section
  "industry":   [ STORY, ... ],               // "Industry" section
  "releases_link": "https://...",             // optional "full release list" link
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
