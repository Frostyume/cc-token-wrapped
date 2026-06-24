#!/usr/bin/env python3
"""One-shot convenience wrapper: collect usage then render in a single command.

    python wrapped.py --start 2026-06-01 --end 2026-06-24 \
                      --lang en --style cyber_purple --out-dir .

Any flag not consumed here is forwarded:
  collect flags  : --start --end --extra-dir --offline --ccusage-timeout
  render flags   : --lang --style --what --no-fun --coffee-price --title
                   --subtitle --bg --accent --bars --text
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECT_FLAGS = {"--start", "--end", "--extra-dir", "--offline", "--ccusage-timeout"}


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--out-dir", default=".")
    args, rest = ap.parse_known_args()
    os.makedirs(args.out_dir, exist_ok=True)
    merged = os.path.join(args.out_dir, "merged_usage.json")

    # split forwarded flags between collect and render
    collect_args, render_args, i = [], [], 0
    while i < len(rest):
        tok = rest[i]
        if tok == "--offline":
            collect_args.append(tok); i += 1; continue
        if tok in COLLECT_FLAGS:
            collect_args += rest[i:i + 2]; i += 2; continue
        render_args.append(tok); i += 1

    py = sys.executable
    subprocess.check_call([py, os.path.join(HERE, "collect.py"),
                           *collect_args, "--out", merged])
    subprocess.check_call([py, os.path.join(HERE, "render.py"),
                           "--data", merged, "--out-dir", args.out_dir, *render_args])


if __name__ == "__main__":
    main()
