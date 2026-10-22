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
:root{--bg:#0b0d14;--bg2:#121624;--card:#161b2c;--card2:#1b2135;--line:#272f48;--text:#e8ebf5;--muted:#9aa3bd;
--accent:#ffb627;--accent2:#7c5cff;--ps:#2f7dff;--nin:#ff3b4a;--xbox:#33c45a;--pc:#a0a8bd;}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:radial-gradient(1200px 600px at 10% -10%,rgba(124,92,255,.22),transparent 60%),
radial-gradient(900px 500px at 110% 0%,rgba(255,182,39,.12),transparent 60%),var(--bg);
color:var(--text);font:16px/1.55 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
min-height:100vh;padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)}
.wrap{max-width:1040px;margin:0 auto;padding:28px 18px 40px}
header{padding:18px 0 22px;border-bottom:1px solid var(--line);margin-bottom:8px}
.kicker{display:inline-flex;align-items:center;gap:8px;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:700}
.kicker .dot{width:8px;height:8px;border-radius:50%;background:var(--accent);box-shadow:0 0 12px var(--accent)}
h1{margin:10px 0 6px;font-size:clamp(30px,8vw,52px);line-height:1.05;letter-spacing:-.02em;font-weight:800;
background:linear-gradient(90deg,#fff 0%,#ffd77a 45%,var(--accent) 70%,#ff8a3d 100%);-webkit-background-clip:text;background-clip:text;color:transparent}
.date{color:var(--muted);font-size:15px;font-weight:500}
nav.jump{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
nav.jump a{color:var(--text);text-decoration:none;font-size:13px;font-weight:600;padding:7px 12px;border-radius:999px;background:var(--bg2);border:1px solid var(--line)}
nav.jump a:hover{border-color:var(--accent)}
section{margin-top:30px}
h2{display:flex;align-items:center;gap:10px;font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin:0 0 14px;font-weight:700}
h2::before{content:"";width:4px;height:18px;border-radius:2px;background:linear-gradient(var(--accent),var(--accent2))}
h2 .count{margin-left:auto;font-size:12px;color:var(--muted);letter-spacing:.05em}
.grid{display:grid;grid-template-columns:1fr;gap:14px}
@media(min-width:720px){.grid{grid-template-columns:1fr 1fr}.wrap{padding:44px 28px 56px}}
.card{position:relative;background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:16px;padding:16px 16px 14px;overflow:hidden;transition:border-color .2s,transform .2s}
.card::after{content:"";position:absolute;inset:0 0 auto 0;height:2px;background:linear-gradient(90deg,var(--accent2),var(--accent));opacity:.7}
.card:hover{border-color:#3a4466;transform:translateY(-2px)}
.card h3{margin:8px 0 6px;font-size:19px;line-height:1.25;letter-spacing:-.01em}
.card p{margin:0;color:#cfd4e4;font-size:15.5px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:3px 8px;border-radius:6px;border:1px solid;line-height:1.4}
.chip-ps{color:#8fb6ff;border-color:rgba(47,125,255,.5);background:rgba(47,125,255,.14)}
.chip-nin{color:#ff8f98;border-color:rgba(255,59,74,.5);background:rgba(255,59,74,.13)}
.chip-xbox{color:#7fe59a;border-color:rgba(51,196,90,.5);background:rgba(51,196,90,.13)}
.chip-pc{color:#d3d8e6;border-color:rgba(160,168,189,.45);background:rgba(160,168,189,.12)}
.chip-game{color:#ffd27a;border-color:rgba(255,182,39,.45);background:rgba(255,182,39,.12)}
.sources{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:12px;padding-top:12px;border-top:1px dashed var(--line)}
.src-label{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:700}
a.src{color:var(--accent);text-decoration:none;font-weight:600;font-size:14px;padding:6px 10px;border-radius:8px;background:rgba(255,182,39,.08);border:1px solid rgba(255,182,39,.25);min-height:32px;display:inline-flex;align-items:center}
a.src:hover{background:rgba(255,182,39,.16)}
ul.releases{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.release{display:flex;gap:14px;align-items:flex-start;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.rel-date{flex:0 0 56px;text-align:center;background:linear-gradient(160deg,rgba(124,92,255,.25),rgba(255,182,39,.15));border:1px solid var(--line);border-radius:10px;padding:6px 0}
.rel-date .d{display:block;font-size:22px;font-weight:800;line-height:1.1}
.rel-date .m{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:700}
.rel-body h3{margin:2px 0 4px;font-size:17px;line-height:1.3}
.rel-note{margin:0 0 8px;color:var(--muted);font-size:14.5px}
.full-list{display:inline-block;margin-top:14px;color:var(--accent);font-weight:600;text-decoration:none;font-size:14px}
.full-list:hover{text-decoration:underline}
footer{margin-top:36px}
.note{display:flex;gap:12px;align-items:flex-start;background:rgba(124,92,255,.1);border:1px solid rgba(124,92,255,.35);border-radius:14px;padding:14px 16px;color:#d9d3ff;font-size:15px}
.note .ico{font-size:18px;line-height:1.3}
.sign{margin-top:18px;text-align:center;color:var(--muted);font-size:13px}
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
<meta name="theme-color" content="#0b0d14">
<meta name="color-scheme" content="dark">
<title>Loot's Gaming Roundup · {date_label}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
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
