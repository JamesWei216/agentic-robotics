#!/usr/bin/env python3
"""Verbose single-object test of the vision (RGB-D) grasp path."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

from agent.skills.expert import Expert  # noqa: E402
from agent.skills.perception import perceive  # noqa: E402

SUITE = sys.argv[1] if len(sys.argv) > 1 else "libero_bolt_v2"
TASK = int(sys.argv[2]) if len(sys.argv) > 2 else 0
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 1000

suite = get_benchmark_dict()[SUITE]()
task = suite.get_task(TASK)
bddl = pathlib.Path(get_libero_path("bddl_files")) / SUITE / task.bddl_file
env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                        horizon=1200, camera_depths=True)
env.seed(SEED)
obs = env.reset()
ex = Expert(env)

last = {"obs": obs}
ex.recorder = lambda o, a: last.__setitem__("obs", o)


def refresh():
    scene = perceive(last["obs"], env.env.sim)
    ex.vision = scene
    return scene


scene = refresh()
for item in scene.summary():
    print("det:", item)
name = "bolt_large_1" if "bolt_large_1" in scene.bolts else list(scene.bolts)[0]
print("target:", name)
gp_vision = scene.grasp_point(name)
gt_gp = None
ex.vision = None
gt_gp = ex.grasp_point(name)
gt_pos = ex.body_pos(name)
ex.vision = scene
print(f"  vision grasp point {np.round(gp_vision, 4)}")
print(f"  truth  grasp point {np.round(gt_gp, 4)}  (pos {np.round(gt_pos, 4)})")
print(f"  delta {np.round((gp_vision - gt_gp) * 1000, 1)} mm")

ex.refresh_vision = refresh
ok, log = ex.grasp(name, verbose=True)
print("grasp_ok:", ok)
print("  jaw after close:", float(np.abs(ex.fingers_qpos()).mean()))
print("  ee:", np.round(ex.ee()[0], 4))
scene2 = refresh()
print("  after-lift detections:", scene2.summary())
print("  truth pos now:", np.round(ex.body_pos(name), 4))
if ok:
    ok2, log2 = ex.transfer("parts_bin_red_1", verbose=True)
    print("transfer_ok:", ok2)
    print("  truth pos:", np.round(ex.body_pos(name), 4), "success:", env.env._check_success())
