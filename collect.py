#!/usr/bin/env python3
"""Collect + merge Claude Code token usage from ccusage, filter by date range.

Usage:
  collect.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]
             [--extra-dir DIR] [--out FILE]

Data sources merged (summed per day, per model):
  1. `ccusage daily --json` on this machine.
  2. Every *.json under --extra-dir (default ~/.claude/ccusage_extra/),
     each being a `ccusage daily --json` dump from another machine.

Both ccusage schemas are accepted: entries keyed by `date` or by `period`.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict

TOK_FIELDS = ["inputTokens", "outputTokens", "cacheCreationTokens",
              "cacheReadTokens", "totalTokens"]
MB_FIELDS = ["inputTokens", "outputTokens", "cacheCreationTokens",
             "cacheReadTokens", "cost"]


def run_ccusage(offline=False, timeout=60):
    exe = shutil.which("ccusage")
    base = [exe, "daily", "--json"] if exe else ["npx", "ccusage@latest", "daily", "--json"]
    # ccusage fetches model pricing online by default and can hang on flaky
    # networks; retry with --offline (cached pricing) if the first call stalls.
    attempts = [base + (["--offline"] if offline else []), base + ["--offline"]]
    seen = []
    for cmd in attempts:
        if cmd in seen:
            continue
        seen.append(cmd)
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL,
                                          timeout=timeout)
            return json.loads(out)
        except subprocess.TimeoutExpired:
            print(f"[warn] ccusage timed out after {timeout}s; retrying --offline",
                  file=sys.stderr)
        except Exception as e:
            print(f"[warn] ccusage failed ({e}); trying --offline / extra-dir",
                  file=sys.stderr)
    print("[warn] ccusage unavailable on this machine; relying on --extra-dir only",
          file=sys.stderr)
    return {"daily": []}


def entry_date(e):
    return e.get("date") or e.get("period")


def load_json_days(obj):
    return {entry_date(e): e for e in obj.get("daily", []) if entry_date(e)}


def add_into(acc, e):
    """Sum one ccusage daily entry into the accumulator dict keyed by date."""
    dt = entry_date(e)
    rec = acc[dt]
    for f in TOK_FIELDS:
        rec[f] += e.get(f, 0)
    rec["totalCost"] += e.get("totalCost", 0)
    for m in e.get("modelBreakdowns", []):
        mb = rec["_models"][m["modelName"]]
        for k in MB_FIELDS:
            mb[k] += m.get(k, 0)


def new_rec():
    r = {f: 0 for f in TOK_FIELDS}
    r["totalCost"] = 0.0
    r["_models"] = defaultdict(lambda: {k: 0 for k in MB_FIELDS})
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--extra-dir",
                    default=os.path.expanduser("~/.claude/ccusage_extra"))
    ap.add_argument("--out", default="merged_usage.json")
    ap.add_argument("--offline", action="store_true",
                    help="use ccusage cached pricing (no network)")
    ap.add_argument("--ccusage-timeout", type=int, default=60)
    a = ap.parse_args()

    acc = defaultdict(new_rec)
    sources = []

    this_machine = run_ccusage(offline=a.offline, timeout=a.ccusage_timeout)
    if this_machine.get("daily"):
        sources.append("this-machine")
        for e in this_machine["daily"]:
            if entry_date(e):
                add_into(acc, e)

    if os.path.isdir(a.extra_dir):
        for fp in sorted(glob.glob(os.path.join(a.extra_dir, "*.json"))):
            try:
                obj = json.load(open(fp))
            except Exception as ex:
                print(f"[warn] skip {fp}: {ex}", file=sys.stderr)
                continue
            if "daily" not in obj:
                continue
            sources.append(os.path.basename(fp))
            for e in obj["daily"]:
                if entry_date(e):
                    add_into(acc, e)

    # range filter
    def in_range(dt):
        if a.start and dt < a.start:
            return False
        if a.end and dt > a.end:
            return False
        return True

    daily = []
    for dt in sorted(acc):
        if not in_range(dt):
            continue
        rec = acc[dt]
        models = rec.pop("_models")
        out = {"date": dt}
        for f in TOK_FIELDS:
            out[f] = rec[f]
        out["totalCost"] = round(rec["totalCost"], 6)
        out["modelBreakdowns"] = [dict(modelName=k, **{kk: (round(v[kk], 6)
                                  if kk == "cost" else v[kk]) for kk in MB_FIELDS})
                                  for k, v in sorted(models.items())]
        out["modelsUsed"] = sorted(models)
        daily.append(out)

    totals = {f: sum(r[f] for r in daily) for f in TOK_FIELDS}
    totals["totalCost"] = round(sum(r["totalCost"] for r in daily), 6)
    result = {
        "range": {"start": daily[0]["date"] if daily else a.start,
                  "end": daily[-1]["date"] if daily else a.end,
                  "days": len(daily)},
        "sources": sources,
        "daily": daily,
        "totals": totals,
    }
    json.dump(result, open(a.out, "w"), ensure_ascii=False, indent=2)

    print(f"sources merged : {', '.join(sources) or '(none)'}")
    print(f"days           : {len(daily)}"
          + (f"  ({daily[0]['date']} -> {daily[-1]['date']})" if daily else ""))
    print(f"total tokens   : {totals['totalTokens']:,}")
    print(f"total cost     : ${totals['totalCost']:,.2f}")
    print(f"written        : {a.out}")


if __name__ == "__main__":
    main()
