#!/usr/bin/env python3
"""Stage 5 — failure diagnosis: turn a failed trace into an actionable cause.

赛题 2.f: 运行日志与失败案例分析 (this is the module that produces them).
"""
from __future__ import annotations

import json
import pathlib

from agent import llm
from agent.prompts import diagnose_prompt

# Rule-based pre-pass: catches the failures we already understand, so the LLM is
# only asked about genuinely novel ones (and the report has a stable taxonomy).
TAXONOMY = [
    ("grasp_failed", "夹爪闭合时未夹到物体（拾取失败）",
     lambda ev: any(e.get("event") == "pick" and e.get("grasped") is False for e in ev)),
    ("placed_but_not_in_bin", "已移动但目标谓词不成立（放偏/弹出）",
     lambda ev: any(e.get("event") == "place" and e.get("success") is False for e in ev)),
    ("timeout", "episode 超出步数/时间上限",
     lambda ev: any(e.get("event") == "episode_end" and e.get("steps", 0) > 550 for e in ev)),
    ("safety_reject", "安全层拒绝动作（工作空间/位移超限）",
     lambda ev: any(e.get("event") == "reject_workspace" for e in ev)),
    ("confirm_denied", "人确认环节被拒",
     lambda ev: any("denied" in str(e.get("decision", "")) for e in ev)),
    ("crash", "进程异常退出（未完成 episode）",
     lambda ev: not any(e.get("event") == "episode_end" for e in ev)),
]


def classify(events: list[dict]) -> list[str]:
    return [name for name, _desc, pred in TAXONOMY if pred(events)]


def log_tail(episodes: list[dict], limit: int = 60) -> str:
    lines = []
    for ep in episodes[:3]:
        lines.append(f"--- task {ep.get('task_idx')} seed {ep.get('seed')} "
                     f"success={ep.get('success')} exit={ep.get('exit_code')} err={ep.get('error')}")
        for ev in ep.get("events", [])[-limit:]:
            lines.append("  " + json.dumps(ev, ensure_ascii=False)[:300])
    return "\n".join(lines)


def diagnose(episodes: list[dict], plan_summary_text: str, metrics_text: str,
             *, model: str | None = None) -> dict:
    events = [e for ep in episodes for e in ep.get("events", [])]
    labels = classify(events)
    try:
        d = llm.chat_json(
            diagnose_prompt(log_tail(episodes), plan_summary_text, metrics_text),
            model=model, max_tokens=1200, think=True)
        d.setdefault("taxonomy", labels)
        return d
    except Exception as e:  # noqa: BLE001 - never let a model glitch kill the run
        return {
            "root_cause": "LLM diagnosis unavailable: " + str(e)[:200],
            "evidence": [f"rule-based labels: {labels}"],
            "failure_stage": labels[0] if labels else "unknown",
            "fix_hint": "inspect run.log / trace.jsonl for the first failing phase",
            "severity": "unknown",
            "taxonomy": labels,
        }


def save(diag: dict, path: pathlib.Path) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(diag, ensure_ascii=False, indent=2) + "\n")
    return path


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("metrics")   # metrics.json from the verifier
    ap.add_argument("--out", default="runtime/diagnosis.json")
    args = ap.parse_args()
    data = json.loads(pathlib.Path(args.metrics).read_text())
    failed = [e for e in data["episodes"] if not e["success"]]
    diag = diagnose(failed, "n/a", json.dumps({k: data[k] for k in
                                              ("overall", "n", "per_task")}, ensure_ascii=False))
    save(diag, pathlib.Path(args.out))
    print(json.dumps(diag, ensure_ascii=False, indent=2))
