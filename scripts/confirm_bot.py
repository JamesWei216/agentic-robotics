#!/usr/bin/env python3
"""Drive the human-confirmation web panel from the command line (demo/evidence).

Starts nothing itself: it polls http://127.0.0.1:PORT/ like a browser would,
snapshots the pending requests, and approves them through the same POST endpoint
the Approve button uses. Every snapshot is written to the output directory so the
report can show the panel state at each gated action.

    python scripts/confirm_bot.py --port 8077 --out runs/confirm_demo --timeout 240
"""
import argparse
import json
import pathlib
import re
import time
import urllib.parse
import urllib.request


def fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.read().decode("utf-8", "replace")


def post(url: str, data: dict) -> None:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except urllib.error.HTTPError:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8077)
    ap.add_argument("--out", default="runs/confirm_demo")
    ap.add_argument("--timeout", type=float, default=240)
    ap.add_argument("--decision", default="approve")
    args = ap.parse_args()

    base = f"http://127.0.0.1:{args.port}/"
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = []
    seen = set()
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        try:
            html = fetch(base)
        except Exception as exc:                      # panel not up yet
            time.sleep(1.0)
            continue
        ids = re.findall(r'name="id" value="([0-9a-f]+)"', html)
        actions = re.findall(r'<div class="act">([^<]+)</div>', html)
        if ids:
            (out / f"panel_{len(seen) + 1:02d}.html").write_text(html)
            for rid, act in zip(ids, actions):
                if rid in seen:
                    continue
                seen.add(rid)
                log.append({"t": time.time(), "id": rid, "action": act,
                            "decision": args.decision})
                post(base + "decide", {"id": rid, "decision": args.decision})
                print(f"  [operator] {act} -> {args.decision}")
                time.sleep(0.2)
        time.sleep(0.4)
        # stop once the run has finished writing episodes and nothing is pending
        if seen and not ids:
            break
    (out / "operator_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2))
    print(f"approved {len(log)} gated actions; snapshots in {out}")


if __name__ == "__main__":
    main()
