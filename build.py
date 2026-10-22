#!/usr/bin/env python3
"""Render Loot's Gaming Roundup from a JSON file into a self-contained HTML page.

Usage:
    python3 build.py 2026-10-11.json            # writes 2026-10-11.html + index.html
    python3 build.py data.json -o out.html      # custom output, no index copy
    python3 build.py data.json --no-index       # skip updating index.html
"""
import argparse, json, os, shutil, sys
from html import escape

TAG_CLASS = {
    "ps5": "ps", "playstation": "ps", "ps plus": "ps",
    "switch": "nin", "switch 2": "nin", "nintendo": "nin", "pokémon": "nin", "pokemon": "nin",
    "xbox": "xbox", "pc": "pc",
}

def chip(tag):
    cls = TAG_CLASS.get(tag.strip().lower(), "game")
    return f'<span class="chip chip-{cls}">{escape(tag)}</span>'

def links_html(links):
    if not links:
        return ""
    items = "".join(
        f'<a class="src" href="{escape(l["url"], quote=True)}" target="_blank" rel="noopener noreferrer">'
        f'{escape(l["label"])}<span aria-hidden="true"> ↗</span></a>'
        for l in links)
    return f'<div class="sources"><span class="src-label">Source</span>{items}</div>'

def story_card(s):
    chips = "".join(chip(t) for t in s.get("tags", []))
    return (f'<article class="card">'
            f'<div class="chips">{chips}</div>'
            f'<h3>{escape(s["title"])}</h3>'
            f'<p>{escape(s["body"])}</p>'
            f'{links_html(s.get("links", []))}'
            f'</article>')

def release_row(r):
    chips = "".join(chip(t) for t in r.get("tags", []))
    note = f'<p class="rel-note">{escape(r["note"])}</p>' if r.get("note") else ""
    day, _, mon = r["date"].partition(" ")
    return (f'<li class="release">'
            f'<div class="rel-date"><span class="d">{escape(day)}</span><span class="m">{escape(mon)}</span></div>'
            f'<div class="rel-body"><h3>{escape(r["title"])}</h3>{note}'
            f'{"<div class=chips>" + chips + "</div>" if chips else ""}</div>'
            f'</li>')

CSS = r"""
/* Loot's Gaming Roundup: clean modern news theme, dark mode
   Drop-in replacement for the CSS string in build.py (same class names).
   Fonts: Inter Tight (headlines/UI), Inter (body), JetBrains Mono (small meta). Free Google Fonts. */
@import url("https://fonts.googleapis.com/css2?family=Inter+Tight:wght@600;700;800&family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600&family=JetBrains+Mono:wght@500&display=swap");

:root{
  --bg:#0f1012;          /* page */
  --surface:#17191c;     /* cards */
  --surface-2:#1e2125;   /* hover, inset blocks */
  --border:#2a2d32;      /* hairlines */
  --border-strong:#3a3e45;
  --text:#ededef;        /* 15.1:1 on surface */
  --text-2:#b3b7bf;      /* body copy, 8.8:1 */
  --text-3:#8b9099;      /* meta, 5.5:1 */
  --accent:#f0b445;      /* crown gold: links, kicker, focus (9.5:1) */
  --accent-hover:#ffc85e;
  --accent-tint:rgba(240,180,69,.12);
  /* Platform colours: functional only */
  --ps:#6aa5ff; --nin:#ff6f6f; --xbox:#5ad18a; --pc:#b9bfca;
  --sans:"Inter",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --head:"Inter Tight","Inter",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:400 16px/1.6 var(--sans);
  -webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;min-height:100vh;
  padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)}
.wrap{max-width:760px;margin:0 auto;padding:24px 18px 48px}
@media(min-width:720px){.wrap{padding:48px 32px 72px}}
a:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:6px}

/* Header */
header{display:grid;grid-template-columns:auto 1fr;column-gap:18px;align-items:center;padding:0;margin-bottom:0}
header>*{grid-column:1 / -1}
header .logo{grid-column:1;grid-row:1 / span 2;width:84px;height:84px;object-fit:contain}
header .logo~.kicker,header .logo~h1{grid-column:2}
@media(max-width:560px){header .logo{width:60px;height:60px}}
.kicker{display:inline-flex;align-items:center;gap:8px;align-self:end;font:600 12px/1.2 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.kicker .dot{width:6px;height:6px;border-radius:50%;background:var(--accent)}
h1{margin:6px 0 0;align-self:start;font:800 clamp(30px,6.4vw,56px)/1.04 var(--head);letter-spacing:-.03em;color:var(--text)}
.date{margin-top:16px;font:500 13px/1.4 var(--mono);color:var(--text-3)}
nav.jump{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}
nav.jump a{display:inline-flex;align-items:center;min-height:36px;padding:0 14px;border-radius:999px;border:1px solid var(--border);
  background:var(--surface);color:var(--text-2);text-decoration:none;font:500 14px/1 var(--sans);transition:border-color .15s,color .15s}
nav.jump a:hover{border-color:var(--border-strong);color:var(--text)}

/* Sections: editorial breaks, no boxes */
section{margin-top:56px}
header+section{margin-top:44px}
h2{display:flex;align-items:baseline;gap:12px;margin:0;padding-top:14px;border-top:2px solid var(--text);
  font:700 24px/1.2 var(--head);letter-spacing:-.015em;color:var(--text)}
h2 .count{margin-left:auto;font:500 12px/1 var(--mono);color:var(--text-3);letter-spacing:0}

/* Story feed: one column, hairline dividers, no card boxes */
.grid{display:block}
.card{padding:28px 0 30px}
.card+.card{border-top:1px solid var(--border)}
.card h3{margin:12px 0 10px;font:700 clamp(21px,3.4vw,25px)/1.25 var(--head);letter-spacing:-.018em;color:var(--text);text-wrap:balance}
.card p{margin:0;color:var(--text-2);font-size:16.5px;line-height:1.68}

/* Platform chips: flat tags, coloured dot + coloured text on a faint tint */
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{--c:var(--text-3);display:inline-flex;align-items:center;gap:6px;padding:3px 8px;border-radius:6px;
  font:600 11.5px/1.5 var(--sans);letter-spacing:.02em;color:var(--c);
  background:color-mix(in srgb,var(--c) 12%,transparent);border:1px solid color-mix(in srgb,var(--c) 26%,transparent)}
.chip::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
.chip-ps{--c:var(--ps)}
.chip-nin{--c:var(--nin)}
.chip-xbox{--c:var(--xbox)}
.chip-pc{--c:var(--pc)}
.chip-game{--c:var(--text-2);background:transparent;border-color:var(--border-strong)}
.chip-game::before{display:none}

/* Sources: quiet meta row */
.sources{display:flex;flex-wrap:wrap;align-items:center;gap:2px 16px;margin-top:14px}
.src-label{font:500 11px/1 var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--text-3)}
a.src{display:inline-flex;align-items:center;min-height:32px;color:var(--text-2);text-decoration:none;font:500 14px/1.2 var(--sans)}
a.src span{color:var(--text-3)}
a.src:hover{color:var(--accent)}
a.src:hover span{color:var(--accent)}

/* Releases: unboxed list, hairline rows */
ul.releases{list-style:none;margin:0;padding:0}
.release{display:flex;gap:20px;align-items:flex-start;padding:18px 0}
.release+.release{border-top:1px solid var(--border)}
.rel-date{flex:0 0 64px;padding-top:1px;white-space:nowrap}
.rel-date .d{display:block;font:700 20px/1.05 var(--head);letter-spacing:-.02em;color:var(--text)}
.rel-date .m{display:block;margin-top:5px;font:500 11px/1 var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--text-3)}
.rel-body h3{margin:0 0 4px;font:600 18px/1.3 var(--head);letter-spacing:-.01em;color:var(--text)}
.rel-note{margin:0 0 8px;color:var(--text-3);font-size:15px}
.full-list{display:inline-block;margin-top:14px;color:var(--accent);font:600 14px/1.4 var(--sans);text-decoration:none}
.full-list:hover{color:var(--accent-hover);text-decoration:underline;text-underline-offset:3px}

/* Footer */
footer{margin-top:56px;padding-top:24px;border-top:1px solid var(--border)}
.note{display:flex;gap:12px;align-items:flex-start;padding:2px 0 2px 16px;border-left:2px solid var(--accent);color:var(--text-2);font-size:15.5px;line-height:1.6}
.note .ico{font-size:15px;line-height:1.6}
.sign{margin-top:28px;text-align:center;color:var(--text-3);font:500 12px/1.5 var(--mono)}
"""

def render(data):
    games = data.get("your_games", [])
    industry = data.get("industry", [])
    releases = data.get("releases", [])
    sections, nav = [], []
    if games:
        nav.append('<a href="#your-games">Your games</a>')
        sections.append(f'<section id="your-games"><h2>Your games<span class="count">{len(games)} stories</span></h2>'
                        f'<div class="grid">{"".join(story_card(s) for s in games)}</div></section>')
    if industry:
        nav.append('<a href="#industry">Industry</a>')
        sections.append(f'<section id="industry"><h2>Industry<span class="count">{len(industry)} stories</span></h2>'
                        f'<div class="grid">{"".join(story_card(s) for s in industry)}</div></section>')
    if releases:
        nav.append('<a href="#out-this-week">Out this week</a>')
        full = (f'<a class="full-list" href="{escape(data["releases_link"], quote=True)}" target="_blank" rel="noopener noreferrer">'
                f'See the full release list ↗</a>') if data.get("releases_link") else ""
        sections.append(f'<section id="out-this-week"><h2>Out this week</h2>'
                        f'<ul class="releases">{"".join(release_row(r) for r in releases)}</ul>{full}</section>')
    note = (f'<div class="note"><span class="ico" aria-hidden="true">📌</span><div>{escape(data["footer_note"])}</div></div>'
            if data.get("footer_note") else "")
    date_label = escape(data.get("date_label", data.get("date", "")))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0f1012">
<meta name="color-scheme" content="dark">
<title>Loot's Gaming Roundup · {date_label}</title>
<meta name="description" content="Daily gaming news: your games, industry news and what's out this week.">
<link rel="icon" href="/brand/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/brand/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/brand/favicon-16.png">
<link rel="apple-touch-icon" href="/brand/apple-touch-icon-180.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<meta property="og:type" content="website">
<meta property="og:site_name" content="Loot's Gaming Roundup">
<meta property="og:title" content="Loot's Gaming Roundup · {date_label}">
<meta property="og:description" content="Daily gaming news: your games, industry news and what's out this week.">
<meta property="og:image" content="https://loot-gaming-roundup.vercel.app/brand/og-1200x630.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Loot's Gaming Roundup">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Loot's Gaming Roundup · {date_label}">
<meta name="twitter:description" content="Daily gaming news: your games, industry news and what's out this week.">
<meta name="twitter:image" content="https://loot-gaming-roundup.vercel.app/brand/og-1200x630.png">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
<img class="logo" src="brand/logo-256.png" alt="Loot" width="84" height="84">
<div class="kicker"><span class="dot"></span>Daily gaming news</div>
<h1>Loot's Gaming Roundup</h1>
<div class="date">{date_label}</div>
<nav class="jump">{"".join(nav)}</nav>
</header>
{"".join(sections)}
<footer>{note}<div class="sign">Compiled by Loot · links open in a new tab</div></footer>
</div>
</body>
</html>
"""

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json_file")
    ap.add_argument("-o", "--output")
    ap.add_argument("--no-index", action="store_true")
    a = ap.parse_args()
    with open(a.json_file, encoding="utf-8") as f:
        data = json.load(f)
    here = os.path.dirname(os.path.abspath(__file__))
    out = a.output or os.path.join(here, f'{data["date"]}.html')
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(data))
    print("wrote", out)
    if not a.output and not a.no_index:
        idx = os.path.join(here, "index.html")
        shutil.copyfile(out, idx)
        print("wrote", idx)

if __name__ == "__main__":
    main()
