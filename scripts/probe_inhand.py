#!/usr/bin/env python3
"""Wrist-camera in-hand check: how many steel pixels are visible in the fingers'
field of view for (a) nothing in hand, (b) a bolt in hand?"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

from agent.skills.expert import Expert  # noqa: E402
from agent.skills.perception import segment_masks, perceive  # noqa: E402


def steel_roi(obs, tag):
    img = obs["robot0_eye_in_hand_image"]
    masks = segment_masks(img)
    steel = masks["steel"]
    h, w = steel.shape
    # central band of the wrist view = between the jaws
    roi = steel[int(h * 0.25):int(h * 0.85), int(w * 0.25):int(w * 0.75)]
    print(f"  [{tag}] wrist steel px total={int(steel.sum())} centre-roi={int(roi.sum())}")
    return int(roi.sum())


for task_idx, name in ((0, "bolt_large_1"), (1, "bolt_small_1")):
    suite = get_benchmark_dict()["libero_bolt_v2"]()
    task = suite.get_task(task_idx)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / "libero_bolt_v2" / task.bddl_file
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                             horizon=1200, camera_depths=True)
    env.seed(1000)
    obs = env.reset()
    ex = Expert(env)
    last = {"obs": obs}
    ex.recorder = lambda o, a: last.__setitem__("obs", o)
    print(f"\n== task {task_idx} target {name}")
    steel_roi(last["obs"], "at reset (empty, open)")
    # close jaws on air
    for _ in range(35):
        ex.step(np.zeros(3), np.zeros(3), 1.0)
    steel_roi(last["obs"], "closed on air")
    ex.set_gripper(-1.0, steps=10)
    # now grasp via vision
    scene = perceive(last["obs"], env.env.sim)
    ex.vision = scene
    ex.refresh_vision = lambda: perceive(last["obs"], env.env.sim)
    ok, log = ex.grasp(name, verbose=False)
    steel_roi(last["obs"], f"after grasp ok={ok}")
    print("   jaw:", float(np.abs(ex.fingers_qpos()).mean()))
