#!/usr/bin/env python3
"""Verbose single-episode probe for the multi-part (variant) suite.

Runs the generated task code for one (task, seed) with AGENT_RENDER=0 but prints
every primitive event, then reports where the grasp failed with ground-truth
geometry (test oracle only).

    python scripts/diag_multipart.py 1 1001
"""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["MUJOCO_GL"] = "egl"
os.environ["PYOPENGL_PLATFORM"] = "egl"
os.environ["AGENT_SUITE"] = os.environ.get("AGENT_SUITE", "libero_bolt_multi")

from agent import executor  # noqa: E402

TASK = int(sys.argv[1]) if len(sys.argv) > 1 else 1
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1001
CODE = sys.argv[3] if len(sys.argv) > 3 else None

code = pathlib.Path(CODE) if CODE else sorted((ROOT / "runs").glob("*multi_final/task.py"))[-1]
run_dir = ROOT / "runs" / "diag" / f"multipart_t{TASK}_s{SEED}"
run_dir.mkdir(parents=True, exist_ok=True)

res = executor.run_episode(code, task_idx=TASK, seed=SEED, run_dir=run_dir,
                           render=False)
print(f"\nsuccess={res.success} steps={res.steps} exit={res.exit_code}")
ev = res.events
for e in ev:
    if e["event"] in ("scan", "pick", "place", "place_retry", "place_retry_skipped",
                      "check", "episode_end", "todo"):
        keep = {k: e[k] for k in ("object", "bin", "grasped", "success", "steps_left") if k in e}
        print(f"  {e['event']:22s} steps={e['steps']:5d} {keep}")
print(f"\ntrace: {run_dir}/trace.jsonl")
