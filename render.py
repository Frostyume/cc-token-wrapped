#!/usr/bin/env python3
"""Render a shareable 'Token Wrapped' poster and/or a multi-panel dashboard
from a merged usage JSON produced by collect.py.

Usage:
  render.py --data merged_usage.json [--what both|poster|dashboard]
            [--lang en|zh] [--style NAME|custom] [--no-fun]
            [--title "..."] [--subtitle "..."] [--out-dir DIR]
            [--coffee-price 5.0]
            # custom style overrides (hex), used when --style custom:
            [--bg "#100C2E,#561C78,#C8326E"] [--accent "#FFD86B"]
            [--bars "#FFD86B"] [--text light|dark]

Presets: cyber_purple neon_night blue_gold cyber_green minimal_white
"""
import argparse
import json
import os
from collections import defaultdict

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
}

# ---- i18n ----------------------------------------------------------------
STR = {
    "en": {
        "tag": "✦  MY CLAUDE CODE WRAPPED  ✦",
        "title": "My Token Usage",
        "rhythm": "daily rhythm",
        "cost": "Total spent", "cost_fun": "Total spent (≈ {c:,.0f} lattes)",
        "novels": "≈ {n:,.0f} novels written", "output": "{v} output tokens",
        "peak": "Peak day ({d})", "avg": "Avg per day",
        "fun_line": "★  ≈ {h:,.0f} hours of nonstop reading  ★",
        "sub": "{t:,} tokens  ·  {d} {dw} with Claude",
        "powered": "Powered by Claude Code",
        "d_title": "My Token Usage", "d_daily": "tokens / day",
        "d_cumcost": "cumulative cost", "d_cost_model": "Daily cost by model",
        "d_share": "Cost share by model", "d_total": "total cost ($)",
        "d_tokday": "tokens / day", "d_costday": "cost / day ($)",
        "d_cap": ("Total {tk} tokens · ${c:,.0f} · {n} days "
                  "({s}→{e})  |  cache read {cr} ({crp:.0f}%) · output {o}"),
    },
    "zh": {
        "tag": "✦  MY CLAUDE CODE WRAPPED  ✦",
        "title": "我的 Token 用量报告",
        "rhythm": "每日用量节奏",
        "cost": "总花费", "cost_fun": "总花费 (≈ {c:,.0f} 杯咖啡)",
        "novels": "≈ 写了 {n:,.0f} 本小说", "output": "{v} 输出 token",
        "peak": "单日峰值 ({d})", "avg": "平均每天",
        "fun_line": "★  ≈ 连续阅读 {h:,.0f} 小时  ★",
        "sub": "{t:,} tokens  ·  {d} {dw}和 Claude 相伴",
        "powered": "Powered by Claude Code",
        "d_title": "我的 Token 用量报告", "d_daily": "每日 token",
        "d_cumcost": "累计成本", "d_cost_model": "每日成本 · 按模型",
        "d_share": "成本占比 · 按模型", "d_total": "总成本 ($)",
        "d_tokday": "Tokens / day", "d_costday": "Cost / day ($)",
        "d_cap": ("合计 {tk} tokens · ${c:,.0f} · {n} 天 "
                  "({s}→{e})  |  cache read {cr} ({crp:.0f}%) · output {o}"),
    },
}


def find_cjk():
    prefer = ["Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans SC",
              "WenQuanYi Zen Hei", "Microsoft YaHei", "PingFang SC", "SimHei"]
    have = {f.name for f in fm.fontManager.ttflist}
    for p in prefer:
        if p in have:
            return p
    return None


def hexlist(s):
    return [c.strip() for c in s.split(",") if c.strip()]


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


# ---- poster --------------------------------------------------------------
def render_poster(data, st, S, title, subtitle, fun, coffee_price, out):
    daily, tot, rng = data["daily"], data["totals"], data["range"]
    TOTAL, COST, NDAYS = tot["totalTokens"], tot["totalCost"], max(rng["days"], 1)
    if not daily or TOTAL <= 0:
        print("[skip] no data for poster"); return
    peak = max(daily, key=lambda r: r["totalTokens"])
    avg = TOTAL / NDAYS
    words = TOTAL * WORDS_PER_TOKEN
    novels = words / WORDS_PER_NOVEL
    read_hours = words / READING_WPM / 60
    coffees = COST / coffee_price if coffee_price > 0 else 0

    dark = st["text"] == "dark"
    WHITE = "#15131F" if dark else "#FFFFFF"
    DIM = "#5A5570" if dark else "#D8CFF0"
    FAINT = "#8A85A0" if dark else "#FFFFFFAA"
    GOLD = st["accent"]

    fig = plt.figure(figsize=(9, 12.5), dpi=120)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.imshow(gradient_img(st["bg"]), extent=[0, 1, 0, 1], aspect="auto",
              origin="lower", zorder=0)
    for (cx, cy), (col, a) in zip([(0.82, 0.88), (0.15, 0.30), (0.5, 0.6)], st["glows"]):
        ax.scatter([cx], [cy], s=9000, color=col, alpha=a, zorder=1, edgecolors="none")

    def T(x, y, s, size, color=WHITE, w="bold", a=1.0):
        ax.text(x, y, s, fontsize=size, color=color, weight=w, ha="center",
                va="center", zorder=5, alpha=a)

    T(0.5, 0.952, S["tag"], 15, GOLD)
    T(0.5, 0.923, title, 22, WHITE)

    big, unit = hero(TOTAL, "zh" if S is STR["zh"] else "en")
    T(0.5, 0.80, big, 150, WHITE)
    T(0.5, 0.695, unit, 27, GOLD)
    T(0.5, 0.648, subtitle, 17, DIM, w="normal")

    toks = np.array([r["totalTokens"] for r in daily], float)
    n = len(toks); mx = toks.max() if toks.size else 1
    norm = toks / mx if mx > 0 else toks
    xs = np.linspace(0.10, 0.90, n) if n > 1 else np.array([0.5])
    bw = min((0.80 / max(n, 1)) * 0.62, 0.045)  # cap so few-day posters stay tidy
    by0, bh = 0.46, 0.14
    for xi, h in zip(xs, norm):
        for a, wmul in [(0.22, 2.4), (1.0, 1.0)]:
            ax.add_patch(FancyBboxPatch((xi - bw * wmul / 2, by0), bw * wmul,
                         h * bh + (0.02 if a < 1 else 0),
                         boxstyle="round,pad=0,rounding_size=0.006",
                         linewidth=0, facecolor=st["bars"], alpha=a, zorder=4))
    T(0.5, 0.435, S["rhythm"], 13, DIM, w="normal")

    def chip(cx, cy, big_s, small, sym):
        w, hgt = 0.40, 0.105
        ec = "#15131F22" if dark else "#FFFFFF40"
        fc = "#15131F0D" if dark else "#FFFFFF1A"
        ax.add_patch(FancyBboxPatch((cx - w / 2, cy - hgt / 2), w, hgt,
                     boxstyle="round,pad=0.006,rounding_size=0.02",
                     linewidth=1.2, edgecolor=ec, facecolor=fc, zorder=4))
        T(cx, cy + 0.022, f"{sym} {big_s}", 26, WHITE)
        T(cx, cy - 0.028, small, 13.5, DIM, w="normal")

    cy1, cy2 = 0.345, 0.225
    cost_small = S["cost_fun"].format(c=coffees) if fun else S["cost"]
    chip(0.29, cy1, f"${COST:,.0f}", cost_small, "☕")
    if fun:
        chip(0.71, cy1, f"{novels:,.0f}", S["novels"].format(n=novels), "◆")
    else:
        chip(0.71, cy1, fmt_tok(tot["outputTokens"]),
             S["output"].format(v=fmt_tok(tot["outputTokens"])), "◆")
    chip(0.29, cy2, fmt_tok(peak["totalTokens"]), S["peak"].format(d=peak["date"][5:]), "▲")
    chip(0.71, cy2, fmt_tok(avg), S["avg"], "⚡")

    if fun:
        T(0.5, 0.135, S["fun_line"].format(h=read_hours), 18, GOLD)
    T(0.5, 0.075, f"{rng['start']}  →  {rng['end']}", 15, DIM, w="normal")
    T(0.5, 0.045, S["powered"], 12.5, FAINT, w="normal")

    face = st["bg"][0]
    fig.savefig(f"{out}.png", dpi=200, facecolor=face)
    fig.savefig(f"{out}.pdf", facecolor=face)
    plt.close(fig)
    print(f"poster -> {out}.png")


# ---- dashboard -----------------------------------------------------------
def render_dashboard(data, st, S, title, out):
    daily, tot = data["daily"], data["totals"]
    if not daily or tot["totalTokens"] <= 0:
        print("[skip] no data for dashboard"); return
    dates = [r["date"][5:] for r in daily]; x = range(len(dates))
    dark = st["text"] == "dark"
    fg = "#222" if dark else "#EDEAF6"
    face = st["bg"][0]; barc = st["bars"]

    model_cost = defaultdict(float)
    for r in daily:
        for m in r["modelBreakdowns"]:
            model_cost[m["modelName"]] += m["cost"]
    models = sorted(model_cost, key=model_cost.get, reverse=True)
    palette = ["#3775BA", "#42949E", "#9A4D8E", "#8BCF8B", "#E08E45", "#CFCECE"]
    cmap = {m: palette[i % len(palette)] for i, m in enumerate(models)}

    plt.rcParams.update({
        "axes.edgecolor": fg, "axes.labelcolor": fg, "text.color": fg,
        "xtick.color": fg, "ytick.color": fg, "axes.spines.top": False,
        "axes.spines.right": False, "axes.linewidth": 1.6,
    })
    fig = plt.figure(figsize=(16, 9), dpi=120, facecolor=face)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1], hspace=0.34, wspace=0.22,
                          left=0.07, right=0.94, top=0.88, bottom=0.09)

    ax1 = fig.add_subplot(gs[0, :]); ax1.set_facecolor(face)
    ax1.bar(x, [r["totalTokens"] for r in daily], color=barc, width=0.72, label=S["d_daily"])
    ax1.set_ylabel(S["d_tokday"]); ax1.yaxis.set_major_formatter(FuncFormatter(fmt_tok))
    ax1.set_xticks(list(x)); ax1.set_xticklabels(dates, rotation=60, ha="right", fontsize=9)
    ax1.set_title(title, fontsize=18, pad=12, color=fg, weight="bold")
    ax1b = ax1.twinx(); ax1b.set_facecolor("none"); ax1b.spines["top"].set_visible(False)
    cum, s = [], 0
    for r in daily: s += r["totalCost"]; cum.append(s)
    ax1b.plot(x, cum, color="#E9573F", lw=2.6, marker="o", ms=4, label=S["d_cumcost"])
    ax1b.set_ylabel("Cumulative $", color="#E9573F"); ax1b.tick_params(axis="y", colors="#E9573F")
    ax1b.set_ylim(bottom=0)
    h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax1b.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=12,
               facecolor=face, edgecolor="none", labelcolor=fg)

    ax2 = fig.add_subplot(gs[1, 0]); ax2.set_facecolor(face)
    bottom = [0.0] * len(daily)
    for m in models:
        vals = [sum(b["cost"] for b in r["modelBreakdowns"] if b["modelName"] == m)
                for r in daily]
        ax2.bar(x, vals, bottom=bottom, color=cmap[m], width=0.72,
                label=m.replace("claude-", ""))
        bottom = [a + b for a, b in zip(bottom, vals)]
    ax2.set_ylabel(S["d_costday"])
    ax2.set_xticks(list(x)); ax2.set_xticklabels(dates, rotation=60, ha="right", fontsize=8)
    ax2.set_title(S["d_cost_model"], fontsize=15, color=fg, weight="bold")
    ax2.legend(fontsize=10, loc="upper left", facecolor=face, edgecolor="none", labelcolor=fg)

    ax3 = fig.add_subplot(gs[1, 1]); ax3.set_facecolor(face)
    vals = [model_cost[m] for m in models]; ypos = range(len(models))
    ax3.barh(list(ypos), vals, color=[cmap[m] for m in models])
    ax3.set_yticks(list(ypos)); ax3.set_yticklabels([m.replace("claude-", "") for m in models],
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
    fig.text(0.5, 0.945, cap, ha="center", fontsize=12.5, color=fg)

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
    if a.lang == "zh" and not cjk:
        print("[warn] no CJK font found; Chinese text may render as boxes. "
              "Install fonts-noto-cjk or use --lang en.")
    plt.rcParams["font.family"] = ([cjk] if cjk else []) + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    if a.style == "custom":
        st = dict(bg=hexlist(a.bg or "#100C2E,#561C78,#C8326E"),
                  accent=a.accent or "#FFD86B", bars=a.bars or (a.accent or "#FFD86B"),
                  text=a.text or "light",
                  glows=[(a.accent or "#FFD86B", 0.16),
                         (a.bars or "#5D9BFF", 0.14), ("#FFFFFF", 0.06)])
    else:
        st = STYLES.get(a.style, STYLES["cyber_purple"])

    data = json.load(open(a.data))
    if not data.get("daily"):
        print("[error] no usage data in", a.data, "- nothing to render."); return
    rng = data["range"]
    title = a.title or S["title"]
    dw = ("天" if a.lang == "zh" else ("day" if rng["days"] == 1 else "days"))
    sub = a.subtitle or S["sub"].format(t=data["totals"]["totalTokens"],
                                        d=rng["days"], dw=dw)
    fun = not a.no_fun
    os.makedirs(a.out_dir, exist_ok=True)

    if a.what in ("both", "poster"):
        render_poster(data, st, S, title, sub, fun, a.coffee_price,
                      os.path.join(a.out_dir, "token_wrapped"))
    if a.what in ("both", "dashboard"):
        render_dashboard(data, st, S, a.title or S["d_title"],
                         os.path.join(a.out_dir, "token_dashboard"))


if __name__ == "__main__":
    main()
