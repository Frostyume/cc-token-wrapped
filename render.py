#!/usr/bin/env python3
"""Render a shareable 'Token Wrapped' poster and/or a multi-panel dashboard
from a merged usage JSON produced by collect.py.

Usage:
  render.py --data merged_usage.json [--what both|poster|dashboard]
            [--lang en|zh] [--style NAME|custom] [--size poster|story|square]
            [--font "Font Name"] [--no-fun]
            [--title "..."] [--subtitle "..."] [--out-dir DIR]
            [--coffee-price 5.0]
            # custom style overrides (hex), used when --style custom:
            [--bg "#100C2E,#561C78,#C8326E"] [--accent "#FFD86B"]
            [--bars "#FFD86B"] [--text light|dark]

--style accepts a built-in preset, "custom" (+ hex overrides), or the name of a
theme file <name>.json under ~/.claude/token-wrapped-themes/ or this repo's themes/.

Built-in presets:
  cyber_purple neon_night blue_gold cyber_green minimal_white sunset graphite sakura
"""
import argparse
import json
import os
from collections import defaultdict
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.colors as mcolors
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter
import numpy as np

# ---- fun-fact constants (documented; tweak freely) -----------------------
WORDS_PER_TOKEN = 0.75       # rough English words per token
WORDS_PER_NOVEL = 100_000    # words in a typical novel
READING_WPM = 200            # average reading speed (words/min)

# ---- style presets -------------------------------------------------------
STYLES = {
    "cyber_purple": dict(bg=["#100C2E", "#561C78", "#C8326E"], accent="#FFD86B",
                         bars="#FFD86B", text="light",
                         glows=[("#FF5DA2", 0.18), ("#5D9BFF", 0.16), ("#FFD86B", 0.10)]),
    "neon_night":   dict(bg=["#070713", "#1A0F3C", "#2C0A4E"], accent="#00F0FF",
                         bars="#FF2EC4", text="light",
                         glows=[("#00F0FF", 0.16), ("#FF2EC4", 0.18), ("#7A5CFF", 0.12)]),
    "blue_gold":    dict(bg=["#0A1A2F", "#103A6B", "#1E5A9E"], accent="#FFCB47",
                         bars="#FFCB47", text="light",
                         glows=[("#FFCB47", 0.14), ("#5D9BFF", 0.16), ("#FFFFFF", 0.06)]),
    "cyber_green":  dict(bg=["#06160E", "#0C3A24", "#10663C"], accent="#6BFFB0",
                         bars="#6BFFB0", text="light",
                         glows=[("#6BFFB0", 0.16), ("#2EE6A6", 0.14), ("#D7FF6B", 0.08)]),
    "minimal_white":dict(bg=["#FFFFFF", "#F3F3F7", "#E9E9F0"], accent="#0F4D92",
                         bars="#0F4D92", text="dark",
                         glows=[("#0F4D92", 0.06), ("#42949E", 0.05), ("#FFD700", 0.05)]),
    "sunset":       dict(bg=["#2B0A3D", "#7A1E5B", "#E0653A"], accent="#FFD45E",
                         bars="#FF9E4A", text="light",
                         glows=[("#FF7E5F", 0.18), ("#FEB47B", 0.14), ("#C84B8E", 0.12)]),
    "graphite":     dict(bg=["#0D0F12", "#1A1E24", "#2A3038"], accent="#7FE7C4",
                         bars="#7FE7C4", text="light",
                         glows=[("#7FE7C4", 0.10), ("#5D9BFF", 0.08), ("#FFFFFF", 0.04)]),
    "sakura":       dict(bg=["#FFF1F4", "#FBE2EC", "#F6D4E4"], accent="#D6336C",
                         bars="#E64980", text="dark",
                         glows=[("#FF8FB1", 0.10), ("#FFC2D6", 0.10), ("#C8A2D8", 0.07)]),
}

THEME_DIRS = [os.path.expanduser("~/.claude/token-wrapped-themes"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")]

# ---- poster layout presets (axes-fraction anchors per aspect) ------------
LAYOUTS = {
    "poster": dict(figsize=(9, 12.5), hero_size=140,
                   tag=0.957, title=0.928, hero=0.808, unit=0.703, sub=0.660,
                   bars_y0=0.548, bars_h=0.098, rhythm=0.523,
                   models_hdr=0.482, models_y0=0.430, models_dy=0.050,
                   chips=0.232, fun=0.130, range=0.073, powered=0.043,
                   glows=[(0.82, 0.88), (0.15, 0.30), (0.5, 0.6)]),
    "story":  dict(figsize=(9, 16), hero_size=150,
                   tag=0.962, title=0.938, hero=0.838, unit=0.748, sub=0.710,
                   bars_y0=0.612, bars_h=0.090, rhythm=0.590,
                   models_hdr=0.548, models_y0=0.498, models_dy=0.048,
                   chips=0.318, fun=0.205, range=0.135, powered=0.095,
                   glows=[(0.82, 0.90), (0.15, 0.32), (0.5, 0.62)]),
    "square": dict(figsize=(10, 10), hero_size=110,
                   tag=0.955, title=0.917, hero=0.782, unit=0.655, sub=0.606,
                   bars_y0=0.498, bars_h=0.074, rhythm=0.470,
                   models_hdr=0.422, models_y0=0.372, models_dy=0.050,
                   chips=0.178, fun=0.090, range=0.050, powered=0.022,
                   glows=[(0.84, 0.86), (0.14, 0.28), (0.5, 0.58)]),
}

# ---- i18n ----------------------------------------------------------------
STR = {
    "en": {
        "tag": "✦  MY CLAUDE CODE WRAPPED  ✦",
        "title": "My Token Usage",
        "rhythm": "daily rhythm",
        "models": "TOP MODELS",
        "cost": "Total spent", "cost_fun": "Total spent  ·  ≈ {c} lattes",
        "peak": "Peak day ({d})", "avg": "Avg per day", "output": "output tokens",
        "fun_line": "★  ≈ {nv} novels  ·  {rd} of nonstop reading  ★",
        "read_h": "{v} hours", "read_d": "{v} days", "read_y": "{v} years",
        "sub": "{t}  ·  {d} {dw} with Claude",
        "powered": "Powered by Claude Code",
        "tag_min": "CLAUDE CODE · TOKEN REPORT", "min_top": "top model",
        "arch": {"marathon": "The Marathoner", "weekend": "The Weekend Warrior",
                 "sprinter": "The Sprinter", "steady": "The Steady Builder",
                 "explorer": "The Explorer"},
        "report": "TOKEN USAGE REPORT", "kpi_spent": "Total spent",
        "kpi_tokens": "Total tokens", "kpi_days": "Active days", "kpi_top": "Top model",
        "tbl_model": "Model", "tbl_cost": "Cost", "tbl_share": "Share",
        "biz_cum": "Cumulative spend", "prompt": "ccusage --wrapped",
        "t_total": "total", "t_spent": "spent", "t_days": "days", "t_top": "top",
        "t_cache": "cache", "t_out": "output", "you_are": "you are",
        "receipt": "TOKEN RECEIPT", "r_thanks": "THANK YOU FOR VIBE CODING",
        "r_item": "ITEM", "r_amt": "AMOUNT",
        "d_title": "My Token Usage", "d_daily": "tokens / day",
        "d_cumcost": "cumulative cost", "d_cost_model": "Daily cost by model",
        "d_share": "Cost share by model", "d_total": "total cost ($)",
        "d_tokday": "tokens / day", "d_costday": "cost / day ($)",
        "d_heat": "Activity (tokens / day)",
        "d_active": "active days", "d_streak": "longest streak",
        "d_busy": "busiest day", "d_avgday": "avg / day",
        "d_streak_u": "{v} days", "d_less": "Less", "d_more": "More",
        "wd": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "d_cap": ("Total {tk} tokens · ${c:,.0f} · {n} days "
                  "({s}→{e})  |  cache read {cr} ({crp:.0f}%) · output {o}"),
    },
    "zh": {
        "tag": "✦  MY CLAUDE CODE WRAPPED  ✦",
        "title": "我的 Token 用量报告",
        "rhythm": "每日用量节奏",
        "models": "模型 TOP 榜",
        "cost": "总花费", "cost_fun": "总花费  ·  ≈ {c} 杯咖啡",
        "peak": "单日峰值 ({d})", "avg": "平均每天", "output": "输出 token",
        "fun_line": "★  ≈ {nv} 本小说  ·  连续阅读 {rd}  ★",
        "read_h": "{v} 小时", "read_d": "{v} 天", "read_y": "{v} 年",
        "sub": "{t}  ·  {d} {dw}和 Claude 相伴",
        "powered": "Powered by Claude Code",
        "tag_min": "CLAUDE CODE · 用量报告", "min_top": "头号模型",
        "arch": {"marathon": "马拉松选手", "weekend": "周末战士",
                 "sprinter": "短跑冲刺型", "steady": "稳健建造者",
                 "explorer": "探索者"},
        "report": "TOKEN 用量报告", "kpi_spent": "总花费",
        "kpi_tokens": "总 token", "kpi_days": "活跃天数", "kpi_top": "头号模型",
        "tbl_model": "模型", "tbl_cost": "成本", "tbl_share": "占比",
        "biz_cum": "累计花费", "prompt": "ccusage --wrapped",
        "t_total": "总计", "t_spent": "花费", "t_days": "天数", "t_top": "头号",
        "t_cache": "缓存", "t_out": "输出", "you_are": "你是",
        "receipt": "TOKEN 小票", "r_thanks": "感谢使用 CLAUDE CODE",
        "r_item": "项目", "r_amt": "金额",
        "d_title": "我的 Token 用量报告", "d_daily": "每日 token",
        "d_cumcost": "累计成本", "d_cost_model": "每日成本 · 按模型",
        "d_share": "成本占比 · 按模型", "d_total": "总成本 ($)",
        "d_tokday": "Tokens / day", "d_costday": "Cost / day ($)",
        "d_heat": "活跃度 (每日 token)",
        "d_active": "活跃天数", "d_streak": "最长连续",
        "d_busy": "最忙的一天", "d_avgday": "平均每天",
        "d_streak_u": "{v} 天", "d_less": "少", "d_more": "多",
        "wd": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
        "d_cap": ("合计 {tk} tokens · ${c:,.0f} · {n} 天 "
                  "({s}→{e})  |  cache read {cr} ({crp:.0f}%) · output {o}"),
    },
}


def find_cjk():
    prefer = ["Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans SC",
              "WenQuanYi Zen Hei", "Microsoft YaHei", "PingFang SC", "SimHei",
              "Noto Serif CJK SC"]
    have = {f.name for f in fm.fontManager.ttflist}
    for p in prefer:
        if p in have:
            return p
    return None


def hexlist(s):
    return [c.strip() for c in s.split(",") if c.strip()]


def load_style(name, a):
    """Resolve --style into a style dict: preset | custom | theme file."""
    if name == "custom":
        return dict(bg=hexlist(a.bg or "#100C2E,#561C78,#C8326E"),
                    accent=a.accent or "#FFD86B",
                    bars=a.bars or (a.accent or "#FFD86B"),
                    text=a.text or "light",
                    glows=[(a.accent or "#FFD86B", 0.16),
                           (a.bars or "#5D9BFF", 0.14), ("#FFFFFF", 0.06)])
    if name in STYLES:
        return STYLES[name]
    for d in THEME_DIRS:
        fp = os.path.join(d, f"{name}.json")
        if os.path.isfile(fp):
            try:
                t = json.load(open(fp))
            except Exception as e:
                print(f"[warn] bad theme file {fp}: {e}; using cyber_purple")
                return STYLES["cyber_purple"]
            acc = t.get("accent", "#FFD86B")
            return dict(bg=t.get("bg", ["#100C2E", "#561C78", "#C8326E"]),
                        accent=acc, bars=t.get("bars", acc),
                        text=t.get("text", "light"),
                        glows=t.get("glows") or [(acc, 0.16),
                                                 (t.get("bars", "#5D9BFF"), 0.14),
                                                 ("#FFFFFF", 0.06)])
    print(f"[warn] unknown style/theme '{name}'; using cyber_purple")
    return STYLES["cyber_purple"]


def gradient_img(bg):
    c = [np.array(mcolors.to_rgb(x)) for x in bg]
    if len(c) == 1: c = c * 3
    if len(c) == 2: c = [c[0], (c[0] + c[1]) / 2, c[1]]
    img = np.zeros((512, 1, 3))
    for i, t in enumerate(np.linspace(0, 1, 512)):
        if t < 0.5: f = t / 0.5; img[i, 0] = c[0] * (1 - f) + c[1] * f
        else: f = (t - 0.5) / 0.5; img[i, 0] = c[1] * (1 - f) + c[2] * f
    return img


def fmt_tok(x, _=None):
    if x >= 1e9: return f"{x/1e9:.1f}B"
    if x >= 1e6: return f"{x/1e6:.0f}M"
    if x >= 1e3: return f"{x/1e3:.0f}K"
    return f"{x:.0f}"


def fmt_count(x):
    """Compact count for fun-facts (keeps one decimal in the K/M/B range)."""
    if x >= 1e9: return f"{x/1e9:.1f}B"
    if x >= 1e6: return f"{x/1e6:.1f}M"
    if x >= 1e3: return f"{x/1e3:.1f}K"
    if x >= 100: return f"{x:.0f}"
    return f"{x:.1f}" if x < 10 else f"{x:.0f}"


def reading_human(read_hours, S):
    """Pick the largest sensible time unit so the number stays relatable."""
    if read_hours < 48:
        return S["read_h"].format(v=fmt_count(read_hours))
    days = read_hours / 24
    if days < 365:
        return S["read_d"].format(v=fmt_count(days))
    return S["read_y"].format(v=fmt_count(days / 365))


def hero(total, lang):
    """Return (big_number, unit_label) sized for the audience."""
    if lang == "zh":
        if total >= 1e8: return f"{total/1e8:.1f}", f"亿 个 TOKEN  ·  {total/1e9:.2f} Billion"
        if total >= 1e4: return f"{total/1e4:.1f}", "万 个 TOKEN"
        return f"{total:,}", "个 TOKEN"
    if total >= 1e9: return f"{total/1e9:.2f}", "BILLION TOKENS"
    if total >= 1e6: return f"{total/1e6:.0f}", "MILLION TOKENS"
    if total >= 1e3: return f"{total/1e3:.0f}", "THOUSAND TOKENS"
    return f"{total:,}", "TOKENS"


def model_costs(daily):
    """Aggregate {modelName: cost} across all days, sorted high→low."""
    mc = defaultdict(float)
    for r in daily:
        for m in r["modelBreakdowns"]:
            mc[m["modelName"]] += m["cost"]
    return dict(sorted(mc.items(), key=lambda kv: kv[1], reverse=True))


def short_model(name):
    return name.replace("claude-", "").replace("-latest", "")


def derive(data, coffee_price):
    """All numbers a template might want, computed once."""
    daily, tot, rng = data["daily"], data["totals"], data["range"]
    TOTAL, COST, NDAYS = tot["totalTokens"], tot["totalCost"], max(rng["days"], 1)
    peak = max(daily, key=lambda r: r["totalTokens"])
    words = TOTAL * WORDS_PER_TOKEN
    mc = model_costs(daily)
    active = sum(1 for r in daily if r["totalTokens"] > 0)
    wd_tok = defaultdict(float)
    for r in daily:
        wd_tok[date.fromisoformat(r["date"]).weekday()] += r["totalTokens"]
    weekend = sum(v for k, v in wd_tok.items() if k >= 5)
    return dict(daily=daily, tot=tot, rng=rng, TOTAL=TOTAL, COST=COST, NDAYS=NDAYS,
                peak=peak, avg=TOTAL / NDAYS, words=words, novels=words / WORDS_PER_NOVEL,
                read_hours=words / READING_WPM / 60,
                coffees=(COST / coffee_price if coffee_price > 0 else 0),
                mc=mc, top=list(mc.items())[:3], toks=[r["totalTokens"] for r in daily],
                active=active, streak=_streak(daily),
                busy_wd=(max(wd_tok, key=wd_tok.get) if wd_tok else 0),
                weekend_share=(weekend / TOTAL if TOTAL else 0))


def archetype(m, S):
    """A light 'developer archetype' derived only from daily-grain signals."""
    a = S["arch"]
    if m["streak"] >= 7:
        return a["marathon"]
    if m["weekend_share"] >= 0.45:
        return a["weekend"]
    if m["peak"]["totalTokens"] >= 3 * m["avg"]:
        return a["sprinter"]
    if m["active"] >= 0.8 * m["NDAYS"]:
        return a["steady"]
    return a["explorer"]


def _sparkline(ax, toks, x0, x1, y0, y1, color, lw=2.2, dot=True):
    """Draw a thin sparkline in axes-fraction coords (ax is a 0..1 canvas)."""
    n = len(toks); mx = max(toks) if toks else 1
    xs = np.linspace(x0, x1, n) if n > 1 else np.array([(x0 + x1) / 2])
    ys = [y0 + (t / mx) * (y1 - y0) if mx > 0 else y0 for t in toks]
    ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round", zorder=5)
    if dot and n:
        i = int(np.argmax(toks))
        ax.scatter([xs[i]], [ys[i]], s=42, color=color, zorder=6, edgecolors="none")


# ---- template: minimal (editorial / Swiss) -------------------------------
def tpl_minimal(data, st, S, lang, L, m, title, subtitle, fun, out):
    dark = st["text"] == "dark"
    INK = "#15131F" if dark else "#F4F2FA"
    DIM = "#7B7690" if dark else "#A9A4C0"
    HAIR = "#15131F26" if dark else "#FFFFFF33"
    ACC = st["accent"]
    fig = plt.figure(figsize=L["figsize"], dpi=120)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, facecolor=st["bg"][0], zorder=0))
    ML, MR = 0.12, 0.88

    def T(x, y, s, size, color=INK, w="normal", ha="left", a=1.0, ls=0.0):
        t = ax.text(x, y, s, fontsize=size, color=color, weight=w, ha=ha, va="center",
                    zorder=5, alpha=a)
        if ls: t.set_fontproperties(t.get_fontproperties());
        return t

    def rule(y):
        ax.plot([ML, MR], [y, y], color=HAIR, lw=1.3, zorder=2)

    T(ML, 0.93, S["tag_min"], 14.5, ACC, w="bold")
    T(MR, 0.93, f"{m['rng']['start']} → {m['rng']['end']}", 13, DIM, ha="right")
    rule(0.908)

    big, unit = hero(m["TOTAL"], lang)
    T(ML, 0.78, big, 116, INK, w="normal")
    T(ML, 0.672, unit, 22, DIM, w="normal")
    T(ML, 0.628, f"{m['TOTAL']:,}", 15, DIM, w="normal")

    rule(0.555)
    cols = [(f"${m['COST']:,.0f}", S["cost"], 30),
            (str(m["NDAYS"]), S["d_active"], 30),
            (short_model(m["top"][0][0]) if m["top"] else "—", S["min_top"], 25)]
    xs = [ML, 0.40, 0.64]
    for (val, lab, fs), x in zip(cols, xs):
        T(x, 0.50, val, fs, INK, w="bold")
        T(x, 0.452, lab, 13, DIM)
    rule(0.408)

    _sparkline(ax, m["toks"], ML, MR, 0.27, 0.36, ACC, lw=2.4)
    T(ML, 0.235, S["rhythm"], 12.5, DIM)

    rule(0.085)
    T(ML, 0.055, S["powered"], 12.5, DIM)
    T(MR, 0.055, "claude.com/claude-code", 12, DIM, ha="right")

    fig.savefig(f"{out}.png", dpi=200, facecolor=st["bg"][0])
    fig.savefig(f"{out}.pdf", facecolor=st["bg"][0])
    plt.close(fig)
    print(f"poster[minimal] -> {out}.png")


def _stub(name):
    def f(data, st, S, lang, L, m, title, subtitle, fun, out):
        print(f"[todo] template '{name}' not implemented yet")
    return f


def _lum(c):
    r, g, b = mcolors.to_rgb(c)
    return 0.299 * r + 0.587 * g + 0.114 * b


# ---- template: business (exec one-pager) ---------------------------------
def tpl_business(data, st, S, lang, L, m, title, subtitle, fun, out):
    dark = st["text"] == "light"  # dark-background style → dark report paper
    PAPER = "#14161C" if dark else "#FFFFFF"
    PANEL = "#1E222B" if dark else "#F6F7FB"
    INK = "#EEF1F7" if dark else "#1B1E27"
    DIM = "#9AA3B2" if dark else "#6B7280"
    BORDER = "#2C313C" if dark else "#E3E6EF"
    ACC = st["accent"]
    ON_ACC = "#0B0B10" if _lum(ACC) > 0.6 else "#FFFFFF"
    fig = plt.figure(figsize=L["figsize"], dpi=120)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, facecolor=PAPER, zorder=0))
    ML, MR = 0.08, 0.92

    def T(x, y, s, size, color=INK, w="normal", ha="left", a=1.0):
        ax.text(x, y, s, fontsize=size, color=color, weight=w, ha=ha, va="center",
                zorder=6, alpha=a)

    # header bar
    ax.add_patch(FancyBboxPatch((ML, 0.905), MR - ML, 0.072,
                 boxstyle="round,pad=0,rounding_size=0.01", linewidth=0,
                 facecolor=ACC, zorder=3))
    T(ML + 0.025, 0.941, title, 23, ON_ACC, w="bold")
    T(MR - 0.025, 0.941, f"{m['rng']['start']} → {m['rng']['end']}", 13.5, ON_ACC,
      ha="right", a=0.9)
    T(ML, 0.862, S["report"], 13, DIM, w="bold")

    # KPI cards
    kpis = [(fmt_tok(m["TOTAL"]), S["kpi_tokens"]), (f"${m['COST']:,.0f}", S["kpi_spent"]),
            (str(m["NDAYS"]), S["kpi_days"]),
            (f"{(m['top'][0][1]/(m['COST'] or 1)*100):.0f}%", S["kpi_top"])]
    cw, gap = 0.198, 0.012
    x0 = ML
    for i, (val, lab) in enumerate(kpis):
        cx = x0 + i * (cw + gap)
        ax.add_patch(FancyBboxPatch((cx, 0.745), cw, 0.085,
                     boxstyle="round,pad=0,rounding_size=0.012", linewidth=1.2,
                     edgecolor=BORDER, facecolor=PANEL, zorder=3))
        T(cx + 0.018, 0.806, val, 24, INK, w="bold")
        T(cx + 0.018, 0.766, lab, 11.5, DIM)

    # cumulative spend chart (real axes)
    T(ML, 0.70, S["biz_cum"], 14, INK, w="bold")
    cax = fig.add_axes([0.085, 0.435, 0.835, 0.235])
    cum, s = [], 0.0
    for r in m["daily"]: s += r["totalCost"]; cum.append(s)
    xx = range(len(cum))
    cax.fill_between(xx, cum, color=ACC, alpha=0.14, zorder=2)
    cax.plot(xx, cum, color=ACC, lw=2.6, zorder=3)
    cax.set_facecolor(PAPER)
    for sp in ["top", "right"]: cax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]: cax.spines[sp].set_color(BORDER)
    cax.tick_params(colors=DIM, labelsize=9)
    cax.set_ylim(bottom=0); cax.margins(x=0)
    cax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    n = len(m["daily"]); step = max(1, n // 6)
    cax.set_xticks(list(xx)[::step])
    cax.set_xticklabels([m["daily"][i]["date"][5:] for i in list(xx)[::step]],
                        fontsize=8.5, color=DIM)
    cax.grid(axis="y", color=BORDER, lw=0.8, alpha=0.6)

    # model table
    ty = 0.355
    T(ML, ty, S["tbl_model"], 12.5, DIM, w="bold")
    T(0.56, ty, S["tbl_cost"], 12.5, DIM, w="bold", ha="right")
    T(0.66, ty, S["tbl_share"], 12.5, DIM, w="bold")
    ax.plot([ML, MR], [ty - 0.018, ty - 0.018], color=BORDER, lw=1.2, zorder=4)
    tc = m["COST"] or 1
    bx0, bx1 = 0.66, 0.855
    for i, (name, c) in enumerate(list(m["mc"].items())[:5]):
        ry = ty - 0.045 - i * 0.046
        T(ML, ry, short_model(name), 14, INK, w="bold")
        T(0.56, ry, f"${c:,.0f}", 14, INK, ha="right")
        share = c / tc
        ax.add_patch(FancyBboxPatch((bx0, ry - 0.011), (bx1 - bx0) * share, 0.022,
                     boxstyle="round,pad=0,rounding_size=0.004", linewidth=0,
                     facecolor=ACC, alpha=0.85, zorder=4))
        T(bx1, ry, f"{share*100:.0f}%", 12, DIM, ha="right")

    ax.plot([ML, MR], [0.072, 0.072], color=BORDER, lw=1.2)
    T(ML, 0.045, S["powered"], 12, DIM)
    T(MR, 0.045, "claude.com/claude-code", 11.5, DIM, ha="right")

    fig.savefig(f"{out}.png", dpi=200, facecolor=PAPER)
    fig.savefig(f"{out}.pdf", facecolor=PAPER)
    plt.close(fig)
    print(f"poster[business] -> {out}.png")


ARCH_SYM = {"marathon": "⚡", "weekend": "★", "sprinter": "▲",
            "steady": "◆", "explorer": "✦"}
_BLOCKS = "▁▂▃▄▅▆▇█"


def _ascii_spark(toks):
    mx = max(toks) if toks else 1
    return "".join(_BLOCKS[min(7, int((t / mx) * 7.99)) if mx > 0 else 0] for t in toks)


# ---- template: terminal (CRT readout) ------------------------------------
def tpl_terminal(data, st, S, lang, L, m, title, subtitle, fun, out):
    BG = "#05080B"
    PH = st["bars"]                       # phosphor (readout) colour
    ACC = st["accent"]
    DIM = mcolors.to_hex(np.array(mcolors.to_rgb(PH)) * 0.55 + 0.0)
    MONO = "monospace" if lang == "en" else None
    fig = plt.figure(figsize=L["figsize"], dpi=120)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, facecolor=BG, zorder=0))
    # scanlines
    for yy in np.arange(0, 1, 0.0065):
        ax.plot([0, 1], [yy, yy], color="#FFFFFF", lw=0.6, alpha=0.025, zorder=1)
    # window frame
    fx, fw = 0.06, 0.88
    ax.add_patch(FancyBboxPatch((fx, 0.06), fw, 0.88,
                 boxstyle="round,pad=0,rounding_size=0.012", linewidth=1.6,
                 edgecolor=PH, facecolor="#0A0E12", zorder=2))
    ax.plot([fx, fx + fw], [0.892, 0.892], color=PH, lw=1.4, zorder=3)
    for i, cdot in enumerate(["#FF5F56", "#FFBD2E", "#27C93F"]):
        ax.scatter([fx + 0.03 + i * 0.028], [0.915], s=120, color=cdot, zorder=4,
                   edgecolors="none")
    ax.text(0.5, 0.915, S["prompt"], fontsize=13, color=DIM, ha="center", va="center",
            family=MONO, zorder=4)

    ML = fx + 0.04
    T = lambda x, y, s, sz, c=PH, ha="left", w="normal": ax.text(
        x, y, s, fontsize=sz, color=c, ha=ha, va="center", family=MONO, weight=w, zorder=5)

    T(ML, 0.852, f"$ claude-code stats {m['rng']['start']}..{m['rng']['end']}", 12.5, DIM)
    big, unit = hero(m["TOTAL"], lang)
    T(ML, 0.775, big, 62, PH, w="bold")
    T(ML, 0.705, f"// {unit.lower()}", 15, ACC)

    def row(y, label, value):
        dots = "." * max(3, 17 - len(label))
        T(ML, y, f"> {label} {dots}", 15, DIM)
        T(fx + fw - 0.04, y, value, 15, PH, ha="right", w="bold")

    crp = m["tot"]["cacheReadTokens"] / m["TOTAL"] * 100 if m["TOTAL"] else 0
    rows = [(S["t_spent"], f"${m['COST']:,.0f}"),
            (S["t_days"], str(m["NDAYS"])),
            (S["t_top"], f"{short_model(m['top'][0][0])} ({m['top'][0][1]/(m['COST'] or 1)*100:.0f}%)"),
            (S["t_out"], fmt_tok(m["tot"]["outputTokens"])),
            (S["t_cache"], f"{fmt_tok(m['tot']['cacheReadTokens'])} ({crp:.0f}%)")]
    y = 0.635
    for lab, val in rows:
        row(y, lab, val); y -= 0.05

    # ascii sparkline of daily tokens (wrap to fit)
    spark = _ascii_spark(m["toks"])
    T(ML, 0.345, "daily:", 13, DIM)
    T(ML, 0.305, spark, 15, PH)
    # ascii activity heatmap (last 7x cols)
    by = {r["date"]: r["totalTokens"] for r in m["daily"]}
    vmax = max(by.values()) if by else 1
    shades = " ░▒▓█"
    T(ML, 0.255, "activity:", 13, DIM)
    d0 = date.fromisoformat(m["daily"][0]["date"])
    start = date.fromordinal(d0.toordinal() - d0.weekday())
    d1 = date.fromisoformat(m["daily"][-1]["date"])
    ncols = (d1.toordinal() - start.toordinal()) // 7 + 1
    for wd in range(7):
        line = ""
        for c in range(ncols):
            o = start.toordinal() + c * 7 + wd
            v = by.get(date.fromordinal(o).isoformat())
            line += "·" if v is None else shades[min(4, int((v / vmax) * 4.99)) if vmax else 0]
        T(ML + 0.10, 0.225 - wd * 0.018, line, 12, ACC)
        T(ML, 0.225 - wd * 0.018, S["wd"][wd][:3] if lang == "en" else S["wd"][wd],
          10, DIM)

    if fun:
        nv, rd = fmt_count(m["novels"]), reading_human(m["read_hours"], S)
        msg = (f"# {nv} novels · {rd} of reading" if lang == "en"
               else f"# {nv} 本小说 · 阅读 {rd}")
        T(ML, 0.085, msg, 12.5, DIM)
    T(ML, 0.05, "> _", 16, PH, w="bold")

    fig.savefig(f"{out}.png", dpi=200, facecolor=BG)
    fig.savefig(f"{out}.pdf", facecolor=BG)
    plt.close(fig)
    print(f"poster[terminal] -> {out}.png")


# ---- template: playful (sticker / fun) -----------------------------------
def tpl_playful(data, st, S, lang, L, m, title, subtitle, fun, out):
    dark = st["text"] == "dark"
    INK = "#1A1330" if dark else "#FFFFFF"
    DIM = "#4A4460" if dark else "#FFFFFFCC"
    ACC = st["accent"]
    ON_ACC = "#0B0B10" if _lum(ACC) > 0.6 else "#FFFFFF"
    confetti_cols = [ACC, st["bars"]] + [g[0] for g in st["glows"]]
    fig = plt.figure(figsize=L["figsize"], dpi=120)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.imshow(gradient_img(st["bg"]), extent=[0, 1, 0, 1], aspect="auto",
              origin="lower", zorder=0)

    # confetti (deterministic pseudo-random, kept out of the central column)
    for i in range(54):
        x = (np.sin((i + 1) * 12.9898) * 43758.5453) % 1
        y = (np.sin((i + 1) * 78.233) * 43758.5453) % 1
        if 0.2 < x < 0.8 and 0.18 < y < 0.92:
            continue
        ax.scatter([x], [y], s=[60, 120, 200][i % 3], marker=["o", "s", "^"][i % 3],
                   color=confetti_cols[i % len(confetti_cols)], alpha=0.55,
                   zorder=1, edgecolors="none")

    def T(x, y, s, size, color=INK, w="bold", ha="center", a=1.0):
        ax.text(x, y, s, fontsize=size, color=color, weight=w, ha=ha, va="center",
                zorder=6, alpha=a)

    T(0.5, 0.955, S["tag"], 16, ACC)

    # archetype badge (chunky pill)
    arch = archetype(m, S)
    sym = ARCH_SYM[next(k for k, v in S["arch"].items() if v == arch)]
    T(0.5, 0.905, S["you_are"], 13, DIM, w="normal")
    bw = 0.62
    ax.add_patch(FancyBboxPatch((0.5 - bw / 2, 0.838), bw, 0.052,
                 boxstyle="round,pad=0.004,rounding_size=0.03", linewidth=0,
                 facecolor=ACC, zorder=4))
    T(0.5, 0.864, f"{sym}  {arch}", 24, ON_ACC)

    big, unit = hero(m["TOTAL"], lang)
    T(0.5, 0.715, big, 132, INK)
    T(0.5, 0.60, f"{unit} !!", 26, ACC)
    T(0.5, 0.555, subtitle, 16, DIM, w="normal")

    # chunky stat chips (row of 3)
    def chip(cx, big_s, small, sym):
        w, h = 0.275, 0.135
        ax.add_patch(FancyBboxPatch((cx - w / 2, 0.40), w, h,
                     boxstyle="round,pad=0.006,rounding_size=0.04", linewidth=0,
                     facecolor=INK if not dark else "#FFFFFF", alpha=0.12, zorder=3))
        ax.add_patch(FancyBboxPatch((cx - w / 2, 0.40), w, h,
                     boxstyle="round,pad=0.006,rounding_size=0.04", linewidth=2.4,
                     edgecolor=ACC, facecolor="none", zorder=4))
        T(cx, 0.515, sym, 30, ACC)
        T(cx, 0.468, big_s, 25, INK)
        T(cx, 0.425, small, 12.5, DIM, w="normal")
    chip(0.235, f"${m['COST']:,.0f}", S["t_spent"], "☕")
    chip(0.5, fmt_count(m["novels"]), "novels" if lang == "en" else "本小说", "◆")
    chip(0.765, fmt_tok(m["peak"]["totalTokens"]), S["t_top"], "▲")

    # chunky rounded bars
    toks = np.array(m["toks"], float); n = len(toks)
    mx = toks.max() if toks.size else 1
    xs = np.linspace(0.13, 0.87, n) if n > 1 else np.array([0.5])
    bw2 = min((0.74 / max(n, 1)) * 0.7, 0.05)
    for xi, h in zip(xs, toks / mx if mx > 0 else toks):
        ax.add_patch(FancyBboxPatch((xi - bw2 / 2, 0.255), bw2, max(h * 0.10, 0.004),
                     boxstyle="round,pad=0,rounding_size=0.012", linewidth=0,
                     facecolor=st["bars"], zorder=4))

    # speech-bubble fun fact
    if fun:
        bx, by, bw3, bh3 = 0.16, 0.10, 0.68, 0.07
        ax.add_patch(FancyBboxPatch((bx, by), bw3, bh3,
                     boxstyle="round,pad=0.006,rounding_size=0.04", linewidth=0,
                     facecolor=ACC, zorder=4))
        ax.add_patch(plt.Polygon([[0.30, by], [0.36, by], [0.31, by - 0.028]],
                     closed=True, facecolor=ACC, zorder=4, edgecolor="none"))
        msg = (f'"read {reading_human(m["read_hours"], S)} straight!"' if lang == "en"
               else f'"连续读了 {reading_human(m["read_hours"], S)}！"')
        T(0.5, by + bh3 / 2, msg, 17, ON_ACC)

    T(0.5, 0.04, S["powered"], 12.5, DIM, w="normal")

    face = st["bg"][0]
    fig.savefig(f"{out}.png", dpi=200, facecolor=face)
    fig.savefig(f"{out}.pdf", facecolor=face)
    plt.close(fig)
    print(f"poster[playful] -> {out}.png")


# ---- template: receipt (printed till receipt) ----------------------------
def tpl_receipt(data, st, S, lang, L, m, title, subtitle, fun, out):
    BG = "#26231F"
    PAPER = "#F7F4EC"
    INK = "#1C1A17"
    DIM = "#6E6A62"
    ACC = st["accent"]
    if _lum(ACC) > 0.78:                  # keep the star readable on white paper
        ACC = mcolors.to_hex(np.array(mcolors.to_rgb(ACC)) * 0.7)
    MONO = "monospace" if lang == "en" else None
    fig = plt.figure(figsize=L["figsize"], dpi=120)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, facecolor=BG, zorder=0))

    px0, px1 = 0.24, 0.76
    pcx = (px0 + px1) / 2
    ptop, pbot = 0.92, 0.255
    ax.add_patch(plt.Rectangle((px0, pbot), px1 - px0, ptop - pbot, facecolor=PAPER,
                 zorder=2))
    # torn zigzag edges (BG-coloured teeth biting into the paper)
    teeth = 13; tw = (px1 - px0) / teeth
    for k in range(teeth):
        xx = px0 + k * tw
        ax.add_patch(plt.Polygon([[xx, ptop], [xx + tw, ptop], [xx + tw / 2, ptop - 0.012]],
                     closed=True, facecolor=BG, zorder=3, edgecolor="none"))
        ax.add_patch(plt.Polygon([[xx, pbot], [xx + tw, pbot], [xx + tw / 2, pbot + 0.012]],
                     closed=True, facecolor=BG, zorder=3, edgecolor="none"))

    def C(y, s, sz, c=INK, w="normal"):
        ax.text(pcx, y, s, fontsize=sz, color=c, ha="center", va="center",
                family=MONO, weight=w, zorder=5)

    def LR(y, l, r, sz=13, c=INK, w="normal"):
        ax.text(px0 + 0.022, y, l, fontsize=sz, color=c, ha="left", va="center",
                family=MONO, weight=w, zorder=5)
        ax.text(px1 - 0.022, y, r, fontsize=sz, color=c, ha="right", va="center",
                family=MONO, weight=w, zorder=5)

    def dash(y, ch="-"):
        C(y, ch * 30, 12, DIM)

    C(0.885, f"★  CLAUDE CODE  ★", 16, ACC, w="bold")
    C(0.86, S["receipt"], 12.5, DIM, w="bold")
    dash(0.838)
    C(0.818, f"{m['rng']['start']}  -  {m['rng']['end']}", 12, INK)
    dash(0.798)
    LR(0.778, S["r_item"], S["r_amt"], 11.5, DIM, w="bold")

    items = [(S["t_total"] + " tokens" if lang == "en" else "总 token", fmt_tok(m["TOTAL"])),
             (S["t_out"] + " tokens" if lang == "en" else "输出 token", fmt_tok(m["tot"]["outputTokens"])),
             (S["t_cache"] + " read" if lang == "en" else "缓存读取", fmt_tok(m["tot"]["cacheReadTokens"])),
             (S["d_active"], str(m["NDAYS"])),
             (S["d_streak"], S["d_streak_u"].format(v=m["streak"]))]
    y = 0.752
    for l, r in items:
        LR(y, l, r, 13); y -= 0.026
    dash(y + 0.004); y -= 0.022
    for name, c in list(m["mc"].items())[:4]:
        LR(y, short_model(name), f"${c:,.2f}", 13); y -= 0.026
    C(y + 0.003, "=" * 30, 12, INK); y -= 0.03
    LR(y, "TOTAL", f"${m['COST']:,.2f}", 18, INK, w="bold"); y -= 0.03
    C(y + 0.006, "=" * 30, 12, INK); y -= 0.03

    if fun:
        C(y, f"≈ {fmt_count(m['coffees'])} lattes  &  "
             f"{fmt_count(m['novels'])} novels" if lang == "en"
             else f"≈ {fmt_count(m['coffees'])} 杯咖啡 & {fmt_count(m['novels'])} 本小说",
          12, DIM); y -= 0.03

    # barcode from daily tokens (deterministic)
    toks = m["toks"]; mx = max(toks) if toks else 1
    bx = px0 + 0.03; bar_top = y - 0.005; bar_h = 0.045; i = 0
    while bx < px1 - 0.03:
        t = toks[i % len(toks)] if toks else 0
        w = 0.0035 + 0.006 * (t / mx if mx else 0)
        ax.add_patch(plt.Rectangle((bx, bar_top - bar_h), w * 0.6, bar_h,
                     facecolor=INK, zorder=5, edgecolor="none"))
        bx += w; i += 1
    C(bar_top - bar_h - 0.022, "*" + "".join(str((d * 7) % 10) for d in range(12)) + "*",
      11, DIM)
    C(bar_top - bar_h - 0.06, S["r_thanks"], 12.5, ACC, w="bold")

    fig.savefig(f"{out}.png", dpi=200, facecolor=BG)
    fig.savefig(f"{out}.pdf", facecolor=BG)
    plt.close(fig)
    print(f"poster[receipt] -> {out}.png")


# ---- poster --------------------------------------------------------------
def render_poster(data, st, S, lang, L, title, subtitle, fun, coffee_price, out):
    daily, tot, rng = data["daily"], data["totals"], data["range"]
    TOTAL, COST, NDAYS = tot["totalTokens"], tot["totalCost"], max(rng["days"], 1)
    if not daily or TOTAL <= 0:
        print("[skip] no data for poster"); return
    peak = max(daily, key=lambda r: r["totalTokens"])
    words = TOTAL * WORDS_PER_TOKEN
    novels = words / WORDS_PER_NOVEL
    read_hours = words / READING_WPM / 60
    coffees = COST / coffee_price if coffee_price > 0 else 0

    dark = st["text"] == "dark"
    WHITE = "#15131F" if dark else "#FFFFFF"
    DIM = "#5A5570" if dark else "#D8CFF0"
    FAINT = "#8A85A0" if dark else "#FFFFFFAA"
    GOLD = st["accent"]

    fig = plt.figure(figsize=L["figsize"], dpi=120)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.imshow(gradient_img(st["bg"]), extent=[0, 1, 0, 1], aspect="auto",
              origin="lower", zorder=0)
    for (cx, cy), (col, al) in zip(L["glows"], st["glows"]):
        ax.scatter([cx], [cy], s=9000, color=col, alpha=al, zorder=1, edgecolors="none")

    def T(x, y, s, size, color=WHITE, w="bold", a=1.0, ha="center"):
        ax.text(x, y, s, fontsize=size, color=color, weight=w, ha=ha,
                va="center", zorder=5, alpha=a)

    T(0.5, L["tag"], S["tag"], 15, GOLD)
    T(0.5, L["title"], title, 22, WHITE)

    big, unit = hero(TOTAL, lang)
    T(0.5, L["hero"], big, L["hero_size"], WHITE)
    T(0.5, L["unit"], unit, 27, GOLD)
    T(0.5, L["sub"], subtitle, 17, DIM, w="normal")

    # daily rhythm bars
    toks = np.array([r["totalTokens"] for r in daily], float)
    n = len(toks); mx = toks.max() if toks.size else 1
    norm = toks / mx if mx > 0 else toks
    xs = np.linspace(0.10, 0.90, n) if n > 1 else np.array([0.5])
    bw = min((0.80 / max(n, 1)) * 0.62, 0.045)
    by0, bh = L["bars_y0"], L["bars_h"]
    for xi, h in zip(xs, norm):
        for a, wmul in [(0.22, 2.4), (1.0, 1.0)]:
            ax.add_patch(FancyBboxPatch((xi - bw * wmul / 2, by0), bw * wmul,
                         h * bh + (0.014 if a < 1 else 0),
                         boxstyle="round,pad=0,rounding_size=0.006",
                         linewidth=0, facecolor=st["bars"], alpha=a, zorder=4))
    T(0.5, L["rhythm"], S["rhythm"], 13, DIM, w="normal")

    # TOP MODELS strip (Wrapped staple)
    mc = model_costs(daily)
    top = list(mc.items())[:3]
    tc = COST or 1
    T(0.5, L["models_hdr"], S["models"], 13.5, GOLD)
    mrank = ["①", "②", "③"]
    bar_x0, bar_x1 = 0.40, 0.86
    mxc = top[0][1] if top and top[0][1] > 0 else 1
    for i, (name, c) in enumerate(top):
        y = L["models_y0"] - i * L["models_dy"]
        T(0.135, y, f"{mrank[i]} {short_model(name)}", 14, WHITE, ha="left")
        w = (bar_x1 - bar_x0) * (c / mxc)
        ax.add_patch(FancyBboxPatch((bar_x0, y - 0.013), max(w, 0.004), 0.026,
                     boxstyle="round,pad=0,rounding_size=0.008",
                     linewidth=0, facecolor=st["bars"], alpha=0.92, zorder=4))
        T(bar_x1 + 0.015, y, f"{c/tc*100:.0f}%", 13, DIM, w="normal", ha="left")

    # two chips: cost + peak
    def chip(cx, cy, big_s, small, sym):
        w, hgt = 0.40, 0.092
        ec = "#15131F22" if dark else "#FFFFFF40"
        fc = "#15131F0D" if dark else "#FFFFFF1A"
        ax.add_patch(FancyBboxPatch((cx - w / 2, cy - hgt / 2), w, hgt,
                     boxstyle="round,pad=0.006,rounding_size=0.02",
                     linewidth=1.2, edgecolor=ec, facecolor=fc, zorder=4))
        T(cx, cy + 0.019, f"{sym} {big_s}", 26, WHITE)
        T(cx, cy - 0.024, small, 13, DIM, w="normal")

    cost_small = S["cost_fun"].format(c=fmt_count(coffees)) if fun else S["cost"]
    chip(0.29, L["chips"], f"${COST:,.0f}", cost_small, "☕")
    chip(0.71, L["chips"], fmt_tok(peak["totalTokens"]),
         S["peak"].format(d=peak["date"][5:]), "▲")

    if fun:
        T(0.5, L["fun"], S["fun_line"].format(nv=fmt_count(novels),
                                              rd=reading_human(read_hours, S)),
          17, GOLD)
    T(0.5, L["range"], f"{rng['start']}  →  {rng['end']}", 15, DIM, w="normal")
    T(0.5, L["powered"], S["powered"], 12.5, FAINT, w="normal")

    face = st["bg"][0]
    fig.savefig(f"{out}.png", dpi=200, facecolor=face)
    fig.savefig(f"{out}.pdf", facecolor=face)
    plt.close(fig)
    print(f"poster -> {out}.png")


# ---- dashboard -----------------------------------------------------------
def _heatmap(ax, daily, st, S, fg, face):
    """GitHub-style contribution calendar of daily tokens."""
    by_date = {r["date"]: r["totalTokens"] for r in daily}
    d0 = date.fromisoformat(daily[0]["date"])
    d1 = date.fromisoformat(daily[-1]["date"])
    start = date.fromordinal(d0.toordinal() - d0.weekday())  # back to Monday
    ncols = (d1.toordinal() - start.toordinal()) // 7 + 1
    grid = np.full((7, ncols), np.nan)
    for o in range(start.toordinal(), d1.toordinal() + 1):
        dd = date.fromordinal(o)
        col = (o - start.toordinal()) // 7
        grid[dd.weekday(), col] = by_date.get(dd.isoformat(), 0)
    vmax = np.nanmax(grid) if np.isfinite(grid).any() else 1
    base = np.array(mcolors.to_rgb(face))
    acc = np.array(mcolors.to_rgb(st["bars"]))
    empty = base * 0.6 + np.array([0.5, 0.5, 0.5]) * 0.4
    pad = 0.12
    for r in range(7):
        for c in range(ncols):
            v = grid[r, c]
            if np.isnan(v):
                continue
            t = (v / vmax) ** 0.6 if vmax > 0 else 0
            col = empty * (1 - t) + acc * t if v > 0 else empty
            ax.add_patch(plt.Rectangle((c + pad, 6 - r + pad), 1 - 2 * pad, 1 - 2 * pad,
                         facecolor=col, edgecolor="none"))
    ax.set_xlim(-1.4, ncols + 0.2); ax.set_ylim(-1.4, 7.2); ax.set_aspect("equal")
    ax.set_anchor("W"); ax.axis("off")
    ax.set_title(S["d_heat"], fontsize=15, color=fg, weight="bold", loc="left", x=0)
    for i in (0, 2, 4):
        ax.text(-0.35, 6 - i + 0.5, S["wd"][i], ha="right", va="center",
                fontsize=8.5, color=fg, alpha=0.85)
    # legend: Less ▢▢▢▢ More
    ax.text(0, -0.9, S["d_less"], ha="left", va="center", fontsize=8.5, color=fg, alpha=0.85)
    for k in range(4):
        t = (k + 1) / 4
        ax.add_patch(plt.Rectangle((0.9 + k * 0.55, -1.18), 0.42, 0.42,
                     facecolor=empty * (1 - t) + acc * t, edgecolor="none"))
    ax.text(0.9 + 4 * 0.55 + 0.05, -0.9, S["d_more"], ha="left", va="center",
            fontsize=8.5, color=fg, alpha=0.85)


def _streak(daily):
    """Longest run of consecutive calendar days with usage."""
    days = sorted(date.fromisoformat(r["date"]) for r in daily if r["totalTokens"] > 0)
    best = run = 0
    prev = None
    for d in days:
        run = run + 1 if prev and (d.toordinal() - prev.toordinal() == 1) else 1
        best = max(best, run); prev = d
    return best


def _stat_tiles(ax, daily, st, S, fg):
    """Four Wrapped-flavored summary tiles next to the heatmap."""
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    active = sum(1 for r in daily if r["totalTokens"] > 0)
    peak = max(daily, key=lambda r: r["totalTokens"])
    wd_tok = defaultdict(float)
    for r in daily:
        wd_tok[date.fromisoformat(r["date"]).weekday()] += r["totalTokens"]
    busy_wd = max(wd_tok, key=wd_tok.get) if wd_tok else 0
    avg = sum(r["totalTokens"] for r in daily) / max(len(daily), 1)
    tiles = [(str(active), S["d_active"]),
             (S["d_streak_u"].format(v=_streak(daily)), S["d_streak"]),
             (S["wd"][busy_wd], S["d_busy"]),
             (fmt_tok(avg), S["d_avgday"])]
    dark = st["text"] == "dark"
    panel = "#00000012" if dark else "#FFFFFF1C"
    ec = "#15131F22" if dark else "#FFFFFF33"
    for i, (big, lab) in enumerate(tiles):
        cx = 0.27 + (i % 2) * 0.46
        cy = 0.72 - (i // 2) * 0.5
        ax.add_patch(FancyBboxPatch((cx - 0.21, cy - 0.18), 0.42, 0.36,
                     boxstyle="round,pad=0.01,rounding_size=0.05",
                     linewidth=1.1, edgecolor=ec, facecolor=panel, zorder=3))
        ax.text(cx, cy + 0.05, big, ha="center", va="center", fontsize=21,
                color=st["accent"], weight="bold", zorder=4)
        ax.text(cx, cy - 0.10, lab, ha="center", va="center", fontsize=11,
                color=fg, alpha=0.9, zorder=4)


def render_dashboard(data, st, S, L, title, out):
    daily, tot = data["daily"], data["totals"]
    if not daily or tot["totalTokens"] <= 0:
        print("[skip] no data for dashboard"); return
    dates = [r["date"][5:] for r in daily]; x = range(len(dates))
    dark = st["text"] == "dark"
    fg = "#1A1A22" if dark else "#EDEAF6"
    face = st["bg"][0]; barc = st["bars"]
    grid_c = (fg + "22") if len(fg) == 7 else fg
    panel = "#00000010" if dark else "#FFFFFF14"
    line_c = st["accent"]

    mc = model_costs(daily)
    models = list(mc)
    palette = ["#3775BA", "#42949E", "#9A4D8E", "#8BCF8B", "#E08E45", "#CFCECE"]
    cmap = {m: palette[i % len(palette)] for i, m in enumerate(models)}

    plt.rcParams.update({
        "axes.edgecolor": fg, "axes.labelcolor": fg, "text.color": fg,
        "xtick.color": fg, "ytick.color": fg, "axes.spines.top": False,
        "axes.spines.right": False, "axes.linewidth": 1.4,
        "grid.color": grid_c, "grid.alpha": 0.35,
    })
    fig = plt.figure(figsize=(16, 11), dpi=120)
    bg = fig.add_axes([0, 0, 1, 1]); bg.axis("off")
    bg.imshow(gradient_img(st["bg"]), extent=[0, 1, 0, 1], aspect="auto",
              origin="lower", zorder=-5)
    gs = fig.add_gridspec(3, 2, height_ratios=[1.25, 0.55, 1.05],
                          hspace=0.42, wspace=0.2,
                          left=0.065, right=0.93, top=0.9, bottom=0.07)

    def style_ax(a):
        a.set_facecolor(panel); a.grid(axis="y", linewidth=0.8)
        for s in a.spines.values(): s.set_alpha(0.5)

    # row 0: daily tokens + cumulative cost
    ax1 = fig.add_subplot(gs[0, :]); style_ax(ax1)
    ax1.bar(x, [r["totalTokens"] for r in daily], color=barc, width=0.74,
            label=S["d_daily"], zorder=3)
    ax1.set_ylabel(S["d_tokday"]); ax1.yaxis.set_major_formatter(FuncFormatter(fmt_tok))
    ax1.set_xticks(list(x)); ax1.set_xticklabels(dates, rotation=60, ha="right", fontsize=9)
    ax1.set_title(title, fontsize=19, pad=12, color=st["accent"], weight="bold")
    ax1b = ax1.twinx(); ax1b.set_facecolor("none"); ax1b.spines["top"].set_visible(False)
    ax1b.grid(False)
    cum, s = [], 0
    for r in daily: s += r["totalCost"]; cum.append(s)
    ax1b.plot(x, cum, color=line_c, lw=2.8, marker="o", ms=4, label=S["d_cumcost"],
              zorder=5)
    ax1b.set_ylabel("Cumulative $", color=line_c); ax1b.tick_params(axis="y", colors=line_c)
    ax1b.set_ylim(bottom=0)
    h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax1b.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=12,
               facecolor=face, edgecolor="none", labelcolor=fg)

    # row 1: contribution heatmap (left) + summary tiles (right)
    axh = fig.add_subplot(gs[1, 0])
    _heatmap(axh, daily, st, S, fg, face)
    axs = fig.add_subplot(gs[1, 1])
    _stat_tiles(axs, daily, st, S, fg)

    # row 2 left: daily cost by model (stacked)
    ax2 = fig.add_subplot(gs[2, 0]); style_ax(ax2)
    bottom = [0.0] * len(daily)
    for m in models:
        vals = [sum(b["cost"] for b in r["modelBreakdowns"] if b["modelName"] == m)
                for r in daily]
        ax2.bar(x, vals, bottom=bottom, color=cmap[m], width=0.74,
                label=short_model(m), zorder=3)
        bottom = [aa + bb for aa, bb in zip(bottom, vals)]
    ax2.set_ylabel(S["d_costday"])
    ax2.set_xticks(list(x)); ax2.set_xticklabels(dates, rotation=60, ha="right", fontsize=8)
    ax2.set_title(S["d_cost_model"], fontsize=15, color=fg, weight="bold")
    ax2.legend(fontsize=10, loc="upper left", facecolor=face, edgecolor="none",
               labelcolor=fg)

    # row 2 right: cost share by model
    ax3 = fig.add_subplot(gs[2, 1]); style_ax(ax3); ax3.grid(False)
    vals = [mc[m] for m in models]; ypos = range(len(models))
    ax3.barh(list(ypos), vals, color=[cmap[m] for m in models], zorder=3)
    ax3.set_yticks(list(ypos)); ax3.set_yticklabels([short_model(m) for m in models],
                                                    fontsize=11)
    ax3.invert_yaxis(); ax3.set_xlabel(S["d_total"])
    ax3.set_title(S["d_share"], fontsize=15, color=fg, weight="bold")
    tc = tot["totalCost"] or 1
    for i, v in zip(ypos, vals):
        ax3.text(v, i, f"  ${v:,.0f} ({v/tc*100:.0f}%)", va="center", fontsize=10, color=fg)
    ax3.set_xlim(right=max(vals) * 1.28 if vals else 1)

    crp = tot["cacheReadTokens"] / tot["totalTokens"] * 100 if tot["totalTokens"] else 0
    cap = S["d_cap"].format(tk=fmt_tok(tot["totalTokens"]), c=tot["totalCost"],
                            n=len(daily), s=daily[0]["date"], e=daily[-1]["date"],
                            cr=fmt_tok(tot["cacheReadTokens"]), crp=crp,
                            o=fmt_tok(tot["outputTokens"]))
    fig.text(0.5, 0.955, cap, ha="center", fontsize=12.5, color=fg)

    fig.savefig(f"{out}.png", dpi=300, bbox_inches="tight", facecolor=face)
    fig.savefig(f"{out}.pdf", bbox_inches="tight", facecolor=face)
    plt.close(fig)
    print(f"dashboard -> {out}.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--what", default="both", choices=["both", "poster", "dashboard"])
    ap.add_argument("--lang", default="en", choices=["en", "zh"])
    ap.add_argument("--style", default="cyber_purple")
    ap.add_argument("--template", default="wrapped",
                    choices=["wrapped", "minimal", "business", "playful",
                             "terminal", "receipt"],
                    help="poster layout language (orthogonal to --style colors)")
    ap.add_argument("--size", default="poster", choices=["poster", "story", "square"])
    ap.add_argument("--font", default=None, help="preferred font family for all text")
    ap.add_argument("--no-fun", action="store_true")
    ap.add_argument("--coffee-price", type=float, default=5.0)
    ap.add_argument("--title", default=None)
    ap.add_argument("--subtitle", default=None)
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--bg"); ap.add_argument("--accent")
    ap.add_argument("--bars"); ap.add_argument("--text", choices=["light", "dark"])
    a = ap.parse_args()

    S = STR[a.lang]
    cjk = find_cjk()
    if a.lang == "zh" and not cjk and not a.font:
        print("[warn] no CJK font found; Chinese text may render as boxes. "
              "Install fonts-noto-cjk, pass --font, or use --lang en.")
    fam = ([a.font] if a.font else []) + ([cjk] if cjk else []) + ["DejaVu Sans"]
    plt.rcParams["font.family"] = fam
    plt.rcParams["axes.unicode_minus"] = False

    st = load_style(a.style, a)
    L = LAYOUTS[a.size]

    data = json.load(open(a.data))
    if not data.get("daily"):
        print("[error] no usage data in", a.data, "- nothing to render."); return
    rng = data["range"]
    title = a.title or S["title"]
    dw = ("天" if a.lang == "zh" else ("day" if rng["days"] == 1 else "days"))
    sub = a.subtitle or S["sub"].format(t=f"{data['totals']['totalTokens']:,} tokens",
                                        d=rng["days"], dw=dw)
    fun = not a.no_fun
    os.makedirs(a.out_dir, exist_ok=True)

    TEMPLATES = {"minimal": tpl_minimal, "business": tpl_business,
                 "playful": tpl_playful, "terminal": tpl_terminal,
                 "receipt": tpl_receipt}
    if a.what in ("both", "poster"):
        out = os.path.join(a.out_dir, "token_wrapped")
        if a.template == "wrapped":
            render_poster(data, st, S, a.lang, L, title, sub, fun, a.coffee_price, out)
        else:
            m = derive(data, a.coffee_price)
            TEMPLATES[a.template](data, st, S, a.lang, L, m, title, sub, fun, out)
    if a.what in ("both", "dashboard"):
        render_dashboard(data, st, S, L, a.title or S["d_title"],
                         os.path.join(a.out_dir, "token_dashboard"))


if __name__ == "__main__":
    main()
