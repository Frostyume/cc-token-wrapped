#!/usr/bin/env python3
"""Generate a synthetic merged_usage.json (no real account data) so the repo can
ship example posters/dashboards. Deterministic — no randomness, no network."""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"]
# per-1M output-token cost stand-ins, purely for a believable demo
RATE = {"claude-opus-4-8": 75.0, "claude-sonnet-4-6": 15.0, "claude-haiku-4-5": 4.0}
START_DAY = 1  # 2026-03-DD


def day(i):
    # a believable wave: ramps up, peaks mid-month, tapers off
    base = 6e6 + 9e6 * (math.sin(i / 4.0) ** 2) + 5e6 * math.exp(-((i - 11) ** 2) / 40)
    out = int(base * 0.012) + 1500
    cache_read = int(base * 9.2)
    cache_create = int(base * 0.55)
    inp = int(base * 0.004) + 80
    total = inp + out + cache_read + cache_create
    # split across models by a fixed daily-shifting weight
    w = [0.55 + 0.1 * math.sin(i / 3), 0.30, 0.15]
    w = [x / sum(w) for x in w]
    mbs, cost = [], 0.0
    for m, frac in zip(MODELS, w):
        o = int(out * frac)
        c = round(o / 1e6 * RATE[m] + cache_read * frac / 1e6 * RATE[m] * 0.022, 4)
        cost += c
        mbs.append(dict(modelName=m, inputTokens=int(inp * frac),
                        outputTokens=o, cacheCreationTokens=int(cache_create * frac),
                        cacheReadTokens=int(cache_read * frac), cost=c))
    return dict(date=f"2026-03-{START_DAY+i:02d}", inputTokens=inp, outputTokens=out,
                cacheCreationTokens=cache_create, cacheReadTokens=cache_read,
                totalTokens=total, totalCost=round(cost, 4),
                modelBreakdowns=mbs, modelsUsed=MODELS)


def main():
    daily = [day(i) for i in range(28)]
    fields = ["inputTokens", "outputTokens", "cacheCreationTokens",
              "cacheReadTokens", "totalTokens"]
    totals = {f: sum(d[f] for d in daily) for f in fields}
    totals["totalCost"] = round(sum(d["totalCost"] for d in daily), 4)
    out = {"range": {"start": daily[0]["date"], "end": daily[-1]["date"],
                     "days": len(daily)},
           "sources": ["synthetic-demo"], "daily": daily, "totals": totals}
    p = os.path.join(HERE, "sample_usage.json")
    json.dump(out, open(p, "w"), ensure_ascii=False, indent=2)
    print("wrote", p, "| total tokens:", f"{totals['totalTokens']:,}",
          "| cost: $%.0f" % totals["totalCost"])


if __name__ == "__main__":
    main()
