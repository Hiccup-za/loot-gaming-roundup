#!/usr/bin/env python3
"""Render Loot's Gaming Roundup from a JSON file into a self-contained HTML page.

Usage:
    python3 build.py 2026-10-11.json            # writes 2026-10-11.html + index.html
    python3 build.py --all                      # rebuild every edition, index, archive, sitemap
    python3 build.py data.json -o out.html      # custom output, no index copy
    python3 build.py data.json --no-index       # skip updating index.html
"""
import argparse, json, os, re, shutil, sys
from html import escape

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
@media(min-width:720px){
  .bar{flex-direction:row;align-items:center;justify-content:space-between;gap:20px;padding-top:14px;padding-bottom:14px}
  .brand{gap:14px}
  .brand .logo{width:56px;height:56px}
  h1{font-size:24px}
  nav.jump{margin:0;padding:0;overflow:visible}
  nav.jump a{min-height:34px;font-size:14px}
}

/* Intro line under the bar (scrolls away) */
.intro{display:flex;flex-wrap:wrap;align-items:center;gap:6px 16px}
.kicker{display:inline-flex;align-items:center;gap:8px;font:600 12px/1.2 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.kicker .dot{width:6px;height:6px;border-radius:50%;background:var(--accent)}
.date{font:500 13px/1.4 var(--mono);color:var(--text-3)}

/* Sections: editorial breaks, no boxes */
section{margin-top:56px;scroll-margin-top:calc(var(--bar-h) + env(safe-area-inset-top) + 12px)}
.intro+.layout>:first-child>section:first-child{margin-top:28px}
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

/* Edition readership chart (client-loaded) */
.views{margin-top:36px;padding-top:14px;border-top:2px solid var(--text)}
.views h2{font-size:20px;margin-bottom:12px}
.views-stat{margin:0 0 10px;color:var(--text-2);font-size:15px}
.views-stat strong{color:var(--accent);font-weight:600}
.views-note{margin:0 0 12px;color:var(--text-3);font-size:13.5px;line-height:1.5;max-width:38em}
.views-unavail{margin:0;color:var(--text-3);font:500 13px/1.4 var(--mono)}
.views-figure{margin:0}
.views-svg{display:block;width:100%;height:auto;max-height:220px;color:var(--accent)}
.views-caption{margin-top:8px;color:var(--text-3);font:500 11px/1.4 var(--mono)}
.views-axis{stroke:var(--border);stroke-width:1}
.views-grid{stroke:var(--border);stroke-width:1;opacity:.55}
.views-line{fill:none;stroke:var(--accent);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.views-area{fill:var(--accent-tint)}
.views-dot{fill:var(--accent)}
.views-label{fill:var(--text-3);font:500 10px/1 var(--mono)}
@media(min-width:1000px){.views{margin-top:28px}}

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
  .side h2{font-size:20px}
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
  h2{font-size:26px}
  .side h2{font-size:21px}
  .card{padding:32px 0 34px}
  .card h3{font-size:28px}
  .card p{font-size:17.5px;line-height:1.7}
  .side .rel-body h3{font-size:16px}
}
"""

VIEWS_SCRIPT = r"""
(function(){
  var root=document.getElementById("edition-views");
  if(!root)return;
  var edition=root.getAttribute("data-edition-date");
  if(!edition)return;
  var statEl=document.getElementById("views-stat");
  var noteEl=document.getElementById("views-note");
  var unavailEl=document.getElementById("views-unavail");
  var figEl=document.getElementById("views-figure");
  var svgEl=document.getElementById("views-svg");
  var capEl=document.getElementById("views-caption");
  function showUnavailable(){
    root.hidden=false;
    if(unavailEl)unavailEl.hidden=false;
    if(figEl)figEl.hidden=true;
    if(statEl)statEl.textContent="";
    if(noteEl)noteEl.hidden=true;
  }
  function fmt(n){return n.toLocaleString("en-ZA");}
  function shortDate(iso){
    var p=iso.split("-");
    return p[2]+" "+["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][+p[1]-1];
  }
  function drawChart(tracked){
    if(!tracked.length||!svgEl)return;
    var w=640,h=180,pad={t:12,r:12,b:28,l:36};
    var iw=w-pad.l-pad.r,ih=h-pad.t-pad.b;
    var maxPv=0;
    for(var i=0;i<tracked.length;i++)if(tracked[i].pageviews>maxPv)maxPv=tracked[i].pageviews;
    if(maxPv<1)maxPv=1;
    var pts=[];
    for(var j=0;j<tracked.length;j++){
      var x=pad.l+(tracked.length===1?iw/2:(iw*j/(tracked.length-1)));
      var y=pad.t+ih-(tracked[j].pageviews/maxPv)*ih;
      pts.push({x:x,y:y,pv:tracked[j].pageviews,d:tracked[j].date});
    }
    var area="M"+pts[0].x+" "+(pad.t+ih)+" L"+pts[0].x+" "+pts[0].y;
    var line="M"+pts[0].x+" "+pts[0].y;
    for(var k=1;k<pts.length;k++){
      line+=" L"+pts[k].x+" "+pts[k].y;
      area+=" L"+pts[k].x+" "+pts[k].y;
    }
    area+=" L"+pts[pts.length-1].x+" "+(pad.t+ih)+" Z";
    var grid="";
    for(var g=0;g<=3;g++){
      var gy=pad.t+(ih*g/3);
      grid+='<line class="views-grid" x1="'+pad.l+'" y1="'+gy+'" x2="'+(w-pad.r)+'" y2="'+gy+'"/>';
    }
    var dots="",labels="";
    var labelEvery=Math.max(1,Math.ceil(tracked.length/6));
    for(var m=0;m<pts.length;m++){
      dots+='<circle class="views-dot" cx="'+pts[m].x+'" cy="'+pts[m].y+'" r="3"/>';
      if(m===0||m===pts.length-1||m%labelEvery===0){
        labels+='<text class="views-label" x="'+pts[m].x+'" y="'+(h-6)+'" text-anchor="middle">'+shortDate(pts[m].d)+'</text>';
      }
    }
    svgEl.setAttribute("viewBox","0 0 "+w+" "+h);
    svgEl.innerHTML='<line class="views-axis" x1="'+pad.l+'" y1="'+(pad.t+ih)+'" x2="'+(w-pad.r)+'" y2="'+(pad.t+ih)+'"/>'+
      grid+'<path class="views-area" d="'+area+'"/><path class="views-line" d="'+line+'"/>'+dots+labels;
    if(capEl)capEl.textContent="Daily page views (tracked paths combined)";
  }
  fetch("/api/views?date="+encodeURIComponent(edition),{credentials:"same-origin"})
    .then(function(r){if(!r.ok)throw 0;return r.json();})
    .then(function(data){
      if(!data||data.unavailable)throw 0;
      root.hidden=false;
      if(unavailEl)unavailEl.hidden=true;
      var tracked=(data.series||[]).filter(function(p){return p.tracked;});
      if(data.trackingNote&&noteEl){noteEl.textContent=data.trackingNote;noteEl.hidden=false;}
      var parts=[];
      if(data.launchDayViews!=null){
        parts.push("<strong>"+fmt(data.launchDayViews)+"</strong> views on launch day");
      }
      if(typeof data.totalViews==="number"){
        parts.push("<strong>"+fmt(data.totalViews)+"</strong> total since tracking");
      }
      if(statEl)statEl.innerHTML=parts.join(" · ");
      if(tracked.length&&figEl){
        figEl.hidden=false;
        drawChart(tracked);
      }else if(figEl)figEl.hidden=true;
    })
    .catch(function(){showUnavailable();});
})();
"""

def views_section(edition_date):
    d = escape(edition_date)
    return (
        f'<section class="views" id="edition-views" data-edition-date="{d}" hidden>'
        f'<h2>Daily views</h2>'
        f'<p class="views-stat" id="views-stat"></p>'
        f'<p class="views-note" id="views-note" hidden></p>'
        f'<p class="views-unavail" id="views-unavail" hidden>Views unavailable</p>'
        f'<figure class="views-figure" id="views-figure" hidden>'
        f'<svg class="views-svg" id="views-svg" role="img" aria-labelledby="views-caption"></svg>'
        f'<figcaption class="views-caption" id="views-caption"></figcaption>'
        f'</figure></section>'
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
        nav.append('<a href="#out-this-week">Out this week</a>')
        full = (f'<a class="full-list" href="{escape(data["releases_link"], quote=True)}" target="_blank" rel="noopener noreferrer">'
                f'See the full release list ↗</a>') if data.get("releases_link") else ""
        side.append(f'<section id="out-this-week"><h2>Out this week</h2>'
                        f'<ul class="releases">{"".join(release_row(r) for r in releases)}</ul>{full}</section>')
    nav.append('<a href="/archive.html">Archive</a>')
    note = (f'<div class="note"><span class="ico" aria-hidden="true">📌</span><div>{escape(data["footer_note"])}</div></div>'
            if data.get("footer_note") else "")
    date_label = escape(data.get("date_label", data.get("date", "")))
    edition_date = data.get("date", "")
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
<div class="intro"><div class="kicker"><span class="dot"></span>Daily gaming news</div><div class="date">{date_label}</div></div>
{views_section(edition_date)}
{layout}
<footer>{note}<div class="sign"><a class="full-list" href="/archive.html">Past roundups</a> · Compiled by Loot · links open in a new tab</div></footer>
</div>
<script>{VIEWS_SCRIPT}</script>
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
    editions = []
    for path in list_edition_jsons(root):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        editions.append(data)
    editions.sort(key=lambda d: d["date"], reverse=True)
    return editions


def head_common(title, description, nav, body):
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
<div class="wrap" id="top">
{body}
<footer><div class="sign"><a class="full-list" href="/">Latest roundup</a> · Compiled by Loot · links open in a new tab</div></footer>
</div>
</body>
</html>"""


def render_archive(editions):
    items = []
    for ed in editions:
        slug = escape(ed["date"])
        label = escape(ed.get("date_label", ed["date"]))
        items.append(
            f'<li class="release"><div class="rel-body">'
            f'<h3><a class="full-list" href="/{slug}.html">{label}</a></h3>'
            f'</div></li>')
    nav = '<a href="/">Latest</a>'
    body = (
        '<div class="intro"><div class="kicker"><span class="dot"></span>Archive</div>'
        '<div class="date">Every past edition</div></div>'
        f'<section id="archive"><h2>Past roundups<span class="count">{len(editions)} editions</span></h2>'
        f'<ul class="releases">{"".join(items)}</ul></section>')
    return head_common("Loot's Gaming Roundup · Archive",
                       "Every daily gaming roundup, newest first.",
                       nav, body)


def render_sitemap(editions):
    urls = [f"{SITE_URL}/", f"{SITE_URL}/archive.html"]
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


def build_all(root):
    editions = load_editions(root)
    if not editions:
        print("no edition JSON files found", file=sys.stderr)
        sys.exit(1)
    latest_path = None
    for data in sorted(editions, key=lambda d: d["date"]):
        latest_path = build_edition(root, data)
    write_site_extras(root, editions, latest_html=latest_path, update_index=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json_file", nargs="?")
    ap.add_argument("--all", action="store_true", help="rebuild all editions, index, archive, and sitemap")
    ap.add_argument("-o", "--output")
    ap.add_argument("--no-index", action="store_true")
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    if a.all:
        build_all(here)
        return
    if not a.json_file:
        ap.error("json_file is required unless --all is set")
    with open(a.json_file, encoding="utf-8") as f:
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
