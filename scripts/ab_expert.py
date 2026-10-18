#!/usr/bin/env python3
"""A/B check: original Expert._run vs the split grasp()+transfer() primitives.

Same task/seed, same controller: the two paths must produce the same success and
a comparable step count. Run with the GalaxeaVLA venv.
"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402
from agent.skills.expert import Expert  # noqa: E402

TASK = int(sys.argv[1]) if len(sys.argv) > 1 else 9
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
BOLT, BIN = ("bolt_large_1", "parts_bin_red_1")


def build():
    suite = get_benchmark_dict()["libero_bolt"]()
    task = suite.get_task(TASK)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / "libero_bolt" / task.bddl_file
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=64, camera_widths=64)
    env.seed(SEED)
    env.reset()
    return env


def count(ex):
    return ex._n if hasattr(ex, "_n") else None


class Counter:
    def __init__(self, ex):
        self.ex, self.n = ex, 0
        ex.recorder = self


def main():
    for mode in ("run", "split"):
        env = build()
        ex = Expert(env)
        n = {"i": 0}

        def rec(obs, a, _n=n):
            _n["i"] += 1

        ex.recorder = rec
        if mode == "run":
            ok, log, grasped = ex.run(BOLT, BIN)
        else:
            g_ok, glog = ex.grasp(BOLT)
            ok, log = ex.transfer(BIN)
            grasped = g_ok
        print(f"{mode:6s} task{TASK} seed{SEED}: success={ok} grasped={grasped} "
              f"steps={n['i']} phases={[(p, round(e[0], 4)) for p, e in log]}")
        env.close()


if __name__ == "__main__":
    main()
