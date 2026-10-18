#!/usr/bin/env python3
"""Why does the 2nd part's grasp fail in the multi-part suite?

Reproduces the sequence (grasp #1 -> transfer -> grasp #2) with verbose logs and
prints ground-truth geometry (test oracle) around the failing attempt.
"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

from agent.skills.expert import Expert  # noqa: E402

SUITE = "libero_bolt_multi"
TASK = int(sys.argv[1]) if len(sys.argv) > 1 else 1
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1001

suite = get_benchmark_dict()[SUITE]()
task = suite.get_task(TASK)
bddl = pathlib.Path(get_libero_path("bddl_files")) / SUITE / task.bddl_file
np.random.seed(SEED)
env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                         horizon=2000)
env.seed(SEED)
env.reset()
ex = Expert(env)
sim = env.env.sim


def gt(name):
    return np.round(sim.data.body_xpos[env.env.obj_body_id[name]], 4)


for _ in range(30):
    ex.step(np.zeros(3), np.zeros(3), -1.0)

print("all objects:", {n: list(gt(n)) for n in env.env.obj_body_id
                       if n.startswith(("bolt", "parts_bin"))})

for first in ("bolt_small_1", "bolt_small_2"):
    pos = gt(first)
    print(f"\n=== grasp {first} at {list(pos)}")
    ok, log = ex.grasp(first, verbose=True)
    print(f"    -> ok={ok}")
    print("    GT poses after:", {n: list(gt(n)) for n in ("bolt_small_1", "bolt_small_2")})
    if ok:
        ok2, _ = ex.transfer("parts_bin_blue_1", verbose=True)
        print(f"    transfer ok={ok2}")
        print("    GT after transfer:", {n: list(gt(n)) for n in ("bolt_small_1", "bolt_small_2")})
        print("    GT bins:", {n: list(gt(n)) for n in ("parts_bin_blue_1","parts_bin_red_1")})
        print("    jaw:", float(np.abs(ex.fingers_qpos()).mean()), " done:", env.env.done, " pred:", env.env._check_success())
    for _ in range(20):
        ex.step(np.zeros(3), np.zeros(3), -1.0)
