# 🎁 Token Wrapped

> One sentence → your **Claude Code** token-usage stats for any date range, as a
> shareable "Wrapped" poster *and* a multi-panel dashboard, in the style you pick.

A [Claude Code](https://claude.com/claude-code) **skill** (also runnable as plain CLI
scripts). It reads your local usage logs via [`ccusage`](https://github.com/ryoppippi/ccusage),
merges multiple machines, and renders:

- **`token_wrapped.png`** — a portrait poster built for sharing (Spotify-Wrapped vibe)
- **`token_dashboard.png`** — a landscape analytics chart (daily tokens, cumulative cost, per-model breakdown)

Both also export `.pdf` (vector).

<p align="center">
  <img src="samples/poster_cyber_purple.png" width="32%" alt="cyber_purple poster"/>
  <img src="samples/poster_neon_night.png" width="32%" alt="neon_night poster"/>
  <img src="samples/poster_cyber_green.png" width="32%" alt="cyber_green poster"/>
</p>
<p align="center"><img src="samples/dashboard.png" width="97%" alt="dashboard"/></p>
<p align="center"><sub>↑ rendered from synthetic demo data (<code>samples/</code>), not a real account</sub></p>

---

## Quick start (as a skill)

Copy this folder into `~/.claude/skills/token-wrapped/`, then just ask Claude Code:

```
/token-wrapped last 7 days, cyber green style
/token-wrapped this month --no-fun
/token-wrapped all time, dark background with teal accents
```

Claude resolves the date range, picks the flags, runs the scripts, and shows you the images.

## Quick start (as CLI)

```bash
pip install matplotlib          # ccusage must also be on PATH (npx works too)
SKILL=~/.claude/skills/token-wrapped

# one-shot wrapper (collect + render):
python $SKILL/wrapped.py --start 2026-06-01 --end 2026-06-24 \
                         --lang en --style cyber_purple --out-dir .

# …or the two steps explicitly:
python $SKILL/collect.py --start 2026-06-01 --end 2026-06-24 --out merged_usage.json
python $SKILL/render.py  --data merged_usage.json --lang en --style cyber_purple --out-dir .
```

---

## Features

| | |
|---|---|
| **Any date range** | `--start/--end`, or omit for all-time |
| **Multi-machine** | drop other machines' `ccusage` JSON into `~/.claude/ccusage_extra/`; auto-merged per day & per model |
| **Bilingual** | `--lang en` (default) or `--lang zh` — copy and number units adapt (B/M vs 亿) |
| **5 style presets** | `cyber_purple` · `neon_night` · `blue_gold` · `cyber_green` · `minimal_white` |
| **Custom colors** | `--style custom --bg "#a,#b,#c" --accent "#d" --bars "#e" --text light\|dark` |
| **Pro mode** | `--no-fun` drops the playful comparisons; `--coffee-price` tunes the latte metric |
| **Two outputs** | `--what both\|poster\|dashboard` |

### Styles

`cyber_purple` (default), `neon_night`, `blue_gold`, `cyber_green`, `minimal_white`.
Light backgrounds use dark text automatically.

---

## How it works

```
collect.py   ccusage daily --json  +  ~/.claude/ccusage_extra/*.json
             → sum per day & per model → clip to range → merged_usage.json
render.py    merged_usage.json → token_wrapped.{png,pdf} + token_dashboard.{png,pdf}
```

`merged_usage.json` schema: `{ range, sources, daily[], totals }`. `collect.py` accepts
both `ccusage` entry shapes (`date`-keyed and `period`-keyed).

### Multi-machine

```bash
# on each other machine:
ccusage daily --json > laptop.json
# then copy laptop.json into ~/.claude/ccusage_extra/ on your main box
```

Overlapping dates are **summed** (one person across several machines).

---

## Project layout

```
token-wrapped/
├── SKILL.md            # Claude Code skill manifest + instructions
├── collect.py          # ccusage + multi-machine merge → merged_usage.json
├── render.py           # merged_usage.json → poster + dashboard (i18n, styles)
├── wrapped.py          # one-shot wrapper (collect + render)
├── samples/            # synthetic demo data + example images
│   ├── gen_sample.py   #   regenerate the demo data
│   └── *.png
├── README.md  LICENSE  requirements.txt
```

Regenerate the demo images:

```bash
python samples/gen_sample.py
python render.py --data samples/sample_usage.json --style cyber_purple --out-dir samples
```

## Requirements

- Python 3.8+ with `matplotlib`
- [`ccusage`](https://github.com/ryoppippi/ccusage) on `PATH` (or `npx ccusage@latest`)
- For `--lang zh`: a CJK font (e.g. `fonts-noto-cjk`)

## Notes

- matplotlib can't render color-emoji; the poster uses monochrome symbols only.
- Fun-fact constants (`WORDS_PER_TOKEN`, `WORDS_PER_NOVEL`, `READING_WPM`) live at the
  top of `render.py` — they are rough, for fun, and easy to tweak.

## License

[MIT](./LICENSE)
