"""Safety layer: workspace limits, travel guard, e-stop, audit trail.

This module is deliberately boring and strict: every motion primitive calls
`Safety.guard_*` before issuing a command, and every refusal is written to
`runtime/audit.jsonl` so the report can prove the constraints were enforced
rather than merely documented.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "agent.json").read_text())["safety"]


class SafetyViolation(RuntimeError):
    """Raised when a commanded motion would violate a hard constraint."""


class Estop(RuntimeError):
    """Raised when the emergency stop is engaged."""


def _audit(event: dict) -> None:
    path = ROOT / CFG.get("audit_log", "runtime/audit.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": time.time(), "iso": time.strftime("%Y-%m-%dT%H:%M:%S"), **event}
    with path.open("a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


class Safety:
    def __init__(self):
        self.mode = os.environ.get("AGENT_CONFIRM_MODE", CFG.get("mode", "auto"))
        self.ws = CFG["workspace"]
        self.max_travel = CFG["max_travel_m"]
        self.estop_file = ROOT / CFG.get("estop_file", "runtime/ESTOP")
        self._last_pos = None

    # ------------------------------------------------------------------ e-stop
    def check_estop(self) -> None:
        if self.estop_file.exists():
            _audit({"event": "estop_engaged", "file": str(self.estop_file)})
            raise Estop(f"emergency stop engaged ({self.estop_file.name} present)")

    def set_estop(self, engaged: bool) -> None:
        if engaged:
            self.estop_file.parent.mkdir(parents=True, exist_ok=True)
            self.estop_file.write_text(time.strftime("%Y-%m-%dT%H:%M:%S"))
        elif self.estop_file.exists():
            self.estop_file.unlink()
        _audit({"event": "estop_set", "engaged": engaged})

    # --------------------------------------------------------------- workspace
    def guard_point(self, p, *, label: str = "target") -> None:
        self.check_estop()
        x, y, z = (float(v) for v in p)
        lo = {k: float(v[0]) for k, v in self.ws.items()}
        hi = {k: float(v[1]) for k, v in self.ws.items()}
        bad = [k for k, v in (("x", x), ("y", y), ("z", z)) if not (lo[k] <= v <= hi[k])]
        if bad:
            _audit({"event": "reject_workspace", "label": label, "point": [x, y, z],
                    "violated": bad, "bounds": self.ws})
            raise SafetyViolation(
                f"{label} {tuple(round(v, 3) for v in (x, y, z))} outside workspace "
                f"({'/'.join(bad)}); bounds={self.ws}")

    def guard_travel(self, p_from, p_to) -> None:
        d = sum((float(b) - float(a)) ** 2 for a, b in zip(p_from, p_to)) ** 0.5
        if d > self.max_travel:
            _audit({"event": "reject_travel", "distance_m": round(d, 3),
                    "limit_m": self.max_travel})
            raise SafetyViolation(f"single move of {d:.3f} m exceeds {self.max_travel} m")

    def note_position(self, p) -> None:
        self._last_pos = tuple(float(v) for v in p)

    def guard_motion(self, p_to, *, label: str = "move") -> None:
        self.guard_point(p_to, label=label)
        if self._last_pos is not None:
            self.guard_travel(self._last_pos, p_to)
        else:
            self.note_position(p_to)

    # ------------------------------------------------------------------ events
    @staticmethod
    def audit(event: dict) -> None:
        _audit(event)
