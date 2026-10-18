"""Human-in-the-loop confirmation gate (赛题硬性要求: 人机确认机制).

Three modes, selected with $AGENT_CONFIRM_MODE:
  auto    - sim runs: approve immediately, but still record an audit entry
            (纯仿真不要求运动前确认，但机制必须存在且留痕)
  manual  - real robot: block until a human answers, either at the TTY or
            through the stdlib web UI in confirm_server.py
  deny    - everything needs explicit approval and there is none: used by
            regression tests to prove the gate really gates

Request/decision files live in runtime/confirm/*.json, so the web UI and the
blocking robot process only share a directory -- no sockets, no daemons.
"""
from __future__ import annotations

import getpass
import json
import os
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "runtime" / "confirm"
AUDIT = ROOT / "runtime" / "audit.jsonl"


def _audit(event: dict) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT.open("a") as f:
        f.write(json.dumps({"ts": time.time(),
                            "iso": time.strftime("%Y-%m-%dT%H:%M:%S"), **event},
                           ensure_ascii=False) + "\n")


class ConfirmationDenied(RuntimeError):
    """Raised when a human denies a gated action (or nobody answers)."""


class ConfirmGate:
    def __init__(self, mode: str | None = None, timeout_s: float = 300.0):
        self.mode = (mode or os.environ.get("AGENT_CONFIRM_MODE", "auto")).lower()
        self.timeout_s = float(os.environ.get("AGENT_CONFIRM_TIMEOUT", timeout_s))
        self.count = 0          # number of gated actions requested this episode
        self.approved = 0
        self.denied = 0

    # ------------------------------------------------------------------ public
    def require(self, action: str, details: dict | None = None) -> bool:
        self.count += 1
        details = details or {}
        rid = uuid.uuid4().hex[:12]
        if self.mode == "auto":
            self.approved += 1
            _audit({"event": "confirm", "decision": "auto_approved", "action": action,
                    "details": details, "request": rid})
            return True
        if self.mode == "deny":
            self.denied += 1
            _audit({"event": "confirm", "decision": "denied_by_policy", "action": action,
                    "details": details, "request": rid})
            raise ConfirmationDenied(f"{action}: policy=deny")

        decision = self._ask_human(rid, action, details)
        if decision == "approve":
            self.approved += 1
            _audit({"event": "confirm", "decision": "approved", "action": action,
                    "details": details, "request": rid})
            return True
        self.denied += 1
        _audit({"event": "confirm", "decision": decision, "action": action,
                "details": details, "request": rid})
        raise ConfirmationDenied(f"{action}: {decision}")

    # --------------------------------------------------------------- internals
    def _ask_human(self, rid: str, action: str, details: dict) -> str:
        QUEUE.mkdir(parents=True, exist_ok=True)
        req = QUEUE / f"{rid}.request.json"
        req.write_text(json.dumps({"id": rid, "action": action, "details": details,
                                   "created": time.time(),
                                   "summary": self._summary(action, details)},
                                  ensure_ascii=False, indent=2))
        try:
            if os.isatty(0):
                print(f"\n[CONFIRM] {self._summary(action, details)}")
                if action in ("first_motion", "grasp_close", "release", "estop_reset"):
                    print("  -> 危险动作，请确认现场安全")
                ans = input("  批准执行? [y/N] ").strip().lower()
                return "approve" if ans in ("y", "yes", "是") else "deny"
            # non-interactive: wait for the web UI / another process to decide
            dec = QUEUE / f"{rid}.decision.json"
            deadline = time.time() + self.timeout_s
            while time.time() < deadline:
                if dec.exists():
                    return json.loads(dec.read_text()).get("decision", "timeout")
                time.sleep(0.5)
            return "timeout"
        finally:
            for p in (req, QUEUE / f"{rid}.decision.json"):
                if p.exists() and p.name.endswith("decision.json"):
                    continue
                if p.exists():
                    p.unlink()

    @staticmethod
    def _summary(action: str, details: dict) -> str:
        who = (details or {}).get("object") or (details or {}).get("target") or ""
        extra = " ".join(f"{k}={v}" for k, v in (details or {}).items()
                         if k not in ("object", "target"))
        return f"{action} {who} {extra}".strip()


_GATE: ConfirmGate | None = None


def gate() -> ConfirmGate:
    global _GATE
    if _GATE is None:
        _GATE = ConfirmGate()
    return _GATE
