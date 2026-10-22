#!/usr/bin/env python3
"""Reset-feasibility sweep: every (task, seed) of a suite must reset cleanly.

    python scripts/check_feasible.py [suite] [n_seeds]

Uses the same seeding order as the agent (np.random.seed(then env.seed) right
before reset) so a failure here means the episode would have failed at reset.
"""
import os
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _paths import libero_root  # noqa: E402

sys.path.insert(0, str(libero_root()))
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

suite_name = sys.argv[1] if len(sys.argv) > 1 else "libero_bolt_v2"
n_seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 10
suite = get_benchmark_dict()[suite_name]()
bad = []
for t in range(suite.n_tasks):
    task = suite.get_task(t)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / suite_name / task.bddl_file
    fails = []
    for s in range(1000, 1000 + n_seeds):
        np.random.seed(s)
        env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=64,
                                 camera_widths=64)
        env.seed(s)
        try:
            env.reset()
        except Exception as exc:                      # noqa: BLE001
            fails.append(s)
        print(f"  t{t} s{s}: {'FAIL' if s in fails else 'ok'}", flush=True)
    if fails:
        bad.append((t, fails))
        print(f"== t{t}: infeasible seeds {fails}", flush=True)
total = suite.n_tasks * n_seeds
n_bad = sum(len(f) for _t, f in bad)
print(f"\n{total - n_bad}/{total} resets clean "
      f"({n_bad} infeasible in {len(bad)} task(s))")
sys.exit(1 if n_bad else 0)
