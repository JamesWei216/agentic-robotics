#!/usr/bin/env python3
"""Debug the perception masks: how many pixels each colour class gets, depth range,
and where the GT objects project to in the image."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402
import robosuite.utils.transform_utils as T  # noqa: E402
from robosuite.utils.camera_utils import (  # noqa: E402
    get_camera_intrinsic_matrix, get_camera_extrinsic_matrix)

from agent.skills.perception import segment_masks, rgb_to_hsv, CameraModel  # noqa: E402

SUITE = sys.argv[1] if len(sys.argv) > 1 else "libero_bolt_v2"
TASK = int(sys.argv[2]) if len(sys.argv) > 2 else 0
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 1000

suite = get_benchmark_dict()[SUITE]()
task = suite.get_task(TASK)
bddl = pathlib.Path(get_libero_path("bddl_files")) / SUITE / task.bddl_file
env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                         camera_depths=True)
env.seed(SEED)
obs = env.reset()
img = obs["agentview_image"]
print("obs keys with depth:", [k for k in obs if "depth" in k])
d = obs.get("agentview_depth")
print("depth raw:", None if d is None else (np.asarray(d).shape, float(np.min(d)), float(np.max(d)), float(np.mean(d))))
masks = segment_masks(img)
for k, m in masks.items():
    print(f"mask {k}: {int(m.sum())} px")
h, s, v = rgb_to_hsv(img)
print("hsv ranges: h", np.percentile(h, [5, 50, 95]), "s", np.percentile(s, [5, 50, 95]),
      "v", np.percentile(v, [5, 50, 95]))
sim = env.env.sim
cam = CameraModel(sim, "agentview", 256, 256)
depth = cam.depth_metric(sim, np.asarray(d))
print("metric depth:", float(np.min(depth)), float(np.max(depth)), float(np.mean(depth)))
# project GT positions into pixels
K = cam.K
world2cam = cam.world2cam
for name in ("bolt_small_1", "bolt_large_1", "parts_bin_blue_1", "parts_bin_red_1"):
    p = np.asarray(obs[f"{name}_pos"])
    pc = world2cam @ np.array([p[0], p[1], p[2], 1.0])
    u = K[0, 0] * pc[0] / pc[2] + K[0, 2]
    vv = K[1, 1] * pc[1] / pc[2] + K[1, 2]
    r, c = int(round(vv)), int(round(u))
    ok = 0 <= r < 256 and 0 <= c < 256
    print(f"{name:18s} world {np.round(p,3)} -> pixel (r={r}, c={c}) "
          f"rgb={img[r, c] if ok else 'OOB'} depth={depth[r, c] if ok else -1:.3f} "
          f"dist={(np.linalg.norm(p - np.asarray(sim.data.cam_xpos[sim.model.camera_name2id('agentview')]))):.3f}")
