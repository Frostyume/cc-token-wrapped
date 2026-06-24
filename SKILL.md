---
name: token-wrapped
description: One sentence → Claude Code token-usage stats for any date range, plus a shareable "Wrapped" poster and a multi-panel dashboard in your chosen style. 一句话生成某时间段的 cc token 用量统计 + 自定义风格海报和图表。Use when the user wants to summarize/show off their cc token usage, generate a Wrapped poster or usage dashboard, or asks "how many tokens / how much did I spend".
---

# Token Wrapped

Turn one natural-language request (date range + style + language) into:
① usage numbers ② a portrait shareable poster ③ a landscape multi-panel dashboard.

Data comes from `ccusage` on this machine (it parses `~/.claude/projects/**/*.jsonl`)
and auto-merges any `*.json` dumps from other machines under `~/.claude/ccusage_extra/`.

## Steps

### 1. Parse the date range → start/end
Resolve `--start` / `--end` (`YYYY-MM-DD`) relative to **today**:
- "all / everything / so far" → pass neither (full range)
- "last 7 days / this week" → start = today-6, end = today
- "this month / June" → 1st → end of month (or today)
- "5-14 to 6-24" → explicit start/end
Use the current year when unspecified. Ask if genuinely ambiguous.

### 2. Pick language, style & size
- `--lang en|zh` (default `en`). Numbers and copy adapt (B/M vs 亿).
- Presets `--style`: `cyber_purple` (default) · `neon_night` · `blue_gold` ·
  `cyber_green` · `minimal_white` · `sunset` · `graphite` · `sakura`.
- `--size poster|story|square` (default `poster`): `poster` = portrait 9:12.5,
  `story` = 9:16 for Instagram/WeChat stories, `square` = 1:1 for feeds.
- A theme file: `--style NAME` also resolves `NAME.json` under
  `~/.claude/token-wrapped-themes/` or the skill's `themes/` dir
  (keys: `bg` list, `accent`, `bars`, `text`, optional `glows`).
- Free-form color description → `--style custom` and translate it to hex:
  `--bg "#bottom,#mid,#top" --accent "#c" --bars "#c" --text light|dark`
  (light backgrounds MUST use `--text dark`).
- `--font "Font Name"` forces a font family (useful for brand fonts / CJK).
- Fun comparisons (lattes / novels / reading-hours) are on by default; add `--no-fun`
  for a professional version. `--coffee-price 5.0` tunes the latte comparison.

### 3. Run the scripts
Use any Python that has `matplotlib` (install with `pip install matplotlib` if missing).
Put outputs wherever the user wants (e.g. their project's `results/` or the cwd).

```bash
SKILL="$HOME/.claude/skills/token-wrapped"
PY=python3   # any interpreter with matplotlib

$PY "$SKILL/collect.py" --start 2026-06-18 --end 2026-06-24 --out merged_usage.json
$PY "$SKILL/render.py"  --data merged_usage.json --lang en --style cyber_purple \
                        --size poster --out-dir .
```

- `collect.py` merges this machine + `--extra-dir`, clips to the range, writes
  `merged_usage.json` (`range/sources/daily/totals`) and prints a summary.
- `render.py --what both|poster|dashboard` writes `token_wrapped.png/.pdf` (poster)
  and/or `token_dashboard.png/.pdf` (dashboard).

### 4. Report back
Read the generated PNG to sanity-check (no glyph boxes / number ambiguity), then give
the user the headline numbers (total tokens / cost / days / model share) and the paths.

## Multi-machine merge
Ask the user to drop other machines' `ccusage daily --json > NAME.json` into
`~/.claude/ccusage_extra/`. This skill folds them in every run (summed per day, per
model). Overlapping dates are added together on purpose (one person, several machines).

## Gotchas
- matplotlib can't render color-emoji fonts; the poster uses mono symbols (☕◆▲⚡★✦) only.
- Chinese needs a CJK font; `render.py` auto-detects Noto Sans CJK etc. and warns +
  falls back to DejaVu (Chinese → boxes) if none — then suggest installing `fonts-noto-cjk`.
- For Chinese audiences the hero number is shown in 亿; don't use Billion as the headline
  (a reader may misread it as 亿 and be off by 10×).
