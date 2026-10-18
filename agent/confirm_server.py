#!/usr/bin/env python3
"""Human-in-the-loop confirmation UI (stdlib only, no daemon).

    python -m agent.confirm_server --port 8077

Open http://localhost:8077/ while a `--confirm-mode manual` run is blocked.
Pending gated actions appear with Approve / Reject buttons; the run resumes the
moment a decision is written. The same page has an EMERGENCY STOP that creates
runtime/ESTOP, which every primitive checks before acting.
"""
from __future__ import annotations

import argparse
import json
import pathlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUEUE = ROOT / "runtime" / "confirm"
ESTOP = ROOT / "runtime" / "ESTOP"

PAGE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>Agentic Robotics · 人机确认</title>
<meta http-equiv="refresh" content="2">
<style>
 body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
      background:#0f1115;color:#e8eaed;margin:0;padding:32px}}
 h1{{font-size:20px;font-weight:600;letter-spacing:.2px;margin:0 0 4px}}
 .sub{{color:#8a8f98;font-size:13px;margin-bottom:24px}}
 .card{{background:#171a21;border:1px solid #232833;border-radius:10px;padding:18px;margin-bottom:14px}}
 .act{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#7ee787;font-size:15px}}
 .det{{color:#9aa4b2;font-size:13px;margin-top:8px;white-space:pre-wrap}}
 .row{{display:flex;gap:10px;margin-top:14px}}
 button{{border:0;border-radius:7px;padding:9px 18px;font-size:14px;font-weight:600;cursor:pointer}}
 .ok{{background:#238636;color:#fff}} .no{{background:#da3633;color:#fff}}
 .stop{{background:#8b0000;color:#fff;padding:12px 22px;font-size:15px}}
 .estop{{border:1px solid #f85149;color:#f85149;border-radius:10px;padding:14px 18px;margin-bottom:24px;
        display:flex;justify-content:space-between;align-items:center}}
 .idle{{color:#8a8f98;font-size:14px}}
 .badge{{display:inline-block;background:#30363d;border-radius:20px;padding:3px 10px;font-size:12px;color:#c9d1d9}}
</style></head><body>
<h1>Agentic Robotics · 人机确认面板</h1>
<div class="sub">运行中的 Agent 在危险动作前会阻塞在此，等待人工批准 · 每 2 秒刷新</div>
<div class="estop"><div><b>急停</b> <span class="badge">{estop_badge}</span></div>
  <form method="post" action="/estop">{estop_button}</form></div>
{cards}
</body></html>"""

CARD = """<div class="card">
  <div class="act">{action}</div>
  <div class="det">{details}</div>
  <div class="row">
    <form method="post" action="/decide"><input type="hidden" name="id" value="{id}">
      <input type="hidden" name="decision" value="approve"><button class="ok">批准</button></form>
    <form method="post" action="/decide"><input type="hidden" name="id" value="{id}">
      <input type="hidden" name="decision" value="deny"><button class="no">拒绝</button></form>
  </div>
  <div class="det">request {id} · {age}s</div>
</div>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        return

    def _send(self, body: str, code: int = 200, ctype: str = "text/html; charset=utf-8"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        import time
        QUEUE.mkdir(parents=True, exist_ok=True)
        reqs = sorted(QUEUE.glob("*.request.json"), key=lambda p: p.stat().st_mtime)
        cards = []
        for r in reqs:
            try:
                d = json.loads(r.read_text())
            except json.JSONDecodeError:
                continue
            cards.append(CARD.format(
                action=d.get("action", "?"),
                details=json.dumps(d.get("details", {}), ensure_ascii=False, indent=2),
                id=d.get("id", r.stem.split(".")[0]),
                age=int(time.time() - d.get("created", time.time()))))
        stopped = ESTOP.exists()
        page = PAGE.format(
            cards="\n".join(cards) or '<div class="card idle">当前没有待确认动作 —— Agent 正在自主执行。</div>',
            estop_badge="<b style='color:#f85149'>已触发</b>" if stopped else "正常",
            estop_button='<button class="stop">解除急停</button>' if stopped
                         else '<button class="stop">急停</button>')
        self._send(page)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode())
        path = urlparse(self.path).path
        if path == "/estop":
            if ESTOP.exists():
                ESTOP.unlink()
            else:
                ESTOP.parent.mkdir(parents=True, exist_ok=True)
                ESTOP.write_text("ui")
        elif path == "/decide":
            rid = (form.get("id") or [""])[0]
            decision = (form.get("decision") or ["deny"])[0]
            if rid:
                (QUEUE / f"{rid}.decision.json").write_text(
                    json.dumps({"id": rid, "decision": decision}))
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Content-Length", "0")
        self.end_headers()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8077)
    args = ap.parse_args()
    QUEUE.mkdir(parents=True, exist_ok=True)
    print(f"confirmation UI: http://localhost:{args.port}/  (queue: {QUEUE})")
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()
