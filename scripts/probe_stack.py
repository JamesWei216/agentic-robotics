#!/usr/bin/env python3
"""Probe the stacking expert directly (no agent layer, no LLM).

Answers one question fast: can the scripted primitive grasp the cube and release
it on the target block accurately enough that the native `On` predicate holds?

    MUJOCO_GL=egl PYTHONPATH=<proj>:<LIBERO> python scripts/probe_stack.py --task 5 --seed 1000 --verbose

Same seeding rule as the harness: np.random.seed(seed) BEFORE the env is built
(LIBERO's env.seed() only seeds the simulator, the layout sampler uses the
global numpy RNG — see docs/failures.md A11).
"""
import argparse
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _paths import libero_root  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIBERO = str(libero_root())
sys.path.insert(0, str(ROOT))
sys.path.insert(0, LIBERO)

from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

from agent.skills.expert import Expert  # noqa: E402

SUITE = "libero_wood_stack"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    mission = json.loads((ROOT / "config" / "missions.json").read_text())[SUITE][str(args.task)]
    suite = get_benchmark_dict()[SUITE]()
    task = suite.get_task(args.task)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / SUITE / task.bddl_file

    np.random.seed(args.seed)
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                             horizon=400 + 800 * max(1, len(mission)))
    env.seed(args.seed)
    env.reset()
    ex = Expert(env)
    print(f"task {args.task}: {task.language}")
    print(f"mission: {mission}")

    all_ok = True
    for item in mission:
        obj, base = item["object"], item["on"]
        if args.verbose:
            print(f"  before: {obj} {np.round(ex.body_pos(obj), 4)} "
                  f"| {base} {np.round(ex.body_pos(base), 4)}")
        g_ok, glog = ex.grasp_block(obj, verbose=args.verbose)
        if not g_ok:
            print(f"  GRASP FAILED {obj} phases={[(n, round(e[0], 4)) for n, e in glog]}")
            all_ok = False
            break
        p_ok, plog = ex.place_on_top(base, verbose=args.verbose)
        c, b = ex.body_pos(obj), ex.body_pos(base)
        print(f"  {obj} on {base}: place_ok={p_ok} dxy={np.linalg.norm(c[:2] - b[:2]) * 1000:.1f}mm "
              f"dz={(c[2] - b[2]) * 1000:.1f}mm phases={[(n, round(e[0], 4)) for n, e in plog]}")
        all_ok = all_ok and p_ok

    goal = bool(env.env._check_success())
    print(f"RESULT task={args.task} seed={args.seed} local_ok={all_ok} goal={goal}")
    env.close()
    return 0 if goal else 1


if __name__ == "__main__":
    sys.exit(main())
