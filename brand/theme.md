# Loot's Gaming Roundup: clean modern news theme (dark mode)

This is a staging copy waiting for Christopher's approval. Nothing has been copied into `/workspace/gaming-roundup/brand/` yet. Previous versions: `v2-cards/` (the dark theme with two-column card boxes) and `retro-rejected/`.

**v3 layout:** a single-column news feed with no boxes. Stories, releases and the pinned note are all unboxed and separated by hairlines and spacing.

`theme.css` replaces the `CSS` string in `build.py` as-is. It uses the same class names: `header`, `.kicker`, `h1`, `.date`, `nav.jump`, `h2 .count`, `.grid`, `.card`, `.chip-*`, `.sources`, `a.src`, `.release`, `.rel-date`, `.note` and `.sign`. The direction is a modern games and tech publication in dark mode:
- a neutral near-black page with a single readable column, no card boxes, and hairline dividers;
- generous spacing and strong type hierarchy;
- a single brand accent.

## Palette
The page is mostly neutral greys. The one accent is the gold of Loot's crown, lifted from the mascot (the crown's median gold is `#c68727`) so it reads on dark. The accent is used only for the kicker, links, the pinned-note rule and the focus ring. Platform colours appear only in platform chips, where they carry meaning.

Contrast ratios are WCAG 2.x against `#17191c`. Text now sits on the page `#0f1012`, where every ratio is slightly higher (for example `--text-3` is 5.9:1).

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `--bg` | `#0f1012` | Page background | n/a |
| `--surface` | `#17191c` | Nav pills only (no longer used for story boxes) | n/a |
| `--surface-2` | `#1e2125` | Spare raised tone, currently unused | n/a |
| `--border` | `#2a2d32` | Hairline dividers between stories and releases, and the footer rule | decorative |
| `--border-strong` | `#3a3e45` | Hover borders and game-tag outline | decorative |
| `--text` | `#ededef` | Headlines, titles and the section rule | 15.1:1 |
| `--text-2` | `#b3b7bf` | Body copy | 8.8:1 |
| `--text-3` | `#8b9099` | Meta: date, counts, source label, sign-off | 5.5:1 (5.9:1 on `--bg`) |
| `--accent` | `#f0b445` | Crown gold: kicker, the full-list link, source-link hover, the pinned-note rule and the focus ring | 9.5:1 |
| `--accent-hover` | `#ffc85e` | Link hover | 11.5:1 |

### Platform chips
Platform chips are small flat tags: a coloured dot and coloured text on a 12% tint of the same colour, with a 26% tint border. The four hues (blue, red, green, grey) are far apart. The dot and the label text also mean the chips never rely on colour alone.

| Class | Tags | Colour | Text on its tint |
|---|---|---|---|
| `.chip-ps` | PS5, PlayStation, PS Plus | `#6aa5ff` blue | 5.8:1 |
| `.chip-nin` | Switch, Switch 2, Nintendo, Pokémon | `#ff6f6f` red | 5.5:1 |
| `.chip-xbox` | Xbox | `#5ad18a` green | 7.3:1 |
| `.chip-pc` | PC | `#b9bfca` cool grey | 7.5:1 |
| `.chip-game` | Any game or franchise tag | `#b3b7bf` text, outline only, no dot | 8.8:1 |

The chip tints use `color-mix()`, which works in all current browsers (Safari 16.2+, Chrome 111+, Firefox 113+).

## Fonts (free Google Fonts)
- **Inter Tight** (600 to 800) for the masthead, section headings, story titles and release titles. It is tight and confident; the masthead uses 800 with −0.03em tracking.
- **Inter** (400 to 600, optical sizing) for body copy, chips, nav and links.
- **JetBrains Mono** (500) only for small meta: the date, story counts, the "Source" label, release months and the sign-off.
- The import is the first rule in `theme.css`:
  `@import url("https://fonts.googleapis.com/css2?family=Inter+Tight:wght@600;700;800&family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600&family=JetBrains+Mono:wght@500&display=swap");`
- This adds the site's only external request. The README currently says the site uses system fonts. Fallbacks are `system-ui`, then `-apple-system`, Segoe UI and Roboto, so the page still looks right if the fonts fail to load. To stay fully self-contained, self-host the variable TTFs; copies are in `work/fonts/`, under the OFL licence.

## Component notes
- **Column.** `.wrap` is capped at 760px and centred. That gives a body measure of about 75 to 85 characters at 16.5px. The header, section headings, stories and footer all share the same left edge.
- **Header.** It is unchanged apart from losing its bottom hairline, because the first section rule now does that job.
  - Optional logo: add `<img class="logo" src="brand/logo-256.png" alt="Loot">` as the first child of `<header>`. It shows at 84px (60px on phones), beside the kicker and title. The date and nav sit full width underneath.
  - The kicker is gold small caps with a dot.
  - `h1` is Inter Tight 800 at `clamp(30px, 6.4vw, 56px)`.
  - The date is mono `--text-3`.
  - The jump nav is quiet pill links.
- **Section breaks (`h2`).** These are editorial breaks, not boxes: a 2px rule in `--text` across the column, then the heading in Inter Tight 700 at 24px, with `.count` as right-aligned mono meta. There is 56px of space above each section (44px for the first).
- **Stories (`.card`).** There is no background, border or radius. Each story has 28 to 30px of vertical padding, and stories are divided by a 1px `--border` hairline (`.card + .card`).
  - Order: tags, then the headline (Inter Tight 700, `clamp(21px, 3.4vw, 25px)`, −0.018em, balanced wrapping), then the body (Inter, 16.5px, line height 1.68, `--text-2`).
  - `.grid` is now a plain block, giving one column at every width.
- **Sources.** A quiet meta row 14px under the body: a mono "SOURCE" label, then the source names in `--text-2` Inter 500 at 14px with a dim ↗. They turn gold on hover. Each has at least a 32px tap height. There is no rule above them.
- **Chips.** Unchanged: small flat tags with a dot and coloured text on a faint tint.
- **Out this week.** An unboxed list with hairline rows and 18px of vertical padding. The date sits in a 64px left column: the day in Inter Tight 700 at 20px, which fits "Today" as well as numbers, and the month in mono underneath. Titles are Inter Tight 600 at 18px, notes are `--text-3`, and tags sit below. "See the full release list ↗" is the gold link under the list.
- **Footer.** A hairline rule above. The pinned `.note` is unboxed: a 2px gold rule on the left with `--text-2` copy and the 📌 icon. `.sign` is centred mono meta.
- **Mobile.** The same single column with 18px side padding. Headlines step down to 21px, the logo drops to 60px and the masthead wraps to two lines.
- **Markup.** No changes are needed beyond the optional logo `<img>` and setting `theme-color` to `#0f1012`.

## Head tags
```html
<meta name="theme-color" content="#0f1012">
<meta name="color-scheme" content="dark">
<link rel="icon" href="/brand/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/brand/favicon-32.png">
<link rel="apple-touch-icon" href="/brand/apple-touch-icon-180.png">
<meta property="og:title" content="Loot's Gaming Roundup">
<meta property="og:description" content="Daily gaming news: your games, industry news and what's out this week.">
<meta property="og:image" content="https://loot-gaming-roundup.vercel.app/brand/og-1200x630.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
```

## Brand assets
- `logo-256.png` and `logo-512.png`: the mascot on a subtle charcoal disc (radial `#282c33` to `#181a1e`, with a `#3a3e46` ring). The crown and lid break out above the disc. The disc stops the dark brown arms and outlines disappearing into the near-black page. Use this version on the site.
- `logo-mascot-256.png` and `logo-mascot-512.png`: a plain transparent cutout, for lighter or textured backgrounds.
- `favicon.ico` (16 + 32), `favicon-32.png` and `favicon-16.png`: a simplified chest face on a dark rounded tile (`#1d2025` with a `#3a3e46` edge).
- `apple-touch-icon-180.png`: the mascot on a solid charcoal radial square. iOS rounds the corners itself.
- `og-1200x630.png`: the share image.
