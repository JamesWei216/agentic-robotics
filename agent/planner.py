#!/usr/bin/env python3
"""Stage 1 — task understanding: natural-language task book -> plan.json.

赛题 2.b: 输入自然语言任务书，输出结构化计划（步骤、约束、风险点）.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

from agent import llm
from agent.prompts import planner_prompt
from agent.schemas import PlanError, plan_summary, validate_plan

ROOT = pathlib.Path(__file__).resolve().parent.parent


@dataclass
class PlanResult:
    plan: dict
    source: str            # "llm" | "fallback"
    attempts: int
    error: str | None = None


def _pair_desc(pair: dict) -> str:
    """One mission item -> human-readable line (sorting uses bin, stacking uses on)."""
    if pair.get("bin"):
        return f"{pair['object']} -> {pair['bin']}"
    if pair.get("on"):
        return f"{pair['object']} stacked on {pair['on']}"
    return str(pair)


def scene_hint(suite: str = "libero_bolt") -> str:
    """Ground the planner in the actual task protocol of the suite."""
    path = ROOT / "config" / "missions.json"
    if not path.exists():
        return ""
    data = json.loads(path.read_text()).get(suite, {})
    lines = [f"SUITE `{suite}` — {len(data)} tasks; each episode requires:"]
    for idx, pairs in list(data.items())[:12]:
        desc = ", ".join(_pair_desc(p) for p in pairs) or "nothing"
        lines.append(f"  task {idx:>2}: {desc}")
    lines.append("At runtime the generated script must read R.todo() and handle every "
                 "item listed there, one object at a time (place it in the named bin, "
                 "or stack it on the named object).")
    return "\n".join(lines)


def _fallback_plan(taskbook: str, suite: str = "libero_bolt") -> dict:
    """Deterministic plan used when the LLM output cannot be validated.

    Keeps the pipeline runnable: the plan still carries steps / constraints /
    risks, just authored by a template instead of the model. There is one
    template per task type (sorting / stacking) selected by the suite name.
    """
    if suite.startswith("libero_wood_stack"):
        return _fallback_stack_plan(taskbook)
    return {
        "task": {
            "name": "bolt sorting (fallback plan)",
            "goal": "Sort every bolt listed by R.todo() into its designated parts bin.",
            "success_criteria": [
                "In(bolt, bin) holds for every pair returned by R.todo()",
                "robot returns to the home pose after the last placement",
            ],
        },
        "scene": {
            "objects": ["bolt_small_1", "bolt_large_1", "parts_bin_blue_1", "parts_bin_red_1"],
            "targets": {"bolt_small_1": "parts_bin_blue_1", "bolt_large_1": "parts_bin_red_1"},
            "workcell": "LIBERO tabletop, Franka Panda + parallel jaw, table z=0.90 m",
        },
        "steps": [
            {"id": 1, "op": "settle", "args": {"steps": 30},
             "purpose": "lying bolts sink ~13 mm in the first frames; grasp pose must be read after settling",
             "on_failure": "abort episode, report scene instability"},
            {"id": 2, "op": "scan", "args": {"category": "bolt"},
             "purpose": "confirm which bolts are present", "on_failure": "fall back to R.todo()"},
            {"id": 3, "op": "pick_and_place", "args": {"object": "bolt_small_1", "bin": "parts_bin_blue_1"},
             "purpose": "small bolt -> blue bin", "on_failure": "log grasp failure and retry once"},
            {"id": 4, "op": "pick_and_place", "args": {"object": "bolt_large_1", "bin": "parts_bin_red_1"},
             "purpose": "large bolt -> red bin", "on_failure": "log grasp failure and retry once"},
            {"id": 5, "op": "check", "args": {},
             "purpose": "verify the In() predicate", "on_failure": "report failure stage"},
            {"id": 6, "op": "home", "args": {}, "purpose": "leave the arm at a safe pose",
             "on_failure": "none"},
        ],
        "constraints": [
            {"id": "C1", "text": "end effector never below z=0.86 m", "enforced_by": "safety layer"},
            {"id": "C2", "text": "lift >= 100 mm before lateral motion", "enforced_by": "primitive pick"},
            {"id": "C3", "text": "carry speed <= 0.015 m/step (0.30 m/s at 20 Hz)", "enforced_by": "primitive move_to"},
            {"id": "C4", "text": "release within 30 mm of the bin cavity floor", "enforced_by": "primitive place"},
            {"id": "C5", "text": "one bolt at a time", "enforced_by": "plan structure"},
        ],
        "risks": [
            {"id": "R1", "text": "bolt still settling when the grasp point is computed",
             "mitigation": "settle(30) before every grasp", "detect": "grasp_ok == false"},
            {"id": "R2", "text": "hex head slips out of the vertical jaws",
             "mitigation": "grasp the shank, not the head", "detect": "grasp_ok == false"},
            {"id": "R3", "text": "large bolt exceeds the jaw travel",
             "mitigation": "slower descend + retry once", "detect": "place success == false"},
            {"id": "R4", "text": "part thrown out of the jaws by fast carry",
             "mitigation": "speed cap 0.015 m/step on transfer", "detect": "In() false"},
        ],
        "confirmations": [
            {"action": "first_motion", "when": "before the first motion after reset", "mode": "auto"},
            {"action": "grasp_close", "when": "before closing the jaws", "mode": "auto"},
            {"action": "release", "when": "before opening the jaws over the bin", "mode": "auto"},
        ],
        "metrics": ["success_rate", "cycle_steps", "confirmation_count", "repair_count"],
        "runtime_binding": "steps 3/4 are bound to R.todo() at runtime (single- or dual-object episodes)",
        "source_taskbook": taskbook[:120],
    }


def _fallback_stack_plan(taskbook: str) -> dict:
    """Deterministic plan for the stacking (码垛) suite."""
    return {
        "task": {
            "name": "wood block stacking (fallback plan)",
            "goal": "Stack every wooden block listed by R.todo() onto the block "
                    "named in the same item, building the required tower.",
            "success_criteria": [
                "On(top, base) holds for every pair returned by R.todo()",
                "robot returns to the home pose after the last placement",
            ],
        },
        "scene": {
            "objects": ["wood_block_1", "wood_block_2", "wood_block_3"],
            "targets": {"wood_block_2": "wood_block_1", "wood_block_3": "wood_block_2"},
            "workcell": "LIBERO tabletop, Franka Panda + parallel jaw, table z=0.90 m, "
                        "40 mm wooden cubes",
        },
        "steps": [
            {"id": 1, "op": "settle", "args": {"steps": 30},
             "purpose": "let the cubes settle after reset before any pose is read",
             "on_failure": "abort episode, report scene instability"},
            {"id": 2, "op": "scan", "args": {"category": "wood_block"},
             "purpose": "confirm which blocks are present", "on_failure": "fall back to R.todo()"},
            {"id": 3, "op": "pick_and_stack",
             "args": {"object": "wood_block_2", "on": "wood_block_1"},
             "purpose": "place the second block on the base block",
             "on_failure": "log grasp failure and retry once"},
            {"id": 4, "op": "pick_and_stack",
             "args": {"object": "wood_block_3", "on": "wood_block_2"},
             "purpose": "place the third block on top of the second",
             "on_failure": "log grasp failure and retry once"},
            {"id": 5, "op": "check", "args": {},
             "purpose": "verify the On() predicates", "on_failure": "report failure stage"},
            {"id": 6, "op": "home", "args": {}, "purpose": "leave the arm at a safe pose",
             "on_failure": "none"},
        ],
        "constraints": [
            {"id": "C1", "text": "end effector never below z=0.86 m", "enforced_by": "safety layer"},
            {"id": "C2", "text": "lift >= 100 mm before lateral motion", "enforced_by": "primitive place_on_top"},
            {"id": "C3", "text": "carry speed <= 0.015 m/step", "enforced_by": "primitive move_to"},
            {"id": "C4", "text": "release <= 10 mm above the target block top face", "enforced_by": "primitive place_on_top"},
            {"id": "C5", "text": "one block at a time, bottom-up order", "enforced_by": "plan structure + R.todo()"},
        ],
        "risks": [
            {"id": "R1", "text": "cube slips out of the parallel jaws during the carry",
             "mitigation": "grasp at centre height, lift slowly, 0.015 m/step cap",
             "detect": "grasp_ok == false / On() false"},
            {"id": "R2", "text": "stack placed more than 30 mm off centre -> On() never true",
             "mitigation": "descend in two stages with 0.008 m/step and settle 30 steps",
             "detect": "stack success == false"},
            {"id": "R3", "text": "tower topples after release",
             "mitigation": "release 10 mm above the top face, no lateral motion while descending",
             "detect": "On() false after the settle steps"},
            {"id": "R4", "text": "upper block pushed off when picking it next to a standing tower",
             "mitigation": "always approach from above; keep >= 100 mm clearance over the stack",
             "detect": "On() false for a pair that was already true"},
        ],
        "confirmations": [
            {"action": "first_motion", "when": "before the first motion after reset", "mode": "auto"},
            {"action": "grasp_close", "when": "before closing the jaws", "mode": "auto"},
            {"action": "release", "when": "before opening the jaws above the stack", "mode": "auto"},
        ],
        "metrics": ["success_rate", "cycle_steps", "confirmation_count", "repair_count"],
        "runtime_binding": "steps 3/4 are bound to R.todo() at runtime (2- or 4-placement episodes)",
        "source_taskbook": taskbook[:120],
    }


def make_plan(taskbook_path: str | pathlib.Path, *, suite: str = "libero_bolt",
              model: str | None = None, retries: int = 1) -> PlanResult:
    taskbook = pathlib.Path(taskbook_path).read_text()
    hint = scene_hint(suite)
    attempts = 0
    last_error = None
    for i in range(retries + 1):
        attempts += 1
        messages = planner_prompt(taskbook, hint)
        if last_error:
            messages.append({"role": "user", "content":
                             f"The previous plan failed validation: {last_error}. "
                             "Return a corrected plan that matches the schema exactly."})
        try:
            raw = llm.chat_json(messages, model=model, max_tokens=6000)
            return PlanResult(validate_plan(raw), "llm", attempts)
        except Exception as e:  # noqa: BLE001
            last_error = f"{type(e).__name__}: {e}"
    return PlanResult(_fallback_plan(taskbook, suite), "fallback", attempts, last_error)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("taskbook")
    ap.add_argument("--suite", default="libero_bolt")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    res = make_plan(args.taskbook, suite=args.suite)
    text = json.dumps(res.plan, ensure_ascii=False, indent=2)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n")
    print(f"source={res.source} attempts={res.attempts} error={res.error}")
    print(plan_summary(res.plan))
    print(text[:2000])
