#!/usr/bin/env python3
"""Where does the blue bin actually sit during a multi-part episode?

The descend for the second part was blocked by `parts_bin_blue_1`; this script
prints the bin pose after every stage of the episode so we can see when (and by
how much) it moves.
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
from agent.skills.expert import Expert  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def show(ex, tag):
    out = {}
    for b in ("parts_bin_blue_1", "parts_bin_red_1"):
        try:
            out[b] = np.round(ex.body_pos(b), 4).tolist()
        except Exception:
            pass
    for o in ("bolt_small_1", "bolt_small_2"):
        try:
            out[o] = np.round(ex.body_pos(o), 4).tolist()
        except Exception:
            pass
    print(f"{tag:22s} {out}")


def main():
    suite_name = sys.argv[1] if len(sys.argv) > 1 else "libero_bolt_multi"
    task_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
    pairs = json.loads((ROOT / "config" / "missions.json").read_text())[suite_name][str(task_idx)]
    suite = get_benchmark_dict()[suite_name]()
    task = suite.get_task(task_idx)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / suite_name / task.bddl_file
    np.random.seed(seed)
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                            horizon=400 + 800 * max(1, len(pairs)))
    env.seed(seed)
    env.reset()
    ex = Expert(env)
    show(ex, "after reset")
    for _ in range(30):
        ex.step(np.zeros(3), np.zeros(3), -1.0)
    show(ex, "after settle")

    ok, _ = ex.grasp(pairs[0]["object"])
    show(ex, f"after grasp (ok={ok})")
    ok2, _ = ex.transfer(pairs[0]["bin"])
    show(ex, f"after transfer (ok={ok2})")
    home = (ex.ee()[0].copy(), ex.ee()[1].copy())
    ex.move_to(home[0], home[1], grip=-1.0, max_steps=120, speed=0.020)
    show(ex, "after home")
    env.close()


if __name__ == "__main__":
    main()
