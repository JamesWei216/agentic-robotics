#!/usr/bin/env python3
"""Sweep the grasp-point z offset (vision xy) to find where the jaws actually
close on the shank; prints jaw reading per attempt."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

from agent.skills.expert import Expert  # noqa: E402
from agent.skills.perception import perceive  # noqa: E402

SUITE, TASK, SEED = "libero_bolt_v2", int(sys.argv[1]) if len(sys.argv) > 1 else 0, 1000
suite = get_benchmark_dict()[SUITE]()
task = suite.get_task(TASK)
bddl = pathlib.Path(get_libero_path("bddl_files")) / SUITE / task.bddl_file
env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                         horizon=4000, camera_depths=True)
env.seed(SEED)
obs = env.reset()
ex = Expert(env)
last = {"obs": obs}
ex.recorder = lambda o, a: last.__setitem__("obs", o)
scene = perceive(last["obs"], env.env.sim)
ex.vision = scene
name = sys.argv[2] if len(sys.argv) > 2 else ("bolt_large_1" if "bolt_large_1" in scene.bolts else list(scene.bolts)[0])
USE_GT = len(sys.argv) > 3 and sys.argv[3] == "gt"
gp = scene.grasp_point(name)
axis = ex.bolt_axis(name)
ex_axis = axis
ex.vision = None
gt_gp = ex.grasp_point(name)
if USE_GT:
    gp = gt_gp
    axis = ex.bolt_axis(name)
Rg = ex.grasp_orientation(axis, R_cur=ex.ee()[1])
print(f"target {name}: vision gp {np.round(gp, 4)}  truth gp {np.round(gt_gp, 4)}")
ex.vision = None if USE_GT else scene

for dz in (0.000, 0.003, 0.006, 0.009, 0.012):
    tgt = gp + np.array([0, 0, dz])
    ex.move_to(tgt + np.array([0, 0, 0.10]), Rg, grip=-1.0, max_steps=100)
    err = ex.move_to(tgt, Rg, grip=-1.0, tol_p=0.004, max_steps=60)
    for _ in range(35):
        ex.step(np.zeros(3), np.zeros(3), 1.0)
    jaw = float(np.abs(ex.fingers_qpos()).mean())
    print(f"  dz={dz * 1000:+5.1f} mm ee={np.round(ex.ee()[0], 4)} err={err[0]:.4f} jaw={jaw:.4f}")
    ex.set_gripper(-1.0, steps=10)
    ex.move_to(tgt + np.array([0, 0, 0.10]), Rg, grip=-1.0, max_steps=100)
