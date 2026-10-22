# Loot's Gaming Roundup: page generator

Each daily roundup is a single self-contained HTML file. All CSS is inline, there's no JavaScript, and it uses system fonts. It's built from a JSON file by `build.py`, so every day's page has the same design.

## Files
- `build.py`: the generator (needs only the Python 3 standard library)
- `YYYY-MM-DD.json`: the stories for one day (example: `2026-10-11.json`)
- `YYYY-MM-DD.html`: the page built for that day
- `index.html`: a copy of the latest day's page
- `preview-mobile.png` / `preview-desktop.png`: screenshots of the latest build

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
- Any other tag (a game or franchise name): gold

## Checking a build visually
```bash
google-chrome --headless=new --no-sandbox --hide-scrollbars --force-device-scale-factor=2 \
  --window-size=390,3700 --screenshot=preview-mobile.png file://$PWD/index.html
google-chrome --headless=new --no-sandbox --hide-scrollbars \
  --window-size=1280,2550 --screenshot=preview-desktop.png file://$PWD/index.html
```
If the page is longer than the window, the bottom gets cut off. Raise the window height when that happens.
