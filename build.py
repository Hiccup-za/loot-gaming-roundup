#!/usr/bin/env python3
"""Render Loot's Gaming Roundup from a JSON file into a self-contained HTML page.

Usage:
    python3 build.py 2026-10-11.json            # writes 2026-10-11.html + index.html
    python3 build.py --all                      # rebuild every edition, index, archive, badges, sitemap
    python3 build.py --backfill-views           # fetch views snapshots for all editions (needs DATABUDDY_API_KEY)
    python3 build.py data.json -o out.html      # custom output, no index copy
    python3 build.py data.json --no-index       # skip updating index.html
"""
import argparse, json, os, re, shutil, sys
from datetime import datetime
from html import escape

import views_fetch

EDITION_JSON = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
SITE_URL = os.environ.get("LOOT_SITE_URL", "https://loot-gaming-roundup.vercel.app")

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
  -webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;min-height:100vh}
:root{--gutter:18px;--bar-h:106px;--max:760px}
@media(min-width:720px){:root{--gutter:32px;--bar-h:86px}}
.wrap{max-width:var(--max);margin:0 auto;padding:20px max(var(--gutter),env(safe-area-inset-right)) max(48px,env(safe-area-inset-bottom)) max(var(--gutter),env(safe-area-inset-left))}
@media(min-width:720px){.wrap{padding-top:28px;padding-bottom:72px}}
a:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:6px}

/* Sticky masthead bar: full-width background, contents on the column's left edge */
header.masthead{position:sticky;top:0;z-index:50;background:rgba(15,16,18,.9);
  -webkit-backdrop-filter:saturate(140%) blur(14px);backdrop-filter:saturate(140%) blur(14px);
  border-bottom:1px solid var(--border);padding-top:env(safe-area-inset-top)}
@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){header.masthead{background:var(--bg)}}
.bar{max-width:var(--max);margin:0 auto;display:flex;flex-direction:column;gap:8px;
  padding:10px max(var(--gutter),env(safe-area-inset-right)) 10px max(var(--gutter),env(safe-area-inset-left))}
.brand{display:flex;align-items:center;gap:10px;min-width:0;color:var(--text);text-decoration:none}
.brand .logo{flex:0 0 auto;width:44px;height:44px;object-fit:contain;display:block;border-radius:0;background:none;border:0;box-shadow:none}
h1{margin:0;min-width:0;font:800 20px/1.1 var(--head);letter-spacing:-.025em;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
nav.jump{display:flex;flex-wrap:nowrap;gap:6px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;
  margin:0 calc(-1 * var(--gutter));padding:0 var(--gutter)}
nav.jump::-webkit-scrollbar{display:none}
nav.jump a{flex:0 0 auto;display:inline-flex;align-items:center;min-height:32px;padding:0 13px;border-radius:999px;border:1px solid var(--border);
  background:var(--surface);color:var(--text-2);text-decoration:none;font:500 13.5px/1 var(--sans);white-space:nowrap;transition:border-color .15s,color .15s}
nav.jump a:hover{border-color:var(--border-strong);color:var(--text)}
nav.jump a[aria-current="true"]{border-color:var(--accent);background:var(--accent-tint);color:var(--accent)}
nav.jump a[aria-current="true"]:hover{border-color:var(--accent-hover);color:var(--accent-hover)}
@media(min-width:720px){
  .bar{flex-direction:row;align-items:center;justify-content:space-between;gap:20px;padding-top:14px;padding-bottom:14px}
  .brand{gap:14px}
  .brand .logo{width:56px;height:56px}
  h1{font-size:24px}
  nav.jump{margin:0;padding:0;overflow:visible}
  nav.jump a{min-height:34px;font-size:14px}
}

/* Intro line under the bar (scrolls away) */
.intro{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 16px}
.intro-lead{display:flex;flex-wrap:wrap;align-items:center;gap:6px 16px;min-width:0}
.kicker{display:inline-flex;align-items:center;gap:8px;font:600 12px/1.2 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.kicker .dot{width:6px;height:6px;border-radius:50%;background:var(--accent)}
.date{font:500 13px/1.4 var(--mono);color:var(--text-3)}

/* Sections: editorial breaks, no boxes */
section{margin-top:56px;scroll-margin-top:calc(var(--bar-h) + env(safe-area-inset-top) + 12px)}
.intro+.layout>:first-child>section:first-child{margin-top:28px}
h2{display:flex;align-items:baseline;gap:12px;margin:0;padding-top:16px;border-top:3px solid var(--text);
  font:800 30px/1.1 var(--head);letter-spacing:-.025em;color:var(--text)}
@media(min-width:720px){h2{font-size:34px}}
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
a.src:hover{color:var(--text);text-decoration:underline;text-underline-offset:3px}
a.src:hover span{color:var(--text-2)}

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

/* Edition views sparkline in sub-header (baked in at build time) */
.edition-views{display:flex;align-items:center;gap:8px;margin:0;padding:4px 0;
  font:500 12px/1.3 var(--sans);color:var(--text-3);flex:0 0 auto;min-height:28px}
.edition-views-muted{color:var(--text-3);opacity:.85;font-size:12px}
.views-num{font:500 13px/1 var(--mono);color:var(--text-2)}
.views-word{white-space:nowrap;letter-spacing:.02em}
.views-spark{display:block;flex:0 0 auto;opacity:.88;overflow:visible}
.views-line{stroke:var(--accent);fill:none;stroke-width:1.25;stroke-linecap:round;stroke-linejoin:round}
.views-stop-top{stop-color:var(--accent-tint)}
.views-stop-bottom{stop-color:var(--accent-tint);stop-opacity:0}
@media(max-width:479px){.edition-views{width:100%;justify-content:flex-end}}

/* Archive: one card per edition, newest first */
.archive-cards{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}
.archive-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  transition:border-color .15s ease,background .15s ease}
.archive-card:hover,.archive-card:focus-within{border-color:var(--border-strong);background:var(--surface-2)}
.archive-card-inner{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px 18px}
a.archive-card-title{flex:1 1 auto;min-width:0;font:600 17px/1.3 var(--head);letter-spacing:-.01em;
  color:var(--accent);text-decoration:none}
a.archive-card-title:hover{color:var(--accent-hover);text-decoration:underline;text-underline-offset:3px}
.archive-card .edition-views{min-height:24px;padding:0}
.archive-card .views-spark{width:72px;height:24px}
.archive-card-meta{flex:0 0 auto;font:500 12px/1.35 var(--sans);color:var(--text-3);text-align:right;max-width:min(220px,42vw)}
.archive-card-meta-muted{opacity:.85}
@media(max-width:479px){
  .archive-card-inner{flex-wrap:wrap;padding:14px 16px}
  a.archive-card-title{flex:1 1 100%}
  .archive-card .edition-views,.archive-card-meta{margin-left:auto}
}

/* Wide screens: main feed + sticky "Out this week" sidebar (phones and tablets keep the single column above) */
@media(min-width:1000px){
  :root{--max:1200px;--gutter:40px;--side:300px;--col-gap:56px}
  .layout.has-side{display:grid;grid-template-columns:minmax(0,1fr) var(--side);column-gap:var(--col-gap);align-items:start;margin-top:36px}
  .layout.has-side>*>section:first-child,.intro+.layout.has-side>*>section:first-child{margin-top:0}
  .layout.has-side+footer{margin-right:calc(var(--side) + var(--col-gap))}
  .side{position:sticky;top:calc(var(--bar-h) + env(safe-area-inset-top) + 28px);
    max-height:calc(100vh - var(--bar-h) - env(safe-area-inset-top) - 52px);overflow-y:auto;overscroll-behavior:contain;
    scrollbar-width:thin;scrollbar-color:var(--border-strong) transparent;padding:0 6px 44px 0;margin-right:-6px;
    -webkit-mask-image:linear-gradient(to bottom,#000 calc(100% - 56px),transparent);mask-image:linear-gradient(to bottom,#000 calc(100% - 56px),transparent)}
  .side::-webkit-scrollbar{width:6px}
  .side::-webkit-scrollbar-thumb{background:var(--border-strong);border-radius:3px}
  h2{font-size:36px}
  .side h2{font-size:30px}
  nav.jump a.jump-side{display:none}
  .side .release{gap:14px;padding:14px 0}
  .side .rel-date{flex-basis:52px}
  .side .rel-date .d{font-size:18px}
  .side .rel-body h3{font-size:15.5px;line-height:1.35}
  .side .rel-note{font-size:13.5px;margin-bottom:6px}
  .side .full-list{margin:10px 0 4px}
  .feed .card p,.feed .card .sources,.note{max-width:38em}
}
@media(min-width:1440px){
  :root{--max:1280px;--gutter:48px;--side:360px;--col-gap:80px;--bar-h:90px}
  h1{font-size:26px}
  .brand .logo{width:60px;height:60px}
  section{margin-top:64px}
  h2{font-size:40px}
  .side h2{font-size:32px}
  .card{padding:32px 0 34px}
  .card h3{font-size:28px}
  .card p{font-size:17.5px;line-height:1.7}
  .side .rel-body h3{font-size:16px}
}

/* Archive: structured edition cards */
.wrap--archive{--max:960px}
@media(min-width:1000px){.wrap--archive{--max:1080px}}
.archive-grid{display:grid;grid-template-columns:1fr;gap:16px;margin-top:28px}
@media(min-width:560px){.archive-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}
@media(min-width:900px){.archive-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}}
a.archive-card{display:flex;flex-direction:column;gap:16px;padding:18px 18px 16px;background:var(--surface);
  border:1px solid var(--border);border-radius:12px;text-decoration:none;color:inherit;
  transition:border-color .15s,background .15s,box-shadow .15s}
a.archive-card:hover{border-color:var(--accent);background:var(--surface-2);box-shadow:0 0 0 1px color-mix(in srgb,var(--accent) 35%,transparent)}
a.archive-card:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.archive-card-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
.archive-card-title{margin:0;flex:1 1 auto;font:700 clamp(16px,2.4vw,17px)/1.25 var(--head);letter-spacing:-.015em;
  color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.archive-year-section+.archive-year-section{margin-top:48px}
.archive-card-read{flex:0 0 auto;display:inline-flex;align-items:center;gap:4px;
  font:600 12px/1 var(--sans);letter-spacing:.04em;text-transform:uppercase;color:var(--accent);white-space:nowrap}
.archive-card-read .arr{font-size:14px;line-height:1}
.archive-stat-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.archive-stat-block{display:flex;flex-direction:column;gap:4px;padding:10px 8px;background:var(--surface-2);
  border:1px solid var(--border);border-radius:8px;text-align:center;min-width:0}
.archive-stat-label{font:600 10px/1 var(--sans);letter-spacing:.1em;text-transform:uppercase;color:var(--text-3)}
.archive-stat-value{font:600 18px/1.1 var(--mono);color:var(--text);font-variant-numeric:tabular-nums}
.archive-stat-value.is-muted{color:var(--text-3)}
.archive-chart-panel{flex:0 0 auto;height:72px;padding:10px 12px;background:var(--surface-2);
  border:1px solid var(--border);border-radius:8px;display:flex;align-items:center;justify-content:center;overflow:hidden}
.archive-chart-panel svg{width:100%;height:100%;display:block}
.archive-chart-line{stroke:var(--accent);fill:none;stroke-width:1.25;vector-effect:non-scaling-stroke;
  stroke-linecap:round;stroke-linejoin:round}
.archive-chart-stop-top{stop-color:var(--accent-tint)}
.archive-chart-stop-bottom{stop-color:var(--accent-tint);stop-opacity:0}
.archive-chart-empty{margin:0;font:500 12px/1.35 var(--sans);color:var(--text-3);text-align:center}

/* Badges: every story/release tag across all editions */
.wrap--badges{--max:960px}
@media(min-width:1000px){.wrap--badges{--max:1080px}}
.badges-list{list-style:none;margin:28px 0 0;padding:0;display:grid;grid-template-columns:1fr;gap:10px}
@media(min-width:560px){.badges-list{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
@media(min-width:900px){.badges-list{grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}
.badge-item{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;
  background:var(--surface);border:1px solid var(--border);border-radius:8px;min-width:0}
.badge-item .chip{flex:0 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.badge-count{flex:0 0 auto;font:600 15px/1 var(--mono);color:var(--text-2);font-variant-numeric:tabular-nums}
.badges-summary{margin-top:28px;display:flex;flex-direction:column;gap:16px}
@media(min-width:960px){.badges-summary{flex-direction:row;align-items:stretch;gap:24px}}
.badges-kpi-panel{flex:0 0 auto;display:flex;flex-direction:column;gap:10px}
@media(min-width:960px){.badges-kpi-panel{flex:0 0 min(300px,34%)}}
.badges-kpi-hero{display:flex;flex-direction:column;gap:8px;padding:20px 18px;background:var(--surface);
  border:1px solid var(--border);border-radius:12px}
.badges-kpi-hero-value{font:700 clamp(34px,4.5vw,44px)/1 var(--mono);color:var(--text);font-variant-numeric:tabular-nums}
.badges-kpi-hero-label{font:600 11px/1.2 var(--sans);letter-spacing:.1em;text-transform:uppercase;color:var(--text-3)}
.badges-kpi-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.badges-trend-panel{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:10px;padding:16px 18px 14px;
  background:var(--surface);border:1px solid var(--border);border-radius:12px}
.badges-trend-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px}
.badges-trend-title{font:600 11px/1.2 var(--sans);letter-spacing:.1em;text-transform:uppercase;color:var(--text-3)}
.badges-trend-range{font:500 12px/1.35 var(--mono);color:var(--text-3);white-space:nowrap}
.badges-trend-chart{flex:1 1 auto;min-height:132px;display:flex;align-items:center}
.badges-trend-chart svg{width:100%;height:132px;display:block}
.badges-trend-axis{font:500 10px/1 var(--mono);fill:var(--text-3)}
.badges-trend-line{stroke:var(--accent);fill:none;stroke-width:1.75;vector-effect:non-scaling-stroke;
  stroke-linecap:round;stroke-linejoin:round}
.badges-trend-dot{fill:var(--accent);stroke:var(--bg);stroke-width:1.5}
.badges-trend-fill{stroke:none}
"""

# Scroll-spy for the masthead nav. A 1px line just below the sticky header is the
# trigger: the active section is the last one whose top has crossed it. On wide
# screens "Out this week" is a sticky sidebar that never scrolls past the line, so
# only the main feed sections drive the state there.
SCROLL_SPY_JS = r"""
(function(){
  if(!('IntersectionObserver' in window))return;
  var header=document.querySelector('header.masthead');
  var links=[].slice.call(document.querySelectorAll('nav.jump a[href^="#"]'));
  var footer=document.querySelector('footer');
  var wide=window.matchMedia('(min-width:1000px)');
  var hasSide=!!document.querySelector('.layout.has-side');
  var observers=[],current=null;
  function setActive(id){
    if(id===current)return;
    current=id;
    links.forEach(function(a){
      if(a.getAttribute('href')==='#'+id)a.setAttribute('aria-current','true');
      else a.removeAttribute('aria-current');
    });
  }
  function spied(){
    return links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1));})
      .filter(function(s){return s&&!(hasSide&&wide.matches&&s.closest('.side'));});
  }
  function line(){return header.getBoundingClientRect().bottom+16;}
  function update(){
    var secs=spied(),y=line(),id=null;
    secs.forEach(function(s){if(s.getBoundingClientRect().top<=y)id=s.id;});
    var atEnd=window.innerHeight+window.scrollY>=document.documentElement.scrollHeight-2;
    if(atEnd&&secs.length&&secs[secs.length-1].getBoundingClientRect().top<window.innerHeight)id=secs[secs.length-1].id;
    setActive(id);
  }
  function observe(){
    observers.forEach(function(o){o.disconnect();});
    var top=Math.round(line());
    var bottom=Math.max(0,window.innerHeight-top-1);
    var spy=new IntersectionObserver(update,{rootMargin:'-'+top+'px 0px -'+bottom+'px 0px'});
    spied().forEach(function(s){spy.observe(s);});
    observers=[spy];
    if(footer){
      var end=new IntersectionObserver(update,{threshold:[0,1]});
      end.observe(footer);
      observers.push(end);
    }
    update();
  }
  var t;
  window.addEventListener('resize',function(){clearTimeout(t);t=setTimeout(observe,150);});
  observe();
})();
"""

def fmt_views(n):
    return f"{int(n):,}"


def sparkline_paths(cum_vals, *, width=88, height=28, pad=2):
    w, h = width, height
    if not cum_vals:
        return "", ""
    iw, ih = w - pad * 2, h - pad * 2
    mx = max(cum_vals)
    xs, ys = [], []
    for j, val in enumerate(cum_vals):
        x = pad + (iw / 2 if len(cum_vals) == 1 else iw * j / (len(cum_vals) - 1))
        if mx == 0:
            ys.append(h - pad - 1.25)
        else:
            ys.append(pad + ih - (val / mx) * ih)
        xs.append(x)
    line = f"M{xs[0]:.2f},{ys[0]:.2f}"
    for k in range(1, len(xs)):
        line += f" L{xs[k]:.2f},{ys[k]:.2f}"
    base = h - pad
    area = f"{line} L{xs[-1]:.2f},{base:.2f} L{xs[0]:.2f},{base:.2f} Z"
    return line, area


def _series_sort_key(point):
    if point.get("timestamp"):
        return point["timestamp"]
    if point.get("date"):
        return point["date"]
    return ""


def views_sparkline(
    data,
    *,
    elem="p",
    spark_w=88,
    spark_h=28,
    muted_only=False,
):
    snap = data.get("views_snapshot")
    muted = f'<{elem} class="edition-views edition-views-muted">Views not recorded</{elem}>'
    if not snap:
        return muted
    series = sorted(snap.get("series") or [], key=_series_sort_key)
    tracked = [
        p
        for p in series
        if p.get("tracked", True) and p.get("pageviews") is not None
    ]
    total = snap.get("total_views")
    if total is None:
        total = sum(int(p.get("pageviews") or 0) for p in tracked)
    note = snap.get("tracking_note")
    if not tracked and total == 0:
        if muted_only:
            tip = escape(note) if note else ""
            title_attr = f' title="{tip}"' if tip else ""
            return (
                f'<span class="archive-card-meta archive-card-meta-muted"{title_attr}>'
                f"Views not recorded</span>"
            )
        if not note:
            return muted
    cum, cum_vals = 0, []
    for p in tracked:
        cum += int(p.get("pageviews") or 0)
        cum_vals.append(cum)
    if len(cum_vals) == 1:
        cum_vals = [0, cum_vals[0]]
    line_d, fill_d = sparkline_paths(cum_vals, width=spark_w, height=spark_h)
    tip = escape(note or views_fetch.VIEWS_PATHS_TOOLTIP)
    label = escape(f"{fmt_views(total)} total views")
    grad_id = f"views-grad-{data.get('date', 'x').replace('-', '')}"
    svg = ""
    if line_d:
        svg = (
            f'<svg class="views-spark" viewBox="0 0 {spark_w} {spark_h}" width="{spark_w}" height="{spark_h}" '
            f'aria-hidden="true" focusable="false">'
            f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop class="views-stop-top" offset="0%"/><stop class="views-stop-bottom" offset="100%"/>'
            f"</linearGradient></defs>"
            f'<path fill="url(#{grad_id})" stroke="none" d="{fill_d}"/>'
            f'<path class="views-line" d="{line_d}" fill="none" stroke-width="1.25" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f"</svg>"
        )
    return (
        f'<{elem} class="edition-views" title="{tip}" aria-label="{label}">'
        f'<span class="views-num">{fmt_views(total)}</span>'
        f'<span class="views-word">total views</span>{svg}</{elem}>'
    )


def render(data):
    games = data.get("your_games", [])
    industry = data.get("industry", [])
    releases = data.get("releases", [])
    sections, side, nav = [], [], []
    if games:
        nav.append('<a href="#your-games">Your games</a>')
        sections.append(f'<section id="your-games"><h2>Your games<span class="count">{len(games)} stories</span></h2>'
                        f'<div class="grid">{"".join(story_card(s) for s in games)}</div></section>')
    if industry:
        nav.append('<a href="#industry">Industry</a>')
        sections.append(f'<section id="industry"><h2>Industry<span class="count">{len(industry)} stories</span></h2>'
                        f'<div class="grid">{"".join(story_card(s) for s in industry)}</div></section>')
    if releases:
        side_cls = ' class="jump-side"' if sections else ""
        nav.append(f'<a{side_cls} href="#out-this-week">Out this week</a>')
        side.append(f'<section id="out-this-week"><h2>Out this week</h2>'
                        f'<ul class="releases">{"".join(release_row(r) for r in releases)}</ul></section>')
    nav.append('<a href="/archive.html">Archive</a>')
    nav.append('<a href="/badges.html">Badges</a>')
    note = (f'<div class="note"><span class="ico" aria-hidden="true">📌</span><div>{escape(data["footer_note"])}</div></div>'
            if data.get("footer_note") else "")
    date_label = escape(data.get("date_label", data.get("date", "")))
    parts = []
    if sections:
        parts.append(f'<main class="feed">{"".join(sections)}</main>')
    if side:
        parts.append(f'<aside class="side" aria-label="Out this week">{"".join(side)}</aside>')
    layout = f'<div class="layout{" has-side" if sections and side else ""}">{"".join(parts)}</div>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0f1012">
<script src="https://cdn.databuddy.cc/databuddy.js" data-client-id="d2f227a9-4c59-4917-b672-37f4eb3d81f9" data-track-outgoing-links="true" data-track-interactions="false" crossorigin="anonymous" async></script>
<meta name="color-scheme" content="dark">
<title>Loot's Gaming Roundup · {date_label}</title>
<meta name="description" content="Daily gaming news: your games, industry news and what's out this week.">
<link rel="icon" href="/brand/favicon.ico?v=2" sizes="16x16 32x32 48x48">
<link rel="icon" type="image/png" sizes="16x16" href="/brand/favicon-16.png?v=2">
<link rel="icon" type="image/png" sizes="32x32" href="/brand/favicon-32.png?v=2">
<link rel="icon" type="image/png" sizes="48x48" href="/brand/favicon-48.png?v=2">
<link rel="icon" type="image/png" sizes="192x192" href="/brand/favicon-192.png?v=2">
<link rel="icon" type="image/png" sizes="512x512" href="/brand/favicon-512.png?v=2">
<link rel="apple-touch-icon" sizes="180x180" href="/brand/apple-touch-icon-180.png?v=2">
<link rel="manifest" href="/site.webmanifest?v=2">
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
<header class="masthead">
<div class="bar">
<a class="brand" href="/" aria-label="Loot's Gaming Roundup, home"><img class="logo" src="brand/logo-mascot-256.png" alt="Loot" width="56" height="56"><h1>Loot's Gaming Roundup</h1></a>
<nav class="jump" aria-label="Sections">{"".join(nav)}</nav>
</div>
</header>
<div class="wrap" id="top">
<div class="intro"><div class="intro-lead"><div class="kicker"><span class="dot"></span>Daily gaming news</div><div class="date">{date_label}</div></div>{views_sparkline(data)}</div>
{layout}
<footer>{note}<div class="sign"><a class="full-list" href="/archive.html">Past roundups</a> · Compiled by Loot · links open in a new tab</div></footer>
</div>
<script>{SCROLL_SPY_JS}</script>
</body>
</html>
"""

def list_edition_jsons(root):
    paths = []
    for name in os.listdir(root):
        if EDITION_JSON.match(name):
            paths.append(os.path.join(root, name))
    return sorted(paths)


def load_editions(root):
    return [r["data"] for r in load_edition_records(root)]


def load_edition_records(root):
    records = []
    for path in list_edition_jsons(root):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        records.append({"path": path, "data": data})
    records.sort(key=lambda r: r["data"]["date"])
    return records


def write_edition_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("updated", path)


def measurement_windows(records):
    """Publish-to-publish windows in edition date order."""
    windows = []
    for i, rec in enumerate(records):
        ws = views_fetch.infer_published_at(rec["data"])
        if i + 1 < len(records):
            we = views_fetch.infer_published_at(records[i + 1]["data"])
        else:
            we = views_fetch.now_jhb()
        windows.append((rec, ws, we))
    return windows


def sync_views(root, *, refresh=False, backfill=False, only_dates=None):
    api_key = os.environ.get("DATABUDDY_API_KEY")
    if not api_key:
        if refresh or backfill:
            print("DATABUDDY_API_KEY not set; skipping views fetch", file=sys.stderr)
        return []
    records = load_edition_records(root)
    updated_dates = []
    for rec, ws, we in measurement_windows(records):
        date_key = rec["data"]["date"]
        if only_dates and date_key not in only_dates:
            continue
        if not views_fetch.needs_views_fetch(rec["data"], we, refresh=refresh, backfill=backfill):
            continue
        try:
            snap = views_fetch.build_views_snapshot(date_key, ws, we, api_key)
        except RuntimeError as e:
            print(f"views fetch failed for {date_key}: {e}", file=sys.stderr)
            continue
        rec["data"]["views_snapshot"] = snap
        write_edition_json(rec["path"], rec["data"])
        updated_dates.append(date_key)
    return updated_dates


def finalize_previous_edition(root, current_date, *, refresh=False, backfill=False):
    records = load_edition_records(root)
    prev = None
    for rec in records:
        if rec["data"]["date"] == current_date:
            break
        prev = rec
    if not prev:
        return
    ws = views_fetch.infer_published_at(prev["data"])
    we = views_fetch.infer_published_at(
        next(r for r in records if r["data"]["date"] == current_date)["data"]
    )
    if not views_fetch.needs_views_fetch(prev["data"], we, refresh=refresh, backfill=backfill):
        return
    api_key = os.environ.get("DATABUDDY_API_KEY")
    if not api_key:
        return
    try:
        snap = views_fetch.build_views_snapshot(prev["data"]["date"], ws, we, api_key)
    except RuntimeError as e:
        print(f"views fetch failed for {prev['data']['date']}: {e}", file=sys.stderr)
        return
    prev["data"]["views_snapshot"] = snap
    write_edition_json(prev["path"], prev["data"])


def edition_story_count(ed):
    return len(ed.get("your_games") or []) + len(ed.get("industry") or [])


def edition_release_day_label(iso_date):
    """Edition calendar day as in release rows, e.g. 22 Oct."""
    d = datetime.strptime(iso_date, "%Y-%m-%d")
    return f"{d.day} {d.strftime('%b')}"


def edition_out_today_count(ed):
    """Releases dated Today or this edition's D Mon — not Out now / later calendar rows."""
    day_mon = edition_release_day_label(ed["date"])
    count = 0
    for release in ed.get("releases") or []:
        raw = (release.get("date") or "").strip()
        if not raw:
            continue
        low = raw.lower()
        if low == "today" or low == day_mon.lower():
            count += 1
    return count


def archive_card_title_html(ed):
    d = datetime.strptime(ed["date"], "%Y-%m-%d")
    wd = escape(d.strftime("%a"))
    rest = escape(f"{d.day} {d.strftime('%B')}")
    return f'<h3 class="archive-card-title">{wd} · {rest}</h3>'


def archive_views_untracked(ed):
    snap = ed.get("views_snapshot")
    if not snap:
        return True
    note = snap.get("tracking_note") or ""
    if note == views_fetch.TRACKING_NOTE_BEFORE or "ended before tracking was live" in note:
        return True
    return False


def archive_cumulative_series(ed):
    snap = ed.get("views_snapshot") or {}
    series = sorted(snap.get("series") or [], key=_series_sort_key)
    tracked = [
        p
        for p in series
        if p.get("tracked", True) and p.get("pageviews") is not None
    ]
    total = snap.get("total_views")
    if total is None:
        total = sum(int(p.get("pageviews") or 0) for p in tracked)
    cum, cum_vals = 0, []
    for p in tracked:
        cum += int(p.get("pageviews") or 0)
        cum_vals.append(cum)
    if len(cum_vals) == 1:
        cum_vals = [0, cum_vals[0]]
    return int(total), cum_vals, snap.get("tracking_note")


def archive_stat_block(label, value, *, muted=False):
    val_cls = "archive-stat-value is-muted" if muted else "archive-stat-value"
    return (
        f'<div class="archive-stat-block">'
        f'<span class="archive-stat-label">{escape(label)}</span>'
        f'<span class="{val_cls}">{escape(value)}</span>'
        f"</div>"
    )


def archive_chart_panel(ed):
    chart_w, chart_h, chart_pad = 400, 72, 8
    if archive_views_untracked(ed):
        return (
            '<div class="archive-chart-panel" aria-hidden="true">'
            '<p class="archive-chart-empty">Views not tracked yet</p></div>'
        )
    total, cum_vals, note = archive_cumulative_series(ed)
    if not cum_vals:
        cum_vals = [0, 0]
    line_d, fill_d = sparkline_paths(
        cum_vals, width=chart_w, height=chart_h, pad=chart_pad
    )
    grad_id = f"archive-grad-{ed.get('date', 'x').replace('-', '')}"
    tip = escape(note or views_fetch.VIEWS_PATHS_TOOLTIP)
    svg = (
        f'<svg class="archive-chart-svg" viewBox="0 0 {chart_w} {chart_h}" '
        f'preserveAspectRatio="none" aria-hidden="true" focusable="false">'
        f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop class="archive-chart-stop-top" offset="0%"/>'
        f'<stop class="archive-chart-stop-bottom" offset="100%"/>'
        f"</linearGradient></defs>"
        f'<path class="archive-chart-fill" fill="url(#{grad_id})" stroke="none" d="{fill_d}"/>'
        f'<path class="archive-chart-line" d="{line_d}"/>'
        f"</svg>"
    )
    return (
        f'<div class="archive-chart-panel" title="{tip}" '
        f'aria-label="{escape(f"{fmt_views(total)} total views chart")}">{svg}</div>'
    )


def archive_card(ed):
    slug = escape(ed["date"])
    full_label = escape(ed.get("date_label", ed["date"]))
    stories = edition_story_count(ed)
    out_today = edition_out_today_count(ed)
    if archive_views_untracked(ed):
        views_val = "—"
        views_muted = True
    else:
        total, _, _ = archive_cumulative_series(ed)
        views_val = fmt_views(total)
        views_muted = False
    stats = (
        archive_stat_block("Stories", str(stories))
        + archive_stat_block("Out today", str(out_today))
        + archive_stat_block("Views", views_val, muted=views_muted)
    )
    return (
        f'<a class="archive-card" href="/{slug}.html" aria-label="{full_label}">'
        f'<div class="archive-card-head">'
        f"{archive_card_title_html(ed)}"
        f'<span class="archive-card-read">Read<span class="arr" aria-hidden="true">→</span></span>'
        f"</div>"
        f'<div class="archive-stat-grid">{stats}</div>'
        f"{archive_chart_panel(ed)}"
        f"</a>"
    )


def head_common(title, description, nav, body, wrap_class="wrap"):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0f1012">
<script src="https://cdn.databuddy.cc/databuddy.js" data-client-id="d2f227a9-4c59-4917-b672-37f4eb3d81f9" data-track-outgoing-links="true" data-track-interactions="false" crossorigin="anonymous" async></script>
<meta name="color-scheme" content="dark">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<link rel="icon" href="/brand/favicon.ico?v=2" sizes="16x16 32x32 48x48">
<link rel="icon" type="image/png" sizes="16x16" href="/brand/favicon-16.png?v=2">
<link rel="icon" type="image/png" sizes="32x32" href="/brand/favicon-32.png?v=2">
<link rel="icon" type="image/png" sizes="48x48" href="/brand/favicon-48.png?v=2">
<link rel="icon" type="image/png" sizes="192x192" href="/brand/favicon-192.png?v=2">
<link rel="icon" type="image/png" sizes="512x512" href="/brand/favicon-512.png?v=2">
<link rel="apple-touch-icon" sizes="180x180" href="/brand/apple-touch-icon-180.png?v=2">
<link rel="manifest" href="/site.webmanifest?v=2">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<style>{CSS}</style>
</head>
<body>
<header class="masthead">
<div class="bar">
<a class="brand" href="/" aria-label="Loot's Gaming Roundup, home"><img class="logo" src="brand/logo-mascot-256.png" alt="Loot" width="56" height="56"><h1>Loot's Gaming Roundup</h1></a>
<nav class="jump" aria-label="Sections">{nav}</nav>
</div>
</header>
<div class="{wrap_class}" id="top">
{body}
<footer><div class="sign"><a class="full-list" href="/">Latest roundup</a> · Compiled by Loot · links open in a new tab</div></footer>
</div>
</body>
</html>"""


def iter_edition_tags(ed):
    for section in ("your_games", "industry"):
        for story in ed.get(section) or []:
            for tag in story.get("tags") or []:
                t = tag.strip()
                if t:
                    yield t
    for release in ed.get("releases") or []:
        for tag in release.get("tags") or []:
            t = tag.strip()
            if t:
                yield t


def collect_tag_counts(editions):
    """Occurrences of each tag on stories and releases across all editions."""
    counts = {}
    for ed in editions:
        for t in iter_edition_tags(ed):
            counts[t] = counts.get(t, 0) + 1
    return counts


def collect_tag_usage_by_edition(editions):
    """Tag occurrences per edition, sorted by edition date."""
    series = []
    for ed in sorted(editions, key=lambda d: d["date"]):
        series.append((ed["date"], sum(1 for _ in iter_edition_tags(ed))))
    return series


def edition_short_label(iso_date):
    d = datetime.strptime(iso_date, "%Y-%m-%d")
    return d.strftime("%d %b")


def badges_usage_chart(series):
    """Line chart of tag occurrences per daily edition."""
    chart_w, chart_h = 560, 132
    pad_l, pad_r, pad_t, pad_b = 40, 14, 14, 30
    if not series:
        return (
            '<div class="badges-trend-panel">'
            '<p class="archive-chart-empty">No badge data yet</p></div>'
        )
    vals = [c for _, c in series]
    mx = max(vals) if vals else 1
    n = len(series)
    iw = chart_w - pad_l - pad_r
    ih = chart_h - pad_t - pad_b
    xs, ys = [], []
    for i, val in enumerate(vals):
        x = pad_l + (iw * i / (n - 1) if n > 1 else iw / 2)
        if mx == 0:
            y = pad_t + ih
        else:
            y = pad_t + ih - (val / mx) * ih
        xs.append(x)
        ys.append(y)
    line = f"M{xs[0]:.2f},{ys[0]:.2f}"
    for k in range(1, len(xs)):
        line += f" L{xs[k]:.2f},{ys[k]:.2f}"
    base = pad_t + ih
    area = f"{line} L{xs[-1]:.2f},{base:.2f} L{xs[0]:.2f},{base:.2f} Z"
    grad_id = "badges-trend-grad"
    dots = []
    for i, ((iso, val), x, y) in enumerate(zip(series, xs, ys)):
        tip = escape(f"{edition_short_label(iso)}: {val} badge uses")
        dots.append(
            f'<circle class="badges-trend-dot" cx="{x:.2f}" cy="{y:.2f}" r="3.5">'
            f"<title>{tip}</title></circle>"
        )
    y_max_y = pad_t
    y_zero_y = pad_t + ih
    y_max_lbl = escape(str(mx))
    x_first = escape(edition_short_label(series[0][0]))
    x_last = escape(edition_short_label(series[-1][0]))
    x_first_x = xs[0]
    x_last_x = xs[-1]
    aria = escape(
        f"Badge uses per edition from {series[0][0]} to {series[-1][0]}. "
        f"Peak day: {mx} uses."
    )
    first_date, last_date = series[0][0], series[-1][0]
    range_lbl = escape(f"{edition_short_label(first_date)} – {edition_short_label(last_date)}")
    svg = (
        f'<svg viewBox="0 0 {chart_w} {chart_h}" preserveAspectRatio="none" '
        f'role="img" aria-label="{aria}">'
        f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop class="archive-chart-stop-top" offset="0%"/>'
        f'<stop class="archive-chart-stop-bottom" offset="100%"/>'
        f"</linearGradient></defs>"
        f'<text class="badges-trend-axis" x="{pad_l - 6}" y="{y_max_y + 4}" text-anchor="end">{y_max_lbl}</text>'
        f'<text class="badges-trend-axis" x="{pad_l - 6}" y="{y_zero_y + 4}" text-anchor="end">0</text>'
        f'<text class="badges-trend-axis" x="{x_first_x:.2f}" y="{chart_h - 6}" text-anchor="start">{x_first}</text>'
        f'<text class="badges-trend-axis" x="{x_last_x:.2f}" y="{chart_h - 6}" text-anchor="end">{x_last}</text>'
        f'<path class="badges-trend-fill" fill="url(#{grad_id})" d="{area}"/>'
        f'<path class="badges-trend-line" d="{line}"/>'
        f'{"".join(dots)}'
        f"</svg>"
    )
    return (
        f'<div class="badges-trend-panel">'
        f'<div class="badges-trend-head">'
        f'<span class="badges-trend-title">Uses per edition</span>'
        f'<span class="badges-trend-range">{range_lbl}</span></div>'
        f'<div class="badges-trend-chart">{svg}</div></div>'
    )


def render_badges(editions):
    counts = collect_tag_counts(editions)
    ordered = sorted(counts.items(), key=lambda x: (-x[1], x[0].lower()))
    usage_series = collect_tag_usage_by_edition(editions)
    total_uses = sum(c for _, c in usage_series)
    n_distinct = len(ordered)
    n_editions = len(editions)
    edition_word = "edition" if n_editions == 1 else "editions"
    items = []
    for tag, count in ordered:
        label = escape(f"{count} appearances")
        items.append(
            f'<li class="badge-item">{chip(tag)}'
            f'<span class="badge-count" aria-label="{label}">{fmt_views(count)}</span></li>'
        )
    kpi = (
        '<div class="badges-summary">'
        '<div class="badges-kpi-panel">'
        '<div class="badges-kpi-hero">'
        f'<span class="badges-kpi-hero-label">Total badge uses</span>'
        f'<span class="badges-kpi-hero-value">{fmt_views(total_uses)}</span>'
        "</div>"
        '<div class="badges-kpi-row">'
        f"{archive_stat_block('Distinct tags', str(n_distinct))}"
        f"{archive_stat_block('Editions', str(n_editions))}"
        "</div></div>"
        f"{badges_usage_chart(usage_series)}"
        "</div>"
    )
    nav = (
        '<a href="/">Latest</a>'
        '<a href="/archive.html">Archive</a>'
        '<a href="/badges.html" aria-current="true">Badges</a>'
    )
    body = (
        '<div class="intro"><div class="kicker"><span class="dot"></span>Badges</div>'
        f'<div class="date">Platforms and games tagged across every daily roundup</div></div>'
        f"{kpi}"
        f'<section id="badges"><h2>All badges<span class="count">sorted by frequency</span></h2>'
        f'<ul class="badges-list">{"".join(items)}</ul></section>'
    )
    return head_common(
        "Loot's Gaming Roundup · Badges",
        "Every platform and game tag used across Loot's daily gaming roundups.",
        nav,
        body,
        wrap_class="wrap wrap--badges",
    )


def render_archive(editions):
    ordered = sorted(editions, key=lambda d: d["date"], reverse=True)
    by_year = {}
    for ed in ordered:
        by_year.setdefault(ed["date"][:4], []).append(ed)
    year_sections = []
    for year in sorted(by_year.keys(), reverse=True):
        year_eds = by_year[year]
        sec_id = "archive" if len(by_year) == 1 else f"archive-{year}"
        sec_cls = "archive-year-section" if len(by_year) > 1 else ""
        cls_attr = f' class="{sec_cls}"' if sec_cls else ""
        year_sections.append(
            f'<section id="{sec_id}"{cls_attr}>'
            f'<h2>Past roundups - {year}<span class="count">{len(year_eds)} editions</span></h2>'
            f'<div class="archive-grid">{"".join(archive_card(ed) for ed in year_eds)}</div>'
            f"</section>"
        )
    nav = (
        '<a href="/">Latest</a>'
        '<a href="/archive.html" aria-current="true">Archive</a>'
        '<a href="/badges.html">Badges</a>'
    )
    body = (
        '<div class="intro"><div class="kicker"><span class="dot"></span>Archive</div>'
        '<div class="date">Every past edition, newest first</div></div>'
        f'{"".join(year_sections)}')
    return head_common(
        "Loot's Gaming Roundup · Archive",
        "Every daily gaming roundup, newest first.",
        nav,
        body,
        wrap_class="wrap wrap--archive",
    )


def render_sitemap(editions):
    urls = [f"{SITE_URL}/", f"{SITE_URL}/archive.html", f"{SITE_URL}/badges.html"]
    for ed in sorted(editions, key=lambda d: d["date"]):
        urls.append(f'{SITE_URL}/{ed["date"]}.html')
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(loc)}</loc>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def write_site_extras(root, editions, latest_html=None, update_index=False):
    archive_path = os.path.join(root, "archive.html")
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(render_archive(editions))
    print("wrote", archive_path)
    badges_path = os.path.join(root, "badges.html")
    with open(badges_path, "w", encoding="utf-8") as f:
        f.write(render_badges(editions))
    print("wrote", badges_path)
    sitemap_path = os.path.join(root, "sitemap.xml")
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write(render_sitemap(editions))
    print("wrote", sitemap_path)
    if update_index and latest_html:
        idx = os.path.join(root, "index.html")
        shutil.copyfile(latest_html, idx)
        print("wrote", idx)


def build_edition(root, data, output=None, no_index=False):
    out = output or os.path.join(root, f'{data["date"]}.html')
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(data))
    print("wrote", out)
    return out


def build_all(root, *, refresh_views=False, backfill_views=False):
    sync_views(root, refresh=refresh_views, backfill=backfill_views)
    records = load_edition_records(root)
    if not records:
        print("no edition JSON files found", file=sys.stderr)
        sys.exit(1)
    latest_path = None
    for rec in records:
        latest_path = build_edition(root, rec["data"])
    editions = load_editions(root)
    write_site_extras(root, editions, latest_html=latest_path, update_index=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json_file", nargs="?")
    ap.add_argument(
        "--all",
        action="store_true",
        help="rebuild all editions, index, archive, badges, and sitemap",
    )
    ap.add_argument(
        "--backfill-views",
        action="store_true",
        help="fetch views snapshots for all editions (respects lock unless combined with --refresh-views)",
    )
    ap.add_argument(
        "--refresh-views",
        action="store_true",
        help="refetch views even when a closed edition already has a snapshot",
    )
    ap.add_argument("-o", "--output")
    ap.add_argument("--no-index", action="store_true")
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    if a.backfill_views and not a.all:
        updated = sync_views(here, refresh=a.refresh_views, backfill=True)
        records = load_edition_records(here)
        latest_path = None
        for rec in records:
            latest_path = build_edition(here, rec["data"])
        write_site_extras(
            here, load_editions(here), latest_html=latest_path, update_index=True
        )
        if updated:
            print("backfilled views for:", ", ".join(updated))
        return
    if a.all:
        build_all(here, refresh_views=a.refresh_views, backfill_views=a.backfill_views)
        return
    if not a.json_file:
        ap.error("json_file is required unless --all or --backfill-views is set")
    json_path = a.json_file if os.path.isabs(a.json_file) else os.path.join(here, a.json_file)
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    if not a.output:
        finalize_previous_edition(
            here, data["date"], refresh=a.refresh_views, backfill=a.backfill_views
        )
        sync_views(
            here,
            refresh=a.refresh_views,
            backfill=a.backfill_views,
            only_dates=[data["date"]],
        )
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    out = build_edition(here, data, a.output, a.no_index)
    if not a.output:
        editions = load_editions(here)
        latest = max(editions, key=lambda d: d["date"])["date"]
        write_site_extras(here, editions,
                          latest_html=out,
                          update_index=not a.no_index and data["date"] == latest)

if __name__ == "__main__":
    main()
