#!/usr/bin/env python3
"""Validate the RGB-D perception module against simulator ground truth.

Ground truth is used ONLY as a test oracle here. The perception path itself sees
image + depth + camera calibration.

    python scripts/validate_perception.py [suite] [n_tasks] [n_seeds]
"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

from agent.skills.perception import perceive, validate_against_truth  # noqa: E402

SUITE = sys.argv[1] if len(sys.argv) > 1 else "libero_bolt_v2"
N_TASKS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
N_SEEDS = int(sys.argv[3]) if len(sys.argv) > 3 else 2

suite = get_benchmark_dict()[SUITE]()
all_errs = []
missing = 0
total = 0
for ti in range(min(N_TASKS, suite.n_tasks)):
    task = suite.get_task(ti)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / SUITE / task.bddl_file
    for seed in range(1000, 1000 + N_SEEDS):
        env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256,
                                 camera_widths=256, camera_depths=True)
        env.seed(seed)
        obs = env.reset()
        scene = perceive(obs, env.env.sim)
        truth = {n[:-4]: np.asarray(obs[n]) for n in obs if n.endswith("_pos")
                 and (n.startswith("bolt") or n.startswith("parts_bin"))
                 and "to_robot0" not in n}
        print(f"\n=== {SUITE} t{ti} seed {seed} ({task.bddl_file[:44]}) ===")
        print("  detected:", [(d["id"], d["length_mm"] if "length_mm" in d else d["kind"])
                              for d in scene.summary()])
        errs = validate_against_truth(scene, truth, verbose=False)
        for name, gt in truth.items():
            rec = scene.bolts.get(name)
            if rec is None:
                continue
            d = np.asarray(gt) - rec["center"]
            ax = np.asarray(rec["axis"])
            along = float(d[0] * ax[0] + d[1] * ax[1])
            cross = float(np.hypot(*((d[:2]) - along * ax[:2])))
            print(f"  {name:14s} along={along * 1000:+6.1f} mm cross={cross * 1000:5.1f} mm "
                  f"dz={(d[2]) * 1000:+6.1f}")
        for name, e in errs:
            total += 1
            if e is None:
                missing += 1
            else:
                all_errs.append(e)
        env.close()

arr = np.array(all_errs) * 1000 if all_errs else np.array([0.0])
print(f"\n== summary: {total} objects, {missing} missed, "
      f"mean pos err {arr.mean():.1f} mm, p95 {np.percentile(arr, 95):.1f} mm, "
      f"max {arr.max():.1f} mm")
