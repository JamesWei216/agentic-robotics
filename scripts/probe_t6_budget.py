#!/usr/bin/env python3
"""Step budget breakdown for one (suite, task, seed) sorting episode.

Wraps Expert.move_to so every leg prints the steps it consumed, then runs the
same sequence the generated code runs (settle -> grasp -> transfer). Used to see
where a 1200-step single-part horizon goes.

    MUJOCO_GL=egl PYTHONPATH=.:/home/wei/work/g05/LIBERO-master \
      /home/wei/work/g05/GalaxeaVLA-main/.venv/bin/python \
      scripts/probe_t6_budget.py libero_bolt_v2 6 1004
"""
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from agent.skills.expert import Expert, EpisodeDone  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    suite_name = sys.argv[1] if len(sys.argv) > 1 else "libero_bolt_v2"
    task_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1004
    pairs = json.loads((ROOT / "config" / "missions.json").read_text())[suite_name][str(task_idx)]
    n_items = max(1, len(pairs))
    suite = get_benchmark_dict()[suite_name]()
    task = suite.get_task(task_idx)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / suite_name / task.bddl_file
    np.random.seed(seed)
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                            horizon=400 + 800 * n_items)
    env.seed(seed)
    env.reset()
    ex = Expert(env)

    def ts():
        return int(getattr(ex.u, "timestep", -1))

    orig = ex.move_to

    def traced(target_pos, target_ori, grip=-1.0, **kw):
        t0 = ts()
        try:
            out = orig(target_pos, target_ori, grip=grip, **kw)
        except EpisodeDone:
            print(f"  leg -> {np.round(np.asarray(target_pos), 3)} TERMINATED at {ts()}")
            raise
        print(f"  leg -> {np.round(np.asarray(target_pos), 3)} grip={grip:+.0f} "
              f"steps={ts() - t0:4d} err={float(out[0])*1000:5.1f}mm kw={kw}")
        return out

    ex.move_to = traced
    for _ in range(30):
        ex.step(np.zeros(3), np.zeros(3), -1.0)
    print(f"after settle t={ts()}")
    for pair in pairs:
        print(f"-- pair {pair}")
        try:
            ok, _ = ex.grasp(pair["object"], verbose=True)
            print(f"   grasp ok={ok} t={ts()}")
            if not ok:
                continue
            ok2, _ = ex.transfer(pair["bin"], verbose=True)
            print(f"   transfer ok={ok2} t={ts()} goal={bool(env.check_success())}")
        except EpisodeDone:
            print(f"   episode terminated at t={ts()} goal={bool(env.check_success())}")
            break
    env.close()


if __name__ == "__main__":
    main()
